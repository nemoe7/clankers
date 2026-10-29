/**
 * Messages (Inbox) tab view for Arena Steering.
 */

import { escapeHtml, renderMarkdownBlock } from "./markdown.js";
import { relativeTime } from "./timestamps.js";

const seenAckCounts = new Map();
let initializedAckCounts = false;
let unreadEditedMsgId = null;
let savedScrollTop = null;
let pinnedToBottom = true;

function stateDotForStatus(status) {
  if (status === "acked") return "said";
  if (status === "seen") return "seen";
  return "sent";
}

export function trackMessageAcks(messages, activeTab) {
  const list = messages || [];
  if (!initializedAckCounts) {
    for (const msg of list) {
      seenAckCounts.set(msg.id, (msg.acks || []).length);
    }
    initializedAckCounts = true;
    return;
  }
  for (const msg of list) {
    const prev = seenAckCounts.get(msg.id);
    const cur = (msg.acks || []).length;
    if (prev !== undefined && cur > prev) {
      if (activeTab !== "inbox" || !pinnedToBottom) {
        unreadEditedMsgId = msg.id;
      }
    }
    seenAckCounts.set(msg.id, cur);
  }
}

export function renderInboxView(container, state, handlers) {
  const prevHistory = container.querySelector("#history");
  if (prevHistory) {
    const dist =
      prevHistory.scrollHeight -
      prevHistory.scrollTop -
      prevHistory.clientHeight;
    pinnedToBottom = dist <= 24;
    savedScrollTop = prevHistory.scrollTop;
  }

  const showHidden = Boolean(state.showHidden);
  const query = (state.searchQuery || "").trim().toLowerCase();

  const visibleMessages = (state.messages || []).filter((msg) => {
    if (!showHidden && msg.hidden) return false;
    if (!query) return true;
    const haystack = [msg.id, msg.body, ...(msg.acks || [])]
      .join("\n")
      .toLowerCase();
    return haystack.includes(query);
  });

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

          return `
            <li class="message" data-msg-id="${escapeHtml(msg.id)}">
              <div class="message-text">${msg.body_html || renderMarkdownBlock(msg.body)}</div>
              ${acksHtml}
              <p class="receipt">
                <span class="state-dot" data-state="${dotState}" title="Status: ${escapeHtml(msg.status)}"></span>
                <code class="note-id" title="Copy message ID">${escapeHtml(msg.id)}</code>
                · <time datetime="${iso}" data-timestamp="${iso}">${rel}</time>${flagsSuffix}
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

  container.innerHTML = `
    <div class="notes-layout">
      <section class="card log-card" aria-label="Message log">
        <div class="row log-toolbar">
          <div class="stack">
            <p id="connection" role="status">
              <button id="survey-open" type="button" aria-label="Open survey results" title="Open survey results">
                <span id="connection-dot" class="dot live animate-pulse" role="img" aria-label="Connected"></span>
              </button>
              <span id="connection-text">Connected</span>
            </p>
            <p id="last-check" class="muted">${lastCheckHtml}</p>
          </div>
          <span class="row tight">
            <input
              id="log-search"
              type="search"
              value="${escapeHtml(state.searchQuery || "")}"
              placeholder="Search messages"
              aria-label="Search the message log"
            />
            <button
              id="skip-poll"
              class="icon-button"
              type="button"
              aria-label="Ask the agent to end its wait now"
              title="Ask the agent to end its wait now"
            >
              <svg class="lucide lucide-skip-forward" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 4v16"></path><path d="M6.029 4.285A2 2 0 0 0 3 6v12a2 2 0 0 0 3.029 1.715l9.997-5.998a2 2 0 0 0 .003-3.432z"></path></svg>
            </button>
            <button
              id="quiet-notes"
              class="icon-button"
              type="button"
              aria-pressed="${showHidden ? "true" : "false"}"
              aria-label="Show hidden messages"
              title="Show hidden messages"
            >
              <svg class="lucide lucide-eye" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"></path><circle cx="12" cy="12" r="3"></circle></svg>
            </button>
          </span>
        </div>
        <div class="log-scroll">
          <button id="log-edited" class="log-edited" type="button" aria-live="polite" ${unreadEditedMsgId ? "" : "hidden"}>New reply</button>
          <ol id="history" aria-label="Messages, oldest first">${historyHtml}</ol>
          <button id="log-newest" class="log-newest" type="button" aria-label="Scroll to bottom" title="Scroll to bottom" hidden>
            <svg class="lucide lucide-arrow-down" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 5v14"></path><path d="m19 12-7 7-7-7"></path></svg>
          </button>
        </div>
        <p id="log-empty" class="receipt" role="status" ${visibleMessages.length ? "hidden" : ""}>No messages yet.</p>
      </section>

      <section class="card compose" id="compose" aria-label="Send a message">
        <form id="form">
          <div class="composer-shell">
            <button
              id="preview-note"
              class="icon-button"
              type="button"
              aria-pressed="false"
              aria-controls="draft-preview"
              aria-label="Preview Markdown"
              title="Preview Markdown"
            >
              <svg class="markdown-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22.27 19.385H1.73A1.73 1.73 0 0 1 0 17.655V6.345a1.73 1.73 0 0 1 1.73-1.73h20.54A1.73 1.73 0 0 1 24 6.345v11.308a1.73 1.73 0 0 1-1.73 1.731Zm-16.501-3.462v-4.5l2.308 2.885 2.307-2.885v4.5h2.308V8.078h-2.308l-2.307 2.885-2.308-2.885H3.46v7.847Zm15.463-3.923h-2.309V8.077h-2.307V12h-2.308l3.461 4.039Z" fill="currentColor" stroke="none"></path></svg>
            </button>
            <textarea
              id="note"
              name="note"
              rows="1"
              aria-label="Your message"
              placeholder="What should happen next?"
              required
            ></textarea>
            <div
              id="draft-preview"
              class="message-text draft-preview"
              tabindex="0"
              role="region"
              aria-label="Markdown draft preview, not sent"
              hidden
            ></div>
            <button
              id="send"
              class="icon-button"
              type="submit"
              aria-label="Send message"
              title="Send message"
              aria-busy="false"
            >
              <svg class="lucide lucide-arrow-up" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 7-7 7 7"></path><path d="M12 19V5"></path></svg>
            </button>
          </div>
        </form>
      </section>
    </div>
  `;

  const historyEl = container.querySelector("#history");
  const logNewestBtn = container.querySelector("#log-newest");
  const logEditedBtn = container.querySelector("#log-edited");

  function syncScrollControls() {
    if (!historyEl) return;
    const dist =
      historyEl.scrollHeight - historyEl.scrollTop - historyEl.clientHeight;
    pinnedToBottom = dist <= 24;
    savedScrollTop = historyEl.scrollTop;
    if (logNewestBtn) {
      logNewestBtn.hidden = pinnedToBottom;
    }
    if (pinnedToBottom && unreadEditedMsgId) {
      const lastId = visibleMessages[visibleMessages.length - 1]?.id;
      if (unreadEditedMsgId === lastId) {
        unreadEditedMsgId = null;
        if (logEditedBtn) logEditedBtn.hidden = true;
      }
    }
  }

  if (historyEl) {
    if (pinnedToBottom || savedScrollTop === null) {
      historyEl.scrollTop = historyEl.scrollHeight;
    } else {
      historyEl.scrollTop = savedScrollTop;
    }
    syncScrollControls();
    historyEl.addEventListener("scroll", syncScrollControls, { passive: true });
  }

  logNewestBtn?.addEventListener("click", () => {
    if (!historyEl) return;
    pinnedToBottom = true;
    historyEl.scrollTo({ top: historyEl.scrollHeight, behavior: "smooth" });
    logNewestBtn.hidden = true;
  });

  logEditedBtn?.addEventListener("click", () => {
    const targetId = unreadEditedMsgId;
    unreadEditedMsgId = null;
    logEditedBtn.hidden = true;
    if (!historyEl) return;
    const row = targetId
      ? historyEl.querySelector(`.message[data-msg-id="${CSS.escape(targetId)}"]`)
      : null;
    if (row) {
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      const reply = row.querySelector(".answer.reply");
      if (reply) {
        reply.dataset.highlight = "true";
        setTimeout(() => {
          if (reply.isConnected) delete reply.dataset.highlight;
        }, 1200);
      }
    } else {
      historyEl.scrollTo({ top: historyEl.scrollHeight, behavior: "smooth" });
    }
  });

  container.querySelector("#survey-open")?.addEventListener("click", (ev) => {
    handlers.onOpenSurvey?.(ev.currentTarget);
  });

  const searchInput = container.querySelector("#log-search");
  searchInput?.addEventListener("input", () => {
    handlers.onSearchChange?.(searchInput.value);
  });

  container
    .querySelector("#skip-poll")
    ?.addEventListener("click", async () => {
      await handlers.onSkipPoll?.();
    });

  container.querySelector("#quiet-notes")?.addEventListener("click", () => {
    handlers.onToggleHidden?.();
  });

  const noteEl = container.querySelector("#note");
  const previewBtn = container.querySelector("#preview-note");
  const draftPreview = container.querySelector("#draft-preview");

  previewBtn?.addEventListener("click", () => {
    const active = previewBtn.getAttribute("aria-pressed") === "true";
    const next = !active;
    previewBtn.setAttribute("aria-pressed", next ? "true" : "false");
    if (draftPreview && noteEl) {
      draftPreview.innerHTML = renderMarkdownBlock(noteEl.value);
      draftPreview.hidden = !next;
      noteEl.hidden = next;
    }
  });

  noteEl?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      container.querySelector("#form")?.requestSubmit();
    }
  });

  const form = container.querySelector("#form");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = (noteEl?.value || "").trim();
    if (!body) return;
    pinnedToBottom = true;
    await handlers.onSendMessage({ body });
    if (noteEl) noteEl.value = "";
  });
}
