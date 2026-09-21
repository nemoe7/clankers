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
  replaceChildren(...children) { this.children = children; }
  // A browser clamps a scroll container when the content inside it collapses, and replacing the report
  // is the case the owner hit: the harness does the same, so a missing restore shows up as a jump to
  // the top here exactly as it does on screen (owner note 60cdef88).
  set innerHTML(value) {
    this.inner = value;
    const panel = elements.get('#reports-panel');
    if (this.id === 'report' && panel) panel.scrollTop = 0;
  }
  get innerHTML() { return this.inner; }
  querySelectorAll(selector) { return this.fields && selector === '.question[data-field]' ? this.fields : []; }
  get lastElementChild() { return this.children.at(-1); }
  focus() { this.focused = true; }
  select() { this.selected = true; }
  setSelectionRange(start, end) { this.selectionStart = start; this.selectionEnd = end; }
  remove() { this.removed = true; }
  requestSubmit() { this.submissions = (this.submissions || 0) + 1; }
}
const elements = new Map();
const documentEvents = {};
const copied = [];
let clipboardFails = false;
let execCommandResult = true;
const get = id => {
  if (!elements.has(id)) {
    const element = new Element();
    // A stub element knows its own id, so the parts of the browser a stub has to model can key on it:
    // the scroll clamp below fires for `#report` and nothing else (owner note 60cdef88).
    if (id.startsWith('#')) element.id = id.slice(1);
    elements.set(id, element);
  }
  return elements.get(id);
};
get('#notes-tab').setAttribute('aria-controls', 'notes-panel');
get('#reports-tab').setAttribute('aria-controls', 'reports-panel');
get('#tasks-tab').setAttribute('aria-controls', 'tasks-panel');
get('#uploads-tab').setAttribute('aria-controls', 'uploads-panel');
get('#reports-panel').hidden = true;
get('#tasks-panel').hidden = true;
get('#uploads-panel').hidden = true;
get('#upload-file').files = [];
get('#note').placeholder = 'What should happen next?';
const storage = new Map();
const root = { dataset: {} };
let counter = 0;
let sendHandler;
let state = { notes: [], reports: [], last_check: null };
let stateFails = false;
let reportFields = 0;
const sent = [];
const readStamps = [];
const saveCalls = [];
const uploadCalls = [];
let uploadFails = false;
let staleToken = false;
let servedToken = 'token-one';
let pageFetches = 0;
const writeTokens = [];
const response = (value, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => value, text: async () => JSON.stringify(value) });
const context = {
  document: { querySelector: get, createElement: tag => Object.assign(new Element(), { tagName: tag }), createTextNode: () => new Element(), documentElement: root, body: { dataset: {}, append() {} }, addEventListener: (name, callback) => { documentEvents[name] = callback; }, execCommand: () => execCommandResult },
  navigator: { clipboard: { writeText: async value => { if (clipboardFails) throw new Error('denied'); copied.push(value); } } },
  localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
  crypto: { randomUUID: () => `note-${++counter}` },
  AbortController,
  setTimeout,
  clearTimeout,
  setInterval: () => {},
  fetch: async (url, options) => {
    if (url === '/api/state') return stateFails ? response({ error: 'server gone' }, false) : response({ ...state, token: servedToken });
    if (url === '/api/markdown') return { ok: true, text: async () => '<strong>draft</strong>' };
    if (url === '/api/notes') {
      const note = JSON.parse(options.body);
      sent.push(note);
      return sendHandler(note);
    }
    if (url.startsWith('/api/reports/') && url.endsWith('/submit')) {
      const submission = JSON.parse(options.body);
      sent.push(submission);
      return response({ ...submission, at: new Date().toISOString() });
    }
    if (url.startsWith('/api/uploads')) {
      // The client sends the file itself, so the body is the bytes and the name rides the query string.
      uploadCalls.push({ url, body: options.body, type: options.headers['Content-Type'], token: options.headers['X-Preview-Token'] });
      if (uploadFails) return response({ error: 'An upload must be 1,000,000 bytes or fewer' }, false);
      const name = decodeURIComponent((url.split('?name=')[1] || 'file'));
      const record = {
        id: `upload-${uploadCalls.length}`, name, type: options.headers['Content-Type'],
        size: options.body.size, sha256: String(uploadCalls.length).repeat(64),
        file: `upload-${uploadCalls.length}${name.includes('.') ? name.slice(name.lastIndexOf('.')) : ''}`,
        at: '2026-09-21T00:00:00+00:00', present: true
      };
      state.uploads = [...(state.uploads || []), record];
      return response(record);
    }
    if (url === '/') {
      // A fresh page carries the token the restarted server accepts, so the retry has one to take.
      // The token rides an HTML attribute, the way the served page carries it; a reader that looked
      // for it inside the script text found nothing once the script shipped minified, which is why
      // the owner's save presses after a reset never landed (note 2647459f).
      pageFetches += 1;
      return { ok: true, status: 200, text: async () => `<body data-token="${servedToken}">` };
    }
    if (url === '/api/save-state') {
      writeTokens.push(options.headers['X-Preview-Token']);
      if (staleToken && options.headers['X-Preview-Token'] !== servedToken) {
        return { ok: false, status: 403, text: async () => JSON.stringify({ error: 'Bad or missing token' }) };
      }
      saveCalls.push(JSON.parse(options.body));
      return response({ path: 'saved-state.ndjson', notes: 2, answers: 1, tasks: 1 });
    }
    if (url.startsWith('/api/reports/') && url.endsWith('/seen')) {
      readStamps.push(url);
      return response({ id: url.split('/')[3], seen_at: new Date().toISOString() });
    }
    if (url.endsWith('/source')) return { ok: true, text: async () => '# Report source\n' };
    return response({ html: '<h1>Report</h1>', fields: reportFields });
  }
};
const tick = () => new Promise(resolve => setImmediate(resolve));
// Receipts are built from named parts, so a test reads the part it means instead of counting.
const part = (node, cls) => node.children.find(child => (child.className || '') === cls);
const event = properties => ({ preventDefault() { this.prevented = true; }, ...properties });

