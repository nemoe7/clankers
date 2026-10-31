// Reactive UI store for Arena Steering.

const TAB_STORAGE_KEY = "steer:activeTab";
const REPORT_STORAGE_KEY = "steer:selectedReportId";
const DRAFT_STORAGE_KEY = "steer:messageDraft";
const PENDING_SEND_KEY = "steer:pendingSend";
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

export function readComposerDraft() {
  try {
    if (typeof localStorage !== "undefined") {
      const draft = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (draft !== null) return draft;
    }
  } catch {
    // Fall back to the current tab when local storage is unavailable.
  }
  return readSessionValue(DRAFT_STORAGE_KEY) || "";
}

export function writeComposerDraft(value) {
  try {
    if (typeof localStorage !== "undefined") {
      if (value) localStorage.setItem(DRAFT_STORAGE_KEY, String(value));
      else localStorage.removeItem(DRAFT_STORAGE_KEY);
      writeSessionValue(DRAFT_STORAGE_KEY, null);
      return;
    }
  } catch {
    // Fall back to the current tab when local storage is unavailable.
  }
  writeSessionValue(DRAFT_STORAGE_KEY, value);
}

export function readPendingSend() {
  try {
    const value = JSON.parse(readSessionValue(PENDING_SEND_KEY) || "null");
    return value && typeof value.request_id === "string" && value.content && typeof value.rawDraft === "string" && Array.isArray(value.attachmentIds) ? value : null;
  } catch {
    return null;
  }
}

export function writePendingSend(value) {
  writeSessionValue(PENDING_SEND_KEY, value ? JSON.stringify(value) : null);
}

export function createStore(initial = {}) {
  const savedTab = readSessionValue(TAB_STORAGE_KEY);
  const savedReportId = readSessionValue(REPORT_STORAGE_KEY);
  const state = {
    activeTab: VALID_TABS.has(savedTab) ? savedTab : "messages",
    messages: [],
    searchQuery: "",
    messagesHasMore: false,
    messagesError: "",
    messagesLoading: false,
    tasks: [],
    reports: [],
    replyParentIds: [],
    composerAttachments: [],
    composerExpanded: false,
    composerError: "",
    pendingSend: readPendingSend(),
    sending: false,
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
