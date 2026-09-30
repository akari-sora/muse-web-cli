"""API seam. The credential file is stat'd for mode 600 and never opened."""

from __future__ import annotations

import stat
from pathlib import Path

from muse_web_cli.model import (
    credential_loose,
    credential_missing,
    empty_like,
    unsupported,
)


class ApiBackend:
    def __init__(self, credential: Path):
        self.credential = credential

    def _gate(self) -> dict | None:
        try:
            info = self.credential.lstat()
        except FileNotFoundError:
            return credential_missing()
        except OSError:
            return credential_missing()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            return credential_loose()
        if (info.st_mode & 0o777) != 0o600:
            return credential_loose()
        return None

    def _blocked(self, kind: str, text: str = "") -> dict | None:
        gate = self._gate()
        if gate is None:
            return None
        if kind == "status":
            return gate
        if kind == "send":
            from muse_web_cli.model import send_payload

            return send_payload(
                backend="api",
                state=gate["state"],
                text=text,
                error=gate.get("error"),
                hint=gate.get("hint"),
            )
        return empty_like(kind, gate)

    def status(self) -> dict:
        return self._blocked("status") or unsupported("status")

    def messages(self, limit: int) -> dict:
        return self._blocked("messages") or unsupported("messages")

    def send(self, text: str, *, wait: bool, timeout: float) -> dict:
        return self._blocked("send", text) or unsupported("send", text=text)

    def pending(self) -> dict:
        return self._blocked("pending") or unsupported("pending")

    def upcoming(self) -> dict:
        return self._blocked("upcoming") or unsupported("upcoming")

    def activity(self) -> dict:
        return self._blocked("activity") or unsupported("activity")

    def memory(self) -> dict:
        return self._blocked("memory") or unsupported("memory")
