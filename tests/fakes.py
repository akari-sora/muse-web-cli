from muse_web_cli.config import paths_for
from muse_web_cli.model import Message, Snapshot
from muse_web_cli.selectors import KEY_SELECTORS, OPTIONAL_SELECTORS, PANEL_TAB_SELECTORS


def ok_snapshot(messages=None, **kwargs) -> Snapshot:
    selectors = {name: True for name in (*KEY_SELECTORS, *PANEL_TAB_SELECTORS, *OPTIONAL_SELECTORS)}
    base = dict(
        host="muse.ai",
        path="/",
        has_log=True,
        has_composer=True,
        has_password=False,
        panel_open=True,
        gate_text="Chat — Muse",
        messages=messages or [],
        selectors=selectors,
    )
    base.update(kwargs)
    return Snapshot(**base)


def paths(tmp_path):
    found = paths_for(tmp_path)
    found.profile.parent.mkdir(parents=True, exist_ok=True)
    return found


def chrome_command(profile, port=9333, headless=False) -> str:
    flags = f"--user-data-dir={profile} --remote-debugging-port={port}"
    if headless:
        flags += " --headless=new"
    return (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
        f"{flags} https://muse.ai/"
    )
