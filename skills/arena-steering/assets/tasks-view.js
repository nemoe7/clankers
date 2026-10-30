// Tasks tab view for Arena Steering (`Current`, `Upcoming`, `Finished`).

import { escapeHtml } from "./markdown.js";
import { relativeTime } from "./timestamps.js";

const CHEVRON_DOWN_SVG = `<svg class="lucide lucide-chevron-down select-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m6 9 6 6 6-6"></path></svg>`;

const TASK_TYPES = ["report", "code", "docs", "ops", "misc"];
const FINISHED_TASK_PAGE_SIZE = 10;

let taskSearchQuery = "";
let taskTypeFilter = "all";
let visibleFinishedCount = FINISHED_TASK_PAGE_SIZE;
const openTaskDetails = new Set();

export function expandTaskTarget(id) {
  taskSearchQuery = "";
  taskTypeFilter = "all";
  visibleFinishedCount = Infinity;
  openTaskDetails.add(id);
}

function formatTypeBadge(type) {
  const normalized = (type || "misc").toLowerCase();
  const label =
    normalized === "ops" || normalized === "operations"
      ? "Ops"
      : normalized.charAt(0).toUpperCase() + normalized.slice(1);
  return `<span class="task-type" data-task-type="${escapeHtml(normalized)}">${escapeHtml(label)}</span>`;
}

function taskDetailLines(task) {
  const lines = [];
  if (task.scope) {
    lines.push(`Scope: ${task.scope}`);
  }
  const links = task.links || {};
  const taskIds = links.task_ids || task.task_ids || task.deps || [];
  const reportIds = links.report_ids || task.report_ids || [];
  for (const dep of taskIds) {
    lines.push(`Needs: ${dep}`);
  }
  for (const rep of reportIds) {
    lines.push(`Report: ${rep}`);
  }
  for (const d of task.details || []) {
    lines.push(d);
  }
  return lines;
}

