'use strict';
const $ = selector => document.querySelector(selector);
const note = $('#note');
const send = $('#send');
const compose = $('#compose');
const expandComposer = $('#composer-expand');
const status = $('#send-status');
const key = 'arena-preview-v1';
// Text above either paste limit becomes one attachment.
const PASTE_LINE_LIMIT = 15;
const PASTE_CHAR_LIMIT = 1500;
const BINARY_TIMEOUT = 600_000;
let pending = null;
let stateBusy = null;
let stateAgain = false;
let reportRequest = 0;
let listSignature = '';
let lastState = null;
// Pending writes project over the latest poll, without changing its trusted server records.
const optimisticState = new Map();
let pollCommits = null;
function getState() {
  if (!lastState || !optimisticState.size) return lastState;
  const state = JSON.parse(JSON.stringify(lastState));
  for (const entry of optimisticState.values()) entry.apply(state);
  return state;
}
async function optimisticWrite(apply, write, commit = apply, echo = null) {
  const key = {};
  const entry = { apply };
  optimisticState.set(key, entry);
  try {
    renderState();
    const result = await write();
    if (lastState) commit(lastState, result);
    if (pollCommits) pollCommits.push(state => commit(state, result));
    if (echo) {
      entry.apply = state => commit(state, result);
      entry.echo = state => echo(state, result);
    }
    return result;
  } finally {
    if (!entry.echo) optimisticState.delete(key);
    renderState();
  }
}
function updateJob(id, updates) {
  return (state, result) => {
    const job = (state.fetch_jobs || []).find(item => item.id === id);
    if (job) Object.assign(job, result || updates);
  };
}
function writeHeaders(type) {
  return { 'Content-Type': type };
}
// Six characters name a note in the log whole, so the mint carries no tail. A clash keeps the
// earlier record, so the mint steps past every ID the state in hand shows.
function newId() {
  const seen = new Set();
  const collect = value => {
    if (!value || typeof value !== 'object') return;
    if (typeof value.id === 'string') seen.add(value.id);
    for (const child of Object.values(value)) collect(child);
  };
  collect(lastState);
  for (let step = 0; step < 8; step += 1) {
    const candidate = crypto.randomUUID().replaceAll('-', '').slice(0, 6);
    if (!seen.has(candidate)) return candidate;
  }
  return crypto.randomUUID().replaceAll('-', '').slice(0, 6);
}
let historySignature = '';
let draftPreviewSequence = 0;
let draftVersion = 0;
let fetchSignature = '';
let fetchBusy = false;
const messageNodes = new Map();
// Only the newest page of the log renders on load. Scrolling up renders the next older page,
// so a long session does not pay for every message at once.
const HISTORY_PAGE = 20;
let historyShown = HISTORY_PAGE;
// Filters can shorten the log and clamp its scroll position, then leave the next view at the first message.
// Restore the end when the owner followed it. Otherwise preserve the position they chose.
let logPinned = true;
const historyAtEnd = history =>
  history.scrollHeight - history.scrollTop - history.clientHeight < 80;

function stored(name) {
  try { return localStorage.getItem(`${key}:${name}`); }
  catch { return null; }
}
/*! @license Lucide 1.59.0 - ISC. Copyright (c) 2026 Lucide Icons and Contributors. See lucide.LICENSE for this and the Feather MIT license. Markdown mark: Simple Icons (CC0-1.0). */

// One table holds each shape a control can swap in, matching its static twin in index.html.
const SVG_NS = 'http://www.w3.org/2000/svg';
const ICONS = {
  'minimize-2': [['path', { d: 'm14 10 7-7' }], ['path', { d: 'M20 10h-6V4' }], ['path', { d: 'm3 21 7-7' }], ['path', { d: 'M4 14h6v6' }]],
  'maximize-2': [['path', { d: 'M15 3h6v6' }], ['path', { d: 'm21 3-7 7' }], ['path', { d: 'm3 21 7-7' }], ['path', { d: 'M9 21H3v-6' }]],
  'arrow-up': [['path', { d: 'm5 12 7-7 7 7' }], ['path', { d: 'M12 19V5' }]],
  sun: [['circle', { cx: '12', cy: '12', r: '4' }], ['path', { d: 'M12 2v2' }],
    ['path', { d: 'M12 20v2' }], ['path', { d: 'm4.93 4.93 1.41 1.41' }],
    ['path', { d: 'm17.66 17.66 1.41 1.41' }], ['path', { d: 'M2 12h2' }],
    ['path', { d: 'M20 12h2' }], ['path', { d: 'm6.34 17.66-1.41 1.41' }],
    ['path', { d: 'm19.07 4.93-1.41 1.41' }]],
  moon: [['path', { d: 'M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401' }]],
  copy: [['rect', { width: '14', height: '14', x: '8', y: '8', rx: '2', ry: '2' }],
    ['path', { d: 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2' }]],
  save: [['path', { d: 'M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z' }],
    ['path', { d: 'M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7' }],
    ['path', { d: 'M7 3v4a1 1 0 0 0 1 1h7' }]],
  check: [['path', { d: 'M20 6 9 17l-5-5' }]],
  x: [['path', { d: 'M18 6 6 18' }], ['path', { d: 'm6 6 12 12' }]],
  'circle-question-mark': [['circle', { cx: '12', cy: '12', r: '10' }], ['path', { d: 'M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3' }], ['path', { d: 'M12 17h.01' }]],
  eye: [['path', { d: 'M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0' }],
    ['circle', { cx: '12', cy: '12', r: '3' }]],
  markdown: [['path', { d: 'M22.27 19.385H1.73A1.73 1.73 0 0 1 0 17.655V6.345a1.73 1.73 0 0 1 1.73-1.73h20.54A1.73 1.73 0 0 1 24 6.345v11.308a1.73 1.73 0 0 1-1.73 1.731Zm-16.501-3.462v-4.5l2.308 2.885 2.307-2.885v4.5h2.308V8.078h-2.308l-2.307 2.885-2.308-2.885H3.46v7.847Zm15.463-3.923h-2.309V8.077h-2.307V12h-2.308l3.461 4.039Z',
    fill: 'currentColor', stroke: 'none' }]],
  flag: [['path', { d: 'M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.333 2q2 0 3.067-.8A1 1 0 0 1 20 4v10a1 1 0 0 1-.4.8A6 6 0 0 1 16 16c-3 0-5-2-8-2a6 6 0 0 0-4 1.528' }]],
  'file-text': [['path', { d: 'M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z' }],
    ['path', { d: 'M14 2v4a2 2 0 0 0 2 2h4' }], ['path', { d: 'M10 9H8' }],
    ['path', { d: 'M16 13H8' }], ['path', { d: 'M16 17H8' }]],
  'loader-circle': [['path', { d: 'M21 12a9 9 0 1 1-6.219-8.56' }]],
};
function icon(name, size = 15) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  for (const [key, value] of Object.entries({
    class: name === 'markdown' ? 'markdown-icon' : `lucide lucide-${name}`, width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    'aria-hidden': 'true', focusable: 'false',
  })) svg.setAttribute(key, value);
  for (const [tag, attributes] of ICONS[name]) {
    const shape = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attributes)) shape.setAttribute(key, value);
    svg.append(shape);
  }
  return svg;
}
function setIcon(button, name, size) {
  button.replaceChildren(icon(name, size));
}
function setPreviewIcon(button) {
  button.replaceChildren(icon('markdown', 15));
  label(button, 'Preview Markdown');
}
function save(name, value) {
  try { localStorage.setItem(`${key}:${name}`, value); return true; }
  catch { return false; }
}
function setTheme(theme) {
  const light = theme === 'light';
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
  const button = $('#theme');
  setIcon(button, light ? 'moon' : 'sun', 17);
  label(button, `Switch to ${light ? 'dark' : 'light'} mode`);
}
setTheme(stored('theme'));
$('#theme').addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  setTheme(theme);
  save('theme', theme);
});

// Set aria-label and title to the same text for screen readers and hover tooltips.
function label(button, text) {
  button.setAttribute('aria-label', text);
  button.title = text;
}

function connectionLabel(state) {
  // A poll shows as the blue dot alone, so its text keeps the normal reading.
  if (state === 'down') return 'Disconnected';
  return state === 'idle' ? 'No agent' : 'Connected';
}
function setConnection(state, text) {
  const dot = $('#connection-dot');
  dot.dataset.state = state;
  dot.setAttribute('aria-label', connectionLabel(state));
  $('#connection-text').textContent = text;
}
// The server stores the wait stamp in second-precision UTC.
// Add Z for the browser parser.
let pollSince = null;
let connectionBase = 'Connecting…';
let callTally = '';
// A turn end leaves the preview visible. State stamps agent calls and lets the header report a missing agent.
// The next agent call clears the turn-end mark.
const AGENT_QUIET_MS = 180_000;
const AGENT_CALL_MS = 1_920_000;
let agentSeenAt = null;
let agentSeenStamp = null;
let turnEndedAt = null;
let turnEndedStamp = null;
let callEndAt = null;
let callEndStamp = null;
function agentSilentMs() {
  return agentSeenAt === null ? null : Date.now() - agentSeenAt;
}
function agentInCall() {
  // A returned poll ended the turn, so the silence that follows is not a running call.
  if (turnEndedAt !== null) return false;
  // The hook stamps every bash call's end, so a call that finished is not a running one,
  // whatever the agent does between calls.
  if (callEndAt !== null && agentSeenAt !== null && agentSeenAt <= callEndAt) return false;
  const silent = agentSilentMs();
  return pollSince === null && silent !== null && silent > AGENT_QUIET_MS && silent <= AGENT_CALL_MS;
}
function agentIdle() {
  // A live poll heartbeat proves the agent is present, so a long wait never reads as idle.
  if (pollSince !== null) return false;
  if (turnEndedAt !== null) return Date.now() - turnEndedAt > AGENT_QUIET_MS;
  const silent = agentSilentMs();
  return silent !== null && silent > AGENT_CALL_MS;
}
function connectionText() {
  // The header names what the agent is doing: the wait while a poll runs, else the stamp of the last bash call.
  // An absent agent carries its own marker in place of the sentence that stood here.
  const tail = agentIdle() ? ' · Agent 404' : '';
  // The tally ends every shape of the line: a poll, a finished call and the quiet line are all
  // read while the count climbs.
  if (pollSince !== null) {
    const label = getState()?.checking_pr ? 'PR checks...'
      : getState()?.waiting_for_gates ? 'Running gates...' : 'Polling…';
    return `${label} ${duration(Date.now() - pollSince)}${tail}${callTally}`;
  }
  if (callEndStamp !== null) return `Bash ${time(callEndStamp)}${tail}${callTally}`;
  return agentIdle() ? `Agent 404${callTally}` : connectionBase + callTally;
}
function stampMs(value) {
  if (typeof value !== 'string') return null;
  const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(value) ? `${value}Z` : value;
  const parsed = Date.parse(stamp);
  return Number.isFinite(parsed) ? parsed : null;
}
function duration(ms) {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return minutes ? `${minutes}m ${String(seconds).padStart(2, '0')}s` : `${seconds}s`;
}
function paintConnection() {
  if (pollSince !== null || agentInCall()) $('#connection-text').textContent = connectionText();
  else if (agentIdle() && $('#connection-dot').dataset.state !== 'down') {
    setConnection('idle', connectionText());
  }
}
// The composer stays open and has no closed state.
// A placeholder is a one-line hint, so a multiline note keeps only its first line.
function clipPlaceholder(text) {
  return String(text).split(/\r?\n/, 1)[0];
}
const STATE_WORDS = { sent: 'Sent', seen: 'Seen', said: 'Said' };
// The log search checks each row's message, rendered answer, and receipt ID. A note ID therefore finds its note.
// The copy button restores the whole log. A narrowed copy would restore a partial log as complete.
let logQuery = '';

function paintSend(busy) {
  setIcon(send, busy ? 'loader-circle' : 'arrow-up', 16);
  label(send, busy ? 'Sending message' : 'Send message');
  send.setAttribute('aria-busy', String(busy));
  const svg = send.children?.[0];
  if (busy && svg && typeof gsap !== 'undefined') {
    gsap.to(svg, { rotation: 360, duration: 1, ease: 'none', repeat: -1 });
  }
}
function paintExpansion() {
  const expanded = Boolean(compose.dataset.expanded);
  expandComposer.setAttribute('aria-expanded', String(expanded));
  label(expandComposer, expanded ? 'Collapse composer' : 'Expand composer');
  setIcon(expandComposer, expanded ? 'minimize-2' : 'maximize-2', 16);
}
function grow() {
  const history = $('#history');
  const priorHistoryHeight = history.clientHeight;
  const priorNoteHeight = parseFloat(note.style.height) || 0;
  const wasMultiline = Boolean(compose.dataset.multiline);
  const wasAttachments = Boolean(compose.dataset.attachments);
  delete compose.dataset.multiline;
  if (!note.value) delete compose.dataset.expanded;
  note.style.height = 'auto';
  note.style.overflowY = note.value ? 'auto' : 'hidden';
  const css = window.getComputedStyle(note);
  const single = parseFloat(css.lineHeight) + parseFloat(css.paddingTop) + parseFloat(css.paddingBottom);
  const multiline = Boolean(note.value && (wasMultiline || note.hidden || note.value.includes('\n') || note.scrollHeight > Math.ceil(single)));
  if (multiline) compose.dataset.multiline = 'true';
  const border = parseFloat(css.borderTopWidth) + parseFloat(css.borderBottomWidth);
  const nextNoteHeight = !note.value || compose.dataset.expanded ? 0 : note.scrollHeight + border;
  note.style.height = nextNoteHeight ? `${nextNoteHeight}px` : '';
  expandComposer.hidden = !multiline && !compose.dataset.expanded;
  paintExpansion();
  const nextHistoryHeight = history.clientHeight;
  const heightDrop = priorHistoryHeight > nextHistoryHeight
    ? priorHistoryHeight - nextHistoryHeight
    : nextHistoryHeight > 0
      ? Math.max(0, nextNoteHeight - priorNoteHeight) + (!wasMultiline && multiline && !wasAttachments ? 38 : 0)
      : 0;
  if (heightDrop > 0 && !compose.dataset.expanded) {
    history.scrollTop = logPinned
      ? history.scrollHeight
      : Math.min(history.scrollHeight, history.scrollTop + heightDrop);
    updateLogJump();
  }
}
expandComposer.addEventListener('click', () => {
  if (compose.dataset.expanded) delete compose.dataset.expanded;
  else compose.dataset.expanded = 'true';
  grow();
  (note.hidden ? $('#draft-preview') : note).focus();
});
let lastViewportHeight = 0;
function syncViewport() {
  const vv = window.visualViewport;
  const vvHeight = vv?.height || 0;
  const innerHeight = window.innerHeight || 0;
  const nextHeight = Math.round(
    vvHeight && innerHeight ? Math.min(vvHeight, innerHeight) : vvHeight || innerHeight
  );
  if (!nextHeight) return;
  const history = $('#history');
  const priorHistoryHeight = history.clientHeight;
  if (nextHeight !== lastViewportHeight) {
    lastViewportHeight = nextHeight;
    document.documentElement.style?.setProperty?.('--app-height', `${nextHeight}px`);
  }
  if ((vv?.offsetTop || window.scrollY) && typeof window.scrollTo === 'function') window.scrollTo(0, 0);
  const nextHistoryHeight = history.clientHeight;
  if (priorHistoryHeight > nextHistoryHeight && !compose.dataset.expanded) {
    history.scrollTop = logPinned
      ? history.scrollHeight
      : Math.min(history.scrollHeight, history.scrollTop + (priorHistoryHeight - nextHistoryHeight));
    updateLogJump();
  }
}
window.addEventListener('resize', () => { syncViewport(); if (stagedFiles.length) renderStagedFiles(); else grow(); });
window.addEventListener('pageshow', () => { syncViewport(); grow(); });
window.visualViewport?.addEventListener?.('resize', syncViewport);
window.visualViewport?.addEventListener?.('scroll', syncViewport);
syncViewport();
paintSend(false);
note.value = stored('draft') || '';
grow();
try { pending = JSON.parse(stored('pending') || 'null'); }
catch { status.textContent = 'Stored retry data is invalid. Draft retained; check the log before resending.'; }
let previewTooltipTimer = null;
function clearPreviewTooltip() {
  clearTimeout(previewTooltipTimer);
  previewTooltipTimer = null;
  const button = $('#preview-note');
  delete button.dataset.tooltip;
  label(button, 'Preview Markdown');
}
let slashCommands = [
  { cmd: '/nemoizer audit', desc: 'Send agent note: run a nemoizer audit and report' },
  { cmd: '/nemoizer collect', desc: 'Scan prose and code for nemoizer findings (modal)' },
  { cmd: '/nemoizer help', desc: 'Show nemoizer commands and clauses (modal)' },
  { cmd: '/nemoizer recipes', desc: 'Browse nemoizer templates and references (modal)' },
  { cmd: '/nemoizer rules', desc: 'Browse nemoizer rules or /nemoizer rules <id> (modal)' },
  { cmd: '/nuu audit', desc: 'Send agent note: run a full nuu audit' },
  { cmd: '/nuu help', desc: 'Show nuu commands and clauses (modal)' },
  { cmd: '/nuu recipe loading-bar', desc: 'Send agent note: apply loading-bar recipe' },
  { cmd: '/nuu recipe modal-manager', desc: 'Send agent note: apply modal-manager recipe' },
  { cmd: '/nuu recipe offline-fonts', desc: 'Send agent note: apply offline-fonts recipe' },
  { cmd: '/nuu recipe scroll-edge-fade', desc: 'Send agent note: apply scroll-edge-fade recipe' },
  { cmd: '/nuu recipes', desc: 'List nuu UI recipes (modal)' },
  { cmd: '/nuu search ', desc: 'Search the nuu UI/UX catalog (modal)' },
];
let slashActiveIndex = 0;
let slashMatches = [];
let slashUnregistered = false;
function recognizedSlashPrefix(raw) {
  if (typeof raw !== 'string' || !raw.startsWith('/')) return '';
  const firstLine = raw.split(/\r?\n/, 1)[0];
  const lower = firstLine.toLowerCase();
  const prefixes = slashCommands
    .map(item => String(item.cmd || '').trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);
  for (const candidate of prefixes) {
    const target = candidate.toLowerCase();
    if (!lower.startsWith(target)) continue;
    const next = firstLine[target.length];
    if (next && !/\s/.test(next)) continue;
    return firstLine.slice(0, target.length);
  }
  return '';
}
function syncSlashComposerStyle() {
  const backdrop = $('#note-backdrop');
  if (!note.value.startsWith('/')) slashUnregistered = false;
  const prefix = note.hidden || slashUnregistered ? '' : recognizedSlashPrefix(note.value);
  if (prefix) {
    note.dataset.slash = 'true';
    note.spellcheck = false;
    if (backdrop) {
      const span = document.createElement('span');
      span.className = 'slash-token';
      span.textContent = prefix;
      backdrop.replaceChildren(span, document.createTextNode(note.value.slice(prefix.length)));
      backdrop.hidden = false;
      backdrop.scrollTop = note.scrollTop;
    }
  } else {
    delete note.dataset.slash;
    note.spellcheck = true;
    if (backdrop) {
      backdrop.replaceChildren();
      backdrop.hidden = true;
    }
  }
}
function hideSlashMenu() {
  syncSlashComposerStyle();
  const menu = $('#slash-menu');
  if (!menu) return;
  menu.hidden = true;
  menu.replaceChildren();
  slashMatches = [];
  slashActiveIndex = 0;
}
function applySlashSelection(entry) {
  if (!entry) return;
  slashUnregistered = false;
  note.value = `${entry.cmd.trim()} `;
  if (typeof note.setSelectionRange === 'function') {
    note.setSelectionRange(note.value.length, note.value.length);
  }
  draftVersion++;
  save('draft', note.value);
  grow();
  hideSlashMenu();
  note.focus();
}
function updateSlashMenu() {
  syncSlashComposerStyle();
  const menu = $('#slash-menu');
  if (!menu || note.hidden || slashUnregistered) return hideSlashMenu();
  const raw = note.value;
  if (!raw.startsWith('/') || raw.includes('\n')) return hideSlashMenu();
  const query = raw.trim().toLowerCase();
  slashMatches = slashCommands.filter(item =>
    item.cmd.toLowerCase().startsWith(query) || query === '/'
  );
  if (!slashMatches.length || (slashMatches.length === 1 && raw.trim().toLowerCase() === slashMatches[0].cmd.trim().toLowerCase())) {
    return hideSlashMenu();
  }
  slashActiveIndex = Math.min(slashActiveIndex, slashMatches.length - 1);
  menu.replaceChildren(...slashMatches.map((item, idx) => {
    const li = document.createElement('li');
    li.className = 'slash-option';
    li.setAttribute('role', 'option');
    li.setAttribute('aria-selected', String(idx === slashActiveIndex));
    const code = document.createElement('code');
    code.textContent = item.cmd.trim();
    const span = document.createElement('span');
    span.textContent = item.desc;
    li.append(code, span);
    li.addEventListener('mousedown', event => {
      event.preventDefault();
      applySlashSelection(item);
    });
    return li;
  }));
  menu.hidden = false;
}
note.addEventListener('input', () => {
  draftVersion++;
  clearPreviewTooltip();
  grow();
  updateSlashMenu();
  if (!save('draft', note.value)) status.textContent = 'Browser storage unavailable. Keep this page open.';
});
note.addEventListener('blur', () => setTimeout(hideSlashMenu, 120));
note.addEventListener('scroll', () => {
  const backdrop = $('#note-backdrop');
  if (backdrop && !backdrop.hidden) backdrop.scrollTop = note.scrollTop;
});

