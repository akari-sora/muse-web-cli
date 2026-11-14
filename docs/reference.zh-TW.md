# muse-web-cli 參考

[English](reference.md) | 繁體中文

安裝、快速開始和指令清單在 [README](../README.zh-TW.md)。這頁是細節。

- [第一次設定](#第一次設定)
- [輸出範例](#輸出範例)
- [指令參考](#指令參考)
- [結束碼](#結束碼)
- [後端](#後端)
- [排解](#排解)
- [平台](#平台)
- [測試與 CI](#測試與-ci)

## 第一次設定

設定檔固定是 `~/.trinity-cli/muse-profile`（Windows 也是你的使用者主目錄底下的 `.trinity-cli`）。同一個設定檔同時只能有一個 Chrome。除錯埠預設 `127.0.0.1:9333`。

1. 有視窗登入。工具不會輸入帳號密碼。Linux 沒有顯示器時，在桌面工作階段登入，或用 `xvfb-run muse-web-cli login`。沒有顯示器時不會關掉已經在跑的 headless Chrome。不要複製 cookie。`login` 確認已登入後，會關掉它自己開的有視窗 Chrome，用同一個設定檔改以無頭重開（有視窗的 Chrome 每次被驅動都會搶鍵盤焦點）。要保留視窗請加 `--keep-window`；之後的指令若接上有視窗、由本工具啟動的 Chrome，會印出警告（`--json` 有 `warning` 欄位）和切換指令。

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

環境變數：`MUSE_WEB_CDP_PORT`、`MUSE_WEB_HEADLESS`、`MUSE_WEB_AUTOSTART`、`MUSE_WEB_BACKEND`、`MUSE_WEB_CHROME`、`MUSE_WEB_KEEP_WINDOW`。優先順序是指令列、環境變數、設定檔、預設。

## 輸出範例

快速開始那幾個指令加上 `--json` 時印出的內容。

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

## 指令參考

全域旗標可放在指令前或後：

| 旗標 | 預設 | 範圍 |
| --- | --- | --- |
| `--json` | 關 | 印出一個 JSON 物件 |
| `--port` | 9333 | 1–65535 |
| `--backend` | `browser` | `browser` 或 `api` |
| `--autostart` | 關 | 埠沒人聽時啟動無頭 Chrome |
| `--keep-window` | 關 | `login` 與 `credential` 保留有視窗的 Chrome，不改以無頭重開（也可用 `MUSE_WEB_KEEP_WINDOW`、設定檔 `keep_window`） |
| `--chrome PATH` | 依作業系統尋找 | 覆寫 `MUSE_WEB_CHROME` |
| `--version` |  | 印出版本 |

- `status` — 工作階段、待核可數量、最新助理訊息是不是卡片。`muse-web-cli status`
- `messages --limit N` — 由舊到新。預設 20，最小 1，超過 100 會截成 100。離畫面外的列是虛擬化的。`--session ID` 只在 `--backend api` 有效。`muse-web-cli messages --limit 20`
- `send TEXT` — `insertText` 加 Enter，只送一次。文字若以 `-` 開頭，前面加 `--`。`--wait` 預設關。`--timeout` 預設 120，必須大於 0。逾時不會重送。`--wait` 只接受送出前快照之後才出現的回覆，聊天很長也一樣。`--session ID` 只在 `--backend api` 有效；瀏覽器後端給了會以結束碼 2 拒絕，不會送出。`muse-web-cli send --wait --timeout 120 -- "文字"`
- `send --attach FILE`（可重複）— 透過 Muse 視窗上傳檔案再送出，只送一次；檔案不存在或不是一般檔案時結束碼 2，什麼都不送。`--attach-sha256 HEX`（可重複，依 `--attach` 的順序）：檔案只讀一次，Muse 拿到的就是算過雜湊的那份位元組（50 MB 內直接交給瀏覽器，更大的先寫成只有自己能讀的暫存副本）；不符就結束碼 2，什麼都不上傳、不送。加 `--session ID` 時先打開那則副聊天室（`muse.ai/thread/<ID>`），送完回主聊天室；有 `--backend api` 憑證時用 api 等回覆。檔案沒附上就不送訊息，並從輸入框移除已附上的檔案（Muse 可能已經收下上傳的檔案）。頁面沒有顯示那則副聊天室（`muse.ai/thread/<ID>`）就什麼都不送。送完回不了主聊天室時仍回報已送出，並在 `warning` 註明。`muse-web-cli --backend api send --session ID --attach bundle.zip --wait -- "解壓縮…"`
- `pending` — 只讀核可項目，不點核可或拒絕。`muse-web-cli pending`
- `upcoming` — 只讀排定任務，不點列。Muse 拿掉了近期分頁；頁面沒有近期分頁時，`upcoming` 只讀動態分頁裡的排定任務那一組（標題像「2項排定任務」或 "2 scheduled tasks"），不含下面按日期分的那幾組。沒有那一組時 `count` 是 0。標題寫的數量比面板列出的多時，`complete` 是 `false`，hint 指向 `--backend api upcoming`；不會點「查看所有排定任務」。`muse-web-cli upcoming`
- `activity` — 只讀動態，不點列。`muse-web-cli activity`
- `memory` — 只讀 MEMORY.md 的 `innerText`，不聚焦、不打字。`muse-web-cli memory`
- `chats` — 列出已經打開的側欄裡的主聊天室與副聊天室。側欄關著時不點開關，`state` 是 `ui_changed`，hint 是「請在 Muse 打開側欄後重試」。不點「新副聊天室」，也不會打開任何一則。新版介面的主標題可能是 null。`muse-web-cli chats`
- `chats --create [--title T]`、`--rename ID --title T`、`--delete ID`、`--switch ID|main` — 只在 `--backend api`。`ID` 是 `chats` 列出的 `session_id`，四個動作用同一套 id。`--create` 會把新聊天室設成目前這一則，`--json` 的 `created` 是它的 id。`--delete` 不接受主聊天室；`--rename`、`--delete` 碰到沒列出的 id 會拒絕，不送出。`muse-web-cli --backend api chats --switch main`
- `credential` — 從已登入的頁面取得 gateway token，只寫進 `~/.trinity-cli/muse-credential`（mode 600），不印出。沒登入會先走 `login`。`muse-web-cli credential`
- `login` — 登入成功後會關掉那個視窗，並以無頭重開同一個設定檔（`headless: true`、`action: relaunched_headless`）；無頭頁面若是登出狀態，`state` 為 `session_expired`。`--keep-window` 略過重開。開有視窗的 Chrome，等你登入。`muse-web-cli login`
- `start` — 啟動專用 Chrome，或接上已經在跑的那一個。`--headless` 是預設（`--headless=new`）。`--headed` 顯示視窗。兩個旗標不能一起用。`muse-web-cli start --headless`
- `stop` — 只停止這個工具自己啟動的進程。`muse-web-cli stop`
- `selftest` — 檢查選擇器在不在，不點任何東西。切換鈕必須在。`upcoming_tab` 會列在 `present`，但不是必要的。`muse-web-cli selftest`

`--json` 的鍵：

- `status`：`backend` `state` `pending` `latest_assistant_is_card` `headless` `error` `hint` `missing`
- `messages`：`backend` `state` `name` `lines` `messages` `error` `hint`。每則是 `role` `text` `presentation`
- `send`：`backend` `state` `attempted` `sent` `text` `reply` `presentation` `elapsed_ms` `error` `hint`
- `pending`：`backend` `state` `count` `items` `error` `hint`。item 是 `title` `detail` `time`
- `upcoming`：`backend` `state` `count` `groups` `error` `hint`；動態分頁列出的排定任務比標題寫的少時，另有 `complete: false`。group 是 `title` 與 `items`（`name` `time`）
- `activity`：同樣有 `groups`，item 是 `title` `detail` `time`
- `memory`：`backend` `state` `chars` `sections` `text` `error` `hint`
- `chats`：`backend` `state` `count` `chats` `error` `hint`。每一則是 `title` `is_current` `kind`（`main` 或 `side`），`--backend api` 另有 `session_id`。沒有副聊天室時 `count` 是主聊天室那一則。新版介面的 `title` 可能是 null
- `credential`：`backend` `state` `action` `wrote` `logged_in` `fields` `error` `hint`。`fields` 只寫每個欄位有沒有值（`true`／`false`），沒有 token 本身
- `login` / `start` / `stop`：`backend` `state` `action` `port` `headless` `tracked` `logged_in` `error` `hint`
- `selftest`：`status` 的鍵，再加上 `present`

瀏覽器後端：`messages` 與 `send` 作用在**目前已經打開**的那一則。若副聊天室是目前這一則，讀到的就是副聊天室。`chats` 只列出，不切換。`--backend api`：`--session ID` 指定一則；沒給就用 `chats --switch`（或 `--create`）記下的那一則；`--switch main` 回主聊天室。

## 結束碼

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

## 後端

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

## 排解

- 埠 9333 沒有 Chrome：`browser_down`。用 `start --headless` 或 `--autostart`。
- 登入牆或人機驗證：`session_expired`。用有視窗的 `login`。Linux 伺服器沒有顯示器時，先在桌面工作階段登入，或用 `xvfb-run`。不要複製 cookie。
- 副聊天室開著：`messages` 讀的是目前這一則。先跑 `chats` 看 `kind` 與 `is_current`。它不會幫你切回主聊天室。
- Muse 改版後選擇器不見：`ui_changed`。`selftest` 的 `missing` 會列出缺的名稱。

## 平台

| 系統 | Python | 驗證方式 |
| --- | --- | --- |
| Linux | 3.12 | GitLab CI：離線單元測試 |
| Windows | 3.12 | GitLab CI：同一套測試，改到程式、測試或打包設定時自動跑 |
| macOS | 3.11、3.12、3.13 | 維護者本機：同一套測試，加上照 README 從 tag 安裝、用新的 Chrome 設定檔跑到登入牆（`session_expired`）的首次使用檢查 |

測試不連 Muse，也不開真的 Chrome。Linux 和 Windows 上真的 Chrome 只靠單元測試涵蓋，沒有實機檢查。

## 測試與 CI

CI 預設使用 GitLab.com 的 runner。維護者可設定 CI/CD 變數 `LINUX_RUNNER_TAG` 與 `WINDOWS_RUNNER_TAG`，把 job 指到自己的 runner。
本機測試：`uv run --group dev pytest`。
