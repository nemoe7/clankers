// Ordered preview-client checks under node:test. Later checks read the page earlier checks left.
// This is not a browser rendering test.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { File } = require('node:buffer');

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
const replySeenCalls = [];
const unpublished = [];
const uploadCalls = [];
let loseUploadResponse = false;
class FormDataStub {
  constructor() { this.fields = new Map(); }
  append(name, value) { this.fields.set(name, [...(this.fields.get(name) || []), value]); }
  get(name) { return (this.fields.get(name) || [])[0]; }
  getAll(name) { return this.fields.get(name) || []; }
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
  File,
  FormData: FormDataStub,
  URL,
  setTimeout,
  clearTimeout,
  setInterval: () => 1,
  clearInterval: () => {},
  fetch: async (url, options) => {
    if (url === '/api/state') return stateFails ? response({ error: 'server gone' }, false) : response({ ...state, token: servedToken });
    if (url === '/api/submissions') return response((state.submissions || []).filter(record => (state.reports || []).some(report => report.id === record.report_id)));
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
      const files = options.body.getAll('file');
      uploadCalls.push({ id, text, files, token: options.headers['X-Preview-Token'],
        contentType: options.headers['Content-Type'] });
      let saved = state.notes.find(note => note.id === id);
      if (!saved) {
        const records = files.map((file, index) => {
          const ext = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')) : '';
          const stored = `${id}${files.length > 1 ? `-${index + 1}` : ''}${ext}`;
          return { id: index ? `${id}-file-${index}` : id, note_id: id, name: file.name,
            type: file.type, size: file.size, sha256: 'c'.repeat(64),
            file: stored, path: `uploads/${stored}`, present: true,
            at: '2026-09-21T00:00:00+00:00' };
        });
        saved = { id, text, attachment_name: files[0].name, attachment_path: records[0].path,
          attachments: records, at: '2026-09-21T00:00:00+00:00', acknowledged_at: null };
        state.notes = [...state.notes, saved];
        state.uploads = [...(state.uploads || []), ...records];
      }
      if (loseUploadResponse) { loseUploadResponse = false; throw new Error('response lost after commit'); }
      return response(saved);
    }
    if (url === '/api/fetch-jobs') {
      const payload = JSON.parse(options.body);
      const record = {
        id: `fetch-${queuedCalls.length + 1}`, url: payload.url, allow_proxy: payload.allow_proxy,
        status: 'queued', approval: 'approved', origin: 'owner', source: null, error: null, name: null, size: null, sha256: null,
        file: null, present: false, at: '2026-09-22T00:00:00+00:00'
      };
      queuedCalls.push({ ...record });
      state.fetch_jobs = [record, ...(state.fetch_jobs || [])];
      if (enqueueResponseLost) { enqueueResponseLost = false; throw new Error('response lost after commit'); }
      return response(record);
    }
    if (url === '/api/fetch-jobs/claim') {
      const record = [...state.fetch_jobs].reverse().find(item => item.status === 'queued' && item.approval === 'approved');
      if (!record) return response({ job: null });
      record.status = 'fetching';
      return response({ job: { ...record, claim: `claim-${record.id}` } });
    }
    if (url.startsWith('/api/fetch-jobs/')) {
      const [, , , id, actionWithQuery] = url.split('/');
      const action = actionWithQuery.split('?')[0];
      const record = state.fetch_jobs.find(item => item.id === id);
      if (!record) return response({ error: 'No queued download' }, false);
      if (action === 'approve' || action === 'deny') {
        if (record.approval !== 'pending' || record.status !== 'queued') {
          return response({ error: 'Request already decided' }, false);
        }
        record.approval = action === 'approve' ? 'approved' : 'denied';
        if (action === 'deny') { record.status = 'failed'; record.error = 'Denied in the preview'; }
        return response(record);
      }
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
        if (record.approval !== 'approved') return response({ error: 'Only approved downloads can be retried' }, false);
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
    if (url.startsWith('/api/messages/') && url.endsWith('/replies/seen')) {
      const id = decodeURIComponent(url.split('/')[3]);
      const count = JSON.parse(options.body).count;
      const item = [...(state.notes || []), ...(state.submissions || [])].find(record => record.id === id);
      if (!item) return response({ error: 'Message not found' }, false);
      item.ack_edited_seen_count = Math.max(Number(item.ack_edited_seen_count || 0), count);
      replySeenCalls.push({ url, count });
      return response({ id, ack_edited_seen_count: item.ack_edited_seen_count });
    }
    if (url.startsWith('/api/reports/') && url.endsWith('/seen')) {
      readStamps.push(url);
      return response({ id: url.split('/')[3], seen_at: new Date().toISOString() });
    }
    if (url.startsWith('/api/reports/') && url.endsWith('/unpublish')) {
      const target = decodeURIComponent(url.split('/')[3]);
      unpublished.push(target);
      writeTokens.push(options.headers['X-Preview-Token']);
      state.reports = state.reports.filter(report => report.id !== target);
      return response({ unpublished: target });
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

test('preview client', async (t) => {
  let copyIcon;
  let normalTimeout;
  let finishCopy;
  let body;
  let log;
  let upcomingBody;
  let finishedBody;
  let detailList;
  let currentBody;
  let taskControl;
  let taskDraft;
  let taskCopied;
  let opened;
  let cacheKeyHere;
  let copiedText;
  let lines;
  let cachedHere;
  let projectHere;
  let noteKeysHere;
  let taskKeysHere;
  let taskLines;
  let release;
  let sending;
  let agentReceipt;
  let beforeGrow;
  let stamp;
  let answer;
  let copyButton;
  let fallback;
  let denied;
  let idCode;
  let textInput;
  let text;
  let uiBox;
  let apiBox;
  let boxes;
  let picks;
  let shipBox;
  let otherBox;
  let otherOption;
  let otherText;
  let choices;
  let verdict;
  let beforeDelayedUpdate;
  let releaseHtml;
  let beforeDirtyRefresh;
  let oldRevision;
  let releaseSubmission;
  let beforeSendingUpdate;
  let sendingReport;
  let pip;
  let agentAck;
  let panel;
  let wait;
  let logStamp;
  let messageRow;
  let visibleRows;
  let logView;
  let jump;
  let priorState;
  let stateCopyButton;
  let cacheKey;
  let sendNote;
  let sendsBefore;
  let fetchesBefore;
  let filteredNotes;
  let longReceipt;
  let longId;
  let noteBox;
  let copiedBefore;
  let firstId;
  let selectBefore;
  let picker;
  let chips;
  let tooMany;
  let first;
  let second;
  let thirdFile;
  let dragging;
  let dropping;
  let badDrop;
  let notesBeforeFile;
  let uploadsBeforeFile;
  let sendsBeforeFile;
  let attached;
  let receipt;
  let waitFor;
  let approvalButton;
  let requested;
  let deniedURL;
  let fetchedBeforeDeny;
  let direct;
  let blocked;
  let retryRow;
  let origin;
  let allOrigins;
  let third;
  let allOriginsThird;
  let codeTabs;
  let tooLarge;
  let callsBeforeLimit;
  let resultsBeforeLimit;
  let streamed;
  let streamBehavior;
  let lost;
  let beforeLost;
  let editedNode;
  let renders;
  let replacements;
  let copiesBeforeNotesOnly;

  await t.test("load the client", async () => {
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/app.js'), 'utf8'), context);
    await tick();
  });

  await t.test("The page supplies the glyph, so the client starts with none; the copy sets it and restores", async () => {
    // The page supplies the glyph, so the client starts with none; the copy sets it and restores it.
    copyIcon = get('#copy-state');
    normalTimeout = context.setTimeout;
    finishCopy = undefined;
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
    body = context.document.body;
    log = get('#history');
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
  });

  await t.test("An empty field keeps the stylesheet's min-height; a placeholder no longer holds the box op", async () => {
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
  });

  await t.test("Switching tabs fires an unawaited refreshState, so flush the queue before a click that", async () => {
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
    upcomingBody = get('#tasks-upcoming-body');
    finishedBody = get('#tasks-finished-body');
  });

  await t.test("The head renders in its own div and stays out of Upcoming; the row shape is asserted on", async () => {
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
  });

  await t.test("The details are a real list, so each carries its own marker rather than being a line in a ", async () => {
    // The details are a real list, so each carries its own marker rather than being a line in a span.
    detailList = upcomingBody.children[0].children[1].children[1];
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
  });

  await t.test("Finished tasks display newest first without changing saved order", async () => {
    const original = state.tasks.finished.slice();
    state.tasks.finished.push({ id: 'latest', title: 'Latest finished', details: [], status: 'finished', order: 2 });
    await get('#refresh-notes').events.click();
    assert.deepEqual(get('#tasks-finished-body').children.map(row => row.title), ['latest', 'shipped']);
    assert.deepEqual(state.tasks.finished.map(task => task.id), ['shipped', 'latest']);
    state.tasks.finished = original;
    await get('#refresh-notes').events.click();
  });

  await t.test("A hostile title is text in the current row, because a row is built with textContent", async () => {
    // A hostile title is text in the current row, because a row is built with textContent
    // rather than innerHTML. The head renders in a div of its own and stays out of Upcoming.
    currentBody = get('#tasks-current-body');
    assert.equal(get('#tasks-current').hidden, false);
    assert.equal(currentBody.children.length, 1);
    assert.equal(currentBody.children[0].children[0].textContent, '<img onerror=alert(1)> dir');
    assert.equal(currentBody.children[0].children[0].className, 'task-title');
    assert.equal(currentBody.children[0].title, 'docs-archive');
    taskControl = currentBody.children[0].children[0];
    assert.equal(taskControl.dataset.taskId, 'docs-archive');
    assert.equal(taskControl.attributes.role, 'button');
    assert.equal(taskControl.tabIndex, 0, 'keyboard users can reach the task ID');
    documentEvents.click(event({ target: taskControl }));
    await tick();
    assert.equal(copied.at(-1), 'docs-archive', 'click copies the full task ID');
    assert.equal(taskControl.dataset.copied, 'good');
    taskDraft = get('#note').value;
    taskCopied = copied.length;
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
  });

  await t.test("An unchanged poll must not rebuild the rows, or an opened details snaps shut three seconds", async () => {
    // An unchanged poll must not rebuild the rows, or an opened details snaps shut three seconds later.
    opened = upcomingBody.children[0].children[1];
    opened.open = true;
    await get('#refresh-notes').events.click();
    assert.equal(upcomingBody.children[0].children[1], opened, 'the row survives an unchanged poll');
    assert.equal(upcomingBody.children[0].children[1].open, true);
  });

  await t.test("The log and the tasks lost their own copy buttons", async () => {
    // The log and the tasks lost their own copy buttons. One copy button carries the note, task and
    // live-answer lines a restore reads back, as NDJSON, and the reports tab keeps its button.
    // Nothing derived rides the copy: no rendered html, token, seq, uploads or last check, and the
    // stamps arrive from the poll already cut to seconds, which is all a restore needs.
    cacheKeyHere = [...storage.keys()].find(key => key.endsWith(':state-cache'));
    assert.ok(cacheKeyHere, 'every poll caches the state the copy button copies');
    state.reports = [{ id: 'r1', title: 'Fielded', updated_at: new Date().toISOString() }];
    state.submissions = [{ id: 'ans-1', report_id: 'r1', text: 'REPORT r1: one', at: '2026-09-22T10:00:00',
      acknowledged_at: null, ack_kind: null, ack_text: null, ack_edited_at: null, replies: null, ack_edited_seen_count: 0, seen_at: null, task_id: null }];
    copied.length = 0;
    get('#copy-state').events.click();
    await tick();
    copiedText = copied.at(-1);
    assert.ok(copiedText.endsWith('\n') && !copiedText.endsWith('\n\n'),
      'the state copies as NDJSON with one trailing newline');
    lines = copiedText.slice(0, -1).split('\n').map(line => JSON.parse(line));
    cachedHere = JSON.parse(storage.get(cacheKeyHere));
    projectHere = (record, keys) => {
      const line = {};
      for (const key of keys) line[key] = record[key] ?? null;
      return line;
    };
    noteKeysHere = ['id', 'text', 'at', 'acknowledged_at', 'ack_kind', 'ack_text', 'ack_edited_at', 'replies', 'ack_edited_seen_count', 'seen_at', 'task_id'];
    taskKeysHere = ['id', 'title', 'details', 'status', 'order'];
    assert.deepEqual(lines, [
      ...cachedHere.notes.map(note => projectHere(note, noteKeysHere)),
      ...(cachedHere.tasks.upcoming || []).map(task => projectHere(task, taskKeysHere)),
      ...(cachedHere.tasks.finished || []).map(task => projectHere(task, taskKeysHere)),
      ...state.submissions,
    ], 'the copy carries the note, task and answer lines a restore reads, and nothing derived');
    taskLines = lines.filter(line => 'title' in line);
    answerLines = lines.filter(line => 'report_id' in line);
    assert.equal(answerLines.length, 1, 'the copy carries the live report answers');
    assert.equal(answerLines[0].id, 'ans-1', 'the answer line is the save-file shape from the server');
    assert.equal(taskLines.length,
      (cachedHere.tasks.upcoming || []).length + (cachedHere.tasks.finished || []).length,
      'every cached task rides the copy');
    assert.equal(get('#copy-state').dataset.state, 'good', 'the click reports through the button');
    assert.match(get('#send-status').textContent,
      new RegExp(`Copied ${lines.length - taskLines.length - answerLines.length} messages, ${answerLines.length} answers and ${taskLines.length} tasks as NDJSON\\.`),
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
  });

  await t.test("A cleared field collapses back to the stylesheet's min-height instead of keeping its grown", async () => {
    // A cleared field collapses back to the stylesheet's min-height instead of keeping its grown size.
    assert.equal(get('#note').style.height, '');
    assert.match(get('#send-status').textContent, /Saved/);
    assert.match(get('#send-status').textContent, /· Message sent\./);
    assert.doesNotMatch(get('#send-status').textContent, /awaiting acknowledgement/);
    assert.equal(get('#note').placeholder, 'keep draft');
    await tick();
    get('#note').value = 'sent while typing';
    release = undefined;
    sendHandler = note => new Promise(resolve => { release = () => resolve(response({ ...note, at: new Date().toISOString() })); });
    sending = get('#form').events.submit(event({}));
    get('#note').value = 'new unsent draft';
    release();
    await sending;
    assert.equal(get('#note').value, 'new unsent draft');
    await tick();
    state = { notes: [{ id: 'one', text: '<img onerror=alert(1)>', at: new Date().toISOString(), acknowledged_at: null }], reports: [], last_check: null };
    await get('#refresh-notes').events.click();
    assert.equal(get('#history').children[0].children[0].textContent, '<img onerror=alert(1)>');
    assert.match(get('#history').children[0].children[2].textContent, /^one ·  · [A-Z][a-z]{2} /);
  });

  await t.test("The line reads ID \u00b7 who \u00b7 state \u00b7 time, and the dot after the ID is the ASCII separator th", async () => {
    // The line reads ID · who · state · time, and the dot after the ID is the ASCII separator the
    // owner asked for by name; the state stays a coloured dot.
    assert.equal(part(get('#history').children[0].children[2], 'receipt-sep').textContent, ' · ');
    assert.equal(part(get('#history').children[0].children[2], 'state-dot').dataset.state, 'sent');
  });

  await t.test("A message that became a task says so, so a line that was read is never mistaken for one th", async () => {
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
  });

  await t.test("A message the agent wrote used to say so through an origin tag; that key is gone from the", async () => {
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
    agentReceipt = get('#history').children.at(-1).children[2];
    assert.deepEqual(agentReceipt.children.map(child => child.className).filter(Boolean),
      ['note-id', 'receipt-sep', 'state-dot'],
      'ID, separator, state — no writer tag remains on the receipt');
    assert.equal(get('#history').children.at(-1).children[0].className, 'message-text',
      'rendered message text is named for what it is, not for a report');
  });

  await t.test("The fixture note is this block's own; the tests after it read the log that was there befor", async () => {
    // The fixture note is this block's own; the tests after it read the log that was there before.
    state.notes.pop();
    await get('#refresh-notes').events.click();
    assert.equal(part(get('#history').children[0].children[2], 'state-dot').title, 'Sent');
    assert.equal(part(get('#history').children[0].children[2], 'state-dot').attributes['aria-label'], 'Sent');
    assert.equal(part(get('#history').children[0].children[2], 'state-dot').attributes.role, 'img');
    assert.equal(context.clipPlaceholder('one\ntwo\nthree'), 'one\ntwo\nthree');
    assert.equal(context.clipPlaceholder('one\ntwo\nthree\nfour'), 'one\ntwo\n\u2026');
    assert.equal(context.clipPlaceholder('one\ntwo\nthree\nfour\nfive'), 'one\ntwo\n\u2026');
    beforeGrow = get('#note').value;
    get('#note').value = ''; get('#note').scrollHeight = 300; context.grow();
    assert.equal(get('#note').style.height, '');
    get('#note').value = beforeGrow; get('#note').scrollHeight = 96; context.grow();
    assert.doesNotMatch(get('#history').children[0].children[2].textContent,
      /Awaiting|ACK-ed|Saved|Delivered|Sent|Seen|Said| id /);
    assert.equal(get('#last-check').textContent, 'Not checked yet.');
    stamp = get('#history').children[0].children[2].textContent;
    assert.match(stamp, /[A-Z][a-z]{2} \d{2}, \d{2}:\d{2}/);
    assert.doesNotMatch(stamp, /\d{2}:\d{2}:\d{2}/);
    assert.doesNotMatch(stamp, /\b\d{4}\b/);
    assert.doesNotMatch(stamp, /[AP]M/);
  });

  await t.test("A seconds-only stamp is UTC on the wire; the formatter pins it to UTC so a browser", async () => {
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
    answer = get('#history').children[0].children[1];
    assert.equal(part(get('#history').children[0].children[2], 'state-dot').dataset.state, 'said');
    assert.equal(part(get('#history').children[0].children[2], 'state-dot').title, 'Said');
    assert.equal(typeof documentEvents.click, 'function');
    copyButton = new Element();
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
    fallback = new Element();
    fallback.className = 'copy-code';
    fallback.dataset = { code: 'second' };
    documentEvents.click({ target: fallback });
    await tick();
    assert.equal(fallback.textContent, '✓');
    assert.equal(fallback.title, 'Copied through the selection fallback');
    execCommandResult = false;
    denied = new Element();
    denied.className = 'copy-code';
    denied.dataset = { code: 'third' };
    documentEvents.click({ target: denied });
    await tick();
    assert.equal(denied.textContent, '✗');
    assert.equal(denied.title, 'Clipboard blocked; select the code and copy it');
    assert.equal(denied.dataset.state, 'bad');
    clipboardFails = false;
  });

  await t.test("The header clock is the log's own face with seconds, so the two cannot disagree", async () => {
    // The header clock is the log's own face with seconds, so the two cannot disagree.
    assert.match(get('#clock').textContent, /^[A-Z][a-z]{2} \d{2}( \d{2})?, \d{2}:\d{2}:\d{2}$/);
    assert.ok(get('#clock').title.length > 3);
  });

  await t.test("A receipt ID copies on a click, and a blocked clipboard says so on the ID itself", async () => {
    // A receipt ID copies on a click, and a blocked clipboard says so on the ID itself.
    idCode = get('#history').children[0].children[2].children[0];
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
    textInput = { value: '', className: 'answer-text', scrollHeight: 40, style: {} };
    text = new Element();
    text.dataset = { field: 'name', type: 'text' };
    text.querySelector = selector => selector === 'textarea.answer-text' ? textInput : null;
    text.querySelectorAll = () => [];
    uiBox = { value: 'ui', checked: false, dataset: {} };
    apiBox = { value: 'api', checked: true, dataset: {} };
    boxes = [uiBox, apiBox];
    picks = new Element();
    picks.dataset = { field: 'areas', type: 'checkbox' };
    picks.querySelector = () => null;
    picks.querySelectorAll = selector => (selector === 'input:checked' ? boxes.filter(box => box.checked) : boxes);
    shipBox = { value: 'Ship it', checked: false, dataset: {} };
    otherBox = { value: 'Other: ___', checked: false, dataset: { label: 'Other' } };
    otherOption = { querySelector: selector => (selector === '[data-label="Other"]' ? otherBox : null) };
    otherText = { value: '', dataset: { custom: 'Other' }, className: 'custom-text', scrollHeight: 40, style: {}, parentElement: otherOption };
    choices = [shipBox, otherBox, otherText];
    verdict = new Element();
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
    textInput.value = 'ada lovelace';
    apiBox.checked = true;
    otherText.value = '  make it red  ';
    await get('#report-form').events.submit(event({}));
    assert.deepEqual(sent.at(-1).answers, { name: 'ada lovelace', areas: ['ui', 'api'], verdict: 'Other: make it red' });
    assert.equal(sent.at(-1).revision, reportRevision, 'send the revision that supplied the form');
    assert.match(get('#report-status').textContent, /^Report · /);
    assert.match(get('#report-status').textContent, / · Awaiting ack/);
    assert.match(get('#report-agent-ack').textContent, /Awaiting ack/);
    assert.ok(get('#report-agent-ack').textContent.includes(sent.at(-1).id.slice(0, 7)),
      'show the seven-character ID immediately after sending');
    assert.ok(!get('#report-agent-ack').textContent.includes(sent.at(-1).id),
      'do not show the full submission ID');
    assert.deepEqual(JSON.parse(storage.get('arena-preview-v1:answers:r1')).answers, { name: 'ada lovelace', areas: ['ui', 'api'], verdict: 'Other: make it red' });
    await get('#refresh-report').events.click();
    await tick();
    assert.match(get('#report-status').textContent, /^Report · 3 fields · Submission /);
    assert.match(get('#report-status').textContent, / · Awaiting ack/);
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
    beforeDelayedUpdate = get('#report').renders;
    releaseHtml = undefined;
    reportHtmlWait = new Promise(resolve => { releaseHtml = resolve; });
    state.reports[0].updated_at = '2026-09-22T12:00:00';
    await get('#refresh-notes').events.click(); await tick();
    textInput.value = 'keep this draft';
    get('#report-form').events.input(event({target:textInput}));
    releaseHtml(); await tick();
    reportHtmlWait = null;
    assert.equal(get('#report').renders, beforeDelayedUpdate, 'keep edits made while an automatic refresh was fetching');
    beforeDirtyRefresh = get('#report').renders;
    oldRevision = reportRevision;
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
    releaseSubmission = undefined;
    reportSubmitWait = new Promise(resolve => { releaseSubmission = resolve; });
    beforeSendingUpdate = get('#report').renders;
    sendingReport = get('#report-form').events.submit(event({}));
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
    get('#notes-tab').events.keydown(event({ key: 'End' }));
    assert.equal(get('#downloads-panel').hidden, false);
    assert.equal(get('#downloads-tab').focused, true);
    assert.equal(get('#downloads-tab').attributes['aria-selected'], 'true');
    get('#tasks-tab').events.keydown(event({ key: 'ArrowLeft' }));
    assert.equal(get('#reports-panel').hidden, false);
    assert.equal(get('#reports-tab').focused, true);
    assert.equal(get('#reports-tab').attributes['aria-selected'], 'true');
  });

  await t.test("The tab carries a pip rather than a count: visible while a report carries no read stamp of", async () => {
    // The tab carries a pip rather than a count: visible while a report carries no read stamp of its
    // own. The stamp lives on the report, so a cleared browser cannot make a read report unread.
    pip = get('#report-pip');
    state.reports = [{ id: 'r1', title: 'Fielded', updated_at: new Date().toISOString(),
      seen_at: '2026-09-20T22:00:00' }];
    await tick();
    await get('#refresh-notes').events.click();
    assert.equal(pip.hidden, true, 'a report carrying a read stamp is not unread');
    assert.equal(pip.title, 'No unread reports');
    assert.equal(get('#report-select').children.find(item => item.value === 'r1').textContent,
      '1. Fielded', 'a report already read is not starred in the select');
  });

  await t.test("An unanswered form moves neither marker: the star and the pip report unread, and nothing e", async () => {
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
    agentAck = get('#report-agent-ack');
    state.reports[0].latest_answer_id = 'a123456-aaaaaaaaaaaaaaaaaaaaaaaaa';
    state.reports[0].latest_answer_at = '2026-09-24T10:00:00';
    state.reports[0].latest_answer_acknowledged_at = null;
    await get('#refresh-notes').events.click();
    assert.equal(agentAck.hidden, false, 'show the latest answer while it awaits a receipt');
    assert.match(agentAck.textContent, /Submission a123456/);
    assert.ok(!agentAck.textContent.includes('a123456-'), 'the UI only shows seven ID characters');
    assert.match(agentAck.textContent, /Awaiting ack/);
    state.reports[0].latest_answer_acknowledged_at = '2026-09-24T10:01:00';
    await get('#refresh-notes').events.click();
    assert.match(agentAck.textContent, /Acked Sep /);
    state.reports[0].acknowledgements = [{ id: 'answer-one', ack_text: 'First', ack_html: '<p>First</p>', acknowledged_at: '2026-09-24T10:01:00', replies: [{text: 'Second', at: '2026-09-24T10:02:00'}] }];
    await get('#refresh-notes').events.click();
    assert.equal(get('#report-ack-history').hidden, false);
    assert.equal(get('#report-ack-history').children.length, 2);
    assert.equal(get('#report-ack-history').children[0].innerHTML, '<p>First</p>');
    assert.equal(get('#report-ack-history').children[1].children[0].textContent, 'Second');
    assert.equal(pip.hidden, false, 'acknowledging an answer does not mark the report read');
    state.reports[0].latest_answer_id = 'b765432-bbbbbbbbbbbbbbbbbbbbbbbbb';
    state.reports[0].latest_answer_at = '2026-09-24T10:02:00';
    state.reports[0].latest_answer_acknowledged_at = null;
    await get('#refresh-notes').events.click();
    assert.match(agentAck.textContent, /Submission b765432/);
    assert.ok(!agentAck.textContent.includes('a123456'), 'the old submission ID disappears');
    assert.match(agentAck.textContent, /Awaiting ack/,
      'a previous receipt does not cover a later answer');
    state.reports = [];
    await get('#refresh-notes').events.click();
    assert.equal(agentAck.hidden, true, 'hide receipts when no report is selected');
    assert.equal(pip.hidden, true, 'with no reports there is nothing unread');
  });

  await t.test("An edited report keeps its star but drops the pip", async () => {
    // An edited report keeps its star but drops the pip: ever_seen remembers the open.
    state.reports = [{ id: 'r1', title: 'Fielded', updated_at: new Date().toISOString(),
      seen_at: null, ever_seen: 1 }];
    await get('#refresh-notes').events.click();
    assert.equal(pip.hidden, true, 'an opened report edited later shows no dot');
    assert.equal(get('#report-select').children.find(item => item.value === 'r1').textContent,
      '1. * Fielded', 'the star still marks the changed text');
    state.reports = [{ id: 'r1', title: 'Fielded', updated_at: new Date().toISOString(),
      seen_at: null, ever_seen: 0 }];
    await get('#refresh-notes').events.click();
    assert.equal(pip.hidden, false, 'a report nobody opened shows the dot');
  });

  await t.test("What stamps a report is the browser showing it: one second in view for one that fits the", async () => {
    // What stamps a report is the browser showing it: one second in view for one that fits the
    // panel with nothing to scroll, and the moment its end is reached for one that does not.
    panel = get('#reports-panel');
    wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
    state.reports = [{ id: 'r1', title: 'Fits', updated_at: new Date().toISOString(), seen_at: null }];
    readStamps.length = 0;
    panel.scrollHeight = 400; panel.clientHeight = 400; panel.scrollTop = 0;
    get('#reports-tab').events.click();
    await tick(); await tick();
    assert.equal(readStamps.length, 0, 'a report that fits is not stamped on sight');
    await wait(1200);
    assert.deepEqual(readStamps, ['/api/reports/r1/seen'], 'one second in view stamps it');
  });

  await t.test("A report longer than the panel is not stamped while its end is out of reach, and the panel", async () => {
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
  });

  await t.test("Leaving the tab before the dwell is over stamps nothing, so a flick past a short report do", async () => {
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
  });

  await t.test("Marking a report read folds the stamp into the state instead of re-rendering: the panel ke", async () => {
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
  });

  await t.test("An update to the report being read keeps the panel where the owner left it, and a report t", async () => {
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
  });

  await t.test("The log filter selects over the dots the log already draws, adds no new notion, and leaves", async () => {
    // The log filter selects over the dots the log already draws, adds no new notion, and leaves the
    // copy alone: that is the restore path, and a filtered copy would restore a partial log.
    logStamp = new Date().toISOString();
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
    messageRow = id => get('#history').children.find(node =>
      node.children[2].children[0].textContent === id);
    visibleRows = () => ['n1', 'n2', 'n3'].filter(id => !messageRow(id).hidden);
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
  });

  await t.test("A filter that matches nothing says so and counts what it is holding back", async () => {
    // A filter that matches nothing says so and counts what it is holding back.
    state.notes = [{ id: 'n1', text: 'unread', at: logStamp, acknowledged_at: null }];
    await get('#refresh-notes').events.click();
    await tick();
    get('#log-filter').value = 'said';
    get('#log-filter').events.change();
    assert.equal(messageRow('n1').hidden, true);
    assert.equal(get('#log-empty').hidden, false, 'a filter with no match explains itself');
    assert.match(get('#log-empty').textContent, /Nothing here is Said yet/);
  });

  await t.test("The filter keeps the log's place: at its end, the log returns there when rows come back,", async () => {
    // The filter keeps the log's place: at its end, the log returns there when rows come back,
    // because the browser clamps the scroll while the view is short and never puts it back.
    logView = get('#history');
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
  });

  await t.test("The jump bar is the remedy for a long log: hidden at the end, shown once the log is scroll", async () => {
    // The jump bar is the remedy for a long log: hidden at the end, shown once the log is scrolled
    // away from it, and taking the log back to the newest message when it is used.
    jump = get('#log-newest');
    logView.scrollTop = 900;
    logView.events.scroll();
    assert.equal(jump.hidden, true, 'no bar while the log sits at its end');
    logView.scrollTop = 120;
    logView.events.scroll();
    assert.equal(jump.hidden, false, 'the bar appears once the log is scrolled away from its end');
    jump.events.click();
    assert.equal(logView.scrollTop, 900, 'the bar returns the log to its newest message');
    assert.equal(jump.hidden, true, 'and goes when there is nothing below');
  });

  await t.test("The save button posts the page's cached copy, so a wiped server is refilled from the brows", async () => {
    // The save button posts the page's cached copy, so a wiped server is refilled from the browser,
    // and a page that has never polled says so instead of posting nothing.
    priorState = state;
    state = {
      notes: [{ id: 'saved', text: 'cached here', at: new Date().toISOString(), acknowledged_at: null }],
      reports: [],
      tasks: { finished: [], upcoming: [{ id: 'saved-task', title: 'Cached here', details: [],
        status: 'upcoming', order: 1, updated_at: new Date().toISOString() }] },
      last_check: null
    };
    await get('#refresh-notes').events.click();
    stateCopyButton = get('#copy-state');
    cacheKey = [...storage.keys()].find(item => item.endsWith(':state-cache'));
    assert.ok(cacheKey, 'every successful poll caches the copy the state button copies');
    copied.length = 0;
    stateCopyButton.events.click();
    await tick();
    assert.equal(copied.length, 1, 'the button copies the cache');
    assert.ok(copied[0].split('\n').filter(Boolean).length > 1, 'the copy carries note and task lines');
    assert.match(get('#send-status').textContent, /Copied \d+ messages, \d+ answers and \d+ tasks as NDJSON\./);
    assert.equal(stateCopyButton.dataset.state, 'good');
    storage.delete(cacheKey);
    copied.length = 0;
    stateCopyButton.events.click();
    await tick();
    assert.equal(copied.length, 0, 'nothing is copied without a cache');
    assert.match(get('#send-status').textContent, /Nothing cached to copy yet/);
    assert.equal(stateCopyButton.dataset.state, 'bad');
  });

  await t.test("A page outlives the server that served it", async () => {
    // A page outlives the server that served it. After a sandbox reset the token baked into the page
    // is refused, so the page takes a fresh token, from the poll or from a fresh page, and tries once
    // more instead of waiting for a manual refresh; the owner pressed save state several times after
    // a reset and nothing landed. The save route is gone, so a note send carries the same proof.
    staleToken = true;
    storage.set(cacheKey, JSON.stringify({ notes: state.notes, tasks: state.tasks }));
    sendHandler = async note => response({ ...note, at: new Date().toISOString() });
    sendNote = async text => {
      get('#note').value = text;
      await get('#form').events.submit(event({}));
    };
  });

  await t.test("First net: the poll hands the page the token the restarted server accepts, so the write la", async () => {
    // First net: the poll hands the page the token the restarted server accepts, so the write lands
    // with no page fetch and no refresh, which is what the owner needed.
    servedToken = 'token-two';
    sendsBefore = sent.length;
    fetchesBefore = pageFetches;
    await get('#refresh-notes').events.click();
    await sendNote('after the poll');
    assert.equal(pageFetches, fetchesBefore, 'the poll already refreshed the token');
    assert.equal(sent.length, sendsBefore + 1, 'the send lands on the token from the poll');
    assert.equal(writeTokens.at(-1), 'token-two', 'the send carries the token the new server accepts');
  });

  await t.test("Second net: a write refused before any poll re-reads the page for its token and tries once", async () => {
    // Second net: a write refused before any poll re-reads the page for its token and tries once more.
    servedToken = 'token-three';
    await sendNote('before any poll');
    await tick();
    assert.equal(pageFetches, fetchesBefore + 1, 'a refused write re-reads the page for its token');
    assert.equal(sent.length, sendsBefore + 2, 'the write lands on the retry');
    assert.equal(writeTokens.at(-1), 'token-three', 'the retry carries the token the new server accepts');
    staleToken = false;
  });

  await t.test("Give the page back the token its own page carried, so a later test that writes does not", async () => {
    // Give the page back the token its own page carried, so a later test that writes does not
    // inherit this one's stand-in token; the poll is what hands it over.
    servedToken = '__TOKEN__';
    await get('#refresh-notes').events.click();
  });

  await t.test("The fixture above is this test's own; later tests read the state that was live before it", async () => {
    // The fixture above is this test's own; later tests read the state that was live before it.
    state = priorState;
    await get('#refresh-notes').events.click();
  });

  await t.test("With the filter matching nothing, the state copy still carries every message: the cache is", async () => {
    // With the filter matching nothing, the state copy still carries every message: the cache is the
    // restore path, and a filtered copy would restore a partial log as if it were all of it.
    get('#log-filter').value = 'said';
    get('#log-filter').events.change();
    copied.length = 0;
    get('#copy-state').events.click();
    await tick();
    filteredNotes = copied.at(-1).slice(0, -1).split('\n')
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
    longReceipt = get('#history').children.at(-1).children[2];
    assert.equal(longReceipt.children[0].textContent, 'a66700e');
    assert.equal(longReceipt.children[0].title, 'a66700e4-37f0-4182-b782-33c38a83728d');
    assert.equal(longReceipt.children[0].className, 'note-id');
    assert.doesNotMatch(longReceipt.textContent, /a66700e4-37f0/);
    assert.match(longReceipt.textContent, /^a66700e ·  · [A-Z][a-z]{2} /);
    assert.equal(part(longReceipt, 'state-dot').dataset.state, 'sent');
  });

  await t.test("A plain click copies the seven characters on show; a shift-click copies the whole ID", async () => {
    // A plain click copies the seven characters on show; a shift-click copies the whole ID.
    longId = longReceipt.children[0];
    assert.notEqual(longId.textContent, longId.dataset.full);
    documentEvents.click({ target: longId });
    await tick();
    assert.equal(copied.at(-1), longId.textContent);
    assert.equal(longId.dataset.copied, 'good');
    documentEvents.click({ target: longId, shiftKey: true });
    await tick();
    assert.equal(copied.at(-1), longId.dataset.full);
    assert.match(longId.title, /^Copied through the clipboard API: /);
  });

  await t.test("A ctrl-click quotes instead of copying: the composer takes a `RE: <shortid>` line, the car", async () => {
    // A ctrl-click quotes instead of copying: the composer takes a `RE: <shortid>` line, the caret
    // lands after it, and a hidden composer is opened first. A draft already written is kept below
    // a blank line rather than lost.
    noteBox = get('#note');
    noteBox.value = 'a draft already written';
    noteBox.hidden = true;
    copiedBefore = copied.length;
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
  });

  await t.test("An empty composer gets exactly the line that was asked for, and quoting a second note", async () => {
    // An empty composer gets exactly the line that was asked for, and quoting a second note
    // retargets the prefix rather than stacking two of them.
    noteBox.value = '';
    firstId = get('#history').children[0].children[2].children[0];
    documentEvents.click({ target: firstId, ctrlKey: true });
    assert.equal(noteBox.value, `RE: ${firstId.textContent}\n`);
    noteBox.value = `RE: ${firstId.textContent}\nsomething typed after it`;
    documentEvents.click({ target: longId, ctrlKey: true });
    assert.equal(noteBox.value, `RE: ${longId.textContent}\n\nsomething typed after it`);
  });

  await t.test("Meta is the same gesture on a Mac, and a plain click still copies rather than quotes", async () => {
    // Meta is the same gesture on a Mac, and a plain click still copies rather than quotes.
    noteBox.value = '';
    documentEvents.click({ target: longId, metaKey: true });
    assert.equal(noteBox.value, `RE: ${longId.textContent}\n`);
    noteBox.value = '';
    documentEvents.click({ target: longId });
    await tick();
    assert.equal(copied.at(-1), longId.textContent, 'a plain click still copies');
    assert.equal(noteBox.value, '', 'and does not fill the composer');
  });

  await t.test("The report copies its Markdown source, fetched on the click rather than riding the poll", async () => {
    // The report copies its Markdown source, fetched on the click rather than riding the poll.
    selectBefore = get('#report-select').value;
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
  });

  await t.test("A report delete asks for a second click against the same selection, then leaves the tab", async () => {
    // A report delete asks for a second click against the same selection, then leaves the tab.
    // Later subtests read the state that was live before this one, so both are restored on exit.
    const keptReports = state.reports;
    const keptSelect = get('#report-select').value;
    state.reports = [
      { id: 'keep1', title: 'Keep', updated_at: '2026-09-25T10:00:00', seen_at: '2026-09-25T10:05:00' },
      { id: 'gone1', title: 'Gone', updated_at: '2026-09-25T10:00:00', seen_at: '2026-09-25T10:05:00' }
    ];
    get('#reports-tab').events.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    get('#report-select').value = 'gone1';
    // The Deleted receipt is transient: the poll the handler fires reloads the report and rewrites
    // the line, so this probe records every write the flow makes before the receipt is asserted.
    const statusLines = [];
    const statusNode = get('#report-status');
    const nodeProto = Object.getPrototypeOf(statusNode);
    const textAccessor = Object.getOwnPropertyDescriptor(nodeProto, 'textContent');
    Object.defineProperty(statusNode, 'textContent', {
      set(value) { statusLines.push(value); textAccessor.set.call(this, value); },
      get() { return textAccessor.get.call(this); }
    });
    get('#unpublish-report').events.click();
    await tick();
    assert.deepEqual(unpublished, [], 'the first click only arms');
    assert.equal(get('#unpublish-report').dataset.state, 'bad', 'the armed button reads danger');
    assert.match(get('#report-status').textContent, /Click ✕ again to confirm/);
    get('#report-select').value = 'keep1';
    get('#unpublish-report').events.click();
    await tick();
    assert.deepEqual(unpublished, [], 'a click against another selection re-arms instead of deleting');
    get('#report-select').value = 'gone1';
    get('#unpublish-report').events.click();
    await tick();
    get('#unpublish-report').events.click();
    await tick();
    assert.deepEqual(unpublished, ['gone1']);
    assert.equal(get('#unpublish-report').dataset.state, '');
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(state.reports.some(report => report.id === 'gone1'), false, 'the server dropped the row');
    assert.ok(statusLines.some(line => /^Report gone1 · Deleted · /.test(line)),
      `the delete receipt flashed; flow wrote: ${statusLines.join(' | ')}`);
    delete statusNode.textContent;
    state.reports = keptReports;
    unpublished.length = 0;
    get('#reports-tab').events.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    get('#report-select').value = keptSelect;
  });

  await t.test("Multiple files stage as removable filename chips beside \"Your message\"", async () => {
    // Multiple files stage as removable filename chips beside "Your message". The saved-files list
    // is deliberately gone; the note receipt and backend state still carry every original name.
    picker = get('#upload-file');
    chips = () => get('#staged-files').children.map(chip => chip.children[0].textContent);
    get('#attach-file').events.click();
    assert.equal(picker.clicks, 1, 'the attach button opens the native multi-file picker');
    picker.files = [{ name: 'empty.bin', size: 0, type: '' }];
    picker.events.change();
    assert.equal(get('#send-status').textContent, 'empty.bin is empty.');
    picker.files = [{ name: 'big.bin', size: 50_000_001, type: 'application/octet-stream' }];
    picker.events.change();
    assert.equal(get('#send-status').textContent, 'big.bin is 50,000,001 bytes; the ceiling is 50,000,000.');
    tooMany = Array.from({ length: 6 }, (_, n) => ({ name: `file-${n}.bin`, size: 1, type: '' }));
    picker.files = tooMany;
    picker.events.change();
    assert.equal(get('#send-status').textContent, 'Staged 6 files. Send note to save them together.');
    assert.equal(get('#staged-files').children.length, 6, 'no count cap stages six files');
    assert.equal(uploadCalls.length, 0, 'choosing files does not upload them yet');
    while (get('#staged-files').children.length) {
      get('#staged-files').children[0].children[1].events.click();
    }
    assert.equal(get('#staged-files').hidden, true, 'clearing the six keeps the exact chips below');
    first = { name: 'report card.pdf', size: 12, type: 'application/pdf', lastModified: 7 };
    second = { name: 'photo.png', size: 2, type: 'image/png', lastModified: 8 };
    thirdFile = { name: 'notes.txt', size: 9, type: 'text/plain', lastModified: 9 };
    picker.files = [first, second];
    picker.events.change();
    assert.deepEqual(chips(), ['report card.pdf', 'photo.png']);
    assert.equal(get('#staged-files').hidden, false);
    assert.equal(get('#staged-files').children[0].children[1].getAttribute('aria-label'), 'Remove report card.pdf');
    assert.equal(uploadCalls.length, 0, 'choosing files does not upload them yet');
    dragging = event({ dataTransfer: { types: ['Files'], files: [thirdFile] } });
    get('#compose').events.dragover(dragging);
    assert.equal(dragging.prevented, true);
    assert.equal(get('#compose').dataset.dragging, 'true');
    dropping = event({ dataTransfer: { types: ['Files'], files: [thirdFile] } });
    get('#compose').events.drop(dropping);
    assert.equal(dropping.prevented, true);
    assert.equal(get('#compose').dataset.dragging, undefined);
    assert.deepEqual(chips(), ['report card.pdf', 'photo.png', 'notes.txt']);
  });

  await t.test("Remove the middle file and reselect it: replacement keeps both chip order and its own remo", async () => {
    // Remove the middle file and reselect it: replacement keeps both chip order and its own remove.
    get('#staged-files').children[1].children[1].events.click();
    assert.deepEqual(chips(), ['report card.pdf', 'notes.txt']);
    picker.files = [second];
    picker.events.change();
    assert.deepEqual(chips(), ['report card.pdf', 'notes.txt', 'photo.png']);
    badDrop = event({ dataTransfer: { types: ['Files'], files: [{ name: 'empty-drop.bin', size: 0, type: '' }] } });
    get('#compose').events.drop(badDrop);
    assert.deepEqual(chips(), ['report card.pdf', 'notes.txt', 'photo.png'], 'an invalid drop keeps staged files');
    assert.equal(get('#send-status').textContent, 'empty-drop.bin is empty.');

  });

  await t.test("One multipart call writes the note and all three files", async () => {
    // One multipart call writes the note and all three files. A lost response keeps them in memory;
    // manual retry reuses the same note ID and the backend returns the one saved message.
    notesBeforeFile = state.notes.length;
    uploadsBeforeFile = (state.uploads || []).length;
    sendsBeforeFile = sent.length;
    get('#note').value = 'Please review all attachments';
    loseUploadResponse = true;
    await get('#form').events.submit(event({}));
    assert.equal(uploadCalls.length, 1);
    assert.deepEqual(uploadCalls[0].files, [first, thirdFile, second]);
    assert.equal(uploadCalls[0].text, 'Please review all attachments');
    assert.equal(uploadCalls[0].contentType, undefined, 'the browser supplies the multipart boundary');
    assert.equal(uploadCalls[0].token, '__TOKEN__');
    assert.equal(sent.length, sendsBeforeFile, 'no separate upload notification note is posted');
    assert.equal(get('#staged-files').hidden, false, 'an unconfirmed response keeps every staged file');
    assert.match(get('#send-status').textContent, /^Save not confirmed:/);
    assert.deepEqual(JSON.parse(storage.get('arena-preview-v1:pending')).attachments.map(item => item.name),
      ['report card.pdf', 'notes.txt', 'photo.png']);
    await get('#form').events.submit(event({}));
    await tick();
    await get('#refresh-notes').events.click();
    assert.equal(uploadCalls.length, 2);
    assert.equal(uploadCalls[0].id, uploadCalls[1].id, 'unchanged retries reuse the note ID');
    assert.equal(state.notes.length, notesBeforeFile + 1);
    assert.equal(state.uploads.length, uploadsBeforeFile + 3);
    assert.equal(sent.length, sendsBeforeFile);
    assert.equal(get('#note').value, '');
    assert.equal(get('#staged-files').hidden, true);
    assert.deepEqual(state.uploads.slice(-3).map(item => item.file), [
      `${uploadCalls[0].id}-1.pdf`, `${uploadCalls[0].id}-2.txt`, `${uploadCalls[0].id}-3.png`
    ]);
    attached = get('#history').children.find(item => item.children[2].children[0].dataset.full === uploadCalls[0].id);
    assert.ok(attached);
    receipt = attached.children[2];
    assert.equal(part(receipt, 'receipt-file').textContent, ' · report card.pdf · notes.txt · photo.png');
    assert.ok(receipt.children.indexOf(part(receipt, 'receipt-file')) > receipt.children.indexOf(part(receipt, 'state-dot')),
      'the filenames follow the receipt date and state dot');

  });

  await t.test("One file without text still writes a note and uses the original single-file basename", async () => {
    // One file without text still writes a note and uses the original single-file basename.
    picker.files = [{ name: 'single.bin', size: 1, type: '' }];
    picker.events.change();
    await get('#form').events.submit(event({}));
    assert.equal(uploadCalls.at(-1).text, 'File: single.bin');
    assert.equal(uploadCalls.at(-1).files.length, 1);
    assert.equal(sent.length, sendsBeforeFile);
    assert.equal(get('#staged-files').hidden, true);

  });

  await t.test("Clipboard images stage with epoch filenames, preserve bytes and use the normal send", async () => {
    const paste = get('#compose').events.paste;
    assert.equal(typeof paste, 'function');
    const before = uploadCalls.length;
    const stamp = 1790674492000;
    context.Date = class extends Date { static now() { return stamp; } };
    const image = new File([new Uint8Array([137, 80, 78, 71])], 'image.png', { type: 'image/png' });
    const jpeg = new File(['jpeg bytes'], 'image.jpeg', { type: 'image/jpeg' });
    const pasteEvent = files => event({ clipboardData: { files, getData: () => '' } });
    try {
      get('#note').value = 'Review this image';
      const plain = event({ clipboardData: { files: [], getData: () => 'text' } });
      paste(plain);
      assert.equal(plain.prevented, undefined, 'native text paste is untouched');
      paste(event({ clipboardData: null }));
      paste(pasteEvent([new File(['x'], 'notes.txt', { type: 'text/plain' })]));
      assert.equal(get('#staged-files').hidden, true, 'non-images do not become attachments');
      const images = pasteEvent([image, image, jpeg]);
      paste(images);
      assert.equal(images.prevented, true);
      assert.deepEqual(chips(), [`${stamp}.png`, `${stamp}-2.png`, `${stamp}.jpg`]);
      const mixed = event({ clipboardData: { files: [image], getData: () => 'caption' } });
      paste(mixed);
      assert.equal(mixed.prevented, undefined, 'mixed text still uses native paste');
      assert.deepEqual(chips(), [`${stamp}.png`, `${stamp}-2.png`, `${stamp}.jpg`, `${stamp}-3.png`]);
      assert.equal(get('#note').value, 'Review this image');
      assert.equal(uploadCalls.length, before, 'pasting only stages files');
      get('#send').disabled = true;
      paste(pasteEvent([image]));
      get('#send').disabled = false;
      assert.equal(chips().length, 4, 'sending does not accept more files');
      paste(pasteEvent([new File([], 'empty.png', { type: 'image/png' })]));
      assert.match(get('#send-status').textContent, /is empty/);
      const oversized = new File([new Uint8Array(50_000_001)], 'large.png', { type: 'image/png' });
      paste(pasteEvent([oversized]));
      assert.match(get('#send-status').textContent, /ceiling is 50,000,000/);
      assert.equal(chips().length, 4, 'invalid paste keeps existing attachments');
      await get('#form').events.submit(event({}));
      assert.equal(uploadCalls.length, before + 1);
      const files = uploadCalls.at(-1).files;
      assert.deepEqual(files.map(file => file.name), [`${stamp}.png`, `${stamp}-2.png`, `${stamp}.jpg`, `${stamp}-3.png`]);
      assert.equal(files[0].type, 'image/png');
      assert.equal(files[0].lastModified, stamp);
      assert.deepEqual(new Uint8Array(await files[0].arrayBuffer()), new Uint8Array(await image.arrayBuffer()));
      assert.equal(get('#staged-files').hidden, true);
    } finally { delete context.Date; get('#send').disabled = false; }
  });

  await t.test("The queue records per-job opt-in and a browser worker claims one URL at a time", async () => {
    // The queue records per-job opt-in and a browser worker claims one URL at a time. Remote fetches
    // omit credentials and referrers. None of these mocks assert actual browser CORS behavior.
    waitFor = async predicate => {
      for (let attempt = 0; attempt < 80; attempt++) {
        if (predicate()) return;
        await tick();
      }
      throw new Error('Browser queue did not settle');
    };
    approvalButton = (url, label) => {
      const row = get('#fetch-approvals').children.find(item => item.children[0].textContent === url);
      return row?.children.at(-1).children.find(item => item.textContent === label);
    };
    requested = 'https://files.example.org/review.zip';
    state.fetch_jobs = [{ id: 'agent-1', url: requested, allow_proxy: false, status: 'queued',
      approval: 'pending', source: null, error: null, size: null, file: null, present: false }];
    await tick(); // The preceding file-send completion can still be finishing its state poll.
    await get('#refresh-notes').events.click();
    assert.equal(get('#downloads-pip').hidden, false, 'a pending request lights the Downloads dot');
    assert.equal(get('#downloads-pip').attributes['aria-label'], '1 download awaiting approval');
    assert.equal(get('#fetch-approvals').children.length, 1);
    assert.ok(approvalButton(requested, 'Approve') && approvalButton(requested, 'Deny'));
    assert.equal(get('#fetch-list').children.length, 0, 'pending requests appear in their own section');
    assert.match(get('#fetch-count').textContent, /1 awaiting approval/);
    assert.equal(remoteCalls.length, 0, 'polling must not claim or fetch an unapproved URL');
    get('#downloads-tab').events.click();
    assert.equal(get('#downloads-pip').hidden, false, 'opening Downloads cannot dismiss a pending decision');
    await approvalButton(requested, 'Approve').events.click();
    await waitFor(() => state.fetch_jobs[0].status === 'saved');
    assert.equal(get('#downloads-pip').hidden, true);
    assert.equal(remoteCalls.at(-1).url, requested, 'an approval queues a normal browser fetch');
    assert.equal(get('#fetch-list').children.length, 1);
    deniedURL = 'https://files.example.org/denied.zip';
    state.fetch_jobs.unshift({ id: 'agent-2', url: deniedURL, allow_proxy: true, status: 'queued',
      approval: 'pending', source: null, error: null, size: null, file: null, present: false });
    fetchedBeforeDeny = remoteCalls.length;
    await get('#refresh-notes').events.click();
    assert.equal(get('#downloads-pip').hidden, false);
    await approvalButton(deniedURL, 'Deny').events.click();
    assert.equal(state.fetch_jobs[0].approval, 'denied');
    assert.equal(state.fetch_jobs[0].status, 'failed');
    assert.equal(get('#downloads-pip').hidden, true);
    assert.equal(remoteCalls.length, fetchedBeforeDeny, 'denial never starts the browser worker');
    assert.equal(get('#fetch-approvals').children.length, 0);
    assert.match(get('#fetch-list').children[0].children[1].textContent, /denied/);
    assert.equal(get('#fetch-list').children[0].children.some(item => item.textContent === 'Retry same URL'), false);
    state.fetch_jobs = [];
    await get('#refresh-notes').events.click();
    get('#notes-tab').events.click();
    resultCalls.length = 0;
    remoteCalls.length = 0;

    get('#fetch-url').value = 'http://example.org/unsafe.zip';
    await get('#fetch-form').events.submit(event({}));
    assert.match(get('#fetch-status').textContent, /Only HTTPS/);
    assert.equal(queuedCalls.length, 0);
    get('#fetch-url').value = 'https://user:password@example.org/unsafe.zip';
    await get('#fetch-form').events.submit(event({}));
    assert.equal(queuedCalls.length, 0, 'embedded credentials are rejected before queueing');

    direct = 'https://files.example.org/plugin.zip';
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

    blocked = 'https://files.example.org/cors.zip';
    remoteBehaviors.set(blocked, { error: 'CORS blocked' });
    get('#fetch-url').value = blocked;
    await get('#fetch-form').events.submit(event({}));
    await waitFor(() => state.fetch_jobs[0]?.status === 'failed');
    assert.equal(queuedCalls[1].allow_proxy, false);
    assert.match(state.fetch_jobs[0].error, /CORS blocked.*proxy fallback checked/);
    assert.equal(remoteCalls.filter(item => item.url.startsWith('https://api.allorigins.win/')).length, 0,
      'no proxy is used without opt-in');
    remoteBehaviors.set(blocked, { chunks: [Uint8Array.from([1])] });
    retryRow = get('#fetch-list').children.find(item => item.children[0].textContent === blocked);
    await retryRow.children.at(-1).events.click();
    await waitFor(() => state.fetch_jobs.find(item => item.url === blocked)?.status === 'saved');
    assert.equal(queuedCalls.length, 2, 'retry reuses the same SQLite job');

    origin = 'https://files.example.org/fallback.zip';
    allOrigins = `https://api.allorigins.win/raw?url=${encodeURIComponent(origin)}`;
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

    third = 'https://files.example.org/third.zip';
    allOriginsThird = `https://api.allorigins.win/raw?url=${encodeURIComponent(third)}`;
    codeTabs = `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(third)}`;
    remoteBehaviors.set(third, { error: 'CORS blocked' });
    remoteBehaviors.set(allOriginsThird, { error: 'Proxy offline' });
    remoteBehaviors.set(codeTabs, { chunks: [Uint8Array.from([5])] });
    get('#fetch-url').value = third;
    get('#fetch-proxy').checked = true;
    await get('#fetch-form').events.submit(event({}));
    await waitFor(() => state.fetch_jobs[0]?.status === 'saved');
    assert.equal(resultCalls.at(-1).source, 'codetabs');
    assert.equal(remoteCalls.at(-1).url, codeTabs);

    // Owner-origin responses pass the old declared and streamed size thresholds.
    tooLarge = 'https://files.example.org/too-large.bin';
    remoteBehaviors.set(tooLarge, { declared: 102_400_001, chunks: [Uint8Array.from([1])] });
    get('#fetch-url').value = tooLarge;
    await get('#fetch-form').events.submit(event({}));
    await waitFor(() => state.fetch_jobs[0]?.status === 'saved');
    assert.equal(state.fetch_jobs[0].origin, 'owner');

    streamed = 'https://files.example.org/stream.bin';
    streamBehavior = { chunks: [{ byteLength: 102_400_001 }] };
    remoteBehaviors.set(streamed, streamBehavior);
    get('#fetch-url').value = streamed;
    await get('#fetch-form').events.submit(event({}));
    await waitFor(() => state.fetch_jobs[0]?.status === 'saved');
    assert.notEqual(streamBehavior.cancelled, true);

    // Approved agent and legacy jobs must still enforce both byte checks.
    for (const [suffix, behavior] of [['declared', { declared: 102_400_001 }], ['stream', { chunks: [{ byteLength: 102_400_001 }] }]]) {
      const url = `https://files.example.org/agent-${suffix}.bin`;
      remoteBehaviors.set(url, behavior);
      state.fetch_jobs.unshift({ id: `agent-${suffix}`, url, origin: suffix === 'declared' ? 'agent' : undefined, status: 'queued', approval: 'approved', allow_proxy: true });
      callsBeforeLimit = remoteCalls.length;
      resultsBeforeLimit = resultCalls.length;
      await get('#refresh-notes').events.click();
      await waitFor(() => state.fetch_jobs[0]?.status === 'failed');
      assert.equal(remoteCalls.length, callsBeforeLimit + 1);
      assert.equal(resultCalls.length, resultsBeforeLimit);
      assert.match(state.fetch_jobs[0].error, /102,400,000 bytes/);
      if (suffix === 'stream') assert.equal(behavior.cancelled, true);
    }
    lost = 'https://files.example.org/lost.bin';
    remoteBehaviors.set(lost, { chunks: [Uint8Array.from([1])] });
    beforeLost = queuedCalls.length;
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
    // A re-ack appends a block: the first answer stays, the new one lands under it with its stamp.
    state.notes[0].replies = [{kind: 'reply', text: 'Second answer', at: '2026-09-22T00:03:00', html: '<p>Second answer</p>'}];
    state.notes[0].ack_edited_at = '2026-09-22T00:03:00';
    await get('#refresh-notes').events.click();
    editedNode = get('#history').children[0];
    assert.match(editedNode.children[2].textContent, / · Replied again Sep 22, /);
    const grown = editedNode.children[1];
    assert.equal(grown.children.length, 2, 'the first answer stays and the re-ack adds a block');
    assert.equal(grown.children[0].tagName, 'p');
    assert.equal(grown.children[0].textContent, 'First answer');
    assert.equal(grown.children[1].className, 'reply-block');
    assert.equal(grown.children[1].innerHTML, '<p>Second answer</p>');
    assert.match(grown.children[1].title, /^Replied again Sep 22, /);
    assert.equal(get('#history').children[1].children[2].children[0].dataset.full, 'newer-note', 'edits keep log order');
    assert.equal(get('#notes-pip').hidden, false);
    assert.equal(get('#log-edited').hidden, false);
    get('#log-filter').value = 'sent';
    get('#log-filter').events.change();
    await get('#log-edited').events.click();
    assert.equal(editedNode.children[1].scrolledIntoView, true);
    assert.equal(get('#log-filter').value, 'all');
    assert.equal(get('#notes-pip').hidden, true);
    await get('#refresh-notes').events.click();
    assert.equal(get('#log-edited').hidden, true, 'an unchanged poll does not notify again');
    assert.deepEqual(replySeenCalls, [{url: '/api/messages/edited-old/replies/seen', count: 1}], 'viewed reply count is written to the server');
    state.notes[0].replies.push({kind: 'note', text: 'Third block, same second'});
    state.notes[0].replies[1].at = '2026-09-22T00:03:00';
    await get('#refresh-notes').events.click();
    assert.equal(get('#log-edited').hidden, false, 'same-second replies still notify');
    assert.equal(editedNode.children[1].children.length, 3);
    assert.equal(editedNode.children[1].children[2].children[0].textContent, 'Third block, same second', 'a note ack renders as plain text');
    await get('#log-edited').events.click();
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/app.js'), 'utf8'), {...context});
    await tick();
    assert.deepEqual(replySeenCalls.map(call => call.count), [1, 2], 'same-second replies get distinct viewed counts');
    assert.equal(get('#log-edited').hidden, true, 'the SQLite-backed viewed count survives a reload');
    state.reports = [{id: 'stable', title: 'Stable', updated_at: '2026-09-22T00:00:00', seen_at: '2026-09-22T00:00:01'}];
    await get('#refresh-notes').events.click();
    get('#report-select').value = 'stable';
    get('#reports-tab').events.click();
    await tick(); await tick();
    renders = get('#report').renders;
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
    replacements = get('#report').replacements;
    get('#refresh-report').events.click();
    assert.equal(get('#report').replacements, replacements, 'keep old content until the refresh arrives');
    await tick(); await tick();
    assert.equal(get('#report').renders, renders + 1, 'explicit refresh still renders');
    state.notes = [{id:'notes-only', text:'No tasks yet', at:'2026-09-22T12:00:00'}];
    state.tasks = null;
    await get('#refresh-notes').events.click();
    copiesBeforeNotesOnly = copied.length;
    await get('#copy-state').events.click();
    await tick();
    assert.equal(copied.length, copiesBeforeNotesOnly + 1, 'copy a session before its first task');
    assert.match(copied.at(-1), /"id":"notes-only"/);
    assert.equal(get('#copy-state').dataset.state, 'good');
  });

  await t.test('Acknowledgement IDs link to matching messages, reports, and tasks', async () => {
    state = {
      notes: [
        { id: 'question', text: 'Question', at: '2026-09-22T12:00:00',
          acknowledged_at: '2026-09-22T12:01:00', ack_kind: 'reply', ack_text: 'See references',
          ack_html: '<p>See <code>report-ref</code>, <code>message-ref</code>, <code>task-ref</code>, <code>missing-ref</code>, <code>duplicate-ref</code>.</p><pre><code>task-ref\n</code></pre>' },
        { id: 'message-ref', text: 'Linked message', at: '2026-09-22T12:02:00' }
      ],
      reports: [
        { id: 'report-ref', title: 'Linked report', updated_at: '2026-09-22T12:00:00' },
        { id: 'duplicate-ref', title: 'Duplicate report', updated_at: '2026-09-22T12:00:00' }
      ],
      tasks: {
        upcoming: [
          { id: 'task-ref', title: 'Linked task', details: [], status: 'upcoming', order: 1 },
          { id: 'duplicate-ref', title: 'Duplicate task', details: [], status: 'upcoming', order: 2 }
        ],
        finished: [], updated_at: '2026-09-22T12:00:00'
      },
      fetch_jobs: [], last_check: null
    };
    await get('#refresh-notes').events.click();
    const row = id => get('#history').children.find(item => item.children[2].children[0].dataset.full === id);
    const answer = row('question').children[1];
    for (const [type, id, panel] of [
      ['report', 'report-ref', 'reports-panel'],
      ['note', 'message-ref', 'notes-panel'],
      ['task', 'task-ref', 'tasks-panel']
    ]) {
      assert.match(answer.innerHTML, new RegExp(`<a class="ack-reference" href="#${panel}" data-reference-type="${type}" data-reference-id="${id}"><code>${id}</code></a>`));
    }
    assert.match(answer.innerHTML, /<code>missing-ref<\/code>/, 'unknown IDs stay plain code');
    assert.match(answer.innerHTML, /<code>duplicate-ref<\/code>/, 'ambiguous IDs stay plain code');
    assert.match(answer.innerHTML, /<pre><code>task-ref\n<\/code><\/pre>/, 'code blocks stay unchanged');

    const follow = (type, id) => {
      const target = new Element();
      target.className = 'ack-reference';
      target.dataset = { referenceType: type, referenceId: id };
      let prevented = false;
      documentEvents.click({ target, preventDefault: () => { prevented = true; } });
      assert.equal(prevented, true, `${type} navigation prevents the fragment jump`);
    };
    get('#log-filter').value = 'said';
    get('#log-filter').events.change();
    follow('report', 'report-ref');
    assert.equal(get('#reports-panel').hidden, false);
    assert.equal(get('#report-select').value, 'report-ref');
    await tick(); await tick();

    follow('note', 'message-ref');
    assert.equal(get('#notes-panel').hidden, false);
    assert.equal(get('#log-filter').value, 'all', 'note links clear filters that hide their target');
    assert.equal(row('message-ref').hidden, false);
    assert.equal(row('message-ref').scrolledIntoView, true);

    follow('task', 'task-ref');
    assert.equal(get('#tasks-panel').hidden, false);
    const taskTitle = get('#tasks-current-body').children[0].children[0];
    assert.equal(taskTitle.scrolledIntoView, true);
    assert.equal(taskTitle.focused, true);
  });
});
