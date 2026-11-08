# muse-web-cli

[English](README.md) | 繁體中文

在終端機操作你已經登入的 Muse 網頁；加上 `--json` 時，每個指令印一個 JSON 物件。

> 正本和 issue 在 <https://gitlab.com/aa22396584/muse-web-cli>。trinity-cli 系列的一部分。

[![pipeline](https://gitlab.com/aa22396584/muse-web-cli/badges/main/pipeline.svg)](https://gitlab.com/aa22396584/muse-web-cli/-/commits/main)
[![release](https://gitlab.com/aa22396584/muse-web-cli/-/badges/release.svg)](https://gitlab.com/aa22396584/muse-web-cli/-/releases)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 功能

- 在終端機操作**你自己已經登入**的 [Muse](https://muse.ai) 網頁。它不是第二個 Muse。
- 預設是瀏覽器後端：用一個專用的 Chrome 設定檔驅動頁面，不讀 cookie；Chrome 自己讀設定檔。
- 可選的 api 後端（`--backend api`）走 Muse gateway。會存 token 的只有 `credential`：它從已登入的頁面取得 gateway token，只寫進 `~/.trinity-cli/muse-credential`（mode 600），不印出來。不用 api 就不必執行它。
- JSON 形狀和結束碼不因後端而改變。
- 指令名稱是 `muse-web-cli`。`muse` 已經被 Meta 的 Muse Code 用掉了（`~/.local/bin/muse`），不要覆蓋它。

需要 Python 3.11 以上、`uv` 或 pipx、以及已安裝的 Google Chrome（或 Chromium）。Playwright 只拿來接上你自己的 Chrome。**不要**執行 `playwright install`。安裝時設定 `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`。不支援 Edge。若頁面顯示這個地區無法使用 Muse，`status` 會是 `region_blocked`（結束碼 2），這個工具不會繞過地區限制。支援的系統見[平台](docs/reference.zh-TW.md#平台)。

## 安裝

v0.1.7。裝好後執行 `muse-web-cli --version`，應印出 `muse-web-cli 0.1.7`。找不到指令時，把 `~/.local/bin` 加進 PATH。

macOS 與 Linux：

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.7"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pipx install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.7"
```

Windows（PowerShell）：

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"
uv tool install "git+https://gitlab.com/aa22396584/muse-web-cli.git@v0.1.7"
muse-web-cli --version
```

升級時把標籤改成要裝的版本，再加 `--force` 裝一次。移除：`uv tool uninstall muse-web-cli` 或 `pipx uninstall muse-web-cli`。在這個 repo 裡開發可以用 `uv tool install --editable .`。

## 設定

```bash
muse-web-cli login
muse-web-cli selftest
muse-web-cli status
muse-web-cli start --headless
```

`login` 開有視窗的 Chrome，工具不會輸入帳號密碼。Linux 沒有顯示器時，在桌面工作階段登入，或用 `xvfb-run muse-web-cli login`。`selftest` 只檢查選擇器，`status` 看工作階段。之後可以無頭使用。設定檔、除錯埠、設定檔案與環境變數見[第一次設定](docs/reference.zh-TW.md#第一次設定)。

## 快速開始

```bash
muse-web-cli --json status
muse-web-cli --json messages --limit 2
muse-web-cli --json chats
muse-web-cli --json send --wait --timeout 120 -- "文字"
muse-web-cli --json pending
```

每個指令印出什麼見[輸出範例](docs/reference.zh-TW.md#輸出範例)。

## 指令

| 指令 | 用途 |
| --- | --- |
| `status` | 工作階段、待核可數量、最新助理訊息是不是卡片 |
| `messages` | 最近訊息，由舊到新（`--limit` 預設 20，超過 100 截成 100） |
| `send` | 只送一次（`--wait`、`--timeout`、`--attach FILE`、`--attach-sha256 HEX`）；逾時不會重送 |
| `pending` | 只讀核可項目，不點核可或拒絕 |
| `upcoming` | 只讀排定任務（近期分頁，或動態分頁裡的排定任務那一組），不點列 |
| `activity` | 只讀動態，不點列 |
| `memory` | 只讀 MEMORY.md 的 `innerText`，不聚焦、不打字 |
| `chats` | 列出主聊天室與副聊天室；`--create`、`--rename`、`--delete`、`--switch` 只在 `--backend api` |
| `credential` | 把 gateway token 寫進 `~/.trinity-cli/muse-credential`（mode 600） |
| `login` | 開有視窗的 Chrome，等你登入 |
| `start` | 啟動專用 Chrome（預設 `--headless`，或 `--headed`），或接上已經在跑的那一個 |
| `stop` | 只停止這個工具自己啟動的進程 |
| `selftest` | 檢查選擇器在不在，不點任何東西 |

全域旗標可放在指令前或後：`--json`、`--port`（預設 9333）、`--backend`（`browser` 或 `api`）、`--autostart`、`--chrome PATH`、`--version`。每個旗標與 JSON 鍵見[指令參考](docs/reference.zh-TW.md#指令參考)。後端怎麼選、憑證檔格式見[後端](docs/reference.zh-TW.md#後端)。

## 安全與隱私

- 記憶體只讀。不會點設定、連接器、邀請、附加檔案按鈕（`send --attach` 直接把檔案放進輸入框的檔案欄位）、新的副聊天室、記憶工具列、核可或拒絕。
- 不讀 cookie，不開 CDP 的 Network / Storage，也不印出 token。印出的 `error`、`hint` 會先清掉 `auth_token=`、`Bearer`、JWT 這類字串；訊息內文不改。
- 瀏覽器後端只在本機驅動專用的 Chrome 設定檔 `~/.trinity-cli/muse-profile`，登入狀態留在那個設定檔裡。api 後端只連 Muse gateway，用 `~/.trinity-cli/muse-credential` 裡的 token。這個檔等於你的登入，不要分享或提交。
- 沒有遙測。除了設定檔、憑證檔，以及 `~/.trinity-cli` 裡的 Chrome 狀態和目前聊天室的小檔案，不在磁碟上存任何東西，也不存訊息。
- 文字輸出和 `--json` 有訊息內容和聊天室資訊。貼到 issue 前先刪掉。
- `uv tool uninstall` 不會刪設定檔和憑證檔。不再使用時，先 `muse-web-cli stop`，再自己刪掉 `~/.trinity-cli/muse-profile` 和 `~/.trinity-cli/muse-credential`。

## 給 agent 用

- 建議 `--json --autostart`，座位不要依後端分支。trinity-cli 就是這樣用：<https://gitlab.com/aa22396584/trinity-cli>
- 結束碼 0 是 `ok`；2 是設定問題（`browser_down`、`session_expired`、`region_blocked`、`profile_busy`、`credential_permissions`）；3 是頁面問題（`ui_changed`、`timeout`）；4 是 `unsupported`（只在 `--backend api`）。`hint` 寫下一步要跑的指令。`timeout` 的 `hint` 是 `nothing was sent again`。見[結束碼](docs/reference.zh-TW.md#結束碼)。
- `send` 只送一次。文字若以 `-` 開頭，前面加 `--`。
- 附帶的 skill 是 `skills/muse-web-cli/SKILL.md`。

## 文件

- [docs/reference.zh-TW.md](docs/reference.zh-TW.md)：第一次設定、輸出範例、每個指令與 JSON 鍵、結束碼、後端與憑證檔、排解、平台、測試與 CI。
- [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.zh-TW.md](SECURITY.zh-TW.md)（安全問題照這份回報，不要開公開 issue）、[CHANGELOG.md](CHANGELOG.md)。

## 相關專案

- trinity-cli — 一個 CLI 管三個常駐代理（Your dot、Grok Bot、Muse）：<https://gitlab.com/aa22396584/trinity-cli>
- chatgpt-dot-cli — ChatGPT Your dot：<https://gitlab.com/aa22396584/chatgpt-dot-cli>
- grok-bot-cli（fork，`gbot`）— Grok Bot：<https://gitlab.com/aa22396584/grok-bot-cli>
- muse-web-cli — 透過網頁操作 Meta Muse（這個 repo）：<https://gitlab.com/aa22396584/muse-web-cli>

## 授權與聲明

MIT，見 [LICENSE](LICENSE)。Copyright (c) 2026 ImL1s。

非官方：這是個人專案，跟 Meta 沒有關係，也沒有得到 Meta 的背書或支援。瀏覽器後端驅動你自己登入的網頁；api 後端呼叫沒有公開文件的 Muse gateway。兩者都可能隨時失效。自動化使用可能違反 Meta 的使用條款，或讓帳號受到限制，風險自負。
