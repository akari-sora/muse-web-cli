import json
from pathlib import Path

import pytest

from muse_web_cli.backends.api import ApiBackend
from muse_web_cli.cli import main
from muse_web_cli.driver import CdpPage
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


def test_main_title_is_null_when_only_chrome_words_are_available():
    assert shape_chats(["聊天室"], []) == [{"title": None, "is_current": True, "kind": "main"}]
    assert shape_chats([], [], page_title="Muse")[0]["title"] is None
    assert shape_chats([], [], page_title="Chat — Muse")[0]["title"] is None
    assert shape_chats([], [], page_title="聊天室")[0]["title"] is None
    assert shape_chats([], [], outside_titles=["聊天室"], page_title="Muse")[0]["title"] is None


def test_main_title_uses_a_heading_or_document_title_and_not_the_chrome_label():
    from_heading = shape_chats([], [], outside_titles=["聊天室", "假文件標題"], page_title="Muse")
    assert from_heading[0]["title"] == "假文件標題"
    from_document = shape_chats([], [], page_title="假文件標題 - Muse")
    assert from_document[0]["title"] == "假文件標題"
    from_prefix = shape_chats([], [], page_title="Muse | 假文件標題")
    assert from_prefix[0]["title"] == "假文件標題"
    spans_win = shape_chats(["聊天室", "假主對話"], [], page_title="別的標題", outside_titles=["假文件標題"])
    assert spans_win[0]["title"] == "假主對話"
    whole = shape_chats([], [], page_title="專案 - 筆記")
    assert whole[0]["title"] == "專案 - 筆記"


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


class _Locator:
    def __init__(self, page):
        self._page = page

    def count(self):
        return self._page.count

    @property
    def first(self):
        return self

    def is_visible(self):
        return self._page.visible

    def click(self, timeout=None):
        self._page.clicks.append("click")


class _Page:
    def __init__(self, *, count, visible):
        self.count = count
        self.visible = visible
        self.clicks = []
        self.evaluated = []

        class _Keys:
            def press(key_self, key):
                self.clicks.append(key)

        self.keyboard = _Keys()

    def locator(self, selector):
        return _Locator(self)

    def evaluate(self, script, arg=None):
        self.evaluated.append("eval")
        return {"ok": True, "mainSpans": [], "rows": [], "pageTitle": "Muse", "outsideTitles": []}


def test_closed_sidebar_issues_no_click_and_uses_the_existing_chats_shape():
    with pytest.raises(PageChanged) as caught:
        read_chats_flow(is_open=lambda: False, read=lambda: {"ok": True})
    assert caught.value.missing == "side_chats"
    assert caught.value.hint == "請在 Muse 打開側欄後重試"
    assert caught.value.error == "讀不到側欄裡的對話清單"

    for count, visible in ((0, False), (1, False)):
        page = _Page(count=count, visible=visible)
        with pytest.raises(PageChanged) as closed:
            CdpPage(page, None).read_chats()
        assert page.clicks == []
        assert page.evaluated == []
        assert closed.value.hint == "請在 Muse 打開側欄後重試"

    class Driver:
        def snapshot(self):
            return ok_snapshot()

        def read_chats(self):
            raise PageChanged(
                "side_chats",
                hint="請在 Muse 打開側欄後重試",
                error="讀不到側欄裡的對話清單",
            )

    payload = collect_chats(Driver())
    assert set(payload) == {"backend", "state", "count", "chats", "error", "hint"}
    assert payload["state"] == "ui_changed"
    assert payload["error"] == "讀不到側欄裡的對話清單"
    assert payload["hint"] == "請在 Muse 打開側欄後重試"
    assert payload["chats"] == []
    assert payload["count"] == 0
    assert exit_for(payload["state"]) == 3


def test_open_sidebar_is_read_without_a_click():
    raw = read_chats_flow(
        is_open=lambda: True,
        read=lambda: {"ok": True, "mainSpans": ["聊天室", "主對話"], "rows": []},
    )
    assert raw["ok"] is True
    page = _Page(count=1, visible=True)
    read = CdpPage(page, None).read_chats()
    assert read["ok"] is True
    assert page.clicks == []
    assert page.evaluated == ["eval"]


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
