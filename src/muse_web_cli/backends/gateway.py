"""Muse hatch gateway calls, mapped into the CLI payload shapes.

The open page tunnels these routes over Noise. This module does not print the
token, the vm id, or message text from a live session.
"""

from __future__ import annotations

import base64
import inspect
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

from muse_web_cli.backends.noise import DAEMON, SENTINEL, NoiseError, Session
from muse_web_cli.model import (
    Message,
    chats_payload,
    grouped_payload,
    memory_payload,
    messages_payload,
    norm,
    pending_payload,
    reply_text,
    send_payload,
    setup_status,
)
from muse_web_cli.output import safe_text

_GATEWAY_REJECTED = "gateway 拒絕這次操作"
_GATEWAY_HINT = "看 gateway 回的狀態，確認 vm_id 與這項操作。token 不會印出來。"
_NODE = "muse-web-cli"
_SNAPSHOT_WINDOW = 20
_POLL_WINDOW = 50
_CAPS = [
    "chat_cancel",
    "delta_stream",
    "custom_reactions",
    "custom_reactions_facebook_thumbs_up_v1",
]


def _unwrap(parsed: dict) -> dict:
    ok = parsed.get("ok")
    if not isinstance(ok, bool):
        return parsed
    if ok and isinstance(parsed.get("result"), dict):
        return parsed["result"]
    if ok:
        return parsed
    raise GatewayError("ui_changed", _GATEWAY_REJECTED, _GATEWAY_HINT)


class GatewayError(Exception):
    def __init__(self, state: str, error: str, hint: str | None = None):
        super().__init__(error)
        self.state = state
        self.error = error
        self.hint = hint


def _current_path(credential: Path) -> Path:
    return credential.parent / "muse-current.json"


def read_current(credential: Path) -> str | None:
    path = _current_path(credential)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    session_id = data.get("session_id") if isinstance(data, dict) else None
    if isinstance(session_id, str) and session_id.strip():
        return session_id.strip()
    return None


def write_current(credential: Path, session_id: str) -> None:
    path = _current_path(credential)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"session_id": session_id}, ensure_ascii=False).encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload)
        try:
            os.fchmod(fd, 0o600)
        except (AttributeError, OSError):
            pass
    finally:
        os.close(fd)
    os.replace(temporary, path)


def clear_current(credential: Path) -> None:
    try:
        _current_path(credential).unlink()
    except FileNotFoundError:
        return


def _role(value: object) -> str | None:
    text = str(value or "").lower()
    if text in {"user", "human"}:
        return "user"
    if text in {"assistant", "bot", "model"}:
        return "assistant"
    return None


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    if isinstance(value, dict):
        return str(value.get("text") or value.get("content") or "")
    return ""


def _message_rows(data: dict) -> list[dict]:
    events = data.get("chat_events")
    if isinstance(events, list):
        return [item for item in events if isinstance(item, dict)]
    if isinstance(data.get("messages"), list):
        return [item for item in data["messages"] if isinstance(item, dict)]
    by_id = data.get("messages_by_id") or data.get("messagesById")
    if isinstance(by_id, dict):
        order = data.get("message_ids") or data.get("messageIds") or list(by_id)
        rows = []
        for key in order:
            row = by_id.get(key) if isinstance(key, str) else None
            if isinstance(row, dict):
                rows.append(row)
        return rows
    for key in ("items", "history"):
        if isinstance(data.get(key), list):
            return [item for item in data[key] if isinstance(item, dict)]
    return []


def _history_query(limit: int, session: str | None) -> dict:
    query = {"limit": str(limit), "transcript_mode": "messages"}
    if session:
        query["session_id"] = session
    return query


def _public_messages(rows: list) -> list[Message]:
    found: list[Message] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("role") not in {"user", "assistant"}:
            continue
        text = row.get("text") if isinstance(row.get("text"), str) else ""
        found.append(
            Message(
                role=row["role"],
                text=text,
                presentation=bool(row.get("presentation")),
                has_actions=True,
            )
        )
    return found


def _same(before: Message, after: Message, *, growing: bool) -> bool:
    if before.role != after.role:
        return False
    old, new = norm(before.text), norm(after.text)
    return new.startswith(old) if growing else new == old


