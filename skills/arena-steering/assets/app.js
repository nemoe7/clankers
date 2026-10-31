import { createComposerUploads } from "./composer-uploads.js";
// Main ES module controller for Arena Steering.

import { api, connectWebSocket } from "./api.js";
import { expandMessageHistory, messageQueryKey, renderMessagesView, trackMessageAcks } from "./messages-view.js";
import {
  escapeHtml,
  highlightCodeBlocks,
  hydrateMermaidBlocks,
  toggleCodeMermaid,
} from "./markdown.js";
import { linkReferences } from "./references.js";
import { createModalManager } from "./modal.js";
import { renderReportsView } from "./reports-view.js";
import { createStore, writePendingSend } from "./state.js";
import { expandTaskTarget, renderTasksView } from "./tasks-view.js";
import { mountRelativeTimers, relativeTime } from "./timestamps.js";

const CHECK_SVG = `<svg class="lucide lucide-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"></path></svg>`;
const SURVEY_OK_SVG = `<svg class="lucide lucide-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"></path></svg>`;
const SURVEY_BAD_SVG = `<svg class="lucide lucide-x" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>`;
const SURVEY_WARN_SVG = `<svg class="lucide lucide-circle-question-mark" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><path d="M12 17h.01"></path></svg>`;
const CAPABILITY_LABELS = {
  R3S0N: "Reasoning",
  V1S0N: "Vision",
  S0R7D: "Sorted",
};

function formatSurveyFieldValue(val) {
  if (val && typeof val === "object" && !Array.isArray(val)) {
    const op = String(val.operator || "");
    if (op === "unknown") return "unknown";
    const symbol = op === "gt" ? ">" : op === "lt" ? "<" : "=";
    return `${symbol} ${val.value}`;
  }
  return String(val);
}

function renderAnswerTooltip(answer) {
  const entries = answer && typeof answer === "object" ? Object.entries(answer) : [];
  if (!entries.length) return "";
  return `<div class="survey-answer-tooltip" role="tooltip">${entries
    .map(
      ([k, v]) =>
        `<div class="survey-answer-row"><span class="survey-answer-key">${escapeHtml(k)}</span><span class="survey-answer-val">${escapeHtml(formatSurveyFieldValue(v))}</span></div>`,
    )
    .join("")}</div>`;
}