function taskMatchesFilter(task) {
  if (taskTypeFilter !== "all" && (task.type || "misc") !== taskTypeFilter) {
    return false;
  }
  if (!taskSearchQuery) {
    return true;
  }
  const haystack = [
    task.id,
    task.title,
    task.type || "",
    ...taskDetailLines(task),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(taskSearchQuery);
}

function renderTaskRow(task) {
  const details = taskDetailLines(task);
  const count = details.length;
  const isOpen =
    openTaskDetails.has(task.id) ||
    Boolean(
      taskSearchQuery &&
        details.some((d) => d.toLowerCase().includes(taskSearchQuery))
    );

  const detailsHtml = count
    ? `
      <details class="task-details" data-task-id="${escapeHtml(task.id)}" ${isOpen ? "open" : ""}>
        <summary>${count} detail${count === 1 ? "" : "s"}</summary>
        <ul class="task-detail-list">
          ${details.map((line) => `<li class="task-detail">${escapeHtml(line)}</li>`).join("")}
        </ul>
      </details>
    `
    : "";

  return `
    <li class="task" data-task-id="${escapeHtml(task.id)}" title="Task ${escapeHtml(task.id)}">
      <span class="task-title" data-blocked="${task.blocked ? "true" : "false"}">${escapeHtml(task.title)}</span>
      ${formatTypeBadge(task.type)}
      ${detailsHtml}
    </li>
  `;
}

export function renderTasksView(container, state) {
  const prevScrollTop = container.scrollTop || 0;
  const allTasks = state.tasks || [];

  const activeTasks = allTasks.filter((t) => t.status !== "finished");
  const finishedTasks = allTasks.filter((t) => t.status === "finished");

  const inProgress = activeTasks.filter((t) => t.status === "in_progress");
  const firstUnblocked =
    inProgress.length > 0
      ? null
      : activeTasks.find((t) => !t.blocked) || null;

  const currentSet = new Set(
    inProgress.length > 0
      ? inProgress.map((t) => t.id)
      : firstUnblocked
        ? [firstUnblocked.id]
        : []
  );

  const currentTasks = activeTasks
    .filter((t) => currentSet.has(t.id))
    .filter(taskMatchesFilter);
  const upcomingTasks = activeTasks
    .filter((t) => !currentSet.has(t.id))
    .filter(taskMatchesFilter);
  const filteredFinished = finishedTasks.filter(taskMatchesFilter);
  const hasMoreFinished =
    !taskSearchQuery &&
    taskTypeFilter === "all" &&
    filteredFinished.length > visibleFinishedCount;
  const shownFinished =
    taskSearchQuery || taskTypeFilter !== "all"
      ? filteredFinished
      : filteredFinished.slice(0, visibleFinishedCount);

  const latestModified = allTasks.reduce(
    (acc, t) => (t.modified_at && t.modified_at > acc ? t.modified_at : acc),
    ""
  );
  const statusHtml = allTasks.length
    ? `Updated <time datetime="${escapeHtml(latestModified)}" data-timestamp="${escapeHtml(latestModified)}">${escapeHtml(relativeTime(latestModified))}</time>`
    : "No task list yet.";

  container.innerHTML = `
    <div class="tasks-layout">
      <div class="row tight tasks-toolbar">
        <p id="tasks-status" class="muted" role="status">${statusHtml}</p>
        <input
          id="task-search"
          type="search"
          class="input"
          value="${escapeHtml(taskSearchQuery)}"
          placeholder="Search tasks"
          aria-label="Search task list"
        />
        <div class="select-wrap task-filter">
          <select id="task-type-filter" class="select" aria-label="Filter tasks by type">
            <option value="all" ${taskTypeFilter === "all" ? "selected" : ""}>All types</option>
            ${TASK_TYPES.map(
              (t) =>
                `<option value="${t}" ${taskTypeFilter === t ? "selected" : ""}>${t === "ops" ? "Ops" : t.charAt(0).toUpperCase() + t.slice(1)}</option>`
            ).join("")}
          </select>
          ${CHEVRON_DOWN_SVG}
        </div>
      </div>

      <div id="tasks-current" class="task-div" ${currentTasks.length ? "" : "hidden"}>
        <h2 id="tasks-current-title" class="task-section-title">Current</h2>
        <ul id="tasks-current-body" class="task-list">
          ${currentTasks.map(renderTaskRow).join("")}
        </ul>
      </div>

      <div id="tasks-upcoming" class="task-div" ${upcomingTasks.length ? "" : "hidden"}>
        <h2 id="tasks-upcoming-title" class="task-section-title">Upcoming</h2>
        <ul id="tasks-upcoming-body" class="task-list">
          ${upcomingTasks.map(renderTaskRow).join("")}
        </ul>
      </div>

      <div id="tasks-finished" class="task-div" ${shownFinished.length ? "" : "hidden"}>
        <h2 id="tasks-finished-title" class="task-section-title">Finished</h2>
        <ul id="tasks-finished-body" class="task-list">
          ${shownFinished.map(renderTaskRow).join("")}
        </ul>
      </div>
    </div>
  `;

  const searchEl = container.querySelector("#task-search");
  searchEl?.addEventListener("input", () => {
    taskSearchQuery = searchEl.value.trim().toLowerCase();
    renderTasksView(container, state);
    const nextSearch = container.querySelector("#task-search");
    if (nextSearch) {
      nextSearch.focus();
      const len = nextSearch.value.length;
      nextSearch.setSelectionRange(len, len);
    }
  });

  const filterEl = container.querySelector("#task-type-filter");
  filterEl?.addEventListener("change", () => {
    taskTypeFilter = filterEl.value;
    renderTasksView(container, state);
  });

  for (const detailsEl of container.querySelectorAll("details.task-details")) {
    detailsEl.addEventListener("toggle", () => {
      const id = detailsEl.dataset.taskId;
      if (!id) return;
      if (detailsEl.open) {
        openTaskDetails.add(id);
      } else {
        openTaskDetails.delete(id);
      }
    });
  }

  container.scrollTop = prevScrollTop;
  container.onscroll = () => {
    if (!hasMoreFinished) return;
    if (
      container.scrollTop + container.clientHeight >=
      container.scrollHeight - 64
    ) {
      visibleFinishedCount += FINISHED_TASK_PAGE_SIZE;
      renderTasksView(container, state);
    }
  };
}
