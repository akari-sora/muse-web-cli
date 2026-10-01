"""Command line for the user's own Muse web app.

The command is muse-web-cli. Meta's Muse Code agent already owns the name `muse`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from muse_web_cli import __version__
from muse_web_cli.backends.api import ApiBackend
from muse_web_cli.backends.browser import BrowserBackend
from muse_web_cli.chrome import (
    alive,
    discover_chrome,
    ensure,
    file_lock,
    kill_pid,
    list_processes,
    port_open,
    spawn,
    stop,
    wait_until_port,
)
from muse_web_cli.config import ConfigError, Settings, resolve_settings
from muse_web_cli.driver import connect
from muse_web_cli.errors import BrowserDown
from muse_web_cli.model import assess, browser_down, empty_like, exit_for, send_payload
from muse_web_cli.output import emit, safe_text

CAPABILITIES = ("status", "messages", "send", "pending", "upcoming", "activity", "memory", "chats")
LIMIT_MAX = 100


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="muse-web-cli",
        description="Drive your own logged-in Muse web app. This does not read cookies or tokens.",
        epilog=(
            "examples:\n"
            "  muse-web-cli login\n"
            "  muse-web-cli selftest\n"
            "  muse-web-cli start --headless\n"
            "  muse-web-cli --json --autostart status\n"
            "  muse-web-cli --json messages --limit 5\n"
            "  muse-web-cli send --wait --timeout 120 -- \"text\"\n"
            "\n"
            "Global flags may appear before or after the command.\n"
            "Exit 0 ok.\n"
            "Exit 2 setup: browser_down, session_expired, region_blocked, profile_busy, credential_permissions.\n"
            "Exit 3 page: ui_changed, timeout.\n"
            "Exit 4 unsupported: the credential file is missing, or base_url / vm_id / endpoints is empty.\n"
            "Point --backend api at ~/.trinity-cli/muse-credential (mode 600) with base_url, auth.type, auth.token, vm_id."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--json", action="store_true", help="print one JSON object (default: off)")
    parser.add_argument("--port", metavar="PORT", help="Chrome DevTools port (default: 9333, range 1-65535)")
    parser.add_argument(
        "--backend",
        choices=("browser", "api"),
        help="which backend to use (default: browser)",
    )
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="start headless Chrome when nothing is listening (default: off)",
    )
    parser.add_argument(
        "--chrome",
        metavar="PATH",
        help="Chrome executable (default: discover per OS; overrides MUSE_WEB_CHROME)",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="session, pending count, and whether the latest reply is a card")
    messages = sub.add_parser("messages", help="recent messages, oldest to newest")
    messages.add_argument(
        "--limit",
        type=int,
        default=20,
        help="how many messages to return (default: 20, minimum 1, values above 100 are capped at 100)",
    )
    messages.add_argument("--session", help="side-chat session id for --backend api; omit to use the switched chat")
    send = sub.add_parser("send", help="type with insertText and press Enter once")
    send.add_argument("text", help="message text; put -- before it if it starts with a dash")
    send.add_argument("--session", help="side-chat session id for --backend api; omit to use the switched chat")
    send.add_argument("--wait", action="store_true", help="wait for the assistant reply (default: off)")
    send.add_argument(
        "--timeout",
        type=float,
        default=120,
        help="seconds for that one wait (default: 120, must be > 0); a timeout never resends",
    )
    sub.add_parser("pending", help="read pending approvals; does not approve or reject")
    sub.add_parser("upcoming", help="read the upcoming tab; does not click a row")
    sub.add_parser("activity", help="read the activity tab; does not click a row")
    sub.add_parser("memory", help="read MEMORY.md innerText; does not focus or edit it")
    chats = sub.add_parser("chats", help="list chats; with --backend api, create, rename, delete, or switch")
    chats.add_argument("--create", action="store_true", help="create a chat on the api backend")
    chats.add_argument("--rename", metavar="SESSION", help="rename a chat on the api backend")
    chats.add_argument("--delete", metavar="SESSION", help="delete a chat on the api backend")
    chats.add_argument("--switch", metavar="SESSION", help="switch chat on the api backend; use main for the primary chat")
    chats.add_argument("--title", help="title for --create or --rename")
    sub.add_parser("login", help="open a headed window so you can log in; never types credentials")
    start = sub.add_parser("start", help="start dedicated Chrome, or attach if that profile is already running")
    start.add_argument("--headed", action="store_true", help="show the window (default: headless)")
    start.add_argument("--headless", action="store_true", help="start with --headless=new (default when --headed is omitted)")
    sub.add_parser("stop", help="stop only the Chrome process this tool started")
    sub.add_parser("selftest", help="check that key selectors exist; clicks nothing")
    return parser


def configure_stdio() -> None:
    """Windows consoles default to cp950/cp1252. zh-TW output must not crash them."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def _split_globals(argv: list[str]) -> tuple[list[str], bool, object, object, bool | None, object]:
    cleaned: list[str] = []
    as_json = False
    port = None
    backend = None
    autostart = None
    chrome = None
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--json":
            as_json = True
            index += 1
            continue
        if item == "--autostart":
            autostart = True
            index += 1
            continue
        if item == "--port" or item.startswith("--port="):
            if item.startswith("--port="):
                port = item.split("=", 1)[1]
                index += 1
                continue
            if index + 1 >= len(argv):
                raise ConfigError("missing value for --port")
            port = argv[index + 1]
            index += 2
            continue
        if item == "--backend" or item.startswith("--backend="):
            if item.startswith("--backend="):
                backend = item.split("=", 1)[1]
                index += 1
                continue
            if index + 1 >= len(argv):
                raise ConfigError("missing value for --backend")
            backend = argv[index + 1]
            index += 2
            continue
        if item == "--chrome" or item.startswith("--chrome="):
            if item.startswith("--chrome="):
                chrome = item.split("=", 1)[1]
                index += 1
                continue
            if index + 1 >= len(argv):
                raise ConfigError("missing value for --chrome")
            chrome = argv[index + 1]
            index += 2
            continue
        cleaned.append(item)
        index += 1
    return cleaned, as_json, port, backend, autostart, chrome