function renderSurveyModalContent(survey) {
  const results = Array.isArray(survey.results) ? survey.results : [];
  const checkedAt = survey.checked_at || survey.answered_at || "";
  if (results.length > 0) {
    const passed = results.filter((r) => r.correct === true).length;
    const capItems = results.filter((r) => r.id in CAPABILITY_LABELS);
    const calItems = results.filter((r) => !(r.id in CAPABILITY_LABELS));
    const subtitle = checkedAt
      ? `<p class="survey-subtitle muted">Answered <time datetime="${escapeHtml(checkedAt)}" data-timestamp="${escapeHtml(checkedAt)}">${escapeHtml(relativeTime(checkedAt))}</time> · ${passed} of ${results.length} verified</p>`
      : `<p class="survey-subtitle muted">${passed} of ${results.length} verified</p>`;
    const capHtml = capItems
      .map((item) => {
        const state = item.correct === true ? "ok" : item.correct === false ? "bad" : "warn";
        const icon = item.correct === true ? SURVEY_OK_SVG : item.correct === false ? SURVEY_BAD_SVG : SURVEY_WARN_SVG;
        const label = CAPABILITY_LABELS[item.id] || item.id;
        return `<div class="survey-cap-pill ${state}" tabindex="0"><span class="survey-status ${state}">${icon}</span><div class="survey-cap-text"><code>${escapeHtml(item.id)}</code><span class="survey-cap-label">${escapeHtml(label)}</span></div>${renderAnswerTooltip(item.answer)}</div>`;
      })
      .join("");
    const calRows = calItems
      .map((item) => {
        const state = item.correct === true ? "ok" : item.correct === false ? "bad" : "warn";
        const icon = item.correct === true ? SURVEY_OK_SVG : item.correct === false ? SURVEY_BAD_SVG : SURVEY_WARN_SVG;
        const entries = item.answer && typeof item.answer === "object" ? Object.entries(item.answer) : [];
        const knownCount = entries.filter(([, v]) => formatSurveyFieldValue(v).toLowerCase() !== "unknown").length;
        const fieldLabel = knownCount === 0 ? "unknown" : `${knownCount}/${entries.length} fields`;
        const pct = Math.max(0, Math.min(100, Math.round(Number(item.confidence || 0) * 100)));
        return `<tr>
          <td>
            <div class="survey-result-id">
              <span class="survey-status ${state}">${icon}</span>
              <span class="survey-id-wrap">
                <button type="button" class="survey-id-trigger"><code>${escapeHtml(item.id)}</code></button>
                ${renderAnswerTooltip(item.answer)}
              </span>
            </div>
          </td>
          <td><span class="survey-field-chip">${escapeHtml(fieldLabel)}</span></td>
          <td>
            <div class="survey-confidence" style="--confidence-pct: ${pct}%">
              <div class="survey-confidence-track"><span class="survey-confidence-fill"></span></div>
              <span class="survey-confidence-value">${pct}%</span>
            </div>
          </td>
        </tr>`;
      })
      .join("");
    return `${subtitle}
      <div>
        <p class="eyebrow survey-section-label">Deterministic checks</p>
        <div class="survey-cap-grid">${capHtml}</div>
      </div>
      <div>
        <p class="eyebrow survey-section-label">Knowledge calibration</p>
        <table class="survey-results">
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Fields</th>
              <th scope="col">Confidence</th>
            </tr>
          </thead>
          <tbody>${calRows}</tbody>
        </table>
      </div>`;
  }
  const questions = survey.questions || [];
  const answers = survey.answers || {};
  if (Object.keys(answers).length > 0 && questions.length > 0) {
    return questions
      .map((q) => {
        const ans = answers[q.id] || "(not answered yet)";
        return `<div class="survey-item"><p class="survey-item-prompt">${escapeHtml(q.prompt)}</p><p class="survey-item-answer">${escapeHtml(ans)}</p></div>`;
      })
      .join("");
  }
  return `<p class="muted">No survey submission recorded yet.</p>`;
}

const store = createStore();
const modal = createModalManager();
const reportCache = new Map();
const pendingReportLoads = new Map();
const ackSeenRequests = new Set();
let cleanupTimers = () => {};
let knownAssetVersion = null;
let reportedTimezone = null;
let lastDataSignature = "";
let lastViewportHeight = 0;

async function ensureReportCached(reportId, expectedModifiedAt = null, { quiet = false } = {}) {
  if (!reportId) return null;
  const cached = reportCache.get(reportId);
  if (
    cached &&
    (!expectedModifiedAt || cached.modified_at === expectedModifiedAt) &&
    Array.isArray(cached.report?.blocks)
  ) {
    return cached.report;
  }
  const loadKey = `${reportId}:${expectedModifiedAt || ""}`;
  if (pendingReportLoads.has(loadKey)) return pendingReportLoads.get(loadKey);
  const load = (async () => {
    if (!quiet) setLoading(true);
    try {
      const res = await api.getReport(reportId);
      if (res?.report) {
        reportCache.set(reportId, {
          modified_at: res.report.modified_at,
          report: res.report,
        });
        return res.report;
      }
      return null;
    } finally {
      if (!quiet) setLoading(false);
      pendingReportLoads.delete(loadKey);
    }
  })();
  pendingReportLoads.set(loadKey, load);
  return load;
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
  const panel = document.getElementById("view-reports");
  if (!panel) return;
  if (active) {
    loadingCount += 1;
    if (loadingDoneTimer) {
      clearTimeout(loadingDoneTimer);
      loadingDoneTimer = null;
    }
    if (panel.getAttribute("data-loading") !== "true") {
      loadingStartAt = Date.now();
      panel.setAttribute("data-loading", "true");
    }
  } else {
    loadingCount = Math.max(0, loadingCount - 1);
    if (loadingCount === 0) {
      const elapsed = Date.now() - loadingStartAt;
      if (elapsed >= 200) {
        panel.setAttribute("data-loading", "done");
        loadingDoneTimer = setTimeout(() => {
          if (
            loadingCount === 0 &&
            panel.getAttribute("data-loading") === "done"
          ) {
            panel.setAttribute("data-loading", "false");
          }
        }, 220);
      } else {
        panel.setAttribute("data-loading", "false");
      }
    }
  }
}

