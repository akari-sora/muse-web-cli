import json
from unittest import mock

from muse_web_cli.flow import message_from_raw
from muse_web_cli.model import (
    Message,
    assess,
    exit_for,
    is_settled,
    messages_payload,
    public_message,
    reply_ready,
    reply_text,
    select_messages,
    user_count,
    visible_messages,
)
from tests.fakes import ok_snapshot


def test_status_ok_and_card():
    snap = ok_snapshot(
        [
            Message("user", "hi"),
            Message("assistant", "card", presentation=True),
        ]
    )
    status = assess(snap)
    assert status["state"] == "ok"
    assert status["latest_assistant_is_card"] is True
    assert exit_for(status["state"]) == 0


def test_session_expired_on_password_and_on_login_url():
    expired = assess(ok_snapshot(has_log=False, has_composer=False, has_password=True, selectors={}))
    assert expired["state"] == "session_expired"
    assert expired["hint"] == "muse-web-cli login"
    assert exit_for(expired["state"]) == 2
    redirected = assess(ok_snapshot(host="www.facebook.com", path="/login.php", has_log=False, has_composer=False, selectors={}))
    assert redirected["state"] == "session_expired"


def test_signed_out_landing_page_is_session_expired_not_ui_changed():
    for heading in ("登入或建立帳號", "Log in or create an account"):
        status = assess(
            ok_snapshot(
                host="muse.ai",
                path="/",
                has_log=False,
                has_composer=False,
                selectors={},
                gate_text=f"Muse — Your Personal AI Agent\n{heading}",
            )
        )
        assert status["state"] == "session_expired"
        assert status["hint"] == "muse-web-cli login"
        assert status["missing"] == []
        assert exit_for(status["state"]) == 2


def test_status_waits_for_a_just_started_page_to_render():
    from muse_web_cli.flow import collect_status

    blank = ok_snapshot(has_log=False, has_composer=False, selectors={}, gate_text="")
    signed_out = ok_snapshot(
        has_log=False, has_composer=False, selectors={}, gate_text="Muse\n登入或建立帳號"
    )

    class Driver:
        def __init__(self):
            self.shots = [blank, blank, signed_out]

        def snapshot(self):
            return self.shots.pop(0) if len(self.shots) > 1 else self.shots[0]

    sleeps = []
    with mock.patch("muse_web_cli.flow.time.sleep", side_effect=sleeps.append):
        status = collect_status(Driver())
    assert status["state"] == "session_expired"
    assert len(sleeps) == 2


def test_a_page_with_nothing_known_is_ui_changed_after_the_settle_window():
    from muse_web_cli.flow import SETTLE_SECONDS, settled_snapshot

    blank = ok_snapshot(has_log=False, has_composer=False, selectors={}, gate_text="")

    class Driver:
        def snapshot(self):
            return blank

    ticks = iter(range(0, 100))
    _, status = settled_snapshot(Driver(), sleep=lambda _: None, clock=lambda: float(next(ticks)))
    assert status["state"] == "ui_changed"
    assert next(ticks) <= SETTLE_SECONDS + 3


def test_login_phrase_in_a_live_chat_is_ignored():
    live = ok_snapshot(gate_text="Log in or create an account")
    assert assess(live)["state"] == "ok"


def test_region_blocked_only_when_chat_is_down():
    blocked = assess(
        ok_snapshot(
            has_log=False,
            has_composer=False,
            selectors={},
            gate_text="Muse is not available in your region",
        )
    )
    assert blocked["state"] == "region_blocked"
    assert exit_for(blocked["state"]) == 2
    live = ok_snapshot(gate_text="not available in your region")
    assert assess(live)["state"] == "ok"


def test_bot_wall_is_session_expired():
    status = assess(ok_snapshot(has_log=False, has_composer=False, selectors={}, gate_text="confirm you're human"))
    assert status["state"] == "session_expired"
    assert status["hint"] == "muse-web-cli login"


