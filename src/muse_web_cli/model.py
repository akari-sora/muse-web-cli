"""Pure page decisions. No browser, no network, no credentials."""

from __future__ import annotations

import re

from dataclasses import dataclass, field

from muse_web_cli.selectors import (
    API_HINT,
    API_UNAVAILABLE,
    BOT_PHRASES,
    CHAT_CHROME,
    CREDENTIAL_HINT,
    CREDENTIAL_HINT_WINDOWS,
    EMPTY_SIDE_CHAT,
    KEY_SELECTORS,
    LOGIN_HINT,
    LOGIN_PHRASES,
    MEMORY_SECTIONS,
    NEW_SIDE_CHAT,
    PANEL_TAB_SELECTORS,
    REGION_PHRASES,
    START_HINT,
    TAB_BY_LABEL,
)

EXIT_OK = 0
EXIT_SETUP = 2
EXIT_PAGE = 3
EXIT_UNSUPPORTED = 4

EXIT_FOR = {
    "ok": EXIT_OK,
    "browser_down": EXIT_SETUP,
    "session_expired": EXIT_SETUP,
    "region_blocked": EXIT_SETUP,
    "credential_permissions": EXIT_SETUP,
    "profile_busy": EXIT_SETUP,
    "ui_changed": EXIT_PAGE,
    "timeout": EXIT_PAGE,
    "unsupported": EXIT_UNSUPPORTED,
}


def exit_for(state: str) -> int:
    return EXIT_FOR.get(state, EXIT_PAGE)


def norm(text: str) -> str:
    return " ".join((text or "").split())


# Muse stores an attached file as a "[file:<mime> <path>]" prefix on the user's text.
_FILE_PREFIX = re.compile(r"^(?:\s*\[file:[^\]\n]*\])+\s*")


def without_files(text: str) -> str:
    return _FILE_PREFIX.sub("", text or "")


@dataclass
class Message:
    role: str
    text: str
    presentation: bool = False
    busy: bool | None = None
    streaming: bool | None = None
    has_actions: bool = False
    typing: bool = False


@dataclass
class Snapshot:
    host: str = ""
    path: str = ""
    has_log: bool = False
    has_composer: bool = False
    has_password: bool = False
    panel_open: bool = False
    gate_text: str = ""
    messages: list[Message] = field(default_factory=list)
    selectors: dict[str, bool] = field(default_factory=dict)


def _phrase(haystack: str, phrases: tuple[str, ...]) -> bool:
    lowered = haystack.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def url_is_login(host: str, path: str) -> bool:
    host = (host or "").lower()
    path = (path or "").lower()
    if "login" in path and ("muse.ai" in host or host.endswith("facebook.com") or host.endswith("meta.com")):
        return True
    if host.endswith("facebook.com") and ("login" in path or path.startswith("/checkpoint")):
        return True
    return False


def include_message(role: str | None, typing: bool) -> bool:
    """Typing indicators carry data-message-item and no data-message-role."""
    if typing:
        return False
    return role in {"user", "assistant"}


def public_message(message: Message) -> dict:
    return {"role": message.role, "text": message.text, "presentation": bool(message.presentation)}


def visible_messages(messages: list[Message]) -> list[Message]:
    return [item for item in messages if include_message(item.role, item.typing)]


def select_messages(messages: list[Message], limit: int) -> list[Message]:
    shown = visible_messages(messages)
    if limit < 1:
        return []
    return shown[-limit:]


def format_lines(messages: list[Message]) -> list[str]:
    return [f"{item.role}: {item.text}" for item in messages]


def latest_assistant(messages: list[Message]) -> Message | None:
    for item in reversed(visible_messages(messages)):
        if item.role == "assistant":
            return item
    return None


