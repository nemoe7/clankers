const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const bundles = {
  arena: {
    features: { "prompt-fill": 1, "open-steering": 1, "hide-composer": 1, "auto-scroll": 1, "transcript-trim": 1, "tab-title": 1, "state-download": 0 },
    labels: {
      "prompt-fill": "Composer — fill",
      "open-steering": "Steering — open",
      "hide-composer": "Composer — hide",
      "auto-scroll": "Transcript — auto-scroll",
      "transcript-trim": "Transcript — trim",
      "tab-title": "Page — tab title",
      "state-download": "State — download",
    },
    // Every Arena entry leads with its module and carries no role word; a switch ends in (ON)/(OFF).
    moduleSwitch: true,
    offByDefault: ["transcript-trim"],
    // The prompt fill owns the three proxy entries; the state download owns its two.
    extraMenus: { "transcript-trim": 2, "prompt-fill": 3, "state-download": 2 },
    // One entry stands outside the feature switches: the global pause.
    globalMenus: 1,
    countMenu: "Transcript — keep ",
    countKey: "clankers-arena-trim-keep",
    baseObservers: 1,
    // The prompt fill owns two timers: the paint and the key watch. Both ride the one switch.
    featureIntervals: {
      "tab-title": 1,
      "prompt-fill": 2,
      "state-download": 1,
      "transcript-trim": 1,
    },
  },
  chatgpt: {
    features: { "hide-elements": 1, "auto-think": 0 },
    labels: { "hide-elements": "Hide elements", "auto-think": "Auto Think" },
    baseObservers: 0,
    featureIntervals: { "auto-think": 1 },
  },
};

