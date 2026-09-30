"""Capability backends. The CLI picks one; commands do not branch inside a backend."""

from muse_web_cli.backends.api import ApiBackend
from muse_web_cli.backends.browser import BrowserBackend

__all__ = ["ApiBackend", "BrowserBackend"]
