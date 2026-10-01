"""JSON and text output. Error strings are scrubbed. Message text is not."""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit, urlunsplit

from muse_web_cli.model import exit_for

_WS = re.compile(r"wss?://\S+")
_HTTP = re.compile(r"https?://\S+")
_SECRET = re.compile(r"(?i)\b(cookie|csrf|csrf-token|token|authorization|set-cookie)\b\s*[:=]\s*\S+")


def strip_query(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return "https://redacted"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def safe_text(text: str) -> str:
    text = _WS.sub("ws://redacted", text or "")
    text = _HTTP.sub(lambda match: strip_query(match.group(0)), text)
    text = _SECRET.sub(r"\1=<redacted>", text)
    return text[:800]


def dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _error_lines(payload: dict) -> list[str]:
    lines = [f"state={payload.get('state')}"]
    if payload.get("error"):
        lines.append(f"error={payload['error']}")
    if payload.get("hint"):
        lines.append(f"hint={payload['hint']}")
    missing = payload.get("missing") or []
    if missing:
        lines.append("missing=" + ",".join(missing))
    return lines


def human(payload: dict) -> str:
    if "action" in payload and "tracked" in payload:
        lines = [
            f"action={payload.get('action')} port={payload.get('port')} "
            f"headless={payload.get('headless')} tracked={str(payload.get('tracked')).lower()} "
            f"logged_in={payload.get('logged_in')}"
        ]
        if payload.get("error"):
            lines.append(f"error={payload['error']}")
        if payload.get("hint"):
            lines.append(f"hint={payload['hint']}")
        return "\n".join(lines)
    if payload.get("state") != "ok":
        return "\n".join(_error_lines(payload))
    if "lines" in payload and "messages" in payload and "name" in payload:
        lines = [f"{payload.get('name', 'Muse')} messages={len(payload.get('messages') or [])}"]
        lines.extend(payload.get("lines") or [])
        return "\n".join(lines)
    if "reply" in payload and "sent" in payload:
        if payload.get("reply") is None:
            return f"sent={str(payload.get('sent')).lower()}"
        return str(payload.get("reply") or "")
    if "sections" in payload and "chars" in payload:
        sections = ",".join(payload.get("sections") or [])
        body = payload.get("text") or ""
        return f"chars={payload.get('chars')} sections={sections}\n{body}".rstrip()
    if "groups" in payload:
        lines = [f"count={payload.get('count')} groups={len(payload.get('groups') or [])}"]
        for group in payload.get("groups") or []:
            lines.append(f"[{group.get('title') or ''}]")
            for item in group.get("items") or []:
                if "name" in item:
                    lines.append(f"- {item.get('name') or ''} | {item.get('time') or ''}")
                else:
                    lines.append(
                        f"- {item.get('title') or ''} | {item.get('detail') or ''} | {item.get('time') or ''}"
                    )
        return "\n".join(lines)
    if "chats" in payload and "count" in payload:
        lines = [f"count={payload.get('count')}"]
        for chat in payload.get("chats") or []:
            mark = " current" if chat.get("is_current") else ""
            session_id = chat.get("session_id")
            suffix = f" id={session_id}" if session_id else ""
            lines.append(f"- {chat.get('kind')}{mark}: {chat.get('title') or ''}{suffix}")
        return "\n".join(lines)
    if "items" in payload and "count" in payload:
        lines = [f"count={payload.get('count')}"]
        for item in payload.get("items") or []:
            lines.append(f"- {item.get('title') or ''} | {item.get('detail') or ''} | {item.get('time') or ''}")
        return "\n".join(lines)
    if "present" in payload:
        missing = ",".join(payload.get("missing") or []) or "-"
        return f"state=ok missing={missing}"
    card = payload.get("latest_assistant_is_card")
    return (
        f"state=ok backend={payload.get('backend')} pending={payload.get('pending')} "
        f"latest_assistant_is_card={str(bool(card)).lower()}"
    )


def emit(payload: dict, *, as_json: bool) -> int:
    if as_json:
        print(dumps(payload))
    else:
        print(human(payload))
    return exit_for(str(payload.get("state")))
