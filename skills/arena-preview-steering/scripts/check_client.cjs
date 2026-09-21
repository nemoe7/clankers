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
  if (!elements.has(id)) elements.set(id, new Element());
  return elements.get(id);
};
get('#notes-tab').setAttribute('aria-controls', 'notes-panel');
get('#reports-tab').setAttribute('aria-controls', 'reports-panel');
get('#tasks-tab').setAttribute('aria-controls', 'tasks-panel');
get('#reports-panel').hidden = true;
get('#tasks-panel').hidden = true;
get('#note').placeholder = 'What should happen next?';
const storage = new Map();
const root = { dataset: {} };
let counter = 0;
let sendHandler;
let state = { notes: [], reports: [], last_check: null };
let stateFails = false;
let reportFields = 0;
const sent = [];
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
    if (url === '/api/state') return stateFails ? response({ error: 'server gone' }, false) : response(state);
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
    if (url.endsWith('/source')) return { ok: true, text: async () => '# Report source\n' };
    return response({ html: '<h1>Report</h1>', fields: reportFields });
  }
};
const tick = () => new Promise(resolve => setImmediate(resolve));
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
  assert.equal(get('#notes-panel').hidden, false);
  get('#notes-tab').events.keydown(event({ key: 'End' }));
  assert.equal(get('#tasks-panel').hidden, false);
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
  // The tasks copy sits here because the fixture's task list only exists inside this block;
  // the log and report buttons are exercised later, once the fixtures hold notes.
  get('#copy-tasks').events.click();
  await tick();
  const records = JSON.parse(copied.at(-1));
  assert.equal(copied.at(-1), `${JSON.stringify(records)}\n`, 'the task copy is minified');
  assert.equal(records.length, state.tasks.finished.length + state.tasks.upcoming.length);
  assert.equal(records[0].id, state.tasks.finished[0].id);
  assert.equal(records.at(-1).id, state.tasks.upcoming.at(-1).id);
  assert.deepEqual(Object.keys(records[0]).sort(),
    ['details', 'id', 'order', 'status', 'title', 'updated_at']);
  state.tasks.upcoming = [];
  await get('#refresh-notes').events.click();
  assert.equal(get('#tasks-current').hidden, true, 'an empty queue has no current task');
  assert.equal(currentBody.children.length, 0);
  assert.equal(get('#tasks-upcoming').hidden, false, 'the section still renders, empty');
  delete state.tasks;
  await get('#refresh-notes').events.click();
  assert.equal(get('#tasks-finished').hidden, true);
  assert.equal(get('#tasks-current').hidden, true, 'no task list, no current div');
  get('#copy-tasks').events.click();
  await tick();
  assert.equal(get('#copy-tasks').title, 'There is no task list to copy');

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
  assert.match(get('#history').children[0].children[2].textContent, /^one · [A-Z][a-z]{2} /);
  assert.equal(get('#history').children[0].children[2].children[1].dataset.state, 'sent');
  assert.equal(get('#history').children[0].children[2].children[1].title, 'Sent');
  assert.equal(get('#history').children[0].children[2].children[1].attributes['aria-label'], 'Sent');
  assert.equal(get('#history').children[0].children[2].children[1].attributes.role, 'img');
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
  assert.equal(get('#history').children[0].children[2].children[1].dataset.state, 'seen');
  assert.equal(get('#history').children[0].children[2].children[1].title, 'Seen');
  state.notes[0].html = '<p>&lt;img onerror=alert(1)&gt;</p>';
  state.notes[0].acknowledged_at = new Date().toISOString();
  state.last_check = new Date().toISOString();
  await get('#refresh-notes').events.click();
  assert.equal(get('#history').children[0].children[2].children[1].dataset.state, 'said');
  assert.equal(get('#history').children[0].children[2].children[1].title, 'Said');
  assert.match(get('#last-check').textContent, /^Last checked [A-Z][a-z]{2} \d{2}, \d{2}:\d{2}$/);
  assert.equal(get('#history').children[0].children[0].innerHTML, '<p>&lt;img onerror=alert(1)&gt;</p>');
  state.notes[0].ack_kind = 'reply';
  state.notes[0].ack_text = '**done**';
  state.notes[0].ack_html = '<p><strong>done</strong></p>';
  await get('#refresh-notes').events.click();
  const answer = get('#history').children[0].children[1];
  assert.equal(get('#history').children[0].children[2].children[1].dataset.state, 'said');
  assert.equal(get('#history').children[0].children[2].children[1].title, 'Said');
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
  assert.match(answer.className, /answer reply report/);
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
  assert.equal(get('#history').children[0].children[2].children[1].dataset.state, 'said');
  assert.equal(get('#history').children[0].children[2].children[1].title, 'Said');
  assert.equal(get('#note').value, 'new unsent draft');
  state.notes.push({ id: 'two', text: 'second', at: new Date().toISOString(), acknowledged_at: null });
  log.scrollHeight = 400; log.clientHeight = 200; log.scrollTop = 200;
  await get('#refresh-notes').events.click();
  assert.deepEqual(log.children.map(item => item.children[2].children[0].textContent), ['one', 'two']);
  assert.deepEqual(log.children.map(item => item.children[2].children[0].tagName), ['code', 'code']);
  assert.deepEqual(log.children.map(item => item.children[2].children[1].tagName), ['span', 'span']);
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
  assert.equal(get('#report-select').children[0].textContent, '1. Fielded');
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
  assert.equal(get('#tasks-panel').hidden, false);
  assert.equal(get('#tasks-tab').focused, true);
  assert.equal(get('#tasks-tab').attributes['aria-selected'], 'true');
  get('#tasks-tab').events.keydown(event({ key: 'ArrowLeft' }));
  assert.equal(get('#reports-panel').hidden, false);
  assert.equal(get('#reports-tab').focused, true);
  assert.equal(get('#reports-tab').attributes['aria-selected'], 'true');
  // The tab carries a pip rather than a count: visible while a report is newer than the last visit,
  // and opening the tab is the visit that clears it. Stamps are set explicitly, because a marker
  // written "now" against a report stamped in the future would never clear and would pass for the
  // wrong reason.
  const pip = get('#report-pip');
  const readKey = [...storage.keys()].find(item => item.endsWith(':reports-read-at'));
  assert.ok(readKey, 'opening the Reports tab records when it was read');
  const atOffset = offset => new Date(Date.now() + offset).toISOString();
  state.reports = [{ id: 'r1', title: 'Fielded', updated_at: atOffset(-60000) }];
  storage.set(readKey, atOffset(0));
  // A tab switch fires an unawaited refreshState, so flush before a click that has to land.
  await tick();
  await get('#refresh-notes').events.click();
  assert.equal(pip.hidden, true, 'a report older than the visit is not unread');
  storage.set(readKey, atOffset(-120000));
  await get('#refresh-notes').events.click();
  assert.equal(pip.hidden, false, 'a report published since the visit is unread');
  assert.equal(pip.title, 'A report has not been read');
  assert.equal(pip.attributes['aria-label'], 'Unread report');
  get('#reports-tab').events.click();
  await tick();
  assert.equal(pip.hidden, true, 'opening the tab clears the pip');
  assert.equal(pip.title, 'No unread report');
  assert.equal(pip.attributes['aria-label'], 'No unread report');
  storage.delete(readKey);
  await get('#refresh-notes').events.click();
  assert.equal(pip.hidden, false, 'a browser that never opened the tab has not read it');
  state.reports = [];
  await get('#refresh-notes').events.click();
  assert.equal(pip.hidden, true, 'with no reports there is nothing unread');
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
  assert.match(longReceipt.textContent, /^a66700e · [A-Z][a-z]{2} /);
  assert.equal(longReceipt.children[1].dataset.state, 'sent');
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
  // The log copies as the JSON lines import-notes reads back, so a wipe costs one paste.
  get('#copy-log').events.click();
  await tick();
  const logLines = copied.at(-1).trim().split('\n').map(line => JSON.parse(line));
  assert.deepEqual(Object.keys(logLines[0]), ['id', 'text', 'at']);
  assert.ok(logLines.length > 0);
  // The copied timestamp stops at the seconds; the fixture's own is a full toISOString(),
  // so a fraction or an offset surviving the copy fails the shape and the sweep below.
  assert.match(logLines[0].at, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/);
  assert.ok(logLines.every(line => !/\.\d|(?:Z|[+-]\d{2}:)/.test(line.at ?? '')),
    'no copied timestamp keeps a fraction or an offset');
  assert.equal(get('#copy-log').dataset.state, 'good');
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
  console.log('PASS: default theme, theme persistence, the chevron bar toggle, the pencil composer toggle and the sun/moon theme button with persistence, the MD eye preview toggle, the green and red connection dot, 24-hour timestamps without seconds or a same-year year, three-tab navigation wrapping both ways with Home and End, the tasks tab rendering the head of the queue in its own div, both stored sections and its unwritten state, draft retention, Enter/IME, retries, receipts with visible note IDs, state dots and a click that copies the short ID or the whole one on shift and quotes it into the composer on ctrl, clipped placeholders, the header clock with its date and seconds, a copy button on each of the three tabs, agent replies and notes in the log, chat order with the log pinned to the newest message, the bare last-sent placeholder, report fields, pre-filled saved answers and the sent receipt');
})().catch(error => { console.error(error); process.exitCode = 1; });
