/**
 * Main ES module controller for Arena Steering.
 */

import { api } from "./api.js";
import { renderInboxView, trackMessageAcks } from "./inbox-view.js";
import {
  escapeHtml,
  hydrateMermaidBlocks,
  toggleCodeMermaid,
} from "./markdown.js";
import { createModalManager } from "./modal.js";
import { renderReportsView } from "./reports-view.js";
import { createStore } from "./state.js";
import { renderTasksView } from "./tasks-view.js";
import { mountRelativeTimers } from "./timestamps.js";

const CHECK_SVG = `<svg class="lucide lucide-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"></path></svg>`;

const store = createStore();
const modal = createModalManager();
const reportCache = new Map();
let cleanupTimers = () => {};
let knownAssetVersion = null;
let lastDataSignature = "";
let lastViewportHeight = 0;

async function ensureReportCached(reportId, expectedModifiedAt = null) {
  if (!reportId) return null;
  const cached = reportCache.get(reportId);
  if (
    cached &&
    (!expectedModifiedAt || cached.modified_at === expectedModifiedAt) &&
    Array.isArray(cached.report?.blocks)
  ) {
    return cached.report;
  }
  const res = await api.getReport(reportId);
  if (res?.report) {
    reportCache.set(reportId, {
      modified_at: res.report.modified_at,
      report: res.report,
    });
    return res.report;
  }
  return null;
}

function hydrateReportsWithCache(summaries) {
  const activeIds = new Set();
  const merged = (summaries || []).map((summary) => {
    activeIds.add(summary.id);
    if (Array.isArray(summary.blocks)) {
      reportCache.set(summary.id, {
        modified_at: summary.modified_at,
        report: summary,
      });
      return summary;
    }
    const cached = reportCache.get(summary.id);
    if (cached && cached.modified_at === summary.modified_at) {
      return {
        ...cached.report,
        ...summary,
        body: cached.report.body,
        blocks: cached.report.blocks,
      };
    }
    return summary;
  });
  for (const key of reportCache.keys()) {
    if (!activeIds.has(key)) {
      reportCache.delete(key);
    }
  }
  return merged;
}

function syncViewportHeight() {
  const vv = window.visualViewport;
  const vvScale = vv?.scale > 0 ? vv.scale : 1;
  const vvHeight = (vv?.height || 0) * vvScale;
  const innerHeight = window.innerHeight || 0;
  const docHeight = document.documentElement?.clientHeight || 0;
  const heights = [vvHeight, innerHeight, docHeight].filter((h) => h > 0);
  const nextHeight = heights.length ? Math.round(Math.min(...heights)) : 0;
  if (!nextHeight) return;
  if (nextHeight !== lastViewportHeight) {
    lastViewportHeight = nextHeight;
    document.documentElement.style?.setProperty?.(
      "--app-height",
      `${nextHeight}px`
    );
  }
  if (
    ((vvScale <= 1.01 && vv?.offsetTop) || window.scrollY) &&
    typeof window.scrollTo === "function"
  ) {
    window.scrollTo(0, 0);
  }
}

let loadingCount = 0;
let loadingStartAt = 0;
let loadingDoneTimer = null;

function setLoading(active) {
  const main = document.getElementById("main-root");
  if (!main) return;
  if (active) {
    loadingCount += 1;
    if (loadingDoneTimer) {
      clearTimeout(loadingDoneTimer);
      loadingDoneTimer = null;
    }
    if (main.getAttribute("data-loading") !== "true") {
      loadingStartAt = Date.now();
      main.setAttribute("data-loading", "true");
    }
  } else {
    loadingCount = Math.max(0, loadingCount - 1);
    if (loadingCount === 0) {
      const elapsed = Date.now() - loadingStartAt;
      if (elapsed >= 200) {
        main.setAttribute("data-loading", "done");
        loadingDoneTimer = setTimeout(() => {
          if (
            loadingCount === 0 &&
            main.getAttribute("data-loading") === "done"
          ) {
            main.setAttribute("data-loading", "false");
          }
        }, 220);
      } else {
        main.setAttribute("data-loading", "false");
      }
    }
  }
}

