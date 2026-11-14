"""Command line for the user's own Muse web app.

The command is muse-web-cli. Meta's Muse Code agent already owns the name `muse`.
"""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from muse_web_cli import __version__
from muse_web_cli.backends.api import ApiBackend
from muse_web_cli.backends.browser import BrowserBackend
from muse_web_cli.capture import CAPTURE_JS, run_credential
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
from muse_web_cli.flow import wait_rendered
from muse_web_cli.model import assess, browser_down, empty_like, exit_for, send_payload
from muse_web_cli.output import emit, safe_text

CAPABILITIES = ("status", "messages", "send", "pending", "upcoming", "activity", "memory", "chats")
LIMIT_MAX = 100


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="muse-web-cli",
        description=(
            "Drive your own logged-in Muse web app. The default backend is the browser. "
            "It does not read cookies and never prints a token. `credential` writes the gateway token "
            "only into ~/.trinity-cli/muse-credential (mode 600); `--backend api` uses that file."
        ),
        epilog=(
            "examples:\n"
            "  muse-web-cli login\n"
            "  muse-web-cli selftest\n"
            "  muse-web-cli start --headless\n"
            "  muse-web-cli --json --autostart status\n"
            "  muse-web-cli --json messages --limit 5\n"
            "  muse-web-cli send --wait --timeout 120 -- \"text\"\n"
            "  muse-web-cli credential\n"
            "  muse-web-cli login --keep-window\n"
            "\n"
            "Global flags may appear before or after the command.\n"
            "Exit 0 ok.\n"
            "Exit 2 setup: browser_down, session_expired, region_blocked, profile_busy, credential_permissions.\n"
            "Exit 3 page: ui_changed, timeout.\n"
            "Exit 4 unsupported (--backend api only): the credential file is missing, or it has no vm_id\n"
            "  and no endpoint for that command.\n"
            "--backend api reads ~/.trinity-cli/muse-credential (mode 600): base_url, auth.type, auth.token, vm_id.\n"
            "Run `muse-web-cli credential` to write it from the logged-in page."
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
        "--keep-window",
        action="store_true",
        help=(
            "login and credential keep the visible Chrome window open (default: off; they relaunch it "
            "headless once you are signed in, because a visible window takes keyboard focus)"
        ),
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
    send.add_argument(
        "--attach",
        action="append",
        metavar="FILE",
        help="attach a file (repeatable); sent through the Muse window, also with --session (default: none)",
    )
    send.add_argument(
        "--attach-sha256",
        action="append",
        metavar="HEX",
        help="expected sha256 of each --attach file, in the same order; a file whose bytes differ stops the send (default: not checked)",
    )
    send.add_argument("--wait", action="store_true", help="wait for the assistant reply (default: off)")
    send.add_argument(
        "--timeout",
        type=float,
        default=120,
        help="seconds for that one wait (default: 120, must be > 0); a timeout never resends",
    )
    sub.add_parser("pending", help="read pending approvals; does not approve or reject")
    sub.add_parser("upcoming", help="read scheduled tasks (the upcoming tab, or the activity tab's scheduled group); does not click a row")
    sub.add_parser("activity", help="read the activity tab; does not click a row")
    sub.add_parser("memory", help="read MEMORY.md innerText; does not focus or edit it")
    chats = sub.add_parser("chats", help="list chats; with --backend api, create, rename, delete, or switch")
    chats.add_argument(
        "--create",
        action="store_true",
        help="create a chat on the api backend; it becomes the switched chat",
    )
    chats.add_argument("--rename", metavar="SESSION", help="rename a listed chat on the api backend")
    chats.add_argument(
        "--delete",
        metavar="SESSION",
        help="delete a listed side chat on the api backend; the main chat is refused",
    )
    chats.add_argument("--switch", metavar="SESSION", help="switch chat on the api backend; use main for the primary chat")
    chats.add_argument("--title", help="title for --create or --rename")
    sub.add_parser(
        "credential",
        help=(
            "write the gateway token from the logged-in page into ~/.trinity-cli/muse-credential "
            "(mode 600, never printed); log in first when the session is missing"
        ),
    )
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


def _split_globals(argv: list[str]) -> tuple[list[str], bool, object, object, bool | None, object, bool | None]:
    cleaned: list[str] = []
    as_json = False
    port = None
    backend = None
    autostart = None
    chrome = None
    keep_window = None
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--json":
            as_json = True
            index += 1
            continue
        if item == "--keep-window":
            keep_window = True
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
    return cleaned, as_json, port, backend, autostart, chrome, keep_window


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


FOCUS_WARNING = (
    "the Muse window is visible (headed) and can take your keyboard focus whenever this tool drives it. "
    "Switch to headless: muse-web-cli stop && muse-web-cli start --headless "
    "(the login stays in the profile; --keep-window or MUSE_WEB_KEEP_WINDOW=1 silences this)"
)
_focus_warned = False
READY_SECONDS = 15.0


def _focus_warning(settings: Settings, ready: dict) -> str | None:
    """A tracked headed Chrome that a non-login command attaches to. Warn once on stderr; never switch it."""
    global _focus_warned
    if getattr(settings, "keep_window", False) or not ready.get("tracked") or ready.get("headless") is not False:
        return None
    if not _focus_warned:
        _focus_warned = True
        print(f"warning: {FOCUS_WARNING}", file=sys.stderr)
    return FOCUS_WARNING


def _page_status(settings: Settings, port: int) -> dict:
    """Attach, wait (bounded) until the page has rendered, and read how it looks."""
    with file_lock(settings.paths.page_lock):
        page = connect(port)
        try:
            return wait_rendered(page, READY_SECONDS)[1]
        finally:
            try:
                page.disconnect()
            except Exception:  # noqa: BLE001
                pass


def _with_page(settings: Settings, *, mode: str, headless: bool, kind: str, text: str, fn):
    ready = _ensure(settings, mode=mode, headless=headless)
    if ready["state"] != "ok":
        return _not_ready(ready, kind, text)
    warning = _focus_warning(settings, ready) if mode == "use" else None
    with file_lock(settings.paths.page_lock):
        try:
            page = connect(ready["port"])
        except BrowserDown as exc:
            failed = dict(ready)
            failed["state"] = "browser_down"
            failed["error"] = exc.error
            failed["hint"] = exc.hint or ready.get("hint")
            return _not_ready(failed, kind, text)
        try:
            payload = fn(page, ready)
            if warning and isinstance(payload, dict):
                payload["warning"] = f"{payload['warning']}; {warning}" if payload.get("warning") else warning
            return payload
        finally:
            # A failed disconnect must not replace what the command already did (a send that went out).
            try:
                page.disconnect()
            except Exception:  # noqa: BLE001
                pass


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


MAX_ATTACHMENT = 512 * 1024 * 1024
_API_SNAPSHOT = 20


def _bad_attachment(paths: list[str]) -> str | None:
    for item in paths:
        path = Path(item).expanduser()
        if not path.is_file() or path.is_symlink():
            return f"--attach needs a regular file: {item}"
        if path.stat().st_size > MAX_ATTACHMENT:
            return f"--attach file is larger than {MAX_ATTACHMENT} bytes: {item}"
    return None


def _bad_sha256(paths: list[str], shas: list[str]) -> str | None:
    if shas and (len(shas) != len(paths) or not all(re.fullmatch(r"[0-9a-fA-F]{64}", sha) for sha in shas)):
        return "--attach-sha256 needs one 64-hex value per --attach, in the same order; nothing was uploaded or sent"
    return None


def _read_attachments(paths: list[str], shas: list[str]) -> list[tuple[str, str, bytes]]:
    """(name, mime type, bytes) of each file, read once. These bytes are the ones uploaded, so a
    file given with --attach-sha256 is checked against exactly what Muse gets."""
    files = []
    for index, item in enumerate(paths):
        path = Path(item).expanduser().resolve()
        data = path.read_bytes()
        if shas and hashlib.sha256(data).hexdigest() != shas[index].lower():
            raise ConfigError(f"--attach {item} does not match its --attach-sha256; nothing was uploaded or sent")
        files.append((path.name, mimetypes.guess_type(path.name)[0] or "application/octet-stream", data))
    return files


# Playwright refuses set_input_files buffers above 50 MB (all files of one call together).
_BUFFER_LIMIT = 50 * 1024 * 1024


@contextmanager
def _uploads(files: list[tuple[str, str, bytes]]):
    """What the file input gets: the read bytes as buffers, or above Playwright's buffer limit,
    private copies (0600 in a 0700 temporary folder) written from those same bytes."""
    if sum(len(data) for _, _, data in files) <= _BUFFER_LIMIT:
        yield [{"name": name, "mimeType": mime, "buffer": data} for name, mime, data in files]
        return
    with tempfile.TemporaryDirectory(prefix="muse-attach-") as tmp:
        paths = []
        for index, (name, _, data) in enumerate(files):
            folder = Path(tmp) / str(index)  # one folder each, so two files may share a name
            folder.mkdir(mode=0o700)
            fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            paths.append(str(folder / name))
        yield paths


def _send_files(settings: Settings, browser, args: argparse.Namespace, files: list[tuple[str, str, bytes]]) -> dict:
    """The window uploads and sends once; with a saved credential the reply is read through the
    api backend, which reads a side chat by its session id and sees the attachment prefix."""
    session = getattr(args, "session", None)
    api = ApiBackend(settings.paths.credential) if settings.paths.credential.exists() else None
    with _uploads(files) as attach:
        if not (args.wait and api):
            return browser.send(args.text, wait=args.wait, timeout=args.timeout, attach=attach, session=session)
        started = time.monotonic()
        snap = api.messages(_API_SNAPSHOT, session=session or "main")
        prior = snap.get("messages") if snap.get("state") == "ok" and isinstance(snap.get("messages"), list) else None
        if prior is None:
            return browser.send(args.text, wait=True, timeout=args.timeout, attach=attach, session=session)
        first = browser.send(args.text, wait=False, timeout=args.timeout, attach=attach, session=session)
    if first.get("state") != "ok" or not first.get("sent"):
        return first
    return api.wait_reply(args.text, first=first, prior=prior, session=session, timeout=args.timeout, started=started)


def _run_capability(settings: Settings, command: str, args: argparse.Namespace) -> dict:
    action, session, title = _chat_mutation(args)
    # An upload only exists in the Muse page, so a send with files always uses the window;
    # --session then opens that side chat by its URL and returns to the main chat afterwards.
    attach = _read_attachments(getattr(args, "attach", None) or [], getattr(args, "attach_sha256", None) or []) if command == "send" else []
    if settings.backend == "api" and not (command == "send" and attach):
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
            "並先執行 muse-web-cli credential 寫好 ~/.trinity-cli/muse-credential。"
        )
    if getattr(args, "session", None) and not (command == "send" and attach):
        raise ConfigError(
            "--session 只在 --backend api 有效。瀏覽器後端讀寫的是 Muse 視窗目前開著的那一則。沒有送出。"
        )

    def run(page, ready):
        backend = BrowserBackend(page, headless=ready.get("headless"))
        if command == "status":
            return backend.status()
        if command == "messages":
            return backend.messages(args.limit)
        if command == "send" and attach:
            return _send_files(settings, backend, args, attach)
        if command == "send":
            return backend.send(args.text, wait=args.wait, timeout=args.timeout)
        return getattr(backend, command)()

    text = args.text if command == "send" else ""
    return _with_page(settings, mode="use", headless=True, kind=command, text=text, fn=run)


