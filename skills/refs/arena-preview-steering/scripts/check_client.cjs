// Dependency-free behavioral checks with a minimal DOM; not a browser rendering test.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  // textContent reads through to children, the way a browser does, so a receipt built from
  // two elements still asserts as one string; setting it clears the children, as in a browser.
  get textContent() {
    return this.children.length ? this.children.map(child => child.textContent).join('') : this.text;
  }
  set textContent(value) {
    this.text = value;
    this.children = [];
  }
  constructor() {
    this.value = '';
    this.text = '';
    this.hidden = false;
    this.disabled = false;
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.events = {};
    this.scrollTop = 0;
    this.scrollHeight = 0;
    this.clientHeight = 0;
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name]; }
  addEventListener(name, callback) { this.events[name] = callback; }
  append(...children) {
    for (const child of children) {
      this.children = this.children.filter(item => item !== child);
      this.children.push(child);
    }
  }
  replaceChildren(...children) { this.children = children; this.replacements = (this.replacements || 0) + 1; }
  // A browser clamps a scroll container when the content inside it collapses, and replacing the report
  // is the case the owner hit: the harness does the same, so a missing restore shows up as a jump to
  // the top here exactly as it does on screen.
  set innerHTML(value) {
    this.inner = value; this.renders = (this.renders || 0) + 1;
    const panel = elements.get('#reports-panel');
    if (this.id === 'report' && panel) panel.scrollTop = 0;
  }
  get innerHTML() { return this.inner; }
  querySelectorAll(selector) { return this.fields && selector === '.question[data-field]' ? this.fields : []; }
  get lastElementChild() { return this.children.at(-1); }
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolledIntoView = true; }
  select() { this.selected = true; }
  setSelectionRange(start, end) { this.selectionStart = start; this.selectionEnd = end; }
  remove() { this.removed = true; }
  requestSubmit() { this.submissions = (this.submissions || 0) + 1; }
  click() { this.clicks = (this.clicks || 0) + 1; }
}
const elements = new Map();
const documentEvents = {};
const windowEvents = {};
const copied = [];
let clipboardFails = false;
let execCommandResult = true;
const get = id => {
  if (!elements.has(id)) {
    const element = new Element();
    // A stub element knows its own id, so the parts of the browser a stub has to model can key on it:
    // the scroll clamp below fires for `#report` and nothing else.
    if (id.startsWith('#')) element.id = id.slice(1);
    elements.set(id, element);
  }
  return elements.get(id);
};
get('#notes-tab').setAttribute('aria-controls', 'notes-panel');
get('#reports-tab').setAttribute('aria-controls', 'reports-panel');
get('#tasks-tab').setAttribute('aria-controls', 'tasks-panel');
get('#downloads-tab').setAttribute('aria-controls', 'downloads-panel');
get('#reports-panel').hidden = true;
get('#tasks-panel').hidden = true;
get('#downloads-panel').hidden = true;
get('#upload-file').files = [];
get('#fetch-proxy').checked = false;
get('#note').placeholder = 'What should happen next?';
const storage = new Map();
const root = { dataset: {} };
let counter = 0;
let sendHandler;
let state = { notes: [], reports: [], fetch_jobs: [], last_check: null };
let stateFails = false;
let reportFields = 0;
let reportRevision = '2026-09-22T12:00:00.100000+00:00';
let reportConflict = false;
let reportHtmlWait = null;
let reportSubmitWait = null;
const sent = [];
const readStamps = [];
const uploadCalls = [];
let loseUploadResponse = false;
class FormDataStub {
  constructor() { this.fields = new Map(); }
  append(name, value) { this.fields.set(name, value); }
  get(name) { return this.fields.get(name); }
}
const queuedCalls = [];
const remoteCalls = [];
const remoteBehaviors = new Map();
const resultCalls = [];
const failedCalls = [];
let enqueueResponseLost = false;
let staleToken = false;
let servedToken = 'token-one';
let pageFetches = 0;
const writeTokens = [];
const response = (value, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => value, text: async () => JSON.stringify(value) });
const context = {
  window: { addEventListener: (name, callback) => { windowEvents[name] = callback; } },
  document: { querySelector: get, createElement: tag => Object.assign(new Element(), { tagName: tag }), createTextNode: () => new Element(), documentElement: root, body: { dataset: {}, append() {} }, addEventListener: (name, callback) => { documentEvents[name] = callback; }, execCommand: () => execCommandResult },
  navigator: { clipboard: { writeText: async value => { if (clipboardFails) throw new Error('denied'); copied.push(value); } } },
  localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
  crypto: { randomUUID: () => `${String(++counter).padStart(8, '0')}-0000-4000-8000-000000000000` },
  AbortController,
  Blob,
  FormData: FormDataStub,
  URL,
  setTimeout,
  clearTimeout,
  setInterval: () => 1,
  clearInterval: () => {},
  fetch: async (url, options) => {
    if (url === '/api/state') return stateFails ? response({ error: 'server gone' }, false) : response({ ...state, token: servedToken });
    if (url === '/api/markdown') return { ok: true, text: async () => '<strong>draft</strong>' };
    if (url === '/api/notes') {
      // A note send is the write the retry tests drive, now that no save route exists.
      writeTokens.push(options.headers['X-Preview-Token']);
      if (staleToken && options.headers['X-Preview-Token'] !== servedToken) {
        return { ok: false, status: 403, text: async () => JSON.stringify({ error: 'Bad or missing token' }) };
      }
      const note = JSON.parse(options.body);
      sent.push(note);
      return sendHandler(note);
    }
    if (url.startsWith('/api/reports/') && url.endsWith('/submit')) {
      const submission = JSON.parse(options.body);
      sent.push(submission);
      if (reportSubmitWait) await reportSubmitWait;
      if (reportConflict) return {ok:false, status:409, text:async () => JSON.stringify({error:'Report changed. Copy entries before refreshing.'})};
      return response({ ...submission, at: new Date().toISOString() });
    }
    if (url === '/api/notes/with-file') {
      const id = options.body.get('id');
      const text = options.body.get('text');
      const file = options.body.get('file');
      uploadCalls.push({ id, text, file, token: options.headers['X-Preview-Token'],
        contentType: options.headers['Content-Type'] });
      let saved = state.notes.find(note => note.id === id);
      if (!saved) {
        saved = { id, text, attachment_name: file.name, attachment_path: `uploads/${id}.pdf`,
          at: '2026-09-21T00:00:00+00:00', acknowledged_at: null };
        state.notes = [...state.notes, saved];
        state.uploads = [...(state.uploads || []), { id, name: file.name, type: file.type,
          size: file.size, sha256: 'c'.repeat(64), file: `${id}.pdf`, present: true,
          at: saved.at }];
      }
      if (loseUploadResponse) { loseUploadResponse = false; throw new Error('response lost after commit'); }
      return response(saved);
    }
    if (url === '/api/fetch-jobs') {
      const payload = JSON.parse(options.body);
      const record = {
        id: `fetch-${queuedCalls.length + 1}`, url: payload.url, allow_proxy: payload.allow_proxy,
        status: 'queued', source: null, error: null, name: null, size: null, sha256: null,
        file: null, present: false, at: '2026-09-22T00:00:00+00:00'
      };
      queuedCalls.push({ ...record });
      state.fetch_jobs = [record, ...(state.fetch_jobs || [])];
      if (enqueueResponseLost) { enqueueResponseLost = false; throw new Error('response lost after commit'); }
      return response(record);
    }
    if (url === '/api/fetch-jobs/claim') {
      const record = [...state.fetch_jobs].reverse().find(item => item.status === 'queued');
      if (!record) return response({ job: null });
      record.status = 'fetching';
      return response({ job: { ...record, claim: `claim-${record.id}` } });
    }
    if (url.startsWith('/api/fetch-jobs/')) {
      const [, , , id, actionWithQuery] = url.split('/');
      const action = actionWithQuery.split('?')[0];
      const record = state.fetch_jobs.find(item => item.id === id);
      if (!record) return response({ error: 'No queued download' }, false);
      if (action === 'result') {
        resultCalls.push({ url, body: options.body, source: options.headers['X-Fetch-Source'] });
        record.status = 'saved';
        record.source = options.headers['X-Fetch-Source'];
        record.name = decodeURIComponent(url.split('?name=')[1]);
        record.type = options.headers['Content-Type'];
        record.size = options.body.size;
        record.sha256 = 'd'.repeat(64);
        record.file = id + (record.name.includes('.') ? record.name.slice(record.name.lastIndexOf('.')) : '');
        record.present = true;
        return response(record);
      }
      if (action === 'fail') {
        record.status = 'failed';
        record.error = JSON.parse(options.body).error;
        failedCalls.push({ id, error: record.error });
      } else if (action === 'retry') {
        record.status = 'queued';
        record.error = null;
      }
      return response(record);
    }
    if (url.startsWith('https://')) {
      remoteCalls.push({ url, options });
      const behavior = remoteBehaviors.get(url) || {};
      if (behavior.error) throw new Error(behavior.error);
      const chunks = behavior.chunks || [Uint8Array.from([1, 2, 3])];
      let position = 0;
      return {
        ok: behavior.ok !== false, status: behavior.status || 200, url: behavior.finalURL || url,
        headers: { get: name => name === 'content-length'
          ? behavior.declared == null ? null : String(behavior.declared)
          : behavior.type || 'application/octet-stream' },
        body: { getReader: () => ({
          read: async () => position < chunks.length ? { done: false, value: chunks[position++] } : { done: true },
          cancel: async () => { behavior.cancelled = true; }
        }) }
      };
    }
    if (url === '/') {
      // A fresh page carries the token the restarted server accepts, so the retry has one to take.
      // The token rides an HTML attribute, the way the served page carries it; a reader that looked
      // for it inside the script text found nothing once the script shipped minified, which is why
      // the owner's save presses after a reset never landed.
      pageFetches += 1;
      return { ok: true, status: 200, text: async () => `<body data-token="${servedToken}">` };
    }
    if (url.startsWith('/api/reports/') && url.endsWith('/seen')) {
      readStamps.push(url);
      return response({ id: url.split('/')[3], seen_at: new Date().toISOString() });
    }
    if (url.endsWith('/source')) return { ok: true, text: async () => '# Report source\n' };
    const renderedRevision = reportRevision;
    if (reportHtmlWait) await reportHtmlWait;
    return response({ html: '<h1>Report</h1>', fields: reportFields, revision: renderedRevision });
  }
};
const tick = () => new Promise(resolve => setImmediate(resolve));
// Receipts are built from named parts, so a test reads the part it means instead of counting.
const part = (node, cls) => node.children.find(child => (child.className || '') === cls);
const event = properties => ({ preventDefault() { this.prevented = true; }, ...properties });

