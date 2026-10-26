const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const chatgptTargets = {
  "hide-claim-offer": "Hide - Claim offer",
  "hide-free-offer": "Hide - Free offer",
  "hide-mode-toggle": "Hide - mode toggle",
  "hide-codex": "Hide - Codex",
  "hide-images": "Hide - Images",
  "hide-library": "Hide - Library",
  "hide-free-badge": "Hide - Free badge",
  "hide-prompt-header": "Hide - prompt header",
  "hide-header-upgrade": "Hide - header Upgrade",
  "hide-header-share": "Hide - header Share",
  "hide-sidebar-upgrade": "Hide - sidebar Upgrade",
  "hide-plus-upsell": "Hide - Upgrade to Plus",
};

const bundles = {
  arena: {
    features: { "auto-wake": 1, "keep-working": 1, "prompt-fill": 1, "open-steering": 1, "preview-sandbox": 1, "hide-composer": 1, "auto-scroll": 1, "transcript-trim": 1, "transcript-alerts": 1, "tab-title": 1, "state-download": 0, "keep-awake": 0 },
    labels: {
      "auto-wake": "Composer - auto-send wake up",
      "keep-working": "Composer - keep working",
      "prompt-fill": "Composer - fill",
      "open-steering": "Steering - open",
      "preview-sandbox": "Steering - new tabs and downloads",
      "hide-composer": "Composer - hide",
      "auto-scroll": "Transcript - auto-scroll",
      "transcript-trim": "Transcript - auto trim",
      "transcript-alerts": "Transcript - hide generation alerts",
      "tab-title": "Page - tab title",
      "state-download": "State - download",
      "keep-awake": "Page - keep awake",
    },
    // Every Arena entry leads with its module and carries no role word. A switch ends in (ON)/(OFF).
    moduleSwitch: true,
    offByDefault: ["transcript-trim"],
    // The prompt fill owns the four proxy entries. The state download owns its three. The auto
    // trim gates its interval line behind the switch alone.
    extraMenus: { "transcript-trim": 1, "prompt-fill": 4, "state-download": 3, "tab-title": 1 },
    // The keep-rows plan, the trim cap and the trim-now press stay on the menu whatever
    // the switch says.
    alwaysMenus: { "transcript-trim": 3 },
    // Logging, global pause, and show-settings-button stay outside the feature switches.
    globalMenus: 3,
    countMenu: "Transcript - keep ",
    countKey: "clankers-arena-trim-keep",
    baseObservers: 1,
    // The prompt fill owns two timers: the paint and the key watch. Both ride the one switch.
    featureIntervals: {
      "tab-title": 1,
      "prompt-fill": 2,
      "state-download": 1,
      "transcript-trim": 1,
      "keep-awake": 1,
    },
  },
  chatgpt: {
    features: { "hide-elements": 1, "auto-think": 0 },
    labels: { "hide-elements": "Hide elements", "auto-think": "Auto Think" },
    alwaysMenus: { "hide-elements": Object.keys(chatgptTargets).length },
    baseObservers: 0,
    featureIntervals: { "auto-think": 1 },
  },
};

