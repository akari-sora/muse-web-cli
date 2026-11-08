"""Paths, env, and the small JSON config. No credential is read here."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Paths:
    profile: Path
    config: Path
    state: Path
    credential: Path
    lock: Path
    # Held for every use of the shared Muse window (open a chat, attach, type, send, read), so two
    # commands never interleave on one page.
    page_lock: Path


def paths_for(home: Path | None = None) -> Paths:
    root = (home or Path.home()) / ".trinity-cli"
    return Paths(
        profile=root / "muse-profile",
        config=root / "muse-web-cli.json",
        state=root / "muse-web-cli-state.json",
        credential=root / "muse-credential",
        lock=root / "muse-web-cli.lock",
        page_lock=root / "muse-web-cli.page.lock",
    )


def parse_bool(value: object, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "new", "headless"}:
        return True
    if text in {"0", "false", "no", "off", "headed"}:
        return False
    raise ConfigError(f"invalid boolean: {value}")


def _shown(path: Path) -> str:
    try:
        return str(Path("~") / path.resolve().relative_to(Path.home().resolve()))
    except (ValueError, OSError, RuntimeError):
        return path.name


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_bytes()
    # PowerShell 5.1 `>` writes UTF-16; Notepad may add a UTF-8 BOM.
    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        data = json.loads(raw.decode(encoding))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"config is not UTF-8 JSON: {_shown(path)}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config must be a JSON object: {_shown(path)}")
    return data


@dataclass
class Settings:
    port: int
    headless: bool
    autostart: bool
    backend: str
    chrome: str | None
    paths: Paths

    @property
    def profile(self) -> Path:
        return self.paths.profile


def _port(value: object, default: int = 9333) -> int:
    if value is None or value == "":
        return default
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"invalid port: {value}") from exc
    if not 1 <= port <= 65535:
        raise ConfigError(f"invalid port: {value}")
    return port


def _backend(value: object, default: str = "browser") -> str:
    if value is None or value == "":
        return default
    name = str(value).strip().lower()
    if name not in {"browser", "api"}:
        raise ConfigError(f"unknown backend: {value}")
    return name


def resolve_settings(
    *,
    home: Path | None = None,
    port: object = None,
    backend: object = None,
    autostart: bool | None = None,
    headless: object = None,
    chrome: object = None,
    environ: dict | None = None,
) -> Settings:
    """CLI flag, then environment, then config file, then default."""
    env = os.environ if environ is None else environ
    found = paths_for(home)
    file = load_config(found.config)
    port_value = port if port is not None else env.get("MUSE_WEB_CDP_PORT", file.get("port"))
    backend_value = backend if backend is not None else env.get("MUSE_WEB_BACKEND", file.get("backend"))
    if autostart is None:
        if "MUSE_WEB_AUTOSTART" in env:
            auto_value: object = env.get("MUSE_WEB_AUTOSTART")
        else:
            auto_value = file.get("autostart")
    else:
        auto_value = autostart
    if headless is None:
        headless_value: object = env.get("MUSE_WEB_HEADLESS", file.get("headless"))
    else:
        headless_value = headless
    if chrome is None:
        chrome = env.get("MUSE_WEB_CHROME") or file.get("chrome") or None
    if isinstance(chrome, str) and not chrome.strip():
        chrome = None
    return Settings(
        port=_port(port_value),
        headless=parse_bool(headless_value, True),
        autostart=parse_bool(auto_value, False),
        backend=_backend(backend_value),
        chrome=str(chrome) if chrome else None,
        paths=found,
    )
