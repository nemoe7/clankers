/**
 * REST client for Arena Steering endpoints.
 * All requests use relative paths so the preview proxy works from any browser origin.
 */

async function requestJson(method, path, body = undefined) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return payload;
}

export const api = {
  getHealth() {
    return requestJson("GET", "/health");
  },
  listMessages({ all = true, hidden = false } = {}) {
    const q = new URLSearchParams({
      all: all ? "1" : "0",
      hidden: hidden ? "1" : "0",
    });
    return requestJson("GET", `/messages?${q.toString()}`);
  },
  sendMessage({ body, hidden = false, blocking = true }) {
    return requestJson("POST", "/messages", { body, hidden, blocking });
  },
  skipPoll() {
    return requestJson("POST", "/poll/skip", {});
  },
  listTasks({ full = true } = {}) {
    const q = new URLSearchParams({ full: full ? "1" : "0" });
    return requestJson("GET", `/tasks?${q.toString()}`);
  },
  createTask(task) {
    return requestJson("POST", "/tasks", task);
  },
  patchTask(taskId, changes) {
    return requestJson("PATCH", `/tasks/${encodeURIComponent(taskId)}`, changes);
  },
  deleteTask(taskId) {
    return requestJson("DELETE", `/tasks/${encodeURIComponent(taskId)}`);
  },
  listReports({ stale = false } = {}) {
    const q = new URLSearchParams({ stale: stale ? "1" : "0" });
    return requestJson("GET", `/reports?${q.toString()}`);
  },
  getReport(reportId) {
    return requestJson("GET", `/reports/${encodeURIComponent(reportId)}`);
  },
  dismissReport(reportId) {
    return requestJson("DELETE", `/reports/${encodeURIComponent(reportId)}`);
  },
  submitReportAnswer(reportId, values) {
    return requestJson(
      "POST",
      `/reports/${encodeURIComponent(reportId)}/answers`,
      { values }
    );
  },
};
