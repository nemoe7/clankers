// Reactive UI store for Arena Steering.

const TAB_STORAGE_KEY = "steer:activeTab";
const REPORT_STORAGE_KEY = "steer:selectedReportId";
const VALID_TABS = new Set(["messages", "tasks", "reports"]);

function readSessionValue(key) {
  try {
    return typeof sessionStorage !== "undefined" ? sessionStorage.getItem(key) : null;
  } catch {
    return null;
  }
}

function writeSessionValue(key, value) {
  try {
    if (typeof sessionStorage === "undefined") return;
    if (value == null || value === "") {
      sessionStorage.removeItem(key);
    } else {
      sessionStorage.setItem(key, String(value));
    }
  } catch {
    // Ignore storage quota or privacy-mode errors.
  }
}

export function createStore(initial = {}) {
  const savedTab = readSessionValue(TAB_STORAGE_KEY);
  const savedReportId = readSessionValue(REPORT_STORAGE_KEY);
  const state = {
    activeTab: VALID_TABS.has(savedTab) ? savedTab : "messages",
    messages: [],
    tasks: [],
    reports: [],
    selectedReportId: savedReportId || null,
    ...initial,
  };
  const listeners = new Set();

  return {
    getState() {
      return state;
    },
    setState(patch) {
      Object.assign(state, typeof patch === "function" ? patch(state) : patch);
      if (VALID_TABS.has(state.activeTab)) {
        writeSessionValue(TAB_STORAGE_KEY, state.activeTab);
      }
      if (state.selectedReportId !== undefined) {
        writeSessionValue(REPORT_STORAGE_KEY, state.selectedReportId);
      }
      for (const listener of listeners) {
        listener(state);
      }
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
