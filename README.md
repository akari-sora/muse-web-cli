# muse-web-cli

[![pipeline](https://gitlab.com/aa22396584/muse-web-cli/badges/main/pipeline.svg)](https://gitlab.com/aa22396584/muse-web-cli/-/commits/main)

[中文](#中文) · [English](#english)

trinity-cli 系列的一部分。Part of the trinity-cli family.

## 中文

### 這是什麼

`muse-web-cli` 在終端機操作**你自己已經登入**的 [Muse](https://muse.ai) 網頁。它用一個專用的 Chrome 設定檔，沒有公開 API。它不是第二個 Muse，也不會把登入狀態另存一份。Chrome 自己讀設定檔；這個工具只驅動頁面。

指令名稱是 `muse-web-cli`。`muse` 已經被 Meta 的 Muse Code 用掉了（`~/.local/bin/muse`），不要覆蓋它。

需要 Python 3.11 以上、`uv` 或 pipx、以及已安裝的 Google Chrome（或 Chromium）。Playwright 只拿來接上你自己的 Chrome。**不要**執行 `playwright install`。安裝時設定 `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`。不支援 Edge。

若頁面顯示這個地區無法使用 Muse，`status` 會是 `region_blocked`（結束碼 2）。這個工具不會繞過地區限制。

### 安裝

v0.1.2。裝好後執行 `muse-web-cli --version`，應印出 `muse-web-cli 0.1.2`。找不到指令時，把 `~/.local/bin` 加進 PATH。

macOS 與 Linux：

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.2"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pipx install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.2"
```

Windows（PowerShell）：

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"
uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.2"
muse-web-cli --version
```

升級時把標籤改成要裝的版本，再加 `--force` 裝一次。移除：`uv tool uninstall muse-web-cli` 或 `pipx uninstall muse-web-cli`。在這個 repo 裡開發可以用 `uv tool install --editable .`。

### 第一次設定

設定檔固定是 `~/.trinity-cli/muse-profile`（Windows 也是你的使用者主目錄底下的 `.trinity-cli`）。同一個設定檔同時只能有一個 Chrome。除錯埠預設 `127.0.0.1:9333`。

1. 有視窗登入。工具不會輸入帳號密碼。Linux 沒有顯示器時，在桌面工作階段登入，或用 `xvfb-run muse-web-cli login`。沒有顯示器時不會關掉已經在跑的 headless Chrome。不要複製 cookie。

```bash
muse-web-cli login
```

2. 確認頁面。`selftest` 只檢查選擇器，不點任何東西。`status` 看工作階段。

```bash
muse-web-cli selftest
muse-web-cli status
```

3. 之後可以無頭使用。埠上已經有 Chrome 就直接接上，不會開第二個。`--autostart` 一律無頭，做完留著給下次用。

```bash
muse-web-cli start --headless
muse-web-cli --autostart status
muse-web-cli stop
```

`stop` 只關這個工具自己啟動的那個進程。它不會動你平常的 Chrome。工作階段失效或無頭模式碰到人機驗證時，結束碼是 2，`hint` 是 `muse-web-cli login`，再用有視窗的方式登入一次。

設定檔 `~/.trinity-cli/muse-web-cli.json`（沒有就用預設）：

```json
{"port": 9333, "headless": true, "autostart": false, "backend": "browser", "chrome": ""}
```

環境變數：`MUSE_WEB_CDP_PORT`、`MUSE_WEB_HEADLESS`、`MUSE_WEB_AUTOSTART`、`MUSE_WEB_BACKEND`、`MUSE_WEB_CHROME`。優先順序是指令列、環境變數、設定檔、預設。

### 快速開始

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
muse-web-cli --json send --wait --timeout 120 -- "文字"
```

```json
{"backend":"browser","state":"ok","attempted":true,"sent":true,"text":"文字","reply":"…","presentation":false,"elapsed_ms":4000,"error":null,"hint":null}
```

```bash
muse-web-cli --json pending
```

```json
{"backend":"browser","state":"ok","count":0,"items":[],"error":null,"hint":null}
```

上面的文字是示意，不是你的對話內容。

### 指令參考

全域旗標可放在指令前或後：

| 旗標 | 預設 | 範圍 |
| --- | --- | --- |
| `--json` | 關 | 印出一個 JSON 物件 |
| `--port` | 9333 | 1–65535 |
| `--backend` | `browser` | `browser` 或 `api` |
| `--autostart` | 關 | 埠沒人聽時啟動無頭 Chrome |
| `--chrome PATH` | 依作業系統尋找 | 覆寫 `MUSE_WEB_CHROME` |
| `--version` |  | 印出版本 |

- `status` — 工作階段、待核可數量、最新助理訊息是不是卡片。`muse-web-cli status`
- `messages --limit N` — 由舊到新。預設 20，最小 1，超過 100 會截成 100。離畫面外的列是虛擬化的。`muse-web-cli messages --limit 20`
- `send TEXT` — `insertText` 加 Enter，只送一次。文字若以 `-` 開頭，前面加 `--`。`--wait` 預設關。`--timeout` 預設 120，必須大於 0。逾時不會重送。`muse-web-cli send --wait --timeout 120 -- "文字"`
- `pending` — 只讀核可項目，不點核可或拒絕。`muse-web-cli pending`
- `upcoming` — 只讀近期，不點列。`muse-web-cli upcoming`
- `activity` — 只讀動態，不點列。`muse-web-cli activity`
- `memory` — 只讀 MEMORY.md 的 `innerText`，不聚焦、不打字。`muse-web-cli memory`
- `chats` — 列出主聊天室與副聊天室，然後關回原來的畫面。不點「新副聊天室」，也不會打開任何一則。`muse-web-cli chats`
- `login` — 開有視窗的 Chrome，等你登入。`muse-web-cli login`
- `start` — 啟動專用 Chrome，或接上已經在跑的那一個。`--headless` 是預設（`--headless=new`）。`--headed` 顯示視窗。兩個旗標不能一起用。`muse-web-cli start --headless`
- `stop` — 只停止這個工具自己啟動的進程。`muse-web-cli stop`
- `selftest` — 檢查選擇器在不在，不點任何東西。切換鈕必須在。`muse-web-cli selftest`

`--json` 的鍵：

- `status`：`backend` `state` `pending` `latest_assistant_is_card` `headless` `error` `hint` `missing`
- `messages`：`backend` `state` `name` `lines` `messages` `error` `hint`。每則是 `role` `text` `presentation`
- `send`：`backend` `state` `attempted` `sent` `text` `reply` `presentation` `elapsed_ms` `error` `hint`
- `pending`：`backend` `state` `count` `items` `error` `hint`。item 是 `title` `detail` `time`
- `upcoming`：`backend` `state` `count` `groups` `error` `hint`。group 是 `title` 與 `items`（`name` `time`）
- `activity`：同樣有 `groups`，item 是 `title` `detail` `time`
- `memory`：`backend` `state` `chars` `sections` `text` `error` `hint`
- `chats`：`backend` `state` `count` `chats` `error` `hint`。每一則是 `title` `is_current` `kind`（`main` 或 `side`）。沒有副聊天室時 `count` 是主聊天室那一則
- `login` / `start` / `stop`：`backend` `state` `action` `port` `headless` `tracked` `logged_in` `error` `hint`
- `selftest`：`status` 的鍵，再加上 `present`

`messages` 與 `send` 作用在**目前已經打開**的那一則。若副聊天室是目前這一則，讀到的就是副聊天室。`chats` 只列出，不切換。

### 結束碼

| 碼 | state | 怎麼處理 |
| --- | --- | --- |
| 0 | `ok` | 不用處理 |
| 2 | `browser_down` | `muse-web-cli start --headless`，或加上 `--autostart` |
| 2 | `session_expired` | `muse-web-cli login`（有視窗） |
| 2 | `region_blocked` | 這個地區不能用。工具不會繞過 |
| 2 | `profile_busy` | 已有一個 Chrome 佔著設定檔。關掉那個視窗，或沿用已經開在 9333 的那一個。不要開第二個 |
| 2 | `credential_permissions` | macOS／Linux：`chmod 600 ~/.trinity-cli/muse-credential`。Windows：檔案必須在使用者主目錄裡，而且是一般檔案 |
| 3 | `ui_changed` | 跑 `selftest`，看 `missing`。不要在頁面上亂點 |
| 3 | `timeout` | `hint` 是 `nothing was sent again`。不要自動再送一次 |
| 4 | `unsupported` | 憑證檔不存在，或 `base_url`／`vm_id`／`endpoints` 沒填。不是「這個功能沒做」 |

### 後端

JSON 形狀和結束碼不因後端而改變。呼叫端不要自己分支。預設是 `browser`。選擇方式：`--backend`、`MUSE_WEB_BACKEND`、或設定檔的 `backend`。優先順序與上面相同。

- `browser`：有視窗或無頭，透過 CDP 操作頁面。預設是這個。
- `api`：憑證有 `vm_id` 時，走已經開啟的 Muse gateway（狀態、訊息、送訊、核可、排程、動態、記憶、聊天室的列表與建改刪切換）。沒有 `vm_id` 時，仍可用 `endpoints` 指到你自己的 REST。工具不會從瀏覽器取出 cookie 或 token，也不會把 token 寫進檔案。

憑證檔由你自己建立：`~/.trinity-cli/muse-credential`。macOS 與 Linux 權限必須正好是 `600`。Windows 不檢查 Unix 權限，但檔案必須在使用者主目錄裡。範例（token 是假的）：

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

`auth.type` 也可以是 `header`，那時用 `header_name`。指到 Muse gateway 時改放 `vm_id`（token 請自己換掉）：

```json
{
  "base_url": "https://hatch.metaaivm.com",
  "vm_id": "your-vm-id",
  "auth": {"type": "bearer", "token": "replace-me"},
  "timeout_s": 30
}
```

檔案不存在，或 `vm_id` 與 `endpoints` 都沒填：結束碼 4。401／403 是 `session_expired`（結束碼 2），下一步是換掉 `auth.token`。其它 4xx 與 5xx 是 `ui_changed`（結束碼 3）。逾時是 `timeout`（結束碼 3），`send` 不會再送一次。`send --wait` 若回應沒有 `reply`，只會再讀 `messages`，不會重送。`chats --create`、`--rename`、`--delete`、`--switch` 只在 `--backend api` 送出請求。瀏覽器後端維持只讀列表。

`start` / `stop` / `login` / `selftest` 永遠管本地 Chrome，不走 api。

### 安全

記憶體只讀。不會點設定、連接器、邀請、附加檔案、新的副聊天室、記憶工具列、核可或拒絕。不會讀、複製、儲存或印出 cookie、token、CSRF。不開 CDP 的 Network / Storage。不在瀏覽器外面重放 Muse 的請求。

### 排解

- 埠 9333 沒有 Chrome：`browser_down`。用 `start --headless` 或 `--autostart`。
- 登入牆或人機驗證：`session_expired`。用有視窗的 `login`。Linux 伺服器沒有顯示器時，先在桌面工作階段登入，或用 `xvfb-run`。不要複製 cookie。
- 副聊天室開著：`messages` 讀的是目前這一則。先跑 `chats` 看 `kind` 與 `is_current`。它不會幫你切回主聊天室。
- Muse 改版後選擇器不見：`ui_changed`。`selftest` 的 `missing` 會列出缺的名稱。

### 和 trinity-cli 一起用

座位不要依後端分支。建議 `--json --autostart`。專案：<https://gitlab.com/aa22396584/trinity-cli>

### 相關專案

- trinity-cli — 一個 CLI 管三個常駐代理（Your dot、Grok Bot、Muse）：<https://gitlab.com/aa22396584/trinity-cli>
- chatgpt-dot-cli — ChatGPT Your dot：<https://gitlab.com/aa22396584/chatgpt-dot-cli>
- grok-bot-cli（fork，`gbot`）— Grok Bot：<https://gitlab.com/aa22396584/grok-bot-cli>（鏡像 <https://github.com/ImL1s/grok-bot-cli>）
- muse-web-cli — 透過網頁操作 Meta Muse（這個 repo）：<https://gitlab.com/aa22396584/muse-web-cli>

MIT，見 [LICENSE](LICENSE)。Copyright (c) 2026 ImL1s。本機測試：`uv run --group dev pytest`。

## English

### What it is

`muse-web-cli` drives the [Muse](https://muse.ai) web app you are already logged into, through a dedicated Chrome profile. There is no public API. It is not a second Muse, and it does not export the login. Chrome reads the profile; this tool only drives the page.

The command is `muse-web-cli`. The name `muse` belongs to Meta's Muse Code (`~/.local/bin/muse`).

You need Python 3.11+, uv or pipx, and Google Chrome or Chromium already installed. Playwright attaches to that Chrome. Do **not** run `playwright install`. Set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` when installing. Edge is not supported.

If the page says Muse is not available in your region, `status` returns `region_blocked` (exit 2). The tool does not bypass that.

### Install

v0.1.2. After installing, `muse-web-cli --version` should print `muse-web-cli 0.1.2`. If the command is missing, add `~/.local/bin` to PATH.

macOS and Linux:

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.2"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pipx install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.2"
```

Windows (PowerShell):

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"
uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.2"
muse-web-cli --version
```

Upgrade by reinstalling the tag you want with `--force`. Uninstall with `uv tool uninstall muse-web-cli` or `pipx uninstall muse-web-cli`. In this checkout, `uv tool install --editable .` works.

### First-time setup

The profile is always `~/.trinity-cli/muse-profile` (`Path.home()` on every OS). One Chrome per profile. The debug port defaults to `127.0.0.1:9333`.

1. Log in headed. The tool never types credentials. On a Linux server with no display, log in on a desktop session or run `xvfb-run muse-web-cli login`. Without a display, login leaves a running headless Chrome in place. Do not copy cookies.

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

Environment: `MUSE_WEB_CDP_PORT`, `MUSE_WEB_HEADLESS`, `MUSE_WEB_AUTOSTART`, `MUSE_WEB_BACKEND`, `MUSE_WEB_CHROME`. Precedence is flag, then environment, then config, then default.

### Quick start

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

### Command reference

Global flags may appear before or after the command:

| Flag | Default | Range |
| --- | --- | --- |
| `--json` | off | print one JSON object |
| `--port` | 9333 | 1–65535 |
| `--backend` | `browser` | `browser` or `api` |
| `--autostart` | off | start headless Chrome when nothing is listening |
| `--chrome PATH` | discovered per OS | overrides `MUSE_WEB_CHROME` |
| `--version` |  | print the version |

- `status` — session, pending count, and whether the latest assistant message is a card. `muse-web-cli status`
- `messages --limit N` — oldest to newest. Default 20, minimum 1, values above 100 are capped at 100. Off-screen rows are virtualized. `muse-web-cli messages --limit 20`
- `send TEXT` — insertText and Enter, once. Put `--` before text that starts with `-`. `--wait` defaults off. `--timeout` defaults to 120 and must be > 0. A timeout never resends. `muse-web-cli send --wait --timeout 120 -- "text"`
- `pending` — read approvals. It does not approve or reject. `muse-web-cli pending`
- `upcoming` — read the upcoming tab. It does not click a row. `muse-web-cli upcoming`
- `activity` — read the activity tab. It does not click a row. `muse-web-cli activity`
- `memory` — read MEMORY.md `innerText`. It does not focus or type. `muse-web-cli memory`
- `chats` — list the main chat and any side chats, then restore the previous view. It does not click "新副聊天室" / new side chat, and it does not open a chat. `muse-web-cli chats`
- `login` — open a headed window so you can log in. `muse-web-cli login`
- `start` — start the dedicated Chrome, or attach if it is already running. `--headless` is the default (`--headless=new`). `--headed` shows the window. The two flags cannot be combined. `muse-web-cli start --headless`
- `stop` — stop only the process this tool started. `muse-web-cli stop`
- `selftest` — check that selectors exist. It clicks nothing. The switcher trigger is required. `muse-web-cli selftest`

`--json` keys:

- `status`: `backend` `state` `pending` `latest_assistant_is_card` `headless` `error` `hint` `missing`
- `messages`: `backend` `state` `name` `lines` `messages` `error` `hint`. Each message is `role` `text` `presentation`
- `send`: `backend` `state` `attempted` `sent` `text` `reply` `presentation` `elapsed_ms` `error` `hint`
- `pending`: `backend` `state` `count` `items` `error` `hint`. An item is `title` `detail` `time`
- `upcoming`: `backend` `state` `count` `groups` `error` `hint`. A group is `title` plus `items` of `name` `time`
- `activity`: the same `groups` shape; an item is `title` `detail` `time`
- `memory`: `backend` `state` `chars` `sections` `text` `error` `hint`
- `chats`: `backend` `state` `count` `chats` `error` `hint`. Each chat is `title` `is_current` `kind` (`main` or `side`). With no side chats, `count` is the main chat only
- `login` / `start` / `stop`: `backend` `state` `action` `port` `headless` `tracked` `logged_in` `error` `hint`
- `selftest`: the `status` keys plus `present`

`messages` and `send` act on the chat that is already open. If a side chat is current, that is what you read. `chats` lists them and does not switch.

### Exit codes

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
| 4 | `unsupported` | The credential file is missing, or `base_url` / `vm_id` / `endpoints` is empty. Not an unimplemented command |

### Backends

JSON shapes and exit codes do not depend on the backend. Callers should not branch. The default is `browser`. Select it with `--backend`, `MUSE_WEB_BACKEND`, or the config key `backend`. Precedence is the same as above.

- `browser`: headed or headless, over CDP. This is the default.
- `api`: with `vm_id`, this talks to the open Muse gateway (status, messages, send, pending, schedules, activity, memory, and chat list/create/rename/delete/switch). Without `vm_id`, `endpoints` still selects a REST path you configure. The tool never extracts cookies or tokens from the browser, and it never writes a token into the file.

You create `~/.trinity-cli/muse-credential` yourself. On macOS and Linux the mode must be exactly `600`. On Windows the Unix mode is not checked, but the file must be under your home directory. Example (the token is fake):

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

`auth.type` may also be `header`, which uses `header_name`. To use the Muse gateway, set `vm_id` and `base_url` to `https://hatch.metaaivm.com` instead of `endpoints`. A missing file, or neither `vm_id` nor `endpoints`, is exit 4. HTTP 401/403 is `session_expired` (exit 2); replace `auth.token`. Other 4xx and 5xx are `ui_changed` (exit 3). A timeout is `timeout` (exit 3), and `send` is not repeated. If `send --wait` gets no `reply`, the client only reads `messages`. It does not post again. `chats --create`, `--rename`, `--delete`, and `--switch` send those requests only with `--backend api`.

`start`, `stop`, `login`, and `selftest` always manage the local Chrome. They are not the api seam.

### Safety

Memory is read-only. The tool never clicks settings, connectors, invites, attach, a new side chat, the memory toolbar, or approve/reject. It does not read, copy, store, or print cookies, tokens, or CSRF values. It does not enable the CDP Network or Storage domains. It does not replay Muse requests outside the browser.

### Troubleshooting

- Nothing is listening on port 9333: `browser_down`. Use `start --headless` or `--autostart`.
- Login wall or bot check: `session_expired`. Use headed `login`. On a Linux server with no display, log in on a desktop session or use `xvfb-run`. Do not copy cookies.
- A side chat is open: `messages` reads the current chat. Run `chats` and look at `kind` and `is_current`. It does not switch back to the main chat.
- Muse shipped a new UI and selectors are gone: `ui_changed`. `selftest` lists the missing names in `missing`.

### Use with trinity-cli

Do not branch on backend. Pass `--json --autostart`. Project: <https://gitlab.com/aa22396584/trinity-cli>

### Related projects

- trinity-cli — one CLI over three always-on agents (Your dot, Grok Bot, Muse): <https://gitlab.com/aa22396584/trinity-cli>
- chatgpt-dot-cli — ChatGPT Your dot: <https://gitlab.com/aa22396584/chatgpt-dot-cli>
- grok-bot-cli (fork, `gbot`) — Grok Bot: <https://gitlab.com/aa22396584/grok-bot-cli> (mirror <https://github.com/ImL1s/grok-bot-cli>)
- muse-web-cli — Meta Muse via the web (this repo): <https://gitlab.com/aa22396584/muse-web-cli>

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 ImL1s. Local tests: `uv run --group dev pytest`.