let messageEpoch = 0;
let olderPageRequest = null;
let loadedMessageKey = null;
let historyCache = null;
let searchBase = null;

export function messageMatchesQuery(message, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return true;
  const haystacks = [message.id, message.body, ...(message.parent_ids || []), ...(message.acks || [])];
  return haystacks.some((item) => String(item || "").toLowerCase().includes(needle));
}

async function fetchMessagePage({ before = "", reset = false } = {}) {
  const state = store.getState();
  const key = messageQueryKey(state);
  // A routine refresh must not invalidate a slower pagination request. Apply
  // the latest changes immediately after the older page finishes instead.
  if (!before && !reset && olderPageRequest?.key === key) {
    olderPageRequest.refreshRequested = true;
    return state.messages || [];
  }
  const epoch = ++messageEpoch;
  const previous = reset || loadedMessageKey !== key ? [] : [...(state.messages || [])];
  if (reset || loadedMessageKey !== key) {
    loadedMessageKey = key;
    store.setState({ messages: [], messagesHasMore: false, messagesError: "", messagesLoading: true });
  }
  try {
    const options = { all: true, hidden: Boolean(state.showHidden), query: (state.searchQuery || "").trim() };
    const result = await api.listMessages({ ...options, before });
    if (epoch !== messageEpoch || messageQueryKey(store.getState()) !== key) return null;
    let fresh = result.messages || [];
    let hasMore = result.has_more;
    if (!before && previous.length) {
      while (hasMore && fresh.length < previous.length) {
        const older = await api.listMessages({ ...options, before: fresh[0].id });
        if (epoch !== messageEpoch || messageQueryKey(store.getState()) !== key) return null;
        fresh = [...(older.messages || []), ...fresh];
        hasMore = older.has_more;
      }
    }
    const ids = new Set(fresh.map((item) => item.id));
    const merged = before
      ? [...fresh, ...previous.filter((item) => !ids.has(item.id))]
      : fresh;
    const current = store.getState();
    if (current.messagesHasMore !== hasMore || current.messagesError || current.messagesLoading ||
        JSON.stringify(current.messages) !== JSON.stringify(merged)) {
      store.setState({ messages: merged, messagesHasMore: hasMore, messagesError: "", messagesLoading: false });
    }
    const activeQuery = (store.getState().searchQuery || "").trim().toLowerCase();
    if (activeQuery && !before) {
      searchBase = { query: activeQuery, messages: merged, hasMore };
    }
    return merged;
  } catch (error) {
    if (epoch === messageEpoch && messageQueryKey(store.getState()) === key) {
      store.setState({ messagesError: `Could not load messages: ${error.message}`, messagesLoading: false });
    }
    return null;
  }
}

