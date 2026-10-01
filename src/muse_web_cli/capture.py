"""Save the gateway credential from the logged-in Muse page.

The page already holds the gateway address. This module asks that page for a
token and writes ~/.trinity-cli/muse-credential. Returned payloads, errors, and
hints never include the token, the vm id, or the gateway host.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

FIELD_NAMES = ("base_url", "vm_id", "auth.type", "auth.token", "timeout_s", "notary_token")
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_SHARED_HOST = "hatch.metaaivm.com"

# Runs inside the logged-in page. The browser attaches its own session.
# Do not read the cookie jar, web storage, or CDP network domains from here.
CAPTURE_JS = r"""
async () => {
  const runtime = window.__hatchEarlyGatewayRuntimeState;
  const snapshot = runtime && runtime.activeRuntime && runtime.activeRuntime.getSnapshot
    ? runtime.activeRuntime.getSnapshot()
    : null;
  const authority = (snapshot && snapshot.connectionAuthority) || {};
  const gatewayUrl = String(authority.gatewayUrl || (runtime && runtime.activeGatewayUrl) || "");
  const vmName = String(authority.vmName || "");
  if (!gatewayUrl) return {ok: false, reason: "no_gateway"};
  const body = {vmAddress: gatewayUrl};
  if (vmName) body.vmName = vmName;
  let response;
  try {
    response = await fetch("/api/hatch/token", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (err) {
    return {ok: false, reason: "token_request"};
  }
  if (!response.ok) return {ok: false, reason: "token_status", status: response.status};
  let parsed;
  try {
    parsed = await response.json();
  } catch (err) {
    return {ok: false, reason: "token_body"};
  }
  if (!parsed || typeof parsed !== "object") return {ok: false, reason: "token_body"};
  return {
    ok: true,
    gatewayUrl,
    vmName,
    token: typeof parsed.token === "string" ? parsed.token : "",
    notary: typeof parsed.notary_token === "string" ? parsed.notary_token : "",
  };
}
"""


def _blank_fields() -> dict:
    return {name: False for name in FIELD_NAMES}


def public_result(
    *,
    state: str,
    wrote: bool,
    fields: dict | None = None,
    error: str | None = None,
    hint: str | None = None,
    logged_in: bool = False,
) -> dict:
    present = _blank_fields()
    if fields:
        for name in FIELD_NAMES:
            present[name] = bool(fields.get(name))
    return {
        "backend": "browser",
        "state": state,
        "action": "credential",
        "wrote": bool(wrote),
        "logged_in": bool(logged_in),
        "fields": present,
        "error": error,
        "hint": hint,
    }


def gateway_identity(gateway_url: str, vm_name: str) -> tuple[str, str]:
    parts = urlsplit((gateway_url or "").strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"https", "http", "wss", "ws"} or not host or parts.username or parts.password:
        raise ValueError("base_url")
    if host != _SHARED_HOST and not host.endswith(".metaaivm.com"):
        raise ValueError("host")
    query = parse_qs(parts.query).get("vm_id") or []
    from_query = query[0].strip() if query and isinstance(query[0], str) else ""
    label = host.split(".")[0]
    named_vm = host.endswith(".metaaivm.com") and host != _SHARED_HOST and bool(_UUID.match(label))
    if host == _SHARED_HOST or named_vm:
        # The per-VM hostname is an id, not a dialable address. The Noise
        # session uses the shared ingress and puts that id in vm_id.
        base = f"https://{_SHARED_HOST}"
        vm_id = from_query or (label if named_vm else "") or (vm_name or "").strip()
    else:
        base = f"https://{host}"
        if parts.port:
            base = f"{base}:{parts.port}"
        vm_id = from_query or (vm_name or "").strip()
    if not vm_id:
        raise ValueError("vm_id")
    return base, vm_id


def document_from(raw: dict) -> tuple[dict | None, list[str]]:
    """Build the credential object. Missing names are returned; secrets stay in the object."""
    if not isinstance(raw, dict) or not raw.get("ok"):
        return None, []
    missing: list[str] = []
    try:
        base_url, vm_id = gateway_identity(str(raw.get("gatewayUrl") or ""), str(raw.get("vmName") or ""))
    except ValueError as exc:
        missing.append(str(exc))
        base_url, vm_id = "", ""
    token = raw.get("token") if isinstance(raw.get("token"), str) else ""
    if not token:
        missing.append("auth.token")
    if missing:
        return None, missing
    document = {
        "base_url": base_url,
        "vm_id": vm_id,
        "auth": {"type": "bearer", "token": token},
        "timeout_s": 30,
        "app_id": "hatch-web",
    }
    notary = raw.get("notary") if isinstance(raw.get("notary"), str) else ""
    if notary.strip():
        document["notary_token"] = notary.strip()
    return document, []


def write_credential(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload.encode("utf-8"))
        try:
            os.fchmod(fd, 0o600)
        except (AttributeError, OSError):
            pass
    finally:
        os.close(fd)
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _failure_from_ready(ready: dict) -> dict:
    state = str(ready.get("state") or "browser_down")
    if state == "ok":
        state = "browser_down"
    return public_result(
        state=state,
        wrote=False,
        error=ready.get("error") if isinstance(ready.get("error"), str) and ready.get("error") else "連不上 Muse 的瀏覽器。",
        hint=ready.get("hint") if isinstance(ready.get("hint"), str) else "muse-web-cli login",
    )


def _region_blocked() -> dict:
    return public_result(
        state="region_blocked",
        wrote=False,
        error="Muse 在這個地區無法使用。",
        hint="這個工具不會繞過地區限制。",
    )


def _waiting() -> dict:
    return public_result(
        state="session_expired",
        wrote=False,
        logged_in=False,
        error="尚未登入。",
        hint="請在開啟的 Chrome 視窗登入 Muse。這個工具不會輸入帳號密碼。完成後再執行 muse-web-cli credential。",
    )


def _from_capture(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return public_result(
            state="ui_changed",
            wrote=False,
            logged_in=True,
            error="抓不到 gateway 憑證。",
            hint="確認 Muse 已登入後再執行 muse-web-cli credential。",
        )
    if not raw.get("ok"):
        status = raw.get("status")
        if raw.get("reason") == "token_status" and status in {401, 403}:
            return public_result(
                state="session_expired",
                wrote=False,
                logged_in=False,
                error="登入工作階段已失效。",
                hint="請在開啟的 Chrome 視窗重新登入 Muse。這個工具不會輸入帳號密碼。",
            )
        return public_result(
            state="ui_changed",
            wrote=False,
            logged_in=True,
            error="抓不到 gateway 憑證。",
            hint="確認 Muse 已登入後再執行 muse-web-cli credential。",
        )
    document, missing = document_from(raw)
    if document is None:
        if "host" in missing:
            return public_result(
                state="ui_changed",
                wrote=False,
                logged_in=True,
                error="gateway 位址不在允許的範圍。沒有寫入檔案。",
                hint="只接受 metaaivm.com。確認 Muse 已連上後再執行 muse-web-cli credential。",
            )
        names = "、".join(missing) if missing else "auth.token"
        return public_result(
            state="ui_changed",
            wrote=False,
            logged_in=True,
            error=f"憑證不完整，缺少 {names}。沒有寫入檔案。",
            hint="確認 Muse 頁面已連上 gateway 後再執行 muse-web-cli credential。",
        )
    return document  # caller writes it; this branch is not a public payload


def run_credential(destination: Path, *, connect, login, capture, session_state) -> dict:
    """connect() -> (ready, page). login() -> payload with logged_in. capture(page) -> dict."""
    ready, page = connect()
    if page is None:
        if str(ready.get("state") or "") == "browser_down":
            opened = login()
            if not opened.get("logged_in"):
                if opened.get("state") not in {None, "", "ok"}:
                    return _failure_from_ready(opened)
                return _waiting()
            ready, page = connect()
        else:
            return _failure_from_ready(ready if isinstance(ready, dict) else {})
    if page is None:
        return _failure_from_ready(ready if isinstance(ready, dict) else {})
    try:
        state = session_state(page)
        if state == "region_blocked":
            return _region_blocked()
        if state == "session_expired":
            _close(page)
            page = None
            opened = login()
            if not opened.get("logged_in"):
                if opened.get("state") not in {None, "", "ok"}:
                    return _failure_from_ready(opened)
                return _waiting()
            ready, page = connect()
            if page is None:
                return _failure_from_ready(ready if isinstance(ready, dict) else {})
            state = session_state(page)
            if state == "region_blocked":
                return _region_blocked()
            if state == "session_expired":
                return _waiting()
        try:
            raw = capture(page)
        except Exception:
            return public_result(
                state="ui_changed",
                wrote=False,
                logged_in=True,
                error="抓不到 gateway 憑證。",
                hint="確認 Muse 已登入後再執行 muse-web-cli credential。",
            )
        built = _from_capture(raw if isinstance(raw, dict) else {})
        if built.get("action") == "credential":
            return built
        try:
            write_credential(destination, built)
        except OSError:
            return public_result(
                state="credential_permissions",
                wrote=False,
                logged_in=True,
                error="寫不進 ~/.trinity-cli/muse-credential。",
                hint="確認家目錄可寫，而且這個檔可以被設成 mode 600。",
            )
        return public_result(state="ok", wrote=True, fields=_present(built), logged_in=True)
    finally:
        _close(page)


def _present(document: dict) -> dict:
    auth = document.get("auth") if isinstance(document.get("auth"), dict) else {}
    return {
        "base_url": bool(document.get("base_url")),
        "vm_id": bool(document.get("vm_id")),
        "auth.type": auth.get("type") == "bearer",
        "auth.token": bool(auth.get("token")),
        "timeout_s": isinstance(document.get("timeout_s"), (int, float)) and document["timeout_s"] > 0,
        "notary_token": bool(document.get("notary_token")),
    }


def _close(page) -> None:
    if page is None:
        return
    close = getattr(page, "disconnect", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        return