(async () => {
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/app.js'), 'utf8'), context);
  await tick();
  // The page supplies the glyph, so the client starts with none; the copy sets it and restores it.
  const copyIcon = get('#copy-state');
  const normalTimeout = context.setTimeout;
  let finishCopy;
  context.setTimeout = callback => { finishCopy = callback; };
  await context.copyFrom(copyIcon, 'icon probe', 'state');
  assert.equal(copyIcon.textContent, '✓');
  finishCopy();
  assert.equal(copyIcon.textContent, '⧉', 'restore the copy glyph when its timer ends');
  context.setTimeout = normalTimeout;
  copied.length = 0;

  assert.equal(root.dataset.theme, 'dark');
  assert.equal(get('#theme').textContent, '☀');
  assert.equal(get('#theme').getAttribute('aria-label'), 'Switch to light mode');
  get('#theme').events.click();
  assert.equal(root.dataset.theme, 'light');
  assert.equal(get('#theme').textContent, '☾');
  assert.equal(get('#theme').getAttribute('aria-label'), 'Switch to dark mode');
  assert.equal(storage.get('arena-preview-v1:theme'), 'light');
  const body = context.document.body;
  const log = get('#history');
  assert.equal(body.dataset.chrome, 'open');
  assert.equal(get('#chrome').getAttribute('aria-expanded'), 'true');
  assert.equal(get('#chrome').getAttribute('aria-label'), 'Collapse bar');
  assert.equal(get('#chrome').textContent, '▲');
  get('#chrome').events.click();
  assert.equal(body.dataset.chrome, 'closed');
  assert.equal(get('#chrome').getAttribute('aria-expanded'), 'false');
  assert.equal(get('#chrome').getAttribute('aria-label'), 'Expand bar');
  assert.equal(get('#chrome').textContent, '▼');
  assert.equal(storage.get('arena-preview-v1:chrome'), 'closed');
  get('#chrome').events.click();
  assert.equal(body.dataset.chrome, 'open');
  assert.equal(get('#chrome').textContent, '▲');
  get('#composer-toggle').events.click();
  assert.equal(body.dataset.composer, 'closed');
  assert.equal(get('#composer-toggle').getAttribute('aria-expanded'), 'false');
  assert.equal(get('#composer-toggle').getAttribute('aria-label'), 'Show composer');
  assert.equal(get('#composer-toggle').textContent, '✎');
  assert.equal(storage.get('arena-preview-v1:composer'), 'closed');
  log.scrollHeight = 500; log.clientHeight = 100; log.scrollTop = 0;
  get('#note').scrollHeight = 96;
  get('#composer-toggle').events.click();
  assert.equal(body.dataset.composer, 'open');
  assert.equal(log.scrollTop, 500);
  // An empty field keeps the stylesheet's min-height; a placeholder no longer holds the box open.
  assert.equal(get('#note').style.height, '');
  get('#note').value = 'a draft';
  context.grow();
  assert.equal(get('#note').style.height, '98px');
  get('#note').value = '**draft**';
  await get('#preview-note').events.click();
  assert.equal(get('#note').hidden, true);
  assert.equal(get('#preview-note').getAttribute('aria-pressed'), 'true');
  assert.equal(get('#preview-note').textContent, 'MD 👁');
  assert.equal(get('#draft-preview').innerHTML, '<strong>draft</strong>');
  assert.equal(sent.length, 0);
  await get('#preview-note').events.click();
  assert.equal(get('#note').hidden, false);
  assert.equal(get('#note').value, '**draft**');
  assert.equal(get('#note').style.height, '98px');
  get('#note').scrollHeight = 140;
  get('#note').value = 'keep draft';
  get('#note').events.input();
  assert.equal(get('#note').style.height, '142px');
  get('#reports-tab').events.click();
  assert.equal(get('#notes-panel').hidden, true);
  assert.equal(get('#note').value, 'keep draft');
  get('#reports-tab').events.keydown(event({ key: 'ArrowLeft' }));
  assert.equal(get('#notes-panel').hidden, false);
  assert.equal(get('#tasks-status').textContent, 'The agent has not written a task list yet.');
  assert.equal(get('#tasks-finished').hidden, true);
  get('#notes-tab').events.keydown(event({ key: 'ArrowRight' }));
  assert.equal(get('#reports-panel').hidden, false);
  get('#reports-tab').events.keydown(event({ key: 'ArrowRight' }));
  assert.equal(get('#tasks-panel').hidden, false);
  assert.equal(get('#reports-panel').hidden, true);
  get('#tasks-tab').events.keydown(event({ key: 'ArrowRight' }));
  assert.equal(get('#downloads-panel').hidden, false, 'the Downloads panel holds the browser queue');
  assert.equal(get('#tasks-panel').hidden, true);
  get('#downloads-tab').events.keydown(event({ key: 'ArrowRight' }));
  assert.equal(get('#notes-panel').hidden, false);
  get('#notes-tab').events.keydown(event({ key: 'End' }));
  assert.equal(get('#downloads-panel').hidden, false);
  get('#tasks-tab').events.keydown(event({ key: 'Home' }));
  assert.equal(get('#notes-panel').hidden, false);
  // Switching tabs fires an unawaited refreshState, so flush the queue before a click that
  // has to land: stateBusy swallows a refresh while another is still in flight.
  await new Promise(resolve => setTimeout(resolve, 0));
  state.tasks = {
    finished: [{ id: 'shipped', title: 'Dots in the receipt', details: [], status: 'finished',
      order: 1, updated_at: new Date().toISOString() }],
    upcoming: [
      { id: 'docs-archive', title: '<img onerror=alert(1)> dir',
        details: ['move BUDGET-EXCEPTIONS.md', 'write arena-quirks.md'], status: 'upcoming',
        order: 1, updated_at: new Date().toISOString() },
      { id: 'second', title: 'Second in line', details: ['its only detail'], status: 'upcoming',
        order: 2, updated_at: new Date().toISOString() }
    ],
    updated_at: new Date().toISOString()
  };
  await get('#refresh-notes').events.click();
  const upcomingBody = get('#tasks-upcoming-body');
  const finishedBody = get('#tasks-finished-body');
  // The head renders in its own div and stays out of Upcoming; the row shape is asserted on
  // the second task, which Upcoming does carry.
  assert.equal(upcomingBody.children.length, 1, 'the head stays out of Upcoming');
  assert.equal(upcomingBody.children[0].tagName, 'li');
  assert.equal(upcomingBody.children[0].children[0].textContent, 'Second in line');
  assert.equal(upcomingBody.children[0].children[0].className, 'task-title');
  assert.equal(upcomingBody.children[0].children[1].tagName, 'details');
  assert.equal(upcomingBody.children[0].children[1].children.length, 2, 'a summary and one list');
  assert.equal(upcomingBody.children[0].children[1].children[0].tagName, 'summary');
  assert.equal(upcomingBody.children[0].children[1].children[0].textContent, '1 detail');
  // The details are a real list, so each carries its own marker rather than being a line in a span.
  const detailList = upcomingBody.children[0].children[1].children[1];
  assert.equal(detailList.tagName, 'ul');
  assert.equal(detailList.className, 'task-detail-list');
  assert.equal(detailList.children.length, 1);
  assert.equal(detailList.children[0].tagName, 'li');
  assert.equal(detailList.children[0].className, 'task-detail');
  assert.equal(detailList.children[0].textContent, 'its only detail');
  assert.equal(upcomingBody.children[0].title, 'second', 'hover shows the task ID, not its detail');
  assert.equal(finishedBody.children.length, 1);
  assert.equal(finishedBody.children[0].title, 'shipped');
  assert.equal(finishedBody.children[0].children.length, 1);
  assert.equal(finishedBody.children[0].children[0].textContent, 'Dots in the receipt');
  assert.equal(get('#tasks-finished').hidden, false);
  assert.equal(get('#tasks-upcoming').hidden, false);
  // A hostile title is text in the current row, because a row is built with textContent
  // rather than innerHTML. The head renders in a div of its own and stays out of Upcoming.
  const currentBody = get('#tasks-current-body');
  assert.equal(get('#tasks-current').hidden, false);
  assert.equal(currentBody.children.length, 1);
  assert.equal(currentBody.children[0].children[0].textContent, '<img onerror=alert(1)> dir');
  assert.equal(currentBody.children[0].children[0].className, 'task-title');
  assert.equal(currentBody.children[0].title, 'docs-archive');
  const taskControl = currentBody.children[0].children[0];
  assert.equal(taskControl.dataset.taskId, 'docs-archive');
  assert.equal(taskControl.attributes.role, 'button');
  assert.equal(taskControl.tabIndex, 0, 'keyboard users can reach the task ID');
  documentEvents.click(event({ target: taskControl }));
  await tick();
  assert.equal(copied.at(-1), 'docs-archive', 'click copies the full task ID');
  assert.equal(taskControl.dataset.copied, 'good');
  const taskDraft = get('#note').value;
  const taskCopied = copied.length;
  documentEvents.click(event({ target: taskControl, ctrlKey: true }));
  assert.equal(copied.length, taskCopied, 'Ctrl-click quotes without copying');
  assert.equal(get('#note').value, `RE: docs-archive\n\n${taskDraft}`);
  assert.equal(get('#notes-panel').hidden, false, 'quoting a task opens the Notes tab');
  assert.equal(get('#note').focused, true);
  get('#note').value = taskDraft;
  get('#tasks-tab').events.click();
  assert.equal(upcomingBody.children.length, 1, 'the head is removed from Upcoming');
  assert.match(get('#tasks-status').textContent, /^Updated /);
  assert.doesNotMatch(get('#tasks-status').textContent, / · |written by|takes no answers/);
  // An unchanged poll must not rebuild the rows, or an opened details snaps shut three seconds later.
  const opened = upcomingBody.children[0].children[1];
  opened.open = true;
  await get('#refresh-notes').events.click();
  assert.equal(upcomingBody.children[0].children[1], opened, 'the row survives an unchanged poll');
  assert.equal(upcomingBody.children[0].children[1].open, true);
  // The log and the tasks lost their own copy buttons. One copy button carries the note and task
  // lines a restore reads back, as NDJSON, and the reports tab keeps its button. Nothing derived
  // rides the copy: no rendered html, token, seq, reports, uploads or last check, and the stamps
  // arrive from the poll already cut to seconds, which is all a restore needs.
  const cacheKeyHere = [...storage.keys()].find(key => key.endsWith(':state-cache'));
  assert.ok(cacheKeyHere, 'every poll caches the state the copy button copies');
  copied.length = 0;
  get('#copy-state').events.click();
  await tick();
  const copiedText = copied.at(-1);
  assert.ok(copiedText.endsWith('\n') && !copiedText.endsWith('\n\n'),
    'the state copies as NDJSON with one trailing newline');
  const lines = copiedText.slice(0, -1).split('\n').map(line => JSON.parse(line));
  const cachedHere = JSON.parse(storage.get(cacheKeyHere));
  const projectHere = (record, keys) => {
    const line = {};
    for (const key of keys) line[key] = record[key] ?? null;
    return line;
  };
  const noteKeysHere = ['id', 'text', 'at', 'acknowledged_at', 'ack_kind', 'ack_text', 'ack_edited_at', 'seen_at', 'task_id'];
  const taskKeysHere = ['id', 'title', 'details', 'status', 'order'];
  assert.deepEqual(lines, [
    ...cachedHere.notes.map(note => projectHere(note, noteKeysHere)),
    ...(cachedHere.tasks.upcoming || []).map(task => projectHere(task, taskKeysHere)),
    ...(cachedHere.tasks.finished || []).map(task => projectHere(task, taskKeysHere)),
  ], 'the copy carries the note and task lines a restore reads, and nothing derived');
  const taskLines = lines.filter(line => 'title' in line);
  assert.equal(lines.filter(line => 'report_id' in line).length, 0, 'the copy carries no report answers');
  assert.equal(taskLines.length,
    (cachedHere.tasks.upcoming || []).length + (cachedHere.tasks.finished || []).length,
    'every cached task rides the copy');
  assert.equal(get('#copy-state').dataset.state, 'good', 'the click reports through the button');
  assert.match(get('#send-status').textContent,
    new RegExp(`Copied ${lines.length - taskLines.length} messages and ${taskLines.length} tasks as NDJSON\\.`),
    'the receipt counts what the clipboard took');
  state.tasks.upcoming = [];
  await get('#refresh-notes').events.click();
  assert.equal(get('#tasks-current').hidden, true, 'an empty queue has no current task');
  assert.equal(currentBody.children.length, 0);
  assert.equal(get('#tasks-upcoming').hidden, false, 'the section still renders, empty');
  delete state.tasks;
  await get('#refresh-notes').events.click();
  assert.equal(get('#tasks-finished').hidden, true);
  assert.equal(get('#tasks-current').hidden, true, 'no task list, no current div');
  storage.delete(cacheKeyHere);
  get('#copy-state').events.click();
  await tick();
  assert.equal(get('#copy-state').title, 'There is no state to copy');

  assert.equal(get('#tasks-status').textContent, 'The agent has not written a task list yet.');
  assert.equal(get('#notes-tab').focused, true);
  get('#note').events.keydown(event({ key: 'Enter', shiftKey: false, isComposing: false }));
  assert.equal(get('#form').submissions, 1);
  get('#note').events.keydown(event({ key: 'Enter', shiftKey: true, isComposing: false }));
  get('#note').events.keydown(event({ key: 'Enter', shiftKey: false, isComposing: true }));
  assert.equal(get('#form').submissions, 1);
  sendHandler = async () => { throw new Error('response lost'); };
  await get('#form').events.submit(event({}));
  assert.equal(get('#note').value, 'keep draft');
  assert.match(get('#send-status').textContent, /Save not confirmed/);
  sendHandler = async note => response({ ...note, at: new Date().toISOString() });
  get('#note').scrollHeight = 72;
  await get('#form').events.submit(event({}));
  assert.equal(sent[0].id, sent[1].id);
  assert.match(sent[0].id, /^[0-9a-f]{7}-[0-9a-f]{25}$/);
  assert.equal(get('#note').value, '');
  // A cleared field collapses back to the stylesheet's min-height instead of keeping its grown size.
  assert.equal(get('#note').style.height, '');
  assert.match(get('#send-status').textContent, /Saved/);
  assert.match(get('#send-status').textContent, /· Message sent\./);
  assert.doesNotMatch(get('#send-status').textContent, /awaiting acknowledgement/);
  assert.equal(get('#note').placeholder, 'keep draft');
  await tick();
  get('#note').value = 'sent while typing';
  let release;
  sendHandler = note => new Promise(resolve => { release = () => resolve(response({ ...note, at: new Date().toISOString() })); });
  const sending = get('#form').events.submit(event({}));
  get('#note').value = 'new unsent draft';
  release();
  await sending;
  assert.equal(get('#note').value, 'new unsent draft');
  await tick();
  state = { notes: [{ id: 'one', text: '<img onerror=alert(1)>', at: new Date().toISOString(), acknowledged_at: null }], reports: [], last_check: null };
  await get('#refresh-notes').events.click();
  assert.equal(get('#history').children[0].children[0].textContent, '<img onerror=alert(1)>');
  assert.match(get('#history').children[0].children[2].textContent, /^one ·  · [A-Z][a-z]{2} /);
  // The line reads ID · who · state · time, and the dot after the ID is the ASCII separator the
  // owner asked for by name; the state stays a coloured dot.
  assert.equal(part(get('#history').children[0].children[2], 'receipt-sep').textContent, ' · ');
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').dataset.state, 'sent');
  // A message that became a task says so, so a line that was read is never mistaken for one that
  // was dropped; the task ID rides in the marker's title.
  state.notes[0].task_id = 'dots-in-receipt';
  await get('#refresh-notes').events.click();
  assert.match(get('#history').children[0].children[2].textContent, / · Task added$/);
  assert.equal(part(get('#history').children[0].children[2], 'receipt-task').title, 'Task dots-in-receipt');
  delete state.notes[0].task_id;
  await get('#refresh-notes').events.click();
  assert.equal(part(get('#history').children[0].children[2], 'receipt-task'), undefined,
    'a message with no task carries no marker');
  // A message the agent wrote used to say so through an origin tag; that key is gone from the
  // schema, and the rendered text wrapper is named for what it is rather than borrowing the
  // report class; owner note d6fcfc2a.
  assert.equal(get('#history').children[0].children[0].className, 'raw-message',
    'a message the server sent without rendered HTML keeps the raw class');
  state.notes.push({
    id: 'from-agent',
    text: 'written by the agent',
    html: '<p>written by the agent</p>',
    at: new Date().toISOString(),
    acknowledged_at: null
  });
  await get('#refresh-notes').events.click();
  const agentReceipt = get('#history').children.at(-1).children[2];
  assert.deepEqual(agentReceipt.children.map(child => child.className).filter(Boolean),
    ['note-id', 'receipt-sep', 'state-dot'],
    'ID, separator, state — no writer tag remains on the receipt');
  assert.equal(get('#history').children.at(-1).children[0].className, 'message-text',
    'rendered message text is named for what it is, not for a report');
  // The fixture note is this block's own; the tests after it read the log that was there before.
  state.notes.pop();
  await get('#refresh-notes').events.click();
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').title, 'Sent');
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').attributes['aria-label'], 'Sent');
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').attributes.role, 'img');
  assert.equal(context.clipPlaceholder('one\ntwo\nthree'), 'one\ntwo\nthree');
  assert.equal(context.clipPlaceholder('one\ntwo\nthree\nfour'), 'one\ntwo\n\u2026');
  assert.equal(context.clipPlaceholder('one\ntwo\nthree\nfour\nfive'), 'one\ntwo\n\u2026');
  const beforeGrow = get('#note').value;
  get('#note').value = ''; get('#note').scrollHeight = 300; context.grow();
  assert.equal(get('#note').style.height, '');
  get('#note').value = beforeGrow; get('#note').scrollHeight = 96; context.grow();
  assert.doesNotMatch(get('#history').children[0].children[2].textContent,
    /Awaiting|ACK-ed|Saved|Delivered|Sent|Seen|Said| id /);
  assert.equal(get('#last-check').textContent, 'Not checked yet.');
  const stamp = get('#history').children[0].children[2].textContent;
  assert.match(stamp, /[A-Z][a-z]{2} \d{2}, \d{2}:\d{2}/);
  assert.doesNotMatch(stamp, /\d{2}:\d{2}:\d{2}/);
  assert.doesNotMatch(stamp, /\b\d{4}\b/);
  assert.doesNotMatch(stamp, /[AP]M/);
  // A seconds-only stamp is UTC on the wire; the formatter pins it to UTC so a browser
  // outside UTC shows the converted local wall clock, not the server's digits.
  {
    const secondsOnly = context.time('2026-06-15T12:00:00');
    const withZone = context.time('2026-06-15T12:00:00Z');
    assert.equal(secondsOnly, withZone,
      'a seconds-only stamp formats as UTC, matching the same instant with a Z');
    const offsetKept = context.time('2026-06-15T12:00:00.000+00:00');
    assert.equal(offsetKept, withZone, 'a stamped offset still parses as UTC');
  }
  assert.equal(get('#history').children[0].children[1].hidden, true);
  assert.match(get('#history').children[0].children[1].className, /^answer/);
  assert.equal(get('#history').children[0].children[2].className, 'receipt');
  state.notes[0].seen_at = new Date().toISOString();
  await get('#refresh-notes').events.click();
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').dataset.state, 'seen');
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').title, 'Seen');
  state.notes[0].html = '<p>&lt;img onerror=alert(1)&gt;</p>';
  state.notes[0].acknowledged_at = new Date().toISOString();
  state.last_check = new Date().toISOString();
  await get('#refresh-notes').events.click();
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').dataset.state, 'said');
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').title, 'Said');
  assert.match(get('#last-check').textContent, /^Last checked [A-Z][a-z]{2} \d{2}, \d{2}:\d{2}$/);
  assert.equal(get('#history').children[0].children[0].innerHTML, '<p>&lt;img onerror=alert(1)&gt;</p>');
  state.notes[0].ack_kind = 'reply';
  state.notes[0].ack_text = '**done**';
  state.notes[0].ack_html = '<p><strong>done</strong></p>';
  await get('#refresh-notes').events.click();
  const answer = get('#history').children[0].children[1];
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').dataset.state, 'said');
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').title, 'Said');
  assert.equal(typeof documentEvents.click, 'function');
  const copyButton = new Element();
  copyButton.className = 'copy-code';
  copyButton.dataset = { code: 'print(1)' };
  documentEvents.click({ target: copyButton });
  await tick();
  assert.equal(copied.at(-1), 'print(1)');
  assert.equal(copyButton.textContent, '✓');
  assert.equal(copyButton.title, 'Copied through the clipboard API');
  assert.equal(copyButton.getAttribute('aria-label'), 'Copied through the clipboard API');
  assert.equal(copyButton.dataset.state, 'good');
  documentEvents.click({ target: new Element() });
  documentEvents.click({});
  clipboardFails = true;
  const fallback = new Element();
  fallback.className = 'copy-code';
  fallback.dataset = { code: 'second' };
  documentEvents.click({ target: fallback });
  await tick();
  assert.equal(fallback.textContent, '✓');
  assert.equal(fallback.title, 'Copied through the selection fallback');
  execCommandResult = false;
  const denied = new Element();
  denied.className = 'copy-code';
  denied.dataset = { code: 'third' };
  documentEvents.click({ target: denied });
  await tick();
  assert.equal(denied.textContent, '✗');
  assert.equal(denied.title, 'Clipboard blocked; select the code and copy it');
  assert.equal(denied.dataset.state, 'bad');
  clipboardFails = false;
  // The header clock is the log's own face with seconds, so the two cannot disagree.
  assert.match(get('#clock').textContent, /^[A-Z][a-z]{2} \d{2}( \d{2})?, \d{2}:\d{2}:\d{2}$/);
  assert.ok(get('#clock').title.length > 3);
  // A receipt ID copies on a click, and a blocked clipboard says so on the ID itself.
  const idCode = get('#history').children[0].children[2].children[0];
  assert.equal(idCode.className, 'note-id');
  clipboardFails = true;
  execCommandResult = false;
  documentEvents.click({ target: idCode });
  await tick();
  assert.equal(idCode.dataset.copied, 'bad');
  assert.match(idCode.title, /^Clipboard blocked; the ID is /);
  clipboardFails = false;
  execCommandResult = true;
  assert.equal(answer.innerHTML, '<p><strong>done</strong></p>');
  assert.match(answer.className, /answer reply message-text/);
  assert.equal(answer.hidden, false);
  state.notes[0].ack_kind = 'note';
  state.notes[0].ack_text = 'rechecked';
  delete state.notes[0].ack_html;
  await get('#refresh-notes').events.click();
  assert.equal(answer.textContent, 'rechecked');
  assert.equal(answer.children.length, 1);
  assert.equal(answer.children[0].tagName, 'p');
  assert.match(answer.className, /answer reply/);
  assert.doesNotMatch(answer.className, /note/);
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').dataset.state, 'said');
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').title, 'Said');
  assert.equal(get('#note').value, 'new unsent draft');
  state.notes.push({ id: 'two', text: 'second', at: new Date().toISOString(), acknowledged_at: null });
  log.scrollHeight = 400; log.clientHeight = 200; log.scrollTop = 200;
  await get('#refresh-notes').events.click();
  assert.deepEqual(log.children.map(item => item.children[2].children[0].textContent), ['one', 'two']);
  assert.deepEqual(log.children.map(item => item.children[2].children[0].tagName), ['code', 'code']);
  assert.deepEqual(log.children.map(item => part(item.children[2], 'receipt-sep').tagName), ['span', 'span']);
  assert.equal(log.scrollTop, 400);
  log.scrollTop = 0;
  state.notes.push({ id: 'three', text: 'third', at: new Date().toISOString(), acknowledged_at: null });
  await get('#refresh-notes').events.click();
  assert.equal(log.scrollTop, 0);
  assert.equal(log.children.at(-1).children[2].children[0].textContent, 'three');
  assert.equal(get('#connection-dot').dataset.state, 'ok');
  assert.equal(get('#connection-dot').getAttribute('aria-label'), 'Connected');
  assert.equal(get('#connection-text').textContent, '3 messages saved');
  stateFails = true;
  await get('#refresh-notes').events.click();
  assert.equal(get('#connection-dot').dataset.state, 'down');
  assert.equal(get('#connection-dot').getAttribute('aria-label'), 'Disconnected');
  assert.match(get('#connection-text').textContent, /Connection failed: server gone/);
  stateFails = false;
  await get('#refresh-notes').events.click();
  assert.equal(get('#connection-dot').dataset.state, 'ok');
  state.reports = [{ id: 'r1', title: 'Fielded', updated_at: new Date().toISOString() }];
  reportFields = 3;
  storage.set('arena-preview-v1:answers:r1', JSON.stringify({ answers: { name: 'ada', areas: ['ui'], verdict: 'Other: make it blue' }, at: '2026-09-20T12:00:00.000Z' }));
  const textInput = { value: '', className: 'answer-text', scrollHeight: 40, style: {} };
  const text = new Element();
  text.dataset = { field: 'name', type: 'text' };
  text.querySelector = selector => selector === 'textarea.answer-text' ? textInput : null;
  text.querySelectorAll = () => [];
  const uiBox = { value: 'ui', checked: false, dataset: {} };
  const apiBox = { value: 'api', checked: true, dataset: {} };
  const boxes = [uiBox, apiBox];
  const picks = new Element();
  picks.dataset = { field: 'areas', type: 'checkbox' };
  picks.querySelector = () => null;
  picks.querySelectorAll = selector => (selector === 'input:checked' ? boxes.filter(box => box.checked) : boxes);
  const shipBox = { value: 'Ship it', checked: false, dataset: {} };
  const otherBox = { value: 'Other: ___', checked: false, dataset: { label: 'Other' } };
  const otherOption = { querySelector: selector => (selector === '[data-label="Other"]' ? otherBox : null) };
  const otherText = { value: '', dataset: { custom: 'Other' }, className: 'custom-text', scrollHeight: 40, style: {}, parentElement: otherOption };
  const choices = [shipBox, otherBox, otherText];
  const verdict = new Element();
  verdict.dataset = { field: 'verdict', type: 'choice' };
  verdict.querySelector = selector => (selector === '[data-custom="Other"]' ? otherText : null);
  verdict.querySelectorAll = selector => (selector === 'input:checked' ? choices.filter(box => box.checked) : choices);
  get('#report').fields = [text, picks, verdict];
  get('#report-select').value = 'r1';
  get('#reports-tab').events.click();
  await tick();
  await get('#refresh-report').events.click();
  await tick();
  assert.equal(get('#report').innerHTML, '<h1>Report</h1>');
  assert.equal(get('#report-select').children[0].textContent, '1. * Fielded',
    'a report with no read stamp carries the asterisk in the select');
  assert.equal(get('#report-submit').hidden, false);
  assert.match(get('#report-status').textContent, /3 fields/);
  assert.equal(textInput.value, 'ada');
  assert.equal(textInput.style.height, '42px', 'restored answers expand the textarea');
  textInput.value = 'first line\nsecond line';
  textInput.scrollHeight = 88;
  documentEvents.input({ target: textInput });
  assert.equal(textInput.style.height, '90px', 'typed lines grow the textarea');
  assert.equal(context.collect(get('#report')).name, 'first line\nsecond line',
    'line breaks survive answer collection');
  textInput.value = 'ada';
  assert.equal(uiBox.checked, true);
  assert.equal(apiBox.checked, false);
  assert.equal(shipBox.checked, false);
  assert.equal(otherBox.checked, true);
  assert.equal(otherText.value, 'make it blue');
  assert.equal(otherText.style.height, '42px');
  otherText.value = 'typed in the slot';
  otherText.scrollHeight = 88;
  documentEvents.input({ target: otherText });
  assert.equal(otherBox.checked, true);
  assert.equal(otherText.style.height, '90px');
  documentEvents.input({ target: get('#note') });
  documentEvents.input({});
  otherText.value = '   ';
  documentEvents.input({ target: otherText });
  assert.equal(otherBox.checked, false);
  otherText.value = 'make it blue';
  documentEvents.input({ target: otherText });
  assert.equal(otherBox.checked, true);
  assert.equal(get('#report-receipt').hidden, false);
  assert.match(get('#report-receipt').textContent, /^✓ Sent /);
  textInput.value = 'ada lovelace';
  apiBox.checked = true;
  otherText.value = '  make it red  ';
  await get('#report-form').events.submit(event({}));
  assert.deepEqual(sent.at(-1).answers, { name: 'ada lovelace', areas: ['ui', 'api'], verdict: 'Other: make it red' });
  assert.equal(sent.at(-1).revision, reportRevision, 'send the revision that supplied the form');
  assert.match(get('#report-status').textContent, /^Answers sent /);
  assert.match(get('#report-agent-ack').textContent, /awaiting agent acknowledgement/);
  assert.ok(get('#report-agent-ack').textContent.includes(sent.at(-1).id.slice(0, 7)),
    'show the seven-character ID immediately after sending');
  assert.ok(!get('#report-agent-ack').textContent.includes(sent.at(-1).id),
    'do not show the full submission ID');
  assert.deepEqual(JSON.parse(storage.get('arena-preview-v1:answers:r1')).answers, { name: 'ada lovelace', areas: ['ui', 'api'], verdict: 'Other: make it red' });
  await get('#refresh-report').events.click();
  await tick();
  assert.match(get('#report-status').textContent, /^Answers sent /);
  assert.match(get('#report-status').textContent, /3 fields stay filled in/);
  assert.equal(otherBox.checked, true);
  assert.equal(otherText.value, 'make it red');
  otherText.value = '   ';
  shipBox.checked = true;
  await get('#report-form').events.submit(event({}));
  assert.deepEqual(sent.at(-1).answers, { name: 'ada lovelace', areas: ['ui', 'api'], verdict: 'Ship it' });
  await get('#refresh-report').events.click();
  await tick();
  assert.equal(shipBox.checked, true);
  assert.equal(otherBox.checked, false);
  assert.equal(otherText.value, '');
  shipBox.checked = false;
  await get('#report-form').events.submit(event({}));
  assert.equal('verdict' in sent.at(-1).answers, false);
  const beforeDelayedUpdate = get('#report').renders;
  let releaseHtml;
  reportHtmlWait = new Promise(resolve => { releaseHtml = resolve; });
  state.reports[0].updated_at = '2026-09-22T12:00:00';
  await get('#refresh-notes').events.click(); await tick();
  textInput.value = 'keep this draft';
  get('#report-form').events.input(event({target:textInput}));
  releaseHtml(); await tick();
  reportHtmlWait = null;
  assert.equal(get('#report').renders, beforeDelayedUpdate, 'keep edits made while an automatic refresh was fetching');
  const beforeDirtyRefresh = get('#report').renders;
  const oldRevision = reportRevision;
  reportRevision = '2026-09-22T12:00:01.200000+00:00';
  state.reports[0].updated_at = '2026-09-22T12:00:01';
  await get('#refresh-notes').events.click(); await tick();
  assert.equal(get('#report').renders, beforeDirtyRefresh, 'automatic updates must keep unsent answers');
  reportConflict = true;
  await get('#report-form').events.submit(event({}));
  assert.equal(sent.at(-1).revision, oldRevision, 'never relabel an old form with the latest poll revision');
  assert.equal(textInput.value, 'keep this draft');
  assert.match(get('#report-status').textContent, /Submission not confirmed.*Report changed/);
  assert.equal(get('#report-submit').disabled, false);
  reportConflict = false;
  await get('#refresh-report').events.click(); await tick();
  assert.equal(get('#report').dataset.revision, reportRevision, 'explicit refresh loads a new revision');
  let releaseSubmission;
  reportSubmitWait = new Promise(resolve => { releaseSubmission = resolve; });
  const beforeSendingUpdate = get('#report').renders;
  const sendingReport = get('#report-form').events.submit(event({}));
  reportRevision = '2026-09-22T12:00:02.300000+00:00';
  state.reports[0].updated_at = '2026-09-22T12:00:02';
  await get('#refresh-notes').events.click(); await tick();
  assert.equal(get('#report').renders, beforeSendingUpdate, 'keep a submitted form until its request completes');
  reportConflict = true;
  releaseSubmission(); await sendingReport;
  assert.equal(get('#report').renders, beforeSendingUpdate, 'keep the form when an in-flight request is rejected');
  assert.match(get('#report-status').textContent, /Submission not confirmed.*Report changed/);
  reportSubmitWait = null;
  reportConflict = false;
  reportFields = 0;
  await get('#refresh-report').events.click();
  await tick();
  assert.equal(get('#report-submit').hidden, true);
  assert.equal(get('#report-receipt').hidden, true);
  get('#notes-tab').events.keydown(event({ key: 'End' }));
  assert.equal(get('#downloads-panel').hidden, false);
  assert.equal(get('#downloads-tab').focused, true);
  assert.equal(get('#downloads-tab').attributes['aria-selected'], 'true');
  get('#tasks-tab').events.keydown(event({ key: 'ArrowLeft' }));
  assert.equal(get('#reports-panel').hidden, false);
  assert.equal(get('#reports-tab').focused, true);
  assert.equal(get('#reports-tab').attributes['aria-selected'], 'true');
  // The tab carries a pip rather than a count: visible while a report carries no read stamp of its
  // own. The stamp lives on the report, so a cleared browser cannot make a read report unread.
  const pip = get('#report-pip');
  state.reports = [{ id: 'r1', title: 'Fielded', updated_at: new Date().toISOString(),
    seen_at: '2026-09-20T22:00:00' }];
  await tick();
  await get('#refresh-notes').events.click();
  assert.equal(pip.hidden, true, 'a report carrying a read stamp is not unread');
  assert.equal(pip.title, 'No unread reports');
  assert.equal(get('#report-select').children.find(item => item.value === 'r1').textContent,
    '1. Fielded', 'a report already read is not starred in the select');
  // An unanswered form moves neither marker: the star and the pip report unread, and nothing else.
  state.reports[0].needs_answer = true;
  await get('#refresh-notes').events.click();
  assert.equal(pip.hidden, true, 'an unanswered form leaves the pip alone');
  assert.equal(get('#report-select').children.find(item => item.value === 'r1').textContent,
    '1. Fielded', 'an unanswered form leaves the star alone');
  state.reports = [{ id: 'r1', title: 'Fielded', updated_at: new Date().toISOString(), seen_at: null }];
  await get('#refresh-notes').events.click();
  assert.equal(pip.hidden, false, 'a report with no read stamp is unread');
  assert.equal(pip.title, 'A report is unread');
  assert.equal(pip.attributes['aria-label'], 'Unread report');
  assert.equal(get('#report-select').children.find(item => item.value === 'r1').textContent,
    '1. * Fielded', 'an unseen report is starred in the select');
  assert.equal([...storage.keys()].filter(item => item.endsWith(':reports-read-at')).length, 0,
    'the tab writes no browser marker now that the stamp lives on the report');
  const agentAck = get('#report-agent-ack');
  state.reports[0].latest_answer_id = 'a123456-aaaaaaaaaaaaaaaaaaaaaaaaa';
  state.reports[0].latest_answer_at = '2026-09-24T10:00:00';
  state.reports[0].latest_answer_acknowledged_at = null;
  await get('#refresh-notes').events.click();
  assert.equal(agentAck.hidden, false, 'show the latest answer while it awaits a receipt');
  assert.match(agentAck.textContent, /Submission a123456/);
  assert.ok(!agentAck.textContent.includes('a123456-'), 'the UI only shows seven ID characters');
  assert.match(agentAck.textContent, /awaiting agent acknowledgement/);
  state.reports[0].latest_answer_acknowledged_at = '2026-09-24T10:01:00';
  await get('#refresh-notes').events.click();
  assert.match(agentAck.textContent, /Agent acknowledged the latest answer/);
  assert.equal(pip.hidden, false, 'acknowledging an answer does not mark the report read');
  state.reports[0].latest_answer_id = 'b765432-bbbbbbbbbbbbbbbbbbbbbbbbb';
  state.reports[0].latest_answer_at = '2026-09-24T10:02:00';
  state.reports[0].latest_answer_acknowledged_at = null;
  await get('#refresh-notes').events.click();
  assert.match(agentAck.textContent, /Submission b765432/);
  assert.ok(!agentAck.textContent.includes('a123456'), 'the old submission ID disappears');
  assert.match(agentAck.textContent, /awaiting agent acknowledgement/,
    'a previous receipt does not cover a later answer');
  state.reports = [];
  await get('#refresh-notes').events.click();
  assert.equal(agentAck.hidden, true, 'hide receipts when no report is selected');
  assert.equal(pip.hidden, true, 'with no reports there is nothing unread');
  // What stamps a report is the browser showing it: one second in view for one that fits the
  // panel with nothing to scroll, and the moment its end is reached for one that does not.
  const panel = get('#reports-panel');
  const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
  state.reports = [{ id: 'r1', title: 'Fits', updated_at: new Date().toISOString(), seen_at: null }];
  readStamps.length = 0;
  panel.scrollHeight = 400; panel.clientHeight = 400; panel.scrollTop = 0;
  get('#reports-tab').events.click();
  await tick(); await tick();
  assert.equal(readStamps.length, 0, 'a report that fits is not stamped on sight');
  await wait(1200);
  assert.deepEqual(readStamps, ['/api/reports/r1/seen'], 'one second in view stamps it');
  // A report longer than the panel is not stamped while its end is out of reach, and the panel is
  // the element that scrolls, so its own position is what counts.
  state.reports = [{ id: 'r1', title: 'Long', updated_at: new Date().toISOString(), seen_at: null }];
  readStamps.length = 0;
  panel.scrollHeight = 900; panel.clientHeight = 300; panel.scrollTop = 0;
  get('#reports-tab').events.click();
  await tick(); await tick();
  assert.equal(readStamps.length, 0, 'an unscrolled long report is not stamped');
  panel.scrollTop = 600;
  panel.events.scroll();
  await tick();
  assert.deepEqual(readStamps, ['/api/reports/r1/seen'], 'reaching the end stamps it at once');
  // Leaving the tab before the dwell is over stamps nothing, so a flick past a short report does
  // not count as reading it.
  readStamps.length = 0;
  panel.scrollHeight = 400; panel.clientHeight = 400; panel.scrollTop = 0;
  get('#reports-tab').events.click();
  await tick(); await tick();
  get('#notes-tab').events.click();
  await tick();
  await wait(1200);
  assert.equal(readStamps.length, 0, 'a report left before its dwell ends is not stamped');
  get('#reports-tab').events.click();
  await tick();
  // Marking a report read folds the stamp into the state instead of re-rendering: the panel keeps
  // its place and that report's label loses its asterisk at once, which is the bug the owner hit
  // when reading a report threw the page back to the top.
  state.reports = [{ id: 'r1', title: 'Long', updated_at: new Date().toISOString(), seen_at: null }];
  await get('#refresh-notes').events.click();
  await tick();
  assert.equal(get('#report-select').children.find(item => item.value === 'r1').textContent,
    '1. * Long', 'an unseen report is starred before the stamp lands');
  readStamps.length = 0;
  panel.scrollHeight = 900; panel.clientHeight = 300; panel.scrollTop = 600;
  panel.events.scroll();
  await tick();
  assert.deepEqual(readStamps, ['/api/reports/r1/seen'], 'reaching the end stamps the report');
  assert.equal(panel.scrollTop, 600, 'the stamp does not move the panel');
  assert.equal(get('#report-select').children.find(item => item.value === 'r1').textContent,
    '1. Long', 'the asterisk goes as soon as the stamp lands');
  assert.equal(pip.hidden, true, 'the pip clears in place');
  // An update to the report being read keeps the panel where the owner left it, and a report the owner
  // switches to starts at its top, because the panel is the scroller and the report is replaced.
  panel.scrollHeight = 900; panel.clientHeight = 300; panel.scrollTop = 450;
  state.reports = [
    { id: 'r1', title: 'Long', updated_at: new Date(Date.now() + 1000).toISOString(), seen_at: new Date().toISOString() },
    { id: 'r2', title: 'Other', updated_at: new Date().toISOString(), seen_at: new Date().toISOString() }
  ];
  await get('#refresh-notes').events.click();
  await tick(); await tick();
  assert.equal(panel.scrollTop, 450, 'a report update keeps the panel where the owner left it');
  get('#report-select').value = 'r2';
  get('#report-select').events.change();
  await tick(); await tick();
  assert.equal(panel.scrollTop, 0, 'a report the owner switched to starts at its top');
  // The log filter selects over the dots the log already draws, adds no new notion, and leaves the
  // copy alone: that is the restore path, and a filtered copy would restore a partial log.
  const logStamp = new Date().toISOString();
  state.notes = [
    { id: 'n1', text: 'unread', at: logStamp, acknowledged_at: null },
    { id: 'n2', text: 'read', at: logStamp, seen_at: logStamp, acknowledged_at: null },
    { id: 'n3', text: 'answered', at: logStamp, seen_at: logStamp, acknowledged_at: logStamp,
      ack_kind: 'note', ack_text: 'ok' }
  ];
  await tick();
  await get('#refresh-notes').events.click();
  await tick();
  assert.equal(get('#log-filter').value, 'all', 'the log opens unfiltered');
  const messageRow = id => get('#history').children.find(node =>
    node.children[2].children[0].textContent === id);
  const visibleRows = () => ['n1', 'n2', 'n3'].filter(id => !messageRow(id).hidden);
  assert.deepEqual(visibleRows(), ['n1', 'n2', 'n3'], 'every message shows under All');
  assert.equal(get('#log-empty').hidden, true, 'nothing to explain while the filter matches');
  assert.equal(messageRow('n1').dataset.state, 'sent');
  assert.equal(messageRow('n2').dataset.state, 'seen');
  assert.equal(messageRow('n3').dataset.state, 'said');
  for (const [filter, expected] of [['sent', ['n1']], ['seen', ['n2']], ['said', ['n3']]]) {
    get('#log-filter').value = filter;
    get('#log-filter').events.change();
    assert.deepEqual(visibleRows(), expected, `the ${filter} filter shows its own state only`);
    assert.equal(get('#log-empty').hidden, true);
  }
  assert.equal([...storage.keys()].some(key => key.endsWith(':log-filter')), true,
    'the chosen filter is remembered');
  // A filter that matches nothing says so and counts what it is holding back.
  state.notes = [{ id: 'n1', text: 'unread', at: logStamp, acknowledged_at: null }];
  await get('#refresh-notes').events.click();
  await tick();
  get('#log-filter').value = 'said';
  get('#log-filter').events.change();
  assert.equal(messageRow('n1').hidden, true);
  assert.equal(get('#log-empty').hidden, false, 'a filter with no match explains itself');
  assert.match(get('#log-empty').textContent, /Nothing here is Said yet/);
  // The filter keeps the log's place: at its end, the log returns there when rows come back,
  // because the browser clamps the scroll while the view is short and never puts it back.
  const logView = get('#history');
  state.notes = [
    { id: 'n1', text: 'unread', at: logStamp, acknowledged_at: null },
    { id: 'n2', text: 'read', at: logStamp, seen_at: logStamp, acknowledged_at: null }
  ];
  await get('#refresh-notes').events.click();
  await tick();
  logView.scrollHeight = 900; logView.clientHeight = 300; logView.scrollTop = 600;
  logView.events.scroll();
  get('#log-filter').value = 'sent';
  get('#log-filter').events.change();
  assert.equal(logView.scrollTop, 900, 'a filtered view with one row sits at its end');
  get('#log-filter').value = 'all';
  get('#log-filter').events.change();
  assert.equal(logView.scrollTop, 900, 'the log returns to its end when the rows come back');
  logView.scrollTop = 0;
  logView.events.scroll();
  get('#log-filter').value = 'seen';
  get('#log-filter').events.change();
  assert.equal(logView.scrollTop, 0, 'a log the owner scrolled away from stays where they left it');
  // The jump bar is the remedy for a long log: hidden at the end, shown once the log is scrolled
  // away from it, and taking the log back to the newest message when it is used.
  const jump = get('#log-newest');
  logView.scrollTop = 900;
  logView.events.scroll();
  assert.equal(jump.hidden, true, 'no bar while the log sits at its end');
  logView.scrollTop = 120;
  logView.events.scroll();
  assert.equal(jump.hidden, false, 'the bar appears once the log is scrolled away from its end');
  jump.events.click();
  assert.equal(logView.scrollTop, 900, 'the bar returns the log to its newest message');
  assert.equal(jump.hidden, true, 'and goes when there is nothing below');
  // The save button posts the page's cached copy, so a wiped server is refilled from the browser,
  // and a page that has never polled says so instead of posting nothing.
  const priorState = state;
  state = {
    notes: [{ id: 'saved', text: 'cached here', at: new Date().toISOString(), acknowledged_at: null }],
    reports: [],
    tasks: { finished: [], upcoming: [{ id: 'saved-task', title: 'Cached here', details: [],
      status: 'upcoming', order: 1, updated_at: new Date().toISOString() }] },
    last_check: null
  };
  await get('#refresh-notes').events.click();
  const stateCopyButton = get('#copy-state');
  const cacheKey = [...storage.keys()].find(item => item.endsWith(':state-cache'));
  assert.ok(cacheKey, 'every successful poll caches the copy the state button copies');
  copied.length = 0;
  stateCopyButton.events.click();
  await tick();
  assert.equal(copied.length, 1, 'the button copies the cache');
  assert.ok(copied[0].split('\n').filter(Boolean).length > 1, 'the copy carries note and task lines');
  assert.match(get('#send-status').textContent, /Copied \d+ messages and \d+ tasks as NDJSON\./);
  assert.equal(stateCopyButton.dataset.state, 'good');
  storage.delete(cacheKey);
  copied.length = 0;
  stateCopyButton.events.click();
  await tick();
  assert.equal(copied.length, 0, 'nothing is copied without a cache');
  assert.match(get('#send-status').textContent, /Nothing cached to copy yet/);
  assert.equal(stateCopyButton.dataset.state, 'bad');
  // A page outlives the server that served it. After a sandbox reset the token baked into the page
  // is refused, so the page takes a fresh token, from the poll or from a fresh page, and tries once
  // more instead of waiting for a manual refresh; the owner pressed save state several times after
  // a reset and nothing landed. The save route is gone, so a note send carries the same proof.
  staleToken = true;
  storage.set(cacheKey, JSON.stringify({ notes: state.notes, tasks: state.tasks }));
  sendHandler = async note => response({ ...note, at: new Date().toISOString() });
  const sendNote = async text => {
    get('#note').value = text;
    await get('#form').events.submit(event({}));
  };
  // First net: the poll hands the page the token the restarted server accepts, so the write lands
  // with no page fetch and no refresh, which is what the owner needed.
  servedToken = 'token-two';
  const sendsBefore = sent.length;
  const fetchesBefore = pageFetches;
  await get('#refresh-notes').events.click();
  await sendNote('after the poll');
  assert.equal(pageFetches, fetchesBefore, 'the poll already refreshed the token');
  assert.equal(sent.length, sendsBefore + 1, 'the send lands on the token from the poll');
  assert.equal(writeTokens.at(-1), 'token-two', 'the send carries the token the new server accepts');
  // Second net: a write refused before any poll re-reads the page for its token and tries once more.
  servedToken = 'token-three';
  await sendNote('before any poll');
  await tick();
  assert.equal(pageFetches, fetchesBefore + 1, 'a refused write re-reads the page for its token');
  assert.equal(sent.length, sendsBefore + 2, 'the write lands on the retry');
  assert.equal(writeTokens.at(-1), 'token-three', 'the retry carries the token the new server accepts');
  staleToken = false;
  // Give the page back the token its own page carried, so a later test that writes does not
  // inherit this one's stand-in token; the poll is what hands it over.
  servedToken = '__TOKEN__';
  await get('#refresh-notes').events.click();
  // The fixture above is this test's own; later tests read the state that was live before it.
  state = priorState;
  await get('#refresh-notes').events.click();
  // With the filter matching nothing, the state copy still carries every message: the cache is the
  // restore path, and a filtered copy would restore a partial log as if it were all of it.
  get('#log-filter').value = 'said';
  get('#log-filter').events.change();
  copied.length = 0;
  get('#copy-state').events.click();
  await tick();
  const filteredNotes = copied.at(-1).slice(0, -1).split('\n')
    .map(line => JSON.parse(line)).filter(line => 'title' in line === false);
  assert.ok(filteredNotes.length > 0, 'the fixture holds messages to carry');
  assert.equal(filteredNotes.length, state.notes.length,
    'the state copies whatever the filter shows, not the filtered view of it');
  get('#log-filter').value = 'all';
  get('#log-filter').events.change();
  await tick();
  state.notes.push({ id: 'old', text: 'old note', at: '2024-06-15T12:00:00.000Z', acknowledged_at: null });
  await get('#refresh-notes').events.click();
  assert.match(get('#history').children.at(-1).children[2].textContent, /[A-Z][a-z]{2} \d{2} \d{2}, \d{2}:\d{2}/);
  state = { notes: [{ id: 'a66700e4-37f0-4182-b782-33c38a83728d', text: 'long id', at: new Date().toISOString(), acknowledged_at: null }], reports: [], last_check: null };
  await get('#refresh-notes').events.click();
  const longReceipt = get('#history').children.at(-1).children[2];
  assert.equal(longReceipt.children[0].textContent, 'a66700e');
  assert.equal(longReceipt.children[0].title, 'a66700e4-37f0-4182-b782-33c38a83728d');
  assert.equal(longReceipt.children[0].className, 'note-id');
  assert.doesNotMatch(longReceipt.textContent, /a66700e4-37f0/);
  assert.match(longReceipt.textContent, /^a66700e ·  · [A-Z][a-z]{2} /);
  assert.equal(part(longReceipt, 'state-dot').dataset.state, 'sent');
  // A plain click copies the seven characters on show; a shift-click copies the whole ID.
  const longId = longReceipt.children[0];
  assert.notEqual(longId.textContent, longId.dataset.full);
  documentEvents.click({ target: longId });
  await tick();
  assert.equal(copied.at(-1), longId.textContent);
  assert.equal(longId.dataset.copied, 'good');
  documentEvents.click({ target: longId, shiftKey: true });
  await tick();
  assert.equal(copied.at(-1), longId.dataset.full);
  assert.match(longId.title, /^Copied through the clipboard API: /);
  // A ctrl-click quotes instead of copying: the composer takes a `RE: <shortid>` line, the caret
  // lands after it, and a hidden composer is opened first. A draft already written is kept below
  // a blank line rather than lost.
  const noteBox = get('#note');
  noteBox.value = 'a draft already written';
  noteBox.hidden = true;
  const copiedBefore = copied.length;
  documentEvents.click({ target: longId, ctrlKey: true });
  assert.equal(copied.length, copiedBefore, 'a ctrl-click leaves the clipboard alone');
  assert.equal(noteBox.value, `RE: ${longId.textContent}\n\na draft already written`);
  assert.equal(noteBox.hidden, false, 'quoting opens a hidden composer');
  assert.equal(noteBox.focused, true);
  assert.equal(noteBox.selectionStart, 12, 'the caret sits after the quote line');
  assert.equal(noteBox.selectionEnd, 12);
  assert.equal(longId.title, `Quoted in the composer: RE: ${longId.textContent}`);
  assert.equal(storage.get([...storage.keys()].find(item => item.endsWith(':draft'))), noteBox.value,
    'the quote is kept as the draft');
  // An empty composer gets exactly the line that was asked for, and quoting a second note
  // retargets the prefix rather than stacking two of them.
  noteBox.value = '';
  const firstId = get('#history').children[0].children[2].children[0];
  documentEvents.click({ target: firstId, ctrlKey: true });
  assert.equal(noteBox.value, `RE: ${firstId.textContent}\n`);
  noteBox.value = `RE: ${firstId.textContent}\nsomething typed after it`;
  documentEvents.click({ target: longId, ctrlKey: true });
  assert.equal(noteBox.value, `RE: ${longId.textContent}\n\nsomething typed after it`);
  // Meta is the same gesture on a Mac, and a plain click still copies rather than quotes.
  noteBox.value = '';
  documentEvents.click({ target: longId, metaKey: true });
  assert.equal(noteBox.value, `RE: ${longId.textContent}\n`);
  noteBox.value = '';
  documentEvents.click({ target: longId });
  await tick();
  assert.equal(copied.at(-1), longId.textContent, 'a plain click still copies');
  assert.equal(noteBox.value, '', 'and does not fill the composer');
  // The report copies its Markdown source, fetched on the click rather than riding the poll.
  const selectBefore = get('#report-select').value;
  get('#report-select').value = 'p1';
  get('#copy-report').events.click();
  await tick();
  assert.equal(copied.at(-1), '# Report source\n');
  assert.equal(get('#copy-report').dataset.state, 'good');
  get('#report-select').value = '';
  get('#copy-report').events.click();
  await tick();
  assert.equal(get('#copy-report').dataset.state, 'bad');
  assert.equal(get('#copy-report').title, 'There is no report to copy');
  get('#report-select').value = selectBefore;
  // Existing upload records still live beside the composer; a missing file retains its row.
  state.uploads = [
    { id: 'kept', name: 'shot.png', type: 'image/png', size: 2048, sha256: 'a'.repeat(64), file: 'kept.png', at: '2026-09-21T00:00:00+00:00', present: true },
    { id: 'gone', name: 'notes.zip', type: 'application/zip', size: 3000, sha256: 'b'.repeat(64), file: 'gone.zip', at: '2026-09-21T00:00:00+00:00', present: false }
  ];
  await get('#refresh-notes').events.click();
  assert.equal(get('#uploads-count').textContent, '2 files saved.');
  const kept = get('#uploads-list').children[0];
  assert.equal(kept.children[0].textContent, 'shot.png');
  assert.match(kept.children[1].textContent, /^2 kB · image\/png · .* · aaaaaaaaaaaa$/);
  assert.equal(kept.children[2].textContent, 'uploads/kept.png');
  const gone = get('#uploads-list').children[1];
  assert.equal(gone.children[2].textContent, 'the bytes are gone; the record survived a restore');
  assert.equal(gone.children[2].className, 'upload-gone');

  // The file picker is kept, but now stages a single file beside "Your message". The composer
  // accepts one dropped file, rejects empty/oversize files before sending, and can remove/replace it.
  const picker = get('#upload-file');
  get('#attach-file').events.click();
  assert.equal(picker.clicks, 1, 'the attach button opens the native picker');
  picker.files = [{ name: 'empty.bin', size: 0, type: '' }];
  picker.events.change();
  assert.equal(get('#send-status').textContent, 'That file is empty.');
  picker.files = [{ name: 'big.bin', size: 50_000_001, type: 'application/octet-stream' }];
  picker.events.change();
  assert.equal(get('#send-status').textContent, 'That file is 50,000,001 bytes; the ceiling is 50,000,000.');
  assert.equal(uploadCalls.length, 0, 'invalid files never leave the page');
  const file = { name: 'report card.pdf', size: 12, type: 'application/pdf', lastModified: 7 };
  picker.files = [file];
  picker.events.change();
  assert.equal(get('#staged-file').textContent, 'report card.pdf');
  assert.equal(get('#staged-file').hidden, false);
  assert.equal(get('#remove-file').hidden, false);
  assert.equal(uploadCalls.length, 0, 'choosing a file does not upload it yet');
  get('#remove-file').events.click();
  assert.equal(get('#staged-file').hidden, true);
  assert.equal(picker.value, '');
  const dragging = event({ dataTransfer: { types: ['Files'], files: [file] } });
  get('#compose').events.dragover(dragging);
  assert.equal(dragging.prevented, true);
  assert.equal(get('#compose').dataset.dragging, 'true');
  const dropping = event({ dataTransfer: { types: ['Files'], files: [file] } });
  get('#compose').events.drop(dropping);
  assert.equal(dropping.prevented, true);
  assert.equal(get('#compose').dataset.dragging, undefined);
  assert.equal(get('#staged-file').textContent, 'report card.pdf');
  get('#compose').events.drop(event({ dataTransfer: { types: ['Files'], files: [file, file] } }));
  assert.equal(get('#send-status').textContent, 'Attach one file per note.');
  assert.equal(get('#staged-file').textContent, 'report card.pdf', 'a rejected selection keeps the staged file');

  // The file and text share one ID and one multipart call. A lost response keeps both in memory;
  // a manual retry uses the same ID and never generates a separate upload notification note.
  const notesBeforeFile = state.notes.length;
  const sendsBeforeFile = sent.length;
  get('#note').value = 'Please review the attached report';
  loseUploadResponse = true;
  await get('#form').events.submit(event({}));
  assert.equal(uploadCalls.length, 1);
  assert.equal(uploadCalls[0].file, file);
  assert.equal(uploadCalls[0].text, 'Please review the attached report');
  assert.equal(uploadCalls[0].contentType, undefined, 'the browser supplies the multipart boundary');
  assert.equal(uploadCalls[0].token, '__TOKEN__');
  assert.equal(sent.length, sendsBeforeFile, 'no separate note is posted');
  assert.equal(get('#staged-file').hidden, false, 'a failed response keeps the staged file');
  assert.match(get('#send-status').textContent, /^Save not confirmed:/);
  assert.equal(JSON.parse(storage.get('arena-preview-v1:pending')).id, uploadCalls[0].id);
  await get('#form').events.submit(event({}));
  await tick();
  await get('#refresh-notes').events.click();
  assert.equal(uploadCalls.length, 2);
  assert.equal(uploadCalls[0].id, uploadCalls[1].id, 'an unchanged retry has one note ID');
  assert.equal(state.notes.length, notesBeforeFile + 1, 'one message, not a separate upload note');
  assert.equal(sent.length, sendsBeforeFile);
  assert.equal(get('#note').value, '');
  assert.equal(get('#staged-file').hidden, true);
  assert.equal(get('#uploads-list').children.length, 3, 'the linked file stays in composer records');
  assert.equal(get('#uploads-list').children[2].children[0].textContent, 'report card.pdf');
  assert.equal(get('#uploads-list').children[2].children[2].textContent, `uploads/${uploadCalls[0].id}.pdf`);
  const attached = get('#history').children.find(item => item.children[2].children[0].dataset.full === uploadCalls[0].id);
  assert.ok(attached);
  const receipt = attached.children[2];
  assert.equal(part(receipt, 'receipt-file').textContent, ' · report card.pdf');
  assert.ok(receipt.children.indexOf(part(receipt, 'receipt-file')) > receipt.children.indexOf(part(receipt, 'state-dot')),
    'the filename follows the receipt date and state dot');

  // A file-only composer still sends a real note instead of an upload notification.
  picker.files = [{ name: 'single.bin', size: 1, type: '' }];
  picker.events.change();
  await get('#form').events.submit(event({}));
  assert.equal(uploadCalls.at(-1).text, 'File: single.bin');
  assert.equal(sent.length, sendsBeforeFile);
  assert.equal(get('#staged-file').hidden, true);

  // The queue records per-job opt-in and a browser worker claims one URL at a time. Remote fetches
  // omit credentials and referrers. None of these mocks assert actual browser CORS behavior.
  const waitFor = async predicate => {
    for (let attempt = 0; attempt < 80; attempt++) {
      if (predicate()) return;
      await tick();
    }
    throw new Error('Browser queue did not settle');
  };
  get('#fetch-url').value = 'http://example.org/unsafe.zip';
  await get('#fetch-form').events.submit(event({}));
  assert.match(get('#fetch-status').textContent, /Only HTTPS/);
  assert.equal(queuedCalls.length, 0);
  get('#fetch-url').value = 'https://user:password@example.org/unsafe.zip';
  await get('#fetch-form').events.submit(event({}));
  assert.equal(queuedCalls.length, 0, 'embedded credentials are rejected before queueing');

  const direct = 'https://files.example.org/plugin.zip';
  remoteBehaviors.set(direct, { declared: 2, type: 'application/zip', chunks: [Uint8Array.from([80, 75])] });
  get('#fetch-url').value = direct;
  await get('#fetch-form').events.submit(event({}));
  await waitFor(() => state.fetch_jobs[0]?.status === 'saved');
  assert.equal(queuedCalls[0].allow_proxy, false, 'direct access is the per-job default');
  assert.equal(remoteCalls.at(-1).url, direct);
  assert.equal(remoteCalls.at(-1).options.credentials, 'omit');
  assert.equal(remoteCalls.at(-1).options.referrerPolicy, 'no-referrer');
  assert.equal(resultCalls[0].source, 'direct');
  assert.equal(resultCalls[0].body.size, 2);
  assert.equal(get('#fetch-list').children[0].children[2].textContent, 'downloads/fetch-1.zip');
  assert.equal(get('#fetch-count').textContent, '1 URL in history; 0 queued or active.');

  const blocked = 'https://files.example.org/cors.zip';
  remoteBehaviors.set(blocked, { error: 'CORS blocked' });
  get('#fetch-url').value = blocked;
  await get('#fetch-form').events.submit(event({}));
  await waitFor(() => state.fetch_jobs[0]?.status === 'failed');
  assert.equal(queuedCalls[1].allow_proxy, false);
  assert.match(state.fetch_jobs[0].error, /CORS blocked.*proxy fallback checked/);
  assert.equal(remoteCalls.filter(item => item.url.startsWith('https://api.allorigins.win/')).length, 0,
    'no proxy is used without opt-in');
  remoteBehaviors.set(blocked, { chunks: [Uint8Array.from([1])] });
  const retryRow = get('#fetch-list').children.find(item => item.children[0].textContent === blocked);
  await retryRow.children.at(-1).events.click();
  await waitFor(() => state.fetch_jobs.find(item => item.url === blocked)?.status === 'saved');
  assert.equal(queuedCalls.length, 2, 'retry reuses the same SQLite job');

  const origin = 'https://files.example.org/fallback.zip';
  const allOrigins = `https://api.allorigins.win/raw?url=${encodeURIComponent(origin)}`;
  remoteBehaviors.set(origin, { error: 'CORS blocked' });
  remoteBehaviors.set(allOrigins, { chunks: [Uint8Array.from([3, 4])] });
  get('#fetch-url').value = origin;
  get('#fetch-proxy').checked = true;
  await get('#fetch-form').events.submit(event({}));
  await waitFor(() => state.fetch_jobs[0]?.status === 'saved');
  assert.equal(queuedCalls[2].allow_proxy, true);
  assert.equal(get('#fetch-proxy').checked, false, 'the next URL requires its own opt-in');
  assert.equal(resultCalls.at(-1).source, 'allorigins');
  assert.equal(remoteCalls.at(-1).url, allOrigins);

  const third = 'https://files.example.org/third.zip';
  const allOriginsThird = `https://api.allorigins.win/raw?url=${encodeURIComponent(third)}`;
  const codeTabs = `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(third)}`;
  remoteBehaviors.set(third, { error: 'CORS blocked' });
  remoteBehaviors.set(allOriginsThird, { error: 'Proxy offline' });
  remoteBehaviors.set(codeTabs, { chunks: [Uint8Array.from([5])] });
  get('#fetch-url').value = third;
  get('#fetch-proxy').checked = true;
  await get('#fetch-form').events.submit(event({}));
  await waitFor(() => state.fetch_jobs[0]?.status === 'saved');
  assert.equal(resultCalls.at(-1).source, 'codetabs');
  assert.equal(remoteCalls.at(-1).url, codeTabs);

  const tooLarge = 'https://files.example.org/too-large.bin';
  remoteBehaviors.set(tooLarge, { declared: 50_000_001 });
  const callsBeforeLimit = remoteCalls.length;
  const resultsBeforeLimit = resultCalls.length;
  get('#fetch-url').value = tooLarge;
  get('#fetch-proxy').checked = true;
  await get('#fetch-form').events.submit(event({}));
  await waitFor(() => state.fetch_jobs[0]?.status === 'failed');
  assert.equal(remoteCalls.length, callsBeforeLimit + 1, 'a declared oversize file never reaches proxies');
  assert.equal(resultCalls.length, resultsBeforeLimit, 'oversize bytes never reach the preview');
  assert.match(state.fetch_jobs[0].error, /50,000,000 bytes/);

  const streamed = 'https://files.example.org/stream.bin';
  const streamBehavior = { chunks: [{ byteLength: 50_000_001 }] };
  remoteBehaviors.set(streamed, streamBehavior);
  get('#fetch-url').value = streamed;
  await get('#fetch-form').events.submit(event({}));
  await waitFor(() => state.fetch_jobs[0]?.status === 'failed');
  assert.equal(streamBehavior.cancelled, true, 'oversize streams are cancelled');
  assert.equal(resultCalls.length, resultsBeforeLimit);
  const lost = 'https://files.example.org/lost.bin';
  remoteBehaviors.set(lost, { chunks: [Uint8Array.from([1])] });
  const beforeLost = queuedCalls.length;
  enqueueResponseLost = true;
  get('#fetch-url').value = lost;
  await get('#fetch-form').events.submit(event({}));
  assert.equal(queuedCalls.length, beforeLost + 1, 'a lost enqueue response is not blindly retried');
  assert.match(get('#fetch-status').textContent, /Queue not confirmed.*Check the list/);
  await get('#refresh-notes').events.click();
  await waitFor(() => state.fetch_jobs.find(item => item.url === lost)?.status === 'saved');
  state.fetch_jobs = [];
  await get('#refresh-notes').events.click();

  state.notes = [
    {id: 'edited-old', text: 'Older question', at: '2026-09-22T00:00:00', acknowledged_at: '2026-09-22T00:01:00', ack_kind: 'reply', ack_text: 'First answer', ack_edited_at: null},
    {id: 'newer-note', text: 'Newer question', at: '2026-09-22T00:02:00'}
  ];
  await get('#refresh-notes').events.click();
  assert.equal(get('#log-edited').hidden, true);
  state.notes[0].ack_text = 'Changed answer';
  state.notes[0].ack_edited_at = '2026-09-22T00:03:00';
  await get('#refresh-notes').events.click();
  const editedNode = get('#history').children[0];
  assert.match(editedNode.children[2].textContent, / · Edited Sep 22, /);
  assert.equal(get('#history').children[1].children[2].children[0].dataset.full, 'newer-note', 'edits keep log order');
  assert.equal(get('#notes-pip').hidden, false);
  assert.equal(get('#log-edited').hidden, false);
  get('#log-filter').value = 'sent';
  get('#log-filter').events.change();
  get('#log-edited').events.click();
  assert.equal(editedNode.children[1].scrolledIntoView, true);
  assert.equal(get('#log-filter').value, 'all');
  assert.equal(get('#notes-pip').hidden, true);
  await get('#refresh-notes').events.click();
  assert.equal(get('#log-edited').hidden, true, 'an unchanged poll does not notify again');
  assert.ok([...storage.keys()].some(key => key.endsWith(':seen-edits')));
  state.notes[0].ack_text = 'Another edit in the same second';
  await get('#refresh-notes').events.click();
  assert.equal(get('#log-edited').hidden, false, 'same-second edits still notify');
  get('#log-edited').events.click();
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/app.js'), 'utf8'), {...context});
  await tick();
  assert.equal(get('#log-edited').hidden, true, 'viewed edits stay viewed after a reload');
  state.reports = [{id: 'stable', title: 'Stable', updated_at: '2026-09-22T00:00:00', seen_at: '2026-09-22T00:00:01'}];
  await get('#refresh-notes').events.click();
  get('#report-select').value = 'stable';
  get('#reports-tab').events.click();
  await tick(); await tick();
  let renders = get('#report').renders;
  state.reports.push({id: 'other', title: 'Other report', updated_at: '2026-09-22T01:00:00'});
  await get('#refresh-notes').events.click(); await tick();
  assert.equal(get('#report').renders, renders, 'another report must not render the unchanged current report');
  state.last_check = new Date().toISOString();
  await get('#refresh-notes').events.click(); await tick();
  assert.equal(get('#report').renders, renders, 'CLI inbox checks do not render the report');
  state.reports[0].updated_at = '2026-09-22T02:00:00';
  await get('#refresh-notes').events.click(); await tick();
  assert.equal(get('#report').renders, renders + 1, 'current-report updates still render');
  renders = get('#report').renders;
  const replacements = get('#report').replacements;
  get('#refresh-report').events.click();
  assert.equal(get('#report').replacements, replacements, 'keep old content until the refresh arrives');
  await tick(); await tick();
  assert.equal(get('#report').renders, renders + 1, 'explicit refresh still renders');
  state.notes = [{id:'notes-only', text:'No tasks yet', at:'2026-09-22T12:00:00'}];
  state.tasks = null;
  await get('#refresh-notes').events.click();
  const copiesBeforeNotesOnly = copied.length;
  await get('#copy-state').events.click();
  await tick();
  assert.equal(copied.length, copiesBeforeNotesOnly + 1, 'copy a session before its first task');
  assert.match(copied.at(-1), /"id":"notes-only"/);
  assert.equal(get('#copy-state').dataset.state, 'good');
  console.log('PASS: default theme, theme persistence, the chevron bar toggle, the pencil composer toggle and the sun/moon theme button with persistence, the MD eye preview toggle, the green and red connection dot, 24-hour timestamps without seconds or a same-year year, four-tab navigation with Downloads separate from composer uploads, staged picker/drop/removal and one linked file per note with a 50 MB limit, a browser fetch queue with direct/opt-in proxy fallback and streamed size checks, the tasks tab rendering the head of the queue in its own div, both stored sections and its unwritten state, draft retention, Enter/IME, retries, receipts with visible note IDs, state dots and a click that copies the short ID or the whole one on shift and quotes it into the composer on ctrl, clipped placeholders, the header clock with its date and seconds, the copy button on the reports tab and the state copy button, agent replies and notes in the log, chat order with the log pinned to the newest message, the bare last-sent placeholder, report fields, pre-filled saved answers and the sent receipt, and the log filter over Sent, Seen and Said');
})().catch(error => { console.error(error); process.exitCode = 1; });