// File bytes stay in this browser tab.
// Staged files start uploading on drop so the chip shows progress and Send binds stored bytes.
let stagedFiles = [];
const selector = $('#upload-file');
function chipState(entry) {
  if (entry.status === 'uploading') return 'uploading…';
  if (entry.status === 'failed') return 'upload failed';
  return bytes(entry.file.size);
}
async function uploadStaged(entry) {
  // The client names the upload, so a removal can drop a row whose response never arrived.
  entry.status = 'uploading';
  entry.error = '';
  entry.controller = typeof AbortController === 'function' ? new AbortController() : null;
  const body = new FormData();
  body.append('id', entry.id);
  body.append('file', entry.file, entry.file.name);
  const timer = setTimeout(() => entry.controller?.abort(), BINARY_TIMEOUT);
  try {
    const response = await fetch('/api/uploads', {
      method: 'POST', body, cache: 'no-store', signal: entry.controller?.signal
    });
    if (!response.ok) throw new Error(response.status === 502 ? 'HTTP 502: Bad Gateway' : `HTTP ${response.status}`);
    entry.status = 'ready';
  } catch (error) {
    entry.status = entry.aborted ? 'dropped' : 'failed';
    entry.error = error && error.message ? error.message : 'Upload failed';
  } finally {
    clearTimeout(timer);
    entry.controller = null;
    if (stagedFiles.includes(entry)) renderStagedFiles();
  }
}
function isImageAttachment(file) {
  return Boolean(file && ((typeof file.type === 'string' && /^image\//i.test(file.type)) || /\.(?:png|jpe?g|gif|webp|svg|bmp|avif|ico)$/i.test(String(file.name || ''))));
}
function revokeStagedPreview(entry) {
  if (entry && entry.previewUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
    try { URL.revokeObjectURL(entry.previewUrl); } catch { /* Ignore invalid object URL. */ }
    entry.previewUrl = '';
  }
}
async function dropStaged(entry) {
  revokeStagedPreview(entry);
  entry.aborted = true;
  entry.controller?.abort();
  try { await entry.request; } catch { /* The request reports its own state. */ }
  try {
    await fetch(`/api/uploads/${encodeURIComponent(entry.id)}/drop`, {
      method: 'POST', cache: 'no-store', headers: writeHeaders('application/json'), body: '{}'
    });
  } catch { /* No row landed, or a note already owns the bytes. */ }
}
function splitStagedFileName(rawName) {
  const text = String(rawName || '');
  const slash = Math.max(text.lastIndexOf('/'), text.lastIndexOf('\\'));
  const dir = slash >= 0 ? text.slice(0, slash + 1) : '';
  const base = slash >= 0 ? text.slice(slash + 1) : text;
  const dot = base.lastIndexOf('.');
  if (dot > 0) return { dir, stem: base.slice(0, dot), ext: base.slice(dot) };
  return { dir, stem: base, ext: '' };
}
function truncateStagedStem(stem, maxStemChars) {
  if (!(maxStemChars > 0) || stem.length <= maxStemChars) return stem;
  if (maxStemChars <= 3) return `${stem.slice(0, Math.max(1, maxStemChars))}...`;
  const mid = Math.ceil(stem.length / 2);
  const leftHalf = stem.slice(0, mid);
  const rightHalf = stem.slice(mid);
  const keep = Math.max(2, maxStemChars - 3);
  const keepLeft = Math.ceil(keep / 2);
  const keepRight = Math.floor(keep / 2);
  return `${leftHalf.slice(0, keepLeft)}...${keepRight > 0 ? rightHalf.slice(rightHalf.length - keepRight) : ''}`;
}
function formatStagedChipText(rawName, stateText, containerWidth = 0) {
  const { dir, stem, ext } = splitStagedFileName(rawName);
  const suffix = ` · ${stateText}`;
  const fixedChars = dir.length + ext.length + suffix.length;
  const totalBudget = containerWidth > 0
    ? Math.max(fixedChars + 5, Math.floor(Math.max(40, containerWidth - 84) / 7.5))
    : 64;
  const maxStemChars = Math.max(5, totalBudget - fixedChars);
  return `${dir}${truncateStagedStem(stem, maxStemChars)}${ext}${suffix}`;
}
function renderStagedFiles() {
  const holder = $('#staged-files');
  const containerWidth = holder.clientWidth || compose.clientWidth || 0;
  holder.replaceChildren(...stagedFiles.map(entry => {
    const chip = document.createElement('span');
    chip.className = 'staged-chip';
    const name = document.createElement('span');
    name.className = 'staged-chip-name';
    const stateText = chipState(entry);
    name.textContent = formatStagedChipText(entry.file.name, stateText, containerWidth);
    name.title = entry.error
      ? `${entry.file.name} · ${entry.error}`
      : `${entry.file.name} · ${entry.file.size.toLocaleString()} bytes`;
    const remove = document.createElement('button');
    remove.type = 'button';
    setIcon(remove, 'x', 12);
    label(remove, `Remove ${entry.file.name}`);
    remove.addEventListener('click', () => {
      if (send.disabled) return;
      // A click may reach an element from an earlier render, so the array decides the position.
      const position = stagedFiles.indexOf(entry);
      if (position < 0) return;
      const [dropped] = stagedFiles.splice(position, 1);
      selector.value = '';
      void dropStaged(dropped);
      renderStagedFiles();
      status.textContent = '';
    });
    let lead;
    if (entry.isImage || isImageAttachment(entry.file)) {
      lead = document.createElement('img');
      lead.className = 'staged-chip-lead staged-chip-thumb';
      lead.src = entry.previewUrl || `/api/uploads/${encodeURIComponent(entry.id)}`;
      lead.alt = entry.file.name;
      lead.width = 32;
      lead.height = 32;
    } else {
      lead = document.createElement('span');
      lead.className = 'staged-chip-lead staged-chip-file';
      lead.setAttribute('aria-hidden', 'true');
      setIcon(lead, 'file-text', 16);
    }
    chip.append(name, remove, lead);
    return chip;
  }));
  for (const [index, chip] of Array.from(holder.children).entries()) {
    const name = chip.children?.[0];
    const entry = stagedFiles[index];
    if (!name || !entry || !(name.clientWidth > 0) || !(name.scrollWidth > name.clientWidth)) continue;
    const { dir, stem, ext } = splitStagedFileName(entry.file.name);
    const suffix = ` · ${chipState(entry)}`;
    let limit = stem.length - 1;
    while (limit >= 5 && name.scrollWidth > name.clientWidth) {
      name.textContent = `${dir}${truncateStagedStem(stem, limit)}${ext}${suffix}`;
      limit -= 1;
    }
  }
  holder.hidden = !stagedFiles.length;
  if (stagedFiles.length) compose.dataset.attachments = 'true';
  else delete compose.dataset.attachments;
  grow();
}
function clearStagedFiles() {
  for (const entry of stagedFiles) revokeStagedPreview(entry);
  stagedFiles = [];
  selector.value = '';
  renderStagedFiles();
}
function stageFiles(files) {
  if (send.disabled || !files.length) return;
  for (const file of files) {
    if (!file.name || file.name.length > 200) { status.textContent = 'Use filenames of 1–200 characters.'; return; }
    if (!file.size) { status.textContent = `${file.name} is empty.`; return; }
  }
  const entries = [];
  for (const file of files) {
    let id = newId();
    while (stagedFiles.some(entry => entry.id === id) || entries.some(entry => entry.id === id)) id = newId();
    const isImage = isImageAttachment(file);
    let previewUrl = '';
    if (isImage && typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
      try { previewUrl = URL.createObjectURL(file); } catch { previewUrl = ''; }
    }
    entries.push({ file, id, isImage, previewUrl, status: 'uploading', error: '', aborted: false, controller: null, request: null });
  }
  stagedFiles.push(...entries);
  selector.value = '';
  renderStagedFiles();
  for (const entry of entries) entry.request = uploadStaged(entry);
  status.textContent = '';
}
$('#attach-file').addEventListener('click', () => selector.click());
selector.addEventListener('change', () => stageFiles(Array.from(selector.files || [])));
let pasteAsText = false;
compose.addEventListener('keydown', event => {
  pasteAsText = event.key.toLowerCase() === 'v' && event.ctrlKey && event.shiftKey;
});
compose.addEventListener('keyup', () => { pasteAsText = false; });
compose.addEventListener('focusout', () => { pasteAsText = false; });
compose.addEventListener('paste', event => {
  const plainText = pasteAsText;
  pasteAsText = false;
  if (send.disabled || plainText) return;
  const clip = event.clipboardData;
  const images = Array.from(clip?.files || []).filter(file => file.type.startsWith('image/'));
  const text = clip?.getData('text/plain') || '';
  if (!images.length) {
    const lines = text.split('\n').length;
    // A Unicode character uses at most two UTF-16 units. Inspect only enough text to decide the limit.
    if (lines < PASTE_LINE_LIMIT && Array.from(text.slice(0, PASTE_CHAR_LIMIT * 2 + 1)).length <= PASTE_CHAR_LIMIT) return;
    event.preventDefault();
    const stamp = Date.now();
    const base = `${lines}-pasted-lines-${stamp}`;
    const names = new Set(stagedFiles.map(entry => entry.file.name));
    let name = `${base}.txt`;
    for (let index = 2; names.has(name); index++) name = `${base}-${index}.txt`;
    stageFiles([new File([text], name, { type: 'text/plain', lastModified: stamp })]);
    return;
  }
  if (!text) event.preventDefault();
  const stamp = Date.now();
  const names = new Set(stagedFiles.map(entry => entry.file.name));
  stageFiles(images.map(file => {
    const extension = file.type === 'image/jpeg' ? 'jpg' : file.type.slice(6).split('+')[0].replace(/[^a-z0-9]/gi, '') || 'img';
    let name = `${stamp}.${extension}`;
    for (let index = 2; names.has(name); index++) name = `${stamp}-${index}.${extension}`;
    names.add(name);
    return new File([file], name, { type: file.type, lastModified: stamp });
  }));
});
const hasDraggedFile = event => Array.from((event.dataTransfer || {}).types || []).includes('Files');
for (const type of ['dragenter', 'dragover']) compose.addEventListener(type, event => {
  if (!hasDraggedFile(event)) return;
  event.preventDefault();
  compose.dataset.dragging = 'true';
});
compose.addEventListener('dragleave', () => { delete compose.dataset.dragging; });
compose.addEventListener('drop', event => {
  if (!hasDraggedFile(event) && !(event.dataTransfer && event.dataTransfer.files.length)) return;
  event.preventDefault();
  delete compose.dataset.dragging;
  stageFiles(Array.from(event.dataTransfer.files || []));
});

let liveSocket = null;
let socketRetry = null;
let pollTimer = null;
let lastSocketMessage = 0;
let socketSequence = 0;
const socketCalls = new Map();
function startPolling() {
  if (pollTimer === null) pollTimer = setInterval(refreshState, 3000);
}
function socketRefresh() {
  if (stateBusy) stateAgain = true;
  else void refreshState();
}
function connectSocket() {
  if (typeof WebSocket !== 'function' || liveSocket && liveSocket.readyState < 2) return;
  const url = new URL(window.location.href);
  if (url.searchParams.get('transport') === 'poll') return;
  url.pathname = '/api/ws';
  url.search = '';
  url.hash = '';
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  let socket;
  try { socket = new WebSocket(url); } catch { return; }
  liveSocket = socket;
  const deadline = setTimeout(() => socket.close(), 10000);
  socket.addEventListener('open', () => {
    clearTimeout(deadline);
    lastSocketMessage = Date.now();
    clearInterval(pollTimer);
    pollTimer = null;
    socketRefresh();
  });
  socket.addEventListener('message', event => {
    if (liveSocket !== socket) return;
    try {
      const value = JSON.parse(event.data);
      lastSocketMessage = Date.now();
      if (value.type === 'heartbeat') { socket.send(JSON.stringify({type: 'pong'})); return; }
      if (value.type === 'change') { socketRefresh(); return; }
      if (value.type !== 'response') throw new Error('Unknown WebSocket message');
      const pending = socketCalls.get(value.id);
      if (!pending) return;
      if (!Number.isInteger(value.status) || value.status < 200 || value.status > 599 || typeof value.body !== 'string') {
        throw new Error('Invalid WebSocket reply');
      }
      const response = new Response(value.status === 204 ? null : value.body,
        {status: value.status, headers: {'Content-Type': value.contentType || 'application/json'}});
      socketCalls.delete(value.id);
      clearTimeout(pending.timer);
      pending.resolve(response);
    } catch { socket.close(1002); }
  });
  socket.addEventListener('error', () => socket.close());
  socket.addEventListener('close', () => {
    clearTimeout(deadline);
    if (liveSocket !== socket) return;
    liveSocket = null;
    for (const pending of socketCalls.values()) {
      clearTimeout(pending.timer);
      pending.reject(new TypeError('WebSocket closed before a reply'));
    }
    socketCalls.clear();
    startPolling();
    void refreshState();
    clearTimeout(socketRetry);
    socketRetry = setTimeout(connectSocket, 1000);
  });
}
function socketRequest(path, options, timeoutMs) {
  const socket = liveSocket;
  const id = String(++socketSequence);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      socketCalls.delete(id);
      reject(new TypeError('WebSocket reply timed out'));
      socket.close();
    }, timeoutMs);
    socketCalls.set(id, {resolve, reject, timer});
    try { socket.send(JSON.stringify({id, path, method: options.method || 'GET', headers: options.headers || {}, body: options.body || ''})); }
    catch (error) {
      socketCalls.delete(id);
      clearTimeout(timer);
      reject(error);
      socket.close();
    }
  });
}
function checkSocket() {
  if (liveSocket?.readyState === 1 && Date.now() - lastSocketMessage > 30000) liveSocket.close();
}

// Short requests keep their ten-second timer. Binary transfers have a longer deadline and no
// automatic retry after a lost response: the server may have saved the bytes already.
async function attempt(path, options, timeoutMs) {
  if (liveSocket?.readyState === 1 && path.startsWith('/api/') &&
      (options.body === undefined || typeof options.body === 'string')) {
    return socketRequest(path, options, timeoutMs);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(path, { ...options, cache: 'no-store', signal: controller.signal });
  } finally { clearTimeout(timer); }
}
// Small writes retry once after a network failure.
async function request(path, options = {}) {
  const { timeoutMs = 10_000, retryOnFailure = true, ...init } = options;
  let response;
  try {
    response = await attempt(path, init, timeoutMs);
  } catch (error) {
    if (!retryOnFailure) throw error;
    await new Promise((done) => setTimeout(done, 1000));
    response = await attempt(path, init, timeoutMs);
  }
  if (!response.ok) {
    const message = await response.text();
    let error;
    try { error = JSON.parse(message).error; } catch {
      // A gateway answers a dead backend with a long HTML page. Keep the connection line short.
      error = /^\s*</.test(message) ? '' : message.trim().replace(/\s+/g, ' ').slice(0, 120);
    }
    throw new Error(error || `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`);
  }
  return response;
}
function showWorkspace(usage) {
  const node = $('#workspace-use');
  if (!usage) {
    node.textContent = 'Workspace file use is unavailable.';
    return;
  }
  node.textContent = `Workspace files: ${bytes(usage.bytes)} in ${usage.files.toLocaleString()} files. Documented snapshot cap: ${bytes(usage.documented_cap_bytes)}.`;
}
function bytes(value) {
  if (value < 1000) return `${value} B`;
  if (value < 1000000) return `${Math.round(value / 1000)} kB`;
  return `${(value / 1000000).toFixed(2)} MB`;
}
function stampDate(value) {
  // The state omits the UTC offset and keeps seconds only. Date would interpret those digits as local time.
  // Pin seconds-only ISO stamps to UTC before local formatting so each zone shows the correct time.
  return new Date(
    typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(value)
      ? `${value}Z`
      : value
  );
}
function clock(value) {
  // The composer footer names the key's freshness in the room a narrow width leaves:
  // the hour and minute alone.
  const parts = Object.fromEntries(new Intl.DateTimeFormat(undefined, {
    hour: '2-digit', minute: '2-digit', hour12: false
  }).formatToParts(stampDate(value)).map(part => [part.type, part.value]));
  return `${parts.hour}:${parts.minute}`;
}
function time(value) {
  // The stamps read as an age: minutes under an hour, whole hours from an hour up.
  const minutes = Math.floor((Date.now() - stampDate(value).getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min${minutes === 1 ? '' : 's'} ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours} hour${hours === 1 ? '' : 's'} ago`;
}
function clockTime(value) {
  // The header clock shows absolute time in the browser's local zone.
  const date = stampDate(value);
  const parts = Object.fromEntries(new Intl.DateTimeFormat(undefined, {
    month: 'short', day: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
  }).formatToParts(date).map(part => [part.type, part.value]));
  const year = date.getFullYear() === new Date().getFullYear() ? '' : ` ${parts.year}`;
  return `${parts.month} ${parts.day}${year}, ${parts.hour}:${parts.minute}`;
}
let unreadEdits = [];
// SQLite stores the number of reply blocks the page marked as viewed. Counts distinguish two
// replies with the same second-level timestamp, and survive a page reload.
function updateEdits(notes) {
  unreadEdits = notes.filter(item => item.ack_edited_at
    && Number(item.ack_edited_seen_count || 0) < (item.replies || []).length);
  const button = $('#log-edited');
  $('#notes-pip').hidden = button.hidden = !unreadEdits.length;
  if (!unreadEdits.length) delete button.dataset.error;
  button.textContent = button.dataset.error ? 'Not saved' : unreadEdits.length > 1 ? `New replies (${unreadEdits.length})` : 'New reply';
  label(button, button.dataset.error || button.textContent);
}
const ACK_REFERENCE_PANELS = {note: 'notes-panel', report: 'reports-panel', task: 'tasks-panel'};
function referenceTypes(state) {
  const references = new Map();
  const add = (type, items) => {
    for (const item of items || []) {
      if (typeof item.id !== 'string') continue;
      if (references.has(item.id) && references.get(item.id) !== type) references.set(item.id, null);
      else references.set(item.id, type);
    }
  };
  add('note', state.notes);
  add('report', state.reports);
  add('task', [...(state.tasks?.upcoming || []), ...(state.tasks?.finished || [])]);
  return references;
}
function linkReferences(html, references) {
  return html.replace(/<code>([^<]+)<\/code>/g, (code, id) => {
    const type = references.get(id);
    if (!type) return code;
    const panel = ACK_REFERENCE_PANELS[type];
    return `<a class="ack-reference" href="#${panel}" data-reference-type="${type}" data-reference-id="${id}"><code>${id}</code></a>`;
  });
}
function revealMessage(id) {
  const row = messageNodes.get(id);
  if (!row || $('#history').contains(row)) return row;
  const notes = (getState()?.notes || []).filter(item => !item.quiet);
  const index = notes.findIndex(item => item.id === id);
  if (index < 0) return;
  historyShown = Math.max(historyShown, notes.length - index);
  renderHistoryWindow(notes);
  return row;
}
$('#log-edited').addEventListener('click', async () => {
  const item = unreadEdits[0];
  if (!item) return;
  const button = $('#log-edited');
  delete button.dataset.error;
  showTab($('#notes-tab'));
  clearLogSearch();
  const row = revealMessage(item.id);
  if (!row) return;
  const answer = row.children[1];
  answer.setAttribute('tabindex', '-1');
  answer.focus({preventScroll: true});
  markJumpHighlight(answer);
  const replyCount = (item.replies || []).length;
  const apply = (state, receipt) => {
    const message = state.notes.find(note => note.id === item.id);
    if (message) message.ack_edited_seen_count = Math.max(
      Number(message.ack_edited_seen_count || 0), receipt?.ack_edited_seen_count ?? replyCount);
  };
  try {
    const write = optimisticWrite(apply, async () => {
      const response = await request(`/api/messages/${encodeURIComponent(item.id)}/replies/seen`, {
        method: 'POST', headers: writeHeaders('application/json'), body: JSON.stringify({count: replyCount})
      });
      const receipt = await response.json();
      if (receipt.id !== item.id || !Number.isInteger(receipt.ack_edited_seen_count)) {
        throw new Error('The viewed-reply receipt was invalid');
      }
      return receipt;
    }, apply, (state, receipt) => {
      const message = state.notes.find(note => note.id === item.id);
      return !message || Number(message.ack_edited_seen_count || 0) >= receipt.ack_edited_seen_count;
    });
    // Render the optimistic receipt first so its history refresh cannot cancel the animation.
    answer.scrollIntoView({block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
    await write;
  } catch (error) {
    button.dataset.error = `Could not save reply status: ${error.message}`;
    updateEdits(getState().notes);
  }
});
function showHistory(notes) {
  const signature = JSON.stringify(notes);
  if (signature === historySignature) return;
  historySignature = signature;
  const references = referenceTypes(getState() || {notes});
  if (notes.length) note.placeholder = clipPlaceholder(notes[notes.length - 1].text);
  const history = $('#history');
  const place = history.scrollTop;
  if (messageNodes.size) logPinned = historyAtEnd(history);
  for (const item of notes) {
    let node = messageNodes.get(item.id);
    if (!node) {
      node = document.createElement('li');
      node.className = 'message';
      const text = document.createElement('div');
      node.append(text, document.createElement('div'), document.createElement('div'));
      messageNodes.set(item.id, node);
    }
    const text = node.children[0];
    text.className = item.html === undefined ? 'raw-message' : 'message-text';
    if (item.html === undefined) text.textContent = item.text.replace(/\\n/g, '\n');
    else text.innerHTML = item.html;
    const receipt = node.children[2];
    receipt.className = 'receipt';
    const receiptId = document.createElement('code');
    receiptId.className = 'note-id';
    receiptId.textContent = item.id.slice(0, 6);
    receiptId.title = item.id;
    receiptId.dataset.full = item.id;
    // The dot shows Sent until the agent records seen_at, Seen after that receipt, and Said after an answer.
    // The title and aria-label carry the words. The receipt line carries the dot.
    const state = item.acknowledged_at ? 'said' : item.seen_at ? 'seen' : 'sent';
    node.dataset.state = state;
    const receiptDot = document.createElement('span');
    receiptDot.className = 'state-dot';
    receiptDot.dataset.state = state;
    receiptDot.setAttribute('role', 'img');
    receiptDot.setAttribute('aria-label', item.pending ? 'Sending' : STATE_WORDS[state]);
    receiptDot.title = item.pending ? 'Sending' : STATE_WORDS[state];
    const receiptState = document.createElement('span');
    receiptState.textContent = ` · ${time(item.at)}` +
      (item.ack_edited_at ? ` · Replied again ${time(item.ack_edited_at)}` : '');
    receiptState.dataset.at = item.at;
    if (item.ack_edited_at) receiptState.dataset.ackEditedAt = item.ack_edited_at;
    // Separate the receipt ID, state, time, filenames, and task with middle dots.
    const separator = document.createElement('span');
    separator.className = 'receipt-sep';
    separator.textContent = ' · ';
    // Mark messages that become tasks so the owner can distinguish a read message from a dropped one.
    // Put the task ID between `Task` and `added`, and include it in the marker's title.
    const receiptTask = document.createElement('span');
    receiptTask.className = 'receipt-task';
    // The ID rides in a code element, linked like an ack reference,
    // so the receipt jump opens the Tasks tab on that row.
    if (item.task_id) {
      const link = document.createElement('a');
      link.className = 'ack-reference';
      link.href = `#${ACK_REFERENCE_PANELS.task}`;
      link.dataset.referenceType = 'task';
      link.dataset.referenceId = item.task_id;
      const code = document.createElement('code');
      code.textContent = item.task_id;
      link.append(code);
      receiptTask.append(' · Task ', link, ' added');
    } else {
      receiptTask.textContent = ' · Task added';
    }
    receiptTask.title = item.task_id ? `Task ${item.task_id}` : '';
    const receiptFile = document.createElement('span');
    receiptFile.className = 'receipt-file';
    const names = item.attachments?.length
      ? item.attachments.map(file => file.name)
      : item.attachment_name ? [item.attachment_name] : [];
    receiptFile.textContent = names.map(name => ` · ${name}`).join('');
    receipt.replaceChildren(
      receiptId, separator, receiptDot, receiptState,
      ...(names.length ? [receiptFile] : []), ...(item.task_id ? [receiptTask] : [])
    );
    // Both acknowledgement types use server HTML when available, or a text paragraph with .message p pre-wrap.
    // Append later answers below earlier ones. Each block retains its type and timestamp title.
    const answer = node.children[1];
    if (item.ack_text) {
      answer.className = item.ack_type === 'reply' ? 'answer reply message-text' : 'answer reply';
      answer.hidden = false;
      const blocks = (item.replies || []).map(reply => {
        const block = document.createElement('div');
        block.className = 'reply-block';
        block.title = `Replied again ${time(reply.at)}`;
        if (reply.type === 'reply' && reply.html !== undefined) {
          block.innerHTML = linkReferences(reply.html, references);
        }
        else {
          const plain = document.createElement('p');
          plain.textContent = reply.text.replace(/\\n/g, '\n');
          block.replaceChildren(plain);
        }
        return block;
      });
      if (item.ack_html === undefined) {
        const plain = document.createElement('p');
        plain.textContent = item.ack_text.replace(/\\n/g, '\n');
        answer.replaceChildren(plain, ...blocks);
      } else {
        answer.innerHTML = linkReferences(item.ack_html, references);
        answer.append(...blocks);
      }
    } else {
      answer.className = 'answer';
      answer.hidden = true;
      answer.replaceChildren();
    }
  }
  // Remove nodes absent from the polled notes so stale rows cannot match the log filter.
  // The filter counts read the same node map.
  const current = new Set(notes.map(item => item.id));
  for (const id of [...messageNodes.keys()]) if (!current.has(id)) messageNodes.delete(id);
  renderHistoryWindow(notes);
  updateEdits(notes);
  applyLogSearch();
  if (history.clientHeight > 0 && history.scrollHeight <= history.clientHeight + 1) {
    history.scrollTop = 0;
    logPinned = true;
  } else {
    history.scrollTop = logPinned ? history.scrollHeight : place;
  }
  updateLogJump();
}

