'use strict';
const $ = selector => document.querySelector(selector);
const note = $('#note');
const send = $('#send');
const status = $('#send-status');
const key = 'arena-preview-v1';
let pending = null;
let stateBusy = false;
let reportRequest = 0;
let reportSignature = '';
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
  document.documentElement.dataset.theme = theme === 'light' ? 'light' : 'dark';
  const action = theme === 'light' ? 'Dark mode' : 'Light mode';
  $('#theme').textContent = action;
  $('#theme').setAttribute('aria-label', `Switch to ${action.toLowerCase()}`);
}
setTheme(stored('theme'));
$('#theme').addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  setTheme(theme);
  save('theme', theme);
});
note.value = stored('draft') || '';
try { pending = JSON.parse(stored('pending') || 'null'); }
catch { status.textContent = 'Stored retry data is invalid. Draft retained; check the log before resending.'; }
note.addEventListener('input', () => {
  $('#draft').textContent = save('draft', note.value)
    ? 'Draft saved in this browser.' : 'Browser storage unavailable. Keep this page open.';
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
  return new Date(value).toLocaleString();
}
function showHistory(notes) {
  const signature = JSON.stringify(notes);
  if (signature === historySignature) return;
  historySignature = signature;
  if (notes.length) note.placeholder = `Last sent: ${notes[notes.length - 1].text}`;
  const history = $('#history');
  for (const item of [...notes].reverse()) {
    let node = messageNodes.get(item.id);
    if (!node) {
      node = document.createElement('li');
      node.className = 'message';
      const text = document.createElement('div');
      node.append(text, document.createElement('div'));
      messageNodes.set(item.id, node);
    }
    const text = node.children[0];
    text.className = item.html === undefined ? 'raw-message' : 'report';
    if (item.html === undefined) text.textContent = item.text;
    else text.innerHTML = item.html;
    const receipt = node.lastElementChild;
    receipt.className = 'receipt';
    receipt.textContent = item.acknowledged_at
      ? `Acknowledged ${time(item.acknowledged_at)} · Saved ${time(item.at)}`
      : `Saved ${time(item.at)} · Awaiting acknowledgement`;
    history.append(node);
  }
}
async function refreshState() {
  if (stateBusy) return;
  stateBusy = true;
  try {
    const state = await (await request('/api/state')).json();
    $('#connection').textContent = state.notes.length ? `${state.notes.length} messages saved · Connected` : 'Connected · No messages yet';
    if (state.rendering_error) $('#connection').textContent += ` · Markdown log unavailable; raw text shown: ${state.rendering_error}`;
    $('#last-check').textContent = state.last_check ? `Agent last checked ${time(state.last_check)}` : 'Agent has not checked this inbox yet.';
    showHistory(state.notes);
    const signature = JSON.stringify(state.reports);
    if (signature !== reportSignature) {
      reportSignature = signature;
      const select = $('#report-select');
      const selected = select.value || stored('report');
      select.replaceChildren();
      for (const report of state.reports) {
        const option = document.createElement('option');
        option.value = report.id;
        option.textContent = report.title;
        select.append(option);
      }
      if (!state.reports.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No reports published yet';
        select.append(option);
      } else if (state.reports.some(report => report.id === selected)) select.value = selected;
      $('#report-count').textContent = state.reports.length;
      if (!$('#reports-panel').hidden) loadReport();
    }
  } catch (error) { $('#connection').textContent = `Connection failed: ${error.message}. Draft kept; history may be stale.`; }
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
    note.placeholder = `Last sent: ${result.text}`;
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
  $('#preview-note').textContent = 'Preview';
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
  $('#preview-note').textContent = 'Write';
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
async function loadReport() {
  const id = $('#report-select').value;
  const sequence = ++reportRequest;
  $('#report').replaceChildren();
  if (!id) { $('#report-status').textContent = 'No report has been published yet.'; return; }
  save('report', id);
  $('#report-status').textContent = 'Loading report…';
  try {
    const rendered = await (await request(`/api/reports/${encodeURIComponent(id)}/html`)).text();
    if (sequence !== reportRequest) return;
    $('#report').innerHTML = rendered;
    $('#report-status').textContent = 'Report loaded. Updates appear automatically; the agent can export a standalone HTML file on request.';
  } catch (error) {
    if (sequence === reportRequest) $('#report-status').textContent = `Report unavailable: ${error.message}`;
  }
}
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