async function refreshAll(force = false) {
  try {
    const curState = store.getState();
    const [health, msgRes, taskRes, repRes] = await Promise.all([
      api.getHealth(),
      fetchMessagePage(),
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
    const browserTimezone =
      Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    if (
      browserTimezone &&
      health.timezone !== browserTimezone &&
      reportedTimezone !== browserTimezone
    ) {
      reportedTimezone = browserTimezone;
      api.setTimezone(browserTimezone).catch(() => {
        reportedTimezone = null;
      });
    }
    const messages = msgRes || store.getState().messages || [];
    const tasks = taskRes.tasks || [];
    const reportSummaries = repRes.reports || [];
    const survey = health.survey || {};
    trackMessageAcks(messages.filter((msg) => curState.showHidden || !msg.hidden));
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
    const replyParentIds = curState.replyParentIds || [];
    const nextSignature = JSON.stringify({
      messages,
      tasks,
      reports,
      survey,
      selectedReportId,
      replyParentIds,
      showHidden: Boolean(curState.showHidden),
    });
    if (!force && nextSignature === lastDataSignature) {
      return;
    }
    lastDataSignature = nextSignature;
    store.setState({
      tasks,
      reports,
      survey,
      selectedReportId,
      replyParentIds,
    });
  } catch (err) {
    console.error(err);
  }
}

const composerUploads = createComposerUploads(store, (file) => api.uploadFile(file));

const handlers = {
  async onSendMessage(payload) {
    let pending = store.getState().pendingSend;
    if (store.getState().sending) throw new Error("A send is already in progress");
    const content = { body: payload.body, parent_ids: payload.parent_ids || [], attachments: payload.attachments || [] };
    if (pending && JSON.stringify(pending.content) !== JSON.stringify(content)) {
      throw new Error("Retry the unconfirmed send before sending changes");
    }
    if (!pending) {
      pending = { request_id: crypto.randomUUID(), content, rawDraft: payload.rawDraft, attachmentIds: payload.attachmentIds || [] };
      writePendingSend(pending);
    }
    store.setState({ pendingSend: pending, sending: true });
    try {
      const request = { ...pending.content, request_id: pending.request_id };
      if (request.attachments.length) {
        await api.sendMessageWithFile(request);
        composerUploads.clearSent(pending.attachmentIds);
      } else {
        await api.sendMessage(request);
      }
      if (JSON.stringify(store.getState().replyParentIds || []) === JSON.stringify(request.parent_ids)) {
        store.setState({ replyParentIds: [] });
      }
      writePendingSend(null);
      store.setState({ pendingSend: null, sending: false });
    } catch (error) {
      store.setState({ sending: false });
      throw error;
    }
    await refreshAll(true);
  },
  onDiscardPendingSend() {
    writePendingSend(null);
    store.setState({ pendingSend: null });
  },
  async onNavigateReference(type, id) {
    if (!id) return;
    try {
      const current = store.getState();
      if (type === "message") {
        let target = (current.messages || []).find((item) => item.id === id);
        if (!target) target = (await api.getMessage(id)).message;
        if (!target) throw new Error("Message not found");
        expandMessageHistory();
        const latest = store.getState();
        store.setState({ activeTab: "messages", searchQuery: "", showHidden: latest.showHidden || target.hidden,
          messages: (latest.messages || []).some((item) => item.id === id) ? latest.messages : [...(latest.messages || []), target] });
      } else if (type === "task") {
        let target = (current.tasks || []).find((item) => item.id === id);
        if (!target) target = (await api.getTask(id)).task;
        if (!target) throw new Error("Task not found");
        expandTaskTarget(id);
        const latest = store.getState();
        store.setState({ activeTab: "tasks", tasks: (latest.tasks || []).some((item) => item.id === id) ? latest.tasks : [...(latest.tasks || []), target] });
      } else if (type === "report") {
        let target = (current.reports || []).find((item) => item.id === id);
        if (!target) target = (await api.getReport(id)).report;
        if (!target) throw new Error("Report not found");
        if (!(current.reports || []).some((item) => item.id === id)) {
          store.setState({ reports: [...(current.reports || []), target] });
        }
        store.setState({ activeTab: "reports" });
        await handlers.onSelectReport(id);
        return;
      } else return;
      const selector = type === "message" ? `.message[data-msg-id="${CSS.escape(id)}"]` : `.task[data-task-id="${CSS.escape(id)}"]`;
      const row = document.querySelector(selector);
      row?.scrollIntoView({ behavior: "smooth", block: "center" });
      if (row) {
        row.dataset.highlight = "true";
        setTimeout(() => { if (row.isConnected) delete row.dataset.highlight; }, 1200);
      }
    } catch (error) {
      console.error(error);
      window.alert(`Could not open ${type} ${id}.`);
    }
  },
  async onMarkRepliesSeen(id, revision) {
    try {
      await api.markRepliesSeen(id, revision);
    } catch (error) {
      if (!String(error.message).includes("(409)")) console.error(error);
    }
    await refreshAll(true);
  },
  onStageComposerFiles(files) {
    return composerUploads.stage(files);
  },
  onRetryComposerAttachment(id) {
    return composerUploads.retry(id);
  },
  onRemoveComposerAttachment(id) {
    composerUploads.remove(id);
  },
  onToggleComposerExpanded() {
    store.setState({
      composerExpanded: !store.getState().composerExpanded,
    });
  },
  onToggleReplyParent(parentId) {
    if (!parentId) return;
    const current = store.getState().replyParentIds || [];
    const next = current.includes(parentId)
      ? current.filter((id) => id !== parentId)
      : [...current, parentId];
    store.setState({ replyParentIds: next });
  },
  async onSkipPoll() {
    await api.skipPoll();
  },
  async onToggleHidden() {
    const nextHidden = !store.getState().showHidden;
    historyCache = null;
    store.setState({ showHidden: nextHidden });
    await fetchMessagePage({ reset: true });
  },
  onSearchChange(query) {
    const state = store.getState();
    const wasSearching = Boolean((state.searchQuery || "").trim());
    const searching = Boolean(query.trim());
    if (!wasSearching && searching) {
      historyCache = { messages: [...(state.messages || [])], hasMore: state.messagesHasMore };
    }
    store.setState({ searchQuery: query });
    if (wasSearching && !searching && historyCache) {
      searchBase = null;
      loadedMessageKey = messageQueryKey(store.getState());
      store.setState({ messages: historyCache.messages, messagesHasMore: historyCache.hasMore, messagesError: "" });
      historyCache = null;
      fetchMessagePage();
      return;
    }
    const needle = query.trim().toLowerCase();
    if (searchBase && needle.startsWith(searchBase.query)) {
      messageEpoch += 1;
      loadedMessageKey = messageQueryKey(store.getState());
      store.setState({
        messages: searchBase.messages.filter((item) => messageMatchesQuery(item, needle)),
        messagesHasMore: searchBase.hasMore,
        messagesError: "",
        messagesLoading: false,
      });
      return;
    }
    searchBase = null;
    fetchMessagePage({ reset: true });
  },
  async onLoadOlderMessages() {
    const state = store.getState();
    const key = messageQueryKey(state);
    if (olderPageRequest?.key === key || !state.messagesHasMore || !state.messages.length) return;
    const request = { key, refreshRequested: false };
    olderPageRequest = request;
    try {
      await fetchMessagePage({ before: state.messages[0].id });
    } finally {
      if (olderPageRequest === request) olderPageRequest = null;
      if (request.refreshRequested && messageQueryKey(store.getState()) === key) {
        refreshAll(true);
      }
    }
  },
  async onOpenSurvey(trigger) {
    const res = await api.getSurvey().catch(() => ({ survey: store.getState().survey || {} }));
    const survey = res.survey || {};
    const rowsHtml = renderSurveyModalContent(survey);
    const decision = await modal.open("survey-results", {
      title: "Survey Verification",
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

function maybeMarkAckSeen(report) {
  if (!report || report.ack_seen) return;
  const answers = report.answers || [];
  const latest = answers[answers.length - 1];
  if (!latest || latest.status !== "acked") return;
  const key = `${report.id}:${latest.id}:${(latest.acks || []).length}`;
  if (ackSeenRequests.has(key)) return;
  ackSeenRequests.add(key);
  api
    .markReportAckSeen(report.id)
    .then((res) => {
      if (res?.report) {
        reportCache.set(report.id, {
          modified_at: res.report.modified_at,
          report: res.report,
        });
        const hydrated = hydrateReportsWithCache(store.getState().reports || []);
        store.setState({ reports: hydrated });
      }
    })
    .catch(() => {
      ackSeenRequests.delete(key);
    });
}

function handleReportAcked(event) {
  const report = event?.report;
  if (!report?.id) {
    refreshAll(false);
    return;
  }
  reportCache.set(report.id, {
    modified_at: report.modified_at,
    report,
  });
  const reports = store.getState().reports || [];
  const nextReports = reports.some((r) => r.id === report.id)
    ? reports.map((r) => (r.id === report.id ? report : r))
    : [...reports, report];
  lastDataSignature = "";
  store.setState({ reports: nextReports });
}

function reportNeedsAttention(report) {
  if (!report || report.status === "dismissed") return false;
  const notYetSeen = !report.seen;
  const hasUnansweredFields = Boolean(
    report.needs_answer ??
      ((report.fields || []).length > 0 && (report.answers || []).length === 0)
  );
  const answers = report.answers || [];
  const latest = answers[answers.length - 1];
  const hasUnseenAck = latest?.status === "acked" && !report.ack_seen;
  return notYetSeen || hasUnansweredFields || hasUnseenAck;
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

  const messagesEl = document.getElementById("view-messages");
  const tasksEl = document.getElementById("view-tasks");
  const reportsEl = document.getElementById("view-reports");

  if (messagesEl) messagesEl.hidden = state.activeTab !== "messages";
  if (tasksEl) tasksEl.hidden = state.activeTab !== "tasks";
  if (reportsEl) reportsEl.hidden = state.activeTab !== "reports";

  if (state.activeTab === "messages" && messagesEl) {
    renderMessagesView(messagesEl, state, handlers);
    highlightCodeBlocks(messagesEl);
    hydrateMermaidBlocks(messagesEl);
  } else if (state.activeTab === "tasks" && tasksEl) {
    renderTasksView(tasksEl, state, handlers);
  } else if (state.activeTab === "reports" && reportsEl) {
    renderReportsView(reportsEl, state, handlers);
    highlightCodeBlocks(reportsEl);
    hydrateMermaidBlocks(reportsEl);
    maybeMarkAckSeen(reports.find((r) => r.id === state.selectedReportId));
  }

  const activeView = { messages: messagesEl, tasks: tasksEl, reports: reportsEl }[state.activeTab];
  if (activeView) linkReferences(activeView, state);
  cleanupTimers = mountRelativeTimers(document);
}

function initImageModal() {
  const dialog = document.getElementById("image-modal");
  const stage = document.getElementById("image-modal-stage");
  const close = document.getElementById("image-modal-close");
  if (!dialog || !stage || !close) return;
  let scale = 1;
  let x = 0;
  let y = 0;
  let drag = null;
  let panDistance = 0;
  let viewerSeq = 0;
  const pointers = new Map();
  let pinch = null;
  const pinchDistance = () => {
    const [a, b] = [...pointers.values()];
    return Math.hypot(a.x - b.x, a.y - b.y) || 1;
  };
  const update = () => {
    const media = stage.firstElementChild;
    if (media) media.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
  };
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    stage.replaceChildren();
    drag = null;
    pointers.clear();
    pinch = null;
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog || (event.target === stage && panDistance <= 4)) dialog.close();
  });
  stage.addEventListener("dragstart", (event) => event.preventDefault());
  stage.addEventListener("wheel", (event) => {
    event.preventDefault();
    scale = Math.min(8, Math.max(0.25, scale * Math.exp(-event.deltaY * 0.001)));
    update();
  }, { passive: false });
  stage.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.size === 2) {
      drag = null;
      pinch = { distance: pinchDistance(), scale };
      panDistance = Number.POSITIVE_INFINITY;
      return;
    }
    drag = {
      pointer: event.pointerId,
      x: event.clientX - x,
      y: event.clientY - y,
      startX: event.clientX,
      startY: event.clientY,
    };
    panDistance = 0;
    stage.setPointerCapture(event.pointerId);
  });
  stage.addEventListener("pointermove", (event) => {
    if (!pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pinch && pointers.size >= 2) {
      scale = Math.min(8, Math.max(0.25, (pinch.scale * pinchDistance()) / pinch.distance));
      update();
      return;
    }
    if (!drag || drag.pointer !== event.pointerId) return;
    panDistance = Math.max(
      panDistance,
      Math.abs(event.clientX - drag.startX) + Math.abs(event.clientY - drag.startY),
    );
    x = event.clientX - drag.x;
    y = event.clientY - drag.y;
    update();
  });
  const endDrag = (event) => {
    pointers.delete(event.pointerId);
    if (pointers.size < 2) pinch = null;
    if (drag?.pointer === event.pointerId) drag = null;
  };
  stage.addEventListener("pointerup", endDrag);
  stage.addEventListener("pointercancel", endDrag);
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!target.closest?.("#view-messages, #view-reports")) return;
    const media = target.closest(".mermaid-diagram svg, .mermaid-block svg, img");
    if (!media) return;
    event.preventDefault();
    scale = 1;
    x = 0;
    y = 0;
    const clone = media.cloneNode(true);
    const sourceId = clone.getAttribute("id");
    clone.removeAttribute("id");
    clone.setAttribute("draggable", "false");
    if (media.tagName.toLowerCase() === "svg") {
      const sourceBox = media.getBoundingClientRect();
      clone.setAttribute("class", "mermaid-svg");
      if (sourceBox.width) clone.style.width = `${Math.round(sourceBox.width)}px`;
      // Mermaid scopes its embedded styles to the diagram ID, so the copy keeps a unique one.
      if (sourceId) {
        const viewerId = `${sourceId}-viewer-${++viewerSeq}`;
        clone.setAttribute("id", viewerId);
        const style = clone.querySelector("style");
        if (style) style.textContent = style.textContent.split(`#${sourceId}`).join(`#${viewerId}`);
      }
    }
    stage.replaceChildren(clone);
    update();
    dialog.showModal();
  });
}

