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
  if (open) scrollHistory(true);
});
note.value = stored('draft') || '';
try { pending = JSON.parse(stored('pending') || 'null'); }
catch { status.textContent = 'Stored retry data is invalid. Draft retained; check the log before resending.'; }
note.addEventListener('input', () => {
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
  if (notes.length) note.placeholder = notes[notes.length - 1].text;
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
    const receipt = node.children[1];
    receipt.className = 'receipt';
    receipt.textContent = `${item.acknowledged_at
      ? `ACK-ed ${time(item.acknowledged_at)} · Saved ${time(item.at)}`
      : `Saved ${time(item.at)} · Awaiting ACK`} · id ${item.id.slice(0, 7)}`;
    const answer = node.children[2];
    if (item.ack_text && item.ack_kind === 'reply') {
      answer.className = 'answer reply report';
      answer.hidden = false;
      if (item.ack_html === undefined) answer.textContent = item.ack_text;
      else answer.innerHTML = item.ack_html;
    } else if (item.ack_text) {
      answer.className = 'answer note';
      answer.hidden = false;
      answer.textContent = item.ack_text;
    } else {
      answer.className = 'answer';
      answer.hidden = true;
      answer.textContent = '';
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
    setConnection('ok', state.notes.length ? `${state.notes.length} messages saved` : 'No messages yet');
    if (state.rendering_error) $('#connection-text').textContent += ` · Markdown log unavailable; raw text shown: ${state.rendering_error}`;
    $('#last-check').textContent = state.last_check ? `Agent last checked ${time(state.last_check)}` : 'Agent has not checked this inbox yet.';
    showHistory(state.notes);
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
      $('#report-count').textContent = state.reports.length;
      if (!$('#reports-panel').hidden) loadReport();
    }
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
    note.placeholder = result.text;
    status.textContent = result.acknowledged_at ? 'Saved · already acknowledged.' : `Saved ${new Date(result.at).toLocaleTimeString()} · awaiting acknowledgement.`;
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
      const checked = [...field.querySelectorAll('input:checked')].map(control => control.value);
      if (checked.length) answers[id] = field.dataset.type === 'choice' ? checked[0] : checked;
    }
  }
  return answers;
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
    for (const control of field.querySelectorAll('input')) control.checked = values.includes(control.value);
  }
}
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
    $('#report-status').textContent = result.fields
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
    $('#report-status').textContent = `Saved ${new Date(result.at).toLocaleTimeString()} · the agent reads the inbox; awaiting acknowledgement. Your entries stay on screen.`;
  } catch (error) {
    $('#report-status').textContent = `Submission not confirmed: ${error.message}. Entries are kept; resending creates a new answer.`;
  } finally { button.disabled = false; }
});
const tabs = [$('#notes-tab'), $('#reports-tab')];
function showTab(tab) {
  for (const item of tabs) {
    const selected = tab === item;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
    $('#' + item.getAttribute('aria-controls')).hidden = !selected;
  }
  if (tab === tabs[1]) { refreshState(); loadReport(); }
}
for (const tab of tabs) {
  tab.addEventListener('click', () => showTab(tab));
  tab.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[1] : tabs[1 - tabs.indexOf(tab)];
    showTab(next);
    next.focus();
  });
}
$('#report-select').addEventListener('change', loadReport);
$('#refresh-report').addEventListener('click', () => { refreshState(); loadReport(); });
$('#refresh-notes').addEventListener('click', refreshState);
refreshState();
setInterval(refreshState, 3000);
