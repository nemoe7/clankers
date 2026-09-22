'use strict';
const $ = selector => document.querySelector(selector);
const note = $('#note');
const send = $('#send');
const status = $('#send-status');
const key = 'arena-preview-v1';
// The ceiling matches MAX_UPLOAD in preview.py, on the owner's answer.
const MAX_UPLOAD = 1_000_000;
let pending = null;
let stateBusy = false;
let reportRequest = 0;
let listSignature = '';
let lastState = null;
// The write token starts as the one baked into this page and is refreshed from every poll, so a save
// pressed after a server restart lands without a browser refresh. The owner pressed save state
// several times after a sandbox reset and nothing arrived until a manual refresh,
// and the retry that re-read the page for a token could not read the shipped minified page.
const pageToken = () => (document.body.dataset || {}).token || '__TOKEN__';
let writeToken = pageToken();
function writeHeaders(type) {
  return { 'Content-Type': type, 'X-Preview-Token': writeToken };
}
// A cited ID prefix has to be a whole visible segment, so the first hyphen sits after 7 characters.
function newId() {
  const hex = crypto.randomUUID().replaceAll('-', '');
  return `${hex.slice(0, 7)}-${hex.slice(7)}`;
}
let historySignature = '';
let draftPreviewSequence = 0;
let uploadSignature = '';
const messageNodes = new Map();

function stored(name) {
  try { return localStorage.getItem(`${key}:${name}`); }
  catch { return null; }
}
function save(name, value) {
  try { localStorage.setItem(`${key}:${name}`, value); return true; }
  catch { return false; }
}
function setTheme(theme) {
  const light = theme === 'light';
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
  const button = $('#theme');
  button.textContent = light ? '☾' : '☀';
  label(button, `Switch to ${light ? 'dark' : 'light'} mode`);
}
setTheme(stored('theme'));
$('#theme').addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  setTheme(theme);
  save('theme', theme);
});
function setPanel(name, button, open, labels) {
  document.body.dataset[name] = open ? 'open' : 'closed';
  button.setAttribute('aria-expanded', open ? 'true' : 'false');
  button.textContent = open ? labels.text[0] : labels.text[1];
  if (labels.name) label(button, open ? labels.name[0] : labels.name[1]);
}
// The accessible name and the hover text say the same thing, so a button that explains itself to a
// screen reader also explains itself to a mouse; owner note bef51970.
function label(button, text) {
  button.setAttribute('aria-label', text);
  button.title = text;
}

function setConnection(state, text) {
  const dot = $('#connection-dot');
  dot.dataset.state = state;
  dot.setAttribute('aria-label', state === 'ok' ? 'Connected' : 'Disconnected');
  $('#connection-text').textContent = text;
}
function scrollHistory(force) {
  const history = $('#history');
  const near = history.scrollHeight - history.scrollTop - history.clientHeight < 80;
  if (force || near) history.scrollTop = history.scrollHeight;
}
const chromeButton = $('#chrome');
const composerButton = $('#composer-toggle');
const chromeLabels = { text: ['▲', '▼'], name: ['Collapse bar', 'Expand bar'] };
const composerLabels = { text: ['✎', '✎'], name: ['Hide composer', 'Show composer'] };
setPanel('chrome', chromeButton, stored('chrome') !== 'closed', chromeLabels);
setPanel('composer', composerButton, stored('composer') !== 'closed', composerLabels);
chromeButton.addEventListener('click', () => {
  const open = document.body.dataset.chrome === 'closed';
  setPanel('chrome', chromeButton, open, chromeLabels);
  save('chrome', open ? 'open' : 'closed');
});
composerButton.addEventListener('click', () => {
  const open = document.body.dataset.composer === 'closed';
  setPanel('composer', composerButton, open, composerLabels);
  save('composer', open ? 'open' : 'closed');
  if (open) {
    grow();
    scrollHistory(true);
  }
});
// A placeholder is a hint rather than a draft: past three lines it keeps two and an ellipsis.
function clipPlaceholder(text) {
  const lines = String(text).split('\n');
  return lines.length > 3 ? `${lines.slice(0, 2).join('\n')}\n\u2026` : lines.join('\n');
}
const STATE_WORDS = { sent: 'Sent', seen: 'Seen', said: 'Said' };
// The log's dots already say where each message stands, so the filter selects over that and adds no
// new notion: Sent is unread and unanswered, Seen is read by the agent's poll but unanswered, Said
// is answered. The copy button stays whole-log, because it is the restore path and a filtered copy
// would restore a partial log as if it were all of it.
const LOG_FILTERS = { all: 'All messages', sent: 'Sent', seen: 'Seen', said: 'Said' };

function grow() {
  // The textarea grows with the draft instead of scrolling inside itself, so it expands upward and
  // the log gives way; when the pair no longer fits, the notes panel scrolls and the log stays
  // reachable by scrolling up. Setting height to auto first lets it shrink again after a send, and
  // the 2px are the border, which scrollHeight leaves out under box-sizing: border-box; without them
  // the box is set 2px short and answers with a scrollbar of its own.
  // An empty field keeps the stylesheet's min-height: a placeholder must not hold the box open,
  // or the composer stays expanded after a long send.
  if (!note.value) { note.style.height = ''; return; }
  note.style.height = 'auto';
  note.style.height = `${note.scrollHeight + 2}px`;
}
note.value = stored('draft') || '';
grow();
try { pending = JSON.parse(stored('pending') || 'null'); }
catch { status.textContent = 'Stored retry data is invalid. Draft retained; check the log before resending.'; }
note.addEventListener('input', () => {
  grow();
  if (!save('draft', note.value)) status.textContent = 'Browser storage unavailable. Keep this page open.';
});