function initEvents() {
  initImageModal();
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

  const preloadReport = (event) => {
    const target = event.target.closest?.(".report-picker-link[data-report-id], [data-reference-type=report]");
    const reportId = target?.dataset.reportId || target?.dataset.referenceId;
    if (!reportId) return;
    const summary = (store.getState().reports || []).find((item) => item.id === reportId);
    ensureReportCached(reportId, summary?.modified_at, { quiet: true }).catch(console.error);
  };
  document.addEventListener("pointerover", preloadReport);
  document.addEventListener("focusin", preloadReport);

  document.addEventListener("click", async (event) => {
    const reference = event.target.closest?.("[data-reference-type]");
    if (reference) {
      await handlers.onNavigateReference(reference.dataset.referenceType, reference.dataset.referenceId);
      return;
    }
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
    const receiptChip = event.target.closest?.("code.msg-id.receipt-id");
    if (receiptChip) {
      const parentId = (
        receiptChip.dataset.msgId ||
        receiptChip.textContent ||
        ""
      ).trim();
      if (!event.shiftKey) {
        handlers.onToggleReplyParent(parentId);
        return;
      }
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(parentId).catch(() => {});
      }
      receiptChip.dataset.state = "good";
      setTimeout(() => {
        if (receiptChip.isConnected) {
          delete receiptChip.dataset.state;
        }
      }, 1000);
      return;
    }
    const msgChip = event.target.closest?.("code.msg-id");
    if (msgChip) {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard
          .writeText(msgChip.textContent || "")
          .catch(() => {});
      }
      msgChip.dataset.state = "good";
      setTimeout(() => {
        if (msgChip.isConnected) {
          delete msgChip.dataset.state;
        }
      }, 1000);
    }
  });
}

store.subscribe(renderApp);
initEvents();
refreshAll(true);
// Finished runs reach the client as a change event from the server, so no task polling remains.

connectWebSocket({
  onChange: () => refreshAll(false),
  onReload: () => window.location.reload(),
  onReportAcked: handleReportAcked,
});
