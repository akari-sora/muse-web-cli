import json

import pytest

from muse_web_cli.backends.api import ApiBackend
from muse_web_cli.cli import main
from muse_web_cli.errors import PageChanged
from muse_web_cli.flow import collect_chats
from muse_web_cli.model import exit_for, shape_chats, unsupported
from muse_web_cli.nav import guard_click, read_chats_flow
from muse_web_cli.selectors import KEY_SELECTORS, NEW_SIDE_CHAT, SWITCHER
from tests.fakes import ok_snapshot


def test_selftest_requires_the_switcher():
    assert "switcher" in KEY_SELECTORS
    assert "hatch-chat-switcher-trigger" in SWITCHER
    with pytest.raises(Exception):
        guard_click("button.new-side-chat")


def test_main_chat_only():
    chats = shape_chats(["聊天室", "主對話"], [{"title": "新副聊天室", "current": False}, {"title": "", "options": True}])
    assert chats == [{"title": "主對話", "is_current": True, "kind": "main"}]
    assert [item["kind"] for item in chats] == ["main"]


def test_main_and_side_chats():
    chats = shape_chats(
        ["聊天室", "主對話"],
        [
            {"title": "新副聊天室", "current": False},
            {"title": "旁邊", "current": True},
            {"title": "另一個", "current": False},
        ],
    )
    assert [item["kind"] for item in chats] == ["main", "side", "side"]
    assert chats[0]["is_current"] is False
    assert [item["is_current"] for item in chats[1:]] == [True, False]
    assert NEW_SIDE_CHAT[0] not in [item["title"] for item in chats]


def test_missing_panel_is_ui_changed_and_closes():
    calls = []

    def is_open():
        return False

    def open_panel():
        calls.append("open")

    def close_panel():
        calls.append("close")

    try:
        read_chats_flow(is_open=is_open, open_panel=open_panel, close_panel=close_panel, read=lambda: {"ok": True})
    except PageChanged as exc:
        assert exc.missing == "side_chats"
    else:
        raise AssertionError("expected PageChanged")
    assert calls == ["open", "close"]

    class Driver:
        def snapshot(self):
            return ok_snapshot()

        def read_chats(self):
            raise PageChanged("side_chats")

    payload = collect_chats(Driver())
    assert payload["state"] == "ui_changed"
    assert payload["chats"] == []
    assert payload["count"] == 0
    assert exit_for(payload["state"]) == 3


def test_panel_is_closed_after_a_read():
    state = {"open": False}
    calls = []

    def is_open():
        return state["open"]

    def open_panel():
        calls.append("open")
        state["open"] = True

    def close_panel():
        calls.append("close")
        state["open"] = False

    raw = read_chats_flow(
        is_open=is_open,
        open_panel=open_panel,
        close_panel=close_panel,
        read=lambda: {"ok": True, "mainSpans": ["聊天室", "主對話"], "rows": []},
    )
    assert raw["ok"] is True
    assert calls == ["open", "close"]
    assert state["open"] is False


def test_api_chats_are_unsupported(tmp_path, capsys):
    path = tmp_path / ".trinity-cli" / "muse-credential"
    path.parent.mkdir(parents=True)
    path.write_text("token-like", encoding="utf-8")
    path.chmod(0o600)
    payload = ApiBackend(path).chats()
    assert payload == unsupported("chats")
    assert payload["chats"] == []
    assert exit_for(payload["state"]) == 4
    code = main(["--backend", "api", "--json", "chats"], home=tmp_path)
    assert code == 4
    body = capsys.readouterr().out
    assert "token-like" not in body
    assert json.loads(body)["chats"] == []
