"""Start, reuse, and stop the dedicated Chrome. Never opens profile databases."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from muse_web_cli.config import Paths
from muse_web_cli.selectors import MUSE_URL

CHROME_CANDIDATES = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/google-chrome-stable"),
    Path("/usr/bin/chromium"),
    Path("/usr/bin/chromium-browser"),
)


@dataclass(frozen=True)
class Proc:
    pid: int
    command: str


def discover_chrome(explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.is_file() and os.access(path, os.X_OK) else None
    for candidate in CHROME_CANDIDATES:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def launch_argv(chrome: Path, profile: Path, port: int, *, headless: bool) -> list[str]:
    argv = [
        str(chrome),
        f"--user-data-dir={profile}",
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
        "--window-size=1440,900",
    ]
    if headless:
        argv.append("--headless=new")
    argv.append(MUSE_URL)
    return argv


def is_main_chrome(proc: Proc, profile: Path) -> bool:
    command = proc.command
    if "--type=" in command or "Helper" in command:
        return False
    if f"--user-data-dir={profile}" not in command:
        return False
    exe = command.split(" --", 1)[0]
    base = exe.rsplit("/", 1)[-1]
    return "Chrome" in exe or "Chromium" in exe or base in {"chrome", "chromium"}


def debug_port(command: str) -> int | None:
    match = re.search(r"--remote-debugging-port=(\d+)", command)
    if not match:
        return None
    return int(match.group(1))


def command_is_headless(command: str) -> bool:
    return "--headless" in command


def list_processes() -> list[Proc]:
    raw = subprocess.check_output(["ps", "-ax", "-o", "pid=,command="], text=True)
    found: list[Proc] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        pid_text, _, command = text.partition(" ")
        if pid_text.isdigit() and command:
            found.append(Proc(int(pid_text), command.strip()))
    return found


def port_open(port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_until_port(port: int, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_open(port):
            return True
        time.sleep(0.25)
    return False


def spawn(argv: list[str]) -> int:
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc.pid


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def kill_pid(pid: int) -> None:
    """Signal one pid. Callers must already have proved it is the tracked Chrome."""
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not alive(pid):
            return
        time.sleep(0.25)
    os.kill(pid, signal.SIGKILL)


def read_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(path, 0o600)


def clear_state(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


@contextmanager
def file_lock(path: Path):
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _result(
    *,
    state: str,
    action: str,
    port: int | None,
    headless: bool | None,
    tracked: bool,
    pid: int | None,
    error: str | None = None,
    hint: str | None = None,
) -> dict:
    return {
        "state": state,
        "action": action,
        "port": port,
        "headless": headless,
        "tracked": tracked,
        "pid": pid,
        "error": error,
        "hint": hint,
    }


def _matches_tracked(proc: Proc, profile: Path, port: int | None) -> bool:
    if not is_main_chrome(proc, profile):
        return False
    found = debug_port(proc.command)
    if port is not None and found is not None and found != port:
        return False
    return True


def ensure(
    *,
    paths: Paths,
    procs: list[Proc],
    port_open_fn: Callable[[], bool],
    spawn_fn: Callable[[list[str]], int],
    kill_fn: Callable[[int], None],
    alive_fn: Callable[[int], bool],
    wait_ready: Callable[[int], bool],
    mode: str,
    headless: bool,
    autostart: bool,
    chrome: Path | None,
    port: int,
) -> dict:
    """Connect to the profile's Chrome, or launch one. Never launches a second."""
    mains = [proc for proc in procs if is_main_chrome(proc, paths.profile)]
    state = read_state(paths.state)
    tracked_pid = state.get("pid") if isinstance(state.get("pid"), int) else None
    force_launch = False

    if mains:
        proc = mains[0]
        tracked = tracked_pid == proc.pid and _matches_tracked(proc, paths.profile, state.get("port"))
        owns_headless = tracked and command_is_headless(proc.command)
        if mode == "login" and owns_headless:
            kill_fn(proc.pid)
            for _ in range(20):
                if not alive_fn(proc.pid):
                    break
            else:
                return _result(
                    state="browser_down",
                    action="connected",
                    port=debug_port(proc.command),
                    headless=True,
                    tracked=True,
                    pid=proc.pid,
                    error="could not stop the headless Chrome this tool started",
                    hint="muse-web-cli stop",
                )
            clear_state(paths.state)
            mains = []
            force_launch = True
        else:
            found_port = debug_port(proc.command)
            if found_port is None:
                return _result(
                    state="profile_busy",
                    action="connected",
                    port=None,
                    headless=command_is_headless(proc.command),
                    tracked=False,
                    pid=proc.pid,
                    error="dedicated Chrome is already running without a debug port",
                    hint="Quit that Muse window, then run muse-web-cli start --headless",
                )
            return _result(
                state="ok",
                action="connected",
                port=found_port,
                headless=command_is_headless(proc.command),
                tracked=tracked,
                pid=proc.pid,
                error=None,
                hint=None,
            )

    if port_open_fn() and not force_launch:
        return _result(
            state="ok",
            action="connected",
            port=port,
            headless=None,
            tracked=False,
            pid=None,
            error=None,
            hint=None,
        )

    launch = mode in {"start", "login"} or (mode == "use" and autostart)
    if not launch:
        return _result(
            state="browser_down",
            action="not_tracked",
            port=port,
            headless=None,
            tracked=False,
            pid=None,
            error="debug port is not open",
            hint="muse-web-cli start --headless",
        )
    if chrome is None:
        return _result(
            state="browser_down",
            action="not_tracked",
            port=port,
            headless=None,
            tracked=False,
            pid=None,
            error="Google Chrome was not found",
            hint="Install Google Chrome, or set MUSE_WEB_CHROME",
        )
    want_headless = True if mode == "use" else (False if mode == "login" else headless)
    argv = launch_argv(chrome, paths.profile, port, headless=want_headless)
    pid = spawn_fn(argv)
    if not wait_ready(port):
        kill_fn(pid)
        return _result(
            state="browser_down",
            action="started",
            port=port,
            headless=want_headless,
            tracked=False,
            pid=None,
            error="Chrome exited before the debug port opened",
            hint="muse-web-cli login",
        )
    write_state(
        paths.state,
        {"pid": pid, "port": port, "headless": want_headless, "profile": str(paths.profile)},
    )
    return _result(
        state="ok",
        action="started",
        port=port,
        headless=want_headless,
        tracked=True,
        pid=pid,
        error=None,
        hint=None,
    )


def stop(
    *,
    paths: Paths,
    procs: list[Proc],
    kill_fn: Callable[[int], None],
) -> dict:
    """Stop only the Chrome whose pid this tool recorded. Never signal any other pid."""
    state = read_state(paths.state)
    pid = state.get("pid")
    port = state.get("port") if isinstance(state.get("port"), int) else None
    if not isinstance(pid, int):
        return _result(
            state="ok",
            action="not_tracked",
            port=port,
            headless=None,
            tracked=False,
            pid=None,
        )
    proc = next((item for item in procs if item.pid == pid), None)
    if proc is None:
        clear_state(paths.state)
        return _result(
            state="ok",
            action="not_tracked",
            port=port,
            headless=None,
            tracked=False,
            pid=None,
        )
    if not _matches_tracked(proc, paths.profile, port):
        return _result(
            state="ok",
            action="not_tracked",
            port=port,
            headless=None,
            tracked=False,
            pid=None,
            error="tracked pid is not the dedicated Muse Chrome",
            hint=None,
        )
    kill_fn(pid)
    clear_state(paths.state)
    return _result(
        state="ok",
        action="stopped",
        port=port,
        headless=bool(state.get("headless")),
        tracked=False,
        pid=pid,
    )
