'use strict';
const $ = selector => document.querySelector(selector);
const note = $('#note');
const send = $('#send');
const status = $('#send-status');
const key = 'arena-preview-v1';
let pending = null;
let stateBusy = false;
let reportRequest = 0;
let listSignature = '';
let lastState = null;
let historySignature = '';
let draftPreviewSequence = 0;
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
  button.setAttribute('aria-label', `Switch to ${light ? 'dark' : 'light'} mode`);
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
  if (labels.name) button.setAttribute('aria-label', open ? labels.name[0] : labels.name[1]);
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

async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(path, { ...options, cache: 'no-store', signal: controller.signal });
    if (!response.ok) {
      const message = await response.text();
      let error;
      try { error = JSON.parse(message).error; } catch { error = message; }
      throw new Error(error || `HTTP ${response.status}`);
    }
    return response;
  } finally { clearTimeout(timer); }
}
function time(value) {
  const date = new Date(value);
  const parts = Object.fromEntries(new Intl.DateTimeFormat(undefined, {
    month: 'short', day: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
  }).formatToParts(date).map(part => [part.type, part.value]));
  const year = date.getFullYear() === new Date().getFullYear() ? '' : ` ${parts.year}`;
  return `${parts.month} ${parts.day}${year}, ${parts.hour}:${parts.minute}`;
}
function showHistory(notes) {
  const signature = JSON.stringify(notes);
  if (signature === historySignature) return;
  historySignature = signature;
  if (notes.length) note.placeholder = clipPlaceholder(notes[notes.length - 1].text);
  const history = $('#history');
  const pinned = !messageNodes.size
    || history.scrollHeight - history.scrollTop - history.clientHeight < 80;
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
    text.className = item.html === undefined ? 'raw-message' : 'report';
    if (item.html === undefined) text.textContent = item.text;
    else text.innerHTML = item.html;
    const receipt = node.children[2];
    receipt.className = 'receipt';
    const receiptId = document.createElement('code');
    receiptId.className = 'note-id';
    receiptId.textContent = item.id.slice(0, 7);
    receiptId.title = item.id;
    receiptId.dataset.full = item.id;
    // Sent until the agent reads it, Seen once a CLI read has stamped seen_at, Said once answered.
    // The state is a coloured dot; the word lives in its title and aria-label instead of the line.
    const state = item.acknowledged_at ? 'said' : item.seen_at ? 'seen' : 'sent';
    const receiptDot = document.createElement('span');
    receiptDot.className = 'state-dot';
    receiptDot.dataset.state = state;
    receiptDot.setAttribute('role', 'img');
    receiptDot.setAttribute('aria-label', STATE_WORDS[state]);
    receiptDot.title = STATE_WORDS[state];
    const receiptState = document.createElement('span');
    receiptState.textContent = ` · ${time(item.at)}`;
    receipt.replaceChildren(receiptId, receiptDot, receiptState);
    // One answer style for both acknowledgement kinds: rendered HTML when the server sent it, and
    // otherwise the text in a paragraph, which inherits pre-wrap from .message p.
    const answer = node.children[1];
    if (item.ack_text) {
      answer.className = item.ack_kind === 'reply' ? 'answer reply report' : 'answer reply';
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
    history.append(node);
  }
  if (pinned) history.scrollTop = history.scrollHeight;
}
async function refreshState() {
  if (stateBusy) return;
  stateBusy = true;
  try {
    const state = await (await request('/api/state')).json();
    lastState = state;
    setConnection('ok', state.notes.length ? `${state.notes.length} messages saved` : 'No messages yet');
    if (state.rendering_error) $('#connection-text').textContent += ` · Markdown log unavailable; raw text shown: ${state.rendering_error}`;
    $('#last-check').textContent = state.last_check ? `Last checked ${time(state.last_check)}` : 'Not checked yet.';
    showHistory(state.notes);
    renderTasksIfChanged(state.tasks);
    const signature = JSON.stringify(state.reports);
    if (signature !== listSignature) {
      listSignature = signature;
      const select = $('#report-select');
      const selected = select.value || stored('report');
      select.replaceChildren();
      state.reports.forEach((report, position) => {
        const option = document.createElement('option');
        option.value = report.id;
        option.textContent = `${position + 1}. ${report.title}`;
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
  if (!pending || pending.text !== text) pending = { id: crypto.randomUUID(), text };
  save('pending', JSON.stringify(pending));
  send.disabled = true;
  status.textContent = 'Sending…';
  try {
    const result = await (await request('/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Preview-Token': '__TOKEN__' },
      body: JSON.stringify(pending)
    })).json();
    note.placeholder = clipPlaceholder(result.text);
    status.textContent = result.acknowledged_at ? 'Saved · already acknowledged.' : `Saved ${new Date(result.at).toLocaleTimeString()} · Message sent.`;
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
      headers: { 'Content-Type': 'application/json', 'X-Preview-Token': '__TOKEN__' },
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
  button.setAttribute('aria-label', 'Copy code');
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
  button.setAttribute('aria-label', words || blocked);
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
async function copyFrom(button, text, what) {
  const words = text === null ? null : await copyText(text);
  const message = words || (text === null ? `There is no ${what} to copy`
    : `Clipboard blocked; select the ${what} and copy it`);
  button.textContent = words ? '✓' : '✗';
  button.setAttribute('aria-label', message);
  button.title = message;
  button.dataset.state = words ? 'good' : 'bad';
  setTimeout(() => {
    button.textContent = '⧉';
    button.setAttribute('aria-label', `Copy the ${what}`);
    button.title = `Copy the ${what}`;
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
$('#copy-log').addEventListener('click', () => {
  const notes = lastState ? lastState.notes : [];
  copyFrom($('#copy-log'), notes.length ? `${notes.map(
    note => JSON.stringify({ id: note.id, text: note.text, at: stamp(note.at) })
  ).join('\n')}\n` : null, 'message log');
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
$('#copy-tasks').addEventListener('click', () => {
  const tasks = lastState && lastState.tasks;
  const records = tasks ? [...tasks.finished, ...tasks.upcoming] : [];
  copyFrom($('#copy-tasks'), records.length ? `${JSON.stringify(records)}\n` : null,
    'task list');
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
      headers: { 'Content-Type': 'application/json', 'X-Preview-Token': '__TOKEN__' },
      body: JSON.stringify({ id: crypto.randomUUID(), answers })
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
    // The details inside it are a real <ul>, on the owner's note 11a35a0f, so each carries its own
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
  status.textContent = `Updated ${time(tasks.updated_at)} · written by the agent; it takes no answers.`;
  // The head of the queue gets a div of its own so what the agent is on next is visible without
  // reading down a list. It stays in Upcoming as well: removing it would leave a hole in the
  // authoritative order, and the copy button hands both stored sections over as they are.
  const head = tasks.upcoming[0];
  $('#tasks-current-body').replaceChildren(...(head ? [taskRow(head)] : []));
  current.hidden = !head;
  $('#tasks-finished-body').replaceChildren(...tasks.finished.map(task => taskRow(task)));
  $('#tasks-upcoming-body').replaceChildren(...tasks.upcoming.map(task => taskRow(task)));
  finished.hidden = false;
  upcoming.hidden = false;
}
const tabs = [$('#notes-tab'), $('#reports-tab'), $('#tasks-tab')];
// The Reports tab carries a pip rather than a count: what the owner needs from a tab is whether
// something there is unread, not how many reports exist. A report is unread while its update time
// is newer than the last time the tab was opened, and that marker lives in browser storage rather
// than in a column, because reports carry no seen_at and adding one is a separate task.
function updateReportPip(reports) {
  const pip = $('#report-pip');
  const readAt = stored('reports-read-at');
  const unread = reports.some(report => !readAt || (report.updated_at || '') > readAt);
  pip.hidden = !unread;
  pip.title = unread ? 'A report has not been read' : 'No unread report';
  pip.setAttribute('aria-label', unread ? 'Unread report' : 'No unread report');
}
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
    save('reports-read-at', new Date().toISOString());
    refreshState();
    loadReport();
  }
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
$('#report-select').addEventListener('change', loadReport);
$('#refresh-report').addEventListener('click', () => { refreshState(); loadReport(); });
$('#refresh-notes').addEventListener('click', refreshState);
refreshState();
setInterval(refreshState, 3000);
