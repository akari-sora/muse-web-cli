from contextlib import contextmanager

import pytest

from muse_web_cli import cli
from muse_web_cli.config import paths_for, resolve_settings
from muse_web_cli.flow import collect_selftest, wait_rendered
from tests.fakes import ok_snapshot

HEADED = {"state": "ok", "action": "started", "port": 9333, "headless": False, "tracked": True, "pid": 5}
HEADLESS = {"state": "ok", "action": "started", "port": 9333, "headless": True, "tracked": True, "pid": 6}


class Page:
    def __init__(self, *snaps):
        self.snaps = list(snaps)
        self.disconnected = False

    def snapshot(self):
        return self.snaps.pop(0) if len(self.snaps) > 1 else self.snaps[0]

    def click(self, selector):  # pragma: no cover - the editor is never up in these tests
        raise AssertionError("no click expected")

    def disconnect(self):
        self.disconnected = True


def loading():
    return ok_snapshot(has_log=False, has_composer=False, selectors={})


def signed_out():
    return ok_snapshot(has_log=False, has_composer=False, has_password=True, host="muse.ai", path="/login", selectors={})


class Env:
    """Stands in for Chrome: records stop and launch calls, answers with a page per launch."""

    def __init__(self, monkeypatch, tmp_path, *, headless_page):
        self.calls = []
        self.page = headless_page
        self.settings = resolve_settings(home=tmp_path, environ={})
        self.headed_page = Page(ok_snapshot())

        @contextmanager
        def lock(path):
            yield

        def ensure(settings, *, mode, headless):
            self.calls.append(("ensure", mode, headless))
            return dict(HEADLESS) if headless else dict(HEADED)

        def stop(**kwargs):
            self.calls.append(("stop",))
            return {"state": "ok", "action": "stopped", "tracked": False, "pid": 5}

        def connect(port):
            headless = ("ensure", "start", True) in self.calls
            return self.page if headless else self.headed_page

        monkeypatch.setattr(cli, "file_lock", lock)
        monkeypatch.setattr(cli, "_ensure", ensure)
        monkeypatch.setattr(cli, "stop", stop)
        monkeypatch.setattr(cli, "list_processes", lambda: [])
        monkeypatch.setattr(cli, "connect", connect)
        monkeypatch.setattr(cli, "READY_SECONDS", 0.0)
        monkeypatch.setattr(cli, "_focus_warned", False)


def login(settings):
    return cli._run_lifecycle(settings, cli.argparse.Namespace(command="login"))


def test_login_relaunches_headless_once_signed_in(monkeypatch, tmp_path):
    env = Env(monkeypatch, tmp_path, headless_page=Page(ok_snapshot()))
    out = login(env.settings)
    assert env.calls == [("ensure", "login", False), ("stop",), ("ensure", "start", True)]
    assert out["headless"] is True
    assert out["tracked"] is True
    assert out["logged_in"] is True
    assert out["state"] == "ok"
    assert out["action"] == "relaunched_headless"
    assert env.headed_page.disconnected and env.page.disconnected


def test_headless_signed_out_reports_session_expired_and_does_not_loop(monkeypatch, tmp_path):
    env = Env(monkeypatch, tmp_path, headless_page=Page(signed_out()))
    out = login(env.settings)
    assert env.calls.count(("stop",)) == 1
    assert env.calls.count(("ensure", "start", True)) == 1
    assert out["state"] == "session_expired"
    assert out["logged_in"] is False
    assert out["headless"] is True
    assert "muse-web-cli login" in out["hint"]


def test_keep_window_keeps_the_headed_chrome(monkeypatch, tmp_path):
    env = Env(monkeypatch, tmp_path, headless_page=Page(ok_snapshot()))
    env.settings.keep_window = True
    out = login(env.settings)
    assert env.calls == [("ensure", "login", False)]
    assert out["headless"] is False


def test_untracked_headed_chrome_is_never_closed(monkeypatch, tmp_path):
    env = Env(monkeypatch, tmp_path, headless_page=Page(ok_snapshot()))
    monkeypatch.setattr(cli, "_ensure", lambda settings, **kw: {**HEADED, "tracked": False, "pid": None})
    out = login(env.settings)
    assert out["headless"] is False
    assert ("stop",) not in env.calls


