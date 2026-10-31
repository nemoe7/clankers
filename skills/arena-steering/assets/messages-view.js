// Messages tab view for Arena Steering.

import {
  escapeHtml,
  hydrateMermaidBlocks,
  renderMarkdownBlock,
} from "./markdown.js";
import { relativeTime } from "./timestamps.js";
import { readComposerDraft, writeComposerDraft } from "./state.js";

const EYE_OPEN_SVG = `<svg class="lucide lucide-eye" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
const EYE_CLOSED_SVG = `<svg class="lucide lucide-eye-off" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"></path><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"></path><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"></path><path d="m2 2 20 20"></path></svg>`;
const SKIP_FORWARD_SVG = `<svg class="lucide lucide-skip-forward" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 4v16"></path><path d="M6.029 4.285A2 2 0 0 0 3 6v12a2 2 0 0 0 3.029 1.715l9.997-5.998a2 2 0 0 0 .003-3.432z"></path></svg>`;
const CHECK_SVG = `<svg class="lucide lucide-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"></path></svg>`;
const EXPAND_SVG = `<svg class="lucide lucide-maximize-2" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6"></path><path d="m21 3-7 7"></path><path d="m3 21 7-7"></path><path d="M9 21H3v-6"></path></svg>`;
const COLLAPSE_SVG = `<svg class="lucide lucide-minimize-2" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m14 10 7-7"></path><path d="M20 10h-6V4"></path><path d="m3 21 7-7"></path><path d="M4 14h6v6"></path></svg>`;
const FILE_SVG = `<svg class="lucide lucide-file-text" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"></path><path d="M14 2v6h6"></path><path d="M10 9H8"></path><path d="M16 13H8"></path><path d="M16 17H8"></path></svg>`;
const SEND_SVG = `<svg class="lucide lucide-arrow-up" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 7-7 7 7"></path><path d="M12 19V5"></path></svg>`;
const SENDING_SVG = `<svg class="lucide lucide-loader-circle" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>`;

const AGENT_QUIET_MS = 180_000;
const AGENT_CALL_MS = 1_920_000;

function connectionStamp(value) {
  if (typeof value !== "string" || !value) return null;
  const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value) ? `${value}Z` : value;
  const parsed = Date.parse(stamp);
  return Number.isFinite(parsed) ? parsed : null;
}

export function connectionPresentation(connection = {}, now = Date.now()) {
  if (connection.error) return { state: "down", label: "Disconnected", text: "Connection failed" };
  if (!connection.loaded) return { state: "connecting", label: "Connecting", text: "Connecting…" };
  if (connection.polling) {
    const since = connectionStamp(connection.polling_since);
    const seconds = since === null ? 0 : Math.max(0, Math.floor((now - since) / 1000));
    const duration = seconds >= 60 ? `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s` : `${seconds}s`;
    return { state: "polling", label: "Connected", text: `Polling… ${duration}` };
  }
  const ended = connectionStamp(connection.turn_ended_at);
  const seen = connectionStamp(connection.agent_seen_at);
  const idle = ended !== null ? now - ended > AGENT_QUIET_MS : seen !== null && now - seen > AGENT_CALL_MS;
  return idle
    ? { state: "idle", label: "No agent", text: "Agent 404" }
    : { state: "ok", label: "Connected", text: "Connected" };
}

export function paintConnection(container, connection) {
  const dot = container?.querySelector("#connection-dot");
  const text = container?.querySelector("#connection-text");
  if (!dot || !text) return;
  const current = connectionPresentation(connection);
  dot.dataset.state = current.state;
  dot.setAttribute("aria-label", current.label);
  text.textContent = current.text;
  text.title = current.text;
}

const MESSAGE_PAGE_SIZE = 15;
const OLDER_PAGE_TRIGGER_PX = 320;
const PASTE_ATTACHMENT_CHAR_THRESHOLD = 1500;
const PASTE_ATTACHMENT_LINE_THRESHOLD = 15;
let unreadEditedMsgId = null;
let savedScrollTop = null;
let pinnedToBottom = true;
let skipPollFeedbackUntil = 0;
let visibleMessageCount = MESSAGE_PAGE_SIZE;

export function expandMessageHistory() {
  visibleMessageCount = Infinity;
  pinnedToBottom = false;
}
let loadingMoreMessages = null;
let draftRevision = 0;
let draftPreviewActive = false;
let draftPreviewSequence = 0;
let draftPreviewCache = { text: null, html: "" };
let dropAreaAbort = null;
let replyObserver = null;
let historyResizeObserver = null;
let historyScrollTarget = null;
let historyScrollHandler = null;
const renderedMessageSignatures = new WeakMap();
const pendingReplyReceipts = new Set();

if (typeof document !== "undefined") document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible" || !replyObserver) return;
  for (const target of document.querySelectorAll(".reply-seen-sentinel")) {
    replyObserver.unobserve(target);
    replyObserver.observe(target);
  }
});

function attachmentState(item) {
  if (item.status === "uploading") return "uploading…";
  if (item.status === "failed") return "upload failed";
  const size = Number(item.file?.size || 0);
  if (size < 1000) return `${size} B`;
  if (size < 1000000) return `${Math.round(size / 1000)} kB`;
  return `${(size / 1000000).toFixed(2)} MB`;
}

