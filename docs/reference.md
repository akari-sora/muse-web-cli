# muse-web-cli reference

English | [繁體中文](reference.zh-TW.md)

The [README](../README.md) covers install, quick start, and the command list. This page has the details.

- [First-time setup](#first-time-setup)
- [Output examples](#output-examples)
- [Command reference](#command-reference)
- [Exit codes](#exit-codes)
- [Backends](#backends)
- [Troubleshooting](#troubleshooting)
- [Platforms](#platforms)
- [Tests and CI](#tests-and-ci)

## First-time setup

The profile is always `~/.trinity-cli/muse-profile` (`Path.home()` on every OS). One Chrome per profile. The debug port defaults to `127.0.0.1:9333`.

1. Log in headed. The tool never types credentials. On a Linux server with no display, log in on a desktop session or run `xvfb-run muse-web-cli login`. Without a display, login leaves a running headless Chrome in place. Do not copy cookies. Once `login` sees you are signed in, it closes the visible Chrome it started and relaunches the same profile headless (a visible window takes keyboard focus whenever it is driven). Pass `--keep-window` to keep the window; any later command that attaches to a visible tracked Chrome prints a warning (`warning` in `--json`) with the switch command.

```bash
muse-web-cli login
```

2. Confirm the page. `selftest` only checks selectors. `status` checks the session.

```bash
muse-web-cli selftest
muse-web-cli status
```

3. Later use can be headless. If Chrome is already on the profile, the tool attaches and does not launch a second one. `--autostart` is always headless and leaves the process running.

```bash
muse-web-cli start --headless
muse-web-cli --autostart status
muse-web-cli stop
```

`stop` stops only the process this tool started. It does not touch your normal Chrome. When the session expires, or headless mode hits a bot check, the exit code is 2 and `hint` is `muse-web-cli login`.

Config file `~/.trinity-cli/muse-web-cli.json` (defaults apply if it is missing):

```json
{"port": 9333, "headless": true, "autostart": false, "backend": "browser", "chrome": ""}
```

Environment: `MUSE_WEB_CDP_PORT`, `MUSE_WEB_HEADLESS`, `MUSE_WEB_AUTOSTART`, `MUSE_WEB_BACKEND`, `MUSE_WEB_CHROME`, `MUSE_WEB_KEEP_WINDOW`. Precedence is flag, then environment, then config, then default.

## Output examples

What the quick-start commands print with `--json`.

```bash
muse-web-cli --json status
```

```json
{"backend":"browser","state":"ok","pending":0,"latest_assistant_is_card":false,"headless":false,"error":null,"hint":null,"missing":[]}
```

```bash
muse-web-cli --json messages --limit 2
```

```json
{"backend":"browser","state":"ok","name":"Muse","lines":["user: …","assistant: …"],"messages":[{"role":"user","text":"…","presentation":false}],"error":null,"hint":null}
```

```bash
muse-web-cli --json chats
```

```json
{"backend":"browser","state":"ok","count":1,"chats":[{"title":"…","is_current":true,"kind":"main"}],"error":null,"hint":null}
```

```bash
muse-web-cli --json send --wait --timeout 120 -- "text"
```

```json
{"backend":"browser","state":"ok","attempted":true,"sent":true,"text":"text","reply":"…","presentation":false,"elapsed_ms":4000,"error":null,"hint":null}
```

```bash
muse-web-cli --json pending
```

```json
{"backend":"browser","state":"ok","count":0,"items":[],"error":null,"hint":null}
```

The words above are placeholders, not a real transcript.

## Command reference

Global flags may appear before or after the command:

| Flag | Default | Range |
| --- | --- | --- |
| `--json` | off | print one JSON object |
| `--port` | 9333 | 1–65535 |
| `--backend` | `browser` | `browser` or `api` |
| `--autostart` | off | start headless Chrome when nothing is listening |
| `--keep-window` | off | `login` and `credential` keep the visible window open instead of relaunching headless (also `MUSE_WEB_KEEP_WINDOW`, config `keep_window`) |
| `--chrome PATH` | discovered per OS | overrides `MUSE_WEB_CHROME` |
| `--version` |  | print the version |

- `status` — session, pending count, and whether the latest assistant message is a card. `muse-web-cli status`
- `messages --limit N` — oldest to newest. Default 20, minimum 1, values above 100 are capped at 100. Off-screen rows are virtualized. `--session ID` works only with `--backend api`. `muse-web-cli messages --limit 20`
- `send TEXT` — insertText and Enter, once. Put `--` before text that starts with `-`. `--wait` defaults off. `--timeout` defaults to 120 and must be > 0. A timeout never resends. `--wait` accepts only a reply that appears after the pre-send snapshot, in long chats too. `--session ID` works only with `--backend api`; the browser backend refuses it with exit 2 and sends nothing. `muse-web-cli send --wait --timeout 120 -- "text"`
- `send --attach FILE` (repeatable) — uploads through the Muse window and sends once; a missing or non-regular file exits 2 and sends nothing. `--attach-sha256 HEX` (repeatable, in `--attach` order): each file is read once and Muse gets exactly the hashed bytes (handed to the browser directly up to 50 MB, above that through a private temporary copy); a mismatch exits 2 and nothing is uploaded or sent. With `--session ID` it opens that side chat (`muse.ai/thread/<ID>`) and returns to the main chat afterwards; with an `--backend api` credential the reply is read through the api. If a file does not attach, no message is sent and the attached files are removed from the composer (Muse may already have stored the upload). If the page does not show that side chat (`muse.ai/thread/<ID>`), nothing is sent. If the window cannot go back to the main chat afterwards, the send is still reported as sent, with a `warning`. `muse-web-cli --backend api send --session ID --attach bundle.zip --wait -- "unzip …"`
- `pending` — read approvals. It does not approve or reject. `muse-web-cli pending`
- `upcoming` — read scheduled tasks. It does not click a row. Muse removed the Upcoming tab; on a page without it, `upcoming` reads only the Activity tab's scheduled group (headed like 「2項排定任務」 or "2 scheduled tasks") and leaves out the dated groups below it. With no such group, `count` is 0. When the header counts more tasks than the panel lists, `complete` is `false` and the hint points to `--backend api upcoming`; 「查看所有排定任務」 (view all scheduled tasks) is not clicked. `muse-web-cli upcoming`
- `activity` — read the activity tab. It does not click a row. `muse-web-cli activity`
- `memory` — read MEMORY.md `innerText`. It does not focus or type. `muse-web-cli memory`
- `chats` — list the main chat and any side chats already showing in the sidebar. A closed sidebar is not clicked; `state` is `ui_changed` and the hint is「請在 Muse 打開側欄後重試」. It does not click "新副聊天室" / new side chat, and it does not open a chat. On the new shell the main `title` may be null. `muse-web-cli chats`
- `chats --create [--title T]`, `--rename ID --title T`, `--delete ID`, `--switch ID|main` — `--backend api` only. `ID` is the `session_id` that `chats` lists; all four use the same ids. `--create` makes the new chat the switched one; `--json` has its id in `created`. `--delete` refuses the main chat; `--rename` and `--delete` refuse an id that was not listed and send nothing. `muse-web-cli --backend api chats --switch main`
- `credential` — get the gateway token from the logged-in page and write it only into `~/.trinity-cli/muse-credential` (mode 600). It never prints it. Runs `login` first when the session is missing. `muse-web-cli credential`
- `login` — open a headed window so you can log in. Once signed in it closes that window and relaunches the profile headless (`headless: true`, `action: relaunched_headless`); if the headless page is signed out, `state` is `session_expired`. `--keep-window` skips the relaunch. `muse-web-cli login`
- `start` — start the dedicated Chrome, or attach if it is already running. `--headless` is the default (`--headless=new`). `--headed` shows the window. The two flags cannot be combined. `muse-web-cli start --headless`
- `stop` — stop only the process this tool started. `muse-web-cli stop`
- `selftest` — check that selectors exist. It clicks nothing. The switcher trigger is required. `upcoming_tab` is reported in `present` but not required. `muse-web-cli selftest`

`--json` keys:

- `status`: `backend` `state` `pending` `latest_assistant_is_card` `headless` `error` `hint` `missing`
- `messages`: `backend` `state` `name` `lines` `messages` `error` `hint`. Each message is `role` `text` `presentation`
- `send`: `backend` `state` `attempted` `sent` `text` `reply` `presentation` `elapsed_ms` `error` `hint`
- `pending`: `backend` `state` `count` `items` `error` `hint`. An item is `title` `detail` `time`
- `upcoming`: `backend` `state` `count` `groups` `error` `hint`, plus `complete: false` only when the Activity tab lists fewer scheduled tasks than its header counts. A group is `title` plus `items` of `name` `time`
- `activity`: the same `groups` shape; an item is `title` `detail` `time`
- `memory`: `backend` `state` `chars` `sections` `text` `error` `hint`
- `chats`: `backend` `state` `count` `chats` `error` `hint`. Each chat is `title` `is_current` `kind` (`main` or `side`), plus `session_id` on `--backend api`. With no side chats, `count` is the main chat only. On the new shell `title` may be null
- `credential`: `backend` `state` `action` `wrote` `logged_in` `fields` `error` `hint`. `fields` only says whether each field has a value (`true`/`false`); the token itself is never in the output
- `login` / `start` / `stop`: `backend` `state` `action` `port` `headless` `tracked` `logged_in` `error` `hint`
- `selftest`: the `status` keys plus `present`

Browser backend: `messages` and `send` act on the chat that is already open. If a side chat is current, that is what you read. `chats` lists them and does not switch. `--backend api`: `--session ID` picks a chat; without it, the chat saved by `chats --switch` (or `--create`) is used; `--switch main` goes back to the main chat.

## Exit codes

| Code | state | Fix |
| --- | --- | --- |
| 0 | `ok` | nothing to do |
| 2 | `browser_down` | `muse-web-cli start --headless`, or pass `--autostart` |
| 2 | `session_expired` | `muse-web-cli login` (headed) |
| 2 | `region_blocked` | Muse is not available here. The tool does not bypass it |
| 2 | `profile_busy` | One Chrome already holds the profile. Quit that window, or reuse the one already on 9333. Do not start a second |
| 2 | `credential_permissions` | macOS/Linux: `chmod 600 ~/.trinity-cli/muse-credential`. Windows: the file must be a regular file under your home directory |
| 3 | `ui_changed` | Run `selftest` and read `missing`. Do not click around the page |
| 3 | `timeout` | `hint` is `nothing was sent again`. Do not send again automatically |
| 4 | `unsupported` | `--backend api` only: the credential file is missing, or it has no `vm_id` and no endpoint for that command. A state sent by a server never becomes 4. A missing token, bad JSON, or a wrong field is 2 or 3. Not an unimplemented command |

## Backends

JSON shapes and exit codes do not depend on the backend. Callers should not branch. The default is `browser`. Select it with `--backend`, `MUSE_WEB_BACKEND`, or the config key `backend`. Precedence is the same as above.

- `browser`: headed or headless, over CDP. This is the default.
- `api`: the Muse gateway is this backend. With `vm_id`, it talks to the gateway (status, messages, send, pending, schedules, activity, memory, and chat list/create/rename/delete/switch). Without `vm_id`, `endpoints` still selects a REST path you configure.

`credential` gets the gateway token from the logged-in Muse page and writes it only into `~/.trinity-cli/muse-credential`. If the session is missing, it runs `login` (a visible window) and writes after that login finishes. On macOS and Linux the file mode is `600` and the directory mode is `700`. It does not print the token. If you still have to approve the window, the exit code is 2 and nothing is written. An expired session (HTTP 401/403) is also exit 2 and says so instead of "not logged in"; region blocks, a browser that will not start, and a busy profile keep their own state.

```bash
muse-web-cli credential
```

Example (the token is fake):

```json
{
  "base_url": "https://example.test",
  "auth": {"type": "bearer", "token": "replace-me", "header_name": "Authorization"},
  "endpoints": {
    "status": {"method": "GET", "path": "/status"},
    "messages": {"method": "GET", "path": "/messages"},
    "send": {"method": "POST", "path": "/send"},
    "pending": {"method": "GET", "path": "/pending"},
    "upcoming": {"method": "GET", "path": "/upcoming"},
    "activity": {"method": "GET", "path": "/activity"},
    "memory": {"method": "GET", "path": "/memory"},
    "chats": {"method": "GET", "path": "/chats"}
  },
  "timeout_s": 30
}
```

`auth.type` may also be `header`, which uses `header_name`. An `endpoints` file like the one above is for a REST service you run yourself. The Muse gateway file is written by `muse-web-cli credential` and holds `vm_id` instead of `endpoints`. Do not write it by hand or copy a token out of the browser.

A missing file, or no `vm_id` and no endpoint for that command, is exit 4. HTTP 401/403 is `session_expired` (exit 2). For the Muse gateway, sign in again in Chrome and rerun `muse-web-cli credential`. For your own REST service, replace `auth.token`. Other 4xx and 5xx are `ui_changed` (exit 3). A server's own `error` and `hint` are scrubbed of token, Bearer, and JWT strings before printing. A timeout is `timeout` (exit 3), and `send` is not repeated. If `send --wait` gets no `reply`, the client only reads `messages`. It does not post again. On the gateway, `send --wait` finishes reading the open Noise stream before the next request; if that stream is quiet for a while it keeps waiting until `--timeout`. `chats --create`, `--rename`, `--delete`, and `--switch` send those requests only with `--backend api`.

`start`, `stop`, `login`, and `selftest` always manage the local Chrome. They are not the api seam.

## Troubleshooting

- Nothing is listening on port 9333: `browser_down`. Use `start --headless` or `--autostart`.
- Login wall or bot check: `session_expired`. Use headed `login`. On a Linux server with no display, log in on a desktop session or use `xvfb-run`. Do not copy cookies.
- A side chat is open: `messages` reads the current chat. Run `chats` and look at `kind` and `is_current`. It does not switch back to the main chat.
- Muse shipped a new UI and selectors are gone: `ui_changed`. `selftest` lists the missing names in `missing`.

## Platforms

| OS | Python | How it was checked |
| --- | --- | --- |
| Linux | 3.12 | GitLab CI: the offline unit suite |
| Windows | 3.12 | GitLab CI: the same suite, run automatically when code, tests, or packaging change |
| macOS | 3.11, 3.12, 3.13 | Maintainer machine: the same suite, plus a first-run check that installs from the tag as the README says and reaches the login wall (`session_expired`) with a fresh Chrome profile |

The tests do not contact Muse or start a real Chrome. On Linux and Windows, real Chrome is covered by unit tests only, with no live check.

## Tests and CI

CI uses GitLab.com runners by default. Maintainers can point jobs at their own runners by setting the CI/CD variables `LINUX_RUNNER_TAG` and `WINDOWS_RUNNER_TAG`.
Local tests: `uv run --group dev pytest`.