for (const [domain, bundle] of Object.entries(bundles)) {
  const { features, labels, countMenu, countKey, baseObservers, featureIntervals } = bundle;
  const offByDefault = new Set(bundle.offByDefault || []);
  const extraMenus = bundle.extraMenus || {};
  const source = fs.readFileSync(
    path.join(__dirname, "../../userscripts", `${domain}.user.js`), "utf8",
  );
  const header = /\/\/ ==UserScript==[\s\S]*?\/\/ ==\/UserScript==/.exec(source)[0];
  if (/^\/\/ @grant\s+GM_xmlhttpRequest\s*$/m.test(header)) {
    assert.match(header, /^\/\/ @connect\s+arena\.site\s*$/m, `${domain}: the connect tag names the preview host only`);
  }

  const keys = Object.keys(features);
  const stored = new Map();
  let refuseWrite = false;
  let promptAnswer = null;
  const alwaysMenus = bundle.alwaysMenus || {};
  const alwaysTotal = keys.reduce((total, key) => total + (alwaysMenus[key] || 0), 0);

  function isOn(saved, key) {
    return offByDefault.has(key) ? saved.get(key) === true : saved.get(key) !== false;
  }
  const observersFor = (saved) => baseObservers + keys.reduce((total, key) => total + (isOn(saved, key) ? features[key] : 0), 0);
  const intervalsFor = (saved) => keys.reduce((total, key) => total + (isOn(saved, key) ? (featureIntervals[key] || 0) : 0), 0);
  const pauseKey = "clankers-arena-userscript-paused";
  const menusFor = (saved) =>
    (bundle.globalMenus || 0) +
    keys.length +
    alwaysTotal +
    keys.reduce((total, key) => total + (isOn(saved, key) ? (extraMenus[key] || 0) : 0), 0);

  function load(documentOverride) {
    const menus = new Map();
    const logs = [];
    const intervals = [];
    const active = { observers: 0, intervals: 0, clicks: 0 };
    let nextId = 1;
    const pill = {
      textContent: "Think",
      click() { active.clicks += 1; },
    };
    const context = {
      console: Object.fromEntries(["log", "warn", "error"].map((level) => [level, (...args) => logs.push(args)])), URL,
      location: { href: `https://${domain === "arena" ? "arena.ai/agent" : "chatgpt.com/"}`, pathname: "/agent" },
      document: documentOverride || {
        documentElement: {},
        querySelector() { return null; },
        querySelectorAll(selector) { return selector.includes('aria-pressed="false"') ? [pill] : []; },
      },
      window: { addEventListener() {}, removeEventListener() {} },
      sessionStorage: { getItem() { return null; } },
      MutationObserver: class {
        observe() { active.observers += 1; }
        disconnect() { active.observers -= 1; }
      },
      setInterval(callback, ms) {
        assert.ok(
          (Number.isInteger(ms) && ms >= 1000 && ms <= 60000) || ms === 900000,
          `An interval stays inside the 1 s to 60 s owner range or the 15 min key rotation, not ${ms} ms`,
        );
        active.intervals += 1;
        intervals.push(callback);
      },
      clearInterval() { active.intervals -= 1; },
      setTimeout() { throw new Error("No steering button should schedule a click"); },
      clearTimeout() {},
      prompt() { return promptAnswer; },
      GM_getValue(key, fallback) {
        if (stored.has(key)) return stored.get(key);
        if (key === "clankers-arena-show-settings-button" && !testMasterSwitchDefault) return false;
        return fallback;
      },
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
    return { menus, active, logs, intervals };
  }

  let testMasterSwitchDefault = false;
  const moduleSwitch = bundle.moduleSwitch === true;
  function menuFor(page, key) {
    return [...page.menus.values()].find((item) =>
      item.label.startsWith(labels[key] + (moduleSwitch ? " (" : ":")));
  }
  // A switch label reads (ON)/(OFF) for the Arena bundle and `: ON - toggle` for ChatGPT.
  const reads = (label, on) => label.includes(moduleSwitch ? (on ? "(ON)" : "(OFF)") : (on ? ": ON" : ": OFF"));

  if (domain === "arena") {
    testMasterSwitchDefault = true;
    const masterDefault = load();
    assert.deepEqual(
      [...masterDefault.menus.values()].map((item) => item.label),
      ["Userscript - show settings button (ON)"],
      "When show settings button is ON, Tampermonkey hides all other menu items",
    );
    masterDefault.menus.values().next().value.callback();
    assert.equal(stored.get("clankers-arena-show-settings-button"), false);
    assert.ok(
      masterDefault.menus.size > 1,
      "Disabling show settings button reveals all other Tampermonkey menu items",
    );
    stored.clear();
    testMasterSwitchDefault = false;
  }

  const defaults = load();
  assert.equal(defaults.menus.size, menusFor(stored));
  if (domain === "arena") {
    // The owner's shape decision: one module's entries share a prefix, a switch names its state in parentheses, and no entry carries a role word.
    // The modules sit in one order, and one module's entries stay together: Composer, Proxy, Steering, Transcript, State, Page, Userscript.
    const expected = [
      "Composer - fill (ON)",
      "Composer - hide (ON)",
      "Composer - auto-send wake up (ON)",
      "Composer - keep working (ON)",
      "Proxy - host",
      "Proxy - preview host",
      "Proxy - master key",
      "Proxy - post key now",
      "Steering - open (ON)",
      "Steering - new tabs and downloads (ON)",
      "Transcript - auto-scroll (ON)",
      "Transcript - auto trim (OFF)",
      "Transcript - keep 50 rows",
      "Transcript - trim cap 200 rows",
      "Transcript - trim now",
      "Transcript - hide generation alerts (ON)",
      "State - download (ON)",
      "State - choose the file",
      "State - force save",
      "State - reset-window overwrite (ON)",
      "Page - keep awake (ON)",
      "Page - tab title (ON)",
      "Tab title - every 1 s",
      "Userscript - log level (INFO)",
      "Userscript - pause all",
      "Userscript - show settings button (OFF)",
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

  if (domain === "arena") {
    stored.clear();
    const loggingPage = load();
    const wakeLines = () => loggingPage.logs.filter((args) => args[0] === "[NemoUtils][wake][warn] unavailable").length;
    const initialWake = wakeLines();
    assert.equal(initialWake, 0);
    const wakeTick = loggingPage.intervals.find((callback) => callback.name === "sync");
    assert.ok(wakeTick);
    wakeTick(); wakeTick();
    assert.equal(wakeLines(), initialWake + 2, "repeated events must not be suppressed");
    const loggingMenu = [...loggingPage.menus.values()].find((item) => item.label === "Userscript - log level (INFO)");
    assert.ok(loggingMenu);
    loggingMenu.callback();
    assert.equal(stored.get("clankers-arena-log-level"), "debug");
    assert.deepEqual(loggingPage.active, defaults.active, "Logging settings must not change feature activity");
    assert.ok([...load().menus.values()].some((item) => item.label === "Userscript - log level (DEBUG)"));
    refuseWrite = true;
    try {
      assert.doesNotThrow(() => loggingMenu.callback());
      assert.equal(stored.get("clankers-arena-log-level"), "debug");
    } finally {
      refuseWrite = false;
    }
    stored.clear();
  }

  if (domain === "chatgpt") {
    for (const [key, label] of Object.entries(chatgptTargets)) {
      stored.clear();
      let page = load();
      const targetMenu = () => [...page.menus.values()].find((item) => item.label.startsWith(label + ":"));
      assert.ok(targetMenu(), `Every managed target has a menu: ${key}`);
      assert.ok(reads(targetMenu().label, true), `${key} ships on`);
      const beforeFailure = { ...page.active };
      refuseWrite = true;
      try {
        try { targetMenu().callback(); }
        catch (error) { assert.match(error.message, /Storage write failed/); }
      } finally { refuseWrite = false; }
      assert.equal(stored.has(key), false, "A failed write keeps the saved preference");
      assert.ok(reads(targetMenu().label, true), "A failed write keeps the target switch on");
      assert.deepEqual(page.active, beforeFailure, "A failed write keeps feature activity");
      targetMenu().callback();
      assert.equal(stored.get(key), false);
      assert.ok(reads(targetMenu().label, false));
      assert.equal(page.active.observers, observersFor(stored), "Individual switches share the existing observer");
      page = load();
      assert.ok(reads(targetMenu().label, false), "Reload keeps each target preference");
      menuFor(page, "hide-elements").callback();
      assert.equal(page.active.observers, observersFor(stored));
      assert.ok(targetMenu(), "Individual preferences stay available while the master is off");
      targetMenu().callback();
      assert.equal(stored.get(key), true);
      assert.equal(page.active.observers, observersFor(stored), "A target switch cannot enable the master");
      menuFor(page, "auto-think").callback();
      assert.equal(page.active.intervals, intervalsFor(stored), "The master leaves Auto Think independent");
      menuFor(page, "hide-elements").callback();
      assert.equal(page.active.observers, observersFor(stored));
      assert.equal(page.active.intervals, intervalsFor(stored));
      assert.ok(reads(targetMenu().label, true));
    }
    stored.clear();
    function managedNode(hidden) {
      const attrs = new Map();
      if (hidden !== undefined) attrs.set("hidden", hidden);
      return {
        hasAttribute(name) { return attrs.has(name); },
        getAttribute(name) { return attrs.has(name) ? attrs.get(name) : null; },
        setAttribute(name, value) { attrs.set(name, String(value)); },
        removeAttribute(name) { attrs.delete(name); },
      };
    }
    const mode = managedNode();
    const codex = managedNode();
    const prehidden = [managedNode(""), managedNode("until-found")];
    const scoped = load({
      documentElement: {},
      querySelector(selector) {
        return selector === "div.\\@container\\/home-mode-toggle" ? mode : null;
      },
      querySelectorAll(selector) {
        if (selector === 'button[data-sidebar-destination="builtin:codex"]') return [codex];
        if (selector === 'button[data-sidebar-destination="builtin:images"]') return prehidden;
        return [];
      },
    });
    const modeMenu = () => [...scoped.menus.values()].find((item) =>
      item.label.startsWith(chatgptTargets["hide-mode-toggle"] + ":"));
    assert.ok(mode.hasAttribute("hidden") && codex.hasAttribute("hidden"));
    modeMenu().callback();
    assert.equal(mode.hasAttribute("hidden"), false, "An individual switch restores its own target");
    assert.equal(codex.hasAttribute("hidden"), true, "Other managed targets stay hidden");
    const thinkIntervals = scoped.active.intervals;
    menuFor(scoped, "hide-elements").callback();
    assert.equal(codex.hasAttribute("hidden"), false, "The master restores owned hides");
    assert.equal(scoped.active.intervals, thinkIntervals, "The master does not stop Auto Think");
    modeMenu().callback();
    assert.equal(mode.hasAttribute("hidden"), false, "The master still wins over an individual switch");
    menuFor(scoped, "hide-elements").callback();
    assert.ok(mode.hasAttribute("hidden") && codex.hasAttribute("hidden"));
    assert.deepEqual(prehidden.map((node) => node.getAttribute("hidden")), ["", "until-found"],
      "The userscript does not restore or rewrite hides it did not own");
    stored.clear();
  }

  if (countMenu) {
    stored.clear();
    const counted = load();
    const toggle = menuFor(counted, "transcript-trim");
    assert.ok(toggle, "Missing the transcript trim toggle");
    assert.ok(reads(toggle.label, false), "Transcript trim ships OFF");
    // The plan menu is the one that names rows. The switch menu reads ": ON/OFF".
    const findCount = () => [...counted.menus.values()].find((item) => item.label.includes(countMenu));
    const findNow = () =>
      [...counted.menus.values()].find((item) => item.label === "Transcript - trim now");
    // The manual entries answer the switch whatever it reads: a trim now runs with the auto
    // trim still off.
    assert.ok(findCount(), "The count menu stays while the auto trim is off");
    assert.ok(findNow(), "The trim now button stays while the auto trim is off");
    findNow().callback();
    assert.ok(
      findCount().label.includes("50 rows"),
      "The count menu shows the default row limit",
    );
    toggle.callback();
    assert.equal(stored.get("transcript-trim"), true);

    // The count line belongs to the Transcript group, so it sits with its two switches rather
    // than at the bottom the manager appends it to.
    assert.deepEqual(
      [...counted.menus.values()].map((item) => item.label),
      [
        "Composer - fill (ON)",
        "Composer - hide (ON)",
        "Composer - auto-send wake up (ON)",
        "Composer - keep working (ON)",
        "Proxy - host",
        "Proxy - preview host",
        "Proxy - master key",
        "Proxy - post key now",
        "Steering - open (ON)",
        "Steering - new tabs and downloads (ON)",
        "Transcript - auto-scroll (ON)",
        "Transcript - auto trim (ON)",
        "Transcript - keep 50 rows",
        "Transcript - trim cap 200 rows",
        "Transcript - trim now",
        "Transcript - hide generation alerts (ON)",
        "Transcript - auto trim interval 5 s",
        "State - download (ON)",
        "State - choose the file",
        "State - force save",
        "State - reset-window overwrite (ON)",
        "Page - keep awake (ON)",
        "Page - tab title (ON)",
        "Tab title - every 1 s",
        "Userscript - log level (INFO)",
        "Userscript - pause all",
        "Userscript - show settings button (OFF)",
      ],
      "The keep-rows line sits in the Transcript group",
    );
    const findEvery = () =>
      [...counted.menus.values()].find((item) =>
        item.label.startsWith("Transcript - auto trim interval"));
    assert.ok(findEvery(), "The interval menu shows once the auto trim is on");
    assert.ok(findEvery().label.includes("5 s"), "The interval line shows the default tick");
    promptAnswer = "3";
    findEvery().callback();
    promptAnswer = null;
    assert.equal(stored.get("clankers-arena-trim-interval-ms"), 3000, "The prompt sets the trim tick");
    assert.ok(findEvery().label.includes("3 s"), "The interval line shows the saved tick");
    promptAnswer = "120";
    findEvery().callback();
    promptAnswer = null;
    assert.equal(stored.get("clankers-arena-trim-interval-ms"), 60000, "A huge answer clamps to a minute");
    promptAnswer = "zero";
    findEvery().callback();
    promptAnswer = null;
    assert.equal(stored.get("clankers-arena-trim-interval-ms"), 60000, "Garbage keeps the saved tick");
    findEvery().callback();
    assert.equal(stored.get("clankers-arena-trim-interval-ms"), 60000, "A cancel keeps the saved tick");
    const findTitleEvery = () =>
      [...counted.menus.values()].find((item) => item.label.startsWith("Tab title - every"));
    assert.ok(findTitleEvery(), "Missing the tab title interval menu");
    promptAnswer = "2";
    findTitleEvery().callback();
    promptAnswer = null;
    assert.equal(stored.get("clankers-arena-title-interval-ms"), 2000, "The prompt sets the title tick");
    assert.ok(findTitleEvery().label.includes("2 s"), "The title line shows the saved tick");
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
    // The switch gates the interval line alone, so the manual entries stay when it flips
    // back to OFF.
    toggle.callback();
    assert.equal(stored.get("transcript-trim"), false);
    assert.ok(!findEvery(), "The interval line leaves with the switch");
    assert.ok(findCount(), "The count menu stays once the auto trim is off again");
    assert.ok(findNow(), "The trim now button stays once the auto trim is off again");
  }

  stored.clear();
  for (const key of keys) stored.set(key, false);
  const allOff = load();
  assert.equal(allOff.active.observers, baseObservers);
  assert.equal(allOff.active.intervals, 0);
  assert.equal(allOff.menus.size, keys.length + (bundle.globalMenus || 0) + alwaysTotal);
  assert.ok(
    keys.every((key) => reads(menuFor(allOff, key).label, false)),
    "Every disabled feature switch reads OFF; independent target preferences stay unchanged",
  );
  assert.deepEqual(allOff.active, { observers: baseObservers, intervals: 0, clicks: 0 });

  refuseWrite = true;
  const labelsBefore = [...allOff.menus.values()].map((item) => item.label);
  assert.throws(() => allOff.menus.values().next().value.callback(), /Storage write failed/);
  assert.deepEqual([...allOff.menus.values()].map((item) => item.label), labelsBefore);
  assert.ok([...stored.values()].every((value) => value === false));
  // The global pause stops every feature where it stands, with no reload, and the resume
  // brings back the features whose own switch is ON.
  if (domain === "arena") {
    // The storage-failure check above leaves the writes refused. The pause writes again.
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
    assert.equal(live.menus.size, keys.length + bundle.globalMenus + alwaysTotal, "Every feature switch stays usable while paused");
    assert.ok(reads(menuFor(live, "tab-title").label, true), "A paused feature keeps its own switch label");
    assert.ok(resumeMenu(), "The pause entry flips to resume");
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
  const source = fs.readFileSync(path.join(__dirname, '../../userscripts/arena.user.js'), 'utf8');
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
    GM_getValue(key) {
      if (key === 'clankers-arena-show-settings-button') return false;
      return key === 'auto-scroll' && enabled;
    },
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
  const toggleMenu = () => [...menus].find(([label]) => label.startsWith('Transcript - auto-scroll ('))[1]();
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
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const promptFillUrl = "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/userscripts/arena-prompt-fill.txt";
    const arenaMdUrl = "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/rules/ARENA.md";
    const promptFillResponse = "REMOTE PROMPT TEMPLATE FROM REPOSITORY";
    let captchaVisible = true;
    let clicked = 0;
    const posts = [];
    const fetches = [];
    const intervals = [];
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
      console: Object.fromEntries(["log", "warn", "error"].map((level) => [level, (...args) => logged.push(args)])),
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
        if (url === promptFillUrl) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve({}),
            text: () => Promise.resolve(promptFillResponse),
          });
        }
        if (url === arenaMdUrl) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve({}),
            text: () => Promise.resolve("# Rules"),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ key: "testkey-testkey-test", rotated: false, age: 700 }),
          text: () => Promise.resolve(""),
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
    stored.set("clankers-arena-show-settings-button", false);
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
    assert.ok(logged.some(([line]) => line === "[NemoUtils][fill][info] filled"));
    assert.doesNotMatch(JSON.stringify(logged), /clankers|master-secret|testkey-testkey-test|REMOTE PROMPT TEMPLATE/);
    assert.ok(composer.innerText.startsWith("clankers read ARENA.md"), "The fill returns when the check clears");
    assert.ok(composer.innerText.includes(promptFillResponse), "The fill uses the text fetched from the prompt file");
    assert.equal(fetches.filter((url) => url === promptFillUrl).length, 1, "The prompt file loads once");
    assert.equal(fetches.filter((url) => url === arenaMdUrl).length, 1, "ARENA.md loads once");
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
    assert.equal(fetches.filter((url) => url === promptFillUrl).length, 1, "The prompt file stays cached for later chats on the page");
    console.log("ok captcha hold: fill, steering click, proxy posts wait for the check");
  });
}
{
  const { test } = require("node:test");
  // The tab title reads the last message root: the newest row's type carries the mark, a user
  // root carries none, and every row mark ends with the stop control.
  test("tab title row mark", async () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const page = { title: "" };
    const titleMenus = new Map();
    const logged = [];
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
    function classOf(node, name) {
      return (" " + (node.className || "") + " ").indexOf(" " + name + " ") !== -1;
    }
    // The selectors the tab-title read uses, answered the way a real tree answers them.
    function matches(node, selector) {
      if (!node || !node.attrs) return false;
      if (selector === "[data-agent-transcript-message]") return node.attrs["data-agent-transcript-message"] !== undefined;
      if (selector === "svg.lucide-play") return node.tagName === "SVG" && classOf(node, "lucide-play");
      if (selector === 'p[style*="text-shimmer"]') return String(node.attrs.style || "").indexOf("text-shimmer") !== -1;
      if (selector === ".animate-pulse") return classOf(node, "animate-pulse");
      if (selector === "span.text-text-secondary") return node.tagName === "SPAN" && classOf(node, "text-text-secondary");
      if (selector === "button") return node.tagName === "BUTTON";
      if (selector === "p") return node.tagName === "P";
      if (selector === "pre") return node.tagName === "PRE";
      if (selector === "button[aria-label]") return node.tagName === "BUTTON" && node.attrs["aria-label"] !== undefined;
      return false;
    }
    function findAll(root, selector) {
      const hits = [];
      (function walk(item) {
        (item.children || []).forEach((kid) => {
          if (matches(kid, selector)) hits.push(kid);
          walk(kid);
        });
      })(root);
      return hits;
    }
    function node(tag, className, kids) {
      const el = {
        tagName: String(tag).toUpperCase(),
        className: className || "",
        children: kids || [],
        parentElement: null,
        textContent: "",
        attrs: {},
      };
      el.getAttribute = (name) => (Object.prototype.hasOwnProperty.call(el.attrs, name) ? el.attrs[name] : null);
      el.querySelectorAll = (selector) => findAll(el, selector);
      el.querySelector = (selector) => {
        const hits = findAll(el, selector);
        return hits.length ? hits[0] : null;
      };
      Object.defineProperty(el, "firstElementChild", {
        get: () => (el.children.length ? el.children[0] : null),
      });
      el.children.forEach((kid) => { kid.parentElement = el; });
      return el;
    }
    // Both shapes follow the session dump: the agent root ends in the row container, and the
    // user root ends in the raised card with the `prose` body three levels down.
    function agentRoot(rowList) {
      const container = node("div", "flex flex-col gap-2", rowList);
      const root = node("div", "", [
        node("div", "relative overflow-hidden bg-surface-primary rounded-xl border w-full border-transparent", [
          node("div", "px-3 pb-3", [container]),
        ]),
      ]);
      root.attrs["data-agent-transcript-message"] = "true";
      root.attrs["data-chat-message-id"] = "chat-agent";
      return root;
    }
    function userRootNode() {
      const body = node("div", "prose prose-pre:bg-transparent text-wrap break-words", []);
      const card = node(
        "div",
        "relative overflow-hidden bg-surface-raised rounded-lg w-fit max-w-[min(70%,768px)] border-transparent ms-0",
        [node("div", "px-3 text-text-primary body-base py-2", [node("div", "flex flex-col gap-2", [body])])],
      );
      const root = node("div", "", [
        node("div", "", [node("div", "group flex min-w-0 flex-col items-end gap-1", [card])]),
      ]);
      root.attrs["data-agent-transcript-message"] = "true";
      root.attrs["data-chat-message-id"] = "chat-user";
      return root;
    }
    function chatRow() {
      return node("div", "prose", []);
    }
    function labelRow(label, command) {
      const span = node("span", "text-text-secondary body-sm", []);
      span.textContent = label;
      const pre = node("pre", "", []);
      pre.textContent = command || "";
      const button = node("button", "flex w-full", [span, pre]);
      button.attrs["aria-label"] = "Collapse";
      return node("div", "", [button]);
    }
    const stopButton = {
      getAttribute: (name) => (name === "aria-label" ? "Stop generating" : null),
      // The editor-content read walks every labelled button, so the mock answers closest.
      closest: () => null,
      parentElement: null,
      querySelector: () => null,
      querySelectorAll: () => [],
    };
    let roots = [agentRoot([chatRow()])];
    let stop = true;
    const context = {
      console: Object.fromEntries(["log", "warn", "error"].map((level) => [level, (...args) => logged.push(args)])),
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
          if (selector === "[data-agent-transcript-message]") return roots.slice();
          if (selector === "button[aria-label]") return stop ? [stopButton] : [];
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
      GM_getValue(key, fallback) {
        return key === "clankers-arena-show-settings-button" ? false : fallback;
      },
      GM_setValue() {},
      GM_registerMenuCommand(label, callback) { titleMenus.set(label, callback); return label; },
      GM_unregisterMenuCommand(label) { titleMenus.delete(label); },
      GM_xmlhttpRequest() {},
    };
    vm.runInNewContext(source, context, { filename: "arena.user.js" });
    const sync = () => intervals.forEach((item) => item.fn());
    const goto = (path) => {
      context.location.pathname = path;
      context.location.href = "https://arena.ai" + path;
    };

    sync();
    assert.equal(page.title, "Arena | clankers \uD83D\uDCAC", `The chat row raises the balloon: ${page.title}`);
    // The agent root appears when a turn starts. A user root carries no mark, and the hold
    // dies with the stop control.
    goto("/c/two");
    roots = [userRootNode()];
    stop = false;
    sync();
    assert.equal(page.title, "Arena | clankers", `The user root stays quiet: ${page.title}`);
    // A finished turn keeps its rows in the page, so a row mark needs the stop control.
    roots = [agentRoot([labelRow("Bash sleep 25", "$ npm test")])];
    sync();
    assert.equal(page.title, "Arena | clankers", `A finished turn drops the row mark: ${page.title}`);
    // The same page with the turn open raises the bash mark.
    stop = true;
    sync();
    assert.equal(page.title, "Arena | clankers \uD83D\uDDA5\uFE0F", `The bash row raises its mark: ${page.title}`);
    // The generating-questions action row takes the question mark, like the card.
    roots = [agentRoot([labelRow("Generating questions\u2026", "")])];
    sync();
    assert.equal(page.title, "Arena | clankers \u2753", `The question row raises the mark: ${page.title}`);
    const titleLines = logged.filter(([line]) => line.startsWith("[NemoUtils][title]"));
    assert.ok(titleLines.length > 0, "the title path logs a line");
    assert.ok(titleLines.some(([line, data]) => line === "[NemoUtils][title][info] changed" && data.type === "action"));
    assert.ok(titleLines.every(([, data]) => !("speech" in data) && !("repo" in data)));
    assert.doesNotMatch(JSON.stringify(titleLines), /Bash sleep|npm test|Generating questions|clankers/);
    const count = titleLines.length;
    sync();
    assert.equal(logged.filter(([line]) => line.startsWith("[NemoUtils][title]")).length, count);
    titleMenus.get("Page - tab title (ON)")();
    assert.equal(page.title, "", "disabling the feature restores the original title");
    assert.equal(logged.filter(([line]) => line === "[NemoUtils][title][info] restored").length, 1);
    console.log("ok tab title row mark: last root, row type, turn bound");
  });
}