function renderComposerAttachment(item, sending) {
  const name = escapeHtml(item.name || "attachment");
  const lead = item.previewUrl
    ? `<img class="composer-attachment-lead" src="${escapeHtml(item.previewUrl)}" alt="${name}" width="32" height="32">`
    : `<span class="composer-attachment-lead" aria-hidden="true">${FILE_SVG}</span>`;
  return `<span class="composer-attachment-chip" data-upload-status="${escapeHtml(item.status)}">
    ${lead}
    <span class="composer-attachment-name" title="${name}">${name} · ${escapeHtml(attachmentState(item))}</span>
    ${item.status === "failed" ? `<button type="button" data-retry-composer-attachment="${escapeHtml(item.id)}" aria-label="Retry ${name}" ${sending ? "disabled" : ""}>Retry</button>` : ""}
    <button type="button" data-remove-composer-attachment="${escapeHtml(item.id)}" aria-label="Remove ${name}" ${sending ? "disabled" : ""}>×</button>
  </span>`;
}

function stateDotForStatus(status) {
  if (status === "acked") return "said";
  if (status === "seen") return "seen";
  return "sent";
}

export function messageQueryKey(state) {
  return JSON.stringify([Boolean(state.showHidden), (state.searchQuery || "").trim()]);
}

export function trackMessageAcks(messages) {
  const unseen = (messages || []).filter((msg) => (msg.acks || []).length && !msg.replies_seen);
  unreadEditedMsgId = unseen.at(-1)?.id || null;
}

function highlightSearchMatches(root, rawQuery) {
  const query = (rawQuery || "").trim();
  if (!root || !query) return;
  const lowerQuery = query.toLowerCase();
  const qLen = lowerQuery.length;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (
        parent.closest("script, style, svg, .mermaid, mark.search-hit") ||
        !parent.closest(".message-text, code.msg-id")
      ) {
        return NodeFilter.FILTER_REJECT;
      }
      return (node.nodeValue || "").toLowerCase().includes(lowerQuery)
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_SKIP;
    },
  });
  const textNodes = [];
  let current = walker.nextNode();
  while (current) {
    textNodes.push(current);
    current = walker.nextNode();
  }
  for (const textNode of textNodes) {
    const text = textNode.nodeValue || "";
    const lower = text.toLowerCase();
    const frag = document.createDocumentFragment();
    let cursor = 0;
    let idx = lower.indexOf(lowerQuery, cursor);
    while (idx !== -1) {
      if (idx > cursor) {
        frag.appendChild(document.createTextNode(text.slice(cursor, idx)));
      }
      const mark = document.createElement("mark");
      mark.className = "search-hit";
      mark.textContent = text.slice(idx, idx + qLen);
      frag.appendChild(mark);
      cursor = idx + qLen;
      idx = lower.indexOf(lowerQuery, cursor);
    }
    if (cursor < text.length) {
      frag.appendChild(document.createTextNode(text.slice(cursor)));
    }
    textNode.parentNode?.replaceChild(frag, textNode);
  }
}

// Keep the scroll container and unchanged message cards connected while pages are
// added. Replacing them interrupts a scrollbar drag or an ongoing touch gesture.
function updateHistory(history, nextHistory, signatures) {
  const existing = new Map(
    Array.from(history.querySelectorAll(":scope > .message"), (node) => [node.dataset.msgId, node])
  );
  const nextChildren = Array.from(nextHistory.children);
  for (let i = 0; i < 2; i += 1) {
    history.children[i].replaceWith(nextChildren[i]);
  }
  const wanted = nextChildren.slice(2).map((node) => {
    const signature = signatures.get(node.dataset.msgId);
    const old = existing.get(node.dataset.msgId);
    const use = old && renderedMessageSignatures.get(old) === signature ? old : node;
    renderedMessageSignatures.set(use, signature);
    return use;
  });
  const retained = new Set(wanted);
  for (const old of existing.values()) {
    if (!retained.has(old)) old.remove();
  }
  wanted.forEach((node, index) => {
    const current = history.children[index + 2] || null;
    if (node !== current) history.insertBefore(node, current);
  });
}