// One attempt, with the abort timer every write has always carried.
async function attempt(path, options) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    return await fetch(path, { ...options, cache: 'no-store', signal: controller.signal });
  } finally { clearTimeout(timer); }
}
// A page outlives the server it came from. A sandbox reset starts the server with a new write token,
// so the copy baked into this page is refused and every write needs a manual refresh first: the
// owner pressed save state several times after a reset and nothing landed until they reloaded and
// pasted the log by hand. A refused write now takes the token from a fresh page and
// tries once more, and a write that never reached a server waits a second and tries again.
async function request(path, options = {}) {
  let response;
  try {
    response = await attempt(path, options);
  } catch {
    await new Promise((done) => setTimeout(done, 1000));
    response = await attempt(path, options);
  }
  if (response.status === 401 || response.status === 403) {
    const page = await (await fetch('/', { cache: 'no-store' })).text();
    const token = (page.match(/data-token="([^"]+)"/) || [])[1];
    if (token) {
      writeToken = token;
      const headers = { ...(options.headers || {}), 'X-Preview-Token': token };
      response = await attempt(path, { ...options, headers });
    }
  }
  if (!response.ok) {
    const message = await response.text();
    let error;
    try { error = JSON.parse(message).error; } catch { error = message; }
    throw new Error(error || `HTTP ${response.status}`);
  }
  return response;
}
function bytes(value) {
  if (value < 1000) return `${value} B`;
  if (value < 1000000) return `${Math.round(value / 1000)} kB`;
  return `${(value / 1000000).toFixed(2)} MB`;
}
function time(value) {
  // The state surface cuts stamps to seconds and drops the UTC offset. Date would read
  // those digits as local time and show the server's wall clock in every zone, so a
  // seconds-only ISO stamp is pinned to UTC before the local formatter sees it.
  const date = new Date(
    typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(value)
      ? `${value}Z`
      : value
  );
  const parts = Object.fromEntries(new Intl.DateTimeFormat(undefined, {
    month: 'short', day: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
  }).formatToParts(date).map(part => [part.type, part.value]));
  const year = date.getFullYear() === new Date().getFullYear() ? '' : ` ${parts.year}`;
  return `${parts.month} ${parts.day}${year}, ${parts.hour}:${parts.minute}`;
}
let seenEdits;
try { seenEdits = new Map(Object.entries(JSON.parse(stored('seen-edits') || '{}'))); }
catch { seenEdits = new Map(); }
let unreadEdits = [];
const editKey = item => JSON.stringify([item.ack_edited_at, item.ack_kind, item.ack_text]);
function updateEdits(notes) {
  unreadEdits = notes.filter(item => item.ack_edited_at && seenEdits.get(item.id) !== editKey(item));
  $('#notes-pip').hidden = $('#log-edited').hidden = !unreadEdits.length;
  $('#log-edited').textContent = unreadEdits.length > 1 ? `New edits (${unreadEdits.length})` : 'New edit';
}
$('#log-edited').addEventListener('click', () => {
  const item = unreadEdits[0];
  if (!item) return;
  showTab($('#notes-tab'));
  $('#log-filter').value = 'all';
  save('log-filter', 'all');
  applyLogFilter();
  const answer = messageNodes.get(item.id).children[1];
  answer.scrollIntoView({block: 'center'});
  answer.setAttribute('tabindex', '-1');
  answer.focus({preventScroll: true});
  seenEdits.set(item.id, editKey(item));
  save('seen-edits', JSON.stringify(Object.fromEntries(seenEdits)));
  updateEdits(lastState.notes);
});
function showHistory(notes) {
  const signature = JSON.stringify(notes);
  if (signature === historySignature) return;
  historySignature = signature;
  if (notes.length) note.placeholder = clipPlaceholder(notes[notes.length - 1].text);
  const history = $('#history');
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
    if (item.html === undefined) text.textContent = item.text;
    else text.innerHTML = item.html;
    const receipt = node.children[2];
    receipt.className = 'receipt';
    const receiptId = document.createElement('code');
    receiptId.className = 'note-id';
    receiptId.textContent = item.id.slice(0, 7);
    receiptId.title = item.id;
    receiptId.dataset.full = item.id;
    // Sent until the agent reads it, Seen once an explicit receipt has stamped seen_at, Said once answered.
    // The state is a coloured dot; the word lives in its title and aria-label instead of the line.
    const state = item.acknowledged_at ? 'said' : item.seen_at ? 'seen' : 'sent';
    node.dataset.state = state;
    const receiptDot = document.createElement('span');
    receiptDot.className = 'state-dot';
    receiptDot.dataset.state = state;
    receiptDot.setAttribute('role', 'img');
    receiptDot.setAttribute('aria-label', STATE_WORDS[state]);
    receiptDot.title = STATE_WORDS[state];
    const receiptState = document.createElement('span');
    receiptState.textContent = ` · ${time(item.at)}` +
      (item.ack_edited_at ? ` · Edited ${time(item.ack_edited_at)}` : '');
    // The line reads as parts separated by the same ASCII dot: ID · state · time · task.
    // The owner asked for the dot after the ID by name.
    const separator = document.createElement('span');
    separator.className = 'receipt-sep';
    separator.textContent = ' · ';
    // A message that became a task says so, so a line that was read is never mistaken for a line
    // that was dropped. The task ID rides in the title; the owner asked for the marker on note
    // fe00a32d and named it `Task added`.
    const receiptTask = document.createElement('span');
    receiptTask.className = 'receipt-task';
    receiptTask.textContent = ' · Task added';
    receiptTask.title = item.task_id ? `Task ${item.task_id}` : '';
    receipt.replaceChildren(
      receiptId, separator,
      receiptDot, receiptState, ...(item.task_id ? [receiptTask] : [])
    );
    // One answer style for both acknowledgement kinds: rendered HTML when the server sent it, and
    // otherwise the text in a paragraph, which inherits pre-wrap from .message p.
    const answer = node.children[1];
    if (item.ack_text) {
      answer.className = item.ack_kind === 'reply' ? 'answer reply message-text' : 'answer reply';
      answer.hidden = false;
      if (item.ack_html === undefined) {
        const plain = document.createElement('p');
        plain.textContent = item.ack_text;
        answer.replaceChildren(plain);
      } else answer.innerHTML = item.ack_html;
    } else {
      answer.className = 'answer';
      answer.hidden = true;
      answer.replaceChildren();
    }
  }
  // The log renders from the notes the poll carries, so a node the state no longer holds goes with
  // it; the filter's counts read the same map, and a stale row would answer a filter for a message
  // that is not there any more.
  const current = new Set(notes.map(item => item.id));
  for (const id of [...messageNodes.keys()]) if (!current.has(id)) messageNodes.delete(id);
  history.replaceChildren(...notes.map(item => messageNodes.get(item.id)));
  updateEdits(notes);
  applyLogFilter();
  if (logPinned) history.scrollTop = history.scrollHeight;
  updateLogJump();
}
// The log's own place: a filter change can make the view shorter, and the browser clamps the
// scroll without putting it back, so the next filter that shows rows again would leave the owner
// at the very first message. Being at the end is remembered and restored; scrolled away from it,
// the owner keeps the position they chose.
let logPinned = true;
const historyAtEnd = history =>
  history.scrollHeight - history.scrollTop - history.clientHeight < 80;
