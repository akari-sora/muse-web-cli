import json
import os

from muse_web_cli.capture import (
    CAPTURE_JS,
    document_from,
    public_result,
    run_credential,
    write_credential,
)
from muse_web_cli.cli import main
from muse_web_cli.model import exit_for

TOKEN = "unit-token-not-a-real-secret"
VM = "vm-unit-id"
HOST = "https://vm-unit.example.test"


class Page:
    def __init__(self):
        self.closed = False

    def disconnect(self):
        self.closed = True


def _raw(**overrides):
    data = {
        "ok": True,
        "gatewayUrl": "https://11111111-1111-1111-1111-111111111111.metaaivm.com/",
        "vmName": "ignored-name",
        "token": TOKEN,
        "notary": "",
    }
    data.update(overrides)
    return data


def test_logged_out_session_runs_login_then_writes_mode_600(tmp_path):
    path = tmp_path / ".trinity-cli" / "muse-credential"
    page = Page()
    calls = {"login": 0, "reads": 0}

    def connect():
        calls["reads"] += 1
        if calls["reads"] == 1:
            return {"state": "ok"}, page
        return {"state": "ok"}, page

    def session_state(_page):
        return "session_expired" if calls["login"] == 0 else "ok"

    def login():
        calls["login"] += 1
        return {"logged_in": True, "state": "ok"}

    result = run_credential(
        path,
        connect=connect,
        login=login,
        capture=lambda _page: _raw(),
        session_state=session_state,
    )
    assert calls["login"] == 1
    assert result["wrote"] is True
    assert result["state"] == "ok"
    assert result["fields"]["auth.token"] is True
    assert result["fields"]["vm_id"] is True
    assert result["fields"]["notary_token"] is False
    assert TOKEN not in json.dumps(result)
    assert "11111111" not in json.dumps(result)
    assert page.closed is True
    if os.name != "nt":
        assert (path.stat().st_mode & 0o777) == 0o600
        assert (path.parent.stat().st_mode & 0o777) == 0o700
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["auth"]["type"] == "bearer"
    assert saved["auth"]["token"] == TOKEN
    assert saved["vm_id"] == "11111111-1111-1111-1111-111111111111"
    assert saved["base_url"] == "https://hatch.metaaivm.com"
    assert saved["timeout_s"] == 30


def test_login_not_finished_does_not_write(tmp_path):
    path = tmp_path / "muse-credential"
    page = Page()

    def connect():
        return {"state": "ok"}, page

    result = run_credential(
        path,
        connect=connect,
        login=lambda: {"logged_in": False, "state": "ok"},
        capture=lambda _page: _raw(),
        session_state=lambda _page: "session_expired",
    )
    assert result["state"] == "session_expired"
    assert result["wrote"] is False
    assert result["logged_in"] is False
    assert "登入" in result["error"] or "登入" in result["hint"]
    assert not path.exists()
    assert TOKEN not in json.dumps(result)
    assert exit_for(result["state"]) == 2


def test_browser_down_opens_login(tmp_path):
    path = tmp_path / "muse-credential"
    seen = {"login": 0}

    def connect():
        return {"state": "browser_down", "error": "browser is not available", "hint": "muse-web-cli login"}, None

    def login():
        seen["login"] += 1
        return {"logged_in": False, "state": "ok"}

    result = run_credential(
        path,
        connect=connect,
        login=login,
        capture=lambda _page: _raw(),
        session_state=lambda _page: "ok",
    )
    assert seen["login"] == 1
    assert result["wrote"] is False
    assert not path.exists()


