// Messages tab view for Arena Steering.

import {
  escapeHtml,
  hydrateMermaidBlocks,
  renderMarkdownBlock,
} from "./markdown.js";
import { relativeTime } from "./timestamps.js";

const EYE_OPEN_SVG = `<svg class="lucide lucide-eye" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
const EYE_CLOSED_SVG = `<svg class="lucide lucide-eye-off" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"></path><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"></path><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"></path><path d="m2 2 20 20"></path></svg>`;
const SKIP_FORWARD_SVG = `<svg class="lucide lucide-skip-forward" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 4v16"></path><path d="M6.029 4.285A2 2 0 0 0 3 6v12a2 2 0 0 0 3.029 1.715l9.997-5.998a2 2 0 0 0 .003-3.432z"></path></svg>`;
const CHECK_SVG = `<svg class="lucide lucide-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"></path></svg>`;

const MESSAGE_PAGE_SIZE = 15;
const seenAckCounts = new Map();
let initializedAckCounts = false;
let unreadEditedMsgId = null;
let savedScrollTop = null;
let pinnedToBottom = true;
let skipPollFeedbackUntil = 0;
let visibleMessageCount = MESSAGE_PAGE_SIZE;
let loadingMoreMessages = false;

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
      if (activeTab !== "messages" || !pinnedToBottom) {
        unreadEditedMsgId = msg.id;
      }
    }
    seenAckCounts.set(msg.id, cur);
  }
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

export function renderMessagesView(container, state, handlers) {
  const activeEl = document.activeElement;
  const searchWasFocused =
    Boolean(activeEl && activeEl.id === "log-search" && container.contains(activeEl));
  const searchSelStart = searchWasFocused ? activeEl.selectionStart : null;
  const searchSelEnd = searchWasFocused ? activeEl.selectionEnd : null;

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
  const skipPollGood = Date.now() < skipPollFeedbackUntil;

  const filteredMessages = (state.messages || []).filter((msg) => {
    if (!showHidden && msg.hidden) return false;
    if (!query) return true;
    const haystack = [msg.id, msg.body, ...(msg.acks || [])]
      .join("\n")
      .toLowerCase();
    return haystack.includes(query);
  });

  const hasOlderMessages =
    !query && filteredMessages.length > visibleMessageCount;
  const visibleMessages = query
    ? filteredMessages
    : filteredMessages.slice(
        Math.max(0, filteredMessages.length - visibleMessageCount)
      );

  const linkedTasksByMsg = new Map();
  for (const task of state.tasks || []) {
    const msgIds = task.links?.msg_ids || task.msg_ids || [];
    for (const mid of msgIds) {
      if (!linkedTasksByMsg.has(mid)) {
        linkedTasksByMsg.set(mid, []);
      }
      linkedTasksByMsg.set(mid).push(task.id);
    }
  }

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
            ? ` · ${linkedTasks.map((tid) => `<code class="task-link">${escapeHtml(tid)}</code>`).join(", ")}`
            : "";

          return `
            <li class="message" data-msg-id="${escapeHtml(msg.id)}" data-hidden="${msg.hidden ? "true" : "false"}">
              <div class="message-text">${msg.body_html || renderMarkdownBlock(msg.body)}</div>
              ${acksHtml}
              <p class="receipt">
                <span class="state-dot" data-state="${dotState}" title="Status: ${escapeHtml(msg.status)}"></span>
                <code class="msg-id" title="Copy message ID">${escapeHtml(msg.id)}</code>
                · <time datetime="${iso}" data-timestamp="${iso}">${rel}</time>${flagsSuffix}${filesSuffix}${tasksSuffix}
              </p>
            </li>
          `;
        })
        .join("")
    : "";

  const survey = state.survey || {};
  const checkedAt = survey.checked_at || "";
  const surveyResults = Array.isArray(survey.results) ? survey.results : [];
  let dotStateClass = "live animate-pulse";
  if (surveyResults.length > 0) {
    if (surveyResults.some((item) => item.correct === false)) {
      dotStateClass = "survey-bad";
    } else if (surveyResults.some((item) => item.correct !== true)) {
      dotStateClass = "survey-warn";
    }
  }
  const lastCheckHtml = checkedAt
    ? `Checked <time datetime="${escapeHtml(checkedAt)}" data-timestamp="${escapeHtml(checkedAt)}">${escapeHtml(relativeTime(checkedAt))}</time>`
    : "Live steering active.";

  container.innerHTML = `
    <div class="msgs-layout">
      <section class="card log-card" aria-label="Message log">
        <div class="row log-toolbar">
          <div class="stack">
            <p id="connection" role="status">
              <button id="survey-open" type="button" aria-label="Open survey results" title="Open survey results">
                <span id="connection-dot" class="dot ${dotStateClass}" role="img" aria-label="Connected"></span>
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
          <ol id="history" aria-label="Messages, oldest first">${historyHtml}</ol>
          <button id="log-newest" class="log-newest" type="button" aria-label="Scroll to bottom" title="Scroll to bottom" hidden>
            <svg class="lucide lucide-arrow-down" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 5v14"></path><path d="m19 12-7 7-7-7"></path></svg>
          </button>
        </div>
        <p id="log-empty" class="receipt" role="status" ${visibleMessages.length ? "hidden" : ""}>No messages yet.</p>
      </section>

      <section class="card compose" id="compose" aria-label="Send message">
        <form id="form">
          <div class="composer-shell">
            <button
              id="preview-msg"
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
              id="msg"
              name="msg"
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
    if (
      hasOlderMessages &&
      !loadingMoreMessages &&
      historyEl.scrollTop <= 48 &&
      historyEl.scrollHeight > historyEl.clientHeight
    ) {
      loadingMoreMessages = true;
      const firstCard = historyEl.querySelector(".message");
      const topAnchorId = firstCard?.dataset.msgId || null;
      const prevRectTop = firstCard
        ? firstCard.getBoundingClientRect().top -
          historyEl.getBoundingClientRect().top
        : 0;
      visibleMessageCount += MESSAGE_PAGE_SIZE;
      renderMessagesView(container, state, handlers);
      const nextHistory = container.querySelector("#history");
      if (nextHistory && topAnchorId) {
        const nextCard = nextHistory.querySelector(
          `.message[data-msg-id="${CSS.escape(topAnchorId)}"]`
        );
        if (nextCard) {
          const curRectTop =
            nextCard.getBoundingClientRect().top -
            nextHistory.getBoundingClientRect().top;
          nextHistory.scrollTop += curRectTop - prevRectTop;
          savedScrollTop = nextHistory.scrollTop;
        }
      }
      loadingMoreMessages = false;
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
    historyEl.addEventListener("scroll", syncScrollControls, { passive: true });
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
  const previewBtn = container.querySelector("#preview-msg");
  const draftPreview = container.querySelector("#draft-preview");

  previewBtn?.addEventListener("click", () => {
    const active = previewBtn.getAttribute("aria-pressed") === "true";
    const next = !active;
    previewBtn.setAttribute("aria-pressed", next ? "true" : "false");
    if (draftPreview && msgEl) {
      draftPreview.innerHTML = renderMarkdownBlock(msgEl.value);
      hydrateMermaidBlocks(draftPreview);
      draftPreview.hidden = !next;
      msgEl.hidden = next;
    }
  });

  msgEl?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      container.querySelector("#form")?.requestSubmit();
    }
  });

  const form = container.querySelector("#form");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = (msgEl?.value || "").trim();
    if (!body) return;
    pinnedToBottom = true;
    await handlers.onSendMessage({ body });
    if (msgEl) msgEl.value = "";
  });
}
