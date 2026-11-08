"""upcoming on pages with and without the Upcoming tab. Muse moved scheduled tasks into the Activity tab."""

import pytest

from muse_web_cli.driver import CdpPage
from muse_web_cli.errors import PageChanged
from muse_web_cli.flow import collect_selftest, collect_upcoming
from muse_web_cli.output import human
from muse_web_cli.probes import PANEL_JS, PANEL_STATE_JS, SNAPSHOT_JS
from muse_web_cli.selectors import TAB_ACTIVITY, TAB_IDENTITY, TAB_PENDING, TAB_UPCOMING
from tests.fakes import ok_snapshot

SHAPE = {"backend", "state", "count", "groups", "error", "hint"}


def _activity(header="2項排定任務", scheduled=None):
    if scheduled is None:
        scheduled = [
            {"title": "Heartbeat", "detail": "", "time": "每30分鐘"},
            {"title": "每日晨間簡報", "detail": "", "time": "上午8:06"},
        ]
    groups = [
        {"title": "今天", "items": [{"title": "讀了信箱", "detail": "3 封新信", "time": "上午9:00"}]},
        {"title": "昨天", "items": [{"title": "整理行事曆", "detail": "", "time": "下午5:12"}]},
    ]
    return ([{"title": header, "items": scheduled}] if header is not None else []) + groups


class Driver:
    """No Upcoming tab: the real driver raises PageChanged("upcoming_tab") from the locator count."""

    def __init__(self, activity=None, upcoming=None):
        self.targets = []
        self.activity = _activity() if activity is None else activity
        self.upcoming = upcoming

    def snapshot(self):
        snap = ok_snapshot()
        snap.selectors["upcoming_tab"] = self.upcoming is not None
        return snap

    def read_groups(self, target):
        self.targets.append(target)
        if target == TAB_UPCOMING:
            if self.upcoming is None:
                raise PageChanged("upcoming_tab")
            return self.upcoming
        if target == TAB_ACTIVITY:
            return self.activity
        raise AssertionError(target)


@pytest.mark.parametrize("header", ["2項排定任務", " 2 項排定任務 ", "2 scheduled tasks", "2 Scheduled Tasks"])
def test_without_the_upcoming_tab_upcoming_is_the_activity_tabs_scheduled_group(header):
    driver = Driver(_activity(header))
    payload = collect_upcoming(driver)
    assert payload["state"] == "ok"
    assert payload["count"] == 2
    assert payload["groups"] == [
        {
            "title": header,
            "items": [{"name": "Heartbeat", "time": "每30分鐘"}, {"name": "每日晨間簡報", "time": "上午8:06"}],
        }
    ]
    assert set(payload) == SHAPE
    assert driver.targets == [TAB_UPCOMING, TAB_ACTIVITY]


def test_with_the_upcoming_tab_nothing_changes():
    upcoming = [
        {
            "title": "排程",
            "items": [
                {"title": "Heartbeat", "detail": "", "time": "每30分鐘"},
                {"title": "晨報", "detail": "每天 08:06", "time": ""},
            ],
        }
    ]
    driver = Driver(upcoming=upcoming)
    payload = collect_upcoming(driver)
    assert payload["state"] == "ok"
    assert payload["groups"] == [
        {"title": "排程", "items": [{"name": "Heartbeat", "time": "每30分鐘"}, {"name": "晨報", "time": "每天 08:06"}]}
    ]
    assert set(payload) == SHAPE
    assert driver.targets == [TAB_UPCOMING]


@pytest.mark.parametrize("header", ["5項排定任務", "5 scheduled tasks"])
def test_a_header_larger_than_the_rows_is_reported_as_partial(header):
    payload = collect_upcoming(Driver(_activity(header)))
    assert payload["state"] == "ok"
    assert payload["count"] == 2
    assert payload["complete"] is False
    assert "5" in payload["hint"] and "2" in payload["hint"]
    assert "--backend api upcoming" in payload["hint"]
    text = human(payload)
    assert text.splitlines()[0] == "count=2 groups=1 complete=false"
    assert "hint=" in text


def test_no_scheduled_group_is_zero_only_when_the_activity_tab_loaded():
    payload = collect_upcoming(Driver(_activity(None)))
    assert payload["state"] == "ok"
    assert payload["count"] == 0
    assert payload["groups"] == []
    assert set(payload) == SHAPE
    empty = collect_upcoming(Driver([]))
    assert empty["state"] == "ui_changed"
    assert empty["error"] == "Muse 頁面結構對不上"
    assert empty["groups"] == []


def test_other_page_changes_do_not_fall_back_to_activity():
    class NoPanel(Driver):
        def read_groups(self, target):
            self.targets.append(target)
            raise PageChanged("avatar")

    driver = NoPanel()
    payload = collect_upcoming(driver)
    assert payload["state"] == "ui_changed"
    assert driver.targets == [TAB_UPCOMING]


def test_selftest_does_not_need_the_upcoming_tab():
    class Snap:
        def __init__(self, **missing):
            self.missing = missing

        def snapshot(self):
            snap = ok_snapshot(panel_open=True)
            snap.selectors.update({name: False for name in self.missing})
            return snap

    payload = collect_selftest(Snap(upcoming_tab=True))
    assert payload["state"] == "ok"
    assert payload["missing"] == []
    assert payload["present"]["upcoming_tab"] is False
    still = collect_selftest(Snap(upcoming_tab=True, pending_tab=True))
    assert still["state"] == "ui_changed"
    assert still["missing"] == ["pending_tab"]


_LABELS = {TAB_PENDING: "核可工具", TAB_ACTIVITY: "動態", TAB_IDENTITY: "身分"}


class _Locator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    def count(self):
        return 0 if self.selector == TAB_UPCOMING else 1

    @property
    def first(self):
        return self

    def click(self, timeout=None):
        self.page.clicks.append(self.selector)
        self.page.label = _LABELS[self.selector]


class _NewPanelPage:
    """The status panel as Muse shows it now: 動態 / 核可工具 / 身分, no 近期."""

    def __init__(self, label):
        self.label = label
        self.clicks = []

    def locator(self, selector):
        return _Locator(self, selector)

    def evaluate(self, script, arg=None):
        if script == SNAPSHOT_JS:
            present = {name: True for name in ("log", "composer", "switcher", "avatar", "pending_tab", "activity_tab", "identity_tab", "panel")}
            present["upcoming_tab"] = False
            return {"host": "muse.ai", "path": "/", "hasLog": True, "hasComposer": True, "panelOpen": True, "present": present, "messages": []}
        if script == PANEL_STATE_JS:
            return {"open": True, "label": self.label}
        if script == PANEL_JS:
            assert self.label == "動態"
            return {"groups": _activity()}
        raise AssertionError("unexpected script")


@pytest.mark.parametrize("label, clicks", [("動態", []), ("核可工具", [TAB_ACTIVITY, TAB_PENDING])])
def test_the_driver_finds_no_upcoming_tab_without_clicking_it(monkeypatch, label, clicks):
    monkeypatch.setattr("muse_web_cli.driver.time.sleep", lambda _: None)
    page = _NewPanelPage(label)
    payload = collect_upcoming(CdpPage(page, None))
    assert payload["state"] == "ok"
    assert [item["name"] for item in payload["groups"][0]["items"]] == ["Heartbeat", "每日晨間簡報"]
    assert len(payload["groups"]) == 1
    assert page.clicks == clicks
    assert page.label == label
