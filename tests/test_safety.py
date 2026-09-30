from pathlib import Path

from muse_web_cli.output import safe_text
from muse_web_cli.probes import MEMORY_JS, OBSERVER_JS, PANEL_JS, SNAPSHOT_JS


def test_page_scripts_do_not_touch_auth_material():
    blob = "\n".join((SNAPSHOT_JS, OBSERVER_JS, PANEL_JS, MEMORY_JS))
    for banned in (
        "document.cookie",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "Network.enable",
        "Storage.getCookies",
        ".value",
        "execCommand",
        ".focus(",
    ):
        assert banned not in blob
    assert "MutationObserver" in OBSERVER_JS
    assert "busy === false" in OBSERVER_JS
    assert "streaming === false" in OBSERVER_JS
    assert "innerText" in MEMORY_JS
    assert "hatch-chat-typing-indicator" in OBSERVER_JS


def test_sources_do_not_close_the_browser_or_read_profile_secrets():
    root = Path(__file__).resolve().parents[1] / "src"
    blob = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    for banned in (
        "browser.close(",
        "context.cookies",
        "storage_state",
        "Network.enable",
        "Storage.getCookies",
        "document.cookie",
        "pkill",
        "killall",
        "Login Data",
        "/Cookies",
    ):
        assert banned not in blob
    pyproject = (root.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert 'muse-web-cli = "muse_web_cli.cli:main"' in pyproject
    assert "\nmuse =" not in pyproject


def test_safe_text_strips_query_and_secret_assignments():
    cleaned = safe_text("see https://muse.ai/path?token=abc and cookie=SECRET wss://127.0.0.1/devtools/page/ID")
    assert "token=abc" not in cleaned
    assert "SECRET" not in cleaned
    assert "devtools/page" not in cleaned
    assert "https://muse.ai/path" in cleaned