def test_keep_window_precedence(tmp_path):
    (tmp_path / ".trinity-cli").mkdir()
    paths_for(tmp_path).config.write_text('{"keep_window": true}', encoding="utf-8")
    assert resolve_settings(home=tmp_path, environ={}).keep_window is True
    assert resolve_settings(home=tmp_path, environ={"MUSE_WEB_KEEP_WINDOW": "0"}).keep_window is False
    assert resolve_settings(home=tmp_path, environ={"MUSE_WEB_KEEP_WINDOW": "0"}, keep_window=True).keep_window is True
    assert resolve_settings(home=tmp_path / "none", environ={}).keep_window is False


def test_keep_window_flag_is_global():
    assert cli._split_globals(["login", "--keep-window"])[0] == ["login"]
    assert cli._split_globals(["login", "--keep-window"])[6] is True
    assert cli._split_globals(["login"])[6] is None


def test_later_command_on_a_tracked_headed_chrome_warns_once(monkeypatch, tmp_path, capsys):
    env = Env(monkeypatch, tmp_path, headless_page=Page(ok_snapshot()))
    monkeypatch.setattr(cli, "_ensure", lambda settings, **kw: dict(HEADED))
    first = cli._with_page(env.settings, mode="use", headless=True, kind="status", text="", fn=lambda page, ready: {"state": "ok"})
    cli._with_page(env.settings, mode="use", headless=True, kind="status", text="", fn=lambda page, ready: {"state": "ok"})
    assert "keyboard focus" in first["warning"]
    assert "muse-web-cli stop && muse-web-cli start --headless" in first["warning"]
    assert capsys.readouterr().err.count("warning:") == 1


@pytest.mark.parametrize(
    "ready, keep, mode",
    [
        (HEADLESS, False, "use"),
        ({**HEADED, "tracked": False}, False, "use"),
        (HEADED, True, "use"),
        (HEADED, False, "login"),
    ],
)
def test_no_warning_when_headless_untracked_kept_or_logging_in(monkeypatch, tmp_path, capsys, ready, keep, mode):
    env = Env(monkeypatch, tmp_path, headless_page=Page(ok_snapshot()))
    env.settings.keep_window = keep
    monkeypatch.setattr(cli, "_ensure", lambda settings, **kw: dict(ready))
    out = cli._with_page(env.settings, mode=mode, headless=True, kind="status", text="", fn=lambda page, r: {"state": "ok"})
    assert "warning" not in out
    assert capsys.readouterr().err == ""


def test_start_waits_for_the_page_after_launching(monkeypatch, tmp_path):
    env = Env(monkeypatch, tmp_path, headless_page=Page(ok_snapshot()))
    seen = []
    monkeypatch.setattr(cli, "_page_status", lambda settings, port: seen.append(port) or {"state": "ok"})
    args = cli.argparse.Namespace(command="start", headed=False, headless=True)
    out = cli._run_lifecycle(env.settings, args)
    assert seen == [9333]
    assert out["state"] == "ok"


def test_selftest_looks_again_once_when_the_page_is_still_loading():
    page = Page(loading(), ok_snapshot())
    sleeps = []
    payload = collect_selftest(page, sleep=sleeps.append)
    assert payload["state"] == "ok"
    assert sleeps == [3.0]


def test_selftest_does_not_wait_when_the_page_is_fine_and_gives_up_after_one_retry():
    sleeps = []
    assert collect_selftest(Page(ok_snapshot()), sleep=sleeps.append)["state"] == "ok"
    assert sleeps == []
    assert collect_selftest(Page(loading()), sleep=sleeps.append)["state"] == "ui_changed"
    assert sleeps == [3.0]


def test_wait_rendered_stops_as_soon_as_the_page_renders():
    page = Page(loading(), loading(), ok_snapshot())
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    snap, status = wait_rendered(page, 15.0, sleep=sleep, clock=lambda: now[0])
    assert status["state"] == "ok"
    assert now[0] == 1.0