{
  const saved = new Map();
  const menus = new Map();
  const observers = [];
  let generating = false;
  let display = "flex";
  let priority = "";
  const alert = {
    isConnected: true,
    matches() { return true; },
    getClientRects() { return display === "none" ? [] : [{}]; },
    style: {
      getPropertyValue() { return display; },
      getPropertyPriority() { return priority; },
      setProperty(key, value, rank) { display = value; priority = rank; },
      removeProperty() { display = ""; priority = ""; },
    },
  };
  const context = {
    console, URL,
    document: {
      documentElement: {},
      querySelector() { return null; },
      querySelectorAll(selector) {
        if (selector === "button[aria-label]") return generating ? [{ getAttribute() { return "Stop generating"; } }] : [];
        if (selector.startsWith('[role="alert"]')) return [alert];
        return [];
      },
    },
    GM_getValue(key, fallback) {
      if (saved.has(key)) return saved.get(key);
      return ["transcript-alerts", "clankers-arena-userscript-paused", "clankers-arena-log-level"].includes(key) ? fallback : false;
    },
    GM_setValue(key, value) { saved.set(key, value); },
    GM_registerMenuCommand(label, callback) { menus.set(label, callback); return label; },
    GM_unregisterMenuCommand(label) { menus.delete(label); },
    MutationObserver: class {
      constructor(callback) { this.callback = callback; observers.push(this); }
      observe(target, options) { this.active = true; this.options = options; }
      disconnect() { this.active = false; }
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8"), context);
  const notify = () => observers.filter((o) => o.active).forEach((o) => o.callback());
  const toggle = () => menus.get("Transcript - hide generation alerts (" + (saved.get("transcript-alerts") === false ? "OFF" : "ON") + ")")();
  assert.ok(menus.has("Transcript - hide generation alerts (ON)"));
  assert.ok(menus.has("Transcript - auto trim (OFF)"));
  assert.equal(display, "flex");
  generating = true; notify();
  assert.equal(display, "none", "alert hiding must not require auto trim");
  assert.ok(observers.some((o) => o.active && o.options.attributes && o.options.attributeFilter.includes("aria-label")));
  toggle();
  assert.equal(saved.get("transcript-alerts"), false);
  assert.equal(display, "flex");
  toggle();
  assert.equal(display, "none");
  menus.get("Userscript - pause all")();
  assert.equal(display, "flex");
  menus.get("Userscript - resume all")();
  assert.equal(display, "none");
  generating = false; notify();
  assert.equal(display, "flex");
}

{
  const { test } = require("node:test");
  test("auto wake sends an exact visible draft once after a cancellable delay", () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const saved = new Map(Object.keys(bundles.arena.features).filter(key => key !== "auto-wake" && key !== "keep-working").map(key => [key, false]));
  saved.set("clankers-arena-show-settings-button", false);
    const timers = new Map();
    const menus = new Map();
    const listeners = new Map();
    const observers = [];
    const logged = [];
    let next = 0;
    let clicks = 0;
    let captcha = false;
    let present = true;
    let alerts = [];
    let roots = [];
    let keepWorkingVisible = false;
    let keepWorkingClicks = 0;
    const spinnerRow = {
      tagName: "DIV",
      className: "flex w-fit items-center justify-start gap-1.5",
      outerHTML: '<div class="flex w-fit items-center justify-start gap-1.5"><div class="flex size-4 shrink-0 items-center justify-center"><div class="size-4"><canvas width="16" height="16" style="vertical-align: top; width: 16px; height: 16px;"></canvas></div></div></div>',
    };
    const proseRow = {
      tagName: "DIV",
      className: "prose",
      outerHTML: '<div class="prose"><p>Done.</p></div>',
    };
    const actionRow = {
      tagName: "DIV",
      className: "flex flex-col",
      outerHTML: '<div class="flex flex-col"><button aria-label="Collapse">Ran command</button></div>',
    };
    const keepWorkingButton = {
      disabled: false,
      hidden: false,
      textContent: "Keep working",
      getAttribute() { return null; },
      getClientRects() { return this.hidden ? [] : [{}]; },
      click() { keepWorkingClicks += 1; },
    };
    const messageRoot = (id, hasError, rows = []) => ({
      id,
      children: rows,
      querySelector(selector) {
        if (selector === ":scope > div > div.px-3.pb-3 > div.flex.flex-col.gap-2") return null;
        return hasError ? errorBanner : null;
      },
    });
    const errorBanner = { hidden: false, getClientRects() { return this.hidden ? [] : [{}]; } };
    const button = {
      disabled: false, hidden: false, ariaDisabled: null,
      getAttribute(name) { return name === "aria-disabled" ? this.ariaDisabled : null; },
      getClientRects() { return this.hidden ? [] : [{}]; },
      click() { clicks += 1; },
    };
    const box = { parentElement: { querySelector(selector) {
      return selector === 'button[aria-label="Send message"]' ? button : null;
    } } };
    const editor = {
      innerText: "wake up", hidden: false, ariaDisabled: null,
      focus() {},
      get textContent() { return this.innerText; },
      getAttribute(name) { return name === "aria-disabled" ? this.ariaDisabled : null; },
      getClientRects() { return this.hidden ? [] : [{}]; },
      closest(selector) { return selector === ".editor-content" ? box : null; },
    };
    const emit = (name, event = {}) => {
      for (const callback of [...(listeners.get(name) || [])]) callback(event);
    };
    const fire = () => { for (const observer of observers) if (observer.active) observer.callback([]); };
    const flush = () => {
      const pending = [...timers.values()];
      timers.clear();
      for (const timer of pending) timer.callback();
    };
    const context = {
      console: { log(...args) { logged.push(args); }, warn(...args) { logged.push(args); }, error(...args) { logged.push(args); } }, URL,
      location: { href: "https://arena.ai/agent/session", pathname: "/agent/session" },
      document: {
        documentElement: {},
        createRange() { return { selectNodeContents() {} }; },
        execCommand(command, ui, text) { assert.equal(command, "insertText"); editor.innerText = text; return true; },
        querySelector(selector) {
          if (selector.includes("tiptap")) return present ? editor : null;
          if (selector.includes("button:nth-child(3)")) return keepWorkingVisible ? keepWorkingButton : null;
          return null;
        },
        querySelectorAll(selector) {
          if (selector === "[data-agent-transcript-message]") return roots;
          if (selector.includes("border-red-500")) return alerts;
          return captcha && selector.includes("recaptcha-v2") ? [{ getAttribute() { return null; } }] : [];
        },
      },
      window: {
        getSelection() { return { removeAllRanges() {}, addRange() {} }; },
        addEventListener(name, callback) {
          if (!listeners.has(name)) listeners.set(name, new Set());
          listeners.get(name).add(callback);
        },
        removeEventListener(name, callback) { listeners.get(name)?.delete(callback); },
      },
      sessionStorage: { getItem() { return null; } },
      MutationObserver: class {
        constructor(callback) { this.callback = callback; this.active = false; observers.push(this); }
        observe() { this.active = true; }
        disconnect() { this.active = false; }
      },
      setTimeout(callback, ms) { const id = ++next; timers.set(id, { callback, ms }); return id; },
      clearTimeout(id) { timers.delete(id); },
      setInterval() {}, clearInterval() {},
      GM_getValue(key, fallback) { return saved.has(key) ? saved.get(key) : fallback; },
      GM_setValue(key, value) { saved.set(key, value); },
      GM_registerMenuCommand(label, callback) { const id = ++next; menus.set(id, { label, callback }); return id; },
      GM_unregisterMenuCommand(id) { menus.delete(id); },
    };
    vm.runInNewContext(source, context);
    assert.equal(timers.size, 1, "default On schedules the matching draft");
    assert.ok([...timers.values()].every(timer => timer.ms >= 0 && timer.ms <= 5000));
    fire(); fire();
    assert.equal(timers.size, 1, "mutations do not schedule duplicate sends");
    for (const text of ["wake upwake up", "Wake up", " wake up", "wake up ", "wake up\n", "other"]) {
      editor.innerText = text;
      emit("input", { isComposing: false });
      fire(); flush();
      assert.equal(clicks, 0, text);
      assert.equal(editor.innerText, text, "other drafts are not changed");
    }
    editor.innerText = "wake up";
    fire();
    editor.hidden = true;
    fire();
    assert.equal(timers.size, 0, "the composer-hide state cancels a pending send");
    editor.hidden = false;
    fire();
    button.disabled = true;
    flush();
    assert.equal(clicks, 0, "the timer checks the live button again");
    button.disabled = false;
    button.ariaDisabled = "true";
    fire();
    assert.equal(timers.size, 0);
    button.ariaDisabled = null;
    fire(); flush();
    assert.equal(clicks, 1);
    fire(); flush();
    assert.equal(clicks, 1, "one unchanged draft sends once");
    present = false; fire();
    present = true; fire(); flush();
    assert.equal(clicks, 1, "remounting the unchanged composer must not send again");
    editor.innerText = "";
    fire();
    captcha = true;
    editor.innerText = "wake up";
    fire();
    assert.equal(timers.size, 0, "captcha holds automatic sends");
    captcha = false;
    fire();
    emit("compositionstart");
    flush();
    assert.equal(clicks, 1, "IME composition cancels the pending send");
    emit("compositionend");
    const toggle = () => [...menus.values()].find(item => item.label.startsWith("Composer - auto-send wake up")).callback();
    toggle();
    fire(); flush();
    assert.equal(clicks, 1, "Off cancels the timer and observers");
    assert.equal(saved.get("auto-wake"), false);
    toggle();
    [...menus.values()].find(item => item.label === "Userscript - pause all").callback();
    flush();
    assert.equal(clicks, 1, "global pause cancels the send");
    [...menus.values()].find(item => item.label === "Userscript - resume all").callback();
    flush();
    assert.equal(clicks, 2);
    fire(); flush();
    assert.equal(clicks, 2);
    alerts = [errorBanner];
    roots = [messageRoot("old-root", true), messageRoot("latest-root", false)];
    editor.innerText = "";
    fire(); flush();
    assert.equal(editor.innerText, "", "errors in older roots must not trigger recovery");
    assert.equal(clicks, 2);
    roots = [messageRoot("old-root", true), messageRoot("latest-root", true)];
    errorBanner.hidden = true;
    editor.innerText = "Keep this draft";
    fire(); flush();
    assert.equal(editor.innerText, "Keep this draft");
    assert.equal(clicks, 2);
    editor.innerText = "";
    editor.hidden = true;
    fire();
    assert.equal(editor.innerText, "", "hidden composers must not be filled");
    editor.hidden = false;
    captcha = true;
    fire();
    assert.equal(editor.innerText, "", "captcha holds error recovery too");
    captcha = false;
    emit("compositionstart");
    fire();
    assert.equal(editor.innerText, "", "IME holds error recovery too");
    emit("compositionend");
    assert.equal(editor.innerText, "wake up", "the latest-root error triggers even when trim hides its banner");
    assert.equal(timers.size, 1);
    flush();
    assert.equal(clicks, 3);
    editor.innerText = "";
    fire(); flush();
    assert.equal(editor.innerText, "", "an unchanged error cannot create a retry loop");
    assert.equal(clicks, 3);
    roots = [messageRoot("latest-root", true)];
    fire(); flush();
    assert.equal(clicks, 3, "the same root ID cannot repeat after a remount");
    roots = [messageRoot("newest-root", true)];
    fire(); flush();
    assert.equal(clicks, 4, "a new latest root permits one recovery");
    roots = [messageRoot("no-button-root", false, [proseRow, actionRow])];
    present = true;
    editor.innerText = "";
    keepWorkingVisible = false;
    fire(); flush();
    assert.equal(keepWorkingClicks, 0);
    assert.equal(editor.innerText, "", "does not type wake up if Keep working never showed up");
    present = false;
    keepWorkingVisible = true;
    roots = [messageRoot("spinner-root", false, [actionRow, spinnerRow])];
    fire(); flush();
    assert.equal(keepWorkingClicks, 0, "Keep working stays idle while the last row is the 16x16 canvas spinner");
    roots = [messageRoot("prose-root", false, [actionRow, proseRow])];
    fire(); flush();
    assert.equal(keepWorkingClicks, 0, "Keep working stays idle when the last row has the prose class");
    roots = [messageRoot("stopped-root", false, [proseRow, actionRow])];
    const toggleKeepWorking = () => [...menus.values()].find(item => item.label.startsWith("Composer - keep working")).callback();
    toggleKeepWorking();
    assert.equal(saved.get("keep-working"), false);
    fire(); flush();
    assert.equal(keepWorkingClicks, 0, "Keep working toggle Off disables the click");
    toggleKeepWorking();
    assert.equal(saved.get("keep-working"), true);
    assert.equal(keepWorkingClicks, 0, "waits for the random 0-5s delay before clicking Keep working");
    assert.equal(timers.size, 1);
    assert.ok([...timers.values()].every(timer => timer.ms >= 0 && timer.ms <= 5000));
    flush();
    assert.equal(keepWorkingClicks, 1, "Keep working clicks once when the last row is neither spinner nor prose");
    assert.ok(logged.some(([line]) => line === "[NemoUtils][keep-working][info] clicked"));
    assert.equal(editor.innerText, "", "waits for the composer before typing wake up");
    fire(); flush();
    assert.equal(keepWorkingClicks, 1, "does not click Keep working repeatedly for the same root");
    keepWorkingVisible = false;
    present = true;
    fire();
    assert.equal(editor.innerText, "wake up", "types wake up once the composer mounts");
    assert.ok(logged.some(([line]) => line === "[NemoUtils][keep-working][info] filled"));
    flush();
    assert.equal(clicks, 5, "sends wake up after Keep working opens the composer");
  });
}

{
  const { test } = require("node:test");
  test("setComposerText renders inline backtick spans as code elements", () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const makeNode = (tag) => ({
      tagName: tag.toUpperCase(),
      children: [],
      _text: "",
      get firstChild() { return this.children[0] || null; },
      get textContent() {
        return this.children.length
          ? this.children.map(child => child.textContent).join("")
          : this._text;
      },
      set textContent(value) {
        this.children = [];
        this._text = String(value);
      },
      get innerText() {
        return this.children.length
          ? this.children.map(child => child.textContent).join("\n")
          : this._text;
      },
      appendChild(child) { this.children.push(child); return child; },
      removeChild(child) {
        const idx = this.children.indexOf(child);
        if (idx >= 0) this.children.splice(idx, 1);
      },
      dispatchEvent() {},
      focus() {},
      getAttribute() { return null; },
    });
    const composer = makeNode("div");
    let execCalled = false;
    const context = {
      console: { log() {}, warn() {}, error() {} },
      URL,
      InputEvent: class { constructor(type, init) { this.type = type; Object.assign(this, init); } },
      location: { href: "https://arena.ai/agent", pathname: "/agent" },
      document: {
        documentElement: {},
        createElement(tag) { return makeNode(tag); },
        createTextNode(text) { return { nodeType: 3, textContent: String(text) }; },
        createRange() { return { selectNodeContents() {} }; },
        execCommand() { execCalled = true; return true; },
        querySelector(selector) {
          if (selector === 'div.tiptap.ProseMirror[contenteditable="true"]') return composer;
          if (selector.indexOf("div.relative.z-10") === 0) {
            return {
              textContent: "nemoe7/clankers",
              querySelectorAll() {
                return [{ textContent: "nemoe7/clankers" }];
              },
            };
          }
          return null;
        },
        querySelectorAll() { return []; },
        title: "",
      },
      window: {
        addEventListener() {},
        removeEventListener() {},
        getSelection() { return { removeAllRanges() {}, addRange() {} }; },
      },
      getComputedStyle() { return { overflowY: "auto" }; },
      MutationObserver: class { observe() {} disconnect() {} },
      ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
      requestAnimationFrame() { return 1; },
      cancelAnimationFrame() {},
      setInterval() { return 1; },
      clearInterval() {},
      setTimeout() { return 1; },
      clearTimeout() {},
      fetch(url) {
        return Promise.resolve({
          ok: true,
          status: 200,
          text: () => Promise.resolve(
            url.includes("arena-prompt-fill.txt")
              ? "Run `arena-preview survey '<json>'` and `git ls-remote origin <branch>`.\nPlain line"
              : "",
          ),
        });
      },
      sessionStorage: { getItem() { return null; }, setItem() {} },
      GM_getValue(key, fallback) {
        if (key === "prompt-fill") return true;
        return false;
      },
      GM_setValue() {},
      GM_registerMenuCommand() { return 1; },
      GM_unregisterMenuCommand() {},
      GM_xmlhttpRequest() {},
    };
    vm.runInNewContext(source, context);
    return new Promise((resolve) => setImmediate(resolve)).then(() => {
      assert.equal(execCalled, false, "inline backtick spans bypass plain-text execCommand");
      assert.equal(composer.children.length, 4);
      const codeNodes = composer.children[2].children.filter(node => node.tagName === "CODE");
      assert.deepEqual(
        codeNodes.map(node => node.textContent),
        ["arena-preview survey '<json>'", "git ls-remote origin <branch>"],
      );
      assert.equal(composer.children[3].textContent, "Plain line");
    });
  });
}

