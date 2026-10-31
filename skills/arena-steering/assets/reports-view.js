// Reports tab view with left TOC rail, center report column, and right report selector rail.

import { escapeHtml, renderMarkdownBlock } from "./markdown.js";
import { relativeTime } from "./timestamps.js";

const COPY_SVG = `<svg class="lucide lucide-copy" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>`;
const CHECK_SVG = `<svg class="lucide lucide-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"></path></svg>`;
const DISMISS_SVG = `<svg class="lucide lucide-x" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>`;
const SEND_SVG = `<svg class="lucide lucide-send" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"></path><path d="m21.854 2.147-10.94 10.939"></path></svg>`;
const UNANSWERED_SVG = `<svg class="lucide lucide-circle-help report-picker-help-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><path d="M12 17h.01"></path></svg>`;
const CHEVRON_DOWN_SVG = `<svg class="lucide lucide-chevron-down" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m6 9 6 6 6-6"></path></svg>`;
const ARROW_UP_SVG = `<svg class="lucide lucide-arrow-up" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m5 12 7-7 7 7"></path><path d="M12 19V5"></path></svg>`;

const CUSTOM_SENTINEL = "__custom__";
const TOC_TOP_THRESHOLD_PX = 48;
const TOC_BOTTOM_CLAMP_PX = 8;
const TOC_CLICK_LOCK_MS = 650;

let lastRenderedReportId = null;
const DRAFT_KEY = "steer-report-drafts";

function readDrafts() {
  try {
    return JSON.parse(window.localStorage.getItem(DRAFT_KEY) || "{}");
  } catch {
    return {};
  }
}

function readDraft(reportId, fieldId) {
  const drafts = readDrafts();
  const key = `${reportId}:${fieldId}`;
  return Object.hasOwn(drafts, key) ? drafts[key] : undefined;
}

function writeDrafts(reportId, values) {
  try {
    const drafts = readDrafts();
    for (const [fieldId, value] of Object.entries(values)) {
      drafts[`${reportId}:${fieldId}`] = value;
    }
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(drafts));
  } catch {
    /* storage can be unavailable, so drafts stay in memory for this render */
  }
}

function clearDrafts(reportId) {
  try {
    const drafts = readDrafts();
    for (const key of Object.keys(drafts)) {
      if (key.startsWith(`${reportId}:`)) delete drafts[key];
    }
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(drafts));
  } catch {
    /* nothing to clear when storage is unavailable */
  }
}

function storedValuesFor(report) {
  const merged = {};
  for (const answer of report.answers || []) {
    for (const [fieldId, value] of Object.entries(answer.values || {})) {
      merged[fieldId] = value;
    }
  }
  return merged;
}

let mobilePickerCollapsed = false;
let activeScrollCleanup = null;

function renderFieldBlock(field, headings, stored = null) {
  const fieldId = escapeHtml(field.id);
  const label = escapeHtml(field.question || field.label);
  const anchorId = `field-${field.id}`;
  if (Array.isArray(headings)) {
    headings.push({ id: anchorId, level: 3, text: field.question || field.label });
  }
  const recommended = new Set(field.recommended || []);
  const options = field.options || [];
  const storedList = Array.isArray(stored)
    ? stored.map(String)
    : stored === null || stored === undefined || stored === ""
      ? []
      : [String(stored)];
  const storedSet = new Set(storedList);
  const customStored = storedList.find((item) => !options.includes(item)) || "";

  if (field.type === "text") {
    const textValue = storedList[0] || "";
    return `
      <div class="field-card question" id="${escapeHtml(anchorId)}" data-field-id="${fieldId}" data-field-type="text">
        <div class="field-header">
          <span class="field-label">${label}</span>
          <code class="field-id-chip msg-id">${fieldId}</code>
        </div>
        <input type="text" class="input field-text-input" name="field-${fieldId}" value="${escapeHtml(textValue)}" placeholder="Something else..." aria-label="${label}">
      </div>
    `;
  }

  const inputType = field.type === "choice" ? "radio" : "checkbox";
  const optionsHtml = options
    .map((opt) => {
      const checked = storedSet.has(opt) ? "checked" : "";
      const star = recommended.has(opt)
        ? '<span class="option-star" aria-label="Recommended by the agent">*</span> '
        : "";
      return `
        <label class="option-row${recommended.has(opt) ? " is-recommended" : ""}">
          <input type="${inputType}" name="field-${fieldId}" value="${escapeHtml(opt)}" ${checked}>
          <span>${star}${escapeHtml(opt)}</span>
        </label>
      `;
    })
    .join("");

  return `
    <div class="field-card question" id="${escapeHtml(anchorId)}" data-field-id="${fieldId}" data-field-type="${escapeHtml(field.type)}">
      <div class="field-header">
        <span class="field-label">${label}</span>
        <code class="field-id-chip msg-id">${fieldId}</code>
      </div>
      <div class="options">
        ${optionsHtml}
        <label class="option-row option-custom">
          <input type="${inputType}" name="field-${fieldId}" value="${CUSTOM_SENTINEL}" class="custom-toggle" ${customStored ? "checked" : ""} aria-label="Something else for ${label}">
          <input type="text" class="input custom-text-input" value="${escapeHtml(customStored)}" placeholder="Something else..." aria-label="Custom response for ${label}">
        </label>
      </div>
    </div>
  `;
}