def is_settled(message: Message) -> bool:
    """A reply is done when actions are up and it is not still streaming.

    Both flags false with the copy action is the in-flight completion signal.
    After completion Muse removes the attributes, so both missing plus the copy
    action is the same finished state. One flag alone is not done.
    A presentation card is waiting on the user; it is done for reading and is never clicked.
    """
    if message.typing or message.role != "assistant":
        return False
    if message.presentation:
        return True
    if not message.has_actions:
        return False
    if message.busy is True or message.streaming is True:
        return False
    both_false = message.busy is False and message.streaming is False
    both_cleared = message.busy is None and message.streaming is None
    return both_false or both_cleared


def user_count(messages: list[Message], text: str) -> int:
    wanted = norm(text)
    return sum(1 for item in visible_messages(messages) if item.role == "user" and norm(without_files(item.text)) == wanted)


def reply_after(messages: list[Message], text: str) -> list[Message]:
    shown = visible_messages(messages)
    index = -1
    wanted = norm(text)
    for i, item in enumerate(shown):
        if item.role == "user" and norm(without_files(item.text)) == wanted:
            index = i
    if index < 0:
        return []
    return [item for item in shown[index + 1 :] if item.role == "assistant"]


def reply_ready(messages: list[Message], text: str) -> bool:
    tail = reply_after(messages, text)
    if not tail:
        return False
    if any(item.busy is True or item.streaming is True for item in tail):
        return False
    return is_settled(tail[-1])


def reply_text(messages: list[Message], text: str) -> tuple[str, bool] | None:
    tail = reply_after(messages, text)
    if not tail or not reply_ready(messages, text):
        return None
    body = "\n".join(item.text for item in tail if item.text).strip()
    return body, any(item.presentation for item in tail)


def missing_keys(selectors: dict[str, bool], *, panel_open: bool) -> list[str]:
    names = list(KEY_SELECTORS)
    if panel_open:
        names.extend(PANEL_TAB_SELECTORS)
    return [name for name in names if not selectors.get(name)]


def assess(snapshot: Snapshot) -> dict:
    """Login and region win over ui_changed. A live chat ignores gate phrases."""
    chat_up = snapshot.has_log and snapshot.has_composer
    if not chat_up and (url_is_login(snapshot.host, snapshot.path) or snapshot.has_password):
        return _status("session_expired", error="登入工作階段已失效", hint=LOGIN_HINT)
    if not chat_up and _phrase(snapshot.gate_text, LOGIN_PHRASES):
        return _status("session_expired", error="還沒有登入 Muse (not logged in)", hint=LOGIN_HINT)
    if not chat_up and _phrase(snapshot.gate_text, BOT_PHRASES):
        return _status("session_expired", error="頁面要求重新登入或人機驗證", hint=LOGIN_HINT)
    if not chat_up and _phrase(snapshot.gate_text, REGION_PHRASES):
        return _status("region_blocked", error="Muse 在這個地區無法使用", hint=None)
    missing = missing_keys(snapshot.selectors, panel_open=False)
    # Log and composer are the chat surface; the selector map may say the same thing.
    if not snapshot.has_log and "log" not in missing:
        missing = ["log", *missing]
    if not snapshot.has_composer and "composer" not in missing:
        missing = [*missing, "composer"]
    if missing:
        return _status(
            "ui_changed",
            error="Muse 頁面結構對不上",
            hint=None,
            missing=missing,
        )
    last = latest_assistant(snapshot.messages)
    return _status(
        "ok",
        pending=None,
        latest_assistant_is_card=bool(last and last.presentation),
    )


def _status(
    state: str,
    *,
    error: str | None = None,
    hint: str | None = None,
    pending: int | None = None,
    latest_assistant_is_card: bool | None = None,
    missing: list[str] | None = None,
    backend: str = "browser",
    headless: bool | None = None,
) -> dict:
    return {
        "backend": backend,
        "state": state,
        "pending": pending,
        "latest_assistant_is_card": latest_assistant_is_card,
        "headless": headless,
        "error": error,
        "hint": hint,
        "missing": missing or [],
    }


