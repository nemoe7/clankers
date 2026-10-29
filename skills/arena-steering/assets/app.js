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

const SUN_SVG = `<svg class="lucide lucide-sun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path></svg>`;
const MOON_SVG = `<svg class="lucide lucide-moon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"></path></svg>`;

const store = createStore();
const modal = createModalManager();
let cleanupTimers = () => {};

function setLoading(active) {
  const main = document.getElementById("main-root");
  if (main) {
    main.setAttribute("data-loading", active ? "true" : "false");
  }
}

function showBanner(text) {
  const banner = document.getElementById("status-banner");
  if (!banner) return;
  if (!text) {
    banner.hidden = true;
    banner.textContent = "";
    return;
  }
  banner.hidden = false;
  banner.textContent = text;
}

function applyTheme(next) {
  const root = document.documentElement;
  root.classList.toggle("dark", next === "dark");
  root.classList.toggle("light", next === "light");
  root.dataset.theme = next;
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  const isLight = next === "light";
  btn.innerHTML = isLight ? MOON_SVG : SUN_SVG;
  const label = `Switch to ${isLight ? "dark" : "light"} mode`;
  btn.setAttribute("aria-label", label);
  btn.title = label;
}

async function refreshAll() {
  setLoading(true);
  try {
    const curState = store.getState();
    const [health, msgRes, taskRes, repRes] = await Promise.all([
      api.getHealth(),
      api.listMessages({ all: true, hidden: Boolean(curState.showHidden) }),
      api.listTasks({ full: true }),
      api.listReports({ stale: false }),
    ]);
    const pill = document.getElementById("version-pill");
    if (pill && health.version) {
      pill.textContent = `v${health.version}`;
    }
    store.setState({
      messages: msgRes.messages || [],
      tasks: taskRes.tasks || [],
      reports: repRes.reports || [],
    });
  } catch (err) {
    showBanner(err.message || "Failed to load steering data.");
  } finally {
    setLoading(false);
  }
}

const handlers = {
  async onSendMessage(payload) {
    await api.sendMessage(payload);
    showBanner("Message queued for agent.");
    await refreshAll();
  },
  async onSkipPoll() {
    await api.skipPoll();
    showBanner("Skip-poll stamp recorded.");
  },
  async onToggleHidden() {
    const nextHidden = !store.getState().showHidden;
    store.setState({ showHidden: nextHidden });
    await refreshAll();
  },
  onSearchChange(query) {
    store.setState({ searchQuery: query });
  },
  async onCreateTask(task) {
    await api.createTask(task);
    showBanner(`Task ${task.id} created.`);
    await refreshAll();
  },
  onToggleEditTask(taskId) {
    const cur = store.getState().editingTaskId;
    store.setState({ editingTaskId: cur === taskId ? null : taskId });
  },
  async onPatchTask(taskId, changes) {
    await api.patchTask(taskId, changes);
    store.setState({ editingTaskId: null });
    showBanner(`Task ${taskId} updated.`);
    await refreshAll();
  },
  async onDeleteTask(taskId, trigger) {
    const decision = await modal.open("confirm-delete", {
      title: `Delete task ${taskId}?`,
      slots: { message: `Remove task "${taskId}" from the queue?` },
      trigger,
    });
    if (decision !== "confirm") return;
    await api.deleteTask(taskId);
    showBanner(`Task ${taskId} removed.`);
    await refreshAll();
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
    showBanner(`Report ${reportId} dismissed.`);
    await refreshAll();
  },
  async onSubmitReportAnswer(reportId, values) {
    await api.submitReportAnswer(reportId, values);
    showBanner(`Submitted answers for ${reportId}.`);
    await refreshAll();
  },
};

function renderApp(state) {
  cleanupTimers();

  const unreadCount = state.messages.filter((m) => m.status !== "acked").length;
  const openTasks = state.tasks.filter((t) => t.status !== "finished").length;
  const openReports = state.reports.filter(
    (r) => r.status === "published"
  ).length;

  document.getElementById("badge-inbox").textContent = String(unreadCount);
  document.getElementById("badge-tasks").textContent = String(openTasks);
  document.getElementById("badge-reports").textContent = String(openReports);

  for (const btn of document.querySelectorAll(".tab-btn")) {
    const active = btn.dataset.tab === state.activeTab;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  }

  const inboxEl = document.getElementById("view-inbox");
  const tasksEl = document.getElementById("view-tasks");
  const reportsEl = document.getElementById("view-reports");

  inboxEl.hidden = state.activeTab !== "inbox";
  tasksEl.hidden = state.activeTab !== "tasks";
  reportsEl.hidden = state.activeTab !== "reports";

  if (state.activeTab === "inbox") {
    renderInboxView(inboxEl, state, handlers);
  } else if (state.activeTab === "tasks") {
    renderTasksView(tasksEl, state, handlers);
  } else if (state.activeTab === "reports") {
    renderReportsView(reportsEl, state, handlers);
  }

  cleanupTimers = mountRelativeTimers(document);
}

function initEvents() {
  window.addEventListener("keydown", (event) => {
    if (event.key === "Tab") {
      document.documentElement.setAttribute("data-keyboard-nav", "true");
    }
  });
  window.addEventListener("pointerdown", () => {
    document.documentElement.removeAttribute("data-keyboard-nav");
  });

  for (const btn of document.querySelectorAll(".tab-btn")) {
    btn.addEventListener("click", () => {
      store.setState({ activeTab: btn.dataset.tab });
    });
  }

  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    const next = store.getState().theme === "dark" ? "light" : "dark";
    applyTheme(next);
    store.setState({ theme: next });
  });
}

store.subscribe(renderApp);
initEvents();
refreshAll();
setInterval(refreshAll, 5000);