// The window shows the newest `historyShown` messages. Scrolling up adds older rows above the viewport.
// Offset the scroll by their added height so the owner keeps the same message in view.
function renderHistoryWindow(notes) {
  const history = $('#history');
  const place = history.scrollTop;
  const rows = notes.slice(-historyShown).map(item => messageNodes.get(item.id));
  const current = new Set(rows);
  for (const child of Array.from(history.children)) {
    if (!current.has(child)) history.removeChild(child);
  }
  rows.forEach((row, index) => {
    if (history.children[index] !== row) history.insertBefore(row, history.children[index] || null);
  });
  history.scrollTop = place;
}

function loadOlderMessages() {
  const state = getState();
  const notes = ((state && state.notes) || []).filter(item => !item.quiet);
  if (notes.length <= historyShown) return;
  const history = $('#history');
  const before = history.scrollHeight;
  historyShown = Math.min(historyShown + HISTORY_PAGE, notes.length);
  renderHistoryWindow(notes);
  applyLogSearch();
  history.scrollTop += history.scrollHeight - before;
  updateLogJump();
}
$('#history').addEventListener('scroll', () => {
  const history = $('#history');
  logPinned = historyAtEnd(history);
  if (history.scrollTop < 80) loadOlderMessages();
  updateLogJump();
});
// Show the jump bar only when a nonempty log extends beyond its panel and the owner scrolls away from the end.
// The jump returns to that end. An empty log has no destination.
function updateLogJump() {
  const history = $('#history');
  const scrollable = messageNodes.size > 0 && history.scrollHeight > history.clientHeight + 1;
  history.dataset.scrollable = scrollable ? 'true' : 'false';
  $('#log-newest').hidden = logPinned || !messageNodes.size;
}
function scrollJump(element, top) {
  element.scrollTo({top, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
}
$('#log-newest').addEventListener('click', () => {
  const history = $('#history');
  scrollJump(history, history.scrollHeight);
  logPinned = true;
  updateLogJump();
});
// Split one run of text at each match. Returns null when the run holds no match, so the caller
// keeps the text node as it stands.
function splitMatches(plain, query) {
  const lower = plain.toLowerCase();
  let pos = lower.indexOf(query);
  if (pos < 0) return null;
  const parts = [];
  let start = 0;
  while (pos > -1) {
    parts.push(plain.slice(start, pos));
    const mark = document.createElement('mark');
    mark.className = 'search-hit';
    mark.textContent = plain.slice(pos, pos + query.length);
    parts.push(mark);
    start = pos + query.length;
    pos = lower.indexOf(query, start);
  }
  parts.push(plain.slice(start));
  return parts;
}
// Search nested text nodes because rendered answers contain markup. Unwrap old marks before applying a changed or cleared query.
// Return true when the node's own children change, and preserve the answer markup.
function markNode(node, query) {
  const kids = Array.from(node.childNodes || node.children || []);
  if (!kids.length) {
    const parts = query && node.textContent ? splitMatches(node.textContent, query) : null;
    if (!parts) return false;
    node.replaceChildren(...parts);
    return true;
  }
  // Text and earlier marks merge into one run, so a match can span pieces an earlier query split.
  let changed = false;
  const runs = [];
  for (const child of kids) {
    const isText = typeof child === 'string' || child.nodeType === 3;
    const isMark = !isText && child.className === 'search-hit';
    if (isText || isMark) {
      if (isMark) changed = true;
      const text = typeof child === 'string' ? child : (isMark ? child.textContent : child.nodeValue);
      const last = runs.length ? runs[runs.length - 1] : null;
      if (typeof last === 'string') runs[runs.length - 1] = last + text;
      else runs.push(text);
    } else {
      runs.push(child);
    }
  }
  const out = [];
  for (const run of runs) {
    if (typeof run === 'string') {
      const parts = query ? splitMatches(run, query) : null;
      if (parts) {
        out.push(...parts);
        changed = true;
      } else {
        out.push(run);
      }
    } else {
      markNode(run, query);
      out.push(run);
    }
  }
  if (changed) node.replaceChildren(...out);
  return changed;
}
function markRowMatches(node, query) {
  // Keep rows that match the query, and mark the matching words so the owner can find them immediately.
  // Search plain or rendered message text, the agent reply block, and the receipt ID.
  const answer = node.children[1];
  const receipt = node.children[2];
  markNode(node.children[0], query);
  if (answer) markNode(answer, query);
  if (receipt && receipt.children[0]) markNode(receipt.children[0], query);
}
function applyLogSearch() {
  const query = logQuery.trim().toLowerCase();
  let shown = 0;
  for (const node of messageNodes.values()) {
    const visible = !query || node.textContent.toLowerCase().includes(query);
    node.hidden = !visible;
    markRowMatches(node, query);
    if (visible) shown += 1;
  }
  const total = messageNodes.size;
  $('#history').setAttribute('aria-label', query
    ? `Messages matching "${logQuery.trim()}", oldest first`
    : 'Messages, oldest first');
  const empty = $('#log-empty');
  empty.hidden = shown > 0 || total === 0;
  empty.textContent = `Nothing here matches "${logQuery.trim()}"; ${total} message`
    + `${total === 1 ? '' : 's'} saved, and the copy button still carries all of them.`;
  if (logPinned) $('#history').scrollTop = $('#history').scrollHeight;
  updateLogJump();
}
// The search is a look at the log rather than a setting, so nothing writes it down. A reference
// jump clears it, because a narrowed log could hide the row the jump is heading for.
function clearLogSearch() {
  $('#log-search').value = '';
  logQuery = '';
  applyLogSearch();
}
$('#log-search').addEventListener('input', () => {
  logQuery = $('#log-search').value;
  applyLogSearch();
});
function renderState() {
  const state = getState();
  if (!state) return;
  // Cache polled notes and tasks so the save button works after a server wipe. Publish reports again from their sources.
  // The copy exports notes, tasks, and report answers for the unified importer.
  save('state-cache', JSON.stringify({ notes: lastState.notes, tasks: lastState.tasks }));
  // Quiet notes inform the agent, not the log.
  // They stay in the cache and state export while the log and its tally show owner messages.
  const logNotes = state.notes.filter(item => !item.quiet);
  const confirmed = logNotes.filter(item => !item.pending).length;
  const saved = confirmed ? `${confirmed} messages saved` : 'No messages yet';
  // The header carries the same tally the gate keeps, so the owner sees the call count
  // the stderr banner names without leaving the page.
  const calls = state.calls_since_message || 0;
  // The tally counts up to the half-way mark, then down, and says Blocked at the same
  // count the gate blocks at.
  const threshold = state.gate_threshold || 10;
  const shown = calls <= Math.floor(threshold / 2) ? calls : threshold - calls;
  callTally = calls
    ? calls >= threshold
      ? ' · Blocked'
      : ` · ${shown} call${shown === 1 ? '' : 's'}`
    : '';
  pollSince = state.polling ? stampMs(state.polling_since) : null;
  agentSeenAt = stampMs(state.agent_seen_at);
  agentSeenStamp = state.agent_seen_at;
  turnEndedAt = stampMs(state.turn_ended_at);
  turnEndedStamp = state.turn_ended_at || null;
  callEndAt = stampMs(state.agent_call_ended_at);
  callEndStamp = state.agent_call_ended_at || null;
  connectionBase = saved;
  setConnection(state.polling ? 'polling' : agentIdle() ? 'idle' : 'ok', connectionText());
  if (state.rendering_error) {
    connectionBase += ` · Markdown log unavailable; raw text shown: ${state.rendering_error}`;
    paintConnection();
  }
  // The ack writes the same stamp as a read does, so the label is true.
  $('#last-check').textContent = state.last_check ? `Last read/ack: ${time(state.last_check)}` : 'No read or ack yet.';
  showHistory(logNotes);
  renderTasksIfChanged(state.tasks);
  renderFetchIfChanged(state.fetch_jobs || []);
  renderAgentKey(state.agent_key);
  paintSkipPoll(state.skip_poll);
  paintInterrupt(state.agent_interrupt_pending);
  showWorkspace(state.workspace);
  syncDocumentTitle();
  const signature = reportsSignature(state.reports);
  if (signature !== listSignature) {
    listSignature = signature;
    const select = $('#report-select');
    const selected = select.value || stored('report');
    const shown = $('#report').dataset.reportId;
    const pendingDelete = state.pending_report_deletes?.includes(shown);
    // Held only while the shown report is really gone: a republished ID releases it.
    heldReport = shown && !pendingDelete
      && !state.reports.some(report => report.id === shown) && !$('#reports-panel').hidden
      && reportView.id === shown && reportView.at > 0
      ? { id: shown, title: reportTitles.get(shown) || shown }
      : null;
    for (const report of state.reports) reportTitles.set(report.id, report.title);
    const ids = state.reports.map(report => report.id);
    if (heldReport) ids.push(heldReport.id);
    if (!ids.length) ids.push('');
    const options = Array.from(select.children);
    if (options.length !== ids.length || options.some((option, index) => option.value !== ids[index])) {
      select.replaceChildren();
      state.reports.forEach((report, position) => {
        const option = document.createElement('option');
        option.value = report.id;
        option.textContent = reportLabel(report, position);
        select.append(option);
      });
      if (heldReport && !state.reports.some(report => report.id === heldReport.id)) {
        const option = document.createElement('option');
        option.value = heldReport.id;
        option.textContent = `${heldReport.title} · unpublished`;
        select.append(option);
      }
      if (!state.reports.length && !heldReport) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No reports published yet';
        select.append(option);
        select.value = '';
      } else if (state.reports.some(report => report.id === selected)) select.value = selected;
      else if (heldReport && heldReport.id === selected) select.value = selected;
      else select.value = state.reports.find(report => report.needs_answer)?.id || state.reports[0]?.id || '';
    }
    const selectedReport = state.reports.find(report => report.id === select.value);
    if (!$('#reports-panel').hidden && !pendingDelete &&
        ($('#report').dataset.reportId !== select.value ||
         $('#report').dataset.updatedAt !== (selectedReport?.updated_at || ''))) loadReport();
    // When the report is already open, mark new acks seen immediately without waiting for a tab switch.
    else if (!$('#reports-panel').hidden && ackUnread(selectedReport)) void markAckSeen(select.value);
  }
  // The pip tracks unopened reports, edited reports keep their star, and the receipt tracks the latest answer.
  for (const option of $('#report-select').children) {
    const position = state.reports.findIndex(report => report.id === option.value);
    const label = position >= 0 ? reportLabel(state.reports[position], position)
      : heldReport && option.value === heldReport.id ? `${heldReport.title} · unpublished` : null;
    if (label !== null && option.textContent !== label) option.textContent = label;
  }
  updateReportPip(state.reports);
  updateReportNavigation();
  updateReportTop();
  renderReportAcknowledgement();
  checkReportRead();
}
async function refreshState() {
  // A caller that arrives during a read joins it, so a fresh state always precedes its render.
  if (stateBusy) return stateBusy;
  const running = readState();
  stateBusy = running;
  try {
    return await running;
  } finally {
    if (stateBusy === running) stateBusy = null;
  }
}
function browserTimezone() {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ''; }
  catch { return ''; }
}
async function readState() {
  let queueReady = false;
  pollCommits = [];
  try {
    const tz = browserTimezone();
    const state = await (await request('/api/state', tz ? { headers: { 'X-Timezone': tz } } : undefined)).json();
    if (Array.isArray(state.slash_commands)) {
      slashCommands = state.slash_commands;
      syncSlashComposerStyle();
    }
    for (const [key, entry] of optimisticState) if (entry.echo?.(state)) optimisticState.delete(key);
    for (const commit of pollCommits) commit(state);
    lastState = state;
    renderState();
    queueReady = true;
  } catch (error) {
    pollSince = null;
    setConnection('down', /^HTTP 502\b/.test(error.message) ? 'HTTP 502: Bad Gateway' : `Connection failed: ${error.message}. Draft kept; history may be stale.`);
  }
  finally {
    stateBusy = null;
    pollCommits = null;
    if (stateAgain) { stateAgain = false; socketRefresh(); }
    if (queueReady && (lastState?.fetch_jobs || []).some(item => item.approval === 'approved'
      && (item.status === 'queued'
        || (item.status === 'fetching' && Date.parse(item.lease_until) <= Date.now())))) {
      void pumpFetchQueue();
    }
  }
}
$('#form').addEventListener('submit', async event => {
  event.preventDefault();
  if (send.disabled || (!note.value.trim() && !stagedFiles.length)) return;
  hideSlashMenu();
  const draft = note.value;
  const submittedVersion = draftVersion;
  let expandedSlashText = '';
  if (draft.trim().startsWith('/') && !stagedFiles.length && /^\/(nuu|nemoizer)(?:\s|$)/i.test(draft.trim())) {
    send.disabled = selector.disabled = $('#attach-file').disabled = true;
    paintSend(true);
    status.textContent = '';
    let slashResult = null;
    try {
      slashResult = await (await request('/api/slash', {
        method: 'POST',
        headers: writeHeaders('application/json'),
        body: JSON.stringify({ text: draft.trim() }),
        timeoutMs: 30_000,
        retryOnFailure: false,
      })).json();
    } catch (error) {
      status.textContent = `Slash command failed: ${error.message}`;
      send.disabled = selector.disabled = $('#attach-file').disabled = false;
      paintSend(false);
      return;
    }
    if (slashResult?.mode === 'query') {
      note.value = '';
      save('draft', '');
      writeMode();
      send.disabled = selector.disabled = $('#attach-file').disabled = false;
      paintSend(false);
      const view = document.createElement('article');
      view.className = 'report slash-output';
      const rawHtml = (slashResult.html && !slashResult.html.includes('&lt;!--')) ? slashResult.html : renderMessageMarkdown(slashResult.markdown || '');
      view.innerHTML = await renderMermaidBlocks(rawHtml);
      void openModal({ title: slashResult.title || slashResult.command || 'Slash Command', content: view, readOnly: true, wide: true });
      return;
    }
    if (slashResult?.mode === 'note' && typeof slashResult.text === 'string') {
      expandedSlashText = slashResult.text;
    }
  }
  const names = stagedFiles.map(entry => entry.file.name);
  const text = expandedSlashText || (draft.trim() ? draft : names.length === 1 ? `File: ${names[0]}` : `Files: ${names.join(', ')}`);
  const uploadIds = stagedFiles.map(entry => entry.id);
  const formerIds = Array.isArray(pending?.upload_ids) ? pending.upload_ids : [];
  if (!pending || pending.text !== text || JSON.stringify(formerIds) !== JSON.stringify(uploadIds)) {
    pending = { id: newId(), text, ...(uploadIds.length ? { upload_ids: uploadIds } : {}) };
  }
  save('pending', JSON.stringify(pending));
  send.disabled = selector.disabled = $('#attach-file').disabled = true;
  paintSend(true);
  status.textContent = '';
  const sending = { id: pending.id, text, at: new Date().toISOString(), pending: true };
  const apply = (state, result) => {
    const record = result ? { html: sending.html, ...result } : sending;
    const position = state.notes.findIndex(item => item.id === sending.id);
    if (position < 0) state.notes.push(record);
    else if (result) state.notes[position] = record;
  };
  try {
    note.value = '';
    save('draft', '');
    writeMode();
    sending.html = renderMessageMarkdown(text);
    // A send waits for the eager uploads, then gives a failed one one more try.
    if (stagedFiles.some(entry => entry.status === 'uploading')) {
      await Promise.all(stagedFiles.map(entry => entry.request));
    }
    const broken = stagedFiles.filter(entry => entry.status === 'failed');
    if (broken.length) {
      await Promise.all(broken.map(entry => uploadStaged(entry)));
    }
    if (stagedFiles.some(entry => entry.status !== 'ready')) {
      const failedEntry = stagedFiles.find(entry => entry.status !== 'ready');
      if (failedEntry?.error && /^HTTP 502\b/.test(failedEntry.error)) {
        throw new Error('HTTP 502: Bad Gateway');
      }
      throw new Error('A file did not upload. Check the connection and send again');
    }
    const postNote = async () => {
      const payload = {
        id: pending.id, text,
        ...(stagedFiles.length ? { upload_ids: stagedFiles.map(entry => entry.id) } : {})
      };
      return (await request('/api/notes', {
        method: 'POST', headers: writeHeaders('application/json'), body: JSON.stringify(payload)
      })).json();
    };
    const result = await optimisticWrite(apply, async () => {
      // The note binds stored uploads so bytes never cross the wire twice.
      // Repeating the same note ID, text, and upload set returns the first record.
      try {
        return await postNote();
      } catch (error) {
        if (!stagedFiles.length || !/No staged file is stored under this ID/.test(error.message)) {
          throw error;
        }
        await Promise.all(stagedFiles.map(entry => uploadStaged(entry)));
        if (stagedFiles.some(entry => entry.status !== 'ready')) {
          throw new Error('A file did not upload. Check the connection and send again');
        }
        return await postNote();
      }
    });
    note.placeholder = clipPlaceholder(result.text);
    status.textContent = '';
    pending = null;
    save('pending', 'null');
    clearStagedFiles();
    refreshState();
  } catch (error) {
    if (draftVersion === submittedVersion && !note.value) {
      note.value = draft;
      save('draft', draft);
      writeMode();
    }
    status.textContent = /^HTTP 502\b/.test(error.message)
      ? 'HTTP 502: Bad Gateway'
      : `Save not confirmed: ${error.message}. Draft${stagedFiles.length ? ' and files' : ''} kept.`;
  }
  finally {
    send.disabled = selector.disabled = $('#attach-file').disabled = false;
    paintSend(false);
  }
});
// A touch keyboard offers no Shift key, so there the Return key writes the newline and the Send
// button sends. The hint names whichever the Return key does.
const touchPointer = window.matchMedia?.('(pointer: coarse)');
function paintSendHint() {
  // The separator rides the hint, so a phone that drops the hint leaves the key line whole.
  $('#send-hint').textContent = touchPointer?.matches
    ? 'Return: new line · Send sends · '
    : 'Enter sends · Shift+Enter: new line · ';
}
touchPointer?.addEventListener?.('change', paintSendHint);
paintSendHint();
note.addEventListener('keydown', event => {
  if (event.key === 'Backspace' && !event.ctrlKey && !event.metaKey && !event.altKey && note.dataset.slash === 'true') {
    const prefix = recognizedSlashPrefix(note.value);
    const selStart = typeof note.selectionStart === 'number' ? note.selectionStart : note.value.length;
    const selEnd = typeof note.selectionEnd === 'number' ? note.selectionEnd : selStart;
    if (prefix && selStart === selEnd && (selStart <= prefix.length || (selStart === prefix.length + 1 && (note.value[prefix.length] === ' ' || note.value[prefix.length] === '\n')))) {
      event.preventDefault();
      if (note.value.slice(prefix.length) === ' ' || note.value.slice(prefix.length) === '\n') {
        note.value = note.value.slice(0, prefix.length);
        save('draft', note.value);
      }
      slashUnregistered = true;
      hideSlashMenu();
      grow();
      return;
    }
  }
  const menu = $('#slash-menu');
  if (menu && !menu.hidden && slashMatches.length) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const step = event.key === 'ArrowDown' ? 1 : -1;
      slashActiveIndex = (slashActiveIndex + step + slashMatches.length) % slashMatches.length;
      Array.from(menu.children).forEach((li, idx) => {
        const active = idx === slashActiveIndex;
        li.setAttribute('aria-selected', String(active));
        if (active) li.scrollIntoView?.({ block: 'nearest' });
      });
      return;
    }
    if (event.key === 'Tab') {
      event.preventDefault();
      applySlashSelection(slashMatches[slashActiveIndex]);
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      hideSlashMenu();
      return;
    }
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && !touchPointer?.matches) {
      const selected = slashMatches[slashActiveIndex];
      if (selected && note.value.trim().toLowerCase() !== selected.cmd.trim().toLowerCase()) {
        event.preventDefault();
        applySlashSelection(selected);
        return;
      }
    }
  }
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && !touchPointer?.matches) {
    event.preventDefault();
    if (!send.disabled) $('#form').requestSubmit();
  }
});
function writeMode() {
  draftPreviewSequence++;
  note.hidden = false;
  grow();
  syncSlashComposerStyle();
  $('#draft-preview').hidden = true;
  clearPreviewTooltip();
  setPreviewIcon($('#preview-note'));
  $('#preview-note').setAttribute('aria-pressed', 'false');
}
$('#preview-note').addEventListener('click', async () => {
  if (note.hidden) { writeMode(); note.focus(); return; }
  if (!note.value.trim()) {
    const button = $('#preview-note');
    clearTimeout(previewTooltipTimer);
    label(button, 'Write something first');
    button.dataset.tooltip = 'Write something first';
    previewTooltipTimer = setTimeout(clearPreviewTooltip, 1500);
    return;
  }
  clearPreviewTooltip();
  const sequence = ++draftPreviewSequence;
  note.hidden = true;
  const panel = $('#draft-preview');
  panel.hidden = false;
  grow();
  panel.textContent = 'Rendering draft…';
  setPreviewIcon($('#preview-note'));
  $('#preview-note').setAttribute('aria-pressed', 'true');
  try {
    const rendered = await (await request('/api/markdown', {
      method: 'POST',
      headers: writeHeaders('application/json'),
      body: JSON.stringify({ text: note.value })
    })).text();
    if (sequence === draftPreviewSequence) panel.innerHTML = rendered;
  } catch (error) {
    if (sequence === draftPreviewSequence) panel.textContent = `Preview unavailable: ${error.message}. Use Write to continue; sending still works.`;
  }
});
function collect(root) {
  const answers = {};
  for (const field of root.querySelectorAll('.question[data-field]')) {
    const id = field.dataset.field;
    if (field.dataset.type === 'text') {
      const input = field.querySelector('textarea.answer-text');
      if (input && input.value.trim()) answers[id] = input.value;
    } else {
      const values = [];
      for (const control of field.querySelectorAll('input:checked')) {
        const label = control.dataset.label;
        if (label === undefined) { values.push({ type: 'preset', value: control.value }); continue; }
        const typed = byDataAttr(field, 'custom', label);
        if (typed) values.push({ type: 'custom', label, value: typed.value });
      }
      if (values.length) answers[id] = field.dataset.type === 'choice' ? values[0] : values;
    }
  }
  return answers;
}
// Report labels can contain backslashes or brackets, so compare dataset values instead of building selectors from labels.
// Only the caller's constant attribute name enters the selector. Label text needs no escaping.
function byDataAttr(root, key, value) {
  if (!root || !root.querySelectorAll) return null;
  for (const el of root.querySelectorAll(`[data-${key}]`)) {
    if (el.dataset && el.dataset[key] === value) return el;
  }
  return null;
}
function customValue(values, label) {
  for (const value of values) {
    if (value && typeof value === 'object') {
      if (value.type === 'custom' && value.label === label && typeof value.value === 'string') return value.value;
      continue;
    }
    if (typeof value !== 'string' || !value.startsWith(`${label}: `)) continue;
    const typed = value.slice(label.length + 2).trim();
    if (typed) return typed;
  }
  return null;
}
function applyAnswers(root, answers) {
  for (const field of root.querySelectorAll('.question[data-field]')) {
    const saved = answers[field.dataset.field];
    if (saved === undefined) continue;
    if (field.dataset.type === 'text') {
      const input = field.querySelector('textarea.answer-text');
      if (input) {
        input.value = saved;
        growSlot(input);
      }
      continue;
    }
    const values = Array.isArray(saved) ? saved : [saved];
    for (const control of field.querySelectorAll('input, textarea')) {
      const label = control.dataset.label;
      const slot = control.dataset.custom;
      if (label === undefined && slot === undefined) {
        control.checked = values.some(value => value === control.value || (value?.type === 'preset' && value.value === control.value));
        continue;
      }
      const typed = customValue(values, label === undefined ? slot : label);
      if (label !== undefined) control.checked = typed !== null;
      if (slot !== undefined) {
        control.value = typed === null ? '' : typed;
        growSlot(control);
      }
    }
  }
}
function rest(button) {
  setIcon(button, 'copy', 14);
  label(button, 'Copy code');
  button.title = 'Copy code';
  button.dataset.state = '';
}
// One clipboard path for every copy in the UI: the API first, the selection fallback second,
// and null when the browser allowed neither.
async function copyText(text) {
  try {
    if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('clipboard unavailable');
    await navigator.clipboard.writeText(text);
    return 'Copied through the clipboard API';
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    document.body.append(area);
    area.select();
    const copied = typeof document.execCommand === 'function' && document.execCommand('copy');
    area.remove();
    return copied ? 'Copied through the selection fallback' : null;
  }
}
async function copyCode(button) {
  const words = await copyText(button.dataset.code || '');
  const blocked = 'Clipboard blocked; select the code and copy it';
  setIcon(button, words ? 'check' : 'x', 14);
  label(button, words || blocked);
  button.title = words || blocked;
  button.dataset.state = words ? 'good' : 'bad';
  setTimeout(() => rest(button), 1500);
}
async function toggleCodeMarkdown(button) {
  const block = button.closest?.('.code-block') || button.parentElement;
  if (!block) return;
  const existing = typeof block.querySelector === 'function'
    ? block.querySelector('.code-md-preview')
    : [...(block.children || [])].find(child => child.className === 'code-md-preview');
  if (block.dataset.mdState === 'rendered') {
    delete block.dataset.mdState;
    if (existing) existing.hidden = true;
    button.setAttribute('aria-pressed', 'false');
    label(button, 'Preview Markdown');
    button.title = 'Preview Markdown';
    return;
  }
  let rendered = existing;
  if (!rendered) {
    rendered = document.createElement('div');
    rendered.className = 'code-md-preview';
    const text = button.dataset.code || '';
    if (typeof renderMessageMarkdown === 'function') {
      rendered.innerHTML = renderMessageMarkdown(text);
    } else {
      try {
        const reply = await request('/api/markdown', {
          method: 'POST',
          headers: writeHeaders('application/json'),
          body: JSON.stringify({ text }),
        });
        rendered.innerHTML = await reply.text();
      } catch {
        rendered.textContent = text;
      }
    }
    block.append(rendered);
  }
  rendered.hidden = false;
  block.dataset.mdState = 'rendered';
  button.setAttribute('aria-pressed', 'true');
  label(button, 'Show Markdown source');
  button.title = 'Show Markdown source';
}
// A click inserts `RE: <shortid>`, moves the caret after it, preserves the draft below a blank line, and replaces an existing quote prefix. The same gesture serves phones and desktops without Ctrl or a separate copy action.
// Reveal the composer's tab, restore write mode, and regrow the textarea after changes because hidden panels collapse its height and preview mode hides the quote.
function quoteId(id, control) {
  showTab(tabs[0]);
  const rest = note.value.replace(/^RE: \S+\n/, '');
  note.value = `RE: ${id}\n${rest ? `\n${rest}` : ''}`;
  writeMode();
  note.focus();
  const caret = id.length + 5;
  note.setSelectionRange(caret, caret);
  save('draft', note.value);
  control.title = `Quoted in the composer: RE: ${id}`;
}
function quoteNoteId(code) {
  // A cited note ID is its six characters, which are the whole ID of a note minted now. A report
  // ID is a slug: six characters of it name nothing, so it marks itself whole.
  const full = code.dataset.full || code.textContent;
  quoteId(code.dataset.quote === 'full' ? full : full.slice(0, 6), code);
}
// Show the report ID in the status line as a clickable code element that quotes into the composer.
function placeReportStatus() {
  const status = $('#report-status');
  const report = $('#report');
  const form = $('#report-form');
  if (!status || !report || !form) return;
  const heading = report.querySelector?.('h1, H1');
  if (heading?.parentNode) heading.parentNode.insertBefore(status, heading.nextSibling);
  else form.insertBefore?.(status, report);
}
function clearReportBody() {
  const status = $('#report-status');
  const report = $('#report');
  const form = $('#report-form');
  if (status && report && form) form.insertBefore?.(status, report);
  report.replaceChildren();
}
function reportStatusLine(text, id, answerId = null) {
  const status = $('#report-status');
  if (!id) {
    status.textContent = text;
    return;
  }
  const parts = [];
  for (const [value, full] of [[answerId, false], [id, true]]) {
    if (!value) continue;
    const code = document.createElement('code');
    code.className = 'note-id';
    code.textContent = full ? value : value.slice(0, 6);
    code.dataset.full = value;
    if (full) code.dataset.quote = 'full';
    code.title = value;
    if (parts.length) parts.push(' · ');
    parts.push(code);
  }
  if (text) {
    if (parts.length) parts.push('\n');
    parts.push(text);
  }
  status.replaceChildren(...parts);
}
function quoteTaskId(title) {
  const savedTitle = title.title;
  quoteId(title.dataset.taskId, title);
  // Keep the task tooltip after quoting.
  const row = title.closest?.('.task') || title.parentElement;
  title.title = savedTitle || row?.title || title.dataset.taskId;
}
function quoteQuestionId(target) {
  const reportId = $('#report').dataset.reportId || $('#report-select').value;
  const code = target.querySelector?.('CODE, code');
  const questionId = target.dataset?.questionId ||
    target.closest?.('.question')?.dataset?.field ||
    (code && code.textContent) ||
    (target.textContent || '').replace(/^Question ID:\s*/i, '').trim();
  if (!reportId || !questionId) return;
  quoteId(`${reportId}/${questionId}`, target);
}
// The tab buttons share one confirmation, and null text means there was nothing to copy.
const copyTimers = new WeakMap();
async function copyFrom(button, text, what, glyph = 'copy', failure = null) {
  // The label a copy came in with is the label it leaves behind, so a restored `Copy the state`
  // never names the wrong job.
  const before = button.title;
  const words = text === null ? null : await copyText(text);
  const message = words || failure || (text === null ? `There is no ${what} to copy`
    : `Clipboard blocked; select the ${what} and copy it`);
  clearTimeout(copyTimers.get(button));
  setIcon(button, words ? 'check' : 'x', 15);
  label(button, message);
  button.title = message;
  button.dataset.state = words ? 'good' : 'bad';
  copyTimers.set(button, setTimeout(() => {
    setIcon(button, typeof glyph === 'function' ? glyph() : glyph, 15);
    label(button, before);
    button.title = before;
    button.dataset.state = '';
    copyTimers.delete(button);
  }, 1500));
}
function growSlot(area) {
  // Include the border so the field does not need a scrollbar.
  area.style.height = 'auto';
  area.style.height = `${area.scrollHeight + 2}px`;
}
document.addEventListener('input', event => {
  const target = event.target;
  if (!target || typeof target.className !== 'string') return;
  const classes = target.className.split(' ');
  if (classes.includes('answer-text')) { growSlot(target); return; }
  if (!classes.includes('custom-text')) return;
  growSlot(target);
  // Typing in a slot is choosing it: the box checks itself, and blanking the text lets go again.
  const label = target.dataset.custom || '';
  const slot = byDataAttr(target.parentElement, 'label', label);
  if (slot) slot.checked = Boolean(target.value.trim());
});
document.addEventListener('click', event => {
  const image = event.target?.tagName === 'IMG' || event.target?.tagName === 'img'
    ? event.target : event.target?.closest?.('.report img');
  if (image && ($('#report')?.contains?.(image) || image.closest?.('#report, .report'))) {
    openImageModal(image);
    return;
  }
  const parent = event.target?.parentElement;
  const target = event.target?.closest?.('.copy-code, .preview-code-md, .note-id, .task-title, .question-id') ||
    (typeof parent?.className === 'string' && parent.className.split(' ').includes('question-id')
      ? parent : event.target);
  const reference = target?.closest?.('a.ack-reference') ||
    (typeof target?.className === 'string' && target.className.split(' ').includes('ack-reference')
      ? target : null);
  if (reference) {
    event.preventDefault();
    followReference(reference.dataset.referenceType, reference.dataset.referenceId);
    return;
  }
  if (!target || typeof target.className !== 'string') return;
  const classes = target.className.split(' ');
  if (classes.includes('copy-code')) copyCode(target);
  else if (classes.includes('preview-code-md')) toggleCodeMarkdown(target);
  // An ID takes one gesture on every device: a click quotes it, with or without a modifier.
  else if (classes.includes('note-id')) quoteNoteId(target);
  else if (classes.includes('task-title')) quoteTaskId(target);
  else if (classes.includes('question-id')) quoteQuestionId(target);
});
document.addEventListener('keydown', event => {
  const target = event.target;
  if (!target || typeof target.className !== 'string' ||
      !target.className.split(' ').includes('task-title')) return;
  if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  quoteTaskId(target);
});
// Append seconds to the header's local clock.
function showClock() {
  const now = new Date();
  const clock = $('#clock');
  clock.textContent = `${clockTime(now.toISOString())}:${String(now.getSeconds()).padStart(2, '0')}`;
  clock.title = now.toLocaleDateString(undefined, {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });
}
showClock();
setInterval(showClock, 1000);
  // Copy state exports notes, tasks, and report answers for `state import`.
  // One request carries the server's NDJSON, which matches the save file.
  const copyStateButton = $('#copy-state');
  let userscriptForceSave = false;
  function enableUserscriptForceSave() {
    userscriptForceSave = true;
    setIcon(copyStateButton, 'save', 16);
    label(copyStateButton, 'Force save state');
  }
  function notifyParentPreviewReady() {
    if (typeof window !== 'undefined' && window.parent && window.parent !== window &&
        typeof window.parent.postMessage === 'function') {
      try { window.parent.postMessage({ type: 'clankers:preview-ready' }, '*'); }
      catch {}
    }
  }
  window.addEventListener('message', event => {
    if (!event || !event.data || event.data.type !== 'clankers:userscript-ready') return;
    enableUserscriptForceSave();
  });
  notifyParentPreviewReady();
  copyStateButton.addEventListener('click', async () => {
    if (userscriptForceSave && typeof window !== 'undefined' && window.parent &&
        window.parent !== window && typeof window.parent.postMessage === 'function') {
      window.parent.postMessage({ type: 'clankers:force-save' }, '*');
      setIcon(copyStateButton, 'check', 16);
      copyStateButton.dataset.state = 'good';
      label(copyStateButton, 'Force save requested');
      (window.setTimeout || setTimeout)(() => {
        delete copyStateButton.dataset.state;
        setIcon(copyStateButton, 'save', 16);
        label(copyStateButton, 'Force save state');
      }, 1500);
      return;
    }
    let payload = null;
    try { payload = await (await request('/api/copy-state')).json(); }
    catch { payload = null; }
    if (!payload || !payload.text) {
      return copyFrom(copyStateButton, null, 'state', 'copy', 'The state route did not answer; nothing is copied.');
    }
    await copyFrom(copyStateButton, payload.text, 'state');
  });
