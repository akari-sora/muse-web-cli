"""Run the chat selectors in headless Chromium.

Skipped when this interpreter has no playwright. The system python does not
ship it; the uv tool env at
~/.local/share/uv/tools/muse-web-cli/bin/python3 does.
"""

from pathlib import Path

import pytest

pytest.importorskip(
    "playwright.sync_api",
    reason=(
        "系統 python 沒裝 playwright；"
        "uv 工具環境 ~/.local/share/uv/tools/muse-web-cli/bin/python3 有裝"
    ),
)

from playwright.sync_api import sync_playwright

from muse_web_cli.driver import CdpPage
from muse_web_cli.flow import collect_chats
from muse_web_cli.model import shape_chats
from muse_web_cli.probes import CHATS_JS, SNAPSHOT_JS

_FIXTURES = Path(__file__).parent / "fixtures"
_CLICK_WATCH = """
() => {
  window.__clicks = [];
  document.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const target = event.target;
    window.__clicks.push(target && target.getAttribute ? target.getAttribute("data-testid") : "click");
  }, true);
}
"""


@pytest.fixture(scope="module")
def browser():
    # The driver itself may fail to start (a slim image without the libraries its bundled node needs),
    # before any browser is launched; that is "cannot run here", not a test failure.
    try:
        playwright = sync_playwright().start()
    except Exception as exc:
        pytest.skip(f"playwright 已安裝，但它的 driver 起不來：{exc}")
    try:
        try:
            launched = playwright.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"playwright 已安裝，但 headless Chromium 起不來：{exc}")
        try:
            yield launched
        finally:
            launched.close()
    finally:
        playwright.stop()


def _open(browser, name: str):
    page = browser.new_page()
    page.set_content((_FIXTURES / name).read_text(encoding="utf-8"), wait_until="domcontentloaded")
    page.evaluate(_CLICK_WATCH)
    return page


def _clicks(page) -> list:
    return page.evaluate("() => window.__clicks")


def test_chromium_reads_switcher_title_and_current_row(browser):
    sidebar = _open(browser, "switcher_sidebar.html")
    trigger = _open(browser, "switcher_trigger.html")
    missing = _open(browser, "switcher_missing.html")
    try:
        sidebar_snap = sidebar.evaluate(SNAPSHOT_JS)
        trigger_snap = trigger.evaluate(SNAPSHOT_JS)
        missing_snap = missing.evaluate(SNAPSHOT_JS)
        assert sidebar_snap["present"]["switcher"] is True
        assert trigger_snap["present"]["switcher"] is True
        assert missing_snap["present"]["switcher"] is False

        sidebar_raw = sidebar.evaluate(CHATS_JS)
        assert sidebar_raw["ok"] is True
        assert sidebar_raw["mainSpans"] == []
        assert sidebar_raw["pageTitle"] == "Muse"
        assert sidebar_raw["outsideTitles"] == ["假文件標題"]
        current = [row for row in sidebar_raw["rows"] if row["current"]]
        assert [row["title"] for row in current] == ["假側欄對話"]
        shaped = shape_chats(
            sidebar_raw["mainSpans"],
            sidebar_raw["rows"],
            page_title=sidebar_raw["pageTitle"],
            outside_titles=sidebar_raw["outsideTitles"],
        )
        assert shaped[0] == {"title": "假文件標題", "is_current": False, "kind": "main"}
        assert {"title": "假側欄對話", "is_current": True, "kind": "side"} in shaped
        assert {"title": "假另一則", "is_current": False, "kind": "side"} in shaped
        assert all(item["title"] not in {"聊天室", "Muse", "開始副聊天室", "新副聊天室", "側欄裡的標題", "紀錄裡的標題"} for item in shaped)

        sidebar.evaluate(
            """() => {
              document.querySelectorAll("h1").forEach((node) => node.remove());
              document.title = "Muse";
            }"""
        )
        cleared = sidebar.evaluate(CHATS_JS)
        cleared_title = shape_chats(
            cleared["mainSpans"],
            cleared["rows"],
            page_title=cleared["pageTitle"],
            outside_titles=cleared["outsideTitles"],
        )[0]["title"]
        assert cleared_title is None
        sidebar.evaluate("() => { document.title = '聊天室'; }")
        chrome_title = sidebar.evaluate(CHATS_JS)
        assert (
            shape_chats(
                chrome_title["mainSpans"],
                chrome_title["rows"],
                page_title=chrome_title["pageTitle"],
                outside_titles=chrome_title["outsideTitles"],
            )[0]["title"]
            is None
        )
        sidebar.evaluate("() => { document.title = '假文件標題 - Muse'; }")
        from_document = sidebar.evaluate(CHATS_JS)
        assert (
            shape_chats(
                from_document["mainSpans"],
                from_document["rows"],
                page_title=from_document["pageTitle"],
                outside_titles=from_document["outsideTitles"],
            )[0]["title"]
            == "假文件標題"
        )

        trigger.evaluate(
            """() => {
              const shell = document.querySelector('[data-testid="hatch-side-chats-panel-shell"]');
              if (shell) shell.removeAttribute("hidden");
            }"""
        )
        trigger_raw = trigger.evaluate(CHATS_JS)
        assert trigger_raw["mainSpans"] == ["聊天室", "假主對話"]
        old_current = [row for row in trigger_raw["rows"] if row["current"]]
        assert [row["title"] for row in old_current] == ["假副對話"]
        assert (
            shape_chats(
                trigger_raw["mainSpans"],
                trigger_raw["rows"],
                page_title=trigger_raw["pageTitle"],
                outside_titles=trigger_raw["outsideTitles"],
            )[0]["title"]
            == "假主對話"
        )
        trigger.evaluate(
            """() => {
              const row = [...document.querySelectorAll("button")].find((node) => (node.innerText || "").includes("假副對話"));
              row.setAttribute("aria-current", "page");
            }"""
        )
        remarked = trigger.evaluate(CHATS_JS)
        assert [row["title"] for row in remarked["rows"] if row["current"]] == ["假副對話"]

        missing_raw = missing.evaluate(CHATS_JS)
        assert missing_raw["ok"] is False
        assert missing_raw["mainSpans"] == []
        assert _clicks(sidebar) == []
        assert _clicks(trigger) == []
        assert _clicks(missing) == []
    finally:
        sidebar.close()
        trigger.close()
        missing.close()


def test_chromium_closed_sidebar_does_not_click(browser):
    page = _open(browser, "switcher_sidebar.html")
    try:
        page.evaluate(
            """() => {
              document.querySelector('[data-testid="hatch-side-chats-panel-content"]').setAttribute("hidden", "");
            }"""
        )
        assert page.locator('[data-testid="hatch-side-chats-panel-content"]').is_visible() is False
        payload = collect_chats(CdpPage(page, None))
        assert payload["state"] == "ui_changed"
        assert payload["hint"] == "請在 Muse 打開側欄後重試"
        assert payload["error"] == "讀不到側欄裡的對話清單"
        assert payload["chats"] == []
        assert set(payload) == {"backend", "state", "count", "chats", "error", "hint"}
        assert _clicks(page) == []
        assert page.url.startswith("about:")
    finally:
        page.close()