def test_missing_selector_is_ui_changed():
    snap = ok_snapshot()
    snap.selectors["composer"] = False
    snap.has_composer = False
    status = assess(snap)
    assert status["state"] == "ui_changed"
    assert "composer" in status["missing"]
    assert exit_for(status["state"]) == 3


def test_chat_ignores_gate_canary():
    snap = ok_snapshot(gate_text="cookie=SECRETCOOKIEVALUE captcha")
    blob = json.dumps(assess(snap))
    assert "SECRETCOOKIEVALUE" not in blob
    assert assess(snap)["state"] == "ok"


def test_typing_indicator_is_filtered():
    messages = [
        Message("user", "hi"),
        Message("assistant", "…", typing=True, busy=True, streaming=True),
        Message("status", "typing", typing=True),
        Message("assistant", "done", busy=False, streaming=False, has_actions=True),
    ]
    assert [item.text for item in visible_messages(messages)] == ["hi", "done"]


def test_completion_needs_both_flags():
    assert is_settled(Message("assistant", "ok", busy=False, streaming=False, has_actions=True))
    assert not is_settled(Message("assistant", "ok", busy=False, streaming=True, has_actions=True))
    assert not is_settled(Message("assistant", "ok", busy=True, streaming=False, has_actions=True))
    assert not is_settled(Message("assistant", "ok", busy=False, streaming=None, has_actions=True))
    assert not is_settled(Message("assistant", "ok", busy=None, streaming=False, has_actions=True))
    assert not is_settled(Message("assistant", "ok", busy=False, streaming=False, has_actions=False))
    assert is_settled(Message("assistant", "card", presentation=True))
    assert not is_settled(Message("assistant", "type", typing=True, busy=False, streaming=False, has_actions=True))
    assert is_settled(Message("assistant", "ok", busy=None, streaming=None, has_actions=True))
    assert not is_settled(Message("assistant", "ok", busy=None, streaming=None, has_actions=False))


def test_messages_shape_and_order():
    messages = [Message("user", str(i), presentation=False) for i in range(10)]
    messages[9] = Message("assistant", "9", presentation=True)
    payload = messages_payload(messages, backend="browser", limit=3)
    assert list(payload) == ["backend", "state", "name", "lines", "messages", "error", "hint"]
    assert payload["name"] == "Muse"
    assert payload["lines"] == ["user: 7", "user: 8", "assistant: 9"]
    assert list(payload["messages"][0]) == ["role", "text", "presentation"]
    assert payload["messages"][-1]["presentation"] is True
    assert [item.text for item in select_messages(messages, 3)] == ["7", "8", "9"]


def test_reply_uses_the_new_turn_only():
    before = [Message("user", "hi"), Message("assistant", "old", busy=False, streaming=False, has_actions=True)]
    after = before + [
        Message("user", "hi"),
        Message("assistant", "new", busy=False, streaming=False, has_actions=True),
    ]
    assert user_count(after, "hi") > user_count(before, "hi")
    assert reply_ready(after, "hi")
    assert reply_text(after, "hi") == ("new", False)
    streaming = before + [Message("user", "hi"), Message("assistant", "new", busy=False, streaming=True, has_actions=False)]
    assert not reply_ready(streaming, "hi")


def test_offscreen_user_label_is_stripped():
    item = message_from_raw({"role": "user", "text": "你：trinity 測試"})
    labeled = message_from_raw({"role": "user", "text": "用戶訊息：trinity 測試"})
    assert item.text == "trinity 測試"
    assert labeled.text == "trinity 測試"
    assert user_count([item, labeled], "trinity 測試") == 2
    assert message_from_raw({"role": "assistant", "text": "你：留下"}).text == "你：留下"


def test_public_message_hides_internal_flags():
    assert public_message(Message("assistant", "x", busy=False, streaming=False, has_actions=True)) == {
        "role": "assistant",
        "text": "x",
        "presentation": False,
    }