def _lifecycle(ready: dict, *, logged_in=None, hint=None, action=None) -> dict:
    return {
        "backend": "browser",
        "state": ready["state"],
        "action": action or ready.get("action"),
        "port": ready.get("port"),
        "headless": ready.get("headless"),
        "tracked": ready.get("tracked"),
        "logged_in": logged_in,
        "error": ready.get("error"),
        "hint": ready.get("hint") if hint is None else hint,
    }


def _not_ready(ready: dict, kind: str, text: str = "") -> dict:
    status = browser_down(ready.get("error") or "browser is not available", hint=ready.get("hint"))
    if ready.get("state") in {"profile_busy", "session_expired", "region_blocked", "browser_down"}:
        status["state"] = ready["state"]
    if kind == "lifecycle":
        return _lifecycle(ready)
    if kind == "status":
        return status
    if kind == "selftest":
        status["present"] = {}
        return status
    if kind == "send":
        return send_payload(
            backend="browser",
            state=status["state"],
            text=text,
            error=status.get("error"),
            hint=status.get("hint"),
        )
    return empty_like(kind, status)


def _ensure(settings: Settings, *, mode: str, headless: bool) -> dict:
    chrome = discover_chrome(settings.chrome)
    with file_lock(settings.paths.lock):
        return ensure(
            paths=settings.paths,
            procs=list_processes(),
            port_open_fn=lambda: port_open(settings.port),
            spawn_fn=spawn,
            kill_fn=kill_pid,
            alive_fn=alive,
            wait_ready=lambda ready_port: wait_until_port(ready_port),
            mode=mode,
            headless=headless,
            autostart=settings.autostart,
            chrome=chrome,
            port=settings.port,
        )


def _with_page(settings: Settings, *, mode: str, headless: bool, kind: str, text: str, fn):
    ready = _ensure(settings, mode=mode, headless=headless)
    if ready["state"] != "ok":
        return _not_ready(ready, kind, text)
    try:
        page = connect(ready["port"])
    except BrowserDown as exc:
        failed = dict(ready)
        failed["state"] = "browser_down"
        failed["error"] = exc.error
        failed["hint"] = exc.hint or ready.get("hint")
        return _not_ready(failed, kind, text)
    try:
        return fn(page, ready)
    finally:
        page.disconnect()


def _chat_mutation(args: argparse.Namespace) -> tuple[str | None, str | None, str | None]:
    if args.command != "chats":
        return None, None, None
    chosen = [name for name in ("create", "rename", "delete", "switch") if getattr(args, name, None)]
    if len(chosen) > 1:
        raise ConfigError("chats 一次只做一件事：--create、--rename、--delete 或 --switch。")
    if not chosen:
        return None, None, None
    name = chosen[0]
    if name == "rename" and not args.title:
        raise ConfigError("請加上 --title。")
    if name == "create":
        return "create", None, args.title
    if name == "rename":
        return "rename", args.rename, args.title
    if name == "delete":
        return "delete", args.delete, None
    return "switch", args.switch, None