def _fresh_start(prior: list[Message], rows: list[Message]) -> int | None:
    """Index in rows of the first message newer than the pre-send window.

    Both reads return only the latest messages, so positions shift once the chat
    is longer than a window. The windows are lined up by content instead. The
    last pre-send message may still have been streaming, so it only has to be a
    prefix. None means the windows do not line up and nothing counts as new.
    """
    if not prior:
        return 0
    for size in range(len(prior), 0, -1):
        tail = prior[-size:]
        starts = range(len(rows) - size + 1) if size == len(prior) else range(1)
        for start in starts:
            window = rows[start : start + size]
            if len(window) == size and all(
                _same(old, new, growing=index == size - 1) for index, (old, new) in enumerate(zip(tail, window))
            ):
                return start + size
    return None


def _new_reply(prior: list, rows: list, text: str) -> tuple[str, bool] | None:
    """A settled assistant reply to text that was not in the pre-send snapshot."""
    after = _public_messages(rows)
    start = _fresh_start(_public_messages(prior), after)
    if start is None:
        return None
    ready = reply_text(after[start:], text)
    if ready is None or not ready[0]:
        return None
    return ready


def messages_from(data: dict) -> list[Message]:
    found: list[Message] = []
    for row in _message_rows(data):
        role = _role(row.get("role"))
        if role is None:
            role = _event_role(row.get("event_name"))
        if role is None:
            continue
        text = _event_text(row)
        presentation = bool(row.get("presentation") or row.get("card"))
        found.append(Message(role=role, text=text, presentation=presentation, has_actions=True))
    return found


def _event_role(value: object) -> str | None:
    text = str(value or "")
    if text.endswith(".user"):
        return "user"
    if text.endswith(".assistant"):
        return "assistant"
    return None


def _event_text(row: dict) -> str:
    for key in ("text", "display_text", "content", "body"):
        if row.get(key) is not None:
            text = _text(row.get(key))
            if text:
                return text
    payload = row.get("payload")
    if isinstance(payload, dict):
        for key in ("display_text", "text", "content", "body"):
            if payload.get(key) is not None:
                text = _text(payload.get(key))
                if text:
                    return text
    return ""


