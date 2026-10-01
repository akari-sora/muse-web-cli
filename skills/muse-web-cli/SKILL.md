---
name: muse-web-cli
description: >-
  Drive the user's own logged-in Meta Muse web app (muse.ai) with the
  muse-web-cli command, headed or headless, on macOS, Linux, or Windows. Use when
  the user asks to check Muse, read Muse messages, list Muse chats, send a message
  to Muse, or look at Muse pending approvals, upcoming items, activity, or memory.
  用 muse-web-cli 操作使用者自己已登入的 Meta Muse：當使用者要查看 Muse、讀 Muse 訊息、列出聊天室、傳訊息給 Muse，或查看核可、近期、動態、記憶時使用。
  The command is muse-web-cli, never muse. 指令是 muse-web-cli，不是 muse。
---

# Muse web

`muse-web-cli` drives the user's own logged-in Muse page. It is not a second Muse. The login stays in `~/.trinity-cli/muse-profile`. The default backend drives the page. `--backend api` uses `~/.trinity-cli/muse-credential`: `vm_id` selects the open Muse gateway, and `endpoints` selects a REST path you configure.

Reply in the language of the user's message.

For cross-agent tasks (ask all three, hand off, digest), use the `trinity-cli` skill.

## Steps

1. Run `muse-web-cli --json --autostart status`. If it is not on PATH, use `~/.local/bin/muse-web-cli`.
2. Exit 2 and `browser_down`: run it again with `--autostart`, or `muse-web-cli start --headless`. Exit 2 and `session_expired`: ask the user to run headed `muse-web-cli login`. A headless bot check uses the same hint. The tool never types credentials. On Linux without a display, login needs a desktop session or `xvfb-run`.
3. Exit 2 and `profile_busy`: one Chrome already holds the profile. Do not start a second one. Exit 2 and `region_blocked`: stop; the tool cannot bypass a region wall. Exit 2 and `credential_permissions`: on macOS/Linux run `chmod 600 ~/.trinity-cli/muse-credential`; on Windows the file must be a regular file under the user home.
4. Exit 3 and `ui_changed`: run `selftest` and report the names in `missing`. Do not click around the page. Exit 3 and `timeout`: do not send again.
5. Exit 4 and `unsupported`: the credential file is missing, or `base_url`, `auth.type`, `auth.token`, and `vm_id` (or `endpoints`) are empty. Say which field to fill. Do not treat a missing implementation as unsupported. Keep the default `--backend browser` unless the user pointed the credential at the gateway.
6. Run `messages` only to read, and `send` only when the user asked to send. Use `send --wait --timeout 120`. A timeout never resends. On `--backend api`, `--session` selects a side chat; omit it to use the chat last switched.
7. `pending`, `upcoming`, `activity`, and `memory` are read-only. `chats` lists the main chat and side chats. With `--backend api`, `chats --create`, `--rename SESSION --title`, `--delete SESSION`, and `--switch SESSION` (or `--switch main`) perform that request. The browser backend does not click those controls.

## Commands

`--json`, `--port` (default 9333, range 1-65535), `--backend` (`browser` or `api`, default `browser`), `--autostart` (default off), and `--chrome` may appear before or after the command. Precedence is flag, then environment, then `~/.trinity-cli/muse-web-cli.json`, then default. Do not branch on backend. The api backend needs `base_url`, `bearer` or header auth, `timeout_s`, and either `vm_id` or `endpoints`. A missing file or an empty endpoint is `unsupported`.

- `status` — session, pending count, whether the latest assistant message is a card
- `messages --limit N` — oldest to newest; default 20, minimum 1, values above 100 are capped at 100
- `send --wait --timeout 120 -- TEXT` — insertText and Enter once; `--wait` defaults off; `--timeout` defaults to 120 and must be > 0
- `pending` / `upcoming` / `activity` / `memory` / `chats`
- `login` / `start` / `start --headed` / `start --headless` / `stop` / `selftest`

`start` defaults to headless. If Chrome is already using the profile, attach; do not launch a second process. `stop` stops only the process this tool started. `selftest` clicks nothing and requires the chat switcher.

## Exit codes

- 0: ok
- 2: `browser_down`, `session_expired`, `region_blocked`, `profile_busy`, `credential_permissions`
- 3: `ui_changed`, `timeout`
- 4: `unsupported`

## Safety

- Do not read, store, or print cookies, tokens, or CSRF, and do not call Muse over HTTP yourself.
- Do not click settings, connectors, invites, attach, a new side chat, the memory toolbar, or approve/reject.
- Memory is read-only. Do not focus it or type into it.
- Do not ask Muse to delete files or run destructive commands.
- Do not ask Muse to message anyone.
- Do not ask Muse to buy anything or change the account.
- Test messages stay short and say they are a test. Do not send unless the user asked.