def _connect_page(settings: Settings):
    ready = _ensure(settings, mode="use", headless=True)
    if ready["state"] != "ok":
        return ready, None
    _focus_warning(settings, ready)
    try:
        return ready, connect(ready["port"])
    except BrowserDown as exc:
        failed = dict(ready)
        failed["state"] = "browser_down"
        failed["error"] = exc.error
        failed["hint"] = exc.hint or ready.get("hint")
        return failed, None


def _run_credential(settings: Settings) -> dict:
    def session_state(page) -> str:
        return assess(page.snapshot())["state"]

    def capture(page):
        raw = page._eval(CAPTURE_JS)
        return raw if isinstance(raw, dict) else {"ok": False, "reason": "token_body"}

    return run_credential(
        settings.paths.credential,
        connect=lambda: _connect_page(settings),
        login=lambda: _run_lifecycle(settings, argparse.Namespace(command="login")),
        capture=capture,
        session_state=session_state,
    )


def _go_headless(settings: Settings, shown: dict) -> dict:
    """Signed in: close the visible Chrome this tool started and reopen the same profile headless, so
    the window cannot take keyboard focus. Not signed in on the headless side: say so and stop (no loop)."""
    with file_lock(settings.paths.lock):
        stopped = stop(paths=settings.paths, procs=list_processes(), kill_fn=kill_pid)
    if stopped.get("action") != "stopped":
        return shown  # not the Chrome we started; leave things as they are
    ready = _ensure(settings, mode="start", headless=True)
    if ready["state"] != "ok":
        return _lifecycle(ready, action="relaunched_headless")
    try:
        status = _page_status(settings, ready["port"])
    except BrowserDown as exc:
        failed = dict(ready)
        failed["state"] = "browser_down"
        failed["error"] = exc.error
        failed["hint"] = exc.hint or ready.get("hint")
        return _lifecycle(failed, action="relaunched_headless")
    signed_in = status["state"] == "ok"
    payload = _lifecycle(
        ready,
        logged_in=True if signed_in else (False if status["state"] == "session_expired" else None),
        hint=status.get("hint"),
        action="relaunched_headless",
    )
    payload["state"] = status["state"]
    payload["error"] = status.get("error")
    return payload


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
        if ready["state"] == "ok" and ready.get("action") == "started":
            try:
                _page_status(settings, ready["port"])  # a just-started Chrome: let the page load first
            except BrowserDown:
                pass
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

        payload = _with_page(settings, mode="login", headless=False, kind="lifecycle", text="", fn=finish)
        if (
            payload.get("logged_in")
            and payload.get("tracked")
            and payload.get("headless") is False
            and not settings.keep_window
        ):
            return _go_headless(settings, payload)
        return payload
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
        cleaned, as_json, port, backend, autostart, chrome, keep_window = _split_globals(raw)
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
        settings = resolve_settings(
            home=home,
            port=port,
            backend=backend,
            autostart=autostart,
            chrome=chrome,
            keep_window=keep_window,
            environ=os.environ,
        )
    except ConfigError as exc:
        print(safe_text(str(exc)), file=sys.stderr)
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
        if args.command == "send" and (args.attach or args.attach_sha256):
            bad = _bad_attachment(args.attach or []) or _bad_sha256(args.attach or [], args.attach_sha256 or [])
            if bad:
                print(bad, file=sys.stderr)
                return 2
        if args.command == "credential":
            payload = _run_credential(settings)
        elif args.command in CAPABILITIES:
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
