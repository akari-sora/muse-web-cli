"""Browser backend. Headless and headed sessions call the same flows."""

from __future__ import annotations

from muse_web_cli.errors import BrowserDown, PageChanged
from muse_web_cli.flow import (
    collect_activity,
    collect_chats,
    collect_memory,
    collect_messages,
    collect_pending,
    collect_selftest,
    collect_status,
    collect_upcoming,
    perform_send,
)
from muse_web_cli.model import browser_down, empty_like, send_payload
from muse_web_cli.output import safe_text


class BrowserBackend:
    def __init__(self, driver, *, headless: bool | None):
        self.driver = driver
        self.headless = headless

    def _down(self, exc: BrowserDown, kind: str, text: str = "") -> dict:
        status = browser_down(exc.error, hint=exc.hint)
        if kind == "status":
            status["headless"] = self.headless
            return status
        if kind == "send":
            return send_payload(
                backend="browser",
                state="browser_down",
                text=text,
                error=status["error"],
                hint=status["hint"],
            )
        if kind == "selftest":
            status["present"] = {}
            return status
        return empty_like(kind, status)

    def status(self) -> dict:
        try:
            payload = collect_status(self.driver)
        except BrowserDown as exc:
            payload = self._down(exc, "status")
        payload["backend"] = "browser"
        payload["headless"] = self.headless
        return payload

    def messages(self, limit: int) -> dict:
        try:
            return collect_messages(self.driver, limit)
        except BrowserDown as exc:
            return self._down(exc, "messages")

    def send(self, text: str, *, wait: bool, timeout: float, attach: list[str] | None = None, session: str | None = None) -> dict:
        try:
            if not session:
                return perform_send(self.driver, text, wait=wait, timeout=timeout, attach=attach)
            # A side chat is shown by its URL; the window goes back to the main chat afterwards.
            try:
                try:
                    self.driver.open_thread(session)
                except PageChanged:
                    payload = send_payload(backend="browser", state="ui_changed", text=text,
                                           error="the Muse window did not show that side chat; nothing was sent", hint=None)
                else:
                    payload = perform_send(self.driver, text, wait=wait, timeout=timeout, attach=attach, side_chat=True)
            finally:
                warning = self._back_to_main()
            if warning:
                payload["warning"] = warning
            return payload
        except BrowserDown as exc:
            return self._down(exc, "send", text)

    def _back_to_main(self) -> str:
        """Best effort. A send that already happened is never reported as not sent because of this."""
        try:
            self.driver.open_thread(None)
        except Exception as exc:
            return f"the Muse window did not go back to the main chat: {safe_text(str(exc))}"
        return ""

    def pending(self) -> dict:
        try:
            return collect_pending(self.driver)
        except BrowserDown as exc:
            return self._down(exc, "pending")

    def upcoming(self) -> dict:
        try:
            return collect_upcoming(self.driver)
        except BrowserDown as exc:
            return self._down(exc, "upcoming")

    def activity(self) -> dict:
        try:
            return collect_activity(self.driver)
        except BrowserDown as exc:
            return self._down(exc, "activity")

    def chats(self) -> dict:
        try:
            return collect_chats(self.driver)
        except BrowserDown as exc:
            return self._down(exc, "chats")

    def memory(self) -> dict:
        try:
            return collect_memory(self.driver)
        except BrowserDown as exc:
            return self._down(exc, "memory")

    def selftest(self) -> dict:
        try:
            return collect_selftest(self.driver)
        except BrowserDown as exc:
            return self._down(exc, "selftest")