async function refreshAll(force = false) {
  setLoading(true);
  try {
    const curState = store.getState();
    const [health, msgRes, taskRes, repRes] = await Promise.all([
      api.getHealth(),
      api.listMessages({ all: true, hidden: Boolean(curState.showHidden) }),
      api.listTasks({ full: true }),
      api.listReports({ stale: false, summary: true }),
    ]);
    if (health.asset_version) {
      if (knownAssetVersion && knownAssetVersion !== health.asset_version) {
        window.location.reload();
        return;
      }
      knownAssetVersion = health.asset_version;
    }
    if (health.repo) {
      const expectedTitle = `${health.repo} - Steering`;
      if (document.title !== expectedTitle) {
        document.title = expectedTitle;
      }
    }
    const messages = msgRes.messages || [];
    const tasks = taskRes.tasks || [];
    const reportSummaries = repRes.reports || [];
    const survey = health.survey || {};
    trackMessageAcks(messages, curState.activeTab);
    const selectedReportId =
      curState.selectedReportId &&
      reportSummaries.some((r) => r.id === curState.selectedReportId)
        ? curState.selectedReportId
        : reportSummaries[0]?.id || null;
    if (selectedReportId) {
      const selectedSummary = reportSummaries.find(
        (r) => r.id === selectedReportId
      );
      await ensureReportCached(selectedReportId, selectedSummary?.modified_at);
    }
    const reports = hydrateReportsWithCache(reportSummaries);
    const nextSignature = JSON.stringify({
      messages,
      tasks,
      reports,
      survey,
      selectedReportId,
      showHidden: Boolean(curState.showHidden),
    });
    if (!force && nextSignature === lastDataSignature) {
      return;
    }
    lastDataSignature = nextSignature;
    store.setState({
      messages,
      tasks,
      reports,
      survey,
      selectedReportId,
    });
  } catch (err) {
    console.error(err);
  } finally {
    setLoading(false);
  }
}

const handlers = {
  async onSendMessage(payload) {
    await api.sendMessage(payload);
    await refreshAll(true);
  },
  async onSkipPoll() {
    await api.skipPoll();
  },
  async onToggleHidden() {
    const nextHidden = !store.getState().showHidden;
    store.setState({ showHidden: nextHidden });
    await refreshAll(true);
  },
  onSearchChange(query) {
    store.setState({ searchQuery: query });
  },
  async onOpenSurvey(trigger) {
    const res = await api.getSurvey().catch(() => ({ survey: store.getState().survey || {} }));
    const survey = res.survey || {};
    const questions = survey.questions || [];
    const answers = survey.answers || {};
    const rowsHtml = questions.length
      ? questions
          .map((q) => {
            const ans = answers[q.id] || "(not answered yet)";
            return `<div class="survey-item"><p class="survey-item-prompt">${escapeHtml(q.prompt)}</p><p class="survey-item-answer">${escapeHtml(ans)}</p></div>`;
          })
          .join("")
      : `<p class="muted">No survey questions configured.</p>`;
    const decision = await modal.open("survey-results", {
      title: "Survey Results & Bible Check",
      htmlSlots: { content: rowsHtml },
      trigger,
    });
    if (decision === "bible-check") {
      await api.triggerBibleCheck(true).catch(() => {});
      await refreshAll(true);
    }
  },
  async onSelectReport(reportId) {
    const curReports = store.getState().reports || [];
    const target = curReports.find((r) => r.id === reportId);
    if (target && !target.seen) {
      const seenRes = await api.markReportSeen(reportId).catch(() => null);
      if (seenRes?.report) {
        reportCache.set(reportId, {
          modified_at: seenRes.report.modified_at,
          report: seenRes.report,
        });
      }
      store.setState({ selectedReportId: reportId });
      await refreshAll(true);
      return;
    }
    await ensureReportCached(reportId, target?.modified_at);
    const hydrated = hydrateReportsWithCache(store.getState().reports || []);
    store.setState({ selectedReportId: reportId, reports: hydrated });
  },
  async onDismissReport(reportId, trigger) {
    const decision = await modal.open("confirm-delete", {
      title: `Dismiss report ${reportId}?`,
      slots: { message: `Mark report "${reportId}" as dismissed?` },
      trigger,
    });
    if (decision !== "confirm") return;
    reportCache.delete(reportId);
    await api.dismissReport(reportId);
    await refreshAll(true);
  },
  async onSubmitReportAnswer(reportId, values) {
    const ansRes = await api.submitReportAnswer(reportId, values);
    if (ansRes?.report) {
      reportCache.set(reportId, {
        modified_at: ansRes.report.modified_at,
        report: ansRes.report,
      });
    }
    await refreshAll(true);
  },
};