$('#copy-report').addEventListener('click', async () => {
  const id = $('#report-select').value;
  if (!id) return copyFrom($('#copy-report'), null, 'report');
  try {
    const source = await (await request(`/api/reports/${encodeURIComponent(id)}/source`)).text();
    copyFrom($('#copy-report'), source, 'report');
  } catch {
    copyFrom($('#copy-report'), null, 'report');
  }
});
function savedAnswers(id) {
  try { return JSON.parse(stored(`answers:${id}`) || 'null'); }
  catch { return null; }
}
// Use the log's receipt grammar: object, state dot, and time, joined by dots without sentences.
// Show the latest of the three timestamps in the receipt and retain earlier timestamps in the object's title.
function submissionParts(report) {
  if (!report?.latest_answer_at) return '';
  return ` · Submission ${report.latest_answer_id.slice(0, 6)}`;
}
// The read stamp is report-level, so it counts only when it lands after the latest answer.
function submissionSeenAt(report) {
  const seen = report.agent_seen_at;
  return seen && seen >= report.latest_answer_at ? seen : '';
}
function submissionState(report) {
  if (report.latest_answer_acknowledged_at) return 'said';
  return submissionSeenAt(report) ? 'seen' : 'sent';
}
// Keep an agent reply unread until the owner opens the report after that reply.
// The star and tab dot carry this state, and opening the report clears it.
function ackUnread(report) {
  return Boolean(report?.latest_answer_acknowledged_at &&
    (!report.ack_seen_at || report.ack_seen_at < report.latest_answer_acknowledged_at));
}
function submissionStateWord(report) {
  if (report.pending_answer) return 'Sending';
  if (report.latest_answer_acknowledged_at) return `Acked ${time(report.latest_answer_acknowledged_at)}`;
  return submissionSeenAt(report) ? 'Awaiting ack' : 'Sent';
}
function submissionStamp(report) {
  return report.latest_answer_acknowledged_at || submissionSeenAt(report) || report.latest_answer_at;
}
function submissionStampTitle(report) {
  return `Sent ${time(report.latest_answer_at)}` +
    (submissionSeenAt(report) ? ` · Read ${time(report.agent_seen_at)}` : '') +
    (report.latest_answer_acknowledged_at ? ` · Acked ${time(report.latest_answer_acknowledged_at)}` : '');
}
function submissionReceipt(report) {
  const parts = submissionParts(report);
  if (!parts) return [];
  const separator = () => {
    const node = document.createElement('span');
    node.className = 'receipt-sep';
    node.textContent = ' · ';
    return node;
  };
  const stamp = document.createElement('span');
  stamp.textContent = parts.slice(3);
  stamp.title = submissionStampTitle(report);
  const dot = document.createElement('span');
  dot.className = 'state-dot';
  dot.dataset.state = submissionState(report);
  dot.setAttribute('role', 'img');
  dot.setAttribute('aria-label', submissionStateWord(report));
  dot.title = submissionStateWord(report);
  const when = document.createElement('span');
  when.textContent = time(submissionStamp(report));
  return [stamp, separator(), dot, separator(), when];
}
function renderReportAcknowledgement() {
  const report = getState()?.reports.find(item => item.id === $('#report-select').value);
  const receipt = $('#report-agent-ack');
  receipt.replaceChildren(...submissionReceipt(report));
  receipt.hidden = !receipt.children.length;
  const footer = $('#report-agent-ack-footer');
  footer.replaceChildren(...submissionReceipt(report));
  footer.hidden = receipt.hidden;
  const history = $('#report-ack-history');
  const references = referenceTypes(getState() || {});
  const blocks = [];
  for (const ack of report?.acknowledgements || []) {
    for (const reply of [{text: ack.ack_text, html: ack.ack_html, at: ack.acknowledged_at}, ...(ack.replies || [])]) {
      const block = document.createElement('div');
      block.className = 'reply-block';
      block.title = `Submission ${ack.id.slice(0, 6)} · ${time(reply.at)}`;
      if (reply.html !== undefined) block.innerHTML = linkReferences(reply.html, references);
      else {
        const plain = document.createElement('p');
        plain.textContent = reply.text.replace(/\\n/g, '\n');
        block.replaceChildren(plain);
      }
      blocks.push(block);
    }
  }
  history.replaceChildren(...blocks);
  history.hidden = !blocks.length;
}
// An agent unpublish lands at once, even while the owner reads. The page keeps that report
// and its row on screen until the owner clicks away, so the panel never empties under a reader.
let heldReport = null;
const reportTitles = new Map();
let reportDirty = false;
// Save checked boxes and typed answers on every edit so a reload keeps the draft.
// Submitting replaces the record with the server timestamp.
function saveReportDraft() {
  const id = $('#report').dataset.reportId;
  if (!id || id !== $('#report-select').value) return;
  const previous = savedAnswers(id);
  save(`answers:${id}`, JSON.stringify({
    answers: collect($('#report')),
    at: previous?.at || new Date().toISOString()
  }));
}
$('#report-form').addEventListener('input', () => { reportDirty = true; saveReportDraft(); });
$('#report-form').addEventListener('change', () => { reportDirty = true; saveReportDraft(); });
function nextReportId() {
  const select = $('#report-select');
  const options = [...select.children];
  const position = options.findIndex(option => option.value === select.value);
  return position < 0 ? '' : options[position + 1]?.value || '';
}
function updateReportTop() {
  const panel = $('#reports-panel');
  $('#reports-scroll-frame').hidden = panel.hidden;
  $('#report-top').hidden = panel.hidden || panel.scrollTop <= 0;
}
$('#report-top').addEventListener('click', () => {
  scrollJump($('#reports-panel'), 0);
  updateReportTop();
});
function updateReportNavigation() {
  $('#next-report').disabled = !nextReportId();
}
const MERMAID_STRICT_CONFIG = Object.freeze({
  startOnLoad: false,
  securityLevel: 'strict',
  htmlLabels: false,
  maxTextSize: 50000,
  maxEdges: 500,
  suppressErrorRendering: true,
});
function escapeSvgText(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function unescapeHtmlEntities(value) {
  return String(value)
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&#x27;/gi, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}
function sanitizeMermaidSvg(svgText) {
  if (typeof svgText !== 'string') return null;
  const trimmed = svgText.trim();
  if (!/^<[s]vg\b[\s\S]*<\/svg>$/i.test(trimmed)) return null;
  if (/<(script|foreignobject|iframe|object|embed|audio|video|canvas|applet|meta|link|style)\b/i.test(trimmed)) {
    return null;
  }
  if (/\bon[a-z]+\s*=|javascript:|vbscript:|data:text\/html|@import|\burl\s*\(\s*["']?\s*(?!#)/i.test(trimmed)) {
    return null;
  }
  if (/\b(?:xlink:)?href\s*=\s*["']?\s*(?!#)/i.test(trimmed)) {
    return null;
  }
  if (!/\bclass\s*=\s*["'][^"']*mermaid-svg/i.test(trimmed)) {
    return trimmed.replace(/^<[s]vg\b/i, '<' + 'svg class="mermaid-svg" role="img"');
  }
  return trimmed;
}
function parseFlowNodeToken(token, nodes) {
  const clean = token.trim();
  if (!clean) return null;
  const match = /^([A-Za-z0-9_.]+(?:-[A-Za-z0-9_.]+)*)(?:\[\[(.*?)\]\]|\(\((.*?)\)\)|\(\[(.*?)\]\)|\[(.*?)\]|\((.*?)\)|\{(.*?)\})?$/.exec(clean);
  if (!match) return null;
  const id = match[1];
  const rawLabel = match[2] ?? match[3] ?? match[4] ?? match[5] ?? match[6] ?? match[7];
  const shape = match[3] !== undefined ? 'circle' : match[7] !== undefined ? 'diamond' : match[4] !== undefined || match[6] !== undefined ? 'round' : 'rect';
  const existing = nodes.get(id);
  const label = rawLabel !== undefined ? rawLabel.replace(/^"(.*)"$/, '$1').trim() : (existing?.label || id);
  if (/<[a-z!/][^>]*>/i.test(label)) throw new Error('HTML labels are disabled in strict mode');
  const record = { id, label, shape: rawLabel !== undefined ? shape : (existing?.shape || 'rect') };
  nodes.set(id, record);
  return id;
}
function renderFlowchartSvg(lines, header, config) {
  const dirMatch = /^(?:flowchart|graph)(?:\s+(TD|TB|BT|LR|RL))?\s*$/.exec(header);
  if (!dirMatch) throw new Error('Invalid flowchart header');
  const dir = dirMatch[1] || 'TD';
  const horizontal = dir === 'LR' || dir === 'RL';
  const reverse = dir === 'BT' || dir === 'RL';
  const nodes = new Map();
  const edges = [];
  for (const rawLine of lines) {
    const line = rawLine.trim().replace(/;$/, '');
    if (!line || line.startsWith('%%') || /^subgraph\b/i.test(line) || /^end$/i.test(line) || /^direction\s+(?:TD|TB|BT|LR|RL)$/i.test(line)) continue;
    if (/^(?:click|callback)\b/i.test(line)) throw new Error('Interactive directives are disabled in strict mode');
    const edgeMatch = /^(.+?)\s*(?:--\s*([^>-][^>]*?)\s*-->|-\.\s*(.*?)\s*\.->|==\s*(.*?)\s*==>|--+>|\.-+>|==+>|---+)\s*(?:\|([^|]*)\|\s*)?(.+)$/.exec(line);
    if (edgeMatch) {
      const fromId = parseFlowNodeToken(edgeMatch[1], nodes);
      const toId = parseFlowNodeToken(edgeMatch[6], nodes);
      if (!fromId || !toId) throw new Error(`Invalid flowchart edge: ${line}`);
      const edgeLabel = (edgeMatch[2] ?? edgeMatch[3] ?? edgeMatch[4] ?? edgeMatch[5] ?? '').trim();
      if (/<[a-z!/][^>]*>/i.test(edgeLabel)) throw new Error('HTML labels are disabled in strict mode');
      const dotted = line.includes('-.');
      const open = /---+$/.test(line.slice(edgeMatch[1].length, line.length - edgeMatch[6].length).trim());
      edges.push({ from: fromId, to: toId, label: edgeLabel, dotted, open });
      if (edges.length > config.maxEdges) throw new Error('Mermaid edge limit exceeded');
      continue;
    }
    if (!parseFlowNodeToken(line, nodes)) throw new Error(`Invalid flowchart statement: ${line}`);
  }
  if (!nodes.size) throw new Error('Empty flowchart');
  const ordered = [...nodes.values()];
  const depths = new Map(ordered.map(node => [node.id, 0]));
  for (let pass = 0; pass < ordered.length; pass++) {
    for (const edge of edges) {
      const dFrom = depths.get(edge.from) || 0;
      const dTo = depths.get(edge.to) || 0;
      if (edge.from !== edge.to && dTo < dFrom + 1 && dFrom + 1 < ordered.length) {
        depths.set(edge.to, dFrom + 1);
      }
    }
  }
  const layers = [];
  for (const node of ordered) {
    const d = depths.get(node.id) || 0;
    if (!layers[d]) layers[d] = [];
    layers[d].push(node);
  }
  const denseLayers = layers.filter(Boolean);
  if (reverse) denseLayers.reverse();
  const maxBreadth = Math.max(1, ...denseLayers.map(layer => layer.length));
  const boxW = 148;
  const boxH = 44;
  const mainGap = 56;
  const crossGap = 36;
  const pad = 24;
  const spanW = maxBreadth * boxW + (maxBreadth - 1) * crossGap;
  const spanH = maxBreadth * boxH + (maxBreadth - 1) * crossGap;
  const coords = new Map();
  denseLayers.forEach((layer, layerIdx) => {
    const layerW = layer.length * boxW + (layer.length - 1) * crossGap;
    const layerH = layer.length * boxH + (layer.length - 1) * crossGap;
    layer.forEach((node, slotIdx) => {
      const x = horizontal
        ? pad + layerIdx * (boxW + mainGap)
        : pad + Math.round((spanW - layerW) / 2) + slotIdx * (boxW + crossGap);
      const y = horizontal
        ? pad + Math.round((spanH - layerH) / 2) + slotIdx * (boxH + crossGap)
        : pad + layerIdx * (boxH + mainGap);
      coords.set(node.id, { x, y, cx: x + boxW / 2, cy: y + boxH / 2 });
    });
  });
  const width = horizontal
    ? pad * 2 + denseLayers.length * boxW + (denseLayers.length - 1) * mainGap
    : pad * 2 + Math.max(spanW, boxW + 40);
  const height = horizontal
    ? pad * 2 + Math.max(spanH, boxH + 32)
    : pad * 2 + denseLayers.length * boxH + (denseLayers.length - 1) * mainGap;
  const parts = [
    `<${'svg'} class="mermaid-svg" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" data-diagram-type="flowchart" data-direction="${dir}">`,
    '<defs><marker id="mermaid-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="var(--muted)" /></marker></defs>',
  ];
  for (const edge of edges) {
    const a = coords.get(edge.from);
    const b = coords.get(edge.to);
    if (!a || !b) continue;
    const x1 = horizontal ? (a.cx <= b.cx ? a.x + boxW : a.x) : a.cx;
    const y1 = horizontal ? a.cy : (a.cy <= b.cy ? a.y + boxH : a.y);
    const x2 = horizontal ? (a.cx <= b.cx ? b.x : b.x + boxW) : b.cx;
    const y2 = horizontal ? b.cy : (a.cy <= b.cy ? b.y : b.y + boxH);
    const dash = edge.dotted ? ' stroke-dasharray="4 3"' : '';
    const marker = edge.open ? '' : ' marker-end="url(#mermaid-arrow)"';
    parts.push(`<line class="mermaid-edge" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="var(--muted)" stroke-width="1.5"${dash}${marker} />`);
    if (edge.label) {
      const mx = Math.round((x1 + x2) / 2);
      const my = Math.round((y1 + y2) / 2) - 6;
      parts.push(`<text class="mermaid-edge-label" x="${mx}" y="${my}" text-anchor="middle" fill="var(--muted)" font-size="12">${escapeSvgText(edge.label)}</text>`);
    }
  }
  for (const node of ordered) {
    const pos = coords.get(node.id);
    const rx = node.shape === 'round' ? 12 : node.shape === 'circle' ? 22 : 6;
    parts.push(`<g class="mermaid-node" data-node-id="${escapeSvgText(node.id)}">`);
    if (node.shape === 'diamond') {
      const pts = `${pos.cx},${pos.y - 4} ${pos.x + boxW + 6},${pos.cy} ${pos.cx},${pos.y + boxH + 4} ${pos.x - 6},${pos.cy}`;
      parts.push(`<polygon points="${pts}" fill="var(--panel)" stroke="var(--border)" stroke-width="1.5" />`);
    } else {
      parts.push(`<rect x="${pos.x}" y="${pos.y}" width="${boxW}" height="${boxH}" rx="${rx}" fill="var(--panel)" stroke="var(--border)" stroke-width="1.5" />`);
    }
    parts.push(`<text x="${pos.cx}" y="${pos.cy + 4}" text-anchor="middle" fill="var(--text)" font-size="13">${escapeSvgText(node.label)}</text></g>`);
  }
  parts.push('</svg>');
  return parts.join('');
}
function renderSequenceSvg(lines, config) {
  const actors = new Map();
  const messages = [];
  const ensureActor = (id, label = id) => {
    if (/<[a-z!/][^>]*>/i.test(label)) throw new Error('HTML labels are disabled in strict mode');
    if (!actors.has(id)) actors.set(id, { id, label: label.replace(/^"(.*)"$/, '$1').trim() });
  };
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('%%') || /^(?:autonumber|activate|deactivate|loop|alt|else|opt|par|end)\b/i.test(line)) continue;
    const partMatch = /^(?:participant|actor)\s+([A-Za-z0-9_.-]+)(?:\s+as\s+(.+))?$/i.exec(line);
    if (partMatch) {
      ensureActor(partMatch[1], partMatch[2] || partMatch[1]);
      continue;
    }
    const msgMatch = /^([A-Za-z0-9_.]+(?:-[A-Za-z0-9_.]+)*)\s*(-->>|->>|-->|->|--x|-x)\s*([A-Za-z0-9_.]+(?:-[A-Za-z0-9_.]+)*)\s*:\s*(.*)$/.exec(line);
    if (msgMatch) {
      ensureActor(msgMatch[1]);
      ensureActor(msgMatch[3]);
      if (/<[a-z!/][^>]*>/i.test(msgMatch[4])) throw new Error('HTML labels are disabled in strict mode');
      messages.push({ from: msgMatch[1], to: msgMatch[3], arrow: msgMatch[2], text: msgMatch[4].trim() });
      if (messages.length > config.maxEdges) throw new Error('Mermaid edge limit exceeded');
      continue;
    }
    throw new Error(`Invalid sequenceDiagram statement: ${line}`);
  }
  if (!actors.size) throw new Error('Empty sequenceDiagram');
  const actorList = [...actors.values()];
  const colW = 160;
  const pad = 24;
  const headH = 38;
  const rowH = 44;
  const width = Math.max(240, pad * 2 + actorList.length * colW);
  const height = pad * 2 + headH + Math.max(1, messages.length) * rowH + 24;
  const parts = [
    `<${'svg'} class="mermaid-svg" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" data-diagram-type="sequenceDiagram">`,
    '<defs><marker id="mermaid-seq-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="var(--muted)" /></marker></defs>',
  ];
  const xOf = new Map();
  actorList.forEach((actor, idx) => {
    const cx = pad + idx * colW + colW / 2;
    xOf.set(actor.id, cx);
    parts.push(`<g class="mermaid-actor" data-actor-id="${escapeSvgText(actor.id)}">`);
    parts.push(`<line x1="${cx}" y1="${pad + headH}" x2="${cx}" y2="${height - pad}" stroke="var(--border)" stroke-dasharray="4 3" />`);
    parts.push(`<rect x="${cx - 60}" y="${pad}" width="120" height="${headH}" rx="6" fill="var(--panel)" stroke="var(--border)" stroke-width="1.5" />`);
    parts.push(`<text x="${cx}" y="${pad + 23}" text-anchor="middle" fill="var(--text)" font-size="13">${escapeSvgText(actor.label)}</text></g>`);
  });
  messages.forEach((msg, idx) => {
    const y = pad + headH + (idx + 1) * rowH - 8;
    const x1 = xOf.get(msg.from) || pad;
    const x2 = xOf.get(msg.to) || pad;
    const dash = msg.arrow.startsWith('--') ? ' stroke-dasharray="4 3"' : '';
    parts.push(`<line class="mermaid-edge" x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="var(--muted)" stroke-width="1.5"${dash} marker-end="url(#mermaid-seq-arrow)" />`);
    if (msg.text) {
      parts.push(`<text class="mermaid-edge-label" x="${Math.round((x1 + x2) / 2)}" y="${y - 6}" text-anchor="middle" fill="var(--text)" font-size="12">${escapeSvgText(msg.text)}</text>`);
    }
  });
  parts.push('</svg>');
  return parts.join('');
}
function renderStateSvg(lines, config) {
  const flowLines = [];
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('%%')) continue;
    const tr = /^(\[\*\]|[A-Za-z0-9_.-]+)\s*-->\s*(\[\*\]|[A-Za-z0-9_.-]+)(?:\s*:\s*(.+))?$/.exec(line);
    if (tr) {
      const from = tr[1] === '[*]' ? 'start_state((●))' : tr[1];
      const to = tr[2] === '[*]' ? 'end_state((◉))' : tr[2];
      const label = tr[3] ? `|${tr[3].trim()}| ` : '';
      flowLines.push(`${from} --> ${label}${to}`);
      continue;
    }
    throw new Error(`Invalid stateDiagram statement: ${line}`);
  }
  return renderFlowchartSvg(flowLines, 'flowchart TD', config).replace('data-diagram-type="flowchart"', 'data-diagram-type="stateDiagram"');
}
function parseAndRenderMermaid(source, config = MERMAID_STRICT_CONFIG) {
  if (typeof source !== 'string') throw new Error('Mermaid source must be a string');
  if (source.length > config.maxTextSize) throw new Error('Mermaid source exceeds maxTextSize');
  const rawLines = source.replace(/\r\n?/g, '\n').split('\n');
  const bodyLines = [];
  let header = '';
  for (const line of rawLines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('%%')) continue;
    if (!header) header = trimmed;
    else bodyLines.push(line);
  }
  if (!header) throw new Error('Empty Mermaid diagram');
  if (/^(?:flowchart|graph)\b/.test(header)) {
    return { diagramType: 'flowchart', svg: renderFlowchartSvg(bodyLines, header, config) };
  }
  if (/^sequenceDiagram\s*$/.test(header)) {
    return { diagramType: 'sequenceDiagram', svg: renderSequenceSvg(bodyLines, config) };
  }
  if (/^stateDiagram(?:-v2)?\s*$/.test(header)) {
    return { diagramType: 'stateDiagram', svg: renderStateSvg(bodyLines, config) };
  }
  throw new Error(`Unsupported or invalid Mermaid diagram: ${header}`);
}
const mermaidRuntime = {
  config: { ...MERMAID_STRICT_CONFIG },
  initialize(overrides = {}) {
    this.config = Object.freeze({
      ...MERMAID_STRICT_CONFIG,
      ...(overrides && typeof overrides === 'object' ? overrides : {}),
      startOnLoad: false,
      securityLevel: 'strict',
      htmlLabels: false,
      suppressErrorRendering: true,
    });
    return this.config;
  },
  parse(source) {
    const { diagramType } = parseAndRenderMermaid(source, this.config);
    return { diagramType };
  },
  async render(id, source) {
    const { svg } = parseAndRenderMermaid(source, this.config);
    const safe = sanitizeMermaidSvg(svg);
    if (!safe) throw new Error('Unsafe Mermaid SVG rejected');
    return { svg: safe, id };
  },
  sanitizeSvg: sanitizeMermaidSvg,
};
globalThis.mermaid = mermaidRuntime;
const MERMAID_BLOCK_RE = /<div class="code-block">(\s*<button\b[^>]*class="copy-code"[\s\S]*?<\/button>)?\s*<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>\s*<\/div>/g;
async function renderMermaidBlocks(html, sequence) {
  if (typeof html !== 'string' || !html.includes('language-mermaid')) return html;
  const matches = [...html.matchAll(MERMAID_BLOCK_RE)];
  if (!matches.length) return html;
  let cursor = 0;
  let out = '';
  let index = 0;
  for (const match of matches) {
    if (sequence !== undefined && sequence !== reportRequest) return html;
    const [full, copyBtn = '', escapedSource = ''] = match;
    out += html.slice(cursor, match.index);
    cursor = match.index + full.length;
    const rawSource = unescapeHtmlEntities(escapedSource);
    let safeSvg = null;
    try {
      const rendered = await globalThis.mermaid.render(`mermaid-report-${sequence || 0}-${index++}`, rawSource);
      safeSvg = sanitizeMermaidSvg(typeof rendered === 'string' ? rendered : rendered?.svg);
    } catch {
      safeSvg = null;
    }
    if (safeSvg) {
      out += `<div class="code-block" data-mermaid-state="rendered">${copyBtn}<div class="mermaid-diagram" role="figure" aria-label="Mermaid diagram">${safeSvg}</div><pre><code class="language-mermaid">${escapedSource}</code></pre></div>`;
    } else {
      out += `<div class="code-block" data-mermaid-state="fallback">${copyBtn}<pre><code class="language-mermaid">${escapedSource}</code></pre></div>`;
    }
  }
  out += html.slice(cursor);
  return out;
}
async function loadReport(force = false) {
  updateReportNavigation();
  const id = $('#report-select').value;
  // A report the agent unpublished keeps its body until the owner clicks away.
  if (id && heldReport && heldReport.id === id &&
      !(getState()?.reports || []).some(report => report.id === id)) return;
  const sequence = ++reportRequest;
  // Replacing report HTML collapses the scrolling panel and clamps it to the top.
  // Preserve position for an update to the current report. Open a different report at its own top.
  const panel = $('#reports-panel');
  const place = panel.scrollTop;
  const updating = $('#report').dataset.reportId === id;
  const keepEntries = () => updating && force !== true && (reportDirty || $('#report-submit').disabled);
  if (keepEntries()) return;
  const revision = getState()?.reports.find(report => report.id === id)?.updated_at || '';
  if (!updating || !id) {
    $('#report').replaceChildren();
    $('#report-submit').hidden = true;
  }
  if (!id) {
    delete panel.dataset.loading;
    panel.setAttribute('aria-busy', 'false');
    $('#report-status').textContent = 'No report published yet.';
    return;
  }
  save('report', id);
  panel.dataset.loading = 'true';
  panel.setAttribute('aria-busy', 'true');
  $('#report-status').textContent = 'Loading report…';
  try {
    const result = await (await request(`/api/reports/${encodeURIComponent(id)}/html`)).json();
    if (sequence !== reportRequest || keepEntries()) return;
    const html = await renderMermaidBlocks(result.html, sequence);
    if (sequence !== reportRequest || keepEntries()) return;
    reportDirty = false;
    $('#report').innerHTML = html;
    $('#report').dataset.reportId = id;
    $('#report').dataset.updatedAt = revision;
    $('#report').dataset.revision = result.revision;
    panel.scrollTop = updating ? place : 0;
    updateReportTop();
    $('#report-submit').hidden = !result.fields;
    const saved = result.fields ? savedAnswers(id) : null;
    if (saved && saved.answers) {
      applyAnswers($('#report'), saved.answers);
    }
    $('#report-form').dataset.fields = result.fields;
    const report = getState()?.reports.find(item => item.id === id);
    // Show one date: Edited for a republished report, or Published.
    const stampSource = result.edited && result.published && result.edited !== result.published
      ? `Edited ${time(result.edited)}`
      : result.published || result.edited ? `Published ${time(result.published || result.edited)}` : '';
    reportStatusLine(stampSource, id, report?.latest_answer_at ? report.latest_answer_id : null);
    // Opening the report clears any unread ack immediately because the receipt sits at the panel top.
    if (report && ackUnread(report)) void markAckSeen(id);
    checkReportRead();
  } catch (error) {
    if (sequence === reportRequest) $('#report-status').textContent = `Report unavailable: ${error.message}`;
  } finally {
    if (sequence === reportRequest) {
      delete panel.dataset.loading;
      panel.setAttribute('aria-busy', 'false');
    }
  }
}
$('#report-form').addEventListener('submit', async event => {
  event.preventDefault();
  const id = $('#report').dataset.reportId;
  if (!id || id !== $('#report-select').value) return;
  const revision = $('#report').dataset.revision;
  const button = $('#report-submit');
  const answers = collect($('#report'));
  if (button.disabled) return;
  reportDirty = true;
  button.disabled = true;
  $('#report-status').textContent = 'Sending…';
  const answer = { id: newId(), answers, revision };
  const original = getState()?.reports.find(report => report.id === id)?.updated_at;
  const at = new Date().toISOString();
  const apply = (state, result) => {
    const report = state.reports.find(item => item.id === id);
    if (!report || report.updated_at !== original) return;
    Object.assign(report, { latest_answer_id: answer.id, latest_answer_at: result?.at || at,
      latest_answer_acknowledged_at: null, needs_answer: false });
    if (result) delete report.pending_answer;
    else report.pending_answer = true;
  };
  try {
    const result = await optimisticWrite(apply, async () =>
      (await request(`/api/reports/${encodeURIComponent(id)}/submit`, {
        method: 'POST', headers: writeHeaders('application/json'), body: JSON.stringify(answer)
      })).json());
    save(`answers:${id}`, JSON.stringify({ answers, at: result.at }));
    // Submitting an answer marks the report read unless an earlier read stamp exists.
    const answered = getState()?.reports.find(item => item.id === id);
    if (answered && !answered.seen_at) void markReportRead(id);
    if ($('#report').dataset.reportId !== id || $('#report').dataset.revision !== revision) return;
    reportDirty = JSON.stringify(collect($('#report'))) !== JSON.stringify(answers);
    // Keep the report ID chip after a send, matching the loaded status line.
    reportStatusLine('', id, result.id);
    void refreshState();
  } catch (error) {
    if ($('#report').dataset.reportId === id) {
      reportStatusLine(
        `Submission not confirmed: ${error.message}. Entries are kept; resending creates a new answer.`,
        id,
      );
    }
  } finally { button.disabled = false; }
});
// The CLI writes task status, and the Tasks tab reads it on the state poll.
// Build rows with textContent so hostile titles remain text.
function taskFilterType(task) {
  if (task.type === 'operations') return 'ops';
  return task.type === 'unspecified' ? 'misc' : task.type || 'misc';
}
function taskTooltip(task) {
  const stamp = task.completed_at || task.updated_at;
  const age = stamp ? time(stamp) : '';
  const hasOrder = task.order !== undefined && task.order !== null && task.order !== '';
  const first = hasOrder ? `${task.order}. ${task.id}` : task.id;
  const runs = Array.isArray(task.runs) && task.runs.length ? task.runs.join(' ') : '';
  return [first, age, runs].filter(Boolean).join('\n');
}
function rowTaskId(row) {
  return row?.dataset?.taskId || row?.querySelector?.('.task-title')?.dataset?.taskId || row?.title || '';
}
function taskRow(task) {
  const item = document.createElement('li');
  item.className = 'task';
  item.dataset.taskId = task.id;
  const tooltip = taskTooltip(task);
  item.title = tooltip;
  const title = document.createElement('span');
  title.className = 'task-title';
  title.textContent = task.title;
  title.dataset.taskId = task.id;
  title.title = tooltip;
  // A blocked task reads muted, so the queue shows what the agent can act on next.
  if (task.blocked) {
    title.dataset.blocked = 'true';
  }
  // A live linked gate overrides that muted title color without changing the rest of the row.
  if (task.runs && task.runs.length) {
    title.dataset.waitingGate = 'true';
  }
  title.tabIndex = 0;
  title.setAttribute('role', 'button');
  title.setAttribute('aria-label', `${task.title}. Task ID ${task.id}. Press Enter to quote it`);
  const rows = [title];
  // The badge sits beside the title, ahead of the details collapse.
  // An Unspecified task has no badge, so old rows keep their shape.
  const type = task.type || 'misc';
  if (type !== 'unspecified') {
    const badge = document.createElement('span');
    badge.className = 'task-type';
    badge.textContent = type === 'operations' ? 'Ops' : type[0].toUpperCase() + type.slice(1);
    badge.dataset.taskType = type;
    rows.push(badge);
  }
  const linked = task.answers && task.answers.length ? task.answers : null;
  if (task.details.length || linked) {
    // Native <details> keeps long tasks keyboard-accessible in one collapsed row without script, and its <ul> gives each detail a separate marker. Collapse linked receipts with that row so they appear only on expansion.
    // Keep every word in linked answers because the 120-character step cap applies only to manual steps.
    const details = document.createElement('details');
    details.className = 'task-details';
    const summary = document.createElement('summary');
    const count = task.details.length + (linked ? linked.length : 0);
    summary.textContent = `${count} detail${count === 1 ? '' : 's'}`;
    const parts = [summary];
    if (task.details.length) {
      const list = document.createElement('ul');
      list.className = 'task-detail-list';
      list.replaceChildren(...task.details.map(line => {
        const detail = document.createElement('li');
        detail.className = 'task-detail';
        detail.textContent = line;
        return detail;
      }));
      parts.push(list);
    }
    if (linked) {
      // Build linked answers with textContent so hostile text remains text.
      // This block permits no edits. The manual details above retain every CLI edit.
      const answers = document.createElement('div');
      answers.className = 'task-answers';
      const reports = getState()?.reports || [];
      answers.replaceChildren(...linked.map((answer) => {
        const entry = document.createElement('div');
        entry.className = 'task-answer';
        const answerId = document.createElement('code');
        answerId.textContent = answer.id;
        let answerLabel = answerId;
        if (reports.some(report => report.id === answer.report_id)) {
          const link = document.createElement('a');
          link.className = 'ack-reference';
          link.href = `#${ACK_REFERENCE_PANELS.report}`;
          link.dataset.referenceType = 'report';
          link.dataset.referenceId = answer.report_id;
          link.append(answerId);
          answerLabel = link;
        }
        const stamp = document.createElement('time');
        stamp.dateTime = answer.at;
        stamp.title = stampDate(answer.at).toLocaleString();
        stamp.textContent = time(answer.at);
        const text = document.createElement('p');
        text.className = 'task-answer-text';
        text.textContent = answer.text;
        entry.replaceChildren(answerLabel, stamp, text);
        return entry;
      }));
      parts.push(answers);
    }
    details.replaceChildren(...parts);
    if (taskSearch && parts.slice(1).some(part => part.textContent.toLowerCase().includes(taskSearch))) details.open = true;
    rows.push(details);
  }
  item.replaceChildren(...rows);
  if (taskSearch) markNode(item, taskSearch);
  return item;
}

// Guard task rendering with a payload signature because rebuilding rows closes open <details> elements.
let taskSignature = Symbol('tasks not yet rendered');
// Changing the filter re-renders the last tasks immediately, and later polls keep the filter applied.
let taskTypeFilter = 'all';
// Typing in search re-renders the last tasks immediately, and later polls keep both filters applied.
let taskSearch = '';
let lastTasksPayload = null;

function renderTasksIfChanged(tasks) {
  const published = new Set((getState()?.reports || []).map(report => report.id));
  const linked = [...(tasks?.upcoming || []), ...(tasks?.finished || [])]
    .flatMap(task => (task.answers || []).map(answer => published.has(answer.report_id)));
  const signature = JSON.stringify([tasks, linked]);
  if (signature !== taskSignature) {
    taskSignature = signature;
    renderTasks(tasks);
  } else if (tasks) {
    $('#tasks-status').textContent = `Updated ${time(tasks.updated_at)}`;
  }
  if (tasks) {
    const byId = new Map([...(tasks.upcoming || []), ...(tasks.finished || [])].map(task => [task.id, task]));
    for (const row of [...$('#tasks-current-body').children, ...$('#tasks-upcoming-body').children, ...$('#tasks-finished-body').children]) {
      const record = byId.get(rowTaskId(row));
      if (record) {
        const tooltip = taskTooltip(record);
        row.title = tooltip;
        const titleNode = row.children?.find?.(child => child.className === 'task-title') || row.querySelector?.('.task-title');
        if (titleNode) titleNode.title = tooltip;
      }
    }
  }
  for (const stamp of document.querySelectorAll('.task-answer time')) {
    stamp.textContent = time(stamp.dateTime);
    if (taskSearch) markNode(stamp, taskSearch);
  }
}

function taskHaystack(task) {
  return [task.title, task.id, task.type || 'unspecified', ...(task.details || []),
    ...(task.answers || []).flatMap(answer => [answer.id, answer.text])]
    .join(' ').toLowerCase();
}

function renderTasks(tasks) {
  const status = $('#tasks-status');
  const current = $('#tasks-current');
  const finished = $('#tasks-finished');
  const upcoming = $('#tasks-upcoming');
  lastTasksPayload = tasks;
  if (!tasks) {
    status.textContent = 'No task list yet.';
    current.hidden = true;
    finished.hidden = true;
    upcoming.hidden = true;
    return;
  }
  status.textContent = `Updated ${time(tasks.updated_at)}`;
  const visible = task =>
    (taskTypeFilter === 'all' || taskFilterType(task) === taskTypeFilter)
    && (!taskSearch || taskHaystack(task).includes(taskSearch));
  // Show the first unblocked upcoming task separately. Report-blocked tasks may sort first in the stored list.
  // Preserve stored order and the copy button's two stored sections.
  const shownUpcoming = tasks.upcoming.filter(visible);
  const head = shownUpcoming.find(task => !task.blocked);
  // The current seat and the upcoming list read as one queue, so a dragged row crosses both.
  const currentBody = $('#tasks-current-body');
  const upcomingBody = $('#tasks-upcoming-body');
  currentBody.replaceChildren(...(head ? [draggableTaskRow(head, currentBody)] : []));
  current.hidden = !head;
  $('#tasks-finished-body').replaceChildren(...tasks.finished.filter(visible).map(task => taskRow(task)));
  // The head already renders in its own div above. Re-listing it in Upcoming duplicates it.
  const restUpcoming = shownUpcoming.filter(task => task !== head);
  upcomingBody.replaceChildren(...restUpcoming.map(task => draggableTaskRow(task, upcomingBody)));
  finished.hidden = false;
  upcoming.hidden = false;
}

/*! @license Sortable 1.15.7 - MIT. Copyright (c) 2019 All contributors to Sortable. See sortable.LICENSE and gsap.LICENSE. GSAP 3.15.0 - Standard "No Charge" GreenSock License (https://gsap.com/standard-license), Copyright (c) 2008-2026 GreenSock. */

// Dragging a row inside the Upcoming area previews its landing seat and renders that order on drop.
let draggingTaskId = null;
let dragStartPayload = null;
let previewIds = null;
let touchPointerId = null;
let touchTarget = null;
function queueTaskRows() {
  return [...$('#tasks-current-body').children, ...$('#tasks-upcoming-body').children];
}
// Other queue rows keep their place.
// The dragged row lands above the hovered row or at the end on empty space.
function drawnTaskIds(list, anchorId) {
  const ids = queueTaskRows().filter(row => rowTaskId(row) !== draggingTaskId).map(row => rowTaskId(row));
  const at = anchorId ? ids.indexOf(anchorId) : -1;
  if (at >= 0) {
    ids.splice(at, 0, draggingTaskId);
    return ids;
  }
  return list === $('#tasks-current-body') ? [draggingTaskId, ...ids] : [...ids, draggingTaskId];
}
// The drawn names refill the slots they came from, so an unlisted task keeps its own slot.
function drawTaskOrder(ids) {
  const stored = lastTasksPayload;
  const drawn = ids.map(id => stored.upcoming.find(task => task.id === id));
  let next = 0;
  const upcoming = stored.upcoming
    .map(task => (ids.includes(task.id) ? drawn[next++] : task))
    .map((task, index) => ({ ...task, order: index + 1 }));
  return { ...stored, upcoming, updated_at: new Date().toISOString() };
}
// Where every row sits now, so a row that makes way can slide from its old seat.
function queueTops() {
  const tops = new Map();
  for (const row of queueTaskRows()) {
    if (typeof row.getBoundingClientRect === 'function') {
      tops.set(rowTaskId(row), row.getBoundingClientRect().top);
    }
  }
  return tops;
}

const gsapTweens = new WeakMap();
const gsapEaseMap = {
  none: 'linear',
  'power1.out': 'cubic-bezier(0.22, 1, 0.36, 1)',
  'power2.out': 'cubic-bezier(0.22, 1, 0.36, 1)',
  'ease-out': 'ease-out',
};
function gsapReducedMotion() {
  return Boolean(typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}
function gsapFrameStyle(vars = {}) {
  const style = {};
  const parts = [];
  if (vars.x !== undefined || vars.y !== undefined) {
    parts.push(`translate(${vars.x ?? 0}px, ${vars.y ?? 0}px)`);
  }
  if (vars.scale !== undefined) parts.push(`scale(${vars.scale})`);
  if (vars.rotation !== undefined) parts.push(`rotate(${vars.rotation}deg)`);
  if (parts.length) style.transform = parts.join(' ');
  if (vars.opacity !== undefined) style.opacity = String(vars.opacity);
  return style;
}
function gsapApplyStyle(target, vars = {}) {
  if (!target || !target.style) return;
  const frame = gsapFrameStyle(vars);
  for (const [prop, value] of Object.entries(frame)) target.style[prop] = value;
}
const gsap = {
  version: '3.15.0',
  killTweensOf(target) {
    if (!target || typeof target !== 'object') return;
    const active = gsapTweens.get(target);
    if (active && typeof active.cancel === 'function') {
      try { active.cancel(); } catch {}
    }
    gsapTweens.delete(target);
  },
  set(target, vars = {}) {
    if (!target || typeof target !== 'object') return this;
    this.killTweensOf(target);
    gsapApplyStyle(target, vars);
    return this;
  },
  fromTo(target, fromVars = {}, toVars = {}) {
    if (!target || typeof target !== 'object') return { kill() {} };
    this.killTweensOf(target);
    gsapApplyStyle(target, toVars);
    const ms = Math.max(0, Number(toVars.duration ?? 0.16) * 1000);
    if (!gsapReducedMotion() && ms > 0 && typeof target.animate === 'function') {
      const startFrame = gsapFrameStyle(fromVars);
      const endFrame = gsapFrameStyle(toVars);
      if (Object.keys(startFrame).length && Object.keys(endFrame).length) {
        const anim = target.animate([startFrame, endFrame], {
          duration: ms,
          easing: gsapEaseMap[toVars.ease] || toVars.ease || 'ease-out',
          iterations: toVars.repeat === -1 ? Infinity : 1 + Math.max(0, Number(toVars.repeat || 0)),
        });
        gsapTweens.set(target, anim);
      }
    }
    return { kill: () => this.killTweensOf(target) };
  },
  to(target, toVars = {}) {
    const fromVars = {};
    if (toVars.rotation !== undefined) fromVars.rotation = 0;
    if (toVars.opacity !== undefined) fromVars.opacity = 1;
    if (toVars.x !== undefined || toVars.y !== undefined) { fromVars.x = 0; fromVars.y = 0; }
    if (toVars.scale !== undefined) fromVars.scale = 1;
    return this.fromTo(target, fromVars, toVars);
  },
  from(target, fromVars = {}) {
    const toVars = { ...fromVars };
    if (fromVars.opacity !== undefined) toVars.opacity = 1;
    if (fromVars.x !== undefined) toVars.x = 0;
    if (fromVars.y !== undefined) toVars.y = 0;
    if (fromVars.scale !== undefined) toVars.scale = 1;
    return this.fromTo(target, fromVars, toVars);
  },
};
globalThis.gsap = gsap;

function slideTaskRows(before, duration = 140, easing = 'ease-out') {
  for (const row of queueTaskRows()) {
    const was = before.get(rowTaskId(row));
    if (was === undefined || typeof row.getBoundingClientRect !== 'function') continue;
    const shift = was - row.getBoundingClientRect().top;
    if (!shift) continue;
    gsap.fromTo(row, { y: shift }, { y: 0, duration: duration / 1000, ease: easing });
  }
}
// The dragged row takes its seat as the pointer moves, and a line marks that seat. The status line
// keeps its stored stamp, so a preview never reads as a saved order.
function previewTaskOrder(list, anchor) {
  delete $('#tasks-upcoming-body').dataset.drop;
  const anchorId = anchor ? rowTaskId(anchor) : null;
  const ids = drawnTaskIds(list, anchorId);
  const shown = previewIds;
  if (shown && shown.length === ids.length && shown.every((id, index) => id === ids[index])) {
    return ids;
  }
  previewIds = ids;
  const sortable = list?.sortable;
  const before = sortable ? sortable.captureAnimationState() : queueTops();
  const status = $('#tasks-status').textContent;
  renderTasksIfChanged(drawTaskOrder(ids));
  $('#tasks-status').textContent = status;
  for (const row of queueTaskRows()) {
    delete row.dataset.drop;
    if (rowTaskId(row) === draggingTaskId) {
      row.dataset.dragging = 'true';
      Sortable.ghost = row;
    } else if (anchorId && rowTaskId(row) === anchorId) {
      row.dataset.drop = 'true';
    }
  }
  if (sortable) sortable.animateAll(before);
  else slideTaskRows(before);
  return ids;
}
function endTaskDrag() {
  const panel = $('#tasks-panel');
  if (touchPointerId !== null && typeof panel.hasPointerCapture === 'function' && panel.hasPointerCapture(touchPointerId)) {
    try { panel.releasePointerCapture(touchPointerId); } catch {}
  }
  touchPointerId = null;
  touchTarget = null;
  Sortable.active = null;
  Sortable.dragged = null;
  Sortable.ghost = null;
  delete $('#tasks-upcoming-body').dataset.drop;
  delete $('#tasks-upcoming-body').dataset.dragging;
  draggingTaskId = null;
  dragStartPayload = null;
  previewIds = null;
  for (const row of queueTaskRows()) {
    delete row.dataset.dragging;
    delete row.dataset.drop;
  }
}
function startTaskDrag(row, sortable = null) {
  draggingTaskId = rowTaskId(row);
  dragStartPayload = lastTasksPayload;
  previewIds = null;
  Sortable.active = sortable;
  Sortable.dragged = row;
  Sortable.ghost = row;
  $('#tasks-upcoming-body').dataset.dragging = 'true';
  row.dataset.dragging = 'true';
}
function touchQueueSeat(node) {
  const lists = [$('#tasks-current-body'), $('#tasks-upcoming-body')];
  for (const list of lists) {
    if (node === list) return { list, row: null };
    for (const row of list.children) {
      if (row === node || (typeof row.contains === 'function' && row.contains(node))) return { list, row };
    }
  }
  return null;
}
// A drag that ends without a drop, by Escape or a release outside the queue, puts the rows back.
function cancelTaskDrag() {
  if (dragStartPayload) renderTasksIfChanged(dragStartPayload);
  endTaskDrag();
}
async function writeTaskOrder(ids, stored) {
  if (stored) renderTasksIfChanged(drawTaskOrder(ids));
  try {
    const reply = await (await request('/api/tasks/order', {
      method: 'POST', headers: writeHeaders('application/json'), body: JSON.stringify({ ids })
    })).json();
    renderTasksIfChanged(reply);
  } catch (error) {
    if (stored) renderTasksIfChanged(stored);
    $('#tasks-status').textContent = `Order not saved: ${error.message}`;
  }
}
class Sortable {
  static version = '1.15.7';
  static active = null;
  static dragged = null;
  static ghost = null;
  static instances = [];
  static create(el, options) {
    return new Sortable(el, options);
  }
  static get(el) {
    return el?.sortable || null;
  }
  constructor(el, options = {}) {
    this.el = el;
    this.options = {
      group: 'tasks-queue',
      handle: '.task-drag-handle',
      draggable: '.task',
      animation: 140,
      easing: 'ease-out',
      ghostClass: 'sortable-ghost',
      dragClass: 'sortable-drag',
      dataIdAttr: 'data-task-id',
      ...options,
    };
    el.sortable = this;
    Sortable.instances.push(this);
    this._bindList();
  }
  option(name, value) {
    if (value === undefined) return this.options[name];
    this.options[name] = value;
    return value;
  }
  toArray() {
    return [...this.el.children].map(item => rowTaskId(item) || item.getAttribute?.(this.options.dataIdAttr) || '');
  }
  captureAnimationState() {
    return this.options.animation ? queueTops() : new Map();
  }
  animateAll(before) {
    if (!this.options.animation || !before) return;
    slideTaskRows(before, this.options.animation, this.options.easing);
  }
  bindRow(row) {
    const list = this.el;
    const handle = document.createElement('button');
    handle.className = 'task-drag-handle';
    handle.type = 'button';
    handle.draggable = true;
    handle.style.touchAction = 'none';
    const taskTitle = row.querySelector?.('.task-title')?.textContent || row.children[0]?.textContent || rowTaskId(row);
    handle.setAttribute('aria-label', `Drag to reorder ${taskTitle}`);
    handle.title = `Drag to reorder ${taskTitle}`;
    row.dataset.dragHandle = 'true';
    row.insertBefore(handle, row.children[0]);
    handle.addEventListener('pointerdown', event => {
      if (event.pointerType !== 'touch' || event.isPrimary === false || (event.button ?? 0) !== 0) return;
      event.preventDefault();
      startTaskDrag(row, this);
      touchPointerId = event.pointerId;
      touchTarget = { list, row };
      if (typeof $('#tasks-panel').setPointerCapture === 'function') {
        try { $('#tasks-panel').setPointerCapture(event.pointerId); } catch {}
      }
    });
    handle.addEventListener('dragstart', event => {
      startTaskDrag(row, this);
      // Firefox starts no drag without payload data.
      if (event.dataTransfer) event.dataTransfer.setData('text/plain', rowTaskId(row));
    });
    row.addEventListener('dragover', event => {
      if (!draggingTaskId) return;
      // The seat under the pointer takes the drop, the dragged row included.
      event.preventDefault();
      if (rowTaskId(row) !== draggingTaskId) previewTaskOrder(list, row);
    });
    row.addEventListener('drop', event => {
      if (!draggingTaskId) return;
      event.preventDefault();
      const ids = rowTaskId(row) === draggingTaskId && previewIds ? previewIds : drawnTaskIds(list, rowTaskId(row));
      void writeTaskOrder(ids, dragStartPayload);
      endTaskDrag();
    });
    handle.addEventListener('dragend', cancelTaskDrag);
    return row;
  }
  _bindList() {
    const list = this.el;
    list.addEventListener('dragover', event => {
      if (!draggingTaskId || event.target !== list) return;
      event.preventDefault();
      previewTaskOrder(list, null);
      if (list.id === 'tasks-upcoming-body') list.dataset.drop = 'true';
    });
    list.addEventListener('drop', event => {
      if (!draggingTaskId || event.target !== list) return;
      event.preventDefault();
      void writeTaskOrder(drawnTaskIds(list, null), dragStartPayload);
      endTaskDrag();
    });
  }
}
globalThis.Sortable = Sortable;
function draggableTaskRow(task, list) {
  const row = taskRow(task);
  const sortable = Sortable.get(list) || Sortable.create(list, {
    group: 'tasks-queue', handle: '.task-drag-handle', draggable: '.task', animation: 140,
  });
  return sortable.bindRow(row);
}
for (const list of [$('#tasks-current-body'), $('#tasks-upcoming-body')]) {
  Sortable.create(list, {
    group: 'tasks-queue',
    handle: '.task-drag-handle',
    draggable: '.task',
    animation: 140,
  });
}
window.addEventListener('pointermove', event => {
  if (!draggingTaskId || event.pointerId !== touchPointerId) return;
  event.preventDefault();
  const seat = typeof document.elementFromPoint === 'function'
    ? touchQueueSeat(document.elementFromPoint(event.clientX, event.clientY))
    : null;
  touchTarget = seat;
  if (!seat) return;
  if (seat.row) {
    if (rowTaskId(seat.row) !== draggingTaskId) previewTaskOrder(seat.list, seat.row);
  } else {
    previewTaskOrder(seat.list, null);
    if (seat.list.id === 'tasks-upcoming-body') seat.list.dataset.drop = 'true';
  }
});
window.addEventListener('pointerup', event => {
  if (!draggingTaskId || event.pointerId !== touchPointerId) return;
  const seat = typeof document.elementFromPoint === 'function'
    ? touchQueueSeat(document.elementFromPoint(event.clientX, event.clientY))
    : touchTarget;
  if (!seat) { cancelTaskDrag(); return; }
  const ids = seat.row
    ? (rowTaskId(seat.row) === draggingTaskId && previewIds ? previewIds : drawnTaskIds(seat.list, rowTaskId(seat.row)))
    : drawnTaskIds(seat.list, null);
  void writeTaskOrder(ids, dragStartPayload);
  endTaskDrag();
});
window.addEventListener('pointercancel', event => {
  if (!draggingTaskId || event.pointerId !== touchPointerId) return;
  cancelTaskDrag();
});

$('#task-type-filter').addEventListener('change', () => {
  taskTypeFilter = $('#task-type-filter').value;
  if (lastTasksPayload) renderTasks(lastTasksPayload);
});
$('#task-search').addEventListener('input', () => {
  taskSearch = $('#task-search').value.trim().toLowerCase();
  if (lastTasksPayload) renderTasks(lastTasksPayload);
});
const tabs = [$('#notes-tab'), $('#reports-tab'), $('#tasks-tab'), $('#downloads-tab')];
// The tab pip shows whether any report remains unread, independently of the report count. Server-side read stamps survive browser resets, synchronize browsers, and tell the agent about each read.
// Exclude agent receipts and ack-open stamps from the list signature so server updates cannot rebuild the select while the owner reads.
function reportsSignature(reports) {
  return JSON.stringify(reports, (key, value) =>
    key === 'agent_seen_at' || key === 'ack_seen_at' ? undefined : value);
}
function reportLabel(report, position) {
  const markers = `${!report.seen_at || ackUnread(report) ? '*' : ''}${report.needs_answer ? '^' : ''}`;
  return `${position + 1}.${markers ? ` ${markers}` : ''} ${report.title}`;
}
let ackBatchPending = false;
function updateReportPip(reports) {
  const pip = $('#report-pip');
  // A report nobody opened, or one whose answer carries an ack the owner has not opened since,
  // is unread.
  const unseen = reports.filter(report =>
    (!report.seen_at && !report.ever_seen) || ackUnread(report));
  pip.hidden = unseen.length === 0;
  pip.title = unseen.length ? 'A report is unread' : 'No unread reports';
  pip.setAttribute('aria-label', unseen.length ? 'Unread report' : 'No unread reports');
  $('#mark-report-acks-seen').disabled = ackBatchPending || !reports.some(ackUnread);
}
function unseenReportId() {
  const state = getState();
  const reports = (state && state.reports) || [];
  const report = reports.find(item => item.id === $('#report-select').value);
  return report && !report.seen_at ? report.id : null;
}
const pendingReportReads = new Set();
async function markReportRead(id) {
  const original = getState()?.reports.find(report => report.id === id)?.updated_at;
  const readKey = `${id}:${original}`;
  if (pendingReportReads.has(readKey)) return;
  pendingReportReads.add(readKey);
  const at = new Date().toISOString();
  const apply = (state, result) => {
    const report = state.reports.find(item => item.id === id);
    if (report && report.updated_at === original) report.seen_at = result?.seen_at || at;
  };
  try {
    await optimisticWrite(apply, async () =>
      (await request(`/api/reports/${encodeURIComponent(id)}/seen`, {
        method: 'POST', headers: writeHeaders('application/json'), body: '{}'
      })).json());
  } catch (error) {
    // A later look retries a failed read stamp.
  } finally { pendingReportReads.delete(readKey); }
}
// An agent ack holds a star and the tab dot until the owner opens the report. The open is the
// gesture, not the read: the receipt sits at the top of the panel, so the visit clears it.
async function markAckSeen(id) {
  const original = getState()?.reports.find(item => item.id === id);
  if (!original) return false;
  const { latest_answer_id, latest_answer_acknowledged_at } = original;
  const at = new Date().toISOString();
  const apply = (state, result) => {
    const report = state.reports.find(item => item.id === id);
    if (report && report.latest_answer_id === latest_answer_id
        && report.latest_answer_acknowledged_at === latest_answer_acknowledged_at) {
      report.ack_seen_at = result?.ack_seen_at || at;
    }
  };
  try {
    await optimisticWrite(apply, async () => (await request(`/api/reports/${encodeURIComponent(id)}/ack-seen`, {
      method: 'POST', headers: writeHeaders('application/json'), body: '{}'
    })).json());
    return true;
  } catch (error) {
    return false;
  }
}
$('#mark-report-acks-seen').addEventListener('click', async () => {
  if (ackBatchPending) return;
  const reports = getState()?.reports || [];
  const unread = reports.filter(ackUnread);
  if (!unread.length) return;
  ackBatchPending = true;
  updateReportPip(reports);
  try {
    const saved = await Promise.all(unread.map(report => markAckSeen(report.id)));
    $('#report-status').textContent = saved.every(Boolean)
      ? 'Report acknowledgements marked seen.'
      : 'Some acknowledgements could not be marked seen; try again.';
  } finally {
    ackBatchPending = false;
    updateReportPip(getState()?.reports || []);
  }
});
// View stamps let agent changes preserve the report while the owner reads it.
// Clear the stamp in a background tab because only a visible page can record a view.
const REPORT_VIEW_MS = 30 * 1000;
const reportView = { id: null, at: 0 };
async function markReportViewed(id, active = true) {
  if (active && reportView.id === id && Date.now() - reportView.at < REPORT_VIEW_MS) return;
  reportView.id = id;
  reportView.at = active ? Date.now() : 0;
  try {
    await (await request(`/api/reports/${encodeURIComponent(id)}/view`, {
      method: 'POST', headers: writeHeaders('application/json'), body: JSON.stringify({active})
    })).json();
  } catch (error) {
    // A view stamp the owner never sees costs them nothing. The next look retries.
  }
}
function shownReportId() {
  const panel = $('#reports-panel');
  return panel.hidden ? null : $('#report-select').value || null;
}
function checkReportRead() {
  const panel = $('#reports-panel');
  const shown = shownReportId();
  if (shown && !document.hidden) void markReportViewed(shown);
  const id = panel.hidden ? null : unseenReportId();
  const report = getState()?.reports.find(item => item.id === id);
  const body = $('#report');
  if (id && !document.hidden && body.dataset.reportId === id &&
      body.dataset.updatedAt === (report?.updated_at || '')) void markReportRead(id);
}
$('#reports-panel').addEventListener('scroll', () => { checkReportRead(); updateReportTop(); });
// Leaving the report or hiding the page clears its viewed state.
document.addEventListener('visibilitychange', () => {
  const shown = shownReportId();
  if (document.hidden) {
    if (shown) void markReportViewed(shown, false);
  } else {
    checkReportRead();
  }
});
const TAB_TITLES = {
  'notes-tab': 'Messages',
  'reports-tab': 'Reports',
  'tasks-tab': 'Tasks',
  'downloads-tab': 'Downloads',
};
function syncDocumentTitle() {
  const repo = getState()?.repo || String(document.title || '').split(' - Steering')[0].trim() || 'Workspace';
  const active = tabs.find(item => item.getAttribute('aria-selected') === 'true') || tabs[0];
  const label = TAB_TITLES[active?.id] || 'Messages';
  document.title = `${repo} - Steering${label === 'Messages' ? '' : ` | ${label}`}`;
}
function showTab(tab) {
  clearJumpHighlight();
  const alreadySelected = tab.getAttribute('aria-selected') === 'true';
  const left = tab === tabs[1] ? null : shownReportId();
  for (const item of tabs) {
    const selected = tab === item;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = item.id === 'downloads-tab' ? 0 : (selected ? 0 : -1);
    const panel = $('#' + item.getAttribute('aria-controls'));
    panel.hidden = !selected;
    if (selected && !alreadySelected) gsap.fromTo(panel, { opacity: 0 }, { opacity: 1, duration: 0.16, ease: 'power1.out' });
  }
  syncDocumentTitle();
  if (tab === tabs[0]) grow();
  updateReportTop();
  if (tab === tabs[1]) {
    // Record the tab visit before the poll recomputes its pip so the marker clears during this visit.
    refreshState();
    loadReport();
  } else {
    if (left) void markReportViewed(left, false);
    releaseHeldReport(null);
  }
}
// Highlight a task or answer reached by a jump. Clear the mark after a short delay or a tab change.
// Keep the row, its data, and its order unchanged.
let jumpHighlightRow = null;
let jumpHighlightTimer = 0;

function clearJumpHighlight() {
  if (jumpHighlightTimer) {
    clearTimeout(jumpHighlightTimer);
    jumpHighlightTimer = 0;
  }
  if (jumpHighlightRow) {
    delete jumpHighlightRow.dataset.highlight;
    jumpHighlightRow = null;
  }
}

function markJumpHighlight(row) {
  clearJumpHighlight();
  jumpHighlightRow = row;
  row.dataset.highlight = 'true';
  jumpHighlightTimer = setTimeout(() => {
    jumpHighlightTimer = 0;
    delete row.dataset.highlight;
    jumpHighlightRow = null;
  }, 2500);
}

function followReference(type, id) {
  if (!ACK_REFERENCE_PANELS[type] || !lastState) return;
  if (type === 'note') {
    if (!(getState()?.notes || []).some(item => item.id === id)) return;
    showTab($('#notes-tab'));
    clearLogSearch();
    const row = revealMessage(id);
    if (!row) return;
    row.scrollIntoView({block: 'center'});
    row.setAttribute('tabindex', '-1');
    row.focus({preventScroll: true});
    return;
  }
  if (type === 'report') {
    const select = $('#report-select');
    if (!(getState()?.reports || []).some(item => item.id === id)) return;
    select.value = id;
    renderReportAcknowledgement();
    showTab($('#reports-tab'));
    select.focus();
    return;
  }
  const groups = ['upcoming', 'finished'];
  const target = groups
    .map(group => (getState().tasks?.[group] || []).find(item => item.id === id))
    .find(Boolean);
  if (!target) return;
  // A task reference switches a type filter that hides its target to the target type.
  // It clears a search query only when that query hides the target.
  const targetType = taskFilterType(target);
  if (taskTypeFilter !== 'all' && taskTypeFilter !== targetType) {
    taskTypeFilter = targetType;
    $('#task-type-filter').value = targetType;
  }
  if (taskSearch && !taskHaystack(target).includes(taskSearch)) {
    taskSearch = '';
    $('#task-search').value = '';
  }
  renderTasks(lastTasksPayload);
  showTab($('#tasks-tab'));
  const row = [
    ...$('#tasks-current-body').children,
    ...$('#tasks-upcoming-body').children,
    ...$('#tasks-finished-body').children
  ].find(item => rowTaskId(item) === id);
  const title = row && row.children[0];
  if (!title) return;
  const details = row.querySelector('details');
  if (details) details.open = true;
  title.scrollIntoView({block: 'center'});
  title.focus({preventScroll: true});
  markJumpHighlight(row);
}
for (const tab of tabs) {
  tab.addEventListener('click', () => showTab(tab));
  tab.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const step = event.key === 'ArrowRight' ? 1 : -1;
    const next = event.key === 'Home' ? tabs[0]
      : event.key === 'End' ? tabs[tabs.length - 1]
        : tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
    showTab(next);
    next.focus();
  });
}
// The server queues URLs, claims work, and stores bytes. Only the owner's browser contacts remote sites.
// Store the proxy choice per job. It supplies no global preference or automatic fallback.
function downloadName(url) {
  const part = new URL(url).pathname.split('/').filter(Boolean).at(-1) || 'download.bin';
  let name;
  try { name = decodeURIComponent(part); } catch { name = part; }
  return name.replace(/[\\/\u0000-\u001f\u007f]/g, '_').slice(0, 200) || 'download.bin';
}
function downloadRow(item) {
  const row = document.createElement('li');
  row.className = 'download-row';
  const url = document.createElement('span');
  url.className = 'fetch-url';
  url.textContent = item.url;
  const meta = document.createElement('span');
  meta.className = 'fetch-meta';
  meta.textContent = `${item.approval === 'denied' ? 'denied' : item.status}`
    + (item.source ? ` · ${item.source}` : '')
    + (item.size == null ? '' : ` · ${bytes(item.size)} · ${item.sha256.slice(0, 12)}`);
  row.append(url, meta);
  if (item.status === 'failed' && item.error) {
    const error = document.createElement('span');
    error.textContent = item.error;
    row.append(error);
    if (item.approval !== 'denied') {
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.textContent = 'Retry same URL';
      retry.addEventListener('click', async () => {
        retry.disabled = true;
        try {
          await optimisticWrite(updateJob(item.id, { status: 'queued', error: null }), async () =>
            (await request(`/api/fetch-jobs/${item.id}/retry`, {
              method: 'POST', headers: writeHeaders('application/json'), body: '{}'
            })).json());
          $('#fetch-status').textContent = `Queued ${item.url} again.`;
          await refreshState();
        } catch (failure) { $('#fetch-status').textContent = `Retry failed: ${failure.message}`; }
        finally { retry.disabled = false; }
      });
      row.append(retry);
    }
  }
  if (item.status === 'saved') {
    const where = document.createElement('span');
    where.className = item.present ? 'fetch-meta' : 'upload-gone';
    where.textContent = item.present ? `downloads/${item.file}`
      : 'The bytes are gone; the record survived a restore.';
    row.append(where);
  }
  // The owner's ✕ drops a record and the bytes it staged. It arms on the first click the way
  // report removal does, so a stray click never removes a download.
  if (item.approval !== 'pending' && !item.pending) {
    const drop = document.createElement('button');
    drop.type = 'button';
    drop.className = 'icon-button fetch-drop';
    setIcon(drop, 'x', 14);
    drop.setAttribute('aria-label', `Delete ${item.url}`);
    drop.addEventListener('click', async () => {
      if (drop.dataset.armed !== item.id) {
        drop.dataset.armed = item.id;
        drop.dataset.state = 'bad';
        $('#fetch-status').textContent = `Delete ${item.url}? Click ✕ again.`;
        setTimeout(() => {
          if (drop.dataset.armed === item.id) { delete drop.dataset.armed; delete drop.dataset.state; }
        }, 8000);
        return;
      }
      delete drop.dataset.armed;
      drop.disabled = true;
      try {
        await optimisticWrite(state => {
          state.fetch_jobs = (state.fetch_jobs || []).filter(job => job.id !== item.id);
        }, () => request(`/api/fetch-jobs/${item.id}/drop`, {
          method: 'POST', headers: writeHeaders('application/json'), body: '{}'
        }));
        $('#fetch-status').textContent = `Deleted ${item.url}.`;
        await refreshState();
      } catch (failure) { $('#fetch-status').textContent = `Delete failed: ${failure.message}`; }
      finally { drop.disabled = false; }
    });
    row.append(drop);
  }
  return row;
}
function approvalRow(item) {
  const row = document.createElement('li');
  row.className = 'download-row';
  const url = document.createElement('span');
  url.className = 'fetch-url';
  url.textContent = item.url;
  const meta = document.createElement('span');
  meta.className = 'fetch-meta';
  meta.textContent = 'Agent request';
  const actions = document.createElement('div');
  actions.className = 'row tight fetch-decisions';
  const buttons = ['approve', 'deny'].map(action => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = action === 'approve' ? 'Approve' : 'Deny';
    label(button, `${button.textContent} download of ${item.url}`);
    button.addEventListener('click', async () => {
      buttons.forEach(control => { control.disabled = true; });
      try {
        await optimisticWrite(updateJob(item.id, {
          approval: action === 'approve' ? 'approved' : 'denied',
          status: action === 'approve' ? 'queued' : 'failed',
          error: action === 'approve' ? null : 'Denied in the preview'
        }), async () => (await request(`/api/fetch-jobs/${item.id}/${action}`, {
          method: 'POST', headers: writeHeaders('application/json'), body: '{}', retryOnFailure: false
        })).json());
        $('#fetch-status').textContent = action === 'approve'
          ? `Approved ${item.url}; queued for browser download.`
          : `Denied ${item.url}; this request will not be downloaded.`;
      } catch (error) {
        $('#fetch-status').textContent = `Decision not confirmed: ${error.message}. Check the list before trying again.`;
      } finally {
        await refreshState(); // The server can accept a decision even when its response goes missing.
        buttons.forEach(control => { control.disabled = false; });
      }
    });
    return button;
  });
  actions.append(...buttons);
  row.append(url, meta, actions);
  return row;
}
// Show seven characters of the userscript key and its freshness hour so a stale key is visible without exposing the full key in the log.
// Keep the host and full timestamp in the tooltip so the footer fits a phone.
function renderAgentKey(record) {
  const line = $('#agent-key');
  if (!record) {
    line.textContent = 'No key recorded.';
    line.title = '';
    return;
  }
  // Only the key characters are monospace, so the label and the hour read as prose.
  const key = document.createElement('code');
  key.textContent = record.key.slice(0, 7);
  line.replaceChildren('Key ', key, ` · ${clock(record.at)}`);
  line.title = `${record.host ? `${record.host} · ` : ''}set ${time(record.at)}`;
}
function renderFetchIfChanged(jobs) {
  const signature = JSON.stringify(jobs);
  if (signature === fetchSignature) return;
  fetchSignature = signature;
  const pending = jobs.filter(item => item.approval === 'pending');
  const history = jobs.filter(item => item.approval !== 'pending');
  const pip = $('#downloads-pip');
  pip.hidden = pending.length === 0;
  pip.title = pending.length ? `${pending.length} download${pending.length === 1 ? '' : 's'} awaiting approval`
    : 'No downloads awaiting approval';
  pip.setAttribute('aria-label', pip.title);
  $('#fetch-approvals').replaceChildren(...pending.map(item => approvalRow(item)));
  $('#fetch-approval-count').textContent = pending.length
    ? `${pending.length} request${pending.length === 1 ? '' : 's'} awaiting approval.`
    : 'No approvals waiting.';
  $('#fetch-list').replaceChildren(...history.map(item => downloadRow(item)));
  const active = history.filter(item => item.status === 'queued' || item.status === 'fetching').length;
  const count = history.length
    ? `${history.length} in history · ${active} queued or active.`
    : 'No downloads yet.';
  $('#fetch-count').textContent = count + (pending.length ? ` · ${pending.length} awaiting approval.` : '');
}

