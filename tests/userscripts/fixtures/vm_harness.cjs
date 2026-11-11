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
    // The prompt fill owns the four proxy entries. The state download owns its two. The auto
    // trim gates its interval line behind the switch alone.
    extraMenus: { "transcript-trim": 1, "prompt-fill": 4, "state-download": 2, "tab-title": 1 },
    // Keep-rows plan, trim cap, and trim-now press stay on menu regardless of switch state.
    alwaysMenus: { "transcript-trim": 3 },
    // Logging, global pause, and show-settings-button stay outside the feature switches.
    globalMenus: 3,
    countMenu: "Transcript - keep ",
    countKey: "clankers-arena-trim-keep",
    baseObservers: 1,
    // Prompt fill owns two timers: paint and key watch. Both ride one switch.
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


function runBundle(requestedDomain) {
for (const [domain, bundle] of Object.entries(bundles)) {
  if (domain !== requestedDomain) continue;
  const { features, labels, countMenu, countKey, baseObservers, featureIntervals } = bundle;
  const offByDefault = new Set(bundle.offByDefault || []);
  const extraMenus = bundle.extraMenus || {};
  const source = fs.readFileSync(
    path.join(__dirname, "../../../userscripts", `${domain}.user.js`), "utf8",
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
    // The owner's shape decision: one module's entries share a prefix, a switch names its state in parentheses. No entry carries a role word.
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

    // The count line belongs to the Transcript group.
    // So it sits with its two switches rather than at the bottom the manager appends it to.
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
  // The global pause stops every feature where it stands.
  // With no reload, the resume brings back the features whose own switch is ON.
  if (domain === "arena") {
    // Storage-failure check above keeps write rejection active. Pause writes again.
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
    // Pause leaves switches alone, so next unpaused load runs them again.
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
}

function loadChecks(file) {
  const source = fs.readFileSync(path.join(__dirname, "../../../userscripts", file), "utf8");
  // `fetch` resolves against the host realm at call time, so one case can drive it. The
  // session store lives in the VM realm too, so a case can plant a saved slug.
  const session = {
    value: null,
    getItem() {
      return session.value;
    },
    setItem(key, value) {
      session.value = value;
    },
  };
  // The manager menu keeps every registered command, so a case can press one by hand.
  const menus = [];
  const values = {};
  const context = {
    GM_getValue: (key, fallback) => Object.hasOwn(values, key) ? values[key] : fallback,
    GM_setValue: (key, value) => { values[key] = value; },
    console,
    URL,
    sessionStorage: session,
    // The bundle asks for GM_download, so the manager hands it over outside a browser too.
    GM_download: function () {},
    GM_registerMenuCommand: function (label, run) {
      menus.push({ label: label, run: run });
    },
    GM_unregisterMenuCommand: function () {},
    fetch: (...args) => globalThis.fetch(...args),
  };
  vm.runInNewContext(source, context, { filename: file });
  return { checks: context.CLANKERS_CHECKS, session, menus, context };
}

module.exports = { bundles, runBundle, loadChecks };
