"""API backend.

With vm_id, calls go through the Muse gateway. Without it, endpoints select a
REST path the user configured. This module never writes the credential file,
never reads the browser, and never prints the token.
"""

from __future__ import annotations

import json
import os
import stat
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit

from muse_web_cli.model import (
    EXIT_FOR,
    credential_loose,
    credential_outside_home,
    empty_like,
    send_payload,
    setup_status,
    unsupported,
)
from muse_web_cli.output import safe_text
from muse_web_cli.selectors import API_HINT

_KINDS = ("status", "messages", "send", "pending", "upcoming", "activity", "memory", "chats")
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


class TransportError(Exception):
    def __init__(self, error: str):
        super().__init__(error)
        self.error = error


def _windows(platform: str | None) -> bool:
    name = os.name if platform is None else platform
    return name in {"nt", "win32"}


def _under_home(path: Path, home: Path) -> bool:
    try:
        target = path.resolve()
        root = home.resolve()
    except OSError:
        return False
    return target == root or root in target.parents


def urllib_transport(method: str, url: str, headers: dict, body: dict | None, timeout: float) -> tuple[int, bytes]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Accept": "application/json", **headers}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except TimeoutError:
        raise
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, TimeoutError)):
            raise TimeoutError(safe_text(str(exc.reason))) from exc
        raise TransportError(safe_text(str(exc.reason))) from exc


def _public_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.hostname or "", parts.path, "", ""))


def _auth_headers(auth: dict) -> dict[str, str]:
    kind = str(auth.get("type") or "")
    token = auth.get("token")
    if not isinstance(token, str) or not token:
        raise ValueError("auth.token")
    if kind == "bearer":
        return {"Authorization": f"Bearer {token}"}
    if kind == "header":
        name = str(auth.get("header_name") or "Authorization").strip()
        if not name:
            raise ValueError("auth.header_name")
        return {name: token}
    raise ValueError("auth.type")


