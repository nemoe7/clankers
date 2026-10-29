/**
 * Reports tab view with inline Markdown fields and built-in "Something else..." custom input.
 */

import { escapeHtml, renderMarkdownBlock } from "./markdown.js";
import { relativeTime } from "./timestamps.js";

const COPY_SVG = `<svg class="lucide lucide-copy" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>`;
const DISMISS_SVG = `<svg class="lucide lucide-x" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>`;
const SEND_SVG = `<svg class="lucide lucide-send" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"></path><path d="m21.854 2.147-10.94 10.939"></path></svg>`;

const CUSTOM_SENTINEL = "__custom__";

function renderFieldBlock(field) {
  const fieldId = escapeHtml(field.id);
  const label = escapeHtml(field.label);
  const recommended = new Set(field.recommended || []);

  if (field.type === "text") {
    return `
      <div class="field-card" data-field-id="${fieldId}" data-field-type="text">
        <div class="field-header">
          <span class="field-label">${label}</span>
          <span class="meta-pill">${fieldId}</span>
        </div>
        <input type="text" class="input field-text-input" name="field-${fieldId}" placeholder="Enter response...">
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
    <div class="field-card" data-field-id="${fieldId}" data-field-type="${escapeHtml(field.type)}">
      <div class="field-header">
        <span class="field-label">${label}</span>
        <span class="meta-pill">${fieldId}</span>
      </div>
      ${optionsHtml}
      <label class="option-row">
        <input type="${inputType}" name="field-${fieldId}" value="${CUSTOM_SENTINEL}" class="custom-toggle">
        <span>Something else...</span>
      </label>
      <div class="custom-input-wrap" hidden>
        <input type="text" class="input custom-text-input" placeholder="Specify something else...">
      </div>
    </div>
  `;
}

export function renderReportsView(container, state, handlers) {
  const reports = state.reports || [];
  if (!reports.length) {
    container.innerHTML = `<div class="card"><p>No published reports.</p></div>`;
    return;
  }

  const selectedId =
    state.selectedReportId && reports.some((r) => r.id === state.selectedReportId)
      ? state.selectedReportId
      : reports[0].id;
  const activeReport = reports.find((r) => r.id === selectedId) || reports[0];

  const navHtml = reports
    .map((rep) => {
      const isActive = rep.id === activeReport.id ? "is-active" : "";
      return `
        <button type="button" class="report-nav-item ${isActive}" data-report-id="${escapeHtml(rep.id)}">
          <div style="display: flex; justify-content: space-between; gap: 6px; align-items: center;">
            <strong>${escapeHtml(rep.title)}</strong>
            <span class="status-pill status-${escapeHtml(rep.status)}">${escapeHtml(rep.status)}</span>
          </div>
          <div style="margin-top: 4px;">
            <span class="meta-pill">${escapeHtml(rep.id)}</span>
          </div>
        </button>
      `;
    })
    .join("");

  const blocks = activeReport.blocks || [
    { type: "markdown", markdown: activeReport.body || "" },
  ];
  const hasFields = (activeReport.fields || []).length > 0;

  const renderedBlocks = blocks
    .map((block) => {
      if (block.type === "field") {
        return renderFieldBlock(block.field);
      }
      return `<div class="prose-block">${renderMarkdownBlock(block.markdown)}</div>`;
    })
    .join("");

  const answersHtml = (activeReport.answers || []).length
    ? activeReport.answers
        .map(
          (ans) => `
            <div class="ack-box">
              <div style="display: flex; justify-content: space-between; gap: 8px;">
                <span class="meta-pill">answer ${escapeHtml(ans.id)}</span>
                <time class="meta-pill" datetime="${escapeHtml(ans.modified_at)}" data-timestamp="${escapeHtml(ans.modified_at)}">
                  ${escapeHtml(relativeTime(ans.modified_at))}
                </time>
              </div>
              <pre class="mono" style="margin: 6px 0 0; font-size: 12px;">${escapeHtml(JSON.stringify(ans.values, null, 2))}</pre>
              ${
                ans.ack
                  ? `<div style="margin-top: 6px;">${renderMarkdownBlock(ans.ack)}</div>`
                  : ""
              }
            </div>
          `
        )
        .join("")
    : "";

  container.innerHTML = `
    <div class="reports-layout">
      <aside>${navHtml}</aside>
      <div class="card">
        <div class="card-header">
          <div>
            <span class="meta-pill">${escapeHtml(activeReport.id)}</span>
            <h2 class="card-title" style="margin-top: 4px;">${escapeHtml(activeReport.title)}</h2>
          </div>
          <div style="display: flex; gap: 8px; align-items: center;">
            <span class="status-pill status-${escapeHtml(activeReport.status)}">${escapeHtml(activeReport.status)}</span>
            <button type="button" class="icon-button" id="copy-report-btn" data-copy-report="${escapeHtml(activeReport.id)}" aria-label="Copy report ${escapeHtml(activeReport.id)}" title="Copy report Markdown">${COPY_SVG}</button>
            <button type="button" class="icon-button" id="dismiss-report-btn" data-dismiss-report="${escapeHtml(activeReport.id)}" aria-label="Dismiss report ${escapeHtml(activeReport.id)}" title="Dismiss report">${DISMISS_SVG}</button>
          </div>
        </div>
        <form id="report-answer-form">
          ${renderedBlocks}
          ${
            hasFields
              ? `<div class="composer-row"><button type="submit" class="btn btn-primary">${SEND_SVG} Submit Answers</button></div>`
              : ""
          }
        </form>
        ${answersHtml}
      </div>
    </div>
  `;

  for (const navBtn of container.querySelectorAll(".report-nav-item")) {
    navBtn.addEventListener("click", () => {
      handlers.onSelectReport(navBtn.dataset.reportId);
    });
  }

  for (const card of container.querySelectorAll(".field-card")) {
    const customToggle = card.querySelector(".custom-toggle");
    const customWrap = card.querySelector(".custom-input-wrap");
    if (!customToggle || !customWrap) continue;
    card.addEventListener("change", () => {
      customWrap.hidden = !customToggle.checked;
      if (customToggle.checked) {
        customWrap.querySelector(".custom-text-input")?.focus();
      }
    });
  }

  const copyBtn = container.querySelector("[data-copy-report]");
  copyBtn?.addEventListener("click", async () => {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(activeReport.body || "");
    }
  });

  const dismissBtn = container.querySelector("[data-dismiss-report]");
  dismissBtn?.addEventListener("click", async () => {
    await handlers.onDismissReport(activeReport.id, dismissBtn);
  });

  const form = container.querySelector("#report-answer-form");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = {};
    for (const card of form.querySelectorAll(".field-card")) {
      const fieldId = card.dataset.fieldId;
      const fieldType = card.dataset.fieldType;
      if (fieldType === "text") {
        values[fieldId] = card.querySelector(".field-text-input").value.trim();
      } else if (fieldType === "choice") {
        const checked = card.querySelector("input[type='radio']:checked");
        if (!checked) continue;
        if (checked.value === CUSTOM_SENTINEL) {
          values[fieldId] = card.querySelector(".custom-text-input").value.trim();
        } else {
          values[fieldId] = checked.value;
        }
      } else if (fieldType === "checkbox") {
        const checkedBoxes = [
          ...card.querySelectorAll("input[type='checkbox']:checked"),
        ];
        const list = [];
        for (const box of checkedBoxes) {
          if (box.value === CUSTOM_SENTINEL) {
            const customVal = card
              .querySelector(".custom-text-input")
              .value.trim();
            if (customVal) list.push(customVal);
          } else {
            list.push(box.value);
          }
        }
        values[fieldId] = list;
      }
    }
    await handlers.onSubmitReportAnswer(activeReport.id, values);
  });
}
