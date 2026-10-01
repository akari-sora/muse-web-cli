import json

from muse_web_cli.backends.api import ApiBackend
from muse_web_cli.model import exit_for

TOKEN = "user-supplied-token"


def _file(tmp_path, endpoints, mode=0o600):
    path = tmp_path / "muse-credential"
    path.write_text(
        json.dumps(
            {
                "base_url": "https://example.test",
                "auth": {"type": "bearer", "token": TOKEN},
                "endpoints": endpoints,
                "timeout_s": 5,
            }
        ),
        encoding="utf-8",
    )
    path.chmod(mode)
    return path


def _backend(tmp_path, endpoints, transport, **kwargs):
    return ApiBackend(_file(tmp_path, endpoints), transport=transport, **kwargs)


def test_each_capability_maps_a_sample_response(tmp_path):
    seen = []

    def transport(method, url, headers, body, timeout):
        seen.append((method, url, headers["Authorization"], body))
        samples = {
            "/status": {"state": "ok", "pending": 1, "latest_assistant_is_card": False, "headless": None, "missing": []},
            "/messages": {"name": "Muse", "lines": ["user: hi"], "messages": [{"role": "user", "text": "hi", "presentation": False}]},
            "/send": {"attempted": True, "sent": True, "reply": "ok", "presentation": False, "elapsed_ms": 3},
            "/pending": {"items": [{"title": "t", "detail": "d", "time": "now"}]},
            "/upcoming": {"groups": [{"title": "g", "items": [{"name": "n", "time": "t"}]}]},
            "/activity": {"groups": [{"title": "g", "items": [{"title": "t", "detail": "d", "time": "now"}]}]},
            "/memory": {"text": "Facts\n", "sections": ["Facts"]},
            "/chats": {"chats": [{"title": "main", "is_current": True, "kind": "main"}]},
        }
        path = url.split("?", 1)[0].rsplit(".test", 1)[-1]
        return 200, json.dumps(samples[path]).encode()

    endpoints = {
        "status": {"method": "GET", "path": "/status"},
        "messages": {"method": "GET", "path": "/messages"},
        "send": {"method": "POST", "path": "/send"},
        "pending": {"method": "GET", "path": "/pending"},
        "upcoming": {"method": "GET", "path": "/upcoming"},
        "activity": {"method": "GET", "path": "/activity"},
        "memory": {"method": "GET", "path": "/memory"},
        "chats": {"method": "GET", "path": "/chats"},
    }
    backend = _backend(tmp_path, endpoints, transport)
    status = backend.status()
    messages = backend.messages(5)
    sent = backend.send("hello", wait=False, timeout=2)
    assert status["pending"] == 1 and status["backend"] == "api"
    assert messages["messages"][0]["role"] == "user"
    assert "limit=5" in seen[1][1]
    assert sent["reply"] == "ok" and sent["text"] == "hello" and sent["sent"] is True
    assert backend.pending()["count"] == 1
    assert backend.upcoming()["groups"][0]["items"][0]["name"] == "n"
    assert backend.activity()["count"] == 1
    assert backend.memory()["chars"] == len("Facts\n")
    assert backend.chats()["count"] == 1
    assert all(item[2] == f"Bearer {TOKEN}" for item in seen)
    assert TOKEN not in json.dumps(status)


def test_missing_endpoint_is_unsupported_without_a_request(tmp_path):
    def transport(*args):
        raise AssertionError("network")

    payload = _backend(tmp_path, {}, transport).pending()
    assert payload["state"] == "unsupported"
    assert payload["items"] == []
    assert exit_for(payload["state"]) == 4


def test_auth_failure_is_session_expired(tmp_path):
    def transport(method, url, headers, body, timeout):
        return 401, b""

    payload = _backend(tmp_path, {"status": {"method": "GET", "path": "/status"}}, transport).status()
    assert payload["state"] == "session_expired"
    assert exit_for(payload["state"]) == 2
    assert TOKEN not in json.dumps(payload)


def test_server_error_is_exit_3(tmp_path):
    def transport(method, url, headers, body, timeout):
        return 503, b""

    payload = _backend(tmp_path, {"memory": {"method": "GET", "path": "/memory"}}, transport).memory()
    assert payload["state"] == "ui_changed"
    assert payload["text"] == ""
    assert exit_for(payload["state"]) == 3


def test_send_timeout_does_not_post_again(tmp_path):
    posts = []

    def transport(method, url, headers, body, timeout):
        posts.append(method)
        raise TimeoutError()

    payload = _backend(tmp_path, {"send": {"method": "POST", "path": "/send"}}, transport).send("nonce-text", wait=True, timeout=1)
    assert posts == ["POST"]
    assert payload["state"] == "timeout"
    assert payload["attempted"] is True
    assert payload["sent"] is False
    assert payload["hint"] == "nothing was sent again"
    assert payload["text"] == "nonce-text"
    assert exit_for(payload["state"]) == 3


def test_wait_polls_messages_and_does_not_resend(tmp_path):
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append((method, url))
        if method == "POST":
            return 200, json.dumps({"sent": True, "attempted": True, "reply": None}).encode()
        return 200, json.dumps({"messages": [{"role": "user", "text": "nonce-text"}, {"role": "assistant", "text": "ok"}]}).encode()

    payload = _backend(
        tmp_path,
        {
            "send": {"method": "POST", "path": "/send"},
            "messages": {"method": "GET", "path": "/messages"},
        },
        transport,
        sleep=lambda seconds: None,
    ).send("nonce-text", wait=True, timeout=2)
    assert [item[0] for item in calls].count("POST") == 1
    assert payload["reply"] == "ok"
    assert payload["state"] == "ok"


def test_windows_skips_mode_and_requires_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    path = _file(home, {"status": {"method": "GET", "path": "/status"}}, mode=0o644)

    def transport(method, url, headers, body, timeout):
        return 200, json.dumps({"pending": 0, "latest_assistant_is_card": False, "missing": []}).encode()

    inside = ApiBackend(path, transport=transport, platform="nt", home=home).status()
    assert inside["state"] == "ok"
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    moved = outside / "muse-credential"
    path.replace(moved)
    moved.chmod(0o644)
    blocked = ApiBackend(moved, transport=transport, platform="nt", home=home).status()
    assert blocked["state"] == "credential_permissions"
    assert "home" in blocked["error"]
    assert TOKEN not in json.dumps(blocked)


def test_server_error_text_is_scrubbed_and_cannot_claim_exit_4(tmp_path):
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signaturevalue"

    def transport(method, url, headers, body, timeout):
        payload = {
            "state": "unsupported",
            "error": f"access_token={TOKEN} Bearer {TOKEN} {jwt}",
            "hint": f"'token': '{TOKEN}'",
            "token": TOKEN,
        }
        return 200, json.dumps(payload).encode()

    status = _backend(tmp_path, {"status": {"method": "GET", "path": "/status"}}, transport).status()
    assert status["state"] == "ui_changed"
    assert exit_for(status["state"]) == 3
    assert "token" not in status
    blob = json.dumps(status)
    assert TOKEN not in blob
    assert jwt not in blob