def test_missing_token_is_exit_4_and_stdout_has_no_secret(tmp_path, capsys, monkeypatch):
    path = tmp_path / "muse-credential"
    page = Page()
    result = run_credential(
        path,
        connect=lambda: ({"state": "ok"}, page),
        login=lambda: (_ for _ in ()).throw(AssertionError("login")),
        capture=lambda _page: _raw(token=""),
        session_state=lambda _page: "ok",
    )
    assert result["state"] == "unsupported"
    assert result["wrote"] is False
    assert "auth.token" in result["error"]
    assert not path.exists()
    assert TOKEN not in json.dumps(result)
    assert exit_for(result["state"]) == 4

    monkeypatch.setattr("muse_web_cli.cli._run_credential", lambda settings: result)
    code = main(["--json", "credential"], home=tmp_path)
    printed = capsys.readouterr().out
    assert code == 4
    assert TOKEN not in printed
    assert "11111111" not in printed


def test_selector_mismatch_still_writes_without_opening_login(tmp_path):
    path = tmp_path / "muse-credential"
    page = Page()
    result = run_credential(
        path,
        connect=lambda: ({"state": "ok"}, page),
        login=lambda: (_ for _ in ()).throw(AssertionError("login")),
        capture=lambda _page: _raw(),
        session_state=lambda _page: "ui_changed",
    )
    assert result["wrote"] is True
    assert result["state"] == "ok"
    assert path.is_file()
    assert TOKEN not in json.dumps(result)


def test_login_then_selector_mismatch_still_writes(tmp_path):
    path = tmp_path / "muse-credential"
    page = Page()
    calls = {"n": 0}

    def connect():
        calls["n"] += 1
        if calls["n"] == 1:
            return {"state": "browser_down", "error": "down", "hint": "muse-web-cli login"}, None
        return {"state": "ok"}, page

    result = run_credential(
        path,
        connect=connect,
        login=lambda: {"logged_in": True, "state": "ok"},
        capture=lambda _page: _raw(),
        session_state=lambda _page: "ui_changed",
    )
    assert calls["n"] == 2
    assert result["wrote"] is True
    assert TOKEN not in json.dumps(result)
    assert "11111111" not in json.dumps(result)


def test_already_logged_in_does_not_open_login(tmp_path):
    path = tmp_path / "muse-credential"
    page = Page()
    result = run_credential(
        path,
        connect=lambda: ({"state": "ok"}, page),
        login=lambda: (_ for _ in ()).throw(AssertionError("login")),
        capture=lambda _page: _raw(notary="notary-unit"),
        session_state=lambda _page: "ok",
    )
    assert result["wrote"] is True
    assert result["fields"]["notary_token"] is True
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["notary_token"] == "notary-unit"
    assert "notary-unit" not in json.dumps(result)


def test_shared_gateway_uses_vm_name_and_public_result_hides_it():
    document, missing = document_from(
        {
            "ok": True,
            "gatewayUrl": "https://hatch.metaaivm.com/v1/noise",
            "vmName": VM,
            "token": TOKEN,
            "notary": "",
        }
    )
    assert missing == []
    assert document["base_url"] == "https://hatch.metaaivm.com"
    assert document["vm_id"] == VM
    shown = public_result(state="ok", wrote=True, fields={"base_url": True, "vm_id": True, "auth.token": True}, logged_in=True)
    blob = json.dumps(shown)
    assert VM not in blob
    assert TOKEN not in blob


def test_capture_script_does_not_read_cookies_or_storage():
    for banned in (
        "document.cookie",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "Network.enable",
        "Storage.getCookies",
    ):
        assert banned not in CAPTURE_JS
    assert "/api/hatch/token" in CAPTURE_JS


def test_write_credential_replaces_a_loose_file(tmp_path):
    path = tmp_path / "muse-credential"
    path.write_text("stale", encoding="utf-8")
    os.chmod(path, 0o644)
    write_credential(path, {"base_url": HOST, "vm_id": VM, "auth": {"type": "bearer", "token": TOKEN}, "timeout_s": 30})
    if os.name != "nt":
        assert (path.stat().st_mode & 0o777) == 0o600
    assert json.loads(path.read_text(encoding="utf-8"))["auth"]["token"] == TOKEN