def messages_payload(
    messages: list[Message],
    *,
    backend: str,
    limit: int,
    state: str = "ok",
    error: str | None = None,
    hint: str | None = None,
) -> dict:
    chosen = select_messages(messages, limit) if state == "ok" else []
    public = [public_message(item) for item in chosen]
    return {
        "backend": backend,
        "state": state,
        "name": "Muse",
        "lines": format_lines(chosen) if state == "ok" else [],
        "messages": public,
        "error": error,
        "hint": hint,
    }


def send_payload(
    *,
    backend: str,
    state: str,
    text: str,
    attempted: bool = False,
    sent: bool = False,
    reply: str | None = None,
    presentation: bool | None = None,
    elapsed_ms: int | None = None,
    error: str | None = None,
    hint: str | None = None,
) -> dict:
    return {
        "backend": backend,
        "state": state,
        "attempted": attempted,
        "sent": sent,
        "text": text,
        "reply": reply,
        "presentation": presentation,
        "elapsed_ms": elapsed_ms,
        "error": error,
        "hint": hint,
    }


_CHAT_SKIP = frozenset((*CHAT_CHROME, *NEW_SIDE_CHAT, *EMPTY_SIDE_CHAT))
_PAGE_CHROME = _CHAT_SKIP | frozenset(
    {
        "Muse",
        "Meta Muse",
        "Meta AI",
        "Your Personal AI Agent",
        "副聊天室",
        "Side chats",
    }
)
_PAGE_CHROME_FOLDED = frozenset(item.casefold() for item in _PAGE_CHROME)
_TITLE_SEPS = (" — ", " – ", " - ", " | ", " · ")


def _chrome_label(text: str) -> bool:
    return text in _PAGE_CHROME or text.casefold() in _PAGE_CHROME_FOLDED


def _conversation_title(raw: str | None) -> str | None:
    """A chat name from a heading or document.title. Interface words are not names."""
    text = norm(str(raw or ""))
    if not text or _chrome_label(text):
        return None
    for sep in _TITLE_SEPS:
        if sep not in text:
            continue
        head, _, tail = text.partition(sep)
        head, tail = head.strip(), tail.strip()
        if not head or not tail:
            continue
        head_chrome = _chrome_label(head)
        tail_chrome = _chrome_label(tail)
        if head_chrome and tail_chrome:
            return None
        if head_chrome:
            return _conversation_title(tail)
        if tail_chrome:
            return _conversation_title(head)
        return text
    return text


def _first_conversation_title(values) -> str | None:
    if values is None:
        return None
    items = [values] if isinstance(values, str) else list(values)
    for item in items:
        title = _conversation_title(None if item is None else str(item))
        if title:
            return title
    return None


def shape_chats(
    main_spans: list[str] | None,
    rows: list[dict] | None,
    *,
    page_title: str | None = None,
    outside_titles=None,
) -> list[dict]:
    """Main chat first, then side chats. Empty-state copy and the new-chat control are not chats.

    The main title is a name from the old switcher, a heading outside the sidebar,
    or document.title. Interface labels are left out. None means no name was found.
    """
    spans = [str(item or "").strip() for item in (main_spans or []) if str(item or "").strip()]
    titled = [item for item in spans if item not in _CHAT_SKIP]
    if titled:
        main_title = max(titled, key=len)
    else:
        main_title = _first_conversation_title(outside_titles) or _conversation_title(page_title)
    sides: list[dict] = []
    for row in rows or []:
        if row.get("options"):
            continue
        title = str(row.get("title") or "").strip()
        if not title or title in _CHAT_SKIP:
            continue
        sides.append(
            {
                "title": title,
                "is_current": bool(row.get("current")),
                "kind": "side",
            }
        )
    current_side = any(item["is_current"] for item in sides)
    return [{"title": main_title, "is_current": not current_side, "kind": "main"}, *sides]


def chats_payload(chats: list[dict] | None, *, backend: str, state: str = "ok", error=None, hint=None) -> dict:
    rows = chats or []
    return {
        "backend": backend,
        "state": state,
        "count": len(rows) if state == "ok" else 0,
        "chats": rows if state == "ok" else [],
        "error": error,
        "hint": hint,
    }


