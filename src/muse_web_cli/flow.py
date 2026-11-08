"""Capability flows shared by headed and headless sessions."""

from __future__ import annotations

import re
import time

from dataclasses import dataclass

from muse_web_cli.errors import BrowserDown, PageChanged
from muse_web_cli.model import (
    Message,
    Snapshot,
    assess,
    browser_down,
    chats_payload,
    empty_like,
    memory_payload,
    shape_chats,
    messages_payload,
    pending_payload,
    reply_text,
    send_payload,
    user_count,
    grouped_payload,
    missing_keys,
    _status,
)
from muse_web_cli.nav import read_chats_flow, read_memory_flow, read_with_tab
from muse_web_cli.selectors import TAB_ACTIVITY, TAB_IDENTITY, TAB_PENDING, TAB_UPCOMING


@dataclass
class WaitResult:
    timed_out: bool
    phase: str
    messages: list[Message]


def _fail(kind: str, status: dict) -> dict:
    if kind == "status":
        return status
    if kind == "send":
        return send_payload(
            backend=status.get("backend", "browser"),
            state=status["state"],
            text="",
            error=status.get("error"),
            hint=status.get("hint"),
        )
    return empty_like(kind, status)


def _page_error(kind: str, missing: str) -> dict:
    status = _status("ui_changed", error="Muse 頁面結構對不上", missing=[missing])
    return _fail(kind, status)


SETTLE_SECONDS = 8.0
SETTLE_STEP = 0.5


def _blank(snap: Snapshot, status: dict) -> bool:
    return (
        status["state"] == "ui_changed"
        and not snap.has_log
        and not snap.has_composer
        and not any(snap.selectors.values())
    )


def settled_snapshot(driver, *, sleep=None, clock=None) -> tuple[Snapshot, dict]:
    """A just-started Chrome may not have rendered anything we know yet."""
    sleep = sleep or time.sleep
    clock = clock or time.monotonic
    snap = driver.snapshot()
    status = assess(snap)
    deadline = clock() + SETTLE_SECONDS
    while _blank(snap, status) and clock() < deadline:
        sleep(SETTLE_STEP)
        snap = driver.snapshot()
        status = assess(snap)
    return snap, status


def collect_status(driver) -> dict:
    snap, status = settled_snapshot(driver)
    if status["state"] != "ok":
        return status
    try:
        groups = driver.read_groups(TAB_PENDING)
    except PageChanged as exc:
        return _page_error("status", exc.missing)
    count = sum(len(group.get("items") or []) for group in groups)
    status["pending"] = count
    return status


def collect_messages(driver, limit: int) -> dict:
    snap, status = settled_snapshot(driver)
    if status["state"] != "ok":
        return empty_like("messages", status)
    return messages_payload(snap.messages, backend="browser", limit=limit)


# A side chat page (muse.ai/thread/<id>) has the log and composer but not the main chat's
# status-panel avatar or chat switcher; sending needs only the first two.
SIDE_CHAT_ABSENT = frozenset({"avatar", "switcher"})