async function fetchRemote(job) {
  // Direct access first, then the two CORS proxies: the fallback needs no opt-in.
  const candidates = [
    { source: 'direct', label: 'Direct', url: job.url },
    { source: 'allorigins', label: 'AllOrigins', url: `https://api.allorigins.win/raw?url=${encodeURIComponent(job.url)}` },
    { source: 'codetabs', label: 'CodeTabs', url: `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(job.url)}` }
  ];
  const failures = [];
  for (const candidate of candidates) {
    $('#fetch-status').textContent = `Fetching via ${candidate.label}…`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), BINARY_TIMEOUT);
    try {
      const response = await fetch(candidate.url, {
        credentials: 'omit', referrerPolicy: 'no-referrer', cache: 'no-store', signal: controller.signal
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (new URL(response.url).protocol !== 'https:') throw new Error('Redirect did not end at HTTPS');
      if (!response.body || typeof response.body.getReader !== 'function') {
        throw new Error('This browser cannot stream the response');
      }
      const reader = response.body.getReader();
      const chunks = [];
      let size = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          chunks.push(value);
        }
      } catch (error) {
        try { await reader.cancel(); } catch { /* A failed cancellation still ends this attempt. */ }
        throw error;
      }
      if (!size) throw new Error('The response was empty');
      const type = response.headers.get('content-type') || 'application/octet-stream';
      return { body: new Blob(chunks, { type }), type, source: candidate.source };
    } catch (error) {
      if (error instanceof RangeError) throw error;
      failures.push(`${candidate.label}: ${error.message || String(error)}`);
    } finally { clearTimeout(timer); }
  }
  throw new Error(failures.join('; '));
}

