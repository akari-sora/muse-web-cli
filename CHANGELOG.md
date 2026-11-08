# Changelog

## [0.1.7] - 2026-11-09

- Muse removed the Upcoming tab from the status panel and moved scheduled tasks into the Activity tab, as its first group (「2項排定任務」). On such a page `upcoming` reads only that group from the Activity tab, in the same `name` / `time` shape, and leaves out the dated groups below it; 0.1.6 returned `ui_changed`. A page that still has the Upcoming tab is read as before. The missing tab is found from the locator count, so no extra control is clicked.
- When the header counts more tasks than the panel lists, `upcoming` adds `complete: false` and a hint pointing to `--backend api upcoming`. 「查看所有排定任務」 is not clicked. An Activity tab with groups but no scheduled group is `count` 0; an Activity tab with nothing in it is `ui_changed`.
- `selftest` no longer requires `upcoming_tab`; it is still reported in `present`.

## [0.1.6] - 2026-11-08

- `send --attach FILE` (repeatable) uploads files through the Muse window's composer file input (the attach button is never clicked) and sends one message. A missing or non-regular file exits 2 and nothing is sent; a file that does not attach sends nothing and is removed from the composer.
- `send --attach-sha256 HEX` (repeatable, in `--attach` order): each file is read once and Muse gets exactly the hashed bytes (handed to the browser up to 50 MB, above that through a private temporary copy that is removed afterwards). A mismatch exits 2; nothing is uploaded or sent.
- `send --session ID` opens that side chat by its URL, checks that the page really shows it before anything is attached or typed, and returns to the main chat afterwards; a failed return keeps the send as sent, with a `warning`. With an `--backend api` credential the reply is read through the api; a reply that starts with `[file: …]` still matches.
- A sent message is never reported as not sent: every failure from the Enter key on (the key press, the page changing, the page going away while waiting) is `attempted: true`, "may have been sent". A failed disconnect no longer replaces the result.
- One lock (`~/.trinity-cli/muse-web-cli.page.lock`) around every use of the Muse window, so two commands cannot interleave.
- `chats --create` returns the new chat's id as `created`.
- `cryptography` 50 (was capped below 47): fixes GHSA-537c, GHSA-jwv3 and GHSA-g6cj (#1). Only X25519, AES-GCM and key serialization are used.

## [0.1.5] - 2026-10-08

- Muse's chat switcher is the dock control for the side-chat sidebar. `selftest` still accepts the old dropdown trigger, and a page with neither reports `ui_changed`. trinity-cli's Muse seat works again.
- On the new Muse shell, the main chat `title` may be null. `chats` uses a heading outside the sidebar, or `document.title`, and only when that text is not an interface label such as 「聊天室」. The old dropdown's name span is still used when it is there.
- `chats` does not click the dock link or any control that opens or closes the sidebar. A closed sidebar is `ui_changed` with hint 「請在 Muse 打開側欄後重試」.
- A side-chat row with `aria-current="page"` counts as the current chat, as well as `aria-current="true"`.
- A fresh profile that lands on Muse's signed-out page reports `session_expired` with the `muse-web-cli login` hint. It used to say `ui_changed`.
- `status`, `messages`, and `send` wait up to 8 seconds for a just-started Chrome to render the page before deciding it changed.
- `--help` and `--version` work even when the config file is broken.
- A config file saved with a UTF-8 byte-order mark, or as UTF-16 by PowerShell 5.1, loads. A config that is not text says so without printing the full path.
- Windows: a profile path with a space matches the running Chrome; PowerShell process output is read as UTF-8; the profile lock waits while another process holds it instead of failing at once.
- Hints say to rerun `muse-web-cli credential` instead of editing `auth.token` by hand.
- Docs: disclaimer and terms risk, privacy, platform matrix, and the uninstall cleanup. The gateway credential is written by `credential`, never by hand. CONTRIBUTING.md, SECURITY.md, and issue and merge request templates. No mirror link.
- Tests: Playwright loads three fixture DOMs and runs the real `SNAPSHOT_JS` / `CHATS_JS`. They are skipped when Playwright is not installed.

## [0.1.4] - 2026-10-01

- `send --wait` on the gateway now finds the reply in a chat longer than 20 messages. 0.1.3 compared positions in two windows that each hold only the latest messages, so in a long chat every wait timed out even after the reply arrived. The pre-send window and the poll are now lined up by content, and the poll reads 50 messages.
- `send --wait` keeps waiting until `--timeout` when the open Noise stream is quiet for longer than `timeout_s`. It still finishes reading that stream before the next request, and it still never sends again.
- `--session` on the browser backend is refused with exit 2 before anything is sent. It used to be ignored, so the text went to whatever chat the window had open.
- `chats --rename` and `--delete` take only a `session_id` that `chats` lists, the same ids as `--switch`. `--delete` refuses the main chat. Nothing is sent when the id is refused.
- Every printed `error` and `hint` is scrubbed of `auth_token=`, `access_token=`, `api_key:`, `password=`, `Bearer …`, and bare JWTs, in JSON and text output. A REST server's own error state is reshaped and can no longer produce exit 4 or extra keys.
- Clearing a draft that React did not commit uses Control+A on Linux and Windows (Meta+A only on macOS).
- Docs: the default backend is the browser; the gateway is `--backend api`; only `credential` stores a token, and only in `~/.trinity-cli/muse-credential` (mode 600). `credential`, `--session`, and the chat mutation flags are in the command reference.
- CI: a tag pipeline fails when the tag is not `v` plus the `pyproject.toml` version, or when that changelog section still says Unreleased. Tests check that the version, this changelog, `uv.lock`, and the README install pins agree.

## [0.1.3] - 2026-10-01

- The token is written only into `~/.trinity-cli/muse-credential` (mode 600) and is not printed. `credential` does that write; it does not print the token.
- The gateway is the `--backend api` behavior. Exit 4 is only a missing credential file, or both `vm_id` and `endpoints` empty. A missing token, bad JSON, a wrong auth field, and a permission error name the next step and use exit 2 or 3.
- `send --wait` accepts only a settled assistant message that appears after the pre-send snapshot, and returns immediately when that read is not ok.

## [0.1.2] - 2026-10-01

- Document first-time setup, every command, exit-code fixes, and troubleshooting in Traditional Chinese and English.
- Show global flags, defaults, and examples in `--help`.
- Support Linux, Windows, and macOS: Chrome discovery, process stop, profile locks, and UTF-8 console output. Linux is covered by CI, Windows by CI, and macOS by local tests plus a live read-only check.
- `login` on Linux without a display returns `browser_down` and leaves an already-running headless Chrome in place.
- The api backend is a generic client for a credential the user writes. With `vm_id` it calls the open Muse gateway for status, messages, send, pending, schedules, activity, memory, and chat list/create/rename/delete/switch. Exit 4 is a missing credential or an empty endpoint. The tool never extracts cookies or tokens.
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