{
  const { test } = require("node:test");
  test("autosave compares the two saved stamps and confirms only completed writes", async () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const saved = new Map();
    const menus = new Map();
    const timers = [];
    const requests = [];
    const stamp = "2026-10-15T09:00:00+00:00";
    const base = "https://preview.example";
    const logs = [];
    const collect = (...args) => logs.push(args);
    saved.set("clankers-arena-state-scope-o.r", "o.r");
    saved.set("clankers-arena-state-base-o.r", base);
    saved.set("clankers-arena-state-branch-o.r", "");
    saved.set("clankers-arena-state-ask-o.r", false);
    saved.set("clankers-arena-state-stamp-o.r", JSON.stringify({ stamp, note: "", task: "" }));
    const linkClicks = [];
    const makeElement = (tag) => ({
      tagName: tag,
      children: [],
      style: {},
      attributes: {},
      listeners: {},
      textContent: "",
      click() { linkClicks.push(this.download); },
      setAttribute(name, value) { this.attributes[name] = String(value); },
      getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; },
      appendChild(child) { child.parentNode = this; this.children.push(child); return child; },
      removeChild(child) { this.children = this.children.filter((item) => item !== child); return child; },
      addEventListener(name, callback) { this.listeners[name] = callback; },
    });
    const body = makeElement("body");
    const iframe = { getAttribute: (name) => (name === "title" ? "App preview on port 8000" : null), src: base + "/" };
    const documentFake = {
      body,
      visibilityState: "visible",
      createElement: makeElement,
      getElementById: (id) => body.children.find((child) => child.id === id) || null,
      querySelectorAll: (selector) => (selector === "iframe[title]" ? [iframe] : []),
      querySelector: () => null,
      addEventListener: () => {},
    };
    const context = {
      document: documentFake,
      location: { href: "https://arena.ai/c/o/r", pathname: "/c/o/r", search: "" },
      navigator: {},
      sessionStorage: { getItem: (key) => (key === "clankers-arena-agent-slug" ? "o.r" : null), setItem: () => {} },
      localStorage: { getItem: () => null, setItem: () => {} },
      MutationObserver: class { observe() {} disconnect() {} },
      setInterval: (callback) => { timers.push(callback); return timers.length; },
      clearInterval: () => {},
      setTimeout: callback => { callback(); return 0; },
      clearTimeout: () => {},
      fetch: () => Promise.reject(new Error("offline")),
      Blob: class { constructor(parts) { this.parts = parts; } },
      URL: { createObjectURL: () => "blob:x", revokeObjectURL: () => {} },
      console: { log: collect, warn: collect, error: collect, debug: () => {}, info: () => {} },
      GM_getValue: (key, fallback) => (saved.has(key) ? saved.get(key) : fallback),
      GM_setValue: (key, value) => { saved.set(key, value); },
      GM_deleteValue: (key) => { saved.delete(key); },
      GM_registerMenuCommand: (label, callback) => { menus.set(label, callback); return label; },
      GM_unregisterMenuCommand: (label) => { menus.delete(label); },
      GM_xmlhttpRequest: (options) => { requests.push(options); },
      GM_addStyle: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      matchMedia: () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
    };
    context.window = context;
    context.self = context;
    saved.set("clankers-arena-state-hinted", true);
    saved.set("clankers-arena-show-settings-button", false);
    vm.runInNewContext(source, context, { filename: "arena.user.js" });
    const settle = () => new Promise(setImmediate);
    const digest = core => require("node:crypto").createHash("sha256").update(JSON.stringify(core)).digest("hex");
    const scope = { repo: "r", branch: "" };
    const core = [{ id: "n", text: "saved" }];
    const receiptKey = "clankers-arena-state-receipt-o.r";
    const pendingKey = "clankers-arena-state-pending-o.r";
    const receipt = { save_id: "first", digest: digest(core), scope, lastsave: "t1", beforelastsave: null };
    saved.set(receiptKey, receipt);
    const healthy = {
      save_id: "first", scope, core, digest: digest(core), stamp: "t1",
      lastsave: "t1", beforelastsave: null, text: core.map(JSON.stringify).join("\n") + "\n",
    };
    const changedCore = [{ id: "n", text: "changed" }];
    const changed = {
      ...healthy, save_id: "second", core: changedCore, digest: digest(changedCore),
      stamp: "t2", lastsave: "t1", beforelastsave: null,
      text: changedCore.map(JSON.stringify).join("\n") + "\n",
    };
    const panel = () => body.children.find(child => child.id === "clankers-state-panel") || null;
    const respond = async (method, suffix, status, value) => {
      const request = requests.at(-1);
      assert.equal(request.method, method);
      assert.equal(new URL(request.url).pathname, suffix);
      request.onload({ status, responseText: JSON.stringify(value) });
      await settle();
      return request;
    };
    const tick = () => timers.forEach(callback => callback());
    assert.equal(requests.length, 1);
    await respond("GET", "/api/userscript-autosave", 200, healthy);
    assert.equal(panel(), null);
    tick();
    await respond("GET", "/api/userscript-autosave", 502, null);
    assert.equal(panel(), null);
    tick();
    await respond("GET", "/api/userscript-autosave", 200, healthy);
    assert.equal(panel(), null);

    const writes = [];
    const writeAttempts = [];
    let fileText = healthy.text;
    let finishClose;
    let failWrite = false;
    let closeWait = new Promise(resolve => { finishClose = resolve; });
    const handle = { name: "o.r.ndjson", getFile: async () => ({ text: async () => fileText }), createWritable: async () => ({
      write: async text => { writeAttempts.push(text); if (failWrite) throw new Error("write failed"); writes.push(text); },
      close: async () => { await closeWait; fileText = writes.at(-1); },
    }) };
    let availableHandle = handle;
    context.indexedDB = { open() {
      const opening = { result: { transaction: () => ({ objectStore: () => ({ get() {
        const reading = { result: availableHandle };
        queueMicrotask(() => reading.onsuccess());
        return reading;
      } }) }) } };
      queueMicrotask(() => opening.onsuccess());
      return opening;
    } };
    iframe.src = "https://new-preview.example/";
    tick();
    await respond("GET", "/api/userscript-autosave", 200, changed);
    assert.equal(panel(), null);
    assert.deepEqual(writes, []);
    menus.get("State - force save")();
    assert.equal(panel(), null);
    await respond("GET", "/api/userscript-autosave", 200, changed);
    assert.equal(writes.length, 1, "the accepted move writes the server state");
    assert.equal(requests.at(-1).url.endsWith("/userscript-autosave"), true, "no compare request");
    assert.equal(saved.get(receiptKey).lastsave, "t1", "the receipt waits for the close");
    finishClose();
    await settle();
    const confirm = requests.at(-1);
    assert.equal(confirm.method, "POST");
    assert.equal(new URL(confirm.url).pathname, "/api/userscript-autosave");
    const sent = JSON.parse(confirm.data);
    assert.equal(sent.digest, changed.digest);
    assert.equal(sent.lastsave, "t2");
    assert.equal(sent.beforelastsave, "t1");
    await respond("POST", "/api/userscript-autosave", 201, { confirmed: true, save_id: changed.save_id, digest: changed.digest });
    assert.equal(writes.length, 1, "receipt retry does not rewrite the file");
    assert.equal(saved.get(receiptKey).lastsave, "t2");
    assert.equal(saved.get(receiptKey).beforelastsave, "t1");
    assert.equal(saved.get(pendingKey), null);

    closeWait = Promise.resolve();
    const synced = { ...changed, lastsave: "t2", beforelastsave: "t1" };
    tick();
    await respond("GET", "/api/userscript-autosave", 200, synced);
    assert.equal(writes.length, 1, "an in-sync cycle with the same stamp writes nothing");
    assert.equal(panel(), null);
    for (const field of ["type", "kind"]) { // nonemo: NMO100
      const validText = [...changedCore, { [field]: "userscript-autosave" }].map(JSON.stringify).join("\n") + "\n";
      fileText = validText;
      const beforeWrites = writes.slice();
      const beforeReceipt = structuredClone(saved.get(receiptKey));
      const unchangedAttempts = writeAttempts.slice();
      tick();
      await respond("GET", "/api/userscript-autosave", 200, synced);
      assert.deepEqual(writeAttempts, unchangedAttempts);
      assert.deepEqual(writes, beforeWrites);
      assert.deepEqual(structuredClone(saved.get(receiptKey)), beforeReceipt);

      const next = { ...synced, core: healthy.core, digest: healthy.digest, text: healthy.text, stamp: "next" };
      failWrite = true;
      tick();
      await respond("GET", "/api/userscript-autosave", 200, next);
      assert.ok(writeAttempts.length > unchangedAttempts.length);
      assert.deepEqual(writes, beforeWrites);
      assert.deepEqual(structuredClone(saved.get(receiptKey)), beforeReceipt);
      assert.equal(saved.get(pendingKey), null);
      failWrite = false;

      fileText = "{invalid";
      const blockedAttempts = writeAttempts.slice();
      tick();
      await respond("GET", "/api/userscript-autosave", 200, next);
      assert.deepEqual(writeAttempts, blockedAttempts);
      assert.deepEqual(writes, beforeWrites);
      assert.deepEqual(structuredClone(saved.get(receiptKey)), beforeReceipt);
      assert.equal(panel(), null);

      fileText = validText;
      const ahead = { ...synced, lastsave: "ahead", beforelastsave: synced.lastsave };
      tick();
      await respond("GET", "/api/userscript-autosave", 200, ahead);
      assert.deepEqual(writeAttempts, blockedAttempts);
      assert.deepEqual(writes, beforeWrites);
      assert.deepEqual(structuredClone(saved.get(receiptKey)), beforeReceipt);
      assert.equal(panel(), null);
    }
    fileText = changed.text;

    const stale = { ...changed, save_id: "stale", stamp: "t9", lastsave: "t9", beforelastsave: "t2" };
    tick();
    await respond("GET", "/api/userscript-autosave", 200, stale);
    assert.equal(panel(), null);
    assert.equal(writes.length, 1);
    const refusal = logs.map(args => args[1]).filter(data => data && data.code === "autosave-compare").at(-1);
    assert.equal(refusal.detail, "saved t2/t1 server t9/t2 n1 t0 dn0 dt0", "the refusal names both stamp pairs");
    menus.get("State - force save")();
    assert.equal(panel(), null);
    await respond("GET", "/api/userscript-autosave", 200, stale);
    assert.equal(writes.length, 2, "the overwrite button runs force save");
    await respond("POST", "/api/userscript-autosave", 201, { confirmed: true, save_id: stale.save_id, digest: stale.digest });
    assert.equal(saved.get(receiptKey).lastsave, "t9");
    assert.equal(saved.get(receiptKey).beforelastsave, "t9");
    tick();
    await respond("GET", "/api/userscript-autosave", 200, {
      ...stale, save_id: "after-force", stamp: "t10", lastsave: "t9", beforelastsave: "t9",
    });
    assert.equal(writes.length, 2, "future autosaves pass after Force save");

    const diverged = { ...stale, save_id: "diverged", stamp: "t11", lastsave: "t8", beforelastsave: "t7" };
    tick();
    await respond("GET", "/api/userscript-autosave", 200, diverged);
    assert.equal(panel(), null);
    assert.equal(writes.length, 2);

    failWrite = true;
    menus.get("State - force save")();
    await respond("GET", "/api/userscript-autosave", 200, { ...stale, save_id: "failed-write" });
    assert.equal(saved.get(pendingKey), null, "a failed write does not create a pending receipt");
    failWrite = false;

    availableHandle = null;
    menus.get("State - force save")();
    await respond("GET", "/api/userscript-autosave", 200, { ...stale, save_id: "link-only" });
    assert.equal(linkClicks.length, 1);
    assert.equal(saved.get(pendingKey), null);

    let download;
    context.GM_download = options => { download = options; };
    menus.get("State - force save")();
    await respond("GET", "/api/userscript-autosave", 200, { ...stale, save_id: "manager-failed" });
    download.onerror({ error: "blocked" });
    await settle();
    assert.equal(linkClicks.length, 2);
    assert.equal(panel(), null);

    menus.get("State - force save")();
    await respond("GET", "/api/userscript-autosave", 200, { ...stale, save_id: "manager-complete" });
    download.onload();
    await settle();
    await respond("POST", "/api/userscript-autosave", 201, { confirmed: true, save_id: "manager-complete", digest: stale.digest });
    assert.equal(saved.get(receiptKey).save_id, "manager-complete");

    saved.delete("clankers-arena-state-scope-o.r");
    saved.delete(receiptKey);
    saved.delete(pendingKey);
    saved.set("clankers-arena-state-hinted", true);
    availableHandle = null;
    const downloadsBeforeUnlisted = linkClicks.length;
    context.GM_download = undefined;
    let pickerPromise;
    context.showSaveFilePicker = () => pickerPromise;
    tick();
    await respond("GET", "/api/userscript-autosave", 200, { ...healthy, save_id: "unlisted-1", lastsave: null, beforelastsave: null });
    assert.equal(panel(), null);
    menus.get("State - force save")();
    await respond("GET", "/api/userscript-autosave", 200, { ...healthy, save_id: "unlisted-1", lastsave: null, beforelastsave: null });
    assert.equal(linkClicks.length, downloadsBeforeUnlisted, "Force save does not fall back to browser download when the file picker is available");
    assert.equal(panel(), null);

    tick();
    await respond("GET", "/api/userscript-autosave", 200, { ...healthy, save_id: "unlisted-2", lastsave: null, beforelastsave: null });
    assert.equal(panel(), null);
    pickerPromise = Promise.reject(Object.assign(new Error("cancelled"), { name: "AbortError" }));
    menus.get("State - choose the file")();
    await settle();
    assert.equal(panel(), null);

    fileText = "";
    availableHandle = handle;
    context.indexedDB = { open() {
      const opening = { result: { transaction: () => ({ objectStore: () => ({
        get() {
          const reading = { result: availableHandle };
          queueMicrotask(() => reading.onsuccess());
          return reading;
        },
        put() {},
      }) }) } };
      queueMicrotask(() => opening.onsuccess());
      return opening;
    } };
    pickerPromise = Promise.resolve(handle);
    menus.get("State - choose the file")();
    await settle();
    await settle();
    await respond("GET", "/api/userscript-autosave", 200, { ...healthy, save_id: "unlisted-saved", lastsave: null, beforelastsave: null });
    await settle();
    await respond("POST", "/api/userscript-autosave", 201, { confirmed: true, save_id: "unlisted-saved", digest: healthy.digest });
    assert.equal(panel(), null, "a completed Choose file save clears the missing-branch warning");
    assert.equal(saved.get("clankers-arena-state-scope-o.r"), "o.r");
  });
}