export function renderReportsView(container, state, handlers) {
  if (typeof activeScrollCleanup === "function") {
    activeScrollCleanup();
    activeScrollCleanup = null;
  }

  const reports = state.reports || [];
  if (!reports.length) {
    lastRenderedReportId = null;
    container.dataset.scrollable = "false";
    container.innerHTML = `<div class="reports-layout"><p class="muted" id="report-status">No report published yet.</p></div>`;
    return;
  }

  const selectedId =
    state.selectedReportId && reports.some((r) => r.id === state.selectedReportId)
      ? state.selectedReportId
      : reports[0].id;
  const activeReport =
    reports.find((r) => r.id === selectedId) || reports[0];
  const swappedReport =
    lastRenderedReportId !== null && lastRenderedReportId !== activeReport.id;
  lastRenderedReportId = activeReport.id;

  const blocks = activeReport.blocks || [
    { type: "markdown", markdown: activeReport.body || "" },
  ];
  const hasFields = (activeReport.fields || []).length > 0;
  const headings = [];

  const answerValues = storedValuesFor(activeReport);
  const draftValues = readDrafts();
  const fieldValues = { ...answerValues };
  for (const [key, value] of Object.entries(draftValues)) {
    const prefix = `${activeReport.id}:`;
    if (key.startsWith(prefix)) fieldValues[key.slice(prefix.length)] = value;
  }

  const renderedBlocks = blocks
    .map((block) => {
      if (block.type === "field") {
        return renderFieldBlock(block.field, headings, fieldValues[block.field.id]);
      }
      if (typeof block.html === "string") {
        if (Array.isArray(block.headings)) {
          for (const h of block.headings) {
            headings.push(h);
          }
        }
        return `<div class="prose-block">${block.html}</div>`;
      }
      return `<div class="prose-block">${renderMarkdownBlock(block.markdown, { headings })}</div>`;
    })
    .join("");

  const tocLinksHtml = headings
    .map(
      (h, idx) => `
      <a
        href="#${escapeHtml(h.id)}"
        class="report-toc-link ${idx === 0 ? "active" : ""}"
        data-toc-target="${escapeHtml(h.id)}"
        data-level="${h.level}"
        aria-current="${idx === 0 ? "true" : "false"}"
      >${escapeHtml(h.text)}</a>
    `
    )
    .join("");

  const pickerItemsHtml = reports
    .map((rep, idx) => {
      const isActive = rep.id === activeReport.id;
      const isUnseen = !rep.seen;
      const needsAnswer = Boolean(
        rep.needs_answer ??
          ((rep.fields || []).length > 0 && (rep.answers || []).length === 0)
      );
      const markersHtml =
        isUnseen || needsAnswer
          ? `<span class="report-picker-markers">${needsAnswer ? `<span class="report-picker-unanswered" title="Needs answers" aria-label="Needs answers">${UNANSWERED_SVG}</span>` : ""}${isUnseen ? `<span class="report-picker-unseen-dot" title="Unseen report" aria-label="Unseen report"></span>` : ""}</span>`
          : "";
      return `
        <button
          type="button"
          class="report-picker-link report-nav-item ${isActive ? "is-active active" : ""} ${isUnseen ? "is-unseen" : "is-seen"} ${needsAnswer ? "needs-answer" : ""}"
          data-report-id="${escapeHtml(rep.id)}"
          aria-current="${isActive ? "true" : "false"}"
        >
          <span class="report-picker-title">${idx + 1}. ${escapeHtml(rep.title)}</span>
          ${markersHtml}
        </button>
      `;
    })
    .join("");

  const answersHtml = (activeReport.answers || []).length
    ? `<div id="report-ack-history" class="answer reply message-text">${activeReport.answers
        .map((ans, idx) => {
          const iso = escapeHtml(ans.modified_at || "");
          const rel = escapeHtml(relativeTime(ans.modified_at));
          const entries = Object.entries(ans.values || {})
            .map(([k, v]) => {
              const label = ans.field_labels?.[k] || k;
              if (v && typeof v === "object" && !Array.isArray(v)) {
                const selected = Array.isArray(v.selected) ? v.selected : (v.custom ? [] : [v.selected]);
                v = [...selected.filter(Boolean), ...(v.custom ? [v.custom] : [])];
              }
              return `${label}: ${Array.isArray(v) ? v.join(", ") : v}`;
            })
            .join(" · ");
          return `
            <div class="${idx > 0 ? "reply-block" : ""}">
              <p><strong>Answer <code class="msg-id">${escapeHtml(ans.id)}</code></strong> · <time datetime="${iso}" data-timestamp="${iso}">${rel}</time> · ${escapeHtml(entries)}</p>
              ${ans.ack ? ans.ack_html || renderMarkdownBlock(ans.ack) : `<p class="muted">Awaiting agent acknowledgement.</p>`}
            </div>
          `;
        })
        .join("")}</div>`
    : "";

  const updatedAt = activeReport.updated_at || activeReport.modified_at;
  const modIso = escapeHtml(updatedAt || "");
  const modRel = escapeHtml(relativeTime(updatedAt));
  const statusBlockHtml = `
    <div id="report-status" class="report-meta muted" role="status">
      <code class="msg-id">${escapeHtml(activeReport.id)}</code>
      <span>Updated <time datetime="${modIso}" data-timestamp="${modIso}">${modRel}</time></span>
    </div>
  `;
  const renderedWithMeta = renderedBlocks.includes("</h1>")
    ? renderedBlocks.replace("</h1>", `</h1>${statusBlockHtml}`)
    : `<div class="prose-block"><h1>${escapeHtml(activeReport.title)}</h1>${statusBlockHtml}</div>${renderedBlocks}`;

  container.innerHTML = `
    <div class="reports-layout">
      <aside id="report-toc" class="report-toc scroll-panel" aria-label="Report contents" ${headings.length ? "" : "hidden"}>
        <div class="report-toc-list">
          ${tocLinksHtml}
        </div>
      </aside>

      <aside id="report-rail" class="report-rail" aria-label="Report selector and actions" data-mobile-collapsed="${mobilePickerCollapsed ? "true" : "false"}">
        <div class="report-rail-bar">
          <button
            type="button"
            id="report-picker-toggle"
            class="report-picker-toggle"
            aria-expanded="${mobilePickerCollapsed ? "false" : "true"}"
            aria-controls="report-picker"
          >
            ${CHEVRON_DOWN_SVG}
            <span class="report-toc-title">Reports (${reports.length})</span>
          </button>
          <div class="report-rail-actions">
            <button
              type="button"
              class="icon-button"
              id="copy-report-btn"
              data-copy-report="${escapeHtml(activeReport.id)}"
              aria-label="Copy report ${escapeHtml(activeReport.id)}"
              title="Copy report Markdown"
            >${COPY_SVG}</button>
            <button
              type="button"
              class="icon-button"
              id="dismiss-report-btn"
              data-dismiss-report="${escapeHtml(activeReport.id)}"
              aria-label="Dismiss report ${escapeHtml(activeReport.id)}"
              title="Dismiss report"
            >${DISMISS_SVG}</button>
          </div>
        </div>
        <div id="report-picker" class="report-picker scroll-panel" role="region" aria-label="Published reports">
          ${pickerItemsHtml}
        </div>
        ${answersHtml}
      </aside>

      <div id="report-main" class="report-main">
        <form id="report-answer-form">
          <article id="report" class="report" aria-label="Selected report">
            ${renderedWithMeta}
          </article>
          ${
            hasFields
              ? `<div class="report-submit-row"><button type="submit" id="report-submit" class="btn btn-primary">${SEND_SVG} Submit Answers</button></div>`
              : ""
          }
        </form>
      </div>
      ${
        hasFields
          ? `<button type="button" id="report-submit-float" class="btn btn-primary report-submit-float">${SEND_SVG} Submit Answers</button>`
          : ""
      }
      <button
        type="button"
        id="report-scroll-top"
        class="report-scroll-top"
        aria-label="Scroll to top"
        title="Scroll to top"
        hidden
      >${ARROW_UP_SVG}</button>
    </div>
  `;

  if (swappedReport) {
    container.scrollTop = 0;
    if (container.style) {
      container.style.animation = "none";
      void container.offsetHeight;
      container.style.animation = "";
    }
  }

  const railEl = container.querySelector("#report-rail");
  const pickerToggleBtn = container.querySelector("#report-picker-toggle");
  pickerToggleBtn?.addEventListener("click", () => {
    mobilePickerCollapsed = !mobilePickerCollapsed;
    if (railEl) {
      railEl.dataset.mobileCollapsed = mobilePickerCollapsed ? "true" : "false";
    }
    pickerToggleBtn.setAttribute(
      "aria-expanded",
      mobilePickerCollapsed ? "false" : "true"
    );
  });

  const scrollTopBtn = container.querySelector("#report-scroll-top");
  scrollTopBtn?.addEventListener("click", () => {
    if (typeof container.scrollTo === "function") {
      container.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      container.scrollTop = 0;
    }
  });

  let tocClickLockId = null;
  let tocClickLockUntil = 0;
  let tocFlashTimer = null;

  const setActiveTocLink = (targetId) => {
    for (const item of container.querySelectorAll(".report-toc-link")) {
      const isMatch = item.dataset.tocTarget === targetId;
      item.classList.toggle("active", isMatch);
      item.setAttribute("aria-current", isMatch ? "true" : "false");
    }
  };

  const syncScrollState = () => {
    const scrollable =
      (container.scrollHeight || 0) > (container.clientHeight || 0) + 1;
    container.dataset.scrollable = scrollable ? "true" : "false";
    if (scrollTopBtn) {
      scrollTopBtn.hidden = (container.scrollTop || 0) <= 160;
    }
    if (!headings.length) return;
    if (tocClickLockId && Date.now() < tocClickLockUntil) {
      setActiveTocLink(tocClickLockId);
      return;
    }
    tocClickLockId = null;
    if (
      scrollable &&
      container.scrollTop + container.clientHeight >=
        container.scrollHeight - TOC_BOTTOM_CLAMP_PX
    ) {
      setActiveTocLink(headings[headings.length - 1].id);
      return;
    }
    const containerTop = container.getBoundingClientRect?.().top || 0;
    let activeId = headings[0].id;
    for (const h of headings) {
      const el = container.querySelector(`#${CSS.escape(h.id)}`);
      if (!el?.getBoundingClientRect) continue;
      const relTop = el.getBoundingClientRect().top - containerTop;
      if (relTop <= TOC_TOP_THRESHOLD_PX) {
        activeId = h.id;
      } else {
        break;
      }
    }
    setActiveTocLink(activeId);
  };

  container.addEventListener?.("scroll", syncScrollState, { passive: true });
  activeScrollCleanup = () => {
    container.removeEventListener?.("scroll", syncScrollState);
    if (tocFlashTimer) {
      clearTimeout(tocFlashTimer);
      tocFlashTimer = null;
    }
  };
  syncScrollState();

  for (const btn of container.querySelectorAll("[data-report-id]")) {
    btn.addEventListener("click", () => {
      handlers.onSelectReport(btn.dataset.reportId);
    });
  }

  for (const link of container.querySelectorAll("[data-toc-target]")) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const targetId = link.dataset.tocTarget;
      tocClickLockId = targetId;
      tocClickLockUntil = Date.now() + TOC_CLICK_LOCK_MS;
      setActiveTocLink(targetId);
      const targetEl = container.querySelector(`#${CSS.escape(targetId)}`);
      if (targetEl) {
        targetEl.scrollIntoView?.({ behavior: "smooth", block: "start" });
        for (const flashed of container.querySelectorAll("[data-toc-flash]")) {
          delete flashed.dataset.tocFlash;
        }
        targetEl.dataset.tocFlash = "true";
        if (tocFlashTimer) clearTimeout(tocFlashTimer);
        tocFlashTimer = setTimeout(() => {
          if (targetEl.isConnected) {
            delete targetEl.dataset.tocFlash;
          }
        }, 1200);
      }
    });
  }

  for (const question of container.querySelectorAll(".question")) {
    const customToggle = question.querySelector(".custom-toggle");
    const customInput = question.querySelector(".custom-text-input");
    if (!customToggle || !customInput) continue;
    customInput.addEventListener("focus", () => {
      customToggle.checked = true;
    });
    customInput.addEventListener("input", () => {
      if (customInput.value.trim()) {
        customToggle.checked = true;
      }
    });
  }

  const copyBtn = container.querySelector("#copy-report-btn");
  copyBtn?.addEventListener("click", async () => {
    try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard
        .writeText(activeReport.body || "")
        .catch(() => {});
    }
      copyBtn.dataset.state = "good";
      copyBtn.innerHTML = CHECK_SVG;
      setTimeout(() => {
        if (copyBtn.isConnected) {
          delete copyBtn.dataset.state;
          copyBtn.innerHTML = COPY_SVG;
        }
      }, 1400);
    } catch {
      copyBtn.dataset.state = "bad";
    }
  });

  const dismissBtn = container.querySelector("#dismiss-report-btn");
  dismissBtn?.addEventListener("click", async () => {
    await handlers.onDismissReport(activeReport.id, dismissBtn);
  });

  const form = container.querySelector("#report-answer-form");
  const submitBtn = container.querySelector("#report-submit");
  const submitFloat = container.querySelector("#report-submit-float");
  submitFloat?.addEventListener("click", () => {
    if (typeof form?.requestSubmit === "function") {
      form.requestSubmit(submitBtn || undefined);
    } else {
      submitBtn?.click();
    }
  });
  const collectValues = () => {
    const values = {};
    for (const question of container.querySelectorAll(
      ".question[data-field-id]"
    )) {
      const fid = question.dataset.fieldId;
      const ftype = question.dataset.fieldType;
      if (ftype === "text") {
        const val =
          question.querySelector(".field-text-input")?.value.trim() || "";
        if (val) values[fid] = val;
      } else if (ftype === "choice") {
        const checked = question.querySelector('input[type="radio"]:checked');
        if (!checked) continue;
        if (checked.value === CUSTOM_SENTINEL) {
          const customVal =
            question.querySelector(".custom-text-input")?.value.trim() || "";
          if (customVal) values[fid] = customVal;
        } else {
          values[fid] = checked.value;
        }
      } else if (ftype === "checkbox") {
        const checkedList = [
          ...question.querySelectorAll('input[type="checkbox"]:checked'),
        ];
        const selected = [];
        for (const box of checkedList) {
          if (box.value === CUSTOM_SENTINEL) {
            const customVal =
              question.querySelector(".custom-text-input")?.value.trim() || "";
            if (customVal) selected.push(customVal);
          } else {
            selected.push(box.value);
          }
        }
        if (selected.length) values[fid] = selected;
      }
    }
    return values;
  };

  form?.addEventListener("input", () => {
    writeDrafts(activeReport.id, collectValues());
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = collectValues();
    await handlers.onSubmitReportAnswer(activeReport.id, values);
    clearDrafts(activeReport.id);
  });
}
