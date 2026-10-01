# muse-web-cli

[![pipeline](https://gitlab.com/aa22396584/muse-web-cli/badges/main/pipeline.svg)](https://gitlab.com/aa22396584/muse-web-cli/-/commits/main)

[中文](#中文) · [English](#english)

## 中文

`muse-web-cli` 讓你在終端機操作**自己已經登入**的 [Muse](https://muse.ai) 網頁。它不是第二個 Muse，也不會把登入狀態另存一份。登入留在專用的 Chrome 設定檔裡，Chrome 自己讀；這個工具只驅動頁面。

指令名稱是 `muse-web-cli`。`muse` 這個名字已經被 Meta 的 Muse Code 用掉了（`~/.local/bin/muse`），不要覆蓋它。

沒有視窗也能用。先用有視窗的方式登入一次，之後 `start --headless` 或 `--autostart` 會在背景啟動同一個設定檔。無頭模式比較容易碰到人機驗證或登入牆；發生時結束碼是 2，`hint` 會是 `muse-web-cli login`，用有視窗的方式再登入一次。

### 安裝

需要 Python 3.11 以上，以及已安裝的 Google Chrome。Playwright 只拿來接上你自己的 Chrome，不必再下載瀏覽器。

v0.1.1：

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.1"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pipx install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.1"
```

升級時把標籤改成要裝的版本，再裝一次：

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv tool install --force "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.1"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pipx install --force "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.1"
```

移除：

```bash
uv tool uninstall muse-web-cli
pipx uninstall muse-web-cli
```

在這個 repo 裡開發可以用 `uv tool install --editable .`。執行 `muse-web-cli --version` 或 `muse-web-cli --help`。找不到指令時，把 `~/.local/bin` 加進 PATH。

### 登入與背景執行

設定檔固定是 `~/.trinity-cli/muse-profile`。同一個設定檔同時只能有一個 Chrome。除錯埠預設 `127.0.0.1:9333`。

```bash
muse-web-cli login          # 有視窗。你自己登入，工具不會輸入帳號密碼
muse-web-cli start          # 預設 --headless=new；已經在跑就直接接上，不會開第二個
muse-web-cli start --headed # 要看視窗時用這個
muse-web-cli stop           # 只關閉「這個工具自己啟動」的那個 Chrome
```

`stop` 認的是它記下來的 PID，而且會再對一次命令列裡的設定檔路徑。它不會動你平常的 Chrome。如果畫面上那個視窗不是它啟動的，`stop` 會留著不動。

其它指令不管底層是有視窗還是無頭，都走同一條 CDP 路。埠上沒有 Chrome 時加上 `--autostart`，它會自己起一個無頭實例、做完之後留著給下次用：

```bash
muse-web-cli --autostart status
muse-web-cli --autostart send --wait -- "文字"
```

`--autostart` 一律是無頭。要看視窗請用 `login` 或 `start --headed`。

設定檔 `~/.trinity-cli/muse-web-cli.json`（沒有就用預設）：

```json
{"port": 9333, "headless": true, "autostart": false, "backend": "browser"}
```

環境變數：`MUSE_WEB_CDP_PORT`、`MUSE_WEB_HEADLESS`、`MUSE_WEB_AUTOSTART`、`MUSE_WEB_BACKEND`、`MUSE_WEB_CHROME`。優先順序是指令列、環境變數、設定檔、預設。`--json`、`--port`、`--backend`、`--autostart` 放在指令前或後都可以。

### 後端

指令的 JSON 形狀和結束碼不因後端而改變。呼叫端不要自己分支。

- `browser`（預設）：有視窗或無頭，透過 CDP 操作頁面。現在就能用。
- `api`：只有介面縫。`--backend api`、`MUSE_WEB_BACKEND=api` 或設定檔。憑證檔要使用者自己放到 `~/.trinity-cli/muse-credential`，權限必須正好是 `600`。這個工具不會取得、建立、記錄或印出檔案內容，也不會從瀏覽器讀登入資料。權限太鬆會拒絕。檔案不存在時，比照工作階段失效（結束碼 2）。目前沒有受支援的 Muse API，每個能力都回 `unsupported`（結束碼 4）。`status` 的錯誤文字是 `api backend: not available yet (no supported Muse API)`。以後的 API 後端會跟著 `~/.trinity-cli-infra/muse-api-research.md` 走。這裡不會去猜或重放 muse.ai 的請求。

### 指令

```bash
muse-web-cli status
muse-web-cli messages --limit 20
muse-web-cli send --wait --timeout 120 -- "文字"
muse-web-cli pending
muse-web-cli upcoming
muse-web-cli activity
muse-web-cli memory
muse-web-cli chats
muse-web-cli selftest
```

- `messages` 由舊到新。離畫面外的訊息是虛擬化的，讀的是目前掛上的視窗（會先捲到最新）。
- `send` 用 `insertText` 加 Enter，只送一次。`--wait` 等到新的助理訊息完成：複製回覆的按鈕出現，而且 `aria-busy` 與 `data-hatch-markdown-streaming` 都是 false，或這兩個屬性在完成後已被拿掉。逾時不會重送。
- `pending` 只讀，不點核可或拒絕。
- `memory` 只讀 Lexical 編輯器的 `innerText`，不會聚焦、不會打字。
- `chats` 只列出主聊天室和副聊天室。它會打開切換面板、讀完、再關回原來的畫面。不點「新副聊天室」，也不會打開任何一則聊天。
- `selftest` 只檢查選擇器在不在，不點任何東西。切換鈕 `hatch-chat-switcher-trigger` 必須在。

不會點的東西：設定、連接器、邀請、附加檔案、新的側邊聊天、記憶編輯器工具列、核可／拒絕。

### 結束碼

| 碼 | 意義 |
| --- | --- |
| 0 | 成功 |
| 2 | 環境：`browser_down`、`session_expired`、`region_blocked`、`profile_busy`、`credential_permissions` |
| 3 | 頁面：`ui_changed`、`timeout` |
| 4 | `unsupported`（api 後端還沒有實作） |

### 給 trinity 的介面

座位不要依後端分支。預設後端是 browser。建議每次都加 `--json --autostart`，這樣背景工作在埠是空的時候會自己起無頭 Chrome，已經有視窗就沿用。

```bash
muse-web-cli --json --autostart status
muse-web-cli --json --autostart messages --limit 30
muse-web-cli --json --autostart send --wait --timeout 120 -- "文字"
muse-web-cli --json --autostart pending
muse-web-cli --json --autostart upcoming
muse-web-cli --json --autostart activity
muse-web-cli --json --autostart memory
muse-web-cli --json --autostart chats
```

`status`：

```json
{"backend":"browser","state":"ok","pending":0,"latest_assistant_is_card":false,"headless":true,"error":null,"hint":null,"missing":[]}
```

`state` 還可能是 `browser_down`、`session_expired`、`region_blocked`、`profile_busy`、`ui_changed`、`unsupported`、`credential_permissions`。`session_expired` 的 `hint` 是 `muse-web-cli login`。

`messages`：

```json
{"backend":"browser","state":"ok","name":"Muse","lines":["user: 你好","assistant: 收到"],"messages":[{"role":"user","text":"你好","presentation":false},{"role":"assistant","text":"收到","presentation":true}],"error":null,"hint":null}
```

`lines` 與 `messages` 都是由舊到新。`presentation: true` 代表那則是在等使用者的卡片，只讀。

`send`：

```json
{"backend":"browser","state":"ok","attempted":true,"sent":true,"text":"文字","reply":"收到","presentation":false,"elapsed_ms":4000,"error":null,"hint":null}
```

沒加 `--wait` 時 `reply` 和 `presentation` 是 null。逾時時 `state` 是 `timeout`，`hint` 是 `nothing was sent again`，`sent` 表示使用者那則有沒有出現在畫面上。

`pending`：`{"backend","state","count","items","error","hint"}`，item 是 `{"title","detail","time"}`。

`upcoming`：`{"backend","state","count","groups","error","hint"}`，group 是 `{"title","items":[{"name","time"}]}`。

`activity`：同樣有 `groups`，item 是 `{"title","detail","time"}`。

`memory`：`{"backend","state","chars","sections","text","error","hint"}`。`sections` 是內文裡看得到的 `Facts`、`Preferences`、`Commitments`。

`chats`：`{"backend","state","count","chats","error","hint"}`。每一則是 `{"title","is_current","kind"}`，`kind` 是 `main` 或 `side`。沒有副聊天室時 `count` 是主聊天室那一則。

api 後端用同一組鍵。還沒實作時 `state` 是 `unsupported`，結束碼 4，列表是空的，`memory.text` 是空字串。

`start` / `stop` / `login` / `selftest` 永遠管本地 Chrome，不走 api 縫。`selftest` 失敗時 `missing` 列出缺的選擇器名稱。

### 風險

這是在自動化你自己的瀏覽器，可能抵觸 Meta 的服務條款，也可能被偵測為自動化。無頭模式風險更高。介面改版、或 aria-label 不是繁體中文時，`selftest` / `status` 會回 `ui_changed`。繁體中文標籤是在已登入的頁面上核對過的；英文標籤是同一組控制項的備用寫法，那次頁面上沒有出現。

### 不會做的事

不讀、不複製、不存、不印 cookie、token、CSRF 或其它登入材料。不開 CDP 的 Network / Storage domain。不在瀏覽器外面重放請求。不把憑證寫進檔案。api 後端也不會去讀那個憑證檔的內容。

### 授權

MIT，見 [LICENSE](LICENSE)。Copyright (c) 2026 ImL1s。

本機測試：

```bash
uv run --group dev pytest
```

## English

`muse-web-cli` drives the Muse web app you are already logged into. It is not a second Muse, and it does not export the login. The login stays in a dedicated Chrome profile; Chrome reads it, and this tool only drives the page.

The command is `muse-web-cli`. The name `muse` belongs to Meta's Muse Code agent (`~/.local/bin/muse`).

It works without a visible window. Log in once headed, then `start --headless` or `--autostart` reuses that same profile in the background. Headless mode is more likely to hit a bot check or a login wall. That is `session_expired` (exit 2) with hint `muse-web-cli login`: run the headed login once.

### Install

Python 3.11+, and Google Chrome already installed. Playwright attaches to that Chrome. Do not download a Playwright browser.

v0.1.1:

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.1"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pipx install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.1"
```

Upgrade by reinstalling the tag you want:

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv tool install --force "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.1"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pipx install --force "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.1"
```

Uninstall:

```bash
uv tool uninstall muse-web-cli
pipx uninstall muse-web-cli
```

For development in this checkout, `uv tool install --editable .` works. Run `muse-web-cli --version` or `muse-web-cli --help`. If the command is missing, add `~/.local/bin` to PATH.

### Login and background use

The profile is always `~/.trinity-cli/muse-profile`. Chrome allows one process per profile. The debug port defaults to `127.0.0.1:9333`.

```bash
muse-web-cli login           # headed. You log in. The tool never types credentials
muse-web-cli start           # headless=new unless a Chrome is already on the profile
muse-web-cli start --headed
muse-web-cli stop            # only the process this tool started
```

`stop` signals the recorded PID only after the command line still points at this profile. It does not touch your normal Chrome. If the window was not started by this tool, `stop` leaves it running.

Every other command uses the same CDP path whether the window is visible or not. `--autostart` starts a headless instance when the port is closed, then leaves it running:

```bash
muse-web-cli --autostart status
muse-web-cli --autostart send --wait -- "text"
```

Autostart is always headless. Use `login` or `start --headed` when you need a window.

Config file `~/.trinity-cli/muse-web-cli.json` (defaults apply if it is missing):

```json
{"port": 9333, "headless": true, "autostart": false, "backend": "browser"}
```

Environment: `MUSE_WEB_CDP_PORT`, `MUSE_WEB_HEADLESS`, `MUSE_WEB_AUTOSTART`, `MUSE_WEB_BACKEND`, `MUSE_WEB_CHROME`. Precedence is flag, then environment, then config, then default. `--json`, `--port`, `--backend`, and `--autostart` may appear before or after the command.

### Backends

JSON shapes and exit codes do not depend on the backend. Callers should not branch.

- `browser` (default): headed or headless, over CDP. This works now.
- `api`: a seam only. Select it with `--backend api`, `MUSE_WEB_BACKEND=api`, or the config key. The user places `~/.trinity-cli/muse-credential` themselves, mode exactly `600`. The tool never obtains, creates, logs, or prints the file, and never reads auth material from the browser. Looser permissions are refused. A missing file is a session-expired setup error (exit 2). There is no supported Muse API yet, so every capability returns `unsupported` (exit 4). `status` reports `api backend: not available yet (no supported Muse API)`. A future api backend will follow `~/.trinity-cli-infra/muse-api-research.md`. This repo does not sniff or replay muse.ai requests.

### Commands

```bash
muse-web-cli status
muse-web-cli messages --limit 20
muse-web-cli send --wait --timeout 120 -- "text"
muse-web-cli pending
muse-web-cli upcoming
muse-web-cli activity
muse-web-cli memory
muse-web-cli chats
muse-web-cli selftest
```

- `messages` is oldest to newest. Off-screen rows are virtualized; the command scrolls to the latest mounted window.
- `send` uses insertText and Enter, once. `--wait` finishes when the copy-reply action is present and both `aria-busy` and `data-hatch-markdown-streaming` are false, or those attributes have already been removed. A timeout never resends.
- `pending` is read-only. It does not approve or reject.
- `memory` reads the Lexical editor's `innerText`. It does not focus or type.
- `chats` lists the main chat and any side chats. It opens the switcher, reads, and restores the previous view. It does not click "新副聊天室" / new side chat, and it does not open a chat.
- `selftest` checks that selectors exist. It clicks nothing. The switcher trigger `hatch-chat-switcher-trigger` is required.

It never clicks settings, connector cards, invites, attach file, a new side chat, the memory editor toolbar, or approve/reject.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 2 | setup: `browser_down`, `session_expired`, `region_blocked`, `profile_busy`, `credential_permissions` |
| 3 | page: `ui_changed`, `timeout` |
| 4 | `unsupported` (the api backend is not implemented) |

### Interface for trinity

Do not branch on backend. The default is browser. Pass `--json --autostart` so a background caller starts headless Chrome when the port is free, and reuses a headed window when one is already up.

```bash
muse-web-cli --json --autostart status
muse-web-cli --json --autostart messages --limit 30
muse-web-cli --json --autostart send --wait --timeout 120 -- "text"
muse-web-cli --json --autostart pending
muse-web-cli --json --autostart upcoming
muse-web-cli --json --autostart activity
muse-web-cli --json --autostart memory
muse-web-cli --json --autostart chats
```

`status`:

```json
{"backend":"browser","state":"ok","pending":0,"latest_assistant_is_card":false,"headless":true,"error":null,"hint":null,"missing":[]}
```

`state` may also be `browser_down`, `session_expired`, `region_blocked`, `profile_busy`, `ui_changed`, `unsupported`, or `credential_permissions`. The `session_expired` hint is `muse-web-cli login`.

`messages`:

```json
{"backend":"browser","state":"ok","name":"Muse","lines":["user: hi","assistant: ok"],"messages":[{"role":"user","text":"hi","presentation":false},{"role":"assistant","text":"ok","presentation":true}],"error":null,"hint":null}
```

`lines` and `messages` are oldest to newest. `presentation: true` is a card waiting on the user. Read it; do not click it.

`send`:

```json
{"backend":"browser","state":"ok","attempted":true,"sent":true,"text":"text","reply":"ok","presentation":false,"elapsed_ms":4000,"error":null,"hint":null}
```

Without `--wait`, `reply` and `presentation` are null. On timeout, `state` is `timeout`, `hint` is `nothing was sent again`, and `sent` says whether the user row appeared.

`pending`: `{"backend","state","count","items","error","hint"}` with items `{"title","detail","time"}`.

`upcoming`: `{"backend","state","count","groups","error","hint"}` with groups `{"title","items":[{"name","time"}]}`.

`activity`: the same `groups` shape, items `{"title","detail","time"}`.

`memory`: `{"backend","state","chars","sections","text","error","hint"}`. `sections` lists `Facts`, `Preferences`, and `Commitments` when they appear in the text.

`chats`: `{"backend","state","count","chats","error","hint"}`. Each chat is `{"title","is_current","kind"}` with `kind` `main` or `side`. With no side chats, `count` is the main chat only.

The api backend uses the same keys. Until it is implemented, `state` is `unsupported`, the exit code is 4, lists are empty, and `memory.text` is an empty string.

`start`, `stop`, `login`, and `selftest` always manage the local Chrome. They are not the api seam. `selftest` puts the missing selector names in `missing`.

### Risks

This automates your own browser. That can conflict with Meta's terms, and it can be detected. Headless mode raises that risk. If the UI changes, or the labels are not Traditional Chinese, `selftest` and `status` return `ui_changed`. The zh-TW labels were checked on a logged-in page. English labels are best-effort equivalents; that page did not show them.

### What it does not do

It does not read, copy, store, or print cookies, tokens, CSRF values, or other auth material. It does not enable the CDP Network or Storage domains. It does not replay requests outside the browser. It does not write credentials to a file. The api backend does not read the credential file's contents.

### License

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 ImL1s.

Local tests:

```bash
uv run --group dev pytest
```