$('#history').addEventListener('scroll', () => {
  logPinned = historyAtEnd($('#history'));
  updateLogJump();
});
// The jump bar is the remedy for a log that is longer than its panel: it appears only while the
// log is scrolled away from its end, and it takes the log back there. An empty log has nothing to
// jump to, so it stays hidden then as well.
function updateLogJump() {
  $('#log-newest').hidden = logPinned || !messageNodes.size;
}
$('#log-newest').addEventListener('click', () => {
  const history = $('#history');
  history.scrollTop = history.scrollHeight;
  logPinned = true;
  updateLogJump();
});
function applyLogFilter() {
  const filter = $('#log-filter').value;
  let shown = 0;
  for (const node of messageNodes.values()) {
    const visible = filter === 'all' || node.dataset.state === filter;
    node.hidden = !visible;
    if (visible) shown += 1;
  }
  const total = messageNodes.size;
  $('#history').setAttribute('aria-label', filter === 'all'
    ? 'Messages, oldest first'
    : `Messages, oldest first, ${LOG_FILTERS[filter]} only`);
  const empty = $('#log-empty');
  empty.hidden = shown > 0 || total === 0;
  empty.textContent = `Nothing here is ${LOG_FILTERS[filter]} yet; ${total} message`
    + `${total === 1 ? '' : 's'} saved, and the copy button still carries all of them.`;
  if (logPinned) $('#history').scrollTop = $('#history').scrollHeight;
  updateLogJump();
}
const savedLogFilter = stored('log-filter');
$('#log-filter').value = LOG_FILTERS[savedLogFilter] ? savedLogFilter : 'all';
$('#log-filter').addEventListener('change', () => {
  save('log-filter', $('#log-filter').value);
  applyLogFilter();
});
async function refreshState() {
  if (stateBusy) return;
  stateBusy = true;
  try {
    const state = await (await request('/api/state')).json();
    lastState = state;
    if (state.token) writeToken = state.token;
    // The page keeps its own copy of what the poll delivered, so the save button still has something
    // to write after a wipe has emptied the server. Notes and tasks only: reports are re-published
    // from their sources, and the button writes what the two importers can read back.
    save('state-cache', JSON.stringify({ notes: state.notes, tasks: state.tasks }));
    setConnection('ok', state.notes.length ? `${state.notes.length} messages saved` : 'No messages yet');
    if (state.rendering_error) $('#connection-text').textContent += ` · Markdown log unavailable; raw text shown: ${state.rendering_error}`;
    $('#last-check').textContent = state.last_check ? `Last checked ${time(state.last_check)}` : 'Not checked yet.';
    showHistory(state.notes);
    renderTasksIfChanged(state.tasks);
    renderUploadsIfChanged(state.uploads);
    const signature = JSON.stringify(state.reports);
    if (signature !== listSignature) {
      listSignature = signature;
      const select = $('#report-select');
      const selected = select.value || stored('report');
      select.replaceChildren();
      state.reports.forEach((report, position) => {
        const option = document.createElement('option');
        option.value = report.id;
        option.textContent = reportLabel(report, position);
        select.append(option);
      });
      if (!state.reports.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No reports published yet';
        select.append(option);
      } else if (state.reports.some(report => report.id === selected)) select.value = selected;
      if (!$('#reports-panel').hidden) loadReport();
    }
    // The pip follows every poll: a report can grow newer than the last visit without the list changing.
    updateReportPip(state.reports);
  } catch (error) { setConnection('down', `Connection failed: ${error.message}. Draft kept; history may be stale.`); }
  finally { stateBusy = false; }
}
$('#form').addEventListener('submit', async event => {
  event.preventDefault();
  if (send.disabled || !note.value.trim()) return;
  const text = note.value;
  if (!pending || pending.text !== text) pending = { id: newId(), text };
  save('pending', JSON.stringify(pending));
  send.disabled = true;
  status.textContent = 'Sending…';
  try {
    const result = await (await request('/api/notes', {
      method: 'POST',
      headers: writeHeaders('application/json'),
      body: JSON.stringify(pending)
    })).json();
    note.placeholder = clipPlaceholder(result.text);
    status.textContent = result.acknowledged_at ? 'Saved · already acknowledged.' : `Saved ${time(result.at)} · Message sent.`;
    pending = null;
    save('pending', 'null');
    if (note.value === text) {
      note.value = '';
      save('draft', '');
      writeMode();
    }
    refreshState();
  } catch (error) { status.textContent = `Save not confirmed: ${error.message}. Draft kept; retrying unchanged text uses the same message ID.`; }
  finally { send.disabled = false; }
});
note.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    if (!send.disabled) $('#form').requestSubmit();
  }
});
function writeMode() {
  draftPreviewSequence++;
  note.hidden = false;
  grow();
  $('#draft-preview').hidden = true;
  $('#preview-note').textContent = 'MD 👁';
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
  $('#preview-note').textContent = 'MD 👁';
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
      const input = field.querySelector('input[type="text"]');
      if (input && input.value.trim()) answers[id] = input.value;
    } else {
      const values = [];
      for (const control of field.querySelectorAll('input:checked')) {
        const label = control.dataset.label;
        if (label === undefined) { values.push(control.value); continue; }
        const typed = field.querySelector(`[data-custom="${label.replace(/"/g, '\\"')}"]`);
        if (typed && typed.value.trim()) values.push(`${label}: ${typed.value.trim()}`);
      }
      if (values.length) answers[id] = field.dataset.type === 'choice' ? values[0] : values;
    }
  }
  return answers;
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
      const input = field.querySelector('input[type="text"]');
      if (input) input.value = saved;
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
  button.textContent = '⧉';
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
  button.textContent = words ? '✓' : '✗';
  label(button, words || blocked);
  button.title = words || blocked;
  button.dataset.state = words ? 'good' : 'bad';
  setTimeout(() => rest(button), 1500);
}
// A receipt's ID is the handle the owner quotes back, so a click copies the whole of it
// rather than the seven characters on show, and says which clipboard path it took.
// A plain click copies the seven characters on show; a shift-click copies the whole ID.
async function copyNoteId(code, shift) {
  const full = code.dataset.full || code.textContent;
  const text = shift ? full : code.textContent;
  const words = await copyText(text);
  code.dataset.copied = words ? 'good' : 'bad';
  code.title = words ? `${words}: ${text}` : `Clipboard blocked; the ID is ${text}`;
  setTimeout(() => {
    delete code.dataset.copied;
    code.title = full;
  }, 1500);
}
// A ctrl-click quotes the note back instead of copying it: the composer takes a `RE: <shortid>`
// line and the caret lands after it. A draft already written is kept below a blank line rather
// than lost, and a first line that is already a quote is retargeted, so quoting a second note
// replaces the prefix instead of stacking two. Meta is taken with ctrl, since that is the same
// gesture on a Mac.
function quoteNoteId(code) {
  const short = (code.dataset.full || code.textContent).slice(0, 7);
  const rest = note.value.replace(/^RE: \S+\n/, '');
  note.value = `RE: ${short}\n${rest ? `\n${rest}` : ''}`;
  if (note.hidden) writeMode();
  note.focus();
  const caret = short.length + 5;
  note.setSelectionRange(caret, caret);
  save('draft', note.value);
  code.title = `Quoted in the composer: RE: ${short}`;
}
// The three tab buttons share one confirmation, and null text means there was nothing to copy.
async function copyFrom(button, text, what, glyph = '⧉') {
  // The label a copy came in with is the label it leaves behind: the save button copies the state on
  // a shift-click and saves on a plain click, so a restored `Copy the state` would name the wrong job.
  const before = button.title;
  const words = text === null ? null : await copyText(text);
  const message = words || (text === null ? `There is no ${what} to copy`
    : `Clipboard blocked; select the ${what} and copy it`);
  button.textContent = words ? '✓' : '✗';
  label(button, message);
  button.title = message;
  button.dataset.state = words ? 'good' : 'bad';
  setTimeout(() => {
    button.textContent = typeof glyph === 'function' ? glyph() : glyph;
    label(button, before);
    button.title = before;
    button.dataset.state = '';
  }, 1500);
}
function growSlot(area) {
  // The same 2px of border the composer adds; see grow().
  area.style.height = 'auto';
  area.style.height = `${area.scrollHeight + 2}px`;
}
document.addEventListener('input', event => {
  const target = event.target;
  if (!target || typeof target.className !== 'string') return;
  if (!target.className.split(' ').includes('custom-text')) return;
  growSlot(target);
  // Typing in a slot is choosing it: the box checks itself, and blanking the text lets go again.
  const label = (target.dataset.custom || '').replace(/"/g, '\\"');
  const slot = target.parentElement && target.parentElement.querySelector(`[data-label="${label}"]`);
  if (slot) slot.checked = Boolean(target.value.trim());
});
document.addEventListener('click', event => {
  const target = event.target;
  if (!target || typeof target.className !== 'string') return;
  const classes = target.className.split(' ');
  if (classes.includes('copy-code')) copyCode(target);
  else if (classes.includes('note-id')) {
    // Three modifiers on one element: plain copies the short ID, shift the whole one, ctrl quotes.
    if (event.ctrlKey || event.metaKey) quoteNoteId(target);
    else copyNoteId(target, event.shiftKey);
  }
});
// The header clock is the log's own face with seconds appended, so the two never disagree.
function showClock() {
  const now = new Date();
  const clock = $('#clock');
  clock.textContent = `${time(now.toISOString())}:${String(now.getSeconds()).padStart(2, '0')}`;
  clock.title = now.toLocaleDateString(undefined, {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });
}
showClock();
setInterval(showClock, 1000);
// A copied timestamp stops at the seconds: the fraction and the offset cost characters on every
// line of a backup and carry nothing a restore needs. The store itself keeps full precision, so
// this is a property of the copy and not of the record.
function stamp(value) {
  return typeof value === 'string'
    ? value.replace(/\.\d+/, '').replace(/(?:Z|[+-]\d{2}:?\d{2})$/, '') : value;
}
// Each tab copies what restores or exports it: the log as the lines import-notes reads back,
// the shown report as the Markdown publish takes, the tasks as the JSON task-import reads.
// The JSON copies are minified on purpose: the agent parses them, and the whitespace only costs tokens.
// A copied line carries its receipt too, so a restore keeps the time the acknowledgement was
// actually written instead of the time the restore ran. Every key is present on every line,
// null where absent, because import-notes refuses a partial receipt rather than filling it in.
// The save button posts the cached copy to the server, which writes one file at the repository
// root for the importers to read; the report answers come from the server's own records. It is the only action that puts the page's data on disk, and it is the
// reason a restore no longer needs the owner to paste anything: the browser is the surviving copy.
// The log's copy and the tasks' copy are gone, and this button carries the copy on a shift-click
// as JSON; the reports tab keeps its own button.
// The shift-click copy carries only what a restore reads back: the note and task lines the
// save file writes, in the same keys. Nothing derived rides it: the server renders html for
// display and a restore re-renders from text, the token dies with its server, seq orders one
// display only, and reports, uploads and the last check have no importer. The stamps arrive
// from the state poll already cut to seconds, which is all a restore needs.
const NOTE_LINE_KEYS = ['id', 'text', 'at', 'acknowledged_at', 'ack_kind', 'ack_text', 'ack_edited_at', 'seen_at', 'task_id'];
const TASK_LINE_KEYS = ['id', 'title', 'details', 'status', 'order'];
function restoreLine(record, keys) {
  const line = {};
  for (const key of keys) line[key] = record[key] ?? null;
  return line;
}
function restoreCopy(cached) {
  // A session that has written no task yet is sent `tasks: null`, and its notes are still a log worth
  // copying, so the queue defaults to two empty divs instead of cancelling the copy.
  const tasks = cached.tasks || {};
  return {
    notes: cached.notes.map(note => restoreLine(note, NOTE_LINE_KEYS)),
    tasks: {
      upcoming: (tasks.upcoming || []).map(task => restoreLine(task, TASK_LINE_KEYS)),
      finished: (tasks.finished || []).map(task => restoreLine(task, TASK_LINE_KEYS)),
    },
  };
}
const saveButton = $('#save-state');
let saveHover = false, saveShift = false;
function saveGlyph() { return saveHover && saveShift ? '⧉' : '⤓'; }
function updateSaveIcon() {
  if (!['✓', '✗'].includes(saveButton.textContent)) saveButton.textContent = saveGlyph();
}
saveButton.addEventListener('pointerenter', event => {
  saveHover = true;
  saveShift = event.shiftKey;
  updateSaveIcon();
});
saveButton.addEventListener('pointerleave', () => { saveHover = false; updateSaveIcon(); });
for (const type of ['keydown', 'keyup']) {
  document.addEventListener(type, event => { saveShift = event.shiftKey; updateSaveIcon(); });
}
window.addEventListener('blur', () => { saveHover = saveShift = false; updateSaveIcon(); });
$('#save-state').addEventListener('click', async (event) => {
  const button = $('#save-state');
  if (event && event.shiftKey) {
    let cached = null;
    try { cached = JSON.parse(stored('state-cache') || 'null'); } catch { cached = null; }
    const usable = cached && Array.isArray(cached.notes);
    return copyFrom(button, usable ? `${JSON.stringify(restoreCopy(cached))}\n` : null, 'state', saveGlyph);
  }
  let cached = null;
  try { cached = JSON.parse(stored('state-cache') || 'null'); } catch { cached = null; }
  if (!cached || !Array.isArray(cached.notes) || !cached.tasks) {
    status.textContent = 'Nothing cached to save yet; the page caches its copy on every poll.';
    button.dataset.state = 'bad';
    setTimeout(() => delete button.dataset.state, 1500);
    return;
  }
  button.disabled = true;
  status.textContent = 'Saving the log and the tasks…';
  try {
    const result = await (await request('/api/save-state', {
      method: 'POST',
      headers: writeHeaders('application/json'),
      body: JSON.stringify(cached)
    })).json();
    status.textContent =
      `Saved ${result.notes} messages, ${result.answers} report answers and ` +
      `${result.tasks} tasks to ${result.path}.`;
    button.dataset.state = 'good';
  } catch (error) {
    status.textContent = `Not saved: ${error.message}. The cache is kept; press the button again.`;
    button.dataset.state = 'bad';
  } finally {
    button.disabled = false;
    setTimeout(() => delete button.dataset.state, 1500);
  }
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
function showReceipt(at) {
  const receipt = $('#report-receipt');
  receipt.textContent = `✓ Sent ${time(at)} · your answers stay filled in; change them and send again.`;
  receipt.hidden = false;
}
async function loadReport() {
  const id = $('#report-select').value;
  const sequence = ++reportRequest;
  // The reports panel is the element that scrolls, and replacing the report collapses its content, so
  // the browser clamps the panel to the top before the new HTML arrives. An update to the report being
  // read keeps the owner's place; a report the owner switched to starts at its own top. Owner's bug
  // report, the same class as the seen stamp.
  const panel = $('#reports-panel');
  const place = panel.scrollTop;
  const updating = $('#report').dataset.reportId === id;
  $('#report').replaceChildren();
  $('#report-submit').hidden = true;
  $('#report-receipt').hidden = true;
  if (!id) { $('#report-status').textContent = 'No report has been published yet.'; return; }
  save('report', id);
  $('#report-status').textContent = 'Loading report…';
  try {
    const result = await (await request(`/api/reports/${encodeURIComponent(id)}/html`)).json();
    if (sequence !== reportRequest) return;
    $('#report').innerHTML = result.html;
    $('#report').dataset.reportId = id;
    panel.scrollTop = updating ? place : 0;
    $('#report-submit').hidden = !result.fields;
    const saved = result.fields ? savedAnswers(id) : null;
    if (saved && saved.answers) {
      applyAnswers($('#report'), saved.answers);
      showReceipt(saved.at);
    }
    $('#report-status').textContent = saved && saved.answers
      ? `Answers sent ${saved.at ? time(saved.at) : 'earlier'} · ${result.fields} field${result.fields === 1 ? '' : 's'} stay filled in; change them and send again to replace them.`
      : result.fields
        ? `Report loaded with ${result.fields} field${result.fields === 1 ? '' : 's'}. Fill them in, then send; answers reach the agent inbox as one note.`
        : 'Report loaded. Updates appear automatically.';
    checkReportRead();
  } catch (error) {
    if (sequence === reportRequest) $('#report-status').textContent = `Report unavailable: ${error.message}`;
  }
}
$('#report-form').addEventListener('submit', async event => {
  event.preventDefault();
  const id = $('#report-select').value;
  if (!id) return;
  const button = $('#report-submit');
  const answers = collect($('#report'));
  button.disabled = true;
  $('#report-status').textContent = 'Sending…';
  try {
    const result = await (await request(`/api/reports/${encodeURIComponent(id)}/submit`, {
      method: 'POST',
      headers: writeHeaders('application/json'),
      body: JSON.stringify({ id: newId(), answers })
    })).json();
    if (save(`answers:${id}`, JSON.stringify({ answers, at: result.at }))) showReceipt(result.at);
    $('#report-status').textContent = `Answers sent ${time(result.at)} · the agent reads the inbox; awaiting acknowledgement. Your entries stay on screen.`;
  } catch (error) {
    $('#report-status').textContent = `Submission not confirmed: ${error.message}. Entries are kept; resending creates a new answer.`;
  } finally { button.disabled = false; }
});
// The Tasks tab is the agent's own status: two divs, written by the CLI, read on the same poll.
// A row is built from the record with textContent, so a hostile title stays text.
function taskRow(task) {
  const item = document.createElement('li');
  item.className = 'task';
  item.title = task.details.join('\n');
  const title = document.createElement('span');
  title.className = 'task-title';
  title.textContent = task.title;
  const rows = [title];
  if (task.details.length) {
    // A <details> rather than a span, so a task carrying ten long lines costs one collapsed row
    // and the whole list stays scannable. Native element: no script, and keyboard reachable.
    // The details inside it are a real <ul>, so each carries its own
    // marker and reads as a list of separate statements rather than lines inside one block.
    const details = document.createElement('details');
    details.className = 'task-details';
    const summary = document.createElement('summary');
    summary.textContent = `${task.details.length} detail${task.details.length === 1 ? '' : 's'}`;
    const list = document.createElement('ul');
    list.className = 'task-detail-list';
    list.replaceChildren(...task.details.map(line => {
      const detail = document.createElement('li');
      detail.className = 'task-detail';
      detail.textContent = line;
      return detail;
    }));
    details.replaceChildren(summary, list);
    rows.push(details);
  }
  item.replaceChildren(...rows);
  return item;
}

// Tasks re-render only when the payload changed, the way the report list already guards on its own
// signature. Without this every poll rebuilds the rows and snaps an opened <details> shut, which
// would make the collapse below useless three seconds after the owner clicked it.
// A symbol rather than null: JSON.stringify of a missing task list is undefined, and undefined
// normalised to null would equal a null sentinel and skip the first render entirely.
let taskSignature = Symbol('tasks not yet rendered');

// An upload keeps its bytes beside the preview database and its record inside it, on the owner's
// answers: any bytes, a 1,000,000-byte ceiling, and a record that
// outlives them. The row says which of the two is gone, because a restore removes the bytes and
// leaves the record, and a download link on a file that is not there would open nothing.
function uploadRow(item) {
  const row = document.createElement('li');
  row.className = 'upload-row';
  const name = document.createElement('span');
  name.className = 'upload-name';
  name.textContent = item.name;
  const meta = document.createElement('span');
  meta.className = 'upload-meta';
  meta.textContent = `${bytes(item.size)} · ${item.type} · ${time(item.at)} · ${item.sha256.slice(0, 12)}`;
  row.append(name, meta);
  const where = document.createElement('span');
  where.className = 'upload-where';
  // The path rather than a download link: the preview offers no download controls, on the standing
  // owner choice, so the row says which file on disk the bytes are in for a terminal to read.
  where.textContent = item.present ? `uploads/${item.file}` : 'the bytes are gone; the record survived a restore';
  if (!item.present) where.className = 'upload-gone';
  row.append(where);
  return row;
}
function renderUploadsIfChanged(uploads) {
  const signature = JSON.stringify(uploads || []);
  if (signature === uploadSignature) return;
  uploadSignature = signature;
  const rows = uploads || [];
  $('#uploads-list').replaceChildren(...rows.map(item => uploadRow(item)));
  $('#uploads-count').textContent = rows.length
    ? `${rows.length} file${rows.length === 1 ? '' : 's'} saved.`
    : 'No files uploaded yet.';
}
function renderTasksIfChanged(tasks) {
  const signature = JSON.stringify(tasks);
  if (signature === taskSignature) return;
  taskSignature = signature;
  renderTasks(tasks);
}

function renderTasks(tasks) {
  const status = $('#tasks-status');
  const current = $('#tasks-current');
  const finished = $('#tasks-finished');
  const upcoming = $('#tasks-upcoming');
  if (!tasks) {
    status.textContent = 'The agent has not written a task list yet.';
    current.hidden = true;
    finished.hidden = true;
    upcoming.hidden = true;
    return;
  }
  status.textContent = `Updated ${time(tasks.updated_at)}`;
  // The head of the queue gets a div of its own so what the agent is on next is visible without
  // reading down a list. It stays in Upcoming as well: removing it would leave a hole in the
  // authoritative order, and the copy button hands both stored sections over as they are.
  const head = tasks.upcoming[0];
  $('#tasks-current-body').replaceChildren(...(head ? [taskRow(head)] : []));
  current.hidden = !head;
  $('#tasks-finished-body').replaceChildren(...tasks.finished.map(task => taskRow(task)));
  // The head already renders in its own div above; re-listing it in Upcoming duplicates it.
  $('#tasks-upcoming-body').replaceChildren(...tasks.upcoming.slice(1).map(task => taskRow(task)));
  finished.hidden = false;
  upcoming.hidden = false;
}
const tabs = [$('#notes-tab'), $('#reports-tab'), $('#tasks-tab'), $('#uploads-tab')];
// The Reports tab carries a pip rather than a count: what the owner needs from a tab is whether
// something there is unread, not how many reports exist. A report is unread until the owner has
// been shown it, and that reading is stamped on the report itself rather than kept in browser
// storage, so it survives a cleared browser, holds across browsers, and tells the agent the
// report was read instead of leaving it to infer one.
function reportLabel(report, position) {
  return `${position + 1}.${report.seen_at ? '' : ' *'} ${report.title}`;
}
function updateReportPip(reports) {
  const pip = $('#report-pip');
  const unseen = reports.filter(report => !report.seen_at);
  pip.hidden = unseen.length === 0;
  pip.title = unseen.length ? 'A report has not been read' : 'No unread report';
  pip.setAttribute('aria-label', unseen.length ? 'Unread report' : 'No unread report');
}
// A report counts as read when the browser has shown it: scrolled to its end, or, for a report
// that fits the panel with nothing to scroll, held in view for five seconds on owner direction,
// so a flick past it stamps nothing. Republishing clears the stamp, so changed text is unread.
const REPORT_READ_DWELL = 1000;
let readPending = null;
function clearReadTimer() {
  if (readPending) { clearTimeout(readPending.timer); readPending = null; }
}
function unseenReportId() {
  const reports = (lastState && lastState.reports) || [];
  const report = reports.find(item => item.id === $('#report-select').value);
  return report && !report.seen_at ? report.id : null;
}
async function markReportRead(id) {
  clearReadTimer();
  let stamped;
  try {
    stamped = await (await request(`/api/reports/${encodeURIComponent(id)}/seen`, {
      method: 'POST',
      headers: writeHeaders('application/json'),
      body: '{}'
    })).json();
  } catch (error) {
    // A stamp that fails costs the owner nothing they have to act on, and the next look retries.
    return;
  }
  // The stamp is folded into the state rather than fetched again. A poll after it would see a
  // changed reports signature, rebuild the select and re-fetch the report, which loses the
  // owner's place in a long report. The server's own stamp is stored and the signature is moved
  // with it, so the next poll matches this state and renders nothing.
  const reports = (lastState && lastState.reports) || [];
  const report = reports.find(item => item.id === id);
  if (!report) return;
  report.seen_at = stamped.seen_at || new Date().toISOString();
  listSignature = JSON.stringify(reports);
  updateReportPip(reports);
  const option = [...$('#report-select').children].find(item => item.value === id);
  if (option) option.textContent = reportLabel(report, reports.indexOf(report));
}
function checkReportRead() {
  const panel = $('#reports-panel');
  const id = panel.hidden ? null : unseenReportId();
  const viewport = panel.clientHeight;
  // A panel with no height yet has no report in it to read, and a report still being fetched is
  // not one either: reading is what this stamps, so it waits until there is something to look at.
  if (!id || !viewport || !panel.scrollHeight) { clearReadTimer(); return; }
  if (panel.scrollHeight > viewport + 1) {
    // There is more report than panel, so reaching the end is the gesture that reads it.
    if (panel.scrollTop + viewport >= panel.scrollHeight - 2) markReportRead(id);
    else clearReadTimer();
    return;
  }
  if (readPending && readPending.id === id) return;
  clearReadTimer();
  readPending = { id, timer: setTimeout(() => markReportRead(id), REPORT_READ_DWELL) };
}
$('#reports-panel').addEventListener('scroll', checkReportRead);
function showTab(tab) {
  for (const item of tabs) {
    const selected = tab === item;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
    $('#' + item.getAttribute('aria-controls')).hidden = !selected;
  }
  if (tab === tabs[1]) {
    // Opening the tab is reading it, so the marker is written before the poll that recomputes the
    // pip: it goes out on this visit rather than surviving until the next one.
    refreshState();
    loadReport();
  } else clearReadTimer();
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
// An upload sends the file itself rather than a JSON envelope, so the body is the bytes and the name
// rides the query string; the content type is the browser's, since the server stores any bytes as they
// arrived and records what they were.
$('#upload-send').addEventListener('click', async () => {
  const button = $('#upload-send');
  if (button.disabled) return;
  const input = $('#upload-file');
  const line = $('#upload-status');
  const files = Array.from(input.files || []);
  if (!files.length) { line.textContent = 'Choose a file first.'; return; }
  for (const file of files) {
    const name = files.length === 1 ? 'That file' : file.name;
    if (!file.size) { line.textContent = `${name} is empty.`; return; }
    if (file.size > MAX_UPLOAD) {
      line.textContent = `${name} is ${file.size.toLocaleString()} bytes; the ceiling is ${MAX_UPLOAD.toLocaleString()}.`;
      return;
    }
  }
  const saved = [];
  let current;
  button.disabled = input.disabled = true;
  try {
    for (const file of files) {
      current = file;
      line.textContent = `Uploading ${file.name}…`;
      const response = await request(`/api/uploads?name=${encodeURIComponent(file.name)}`, {
        method: 'POST',
        headers: writeHeaders(file.type || 'application/octet-stream'),
        body: file
      });
      saved.push(await response.json());
    }
    const record = saved[0];
    line.textContent = files.length === 1
      ? `Saved ${record.name} · ${bytes(record.size)} · ${record.sha256.slice(0, 12)}`
      : `Saved ${saved.length} files: ${saved.map(record => record.name).join(', ')}`;
    input.value = '';
  } catch (error) {
    line.textContent = `Upload failed: ${error.message}` + (files.length === 1 ? ''
      : ` (${current.name}). Saved ${saved.length} of ${files.length}: ${saved.map(record => record.name).join(', ') || 'none'}. Select remaining files before retrying.`);
  } finally {
    button.disabled = input.disabled = false;
    if (saved.length) await refreshState();
  }
});
$('#report-select').addEventListener('change', loadReport);
$('#refresh-report').addEventListener('click', () => { refreshState(); loadReport(); });
$('#refresh-notes').addEventListener('click', refreshState);
refreshState();
setInterval(refreshState, 3000);
