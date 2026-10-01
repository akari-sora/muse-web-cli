import base64
import json

from muse_web_cli.backends.api import ApiBackend
from muse_web_cli.cli import main
from muse_web_cli.model import exit_for

TOKEN = "unit-test-token"


class Script:
    def __init__(self, table, *, fail=None):
        self.table = table
        self.fail = fail or {}
        self.calls = []
        self.sent = False

    def call(self, service, verb, path, *, body, accept_first=False):
        key = path.split("?", 1)[0]
        self.calls.append((service, verb, key, body, accept_first, path))
        if key == "/chat/stream":
            self.sent = True
        if key in self.fail:
            raise self.fail[key]
        status, payload = self.table[key]
        if key == "/chat/history" and self.sent:
            payload = _history_after_send()
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        return status, raw

    def close(self):
        return None


def _file(tmp_path):
    path = tmp_path / "muse-credential"
    path.write_text(
        json.dumps(
            {
                "base_url": "https://hatch.metaaivm.com",
                "vm_id": "vm-unit",
                "auth": {"type": "bearer", "token": TOKEN},
                "timeout_s": 5,
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _table():
    return {
        "/health": (200, {"ok": True}),
        "/approvals": (
            200,
            {"pending_approvals": [{"display_name": "check", "reason": "d", "requested_at_ms": 1}]},
        ),
        "/chat/history": (
            200,
            {
                "messageIds": ["a", "b"],
                "messagesById": {
                    "a": {"role": "human", "content": "nonce-text"},
                    "b": {"role": "assistant", "content": "ok", "card": True},
                },
            },
        ),
        "/chat/stream": (200, {"accepted": True}),
        "/tasks": (
            200,
            {"schedules": [{"id": "job-1", "title": "morning", "schedule_key": "daily", "next_run_at_utc": 1700000000}]},
        ),
        "/activity": (
            200,
            {"days": [{"date": "today", "activities": [{"title": "note", "type": "goal", "timestamp": "1"}]}]},
        ),
        "/fs/read": (
            200,
            {"len": 18, "data_base64": base64.b64encode(b"Facts\nPreferences").decode("ascii")},
        ),
        "/api/session/list": (
            200,
            {
                "sessions": [
                    {"session_id": "main-1", "title": "主對話", "is_primary": True},
                    {"session_id": "side-1", "title": "副對話", "is_thread": True},
                ]
            },
        ),
        "/session/start": (200, {"session_id": "side-2", "title": "新聊天"}),
        "/session/rename": (200, {"ok": True}),
        "/session/delete": (200, {"deleted": True}),
    }


def _history_after_send():
    return {
        "messageIds": ["a", "b", "c", "d"],
        "messagesById": {
            "a": {"role": "human", "content": "nonce-text"},
            "b": {"role": "assistant", "content": "ok", "card": True},
            "c": {"role": "human", "content": "nonce-text"},
            "d": {"role": "assistant", "content": "fresh-ok"},
        },
    }


def _backend(tmp_path, script, **kwargs):
    return ApiBackend(_file(tmp_path), gateway_session=script, sleep=lambda seconds: None, **kwargs)


def test_gateway_covers_every_ui_operation(tmp_path):
    script = Script(_table())
    backend = _backend(tmp_path, script)
    status = backend.status()
    messages = backend.messages(2)
    sent = backend.send("nonce-text", wait=True, timeout=2)
    pending = backend.pending()
    upcoming = backend.upcoming()
    activity = backend.activity()
    memory = backend.memory()
    listed = backend.chats()
    created = backend.chats(action="create", title="新聊天")
    renamed = backend.chats(action="rename", session="side-1", title="改名")
    deleted = backend.chats(action="delete", session="side-1")
    switched = backend.chats(action="switch", session="side-1")
    blob = json.dumps([status, messages, sent, pending, upcoming, activity, memory, listed, created, renamed, deleted, switched])
    assert TOKEN not in blob
    assert status["state"] == "ok" and status["pending"] == 1 and status["latest_assistant_is_card"] is True
    assert messages["messages"][0] == {"role": "user", "text": "nonce-text", "presentation": False}
    assert messages["messages"][1]["presentation"] is True
    assert sent["sent"] is True and sent["reply"] == "fresh-ok"
    assert sum(1 for item in script.calls if item[1] == "POST" and item[2] == "/chat/stream") == 1
    assert pending["count"] == 1
    assert upcoming["groups"][0]["items"][0]["name"] == "morning"
    assert "daily" in upcoming["groups"][0]["items"][0]["time"]
    assert activity["count"] == 1
    assert "Facts" in memory["sections"]
    assert listed["chats"][0]["kind"] == "main" and listed["chats"][0]["session_id"] == "main-1"
    assert created["state"] == "ok" and renamed["state"] == "ok" and deleted["state"] == "ok"
    assert switched["chats"][1]["is_current"] is True
    paths = [item[2] for item in script.calls]
    for path in (
        "/health",
        "/approvals",
        "/chat/history",
        "/chat/stream",
        "/tasks",
        "/activity",
        "/fs/read",
        "/api/session/list",
        "/session/start",
        "/session/rename",
        "/session/delete",
    ):
        assert path in paths
    assert "/navigation/recents/touch" not in paths
    history = [item[5] for item in script.calls if item[2] == "/chat/history"]
    assert history and all("transcript_mode=messages" in item for item in history)
    activity = [item[5] for item in script.calls if item[2] == "/activity"]
    assert activity and "capabilities=ACTIVITY_FEED_GOALS" in activity[0]
    deleted = json.loads(next(item[3] for item in script.calls if item[2] == "/session/delete"))
    assert deleted == {"method": "/api/session/delete", "session_id": "side-1"}
    assert exit_for("ok") == 0


def test_gateway_auth_timeout_and_redaction(tmp_path):
    denied = Script({"/health": (401, b"token=unit-test-token")})
    payload = _backend(tmp_path, denied).status()
    assert payload["state"] == "session_expired"
    assert "auth.token" in payload["hint"]
    assert TOKEN not in json.dumps(payload)
    assert exit_for(payload["state"]) == 2

    stalled = Script(_table(), fail={"/chat/stream": TimeoutError()})
    sent = _backend(tmp_path, stalled).send("nonce-text", wait=True, timeout=1)
    assert [item[2] for item in stalled.calls] == ["/chat/history", "/chat/stream"]
    assert sent["state"] == "timeout"
    assert sent["attempted"] is True and sent["sent"] is False
    assert sent["hint"] == "沒有再送一次"
    assert TOKEN not in json.dumps(sent)

    messy = Script({"/health": (500, b"token=unit-test-token")})
    broken = _backend(tmp_path, messy).status()
    assert broken["state"] == "ui_changed"
    assert TOKEN not in json.dumps(broken)
    assert "redacted" in json.dumps(broken)


def test_switch_main_clears_the_saved_chat(tmp_path):
    script = Script(_table())
    backend = _backend(tmp_path, script)
    backend.chats(action="switch", session="side-1")
    again = backend.chats(action="switch", session="main")
    assert again["chats"][0]["is_current"] is True
    assert again["chats"][1]["is_current"] is False
    saved = tmp_path / "muse-current.json"
    assert not saved.exists()


def test_unknown_switch_names_the_next_step(tmp_path):
    script = Script(_table())
    missing = _backend(tmp_path, script).chats(action="switch", session="missing-chat")
    assert missing["state"] == "ui_changed"
    assert "chats" in missing["hint"]
    assert "--switch main" in missing["hint"]
    assert TOKEN not in json.dumps(missing)
    assert not (tmp_path / "muse-current.json").exists()
    assert exit_for(missing["state"]) == 3


def test_browser_mutation_points_at_the_api(tmp_path, capsys):
    code = main(["chats", "--create"], home=tmp_path)
    assert code == 2
    err = capsys.readouterr().err
    assert "vm_id" in err
    assert "--backend api" in err