def pending_payload(items: list[dict] | None, *, backend: str, state: str = "ok", error=None, hint=None) -> dict:
    rows = items or []
    return {
        "backend": backend,
        "state": state,
        "count": len(rows) if state == "ok" else 0,
        "items": rows if state == "ok" else [],
        "error": error,
        "hint": hint,
    }


def grouped_payload(
    groups: list[dict] | None,
    *,
    backend: str,
    state: str = "ok",
    error=None,
    hint=None,
) -> dict:
    rows = groups or []
    count = sum(len(group.get("items") or []) for group in rows) if state == "ok" else 0
    return {
        "backend": backend,
        "state": state,
        "count": count,
        "groups": rows if state == "ok" else [],
        "error": error,
        "hint": hint,
    }


def memory_payload(
    text: str | None,
    *,
    backend: str,
    state: str = "ok",
    error=None,
    hint=None,
) -> dict:
    body = text or ""
    sections = [name for name in MEMORY_SECTIONS if name in body] if state == "ok" else []
    return {
        "backend": backend,
        "state": state,
        "chars": len(body) if state == "ok" else 0,
        "sections": sections,
        "text": body if state == "ok" else "",
        "error": error,
        "hint": hint,
    }


def unsupported(
    kind: str,
    *,
    backend: str = "api",
    text: str = "",
    error: str | None = None,
    hint: str | None = None,
) -> dict:
    error = API_UNAVAILABLE if error is None else error
    hint = API_HINT if hint is None else hint
    if kind == "status":
        return _status("unsupported", error=error, hint=hint, backend=backend)
    if kind == "messages":
        return messages_payload([], backend=backend, limit=0, state="unsupported", error=error, hint=hint)
    if kind == "send":
        return send_payload(backend=backend, state="unsupported", text=text, error=error, hint=hint)
    if kind == "pending":
        return pending_payload([], backend=backend, state="unsupported", error=error, hint=hint)
    if kind in {"upcoming", "activity"}:
        return grouped_payload([], backend=backend, state="unsupported", error=error, hint=hint)
    if kind == "memory":
        return memory_payload("", backend=backend, state="unsupported", error=error, hint=hint)
    if kind == "chats":
        return chats_payload([], backend=backend, state="unsupported", error=error, hint=hint)
    raise KeyError(kind)


def setup_status(state: str, error: str, hint: str | None, *, backend: str) -> dict:
    return _status(state, error=error, hint=hint, backend=backend)


def credential_loose(*, error: str | None = None, hint: str | None = None) -> dict:
    return setup_status(
        "credential_permissions",
        error or "credential file must be mode 600",
        CREDENTIAL_HINT if hint is None else hint,
        backend="api",
    )


def credential_outside_home() -> dict:
    return credential_loose(
        error="credential file must be inside your home directory",
        hint=CREDENTIAL_HINT_WINDOWS,
    )


def browser_down(error: str, *, hint: str | None = None) -> dict:
    return setup_status("browser_down", error, hint if hint is not None else START_HINT, backend="browser")


def tab_selector(label: str | None) -> str | None:
    if not label:
        return None
    return TAB_BY_LABEL.get(label)


def empty_like(kind: str, status: dict) -> dict:
    """Carry a non-ok page/setup status in the command's stable shape."""
    state = status["state"]
    error = status.get("error")
    hint = status.get("hint")
    backend = status.get("backend", "browser")
    if kind == "status":
        return status
    if kind == "messages":
        return messages_payload([], backend=backend, limit=0, state=state, error=error, hint=hint)
    if kind == "pending":
        return pending_payload([], backend=backend, state=state, error=error, hint=hint)
    if kind in {"upcoming", "activity"}:
        return grouped_payload([], backend=backend, state=state, error=error, hint=hint)
    if kind == "memory":
        return memory_payload("", backend=backend, state=state, error=error, hint=hint)
    if kind == "chats":
        return chats_payload([], backend=backend, state=state, error=error, hint=hint)
    raise KeyError(kind)
