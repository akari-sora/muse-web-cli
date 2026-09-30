"""Expected failures. These never carry cookies or tokens."""

from __future__ import annotations


class BrowserDown(Exception):
    def __init__(self, error: str, hint: str | None = None):
        super().__init__(error)
        self.error = error
        self.hint = hint


class PageChanged(Exception):
    def __init__(self, missing: str):
        super().__init__(missing)
        self.missing = missing
