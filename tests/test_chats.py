import json
from pathlib import Path

import pytest

from muse_web_cli.backends.api import ApiBackend
from muse_web_cli.cli import main
from muse_web_cli.errors import PageChanged
from muse_web_cli.flow import collect_chats
from muse_web_cli.model import assess, exit_for, shape_chats
from muse_web_cli.nav import ALLOWED_CLICKS, guard_click, read_chats_flow
from muse_web_cli.selectors import (
    KEY_SELECTORS,
    NEW_SIDE_CHAT,
    SWITCHER,
    SWITCHER_TESTIDS,
    switcher_in_markup,
    switcher_selectors,
)
from tests.fakes import ok_snapshot

_FIXTURES = Path(__file__).parent / "fixtures"


def _switcher_status(markup: str) -> dict:
    snap = ok_snapshot()
    snap.selectors["switcher"] = switcher_in_markup(markup) is not None
    return assess(snap)


def test_selftest_requires_the_switcher():
    assert "switcher" in KEY_SELECTORS
    assert SWITCHER_TESTIDS[0] == "hatch-nav-chat"
    assert "hatch-chat-switcher-trigger" in SWITCHER
    assert SWITCHER.index("hatch-nav-chat") < SWITCHER.index("hatch-chat-switcher-trigger")
    for selector in switcher_selectors():
        assert selector in ALLOWED_CLICKS
        guard_click(selector)
    with pytest.raises(Exception):
        guard_click("button.new-side-chat")


def test_sidebar_and_dropdown_both_count_as_the_switcher():
    sidebar = (_FIXTURES / "switcher_sidebar.html").read_text(encoding="utf-8")
    dropdown = (_FIXTURES / "switcher_trigger.html").read_text(encoding="utf-8")
    assert "假主對話" in dropdown
    assert "hatch-chat-switcher-trigger" not in sidebar
    assert "hatch-nav-chat" not in dropdown
    assert switcher_in_markup(sidebar) == "hatch-nav-chat"
    assert switcher_in_markup(dropdown) == "hatch-chat-switcher-trigger"
    assert switcher_in_markup(sidebar + dropdown) == "hatch-nav-chat"
    assert _switcher_status(sidebar)["state"] == "ok"
    assert _switcher_status(dropdown)["state"] == "ok"


def test_missing_switcher_is_still_ui_changed():
    markup = (_FIXTURES / "switcher_missing.html").read_text(encoding="utf-8")
    assert switcher_in_markup(markup) is None
    status = _switcher_status(markup)
    assert status["state"] == "ui_changed"
    assert status["error"] == "Muse 頁面結構對不上"
    assert status["missing"] == ["switcher"]
    assert exit_for(status["state"]) == 3


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
    path.write_text(
        json.dumps({"base_url": "https://example.test", "auth": {"type": "bearer", "token": "token-like"}, "endpoints": {}}),
        encoding="utf-8",
    )
    path.chmod(0o600)
    payload = ApiBackend(path).chats()
    assert payload["state"] == "unsupported"
    assert payload["chats"] == []
    assert exit_for(payload["state"]) == 4
    code = main(["--backend", "api", "--json", "chats"], home=tmp_path)
    assert code == 4
    body = capsys.readouterr().out
    assert "token-like" not in body
    assert json.loads(body)["chats"] == []


def test_session_on_the_browser_backend_is_refused_before_chrome(tmp_path, capsys, monkeypatch):
    import muse_web_cli.cli as cli

    def no_chrome(*args, **kwargs):
        raise AssertionError("chrome")

    monkeypatch.setattr(cli, "_ensure", no_chrome)
    for argv in (["send", "--session", "side-1", "--", "hi"], ["messages", "--session", "side-1"]):
        assert cli.main(argv, home=tmp_path) == 2
        err = capsys.readouterr().err
        assert "--backend api" in err
        assert "沒有送出" in err
