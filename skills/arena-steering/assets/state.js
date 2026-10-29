/**
 * Reactive UI store for Arena Steering.
 */

export function createStore(initial = {}) {
  const state = {
    activeTab: "inbox",
    messages: [],
    tasks: [],
    reports: [],
    selectedReportId: null,
    ...initial,
  };
  const listeners = new Set();

  return {
    getState() {
      return state;
    },
    setState(patch) {
      Object.assign(state, typeof patch === "function" ? patch(state) : patch);
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
