/**
 * Tasks tab view for Arena Steering.
 */

import { escapeHtml } from "./markdown.js";
import { relativeTime } from "./timestamps.js";

const PLUS_SVG = `<svg class="lucide lucide-plus" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M5 12h14"></path><path d="M12 5v14"></path></svg>`;
const PENCIL_SVG = `<svg class="lucide lucide-pencil" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"></path><path d="m15 5 4 4"></path></svg>`;
const TRASH_SVG = `<svg class="lucide lucide-trash-2" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path><line x1="10" x2="10" y1="11" y2="17"></line><line x1="14" x2="14" y1="11" y2="17"></line></svg>`;
const LOCK_SVG = `<svg class="lucide lucide-lock" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>`;

const TASK_TYPES = ["code", "docs", "report", "ops", "misc"];
const TASK_STATUSES = ["upcoming", "in_progress", "finished"];

export function renderTasksView(container, state, handlers) {
  const tasks = state.tasks || [];
  const editingTaskId = state.editingTaskId || null;

  const cardsHtml = tasks.length
    ? tasks
        .map((task) => {
          const isEditing = editingTaskId === task.id;
          const detailsHtml = (task.details || []).length
            ? `<ul class="task-details">${task.details
                .map((d) => `<li>${escapeHtml(d)}</li>`)
                .join("")}</ul>`
            : `<p class="meta-pill">No details recorded.</p>`;

          const metaChips = [
            `<span class="meta-pill">type: ${escapeHtml(task.type)}</span>`,
            task.scope
              ? `<span class="meta-pill">scope: ${escapeHtml(task.scope)}</span>`
              : "",
            ...(task.deps || []).map(
              (dep) => `<span class="meta-pill">dep: ${escapeHtml(dep)}</span>`
            ),
            ...(task.report_ids || []).map(
              (rep) => `<span class="meta-pill">report: ${escapeHtml(rep)}</span>`
            ),
            ...(task.msg_ids || []).map(
              (mid) => `<span class="meta-pill">msg: ${escapeHtml(mid)}</span>`
            ),
          ]
            .filter(Boolean)
            .join("");

          const editBlock = isEditing
            ? `
              <form class="task-edit-form" data-task-id="${escapeHtml(task.id)}" style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                <input type="text" name="title" class="input" style="max-width: 260px;" value="${escapeHtml(task.title)}" aria-label="Task title" required>
                <input type="text" name="scope" class="input" style="max-width: 180px;" value="${escapeHtml(task.scope || "")}" placeholder="scope" aria-label="Task scope">
                <button type="submit" class="btn btn-primary">Save</button>
              </form>
            `
            : "";

          return `
            <article class="card" data-task-id="${escapeHtml(task.id)}">
              <div class="card-header">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <span class="meta-pill">${escapeHtml(task.id)}</span>
                  <h3 class="card-title">${escapeHtml(task.title)}</h3>
                  ${
                    task.blocked
                      ? `<span class="status-pill status-blocked pill-blocked" style="display: inline-flex; align-items: center; gap: 4px;">${LOCK_SVG} blocked</span>`
                      : ""
                  }
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <select class="select task-status-select" data-task-id="${escapeHtml(task.id)}" aria-label="Status for ${escapeHtml(task.id)}" style="width: auto;">
                    ${TASK_STATUSES.map(
                      (st) =>
                        `<option value="${st}" ${task.status === st ? "selected" : ""}>${st}</option>`
                    ).join("")}
                  </select>
                  <time class="meta-pill" datetime="${escapeHtml(task.modified_at)}" data-timestamp="${escapeHtml(task.modified_at)}">
                    ${escapeHtml(relativeTime(task.modified_at))}
                  </time>
                  <button type="button" class="icon-button task-edit-btn" data-edit-task="${escapeHtml(task.id)}" aria-label="Edit task ${escapeHtml(task.id)}" title="Edit task">${PENCIL_SVG}</button>
                  <button type="button" class="icon-button task-delete-btn" data-del-task="${escapeHtml(task.id)}" data-task-id="${escapeHtml(task.id)}" aria-label="Delete task ${escapeHtml(task.id)}" title="Delete task">${TRASH_SVG}</button>
                </div>
              </div>
              <div class="task-meta-row">${metaChips}</div>
              ${editBlock}
              ${detailsHtml}
            </article>
          `;
        })
        .join("")
    : `<div class="card"><p>No tasks in queue.</p></div>`;

  container.innerHTML = `
    <div class="card">
      <h2 class="card-title" style="margin-bottom: 12px;">Add Task</h2>
      <form id="task-create-form">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px;">
          <input type="text" class="input" id="task-id" placeholder="kebab-task-id" required>
          <input type="text" class="input" id="task-title" placeholder="Task title" required>
          <select class="select" id="task-type" aria-label="Task type">
            ${TASK_TYPES.map((t) => `<option value="${t}">${t}</option>`).join("")}
          </select>
          <input type="text" class="input" id="task-scope" placeholder="Scope (optional)">
        </div>
        <div class="composer-row">
          <input type="text" class="input" id="task-detail" placeholder="Initial detail line (optional)" style="max-width: 420px;">
          <button type="submit" id="btn-add-task" class="icon-button" aria-label="Add task" title="Add task">${PLUS_SVG}</button>
        </div>
      </form>
    </div>
    <div id="tasks-list">${cardsHtml}</div>
  `;

  const createForm = container.querySelector("#task-create-form");
  createForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const id = container.querySelector("#task-id").value.trim();
    const title = container.querySelector("#task-title").value.trim();
    const type = container.querySelector("#task-type").value;
    const scope = container.querySelector("#task-scope").value.trim();
    const detail = container.querySelector("#task-detail").value.trim();
    if (!id || !title) return;
    await handlers.onCreateTask({
      id,
      title,
      type,
      scope,
      details: detail ? [detail] : [],
    });
  });

  for (const select of container.querySelectorAll(".task-status-select")) {
    select.addEventListener("change", async () => {
      const taskId = select.dataset.taskId;
      await handlers.onPatchTask(taskId, { status: select.value });
    });
  }

  for (const editBtn of container.querySelectorAll("[data-edit-task]")) {
    editBtn.addEventListener("click", () => {
      const taskId = editBtn.dataset.editTask;
      handlers.onToggleEditTask?.(taskId);
    });
  }

  for (const editForm of container.querySelectorAll(".task-edit-form")) {
    editForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const taskId = editForm.dataset.taskId;
      const fd = new FormData(editForm);
      await handlers.onPatchTask(taskId, {
        title: String(fd.get("title") || "").trim(),
        scope: String(fd.get("scope") || "").trim(),
      });
    });
  }

  for (const btn of container.querySelectorAll("[data-del-task]")) {
    btn.addEventListener("click", async () => {
      const taskId = btn.dataset.delTask;
      await handlers.onDeleteTask(taskId, btn);
    });
  }
}