export function renderMessagesView(container, state, handlers) {
  if (historyScrollTarget && historyScrollHandler) {
    historyScrollTarget.removeEventListener("scroll", historyScrollHandler);
  }
  replyObserver?.disconnect();
  replyObserver = null;
  historyResizeObserver?.disconnect();
  historyResizeObserver = null;
  const activeEl = document.activeElement;
  const searchWasFocused =
    Boolean(activeEl && activeEl.id === "log-search" && container.contains(activeEl));
  const searchSelStart = searchWasFocused ? activeEl.selectionStart : null;
  const searchSelEnd = searchWasFocused ? activeEl.selectionEnd : null;
  const prevMsgEl = container.querySelector("#msg");
  const draftWasFocused = Boolean(prevMsgEl && activeEl === prevMsgEl);
  const draftValue = prevMsgEl?.value ?? readComposerDraft();
  if (!draftValue.trim()) draftPreviewActive = false;
  const draftSelStart = draftWasFocused ? prevMsgEl.selectionStart : null;
  const draftSelEnd = draftWasFocused ? prevMsgEl.selectionEnd : null;

  let anchorMsgId = null;
  let anchorOffsetTop = 0;
  const prevHistory = container.querySelector("#history");
  if (prevHistory) {
    const dist =
      prevHistory.scrollHeight -
      prevHistory.scrollTop -
      prevHistory.clientHeight;
    pinnedToBottom = dist <= 24;
    savedScrollTop = prevHistory.scrollTop;
    const historyRect = prevHistory.getBoundingClientRect();
    const visibleCards = prevHistory.querySelectorAll(".message:not([data-hidden='true'])");
    for (let i = visibleCards.length - 1; i >= 0; i -= 1) {
      const card = visibleCards[i];
      const rect = card.getBoundingClientRect();
      if (rect.bottom > historyRect.top + 40 && rect.top < historyRect.bottom - 40) {
        anchorMsgId = card.dataset.msgId || null;
        anchorOffsetTop = rect.top - historyRect.top;
        break;
      }
    }
  }

  const showHidden = Boolean(state.showHidden);
  const query = (state.searchQuery || "").trim().toLowerCase();
  const selectedReplyParentIds = Array.isArray(state.replyParentIds)
    ? state.replyParentIds
    : [];
  const composerAttachments = Array.isArray(state.composerAttachments)
    ? state.composerAttachments
    : [];
  const composerExpanded = Boolean(state.composerExpanded);
  const pendingSend = state.pendingSend;
  const skipPollGood = Date.now() < skipPollFeedbackUntil;

  const visibleMessages = state.messages || [];
  const placeholder = (visibleMessages.at(-1)?.body || "What should happen next?").split(/\r?\n/, 1)[0];
  const hasOlderMessages = Boolean(state.messagesHasMore);

  const linkedTasksByMsg = new Map();
  for (const task of state.tasks || []) {
    const msgIds = task.links?.msg_ids || task.msg_ids || [];
    for (const mid of msgIds) {
      if (!linkedTasksByMsg.has(mid)) {
        linkedTasksByMsg.set(mid, []);
      }
      linkedTasksByMsg.get(mid).push(task.id);
    }
  }

  const messageSignatures = new Map();
  const historyHtml = visibleMessages.length
    ? visibleMessages
        .map((msg) => {
          const acks = msg.acks || [];
          const acksHtmlList = msg.acks_html || [];
          const acksHtml = acks.length
            ? `<div class="answer reply message-text">${acks
                .map(
                  (ack, idx) =>
                    `<div class="${idx > 0 ? "reply-block" : ""}">${acksHtmlList[idx] || renderMarkdownBlock(ack)}</div>`
                )
                .join("")}</div>`
            : "";
          const dotState = stateDotForStatus(msg.status);
          const iso = escapeHtml(msg.modified_at || "");
          const rel = escapeHtml(relativeTime(msg.modified_at));
          const extraFlags = [];
          if (!msg.blocking) extraFlags.push("checkpoint");
          if (msg.hidden) extraFlags.push("hidden");
          const flagsSuffix = extraFlags.length
            ? ` · ${escapeHtml(extraFlags.join(", "))}`
            : "";
          const attachments = Array.isArray(msg.attachments)
            ? msg.attachments
            : [];
          const filesSuffix = attachments.length
            ? `<span class="receipt-file">${attachments
                .map((att) => {
                  const name = escapeHtml(att.name || "");
                  return att.present === false
                    ? ` · ${name} (missing)`
                    : ` · ${name}`;
                })
                .join("")}</span>`
            : "";
          const linkedTasks = linkedTasksByMsg.get(msg.id) || [];
          const tasksSuffix = linkedTasks.length
            ? ` · ${linkedTasks.map((tid) => `<button type="button" class="reference-link" data-reference-type="task" data-reference-id="${escapeHtml(tid)}">${escapeHtml(tid)}</button>`).join(", ")}`
            : "";
          const parentIds = Array.isArray(msg.parent_ids) ? msg.parent_ids : [];
          const parentsSuffix = parentIds.length
            ? ` · ${parentIds
                .map(
                  (pid) =>
                    `<button type="button" class="reply-parent-chip" data-parent-id="${escapeHtml(pid)}" title="Go to parent message">↪ ${escapeHtml(pid)}</button>`
                )
                .join(" ")}`
            : "";
          const replySelected = selectedReplyParentIds.includes(msg.id);
          messageSignatures.set(msg.id, JSON.stringify({ msg, linkedTasks, replySelected, query }));

          return `
            <li class="message" data-msg-id="${escapeHtml(msg.id)}" data-hidden="${msg.hidden ? "true" : "false"}">
              <div class="message-text">${msg.body_html || renderMarkdownBlock(msg.body)}</div>
              ${acksHtml}
              ${acks.length && !msg.replies_seen ? `<span class="reply-seen-sentinel" data-reply-id="${escapeHtml(msg.id)}" data-revision="${escapeHtml(msg.replies_revision || "")}" aria-hidden="true"></span>` : ""}
              <p class="receipt">
                <span class="state-dot" data-state="${dotState}" title="Status: ${escapeHtml(msg.status)}"></span>
                <code class="msg-id receipt-id" data-msg-id="${escapeHtml(msg.id)}" data-reply-selected="${replySelected ? "true" : "false"}" title="Reply to message; Shift+Click copies ID">${escapeHtml(msg.id)}</code>
                · <time datetime="${iso}" data-timestamp="${iso}">${rel}</time>${parentsSuffix}${flagsSuffix}${filesSuffix}${tasksSuffix}
              </p>
            </li>
          `;
        })
        .join("")
    : "";

  const survey = state.survey || {};
  const checkedAt = survey.checked_at || "";
  const lastCheckHtml = checkedAt
    ? `Checked <time datetime="${escapeHtml(checkedAt)}" data-timestamp="${escapeHtml(checkedAt)}">${escapeHtml(relativeTime(checkedAt))}</time>`
    : "Live steering active.";

  const markup = `
    <div class="msgs-layout">
      <section class="card log-card" aria-label="Message log">
        <div class="row log-toolbar">
          <div class="stack">
            <p id="connection" role="status">
              <button id="survey-open" type="button" aria-label="Open survey results" title="Open survey results">
                <span id="connection-dot" class="dot" data-state="connecting" role="img" aria-label="Connecting"></span>
              </button>
              <span id="connection-text">Connecting…</span>
            </p>
            <p id="last-check" class="muted">${lastCheckHtml}</p>
          </div>
          <span class="row tight">
            <input
              id="log-search"
              type="search"
              value="${escapeHtml(state.searchQuery || "")}"
              placeholder="Search messages"
              aria-label="Search message log"
            />
            <button
              id="skip-poll"
              class="icon-button"
              type="button"
              ${skipPollGood ? 'data-state="good"' : ""}
              aria-label="Ask the agent to end its wait now"
              title="Ask the agent to end its wait now"
            >
              ${skipPollGood ? CHECK_SVG : SKIP_FORWARD_SVG}
            </button>
            <button
              id="quiet-msgs"
              class="icon-button"
              type="button"
              aria-pressed="${showHidden ? "true" : "false"}"
              aria-label="${showHidden ? "Hide hidden messages" : "Show hidden messages"}"
              title="${showHidden ? "Hide hidden messages" : "Show hidden messages"}"
            >
              ${showHidden ? EYE_OPEN_SVG : EYE_CLOSED_SVG}
            </button>
          </span>
        </div>
        <div class="log-scroll">
          <button id="log-edited" class="log-edited" type="button" aria-live="polite" ${unreadEditedMsgId ? "" : "hidden"}>New reply</button>
          <ol id="history" aria-label="Messages, oldest first">
            <li ${hasOlderMessages ? "" : "hidden"}><button id="load-older-messages" type="button">Show older messages</button></li>
            <li role="alert" ${state.messagesError ? "" : "hidden"}>${escapeHtml(state.messagesError || "")}</li>
            ${historyHtml}
          </ol>
          <button id="log-newest" class="log-newest" type="button" aria-label="Scroll to bottom" title="Scroll to bottom" hidden>
            <svg class="lucide lucide-arrow-down" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 5v14"></path><path d="m19 12-7 7-7-7"></path></svg>
          </button>
        </div>
        <p id="log-empty" class="receipt" role="status" ${visibleMessages.length || state.messagesError || state.messagesLoading ? "hidden" : ""}>${query ? "No matching messages." : "No messages yet."}</p>
      </section>

      <section class="card compose ${composerExpanded ? "composer-expanded" : ""}" id="compose" aria-label="Send message" ${composerAttachments.length ? 'data-attachments="true"' : ""}>
        <form id="form">
          <div
            id="composer-reply-bar"
            class="composer-reply-bar"
            aria-label="Replying to messages"
            ${selectedReplyParentIds.length ? "" : "hidden"}
          >
            <span class="composer-reply-label">Replying to</span>
            ${selectedReplyParentIds
              .map(
                (pid) =>
                  `<button type="button" class="composer-reply-chip" data-remove-reply-parent="${escapeHtml(pid)}" title="Remove reply parent">↪ ${escapeHtml(pid)} ×</button>`
              )
              .join("")}
          </div>
          ${state.composerError ? `<div class="composer-send-status" role="status">${escapeHtml(state.composerError)}</div>` : ""}
          ${pendingSend && !state.sending ? `<div class="composer-send-status" role="status">Send unconfirmed. The original may have been sent. <button type="button" id="retry-send">Retry previous send</button> <button type="button" id="discard-send" title="The original send might have succeeded">Discard retry</button></div>` : ""}
          <div class="composer-shell">
            <div
              id="composer-attachments"
              class="composer-attachments"
              aria-label="Staged attachments"
              ${composerAttachments.length ? "" : "hidden"}
            >${composerAttachments.map((item) => renderComposerAttachment(item, state.sending)).join("")}</div>
            <button
              id="attach-file"
              class="icon-button"
              type="button"
              aria-label="Attach file"
              title="Attach file"
              ${state.sending ? "disabled" : ""}
            >
              <svg class="lucide lucide-paperclip" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m16 6-8.414 8.586a2 2 0 0 0 2.829 2.829l8.414-8.586a4 4 0 1 0-5.657-5.657l-8.379 8.551a6 6 0 1 0 8.485 8.485l8.379-8.551"></path></svg>
            </button>
            <input id="composer-file-input" type="file" multiple hidden />
            <button
              id="preview-msg"
              class="icon-button"
              type="button"
              aria-pressed="${draftPreviewActive ? "true" : "false"}"
              aria-controls="draft-preview"
              aria-label="Preview Markdown"
              title="Preview Markdown"
            >
              <svg class="markdown-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22.27 19.385H1.73A1.73 1.73 0 0 1 0 17.655V6.345a1.73 1.73 0 0 1 1.73-1.73h20.54A1.73 1.73 0 0 1 24 6.345v11.308a1.73 1.73 0 0 1-1.73 1.731Zm-16.501-3.462v-4.5l2.308 2.885 2.307-2.885v4.5h2.308V8.078h-2.308l-2.307 2.885-2.308-2.885H3.46v7.847Zm15.463-3.923h-2.309V8.077h-2.307V12h-2.308l3.461 4.039Z" fill="currentColor" stroke="none"></path></svg>
            </button>
            <textarea
              id="msg"
              name="msg"
              rows="1"
              aria-label="Your message"
              placeholder="${escapeHtml(placeholder)}"
              ${draftPreviewActive ? "hidden" : ""}
            ></textarea>
            <div
              id="draft-preview"
              class="message-text draft-preview"
              tabindex="0"
              role="region"
              aria-label="Markdown draft preview, not sent"
              ${draftPreviewActive ? "" : "hidden"}
            >${draftPreviewActive && draftPreviewCache.text === draftValue ? draftPreviewCache.html : ""}</div>
            <button
              id="composer-expand"
              class="icon-button"
              type="button"
              aria-expanded="${composerExpanded ? "true" : "false"}"
              aria-label="${composerExpanded ? "Collapse composer" : "Expand composer"}"
              title="${composerExpanded ? "Collapse composer" : "Expand composer"}"
              aria-controls="msg draft-preview"
              ${composerExpanded ? "" : "hidden"}
            >
              ${composerExpanded ? COLLAPSE_SVG : EXPAND_SVG}
            </button>
            <button
              id="send"
              class="icon-button"
              type="submit"
              aria-label="${state.sending ? "Sending message" : "Send message"}"
              title="${state.sending ? "Sending message" : "Send message"}"
              aria-busy="${state.sending ? "true" : "false"}"
              ${state.sending ? "disabled" : ""}
            >
              ${state.sending ? SENDING_SVG : SEND_SVG}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;

  let reusedHistory = false;
  if (prevHistory) {
    const template = document.createElement("template");
    template.innerHTML = markup;
    const nextHistory = template.content.querySelector("#history");
    const replaceSelectors = [".log-toolbar", "#log-edited", "#log-newest", "#log-empty", "#compose"];
    const canUpdate = nextHistory && replaceSelectors.every(
      (selector) => container.querySelector(selector) && template.content.querySelector(selector)
    );
    if (canUpdate) {
      for (const selector of replaceSelectors) {
        container.querySelector(selector).replaceWith(template.content.querySelector(selector));
      }
      updateHistory(prevHistory, nextHistory, messageSignatures);
      reusedHistory = true;
    } else {
      container.replaceChildren(template.content);
    }
  } else {
    container.innerHTML = markup;
  }
  if (!reusedHistory) {
    container.querySelectorAll("#history > .message").forEach((node) => {
      renderedMessageSignatures.set(node, messageSignatures.get(node.dataset.msgId));
    });
  }

  container.querySelector("#load-older-messages")?.addEventListener("click", () => handlers.onLoadOlderMessages?.());
  const historyEl = container.querySelector("#history");
  const logNewestBtn = container.querySelector("#log-newest");
  const logEditedBtn = container.querySelector("#log-edited");

  function syncScrollEdges() {
    const dist =
      historyEl.scrollHeight - historyEl.scrollTop - historyEl.clientHeight;
    historyEl.toggleAttribute("data-scrolled-start", historyEl.scrollTop > 0);
    historyEl.toggleAttribute("data-scrolled-end", dist > 1);
    return dist;
  }

  function syncScrollControls() {
    if (!historyEl) return;
    const dist = syncScrollEdges();
    pinnedToBottom = dist <= 24;
    savedScrollTop = historyEl.scrollTop;
    if (logNewestBtn) {
      logNewestBtn.hidden = pinnedToBottom;
    }
    const key = messageQueryKey(state);
    if (hasOlderMessages && !state.messagesError && loadingMoreMessages?.key !== key && historyEl.scrollTop <= OLDER_PAGE_TRIGGER_PX && historyEl.scrollHeight > historyEl.clientHeight) {
      const request = { key };
      loadingMoreMessages = request;
      Promise.resolve(handlers.onLoadOlderMessages?.()).finally(() => {
        if (loadingMoreMessages === request) loadingMoreMessages = null;
      });
    }
  }

  if (historyEl) {
    if (query) {
      highlightSearchMatches(historyEl, state.searchQuery);
    }
    if (anchorMsgId) {
      const anchorCard = historyEl.querySelector(
        `.message[data-msg-id="${CSS.escape(anchorMsgId)}"]`
      );
      if (anchorCard) {
        historyEl.scrollTop = savedScrollTop ?? 0;
        const historyRect = historyEl.getBoundingClientRect();
        const curOffset = anchorCard.getBoundingClientRect().top - historyRect.top;
        historyEl.scrollTop += curOffset - anchorOffsetTop;
      } else if (pinnedToBottom || savedScrollTop === null) {
        historyEl.scrollTop = historyEl.scrollHeight;
      } else {
        historyEl.scrollTop = savedScrollTop;
      }
    } else if (pinnedToBottom || savedScrollTop === null) {
      historyEl.scrollTop = historyEl.scrollHeight;
    } else {
      historyEl.scrollTop = savedScrollTop;
    }
    syncScrollControls();
    historyScrollTarget = historyEl;
    historyScrollHandler = syncScrollControls;
    historyEl.addEventListener("scroll", historyScrollHandler, { passive: true });
    if (typeof ResizeObserver === "function") {
      historyResizeObserver = new ResizeObserver(syncScrollEdges);
      historyResizeObserver.observe(historyEl);
    }
  }

  if (historyEl && typeof IntersectionObserver === "function") {
    replyObserver = new IntersectionObserver((entries) => {
      if (document.visibilityState !== "visible" || container.hidden) return;
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const id = entry.target.dataset.replyId;
        const revision = entry.target.dataset.revision;
        const key = `${id}:${revision}`;
        if (!id || !revision || pendingReplyReceipts.has(key)) continue;
        pendingReplyReceipts.add(key);
        Promise.resolve(handlers.onMarkRepliesSeen?.(id, revision))
          .finally(() => pendingReplyReceipts.delete(key));
      }
    }, { root: historyEl });
    historyEl.querySelectorAll(".reply-seen-sentinel").forEach((el) => replyObserver.observe(el));
  }

  const searchInput = container.querySelector("#log-search");
  if (searchWasFocused && searchInput) {
    searchInput.focus();
    const len = searchInput.value.length;
    const start = searchSelStart ?? len;
    const end = searchSelEnd ?? len;
    try {
      searchInput.setSelectionRange(start, end);
    } catch {
      // Ignore if input type does not support selection range.
    }
  }

  logNewestBtn?.addEventListener("click", () => {
    if (!historyEl) return;
    pinnedToBottom = true;
    historyEl.scrollTo({ top: historyEl.scrollHeight, behavior: "smooth" });
    logNewestBtn.hidden = true;
  });

  logEditedBtn?.addEventListener("click", () => {
    if (unreadEditedMsgId) handlers.onNavigateReference?.("message", unreadEditedMsgId);
  });

  for (const chip of container.querySelectorAll(".reply-parent-chip")) {
    chip.onclick = () => handlers.onNavigateReference?.("message", chip.dataset.parentId);
  }

  for (const chip of container.querySelectorAll("[data-remove-reply-parent]")) {
    chip.addEventListener("click", () => {
      handlers.onToggleReplyParent?.(chip.dataset.removeReplyParent);
    });
  }

  for (const chip of container.querySelectorAll(
    "[data-remove-composer-attachment]"
  )) {
    chip.addEventListener("click", () => {
      handlers.onRemoveComposerAttachment?.(
        chip.dataset.removeComposerAttachment
      );
    });
  }

  for (const button of container.querySelectorAll("[data-retry-composer-attachment]")) {
    button.addEventListener("click", () => {
      handlers.onRetryComposerAttachment?.(button.dataset.retryComposerAttachment);
    });
  }

  const attachBtn = container.querySelector("#attach-file");
  const fileInput = container.querySelector("#composer-file-input");
  attachBtn?.addEventListener("click", () => {
    fileInput?.click();
  });
  fileInput?.addEventListener("change", async () => {
    const files = Array.from(fileInput.files || []);
    fileInput.value = "";
    if (files.length) {
      await handlers.onStageComposerFiles?.(files);
    }
  });

  container.querySelector("#composer-expand")?.addEventListener("click", () => {
    handlers.onToggleComposerExpanded?.();
    container.querySelector(draftPreviewActive ? "#draft-preview" : "#msg")?.focus();
  });

  container.querySelector("#survey-open")?.addEventListener("click", (ev) => {
    handlers.onOpenSurvey?.(ev.currentTarget);
  });

  searchInput?.addEventListener("input", () => {
    handlers.onSearchChange?.(searchInput.value);
  });

  const skipBtn = container.querySelector("#skip-poll");
  skipBtn?.addEventListener("click", async () => {
    skipPollFeedbackUntil = Date.now() + 1000;
    skipBtn.dataset.state = "good";
    skipBtn.innerHTML = CHECK_SVG;
    await handlers.onSkipPoll?.();
    setTimeout(() => {
      const curBtn = container.querySelector("#skip-poll");
      if (curBtn && Date.now() >= skipPollFeedbackUntil) {
        delete curBtn.dataset.state;
        curBtn.innerHTML = SKIP_FORWARD_SVG;
      }
    }, 1000);
  });

  container.querySelector("#quiet-msgs")?.addEventListener("click", () => {
    handlers.onToggleHidden?.();
  });

  const msgEl = container.querySelector("#msg");
  if (msgEl && draftValue && !msgEl.value) {
    msgEl.value = draftValue;
    if (draftWasFocused) {
      msgEl.focus();
      try {
        msgEl.setSelectionRange(
          draftSelStart ?? draftValue.length,
          draftSelEnd ?? draftValue.length
        );
      } catch {
        // Ignore if textarea selection is unavailable.
      }
    }
  }
  const previewBtn = container.querySelector("#preview-msg");
  const draftPreview = container.querySelector("#draft-preview");
  const composeSection = container.querySelector("#compose");
  const expandBtn = container.querySelector("#composer-expand");
  let previewTooltipTimer = null;

  function clearPreviewTooltip() {
    clearTimeout(previewTooltipTimer);
    if (!previewBtn) return;
    delete previewBtn.dataset.tooltip;
    previewBtn.setAttribute("aria-label", "Preview Markdown");
    previewBtn.title = "Preview Markdown";
  }

  async function renderDraftPreview() {
    if (!draftPreview || !msgEl) return;
    const text = msgEl.value;
    if (draftPreviewCache.text === text) {
      draftPreview.innerHTML = draftPreviewCache.html;
      hydrateMermaidBlocks(draftPreview);
      return;
    }
    const sequence = ++draftPreviewSequence;
    draftPreview.textContent = "Rendering draft…";
    try {
      const result = await handlers.onRenderDraft(text);
      if (sequence !== draftPreviewSequence || !draftPreviewActive) return;
      const panel = container.querySelector("#draft-preview");
      if (!panel || container.querySelector("#msg")?.value !== text) return;
      // The renderer's newline after each break must not create a second visual line.
      const html = result.html.replace(/<br\s*\/?>\r?\n/gi, "<br>");
      draftPreviewCache = { text, html };
      panel.innerHTML = html;
      hydrateMermaidBlocks(panel);
    } catch (error) {
      if (sequence !== draftPreviewSequence || !draftPreviewActive) return;
      const panel = container.querySelector("#draft-preview");
      if (panel) panel.textContent = `Preview unavailable: ${error.message}. Use Write to continue, as sending still works.`;
    }
  }

  function growComposer() {
    if (!msgEl || !composeSection) return;
    const priorHistoryHeight = historyEl?.clientHeight || 0;
    const priorNoteHeight = parseFloat(msgEl.style.height) || 0;
    const wasMultiline = Boolean(composeSection.dataset.multiline);
    const hasAttachments = Boolean(composeSection.dataset.attachments);
    delete composeSection.dataset.multiline;
    if (!msgEl.value && composerExpanded) {
      handlers.onSetComposerExpanded?.(false);
      return;
    }
    msgEl.style.height = "auto";
    msgEl.style.overflowY = msgEl.value ? "auto" : "hidden";
    const css = window.getComputedStyle(msgEl);
    const single = parseFloat(css.lineHeight) + parseFloat(css.paddingTop) + parseFloat(css.paddingBottom);
    const multiline = Boolean(msgEl.value && (wasMultiline || draftPreviewActive || msgEl.value.includes("\n") || msgEl.scrollHeight > Math.ceil(single)));
    if (multiline) composeSection.dataset.multiline = "true";
    const border = parseFloat(css.borderTopWidth) + parseFloat(css.borderBottomWidth);
    const nextHeight = !msgEl.value || composerExpanded || msgEl.hidden ? 0 : msgEl.scrollHeight + border;
    msgEl.style.height = nextHeight ? `${nextHeight}px` : "";
    if (expandBtn) expandBtn.hidden = !multiline && !composerExpanded;
    const nextHistoryHeight = historyEl?.clientHeight || 0;
    const heightDrop = priorHistoryHeight > nextHistoryHeight
      ? priorHistoryHeight - nextHistoryHeight
      : nextHistoryHeight > 0
        ? Math.max(0, nextHeight - priorNoteHeight) + (!wasMultiline && multiline && !hasAttachments ? 38 : 0)
        : 0;
    if (historyEl && heightDrop > 0 && !composerExpanded) {
      historyEl.scrollTop = pinnedToBottom
        ? historyEl.scrollHeight
        : Math.min(historyEl.scrollHeight, historyEl.scrollTop + heightDrop);
      syncScrollControls();
    }
  }

  msgEl?.addEventListener("input", () => {
    draftRevision += 1;
    writeComposerDraft(msgEl.value);
    clearPreviewTooltip();
    growComposer();
  });
  growComposer();
  if (draftPreviewActive && draftPreview) renderDraftPreview();

  previewBtn?.addEventListener("click", () => {
    if (!draftPreview || !msgEl) return;
    if (!draftPreviewActive && !msgEl.value.trim()) {
      clearPreviewTooltip();
      previewBtn.setAttribute("aria-label", "Write something first");
      previewBtn.title = "Write something first";
      previewBtn.dataset.tooltip = "Write something first";
      previewTooltipTimer = setTimeout(clearPreviewTooltip, 1500);
      return;
    }
    clearPreviewTooltip();
    draftPreviewActive = !draftPreviewActive;
    previewBtn.setAttribute("aria-pressed", draftPreviewActive ? "true" : "false");
    draftPreview.hidden = !draftPreviewActive;
    msgEl.hidden = draftPreviewActive;
    growComposer();
    if (draftPreviewActive) renderDraftPreview();
    else {
      draftPreviewSequence += 1;
      msgEl.focus();
    }
  });

  let pasteAsText = false;
  msgEl?.addEventListener("keydown", (event) => {
    pasteAsText = event.key.toLowerCase() === "v" && event.ctrlKey && event.shiftKey;
    if (
      event.key === "Enter" && !event.shiftKey && !event.isComposing &&
      !window.matchMedia?.("(pointer: coarse)")?.matches
    ) {
      event.preventDefault();
      container.querySelector("#form")?.requestSubmit();
    }
  });

  msgEl?.addEventListener("keyup", () => { pasteAsText = false; });
  msgEl?.addEventListener("focusout", () => { pasteAsText = false; });
  msgEl?.addEventListener("paste", async (event) => {
    const plainPaste = pasteAsText;
    pasteAsText = false;
    if (plainPaste || state.sending) return;
    const files = Array.from(event.clipboardData?.files || []);
    const pastedText = event.clipboardData?.getData("text/plain") || "";
    if (files.length) {
      if (!pastedText) event.preventDefault();
      await handlers.onStageComposerFiles?.(files);
      return;
    }
    const lineCount = pastedText.split("\n").length;
    if (
      Array.from(pastedText).length > PASTE_ATTACHMENT_CHAR_THRESHOLD ||
      lineCount >= PASTE_ATTACHMENT_LINE_THRESHOLD
    ) {
      event.preventDefault();
      const pasteFile = new File([pastedText], "pasted-text.txt", {
        type: "text/plain",
      });
      await handlers.onStageComposerFiles?.([pasteFile]);
    }
  });

  const dropArea = container.querySelector(".msgs-layout");
  dropAreaAbort?.abort();
  if (dropArea) {
    dropAreaAbort = new AbortController();
    const listenerOptions = { signal: dropAreaAbort.signal };
    const showDrop = (event) => {
      if (state.sending || !event.dataTransfer?.types?.includes("Files")) return;
      event.preventDefault();
      composeSection?.classList.add("composer-drop-active");
    };
    dropArea.addEventListener("dragenter", showDrop, listenerOptions);
    dropArea.addEventListener("dragover", showDrop, listenerOptions);
    dropArea.addEventListener("dragleave", (event) => {
      if (!dropArea.contains(event.relatedTarget)) {
        composeSection?.classList.remove("composer-drop-active");
      }
    }, listenerOptions);
    dropArea.addEventListener("drop", async (event) => {
      const files = Array.from(event.dataTransfer?.files || []);
      if (state.sending || !files.length) return;
      event.preventDefault();
      composeSection?.classList.remove("composer-drop-active");
      await handlers.onStageComposerFiles?.(files);
    }, listenerOptions);
  }

  async function submitPayload(payload, submittedDraft) {
    const submittedRevision = draftRevision;
    try {
      await handlers.onSendMessage(payload);
    } catch (error) {
      console.error(error);
      return;
    }
    const currentMsgEl = container.querySelector("#msg");
    if (draftRevision === submittedRevision && (currentMsgEl ? currentMsgEl.value === submittedDraft : readComposerDraft() === submittedDraft)) {
      writeComposerDraft("");
      draftPreviewActive = false;
      if (currentMsgEl && currentMsgEl.value === submittedDraft) {
        currentMsgEl.value = "";
        currentMsgEl.hidden = false;
        const currentPreview = container.querySelector("#draft-preview");
        if (currentPreview) currentPreview.hidden = true;
        container.querySelector("#preview-msg")?.setAttribute("aria-pressed", "false");
        currentMsgEl.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }
  }

  container.querySelector("#discard-send")?.addEventListener("click", () => handlers.onDiscardPendingSend?.());

  container.querySelector("#retry-send")?.addEventListener("click", () => {
    if (!pendingSend) return;
    submitPayload({ ...pendingSend.content, attachmentIds: pendingSend.attachmentIds, rawDraft: pendingSend.rawDraft }, pendingSend.rawDraft);
  });

  const form = container.querySelector("#form");
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const submittedDraft = msgEl?.value || "";
    const text = submittedDraft.trim();
    if (!text && !composerAttachments.length) return;
    if (state.sending) return;
    const names = composerAttachments.map((item) => item.name);
    const body = text ? submittedDraft : (names.length === 1 ? `File: ${names[0]}` : `Files: ${names.join(", ")}`);
    pinnedToBottom = true;
    submitPayload({
      body,
      parent_ids: [...selectedReplyParentIds],
      attachments: composerAttachments.map((item) => item.attachment),
      attachmentIds: composerAttachments.map((item) => item.id),
      rawDraft: submittedDraft,
    }, pendingSend ? pendingSend.rawDraft : submittedDraft);
  });
}