def _run_capability(settings: Settings, command: str, args: argparse.Namespace) -> dict:
    action, session, title = _chat_mutation(args)
    if settings.backend == "api":
        backend = ApiBackend(settings.paths.credential)
        if command == "status":
            return backend.status()
        if command == "messages":
            return backend.messages(args.limit, session=args.session)
        if command == "send":
            return backend.send(args.text, wait=args.wait, timeout=args.timeout, session=args.session)
        if command == "chats":
            return backend.chats(action=action, session=session, title=title)
        return getattr(backend, command)()
    if action:
        raise ConfigError(
            "瀏覽器後端只讀聊天列表。建、改、刪、切換請加 --backend api，"
            "並在 ~/.trinity-cli/muse-credential 填 base_url、auth.token、vm_id。"
        )

    def run(page, ready):
        backend = BrowserBackend(page, headless=ready.get("headless"))
        if command == "status":
            return backend.status()
        if command == "messages":
            return backend.messages(args.limit)
        if command == "send":
            return backend.send(args.text, wait=args.wait, timeout=args.timeout)
        return getattr(backend, command)()

    text = args.text if command == "send" else ""
    return _with_page(settings, mode="use", headless=True, kind=command, text=text, fn=run)


def _run_lifecycle(settings: Settings, args: argparse.Namespace) -> dict:
    if args.command == "stop":
        with file_lock(settings.paths.lock):
            ready = stop(paths=settings.paths, procs=list_processes(), kill_fn=kill_pid)
        return _lifecycle(ready)
    if args.command == "start":
        if args.headed and args.headless:
            return _lifecycle(
                {
                    "state": "browser_down",
                    "action": "not_tracked",
                    "port": settings.port,
                    "headless": None,
                    "tracked": False,
                    "error": "--headed and --headless cannot be used together",
                    "hint": None,
                }
            )
        if args.headed:
            headless = False
        elif args.headless:
            headless = True
        else:
            headless = settings.headless
        ready = _ensure(settings, mode="start", headless=headless)
        return _lifecycle(ready)
    if args.command == "login":
        def finish(page, ready):
            status = assess(page.snapshot())
            logged_in = status["state"] == "ok"
            hint = None if logged_in else "在開啟的 Chrome 視窗登入 Muse。這個工具不會輸入帳號密碼。"
            payload = _lifecycle(ready, logged_in=logged_in, hint=hint, action="connected" if logged_in else "login_ready")
            payload["state"] = "ok"
            payload["error"] = None
            return payload

        return _with_page(settings, mode="login", headless=False, kind="lifecycle", text="", fn=finish)
    if args.command == "selftest":
        def finish(page, ready):
            return BrowserBackend(page, headless=ready.get("headless")).selftest()

        return _with_page(settings, mode="use", headless=True, kind="selftest", text="", fn=finish)
    raise ConfigError(f"unknown command {args.command}")


def main(argv: list[str] | None = None, *, home: Path | None = None) -> int:
    os.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")
    configure_stdio()
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        cleaned, as_json, port, backend, autostart, chrome = _split_globals(raw)
        settings = resolve_settings(
            home=home,
            port=port,
            backend=backend,
            autostart=autostart,
            chrome=chrome,
            environ=os.environ,
        )
    except ConfigError as exc:
        print(safe_text(str(exc)), file=sys.stderr)
        return 2
    parser = build_parser()
    try:
        args = parser.parse_args(cleaned)
    except SystemExit as exc:
        code = exc.code
        return 2 if code is None else int(code)
    if not args.command:
        parser.print_help()
        return 2
    try:
        if args.command == "messages" and args.limit < 1:
            print("limit must be >= 1", file=sys.stderr)
            return 2
        if args.command == "messages":
            args.limit = min(args.limit, LIMIT_MAX)
        if args.command == "send" and args.timeout <= 0:
            print("timeout must be > 0", file=sys.stderr)
            return 2
        if args.command in CAPABILITIES:
            payload = _run_capability(settings, args.command, args)
        else:
            payload = _run_lifecycle(settings, args)
    except ConfigError as exc:
        print(safe_text(str(exc)), file=sys.stderr)
        return 2
    except Exception as exc:
        print(safe_text(str(exc)), file=sys.stderr)
        return 3
    return emit(payload, as_json=as_json)


if __name__ == "__main__":
    raise SystemExit(main())
