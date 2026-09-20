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
get('#reports-panel').hidden = true;
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
  assert.equal(get('#note').style.height, '74px');
  assert.match(get('#send-status').textContent, /Saved/);
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
  assert.match(get('#history').children[0].children[2].textContent, /^one · Sent /);
  assert.doesNotMatch(get('#history').children[0].children[2].textContent,
    /Awaiting|ACK-ed|Saved|Delivered| id /);
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
  assert.match(get('#history').children[0].children[2].textContent, /^one · Seen /);
  state.notes[0].html = '<p>&lt;img onerror=alert(1)&gt;</p>';
  state.notes[0].acknowledged_at = new Date().toISOString();
  state.last_check = new Date().toISOString();
  await get('#refresh-notes').events.click();
  assert.match(get('#history').children[0].children[2].textContent, /^one · Said /);
  assert.match(get('#last-check').textContent, /^Last checked [A-Z][a-z]{2} \d{2}, \d{2}:\d{2}$/);
  assert.equal(get('#history').children[0].children[0].innerHTML, '<p>&lt;img onerror=alert(1)&gt;</p>');
  state.notes[0].ack_kind = 'reply';
  state.notes[0].ack_text = '**done**';
  state.notes[0].ack_html = '<p><strong>done</strong></p>';
  await get('#refresh-notes').events.click();
  const answer = get('#history').children[0].children[1];
  assert.match(get('#history').children[0].children[2].textContent, /^one · Said /);
  assert.equal(typeof documentEvents.click, 'function');
  const copyButton = new Element();
  copyButton.className = 'copy-code';
  copyButton.dataset = { code: 'print(1)' };
  documentEvents.click({ target: copyButton });
  await tick();
  assert.deepEqual(copied, ['print(1)']);
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
  assert.equal(answer.innerHTML, '<p><strong>done</strong></p>');
  assert.match(answer.className, /answer reply report/);
  assert.equal(answer.hidden, false);
  state.notes[0].ack_kind = 'note';
  state.notes[0].ack_text = 'rechecked';
  delete state.notes[0].ack_html;
  await get('#refresh-notes').events.click();
  assert.equal(answer.textContent, 'rechecked');
  assert.match(answer.className, /answer note/);
  assert.match(get('#history').children[0].children[2].textContent, /^one · Said /);
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
  assert.equal(get('#reports-panel').hidden, false);
  assert.equal(get('#reports-tab').focused, true);
  assert.equal(get('#reports-tab').attributes['aria-selected'], 'true');
  assert.equal(get('#report-count').textContent, 1);
  await tick();
  state.notes.push({ id: 'old', text: 'old note', at: '2024-06-15T12:00:00.000Z', acknowledged_at: null });
  await get('#refresh-notes').events.click();
  assert.match(get('#history').children.at(-1).children[2].textContent, /[A-Z][a-z]{2} \d{2} \d{2}, \d{2}:\d{2}/);
  state = { notes: [{ id: 'a66700e4-37f0-4182-b782-33c38a83728d', text: 'long id', at: new Date().toISOString(), acknowledged_at: null }], reports: [], last_check: null };
  await get('#refresh-notes').events.click();
  const longReceipt = get('#history').children.at(-1).children[2];
  assert.equal(longReceipt.children[0].textContent, 'a66700e');
  assert.equal(longReceipt.children[0].title, 'a66700e4-37f0-4182-b782-33c38a83728d');
  assert.doesNotMatch(longReceipt.textContent, /a66700e4-37f0/);
  assert.match(longReceipt.textContent, /^a66700e · Sent /);
  console.log('PASS: default theme, theme persistence, the chevron bar toggle, the pencil composer toggle and the sun/moon theme button with persistence, the MD eye preview toggle, the green and red connection dot, 24-hour timestamps without seconds or a same-year year, two-tab navigation, draft retention, Enter/IME, retries, receipts with visible note IDs, agent replies and notes in the log, chat order with the log pinned to the newest message, the bare last-sent placeholder, report fields, pre-filled saved answers and the sent receipt');
})().catch(error => { console.error(error); process.exitCode = 1; });
