from pathlib import Path

from muse_web_cli.chrome import Proc, ensure, is_main_chrome, launch_argv, stop, write_state
from tests.fakes import chrome_command, paths


def _ensure(tmp_path, **overrides):
    found = paths(tmp_path)
    spawned = []
    killed = []

    def spawn(argv):
        spawned.append(argv)
        return 50

    kwargs = dict(
        paths=found,
        procs=[],
        port_open_fn=lambda: False,
        spawn_fn=spawn,
        kill_fn=killed.append,
        alive_fn=lambda pid: False,
        wait_ready=lambda port: True,
        mode="use",
        headless=False,
        autostart=True,
        chrome=Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        port=9333,
    )
    kwargs.update(overrides)
    result = ensure(**kwargs)
    return result, spawned, killed, found


def test_autostart_launches_headless_only_when_port_is_free(tmp_path):
    result, spawned, killed, found = _ensure(tmp_path)
    assert result["action"] == "started"
    assert result["headless"] is True
    assert result["tracked"] is True
    assert "--headless=new" in spawned[0]
    assert f"--user-data-dir={found.profile}" in spawned[0]
    assert "Application Support/Google/Chrome" not in " ".join(spawned[0])
    assert found.state.exists()
    assert killed == []


def test_existing_profile_chrome_is_not_launched_again(tmp_path):
    found = paths(tmp_path)
    proc = Proc(99, chrome_command(found.profile, headless=False))
    result, spawned, killed, _ = _ensure(tmp_path, procs=[proc], port_open_fn=lambda: True)
    assert spawned == []
    assert killed == []
    assert result["action"] == "connected"
    assert result["port"] == 9333
    assert result["tracked"] is False
    assert not found.state.exists()


def test_profile_without_debug_port_does_not_spawn(tmp_path):
    found = paths(tmp_path)
    command = chrome_command(found.profile).replace(" --remote-debugging-port=9333", "")
    result, spawned, _, _ = _ensure(tmp_path, procs=[Proc(7, command)])
    assert spawned == []
    assert result["state"] == "profile_busy"


def test_port_already_open_does_not_spawn(tmp_path):
    result, spawned, _, found = _ensure(tmp_path, port_open_fn=lambda: True, autostart=True)
    assert spawned == []
    assert result["action"] == "connected"
    assert not found.state.exists()


def test_stop_kills_only_the_tracked_pid(tmp_path):
    found = paths(tmp_path)
    write_state(found.state, {"pid": 5, "port": 9333, "headless": True, "profile": str(found.profile)})
    killed = []
    ours = Proc(5, chrome_command(found.profile, headless=True))
    other = Proc(9, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    result = stop(paths=found, procs=[other, ours], kill_fn=killed.append)
    assert killed == [5]
    assert result["action"] == "stopped"
    assert not found.state.exists()


def test_stop_refuses_reused_pid(tmp_path):
    found = paths(tmp_path)
    write_state(found.state, {"pid": 5, "port": 9333, "headless": True})
    killed = []
    result = stop(paths=found, procs=[Proc(5, "python something-else")], kill_fn=killed.append)
    assert killed == []
    assert result["action"] == "not_tracked"
    assert found.state.exists()


def test_stop_without_state_kills_nothing(tmp_path):
    killed = []
    result = stop(paths=paths(tmp_path), procs=[Proc(5, "Google Chrome")], kill_fn=killed.append)
    assert killed == []
    assert result["action"] == "not_tracked"


def test_login_does_not_kill_an_external_chrome(tmp_path):
    found = paths(tmp_path)
    proc = Proc(99, chrome_command(found.profile, headless=True))

    def kill(pid):
        raise AssertionError(pid)

    result, spawned, _, _ = _ensure(tmp_path, procs=[proc], mode="login", headless=False, kill_fn=kill)
    assert spawned == []
    assert result["action"] == "connected"
    assert result["pid"] == 99


def test_login_restarts_only_our_headless_process(tmp_path):
    found = paths(tmp_path)
    write_state(found.state, {"pid": 5, "port": 9333, "headless": True, "profile": str(found.profile)})
    proc = Proc(5, chrome_command(found.profile, headless=True))
    result, spawned, killed, _ = _ensure(tmp_path, procs=[proc], mode="login", headless=False)
    assert killed == [5]
    assert "--headless=new" not in spawned[0]
    assert result["headless"] is False
    assert result["action"] == "started"


def test_headed_argv_has_no_headless_flag():
    argv = launch_argv(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), Path("/tmp/muse-profile"), 9333, headless=False)
    assert "--headless=new" not in argv
    headed = launch_argv(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), Path("/tmp/muse-profile"), 9333, headless=True)
    assert "--headless=new" in headed


def test_helper_processes_are_not_the_main_chrome(tmp_path):
    profile = paths(tmp_path).profile
    helper = Proc(3, chrome_command(profile) + " --type=renderer")
    assert is_main_chrome(helper, profile) is False
    assert is_main_chrome(Proc(4, chrome_command(profile)), profile) is True
