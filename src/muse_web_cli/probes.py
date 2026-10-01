"""Page scripts. They read DOM text only: no cookies, storage, or network."""

from __future__ import annotations

import json

from muse_web_cli import selectors as sel

_MAP = {
    "log": sel.LOG,
    "composer": sel.COMPOSER,
    "switcher": sel.SWITCHER,
    "sideContent": sel.SIDE_CHATS_CONTENT,
    "avatar": sel.AVATAR_BUTTON,
    "pending_tab": sel.TAB_PENDING,
    "upcoming_tab": sel.TAB_UPCOMING,
    "activity_tab": sel.TAB_ACTIVITY,
    "identity_tab": sel.TAB_IDENTITY,
    "panel": sel.PANEL,
    "memory_file": sel.MEMORY_FILE,
    "editor": sel.EDITOR,
    "send_button": sel.SEND_BUTTON,
    "typing": sel.TYPING,
    "password": sel.PASSWORD,
    "messageItem": sel.MESSAGE_ITEM,
    "surrogate": sel.SURROGATE,
    "body": sel.ASSISTANT_BODY,
    "copy": sel.COPY_REPLY,
    "streamingAttr": sel.STREAMING_ATTR,
    "item": sel.ITEM_BUTTON,
    "title": sel.ITEM_TITLE,
    "detail": sel.ITEM_DETAIL,
    "time": sel.ITEM_TIME,
    "editorBody": sel.EDITOR_BODY,
}


def _arg() -> str:
    return json.dumps(_MAP)


SNAPSHOT_JS = f"""
async () => {{
  const sel = {_arg()};
  const shown = (el) => {{
    if (!el) return false;
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }};
  const tri = (value) => {{
    if (value === "true") return true;
    if (value === "false") return false;
    return null;
  }};
  const log = document.querySelector(sel.log);
  if (log) {{
    log.scrollTop = log.scrollHeight;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }}
  const messages = [];
  for (const item of document.querySelectorAll(sel.messageItem)) {{
    if (item.getAttribute("data-testid") === "hatch-chat-typing-indicator") continue;
    if (item.querySelector(sel.typing)) continue;
    const role = item.getAttribute("data-message-role");
    if (role !== "user" && role !== "assistant") continue;
    const body = item.querySelector(sel.body);
    const surrogate = item.querySelector(sel.surrogate);
    let text = "";
    if (surrogate && (surrogate.textContent || "").trim()) text = surrogate.textContent.trim();
    else if (body && (body.textContent || "").trim()) text = body.textContent.trim();
    else {{
      const clone = item.cloneNode(true);
      clone.querySelectorAll("button, svg").forEach((node) => node.remove());
      text = (clone.textContent || "").replace(/\\s+/g, " ").trim();
    }}
    if (role === "user") text = text.replace(/^(?:用戶訊息[：:]|你[：:]|You:)\\s*/, "");
    const busyAttr = item.getAttribute("aria-busy") || (body && body.getAttribute("aria-busy"));
    messages.push({{
      role,
      text,
      presentation: item.hasAttribute("data-message-has-presentation"),
      busy: tri(busyAttr),
      streaming: tri(body && body.getAttribute(sel.streamingAttr)),
      hasActions: !!item.querySelector(sel.copy),
      typing: false,
    }});
  }}
  const present = {{}};
  for (const name of ["log","composer","switcher","avatar","pending_tab","upcoming_tab","activity_tab","identity_tab","panel","memory_file","editor","send_button","typing"]) {{
    present[name] = !!document.querySelector(sel[name]);
  }}
  const parts = [document.title || ""];
  for (const el of document.querySelectorAll("h1, h2, [role='alert'], [role='dialog']")) {{
    if (log && log.contains(el)) continue;
    const bit = (el.textContent || "").trim();
    if (bit) parts.push(bit.slice(0, 200));
  }}
  const panel = document.querySelector(sel.panel);
  return {{
    host: location.host,
    path: location.pathname,
    hasLog: !!log,
    hasComposer: !!document.querySelector(sel.composer),
    hasPassword: !!document.querySelector(sel.password),
    panelOpen: shown(panel),
    gateText: parts.join("\\n").slice(0, 2000),
    present,
    messages,
  }};
}}
"""