def _endpoint(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    method = str(value.get("method") or "").upper()
    path = value.get("path")
    if method not in _METHODS or not isinstance(path, str) or not path.startswith("/"):
        return None
    return {"method": method, "path": path}


def _timeout(data: dict) -> float:
    timeout = data.get("timeout_s", 30)
    try:
        timeout_s = float(timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError("timeout_s") from exc
    if timeout_s <= 0:
        raise ValueError("timeout_s")
    return timeout_s


def _load_muse(data: dict, vm_id: str) -> dict:
    base = data.get("base_url")
    if not isinstance(base, str):
        raise ValueError("base_url")
    parts = urlsplit(base.strip())
    if parts.scheme not in {"https", "wss"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("base_url")
    auth = data.get("auth")
    if not isinstance(auth, dict):
        raise ValueError("auth")
    token = auth.get("token")
    if not isinstance(token, str) or not token:
        raise ValueError("auth.token")
    kind = str(auth.get("type") or "bearer")
    if kind not in {"bearer", "header"}:
        raise ValueError("auth.type")
    app_id = data.get("app_id") or "hatch-web"
    if not isinstance(app_id, str) or not app_id.strip():
        raise ValueError("app_id")
    notary = data.get("notary_token")
    if notary is not None and not isinstance(notary, str):
        raise ValueError("notary_token")
    return {
        "mode": "muse",
        "base_url": base.strip().rstrip("/"),
        "vm_id": vm_id,
        "token": token,
        "app_id": app_id.strip(),
        "notary_token": notary or None,
        "timeout_s": _timeout(data),
    }


def _load_config(text: str) -> dict:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("object")
    vm_id = data.get("vm_id")
    if isinstance(vm_id, str) and vm_id.strip():
        return _load_muse(data, vm_id.strip())
    base = data.get("base_url")
    if not isinstance(base, str):
        raise ValueError("base_url")
    parts = urlsplit(base)
    if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("base_url")
    auth = data.get("auth")
    if not isinstance(auth, dict):
        raise ValueError("auth")
    headers = _auth_headers(auth)
    raw_endpoints = data.get("endpoints") if isinstance(data.get("endpoints"), dict) else {}
    endpoints = {}
    for kind in _KINDS:
        spec = _endpoint(raw_endpoints.get(kind))
        if spec:
            endpoints[kind] = spec
    return {
        "mode": "rest",
        "base_url": base.rstrip("/"),
        "headers": headers,
        "endpoints": endpoints,
        "timeout_s": _timeout(data),
    }


def _reply_after(payload: dict, text: str) -> str | None:
    if isinstance(payload.get("reply"), str):
        return payload["reply"]
    rows = payload.get("messages")
    if not isinstance(rows, list):
        return None
    seen = False
    reply = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("role") == "user" and row.get("text") == text:
            seen = True
            reply = None
            continue
        if seen and row.get("role") == "assistant" and isinstance(row.get("text"), str):
            reply = row["text"]
    return reply


class ApiBackend:
    def __init__(self, credential: Path, *, transport=None, platform: str | None = None, home: Path | None = None, sleep=None, gateway_session=None):
        self.credential = credential
        self.transport = transport or urllib_transport
        self.platform = platform
        self.home = home or Path.home()
        self.sleep = sleep or time.sleep
        self.gateway_session = gateway_session
        self._config: dict | None = None
        self._config_error: dict | None = None
        self._gateway = None

    def _gate(self) -> dict | None:
        try:
            info = self.credential.lstat()
        except FileNotFoundError:
            return unsupported("status")
        except OSError:
            return setup_status(
                "credential_permissions",
                "讀不到憑證檔。",
                "確認檔案權限後再試。",
                backend="api",
            )
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            return credential_loose(error="credential file must be a regular file")
        if _windows(self.platform):
            if not _under_home(self.credential, self.home):
                return credential_outside_home()
        elif (info.st_mode & 0o777) != 0o600:
            return credential_loose()
        return None

    def _prepare(self) -> dict | None:
        gate = self._gate()
        if gate is not None:
            return gate
        if self._config_error is not None:
            return self._config_error
        if self._config is not None:
            return None
        try:
            text = self.credential.read_text(encoding="utf-8")
            self._config = _load_config(text)
        except json.JSONDecodeError:
            self._config_error = setup_status(
                "ui_changed",
                "憑證不是合法的 JSON。",
                "重新執行 muse-web-cli credential，或修正檔案內容。token 不會印出來。",
                backend="api",
            )
            return self._config_error
        except OSError:
            self._config_error = setup_status(
                "credential_permissions",
                "讀不到憑證檔。",
                "確認檔案權限後再試。",
                backend="api",
            )
            return self._config_error
        except ValueError:
            self._config_error = setup_status(
                "ui_changed",
                "憑證欄位不對。",
                "重新執行 muse-web-cli credential。token 不會印出來。",
                backend="api",
            )
            return self._config_error
        return None

    def _shape(self, kind: str, status: dict, text: str = "") -> dict:
        if kind == "status":
            return status
        if kind == "send":
            return send_payload(
                backend="api",
                state=status["state"],
                text=text,
                error=status.get("error"),
                hint=status.get("hint"),
            )
        return empty_like(kind, status)

    def _missing(self, kind: str, text: str = "") -> dict:
        return self._shape(
            kind,
            unsupported(kind, error=f"端點沒填（{kind}）。請在 endpoints 指定，或改填 vm_id。", hint=API_HINT, text=text),
            text,
        )

    def _fail(self, kind: str, state: str, error: str, hint: str | None, text: str = "") -> dict:
        return self._shape(kind, setup_status(state, error, hint, backend="api"), text)

    def _http_error(self, kind: str, status: int, text: str = "") -> dict:
        if status in {401, 403}:
            state, error, hint = "session_expired", f"HTTP {status}", "check the sanctioned credential"
        elif status == 408:
            state, error, hint = "timeout", f"HTTP {status}", "nothing was sent again" if kind == "send" else None
        else:
            state, error, hint = "ui_changed", f"HTTP {status}", None
        return self._fail(kind, state, error, hint, text)

    def _call(self, kind: str, *, body: dict | None, query: dict | None, timeout: float) -> tuple[int, dict]:
        config = self._config or {}
        spec = config["endpoints"][kind]
        url = config["base_url"] + spec["path"]
        if query:
            url = f"{url}?{urlencode(query)}"
        try:
            status, raw = self.transport(spec["method"], url, dict(config["headers"]), body, timeout)
        except TimeoutError as exc:
            raise TimeoutError(safe_text(str(exc))) from exc
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(safe_text(f"{type(exc).__name__} {_public_url(url)}")) from exc
        if not raw:
            return status, {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise TransportError("response was not JSON") from exc
        if not isinstance(parsed, dict):
            raise TransportError("response was not a JSON object")
        return status, parsed

    def _run(self, kind: str, *, text: str = "", body: dict | None = None, query: dict | None = None, timeout: float | None = None) -> dict:
        blocked = self._prepare()
        if blocked is not None:
            return self._shape(kind, blocked, text)
        if kind not in (self._config or {}).get("endpoints", {}):
            return self._missing(kind, text)
        limit = timeout if timeout is not None else self._config["timeout_s"]
        try:
            status, payload = self._call(kind, body=body, query=query, timeout=limit)
        except TimeoutError:
            hint = "nothing was sent again" if kind == "send" else None
            shaped = self._fail(kind, "timeout", "request timed out", hint, text)
            if kind == "send":
                shaped["attempted"] = True
                shaped["sent"] = False
            return shaped
        except TransportError as exc:
            return self._fail(kind, "ui_changed", exc.error, None, text)
        if status >= 400:
            shaped = self._http_error(kind, status, text)
            if kind == "send" and status == 408:
                shaped["attempted"] = True
                shaped["sent"] = False
            return shaped
        payload["backend"] = "api"
        payload.setdefault("state", "ok")
        payload.setdefault("error", None)
        payload.setdefault("hint", None)
        if payload["state"] != "ok":
            # Exit 4 is decided here, not by the server, and unknown keys are dropped.
            state = str(payload["state"])
            if state not in EXIT_FOR or state == "unsupported":
                state = "ui_changed"
            error = payload["error"] if isinstance(payload["error"], str) else None
            hint = payload["hint"] if isinstance(payload["hint"], str) else None
            return self._fail(kind, state, safe_text(error) if error else "server reported an error", safe_text(hint) if hint else None, text)
        return self._ok(kind, payload, text)

    def _ok(self, kind: str, payload: dict, text: str) -> dict:
        if kind == "status":
            payload.setdefault("pending", None)
            payload.setdefault("latest_assistant_is_card", None)
            payload.setdefault("headless", None)
            payload.setdefault("missing", [])
            return {key: payload.get(key) for key in ("backend", "state", "pending", "latest_assistant_is_card", "headless", "error", "hint", "missing")}
        if kind == "messages":
            rows = payload.get("messages") if isinstance(payload.get("messages"), list) else []
            payload["messages"] = rows
            payload.setdefault("name", "Muse")
            payload.setdefault("lines", [])
            return {key: payload.get(key) for key in ("backend", "state", "name", "lines", "messages", "error", "hint")}
        if kind == "send":
            payload.setdefault("attempted", True)
            payload.setdefault("sent", True)
            payload["text"] = text
            payload.setdefault("reply", None)
            payload.setdefault("presentation", None)
            payload.setdefault("elapsed_ms", None)
            return {key: payload.get(key) for key in ("backend", "state", "attempted", "sent", "text", "reply", "presentation", "elapsed_ms", "error", "hint")}
        if kind == "pending":
            items = payload.get("items") if isinstance(payload.get("items"), list) else []
            payload["items"] = items
            payload["count"] = len(items)
            return {key: payload.get(key) for key in ("backend", "state", "count", "items", "error", "hint")}
        if kind in {"upcoming", "activity"}:
            groups = payload.get("groups") if isinstance(payload.get("groups"), list) else []
            payload["groups"] = groups
            payload["count"] = sum(len(group.get("items") or []) for group in groups if isinstance(group, dict))
            return {key: payload.get(key) for key in ("backend", "state", "count", "groups", "error", "hint")}
        if kind == "memory":
            body = payload.get("text") if isinstance(payload.get("text"), str) else ""
            payload["text"] = body
            payload["chars"] = len(body)
            payload.setdefault("sections", [])
            return {key: payload.get(key) for key in ("backend", "state", "chars", "sections", "text", "error", "hint")}
        chats = payload.get("chats") if isinstance(payload.get("chats"), list) else []
        payload["chats"] = chats
        payload["count"] = len(chats)
        return {key: payload.get(key) for key in ("backend", "state", "count", "chats", "error", "hint")}

    def _muse(self, kind: str, text: str = ""):
        blocked = self._prepare()
        if blocked is not None:
            return self._shape(kind, blocked, text)
        if (self._config or {}).get("mode") != "muse":
            return None
        if self._gateway is None:
            from muse_web_cli.backends.gateway import MuseGateway

            self._gateway = MuseGateway(
                self._config,
                credential=self.credential,
                session=self.gateway_session,
                sleep=self.sleep,
            )
        return self._gateway

    def status(self) -> dict:
        gateway = self._muse("status")
        if gateway is not None:
            if isinstance(gateway, dict):
                return gateway
            return gateway.status()
        return self._run("status")

    def messages(self, limit: int, *, session: str | None = None) -> dict:
        gateway = self._muse("messages")
        if gateway is not None:
            if isinstance(gateway, dict):
                return gateway
            return gateway.messages(limit, session=session)
        return self._run("messages", query={"limit": limit})

    def wait_reply(self, text: str, *, first: dict, prior: list, session: str | None, timeout: float, started: float) -> dict:
        """Wait for the reply to a message the Muse window sent (an upload). Never sends."""
        gateway = self._muse("send", text)
        if gateway is None:
            return {**first, "state": "timeout", "error": "this credential cannot read replies", "hint": "nothing was sent again"}
        if isinstance(gateway, dict):
            return gateway
        return gateway.wait_reply(text, first=first, prior=prior, session=session, timeout=timeout, started=started)

    def send(self, text: str, *, wait: bool, timeout: float, session: str | None = None) -> dict:
        gateway = self._muse("send", text)
        if gateway is not None:
            if isinstance(gateway, dict):
                return gateway
            return gateway.send(text, wait=wait, timeout=timeout, session=session)
        started = time.monotonic()
        first = self._run("send", text=text, body={"text": text, "wait": bool(wait)}, timeout=timeout)
        if not wait or first.get("state") != "ok" or first.get("reply"):
            return first
        if "messages" not in (self._config or {}).get("endpoints", {}):
            return first
        while time.monotonic() - started < timeout:
            remaining = timeout - (time.monotonic() - started)
            polled = self._run("messages", query={"limit": 20}, timeout=max(0.1, remaining))
            if polled.get("state") == "timeout":
                first["state"] = "timeout"
                first["error"] = polled.get("error")
                first["hint"] = "nothing was sent again"
                return first
            if polled.get("state") != "ok":
                return first
            reply = _reply_after(polled, text)
            if reply:
                first["reply"] = reply
                first["elapsed_ms"] = int((time.monotonic() - started) * 1000)
                return first
            self.sleep(0.05)
        first["state"] = "timeout"
        first["error"] = "request timed out"
        first["hint"] = "nothing was sent again"
        return first

    def pending(self) -> dict:
        gateway = self._muse("pending")
        if gateway is not None:
            return gateway if isinstance(gateway, dict) else gateway.pending()
        return self._run("pending")

    def upcoming(self) -> dict:
        gateway = self._muse("upcoming")
        if gateway is not None:
            return gateway if isinstance(gateway, dict) else gateway.upcoming()
        return self._run("upcoming")

    def activity(self) -> dict:
        gateway = self._muse("activity")
        if gateway is not None:
            return gateway if isinstance(gateway, dict) else gateway.activity()
        return self._run("activity")

    def memory(self) -> dict:
        gateway = self._muse("memory")
        if gateway is not None:
            return gateway if isinstance(gateway, dict) else gateway.memory()
        return self._run("memory")

    def chats(self, *, action: str | None = None, session: str | None = None, title: str | None = None) -> dict:
        gateway = self._muse("chats")
        if gateway is not None:
            if isinstance(gateway, dict):
                return gateway
            return gateway.chats(action=action, session=session, title=title)
        body = {"action": action, "session": session, "title": title} if action else None
        return self._run("chats", body=body)
