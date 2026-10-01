# Changelog

## [0.1.2] - 2026-10-01

- Document first-time setup, every command, exit-code fixes, and troubleshooting in Traditional Chinese and English.
- Show global flags, defaults, and examples in `--help`.
- Support Linux, Windows, and macOS: Chrome discovery, process stop, profile locks, and UTF-8 console output. Linux is covered by CI, Windows by CI, and macOS by local tests plus a live read-only check.
- The api backend is a generic client for a credential the user writes. There is no official public Muse API, and the tool never extracts cookies or tokens.
- Part of trinity-cli: https://gitlab.com/aa22396584/trinity-cli

Supported operating systems:

- Linux: install with uv or pipx, then `muse-web-cli login` on a desktop session or `xvfb-run muse-web-cli login`. Headless `start` needs no display.
- Windows (PowerShell): `uv tool install` the tag, then `muse-web-cli login` in a desktop session. The credential file must sit under your home directory.
- macOS: install the tag, then `muse-web-cli login`. The profile stays at `~/.trinity-cli/muse-profile` and the debug port is 9333.

## [0.1.1] - 2026-10-01

- Add a read-only `chats` command that lists the main chat and any side chats.
- Opening the switcher does not create a side chat and does not open one. The previous view is restored.
- The api backend returns `unsupported` for `chats`.

## [0.1.0] - 2026-10-01

- Drive a logged-in Muse web session from the terminal through a dedicated Chrome profile, headed or headless.
- Commands: status, messages, send, pending, upcoming, activity, memory, login, start, stop, selftest.
- The browser backend is the default. The api backend is a seam until a supported Muse API exists.
- The tool does not read cookies, tokens, or the contents of the credential file.
