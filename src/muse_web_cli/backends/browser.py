"""Browser backend. Headless and headed sessions call the same flows."""

from __future__ import annotations

from muse_web_cli.errors import BrowserDown
from muse_web_cli.flow import (
    collect_activity,
    collect_memory,
    collect_messages,
    collect_pending,
    collect_selftest,
    collect_status,
    collect_upcoming,
    perform_send,
)
from muse_web_cli.model import browser_down, empty_like, send_payload


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

    def send(self, text: str, *, wait: bool, timeout: float) -> dict:
        try:
            return perform_send(self.driver, text, wait=wait, timeout=timeout)
        except BrowserDown as exc:
            return self._down(exc, "send", text)

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
