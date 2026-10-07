"""Clicks are an allowlist. Panel reads always try to restore the original tab."""

from __future__ import annotations

from collections.abc import Callable

from muse_web_cli.errors import PageChanged
from muse_web_cli.selectors import (
    AVATAR_BUTTON,
    COMPOSER,
    EDITOR_CLOSE,
    MEMORY_FILE,
    SIDEBAR_CLOSED_ERROR,
    SIDEBAR_CLOSED_HINT,
    SWITCHER,
    TAB_ACTIVITY,
    TAB_IDENTITY,
    TAB_PENDING,
    TAB_UPCOMING,
    switcher_selectors,
)

ALLOWED_CLICKS = frozenset(
    {
        COMPOSER,
        SWITCHER,
        *switcher_selectors(),
        TAB_PENDING,
        TAB_UPCOMING,
        TAB_ACTIVITY,
        TAB_IDENTITY,
        MEMORY_FILE,
        EDITOR_CLOSE,
        AVATAR_BUTTON,
    }
)


class SafetyError(RuntimeError):
    pass


def guard_click(selector: str) -> None:
    if selector not in ALLOWED_CLICKS:
        raise SafetyError(f"refusing to click: {selector}")


def read_with_tab(*, panel_open: Callable[[], bool], current_tab: Callable[[], str | None], click: Callable[[str], None], read: Callable[[], dict], target: str) -> dict:
    if not panel_open():
        click(AVATAR_BUTTON)
    original = current_tab()
    switched = bool(original and original != target)
    if original != target:
        click(target)
    try:
        return read()
    finally:
        if switched and original:
            click(original)


def read_memory_flow(
    *,
    panel_open: Callable[[], bool],
    current_tab: Callable[[], str | None],
    click: Callable[[str], None],
    read_text: Callable[[], str],
) -> str:
    if not panel_open():
        click(AVATAR_BUTTON)
    original = current_tab()
    click(TAB_IDENTITY)
    click(MEMORY_FILE)
    try:
        return read_text()
    finally:
        try:
            click(EDITOR_CLOSE)
        finally:
            if not panel_open():
                click(AVATAR_BUTTON)
            if original and original != TAB_IDENTITY:
                click(original)


def read_chats_flow(*, is_open: Callable[[], bool], read: Callable[[], dict]) -> dict:
    """Read the chat list only when the sidebar is already open.

    A closed sidebar is not clicked open and is not closed. The caller reports
    that the list cannot be read.
    """
    if not is_open():
        raise PageChanged("side_chats", hint=SIDEBAR_CLOSED_HINT, error=SIDEBAR_CLOSED_ERROR)
    return read()