{
  const { test } = require("node:test");
  test("state logs keep a bounded failure reason", () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const logged = [];
    const sink = (...args) => logged.push(args);
    const context = {
      console: { log: sink, warn: sink, error: sink },
      GM_getValue: () => "info",
      GM_setValue: () => {},
      setTimeout: () => 0,
      clearTimeout: () => {},
      setInterval: () => 0,
      clearInterval: () => {},
      URL,
      addEventListener: () => {},
      removeEventListener: () => {},
    };
    vm.runInNewContext(source, context, { filename: "arena.user.js" });
    const { sameSaves, sameSaveDetail, stateDiffCounts, stateMismatchLine } = context.CLANKERS_CHECKS.stateDownload;
    assert.equal(sameSaves(null, { lastsave: "a", beforelastsave: null }), false);
    assert.equal(sameSaves({ lastsave: "a", beforelastsave: null }, { lastsave: "a", beforelastsave: null }), true);
    assert.equal(sameSaves({ lastsave: "a", beforelastsave: "b" }, { lastsave: "a", beforelastsave: null }), false);
    assert.equal(sameSaves({ lastsave: "a", beforelastsave: "b" }, { lastsave: "a", beforelastsave: "b" }), true);
    assert.equal(
      sameSaveDetail({ lastsave: "t2", beforelastsave: "t1" }, { lastsave: "t9", beforelastsave: "t2" }),
      "saved t2/t1 server t9/t2 n0 t0",
      "the detail names both stamp pairs and the counts"
    );
    assert.equal(
      sameSaveDetail(
        { lastsave: "t2", beforelastsave: "t1", counts: { notes: 2, tasks: 1 } },
        { lastsave: "t9", beforelastsave: "t2", counts: { notes: 4, tasks: 1 } }
      ),
      "saved t2/t1 server t9/t2 n4 t1 dn+2 dt0",
      "the detail includes signed diff counts when baseline counts exist"
    );
    assert.equal(
      stateMismatchLine(
        { core: [{ id: "n1", text: "a" }] },
        { core: [{ id: "n1", text: "a" }, { id: "n2", text: "b" }, { id: "t1", title: "Task" }] }
      ),
      "State mismatch (notes +1, tasks +1)."
    );
    assert.deepEqual(
      JSON.parse(JSON.stringify(stateDiffCounts(
        { counts: { notes: 5, tasks: 3 } },
        { counts: { notes: 3, tasks: 4 } }
      ))).notes,
      -2
    );
    assert.equal(
      sameSaveDetail(null, { lastsave: "t9", beforelastsave: null, counts: { notes: 3, tasks: 2 } }),
      "saved none/none server t9/none n3 t2",
      "a missing baseline reads as none"
    );
    const longStamp = "2026-10-15T09:00:00";
    assert.ok(
      sameSaveDetail(
        { lastsave: longStamp, beforelastsave: longStamp },
        { lastsave: longStamp, beforelastsave: longStamp, counts: { notes: 999, tasks: 999 } }
      ).length <= 160,
      "the detail stays inside the log cap"
    );
    const { logEvent } = context.CLANKERS_CHECKS.logging;
    logEvent("state", "failed", { code: "autosave-compare", status: 200, result: "unknown-baseline", detail: "digest" }, "error");
    const [line, data] = logged.at(-1);
    assert.match(line, /\[state\]\[error\] failed/);
    assert.equal(data.code, "autosave-compare");
    assert.equal(data.status, 200);
    assert.equal(data.result, "unknown-baseline");
    assert.equal(data.detail, "digest");
    logEvent("state", "failed", { detail: "x".repeat(500) }, "error");
    assert.equal(logged.at(-1)[1].detail.length, 160);
    logEvent("state", "failed", { result: "other", detail: "" }, "error");
    assert.equal(logged.at(-1).length, 1, "unknown values and empty detail stay out of the log");
  });
}

