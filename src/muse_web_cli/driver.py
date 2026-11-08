"""Playwright adapter. Attaches to Chrome; it does not download or close it.

Network and Storage CDP domains are never enabled. Cookies and tokens are never read.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from muse_web_cli.errors import BrowserDown, PageChanged
from muse_web_cli.flow import WaitResult, message_from_raw
from muse_web_cli.model import Snapshot, tab_selector, url_is_login
from muse_web_cli.nav import guard_click, read_chats_flow, read_memory_flow, read_with_tab
from muse_web_cli.output import safe_text
from muse_web_cli.probes import CHATS_JS, MEMORY_JS, OBSERVER_JS, PANEL_JS, PANEL_STATE_JS, SNAPSHOT_JS
from muse_web_cli.selectors import (
    ATTACHMENT,
    AVATAR_BUTTON,
    COMPOSER,
    EDITOR,
    EDITOR_CLOSE,
    FILE_INPUT,
    LOG,
    MEMORY_FILE,
    MUSE_URL,
    SEND_BUTTON,
    SIDE_CHATS_CONTENT,
    SWITCHER,
    TAB_ACTIVITY,
    TAB_IDENTITY,
    TAB_PENDING,
    TAB_UPCOMING,
    THREAD_URL,
    switcher_selectors,
)

_TAB_CLICKS = frozenset({TAB_PENDING, TAB_UPCOMING, TAB_ACTIVITY, TAB_IDENTITY})

_CLICK_NAME = {
    COMPOSER: "composer",
    SWITCHER: "switcher",
    **{item: "switcher" for item in switcher_selectors()},
    TAB_PENDING: "pending_tab",
    TAB_UPCOMING: "upcoming_tab",
    TAB_ACTIVITY: "activity_tab",
    TAB_IDENTITY: "identity_tab",
    MEMORY_FILE: "memory_file",
    EDITOR_CLOSE: "editor_close",
    AVATAR_BUTTON: "avatar",
}


def _host_path(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.netloc, parts.path


class CdpPage:
    def __init__(self, page, playwright):
        self.page = page
        self._playwright = playwright

    def disconnect(self) -> None:
        # Stopping the driver detaches. Do not ask the browser to quit.
        self._playwright.stop()

    def _eval(self, script: str, arg=None):
        try:
            if arg is None:
                return self.page.evaluate(script)
            return self.page.evaluate(script, arg)
        except Exception as exc:
            if "Timeout" in type(exc).__name__:
                raise
            text = safe_text(str(exc))
            lowered = text.lower()
            if any(bit in lowered for bit in ("closed", "connect", "websocket", "target")):
                raise BrowserDown(text) from exc
            raise PageChanged("page") from exc

    def snapshot(self) -> Snapshot:
        raw = self._eval(SNAPSHOT_JS)
        present = {str(key): bool(value) for key, value in (raw.get("present") or {}).items()}
        return Snapshot(
            host=str(raw.get("host") or ""),
            path=str(raw.get("path") or ""),
            has_log=bool(raw.get("hasLog")),
            has_composer=bool(raw.get("hasComposer")),
            has_password=bool(raw.get("hasPassword")),
            panel_open=bool(raw.get("panelOpen")),
            gate_text=str(raw.get("gateText") or ""),
            messages=[message_from_raw(item) for item in raw.get("messages") or []],
            selectors=present,
        )

    def _wait_until(self, predicate, missing: str, timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while True:
            if predicate():
                return
            if time.monotonic() >= deadline:
                raise PageChanged(missing)
            time.sleep(0.1)

    def click(self, selector: str) -> None:
        guard_click(selector)
        locator = self.page.locator(selector)
        try:
            count = locator.count()
        except Exception as exc:
            raise BrowserDown(safe_text(str(exc))) from exc
        if count == 0:
            raise PageChanged(_CLICK_NAME.get(selector, "control"))
        locator.first.click(timeout=10000)
        if selector in _TAB_CLICKS:
            self._wait_until(
                lambda: tab_selector(self._panel_state().get("label")) == selector,
                "tab",
            )
            # aria-pressed flips before the tab body swaps.
            time.sleep(0.45)
        elif selector == MEMORY_FILE:
            self._wait_until(lambda: self.page.locator(EDITOR).count() > 0, "editor")
        elif selector == EDITOR_CLOSE:
            self._wait_until(lambda: self.page.locator(EDITOR).count() == 0, "editor_close")
        elif selector == AVATAR_BUTTON:
            self._wait_until(lambda: bool(self._panel_state().get("open")), "panel")
        elif selector != COMPOSER:
            time.sleep(0.15)

    def _draft_matches(self, text: str) -> bool:
        value = self.page.locator(COMPOSER).first.input_value()
        return " ".join(value.split()) == " ".join(text.split())

    def insert_text(self, text: str) -> None:
        self.click(COMPOSER)
        if self.page.locator(COMPOSER).first.input_value().strip():
            raise PageChanged("composer_not_empty")
        self.page.keyboard.insert_text(text)
        try:
            # Enter before React commits the draft sends nothing and clears it.
            self._wait_until(
                lambda: self._draft_matches(text) and self.page.locator(SEND_BUTTON).count() > 0,
                "composer",
            )
        except PageChanged:
            self._clear_own_draft(text)
            raise

    def _clear_own_draft(self, text: str) -> None:
        if not self._draft_matches(text):
            return
        self.page.locator(COMPOSER).first.focus()
        self.page.keyboard.press("ControlOrMeta+A")
        self.page.keyboard.press("Backspace")

    def open_thread(self, session_id: str | None) -> None:
        """Show one chat in the window: a side chat by its session id, or the main chat (None)."""
        if session_id is not None and not re.fullmatch(r"[0-9a-fA-F-]{8,64}", session_id):
            raise PageChanged("session")
        self.page.goto(THREAD_URL.format(session_id) if session_id else MUSE_URL)
        self.page.wait_for_load_state("load")
        # The composer is server-rendered before the page is live; the chat log comes after.
        self._wait_until(lambda: self.page.locator(COMPOSER).count() > 0 and self.page.locator(LOG).count() > 0, "composer", timeout=45.0)
        time.sleep(2.0)

    def attach_files(self, paths: list[str]) -> None:
        """Attach files through the composer's file input; the attach button is never clicked."""
        if self.page.locator(ATTACHMENT).count():
            raise PageChanged("composer_not_empty")
        files = [str(Path(p)) for p in paths]
        # A page that is still starting ignores the files; set them again only while none showed up.
        for _ in range(3):
            self.page.locator(FILE_INPUT).first.set_input_files(files)
            try:
                self._wait_until(lambda: self.page.locator(ATTACHMENT).count() >= len(files), "attachment", timeout=10.0)
                break
            except PageChanged:
                if self.page.locator(ATTACHMENT).count():
                    break
        time.sleep(0.5)
        if self.page.locator(ATTACHMENT).count() != len(files):
            self.clear_attachments()
            raise PageChanged("attachment")

    def clear_attachments(self) -> None:
        """Remove files this run attached when the send did not happen."""
        for _ in range(20):
            if not self.page.locator(ATTACHMENT).count():
                return
            self.page.locator(ATTACHMENT).first.click(timeout=5000)
            time.sleep(0.2)

    def press_enter(self) -> None:
        self.page.locator(COMPOSER).first.focus()
        self.page.keyboard.press("Enter")

    def wait_outcome(self, *, text: str, before_count: int, wait: bool, timeout: float) -> WaitResult:
        budget = max(1, int(timeout * 1000))
        self.page.set_default_timeout(budget + 15000)
        try:
            raw = self.page.evaluate(
                OBSERVER_JS,
                {"text": text, "beforeUserCount": before_count, "wait": wait, "timeoutMs": budget},
            )
        except Exception as exc:
            if "Timeout" in type(exc).__name__:
                return WaitResult(True, "reply", [])
            raise
        finally:
            self.page.set_default_timeout(30000)
        messages = [message_from_raw(item) for item in (raw or {}).get("messages") or []]
        return WaitResult(bool((raw or {}).get("timedOut")), str((raw or {}).get("phase") or ""), messages)

    def _panel_state(self) -> dict:
        raw = self._eval(PANEL_STATE_JS)
        return raw if isinstance(raw, dict) else {"open": False, "label": None}

    def read_groups(self, target: str) -> list[dict]:
        def panel_open() -> bool:
            return bool(self._panel_state().get("open"))

        def current() -> str | None:
            return tab_selector(self._panel_state().get("label"))

        def read() -> list[dict]:
            data = self._eval(PANEL_JS)
            return list((data or {}).get("groups") or [])

        return read_with_tab(
            panel_open=panel_open,
            current_tab=current,
            click=self.click,
            read=read,
            target=target,
        )

    def _side_chats_open(self) -> bool:
        locator = self.page.locator(SIDE_CHATS_CONTENT)
        try:
            if locator.count() == 0:
                return False
            return bool(locator.first.is_visible())
        except Exception as exc:
            raise BrowserDown(safe_text(str(exc))) from exc

    def read_chats(self) -> dict:
        def read() -> dict:
            data = self._eval(CHATS_JS)
            if not isinstance(data, dict) or not data.get("ok"):
                raise PageChanged("side_chats")
            return data

        return read_chats_flow(is_open=self._side_chats_open, read=read)

    def read_memory(self) -> str:
        def panel_open() -> bool:
            return bool(self._panel_state().get("open"))

        def current() -> str | None:
            return tab_selector(self._panel_state().get("label"))

        def read_text() -> str:
            data = self._eval(MEMORY_JS)
            if not isinstance(data, dict) or not data.get("ok"):
                raise PageChanged("memory_body")
            return str(data.get("text") or "")

        return read_memory_flow(
            panel_open=panel_open,
            current_tab=current,
            click=self.click,
            read_text=read_text,
        )


def connect(port: int) -> CdpPage:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserDown("playwright is not installed", "uv tool install --editable .") from exc
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        page = _pick_page(browser)
        if page is None:
            context = browser.contexts[0] if browser.contexts else None
            if context is None:
                raise BrowserDown("Chrome has no page context")
            page = context.new_page()
            page.goto(MUSE_URL, wait_until="domcontentloaded", timeout=30000)
        page.set_default_timeout(30000)
        return CdpPage(page, playwright)
    except BrowserDown:
        playwright.stop()
        raise
    except Exception as exc:
        playwright.stop()
        raise BrowserDown(safe_text(str(exc))) from exc


def _pick_page(browser):
    pages = [page for context in browser.contexts for page in context.pages]
    muse = []
    login = []
    for page in pages:
        host, path = _host_path(page.url)
        if host.endswith("muse.ai"):
            muse.append(page)
        elif url_is_login(host, path):
            login.append(page)
    for page in muse:
        try:
            if page.locator(LOG).count():
                return page
        except Exception:
            continue
    if muse:
        return muse[0]
    if login:
        return login[0]
    return None
