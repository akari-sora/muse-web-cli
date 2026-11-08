"""Every Muse selector and UI phrase lives here.

zh-TW aria-labels were read off a logged-in muse.ai page. English labels are
best-effort equivalents for the same controls; that page did not show them.
data-testid and data-pel-click do not depend on the locale.

Nothing in this module is a credential, cookie, or endpoint.
"""

from __future__ import annotations


def labeled(element: str, labels: tuple[str, ...]) -> str:
    return ", ".join(f'{element}[aria-label="{label}"]' for label in labels)


# --- chat surface (zh-TW verified) -----------------------------------------

LOG = labeled('[role="log"]', ("聊天訊息", "Chat messages", "Messages"))
COMPOSER = labeled("textarea", ("傳送訊息", "Send a message", "Send message"))
# Present only while the composer has text. Enter sends; this is not clicked.
SEND_BUTTON = '[data-pel-click="chat_send_message"]'

MESSAGE_ITEM = "[data-message-item]"
MESSAGE = "[data-message-item][data-message-role]"
TYPING = '[data-testid="hatch-chat-typing-indicator"]'
SURROGATE = "[data-message-accessibility-surrogate]"
ASSISTANT_BODY = "[data-hatch-assistant-message-body]"
STREAMING_ATTR = "data-hatch-markdown-streaming"
PRESENTATION_ATTR = "data-message-has-presentation"
ROLE_ATTR = "data-message-role"
# Copy-reply shows up when a normal assistant bubble has finished. Never click it.
COPY_REPLY = (
    '[data-pel-click="chat_copy_response"], '
    'button[aria-label="複製回覆"], '
    'button[aria-label="Copy reply"], '
    'button[aria-label="Copy response"]'
)

# The dock chat control is the switcher on the new shell. The older dropdown
# trigger is kept behind it so a page that still has that button still matches.
# Listed order is the priority. chats does not click either control.
SWITCHER_TESTIDS = (
    "hatch-nav-chat",
    "hatch-chat-switcher-trigger",
)


def switcher_selectors() -> tuple[str, ...]:
    return tuple(f'[data-testid="{testid}"]' for testid in SWITCHER_TESTIDS)


def switcher_in_markup(markup: str) -> str | None:
    """First priority switcher testid that this HTML fragment actually contains."""
    for testid in SWITCHER_TESTIDS:
        if f'data-testid="{testid}"' in markup:
            return testid
    return None


SWITCHER = ", ".join(switcher_selectors())
DOCK = '[data-testid="hatch-dock-rail"]'
SIDE_CHATS = '[data-testid="hatch-side-chats-panel-shell"]'
SIDE_CHATS_CONTENT = '[data-testid="hatch-side-chats-panel-content"]'
# Labels on the switcher and the empty side-chat state. They are not chat titles.
CHAT_CHROME = ("聊天室", "Chat", "Chats")
NEW_SIDE_CHAT = ("新副聊天室", "New side chat")
EMPTY_SIDE_CHAT = ("開始副聊天室", "Start a side chat")
# A closed sidebar is not clicked open. chats uses the existing error and hint keys.
SIDEBAR_CLOSED_ERROR = "讀不到側欄裡的對話清單"
SIDEBAR_CLOSED_HINT = "請在 Muse 打開側欄後重試"

# --- right status panel -----------------------------------------------------

PANEL = "[data-hatch-status-panel-card]"
TAB_PENDING = labeled("button", ("核可工具", "Approvals"))
TAB_UPCOMING = labeled("button", ("近期", "Upcoming"))
TAB_ACTIVITY = labeled("button", ("動態", "Activity"))
TAB_IDENTITY = labeled("button", ("身分", "Identity"))
PANEL_CLOSE = '[data-testid="hatch-status-panel-close"]'

# Reopens the panel after the file editor collapses it. The <img> twin is not a button.
AVATAR_BUTTON = '[role="button"][data-hatch-avatar-interaction][aria-label="Muse"]'

MEMORY_FILE = '[data-pel-click="status_memory_file_click"]'
EDITOR = '[data-testid="hatch-file-editor"]'
EDITOR_BODY = (
    '[data-testid="hatch-file-editor"] [data-lexical-editor], '
    '[data-testid="hatch-file-editor"] [contenteditable="true"]'
)
EDITOR_CLOSE = '[data-testid="hatch-file-editor-close"]'