OBSERVER_JS = f"""
async (payload) => {{
  const sel = {_arg()};
  const sent = payload.text;
  const before = payload.beforeUserCount;
  const timeout = payload.timeoutMs;
  const wantReply = payload.wait;
  const norm = (value) => (value || "").replace(/\\s+/g, " ").trim();
  const tri = (value) => {{
    if (value === "true") return true;
    if (value === "false") return false;
    return null;
  }};
  const collect = () => {{
    if (log) log.scrollTop = log.scrollHeight;
    const messages = [];
    for (const item of document.querySelectorAll(sel.messageItem)) {{
      if (item.getAttribute("data-testid") === "hatch-chat-typing-indicator") continue;
      if (item.querySelector(sel.typing)) continue;
      const role = item.getAttribute("data-message-role");
      if (role !== "user" && role !== "assistant") continue;
      const body = item.querySelector(sel.body);
      const surrogate = item.querySelector(sel.surrogate);
      let text = "";
      if (surrogate && (surrogate.textContent || "").trim()) text = surrogate.textContent.trim();
      else if (body && (body.textContent || "").trim()) text = body.textContent.trim();
      else {{
        const clone = item.cloneNode(true);
        clone.querySelectorAll("button, svg").forEach((node) => node.remove());
        text = (clone.textContent || "").replace(/\\s+/g, " ").trim();
      }}
      if (role === "user") text = text.replace(/^(?:用戶訊息[：:]|你[：:]|You:)\\s*/, "");
      const busyAttr = item.getAttribute("aria-busy") || (body && body.getAttribute("aria-busy"));
      messages.push({{
        role,
        text,
        presentation: item.hasAttribute("data-message-has-presentation"),
        busy: tri(busyAttr),
        streaming: tri(body && body.getAttribute(sel.streamingAttr)),
        hasActions: !!item.querySelector(sel.copy),
        typing: false,
      }});
    }}
    return messages;
  }};
  const userCount = (messages) => messages.filter((item) => item.role === "user" && norm(item.text) === norm(sent)).length;
  const ready = (messages) => {{
    let index = -1;
    messages.forEach((item, i) => {{
      if (item.role === "user" && norm(item.text) === norm(sent)) index = i;
    }});
    if (index < 0) return false;
    const tail = messages.slice(index + 1).filter((item) => item.role === "assistant");
    if (!tail.length) return false;
    if (tail.some((item) => item.busy === true || item.streaming === true)) return false;
    const last = tail[tail.length - 1];
    if (last.presentation) return true;
    if (last.hasActions !== true) return false;
    if (last.busy === true || last.streaming === true) return false;
    const bothFalse = last.busy === false && last.streaming === false;
    const bothCleared = last.busy === null && last.streaming === null;
    return bothFalse || bothCleared;
  }};
  const log = document.querySelector(sel.log);
  if (!log) return {{timedOut: false, phase: "missing", messages: []}};
  return await new Promise((resolve) => {{
    let finished = false;
    const obs = new MutationObserver(() => tick());
    const finish = (value) => {{
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      obs.disconnect();
      resolve(value);
    }};
    const tick = () => {{
      const messages = collect();
      if (userCount(messages) <= before) return;
      if (!wantReply) finish({{timedOut: false, phase: "sent", messages}});
      else if (ready(messages)) finish({{timedOut: false, phase: "reply", messages}});
    }};
    const timer = setTimeout(() => {{
      const messages = collect();
      const arrived = userCount(messages) > before;
      finish({{timedOut: true, phase: arrived ? "reply" : "user", messages}});
    }}, timeout);
    obs.observe(log, {{
      subtree: true,
      childList: true,
      attributes: true,
      characterData: true,
      attributeFilter: ["aria-busy", "data-hatch-markdown-streaming", "data-message-has-presentation", "data-message-role", "data-testid"],
    }});
    tick();
  }});
}}
"""

PANEL_JS = f"""
() => {{
  const sel = {_arg()};
  const shown = (el) => {{
    if (!el) return false;
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }};
  const text = (node, selector) => {{
    const found = node.querySelector(selector);
    return found ? (found.textContent || "").trim() : "";
  }};
  const card = document.querySelector(sel.panel);
  if (!card) return {{groups: []}};
  const groups = [];
  let current = null;
  const ensure = () => {{
    if (!current) {{
      current = {{title: "", items: []}};
      groups.push(current);
    }}
    return current;
  }};
  for (const node of card.querySelectorAll("h3, " + sel.item)) {{
    if (!shown(node)) continue;
    if (node.tagName === "H3") {{
      current = {{title: (node.textContent || "").trim(), items: []}};
      groups.push(current);
      continue;
    }}
    if (node.getAttribute("aria-pressed") !== null) continue;
    const title = text(node, sel.title);
    const footnote = text(node, sel.detail);
    const caption = text(node, sel.time);
    const fields = caption ? {{title, detail: footnote, time: caption}} : {{title, detail: "", time: footnote}};
    ensure().items.push(fields);
  }}
  return {{groups}};
}}
"""

PANEL_STATE_JS = f"""
() => {{
  const sel = {_arg()};
  const shown = (el) => {{
    if (!el) return false;
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }};
  const card = document.querySelector(sel.panel);
  if (!card || !shown(card)) return {{open: false, label: null}};
  const pressed = [...card.querySelectorAll("button[aria-pressed='true']")].find(shown);
  return {{open: true, label: pressed ? pressed.getAttribute("aria-label") : null}};
}}
"""

CHATS_JS = f"""
() => {{
  const sel = {_arg()};
  const norm = (value) => (value || "").replace(/\\s+/g, " ").trim();
  const trigger = document.querySelector(sel.switcher);
  const mainSpans = trigger
    ? [...trigger.querySelectorAll("span")].map((el) => norm(el.innerText)).filter(Boolean)
    : [];
  const content = document.querySelector(sel.sideContent);
  if (!content) return {{ok: false, mainSpans, rows: []}};
  const rows = [];
  for (const row of content.querySelectorAll("button, a, [role='option']")) {{
    if (row.querySelector("input")) continue;
    const aria = row.getAttribute("aria-label") || "";
    rows.push({{
      title: norm(row.innerText),
      current: row.getAttribute("aria-current") === "true" || row.getAttribute("aria-selected") === "true" || row.getAttribute("aria-pressed") === "true",
      options: row.getAttribute("data-testid") === "hatch-side-chats-options" || aria === "副聊天室選項" || aria === "Side chat options",
    }});
  }}
  return {{ok: true, mainSpans, rows}};
}}
"""

MEMORY_JS = f"""
() => {{
  const sel = {_arg()};
  const body = document.querySelector(sel.editorBody);
  if (!body) return {{ok: false, text: ""}};
  return {{ok: true, text: body.innerText || ""}};
}}
"""
