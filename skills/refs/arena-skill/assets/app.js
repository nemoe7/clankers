'use strict';
const $ = selector => document.querySelector(selector);
const note = $('#note');
const send = $('#send');
const sendIdleLabel = send.textContent;
const status = $('#send-status');
const key = 'arena-preview-v1';
// Text above either paste limit becomes one attachment.
const PASTE_LINE_LIMIT = 15;
const PASTE_CHAR_LIMIT = 1500;
const BINARY_TIMEOUT = 600_000;
let pending = null;
let stateBusy = false;
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

function stored(name) {
  try { return localStorage.getItem(`${key}:${name}`); }
  catch { return null; }
}
/*! @license Lucide 1.59.0 - ISC. Copyright (c) 2026 Lucide Icons and Contributors. See lucide.LICENSE for this and the Feather MIT license. Markdown mark: Simple Icons (CC0-1.0). */
// One table holds each shape a control can swap in, so a control redraws from the same source as its static twin in index.html.
const SVG_NS = 'http://www.w3.org/2000/svg';
const ICONS = {
  sun: [['circle', { cx: '12', cy: '12', r: '4' }], ['path', { d: 'M12 2v2' }],
    ['path', { d: 'M12 20v2' }], ['path', { d: 'm4.93 4.93 1.41 1.41' }],
    ['path', { d: 'm17.66 17.66 1.41 1.41' }], ['path', { d: 'M2 12h2' }],
    ['path', { d: 'M20 12h2' }], ['path', { d: 'm6.34 17.66-1.41 1.41' }],
    ['path', { d: 'm19.07 4.93-1.41 1.41' }]],
  moon: [['path', { d: 'M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401' }]],
  copy: [['rect', { width: '14', height: '14', x: '8', y: '8', rx: '2', ry: '2' }],
    ['path', { d: 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2' }]],
  check: [['path', { d: 'M20 6 9 17l-5-5' }]],
  x: [['path', { d: 'M18 6 6 18' }], ['path', { d: 'm6 6 12 12' }]],
  eye: [['path', { d: 'M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0' }],
    ['circle', { cx: '12', cy: '12', r: '3' }]],
  markdown: [['path', { d: 'M22.27 19.385H1.73A1.73 1.73 0 0 1 0 17.655V6.345a1.73 1.73 0 0 1 1.73-1.73h20.54A1.73 1.73 0 0 1 24 6.345v11.308a1.73 1.73 0 0 1-1.73 1.731Zm-16.501-3.462v-4.5l2.308 2.885 2.307-2.885v4.5h2.308V8.078h-2.308l-2.307 2.885-2.308-2.885H3.46v7.847Zm15.463-3.923h-2.309V8.077h-2.307V12h-2.308l3.461 4.039Z',
    fill: 'currentColor', stroke: 'none' }]],
  flag: [['path', { d: 'M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.333 2q2 0 3.067-.8A1 1 0 0 1 20 4v10a1 1 0 0 1-.4.8A6 6 0 0 1 16 16c-3 0-5-2-8-2a6 6 0 0 0-4 1.528' }]],
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

// The accessible name and the hover text say the same thing, so a button that explains itself to a
// screen reader also explains itself to a mouse.
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
    const label = getState()?.waiting_for_gates ? 'Waiting for gates...' : 'Polling…';
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
// A placeholder is a hint rather than a draft: past three lines it keeps two and an ellipsis.
function clipPlaceholder(text) {
  const lines = String(text).split('\n');
  return lines.length > 3 ? `${lines.slice(0, 2).join('\n')}\n\u2026` : lines.join('\n');
}
const STATE_WORDS = { sent: 'Sent', seen: 'Seen', said: 'Said' };
// The log search checks each row's message, rendered answer, and receipt ID. A note ID therefore finds its note.
// The copy button restores the whole log. A narrowed copy would restore a partial log as complete.
let logQuery = '';

function grow() {
  // The textarea grows with a draft and shrinks after a send.
  // Add 2px for the border so it avoids its own scrollbar. An empty field keeps the stylesheet min-height.
  if (!note.value) { note.style.height = ''; return; }
  note.style.height = 'auto';
  note.style.height = `${note.scrollHeight + 2}px`;
}
note.value = stored('draft') || '';
grow();
try { pending = JSON.parse(stored('pending') || 'null'); }
catch { status.textContent = 'Stored retry data is invalid. Draft retained; check the log before resending.'; }
note.addEventListener('input', () => {
  draftVersion++;
  grow();
  if (!save('draft', note.value)) status.textContent = 'Browser storage unavailable. Keep this page open.';
});

// File bytes stay in this browser tab, not in localStorage. Every staged file has its own removal
// control beside "Your message". Picker, drop and paste stage files before one atomic send.
let stagedFiles = [];
const picker = $('#upload-file');
const compose = $('#compose');
const attachmentInfo = file => ({
  name: file.name, size: file.size, type: file.type, lastModified: file.lastModified || null
});
function pendingFiles() {
  if (!pending) return [];
  if (Array.isArray(pending.attachments)) return pending.attachments;
  return pending.attachment ? [pending.attachment] : [];
}
function renderStagedFiles() {
  const holder = $('#staged-files');
  holder.replaceChildren(...stagedFiles.map((file, index) => {
    const chip = document.createElement('span');
    chip.className = 'staged-chip';
    const name = document.createElement('span');
    name.className = 'staged-chip-name';
    name.textContent = `${file.name} · ${bytes(file.size)}`;
    name.title = `${file.name} · ${file.size.toLocaleString()} bytes`;
    const remove = document.createElement('button');
    remove.type = 'button';
    setIcon(remove, 'x', 12);
    label(remove, `Remove ${file.name}`);
    remove.addEventListener('click', () => {
      if (send.disabled) return;
      stagedFiles.splice(index, 1);
      picker.value = '';
      renderStagedFiles();
      status.textContent = stagedFiles.length
        ? `${stagedFiles.length} file${stagedFiles.length === 1 ? '' : 's'} staged.`
        : 'Attachments removed. Draft kept.';
    });
    chip.append(name, remove);
    return chip;
  }));
  holder.hidden = !stagedFiles.length;
}
function clearStagedFiles() {
  stagedFiles = [];
  picker.value = '';
  renderStagedFiles();
}
function stageFiles(files) {
  if (send.disabled || !files.length) return;
  for (const file of files) {
    if (!file.name || file.name.length > 200) { status.textContent = 'Use filenames of 1–200 characters.'; return; }
    if (!file.size) { status.textContent = `${file.name} is empty.`; return; }
  }
  stagedFiles.push(...files);
  picker.value = '';
  renderStagedFiles();
  status.textContent = `Staged ${stagedFiles.length} file${stagedFiles.length === 1 ? '' : 's'}. Send message to save them together.`;
}
$('#attach-file').addEventListener('click', () => picker.click());
picker.addEventListener('change', () => stageFiles(Array.from(picker.files || [])));
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
    const names = new Set(stagedFiles.map(file => file.name));
    let name = `${base}.txt`;
    for (let index = 2; names.has(name); index++) name = `${base}-${index}.txt`;
    stageFiles([new File([text], name, { type: 'text/plain', lastModified: stamp })]);
    return;
  }
  if (!text) event.preventDefault();
  const stamp = Date.now();
  const names = new Set(stagedFiles.map(file => file.name));
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
if (pendingFiles().length) {
  status.textContent = `Reselect ${pendingFiles().length} file${pendingFiles().length === 1 ? '' : 's'} before retrying; this page does not store file bytes.`;
}

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
    // Both acknowledgement kinds use server HTML when available, or a text paragraph with .message p pre-wrap.
    // Append later answers below earlier ones. Each block retains its kind and timestamp title.
    const answer = node.children[1];
    if (item.ack_text) {
      answer.className = item.ack_kind === 'reply' ? 'answer reply message-text' : 'answer reply';
      answer.hidden = false;
      const blocks = (item.replies || []).map(reply => {
        const block = document.createElement('div');
        block.className = 'reply-block';
        block.title = `Replied again ${time(reply.at)}`;
        if (reply.kind === 'reply' && reply.html !== undefined) {
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
  history.scrollTop = logPinned ? history.scrollHeight : place;
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
}
// Filters can shorten the log and clamp its scroll position, then leave the next view at the first message.
// Restore the end when the owner followed it. Otherwise preserve the position they chose.
let logPinned = true;
const historyAtEnd = history =>
  history.scrollHeight - history.scrollTop - history.clientHeight < 80;
$('#history').addEventListener('scroll', () => {
  const history = $('#history');
  logPinned = historyAtEnd(history);
  if (history.scrollTop < 80) loadOlderMessages();
  updateLogJump();
});
// Show the jump bar only when a nonempty log extends beyond its panel and the owner scrolls away from the end.
// The jump returns to that end. An empty log has no destination.
function updateLogJump() {
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
  // A quiet note informs the agent, not the log: it stays in the cache and the copy state
  // while the log and its tally carry the owner-facing messages only.
  const logNotes = state.notes.filter(item => !item.quiet);
  const confirmed = logNotes.filter(item => !item.pending).length;
  const saved = confirmed ? `${confirmed} messages saved` : 'No messages yet';
  // The header carries the same tally the gate keeps, so the owner sees the call count
  // the stderr banner names without leaving the page.
  const calls = state.calls_since_message || 0;
  // The tally names the calls since the owner's first unread message and says Blocked once
  // the count reaches ten.
  callTally = calls
    ? calls >= 10
      ? ' · Blocked'
      : ` · ${calls} call${calls === 1 ? '' : 's'}`
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
    select.replaceChildren();
    state.reports.forEach((report, position) => {
      reportTitles.set(report.id, report.title);
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
    const selectedReport = state.reports.find(report => report.id === select.value);
    if (!$('#reports-panel').hidden && !pendingDelete &&
        ($('#report').dataset.reportId !== select.value ||
         $('#report').dataset.updatedAt !== (selectedReport?.updated_at || ''))) loadReport();
    // A panel already showing the report is the open, so an ack that lands in view stamps at
    // once rather than waiting for a tab switch the owner has no reason to make.
    else if (!$('#reports-panel').hidden && ackUnread(selectedReport)) void markAckSeen(select.value);
  }
  // The pip tracks reports never opened. An edited report keeps its star alone. The separate
  // receipt tracks the selected report's latest answer.
  for (const option of $('#report-select').children) {
    const position = state.reports.findIndex(report => report.id === option.value);
    if (position >= 0) option.textContent = reportLabel(state.reports[position], position);
  }
  updateReportPip(state.reports);
  updateReportNavigation();
  updateReportTop();
  renderReportAcknowledgement();
  checkReportRead();
}
async function refreshState() {
  if (stateBusy) return;
  stateBusy = true;
  let queueReady = false;
  pollCommits = [];
  try {
    const state = await (await request('/api/state')).json();
    for (const [key, entry] of optimisticState) if (entry.echo?.(state)) optimisticState.delete(key);
    for (const commit of pollCommits) commit(state);
    lastState = state;
    renderState();
    queueReady = true;
  } catch (error) { pollSince = null; setConnection('down', `Connection failed: ${error.message}. Draft kept; history may be stale.`); }
  finally {
    stateBusy = false;
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
  const draft = note.value;
  const submittedVersion = draftVersion;
  const names = stagedFiles.map(file => file.name);
  const text = draft.trim() ? draft : names.length === 1 ? `File: ${names[0]}` : `Files: ${names.join(', ')}`;
  const attachments = stagedFiles.map(attachmentInfo);
  const former = pendingFiles();
  if (pending && pending.text === text && former.length &&
      JSON.stringify(former) !== JSON.stringify(attachments)) {
    status.textContent = `Reselect the ${former.length} original files in order to retry this message ID, or edit the draft to start a new message.`;
    return;
  }
  if (!pending || pending.text !== text || JSON.stringify(former) !== JSON.stringify(attachments)) {
    pending = { id: newId(), text, ...(attachments.length ? { attachments } : {}) };
  }
  save('pending', JSON.stringify(pending));
  send.disabled = picker.disabled = $('#attach-file').disabled = true;
  send.textContent = send.dataset.busyLabel;
  status.textContent = attachments.length ? `Sending ${attachments.length} file${attachments.length === 1 ? '' : 's'} with message…` : '';
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
    const result = await optimisticWrite(apply, async () => {
      let response;
      if (stagedFiles.length) {
        const body = new FormData();
        body.append('id', pending.id);
        body.append('text', text);
        for (const file of stagedFiles) body.append('file', file, file.name);
        // The same note ID, text and file set twice is safe: the server answers with the first
        // record, so one retry after a dropped connection cannot duplicate the note.
        const postFiles = () => request('/api/notes/with-file', {
          method: 'POST', body,
          timeoutMs: BINARY_TIMEOUT, retryOnFailure: false
        });
        try { response = await postFiles(); }
        catch (error) {
          // A dropped connection arrives as a TypeError, with no status to read. The same note ID,
          // text and file set replay safely, so one retry covers a blip that lost the body.
          if (!error || error.name !== 'TypeError') throw error;
          status.textContent = 'The upload dropped once; retrying the same message ID…';
          response = await postFiles();
        }
      } else response = await request('/api/notes', {
        method: 'POST', headers: writeHeaders('application/json'), body: JSON.stringify(pending)
      });
      return response.json();
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
    const total = stagedFiles.reduce((sum, file) => sum + file.size, 0);
    const hint = stagedFiles.length > 1 && error && error.name === 'TypeError'
      ? ` The combined upload is ${bytes(total)}; if it fails again, send fewer files per message.` : '';
    status.textContent = `Save not confirmed: ${error.message}. Draft${stagedFiles.length ? ' and files' : ''} kept; retry unchanged files and text with the same message ID.${hint}`;
  }
  finally {
    send.disabled = picker.disabled = $('#attach-file').disabled = false;
    send.textContent = sendIdleLabel;
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
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && !touchPointer?.matches) {
    event.preventDefault();
    if (!send.disabled) $('#form').requestSubmit();
  }
});
function writeMode() {
  draftPreviewSequence++;
  note.hidden = false;
  grow();
  $('#draft-preview').hidden = true;
  setPreviewIcon($('#preview-note'));
  $('#preview-note').setAttribute('aria-pressed', 'false');
}
$('#preview-note').addEventListener('click', async () => {
  if (note.hidden) { writeMode(); note.focus(); return; }
  if (!note.value.trim()) { status.textContent = 'Write a message before previewing.'; return; }
  const sequence = ++draftPreviewSequence;
  note.hidden = true;
  const panel = $('#draft-preview');
  panel.hidden = false;
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
        if (label === undefined) { values.push(control.value); continue; }
        const typed = byDataAttr(field, 'custom', label);
        if (typed && typed.value.trim()) values.push(`${label}: ${typed.value.trim()}`);
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
        control.checked = values.includes(control.value);
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
// The report ID rides the status line as a code element that quotes the report to the composer,
// the one gesture the log's note IDs and the task titles carry too.
function reportStatusLine(text, id, answerId = null) {
  const status = $('#report-status');
  if (!id) {
    status.textContent = text;
    return;
  }
  const parts = text ? [text] : [];
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
  status.replaceChildren(...parts);
}
function quoteTaskId(title) {
  quoteId(title.dataset.taskId, title);
  // Keep the task ID tooltip after quoting.
  title.title = title.dataset.taskId;
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
  // The same 2px of border the composer adds. See grow().
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
  const target = event.target?.closest?.('.copy-code, .note-id, .task-title') || event.target;
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
  // An ID takes one gesture on every device: a click quotes it, with or without a modifier.
  else if (classes.includes('note-id')) quoteNoteId(target);
  else if (classes.includes('task-title')) quoteTaskId(target);
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
copyStateButton.addEventListener('click', async () => {
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
// A reload must keep the draft. The browser restores typed text but not the boxes, so every edit
// writes the answers, and a submit replaces the record with the server's own stamp.
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
  if (!id) { $('#report-status').textContent = 'No report published yet.'; return; }
  save('report', id);
  $('#report-status').textContent = 'Loading report…';
  try {
    const result = await (await request(`/api/reports/${encodeURIComponent(id)}/html`)).json();
    if (sequence !== reportRequest || keepEntries()) return;
    reportDirty = false;
    $('#report').innerHTML = result.html;
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
    // Opening the report is the gesture that clears an unread ack: the receipt sits at the top
    // of the panel, so the mark goes out on this visit rather than on a later scroll.
    if (report && ackUnread(report)) void markAckSeen(id);
    checkReportRead();
  } catch (error) {
    if (sequence === reportRequest) $('#report-status').textContent = `Report unavailable: ${error.message}`;
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
    // An accepted answer is proof the owner read the report, so the read stamps with the send, and
    // a report already stamped keeps its earlier stamp.
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
function taskRow(task) {
  const item = document.createElement('li');
  item.className = 'task';
  item.title = task.id;
  const title = document.createElement('span');
  title.className = 'task-title';
  title.textContent = task.title;
  title.dataset.taskId = task.id;
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

// Guard task rendering with a payload signature because rebuilding rows on every poll closes open <details> elements.
let taskSignature = Symbol('tasks not yet rendered');
// The filter lives beside the payload: a change re-renders the last tasks without
// waiting for a poll, and a later poll renders with the filter still applied.
let taskTypeFilter = 'all';
// The search reads like the filter: a keystroke re-renders the last payload,
// and a later poll keeps both applied.
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

// The owner sorts the queue by dragging a row inside the Upcoming area. A drag previews the landing
// seat, and the drop renders that order at once, with the reply still authoritative.
let draggingTaskId = null;
let dragStartPayload = null;
let previewIds = null;
function queueTaskRows() {
  return [...$('#tasks-current-body').children, ...$('#tasks-upcoming-body').children];
}
// Every other queue row keeps its place: the dragged row lands above the row under the pointer,
// or after the last row when a drop lands on empty space.
function drawnTaskIds(list, anchorId) {
  const ids = queueTaskRows().filter(row => row.title !== draggingTaskId).map(row => row.title);
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
      tops.set(row.title, row.getBoundingClientRect().top);
    }
  }
  return tops;
}
function slideTaskRows(before) {
  for (const row of queueTaskRows()) {
    const was = before.get(row.title);
    if (was === undefined || typeof row.getBoundingClientRect !== 'function') continue;
    const shift = was - row.getBoundingClientRect().top;
    if (!shift || typeof row.animate !== 'function') continue;
    row.animate([{ transform: `translateY(${shift}px)` }, { transform: 'translateY(0)' }],
      { duration: 140, easing: 'ease-out' });
  }
}
// The dragged row takes its seat as the pointer moves, and a line marks that seat. The status line
// keeps its stored stamp, so a preview never reads as a saved order.
function previewTaskOrder(list, anchor) {
  delete $('#tasks-upcoming-body').dataset.drop;
  const ids = drawnTaskIds(list, anchor ? anchor.title : null);
  const shown = previewIds;
  if (shown && shown.length === ids.length && shown.every((id, index) => id === ids[index])) {
    return ids;
  }
  previewIds = ids;
  const before = queueTops();
  const status = $('#tasks-status').textContent;
  renderTasksIfChanged(drawTaskOrder(ids));
  $('#tasks-status').textContent = status;
  for (const row of queueTaskRows()) {
    delete row.dataset.drop;
    if (row.title === draggingTaskId) row.dataset.dragging = 'true';
    else if (anchor && row.title === anchor.title) row.dataset.drop = 'true';
  }
  slideTaskRows(before);
  return ids;
}
function endTaskDrag() {
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
function draggableTaskRow(task, list) {
  const row = taskRow(task);
  const handle = document.createElement('button');
  handle.className = 'task-drag-handle';
  handle.type = 'button';
  handle.draggable = true;
  handle.setAttribute('aria-label', `Drag to reorder ${task.title}`);
  handle.title = `Drag to reorder ${task.title}`;
  row.dataset.dragHandle = 'true';
  row.insertBefore(handle, row.children[0]);
  handle.addEventListener('dragstart', event => {
    draggingTaskId = row.title;
    dragStartPayload = lastTasksPayload;
    previewIds = null;
    $('#tasks-upcoming-body').dataset.dragging = 'true';
    row.dataset.dragging = 'true';
    // Firefox starts no drag without payload data.
    if (event.dataTransfer) event.dataTransfer.setData('text/plain', row.title);
  });
  row.addEventListener('dragover', event => {
    if (!draggingTaskId) return;
    // The seat under the pointer takes the drop, the dragged row included.
    event.preventDefault();
    if (row.title !== draggingTaskId) previewTaskOrder(list, row);
  });
  row.addEventListener('drop', event => {
    if (!draggingTaskId) return;
    event.preventDefault();
    const ids = row.title === draggingTaskId && previewIds ? previewIds : drawnTaskIds(list, row.title);
    void writeTaskOrder(ids, dragStartPayload);
    endTaskDrag();
  });
  handle.addEventListener('dragend', cancelTaskDrag);
  return row;
}
for (const list of [$('#tasks-current-body'), $('#tasks-upcoming-body')]) {
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
function showTab(tab) {
  clearJumpHighlight();
  const left = tab === tabs[1] ? null : shownReportId();
  for (const item of tabs) {
    const selected = tab === item;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
    $('#' + item.getAttribute('aria-controls')).hidden = !selected;
  }
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
  ].find(item => item.title === id);
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
  $('#report').replaceChildren();
  delete $('#report').dataset.reportId;
  delete $('#report').dataset.updatedAt;
  delete $('#report').dataset.revision;
  save('report', '');
  $('#report-status').textContent = `Report ${id} · Unpublished by the agent.`;
}
function clearReportPanel(id) {
  if ($('#report').dataset.reportId !== id && $('#report-select').value !== id) return;
  $('#report').replaceChildren();
  delete $('#report').dataset.reportId;
  delete $('#report').dataset.updatedAt;
  delete $('#report').dataset.revision;
  save('report', '');
  $('#report-status').textContent = `Report ${id} · Deleted · ${time(new Date().toISOString())}`;
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
    const remove = state => { state.reports = state.reports.filter(report => report.id !== id); };
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
  const glyph = button.getAttribute('aria-busy') === 'true' ? 'loader-circle' : 'flag';
  if (button.querySelector('svg')?.getAttribute('class') !== `lucide lucide-${glyph}`) {
    setIcon(button, glyph, 16);
  }
  button.setAttribute('aria-pressed', pending ? 'true' : 'false');
  button.dataset.state = pending || button.dataset.error ? 'bad' : '';
  label(button, button.dataset.error || (pending
    ? 'Read-set check is pending. Click to cancel.'
    : 'Ask the agent to read files missing from context'));
}
$('#agent-interrupt').addEventListener('click', async () => {
  const button = $('#agent-interrupt');
  if (button.disabled) return;
  const armed = button.getAttribute('aria-pressed') !== 'true';
  delete button.dataset.error;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  paintInterrupt(getState()?.agent_interrupt_pending);
  const tab = tabs.find(item => item.getAttribute('aria-selected') === 'true').id.replace('-tab', '');
  try {
    await optimisticWrite(() => {}, async () => (await request('/api/agent-interrupt', {
      method: 'POST', headers: writeHeaders('application/json'),
      body: JSON.stringify({ armed, tab, report_id: tab === 'reports' ? $('#report-select').value || null : null })
    })).json(), (state, result) => { state.agent_interrupt_pending = result.agent_interrupt_pending; });
  } catch (error) {
    button.dataset.error = `Request failed: ${error.message}. Click to retry.`;
    paintInterrupt(getState()?.agent_interrupt_pending);
  } finally {
    button.disabled = false;
    button.setAttribute('aria-busy', 'false');
    paintInterrupt(getState()?.agent_interrupt_pending);
  }
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
  // The painted button carries the server's own answer, so the press always flips what the
  // poll last reported and a stale view cannot re-arm a flag the owner just cleared.
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
