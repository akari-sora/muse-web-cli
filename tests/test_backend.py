import json
import os

from muse_web_cli import __version__
from muse_web_cli.backends.api import ApiBackend
from muse_web_cli.cli import main
from muse_web_cli.config import resolve_settings
from muse_web_cli.model import API_UNAVAILABLE, exit_for, messages_payload, unsupported
from muse_web_cli.selectors import API_UNAVAILABLE as SELECTOR_TEXT


CANARY = "SUPER_SECRET_CANARY_muse_token_value"


def test_backend_precedence(tmp_path):
    home = tmp_path / "home"
    config = home / ".trinity-cli" / "muse-web-cli.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"port": 2, "backend": "api", "headless": False, "autostart": True}), encoding="utf-8")
    from_file = resolve_settings(home=home, environ={})
    assert from_file.backend == "api"
    assert from_file.port == 2
    assert from_file.autostart is True
    assert from_file.headless is False
    from_env = resolve_settings(home=home, environ={"MUSE_WEB_BACKEND": "browser", "MUSE_WEB_CDP_PORT": "3"})
    assert from_env.backend == "browser"
    assert from_env.port == 3
    flagged = resolve_settings(
        home=home,
        port=9,
        backend="api",
        autostart=False,
        headless=True,
        environ={"MUSE_WEB_BACKEND": "browser", "MUSE_WEB_CDP_PORT": "3"},
    )
    assert flagged.backend == "api"
    assert flagged.port == 9
    assert flagged.autostart is False
    assert flagged.headless is True
    default = resolve_settings(home=tmp_path / "empty", environ={})
    assert default.backend == "browser"
    assert default.port == 9333
    assert default.headless is True
    assert default.autostart is False


def test_api_missing_file_is_unsupported(tmp_path):
    payload = ApiBackend(tmp_path / "muse-credential").status()
    assert payload["state"] == "unsupported"
    assert "muse-credential" in payload["error"]
    assert "muse-web-cli credential" in payload["error"]
    assert exit_for(payload["state"]) == 4
    assert CANARY not in json.dumps(payload)


def test_api_refuses_loose_permissions_and_never_reads(tmp_path):
    path = tmp_path / "muse-credential"
    path.write_text(CANARY, encoding="utf-8")
    os.chmod(path, 0o644)
    # Force the POSIX rule. On Windows the real platform skips the mode check.
    loose = ApiBackend(path, platform="posix").status()
    assert loose["state"] == "credential_permissions"
    assert "mode 600" in loose["error"]
    assert CANARY not in json.dumps(loose)
    assert exit_for(loose["state"]) == 2
    os.chmod(path, 0o600)
    path.write_text(json.dumps({"base_url": "https://example.test", "auth": {"type": "bearer", "token": CANARY}, "endpoints": {}}), encoding="utf-8")
    backend = ApiBackend(path)
    payloads = [
        backend.status(),
        backend.messages(5),
        backend.send("hello", wait=True, timeout=1),
        backend.pending(),
        backend.upcoming(),
        backend.activity(),
        backend.memory(),
        backend.chats(),
    ]
    blob = json.dumps(payloads)
    assert CANARY not in blob
    assert all(item["state"] == "unsupported" for item in payloads)
    assert "端點沒填（status）" in payloads[0]["error"]
    assert "vm_id" in payloads[0]["error"]
    assert payloads[2]["sent"] is False


def test_api_shapes_match_browser_shapes():
    browser_messages = messages_payload([], backend="browser", limit=5)
    api_messages = unsupported("messages")
    assert set(browser_messages) == set(api_messages)
    assert set(unsupported("status")) == {
        "backend",
        "state",
        "pending",
        "latest_assistant_is_card",
        "headless",
        "error",
        "hint",
        "missing",
    }
    assert unsupported("pending")["items"] == []
    assert unsupported("activity")["groups"] == []
    assert unsupported("chats")["chats"] == []
    assert exit_for("unsupported") == 4
    assert API_UNAVAILABLE == SELECTOR_TEXT


def test_cli_api_backend_json(tmp_path, capsys):
    code = main(["status", "--json", "--backend", "api"], home=tmp_path)
    assert code == 4
    missing = json.loads(capsys.readouterr().out)
    assert missing["state"] == "unsupported"
    cred = tmp_path / ".trinity-cli" / "muse-credential"
    cred.parent.mkdir(parents=True, exist_ok=True)
    cred.write_text(CANARY, encoding="utf-8")
    os.chmod(cred, 0o600)
    code = main(["--backend", "api", "--json", "messages", "--limit", "5"], home=tmp_path)
    assert code == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "ui_changed"
    assert "credential" in (payload.get("hint") or "")
    assert payload["name"] == "Muse"
    assert payload["messages"] == []
    assert CANARY not in json.dumps(payload)


def test_cli_help_and_limit(tmp_path, capsys):
    assert main(["--help"], home=tmp_path) == 0
    assert main(["messages", "--limit", "0"], home=tmp_path) == 2
    assert "muse-web-cli" in capsys.readouterr().out


def test_cli_version(tmp_path, capsys):
    assert main(["--version"], home=tmp_path) == 0
    assert capsys.readouterr().out.strip() == f"muse-web-cli {__version__}"


def test_wrong_auth_field_and_cleartext_are_exit_3(tmp_path):
    path = tmp_path / "muse-credential"
    path.write_text(
        json.dumps(
            {
                "base_url": "https://hatch.metaaivm.com",
                "vm_id": "vm-unit",
                "auth": {"type": "nope", "token": CANARY},
            }
        ),
        encoding="utf-8",
    )
    os.chmod(path, 0o600)
    wrong = ApiBackend(path).status()
    assert wrong["state"] == "ui_changed"
    assert exit_for(wrong["state"]) == 3
    assert CANARY not in json.dumps(wrong)
    assert "credential" in wrong["hint"]
    path.write_text(
        json.dumps(
            {
                "base_url": "http://hatch.metaaivm.com",
                "vm_id": "vm-unit",
                "auth": {"type": "bearer", "token": CANARY},
            }
        ),
        encoding="utf-8",
    )
    os.chmod(path, 0o600)
    clear = ApiBackend(path).status()
    assert clear["state"] == "ui_changed"
    assert exit_for(clear["state"]) == 3
    assert CANARY not in json.dumps(clear)
    assert "http://" not in json.dumps(clear)


def test_credential_lstat_error_is_exit_2(tmp_path, monkeypatch):
    from pathlib import Path

    path = tmp_path / "muse-credential"
    path.write_text("{}", encoding="utf-8")
    os.chmod(path, 0o600)

    def explode(self, *args, **kwargs):
        raise OSError(13, "denied")

    monkeypatch.setattr(Path, "lstat", explode)
    payload = ApiBackend(path).status()
    assert payload["state"] == "credential_permissions"
    assert exit_for(payload["state"]) == 2
    assert "再試" in payload["hint"]