function reportNeedsAttention(report) {
  if (!report || report.status === "dismissed") return false;
  const notYetSeen = !report.seen;
  const hasUnansweredFields = Boolean(
    report.needs_answer ??
      ((report.fields || []).length > 0 && (report.answers || []).length === 0)
  );
  return notYetSeen || hasUnansweredFields;
}

function renderApp(state) {
  cleanupTimers();

  const reports = state.reports || [];
  const pendingReports = reports.filter((r) => reportNeedsAttention(r)).length;

  const reportPip = document.getElementById("report-pip");
  if (reportPip) {
    reportPip.hidden = pendingReports === 0;
    const label = pendingReports
      ? "Unread or unanswered report"
      : "No unread reports";
    reportPip.title = label;
    reportPip.setAttribute("aria-label", label);
  }

  for (const btn of document.querySelectorAll(".tab-btn")) {
    const active = btn.dataset.tab === state.activeTab;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  }

  const inboxEl = document.getElementById("view-inbox");
  const tasksEl = document.getElementById("view-tasks");
  const reportsEl = document.getElementById("view-reports");

  if (inboxEl) inboxEl.hidden = state.activeTab !== "inbox";
  if (tasksEl) tasksEl.hidden = state.activeTab !== "tasks";
  if (reportsEl) reportsEl.hidden = state.activeTab !== "reports";

  if (state.activeTab === "inbox" && inboxEl) {
    renderInboxView(inboxEl, state, handlers);
    hydrateMermaidBlocks(inboxEl);
  } else if (state.activeTab === "tasks" && tasksEl) {
    renderTasksView(tasksEl, state, handlers);
  } else if (state.activeTab === "reports" && reportsEl) {
    renderReportsView(reportsEl, state, handlers);
    hydrateMermaidBlocks(reportsEl);
  }

  cleanupTimers = mountRelativeTimers(document);
}

function initEvents() {
  syncViewportHeight();
  window.addEventListener("resize", syncViewportHeight);
  window.visualViewport?.addEventListener("resize", syncViewportHeight);
  window.visualViewport?.addEventListener("scroll", syncViewportHeight);

  window.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Tab" ||
        event.key.startsWith("Arrow") ||
        event.key === "Enter" ||
        event.key === " "
      ) {
        document.documentElement.setAttribute("data-keyboard-nav", "true");
      }
    },
    true
  );
  window.addEventListener(
    "pointerdown",
    () => {
      document.documentElement.removeAttribute("data-keyboard-nav");
    },
    true
  );

  for (const btn of document.querySelectorAll(".tab-btn")) {
    btn.addEventListener("click", () => {
      store.setState({ activeTab: btn.dataset.tab });
    });
  }

  const interruptBtn = document.getElementById("agent-interrupt");
  interruptBtn?.addEventListener("click", async () => {
    interruptBtn.setAttribute("aria-busy", "true");
    try {
      await api.triggerBibleCheck();
      await refreshAll(true);
    } finally {
      interruptBtn.setAttribute("aria-busy", "false");
    }
  });

  document.addEventListener("click", async (event) => {
    const mermaidBtn = event.target.closest?.(".preview-code-mermaid");
    if (mermaidBtn) {
      toggleCodeMermaid(mermaidBtn);
      return;
    }
    const copyBtn = event.target.closest?.(".copy-code");
    if (copyBtn) {
      const code = (copyBtn.dataset.code || "").replace(/&#10;/g, "\n");
      const originalHtml = copyBtn.innerHTML;
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(code).catch(() => {});
      }
      copyBtn.dataset.state = "good";
      copyBtn.innerHTML = CHECK_SVG;
      setTimeout(() => {
        if (copyBtn.isConnected) {
          delete copyBtn.dataset.state;
          copyBtn.innerHTML = originalHtml;
        }
      }, 1400);
      return;
    }
    if (event.target.closest?.(".report-picker-link")) {
      return;
    }
    const noteChip = event.target.closest?.("code.note-id");
    if (noteChip) {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard
          .writeText(noteChip.textContent || "")
          .catch(() => {});
      }
      noteChip.dataset.state = "good";
      setTimeout(() => {
        if (noteChip.isConnected) {
          delete noteChip.dataset.state;
        }
      }, 1000);
    }
  });
}

store.subscribe(renderApp);
initEvents();
refreshAll(true);
setInterval(() => refreshAll(false), 5000);
