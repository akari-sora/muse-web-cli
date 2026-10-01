import json
import subprocess
from pathlib import Path

from muse_web_cli.chrome import (
    Proc,
    alive,
    discover_chrome,
    ensure,
    headed_needs_display,
    write_state,
    is_main_chrome,
    kill_pid,
    parse_windows_process_json,
    profile_lock_held,
    spawn,
)
from muse_web_cli.cli import configure_stdio
from muse_web_cli.config import resolve_settings
from tests.fakes import chrome_command, paths


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_windows_chrome_discovery(tmp_path, monkeypatch):
    chrome = _touch(tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe")
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    found = discover_chrome(platform="win32", environ={"PROGRAMFILES": str(tmp_path), "LOCALAPPDATA": ""}, which=lambda name: None)
    assert found == chrome


def test_linux_chrome_discovery_uses_which(tmp_path):
    binary = _touch(tmp_path / "google-chrome")
    found = discover_chrome(platform="linux", environ={}, which=lambda name: str(binary) if name == "google-chrome" else None)
    assert found == binary


def test_macos_candidates_still_win(tmp_path, monkeypatch):
    monkeypatch.setattr("muse_web_cli.chrome.MAC_CHROME", (tmp_path / "missing",))
    binary = _touch(tmp_path / "Google Chrome")
    monkeypatch.setattr("muse_web_cli.chrome.MAC_CHROME", (binary,))
    assert discover_chrome(platform="darwin", which=lambda name: None) == binary


def test_explicit_chrome_override(tmp_path):
    binary = _touch(tmp_path / "chrome")
    assert discover_chrome(str(binary), platform="linux", which=lambda name: None) == binary
    assert discover_chrome(str(tmp_path / "absent"), platform="linux") is None


def test_chrome_flag_beats_env(tmp_path):
    home = tmp_path / "home"
    settings = resolve_settings(home=home, chrome="/flag/chrome", environ={"MUSE_WEB_CHROME": "/env/chrome"})
    assert settings.chrome == "/flag/chrome"
    from_env = resolve_settings(home=home, environ={"MUSE_WEB_CHROME": "/env/chrome"})
    assert from_env.chrome == "/env/chrome"


def test_linux_and_windows_process_names(tmp_path):
    profile = tmp_path / "muse-profile"
    linux = f"/usr/bin/google-chrome --user-data-dir={profile} --remote-debugging-port=9333"
    windows = f'"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --user-data-dir="{profile}" --remote-debugging-port=9333'
    assert is_main_chrome(Proc(1, linux), profile)
    assert is_main_chrome(Proc(2, windows), profile)
    helper = f"/usr/bin/google-chrome --type=renderer --user-data-dir={profile}"
    assert not is_main_chrome(Proc(3, helper), profile)


def test_windows_process_json():
    raw = json.dumps([{"ProcessId": 4, "CommandLine": "chrome.exe --user-data-dir=C:\\p"}, {"ProcessId": 5, "CommandLine": None}])
    found = parse_windows_process_json(raw)
    assert [(item.pid, item.command.startswith("chrome")) for item in found] == [(4, True)]


def test_windows_kill_uses_taskkill(monkeypatch):
    calls = []
    monkeypatch.setattr("muse_web_cli.chrome.sys.platform", "win32")
    monkeypatch.setattr("muse_web_cli.chrome.alive", lambda pid: calls.count("term") == 0)
    monkeypatch.setattr("muse_web_cli.chrome.time.sleep", lambda seconds: None)

    def run(argv, **kwargs):
        calls.append("force" if "/F" in argv else "term")

    monkeypatch.setattr("muse_web_cli.chrome.subprocess.run", run)
    kill_pid(9)
    assert calls[0] == "term"


def test_windows_alive_does_not_signal_zero(monkeypatch):
    monkeypatch.setattr("muse_web_cli.chrome.sys.platform", "win32")
    monkeypatch.setattr("muse_web_cli.chrome._windows_alive", lambda pid: pid == 3)

    def boom(*args):
        raise AssertionError("os.kill")

    monkeypatch.setattr("muse_web_cli.chrome.os.kill", boom)
    assert alive(3) is True
    assert alive(4) is False


def test_windows_spawn_does_not_use_setsid(monkeypatch):
    monkeypatch.setattr("muse_web_cli.chrome.sys.platform", "win32")
    seen = {}

    class Proc:
        pid = 8

    def popen(argv, **kwargs):
        seen.update(kwargs)
        return Proc()

    monkeypatch.setattr(subprocess, "Popen", popen)
    assert spawn(["chrome"]) == 8
    assert "start_new_session" not in seen
    assert "creationflags" in seen


def test_singleton_lock_and_windows_lockfile(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    lock = profile / "SingletonLock"
    lock.symlink_to("host-15")
    assert profile_lock_held(profile, platform="linux", alive_fn=lambda pid: pid == 15) is True
    assert profile_lock_held(profile, platform="linux", alive_fn=lambda pid: False) is False
    assert profile_lock_held(profile, platform="win32") is False
    (profile / "lockfile").write_text("held", encoding="utf-8")

    def held(lock_path):
        return lock_path.name == "lockfile"

    # The Windows branch opens the file with msvcrt, which this host does not import.
    # A missing lockfile is the portable half; a present lockfile is covered by the helper's contract via a stand-in.
    bare = tmp_path / "empty"
    bare.mkdir()
    assert profile_lock_held(bare, platform="win32") is False
    assert held(profile / "lockfile") is True


def test_linux_headed_login_needs_a_display(tmp_path):
    found = paths(tmp_path)
    result = ensure(
        paths=found,
        procs=[],
        port_open_fn=lambda: False,
        spawn_fn=lambda argv: 1,
        kill_fn=lambda pid: None,
        alive_fn=lambda pid: False,
        wait_ready=lambda port: True,
        mode="login",
        headless=False,
        autostart=False,
        chrome=Path("/usr/bin/google-chrome"),
        port=9333,
        platform="linux",
        environ={},
    )
    assert result["state"] == "browser_down"
    assert "xvfb-run" in result["hint"]
    write_state(found.state, {"pid": 5, "port": 9333, "headless": True, "profile": str(found.profile)})
    killed = []
    kept = ensure(
        paths=found,
        procs=[Proc(5, chrome_command(found.profile, headless=True))],
        port_open_fn=lambda: False,
        spawn_fn=lambda argv: 1,
        kill_fn=killed.append,
        alive_fn=lambda pid: True,
        wait_ready=lambda port: True,
        mode="login",
        headless=False,
        autostart=False,
        chrome=Path("/usr/bin/google-chrome"),
        port=9333,
        platform="linux",
        environ={},
    )
    assert killed == []
    assert kept["pid"] == 5
    assert kept["state"] == "browser_down"
    assert not headed_needs_display(True, "linux", {})
    assert headed_needs_display(False, "linux", {"DISPLAY": ":1"}) is False


def test_windows_stdio_reconfigure(monkeypatch):
    monkeypatch.setattr("muse_web_cli.cli.sys.platform", "win32")
    seen = []

    class Stream:
        def reconfigure(self, **kwargs):
            seen.append(kwargs)

    monkeypatch.setattr("muse_web_cli.cli.sys.stdout", Stream())
    monkeypatch.setattr("muse_web_cli.cli.sys.stderr", Stream())
    configure_stdio()
    assert seen == [{"encoding": "utf-8", "errors": "replace"}, {"encoding": "utf-8", "errors": "replace"}]
