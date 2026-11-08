# muse-web-cli

> 正本和 issue 在 <https://gitlab.com/aa22396584/muse-web-cli>。

[![pipeline](https://gitlab.com/aa22396584/muse-web-cli/badges/main/pipeline.svg)](https://gitlab.com/aa22396584/muse-web-cli/-/commits/main)
[![release](https://gitlab.com/aa22396584/muse-web-cli/-/badges/release.svg)](https://gitlab.com/aa22396584/muse-web-cli/-/releases)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[中文](#中文) · [English](#english)

trinity-cli 系列的一部分。Part of the trinity-cli family.

## 中文

### 這是什麼

`muse-web-cli` 在終端機操作**你自己已經登入**的 [Muse](https://muse.ai) 網頁。它不是第二個 Muse。預設是瀏覽器後端：用一個專用的 Chrome 設定檔驅動頁面，不讀 cookie；Chrome 自己讀設定檔。

會存 token 的只有 `credential`：它從已登入的頁面取得 gateway token，只寫進 `~/.trinity-cli/muse-credential`（mode 600），不印出來。`--backend api` 用這份檔案走 Muse gateway。不用 api 就不必執行它。

指令名稱是 `muse-web-cli`。`muse` 已經被 Meta 的 Muse Code 用掉了（`~/.local/bin/muse`），不要覆蓋它。

需要 Python 3.11 以上、`uv` 或 pipx、以及已安裝的 Google Chrome（或 Chromium）。Playwright 只拿來接上你自己的 Chrome。**不要**執行 `playwright install`。安裝時設定 `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`。不支援 Edge。

若頁面顯示這個地區無法使用 Muse，`status` 會是 `region_blocked`（結束碼 2）。這個工具不會繞過地區限制。

非官方：這是個人專案，跟 Meta 沒有關係，也沒有得到 Meta 的背書或支援。瀏覽器後端驅動你自己登入的網頁；api 後端呼叫沒有公開文件的 Muse gateway。兩者都可能隨時失效。自動化使用可能違反 Meta 的使用條款，或讓帳號受到限制，風險自負。

支援的系統見[平台](#平台)。

### 安裝

v0.1.6。裝好後執行 `muse-web-cli --version`，應印出 `muse-web-cli 0.1.6`。找不到指令時，把 `~/.local/bin` 加進 PATH。

macOS 與 Linux：

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.6"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pipx install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.6"
```

Windows（PowerShell）：

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"
uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.6"
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
- `messages --limit N` — 由舊到新。預設 20，最小 1，超過 100 會截成 100。離畫面外的列是虛擬化的。`--session ID` 只在 `--backend api` 有效。`muse-web-cli messages --limit 20`
- `send TEXT` — `insertText` 加 Enter，只送一次。文字若以 `-` 開頭，前面加 `--`。`--wait` 預設關。`--timeout` 預設 120，必須大於 0。逾時不會重送。`--wait` 只接受送出前快照之後才出現的回覆，聊天很長也一樣。`--session ID` 只在 `--backend api` 有效；瀏覽器後端給了會以結束碼 2 拒絕，不會送出。`muse-web-cli send --wait --timeout 120 -- "文字"`
- `send --attach FILE`（可重複）— 透過 Muse 視窗上傳檔案再送出，只送一次；檔案不存在或不是一般檔案時結束碼 2，什麼都不送。`--attach-sha256 HEX`（可重複，依 `--attach` 的順序）：檔案只讀一次，Muse 拿到的就是算過雜湊的那份位元組（50 MB 內直接交給瀏覽器，更大的先寫成只有自己能讀的暫存副本）；不符就結束碼 2，什麼都不上傳、不送。加 `--session ID` 時先打開那則副聊天室（`muse.ai/thread/<ID>`），送完回主聊天室；有 `--backend api` 憑證時用 api 等回覆。檔案沒附上就不送訊息，並從輸入框移除已附上的檔案（Muse 可能已經收下上傳的檔案）。頁面沒有顯示那則副聊天室（`muse.ai/thread/<ID>`）就什麼都不送。送完回不了主聊天室時仍回報已送出，並在 `warning` 註明。`muse-web-cli --backend api send --session ID --attach bundle.zip --wait -- "解壓縮…"`
- `pending` — 只讀核可項目，不點核可或拒絕。`muse-web-cli pending`
- `upcoming` — 只讀近期，不點列。`muse-web-cli upcoming`
- `activity` — 只讀動態，不點列。`muse-web-cli activity`
- `memory` — 只讀 MEMORY.md 的 `innerText`，不聚焦、不打字。`muse-web-cli memory`
- `chats` — 列出已經打開的側欄裡的主聊天室與副聊天室。側欄關著時不點開關，`state` 是 `ui_changed`，hint 是「請在 Muse 打開側欄後重試」。不點「新副聊天室」，也不會打開任何一則。新版介面的主標題可能是 null。`muse-web-cli chats`
- `chats --create [--title T]`、`--rename ID --title T`、`--delete ID`、`--switch ID|main` — 只在 `--backend api`。`ID` 是 `chats` 列出的 `session_id`，四個動作用同一套 id。`--create` 會把新聊天室設成目前這一則，`--json` 的 `created` 是它的 id。`--delete` 不接受主聊天室；`--rename`、`--delete` 碰到沒列出的 id 會拒絕，不送出。`muse-web-cli --backend api chats --switch main`
- `credential` — 從已登入的頁面取得 gateway token，只寫進 `~/.trinity-cli/muse-credential`（mode 600），不印出。沒登入會先走 `login`。`muse-web-cli credential`
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
- `chats`：`backend` `state` `count` `chats` `error` `hint`。每一則是 `title` `is_current` `kind`（`main` 或 `side`），`--backend api` 另有 `session_id`。沒有副聊天室時 `count` 是主聊天室那一則。新版介面的 `title` 可能是 null
- `credential`：`backend` `state` `action` `wrote` `logged_in` `fields` `error` `hint`。`fields` 只寫每個欄位有沒有值（`true`／`false`），沒有 token 本身
- `login` / `start` / `stop`：`backend` `state` `action` `port` `headless` `tracked` `logged_in` `error` `hint`
- `selftest`：`status` 的鍵，再加上 `present`

瀏覽器後端：`messages` 與 `send` 作用在**目前已經打開**的那一則。若副聊天室是目前這一則，讀到的就是副聊天室。`chats` 只列出，不切換。`--backend api`：`--session ID` 指定一則；沒給就用 `chats --switch`（或 `--create`）記下的那一則；`--switch main` 回主聊天室。

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
| 4 | `unsupported` | 只在 `--backend api`：憑證檔不存在，或沒有 `vm_id` 而且這個指令沒有 endpoint。伺服器回的狀態不會變成 4。缺 token、JSON 壞掉、欄位不對是 2 或 3。不是「這個功能沒做」 |

### 後端

JSON 形狀和結束碼不因後端而改變。呼叫端不要自己分支。預設是 `browser`。選擇方式：`--backend`、`MUSE_WEB_BACKEND`、或設定檔的 `backend`。優先順序與上面相同。

- `browser`：有視窗或無頭，透過 CDP 操作頁面。預設是這個。
- `api`：Muse gateway 就是這個後端。憑證有 `vm_id` 時，走 gateway（狀態、訊息、送訊、核可、排程、動態、記憶、聊天室的列表與建改刪切換）。沒有 `vm_id` 時，仍可用 `endpoints` 指到你自己的 REST。

`credential` 從已經登入的 Muse 頁面取得 gateway token，只寫進 `~/.trinity-cli/muse-credential`。沒有登入時，它會先走 `login`（有視窗），登入完成後再寫。macOS 與 Linux 檔案權限是 `600`，目錄是 `700`。它不會把 token 印出來。還沒登入、或視窗還在等你核准時，結束碼是 2，不會假裝已經寫入。登入工作階段失效（401／403）也是 2，訊息會寫「已失效」而不是「尚未登入」；地區限制、瀏覽器打不開、設定檔忙碌保留各自的 state。

```bash
muse-web-cli credential
```

範例（token 是假的）：

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

`auth.type` 也可以是 `header`，那時用 `header_name`。上面這種 `endpoints` 檔是給你自己架的 REST 服務用的。Muse gateway 的檔案由 `muse-web-cli credential` 寫入，裡面是 `vm_id` 而不是 `endpoints`。不要手動填，也不要從瀏覽器複製 token。

檔案不存在，或沒有 `vm_id` 而且這個指令沒有 endpoint：結束碼 4。401／403 是 `session_expired`（結束碼 2）。Muse gateway：在 Chrome 重新登入後再跑 `muse-web-cli credential`。你自己的 REST 服務：換掉 `auth.token`。其它 4xx 與 5xx 是 `ui_changed`（結束碼 3）。伺服器自己回的 `error`、`hint` 會先清掉 token、Bearer、JWT 這類字串再印出。逾時是 `timeout`（結束碼 3），`send` 不會再送一次。`send --wait` 若回應沒有 `reply`，只會再讀 `messages`，不會重送。gateway 的 `send --wait` 等到同一條 Noise 串流讀完才讀下一個請求；串流太久沒動靜時會繼續等到 `--timeout`。`chats --create`、`--rename`、`--delete`、`--switch` 只在 `--backend api` 送出請求。瀏覽器後端維持只讀列表。

`start` / `stop` / `login` / `selftest` 永遠管本地 Chrome，不走 api。

### 安全

記憶體只讀。不會點設定、連接器、邀請、附加檔案按鈕（`send --attach` 直接把檔案放進輸入框的檔案欄位）、新的副聊天室、記憶工具列、核可或拒絕。不讀 cookie，不開 CDP 的 Network / Storage，也不印出 token。`credential` 把 gateway token 只寫進 `~/.trinity-cli/muse-credential`（mode 600）。`--backend api` 用這份憑證呼叫 gateway。印出的 `error`、`hint` 會先清掉 `auth_token=`、`Bearer`、JWT 這類字串；訊息內文不改。

### 排解

- 埠 9333 沒有 Chrome：`browser_down`。用 `start --headless` 或 `--autostart`。
- 登入牆或人機驗證：`session_expired`。用有視窗的 `login`。Linux 伺服器沒有顯示器時，先在桌面工作階段登入，或用 `xvfb-run`。不要複製 cookie。
- 副聊天室開著：`messages` 讀的是目前這一則。先跑 `chats` 看 `kind` 與 `is_current`。它不會幫你切回主聊天室。
- Muse 改版後選擇器不見：`ui_changed`。`selftest` 的 `missing` 會列出缺的名稱。

### 隱私

- 瀏覽器後端只在本機驅動專用的 Chrome 設定檔 `~/.trinity-cli/muse-profile`。登入狀態留在那個設定檔裡，工具不讀 cookie。
- api 後端只連 Muse gateway，用 `~/.trinity-cli/muse-credential` 裡的 token。這個檔等於你的登入，不要分享或提交。
- 沒有遙測。除了設定檔、憑證檔，以及 `~/.trinity-cli` 裡的 Chrome 狀態和目前聊天室的小檔案，不在磁碟上存任何東西，也不存訊息。
- 文字輸出和 `--json` 有訊息內容和聊天室資訊。貼到 issue 前先刪掉。
- `uv tool uninstall` 不會刪設定檔和憑證檔。不再使用時，先 `muse-web-cli stop`，再自己刪掉 `~/.trinity-cli/muse-profile` 和 `~/.trinity-cli/muse-credential`。

### 平台

| 系統 | Python | 驗證方式 |
| --- | --- | --- |
| Linux | 3.12 | GitLab CI：離線單元測試 |
| Windows | 3.12 | GitLab CI：同一套測試，改到程式、測試或打包設定時自動跑 |
| macOS | 3.11、3.12、3.13 | 維護者本機：同一套測試，加上照這份 README 從 tag 安裝、用新的 Chrome 設定檔跑到登入牆（`session_expired`）的首次使用檢查 |

測試不連 Muse，也不開真的 Chrome。Linux 和 Windows 上真的 Chrome 只靠單元測試涵蓋，沒有實機檢查。

### 參與開發

見 [CONTRIBUTING.md](CONTRIBUTING.md)。安全問題照 [SECURITY.md](SECURITY.md) 回報，不要開公開 issue。

### 和 trinity-cli 一起用

座位不要依後端分支。建議 `--json --autostart`。專案：<https://gitlab.com/aa22396584/trinity-cli>

### 相關專案

- trinity-cli — 一個 CLI 管三個常駐代理（Your dot、Grok Bot、Muse）：<https://gitlab.com/aa22396584/trinity-cli>
- chatgpt-dot-cli — ChatGPT Your dot：<https://gitlab.com/aa22396584/chatgpt-dot-cli>
- grok-bot-cli（fork，`gbot`）— Grok Bot：<https://gitlab.com/aa22396584/grok-bot-cli>
- muse-web-cli — 透過網頁操作 Meta Muse（這個 repo）：<https://gitlab.com/aa22396584/muse-web-cli>

CI 預設使用 GitLab.com 的 runner。維護者可設定 CI/CD 變數 `LINUX_RUNNER_TAG` 與 `WINDOWS_RUNNER_TAG`，把 job 指到自己的 runner。

MIT，見 [LICENSE](LICENSE)。Copyright (c) 2026 ImL1s。本機測試：`uv run --group dev pytest`。

## English

### What it is

`muse-web-cli` drives the [Muse](https://muse.ai) web app you are already logged into. It is not a second Muse. The default is the browser backend: it drives the page through a dedicated Chrome profile and does not read cookies; Chrome reads the profile.

Only `credential` stores a token: it gets the gateway token from the logged-in page and writes it only into `~/.trinity-cli/muse-credential` (mode 600). It never prints it. `--backend api` uses that file to call the Muse gateway. Skip it if you do not use the api backend.

The command is `muse-web-cli`. The name `muse` belongs to Meta's Muse Code (`~/.local/bin/muse`).

You need Python 3.11+, uv or pipx, and Google Chrome or Chromium already installed. Playwright attaches to that Chrome. Do **not** run `playwright install`. Set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` when installing. Edge is not supported.

If the page says Muse is not available in your region, `status` returns `region_blocked` (exit 2). The tool does not bypass that.

Unofficial: this is a personal project, not affiliated with, endorsed by, or supported by Meta. The browser backend drives the web app you logged into yourself; the api backend calls the undocumented Muse gateway. Either can break at any time. Automated use may break Meta's terms or get the account limited; any risk is yours.

Supported systems: see [Platforms](#platforms).

### Install

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
- `messages --limit N` — oldest to newest. Default 20, minimum 1, values above 100 are capped at 100. Off-screen rows are virtualized. `--session ID` works only with `--backend api`. `muse-web-cli messages --limit 20`
- `send TEXT` — insertText and Enter, once. Put `--` before text that starts with `-`. `--wait` defaults off. `--timeout` defaults to 120 and must be > 0. A timeout never resends. `--wait` accepts only a reply that appears after the pre-send snapshot, in long chats too. `--session ID` works only with `--backend api`; the browser backend refuses it with exit 2 and sends nothing. `muse-web-cli send --wait --timeout 120 -- "text"`
- `send --attach FILE` (repeatable) — uploads through the Muse window and sends once; a missing or non-regular file exits 2 and sends nothing. `--attach-sha256 HEX` (repeatable, in `--attach` order): each file is read once and Muse gets exactly the hashed bytes (handed to the browser directly up to 50 MB, above that through a private temporary copy); a mismatch exits 2 and nothing is uploaded or sent. With `--session ID` it opens that side chat (`muse.ai/thread/<ID>`) and returns to the main chat afterwards; with an `--backend api` credential the reply is read through the api. If a file does not attach, no message is sent and the attached files are removed from the composer (Muse may already have stored the upload). If the page does not show that side chat (`muse.ai/thread/<ID>`), nothing is sent. If the window cannot go back to the main chat afterwards, the send is still reported as sent, with a `warning`. `muse-web-cli --backend api send --session ID --attach bundle.zip --wait -- "unzip …"`
- `pending` — read approvals. It does not approve or reject. `muse-web-cli pending`
- `upcoming` — read the upcoming tab. It does not click a row. `muse-web-cli upcoming`
- `activity` — read the activity tab. It does not click a row. `muse-web-cli activity`
- `memory` — read MEMORY.md `innerText`. It does not focus or type. `muse-web-cli memory`
- `chats` — list the main chat and any side chats already showing in the sidebar. A closed sidebar is not clicked; `state` is `ui_changed` and the hint is「請在 Muse 打開側欄後重試」. It does not click "新副聊天室" / new side chat, and it does not open a chat. On the new shell the main `title` may be null. `muse-web-cli chats`
- `chats --create [--title T]`, `--rename ID --title T`, `--delete ID`, `--switch ID|main` — `--backend api` only. `ID` is the `session_id` that `chats` lists; all four use the same ids. `--create` makes the new chat the switched one; `--json` has its id in `created`. `--delete` refuses the main chat; `--rename` and `--delete` refuse an id that was not listed and send nothing. `muse-web-cli --backend api chats --switch main`
- `credential` — get the gateway token from the logged-in page and write it only into `~/.trinity-cli/muse-credential` (mode 600). It never prints it. Runs `login` first when the session is missing. `muse-web-cli credential`
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
- `chats`: `backend` `state` `count` `chats` `error` `hint`. Each chat is `title` `is_current` `kind` (`main` or `side`), plus `session_id` on `--backend api`. With no side chats, `count` is the main chat only. On the new shell `title` may be null
- `credential`: `backend` `state` `action` `wrote` `logged_in` `fields` `error` `hint`. `fields` only says whether each field has a value (`true`/`false`); the token itself is never in the output
- `login` / `start` / `stop`: `backend` `state` `action` `port` `headless` `tracked` `logged_in` `error` `hint`
- `selftest`: the `status` keys plus `present`

Browser backend: `messages` and `send` act on the chat that is already open. If a side chat is current, that is what you read. `chats` lists them and does not switch. `--backend api`: `--session ID` picks a chat; without it, the chat saved by `chats --switch` (or `--create`) is used; `--switch main` goes back to the main chat.

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
| 4 | `unsupported` | `--backend api` only: the credential file is missing, or it has no `vm_id` and no endpoint for that command. A state sent by a server never becomes 4. A missing token, bad JSON, or a wrong field is 2 or 3. Not an unimplemented command |

### Backends

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

### Safety

Memory is read-only. The tool never clicks settings, connectors, invites, the attach button (`send --attach` puts files straight into the composer's file input), a new side chat, the memory toolbar, or approve/reject. It does not read cookies, enable the CDP Network or Storage domains, or print a token. `credential` writes the gateway token only into `~/.trinity-cli/muse-credential` (mode 600). `--backend api` calls the gateway with that file. Printed `error` and `hint` text is scrubbed of `auth_token=`, `Bearer`, and JWT strings; message bodies are left as they are.

### Troubleshooting

- Nothing is listening on port 9333: `browser_down`. Use `start --headless` or `--autostart`.
- Login wall or bot check: `session_expired`. Use headed `login`. On a Linux server with no display, log in on a desktop session or use `xvfb-run`. Do not copy cookies.
- A side chat is open: `messages` reads the current chat. Run `chats` and look at `kind` and `is_current`. It does not switch back to the main chat.
- Muse shipped a new UI and selectors are gone: `ui_changed`. `selftest` lists the missing names in `missing`.

### Privacy

- The browser backend drives a dedicated Chrome profile, `~/.trinity-cli/muse-profile`, on your machine only. The login stays in that profile; the tool does not read cookies.
- The api backend talks only to the Muse gateway, with the token in `~/.trinity-cli/muse-credential`. That file is as good as your login; do not share or commit it.
- There is no telemetry. Apart from the profile, the credential file, and small Chrome-state and current-chat files in `~/.trinity-cli`, nothing is written to disk, and no messages are stored.
- Text output and `--json` contain message text and chat details. Remove them before pasting into an issue.
- `uv tool uninstall` leaves the profile and the credential file. When you are done, run `muse-web-cli stop`, then delete `~/.trinity-cli/muse-profile` and `~/.trinity-cli/muse-credential` yourself.

### Platforms

| OS | Python | How it was checked |
| --- | --- | --- |
| Linux | 3.12 | GitLab CI: the offline unit suite |
| Windows | 3.12 | GitLab CI: the same suite, run automatically when code, tests, or packaging change |
| macOS | 3.11, 3.12, 3.13 | Maintainer machine: the same suite, plus a first-run check that installs from the tag as this README says and reaches the login wall (`session_expired`) with a fresh Chrome profile |

The tests do not contact Muse or start a real Chrome. On Linux and Windows, real Chrome is covered by unit tests only, with no live check.

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Report security problems as described in [SECURITY.md](SECURITY.md), not in a public issue.

### Use with trinity-cli

Do not branch on backend. Pass `--json --autostart`. Project: <https://gitlab.com/aa22396584/trinity-cli>

### Related projects

- trinity-cli — one CLI over three always-on agents (Your dot, Grok Bot, Muse): <https://gitlab.com/aa22396584/trinity-cli>
- chatgpt-dot-cli — ChatGPT Your dot: <https://gitlab.com/aa22396584/chatgpt-dot-cli>
- grok-bot-cli (fork, `gbot`) — Grok Bot: <https://gitlab.com/aa22396584/grok-bot-cli>
- muse-web-cli — Meta Muse via the web (this repo): <https://gitlab.com/aa22396584/muse-web-cli>

CI uses GitLab.com runners by default. Maintainers can point jobs at their own runners by setting the CI/CD variables `LINUX_RUNNER_TAG` and `WINDOWS_RUNNER_TAG`.

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 ImL1s. Local tests: `uv run --group dev pytest`.
