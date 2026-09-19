// Dependency-free behavioral checks with a minimal DOM; not a browser rendering test.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor() {
    this.value = '';
    this.textContent = '';
    this.hidden = false;
    this.disabled = false;
    this.children = [];
    this.attributes = {};
    this.events = {};
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
  get lastElementChild() { return this.children.at(-1); }
  focus() { this.focused = true; }
  requestSubmit() { this.submissions = (this.submissions || 0) + 1; }
}
const elements = new Map();
const get = id => {
  if (!elements.has(id)) elements.set(id, new Element());
  return elements.get(id);
};
get('#notes-tab').setAttribute('aria-controls', 'notes-panel');
get('#reports-tab').setAttribute('aria-controls', 'reports-panel');
get('#reports-panel').hidden = true;
const storage = new Map();
const root = { dataset: {} };
let counter = 0;
let sendHandler;
let state = { notes: [], reports: [], last_check: null };
const sent = [];
const response = (value, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => value, text: async () => JSON.stringify(value) });
const context = {
  document: { querySelector: get, createElement: () => new Element(), documentElement: root },
  localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
  crypto: { randomUUID: () => `note-${++counter}` },
  AbortController,
  setTimeout,
  clearTimeout,
  setInterval: () => {},
  fetch: async (url, options) => {
    if (url === '/api/state') return response(state);
    if (url === '/api/markdown') return { ok: true, text: async () => '<strong>draft</strong>' };
    if (url === '/api/notes') {
      const note = JSON.parse(options.body);
      sent.push(note);
      return sendHandler(note);
    }
    return { ok: true, text: async () => '<h1>Report</h1>' };
  }
};
const tick = () => new Promise(resolve => setImmediate(resolve));
const event = properties => ({ preventDefault() { this.prevented = true; }, ...properties });

(async () => {
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/app.js'), 'utf8'), context);
  await tick();
  assert.equal(root.dataset.theme, 'dark');
  get('#theme').events.click();
  assert.equal(root.dataset.theme, 'light');
  assert.equal(storage.get('arena-preview-v1:theme'), 'light');
  get('#note').value = '**draft**';
  await get('#preview-note').events.click();
  assert.equal(get('#note').hidden, true);
  assert.equal(get('#draft-preview').innerHTML, '<strong>draft</strong>');
  assert.equal(sent.length, 0);
  await get('#preview-note').events.click();
  assert.equal(get('#note').hidden, false);
  assert.equal(get('#note').value, '**draft**');
  get('#note').value = 'keep draft';
  get('#note').events.input();
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
  await get('#form').events.submit(event({}));
  assert.equal(sent[0].id, sent[1].id);
  assert.equal(get('#note').value, '');
  assert.match(get('#send-status').textContent, /Saved/);
  assert.match(get('#note').placeholder, /keep draft/);
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
  assert.match(get('#history').children[0].lastElementChild.textContent, /Awaiting acknowledgement/);
  state.notes[0].html = '<p>&lt;img onerror=alert(1)&gt;</p>';
  state.notes[0].acknowledged_at = new Date().toISOString();
  await get('#refresh-notes').events.click();
  assert.match(get('#history').children[0].lastElementChild.textContent, /Acknowledged/);
  assert.equal(get('#history').children[0].children[0].innerHTML, '<p>&lt;img onerror=alert(1)&gt;</p>');
  assert.equal(get('#note').value, 'new unsent draft');
  console.log('PASS: default theme, theme persistence, tabs, draft retention, Enter/IME, retries and receipt display');
})().catch(error => { console.error(error); process.exitCode = 1; });
