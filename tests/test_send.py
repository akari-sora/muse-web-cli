from muse_web_cli.backends.browser import BrowserBackend
from muse_web_cli.flow import WaitResult, perform_send
from muse_web_cli.model import Message
from muse_web_cli.nav import ALLOWED_CLICKS, guard_click, read_memory_flow, read_with_tab
from muse_web_cli.selectors import (
    AVATAR_BUTTON,
    EDITOR_CLOSE,
    MEMORY_FILE,
    SEND_BUTTON,
    SWITCHER,
    TAB_ACTIVITY,
    TAB_IDENTITY,
    TAB_PENDING,
)
from tests.fakes import ok_snapshot

import pytest


class FakeDriver:
    def __init__(self, outcome=None, messages=None):
        self.calls = []
        self.inserts = 0
        self.enters = 0
        self.outcome = outcome or WaitResult(True, "user", [])
        self.messages = messages or []

    def snapshot(self):
        self.calls.append("snapshot")
        return ok_snapshot(self.messages)

    def read_groups(self, target):
        self.calls.append("groups")
        return [{"title": "待審項目", "items": []}]

    def insert_text(self, text):
        self.inserts += 1
        if self.inserts > 1:
            raise AssertionError("resent")
        self.calls.append("insert")

    def press_enter(self):
        self.enters += 1
        if self.enters > 1:
            raise AssertionError("resent")
        self.calls.append("enter")

    def wait_outcome(self, **kwargs):
        self.calls.append("wait")
        return self.outcome


def test_send_timeout_never_resends():
    driver = FakeDriver(WaitResult(True, "reply", [Message("user", "hi")]))
    payload = perform_send(driver, "hi", wait=True, timeout=0.01)
    assert driver.inserts == 1
    assert driver.enters == 1
    assert payload["state"] == "timeout"
    assert payload["sent"] is True
    assert payload["attempted"] is True
    assert payload["hint"] == "nothing was sent again"
    assert driver.calls.count("insert") == 1


def test_nonempty_composer_does_not_send():
    class Dirty(FakeDriver):
        def insert_text(self, text):
            from muse_web_cli.errors import PageChanged

            raise PageChanged("composer_not_empty")

    payload = perform_send(Dirty(), "hi", wait=True, timeout=1)
    assert payload["state"] == "ui_changed"
    assert payload["attempted"] is False
    assert payload["sent"] is False
    assert "nothing was sent" in payload["error"]


def test_send_without_user_row_does_not_retry():
    driver = FakeDriver(WaitResult(True, "user", []))
    payload = perform_send(driver, "hi", wait=False, timeout=0.01)
    assert driver.inserts == 1
    assert payload["sent"] is False
    assert payload["state"] == "timeout"


def test_send_wait_prints_settled_reply():
    outcome = WaitResult(
        False,
        "reply",
        [
            Message("assistant", "old", busy=False, streaming=False, has_actions=True),
            Message("user", "ping"),
            Message("assistant", "pong", busy=False, streaming=False, has_actions=True),
        ],
    )
    payload = perform_send(FakeDriver(outcome), "ping", wait=True, timeout=5)
    assert payload["state"] == "ok"
    assert payload["reply"] == "pong"
    assert payload["presentation"] is False
    assert payload["sent"] is True


def test_headed_and_headless_share_status_and_send():
    sequences = []
    flags = []
    for headless in (True, False):
        driver = FakeDriver(WaitResult(True, "user", []))
        backend = BrowserBackend(driver, headless=headless)
        status = backend.status()
        backend.send("hi", wait=False, timeout=1)
        sequences.append(list(driver.calls))
        flags.append(status["headless"])
        assert status["state"] == "ok"
        assert status["pending"] == 0
    assert sequences[0] == sequences[1]
    assert flags == [True, False]
    assert sequences[0] == ["snapshot", "groups", "snapshot", "insert", "enter", "wait"]