# Utility classes. Scoped to the status card. Date chips in the log use the time class too.
ITEM_BUTTON = "button.flex.w-full.items-start"
ITEM_TITLE = ".text-subheadline-medium"
ITEM_DETAIL = ".text-footnote"
ITEM_TIME = ".text-caption-1"

PASSWORD = 'input[type="password"]'

TAB_BY_LABEL = {
    "核可工具": TAB_PENDING,
    "Approvals": TAB_PENDING,
    "近期": TAB_UPCOMING,
    "Upcoming": TAB_UPCOMING,
    "動態": TAB_ACTIVITY,
    "Activity": TAB_ACTIVITY,
    "身分": TAB_IDENTITY,
    "Identity": TAB_IDENTITY,
}

# Required on a logged-in chat. selftest fails with ui_changed if one is missing.
KEY_SELECTORS = {
    "log": LOG,
    "composer": COMPOSER,
    "switcher": SWITCHER,
    "avatar": AVATAR_BUTTON,
}

# Required only when the status panel is already open (selftest does not open it).
PANEL_TAB_SELECTORS = {
    "pending_tab": TAB_PENDING,
    "upcoming_tab": TAB_UPCOMING,
    "activity_tab": TAB_ACTIVITY,
    "identity_tab": TAB_IDENTITY,
}

# Reported, never required: they are absent unless a tab, a draft, or a reply is open.
OPTIONAL_SELECTORS = {
    "panel": PANEL,
    "memory_file": MEMORY_FILE,
    "editor": EDITOR,
    "send_button": SEND_BUTTON,
    "typing": TYPING,
}

# Clicks are an allowlist (see nav.ALLOWED_CLICKS). These stay listed so a
# reviewer can see the controls the tool must not operate. chats does not click
# the switcher, a sidebar row, or the new-side-chat control.
FORBIDDEN_TESTIDS = (
    "hatch-dock-more",
    "hatch-invite-friends-button",
    "hatch-file-editor-maximize",
    "hatch-file-editor-more-actions",
)
FORBIDDEN_PELS = (
    "connector_",
    "invite_friends_open_click",
    "chat_tap_attachment",
    "chat_threads_open_click",
    "settings_menu_open_click",
    "status_avatar_edit_menu_open",
    "status_edit_identity",
    "status_soul_file_click",
    "markdown_toolbar_format_click",
    "artifact_open_split_click",
    "artifact_options_open_click",
    "mobile_app_upsell_click",
    "chat_copy_response",
    "chat_reply_message",
    "chat_message_overflow_open",
)

# Gate text only (title and headings outside the chat log). Not message bodies.
REGION_PHRASES = (
    "not available in your region",
    "not available in your country",
    "isn't available in your region",
    "is not available in your region",
    "此地區無法使用",
    "你所在的地區無法使用",
    "目前無法在你的國家",
)
# The signed-out landing page stays on muse.ai/ and has no password field.
LOGIN_PHRASES = (
    "log in or create an account",
    "log in or sign up",
    "sign in or create an account",
    "登入或建立帳號",
    "登入或註冊",
    "登录或创建账号",
    "登录或注册",
)
# Headless bot walls are reported as session_expired; the hint is to log in headed.
BOT_PHRASES = (
    "confirm you're human",
    "confirm you are human",
    "security check",
    "captcha",
    "驗證你是真人",
    "安全性檢查",
    "請確認你是真人",
)

MEMORY_SECTIONS = ("Facts", "Preferences", "Commitments")

MUSE_URL = "https://muse.ai/"
# A side chat has its own URL: MUSE_URL + "thread/" + session id.
THREAD_URL = MUSE_URL + "thread/{}"
# Files go in through the composer's hidden file input (set_input_files); the attach button
# (chat_tap_attachment) is never clicked. Each attached file shows a remove button.
FILE_INPUT = 'input[type="file"]'
ATTACHMENT = '[data-pel-click="chat_remove_attachment_click"]'
LOGIN_HINT = "muse-web-cli login"
API_UNAVAILABLE = (
    "找不到 ~/.trinity-cli/muse-credential。"
    "請執行 muse-web-cli credential，它會寫好這個檔（mode 600）。"
)
API_HINT = (
    "執行 muse-web-cli credential，或 trinity-cli login muse。"
    "沒有登入會先開啟登入視窗。這個工具不會印出 token。"
)
CREDENTIAL_HINT = "chmod 600 ~/.trinity-cli/muse-credential"
CREDENTIAL_HINT_WINDOWS = "put ~/.trinity-cli/muse-credential in your home directory"
START_HINT = "muse-web-cli start --headless"