def perform_send(driver, text: str, *, wait: bool, timeout: float, attach: list[str] | None = None, side_chat: bool = False) -> dict:
    """Insert the draft once (with any attachments), press Enter once, then wait. A timeout does not send again."""
    started = time.monotonic()
    snap, status = settled_snapshot(driver)
    if (side_chat and status["state"] == "ui_changed" and snap.has_log and snap.has_composer
            and set(status.get("missing") or []) <= SIDE_CHAT_ABSENT):
        status = {**status, "state": "ok"}
    if status["state"] != "ok":
        return send_payload(
            backend="browser",
            state=status["state"],
            text=text,
            error=status.get("error"),
            hint=status.get("hint"),
        )
    before = user_count(snap.messages, text)
    try:
        if attach:
            driver.attach_files(attach)
        driver.insert_text(text)
        driver.press_enter()
    except PageChanged as exc:
        if attach and exc.missing != "composer_not_empty":
            driver.clear_attachments()
        error = ("composer is not empty; nothing was sent" if exc.missing == "composer_not_empty"
                 else "the file did not attach; nothing was sent" if exc.missing == "attachment" else "Muse 頁面結構對不上")
        return send_payload(
            backend="browser",
            state="ui_changed",
            text=text,
            attempted=False,
            sent=False,
            error=error,
            hint=None,
        )
    # Enter was pressed: from here on, losing the page means the message may have been sent.
    try:
        outcome = driver.wait_outcome(text=text, before_count=before, wait=wait, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — any failure after Enter is "unknown", never "not sent"
        return send_payload(
            backend="browser",
            state="timeout",
            text=text,
            attempted=True,
            sent=False,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            error=f"lost the page after Enter ({type(exc).__name__}); the message may have been sent",
            hint="nothing was sent again",
        )
    elapsed = int((time.monotonic() - started) * 1000)
    if outcome.phase == "missing":
        return send_payload(
            backend="browser",
            state="ui_changed",
            text=text,
            attempted=True,
            sent=False,
            elapsed_ms=elapsed,
            error="Muse 頁面結構對不上",
            hint=None,
        )
    arrived = user_count(outcome.messages, text) > before
    if not arrived:
        return send_payload(
            backend="browser",
            state="timeout",
            text=text,
            attempted=True,
            sent=False,
            elapsed_ms=elapsed,
            error="timed out waiting for the sent message to appear",
            hint="nothing was sent again",
        )
    if not wait:
        return send_payload(
            backend="browser",
            state="ok",
            text=text,
            attempted=True,
            sent=True,
            elapsed_ms=elapsed,
        )
    ready = reply_text(outcome.messages, text)
    if outcome.timed_out or ready is None:
        return send_payload(
            backend="browser",
            state="timeout",
            text=text,
            attempted=True,
            sent=True,
            elapsed_ms=elapsed,
            error="timed out waiting for the assistant reply",
            hint="nothing was sent again",
        )
    body, presentation = ready
    return send_payload(
        backend="browser",
        state="ok",
        text=text,
        attempted=True,
        sent=True,
        reply=body,
        presentation=presentation,
        elapsed_ms=elapsed,
    )


def _groups(driver, target: str, kind: str) -> list[dict] | dict:
    snap = driver.snapshot()
    status = assess(snap)
    if status["state"] != "ok":
        return _fail(kind, status)
    try:
        return driver.read_groups(target)
    except PageChanged as exc:
        return _page_error(kind, exc.missing)


def _rows(groups: list[dict]) -> list[dict]:
    rows = []
    for group in groups:
        rows.extend(group.get("items") or [])
    return rows


def collect_pending(driver) -> dict:
    groups = _groups(driver, TAB_PENDING, "pending")
    if isinstance(groups, dict):
        return groups
    items = [
        {"title": row.get("title") or "", "detail": row.get("detail") or "", "time": row.get("time") or ""}
        for row in _rows(groups)
    ]
    return pending_payload(items, backend="browser")


def collect_upcoming(driver) -> dict:
    groups = _groups(driver, TAB_UPCOMING, "upcoming")
    if isinstance(groups, dict):
        return groups
    shaped = []
    for group in groups:
        items = [
            {"name": row.get("title") or "", "time": row.get("time") or row.get("detail") or ""}
            for row in group.get("items") or []
        ]
        shaped.append({"title": group.get("title") or "", "items": items})
    return grouped_payload(shaped, backend="browser")


def collect_activity(driver) -> dict:
    groups = _groups(driver, TAB_ACTIVITY, "activity")
    if isinstance(groups, dict):
        return groups
    shaped = []
    for group in groups:
        items = [
            {
                "title": row.get("title") or "",
                "detail": row.get("detail") or "",
                "time": row.get("time") or "",
            }
            for row in group.get("items") or []
        ]
        shaped.append({"title": group.get("title") or "", "items": items})
    return grouped_payload(shaped, backend="browser")


def collect_chats(driver) -> dict:
    snap = driver.snapshot()
    status = assess(snap)
    if status["state"] != "ok":
        return empty_like("chats", status)
    try:
        raw = driver.read_chats()
    except PageChanged as exc:
        if exc.hint:
            return chats_payload(
                [],
                backend="browser",
                state="ui_changed",
                error=exc.error,
                hint=exc.hint,
            )
        return _page_error("chats", exc.missing)
    chats = shape_chats(
        raw.get("mainSpans"),
        raw.get("rows"),
        page_title=raw.get("pageTitle"),
        outside_titles=raw.get("outsideTitles"),
    )
    return chats_payload(chats, backend="browser")


def collect_memory(driver) -> dict:
    snap = driver.snapshot()
    status = assess(snap)
    if status["state"] != "ok":
        return empty_like("memory", status)
    try:
        text = driver.read_memory()
    except PageChanged as exc:
        return _page_error("memory", exc.missing)
    return memory_payload(text, backend="browser")


def collect_selftest(driver) -> dict:
    snap = driver.snapshot()
    status = assess(snap)
    present = dict(snap.selectors)
    if status["state"] in {"session_expired", "region_blocked"}:
        payload = dict(status)
        payload["present"] = present
        return payload
    extra = missing_keys(snap.selectors, panel_open=snap.panel_open)
    missing = list(dict.fromkeys([*(status.get("missing") or []), *extra]))
    if missing:
        payload = _status("ui_changed", error="Muse 頁面結構對不上", missing=missing)
        payload["present"] = present
        return payload
    payload = dict(status)
    payload["present"] = present
    payload["missing"] = []
    return payload


def message_from_raw(raw: dict) -> Message:
    role = str(raw.get("role") or "")
    text = str(raw.get("text") or "")
    if role == "user":
        text = re.sub(r"^(?:用戶訊息[：:]|你[：:]|You:)\s*", "", text, count=1)
    return Message(
        role=role,
        text=text,
        presentation=bool(raw.get("presentation")),
        busy=raw.get("busy"),
        streaming=raw.get("streaming"),
        has_actions=bool(raw.get("hasActions") or raw.get("has_actions")),
        typing=bool(raw.get("typing")),
    )


# Re-exported so a backend can map connection failure without importing flow internals.
__all__ = [
    "BrowserDown",
    "collect_activity",
    "collect_chats",
    "collect_memory",
    "collect_messages",
    "collect_pending",
    "collect_selftest",
    "collect_status",
    "collect_upcoming",
    "perform_send",
    "read_memory_flow",
    "read_with_tab",
    "browser_down",
]