def test_tab_restores_original_and_avatar_opens_collapsed_panel():
    clicks = []

    def click(selector):
        guard_click(selector)
        clicks.append(selector)

    def read():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        read_with_tab(
            panel_open=lambda: False,
            current_tab=lambda: TAB_ACTIVITY,
            click=click,
            read=read,
            target=TAB_PENDING,
        )
    assert clicks == [AVATAR_BUTTON, TAB_PENDING, TAB_ACTIVITY]


def test_memory_closes_editor_without_typing():
    clicks = []

    def click(selector):
        guard_click(selector)
        clicks.append(selector)

    text = read_memory_flow(
        panel_open=lambda: True,
        current_tab=lambda: TAB_ACTIVITY,
        click=click,
        read_text=lambda: "Facts\nhello",
    )
    assert text == "Facts\nhello"
    assert clicks == [TAB_IDENTITY, MEMORY_FILE, EDITOR_CLOSE, TAB_ACTIVITY]
    assert SEND_BUTTON not in ALLOWED_CLICKS
    assert SWITCHER in ALLOWED_CLICKS
    assert '[data-testid="hatch-side-chats-options"]' not in ALLOWED_CLICKS
    with pytest.raises(Exception):
        guard_click('[data-testid="hatch-dock-more"]')
    with pytest.raises(Exception):
        guard_click('[data-pel-click="connector_mail"]')
    with pytest.raises(Exception):
        guard_click('[data-testid="hatch-file-editor-maximize"]')


class AttachDriver(FakeDriver):
    def __init__(self, *args, fail_attach=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_attach = fail_attach

    def attach_files(self, paths):
        self.calls.append(("attach", tuple(paths)))
        if self.fail_attach:
            from muse_web_cli.errors import PageChanged

            raise PageChanged("attachment")

    def clear_attachments(self):
        self.calls.append("clear")

    def open_thread(self, session):
        self.calls.append(("open", session))


def test_attachments_go_in_before_the_text_and_send_once():
    outcome = WaitResult(False, "reply", [Message("user", "unzip"), Message("assistant", "done", busy=False, streaming=False, has_actions=True)])
    driver = AttachDriver(outcome)
    payload = perform_send(driver, "unzip", wait=True, timeout=5, attach=["/tmp/a.zip"])
    assert payload["state"] == "ok" and payload["reply"] == "done"
    assert driver.calls.index(("attach", ("/tmp/a.zip",))) < driver.calls.index("insert") < driver.calls.index("enter")


def test_a_file_that_does_not_attach_sends_nothing_and_is_removed():
    driver = AttachDriver(fail_attach=True)
    payload = perform_send(driver, "unzip", wait=True, timeout=5, attach=["/tmp/a.zip"])
    assert payload["state"] == "ui_changed" and payload["sent"] is False and payload["attempted"] is False
    assert "did not attach" in payload["error"]
    assert "clear" in driver.calls and "insert" not in driver.calls


def test_a_side_chat_send_opens_its_url_and_returns_to_main():
    outcome = WaitResult(False, "reply", [Message("user", "x"), Message("assistant", "ok", busy=False, streaming=False, has_actions=True)])
    driver = AttachDriver(outcome)
    BrowserBackend(driver, headless=True).send("x", wait=True, timeout=5, attach=["/tmp/a.zip"], session="f551b46a-2db4-4419-aff5-b8c40af46167")
    assert driver.calls[0] == ("open", "f551b46a-2db4-4419-aff5-b8c40af46167")
    assert driver.calls[-1] == ("open", None)


def test_attach_needs_a_regular_file(tmp_path, capsys):
    from muse_web_cli.cli import main

    assert main(["send", "hi", "--attach", str(tmp_path / "missing.zip")]) == 2
    assert "--attach needs a regular file" in capsys.readouterr().err


def test_an_attachment_prefix_does_not_hide_the_sent_message():
    from muse_web_cli.model import reply_text, user_count

    rows = [Message("user", "[file:application/zip workspace/user/files/b.zip] unzip it"),
            Message("assistant", "done", busy=False, streaming=False, has_actions=True)]
    assert user_count(rows, "unzip it") == 1
    assert reply_text(rows, "unzip it") == ("done", False)