{
  const { test } = require("node:test");
  const { spawn } = require("node:child_process");
  test("autosave round-trips live preview HTTP responses and state import", async () => {
    const pyScript = `
import importlib.util, json, os, subprocess, sys, tempfile, threading
from contextlib import closing
from pathlib import Path

root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("preview_mod", root / "skills/refs/arena-skill/scripts/preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

tmp = tempfile.TemporaryDirectory()
repo = Path(tmp.name) / "r"
repo.mkdir()
subprocess.run(["git", "init", "-b", "arena/11223344-r"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
state_dir = repo / "arena-state"
store = preview.Store(state_dir, create=True)
store.note("first-note", "initial note")
store.write_task("t-1", "Verify autosave", ["Check round-trip"], task_type="code")
report_md = state_dir / "sample-report.md"
report_md.write_text("# Sample Report\\n\\nProceed? {#go}\\n- (x) Yes\\n- ( ) No\\n", encoding="utf-8")
store.publish("sample-report", "Sample Report", report_md)

server = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
print(json.dumps({"base": f"http://127.0.0.1:{server.server_port}"}), flush=True)

for raw in sys.stdin:
  cmd = json.loads(raw)
  op = cmd["op"]
  if op == "mutate":
    store.note("second-note", "second note")
    store.write_task("t-1", "Verify autosave", ["Check round-trip"], status="finished", task_type="code")
    print(json.dumps({"ok": True}), flush=True)
  elif op == "diverge":
    snap = store.userscript_snapshot()
    history = [
      {
        "type": "userscript-autosave",
        "version": 1,
        "save_id": "11111111-1111-4111-8111-111111111111",
        "scope": snap["scope"],
        "digest": snap["digest"],
        "core": snap["core"],
        "stamp": "2098-01-01T00:00:00+00:00",
        "confirmed_at": "2098-01-01T00:00:00+00:00",
        "receipts": {},
      },
      {
        "type": "userscript-autosave",
        "version": 1,
        "save_id": "22222222-2222-4222-8222-222222222222",
        "scope": snap["scope"],
        "digest": snap["digest"],
        "core": snap["core"],
        "stamp": "2099-01-01T00:00:00+00:00",
        "confirmed_at": "2099-01-01T00:00:00+00:00",
        "receipts": {},
      },
    ]
    with closing(store.connect()) as db, db:
      db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (preview.AUTOSAVE_HISTORY, json.dumps(history)))
    store.note("third-note", "diverged note")
    print(json.dumps({"ok": True}), flush=True)
  elif op == "clear":
    store.clear_state()
    print(json.dumps({"ok": True, "force": store.userscript_snapshot().get("force")}), flush=True)
  elif op == "restore_prev":
    store.restore_state(previous=True)
    print(json.dumps({"ok": True, "force": store.userscript_snapshot().get("force")}), flush=True)
  elif op == "inspect":
    snap = store.userscript_snapshot()
    state_notes = {item["id"]: item for item in store.state()["notes"]}
    backup_notes = [
      {
        "id": item["id"],
        "quiet": item.get("quiet"),
        "blocking": item.get("blocking"),
        "type": (state_notes.get(item["id"]) or {}).get("type"),
        "text": item.get("text"),
        "attachments": [att["path"] for att in (item.get("attachments") or [])],
      }
      for item in store.read(include_quiet=True)["pending"]
      if (state_notes.get(item["id"]) or {}).get("type") == "state-backup"
    ]
    visible_notes = [
      item["id"] for item in store.state()["notes"] if not item.get("quiet")
    ]
    print(json.dumps({
      "lastsave": snap["lastsave"],
      "beforelastsave": snap["beforelastsave"],
      "digest": snap["digest"],
      "force": snap.get("force"),
      "backup_notes": backup_notes,
      "visible_notes": visible_notes,
    }), flush=True)
  elif op == "import":
    dest = Path(tmp.name) / "imported" / "r"
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "arena/11223344-r"], cwd=dest, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=dest, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=dest, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=dest, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fresh = preview.Store(dest / "arena-state", create=True)
    counts = fresh.import_state(cmd["text"], replace_tasks=True)
    with closing(fresh.connect()) as db:
      row = db.execute("SELECT source FROM reports WHERE id = ?", ("sample-report",)).fetchone()
    hist_lines = fresh.userscript_history()
    print(json.dumps({
      "counts": counts,
      "report_source": row[0] if row else None,
      "history_count": len(hist_lines),
      "lastsave": fresh.userscript_snapshot().get("lastsave"),
    }), flush=True)
  elif op == "quit":
    server.shutdown()
    tmp.cleanup()
    print(json.dumps({"ok": True}), flush=True)
    break
`;
    const repoRoot = path.resolve(__dirname, "../..");
    const proc = spawn("python3", ["-c", pyScript, repoRoot], { stdio: ["pipe", "pipe", "inherit"] });
    const lines = [];
    let waiters = [];
    let buffer = "";
    proc.stdout.setEncoding("utf8");
    proc.stdout.on("data", chunk => {
      buffer += chunk;
      let idx;
      while ((idx = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);
        if (!line) continue;
        const parsed = JSON.parse(line);
        if (waiters.length) waiters.shift()(parsed);
        else lines.push(parsed);
      }
    });
    const nextMessage = () => lines.length ? Promise.resolve(lines.shift()) : new Promise(resolve => waiters.push(resolve));
    const callPy = async payload => {
      proc.stdin.write(JSON.stringify(payload) + "\n");
      return nextMessage();
    };

    try {
      const { base } = await nextMessage();
      const source = fs.readFileSync(path.join(repoRoot, "userscripts/arena.user.js"), "utf8");
      const saved = new Map();
      const menus = new Map();
      const timers = [];
      let inFlight = [];
      let fileText = "";
      const writes = [];
      const handle = {
        name: "r-arena-11223344-r.ndjson",
        getFile: async () => ({ text: async () => fileText }),
        createWritable: async () => ({
          write: async text => { writes.push(text); },
          close: async () => { fileText = writes.at(-1); },
        }),
      };
      const makeElement = tag => ({
        tagName: tag,
        children: [],
        style: {},
        attributes: {},
        listeners: {},
        textContent: "",
        click() {},
        setAttribute(name, value) { this.attributes[name] = String(value); },
        getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; },
        appendChild(child) { child.parentNode = this; this.children.push(child); return child; },
        removeChild(child) { this.children = this.children.filter(item => item !== child); return child; },
        addEventListener(name, callback) { this.listeners[name] = callback; },
      });
      const body = makeElement("body");
      const iframe = { getAttribute: name => (name === "title" ? "App preview on port 8000" : null), src: base + "/" };
      const context = {
        document: {
          body,
          title: "Arena | r",
          visibilityState: "visible",
          createElement: makeElement,
          getElementById: id => body.children.find(child => child.id === id) || null,
          querySelectorAll: selector => (selector === "iframe[title]" ? [iframe] : []),
          querySelector: selector => {
            if (selector.indexOf("div.relative.z-10") === 0) {
              return {
                querySelectorAll(sel) {
                  if (sel === "span.truncate") return [{ textContent: "o/r" }];
                  if (sel === "a, [title]") {
                    return [{ getAttribute: name => (name === "href" ? "https://github.com/o/r/tree/arena/11223344-r" : null) }];
                  }
                  return [];
                },
              };
            }
            return null;
          },
          addEventListener: () => {},
        },
        location: { href: "https://arena.ai/agent/11223344", pathname: "/agent/11223344", search: "" },
        navigator: {},
        sessionStorage: { getItem: key => (key === "clankers-arena-agent-slug" ? "r" : null), setItem: () => {} },
        localStorage: { getItem: () => null, setItem: () => {} },
        MutationObserver: class { observe() {} disconnect() {} },
        setInterval: callback => { timers.push(callback); return timers.length; },
        clearInterval: () => {},
        setTimeout: callback => { callback(); return 0; },
        clearTimeout: () => {},
        fetch: () => Promise.reject(new Error("offline")),
        Blob: class { constructor(parts) { this.parts = parts; } },
        URL,
        console: { log() {}, warn() {}, error() {}, debug() {}, info() {} },
        GM_getValue: (key, fallback) => {
          if (saved.has(key)) return saved.get(key);
          if (key === "clankers-arena-show-settings-button") return false;
          return fallback;
        },
        GM_setValue: (key, value) => { saved.set(key, value); },
        GM_deleteValue: key => { saved.delete(key); },
        GM_registerMenuCommand: (label, callback) => { menus.set(label, callback); return label; },
        GM_unregisterMenuCommand: label => { menus.delete(label); },
        GM_xmlhttpRequest: options => {
          const p = fetch(options.url, {
            method: options.method || "GET",
            headers: options.headers || {},
            body: options.data,
          }).then(async res => {
            const responseText = await res.text();
            if (options.onload) options.onload({ status: res.status, responseText });
          }).catch(err => {
            if (options.onerror) options.onerror(err);
          });
          inFlight.push(p);
        },
        GM_addStyle: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        matchMedia: () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
        showSaveFilePicker: () => Promise.resolve(handle),
        indexedDB: {
          open() {
            const opening = {
              result: {
                transaction: () => ({
                  objectStore: () => ({
                    get() {
                      const reading = { result: handle };
                      queueMicrotask(() => reading.onsuccess());
                      return reading;
                    },
                    put() {},
                  }),
                }),
              },
            };
            queueMicrotask(() => opening.onsuccess());
            return opening;
          },
        },
      };
      context.window = context;
      context.self = context;
      saved.set("clankers-arena-state-hinted", true);
      vm.runInNewContext(source, context, { filename: "arena.user.js" });

      const drain = async () => {
        for (let i = 0; i < 6; i += 1) {
          const batch = inFlight;
          inFlight = [];
          await Promise.all(batch);
          await new Promise(setImmediate);
        }
      };
      const tick = () => timers.forEach(callback => callback());
      const panel = () => body.children.find(child => child.id === "clankers-state-panel") || null;
      const receiptKey = "clankers-arena-state-receipt-r-arena-11223344-r";

      await drain();
      menus.get("State - choose the file")();
      await drain();
      assert.equal(writes.length, 1, "initial file selection writes and confirms the first snapshot");
      const firstReceipt = structuredClone(saved.get(receiptKey));
      const firstServer = await callPy({ op: "inspect" });
      assert.ok(firstReceipt && firstReceipt.lastsave);
      assert.equal(firstReceipt.lastsave, firstServer.lastsave);
      assert.equal(firstReceipt.beforelastsave, null);

      await callPy({ op: "mutate" });
      tick();
      await drain();
      assert.equal(writes.length, 2, "second autosave writes the mutated state");
      const secondReceipt = structuredClone(saved.get(receiptKey));
      const secondServer = await callPy({ op: "inspect" });
      assert.equal(secondReceipt.lastsave, secondServer.lastsave);
      assert.equal(secondReceipt.beforelastsave, firstReceipt.lastsave);

      await callPy({ op: "diverge" });
      tick();
      await drain();
      assert.equal(writes.length, 2, "diverged server stamps block automatic overwrite");
      assert.equal(panel(), null);
      const divergedServer = await callPy({ op: "inspect" });
      assert.equal(divergedServer.backup_notes.length, 1, "mismatch auto-uploads backup once to inbox");
      assert.equal(divergedServer.backup_notes[0].quiet, 1, "backup note is non-user-visible");
      assert.equal(divergedServer.backup_notes[0].blocking, 1, "backup note requires agent ack");
      assert.equal(divergedServer.backup_notes[0].type, "state-backup");
      assert.equal(divergedServer.visible_notes.includes(divergedServer.backup_notes[0].id), false);
      assert.match(divergedServer.backup_notes[0].text, /arena-preview state compare/);
      assert.match(divergedServer.backup_notes[0].text, /arena-preview state import/);
      assert.equal(divergedServer.backup_notes[0].attachments.length, 1);
      tick();
      await drain();
      const divergedAgain = await callPy({ op: "inspect" });
      assert.equal(divergedAgain.backup_notes.length, 1, "repeated ticks on same mismatch do not re-upload");

      menus.get("State - force save")();
      await drain();
      assert.equal(writes.length, 3, "Force save writes and re-synchronizes after divergence");
      assert.equal(panel(), null);
      const thirdReceipt = structuredClone(saved.get(receiptKey));

      const imported = await callPy({ op: "import", text: fileText });
      assert.deepEqual(imported.counts, { notes: 3, tasks: 1, answers: 0, reports: 1 });
      assert.ok(imported.report_source && imported.report_source.endsWith("sample-report.md"));
      assert.equal(imported.history_count, 2);
      assert.equal(imported.lastsave, thirdReceipt.beforelastsave);

      const clearedResp = await callPy({ op: "clear" });
      assert.equal(clearedResp.force, true, "clear_state sets force=true on userscript snapshot");
      tick();
      await drain();
      assert.equal(writes.length, 4, "server-side force flag writes cleared state without mismatch prompt");
      const afterClearServer = await callPy({ op: "inspect" });
      assert.equal(afterClearServer.force, false, "confirmation clears force flag");

      const restoredResp = await callPy({ op: "restore_prev" });
      assert.equal(restoredResp.force, true, "restore_state sets force=true on userscript snapshot");
      tick();
      await drain();
      assert.equal(writes.length, 5, "server-side force flag writes restored state without mismatch prompt");
      assert.match(fileText, /third-note/);
    } finally {
      await callPy({ op: "quit" }).catch(() => {});
    }
  });
}