def _title(row: dict) -> str:
    for key in ("title", "name", "display_name"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _chat_rows(data: dict) -> list[dict]:
    rows = data.get("sessions") if isinstance(data.get("sessions"), list) else data.get("chats")
    if not isinstance(rows, list):
        return []
    return [item for item in rows if isinstance(item, dict)]


def _chat_id(item: dict) -> str | None:
    for key in ("session_id", "id", "chat_id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _primary(rows: list[dict]) -> dict | None:
    return next((item for item in rows if item.get("is_primary") or item.get("kind") == "main"), None)


def _listed(data: dict, session: str | None, *, action: str) -> None:
    """rename and delete take only an id that chats prints. The main chat is never deleted."""
    rows = _chat_rows(data)
    primary = _primary(rows)
    if action == "delete" and (session == "main" or (primary is not None and _chat_id(primary) == session)):
        raise GatewayError("ui_changed", "主聊天室不能刪。", "只刪 chats 列出的副聊天室。沒有送出刪除。")
    if not session or session not in {item_id for item in rows if (item_id := _chat_id(item))}:
        raise GatewayError(
            "ui_changed",
            "找不到這個聊天室。",
            f"先執行 chats，再用列出的 id --{action}。沒有送出。",
        )


def chats_from(data: dict, *, current: str | None) -> list[dict]:
    parsed = _chat_rows(data)
    primary = _primary(parsed)
    ordered = []
    if primary is not None:
        ordered.append(primary)
    ordered.extend(item for item in parsed if item is not primary)
    chats = []
    for item in ordered:
        session_id = _chat_id(item)
        kind = "main" if item is primary or item.get("kind") == "main" or item.get("is_primary") else "side"
        if item.get("is_thread") is True:
            kind = "side"
        title = _title(item) or ("聊天室" if kind == "main" else "副聊天室")
        is_current = session_id == current if current else kind == "main"
        row = {"title": title, "is_current": is_current, "kind": kind}
        if session_id:
            row["session_id"] = session_id
        chats.append(row)
    if not chats:
        chats.append({"title": "聊天室", "is_current": current is None, "kind": "main"})
    return chats


def _groups(title: str, items: list[dict]) -> list[dict]:
    return [{"title": title, "items": items}] if items else []


def upcoming_from(data: dict) -> list[dict]:
    if isinstance(data.get("groups"), list):
        return [item for item in data["groups"] if isinstance(item, dict)]
    raw = data.get("schedules") or data.get("tasks") or data.get("items") or []
    items = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        when = row.get("time") or row.get("next_run") or row.get("schedule") or row.get("cron") or row.get("schedule_key") or ""
        if row.get("next_run_at_utc") is not None:
            stamp = str(row.get("next_run_at_utc"))
            when = f"{when} {stamp}".strip() if when else stamp
        items.append(
            {
                "name": _title(row) or str(row.get("id") or row.get("prompt") or ""),
                "time": str(when),
            }
        )
    return _groups("排程", items)


def activity_from(data: dict) -> list[dict]:
    if isinstance(data.get("groups"), list):
        return [item for item in data["groups"] if isinstance(item, dict)]
    days = data.get("days") or data.get("events") or data.get("items") or []
    groups = []
    if isinstance(days, list) and days and isinstance(days[0], dict) and (
        "activities" in days[0] or "items" in days[0] or "events" in days[0]
    ):
        for day in days:
            if not isinstance(day, dict):
                continue
            raw = day.get("activities") or day.get("items") or day.get("events") or []
            items = []
            for row in raw if isinstance(raw, list) else []:
                if isinstance(row, dict):
                    items.append(_activity_item(row))
            groups.append({"title": str(day.get("title") or day.get("date") or ""), "items": items})
        return groups
    items = []
    for row in days if isinstance(days, list) else []:
        if isinstance(row, dict):
            items.append(_activity_item(row))
    return _groups("動態", items)


def _activity_item(row: dict) -> dict:
    return {
        "title": _title(row),
        "detail": str(row.get("detail") or row.get("summary") or row.get("type") or ""),
        "time": str(row.get("time") or row.get("timestamp") or row.get("at") or ""),
    }


def pending_from(data: dict) -> list[dict]:
    raw = data.get("pending_approvals")
    if not isinstance(raw, list):
        raw = data.get("items") or data.get("approvals") or data.get("pending") or []
    items = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        title = _title(row) or str(row.get("display_name") or "")
        when = row.get("time") or row.get("created_at") or row.get("requested_at_ms") or ""
        items.append(
            {
                "title": title,
                "detail": str(row.get("detail") or row.get("summary") or row.get("reason") or ""),
                "time": str(when),
            }
        )
    return items


def memory_text(data: dict) -> str:
    for key in ("text", "content", "memory", "markdown", "body"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return ""


def _accepts_first(fn) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    if "accept_first" in params:
        return True
    return any(item.kind == inspect.Parameter.VAR_KEYWORD for item in params.values())


class MuseGateway:
    def __init__(self, config: dict, *, credential: Path, session=None, sleep=None):
        self.config = config
        self.credential = credential
        self.sleep = sleep or time.sleep
        self._session = session
        self._owned = session is None

    def close(self) -> None:
        if self._owned and self._session is not None:
            self._session.close()

    def status(self) -> dict:
        def run():
            self._json(DAEMON, "GET", "/health")
            approvals = self._json(SENTINEL, "GET", "/approvals")
            history = self._json(DAEMON, "GET", "/chat/history", query=_history_query(5, self._pick(None)))
            rows = messages_from(history)
            last = next((item for item in reversed(rows) if item.role == "assistant"), None)
            return {
                "backend": "api",
                "state": "ok",
                "pending": len(pending_from(approvals)),
                "latest_assistant_is_card": bool(last and last.presentation),
                "headless": None,
                "error": None,
                "hint": None,
                "missing": [],
            }

        return self._guard("status", run)

    def messages(self, limit: int, *, session: str | None = None) -> dict:
        def run():
            chosen = self._pick(session)
            data = self._json(DAEMON, "GET", "/chat/history", query=_history_query(limit, chosen))
            return messages_payload(messages_from(data), backend="api", limit=limit)

        return self._guard("messages", run)

    def send(self, text: str, *, wait: bool, timeout: float, session: str | None = None) -> dict:
        started = time.monotonic()
        chosen = self._pick(session)
        prior: list = []
        if wait:
            snap = self.messages(_SNAPSHOT_WINDOW, session=chosen or "main")
            if snap.get("state") != "ok" or not isinstance(snap.get("messages"), list):
                return send_payload(
                    backend="api",
                    state=str(snap.get("state") or "ui_changed"),
                    text=text,
                    error=snap.get("error") if isinstance(snap.get("error"), str) else None,
                    hint=snap.get("hint") if isinstance(snap.get("hint"), str) else None,
                )
            prior = snap["messages"]

        def once():
            body = {
                "items": [{"type": "text", "text": text}],
                "node_id": _NODE,
                "capabilities": _CAPS,
            }
            if chosen:
                body["session_id"] = chosen
            self._json(DAEMON, "POST", "/chat/stream", body=body, accept_first=True)
            return send_payload(backend="api", state="ok", text=text, attempted=True, sent=True)

        first = self._guard("send", once, text=text)
        if first.get("state") == "timeout":
            first["attempted"] = True
            first["sent"] = False
            first["hint"] = "沒有再送一次"
        if not wait or first.get("state") != "ok":
            return first
        return self.wait_reply(text, first=first, prior=prior, session=chosen, timeout=timeout, started=started)

    def wait_reply(self, text: str, *, first: dict, prior: list, session: str | None, timeout: float, started: float) -> dict:
        """Poll until a settled reply to `text` that was not in `prior` arrives. Never sends."""
        chosen = session
        gap = 0.2
        while time.monotonic() - started < timeout:
            remaining = timeout - (time.monotonic() - started)
            polled = self.messages(_POLL_WINDOW, session=chosen or "main")
            state = str(polled.get("state") or "ui_changed")
            if state == "timeout" and time.monotonic() - started < timeout:
                # A long reply can keep the send stream quiet past timeout_s.
                self.sleep(min(gap, max(0.0, timeout - (time.monotonic() - started))))
                gap = min(gap * 2, 2.0)
                continue
            if state != "ok":
                first["state"] = state
                first["error"] = polled.get("error")
                first["hint"] = "沒有再送一次" if state == "timeout" else polled.get("hint")
                return first
            rows = polled.get("messages") if isinstance(polled.get("messages"), list) else []
            ready = _new_reply(prior, rows, text)
            if ready:
                body, presentation = ready
                first["reply"] = body
                first["presentation"] = presentation
                first["elapsed_ms"] = int((time.monotonic() - started) * 1000)
                return first
            self.sleep(min(gap, max(0.0, remaining)))
            gap = min(gap * 2, 2.0)
        first["state"] = "timeout"
        first["error"] = "等待逾時"
        first["hint"] = "沒有再送一次"
        return first

    def pending(self) -> dict:
        def run():
            data = self._json(SENTINEL, "GET", "/approvals")
            return pending_payload(pending_from(data), backend="api")

        return self._guard("pending", run)

    def upcoming(self) -> dict:
        def run():
            data = self._json(DAEMON, "GET", "/tasks")
            return grouped_payload(upcoming_from(data), backend="api")

        return self._guard("upcoming", run)

    def activity(self) -> dict:
        def run():
            data = self._json(DAEMON, "GET", "/activity", query={"limit": "30", "capabilities": "ACTIVITY_FEED_GOALS"})
            return grouped_payload(activity_from(data), backend="api")

        return self._guard("activity", run)

    def memory(self) -> dict:
        def run():
            text = self._read_memory()
            return memory_payload(text, backend="api")

        return self._guard("memory", run)

    def chats(self, *, action: str | None = None, session: str | None = None, title: str | None = None) -> dict:
        def run():
            if action == "create":
                created = self._json(DAEMON, "POST", "/api/chats/start", body={})
                new_id = _chat_id(created)
                if not new_id:
                    raise GatewayError(
                        "ui_changed",
                        "沒有拿到新聊天室的 id。",
                        "聊天可能已建立。再執行 chats，用列出的 id。",
                    )
                self._json(
                    DAEMON,
                    "POST",
                    "/session/rename",
                    body={"session_id": new_id, "title": title or "新聊天"},
                )
                write_current(self.credential, new_id)
            elif action == "rename":
                _listed(self._json(DAEMON, "GET", "/api/session/list"), session, action="rename")
                self._json(
                    DAEMON,
                    "POST",
                    "/session/rename",
                    body={"session_id": session, "title": title or ""},
                )
            elif action == "delete":
                _listed(self._json(DAEMON, "GET", "/api/session/list"), session, action="delete")
                self._json(
                    DAEMON,
                    "POST",
                    "/session/delete",
                    body={"method": "/api/session/delete", "session_id": session},
                )
                if read_current(self.credential) == session:
                    clear_current(self.credential)
            data = self._json(DAEMON, "GET", "/api/session/list")
            if action == "switch":
                target = None if session in {None, "", "main"} else session
                known = {item_id for item in _chat_rows(data) if (item_id := _chat_id(item))}
                if target and target not in known:
                    raise GatewayError(
                        "ui_changed",
                        "找不到這個聊天室。",
                        "先執行 chats，再用列出的 id --switch。--switch main 回到主聊天。",
                    )
                if target:
                    write_current(self.credential, target)
                else:
                    clear_current(self.credential)
            current = read_current(self.credential)
            return chats_payload(chats_from(data, current=current), backend="api")

        return self._guard("chats", run)

    def _read_memory(self) -> str:
        offset = 0
        chunks: list[bytes] = []
        limit = 1024 * 1024
        while offset < limit:
            size = min(262144, limit - offset)
            data = self._json(
                DAEMON,
                "POST",
                "/fs/read",
                body={"path": "MEMORY.md", "offset": offset, "len": size},
            )
            raw = data.get("data_base64") if isinstance(data.get("data_base64"), str) else ""
            if raw:
                try:
                    piece = base64.b64decode(raw, validate=False)
                except (ValueError, TypeError) as exc:
                    raise GatewayError("ui_changed", "記憶檔不是可讀的內容。", "確認 MEMORY.md 還在。") from exc
            else:
                piece = memory_text(data).encode("utf-8")
            chunks.append(piece)
            got = data.get("len") if isinstance(data.get("len"), int) and data.get("len") >= 0 else len(piece)
            if got < size or not piece:
                break
            offset += got
        return b"".join(chunks).decode("utf-8", "replace")

    def _pick(self, session: str | None) -> str | None:
        if session == "main":
            return None
        if session:
            return session
        return read_current(self.credential)

    def _session_call(self):
        if self._session is None:
            self._session = Session(
                self.config["base_url"],
                vm_id=self.config["vm_id"],
                token=self.config["token"],
                app_id=self.config["app_id"],
                notary_token=self.config.get("notary_token"),
                timeout=self.config["timeout_s"],
            )
        return self._session

    def _json(self, service: str, verb: str, path: str, *, body: dict | None = None, query: dict | None = None, accept_first: bool = False) -> dict:
        if query:
            path = f"{path}?{urlencode(query)}"
        raw = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        session = self._session_call()
        kwargs = {"body": raw}
        if accept_first and _accepts_first(session.call):
            kwargs["accept_first"] = True
        try:
            status, payload = session.call(service, verb, path, **kwargs)
        except TimeoutError as exc:
            raise GatewayError("timeout", "等待逾時", "沒有再送一次" if path.startswith("/chat/stream") else "再試一次。沒有重送。") from exc
        except NoiseError as exc:
            raise GatewayError("ui_changed", "連不到 gateway", "檢查 base_url 與 vm_id。token 不會印出來。") from exc
        except OSError as exc:
            raise GatewayError("ui_changed", safe_text(str(exc)) or "連不到 gateway", "檢查 base_url 與 vm_id。") from exc
        if status in {401, 403}:
            raise GatewayError("session_expired", "憑證被拒絕", "在 Chrome 重新登入 Muse，再執行 muse-web-cli credential。這個工具不會印出 token。")
        if status >= 400:
            raise GatewayError("ui_changed", _GATEWAY_REJECTED, _GATEWAY_HINT)
        if not payload:
            return {}
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            if path.split("?", 1)[0] == "/chat/stream":
                return {}
            raise GatewayError("ui_changed", "回應不是 JSON", "檢查 base_url 是不是 hatch gateway。") from exc
        if not isinstance(parsed, dict):
            if path.split("?", 1)[0] == "/chat/stream":
                return {}
            raise GatewayError("ui_changed", "回應不是 JSON 物件", None)
        return _unwrap(parsed)

    def _guard(self, kind: str, fn, text: str = ""):
        try:
            return fn()
        except GatewayError as exc:
            hint = exc.hint
            if kind == "send" and exc.state == "timeout":
                hint = "沒有再送一次"
            status = setup_status(exc.state, exc.error, hint, backend="api")
            if kind == "status":
                return status
            if kind == "send":
                return send_payload(
                    backend="api",
                    state=exc.state,
                    text=text,
                    attempted=exc.state == "timeout",
                    sent=False,
                    error=exc.error,
                    hint=hint,
                )
            from muse_web_cli.model import empty_like

            return empty_like(kind, status)
