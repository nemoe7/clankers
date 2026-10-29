/**
 * Main ES module controller for Arena Steering.
 */

import { api } from "./api.js";
import { renderInboxView } from "./inbox-view.js";
import { createModalManager } from "./modal.js";
import { renderReportsView } from "./reports-view.js";
import { createStore } from "./state.js";
import { renderTasksView } from "./tasks-view.js";
import { mountRelativeTimers } from "./timestamps.js";

const CHECK_SVG = `<svg class="lucide lucide-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"></path></svg>`;

const store = createStore();
const modal = createModalManager();
let cleanupTimers = () => {};
let knownAssetVersion = null;
let lastDataSignature = "";
let lastViewportHeight = 0;

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

function setLoading(active) {
  const main = document.getElementById("main-root");
  if (main) {
    main.setAttribute("data-loading", active ? "true" : "false");
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
      api.listReports({ stale: false }),
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
    const reports = repRes.reports || [];
    const selectedReportId =
      curState.selectedReportId &&
      reports.some((r) => r.id === curState.selectedReportId)
        ? curState.selectedReportId
        : reports[0]?.id || null;
    const nextSignature = JSON.stringify({
      messages,
      tasks,
      reports,
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
  onSelectReport(reportId) {
    store.setState({ selectedReportId: reportId });
  },
  async onDismissReport(reportId, trigger) {
    const decision = await modal.open("confirm-delete", {
      title: `Dismiss report ${reportId}?`,
      slots: { message: `Mark report "${reportId}" as dismissed?` },
      trigger,
    });
    if (decision !== "confirm") return;
    await api.dismissReport(reportId);
    await refreshAll(true);
  },
  async onSubmitReportAnswer(reportId, values) {
    await api.submitReportAnswer(reportId, values);
    await refreshAll(true);
  },
};

const SEEN_REPORTS_KEY = "steer.seenReports";

function loadSeenReports() {
  try {
    const raw = window.localStorage?.getItem(SEEN_REPORTS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveSeenReports(seen) {
  try {
    window.localStorage?.setItem(SEEN_REPORTS_KEY, JSON.stringify(seen));
  } catch {
    // Ignore storage quota or privacy mode errors.
  }
}

function markReportSeen(report) {
  if (!report?.id) return;
  const seen = loadSeenReports();
  const stamp = report.modified_at || "seen";
  if (seen[report.id] !== stamp) {
    seen[report.id] = stamp;
    saveSeenReports(seen);
  }
}

function reportNeedsAttention(report, seen) {
  if (!report || report.status === "dismissed") return false;
  const stamp = report.modified_at || "seen";
  const notYetSeen = seen[report.id] !== stamp;
  const hasUnansweredFields =
    (report.fields || []).length > 0 && (report.answers || []).length === 0;
  return notYetSeen || hasUnansweredFields;
}

function renderApp(state) {
  cleanupTimers();

  const reports = state.reports || [];
  if (state.activeTab === "reports" && reports.length) {
    const activeReport =
      reports.find((r) => r.id === state.selectedReportId) || reports[0];
    markReportSeen(activeReport);
  }
  const seenReports = loadSeenReports();
  const pendingReports = reports.filter((r) =>
    reportNeedsAttention(r, seenReports)
  ).length;

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
  } else if (state.activeTab === "tasks" && tasksEl) {
    renderTasksView(tasksEl, state, handlers);
  } else if (state.activeTab === "reports" && reportsEl) {
    renderReportsView(reportsEl, state, handlers);
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

  document.addEventListener("click", async (event) => {
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
