# Changelog

## [0.1.1] - 2026-10-01

- Add a read-only `chats` command that lists the main chat and any side chats.
- Opening the switcher does not create a side chat and does not open one. The previous view is restored.
- The api backend returns `unsupported` for `chats`.

## [0.1.0] - 2026-10-01

- Drive a logged-in Muse web session from the terminal through a dedicated Chrome profile, headed or headless.
- Commands: status, messages, send, pending, upcoming, activity, memory, login, start, stop, selftest.
- The browser backend is the default. The api backend is a seam until a supported Muse API exists.
- The tool does not read cookies, tokens, or the contents of the credential file.
