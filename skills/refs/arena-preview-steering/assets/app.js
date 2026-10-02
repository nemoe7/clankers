'use strict';
const $ = selector => document.querySelector(selector);
const note = $('#note');
const send = $('#send');
const status = $('#send-status');
const key = 'arena-preview-v1';
// Browser and server both enforce the decimal 50 MB per-file ceiling.
const MAX_UPLOAD = 50_000_000;
// A text paste over this length becomes one attachment instead of filling the composer.
const PASTE_TEXT_LIMIT = 2000;
const MAX_FETCH = 102_400_000;
const BINARY_TIMEOUT = 600_000;
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
let fetchSignature = '';
let fetchBusy = false;
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

function connectionLabel(state) {
  // A poll shows as the blue dot alone, so its text keeps the normal reading.
  return state === 'down' ? 'Disconnected' : 'Connected';
}
function setConnection(state, text) {
  const dot = $('#connection-dot');
  dot.dataset.state = state;
  dot.setAttribute('aria-label', connectionLabel(state));
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

// File bytes stay in this browser tab, not in localStorage. Every staged file has its own removal
// control beside "Your message"; picker, drop and paste stage files before one atomic send.
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
    name.textContent = file.name;
    name.title = file.name;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = '×';
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
    if (file.size > MAX_UPLOAD) {
      status.textContent = `${file.name} is ${file.size.toLocaleString()} bytes; the ceiling is ${MAX_UPLOAD.toLocaleString()}.`;
      return;
    }
  }
  stagedFiles.push(...files);
  picker.value = '';
  renderStagedFiles();
  status.textContent = `Staged ${stagedFiles.length} file${stagedFiles.length === 1 ? '' : 's'}. Send note to save them together.`;
}
$('#attach-file').addEventListener('click', () => picker.click());
picker.addEventListener('change', () => stageFiles(Array.from(picker.files || [])));
compose.addEventListener('paste', event => {
  if (send.disabled) return;
  const clip = event.clipboardData;
  const images = Array.from(clip?.files || []).filter(file => file.type.startsWith('image/'));
  const text = clip?.getData('text/plain') || '';
  if (!images.length) {
    // A long paste becomes one attachment, so a pasted log never fills the composer.
    if (text.length <= PASTE_TEXT_LIMIT) return;
    event.preventDefault();
    const stamp = Date.now();
    const base = `${text.split('\n').length}-pasted-lines-${stamp}`;
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

// Short requests keep their ten-second timer. Binary transfers have a longer deadline and no
// automatic retry after a lost response: the server may have saved the bytes already.
async function attempt(path, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(path, { ...options, cache: 'no-store', signal: controller.signal });
  } finally { clearTimeout(timer); }
}
// A page outlives the server it came from. A sandbox reset changes the write token, so a refused
// write takes the new token from the page. Small writes retry once after a network failure.
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
  if (response.status === 401 || response.status === 403) {
    const page = await (await fetch('/', { cache: 'no-store' })).text();
    const token = (page.match(/data-token="([^"]+)"/) || [])[1];
    if (token) {
      writeToken = token;
      const headers = { ...(init.headers || {}), 'X-Preview-Token': token };
      response = await attempt(path, { ...init, headers }, timeoutMs);
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
let unreadEdits = [];
// SQLite stores the number of reply blocks the page marked as viewed. Counts distinguish two
// replies with the same second-level timestamp, and survive a page reload.
function updateEdits(notes) {
  unreadEdits = notes.filter(item =>
    item.ack_edited_at && Number(item.ack_edited_seen_count || 0) < (item.replies || []).length
  );
  $('#notes-pip').hidden = $('#log-edited').hidden = !unreadEdits.length;
  $('#log-edited').textContent = unreadEdits.length > 1 ? `New replies (${unreadEdits.length})` : 'New reply';
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
$('#log-edited').addEventListener('click', async () => {
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
  try {
    const replyCount = (item.replies || []).length;
    const response = await request(`/api/messages/${encodeURIComponent(item.id)}/replies/seen`, {
      method: 'POST',
      headers: writeHeaders('application/json'),
      body: JSON.stringify({count: replyCount})
    });
    const receipt = await response.json();
    if (receipt.id !== item.id || !Number.isInteger(receipt.ack_edited_seen_count)) {
      throw new Error('The viewed-reply receipt was invalid');
    }
    item.ack_edited_seen_count = receipt.ack_edited_seen_count;
    updateEdits(lastState.notes);
  } catch (error) {
    status.textContent = `Could not save reply status: ${error.message}`;
  }
});
function showHistory(notes) {
  const signature = JSON.stringify(notes);
  if (signature === historySignature) return;
  historySignature = signature;
  const references = referenceTypes(lastState || {notes});
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
    if (item.html === undefined) text.textContent = item.text.replace(/\\n/g, '\n');
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
      (item.ack_edited_at ? ` · Replied again ${time(item.ack_edited_at)}` : '');
    // The line reads as parts separated by the same ASCII dot: ID · state · time · filename · task.
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
    // One answer style for both acknowledgement kinds: rendered HTML when the server sent it, and
    // otherwise the text in a paragraph, which inherits pre-wrap from .message p.
    // A second ack appends a block under the first answer instead of replacing it (the owner's
    // order on the re-ack of 52d7cce); each block keeps its own kind and carries its stamp in
    // its title.
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
  let queueReady = false;
  try {
    const state = await (await request('/api/state')).json();
    lastState = state;
    if (state.token) writeToken = state.token;
    // The page keeps its own copy of what the poll delivered, so the save button still has something
    // to write after a wipe has emptied the server. Notes and tasks only: reports are re-published
    // from their sources, and the copy exports notes, tasks and report answers for the unified importer.
    save('state-cache', JSON.stringify({ notes: state.notes, tasks: state.tasks }));
    const saved = state.notes.length ? `${state.notes.length} messages saved` : 'No messages yet';
    setConnection(state.polling ? 'polling' : 'ok', saved);
    if (state.rendering_error) $('#connection-text').textContent += ` · Markdown log unavailable; raw text shown: ${state.rendering_error}`;
    $('#last-check').textContent = state.last_check ? `Last checked ${time(state.last_check)}` : 'Not checked yet.';
    showHistory(state.notes);
    renderTasksIfChanged(state.tasks);
    renderFetchIfChanged(state.fetch_jobs || []);
    showWorkspace(state.workspace);
    queueReady = true;
    const signature = reportsSignature(state.reports);
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
      const selectedReport = state.reports.find(report => report.id === select.value);
      if (!$('#reports-panel').hidden &&
          ($('#report').dataset.reportId !== select.value ||
           $('#report').dataset.updatedAt !== (selectedReport?.updated_at || ''))) loadReport();
    }
    // The pip tracks reports never opened; an edited report keeps its star alone; the separate
    // receipt tracks the selected report's latest answer.
    updateReportPip(state.reports);
    renderReportAcknowledgement();
  } catch (error) { setConnection('down', `Connection failed: ${error.message}. Draft kept; history may be stale.`); }
  finally {
    stateBusy = false;
    if (queueReady && (lastState.fetch_jobs || []).some(item => item.approval === 'approved'
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
  const names = stagedFiles.map(file => file.name);
  const text = draft.trim() ? draft : names.length === 1 ? `File: ${names[0]}` : `Files: ${names.join(', ')}`;
  const attachments = stagedFiles.map(attachmentInfo);
  const former = pendingFiles();
  if (pending && pending.text === text && former.length &&
      JSON.stringify(former) !== JSON.stringify(attachments)) {
    status.textContent = `Reselect the ${former.length} original files in order to retry this note ID, or edit the draft to start a new note.`;
    return;
  }
  if (!pending || pending.text !== text || JSON.stringify(former) !== JSON.stringify(attachments)) {
    pending = { id: newId(), text, ...(attachments.length ? { attachments } : {}) };
  }
  save('pending', JSON.stringify(pending));
  send.disabled = picker.disabled = $('#attach-file').disabled = true;
  status.textContent = attachments.length ? `Sending ${attachments.length} file${attachments.length === 1 ? '' : 's'} with note…` : 'Sending…';
  try {
    let response;
    if (stagedFiles.length) {
      const body = new FormData();
      body.append('id', pending.id);
      body.append('text', text);
      for (const file of stagedFiles) body.append('file', file, file.name);
      response = await request('/api/notes/with-file', {
        method: 'POST', headers: { 'X-Preview-Token': writeToken }, body,
        timeoutMs: BINARY_TIMEOUT, retryOnFailure: false
      });
    } else response = await request('/api/notes', {
      method: 'POST', headers: writeHeaders('application/json'), body: JSON.stringify(pending)
    });
    const result = await response.json();
    note.placeholder = clipPlaceholder(result.text);
    status.textContent = result.acknowledged_at ? 'Saved · already acknowledged.'
      : `Saved ${time(result.at)} · Message sent${attachments.length ? ` with ${attachments.length} file${attachments.length === 1 ? '' : 's'}` : ''}.`;
    pending = null;
    save('pending', 'null');
    clearStagedFiles();
    if (note.value === draft) {
      note.value = '';
      save('draft', '');
      writeMode();
    }
    refreshState();
  } catch (error) { status.textContent = `Save not confirmed: ${error.message}. Draft${stagedFiles.length ? ' and files' : ''} kept; retry unchanged files and text with the same note ID.`; }
  finally { send.disabled = picker.disabled = $('#attach-file').disabled = false; }
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
      const input = field.querySelector('textarea.answer-text');
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
function quoteId(id, control) {
  const rest = note.value.replace(/^RE: \S+\n/, '');
  note.value = `RE: ${id}\n${rest ? `\n${rest}` : ''}`;
  if (note.hidden) writeMode();
  note.focus();
  const caret = id.length + 5;
  note.setSelectionRange(caret, caret);
  save('draft', note.value);
  control.title = `Quoted in the composer: RE: ${id}`;
}
function quoteNoteId(code) {
  quoteId((code.dataset.full || code.textContent).slice(0, 7), code);
}
async function copyTaskId(title) {
  const id = title.dataset.taskId;
  const words = await copyText(id);
  title.dataset.copied = words ? 'good' : 'bad';
  title.title = words ? `${words}: ${id}` : `Clipboard blocked; the ID is ${id}`;
  setTimeout(() => {
    delete title.dataset.copied;
    title.title = id;
  }, 1500);
}
function quoteTaskId(title) {
  showTab(tabs[0]);
  quoteId(title.dataset.taskId, title);
}
// The tab buttons share one confirmation, and null text means there was nothing to copy.
async function copyFrom(button, text, what, glyph = '⧉') {
  // The label a copy came in with is the label it leaves behind, so a restored `Copy the state`
  // never names the wrong job.
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
  const classes = target.className.split(' ');
  if (classes.includes('answer-text')) { growSlot(target); return; }
  if (!classes.includes('custom-text')) return;
  growSlot(target);
  // Typing in a slot is choosing it: the box checks itself, and blanking the text lets go again.
  const label = (target.dataset.custom || '').replace(/"/g, '\\"');
  const slot = target.parentElement && target.parentElement.querySelector(`[data-label="${label}"]`);
  if (slot) slot.checked = Boolean(target.value.trim());
});
document.addEventListener('click', event => {
  const target = event.target;
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
  else if (classes.includes('note-id')) {
    // Three modifiers on one element: plain copies the short ID, shift the whole one, ctrl quotes.
    if (event.ctrlKey || event.metaKey) quoteNoteId(target);
    else copyNoteId(target, event.shiftKey);
  } else if (classes.includes('task-title')) {
    if (event.ctrlKey || event.metaKey) quoteTaskId(target);
    else void copyTaskId(target);
  }
});
document.addEventListener('keydown', event => {
  const target = event.target;
  if (!target || typeof target.className !== 'string' ||
      !target.className.split(' ').includes('task-title')) return;
  if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  if (event.ctrlKey || event.metaKey) quoteTaskId(target);
  else void copyTaskId(target);
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
// Copy state exports notes, tasks and report answers for `import-state`.
// Report source copies remain Markdown for `publish`.
// The JSON copies are minified on purpose: the agent parses them, and the whitespace only costs tokens.
// A copied line carries its receipt too, so a restore keeps the time the acknowledgement was
// actually written instead of the time the restore ran. Every key is present on every line,
// null where absent, because the importer refuses a partial receipt rather than filling it in.
// Copy state builds NDJSON from cached notes and tasks plus available report answers.
// It does not write to disk. Report sources, uploads, downloads and display-only fields
// are not restored by `import-state`; preserve the backup and republish report sources.
const NOTE_LINE_KEYS = ['id', 'text', 'at', 'acknowledged_at', 'ack_kind', 'ack_text', 'ack_edited_at', 'replies', 'ack_edited_seen_count', 'seen_at', 'task_id'];
const TASK_LINE_KEYS = ['id', 'title', 'details', 'status', 'order', 'blocked'];
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
const copyStateButton = $('#copy-state');
function stateLines(state, answers = []) {
  return [...state.notes, ...state.tasks.upcoming, ...state.tasks.finished, ...answers];
}
copyStateButton.addEventListener('click', async () => {
  let cached = null;
  try { cached = JSON.parse(stored('state-cache') || 'null'); } catch { cached = null; }
  const state = cached && Array.isArray(cached.notes) ? restoreCopy(cached) : null;
  if (!state) status.textContent = 'Nothing cached to copy yet; the page caches its copy on every poll.';
  let answers = null;
  if (state) {
    try { answers = await (await request('/api/submissions')).json(); }
    catch { answers = null; }
  }
  const lines = state ? stateLines(state, answers || []) : [];
  // One JSON line per record is the save format accepted by `import-state`.
  // The server supplies answer lines for reports still in the tab.
  const text = state ? `${lines.map(line => JSON.stringify(line)).join('\n')}\n` : null;
  await copyFrom(copyStateButton, text, 'state');
  if (state) {
    const taskCount = lines.length - state.notes.length - (answers?.length || 0);
    status.textContent = answers
      ? `Copied ${state.notes.length} messages, ${answers.length} answers and ${taskCount} tasks as NDJSON.`
      : `Copied ${state.notes.length} messages and ${taskCount} tasks as NDJSON; the answers did not arrive.`;
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
// One grammar for the report lines, matching the log receipts: object, then the state dot, then
// the time, all joined by the dot, no sentences. The receipt prints the latest of the three
// stamps, and the earlier ones wait in the object's title.
function submissionParts(report) {
  if (!report?.latest_answer_at) return '';
  return ` · Submission ${report.latest_answer_id.slice(0, 7)}`;
}
// The read stamp is report-level, so it counts only when it lands after the latest answer.
function submissionSeenAt(report) {
  const seen = report.agent_seen_at;
  return seen && seen > report.latest_answer_at ? seen : '';
}
function submissionState(report) {
  if (report.latest_answer_acknowledged_at) return 'said';
  return submissionSeenAt(report) ? 'seen' : 'sent';
}
function submissionStateWord(report) {
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
  const report = lastState?.reports.find(item => item.id === $('#report-select').value);
  const receipt = $('#report-agent-ack');
  receipt.replaceChildren(...submissionReceipt(report));
  receipt.hidden = !receipt.children.length;
  const footer = $('#report-agent-ack-footer');
  footer.replaceChildren(...submissionReceipt(report));
  footer.hidden = receipt.hidden;
  const history = $('#report-ack-history');
  const references = referenceTypes(lastState || {});
  const blocks = [];
  for (const ack of report?.acknowledgements || []) {
    for (const reply of [{text: ack.ack_text, html: ack.ack_html, at: ack.acknowledged_at}, ...(ack.replies || [])]) {
      const block = document.createElement('div');
      block.className = 'reply-block';
      block.title = `Submission ${ack.id.slice(0, 7)} · ${time(reply.at)}`;
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
let reportDirty = false;
$('#report-form').addEventListener('input', () => { reportDirty = true; });
async function loadReport(force = false) {
  const id = $('#report-select').value;
  const sequence = ++reportRequest;
  // The reports panel is the element that scrolls, and replacing the report collapses its content, so
  // the browser clamps the panel to the top before the new HTML arrives. An update to the report being
  // read keeps the owner's place; a report the owner switched to starts at its own top. Owner's bug
  // report, the same class as the seen stamp.
  const panel = $('#reports-panel');
  const place = panel.scrollTop;
  const updating = $('#report').dataset.reportId === id;
  const keepEntries = () => updating && force !== true && (reportDirty || $('#report-submit').disabled);
  if (keepEntries()) return;
  const revision = lastState?.reports.find(report => report.id === id)?.updated_at || '';
  if (!updating || !id) {
    $('#report').replaceChildren();
    $('#report-submit').hidden = true;
  }
  if (!id) { $('#report-status').textContent = 'No report has been published yet.'; return; }
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
    $('#report-submit').hidden = !result.fields;
    const saved = result.fields ? savedAnswers(id) : null;
    if (saved && saved.answers) {
      applyAnswers($('#report'), saved.answers);
    }
    $('#report-form').dataset.fields = result.fields;
    const report = lastState?.reports.find(item => item.id === id);
    // One date stamp at a time: a republished report shows Edited and drops the Published
    // line, so the owner reads the newest event, not both. Owner's note on the feature.
    const stampSource = result.edited && result.published && result.edited !== result.published
      ? `Edited ${time(result.edited)}`
      : result.published || result.edited ? `Published ${time(result.published || result.edited)}` : '';
    $('#report-status').textContent =
      `Report · ${result.fields} field${result.fields === 1 ? '' : 's'}` +
      (stampSource ? ` · ${stampSource}` : '') + submissionParts(report);
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
  try {
    const result = await (await request(`/api/reports/${encodeURIComponent(id)}/submit`, {
      method: 'POST',
      headers: writeHeaders('application/json'),
      body: JSON.stringify({ id: newId(), answers, revision })
    })).json();
    save(`answers:${id}`, JSON.stringify({ answers, at: result.at }));
    if ($('#report').dataset.reportId !== id || $('#report').dataset.revision !== revision) return;
    reportDirty = JSON.stringify(collect($('#report'))) !== JSON.stringify(answers);
    $('#report-status').textContent =
      `Report · ${$('#report-form').dataset.fields} fields · Submission ${result.id.slice(0, 7)}`;
    const report = lastState?.reports.find(item => item.id === id);
    if (report) {
      report.latest_answer_id = result.id;
      report.latest_answer_at = result.at;
      report.latest_answer_acknowledged_at = null;
      renderReportAcknowledgement();
    }
    void refreshState();
  } catch (error) {
    if ($('#report').dataset.reportId === id) $('#report-status').textContent = `Submission not confirmed: ${error.message}. Entries are kept; resending creates a new answer.`;
  } finally { button.disabled = false; }
});
// The Tasks tab is the agent's own status: two divs, written by the CLI, read on the same poll.
// A row is built from the record with textContent, so a hostile title stays text.
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
  title.tabIndex = 0;
  title.setAttribute('role', 'button');
  title.setAttribute('aria-label', `${task.title}. Task ID ${task.id}. Press Enter to copy it`);
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
  $('#tasks-finished-body').replaceChildren(...tasks.finished.slice().reverse().map(task => taskRow(task)));
  // The head already renders in its own div above; re-listing it in Upcoming duplicates it.
  $('#tasks-upcoming-body').replaceChildren(...tasks.upcoming.slice(1).map(task => taskRow(task)));
  finished.hidden = false;
  upcoming.hidden = false;
}
const tabs = [$('#notes-tab'), $('#reports-tab'), $('#tasks-tab'), $('#downloads-tab')];
// The Reports tab carries a pip rather than a count: what the owner needs from a tab is whether
// something there is unread, not how many reports exist. A report is unread until the owner has
// been shown it, and that reading is stamped on the report itself rather than kept in browser
// storage, so it survives a cleared browser, holds across browsers, and tells the agent the
// report was read instead of leaving it to infer one.
// The agent receipt moves on the server side while the owner reads, and a moved signature
// would rebuild the select under them, so the signature leaves agent_seen_at out.
function reportsSignature(reports) {
  return JSON.stringify(reports, (key, value) => key === 'agent_seen_at' ? undefined : value);
}
function reportLabel(report, position) {
  return `${position + 1}.${report.seen_at ? '' : ' *'} ${report.title}`;
}
function updateReportPip(reports) {
  const pip = $('#report-pip');
  const unseen = reports.filter(report => !report.seen_at && !report.ever_seen);
  pip.hidden = unseen.length === 0;
  pip.title = unseen.length ? 'A report is unread' : 'No unread reports';
  pip.setAttribute('aria-label', unseen.length ? 'Unread report' : 'No unread reports');
}
// A report counts as read when the browser has shown it: scrolled to its end, or, for a report
// that fits the panel with nothing to scroll, held in view for one second on owner direction,
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
  listSignature = reportsSignature(reports);
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
function followReference(type, id) {
  if (!ACK_REFERENCE_PANELS[type] || !lastState) return;
  if (type === 'note') {
    if (!(lastState.notes || []).some(item => item.id === id)) return;
    showTab($('#notes-tab'));
    $('#log-filter').value = 'all';
    save('log-filter', 'all');
    applyLogFilter();
    const row = messageNodes.get(id);
    if (!row) return;
    row.scrollIntoView({block: 'center'});
    row.setAttribute('tabindex', '-1');
    row.focus({preventScroll: true});
    return;
  }
  if (type === 'report') {
    const select = $('#report-select');
    if (!(lastState.reports || []).some(item => item.id === id)) return;
    select.value = id;
    renderReportAcknowledgement();
    showTab($('#reports-tab'));
    select.focus();
    return;
  }
  const groups = ['upcoming', 'finished'];
  if (!groups.some(group => (lastState.tasks?.[group] || []).some(item => item.id === id))) return;
  showTab($('#tasks-tab'));
  const row = [
    ...$('#tasks-current-body').children,
    ...$('#tasks-upcoming-body').children,
    ...$('#tasks-finished-body').children
  ].find(item => item.title === id);
  const title = row && row.children[0];
  if (!title) return;
  title.scrollIntoView({block: 'center'});
  title.focus({preventScroll: true});
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
// The server queues URLs, claims work and stores bytes; only the owner's browser contacts remote
// sites. The proxy checkbox is saved on each job, not a global preference or an automatic fallback.
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
  meta.textContent = `${item.approval === 'denied' ? 'denied' : item.status} · ${item.allow_proxy ? 'proxy opt-in' : 'direct only'}`
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
          await request(`/api/fetch-jobs/${item.id}/retry`, {
            method: 'POST', headers: writeHeaders('application/json'), body: '{}'
          });
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
  meta.textContent = `Agent request · ${item.allow_proxy ? 'proxy opt-in' : 'direct only'}`;
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
        await request(`/api/fetch-jobs/${item.id}/${action}`, {
          method: 'POST', headers: writeHeaders('application/json'), body: '{}', retryOnFailure: false
        });
        $('#fetch-status').textContent = action === 'approve'
          ? `Approved ${item.url}; queued for browser download.`
          : `Denied ${item.url}; this request will not be downloaded.`;
      } catch (error) {
        $('#fetch-status').textContent = `Decision not confirmed: ${error.message}. Check the list before trying again.`;
      } finally {
        await refreshState(); // A lost response may still have decided the request.
        buttons.forEach(control => { control.disabled = false; });
      }
    });
    return button;
  });
  actions.append(...buttons);
  row.append(url, meta, actions);
  return row;
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
    : 'No requests awaiting approval.';
  $('#fetch-list').replaceChildren(...history.map(item => downloadRow(item)));
  const active = history.filter(item => item.status === 'queued' || item.status === 'fetching').length;
  const count = history.length
    ? `${history.length} URL${history.length === 1 ? '' : 's'} in history; ${active} queued or active.`
    : 'No downloads queued yet.';
  $('#fetch-count').textContent = count + (pending.length ? ` ${pending.length} awaiting approval.` : '');
}

async function fetchRemote(job) {
  const limit = job.origin === 'owner' ? Infinity : MAX_FETCH;
  const candidates = [{ source: 'direct', label: 'Direct', url: job.url }];
  if (job.allow_proxy) candidates.push(
    { source: 'allorigins', label: 'AllOrigins', url: `https://api.allorigins.win/raw?url=${encodeURIComponent(job.url)}` },
    { source: 'codetabs', label: 'CodeTabs', url: `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(job.url)}` }
  );
  const failures = [];
  for (const candidate of candidates) {
    $('#fetch-status').textContent = `Fetching ${job.url} via ${candidate.label}…`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), BINARY_TIMEOUT);
    try {
      const response = await fetch(candidate.url, {
        credentials: 'omit', referrerPolicy: 'no-referrer', cache: 'no-store', signal: controller.signal
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (new URL(response.url).protocol !== 'https:') throw new Error('Redirect did not end at HTTPS');
      const declared = Number(response.headers.get('content-length') || 0);
      if (declared > limit) throw new RangeError(`Download exceeds ${MAX_FETCH.toLocaleString()} bytes`);
      if (!response.body || typeof response.body.getReader !== 'function') {
        throw new Error('This browser cannot stream a response to check its size');
      }
      const reader = response.body.getReader();
      const chunks = [];
      let size = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > limit) throw new RangeError(`Download exceeds ${MAX_FETCH.toLocaleString()} bytes`);
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
      if (error instanceof RangeError) throw error; // Proxies cannot override a per-file limit.
      failures.push(`${candidate.label}: ${error.message || String(error)}`);
    } finally { clearTimeout(timer); }
  }
  const hint = job.allow_proxy ? '' : ' Queue the URL again with proxy fallback checked to try proxy services.';
  throw new Error(failures.join('; ') + hint);
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
        $('#fetch-status').textContent = `Saving ${downloadName(job.url)} in the preview…`;
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
  const checkbox = $('#fetch-proxy');
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
    const job = await (await request('/api/fetch-jobs', {
      method: 'POST', headers: writeHeaders('application/json'),
      body: JSON.stringify({ url: field.value.trim(), allow_proxy: checkbox.checked }),
      retryOnFailure: false
    })).json();
    $('#fetch-status').textContent = `Queued ${job.url} · ${job.allow_proxy ? 'proxy opt-in' : 'direct only'}.`;
    field.value = '';
    checkbox.checked = false;
    await refreshState();
  } catch (error) { $('#fetch-status').textContent = `Queue not confirmed: ${error.message}. Check the list before retrying.`; }
  finally { button.disabled = false; }
});
$('#report-select').addEventListener('change', () => { renderReportAcknowledgement(); loadReport(); });
$('#refresh-report').addEventListener('click', () => { refreshState(); loadReport(true); });
// A delete asks for a second click against the same report, the way the log's armed actions do,
// and the arm expires so a stray first click does not sit armed forever. The server keeps the
// report's answers and its source file; only the tab row goes.
let unpublishArmed = null;
$('#unpublish-report').addEventListener('click', async () => {
  const id = $('#report-select').value;
  if (!id) return;
  const button = $('#unpublish-report');
  if (unpublishArmed !== id) {
    unpublishArmed = id;
    button.dataset.state = 'bad';
    $('#report-status').textContent = `Delete ${id}? Click ✕ again to confirm.`;
    setTimeout(() => {
      if (unpublishArmed === id) { unpublishArmed = null; button.dataset.state = ''; }
    }, 8000);
    return;
  }
  if (button.disabled) return;
  unpublishArmed = null;
  button.disabled = true;
  try {
    await request(`/api/reports/${encodeURIComponent(id)}/unpublish`, {
      method: 'POST', headers: writeHeaders('application/json'), body: '{}'
    });
    button.dataset.state = '';
    $('#report').replaceChildren();
    delete $('#report').dataset.reportId;
    delete $('#report').dataset.updatedAt;
    delete $('#report').dataset.revision;
    save('report', '');
    $('#report-status').textContent = `Report ${id} · Deleted · ${time(new Date().toISOString())}`;
    void refreshState();
  } catch (error) {
    $('#report-status').textContent = `Delete failed: ${error.message}`;
  } finally { button.disabled = false; }
});
$('#refresh-notes').addEventListener('click', refreshState);
refreshState();
setInterval(refreshState, 3000);