{
  const { test } = require("node:test");
  test("configurable timers, dropped stale inner VERSION, and draggable Lucide settings modal", () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const checkSaved = new Map();
    const checkContext = {
      console,
      URL,
      GM_getValue: (k, fallback) => (checkSaved.has(k) ? checkSaved.get(k) : fallback),
      GM_setValue(k, v) { checkSaved.set(k, v); },
      setTimeout: () => 0,
      clearTimeout() {},
      setInterval: () => 0,
      clearInterval() {},
      addEventListener() {},
      removeEventListener() {},
    };
    vm.runInNewContext(source, checkContext);
    assert.equal(checkContext.CLANKERS_CHECKS.tabTitle.VERSION, undefined, "stale inner VERSION constant is dropped from tabTitle");

    const saved = new Map([
      ["auto-scroll", true],
      ["auto-wake", true],
      ["state-download", true],
      ["clankers-arena-state-watch-ms", 12000],
      ["clankers-arena-state-panel-ms", 3500],
      ["clankers-arena-wake-delay-ms", 1200],
      ["clankers-arena-http-jitter-ms", 4000],
    ]);
    const timeouts = [];
    const intervals = [];
    const windowListeners = new Map();
    let modalNode = null;

    const makeElement = (tag) => ({
      tag,
      id: "",
      type: "",
      value: "",
      checked: false,
      className: "",
      textContent: "",
      style: { cssText: "", left: "", top: "", right: "" },
      attrs: {},
      listeners: {},
      children: [],
      parentElement: null,
      isConnected: true,
      setAttribute(name, value) {
        this.attrs[name] = String(value);
        if (name === "id") this.id = String(value);
      },
      getAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
      },
      appendChild(child) {
        child.parentElement = this;
        this.children.push(child);
        if (child.id === "clankers-settings-modal") modalNode = child;
        return child;
      },
      remove() {
        this.isConnected = false;
        if (this === modalNode) modalNode = null;
        if (this.parentElement && Array.isArray(this.parentElement.children)) {
          const idx = this.parentElement.children.indexOf(this);
          if (idx >= 0) this.parentElement.children.splice(idx, 1);
        }
      },
      addEventListener(name, fn) {
        this.listeners[name] = fn;
      },
      closest() {
        return null;
      },
      getBoundingClientRect() {
        return { left: 240, top: 80, width: 380, height: 420 };
      },
      querySelector(sel) {
        for (const child of this.children) {
          if (sel === "[data-clankers-autoscroll-toggle]" && child.attrs["data-clankers-autoscroll-toggle"]) return child;
          if (sel === "[data-clankers-settings-toggle]" && child.attrs["data-clankers-settings-toggle"]) return child;
          if (sel === "[data-clankers-settings-drag]" && child.attrs["data-clankers-settings-drag"]) return child;
          if (sel === "[data-clankers-settings-close]" && child.attrs["data-clankers-settings-close"]) return child;
          if (child.querySelector) {
            const hit = child.querySelector(sel);
            if (hit) return hit;
          }
        }
        return null;
      },
      querySelectorAll(sel) {
        const out = [];
        const visit = (node) => {
          for (const child of node.children || []) {
            if (sel === "input, select" && (child.tag === "input" || child.tag === "select")) out.push(child);
            if (sel === "path" && child.tag === "path") out.push(child);
            if (sel === "section" && child.tag === "section") out.push(child);
            if (sel === "button" && child.tag === "button") out.push(child);
            visit(child);
          }
        };
        visit(this);
        return out;
      },
    });

    const row = makeElement("div");
    const stopButton = makeElement("button");
    stopButton.setAttribute("aria-label", "Stop generating");
    row.appendChild(stopButton);
    row.insertBefore = function (node, ref) {
      node.parentElement = this;
      const idx = this.children.indexOf(ref);
      if (idx >= 0) this.children.splice(idx, 0, node);
      else this.children.push(node);
      return node;
    };

    const body = makeElement("body");
    const doc = {
      documentElement: makeElement("html"),
      body,
      title: "Arena",
      hidden: false,
      getElementById(id) {
        return id === "clankers-settings-modal" ? modalNode : null;
      },
      querySelector() { return null; },
      querySelectorAll(sel) {
        return sel === "button[aria-label]" ? [stopButton] : [];
      },
      createElement: (tag) => makeElement(tag),
      createElementNS: (_ns, tag) => makeElement(tag),
    };

    const context = {
      console,
      URL,
      Math: Object.assign(Object.create(Math), { random: () => 0.999999 }),
      Date: { now: () => 10000 },
      location: { pathname: "/c/session", href: "https://arena.ai/c/session", origin: "https://arena.ai", host: "arena.ai" },
      document: doc,
      window: {
        innerWidth: 1280,
        innerHeight: 800,
        addEventListener(name, fn) { windowListeners.set(name, fn); },
        removeEventListener(name) { windowListeners.delete(name); },
      },
      getComputedStyle() { return { display: "block", visibility: "visible", overflowY: "auto" }; },
      MutationObserver: class { observe() {} disconnect() {} },
      ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
      requestAnimationFrame() { return 1; },
      cancelAnimationFrame() {},
      setTimeout(fn, ms) { timeouts.push({ fn, ms }); return timeouts.length; },
      clearTimeout() {},
      setInterval(fn, ms) { intervals.push({ fn, ms }); return intervals.length; },
      clearInterval() {},
      GM_getValue(key, fallback) { return saved.has(key) ? saved.get(key) : fallback; },
      GM_setValue(key, value) { saved.set(key, value); },
      GM_registerMenuCommand() { return 1; },
      GM_unregisterMenuCommand() {},
    };

    vm.runInNewContext(source, context);

    const watchInterval = intervals.find((entry) => entry.ms === 12000);
    assert.ok(watchInterval, "state-download timer uses configured 12000ms watch interval");
    watchInterval.fn();
    assert.ok(
      timeouts.some((entry) => entry.ms === 3999),
      "jitteredTimer uses configured 4000ms jitter range",
    );

    const autoIndex = row.children.findIndex((el) => el.attrs["data-clankers-autoscroll-toggle"] === "true");
    const settingsIndex = row.children.findIndex((el) => el.attrs["data-clankers-settings-toggle"] === "true");
    const stopIndex = row.children.indexOf(stopButton);
    assert.ok(autoIndex >= 0, "auto-scroll button is in the row");
    assert.equal(settingsIndex, autoIndex + 1, "Lucide settings button sits right after the auto-scroll button");
    assert.equal(stopIndex, settingsIndex + 1, "settings button sits before Stop generating");

    const autoButton = row.children[autoIndex];
    const autoSvg = autoButton.children[0];
    assert.equal(
      autoSvg.attrs.class,
      "lucide lucide-arrow-down-to-line",
      "auto-scroll button renders the Lucide arrow-down-to-line SVG",
    );
    assert.equal(autoSvg.attrs["stroke-width"], "2", "Lucide icon uses stroke-width 2");
    const settingsButton = row.children[settingsIndex];
    const settingsSvg = settingsButton.children[0];
    assert.equal(settingsButton.attrs["aria-pressed"], "false", "settings toggle starts unpressed");
    assert.equal(
      settingsSvg.attrs.class,
      "lucide lucide-settings",
      "settings button renders the Lucide settings SVG",
    );
    assert.equal(settingsSvg.children.length, 2, "Lucide settings icon has path and circle");
    assert.equal(settingsSvg.children[1].attrs.r, "3", "Lucide settings icon uses a circle center");

    settingsButton.listeners.click();
    assert.ok(modalNode, "clicking the settings button opens the settings modal");
    assert.equal(settingsButton.attrs["aria-pressed"], "true", "settings button shows pressed while modal is open");

    const dragHeader = modalNode.querySelector("[data-clankers-settings-drag]");
    assert.ok(dragHeader, "settings modal has a draggable header");
    const closeButton = modalNode.querySelector("[data-clankers-settings-close]");
    assert.ok(closeButton, "settings modal header includes a close button");
    assert.equal(closeButton.attrs["aria-label"], "Close settings", "close button carries accessible label");
    assert.equal(
      closeButton.children[0].attrs.class,
      "lucide lucide-x",
      "close button renders the Lucide x SVG",
    );
    assert.equal(closeButton.querySelectorAll("path").length, 2, "close button renders a 2-path Lucide X icon");
    dragHeader.listeners.mousedown({ button: 0, clientX: 300, clientY: 100, preventDefault() {} });
    windowListeners.get("mousemove")({ clientX: 420, clientY: 190 });
    windowListeners.get("mouseup")();
    assert.equal(modalNode.style.left, "360px", "dragging the modal header updates left position");
    assert.equal(modalNode.style.top, "170px", "dragging the modal header updates top position");

    const sections = modalNode.querySelectorAll("section").map((sec) => sec.attrs["data-settings-section"]);
    assert.deepEqual(
      sections,
      ["Composer", "Page", "Proxy", "State", "Steering", "Transcript", "Userscript"],
      "settings modal groups settings into alphabetized sections",
    );

    const allInputs = modalNode.querySelectorAll("input, select");
    const allButtons = modalNode.querySelectorAll("button");
    for (const actionId of ["choose-state-file", "force-save", "trim-now", "post-key-now"]) {
      assert.ok(
        allButtons.some((btn) => btn.attrs["data-settings-action"] === actionId),
        `settings modal exposes action button ${actionId}`,
      );
    }
    for (const key of [
      "clankers-arena-proxy-host",
      "clankers-arena-preview-proxy-host",
      "clankers-arena-proxy-master",
      "clankers-arena-trim-keep",
      "clankers-arena-trim-cap",
      "clankers-arena-trim-interval-ms",
      "clankers-arena-title-interval-ms",
      "clankers-arena-state-reset-window",
      "clankers-arena-preview-drawer-lock",
      "clankers-arena-preview-drawer-width-px",
      "clankers-arena-log-level",
      "clankers-arena-userscript-paused",
      "clankers-arena-show-settings-button",
    ]) {
      assert.ok(
        allInputs.some((el) => el.attrs["data-setting-key"] === key),
        `settings modal exposes setting ${key}`,
      );
    }
    const drawerLockInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-preview-drawer-lock",
    );
    const drawerWidthInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-preview-drawer-width-px",
    );
    assert.ok(drawerLockInput, "settings modal exposes preview drawer width lock toggle");
    assert.equal(drawerLockInput.type, "checkbox", "preview drawer width lock uses a checkbox toggle");
    assert.equal(drawerLockInput.checked, true, "preview drawer width lock defaults to enabled");
    assert.ok(drawerWidthInput, "settings modal exposes preview drawer width slider");
    assert.equal(drawerWidthInput.type, "range", "preview drawer width uses a range slider");
    assert.equal(drawerWidthInput.value, "1398", "preview drawer width slider defaults to 1398 px");
    drawerWidthInput.value = "1240";
    drawerWidthInput.listeners.change();
    assert.equal(
      saved.get("clankers-arena-preview-drawer-width-px"),
      1240,
      "changing preview drawer width slider persists pixel width",
    );
    drawerLockInput.checked = false;
    drawerLockInput.listeners.change();
    assert.equal(
      saved.get("clankers-arena-preview-drawer-lock"),
      false,
      "toggling preview drawer width lock checkbox persists boolean",
    );
    const wakeMinInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-wake-delay-min-ms",
    );
    const wakeMaxInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-wake-delay-ms",
    );
    const keepMinInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-keep-working-delay-min-ms",
    );
    const keepMaxInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-keep-working-delay-ms",
    );
    assert.ok(wakeMinInput && wakeMaxInput, "settings modal renders min and max sliders for Wake-up delay");
    assert.equal(wakeMinInput.type, "range", "Wake-up min uses a range slider");
    assert.equal(wakeMaxInput.type, "range", "Wake-up max uses a range slider");
    assert.equal(wakeMinInput.attrs["data-range-role"], "min", "Wake-up left slider is min");
    assert.equal(wakeMaxInput.attrs["data-range-role"], "max", "Wake-up right slider is max");
    assert.ok(
      allInputs.indexOf(wakeMinInput) < allInputs.indexOf(wakeMaxInput),
      "Wake-up min slider sits on the left before max slider",
    );
    assert.ok(keepMinInput && keepMaxInput, "settings modal renders min and max sliders for Keep working delay");
    assert.equal(keepMinInput.type, "range", "Keep working min uses a range slider");
    assert.equal(keepMaxInput.type, "range", "Keep working max uses a range slider");
    assert.ok(
      allInputs.indexOf(keepMinInput) < allInputs.indexOf(keepMaxInput),
      "Keep working min slider sits on the left before max slider",
    );
    assert.equal(
      keepMinInput.parentElement,
      keepMaxInput.parentElement,
      "min and max inputs share a single dual-thumb slider track",
    );
    assert.equal(
      keepMinInput.parentElement.attrs["data-dual-slider"],
      "true",
      "shared slider track marks data-dual-slider=true",
    );
    const keepRail = keepMinInput.parentElement.children[0];
    const keepFill = keepRail.children[0];
    assert.equal(
      keepFill.attrs["data-slider-fill"],
      "true",
      "dual-thumb slider track renders a filled range bar between the two thumbs",
    );
    const keepTicks = keepRail.children[1];
    assert.equal(
      keepTicks.attrs["data-slider-ticks"],
      "true",
      "dual-thumb slider track renders integer snap point ticks",
    );
    assert.equal(
      keepTicks.children.length,
      61,
      "0..60 second slider renders 61 integer snap point ticks",
    );
    assert.equal(
      keepMinInput.attrs.list,
      "clankers-snap-clankers-arena-keep-working-delay-min-ms",
      "min slider links to integer snap datalist",
    );
    assert.equal(
      keepMaxInput.attrs.list,
      "clankers-snap-clankers-arena-keep-working-delay-min-ms",
      "max slider links to the same integer snap datalist",
    );

    keepMinInput.value = "2";
    keepMinInput.listeners.change();
    keepMaxInput.value = "9";
    keepMaxInput.listeners.change();
    assert.equal(saved.get("clankers-arena-keep-working-delay-min-ms"), 2000, "changing Keep working min slider persists ms");
    assert.equal(saved.get("clankers-arena-keep-working-delay-ms"), 9000, "changing Keep working max slider persists ms");
    assert.ok(parseFloat(keepFill.style.width) > 0, "filled range bar updates its width between min and max thumbs");

    const watchInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-state-watch-ms",
    );
    assert.ok(watchInput, "settings modal exposes configurable state watch interval input");
    watchInput.value = "25";
    watchInput.listeners.change();
    assert.equal(saved.get("clankers-arena-state-watch-ms"), 25000, "changing modal input persists milliseconds");
    assert.ok(intervals.some((entry) => entry.ms === 25000), "changing state watch interval restarts timer");

    closeButton.listeners.click();
    assert.equal(modalNode, null, "clicking the Lucide X close button closes the modal");
    assert.equal(settingsButton.attrs["aria-pressed"], "false", "settings button resets aria-pressed on close");

    for (const rel of ["userscripts/arena.user.js", "userscripts/chatgpt.user.js", "userscripts/README.md"]) {
      const content = fs.readFileSync(path.join(__dirname, "../..", rel), "utf8");
      assert.ok(!new RegExp("[\\u2013\\u2014]|\\\\u201[34]", "i").test(content), `${rel} must not contain long dashes`);
    }

    const checks = checkContext.CLANKERS_CHECKS;
    assert.equal(
      checks.promptFill.PREVIEW_PROXY_HOST_KEY,
      "clankers-arena-preview-proxy-host",
      "exposes clankers-arena-preview-proxy-host setting key"
    );
    assert.equal(
      checks.promptFill.previewProxyHost("", "https://arena-proxy.taile06e44.ts.net"),
      "https://arena-preview.taile06e44.ts.net",
      "derives arena-preview.<tailnet>.ts.net from clankers-arena-proxy-host when unset"
    );
    assert.equal(
      checks.promptFill.previewProxyHost("https://custom-preview.taile06e44.ts.net/", "https://arena-proxy.taile06e44.ts.net"),
      "https://custom-preview.taile06e44.ts.net",
      "explicit preview proxy host overrides derived default"
    );
    assert.equal(
      checks.promptFill.previewProxyHost("custom-preview.taile06e44.ts.net", ""),
      "https://custom-preview.taile06e44.ts.net",
      "bare hostname normalizes to https"
    );
    const fakeDoc = {
      querySelectorAll(sel) {
        if (sel === "span") {
          return [
            {
              className: "text-text-secondary min-w-0 max-w-[180px] truncate text-sm leading-[1.2]",
              textContent: "clankers - Web Preview",
            },
          ];
        }
        if (sel === "iframe") {
          return [
            {
              src: "https://sbx-otherport.arena.site/",
              getAttribute(name) {
                return name === "title" ? "App preview on port 3000" : "";
              },
            },
          ];
        }
        if (sel === "a") {
          return [
            {
              href: "https://sbx-linkport.arena.site/preview",
            },
          ];
        }
        return [];
      },
    };
    assert.deepEqual(
      JSON.parse(JSON.stringify(checks.promptFill.discoverPreviews(fakeDoc))),
      [
        { url: "https://sbx-otherport.arena.site/", name: "clankers - Web Preview" },
        { url: "https://sbx-linkport.arena.site/", name: "clankers - Web Preview" },
      ],
      "discovers non-steering preview iframe and link URLs on any port along with the header span name"
    );
    const unavailableDoc = {
      querySelectorAll(sel) {
        if (sel === "span") {
          return [
            {
              className: "text-text-secondary min-w-0 max-w-[180px] truncate text-sm leading-[1.2]",
              textContent: "Preview Unavailable",
            },
          ];
        }
        if (sel === "iframe") {
          return [{ src: "https://sbx-dead.arena.site/" }];
        }
        return [];
      },
    };
    assert.deepEqual(
      JSON.parse(JSON.stringify(checks.promptFill.discoverPreviews(unavailableDoc))),
      [],
      "skips preview URLs when the header says Preview Unavailable"
    );
    const steeringAndDemoDoc = {
      querySelectorAll(sel) {
        if (sel === "span") {
          return [
            {
              className: "text-text-secondary min-w-0 max-w-[180px] truncate text-sm leading-[1.2]",
              textContent: "Demo App",
            },
          ];
        }
        if (sel === "iframe[title]" || sel === "iframe") {
          return [
            {
              src: "https://sbx-steering8000.arena.site/",
              getAttribute(name) {
                return name === "title" ? "App preview on port 8000" : "";
              },
            },
            {
              src: "https://sbx-demo3000.arena.site/",
              getAttribute(name) {
                return name === "title" ? "App preview on port 3000" : "";
              },
            },
          ];
        }
        return [];
      },
    };
    assert.deepEqual(
      JSON.parse(JSON.stringify(checks.promptFill.discoverPreviews(steeringAndDemoDoc, "clankers"))),
      [
        { url: "https://sbx-steering8000.arena.site/", name: "clankers - Steering" },
        { url: "https://sbx-demo3000.arena.site/", name: "Demo App" },
      ],
      "uses the arena-skill preview UI repo name for the steering preview while keeping DOM header labels for other previews"
    );
    const reconciled = checks.promptFill.reconcileRecentPreviews(
      { "clankers - Steering": "https://sbx-old8000.arena.site/" },
      [{ url: "https://sbx-steering8000.arena.site/", name: "clankers - Steering" }]
    );
    assert.deepEqual(
      JSON.parse(JSON.stringify(reconciled)),
      {
        byName: { "clankers - Steering": "https://sbx-steering8000.arena.site/" },
        invalidated: ["https://sbx-old8000.arena.site/"],
      },
      "invalidates the previous preview URL when a new URL arrives for the same preview name"
    );
    const makePollRow = (stderrText) => {
      const pres = [{ textContent: "$ arena-preview poll" }];
      if (stderrText) {
        pres.push({ textContent: stderrText });
      }
      return {
        getAttribute: () => "",
        querySelector: (sel) => (sel === "pre" ? pres[0] : null),
        querySelectorAll: (sel) => (sel === "pre" ? pres : []),
      };
    };
    assert.equal(checks.tabTitle.emojiForRow(makePollRow("")), "\uD83D\uDCA4");
    assert.equal(
      checks.tabTitle.emojiForRow(
        makePollRow(
          "poll max 1799 s; bash timeout 1800 s.\nrun suite-readme-shot running 39s\n"
        )
      ),
      checks.tabTitle.BASH_EMOJI
    );
    assert.equal(
      checks.openSteering.PREVIEW_DRAWER_SELECTOR,
      "body > div:nth-child(4) > div > main > div > div > div.absolute.bottom-0.end-0.top-0.z-10.overflow-clip > div"
    );
    assert.equal(checks.openSteering.PREVIEW_DRAWER_WIDTH, "1398px");
    let drawerWidth = "720px";
    let drawerPriority = "";
    const drawerNode = {
      style: {
        getPropertyValue(prop) {
          return prop === "width" ? drawerWidth : "";
        },
        getPropertyPriority(prop) {
          return prop === "width" ? drawerPriority : "";
        },
        setProperty(prop, val, priority) {
          if (prop === "width") {
            drawerWidth = val;
            drawerPriority = priority || "";
          }
        },
      },
    };
    const drawerDoc = {
      querySelector(sel) {
        return sel === checks.openSteering.PREVIEW_DRAWER_SELECTOR ? drawerNode : null;
      },
    };
    assert.equal(checks.openSteering.findPreviewDrawer(drawerDoc), drawerNode);
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(drawerDoc), true);
    assert.equal(drawerWidth, "1398px");
    assert.equal(drawerPriority, "important");
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(drawerDoc), false);

    function makeStyleBox(initialProp, initialVal) {
      const props = new Map([[initialProp, { val: initialVal, priority: "" }]]);
      return {
        props,
        style: {
          getPropertyValue(prop) {
            return props.has(prop) ? props.get(prop).val : "";
          },
          getPropertyPriority(prop) {
            return props.has(prop) ? props.get(prop).priority : "";
          },
          setProperty(prop, val, priority) {
            props.set(prop, { val: String(val || ""), priority: String(priority || "") });
          },
        },
      };
    }
    let drawerOpen = true;
    const fullDrawer = makeStyleBox("width", "680px");
    const headerBox = makeStyleBox("right", "680px");
    const transcriptBox = makeStyleBox("padding-right", "680px");
    const composerBox = makeStyleBox("padding-right", "680px");
    const mainColNode = {
      querySelector(sel) {
        if (sel.includes("Collapse workspace sidebar")) {
          return drawerOpen ? {} : null;
        }
        if (sel.includes("Expand workspace sidebar") || sel.includes("Open workspace")) {
          return drawerOpen ? null : {};
        }
        if (sel === "div.absolute.start-0.top-0.z-20") return headerBox;
        if (sel.includes('[data-perf-target="transcript"]')) return transcriptBox;
        if (sel === "div.flex.min-h-0.flex-1.flex-col > div.shrink-0") return composerBox;
        return null;
      },
    };
    const fullDoc = {
      querySelector(sel) {
        if (sel === checks.openSteering.PREVIEW_DRAWER_SELECTOR) return fullDrawer;
        if (sel === checks.openSteering.PREVIEW_MAIN_SELECTOR) return mainColNode;
        return null;
      },
    };
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(fullDoc), true);
    assert.equal(fullDrawer.style.getPropertyValue("width"), "1398px");
    assert.equal(headerBox.style.getPropertyValue("right"), "1398px");
    assert.equal(transcriptBox.style.getPropertyValue("padding-right"), "1398px");
    assert.equal(composerBox.style.getPropertyValue("padding-right"), "1398px");
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(fullDoc), false);
    drawerOpen = false;
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(fullDoc), true);
    assert.equal(fullDrawer.style.getPropertyValue("width"), "0px");
    assert.equal(headerBox.style.getPropertyValue("right"), "0px");
    assert.equal(transcriptBox.style.getPropertyValue("padding-right"), "0px");
    assert.equal(composerBox.style.getPropertyValue("padding-right"), "0px");
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(fullDoc), false);

    let previewOpenInSidebar = true;
    const outerDrawerBox = makeStyleBox("width", "1153px");
    const innerDrawerBox = makeStyleBox("width", "1153px");
    innerDrawerBox.parentElement = outerDrawerBox;
    innerDrawerBox.querySelector = function (sel) {
      if (sel.includes("Close preview") || sel.includes("App preview")) {
        return previewOpenInSidebar ? {} : null;
      }
      if (sel.includes("Workspace card views")) {
        return previewOpenInSidebar ? null : {};
      }
      return null;
    };
    const transcriptMsgCol = {
      classList: {
        contains(cls) {
          return cls === "max-w-3xl" || cls === "shrink-0";
        },
      },
      parentElement: {
        getAttribute(attr) {
          return attr === "role" ? "log" : "";
        },
      },
      style: {
        val: "1398px",
        priority: "important",
        getPropertyValue(prop) {
          return prop === "padding-right" ? this.val : "";
        },
        getPropertyPriority(prop) {
          return prop === "padding-right" ? this.priority : "";
        },
        setProperty(prop, v, p) {
          if (prop === "padding-right") {
            this.val = v;
            this.priority = p || "";
          }
        },
        removeProperty(prop) {
          if (prop === "padding-right") {
            this.val = "";
            this.priority = "";
          }
        },
      },
    };
    const realHeaderBox = makeStyleBox("right", "1153px");
    const realTranscriptBox = makeStyleBox("padding-right", "1153px");
    const realComposerBox = makeStyleBox("padding-right", "1153px");
    const realMainCol = {
      querySelector(sel) {
        if (sel.includes("Collapse workspace sidebar")) return {};
        if (sel === "div.absolute.start-0.top-0.z-20") return realHeaderBox;
        if (sel.includes('[data-perf-target="transcript"]')) return realTranscriptBox;
        return null;
      },
      querySelectorAll(sel) {
        if (sel === "div.flex.min-h-0.flex-1.flex-col > div.shrink-0") {
          return [transcriptMsgCol, realComposerBox];
        }
        return [];
      },
    };
    const realDoc = {
      querySelector(sel) {
        if (sel === checks.openSteering.PREVIEW_DRAWER_SELECTOR) return innerDrawerBox;
        if (sel === checks.openSteering.PREVIEW_MAIN_SELECTOR) return realMainCol;
        return null;
      },
    };
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(realDoc), true);
    assert.equal(outerDrawerBox.style.getPropertyValue("width"), "1398px");
    assert.equal(innerDrawerBox.style.getPropertyValue("width"), "1398px");
    assert.equal(realHeaderBox.style.getPropertyValue("right"), "1398px");
    assert.equal(realTranscriptBox.style.getPropertyValue("padding-right"), "1398px");
    assert.equal(realComposerBox.style.getPropertyValue("padding-right"), "1398px");
    assert.equal(
      transcriptMsgCol.style.getPropertyValue("padding-right"),
      "",
      "transcript messages column (max-w-3xl) must never receive drawer padding-right",
    );
    previewOpenInSidebar = false;
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(realDoc), true);
    assert.equal(outerDrawerBox.style.getPropertyValue("width"), "256px");
    assert.equal(innerDrawerBox.style.getPropertyValue("width"), "256px");
    assert.equal(realHeaderBox.style.getPropertyValue("right"), "256px");
    assert.equal(realTranscriptBox.style.getPropertyValue("padding-right"), "256px");
    assert.equal(realComposerBox.style.getPropertyValue("padding-right"), "256px");
    assert.equal(
      checks.openSteering.enforcePreviewDrawerWidth(realDoc),
      false,
      "second closed-drawer pass must not mutate styles again",
    );
    previewOpenInSidebar = true;
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(realDoc), true);
    checkContext.GM_setValue("clankers-arena-preview-drawer-lock", false);
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(realDoc), true);
    assert.equal(
      checks.openSteering.enforcePreviewDrawerWidth(realDoc),
      false,
      "second unlocked-drawer pass must not mutate styles again (prevents MutationObserver loop)",
    );
    checkContext.GM_setValue("clankers-arena-preview-drawer-lock", true);

    let styleTextWrites = 0;
    let styleAttrWrites = 0;
    let storedCss = "";
    const styleEl = {
      id: "",
      setAttribute() {
        styleAttrWrites += 1;
      },
      get textContent() {
        return storedCss;
      },
      set textContent(val) {
        styleTextWrites += 1;
        storedCss = String(val || "");
      },
    };
    let headStyle = null;
    const styleDoc = {
      head: {
        appendChild(node) {
          headStyle = node;
        },
      },
      createElement() {
        return styleEl;
      },
      getElementById(id) {
        return id === "clankers-preview-drawer-style" ? headStyle : null;
      },
    };
    assert.equal(typeof checks.openSteering.ensurePreviewDrawerStyle, "function");
    checks.openSteering.ensurePreviewDrawerStyle(styleDoc);
    assert.equal(styleTextWrites, 1, "first ensurePreviewDrawerStyle writes CSS once");
    checks.openSteering.ensurePreviewDrawerStyle(styleDoc);
    assert.equal(
      styleTextWrites,
      1,
      "second ensurePreviewDrawerStyle must not rewrite textContent when CSS is unchanged",
    );
    assert.equal(
      styleAttrWrites,
      1,
      "second ensurePreviewDrawerStyle must not rewrite attributes when style node already exists",
    );

    const allowedBoard = checks.board.applyBoardAction(null, {
      action: "allow",
      session_id: "arena/bdf20cf5-clankers",
    }).board;
    assert.equal(allowedBoard.sessions.length, 1);
    assert.equal(allowedBoard.sessions[0].session_id, "bdf20cf5-clankers");
    const syncedWorker = checks.board.mergePreviewBoard(allowedBoard, {
      session_id: "bdf20cf5-clankers",
      repo: "clankers",
      branch: "arena/bdf20cf5-clankers",
      allowed_sessions: ["bdf20cf5-clankers", "293da56c-clankers"],
      main_session_id: "293da56c-clankers",
      sessions: [
        {
          session_id: "bdf20cf5-clankers",
          repo: "clankers",
          branch: "arena/bdf20cf5-clankers",
          status: "polling",
          polling: true,
          updated_at: "2026-10-25T15:00:00Z",
        },
      ],
      entries: [],
      wakes: {},
    });
    const workerRow = syncedWorker.sessions.find((r) => r.session_id === "bdf20cf5-clankers");
    assert.equal(workerRow.polling, true);
    const wokenAll = checks.board.applyBoardAction(syncedWorker, {
      action: "wake",
      target: "all-polling",
      at: "2026-10-25T15:00:05Z",
    }).board;
    assert.equal(wokenAll.wakes["bdf20cf5-clankers"], "2026-10-25T15:00:05Z");
    assert.equal(
      wokenAll.sessions.find((r) => r.session_id === "bdf20cf5-clankers").polling,
      false,
    );
    const afterWakeConsumed = checks.board.mergePreviewBoard(wokenAll, {
      session_id: "bdf20cf5-clankers",
      repo: "clankers",
      branch: "arena/bdf20cf5-clankers",
      allowed_sessions: ["bdf20cf5-clankers", "293da56c-clankers"],
      main_session_id: "293da56c-clankers",
      sessions: [
        {
          session_id: "bdf20cf5-clankers",
          repo: "clankers",
          branch: "arena/bdf20cf5-clankers",
          status: "active",
          polling: false,
          updated_at: "2026-10-25T15:00:06Z",
        },
      ],
      entries: [],
      wakes: {},
    });
    assert.equal(afterWakeConsumed.wakes["bdf20cf5-clankers"], undefined);
    const wokenFromMainServer = checks.board.mergePreviewBoard(afterWakeConsumed, {
      session_id: "293da56c-clankers",
      repo: "clankers",
      branch: "arena/293da56c-clankers",
      allowed_sessions: ["bdf20cf5-clankers", "293da56c-clankers"],
      main_session_id: "293da56c-clankers",
      sessions: [
        {
          session_id: "bdf20cf5-clankers",
          repo: "clankers",
          branch: "arena/bdf20cf5-clankers",
          status: "polling",
          polling: true,
          updated_at: "2026-10-25T15:00:07Z",
        },
      ],
      entries: [],
      wakes: { "bdf20cf5-clankers": "2026-10-25T15:00:08Z" },
    });
    assert.equal(wokenFromMainServer.wakes["bdf20cf5-clankers"], "2026-10-25T15:00:08Z");
    assert.equal(
      wokenFromMainServer.sessions.find((r) => r.session_id === "bdf20cf5-clankers").polling,
      false,
    );
    checks.board.writeGlobalBoard(afterWakeConsumed);
    assert.deepEqual(
      JSON.parse(
        JSON.stringify(
          checks.promptFill.discoverPreviews(
            steeringAndDemoDoc,
            "clankers",
            "bdf20cf5-clankers",
          ),
        ),
      ),
      [
        {
          url: "https://sbx-steering8000.arena.site/",
          name: "clankers - Steering (bdf20c)",
        },
        { url: "https://sbx-demo3000.arena.site/", name: "Demo App" },
      ],
      "worker session steering preview carries short session suffix to prevent proxy URL collisions",
    );
      assert.deepEqual(
        JSON.parse(
          JSON.stringify(
            checks.promptFill.discoverPreviews(
              steeringAndDemoDoc,
              "clankers",
              "293da56c-clankers",
            ),
          ),
        ),
        [
          {
            url: "https://sbx-steering8000.arena.site/",
            name: "clankers - Steering",
          },
          { url: "https://sbx-demo3000.arena.site/", name: "Demo App" },
        ],
        "main session steering preview keeps the canonical repo - Steering label",
      );
      assert.equal(
        checks.stateDownload.isWorkerSession(
          afterWakeConsumed,
          "bdf20cf5-clankers",
          null,
        ),
        true,
        "worker session on board is identified as worker even when not checking allowed_sessions or force",
      );
      assert.equal(
        checks.stateDownload.isWorkerSession(
          afterWakeConsumed,
          "unlisted-worker-clankers",
          null,
        ),
        true,
        "non-main session when main_session_id is set is identified as worker",
      );
      assert.equal(
        checks.stateDownload.isWorkerSession(
          { main_session_id: "", allowed_sessions: [] },
          "bdf20cf5-clankers",
          { board: { role: "worker" } },
        ),
        true,
        "autosave payload reporting board.role === worker is identified as worker",
      );
      assert.equal(
        checks.stateDownload.isWorkerSession(
          afterWakeConsumed,
          "293da56c-clankers",
          null,
        ),
        false,
        "main session on board is not identified as worker",
      );
    });
  }



