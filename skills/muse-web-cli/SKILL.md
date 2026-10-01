---
name: muse-web-cli
description: >-
  Drive the user's own logged-in Meta Muse web app (muse.ai) with the
  muse-web-cli command, headed or headless. Use when the user asks to check
  Muse, read Muse messages, list Muse chats, send a message to Muse, or look at Muse pending
  approvals, upcoming items, activity, or memory. 用 muse-web-cli 操作使用者自己已登入的
  Meta Muse：當使用者要查看 Muse、讀 Muse 訊息、列出聊天室、傳訊息給 Muse，或查看核可、近期、動態、記憶時使用。
  The command is muse-web-cli, never muse. 指令是 muse-web-cli，不是 muse。
---

# Muse 網頁

用 `muse-web-cli` 操作使用者自己已登入的 Muse。它不是第二個 Muse。登入留在 `~/.trinity-cli/muse-profile`，工具只驅動頁面。

回覆使用使用者這則訊息的語言。

## 步驟

1. 先跑 `muse-web-cli --json --autostart status`（大約數秒）。PATH 沒有時用 `~/.local/bin/muse-web-cli`。
2. 結束碼 2 且 `state` 是 `browser_down`：再跑一次並保留 `--autostart`。若是 `session_expired`，請使用者執行 `muse-web-cli login`（一定是有視窗的）。無頭模式碰到人機驗證時也是這條。工具不會輸入帳號密碼。
3. 結束碼 3 且 `state` 是 `ui_changed`：頁面結構變了，不要亂點，把 `missing` 裡的名稱告訴使用者。
4. 使用者要看訊息才跑 `messages`。要傳訊息才跑 `send`。傳的時候加 `--wait`，逾時不要再送一次。
5. `pending`、`upcoming`、`activity`、`memory`、`chats` 都是唯讀。`chats` 只列出主聊天室和副聊天室，不開新副聊天室，也不會切換聊天。

## 指令

`--json` 可放在指令前或後。預設後端是 `browser`。不要依後端寫分支；api 後端目前每個能力都是 `unsupported`（結束碼 4）。

- `status` — 工作階段、待核可數量、最新助理訊息是不是卡片
- `messages --limit N` — 由舊到新，上限 100
- `send --wait --timeout 120 -- TEXT` — insertText 與 Enter，只送一次
- `pending` / `upcoming` / `activity` / `memory` / `chats`
- `login` / `start` / `start --headed` / `stop` / `selftest`

`start` 預設無頭。設定檔已有 Chrome 時直接接上，不開第二個。`stop` 只關這個工具自己啟動的進程。

## 結束碼

- 0：成功
- 2：`browser_down`、`session_expired`、`region_blocked`、`profile_busy`、`credential_permissions`
- 3：`ui_changed`、`timeout`
- 4：`unsupported`

## 安全限制

- 不要讀、存或印出 cookie、token、CSRF，也不要自己呼叫 muse.ai 的 HTTP API。
- 不要點設定、連接器、邀請、附加檔案、新的側邊聊天、記憶工具列、核可或拒絕。
- 記憶體只讀。不要聚焦，不要打字進去。
- 不要請 Muse 刪檔或執行破壞性指令（例如 rm -rf）。
- 不要請 Muse 傳訊息給任何人（Telegram、email、Slack、WhatsApp）。
- 不要請 Muse 購買，或變更帳號與設定。
- 測試訊息要短，並標明是 trinity 測試。使用者沒有要求時，不要主動傳訊息。
