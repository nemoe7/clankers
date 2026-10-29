/**
 * Reports tab view with left TOC rail, center report column with field cards,
 * inline custom option input, and right scrollable report picker rail.
 */

import { escapeHtml, renderMarkdownBlock } from "./markdown.js";
import { relativeTime } from "./timestamps.js";

const COPY_SVG = `<svg class="lucide lucide-copy" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>`;
const CHECK_SVG = `<svg class="lucide lucide-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"></path></svg>`;
const DISMISS_SVG = `<svg class="lucide lucide-x" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>`;
const SEND_SVG = `<svg class="lucide lucide-send" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"></path><path d="m21.854 2.147-10.94 10.939"></path></svg>`;
const UNANSWERED_SVG = `<svg class="lucide lucide-circle-help report-picker-help-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><path d="M12 17h.01"></path></svg>`;

const CUSTOM_SENTINEL = "__custom__";

function renderFieldBlock(field, headings) {
  const fieldId = escapeHtml(field.id);
  const label = escapeHtml(field.label);
  const anchorId = `field-${field.id}`;
  if (Array.isArray(headings)) {
    headings.push({ id: anchorId, level: 3, text: field.label });
  }
  const recommended = new Set(field.recommended || []);

  if (field.type === "text") {
    return `
      <div class="field-card question" id="${escapeHtml(anchorId)}" data-field-id="${fieldId}" data-field-type="text">
        <div class="field-header">
          <span class="field-label">${label}</span>
          <code class="field-id-chip note-id">${fieldId}</code>
        </div>
        <input type="text" class="input field-text-input" name="field-${fieldId}" placeholder="Enter response..." aria-label="${label}">
      </div>
    `;
  }

  const inputType = field.type === "choice" ? "radio" : "checkbox";
  const optionsHtml = (field.options || [])
    .map((opt) => {
      const checked = recommended.has(opt) ? "checked" : "";
      return `
        <label class="option-row">
          <input type="${inputType}" name="field-${fieldId}" value="${escapeHtml(opt)}" ${checked}>
          <span>${escapeHtml(opt)}</span>
        </label>
      `;
    })
    .join("");

  return `
    <div class="field-card question" id="${escapeHtml(anchorId)}" data-field-id="${fieldId}" data-field-type="${escapeHtml(field.type)}">
      <div class="field-header">
        <span class="field-label">${label}</span>
        <code class="field-id-chip note-id">${fieldId}</code>
      </div>
      <div class="options">
        ${optionsHtml}
        <label class="option-row option-custom">
          <input type="${inputType}" name="field-${fieldId}" value="${CUSTOM_SENTINEL}" class="custom-toggle" aria-label="Something else for ${label}">
          <input type="text" class="input custom-text-input" placeholder="Something else..." aria-label="Custom response for ${label}">
        </label>
      </div>
    </div>
  `;
}

export function renderReportsView(container, state, handlers) {
  const reports = state.reports || [];
  if (!reports.length) {
    container.innerHTML = `<div class="reports-layout"><p class="muted" id="report-status">No report published yet.</p></div>`;
    return;
  }

  const selectedId =
    state.selectedReportId && reports.some((r) => r.id === state.selectedReportId)
      ? state.selectedReportId
      : reports[0].id;
  const activeReport =
    reports.find((r) => r.id === selectedId) || reports[0];

  const blocks = activeReport.blocks || [
    { type: "markdown", markdown: activeReport.body || "" },
  ];
  const hasFields = (activeReport.fields || []).length > 0;
  const headings = [];

  const renderedBlocks = blocks
    .map((block) => {
      if (block.type === "field") {
        return renderFieldBlock(block.field, headings);
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
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
            .join(" · ");
          return `
            <div class="${idx > 0 ? "reply-block" : ""}">
              <p><strong>Submission <code class="note-id">${escapeHtml(ans.id)}</code></strong> · <time datetime="${iso}" data-timestamp="${iso}">${rel}</time> — ${escapeHtml(entries)}</p>
              ${ans.ack ? ans.ack_html || renderMarkdownBlock(ans.ack) : `<p class="muted">Awaiting agent acknowledgement.</p>`}
            </div>
          `;
        })
        .join("")}</div>`
    : "";

  const modIso = escapeHtml(activeReport.modified_at || "");
  const modRel = escapeHtml(relativeTime(activeReport.modified_at));
  const statusBlockHtml = `
    <div id="report-status" class="report-meta muted" role="status">
      <code class="note-id">${escapeHtml(activeReport.id)}</code>
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

      <aside id="report-rail" class="report-rail" aria-label="Report picker and actions">
        <div class="report-rail-bar">
          <span class="report-toc-title">Reports (${reports.length})</span>
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
              ? `<div class="report-submit-row"><button type="submit" class="btn btn-primary">${SEND_SVG} Submit Answers</button></div>`
              : ""
          }
        </form>
      </div>
    </div>
  `;

  for (const btn of container.querySelectorAll("[data-report-id]")) {
    btn.addEventListener("click", () => {
      handlers.onSelectReport(btn.dataset.reportId);
    });
  }

  for (const link of container.querySelectorAll("[data-toc-target]")) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const targetId = link.dataset.tocTarget;
      const targetEl = container.querySelector(`#${CSS.escape(targetId)}`);
      targetEl?.scrollIntoView({ behavior: "smooth", block: "start" });
      for (const item of container.querySelectorAll(".report-toc-link")) {
        item.classList.toggle("active", item === link);
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
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
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
    await handlers.onSubmitReportAnswer(activeReport.id, values);
  });
}
