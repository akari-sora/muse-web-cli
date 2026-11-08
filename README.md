# muse-web-cli

English | [繁體中文](README.zh-TW.md)

Drive the Muse web app you are already logged into from a terminal; with `--json`, each command prints one JSON object.

> Canonical repository and issues: <https://gitlab.com/aa22396584/muse-web-cli>. Part of the trinity-cli family.

[![pipeline](https://gitlab.com/aa22396584/muse-web-cli/badges/main/pipeline.svg)](https://gitlab.com/aa22396584/muse-web-cli/-/commits/main)
[![release](https://gitlab.com/aa22396584/muse-web-cli/-/badges/release.svg)](https://gitlab.com/aa22396584/muse-web-cli/-/releases)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## What it does

- Drives the [Muse](https://muse.ai) web app you are already logged into. It is not a second Muse.
- The default browser backend drives the page through a dedicated Chrome profile and does not read cookies; Chrome reads the profile.
- The optional api backend (`--backend api`) calls the Muse gateway. Only `credential` stores a token: it gets the gateway token from the logged-in page and writes it only into `~/.trinity-cli/muse-credential` (mode 600), never printed. Skip it if you do not use the api backend.
- JSON shapes and exit codes are the same on both backends.
- The command is `muse-web-cli`. The name `muse` belongs to Meta's Muse Code (`~/.local/bin/muse`).

You need Python 3.11+, uv or pipx, and Google Chrome or Chromium already installed. Playwright attaches to that Chrome. Do **not** run `playwright install`. Set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` when installing. Edge is not supported. If the page says Muse is not available in your region, `status` returns `region_blocked` (exit 2); the tool does not bypass that. Supported systems: see [Platforms](docs/reference.md#platforms).

## Install

v0.1.6. After installing, `muse-web-cli --version` should print `muse-web-cli 0.1.6`. If the command is missing, add `~/.local/bin` to PATH.

macOS and Linux:

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.6"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pipx install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.6"
```

Windows (PowerShell):

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"
uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.6"
muse-web-cli --version
```

Upgrade by reinstalling the tag you want with `--force`. Uninstall with `uv tool uninstall muse-web-cli` or `pipx uninstall muse-web-cli`. In this checkout, `uv tool install --editable .` works.

## Set up

```bash
muse-web-cli login
muse-web-cli selftest
muse-web-cli status
muse-web-cli start --headless
```

`login` opens a headed window; the tool never types credentials. On a Linux server with no display, log in on a desktop session or run `xvfb-run muse-web-cli login`. `selftest` only checks selectors; `status` checks the session. After that, use can be headless. Profile, port, config file, and environment variables: [First-time setup](docs/reference.md#first-time-setup).

## Quick start

```bash
muse-web-cli --json status
muse-web-cli --json messages --limit 2
muse-web-cli --json chats
muse-web-cli --json send --wait --timeout 120 -- "text"
muse-web-cli --json pending
```

What each one prints: [Output examples](docs/reference.md#output-examples).

## Commands

| Command | What it does |
| --- | --- |
| `status` | session, pending count, and whether the latest assistant message is a card |
| `messages` | recent messages, oldest to newest (`--limit`, default 20, capped at 100) |
| `send` | send once (`--wait`, `--timeout`, `--attach FILE`, `--attach-sha256 HEX`); a timeout never resends |
| `pending` | read approvals; does not approve or reject |
| `upcoming` | read the upcoming tab; does not click a row |
| `activity` | read the activity tab; does not click a row |
| `memory` | read MEMORY.md `innerText`; does not focus or type |
| `chats` | list the main and side chats; `--create`, `--rename`, `--delete`, `--switch` with `--backend api` only |
| `credential` | write the gateway token into `~/.trinity-cli/muse-credential` (mode 600) |
| `login` | open a headed window so you can log in |
| `start` | start the dedicated Chrome (`--headless` default, or `--headed`), or attach to it |
| `stop` | stop only the process this tool started |
| `selftest` | check that selectors exist; clicks nothing |

Global flags, before or after the command: `--json`, `--port` (default 9333), `--backend` (`browser` or `api`), `--autostart`, `--chrome PATH`, `--version`. Every flag and JSON key: [Command reference](docs/reference.md#command-reference). Backend selection and the credential file: [Backends](docs/reference.md#backends).

## Safety and privacy

- Memory is read-only. The tool never clicks settings, connectors, invites, the attach button (`send --attach` puts files straight into the composer's file input), a new side chat, the memory toolbar, or approve/reject.
- It does not read cookies, enable the CDP Network or Storage domains, or print a token. Printed `error` and `hint` text is scrubbed of `auth_token=`, `Bearer`, and JWT strings; message bodies are left as they are.
- The browser backend drives the dedicated Chrome profile `~/.trinity-cli/muse-profile` on your machine only; the login stays in that profile. The api backend talks only to the Muse gateway, with the token in `~/.trinity-cli/muse-credential`. That file is as good as your login; do not share or commit it.
- There is no telemetry. Apart from the profile, the credential file, and small Chrome-state and current-chat files in `~/.trinity-cli`, nothing is written to disk, and no messages are stored.
- Text output and `--json` contain message text and chat details. Remove them before pasting into an issue.
- `uv tool uninstall` leaves the profile and the credential file. When you are done, run `muse-web-cli stop`, then delete `~/.trinity-cli/muse-profile` and `~/.trinity-cli/muse-credential` yourself.

## For agents

- Pass `--json --autostart` and do not branch on backend. This is how trinity-cli uses it: <https://gitlab.com/aa22396584/trinity-cli>
- Exit 0 is `ok`. Exit 2 is setup (`browser_down`, `session_expired`, `region_blocked`, `profile_busy`, `credential_permissions`), 3 is the page (`ui_changed`, `timeout`), 4 is `unsupported` (`--backend api` only). `hint` names the next command. A `timeout` hint is `nothing was sent again`. See [Exit codes](docs/reference.md#exit-codes).
- `send` sends once. Put `--` before text that starts with `-`.
- The bundled skill is `skills/muse-web-cli/SKILL.md`.

## Documentation

- [docs/reference.md](docs/reference.md): first-time setup, output examples, every command and JSON key, exit codes, backends and the credential file, troubleshooting, platforms, tests and CI.
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) (report security problems there, not in a public issue), [CHANGELOG.md](CHANGELOG.md).

## Related projects

- trinity-cli — one CLI over three always-on agents (Your dot, Grok Bot, Muse): <https://gitlab.com/aa22396584/trinity-cli>
- chatgpt-dot-cli — ChatGPT Your dot: <https://gitlab.com/aa22396584/chatgpt-dot-cli>
- grok-bot-cli (fork, `gbot`) — Grok Bot: <https://gitlab.com/aa22396584/grok-bot-cli>
- muse-web-cli — Meta Muse via the web (this repo): <https://gitlab.com/aa22396584/muse-web-cli>

## License and disclaimer

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 ImL1s.

Unofficial: this is a personal project, not affiliated with, endorsed by, or supported by Meta. The browser backend drives the web app you logged into yourself; the api backend calls the undocumented Muse gateway. Either can break at any time. Automated use may break Meta's terms or get the account limited; any risk is yours.