for (const [domain, bundle] of Object.entries(bundles)) {
  const { features, labels, countMenu, countKey, baseObservers, featureIntervals } = bundle;
  const offByDefault = new Set(bundle.offByDefault || []);
  const extraMenus = bundle.extraMenus || {};
  const source = fs.readFileSync(
    path.join(__dirname, "../userscripts", `${domain}.user.js`), "utf8",
  );
  // A granted cross-origin call meets the dynamic preview host and the owner's proxy host.
  // A manager asks the owner once per host without a connect tag, so the tag is required.
  const header = /\/\/ ==UserScript==[\s\S]*?\/\/ ==\/UserScript==/.exec(source)[0];
  if (/^\/\/ @grant\s+GM_xmlhttpRequest\s*$/m.test(header)) {
    assert.match(header, /^\/\/ @connect\s+arena\.site\s*$/m, `${domain}: the connect tag names the preview host only`);
  }

  const keys = Object.keys(features);
  const stored = new Map();
  let refuseWrite = false;
  let promptAnswer = null;

  function isOn(saved, key) {
    return offByDefault.has(key) ? saved.get(key) === true : saved.get(key) !== false;
  }
  const observersFor = (saved) => baseObservers + keys.reduce((total, key) => total + (isOn(saved, key) ? features[key] : 0), 0);
  const intervalsFor = (saved) => keys.reduce((total, key) => total + (isOn(saved, key) ? (featureIntervals[key] || 0) : 0), 0);
  const pauseKey = "clankers-arena-userscript-paused";
  const menusFor = (saved) =>
    (bundle.globalMenus || 0) +
    keys.length +
    keys.reduce((total, key) => total + (isOn(saved, key) ? (extraMenus[key] || 0) : 0), 0);

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
      window: { addEventListener() {}, removeEventListener() {} },
      sessionStorage: { getItem() { return null; } },
      MutationObserver: class {
        observe() { active.observers += 1; }
        disconnect() { active.observers -= 1; }
      },
      setInterval(callback, ms) {
        assert.ok(
          [1000, 5000, 60000, 900000].includes(ms),
          `An interval runs the paint, the trim tick, the key watch or the key rotation, not ${ms} ms`,
        );
        active.intervals += 1;
      },
      clearInterval() { active.intervals -= 1; },
      setTimeout() { throw new Error("No steering button should schedule a click"); },
      clearTimeout() {},
      prompt() { return promptAnswer; },
      GM_getValue(key, fallback) { return stored.has(key) ? stored.get(key) : fallback; },
      GM_setValue(key, value) {
        if (refuseWrite) throw new Error("Storage write failed");
        assert.ok(
          typeof value === "boolean" || Number.isInteger(value) || typeof value === "string",
          "A saved setting is a switch, a count or a plan",
        );
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

  const moduleSwitch = bundle.moduleSwitch === true;
  function menuFor(page, key) {
    return [...page.menus.values()].find((item) =>
      item.label.startsWith(labels[key] + (moduleSwitch ? " (" : ":")));
  }
  // A switch label reads (ON)/(OFF) for the Arena bundle and `: ON — toggle` for ChatGPT.
  const reads = (label, on) => label.includes(moduleSwitch ? (on ? "(ON)" : "(OFF)") : (on ? ": ON" : ": OFF"));
  const switchLike = (label) => moduleSwitch ? / \((ON|OFF)\)$/.test(label) : label.includes("— toggle");

  const defaults = load();
  assert.equal(defaults.menus.size, menusFor(stored));
  if (domain === "arena") {
    // The owner's shape decision: one module's entries share a prefix, a switch names its state
    // in parentheses, and no entry carries a role word.
    // The modules sit in one order, and one module's entries stay together: Composer, Proxy,
    // Steering, Transcript, State, Page, Userscript.
    const expected = [
      "Composer — fill (ON)",
      "Composer — hide (ON)",
      "Proxy — host",
      "Proxy — master key",
      "Proxy — post key now",
      "Steering — open (ON)",
      "Transcript — auto-scroll (ON)",
      "Transcript — trim (OFF)",
      "State — download (ON)",
      "State — choose the file",
      "State — force save",
      "Page — tab title (ON)",
      "Userscript — pause all",
    ];
    assert.deepEqual(
      [...defaults.menus.values()].map((item) => item.label),
      expected,
      "Every entry leads with its module, and one module's entries sit together",
    );
  }
  assert.equal(defaults.active.observers, observersFor(stored));
  assert.equal(defaults.active.intervals, intervalsFor(stored));
  assert.equal(defaults.active.clicks, domain === "chatgpt" ? 1 : 0);
  assert.equal(stored.size, 0, "Reading defaults must not overwrite settings");

  for (const key of keys) {
    const startsOn = isOn(new Map(), key);
    stored.clear();
    stored.set(key, !startsOn);
    const page = load();
    assert.equal(page.active.observers, observersFor(stored));
    assert.equal(page.active.intervals, intervalsFor(stored));
    assert.equal(page.active.clicks, key === "auto-think" ? 0 : defaults.active.clicks);
    const menu = menuFor(page, key);
    assert.ok(menu, `Missing menu for ${key}`);
    assert.ok(reads(menu.label, !startsOn), `The ${key} menu shows the saved switch`);
    menu.callback();
    assert.equal(stored.get(key), startsOn, "A toggle returns the feature to its default");
    assert.equal(page.active.observers, observersFor(stored));
    assert.equal(page.active.intervals, intervalsFor(stored));
    assert.equal(page.menus.size, menusFor(stored));
    assert.deepEqual(page.active, defaults.active, "The default state returns");
    assert.ok(reads(menuFor(page, key).label, startsOn));
    assert.deepEqual(load().active, defaults.active, "Reload must apply the saved switch");
  }

  if (countMenu) {
    stored.clear();
    const counted = load();
    const toggle = menuFor(counted, "transcript-trim");
    assert.ok(toggle, "Missing the transcript trim toggle");
    assert.ok(reads(toggle.label, false), "Transcript trim ships OFF");
    toggle.callback();
    assert.equal(stored.get("transcript-trim"), true);
    // The plan menu is the one that names rows; the switch menu reads ": ON/OFF".
    const findCount = () => [...counted.menus.values()].find((item) => item.label.includes("keep"));
    assert.ok(findCount(), "Missing the transcript trim count menu");
    const findNow = () =>
      [...counted.menus.values()].find((item) => item.label === "Transcript — trim now");
    assert.ok(findNow(), "Missing the trim now button");
    findNow().callback();
    assert.ok(
      findCount().label.includes("50 rows"),
      "The count menu shows the default row limit",
    );
    // The count line belongs to the Transcript group, so it sits with its two switches rather
    // than at the bottom the manager appends it to.
    assert.deepEqual(
      [...counted.menus.values()].map((item) => item.label),
      [
        "Composer — fill (ON)",
        "Composer — hide (ON)",
        "Proxy — host",
        "Proxy — master key",
        "Proxy — post key now",
        "Steering — open (ON)",
        "Transcript — auto-scroll (ON)",
        "Transcript — trim (ON)",
        "Transcript — keep 50 rows",
        "Transcript — trim now",
        "State — download (ON)",
        "State — choose the file",
        "State — force save",
        "Page — tab title (ON)",
        "Userscript — pause all",
      ],
      "The keep-rows line sits in the Transcript group",
    );
    findCount().callback();
    assert.equal(stored.has(countKey), false, "A cancel keeps the plan unset");
    stored.set(countKey, "2,120");
    findCount().callback();
    assert.equal(stored.get(countKey), "120", "A saved legacy plan keeps its row limit");
    assert.ok(findCount().label.includes("120 rows"));
    promptAnswer = "100";
    findCount().callback();
    assert.equal(stored.get(countKey), "100", "One value sets the global row limit");
    assert.ok(findCount().label.includes("100 rows"));
    promptAnswer = "5";
    findCount().callback();
    assert.equal(stored.get(countKey), "100", "Rows below the floor keep the old plan");
    promptAnswer = "0,100";
    findCount().callback();
    assert.equal(stored.get(countKey), "100", "An invalid legacy plan keeps the old plan");
    promptAnswer = "later";
    findCount().callback();
    assert.equal(stored.get(countKey), "100", "A bad plan keeps the old plan");
    promptAnswer = null;
  }

  stored.clear();
  for (const key of keys) stored.set(key, false);
  const allOff = load();
  assert.equal(allOff.active.observers, baseObservers);
  assert.equal(allOff.active.intervals, 0);
  assert.equal(allOff.menus.size, keys.length + (bundle.globalMenus || 0));
  assert.ok(
    [...allOff.menus.values()]
      .filter((item) => switchLike(item.label))
      .every((item) => reads(item.label, false)),
    "Every feature switch reads OFF",
  );
  assert.deepEqual(allOff.active, { observers: baseObservers, intervals: 0, clicks: 0 });

  refuseWrite = true;
  const labelsBefore = [...allOff.menus.values()].map((item) => item.label);
  assert.throws(() => allOff.menus.values().next().value.callback(), /Storage write failed/);
  assert.deepEqual([...allOff.menus.values()].map((item) => item.label), labelsBefore);
  assert.ok([...stored.values()].every((value) => value === false));
  // The global pause stops every feature where it stands, with no reload, and the resume
  // brings back the features whose own switch is ON (form answer 74b99a5).
  if (domain === "arena") {
    // The storage-failure check above leaves the writes refused; the pause writes again.
    refuseWrite = false;
    stored.clear();
    const live = load();
    const pauseMenu = () => [...live.menus.values()].find((item) => item.label.includes("pause all"));
    const resumeMenu = () => [...live.menus.values()].find((item) => item.label.includes("resume all"));
    assert.ok(pauseMenu(), "Missing the pause-all menu entry");
    assert.equal(live.menus.size, menusFor(stored), "The running set carries the global entry beside the switches");
    pauseMenu().callback();
    assert.equal(stored.get(pauseKey), true, "The pause press is stored, so a reload keeps it");
    assert.deepEqual(
      { observers: live.active.observers, intervals: live.active.intervals },
      { observers: 0, intervals: 0 },
      "The pause stops every observer and timer where it stands",
    );
    assert.equal(live.menus.size, keys.length + bundle.globalMenus, "Every feature switch stays usable while paused");
    assert.ok(reads(menuFor(live, "tab-title").label, true), "A paused feature keeps its own switch label");
    assert.ok(resumeMenu(), "The pause entry flips to resume");
    // A switch flipped while paused is stored, and the resume honors it.
    menuFor(live, "tab-title").callback();
    assert.equal(stored.get("tab-title"), false, "A switch flips while paused");
    resumeMenu().callback();
    assert.equal(stored.get(pauseKey), false, "The resume clears the stored pause");
    assert.deepEqual(
      { observers: live.active.observers, intervals: live.active.intervals },
      {
        observers: observersFor(stored),
        intervals: intervalsFor(stored),
      },
      "The resume brings back the features whose own switch is ON",
    );
    assert.ok(pauseMenu(), "The resume entry flips back to pause");
    // A reload while paused starts with nothing running and still offers the resume.
    stored.set(pauseKey, true);
    const reloaded = load();
    assert.equal(reloaded.active.observers, 0, "A reload keeps the pause");
    assert.equal(reloaded.active.intervals, 0, "A paused reload runs no timer");
    assert.ok(
      [...reloaded.menus.values()].some((item) => item.label.includes("resume all")),
      "A paused reload offers the resume",
    );
    // The pause leaves the switches alone: the next unpaused load runs them again.
    stored.set(pauseKey, false);
    const after = load();
    assert.deepEqual(
      { observers: after.active.observers, intervals: after.active.intervals },
      { observers: observersFor(stored), intervals: intervalsFor(stored) },
      "The switches survive the pause",
    );
  }

  console.log(`ok ${domain}: switches, defaults, storage failure, live switches, and disabled startup`);
}
{
  const source = fs.readFileSync(path.join(__dirname, '../userscripts/arena.user.js'), 'utf8');
  const events = new Map();
  const frames = new Map();
  const observers = [];
  const menus = new Map();
  let enabled = true;
  let serial = 0;
  const scroller = {
    scrollTop: 600, scrollHeight: 1000, clientHeight: 400, isConnected: true,
    addEventListener(name, fn) { events.set(name, fn); },
    removeEventListener(name) { events.delete(name); },
  };
  const content = { parentElement: scroller };
  let message = { parentElement: content, closest() { return scroller; } };
  const row = {
    inserted: null,
    querySelector() { return null; },
    insertBefore(node) { this.inserted = node; },
  };
  const stopButton = {
    getAttribute(name) { return name === 'aria-label' ? 'Stop generating' : null; },
    parentElement: row,
  };
  const makeElement = (tag) => ({
    tag, type: '', className: '', attrs: {}, listeners: {}, children: [],
    setAttribute(name, value) { this.attrs[name] = value; },
    appendChild(child) { this.children.push(child); },
    addEventListener(name, fn) { this.listeners[name] = fn; },
  });
  const context = {
    console, URL,
    location: { pathname: '/agent/one', href: 'https://arena.ai/agent/one' },
    document: {
      documentElement: {},
      querySelector() { return message; },
      querySelectorAll(selector) { return selector === 'button[aria-label]' ? [stopButton] : []; },
      createElement: (tag) => makeElement(tag),
      createElementNS: (namespace, tag) => makeElement(tag),
    },
    window: { addEventListener(name, fn) { events.set(name, fn); }, removeEventListener(name) { events.delete(name); } },
    getComputedStyle() { return { overflowY: 'auto' }; },
    MutationObserver: class { constructor(fn) { observers.push(fn); } observe() {} disconnect() {} },
    ResizeObserver: class { constructor(fn) { observers.push(fn); } observe() {} unobserve() {} disconnect() {} },
    requestAnimationFrame(fn) { frames.set(++serial, fn); return serial; },
    cancelAnimationFrame(id) { frames.delete(id); },
    GM_getValue(key) { return key === 'auto-scroll' && enabled; },
    GM_registerMenuCommand(label, fn) { menus.set(label, fn); return label; },
    GM_unregisterMenuCommand(label) { menus.delete(label); },
    GM_setValue(key, value) { enabled = value; },
  };
  const flush = () => { for (const [id, fn] of [...frames]) { frames.delete(id); fn(); } };
  vm.runInNewContext(source, context);
  flush();
  const toggleButton = row.inserted;
  assert.ok(toggleButton, 'Toggle button is injected into the action row');
  assert.equal(toggleButton.attrs['aria-pressed'], 'true', 'Button starts pressed while follow is ON');
  scroller.scrollTop = 100;
  events.get('scroll')(); flush();
  assert.equal(scroller.scrollTop, 600, 'Enabled mode immediately returns to bottom');
  scroller.scrollHeight = 1600;
  observers[0](); flush();
  assert.equal(scroller.scrollTop, 1200, 'New content follows while pinned');
  scroller.scrollTop = 1100;
  events.get('scroll')();
  scroller.scrollHeight = 2000;
  observers[0](); flush();
  assert.equal(scroller.scrollTop, 1600, 'Enabled mode overrides upward scrolling');
  scroller.scrollTop = 1550;
  events.get('scroll')();
  scroller.scrollHeight = 2200;
  observers[1](); flush();
  assert.equal(scroller.scrollTop, 1800, 'Enabled mode follows resize');
  scroller.scrollHeight = 2500;
  observers[0]();
  context.location.pathname = '/agent/two';
  scroller.scrollTop = 20;
  observers[0](); flush();
  assert.equal(scroller.scrollTop, 2100, 'Enabled mode follows on navigation');
  const toggleMenu = () => [...menus].find(([label]) => label.startsWith('Transcript — auto-scroll ('))[1]();
  toggleButton.listeners.click();
  assert.equal(enabled, false, 'Button click turns follow off');
  assert.equal(toggleButton.attrs['aria-pressed'], 'false', 'Button shows unpressed when off');
  assert.ok(toggleButton.className.includes('hover:bg-surface-raised'), 'Off state lifts on hover');
  assert.ok(!toggleButton.className.includes('hover:bg-interactive-cta-active'), 'Off state keeps the plain hover');
  assert.equal(events.has('scroll'), false, 'OFF removes the scroll listener');
  scroller.scrollTop = 50; flush();
  assert.equal(scroller.scrollTop, 50, 'OFF cancels pending follow');
  toggleButton.listeners.click();
  assert.equal(enabled, true, 'Button click turns follow on');
  assert.equal(toggleButton.attrs['aria-pressed'], 'true', 'Button shows pressed when on');
  assert.ok(toggleButton.className.includes('hover:bg-interactive-cta-active'), 'On state has its own hover');
  assert.ok(!toggleButton.className.includes('hover:bg-surface-raised'), 'On state does not share the hover fill');
  flush();
  assert.equal(scroller.scrollTop, 2100, 'ON follows immediately without reload');
  toggleMenu();
  assert.equal(enabled, false, 'Menu toggle turns follow off');
  assert.equal(toggleButton.attrs['aria-pressed'], 'false', 'Menu toggle updates the button');
  toggleMenu();
  assert.equal(enabled, true, 'Menu toggle restores follow');
  assert.equal(toggleButton.attrs['aria-pressed'], 'true', 'Button follows the menu toggle back on');
  const latestSync = observers.at(-2);
  let generating = true;
  context.document.querySelectorAll = (selector) => selector === 'button[aria-label]' && generating ? [stopButton] : [];
  generating = false;
  scroller.scrollTop = 40;
  events.get('scroll')(); flush();
  assert.equal(scroller.scrollTop, 40, 'Idle transcript (no Stop generating) leaves the scroll alone');
  generating = true;
  latestSync(); flush();
  assert.equal(scroller.scrollTop, 2100, 'Stop generating back means follow resumes');
  message = null;
  latestSync(); flush();
  assert.equal(events.has('scroll'), false, 'Removed transcript releases its listener');
  console.log('ok auto-scroll: growth, resize, navigation, toggle button, menu sync, cleanup');
}
{
  const { test } = require("node:test");
  // The security check owns the page while it shows: the fill, the steering click and the
  // proxy posts wait for it, and the tab title keeps its shield.
  test("captcha hold", async () => {
    const source = fs.readFileSync(path.join(__dirname, "../userscripts/arena.user.js"), "utf8");
    let captchaVisible = true;
    let clicked = 0;
    const posts = [];
    const fetches = [];
    const intervals = [];
    // The timeout ids are tracked, so a cleared wait really leaves the queue.
    const timeouts = new Map();
    let nextTimeout = 0;
    const popstates = [];
    const menus = new Map();
    const stored = new Map();
    const page = { title: "" };
    const composer = {
      innerText: "",
      attrs: {},
      focus() {},
      getAttribute(name) { return this.attrs[name] || null; },
    };
    const captcha = {
      getAttribute() { return null; },
      parentElement: null,
      getClientRects() { return [{}]; },
    };
    const bar = {
      textContent: "nemoe7/clankers",
      querySelectorAll(selector) {
        return selector === "span.truncate" ? [{ textContent: "nemoe7/clankers" }] : [];
      },
    };
    const repoLink = {
      getAttribute(name) {
        if (name === "href") return "https://github.com/nemoe7/clankers";
        if (name === "aria-label") return "Open nemoe7/clankers on GitHub";
        return null;
      },
    };
    const previewFrame = {
      src: "https://preview.example",
      getAttribute(name) { return name === "title" ? "App preview on port 8000" : null; },
    };
    const steering = {
      textContent: "clankers - Steering :8000",
      querySelectorAll(selector) {
        return selector === "span"
          ? [{ textContent: "clankers - Steering" }, { textContent: ":8000" }]
          : [];
      },
      click() { clicked += 1; },
    };
    const logged = [];
    const context = {
      console: { log: (...args) => logged.push(args.join(" ")) },
      URL,
      location: { href: "https://arena.ai/agent", pathname: "/agent" },
      document: {
        documentElement: {},
        execCommand(command, show, text) { composer.innerText = text; return true; },
        createRange() { return { selectNodeContents() {} }; },
        querySelector(selector) {
          if (selector === 'div.tiptap.ProseMirror[contenteditable="true"]') return composer;
          if (selector.indexOf("div.relative.z-10") === 0) return bar;
          if (selector.indexOf('a[aria-label^="Open "]') === 0) return repoLink;
          return null;
        },
        querySelectorAll(selector) {
          if (selector === '.recaptcha-v2-container, iframe[title="reCAPTCHA"]') {
            return captchaVisible ? [captcha] : [];
          }
          if (selector === 'button[type="button"]') return [steering];
          if (selector === "iframe[title]") return [previewFrame];
          return [];
        },
        get title() { return page.title; },
        set title(value) { page.title = value; },
      },
      window: {
        addEventListener(name, fn) { if (name === "popstate") popstates.push(fn); },
        removeEventListener() {},
        getSelection() { return { removeAllRanges() {}, addRange() {} }; },
      },
      getComputedStyle() { return { overflowY: "auto" }; },
      MutationObserver: class { observe() {} disconnect() {} },
      ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
      requestAnimationFrame() { return 1; },
      cancelAnimationFrame() {},
      setInterval(fn, ms) { intervals.push({ ms, fn }); return intervals.length; },
      clearInterval() {},
      setTimeout(fn) {
        nextTimeout += 1;
        timeouts.set(nextTimeout, fn);
        return nextTimeout;
      },
      clearTimeout(id) { timeouts.delete(id); },
      fetch(url) {
        fetches.push(url);
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ key: "testkey-testkey-test", rotated: false, age: 700 }),
          text: () => Promise.resolve("# Rules"),
        });
      },
      sessionStorage: { getItem() { return null; }, setItem() {} },
      prompt() { return null; },
      GM_getValue(key, fallback) { return stored.has(key) ? stored.get(key) : fallback; },
      GM_setValue(key, value) { stored.set(key, value); },
      // The menu map lets one case press the pause entry, as the manager would.
      GM_registerMenuCommand(label, fn) {
        menus.set(label, fn);
        return label;
      },
      GM_unregisterMenuCommand(label) { menus.delete(label); },
      GM_xmlhttpRequest(options) { posts.push(options.method + " " + options.url); },
    };
    stored.set("clankers-arena-proxy-host", "https://proxy.example");
    stored.set("clankers-arena-proxy-master", "master-secret");
    vm.runInNewContext(source, context, { filename: "arena.user.js" });
    const goto = (path) => {
      context.location.pathname = path;
      context.location.href = "https://arena.ai" + path;
    };
    const drainTimeouts = () => {
      const pending = [...timeouts.values()];
      timeouts.clear();
      pending.forEach((fn) => fn());
    };
    const flush = () => {
      drainTimeouts();
      intervals.forEach((item) => item.fn());
      // A jittered HTTP timer defers its call, so the drain repeats for what the ticks scheduled.
      drainTimeouts();
    };
    const settle = () => new Promise((resolve) => setImmediate(resolve));
    const sent = () => posts.filter((entry) => entry.startsWith("POST"));

    assert.equal(composer.innerText, "", "The check holds the fill at load");
    assert.equal(clicked, 0, "The check holds the steering click at load");
    assert.equal(sent().length, 0, "The check holds the key posts at load");
    assert.equal(fetches.length, 0, "The check holds the rotate and key calls at load");
    assert.ok(page.title.includes("\uD83D\uDEE1"), "The tab title still marks the check");

    goto("/agent/one");
    popstates.forEach((fn) => fn());
    flush();
    await settle();
    assert.equal(composer.innerText, "", "The check holds the fill on a session route");
    assert.equal(clicked, 0, "The check holds the steering click on a session route");
    assert.equal(sent().length, 0, "The check holds the key posts on a session route");
    assert.equal(fetches.length, 0, "The check holds the proxy calls on a session route");

    captchaVisible = false;
    goto("/agent");
    // The HTTP timers scatter each call inside its own band: a tick waits a random moment
    // before the request, so no fixed beat forms.
    const httpCalls = () => posts.length + fetches.length;
    const callsBefore = httpCalls();
    intervals.filter((item) => item.ms === 60000).forEach((item) => item.fn());
    await settle();
    assert.equal(httpCalls(), callsBefore, "No HTTP call lands on the timer's own beat");
    flush();
    await settle();
    assert.ok(httpCalls() > callsBefore, "The scattered call lands inside its band");
    popstates.forEach((fn) => fn());
    flush();
    await settle();
    // The fill names the repo it filled (answer e8fc4f6), so one filter shows which page wrote
    // the composer.
    assert.ok(
      logged.includes("[NemoUtils][fill] filled composer for clankers"),
      `the fill line names the repo it filled: ${logged.join(" | ")}`,
    );
    assert.ok(composer.innerText.startsWith("clankers read ARENA.md"), "The fill returns when the check clears");
    assert.ok(composer.innerText.includes("here is ARENA.md:\n# Rules"), "The fill carries the rules file under the message");
    // The pause clears a scattered call that waits, so no request leaves after the press.
    const idle = httpCalls();
    intervals.filter((item) => item.ms === 60000).forEach((item) => item.fn());
    assert.equal(httpCalls(), idle, "A waiting call is not on the wire yet");
    const pauseEntry = [...menus.keys()].find((label) => label.includes("pause all"));
    assert.ok(pauseEntry, "The pause entry stands on this page");
    menus.get(pauseEntry)();
    drainTimeouts();
    await settle();
    assert.equal(httpCalls(), idle, "The pause clears the call that waited");
    assert.ok(sent().length >= 1, "The key posts return when the check clears");
    assert.ok(fetches.length >= 1, "The proxy calls return when the check clears");

    goto("/agent/one");
    popstates.forEach((fn) => fn());
    flush();
    assert.equal(clicked, 1, "The steering click returns when the check clears");
    // A session route and a return to a new chat: the fill memory left with the route,
    // so the same repo fills its new conversation again.
    composer.innerText = "";
    goto("/agent");
    popstates.forEach((fn) => fn());
    flush();
    await settle();
    assert.ok(composer.innerText.startsWith("clankers read ARENA.md"), "The fill returns on a new chat after a session route");
    console.log("ok captcha hold: fill, steering click, proxy posts wait for the check");
  });
}
{
  const { test } = require("node:test");
  // An agent chat message that lands with no turn open raises the solid speech balloon, while
  // a chat switch never reads as a message.
  test("agent message mark", async () => {
    const source = fs.readFileSync(path.join(__dirname, "../userscripts/arena.user.js"), "utf8");
    const page = { title: "" };
    const words = [{ textContent: "Sandbox" }, { textContent: "resumed" }];
    const intervals = [];
    const timeouts = new Map();
    let nextTimeout = 0;
    const composer = { innerText: "", attrs: {}, focus() {}, getAttribute() { return null; } };
    const bar = {
      textContent: "nemoe7/clankers",
      querySelectorAll(selector) {
        return selector === "span.truncate" ? [{ textContent: "nemoe7/clankers" }] : [];
      },
    };
    const repoLink = {
      getAttribute(name) {
        if (name === "href") return "https://github.com/nemoe7/clankers";
        if (name === "aria-label") return "Open nemoe7/clankers on GitHub";
        return null;
      },
    };
    const context = {
      console: { log() {} },
      URL,
      location: { href: "https://arena.ai/c/one", pathname: "/c/one" },
      document: {
        documentElement: {},
        execCommand(command, show, text) { composer.innerText = text; return true; },
        createRange() { return { selectNodeContents() {} }; },
        querySelector(selector) {
          if (selector === 'div.tiptap.ProseMirror[contenteditable="true"]') return composer;
          if (selector.indexOf("div.relative.z-10") === 0) return bar;
          if (selector.indexOf('a[aria-label^="Open "]') === 0) return repoLink;
          return null;
        },
        querySelectorAll(selector) {
          // No stop control stands on this page: the turn is over.
          if (selector === "[data-agent-word]") return words.slice();
          return [];
        },
        get title() { return page.title; },
        set title(value) { page.title = value; },
      },
      window: { addEventListener() {}, removeEventListener() {} },
      getComputedStyle() { return { overflowY: "auto" }; },
      MutationObserver: class { observe() {} disconnect() {} },
      ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
      requestAnimationFrame() { return 1; },
      cancelAnimationFrame() {},
      setInterval(fn, ms) { intervals.push({ ms, fn }); return intervals.length; },
      clearInterval() {},
      setTimeout(fn) { nextTimeout += 1; timeouts.set(nextTimeout, fn); return nextTimeout; },
      clearTimeout(id) { timeouts.delete(id); },
      fetch() {
        return Promise.resolve({
          ok: false,
          status: 404,
          json: () => Promise.resolve({}),
          text: () => Promise.resolve(""),
        });
      },
      sessionStorage: { getItem() { return null; }, setItem() {} },
      prompt() { return null; },
      GM_getValue(key, fallback) { return fallback; },
      GM_setValue() {},
      GM_registerMenuCommand(label) { return label; },
      GM_unregisterMenuCommand() {},
      GM_xmlhttpRequest() {},
    };
    vm.runInNewContext(source, context, { filename: "arena.user.js" });
    const sync = () => intervals.forEach((item) => item.fn());
    const goto = (path) => {
      context.location.pathname = path;
      context.location.href = "https://arena.ai" + path;
    };

    sync();
    assert.equal(page.title, "Arena | clankers", `The first look sets the mark in silence: ${page.title}`);
    // A chat switch swaps the whole transcript, so its fresh words are not a new message.
    goto("/c/two");
    words.push({ textContent: "elsewhere" });
    sync();
    assert.equal(page.title, "Arena | clankers", `A chat switch stays quiet: ${page.title}`);
    // On the new path a further word is a message again.
    words.push({ textContent: "here" });
    sync();
    assert.equal(page.title, "Arena | clankers \uD83D\uDCAC", `A message on the new path raises the balloon: ${page.title}`);
    // The hold bridges the pause between two bursts of words.
    sync();
    assert.equal(page.title, "Arena | clankers \uD83D\uDCAC", `The hold bridges the pause: ${page.title}`);
    console.log("ok agent message mark: silent first look, growth burns, a chat switch stays quiet");
  });
}
