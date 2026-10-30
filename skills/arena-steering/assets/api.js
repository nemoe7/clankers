// REST and WebSocket client for Arena Steering endpoints.
// Relative paths keep the preview proxy working from any browser origin.

let liveSocket = null;
let socketSequence = 0;
let lastSocketMessage = 0;
let socketRetry = null;
const socketCalls = new Map();
let changeHandler = () => {};
let reloadHandler = () => {};
let reportAckedHandler = () => {};
let disconnectPollTimer = null;

function startFallbackPoll() {
  if (disconnectPollTimer) return;
  disconnectPollTimer = setInterval(() => {
    if (!liveSocket || liveSocket.readyState !== 1) {
      changeHandler();
    }
  }, 3000);
}

function stopFallbackPoll() {
  if (disconnectPollTimer) {
    clearInterval(disconnectPollTimer);
    disconnectPollTimer = null;
  }
}

export function connectWebSocket({ onChange, onReload, onReportAcked } = {}) {
  if (typeof onChange === "function") changeHandler = onChange;
  if (typeof onReload === "function") reloadHandler = onReload;
  if (typeof onReportAcked === "function") reportAckedHandler = onReportAcked;
  if (
    typeof WebSocket !== "function" ||
    (liveSocket && liveSocket.readyState < 2)
  ) {
    startFallbackPoll();
    return;
  }
  const url = new URL(window.location.href);
  if (url.searchParams.get("transport") === "poll") {
    startFallbackPoll();
    return;
  }
  url.pathname = "/api/ws";
  url.search = "";
  url.hash = "";
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  let socket;
  try {
    socket = new WebSocket(url);
  } catch {
    startFallbackPoll();
    return;
  }
  liveSocket = socket;
  const deadline = setTimeout(() => socket.close(), 10000);
  socket.addEventListener("open", () => {
    clearTimeout(deadline);
    lastSocketMessage = Date.now();
    stopFallbackPoll();
    changeHandler();
  });
  socket.addEventListener("message", (event) => {
    if (liveSocket !== socket) return;
    try {
      const value = JSON.parse(event.data);
      lastSocketMessage = Date.now();
      if (value.type === "heartbeat") {
        socket.send(JSON.stringify({ type: "pong" }));
        return;
      }
      if (value.type === "change") {
        changeHandler();
        return;
      }
      if (value.type === "report.acked") {
        reportAckedHandler(value);
        return;
      }
      if (value.type === "reload") {
        reloadHandler();
        return;
      }
      if (value.type !== "response") {
        throw new Error("Unknown WebSocket message");
      }
      const pending = socketCalls.get(value.id);
      if (!pending) return;
      socketCalls.delete(value.id);
      clearTimeout(pending.timer);
      const payload =
        typeof value.body === "string" && value.body
          ? JSON.parse(value.body)
          : {};
      if (value.status < 200 || value.status >= 300) {
        pending.reject(
          new Error(payload.error || `Request failed (${value.status})`)
        );
      } else {
        pending.resolve(payload);
      }
    } catch {
      socket.close(1002);
    }
  });
  socket.addEventListener("error", () => socket.close());
  socket.addEventListener("close", () => {
    clearTimeout(deadline);
    if (liveSocket !== socket) return;
    liveSocket = null;
    for (const pending of socketCalls.values()) {
      clearTimeout(pending.timer);
      pending.reject(new TypeError("WebSocket closed before a reply"));
    }
    socketCalls.clear();
    startFallbackPoll();
    clearTimeout(socketRetry);
    socketRetry = setTimeout(
      () =>
        connectWebSocket({
          onChange: changeHandler,
          onReload: reloadHandler,
          onReportAcked: reportAckedHandler,
        }),
      1000
    );
  });
}

setInterval(() => {
  if (liveSocket?.readyState === 1 && Date.now() - lastSocketMessage > 30000) {
    liveSocket.close();
  }
}, 5000);

function socketRequest(method, path, bodyStr, timeoutMs = 15000) {
  const socket = liveSocket;
  const id = String(++socketSequence);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      socketCalls.delete(id);
      reject(new TypeError("WebSocket reply timed out"));
      socket.close();
    }, timeoutMs);
    socketCalls.set(id, { resolve, reject, timer });
    try {
      socket.send(
        JSON.stringify({
          id,
          path,
          method,
          headers: { "Content-Type": "application/json" },
          body: bodyStr || "",
        })
      );
    } catch (error) {
      socketCalls.delete(id);
      clearTimeout(timer);
      reject(error);
      socket.close();
    }
  });
}

async function requestJson(method, path, body = undefined) {
  const bodyStr = body !== undefined ? JSON.stringify(body) : undefined;
  if (liveSocket?.readyState === 1) {
    try {
      return await socketRequest(method, path, bodyStr);
    } catch {
      // Fall back to HTTP fetch if socket closed mid-flight.
    }
  }
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (bodyStr !== undefined) {
    options.body = bodyStr;
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
  listReports({ stale = false, summary = false } = {}) {
    const params = { stale: stale ? "1" : "0" };
    if (summary) params.summary = "1";
    const q = new URLSearchParams(params);
    return requestJson("GET", `/reports?${q.toString()}`);
  },
  getReport(reportId) {
    return requestJson("GET", `/reports/${encodeURIComponent(reportId)}`);
  },
  renderMarkdown(markdown, { breaks = true } = {}) {
    return requestJson("POST", "/markdown", { markdown, breaks });
  },
  dismissReport(reportId) {
    return requestJson("DELETE", `/reports/${encodeURIComponent(reportId)}`);
  },
  markReportSeen(reportId) {
    return requestJson(
      "POST",
      `/reports/${encodeURIComponent(reportId)}/seen`,
      {}
    );
  },
  markReportAckSeen(reportId) {
    return requestJson(
      "POST",
      `/reports/${encodeURIComponent(reportId)}/ack-seen`,
      {}
    );
  },
  submitReportAnswer(reportId, values) {
    return requestJson(
      "POST",
      `/reports/${encodeURIComponent(reportId)}/answers`,
      { values }
    );
  },
  getSurvey() {
    return requestJson("GET", "/survey");
  },
  submitSurvey(answers) {
    return requestJson("POST", "/survey", { answers });
  },
  triggerBibleCheck(active = undefined) {
    const body = active === undefined ? {} : { active: Boolean(active) };
    return requestJson("POST", "/survey/interrupt", body);
  },
};