(async () => {
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/app.js'), 'utf8'), context);
  await tick();
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
  assert.equal(get('#uploads-panel').hidden, false);
  assert.equal(get('#tasks-panel').hidden, true);
  get('#uploads-tab').events.keydown(event({ key: 'ArrowRight' }));
  assert.equal(get('#notes-panel').hidden, false);
  get('#notes-tab').events.keydown(event({ key: 'End' }));
  assert.equal(get('#uploads-panel').hidden, false);
  get('#tasks-tab').events.keydown(event({ key: 'Home' }));
  assert.equal(get('#notes-panel').hidden, false);
  // Switching tabs fires an unawaited refreshState, so flush the queue before a click that
  // has to land: stateBusy swallows a refresh while another is still in flight.
  await new Promise(resolve => setTimeout(resolve, 0));
  state.tasks = {
    finished: [{ id: 'shipped', title: 'Dots in the receipt', details: [], status: 'finished',
      order: 1, updated_at: new Date().toISOString() }],
    upcoming: [{ id: 'docs-archive', title: '<img onerror=alert(1)> dir',
      details: ['move BUDGET-EXCEPTIONS.md', 'write arena-quirks.md'], status: 'upcoming',
      order: 1, updated_at: new Date().toISOString() }],
    updated_at: new Date().toISOString()
  };
  await get('#refresh-notes').events.click();
  const upcomingBody = get('#tasks-upcoming-body');
  const finishedBody = get('#tasks-finished-body');
  assert.equal(upcomingBody.children.length, 1);
  assert.equal(upcomingBody.children[0].tagName, 'li');
  // A hostile title is text, because a row is built with textContent rather than innerHTML.
  assert.equal(upcomingBody.children[0].children[0].textContent, '<img onerror=alert(1)> dir');
  assert.equal(upcomingBody.children[0].children[0].className, 'task-title');
  assert.equal(upcomingBody.children[0].children[1].tagName, 'details');
  assert.equal(upcomingBody.children[0].children[1].children.length, 2, 'a summary and one list');
  assert.equal(upcomingBody.children[0].children[1].children[0].tagName, 'summary');
  assert.equal(upcomingBody.children[0].children[1].children[0].textContent, '2 details');
  // The details are a real list, so each carries its own marker rather than being a line in a span.
  const detailList = upcomingBody.children[0].children[1].children[1];
  assert.equal(detailList.tagName, 'ul');
  assert.equal(detailList.className, 'task-detail-list');
  assert.equal(detailList.children.length, 2);
  assert.equal(detailList.children[0].tagName, 'li');
  assert.equal(detailList.children[0].className, 'task-detail');
  assert.equal(detailList.children[0].textContent, 'move BUDGET-EXCEPTIONS.md');
  assert.equal(detailList.children[1].textContent, 'write arena-quirks.md');
  assert.equal(upcomingBody.children[0].title, 'move BUDGET-EXCEPTIONS.md\nwrite arena-quirks.md');
  assert.equal(finishedBody.children.length, 1);
  assert.equal(finishedBody.children[0].children.length, 1);
  assert.equal(finishedBody.children[0].children[0].textContent, 'Dots in the receipt');
  assert.equal(get('#tasks-finished').hidden, false);
  assert.equal(get('#tasks-upcoming').hidden, false);
  // The head of the queue is duplicated into a div of its own and stays in Upcoming as well.
  const currentBody = get('#tasks-current-body');
  assert.equal(get('#tasks-current').hidden, false);
  assert.equal(currentBody.children.length, 1);
  assert.equal(currentBody.children[0].children[0].textContent, '<img onerror=alert(1)> dir');
  assert.equal(currentBody.children[0].children[0].className, 'task-title');
  assert.equal(currentBody.children[0].title, 'move BUDGET-EXCEPTIONS.md\nwrite arena-quirks.md');
  assert.equal(upcomingBody.children.length, 1, 'the head is not removed from Upcoming');
  assert.match(get('#tasks-status').textContent, /^Updated .* written by the agent; it takes no answers\.$/);
  // An unchanged poll must not rebuild the rows, or an opened details snaps shut three seconds later.
  const opened = upcomingBody.children[0].children[1];
  opened.open = true;
  await get('#refresh-notes').events.click();
  assert.equal(upcomingBody.children[0].children[1], opened, 'the row survives an unchanged poll');
  assert.equal(upcomingBody.children[0].children[1].open, true);
  // The log and the tasks lost their own copy buttons on owner note 586d52f7. The save button
  // copies the state it posts, as JSON, on a shift-click, and the reports tab keeps its button.
  const cacheKeyHere = [...storage.keys()].find(key => key.endsWith(':state-cache'));
  assert.ok(cacheKeyHere, 'every poll caches the state the shift-click copies');
  copied.length = 0;
  get('#save-state').events.click({ shiftKey: true });
  await tick();
  const copy = JSON.parse(copied.at(-1));
  assert.equal(copied.at(-1), `${JSON.stringify(copy)}\n`, 'the state copies as minified JSON');
  assert.deepEqual(copy, JSON.parse(storage.get(cacheKeyHere)),
    'the copy is the state the button posts, so a wipe costs one paste');
  assert.equal(copy.notes.length, 0);
  assert.equal(copy.tasks.finished.length, state.tasks.finished.length);
  assert.equal(get('#save-state').dataset.state, 'good', 'the shift-click reports through the button');
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
  get('#save-state').events.click({ shiftKey: true });
  await tick();
  assert.equal(get('#save-state').title, 'There is no state to copy');

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
  // owner asked for by name (notes 69dcf681 and 7b183104); the state stays a coloured dot.
  assert.equal(part(get('#history').children[0].children[2], 'receipt-sep').textContent, ' · ');
  assert.equal(part(get('#history').children[0].children[2], 'state-dot').dataset.state, 'sent');
  // A message that became a task says so, so a line that was read is never mistaken for one that
  // was dropped (owner note fe00a32d); the task ID rides in the marker's title.
  state.notes[0].task_id = 'dots-in-receipt';
  await get('#refresh-notes').events.click();
  assert.match(get('#history').children[0].children[2].textContent, / · Task added$/);
  assert.equal(part(get('#history').children[0].children[2], 'receipt-task').title, 'Task dots-in-receipt');
  delete state.notes[0].task_id;
  await get('#refresh-notes').events.click();
  assert.equal(part(get('#history').children[0].children[2], 'receipt-task'), undefined,
    'a message with no task carries no marker');
  // A message the agent wrote says so, and the rendered text wrapper is named for what it is rather
  // than borrowing the report class; owner note d6fcfc2a.
  assert.equal(get('#history').children[0].children[0].className, 'raw-message',
    'a message the server sent without rendered HTML keeps the raw class');
  state.notes.push({
    id: 'from-agent',
    text: 'written by the agent',
    html: '<p>written by the agent</p>',
    at: new Date().toISOString(),
    acknowledged_at: null,
    origin: 'agent'
  });
  await get('#refresh-notes').events.click();
  const agentReceipt = get('#history').children.at(-1).children[2];
  assert.deepEqual(agentReceipt.children.map(child => child.className).filter(Boolean),
    ['note-id', 'receipt-sep', 'who', 'receipt-sep', 'state-dot'],
    'ID, separator, writer, separator, state, so every part reads apart from the next');
  assert.equal(part(agentReceipt, 'who').textContent, 'agent');
  assert.equal(part(agentReceipt, 'who').title, 'Written by the agent, not the owner');
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
  const textInput = { value: '' };
  const text = new Element();
  text.dataset = { field: 'name', type: 'text' };
  text.querySelector = () => textInput;
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
  assert.match(get('#report-status').textContent, /^Answers sent /);
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
  reportFields = 0;
  await get('#refresh-report').events.click();
  await tick();
  assert.equal(get('#report-submit').hidden, true);
  assert.equal(get('#report-receipt').hidden, true);
  get('#notes-tab').events.keydown(event({ key: 'End' }));
  assert.equal(get('#uploads-panel').hidden, false);
  assert.equal(get('#uploads-tab').focused, true);
  assert.equal(get('#uploads-tab').attributes['aria-selected'], 'true');
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
  assert.equal(pip.title, 'No unread report');
  assert.equal(get('#report-select').children.find(item => item.value === 'r1').textContent,
    '1. Fielded', 'a report already read is not starred in the select');
  state.reports = [{ id: 'r1', title: 'Fielded', updated_at: new Date().toISOString(), seen_at: null }];
  await get('#refresh-notes').events.click();
  assert.equal(pip.hidden, false, 'a report with no read stamp is unread');
  assert.equal(pip.title, 'A report has not been read');
  assert.equal(pip.attributes['aria-label'], 'Unread report');
  assert.equal(get('#report-select').children.find(item => item.value === 'r1').textContent,
    '1. * Fielded', 'an unseen report is starred in the select');
  assert.equal([...storage.keys()].filter(item => item.endsWith(':reports-read-at')).length, 0,
    'the tab writes no browser marker now that the stamp lives on the report');
  state.reports = [];
  await get('#refresh-notes').events.click();
  assert.equal(pip.hidden, true, 'with no reports there is nothing unread');
  // What stamps a report is the browser showing it: five seconds in view for one that fits the
  // panel with nothing to scroll, and the moment its end is reached for one that does not.
  const panel = get('#reports-panel');
  const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
  state.reports = [{ id: 'r1', title: 'Fits', updated_at: new Date().toISOString(), seen_at: null }];
  readStamps.length = 0;
  panel.scrollHeight = 400; panel.clientHeight = 400; panel.scrollTop = 0;
  get('#reports-tab').events.click();
  await tick(); await tick();
  assert.equal(readStamps.length, 0, 'a report that fits is not stamped on sight');
  await wait(5200);
  assert.deepEqual(readStamps, ['/api/reports/r1/seen'], 'five seconds in view stamps it');
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
  await wait(5200);
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
  const saveButton = get('#save-state');
  const cacheKey = [...storage.keys()].find(item => item.endsWith(':state-cache'));
  assert.ok(cacheKey, 'every successful poll caches the copy the save button posts');
  saveButton.events.click();
  await tick();
  assert.equal(saveCalls.length, 1, 'the button posts the cache');
  assert.ok(saveCalls[0].notes.length > 0 && saveCalls[0].tasks, 'the cache carries notes and tasks');
  assert.match(get('#send-status').textContent, /Saved 2 messages, 1 report answers and 1 tasks to saved-state.ndjson/);
  assert.equal(saveButton.dataset.state, 'good');
  storage.delete(cacheKey);
  saveButton.events.click();
  await tick();
  assert.equal(saveCalls.length, 1, 'nothing is posted without a cache');
  assert.match(get('#send-status').textContent, /Nothing cached to save yet/);
  assert.equal(saveButton.dataset.state, 'bad');
  // A page outlives the server that served it. After a sandbox reset the token baked into the
  // page is refused, so the page takes a fresh token, from the poll or from a fresh page, and
  // tries once more instead of waiting for a manual refresh; the owner pressed save state several
  // times after a reset and nothing landed (note 2647459f).
  staleToken = true;
  storage.set(cacheKey, JSON.stringify({ notes: state.notes, tasks: state.tasks }));
  // First net: the poll hands the page the token the restarted server accepts, so the save lands
  // with no page fetch and no refresh, which is what the owner needed (note 2647459f).
  servedToken = 'token-two';
  const savesBefore = saveCalls.length;
  const fetchesBefore = pageFetches;
  await get('#refresh-notes').events.click();
  saveButton.events.click();
  await tick();
  assert.equal(pageFetches, fetchesBefore, 'the poll already refreshed the token');
  assert.equal(saveCalls.length, savesBefore + 1, 'the save lands on the token from the poll');
  assert.equal(writeTokens.at(-1), 'token-two', 'the save carries the token the new server accepts');
  // Second net: a write refused before any poll re-reads the page for its token and tries once more.
  servedToken = 'token-three';
  saveButton.events.click();
  await tick();
  await tick();
  assert.equal(pageFetches, fetchesBefore + 1, 'a refused write re-reads the page for its token');
  assert.equal(saveCalls.length, savesBefore + 2, 'the write lands on the retry');
  assert.equal(writeTokens.at(-1), 'token-three', 'the retry carries the token the new server accepts');
  assert.equal(saveButton.dataset.state, 'good');
  assert.match(get('#send-status').textContent, /Saved 2 messages, 1 report answers and 1 tasks to saved-state.ndjson/);
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
  get('#save-state').events.click({ shiftKey: true });
  await tick();
  const filteredCopy = JSON.parse(copied.at(-1));
  assert.ok(filteredCopy.notes.length > 0, 'the fixture holds messages to carry');
  assert.equal(filteredCopy.notes.length, state.notes.length,
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
  // The Uploads tab sends the file itself rather than a JSON envelope, and lists what the server
  // holds, on the owner's answers in report submission c27a4dd5: any bytes, a 1,000,000-byte ceiling,
  // and a record that outlives them.
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
  // A record outlives its bytes, so a row whose file is gone says so rather than opening nothing.
  const gone = get('#uploads-list').children[1];
  assert.equal(gone.children[2].textContent, 'the bytes are gone; the record survived a restore');
  assert.equal(gone.children[2].className, 'upload-gone');
  await get('#upload-send').events.click();
  assert.equal(get('#upload-status').textContent, 'Choose a file first.');
  assert.equal(uploadCalls.length, 0);
  get('#upload-file').files = [{ name: 'empty.bin', size: 0, type: '' }];
  await get('#upload-send').events.click();
  assert.equal(get('#upload-status').textContent, 'That file is empty.');
  assert.equal(uploadCalls.length, 0);
  get('#upload-file').files = [{ name: 'big.bin', size: 1_000_001, type: 'application/octet-stream' }];
  await get('#upload-send').events.click();
  assert.equal(get('#upload-status').textContent, 'That file is 1,000,001 bytes; the ceiling is 1,000,000.');
  assert.equal(uploadCalls.length, 0, 'an oversize file never leaves the page');
  const file = { name: 'report card.pdf', size: 12, type: 'application/pdf' };
  get('#upload-file').files = [file];
  await get('#upload-send').events.click();
  assert.equal(uploadCalls.length, 1);
  assert.equal(uploadCalls[0].url, '/api/uploads?name=report%20card.pdf');
  assert.equal(uploadCalls[0].body, file, 'the body is the bytes themselves');
  assert.equal(uploadCalls[0].type, 'application/pdf');
  assert.equal(uploadCalls[0].token, '__TOKEN__');
  assert.equal(get('#upload-status').textContent, 'Saved report card.pdf · 12 B · 111111111111');
  assert.equal(get('#upload-file').value, '');
  assert.equal(get('#uploads-list').children.length, 3, 'the new record joins the list');
  assert.equal(get('#uploads-list').children[2].children[2].textContent, 'uploads/upload-1.pdf');
  assert.equal(get('#uploads-list').children[2].children[0].textContent, 'report card.pdf');
  // A file the browser has no type for still goes: the server stores any bytes as they arrived.
  uploadFails = true;
  get('#upload-file').files = [{ name: 'blob', size: 9, type: '' }];
  await get('#upload-send').events.click();
  assert.equal(uploadCalls[1].type, 'application/octet-stream');
  assert.equal(get('#upload-status').textContent, 'Upload failed: An upload must be 1,000,000 bytes or fewer');
  uploadFails = false;
  console.log('PASS: default theme, theme persistence, the chevron bar toggle, the pencil composer toggle and the sun/moon theme button with persistence, the MD eye preview toggle, the green and red connection dot, 24-hour timestamps without seconds or a same-year year, four-tab navigation wrapping both ways with Home and End, the uploads tab with its ceiling, its byte-exact POST and a record whose bytes are gone, the tasks tab rendering the head of the queue in its own div, both stored sections and its unwritten state, draft retention, Enter/IME, retries, receipts with visible note IDs, state dots and a click that copies the short ID or the whole one on shift and quotes it into the composer on ctrl, clipped placeholders, the header clock with its date and seconds, the copy button on the reports tab and the state copy on a shift-click of the save button, agent replies and notes in the log, chat order with the log pinned to the newest message, the bare last-sent placeholder, report fields, pre-filled saved answers and the sent receipt, and the log filter over Sent, Seen and Said');
})().catch(error => { console.error(error); process.exitCode = 1; });