async function pumpFetchQueue() {
  if (fetchBusy) return;
  fetchBusy = true;
  try {
    while (true) {
      const { job } = await (await request('/api/fetch-jobs/claim', {
        method: 'POST', headers: writeHeaders('application/json'), body: '{}', retryOnFailure: false
      })).json();
      if (!job) break;
      await refreshState();
      const renew = setInterval(() => {
        void request(`/api/fetch-jobs/${job.id}/renew`, {
          method: 'POST', headers: { ...writeHeaders('application/json'), 'X-Fetch-Claim': job.claim }, body: '{}'
        }).catch(error => { $('#fetch-status').textContent = `Lease renewal failed: ${error.message}`; });
      }, 30_000);
      try {
        const file = await fetchRemote(job);
        $('#fetch-status').textContent = `Saving ${downloadName(job.url)}…`;
        const saved = await (await request(
          `/api/fetch-jobs/${job.id}/result?name=${encodeURIComponent(downloadName(job.url))}`, {
            method: 'POST',
            headers: { ...writeHeaders(file.type), 'X-Fetch-Claim': job.claim, 'X-Fetch-Source': file.source },
            body: file.body, timeoutMs: BINARY_TIMEOUT, retryOnFailure: false
          }
        )).json();
        $('#fetch-status').textContent = `Saved ${saved.name} · ${bytes(saved.size)} · ${saved.source}.`;
      } catch (error) {
        $('#fetch-status').textContent = `Download failed: ${error.message}`;
        try {
          await request(`/api/fetch-jobs/${job.id}/fail`, {
            method: 'POST',
            headers: { ...writeHeaders('application/json'), 'X-Fetch-Claim': job.claim },
            body: JSON.stringify({ error: error.message }), retryOnFailure: false
          });
        } catch (failure) {
          $('#fetch-status').textContent += ` Could not record failure: ${failure.message}. Check the queue before retrying.`;
        }
      } finally {
        clearInterval(renew);
        await refreshState();
      }
    }
  } catch (error) { $('#fetch-status').textContent = `Queue unavailable: ${error.message}`; }
  finally { fetchBusy = false; }
}
$('#fetch-form').addEventListener('submit', async event => {
  event.preventDefault();
  const field = $('#fetch-url');
  const button = $('#fetch-add');
  if (button.disabled) return;
  let parsed;
  try { parsed = new URL(field.value.trim()); }
  catch { $('#fetch-status').textContent = 'Enter one valid HTTPS URL.'; return; }
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password) {
    $('#fetch-status').textContent = 'Only HTTPS URLs without embedded credentials are allowed.';
    return;
  }
  button.disabled = true;
  try {
    const local = { id: newId(), url: field.value.trim(), status: 'queueing',
      approval: 'approved', pending: true };
    const job = await optimisticWrite(state => {
      state.fetch_jobs = [local, ...(state.fetch_jobs || [])];
    }, async () => (await request('/api/fetch-jobs', {
      method: 'POST', headers: writeHeaders('application/json'),
      body: JSON.stringify({ url: local.url, allow_proxy: true }), retryOnFailure: false
    })).json(), (state, job) => {
      state.fetch_jobs = [job, ...(state.fetch_jobs || []).filter(item => item.id !== job.id)];
    });
    $('#fetch-status').textContent = `Queued ${job.url}. Tries direct, AllOrigins, CodeTabs.`;
    field.value = '';
    await refreshState();
  } catch (error) { $('#fetch-status').textContent = `Queue not confirmed: ${error.message}. Check the list before retrying.`; }
  finally { button.disabled = false; }
});
function reportSelectionChanged() {
  releaseHeldReport($('#report-select').value);
  renderReportAcknowledgement();
  return loadReport();
}
$('#report-select').addEventListener('change', reportSelectionChanged);
$('#next-report').addEventListener('click', () => {
  const id = nextReportId();
  if (!id) return;
  $('#report-select').value = id;
  return reportSelectionChanged();
});
$('#refresh-report').addEventListener('click', () => { refreshState(); loadReport(true); });
// Removing a report requires a second click on that report before the arm expires, preventing a stray click from remaining armed.
// Remove only the tab row. The server retains the answers and source file.
let unpublishArmed = null;
let unpublishTimer = null;
function clearUnpublishArm() {
  clearTimeout(unpublishTimer);
  unpublishTimer = null;
  unpublishArmed = null;
  $('#unpublish-report').dataset.state = '';
}
document.addEventListener('click', event => {
  if (unpublishArmed && !$('#unpublish-report').contains(event.target)) {
    clearUnpublishArm();
    $('#report-status').textContent = 'Delete canceled.';
  }
}, true);
// A report the agent unpublished leaves the page when the owner clicks away, not before.
function releaseHeldReport(nextId) {
  if (!heldReport || heldReport.id === nextId) return;
  const id = heldReport.id;
  heldReport = null;
  const select = $('#report-select');
  const keep = [...select.children].filter(item => item.value !== id);
  const wasSelected = select.value === id;
  select.replaceChildren(...keep);
  if (wasSelected) select.value = keep.length ? keep[0].value : '';
  if ($('#report').dataset.reportId !== id) return;
  clearReportBody();
  delete $('#report').dataset.reportId;
  delete $('#report').dataset.updatedAt;
  delete $('#report').dataset.revision;
  save('report', '');
  $('#report-status').textContent = `Report ${id} · Unpublished by the agent.`;
}
function clearReportPanel(id) {
  if ($('#report').dataset.reportId !== id && $('#report-select').value !== id) return;
  if (heldReport?.id === id) heldReport = null;
  clearReportBody();
  delete $('#report').dataset.reportId;
  delete $('#report').dataset.updatedAt;
  delete $('#report').dataset.revision;
  const nextId = $('#report-select').value && $('#report-select').value !== id ? $('#report-select').value : '';
  save('report', nextId);
  $('#report-status').textContent = `Report ${id} · Deleted · ${time(new Date().toISOString())}`;
  listSignature = null;
  if (nextId && !$('#reports-panel').hidden) void loadReport(true);
  void refreshState();
}
$('#unpublish-report').addEventListener('click', async () => {
  const id = $('#report-select').value;
  if (!id) return;
  const button = $('#unpublish-report');
  if (unpublishArmed !== id) {
    clearUnpublishArm();
    unpublishArmed = id;
    button.dataset.state = 'bad';
    $('#report-status').textContent = `Delete ${id}? Click ✕ again to confirm.`;
    unpublishTimer = setTimeout(clearUnpublishArm, 8000);
    return;
  }
  if (button.disabled) return;
  clearUnpublishArm();
  button.disabled = true;
  try {
    const report = ((getState()?.reports) || []).find(item => item.id === id);
    if (report && ackUnread(report)) await markAckSeen(id);
    saveReportDraft();
    const remove = state => {
      if (heldReport?.id === id) heldReport = null;
      state.reports = state.reports.filter(report => report.id !== id);
    };
    await optimisticWrite(state => {
      remove(state);
      state.pending_report_deletes = [...(state.pending_report_deletes || []), id];
    }, () => request(`/api/reports/${encodeURIComponent(id)}/unpublish`, {
      method: 'POST', headers: writeHeaders('application/json'), body: '{}'
    }), remove);
    button.dataset.state = '';
    clearReportPanel(id);
  } catch (error) {
    const select = $('#report-select');
    if (!select.value || select.value === id) { select.value = id; await loadReport(true); }
    $('#report-status').textContent = `Delete failed: ${error.message}`;
  } finally { button.disabled = false; }
});
function paintInterrupt(pending) {
  const button = $('#agent-interrupt');
  const busy = button.getAttribute('aria-busy') === 'true';
  const glyph = busy ? 'loader-circle' : 'flag';
  if (button.querySelector('svg')?.getAttribute('class') !== `lucide lucide-${glyph}`) {
    setIcon(button, glyph, 16);
    const svg = button.children?.[0];
    if (busy && svg) gsap.to(svg, { rotation: 360, duration: 1, ease: 'none', repeat: -1 });
  }
  button.setAttribute('aria-pressed', pending ? 'true' : 'false');
  button.dataset.state = pending || button.dataset.error ? 'bad' : '';
  label(button, button.dataset.error || (pending
    ? `Flagged${button.dataset.type ? `: ${button.dataset.type}` : ''}. Click to cancel.`
    : 'Flag a violation'));
}
// One dialog serves every modal.
// A config builds its fields, and a failed submit keeps the form open with the error inline.
const modal = $('#modal');
const modalForm = $('#modal-form');
const imageModal = $('#image-modal');
const imageModalImg = $('#image-modal-img');
const imageModalClose = $('#image-modal-close');
let imageZoom = 1;
let imagePanX = 0;
let imagePanY = 0;
let imageDrag = null;
let imageDragMoved = false;
const imagePointers = new Map();
let imagePinch = null;
function applyImageTransform() {
  if (!imageModalImg) return;
  gsap.set(imageModalImg, { x: imagePanX, y: imagePanY, scale: imageZoom });
  imageModalImg.dataset.zoom = String(imageZoom);
  imageModalImg.dataset.panX = String(imagePanX);
  imageModalImg.dataset.panY = String(imagePanY);
}
function startImagePinch() {
  if (imagePointers.size < 2) { imagePinch = null; return; }
  const [p1, p2] = [...imagePointers.values()];
  const dist = Math.max(Math.hypot(p2.x - p1.x, p2.y - p1.y), 1);
  imagePinch = {
    dist,
    zoom: imageZoom,
    panX: imagePanX,
    panY: imagePanY,
    midX: (p1.x + p2.x) / 2,
    midY: (p1.y + p2.y) / 2,
  };
  imageDrag = null;
}
function openImageModal(image) {
  if (!imageModal || !imageModalImg) return;
  const src = image.getAttribute?.('src') || image.src || '';
  if (!src) return;
  imageModalImg.src = src;
  imageModalImg.alt = image.getAttribute?.('alt') || image.alt || '';
  imageModalImg.draggable = false;
  imageZoom = 1;
  imagePanX = 0;
  imagePanY = 0;
  imageDrag = null;
  imagePinch = null;
  imagePointers.clear();
  imageDragMoved = false;
  delete imageModalImg.dataset.dragging;
  applyImageTransform();
  imageModal.showModal();
  imageModalClose?.focus?.();
}
if (imageModal && imageModalImg) {
  imageModalImg.draggable = false;
  imageModalImg.addEventListener('dragstart', event => event.preventDefault());
  imageModalClose?.addEventListener('click', () => imageModal.close());
  imageModal.addEventListener('click', event => {
    if (imageDragMoved) { imageDragMoved = false; return; }
    if (event.target === imageModal) imageModal.close();
  });
  imageModal.addEventListener('wheel', event => {
    event.preventDefault();
    const prevZoom = imageZoom;
    const factor = event.deltaY < 0 ? 1.2 : 1 / 1.2;
    const nextZoom = Math.min(8, Math.max(0.5, Number((prevZoom * factor).toFixed(3))));
    const scaleRatio = nextZoom / prevZoom;
    if (Number.isFinite(event.clientX) && Number.isFinite(event.clientY)) {
      const rect = imageModalImg.getBoundingClientRect?.();
      const hasRect = rect && (rect.width > 0 || rect.height > 0);
      const centerX = hasRect ? rect.left + rect.width / 2 : (Number(window.innerWidth) || 0) / 2 + imagePanX;
      const centerY = hasRect ? rect.top + rect.height / 2 : (Number(window.innerHeight) || 0) / 2 + imagePanY;
      imagePanX = Number((imagePanX + (event.clientX - centerX) * (1 - scaleRatio)).toFixed(3));
      imagePanY = Number((imagePanY + (event.clientY - centerY) * (1 - scaleRatio)).toFixed(3));
    } else if (nextZoom === 1) {
      imagePanX = 0;
      imagePanY = 0;
    }
    imageZoom = nextZoom;
    applyImageTransform();
  }, { passive: false });
  imageModalImg.addEventListener('pointerdown', event => {
    if (event.button !== undefined && event.button !== 0) return;
    event.preventDefault();
    const pid = event.pointerId ?? 0;
    imagePointers.set(pid, { x: event.clientX, y: event.clientY });
    imageModalImg.setPointerCapture?.(event.pointerId);
    if (imagePointers.size >= 2) {
      imageDragMoved = true;
      startImagePinch();
      return;
    }
    imageDragMoved = false;
    imagePinch = null;
    imageDrag = {
      startX: event.clientX - imagePanX,
      startY: event.clientY - imagePanY,
      originX: event.clientX,
      originY: event.clientY,
      id: pid,
    };
    imageModalImg.dataset.dragging = 'true';
  });
  imageModalImg.addEventListener('pointermove', event => {
    const pid = event.pointerId ?? (imageDrag ? imageDrag.id : 0);
    if (imagePointers.has(pid)) imagePointers.set(pid, { x: event.clientX, y: event.clientY });
    if (imagePointers.size >= 2 && imagePinch) {
      const [p1, p2] = [...imagePointers.values()];
      const dist = Math.max(Math.hypot(p2.x - p1.x, p2.y - p1.y), 1);
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;
      const nextZoom = Math.min(8, Math.max(0.5, Number((imagePinch.zoom * (dist / imagePinch.dist)).toFixed(3))));
      const scaleRatio = nextZoom / imagePinch.zoom;
      const rect = imageModalImg.getBoundingClientRect?.();
      const hasRect = rect && (rect.width > 0 || rect.height > 0);
      const baseCenterX = hasRect
        ? rect.left + rect.width / 2 - imagePanX + imagePinch.panX
        : (Number(window.innerWidth) || 0) / 2 + imagePinch.panX;
      const baseCenterY = hasRect
        ? rect.top + rect.height / 2 - imagePanY + imagePinch.panY
        : (Number(window.innerHeight) || 0) / 2 + imagePinch.panY;
      imagePanX = Number((imagePinch.panX + (midX - imagePinch.midX) + (imagePinch.midX - baseCenterX) * (1 - scaleRatio)).toFixed(3));
      imagePanY = Number((imagePinch.panY + (midY - imagePinch.midY) + (imagePinch.midY - baseCenterY) * (1 - scaleRatio)).toFixed(3));
      imageZoom = nextZoom;
      applyImageTransform();
      return;
    }
    if (!imageDrag || pid !== imageDrag.id) return;
    if (Math.hypot(event.clientX - imageDrag.originX, event.clientY - imageDrag.originY) > 2) imageDragMoved = true;
    imagePanX = event.clientX - imageDrag.startX;
    imagePanY = event.clientY - imageDrag.startY;
    applyImageTransform();
  });
  const endImageDrag = event => {
    const pid = event?.pointerId ?? (imageDrag ? imageDrag.id : 0);
    imagePointers.delete(pid);
    if (event?.pointerId !== undefined) imageModalImg.releasePointerCapture?.(event.pointerId);
    if (imagePointers.size >= 2) {
      startImagePinch();
      return;
    }
    imagePinch = null;
    if (imagePointers.size === 1) {
      const [[remId, remPt]] = [...imagePointers.entries()];
      imageDrag = {
        startX: remPt.x - imagePanX,
        startY: remPt.y - imagePanY,
        originX: remPt.x,
        originY: remPt.y,
        id: remId,
      };
      imageModalImg.dataset.dragging = 'true';
      return;
    }
    imageDrag = null;
    delete imageModalImg.dataset.dragging;
  };
  imageModalImg.addEventListener('pointerup', endImageDrag);
  imageModalImg.addEventListener('pointercancel', endImageDrag);
}
let modalSubmit = null;
let modalBusy = false;
function modalField(field) {
  const wrapper = document.createElement('label');
  wrapper.className = 'field';
  const caption = document.createElement('span');
  caption.textContent = field.label;
  wrapper.append(caption);
  if (field.type === 'select') {
    const select = document.createElement('select');
    select.name = field.name;
    for (const [value, text] of field.options) select.add(new Option(text, value));
    if (field.value) select.value = field.value;
    wrapper.append(select);
  } else {
    const input = document.createElement(field.type === 'textarea' ? 'textarea' : 'input');
    if (field.type !== 'textarea') input.type = 'text';
    input.name = field.name;
    input.value = field.value || '';
    if (field.placeholder) input.placeholder = field.placeholder;
    if (field.maxLength) input.maxLength = field.maxLength;
    wrapper.append(input);
  }
  return wrapper;
}
// The promise resolves with the submit handler's result, or null on Esc and Cancel.
function openModal(config) {
  return new Promise(resolve => {
    const nodes = config.content ? [config.content] : config.fields.map(modalField);
    $('#modal-title').textContent = config.title;
    $('#modal-title').hidden = !!config.hideTitle;
    $('#modal-fields').replaceChildren(...nodes);
    $('#modal-error').hidden = true;
    $('#modal-confirm').textContent = config.confirm || 'Submit';
    $('#modal-confirm').hidden = !!config.readOnly;
    $('#modal-cancel').hidden = !!config.readOnly;
    $('#survey-again').hidden = true;
    modal.dataset.readOnly = String(!!config.readOnly);
    modal.dataset.wide = String(!!config.wide);
    $('#modal-cancel').textContent = config.readOnly ? 'Close' : 'Cancel';
    modalSubmit = async event => {
      event.preventDefault();
      if (modalBusy || config.readOnly) return;
      const values = Object.fromEntries(new FormData(modalForm).entries());
      modalBusy = true;
      try {
        const result = await config.submit(values);
        // Resolve before closing: the close listener answers null, and a promise settles once.
        resolve(result);
        modal.close();
      } catch (error) {
        $('#modal-error').textContent = error.message;
        $('#modal-error').hidden = false;
      } finally {
        modalBusy = false;
      }
    };
    delete modal.dataset.keyboardNav;
    modal.showModal();
    nodes[0]?.querySelector('select, input, textarea')?.focus();
    modal.addEventListener('close', () => resolve(null), { once: true });
  });
}
modalForm.addEventListener('submit', event => modalSubmit?.(event));
$('#modal-cancel').addEventListener('click', () => modal.close());
$('#modal-close')?.addEventListener('click', () => modal.close());
modal.addEventListener('keydown', event => {
  if (['Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
    modal.dataset.keyboardNav = 'true';
  }
});
modal.addEventListener('pointerdown', () => {
  delete modal.dataset.keyboardNav;
});

const SURVEY_REFRESH_MS = 2000;
let surveyView = null;
let surveyBusy = false;
let surveyRequested = false;
let surveyAnswered = false;
function surveyIsOpen(view) {
  return modal.open && $('#modal-fields').children[0] === view;
}
async function requestSurvey() {
  if (surveyRequested) return;
  surveyRequested = true;
  try {
    await request('/api/survey/request', {
      method: 'POST', headers: writeHeaders('application/json'), body: '{}'
    });
  } catch (error) {
    surveyRequested = false;
    throw error;
  }
}
function renderSurvey(view, results, answeredAt) {
  const snapshot = JSON.stringify([results, answeredAt]);
  const relative = answeredAt ? time(answeredAt) : '';
  if (view.dataset.snapshot === snapshot) {
    const age = view.querySelector('time');
    age.textContent = relative;
    age.setAttribute('aria-label', `Last answer: ${relative}`);
    $('#survey-again').disabled = surveyRequested;
    return;
  }
  surveyRequested = false;
  delete view.dataset.requestError;
  const table = document.createElement('table');
  table.className = 'survey-results';
  const header = document.createElement('thead');
  const headings = document.createElement('tr');
  for (const name of ['Correctness', 'Reported confidence']) {
    const cell = document.createElement('th');
    cell.scope = 'col';
    cell.textContent = name;
    headings.append(cell);
  }
  header.append(headings);
  const body = document.createElement('tbody');
  for (const result of results) {
    const row = document.createElement('tr');
    const id = document.createElement('th');
    id.scope = 'row';
    const state = result.correct === null ? 'unknown' : String(result.correct);
    id.dataset.correct = state;
    const code = document.createElement('code');
    code.textContent = result.id;
    id.append(icon(state === 'true' ? 'check' : state === 'false' ? 'x' : 'circle-question-mark', 16), code);
    id.setAttribute('aria-label', `${result.id}: ${state === 'true' ? 'correct' : state === 'false' ? 'incorrect' : 'unknown'}`);
    const confidence = document.createElement('td');
    confidence.className = 'survey-confidence';
    const bar = document.createElement('progress');
    bar.max = 1;
    bar.value = result.confidence;
    const upper = result.confidence > 0.5;
    const fraction = upper ? (result.confidence - 0.5) * 2 : result.confidence * 2;
    bar.style.color = `color-mix(in srgb, var(--survey-${upper ? 'warning' : 'danger'}) ${100 - fraction * 100}%, var(--survey-${upper ? 'success' : 'warning'}))`;
    const value = document.createElement('span');
    value.textContent = `${(result.confidence * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
    bar.setAttribute('aria-label', `Reported confidence for ${result.id}`);
    bar.setAttribute('aria-valuetext', value.textContent);
    confidence.append(bar, value);
    row.append(id, confidence);
    body.append(row);
  }
  table.append(header, body);
  const footer = document.createElement('div');
  footer.className = 'row';
  const age = document.createElement('time');
  age.className = 'muted';
  age.dateTime = answeredAt || '';
  age.hidden = !answeredAt;
  age.textContent = relative;
  age.setAttribute('aria-label', `Last answer: ${relative}`);
  const again = $('#survey-again');
  again.hidden = false;
  again.disabled = surveyRequested;
  footer.append(age);
  view.replaceChildren(table, footer);
  view.dataset.snapshot = snapshot;
}
async function refreshSurvey() {
  const view = surveyView;
  const open = surveyIsOpen(view);
  if ((!open && (surveyAnswered || surveyRequested)) || surveyBusy) return;
  surveyBusy = true;
  try {
    const { results, answered_at } = await (await request('/api/survey')).json();
    surveyAnswered = results !== null;
    if (results === null) {
      if (surveyIsOpen(view)) {
        $('#survey-again').hidden = true;
        view.textContent = 'No submission yet. Requesting an answer from the agent…';
      }
      if (!surveyRequested) await requestSurvey();
      if (surveyIsOpen(view)) view.textContent = 'No submission yet. A request was sent to the agent.';
    } else if (surveyIsOpen(view)) renderSurvey(view, results, answered_at);
    if (surveyIsOpen(view) && !view.dataset.requestError) $('#modal-error').hidden = true;
  } catch (error) {
    if (surveyIsOpen(view)) {
      $('#modal-error').textContent = `Survey load failed: ${error.message}. Retrying while this view stays open.`;
      $('#modal-error').hidden = false;
    }
  } finally { surveyBusy = false; }
}
$('#survey-again').addEventListener('click', async () => {
  const again = $('#survey-again');
  const view = surveyView;
  if (again.disabled || !surveyIsOpen(view)) return;
  again.disabled = true;
  try {
    await requestSurvey();
    if (surveyIsOpen(view)) {
      delete view.dataset.requestError;
      $('#modal-error').hidden = true;
    }
  } catch (error) {
    if (surveyIsOpen(view)) {
      view.dataset.requestError = 'true';
      $('#modal-error').textContent = `Survey request failed: ${error.message}. Try again.`;
      $('#modal-error').hidden = false;
    }
  } finally { again.disabled = surveyRequested; }
});
$('#survey-open').addEventListener('click', async () => {
  if (modal.open) return;
  surveyView = document.createElement('section');
  surveyView.textContent = 'Loading survey…';
  if (surveyAnswered) surveyRequested = false;
  void openModal({ title: 'Survey', content: surveyView, readOnly: true, hideTitle: true });
  $('#modal-cancel').focus();
  await refreshSurvey();
});
void refreshSurvey();
setInterval(refreshSurvey, SURVEY_REFRESH_MS);

// Violation types follow the active tab, and only paths in the repository bible can be selected.
const VIOLATION_TYPES = {
  notes: [
    ['bash-violation', 'Bash violation'],
    ['process-violation', 'Process violation'],
    ['missing-details', 'Missing details'],
    ['out-of-scope', 'Out of scope'],
    ['task-not-created', 'Task not created'],
  ],
  downloads: [['bash-violation', 'Bash violation'], ['process-violation', 'Process violation']],
  reports: [['format-violation', 'Format violation'], ['unnecessary-report', 'Unnecessary report'], ['wall-of-text', 'Wall of text']],
  tasks: [
    ['current-task-violation', 'Current task violation'],
    ['empty-task-list', 'Empty task list'],
    ['missing-details', 'Missing details'],
    ['out-of-scope', 'Out of scope'],
    ['task-not-created', 'Task not created'],
  ],
};
async function postInterrupt(payload) {
  const button = $('#agent-interrupt');
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  paintInterrupt(getState()?.agent_interrupt_pending);
  try {
    return await optimisticWrite(() => {}, async () => (await request('/api/agent-interrupt', {
      method: 'POST', headers: writeHeaders('application/json'), body: JSON.stringify(payload)
    })).json(), (state, result) => { state.agent_interrupt_pending = result.agent_interrupt_pending; });
  } finally {
    button.disabled = false;
    button.setAttribute('aria-busy', 'false');
    paintInterrupt(getState()?.agent_interrupt_pending);
  }
}
$('#agent-interrupt').addEventListener('click', async () => {
  const button = $('#agent-interrupt');
  if (button.disabled) return;
  const tab = tabs.find(item => item.getAttribute('aria-selected') === 'true').id.replace('-tab', '');
  delete button.dataset.error;
  // A second click disarms without a form. The modal opens only on the arming click.
  if (button.getAttribute('aria-pressed') === 'true') {
    delete button.dataset.type;
    try {
      await postInterrupt({ armed: false, tab });
    } catch (error) {
      button.dataset.error = `Request failed: ${error.message}. Click to retry.`;
      paintInterrupt(getState()?.agent_interrupt_pending);
    }
    return;
  }
  const types = VIOLATION_TYPES[tab];
  const reportId = tab === 'reports' ? $('#report-select').value || null : null;
  await openModal({
    title: 'Flag a violation',
    confirm: 'Send flag',
    fields: [
      { name: 'reason', label: 'Violation type', type: 'select', options: types },
      {
        name: 'clause_file',
        label: 'Clause file (optional)',
        type: 'select',
        options: [['', 'No clause file'], ...(getState()?.read_set || []).map(path => [path, path])],
      },
      {
        name: 'note',
        label: 'Cited reason (optional)',
        type: 'textarea',
        placeholder: 'Which clause, and what happened?',
      },
    ],
    submit: async values => {
      button.dataset.type = types.find(([type]) => type === values.reason)[1];
      await postInterrupt({
        armed: true,
        tab,
        report_id: reportId,
        reason: values.reason,
        clause_file: values.clause_file || null,
        note: values.note.trim() || null,
      });
    },
  });
});
// Skip poll toggles a one-shot flag that ends the agent's wait without leaving a note for a later turn.
// A second press cancels the skip, so an early press cannot force the wait to end.
function paintSkipPoll(skipPoll) {
  const button = $('#skip-poll');
  const armed = Boolean(skipPoll);
  button.setAttribute('aria-pressed', armed ? 'true' : 'false');
  button.dataset.state = button.dataset.error ? 'bad' : armed ? 'good' : '';
  label(button, button.dataset.error || (armed
    ? `Skip poll armed ${time(skipPoll)}; the agent ends its wait`
    : 'Ask the agent to end its wait now'));
}
$('#skip-poll').addEventListener('click', async () => {
  const button = $('#skip-poll');
  if (button.disabled) return;
  delete button.dataset.error;
  button.disabled = true;
  // The button state reflects the latest poll so clicking flips the server flag cleanly.
  const arm = button.getAttribute('aria-pressed') !== 'true';
  try {
    const answer = await optimisticWrite(state => { state.skip_poll = arm ? new Date().toISOString() : null; }, async () => (await request('/api/skip-poll', {
      method: 'POST', headers: writeHeaders('application/json'), body: JSON.stringify({ skip: arm })
    })).json(), (state, answer) => { state.skip_poll = answer.skip_poll; });
    paintSkipPoll(answer.skip_poll);
  } catch (error) {
    button.dataset.error = `Skip poll failed: ${error.message}.`;
    paintSkipPoll(getState()?.skip_poll);
  }
  finally { button.disabled = false; }
});
refreshState();
startPolling();
connectSocket();
setInterval(checkSocket, 5000);
// The wait timer repaints between state refreshes, so the seconds move without a request.
setInterval(paintConnection, 1000);
// Render mints each age label once, so a long-open page keeps a stale minute count.
// A half-minute timer repaints every receipt age from its stored stamp.
function repaintReceiptAges() {
  for (const row of messageNodes.values()) {
    const receipt = row.children[2];
    const stamp = receipt && receipt.children[3];
    if (!stamp || !stamp.dataset.at) continue;
    stamp.textContent = ` · ${time(stamp.dataset.at)}` +
      (stamp.dataset.ackEditedAt ? ` · Replied again ${time(stamp.dataset.ackEditedAt)}` : '');
  }
}
setInterval(repaintReceiptAges, 30000);
