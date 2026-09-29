const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const bundles = {
  arena: { "prompt-fill": 1, "open-steering": 1, "hide-composer": 1, "auto-scroll": 1 },
  chatgpt: { "hide-elements": 1, "auto-think": 0 },
};

for (const [domain, features] of Object.entries(bundles)) {
  const source = fs.readFileSync(
    path.join(__dirname, "../userscripts", `${domain}.user.js`), "utf8",
  );
  const keys = Object.keys(features);
  const stored = new Map();
  let refuseWrite = false;

  function load() {
    const menus = new Map();
    const active = { observers: 0, intervals: 0, clicks: 0 };
    let nextId = 1;
    const pill = {
      textContent: "Think",
      click() { active.clicks += 1; },
    };
    const context = {
      console, URL,
      location: { href: `https://${domain === "arena" ? "arena.ai/agent" : "chatgpt.com/"}`, pathname: "/agent" },
      document: {
        documentElement: {},
        querySelector() { return null; },
        querySelectorAll(selector) { return selector.includes("__composer-pill") ? [pill] : []; },
      },
      window: { addEventListener() {} },
      sessionStorage: { getItem() { return null; } },
      MutationObserver: class {
        observe() { active.observers += 1; }
      },
      setInterval(callback, ms) {
        assert.equal(ms, 1000);
        active.intervals += 1;
      },
      setTimeout() { throw new Error("No steering button should schedule a click"); },
      clearTimeout() {},
      GM_getValue(key, fallback) { return stored.has(key) ? stored.get(key) : fallback; },
      GM_setValue(key, value) {
        if (refuseWrite) throw new Error("Storage write failed");
        assert.equal(typeof value, "boolean");
        stored.set(key, value);
      },
      GM_registerMenuCommand(label, callback) {
        const id = nextId++;
        menus.set(id, { label, callback });
        return id;
      },
      GM_unregisterMenuCommand(id) { assert.ok(menus.delete(id)); },
    };
    vm.runInNewContext(source, context, { filename: `${domain}.user.js` });
    return { menus, active };
  }

  const defaults = load();
  assert.equal(defaults.menus.size, keys.length);
  assert.equal(defaults.active.observers, Object.values(features).reduce((a, b) => a + b, 0));
  assert.equal(defaults.active.intervals, domain === "chatgpt" ? 1 : 0);
  assert.equal(defaults.active.clicks, domain === "chatgpt" ? 1 : 0);
  assert.equal(stored.size, 0, "Reading defaults must not overwrite settings");

  for (const key of keys) {
    stored.clear();
    stored.set(key, false);
    const page = load();
    assert.equal(page.active.observers, defaults.active.observers - features[key]);
    assert.equal(page.active.intervals, key === "auto-think" ? 0 : defaults.active.intervals);
    assert.equal(page.active.clicks, key === "auto-think" ? 0 : defaults.active.clicks);
    const menu = [...page.menus.values()].find((item) => item.label.includes(": OFF"));
    assert.ok(menu, `Missing disabled menu for ${key}`);
    const before = { ...page.active };
    menu.callback();
    assert.equal(stored.get(key), true);
    assert.deepEqual(page.active, before, "Menu clicks must not change the active page");
    assert.equal(page.menus.size, keys.length, "Menu updates must not accumulate entries");
    assert.ok([...page.menus.values()].every((item) => item.label.includes(": ON")));
    assert.deepEqual(load().active, defaults.active, "Reload must apply the saved switch");
  }

  stored.clear();
  const page = load();
  const before = { ...page.active };
  for (const menu of [...page.menus.values()]) menu.callback();
  assert.deepEqual([...stored.keys()].sort(), keys.slice().sort());
  assert.ok([...stored.values()].every((value) => value === false));
  assert.deepEqual(page.active, before);
  assert.deepEqual(load().active, { observers: 0, intervals: 0, clicks: 0 });

  const allOff = load();
  refuseWrite = true;
  const labels = [...allOff.menus.values()].map((item) => item.label);
  assert.throws(() => allOff.menus.values().next().value.callback(), /Storage write failed/);
  assert.deepEqual([...allOff.menus.values()].map((item) => item.label), labels);
  assert.ok([...stored.values()].every((value) => value === false));
  console.log(`ok ${domain}: switches, defaults, storage failure, reload, and disabled startup`);
}

{
  const source = fs.readFileSync(path.join(__dirname, '../userscripts/arena.user.js'), 'utf8');
  const events = new Map();
  const frames = new Map();
  const observers = [];
  let serial = 0;
  const scroller = {
    scrollTop: 600, scrollHeight: 1000, clientHeight: 400, isConnected: true,
    addEventListener(name, fn) { events.set(name, fn); },
    removeEventListener(name) { events.delete(name); },
  };
  const content = { parentElement: scroller };
  let message = { parentElement: content, closest() { return scroller; } };
  const context = {
    console, URL,
    location: { pathname: '/agent/one', href: 'https://arena.ai/agent/one' },
    document: { documentElement: {}, querySelector() { return message; } },
    window: { addEventListener(name, fn) { events.set(name, fn); } },
    getComputedStyle() { return { overflowY: 'auto' }; },
    MutationObserver: class { constructor(fn) { observers.push(fn); } observe() {} },
    ResizeObserver: class { constructor(fn) { observers.push(fn); } observe() {} unobserve() {} disconnect() {} },
    requestAnimationFrame(fn) { frames.set(++serial, fn); return serial; },
    cancelAnimationFrame(id) { frames.delete(id); },
    GM_getValue(key) { return key === 'auto-scroll'; },
    GM_registerMenuCommand() {}, GM_unregisterMenuCommand() {}, GM_setValue() {},
  };
  const flush = () => { for (const [id, fn] of [...frames]) { frames.delete(id); fn(); } };
  vm.runInNewContext(source, context);
  flush();
  scroller.scrollHeight = 1600;
  observers[0](); flush();
  assert.equal(scroller.scrollTop, 1200, 'New content follows while pinned');
  scroller.scrollTop = 1100;
  events.get('scroll')();
  scroller.scrollHeight = 2000;
  observers[0](); flush();
  assert.equal(scroller.scrollTop, 1100, 'Upward scroll pauses follow');
  scroller.scrollTop = 1550;
  events.get('scroll')();
  scroller.scrollHeight = 2200;
  observers[1](); flush();
  assert.equal(scroller.scrollTop, 1800, 'Near-bottom scroll resumes resize follow');
  scroller.scrollHeight = 2500;
  observers[0]();
  context.location.pathname = '/agent/two';
  scroller.scrollTop = 20;
  observers[0](); flush();
  assert.equal(scroller.scrollTop, 20, 'Navigation preserves a restored reading position');
  message = null;
  observers[0](); flush();
  assert.equal(events.has('scroll'), false, 'Removed transcript releases its listener');
  console.log('ok auto-scroll: growth, resize, pause, resume, navigation, cleanup');
}
