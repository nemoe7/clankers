// The Arena and ChatGPT bundles carry no checks of their own. Outside a browser each feature publishes its helpers through `exposeChecks`, and this file drives them, so the installed scripts ship runtime code only.
// Run: node --test maintenance/workflows/userscripts.checks.cjs

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function loadChecks(file) {
  const source = fs.readFileSync(path.join(__dirname, "../../userscripts", file), "utf8");
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

function checkArenaLogging(api, menus) {
  assert.equal(typeof api.setLogLevel, "function");
  assert.equal(api.getLogLevel(), "info");
  const lines = [];
  const original = { log: console.log, warn: console.warn, error: console.error };
  for (const method of Object.keys(original)) {
    console[method] = (...args) => lines.push({ method, text: JSON.stringify(args) });
  }
  try {
    const fields = {
      count: 2, repo: "private-repo", filename: "private.ndjson",
      key: "secret-key", message: "secret-message", url: "secret-url", error: "raw-error",
    };
    api.logEvent("state", "saved", fields);
    api.logEvent("state", "saved", fields);
    assert.equal(lines.length, 2, "identical events must remain visible");
    assert.match(lines[0].text, /\[NemoUtils\]\[state\]\[info\] saved/);
    assert.match(lines[0].text, /count/);
    assert.doesNotMatch(lines[0].text, /private|secret|raw-error/);
    api.logEvent("state", "compare", fields, "debug");
    assert.equal(lines.length, 2, "debug must be off by default");
    assert.equal(api.setLogLevel("debug"), true);
    api.logEvent("state", "compare", fields, "debug");
    assert.match(lines.at(-1).text, /private-repo/);
    assert.match(lines.at(-1).text, /private.ndjson/);
    assert.doesNotMatch(lines.at(-1).text, /secret|raw-error/);
    const safeCount = lines.length;
    assert.equal(api.logEvent("state", "secret-message", fields), false);
    assert.equal(lines.length, safeCount, "unknown event names must not reach the console");
    api.logEvent("state", "saved", Object.create({ repo: "secret-message", filename: "secret-key", count: 666 }));
    assert.doesNotMatch(lines.at(-1).text, /secret|666/);
    api.logEvent("state", "saved", { count: "secret-message", code: "raw-error" });
    assert.doesNotMatch(lines.at(-1).text, /secret|raw-error/);
    assert.equal(api.setLogLevel("warn"), true);
    const count = lines.length;
    api.logEvent("state", "saved", fields);
    api.logEvent("state", "failed", fields, "warn");
    api.logEvent("state", "failed", fields, "error");
    assert.equal(lines.length, count + 2);
    assert.equal(lines.at(-2).method, "warn");
    assert.equal(lines.at(-1).method, "error");
    assert.equal(api.setLogLevel("invalid"), false);
    assert.equal(api.getLogLevel(), "warn");
    api.setLogLevel("info");
    let ran = false;
    api.menuItem([], "State — secret-message", () => { ran = true; });
    menus.findLast((entry) => entry.label === "State — secret-message").run();
    assert.equal(ran, true);
    assert.doesNotMatch(lines.at(-1).text, /secret-message/);
    api.registerLogMenu();
    menus.findLast((entry) => entry.label.startsWith("Userscript — log level")).run();
    assert.equal(api.getLogLevel(), "debug");
    for (const method of Object.keys(original)) console[method] = () => { throw Error("closed"); };
    assert.doesNotThrow(() => api.logEvent("state", "failed", fields, "error"));
  } finally {
    Object.assign(console, original);
    api.setLogLevel("info");
  }
  console.log("ok arena logging");
}

function checkLogging(api, menus) {
  var LOG_TAG = api.LOG_TAG;
  var logEvent = api.logEvent;
  var menuItem = api.menuItem;
  // One tag carries every line, so one filter shows the page's story.
  assert.equal(LOG_TAG, "[NemoUtils]");
  var lines = [];
  var original = console.log;
  console.log = function () {
    lines.push(Array.prototype.join.call(arguments, " "));
  };
  try {
    logEvent("feature", "Prompt fill: ON");
    logEvent("fill", "filled composer for clankers");
    logEvent("state", "saved", "detail");
  } finally {
    console.log = original;
  }
  // The module rides a second bracket, so one filter shows one module alone.
  assert.equal(lines[0], "[NemoUtils][feature] Prompt fill: ON");
  assert.equal(lines[1], "[NemoUtils][fill] filled composer for clankers");
  assert.equal(lines[2], "[NemoUtils][state] saved detail");
  // A console that rejects must never break a feature.
  console.log = function () {
    throw new Error("closed console");
  };
  try {
    logEvent("state", "saved");
  } finally {
    console.log = original;
  }
  // Every menu press writes its own line before the command runs.
  if (menuItem) {
    var ran = [];
    var list = [];
    menuItem(list, "State — force save", function () {
      ran.push("save");
    });
    assert.equal(list.length, 1);
    var registered = menus.filter(function (item) {
      return item.label === "State — force save";
    }).pop();
    assert.ok(registered, "the registered entry is reachable by its label");
    assert.equal(registered.label, "State — force save");
    lines.length = 0;
    var pressed = [];
    console.log = function () {
      pressed.push(Array.prototype.join.call(arguments, " "));
    };
    try {
      registered.run();
    } finally {
      console.log = original;
    }
    assert.deepEqual(ran, ["save"]);
    assert.equal(pressed[0], "[NemoUtils][menu] State — force save");
  }
  console.log("ok logging 3");
}

function checkTranscriptAlerts(api) {
  assert.ok(api, "the independent alert submodule must be exposed");
  const selector = '[role="alert"][class~="border-red-500/30"][class~="bg-red-500/10"]';
  assert.equal(api.ALERT_SELECTOR, selector);
  function alert(value = "", priority = "", visible = true) {
    return {
      isConnected: true,
      target: true,
      hidden: false,
      getClientRects() { return visible ? [{}] : []; },
      matches(s) { assert.equal(s, selector); return this.target; },
      style: {
        getPropertyValue() { return value; },
        getPropertyPriority() { return priority; },
        setProperty(key, next, rank) { assert.equal(key, "display"); value = next; priority = rank; },
        removeProperty(key) { assert.equal(key, "display"); value = ""; priority = ""; },
      },
    };
  }
  const first = alert("flex", "important");
  const priorHidden = alert("none", "", false);
  const unrelated = alert(); unrelated.target = false;
  let nodes = [first, priorHidden, unrelated];
  const sync = api.alertVisibility({
    querySelectorAll(s) { assert.equal(s, selector); return nodes.filter((n) => n.target); },
  });
  sync(false);
  assert.equal(first.style.getPropertyValue("display"), "flex");
  sync(true);
  assert.equal(first.style.getPropertyValue("display"), "none");
  assert.equal(first.style.getPropertyPriority("display"), "important");
  assert.equal(priorHidden.style.getPropertyPriority("display"), "");
  assert.equal(unrelated.style.getPropertyValue("display"), "");
  const later = alert(); nodes.push(later);
  first.textContent = "A different error message";
  sync(true); sync(true);
  assert.equal(later.style.getPropertyValue("display"), "none");
  sync(false);
  assert.equal(first.style.getPropertyValue("display"), "flex");
  assert.equal(first.style.getPropertyPriority("display"), "important");
  assert.equal(later.style.getPropertyValue("display"), "");
  assert.equal(priorHidden.style.getPropertyValue("display"), "none");
  const externalHidden = alert("inline", "");
  nodes.push(externalHidden);
  sync(true);
  externalHidden.style.setProperty("display", "none", "");
  sync(false);
  assert.equal(externalHidden.style.getPropertyValue("display"), "none");
  assert.equal(externalHidden.style.getPropertyPriority("display"), "");
  nodes = nodes.filter((n) => n !== externalHidden);
  sync(true);
  later.style.setProperty("display", "grid", "");
  first.target = false;
  sync(true);
  assert.equal(first.style.getPropertyValue("display"), "flex");
  sync(false);
  assert.equal(later.style.getPropertyValue("display"), "grid", "preserve an external style change");
  sync(true); later.isConnected = false; sync(true);
  assert.equal(later.style.getPropertyValue("display"), "grid");
}

function checkPromptFill(api) {
  var isComposerUrl = api.isComposerUrl;
  var slugFromOwnerRepo = api.slugFromOwnerRepo;
  var promptForSlug = api.promptForSlug;
  var shouldWrite = api.shouldWrite;
  var ARENA_MD_URL = api.ARENA_MD_URL;
  var proxyHost = api.proxyHost;
  var keyUrl = api.keyUrl;
  var agentKeyFrom = api.agentKeyFrom;
  var previewBase = api.previewBase;
  var rotateUrl = api.rotateUrl;
  var keyPostUrl = api.keyPostUrl;
  var KEY_WATCH_MS = api.KEY_WATCH_MS;
  var keyNote = api.keyNote;
  var keyChanged = api.keyChanged;
  var keyPostDue = api.keyPostDue;
  var NOTED_KEY = api.NOTED_KEY;
  var fetchJson = api.fetchJson;
  var PREVIEW_FRAME_TITLE = api.PREVIEW_FRAME_TITLE;
  var ROTATE_MIN_SECONDS = api.ROTATE_MIN_SECONDS;
  var ROTATE_DUE_KEY = api.ROTATE_DUE_KEY;
  var rotationDueAt = api.rotationDueAt;
  var rotationWaitMs = api.rotationWaitMs;
  var KEY43 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFG";
  var PROMPT_FILL_URL = api.PROMPT_FILL_URL;
  assert.equal(PROMPT_FILL_URL,
    "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/userscripts/arena-prompt-fill.txt");
  var promptFillText = fs.readFileSync(
    path.join(__dirname, "../../userscripts/arena-prompt-fill.txt"), "utf8").trimEnd();
  var promptSource = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
  assert.equal(promptSource.includes("TEMPLATE_TAIL"), false);
  assert.equal(promptForSlug("clankers", ""), null);
  var prompt = promptForSlug("clankers", promptFillText);
  var promptWithRules = promptForSlug("clankers", promptFillText, "# Rules\n");

  function frames(rows) {
    return {
      querySelectorAll: function (selector) {
        if (selector !== "iframe[title]") return [];
        return rows.map(function (row) {
          return {
            getAttribute: function () {
              return row[0];
            },
            src: row[1],
          };
        });
      },
    };
  }

  var cases = [
    [isComposerUrl("https://arena.ai/agent"), true],
    [isComposerUrl("https://www.arena.ai/agent"), true],
    [isComposerUrl("https://arena.ai/agent?x=1"), true],
    [isComposerUrl("https://arena.ai/agent#x"), true],
    [isComposerUrl("https://arena.ai/agent/"), true],
    [isComposerUrl("https://arena.ai/agent//"), true],
    [isComposerUrl("https://arena.ai/agent/foo"), false],
    [isComposerUrl("https://arena.ai/agent/foo/"), false],
    [isComposerUrl("https://other.example/agent"), false],
    [slugFromOwnerRepo("nemoe7/clankers"), "clankers"],
    [slugFromOwnerRepo("  org/repo  "), "repo"],
    [slugFromOwnerRepo("main"), null],
    [slugFromOwnerRepo("a/"), null],
    [slugFromOwnerRepo("/b"), null],
    [slugFromOwnerRepo("a/b/c"), null],
    // The repo name leads the fetched template. The rules file follows it when available.
    [prompt.split("\n")[0],
      "clankers read ARENA.md AGENTS.md in full before your first edit, and follow both."],
    [prompt.includes(promptFillText), true],
    [prompt.indexOf("here is ARENA.md"), -1],
    [prompt.indexOf("Pareto"), -1],
    [ARENA_MD_URL, "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/rules/ARENA.md"],
    [promptWithRules.indexOf("here is ARENA.md:\n# Rules\n") > 0, true],
    [shouldWrite("", "clankers", null, null), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md", "clankers", null, null), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md\nExpect screenshots to be sent via the steering channel.", "clankers", null, null), true],
    [shouldWrite("clankers read AGENTS.md ARENA.md", "clankers", null, null), true],
    [shouldWrite(prompt, "clankers", null, null), true],
    [shouldWrite("draft", "clankers", null, null), false],
    [shouldWrite("clankers read ARENA.md AGENTS.md", "other", "clankers", null), true],
    [shouldWrite("draft", "clankers", "clankers", null), false],
    [shouldWrite(promptForSlug("other", promptFillText), "clankers", "other", "other"), true],
    // One fill per repo per page: the observer sees no second write, even when the
    // editor hands the text back with different whitespace or the send clears it.
    [shouldWrite(prompt, "clankers", "clankers", "clankers"), false],
    [shouldWrite("clankers read ARENA.md AGENTS.md in full before your first edit, and follow both.\n", "clankers", "clankers", "clankers"), false],
    [shouldWrite("", "clankers", "clankers", "clankers"), false],
    [shouldWrite("draft", "clankers", "clankers", "clankers"), false],
    [proxyHost("https://arena-proxy.example.ts.net/"), "https://arena-proxy.example.ts.net"],
    [proxyHost("https://arena-proxy.example.ts.net/v1"), "https://arena-proxy.example.ts.net"],
    [proxyHost("https://arena-proxy.example.ts.net/v1/"), "https://arena-proxy.example.ts.net"],
    [proxyHost(" https://arena-proxy.example.ts.net "), "https://arena-proxy.example.ts.net"],
    [proxyHost("http://arena-proxy.example.ts.net"), null],
    [proxyHost("https://arena-proxy.example.ts.net/path"), null],
    [proxyHost(""), null],
    [keyUrl("https://h.example", "m k"), "https://h.example/v1/key?master=m%20k"],
    [agentKeyFrom({ key: KEY43 }), KEY43],
    [agentKeyFrom({ key: "short" }), null],
    [agentKeyFrom({ key: "has spaces in it aaaaaaaaaaaaa" }), null],
    [agentKeyFrom(null), null],
    // The composer carries the fill only: the proxy rides the preview.
    [prompt.indexOf("http"), -1],
    [PREVIEW_FRAME_TITLE, "App preview on port 8000"],
    [ROTATE_MIN_SECONDS, 900],
    [ROTATE_DUE_KEY, "clankers-arena-rotate-due"],
    // A saved due time carries the countdown across reloads and tabs.
    [rotationDueAt(1000000, 0, 900), 1900000],
    [rotationDueAt(1000000, 895, 900), 1005000],
    [rotationDueAt(1000000, 900, 900), 1000000],
    [rotationDueAt(1000000, 2000, 900), 1000000],
    [rotationWaitMs(1900000, 1000000), 900000],
    [rotationWaitMs(1000000, 1900000), 0],
    [previewBase(frames([["App preview on port 8000", "https://sbx.example/"]])),
      "https://sbx.example"],
    [previewBase(frames([["Website", "https://x.example/"], ["App preview on port 8000", "https://sbx.example"]]))
      ? "https://sbx.example" : null, "https://sbx.example"],
    [previewBase(frames([["Website", "https://x.example/"]])) , null],
    [previewBase(frames([["App preview on port 8000", ""]])), null],
    [rotateUrl("https://h.example", "m k", 900), "https://h.example/v1/rotate?master=m%20k&min=900"],
    [keyPostUrl("https://sbx.example"), "https://sbx.example/api/key"],
    [KEY_WATCH_MS, 60000],
    [keyChanged("old", "new"), "new"],
    [keyChanged("same", "same"), null],
    [keyChanged("old", null), null],
    // The key posts when the frame appears, and the minute tick posts it again.
    [keyPostDue(null, null, true), false],
    [keyPostDue("https://sbx.example", null, false), true],
    [keyPostDue("https://sbx.example", "https://sbx.example", false), false],
    [keyPostDue("https://sbx.example", "https://sbx.example", true), true],
    [NOTED_KEY, "clankers-arena-noted-key"],
    // The note names the host, because the composer no longer carries it.
    [keyNote("replaced", KEY43, "2026-10-03T15:00:00+00:00", "https://h.example"),
      "Arena proxy https://h.example key replaced at 2026-10-03T15:00:00+00:00. New key: " + KEY43 +
      ". Use it as ?key= in every /v1 call. Routes: /v1/ping lists them;"
      + " skills/arena-skill/arena-egress-proxy holds the map. Never print it."],
    [keyNote("ready", KEY43, "2026-10-03T15:00:00+00:00", "https://h.example"),
      "Arena proxy https://h.example key ready at 2026-10-03T15:00:00+00:00. New key: " + KEY43 +
      ". Use it as ?key= in every /v1 call. Routes: /v1/ping lists them;"
      + " skills/arena-skill/arena-egress-proxy holds the map. Never print it."],
    // The older two-line fill is rebuilt once, without the rules text.
    [shouldWrite("clankers read ARENA.md AGENTS.md.\nExpect screenshots to be sent via the steering channel.", "clankers", "clankers", null), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md.\nExpect screenshots to be sent via the steering channel.", "clankers", "clankers", "clankers"), false],
  ];
  var failed = 0;
  var i;
  var promised;
  for (i = 0; i < cases.length; i += 1) {
    if (cases[i][0] !== cases[i][1]) {
      console.error("check fail", i, cases[i][0], cases[i][1]);
      failed += 1;
    }
  }
  if (failed) {
    throw new Error(failed + " checks failed");
  }
  // fetchJson maps a status and a parsed body, and it must survive a refused fetch.
  globalThis.fetch = function () {
    return Promise.resolve({
      status: 200,
      json: function () {
        return Promise.resolve({ rotated: true, key: KEY43 });
      },
    });
  };
  promised = new Promise(function (resolve, reject) {
    fetchJson("https://h.example/v1/rotate", function (status, body) {
      if (status === 200 && body && body.rotated === true && body.key === KEY43) {
        resolve();
        return;
      }
      reject(new Error("fetchJson lost the answer"));
    });
  });
  globalThis.fetch = function () {
    return Promise.reject(new Error("offline"));
  };
  promised = promised.then(function () {
    return new Promise(function (resolve, reject) {
      fetchJson("https://h.example/v1/rotate", function (status, body) {
        if (status === 0 && body === null) {
          resolve();
          return;
        }
        reject(new Error("fetchJson hid a refused fetch"));
      });
    });
  }).finally(function () {
    delete globalThis.fetch;
  });
  console.log("ok prompt fill " + cases.length);
  return promised;
}

function checkOpenSteering(api) {
  function steeringRowText(rows, expectedSlug) {
    var buttons = rows.map(function (row) {
      return {
        textContent: row[0] + " " + row[1],
        getAttribute: function (name) {
          return name === "aria-label" && row[2] ? row[2] : null;
        },
        querySelectorAll: function (selector) {
          return selector === "span" ? [{ textContent: row[0] }, { textContent: row[1] }] : [];
        },
      };
    });
    var doc = {
      querySelectorAll: function () {
        return buttons;
      },
    };
    var found = findSteeringButton(doc, expectedSlug);
    return found ? found.textContent : null;
  }

  var isSessionUrl = api.isSessionUrl;
  var slugFromOwnerRepo = api.slugFromOwnerRepo;
  var steeringSlugFromLabel = api.steeringSlugFromLabel;
  var isSteeringLabel = api.isSteeringLabel;
  var isSteeringPort = api.isSteeringPort;
  var buttonMatchesSteering = api.buttonMatchesSteering;
  var findSteeringButton = api.findSteeringButton;
  var CLICK_DELAY_MS = api.CLICK_DELAY_MS;

  var cases = [
    [isSessionUrl("https://arena.ai/agent/foo"), true],
    [isSessionUrl("https://www.arena.ai/agent/foo/bar"), true],
    [isSessionUrl("https://arena.ai/agent/foo?x=1"), true],
    [isSessionUrl("https://arena.ai/agent"), false],
    [isSessionUrl("https://arena.ai/agent/"), false],
    [isSessionUrl("https://other.example/agent/foo"), false],
    [slugFromOwnerRepo("nemoe7/clankers"), "clankers"],
    [steeringSlugFromLabel("daedalus - Steering"), "daedalus"],
    [steeringSlugFromLabel("clankers - preview"), "clankers"],
    [steeringSlugFromLabel("clankers preview"), "clankers"],
    [steeringSlugFromLabel("arena"), null],
    [steeringSlugFromLabel("Steering"), null],
    [steeringSlugFromLabel("daedalus - Website"), null],
    [isSteeringLabel("CLANKERS - PREVIEW"), true],
    [isSteeringLabel("daedalus - Website"), false],
    [buttonMatchesSteering("CLANKERS - steering", ":8000", "clankers"), true],
    [buttonMatchesSteering("Steering", ":8000", "clankers"), true],
    [buttonMatchesSteering("daedalus - Steering", ":8000", "clankers"), false],
    [buttonMatchesSteering("clankers - STEERING", ":8001", "CLANKERS"), false],
    [buttonMatchesSteering("daedalus - Preview", ":8000", null), true],
    [buttonMatchesSteering("daedalus - Website", ":8000", null), false],
    [isSteeringPort(":8000"), true],
    [isSteeringPort("8000"), false],
    [steeringRowText([["Website", ":3000"], ["daedalus - Steering", ":8000"]], "clankers"),
      "daedalus - Steering :8000"],
    [steeringRowText([["clankers - Steering", ":8000"], ["daedalus - preview", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["Website", ":3000"], ["arena - preview", ":8000"]], "clankers"),
      "arena - preview :8000"],
    // A Start row is a transcript card. A click on one opens nothing, so it never counts.
    [steeringRowText([["Start clankers - Steering", ":8000"]], "clankers"), null],
    [steeringRowText([["Arena preview", ":8000", "Switch preview port"]], null), null],
    [steeringRowText([["Arena preview", ":8000", "Switch preview port"],
      ["clankers - Steering", ":8000"]], "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["Start clankers - Steering", ":8000"], ["daedalus - preview", ":8000"]],
      "clankers"), "daedalus - preview :8000"],
    // The running row wins over history cards, wherever they sit.
    [steeringRowText([["Start clankers - Steering", ":8000"], ["clankers - Steering", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["clankers - Steering", ":8000"], ["Start clankers - Steering", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["clankers - Steering", ":8000"], ["Start preview", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    // This project's running row outranks a newer row for another project, and a nameless
    // running row outranks a named one for another project.
    [steeringRowText([["clankers - Steering", ":8000"], ["daedalus - preview", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["Steering", ":8000"], ["daedalus - preview", ":8000"]], "clankers"),
      "Steering :8000"],
    // A renamed live row still wins, and it is the only running row here.
    [steeringRowText([["Start clankers - Steering", ":8000"],
      ["daedalus - preview", ":8000"], ["arena - preview", ":8000"]], "clankers"),
      "arena - preview :8000"],
    [CLICK_DELAY_MS, 1000],
  ];
  var failed = 0;
  var i;
  for (i = 0; i < cases.length; i += 1) {
    if (cases[i][0] !== cases[i][1]) {
      console.error("check fail", i, cases[i][0], cases[i][1]);
      failed += 1;
    }
  }
  if (failed) {
    throw new Error(failed + " checks failed");
  }
  console.log("ok open steering " + cases.length);
}

function checkAutoScrollToggle(api) {
  function hasToggleClass(classes, name) {
    return classes.split(" ").indexOf(name) !== -1;
  }

  var AUTO_TOGGLE_CLASS = api.AUTO_TOGGLE_CLASS;
  var autoToggleClasses = api.autoToggleClasses;

  var on = autoToggleClasses(true);
  var off = autoToggleClasses(false);
  var cases = [
    [hasToggleClass(on, "bg-surface-raised"), true],
    [hasToggleClass(on, "bg-transparent"), false],
    [hasToggleClass(off, "bg-transparent"), true],
    [hasToggleClass(off, "bg-surface-raised"), false],
    [hasToggleClass(on, "hover:bg-interactive-cta-active"), true],
    [hasToggleClass(off, "hover:bg-surface-raised"), true],
    [hasToggleClass(AUTO_TOGGLE_CLASS, "h-8"), true],
    [hasToggleClass(AUTO_TOGGLE_CLASS, "w-8"), true],
  ];
  var failed = 0;
  var i;
  for (i = 0; i < cases.length; i += 1) {
    if (cases[i][0] !== cases[i][1]) {
      console.error("check fail", i, cases[i][0], cases[i][1]);
      failed += 1;
    }
  }
  if (failed) {
    throw new Error(failed + " checks failed");
  }
  console.log("ok transcript auto-scroll " + cases.length);
}

function checkTranscriptTrim(api) {
  var normalizePlan = api.normalizePlan;
  var planParts = api.planParts;
  var countLabel = api.countLabel;
  var messageRoots = api.messageRoots;
  var rowsOfRoot = api.rowsOfRoot;
  var trimPlan = api.trimPlan;
  var trimRows = api.trimRows;
  var isSettled = api.isSettled;
  var quietReady = api.quietReady;
  var ACTION_SELECTOR = api.ACTION_SELECTOR;
  var QUESTION_SELECTOR = api.QUESTION_SELECTOR;
  var MIN_ROWS = api.MIN_ROWS;
  var DEFAULT_ROWS = api.DEFAULT_ROWS;
  var DEFAULT_TRIM_CAP = api.DEFAULT_TRIM_CAP;

  function rows(count) {
    var list = [];
    var i;
    for (i = 0; i < count; i += 1) {
      var row = {
        parentElement: {},
        removed: false,
        textContent: "row",
        remove: function () {
          this.removed = true;
          this.parentElement = null;
        },
      };
      row.classList = {
        names: {},
        add: function (name) {
          this.names[name] = true;
        },
        contains: function (name) {
          return Boolean(this.names[name]);
        },
      };
      list.push(row);
    }
    return list;
  }
  function cleared(row) {
    return row.classList.contains("hidden") && row.textContent === "";
  }
  function actionContainer() {
    return {
      removed: false,
      parentElement: {},
      remove: function () {
        this.removed = true;
        this.parentElement = null;
      },
    };
  }
  var BOX = "div.flex.flex-col.gap-2";
  function rowBox(pageRows, nested) {
    var element = {
      children: pageRows,
      closest: function (selector) {
        return selector === BOX ? element : null;
      },
      parentElement: {
        closest: function (selector) {
          return selector === BOX ? nested || null : null;
        },
      },
    };
    return element;
  }
  function messageRoot(boxes, actions, connected) {
    actions = actions || [];
    var root = {
      isConnected: connected !== false,
      removed: false,
      hiddenClass: false,
      remove: function () {
        this.removed = true;
        this.parentElement = null;
      },
      querySelectorAll: function (selector) {
        if (selector === BOX) return boxes;
        return selector === ACTION_SELECTOR ? actions : [];
      },
    };
    root.classList = {
      add: function (name) {
        if (name === "hidden") root.hiddenClass = true;
      },
    };
    root.parentElement = { children: [root] };
    return root;
  }
  function logDoc(roots, withLog) {
    var log = {
      querySelectorAll: function (selector) {
        return selector === '[data-agent-transcript-message="true"]' ? roots : [];
      },
    };
    return {
      querySelectorAll: function (selector) {
        if (selector === '[role="log"]') return withLog ? [log] : [];
        if (selector === '[data-agent-transcript-message="true"]') return withLog ? [] : roots;
        return [];
      },
    };
  }
  var rootActions = [actionContainer(), actionContainer()];
  var rootRows = [rows(25), rows(25)];
  var rootNodes = [
    messageRoot([rowBox(rootRows[0])], [rootActions[0]]),
    messageRoot([rowBox(rootRows[1])], [rootActions[1]]),
  ];
  var rootRowsRemoved = trimPlan(logDoc(rootNodes, true), "20");
  var emptyAction = actionContainer();
  var emptyRoot = messageRoot([rowBox([])], [emptyAction]);
  var emptyTrim = trimPlan(logDoc([emptyRoot], true), "50");
  var globalActions = [actionContainer(), actionContainer(), actionContainer()];
  var globalRows = [rows(25), rows(20), rows(25)];
  var globalNodes = [
    messageRoot([rowBox(globalRows[0])], [globalActions[0]]),
    messageRoot([rowBox(globalRows[1])], [globalActions[1]]),
    messageRoot([rowBox(globalRows[2])], [globalActions[2]]),
  ];
  var globalRemoved = trimPlan(logDoc(globalNodes, true), "40");
  var sparseRows = [rows(30), rows(1)];
  var sparseRoots = sparseRows.map(function (items) {
    return messageRoot([rowBox(items)]);
  });
  assert.equal(trimPlan(logDoc(sparseRoots, true), "50"), 0);
  assert.equal(cleared(sparseRows[0][29]), false);
  var staleRows = rows(3);
  var staleAction = actionContainer();
  var k;
  for (k = 0; k < staleRows.length; k += 1) staleRows[k].parentElement = null;
  var staleRoot = messageRoot([rowBox(staleRows)], [staleAction]);
  var staleRemoved = trimPlan(logDoc([staleRoot], true), "50");
  var goneRows = rows(30);
  var goneAction = actionContainer();
  var goneRoot = messageRoot([rowBox(goneRows)], [goneAction], false);
  var goneRemoved = trimPlan(logDoc([goneRoot], true), "20");
  // An answered question appends a fresh empty root behind the rows, and the keep
  // budget must stay with those rows instead of clearing the page.
  var questionRows = rows(30);
  var questionAction = actionContainer();
  var questionRoot = messageRoot([rowBox(questionRows)], [questionAction]);
  var questionTail = messageRoot([rowBox([])], []);
  var questionRemoved = trimPlan(logDoc([questionRoot, questionTail], true), "20");
  var detached = rows(4);
  detached[0].parentElement = null;
  // One pass cuts at most the cap, so a large backlog drains in steps instead
  // of one blocking burst the page must reconcile at once.
  var cappedTrim = trimRows(rows(300), 50);
  var outerBox = rowBox(rows(1));
  var nestedBox = rowBox(rows(2), outerBox);
  var cases = [
    [trimRows(rows(5), 3), 2],
    [trimRows(rows(3), 3), 0],
    [trimRows(rows(2), 10), 0],
    [trimRows(detached, 2), 1],
    [cappedTrim, DEFAULT_TRIM_CAP],
    [normalizePlan("50"), "50"],
    [normalizePlan(" 50 "), "50"],
    [normalizePlan("5,80"), "80"],
    [normalizePlan("5"), null],
    [normalizePlan("5,5"), null],
    [normalizePlan("0,80"), null],
    [normalizePlan("80 rows"), null],
    [normalizePlan("later"), null],
    [normalizePlan(null), null],
    [planParts("").rows, DEFAULT_ROWS],
    [planParts("4,75").rows, 75],
    [MIN_ROWS, 20],
    [countLabel("50", 0), "Transcript \u2014 keep 50 rows"],
    [countLabel("50", 3), "Transcript \u2014 keep 50 rows (3 removed)"],
    [ACTION_SELECTOR, ":scope > div > div > div.mt-3.flex.flex-col.gap-3"],
    [QUESTION_SELECTOR, '[role="radiogroup"]'],
    [rowsOfRoot(messageRoot([rowBox(rows(3))])).length, 3],
    [rowsOfRoot(messageRoot([outerBox, nestedBox])).length, 1],
    [rowsOfRoot(messageRoot([rowBox(rows(2), outerBox)])).length, 2],
    [messageRoots(logDoc([messageRoot([])], true)).length, 1],
    [messageRoots(logDoc([messageRoot([])], false)).length, 1],
    [messageRoots(logDoc([], true)).length, 0],
    // A lone root is the newest: under its own keep count nothing leaves.
    [trimPlan(logDoc([messageRoot([rowBox(rows(30))])], true), "50"), 0],
    // The newest root keeps exactly its K newest rows: the ten oldest hide and empty.
    [trimPlan(logDoc([messageRoot([rowBox(rows(30))])], true), "20"), 10],
    [rootRowsRemoved, 30],
    // Cut rows stay as hidden empty shells: the page reinstates removed nodes, so the trim hides and empties instead of deleting.
    // The older root hides in full while the newest root keeps its 20 newest rows.
    [cleared(rootRows[0][24]), true],
    [rootRows[0][24].parentElement !== null, true],
    [rootNodes[0].hiddenClass, true],
    [cleared(rootRows[1][0]), true],
    [cleared(rootRows[1][4]), true],
    [cleared(rootRows[1][5]), false],
    [rootRows[1][5].textContent, "row"],
    [rootNodes[1].hiddenClass, false],
    [rootActions[0].removed, true],
    // The action container leaves only with a root that lost every row: the newest
    // root keeps its rows, so its actions, and the newest rows inside them, stay.
    [rootActions[1].removed, false],
    // A lone root is the newest one: it keeps every row and never hides.
    [emptyTrim, 0],
    [emptyAction.removed, false],
    [emptyRoot.hiddenClass, false],
    [emptyRoot.parentElement !== null, true],
    // The newest root keeps 25 rows, and the previous root keeps 15.
    [globalRemoved, 30],
    [cleared(globalRows[0][24]), true],
    [globalNodes[0].hiddenClass, true],
    [cleared(globalRows[1][4]), true],
    [globalNodes[1].hiddenClass, false],
    [cleared(globalRows[2][0]), false],
    [globalNodes[2].hiddenClass, false],
    [globalActions[0].removed, true],
    [globalActions[1].removed, false],
    [globalActions[2].removed, false],
    [staleRemoved, 0],
    [staleAction.removed, false],
    [goneRemoved, 0],
    [goneRows[0].removed, false],
    [goneRows[24].removed, false],
    [goneAction.removed, false],
    [goneRoot.parentElement !== null, true],
    // The empty root an answered question appends takes no keep budget: the rows
    // behind it keep their 20 newest, their action stays, and the page does not clear.
    [questionRemoved, 10],
    [cleared(questionRows[0]), true],
    [cleared(questionRows[9]), true],
    [cleared(questionRows[10]), false],
    [questionRows[29].textContent, "row"],
    [questionAction.removed, false],
    [questionRoot.hiddenClass, false],
    [questionTail.hiddenClass, true],
    [globalNodes[0].parentElement !== null, true],
    [globalNodes[1].parentElement !== null, true],
    [globalNodes[2].parentElement !== null, true],
    // No stop control means no turn, and the trim aborts. It runs only while a turn
    // is up. A question card aborts too. The pulsing icon no longer gates anything.
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function () { return null; } }), false],
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function (selector) { return selector === "svg.animate-pulse" ? {} : null; } }), false],
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function (selector) { return selector === QUESTION_SELECTOR ? {} : null; } }), false],
    [isSettled({ querySelectorAll: function () { return [{ getAttribute: function () { return "Stop generating"; } }]; }, querySelector: function () { return null; } }), true],
    [isSettled({ querySelectorAll: function () { return [{ getAttribute: function () { return "Send"; } }]; }, querySelector: function () { return null; } }), false],
    // Quiet means the whole page holding still, not the row count alone: the page streams into existing
    // rows after the last row lands, so a fresh mutation keeps the trim waiting even while the count holds.
    [quietReady({ rows: null, rowsAt: 0, mutationAt: 0 }, 10, 100000), false],
    [quietReady({ rows: 10, rowsAt: 100000, mutationAt: 0 }, 10, 100500), false],
    [(function () {
      var state = { rows: 10, rowsAt: 0, mutationAt: 100900 };
      return quietReady(state, 10, 101500);
    })(), false],
    [(function () {
      var state = { rows: 10, rowsAt: 0, mutationAt: 0 };
      return quietReady(state, 10, 101500);
    })(), true],
  ];
  var failed = 0;
  var i;
  for (i = 0; i < cases.length; i += 1) {
    if (cases[i][0] !== cases[i][1]) {
      console.error("check fail", i, cases[i][0], cases[i][1]);
      failed += 1;
    }
  }
  if (failed) {
    throw new Error(failed + " checks failed");
  }
  console.log("ok transcript trim " + cases.length);
}

function checkHideComposer(api) {
  var isSessionUrl = api.isSessionUrl;
  var isStopGeneratingLabel = api.isStopGeneratingLabel;
  var shouldHideComposer = api.shouldHideComposer;
  var isSpacerElement = api.isSpacerElement;
  var hasSpacerHeight = api.hasSpacerHeight;
  var enforceSpacerHeight = api.enforceSpacerHeight;
  var SPACER_SELECTOR = api.SPACER_SELECTOR;
  var SPACER_HEIGHT = api.SPACER_HEIGHT;

  var styleState = { height: SPACER_HEIGHT, priority: "", writes: 0 };
  var spacerStyle = {
    getPropertyValue: function (name) {
      return name === "height" ? styleState.height : "";
    },
    getPropertyPriority: function (name) {
      return name === "height" ? styleState.priority : "";
    },
    setProperty: function (name, value, priority) {
      if (name === "height") {
        styleState.height = value;
        styleState.priority = priority;
        styleState.writes += 1;
      }
    },
  };
  var spacer = {
    tagName: "DIV",
    classList: { contains: function (name) { return name === "shrink-0"; } },
    textContent: "",
    style: spacerStyle,
    getAttribute: function (name) {
      return name === "style" ? "height: 24px;" : null;
    },
  };
  var spacerDoc = {
    querySelectorAll: function (selector) {
      return selector === SPACER_SELECTOR ? [spacer] : [];
    },
  };
  var candidate = isSpacerElement(spacer) && hasSpacerHeight(spacer.getAttribute("style"));
  enforceSpacerHeight(spacerDoc);
  var initialPriority = styleState.priority;
  styleState.height = "18px";
  styleState.priority = "";
  enforceSpacerHeight(spacerDoc, [
    {
      type: "attributes",
      attributeName: "style",
      oldValue: "height: 24px !important;",
      target: spacer,
    },
  ]);
  var cases = [
    [isSessionUrl("https://arena.ai/agent/foo"), true],
    [isSessionUrl("https://www.arena.ai/agent/foo/bar"), true],
    [isSessionUrl("https://arena.ai/agent/foo?x=1"), true],
    [isSessionUrl("https://arena.ai/agent"), false],
    [isSessionUrl("https://arena.ai/agent/"), false],
    [isSessionUrl("https://other.example/agent/foo"), false],
    [isStopGeneratingLabel("Stop generating"), true],
    [isStopGeneratingLabel("Stop Generating"), true],
    [isStopGeneratingLabel("stop generating"), true],
    [isStopGeneratingLabel("Send"), false],
    [shouldHideComposer(true, true), true],
    [shouldHideComposer(true, false), false],
    [shouldHideComposer(false, true), false],
    [candidate, true],
    [hasSpacerHeight("height: 24px;"), true],
    [hasSpacerHeight("height: 24px !important;"), true],
    [hasSpacerHeight("height: 25px;"), false],
    [initialPriority, "important"],
    [styleState.height, SPACER_HEIGHT],
    [styleState.priority, "important"],
    [styleState.writes, 2],
  ];
  var failed = 0;
  var i;
  for (i = 0; i < cases.length; i += 1) {
    if (cases[i][0] !== cases[i][1]) {
      console.error("check fail", i, cases[i][0], cases[i][1]);
      failed += 1;
    }
  }
  if (failed) {
    throw new Error(failed + " checks failed");
  }
  console.log("ok hide composer " + cases.length);
}

function checkTabTitle(api, logging) {
  // The bundle hooks change its state. The cases compare the call result to null.
  function expireHold() {
    api.expireHold();
    return null;
  }

  function forgetPath() {
    api.forgetPath();
    return null;
  }

  var repoFromLink = api.repoFromLink;
  var repoForTitle = api.repoForTitle;
  var desiredTitle = api.desiredTitle;
  var syncTitle = api.syncTitle;
  var liveLabel = api.liveLabel;
  var stopSignal = api.stopSignal;
  var childChain = api.childChain;
  var lastRoot = api.lastRoot;
  var userRoot = api.userRoot;
  var rowContainer = api.rowContainer;
  var newestRow = api.newestRow;
  var rowKind = api.rowKind;
  var summaryCard = api.summaryCard;
  var BASH_EMOJI = api.BASH_EMOJI;
  var PLAY_SELECTOR = api.PLAY_SELECTOR;
  var AGENT_EMOJI = api.AGENT_EMOJI;
  var REASONING_EMOJI = api.REASONING_EMOJI;
  var waitingSignal = api.waitingSignal;
  var emojiForRow = api.emojiForRow;
  var actionEmoji = api.actionEmoji;
  var TITLE_PREFIX = api.TITLE_PREFIX;
  var vtag = "";
  var VERSION = api.VERSION;
  var EMOJI_HOLD_MS = api.EMOJI_HOLD_MS;
  var MESSAGE_SELECTOR = api.MESSAGE_SELECTOR;
  var LIVE_ICON_SELECTOR = api.LIVE_ICON_SELECTOR;
  var LIVE_LABEL_SELECTOR = api.LIVE_LABEL_SELECTOR;
  var GROUP_LABEL_SELECTOR = api.GROUP_LABEL_SELECTOR;
  var LABEL_SPAN_SELECTOR = api.LABEL_SPAN_SELECTOR;
  var REPO_LINK_SELECTOR = api.REPO_LINK_SELECTOR;
  var WAITING_SELECTOR = api.WAITING_SELECTOR;
  var WAITING_TEXT_SELECTOR = api.WAITING_TEXT_SELECTOR;
  var HOURGLASS_EMOJI = api.HOURGLASS_EMOJI;
  var CAPTCHA_SELECTOR = api.CAPTCHA_SELECTOR;
  var CAPTCHA_EMOJI = api.CAPTCHA_EMOJI;
  var captchaSignal = api.captchaSignal;
  var QUESTION_SELECTOR = api.QUESTION_SELECTOR;
  var QUESTION_EMOJI = api.QUESTION_EMOJI;
  var questionSignal = api.questionSignal;
  var openDialog = api.openDialog;
  var setPriorTitle = api.setPriorTitle;

  function link(href, label) {
    return {
      getAttribute: function (name) {
        if (name === "href") return href;
        if (name === "aria-label") return label;
        return null;
      },
    };
  }
  function docWith(element, title) {
    return {
      title: title,
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? element : null;
      },
      querySelectorAll: function (selector) {
        return selector === "button[aria-label]" ? [stopButton("Stop generating")] : [];
      },
    };
  }
  function stopButton(label) {
    return {
      getAttribute: function (name) {
        return name === "aria-label" ? label : null;
      },
    };
  }
  // The root-bounded model reads a real tree, so the checks build one: every node answers
  // the selectors the feature uses, and the chain walks land on real children.
  function matches(node, selector) {
    if (!node || !node.attrs) {
      return false;
    }
    if (selector === MESSAGE_SELECTOR) {
      return node.attrs["data-agent-transcript-message"] !== undefined;
    }
    if (selector === PLAY_SELECTOR) {
      return node.tagName === "SVG" && api.classOf(node, "lucide-play");
    }
    if (selector === LIVE_LABEL_SELECTOR) {
      return String(node.attrs.style || "").indexOf("text-shimmer") !== -1;
    }
    if (selector === LIVE_ICON_SELECTOR) {
      return api.classOf(node, "animate-pulse");
    }
    if (selector === GROUP_LABEL_SELECTOR) {
      return node.tagName === "SPAN" && api.classOf(node, "text-text-secondary");
    }
    if (selector === LABEL_SPAN_SELECTOR) {
      return node.tagName === "SPAN" && api.classOf(node, "body-sm");
    }
    if (selector === "a") return node.tagName === "A";
    if (selector === "button") return node.tagName === "BUTTON";
    if (selector === "p") return node.tagName === "P";
    if (selector === "pre") return node.tagName === "PRE";
    if (selector === "button[aria-label]") {
      return node.tagName === "BUTTON" && node.attrs["aria-label"] !== undefined;
    }
    return false;
  }
  function findAll(root, selector) {
    var hits = [];
    (function walk(item) {
      var kids = item.children || [];
      var i;
      for (i = 0; i < kids.length; i += 1) {
        if (matches(kids[i], selector)) hits.push(kids[i]);
        walk(kids[i]);
      }
    })(root);
    return hits;
  }
  function node(tag, className, kids) {
    var el = {
      tagName: String(tag).toUpperCase(),
      className: className || "",
      children: kids || [],
      parentElement: null,
      textContent: "",
      attrs: {},
    };
    el.getAttribute = function (name) {
      return Object.prototype.hasOwnProperty.call(el.attrs, name) ? el.attrs[name] : null;
    };
    el.querySelector = function (selector) {
      var hits = findAll(el, selector);
      return hits.length ? hits[0] : null;
    };
    el.querySelectorAll = function (selector) {
      return findAll(el, selector);
    };
    el.contains = function (candidate) {
      if (candidate === el) return true;
      var i;
      for (i = 0; i < el.children.length; i += 1) {
        if (el.children[i].contains && el.children[i].contains(candidate)) return true;
      }
      return false;
    };
    el.closest = function (selector) {
      var current = el;
      while (current) {
        if (matches(current, selector)) return current;
        current = current.parentElement;
      }
      return null;
    };
    Object.defineProperty(el, "firstElementChild", {
      get: function () {
        return el.children.length ? el.children[0] : null;
      },
    });
    var i;
    for (i = 0; i < el.children.length; i += 1) el.children[i].parentElement = el;
    return el;
  }
  var ROW_CONTAINER_CLASS = "flex flex-col gap-2";
  // The session dump's agent root: the bubble card, then `px-3 pb-3`, then the row
  // container. Every root carries the transcript attributes.
  function agentRoot(rows) {
    var container = node("div", ROW_CONTAINER_CLASS, rows);
    var root = node("div", "", [
      node("div", "relative overflow-hidden bg-surface-primary rounded-xl border w-full border-transparent", [
        node("div", "px-3 pb-3", [container]),
      ]),
    ]);
    root.attrs["data-agent-transcript-message"] = "true";
    root.attrs["data-chat-message-id"] = "chat-agent";
    return root;
  }
  // The session dump's user root: the layout div, the body row, the raised card, then
  // `px-3`, the container and the `prose` body. The agent root is the negation of this fact.
  function userRootNode() {
    var body = node("div", "prose prose-pre:bg-transparent text-wrap break-words", []);
    var card = node("div", "relative overflow-hidden bg-surface-raised rounded-lg w-fit max-w-[min(70%,768px)] border-transparent ms-0", [
      node("div", "px-3 text-text-primary body-base py-2", [
        node("div", ROW_CONTAINER_CLASS, [body]),
      ]),
    ]);
    var root = node("div", "", [
      node("div", "", [node("div", "group flex min-w-0 flex-col items-end gap-1", [card])]),
    ]);
    root.attrs["data-agent-transcript-message"] = "true";
    root.attrs["data-chat-message-id"] = "chat-user";
    return root;
  }
  function actionRow(label) {
    var span = node("span", "text-text-secondary body-sm", []);
    span.textContent = label;
    var button = node("button", "flex w-full", [span]);
    button.attrs["aria-label"] = "Collapse";
    return node("div", "", [button]);
  }
  function commandRow(label, command) {
    var row = actionRow(label);
    if (command) {
      var pre = node("pre", "", []);
      pre.textContent = command;
      row.children[0].children.push(pre);
    }
    return row;
  }
  // The buttonless rows: a size-4 icon beside a single body-sm span. The fetch row keeps the
  // page's URL in an anchor inside that span, so the anchor's copy never joins the label.
  function fetchRow(iconClass, text, url) {
    var icon = node("svg", iconClass, []);
    var span = node("span", "body-sm text-text-tertiary min-w-0 flex-1 truncate leading-4", []);
    if (url) {
      var linkNode = node("a", "text-interactive-link hover:underline", []);
      linkNode.textContent = url;
      span.children.push(linkNode);
    }
    span.textContent = url ? text + " " + url : text;
    return node("div", "flex items-center gap-1.5", [icon, span]);
  }
  function fetchRunningRow() {
    var icon = node("svg", "text-text-tertiary size-4 shrink-0 animate-pulse", []);
    var p = node("p", "relative inline-block", []);
    p.attrs.style = "animation: 2s linear 0s infinite normal none running text-shimmer;";
    p.textContent = "Fetching";
    var linkNode = node("a", "text-interactive-link ms-1 hover:underline", []);
    linkNode.textContent = "https://example.test/page";
    var span = node("span", "body-sm min-w-0 flex-1 truncate leading-4", [p, linkNode]);
    span.textContent = "Fetching https://example.test/page";
    return node("div", "flex items-center gap-1.5", [icon, span]);
  }
  // The process-output row: a size-3 icon beside a plain secondary span, no button.
  function processOutputRow() {
    var icon = node("svg", "text-text-tertiary size-3 shrink-0", []);
    var label = node("span", "text-text-secondary", []);
    label.textContent = "get_process_output";
    return node("div", "body-sm flex items-center gap-1.5", [icon, label]);
  }
  function loneSearchRow(label) {
    var span = node("span", "body-sm text-text-tertiary min-w-0 truncate leading-4", []);
    span.textContent = label;
    var inner = node("span", "flex min-w-0 items-center gap-1.5", [node("svg", "text-text-tertiary size-4 shrink-0", []), span]);
    var head = node("div", "flex select-none items-center gap-1", [inner]);
    head.attrs["aria-expanded"] = "false";
    return node("div", "", [head]);
  }
  function batchFetchRow() {
    var chevron = node("svg", "text-text-tertiary size-3 shrink-0 transition-transform duration-200 rotate-90", []);
    var icon = node("svg", "text-text-tertiary size-4 shrink-0", []);
    var pulse = node("span", "animate-pulse", []);
    pulse.textContent = "Searching the web";
    var label = node("span", "text-text-secondary shrink-0", [pulse]);
    var button = node("button", "body-sm group flex w-full cursor-pointer items-center gap-1.5 leading-[1]", [chevron, icon, label]);
    button.attrs["aria-expanded"] = "true";
    var body = node("div", "flex flex-col gap-2 py-1 ps-[22px]", [fetchRow("text-text-tertiary size-4 shrink-0", "Fetched", "https://example.test/page")]);
    return node("div", "", [button, body]);
  }
  function batchFetchDoneRow() {
    var chevron = node("svg", "text-text-tertiary size-3 shrink-0 transition-transform duration-200", []);
    var icon = node("svg", "text-text-tertiary size-4 shrink-0", []);
    var label = node("span", "text-text-secondary shrink-0", []);
    label.textContent = "Searched the web";
    var button = node("button", "body-sm group flex w-full cursor-pointer items-center gap-1.5 leading-[1]", [chevron, icon, label]);
    button.attrs["aria-expanded"] = "false";
    return node("div", "", [button]);
  }
  function chatRow() {
    var row = node("div", "prose", []);
    row.textContent = "A chat answer";
    return row;
  }
  function reasoningRow() {
    var row = node("div", "not-prose", []);
    row.textContent = "Thinking it over";
    return row;
  }
  function playRow() {
    var play = node("svg", "lucide-play size-4", []);
    var name = node("span", "text-text-secondary", []);
    name.textContent = "Start PR checks";
    var button = node("button", "flex w-full", [play, name]);
    return node("div", "", [button]);
  }
  function summaryRow() {
    var label = node("span", "text-text-secondary", []);
    label.textContent = "Summary";
    var button = node("button", "", [label]);
    return node("div", "", [button]);
  }
  function page(roots, options) {
    options = options || {};
    return {
      title: options.title || "ChatGPT",
      querySelector: function (selector) {
        if (selector !== REPO_LINK_SELECTOR) return null;
        return options.repo === undefined ? repoLink : options.repo;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return roots || [];
        if (selector === "button[aria-label]") {
          return options.stop === false ? [] : [stopButton(options.stopLabel || "Stop generating")];
        }
        if (selector === WAITING_SELECTOR) return options.canvas ? [options.canvas] : [];
        if (selector === CAPTCHA_SELECTOR) return options.captcha ? [options.captcha] : [];
        if (selector === QUESTION_SELECTOR) return options.question ? [options.question] : [];
        return [];
      },
    };
  }
  // The waiting line is a spinner canvas beside the rotating monospace text.
  // An action row also uses the spinner canvas as its icon. The canvas alone does not prove an action row. Require text beside it.
  function pageTree(text, children) {
    var el = {
      text: text || "",
      textContent: text || "",
      children: children || [],
      querySelectorAll: function (selector) {
        var hits = [];
        if (selector !== WAITING_TEXT_SELECTOR) return hits;
        (function walk(item) {
          var i;
          for (i = 0; i < item.children.length; i += 1) {
            if (item.children[i].text || item.children[i].span) hits.push(item.children[i]);
            walk(item.children[i]);
          }
        })(el);
        return hits;
      },
    };
    var i;
    for (i = 0; i < el.children.length; i += 1) el.children[i].parentElement = el;
    return el;
  }
  function rowCanvas(withText, blank) {
    var canvas = pageTree("", []);
    var icon = pageTree("", [pageTree("", [canvas])]);
    var kids = [icon];
    if (withText) {
      var span = pageTree(blank ? "" : "The cat sat on the", []);
      if (blank) span.span = true;
      kids.push(pageTree("", [span]));
    }
    return { canvas: canvas, row: pageTree("", kids) };
  }
  function waitingDoc() {
    // The row carries no mark of its own, so the waiting line is the only news.
    return page([agentRoot([summaryRow()])], { canvas: rowCanvas(true).canvas });
  }
  function blankWaitingDoc() {
    return page([agentRoot([summaryRow()])], { canvas: rowCanvas(true, true).canvas });
  }
  function actionCanvasDoc() {
    return page([agentRoot([actionRow("Bash sleep 25")])], { canvas: rowCanvas(false).canvas });
  }
  function questionCard(label) {
    return {
      getAttribute: function (name) {
        return name === "aria-label" ? label || "Pick one" : null;
      },
    };
  }
  function questionDoc(card, withCaptcha) {
    var options = { question: card || null };
    if (withCaptcha) options.captcha = captchaFrame();
    return page([agentRoot([chatRow()])], options);
  }
  function captchaFrame(state, parked) {
    var frame = {
      title: "reCAPTCHA",
      getAttribute: function () {
        return null;
      },
    };
    if (parked) {
      // A parked node keeps its place in the page after the widget closes: no box renders.
      frame.getClientRects = function () {
        return [];
      };
    }
    if (state) {
      // Radix keeps the dialog in the page after it closes, one data-state away.
      var dialog = {
        getAttribute: function (name) {
          return name === "data-state" ? state : null;
        },
      };
      var middle = { parentElement: dialog, getAttribute: function () { return null; } };
      frame.parentElement = middle;
    }
    return frame;
  }
  function captchaDoc(state, parked) {
    return page([agentRoot([chatRow()])], { captcha: captchaFrame(state, parked) });
  }
  function looseStopDoc() {
    return page([agentRoot([chatRow()])], { stopLabel: "Stop response" });
  }

  var repoLink = link("https://github.com/nemoe7/clankers", "Open nemoe7/clankers on GitHub");
  var labelOnly = link(null, "Open nemoe7/clankers on GitHub");
  var emptyLink = link("", "");
  var setDoc = docWith(repoLink, "ChatGPT");
  var keepDoc = docWith(null, "ChatGPT");
  var goneDoc = docWith(null, TITLE_PREFIX + "clankers" + vtag);
  // One message per fixture: the same mark read twice would resurface as the hold.
  var chatPage = page([agentRoot([chatRow()])]);
  var reasoningPage = page([agentRoot([reasoningRow()])]);
  var bashPage = page([agentRoot([commandRow("Bash sleep 25", "$ npm test")])]);
  var editPage = page([agentRoot([commandRow("Edit main.py")])]);
  var readPage = page([agentRoot([commandRow("Read main.py")])]);
  var searchPage = page([agentRoot([commandRow("Searching the web")])]);
  var fetchPage = page([agentRoot([commandRow("Fetching web page")])]);
  // The buttonless rows and the group three batched fetches collapse into.
  var fetchDonePage = page([agentRoot([fetchRow("text-text-tertiary size-4 shrink-0", "Fetched", "https://example.test/page")])]);
  var fetchFailedPage = page([agentRoot([fetchRow("text-text-tertiary size-4 shrink-0", "Fetch failed", null)])]);
  var searchLonePage = page([agentRoot([loneSearchRow('Searched for "node test runner"')])]);
  var processOutputPage = page([agentRoot([processOutputRow()])]);
  var outputPage = page([agentRoot([commandRow("get_process_output")])]);
  var gearPage = page([agentRoot([commandRow("Agent chat")])]);
  var questionsPage = page([agentRoot([commandRow("Generating questions\u2026")])]);
  var pollPage = page([agentRoot([commandRow("running Bash", "$ arena-preview poll")])]);
  var playPage = page([agentRoot([playRow()])]);
  var summaryPage = page([agentRoot([summaryRow()])]);
  var userPage = page([userRootNode()]);
  var endedPage = page([agentRoot([chatRow()])], { stop: false });
  var quietPage = page([]);
  // `:nth-last-of-type(2)`: the trailing div is never the row.
  var trailingPage = page([agentRoot([commandRow("Bash sleep 25", "$ npm test"), chatRow()])]);
  var thirdPage = page([agentRoot([commandRow("Bash sleep 25", "$ npm test"), chatRow(), reasoningRow()])]);
  var olderRootPage = page([agentRoot([chatRow()]), agentRoot([commandRow("Bash sleep 25", "$ npm test")])]);
  var bashLogLine = loggedTitleLine(bashPage);
  var chatLogLine = loggedTitleLine(chatPage);
  var questionsLogLine = loggedTitleLine(questionsPage);
  var reasoningLogLine = loggedTitleLine(reasoningPage);
  var pollLogLine = loggedTitleLine(pollPage);
  var syncChatPage = page([agentRoot([chatRow()])]);
  var directChat = chatRow();
  var directReasoning = reasoningRow();
  var directAction = commandRow("Bash sleep 25");
  var directPoll = commandRow("running Bash", "$ arena-preview poll");
  var twoRows = [commandRow("Bash sleep 25"), chatRow()];
  var twoRowRoot = agentRoot(twoRows);
  var agentShape = agentRoot([]);
  var userShape = userRootNode();
  var headerChat = chatRow();
  var headerShape = agentRoot([headerChat, node("div", "flex w-fit items-center", [])]);
  var headerCard = headerShape.firstElementChild;
  var headerBody = headerCard.firstElementChild;
  var header = node("div", "flex min-h-[40px] items-center", [node("div", "flex size-4", [])]);
  header.parentElement = headerCard;
  headerCard.children.unshift(header);
  var originalHeaderQuery = headerShape.querySelector;
  headerShape.querySelector = function (selector) {
    if (selector === ":scope > div > div.px-3.pb-3 > div.flex.flex-col.gap-2") {
      return headerBody.firstElementChild;
    }
    return originalHeaderQuery(selector);
  };
  assert.equal(rowContainer(headerShape), headerBody.firstElementChild);
  assert.equal(newestRow(headerShape), headerChat);
  expireHold();
  assert.equal(desiredTitle(page([headerShape])), TITLE_PREFIX + "clankers " + AGENT_EMOJI);

  var promptPage = docWith(null, "Arena");
  promptPage.location = { href: "https://arena.ai/agent/session" };
  promptPage.querySelectorAll = function (selector) {
    return selector.includes('aria-haspopup')
      ? [{ textContent: "daedalus read ARENA.md AGENTS.md in full" }]
      : [];
  };
  assert.equal(repoForTitle(promptPage), "daedalus");
  promptPage.querySelector = function (selector) {
    return selector === REPO_LINK_SELECTOR ? repoLink : null;
  };
  assert.equal(repoForTitle(promptPage), "clankers");

  var cases = [
    // The repo name still reads off the GitHub link, and the memory answers while the
    // path holds.
    [repoFromLink(repoLink), "clankers"],
    [repoFromLink(labelOnly), "clankers"],
    [repoFromLink(emptyLink), null],
    [repoFromLink(null), null],
    [repoForTitle(docWith(repoLink, "ChatGPT")), "clankers"],
    [forgetPath(), null],
    [repoForTitle(docWith(null, "ChatGPT")), null],
    [repoForTitle(docWith(repoLink, "ChatGPT")), "clankers"],
    [repoForTitle(docWith(null, "ChatGPT")), "clankers"],
    // The root reads: the agent root is the negation of the user-root chain, and the row
    // container and the newest row come off the last root alone.
    [userRoot(userShape), true],
    [userRoot(agentShape), false],
    [lastRoot(page([agentShape])), agentShape],
    [lastRoot(quietPage), null],
    [rowContainer(userShape), null],
    [rowContainer(agentShape) === childChain(agentShape, 3), true],
    [newestRow(twoRowRoot) === twoRows[0], true],
    [rowKind(directChat), "chat"],
    [rowKind(directReasoning), "reasoning"],
    [rowKind(directAction), "action"],
    [rowKind(null), "none"],
    // The row kind carries the mark: the chat body takes the balloon, the reasoning block
    // takes the thinking mark, and the action rows keep their label words.
    [expireHold(), null],
    [desiredTitle(chatPage), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [expireHold(), null],
    [desiredTitle(reasoningPage), TITLE_PREFIX + "clankers" + vtag + " " + REASONING_EMOJI],
    [expireHold(), null],
    [desiredTitle(bashPage), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    [expireHold(), null],
    [desiredTitle(editPage), TITLE_PREFIX + "clankers" + vtag + " \u270F\uFE0F"],
    [expireHold(), null],
    [desiredTitle(readPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCD6"],
    [expireHold(), null],
    [desiredTitle(searchPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(fetchPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(fetchDonePage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(fetchFailedPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(searchLonePage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(processOutputPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCDC"],
    [expireHold(), null],
    [desiredTitle(outputPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCDC"],
    [expireHold(), null],
    [desiredTitle(gearPage), TITLE_PREFIX + "clankers" + vtag + " \u2699\uFE0F"],
    [expireHold(), null],
    [desiredTitle(questionsPage), TITLE_PREFIX + "clankers" + vtag + " " + QUESTION_EMOJI],
    [expireHold(), null],
    [desiredTitle(pollPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCA4"],
    [expireHold(), null],
    [desiredTitle(playPage), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    // The trailing div is never the row: with two rows the first one marks, and the
    // third row lands only when it takes the second-to-last place.
    [expireHold(), null],
    [desiredTitle(trailingPage), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    [expireHold(), null],
    [desiredTitle(thirdPage), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    // Every row read starts at the last root, so an older root never marks.
    [expireHold(), null],
    [desiredTitle(olderRootPage), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    // The user root carries no mark, and a finished turn drops every row mark.
    [expireHold(), null],
    [desiredTitle(userPage), TITLE_PREFIX + "clankers" + vtag],
    [desiredTitle(endedPage), TITLE_PREFIX + "clankers" + vtag],
    // The answered question card raises no mark of its own.
    [expireHold(), null],
    [summaryCard(summaryRow()), true],
    [desiredTitle(summaryPage), TITLE_PREFIX + "clankers" + vtag],
    // The emoji picker and structured logs identify the row kind.
    [emojiForRow(directChat), AGENT_EMOJI],
    [emojiForRow(directReasoning), REASONING_EMOJI],
    [emojiForRow(directPoll), "\uD83D\uDCA4"],
    [emojiForRow(null), null],
    [chatLogLine.data.kind, "chat"],
    [reasoningLogLine.data.kind, "reasoning"],
    [bashLogLine.data.kind, "action"],
    [pollLogLine.data.kind, "poll"],
    // The hold bridges the gaps inside a turn and dies with the stop control.
    [expireHold(), null],
    [desiredTitle(chatPage), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [desiredTitle(quietPage), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [expireHold(), null],
    [desiredTitle(quietPage), TITLE_PREFIX + "clankers" + vtag],
    // A drifted stop label still opens the gate. The exact wording does not.
    [stopSignal(looseStopDoc()), true],
    [stopSignal(page([], { stop: false })), false],
    // The waiting line is a turn mark too: no control, no hourglass.
    [expireHold(), null],
    [desiredTitle(page([agentRoot([chatRow()])], { stop: false, canvas: rowCanvas(true).canvas })),
      TITLE_PREFIX + "clankers" + vtag],
    // A named action outranks the line, so the poll row keeps its own emoji. The row read
    // runs before the waiting line on the same page.
    [expireHold(), null],
    [
      desiredTitle(page([agentRoot([commandRow("running Bash", "$ arena-preview poll")])], {
        canvas: rowCanvas(true).canvas,
      })),
      TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCA4",
    ],
    [expireHold(), null],
    [waitingSignal(waitingDoc()), true],
    [waitingSignal(blankWaitingDoc()), true],
    // The owner's action row carries the very same canvas as its icon, so the canvas alone
    // never reads as a waiting line and never outranks the Bash row.
    [waitingSignal(actionCanvasDoc()), false],
    [waitingSignal(setDoc), false],
    [expireHold(), null],
    [desiredTitle(waitingDoc()), TITLE_PREFIX + "clankers" + vtag + " " + HOURGLASS_EMOJI],
    [expireHold(), null],
    [desiredTitle(actionCanvasDoc()), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    [WAITING_SELECTOR, 'canvas[width="16"][height="16"]'],
    [WAITING_TEXT_SELECTOR, 'span[class*="whitespace-pre"]'],
    // The ask_user card holds the title with a question mark, and the security check beats
    // it, like every other mark.
    [questionSignal(questionDoc(questionCard())), true],
    [questionSignal(questionDoc(null)), false],
    [expireHold(), null],
    [desiredTitle(questionDoc(questionCard())), TITLE_PREFIX + "clankers" + vtag + " " + QUESTION_EMOJI],
    [expireHold(), null],
    [desiredTitle(questionDoc(questionCard(), true)), TITLE_PREFIX + "clankers" + vtag + " " + CAPTCHA_EMOJI],
    [captchaSignal(captchaDoc()), true],
    [captchaSignal(captchaDoc("closed")), false],
    [captchaSignal(captchaDoc(null, true)), false],
    [openDialog(node("div", "", [])), true],
    // Every mark keeps its own label words, so the map stands.
    [actionEmoji("running Bash"), BASH_EMOJI],
    [actionEmoji("used Bash"), BASH_EMOJI],
    [actionEmoji("Running commands"), BASH_EMOJI],
    [actionEmoji("Ran commands"), BASH_EMOJI],
    [actionEmoji("Reading files"), "\uD83D\uDCD6"],
    [actionEmoji("Explored"), "\uD83D\uDCD6"],
    [actionEmoji("Edit"), "\u270F\uFE0F"],
    [actionEmoji("Writing"), "\u270F\uFE0F"],
    [actionEmoji("Searching the web"), "\uD83D\uDD0D"],
    [actionEmoji("Fetching web page"), "\uD83D\uDD0D"],
    [actionEmoji("Thought for 2 seconds"), "\uD83D\uDCAD"],
    [actionEmoji("Waiting"), "\uD83D\uDCA4"],
    [actionEmoji("get_process_output"), "\uD83D\uDCDC"],
    [actionEmoji("Agent chat"), "\u2699\uFE0F"],
    [actionEmoji(null), null],
    [liveLabel(directAction), "Bash sleep 25"],
    // The buttonless rows keep their label in a body-sm span, and the fetch row's URL anchor
    // never joins the label words.
    [liveLabel(fetchRunningRow()), "Fetching"],
    [liveLabel(fetchRow("text-text-tertiary size-4 shrink-0", "Fetched", "https://example.test/page")), "Fetched"],
    [liveLabel(fetchRow("text-text-tertiary size-4 shrink-0", "Fetch failed", null)), "Fetch failed"],
    [liveLabel(loneSearchRow('Searched for "node test runner"')), 'Searched for "node test runner"'],
    [liveLabel(fetchRow("text-text-tertiary size-4 shrink-0", "https://example.test/page", "https://example.test/page")), null],
    [liveLabel(batchFetchRow()), "Searching the web"],
    [liveLabel(batchFetchDoneRow()), "Searched the web"],
    [liveLabel(processOutputRow()), "get_process_output"],
    [liveLabel(null), null],
    [polls("arena-preview poll --max 1"), true],
    [polls("python preview.py poll"), true],
    [polls("cat skills/arena-skill/README.md | grep polling"), false],
    // The title writes through syncTitle, and the line carries the row anchors.
    [setPriorTitle("ChatGPT"), undefined],
    [expireHold(), null],
    [syncTitle(syncChatPage), true],
    [syncChatPage.title, TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [syncTitle(syncChatPage), false],
    // The hold is still warm from the mark above. The quiet write needs its own window.
    [expireHold(), null],
    [syncTitle(quietPage), true],
    [quietPage.title, TITLE_PREFIX + "clankers" + vtag],
    [bashLogLine.text, "[NemoUtils][title][info] changed"],
    [bashLogLine.data.kind, "action"],
    [bashLogLine.data.emoji, BASH_EMOJI],
    [bashLogLine.data.repo, undefined],
    [chatLogLine.text, "[NemoUtils][title][info] changed"],
    [chatLogLine.data.kind, "chat"],
    [chatLogLine.data.emoji, AGENT_EMOJI],
    [questionsLogLine.text, "[NemoUtils][title][info] changed"],
    [questionsLogLine.data.kind, "action"],
    [questionsLogLine.data.emoji, QUESTION_EMOJI],
    [VERSION, "1.10.27"],
  ];
  // The title writes through syncTitle, which logs the signal that won. The capture keeps
  // the host console clean and returns the last line.
  function loggedTitle(doc) {
    var lines = [];
    var original = console.log;
    console.log = function (text, data) {
      lines.push({ text: text, data: JSON.parse(JSON.stringify(data || {})) });
    };
    try {
      doc.title = "ChatGPT";
      api.syncTitle(doc);
    } finally {
      console.log = original;
    }
    return lines;
  }
  function loggedTitleLine(doc) {
    var lines = loggedTitle(doc);
    assert.equal(lines.length, 1, "normal title output must omit debug conditions");
    return lines[0];
  }

  function polls(text) {
    return api.POLL_RE.test(text.toLowerCase());
  }
  var failed = 0;
  var i;
  for (i = 0; i < cases.length; i += 1) {
    if (cases[i][0] !== cases[i][1]) {
      console.error("check fail", i, cases[i][0], cases[i][1]);
      failed += 1;
    }
  }
  if (failed) {
    throw new Error(failed + " checks failed");
  }
  api.setPriorTitle(quietPage.title);
  var restoreLines = [];
  var restoreConsole = console.log;
  console.log = (...args) => restoreLines.push(args);
  try {
    assert.equal(api.restoreTitle(quietPage), false);
    assert.equal(restoreLines.length, 0, "restoring an equal title must stay silent");
    quietPage.title = "External title";
    api.syncTitle(quietPage);
    api.setPriorTitle("Original title");
    restoreLines.length = 0;
    assert.equal(api.restoreTitle(quietPage), true);
    assert.equal(quietPage.title, "Original title");
    assert.equal(restoreLines.length, 1);
    assert.equal(restoreLines[0][0], "[NemoUtils][title][info] restored");
    api.syncTitle(quietPage);
  } finally {
    console.log = restoreConsole;
  }
  // One line per change stays, and the plain unchanged line is gone: a second
  // sync with the title already in place writes nothing at all.
  var quiet = [];
  var louder = console.log;
  console.log = function () {
    quiet.push(Array.prototype.join.call(arguments, " "));
  };
  try {
    api.syncTitle(quietPage);
    logging.setLogLevel("debug");
    api.syncTitle(quietPage);
  } finally {
    console.log = louder;
    logging.setLogLevel("info");
  }
  if (quiet.length) {
    console.error("check fail", "unchanged title line", quiet.join(" | "));
    throw new Error("the unchanged title line still fires: " + quiet.join(" | "));
  }
  logging.setLogLevel("debug");
  try {
    expireHold();
    var firstChange = loggedTitle(bashPage);
    var secondChange = loggedTitle(bashPage);
    assert.equal(firstChange.length, 2);
    assert.equal(secondChange.length, 2, "real title changes must not use a time throttle");
    assert.equal(firstChange[1].text, "[NemoUtils][title][debug] conditions");
    assert.deepEqual(firstChange[1].data, { captcha: false, question: false, live: true });
    assert.doesNotMatch(JSON.stringify(firstChange), /Bash sleep|row=/);
  } finally {
    logging.setLogLevel("info");
  }
  console.log("ok tab title " + cases.length);
}

function checkHideElements(api) {
  function fakeElement() {
    return {
      hidden: false,
      hasAttribute: function (name) {
        return name === "hidden" && this.hidden;
      },
      setAttribute: function (name) {
        if (name === "hidden") {
          this.hidden = true;
        }
      },
    };
  }

  var CLAIM_TEXT = api.CLAIM_TEXT;
  var CLAIM_DIV_SELECTOR = api.CLAIM_DIV_SELECTOR;
  var FREE_OFFER_TEXT = api.FREE_OFFER_TEXT;
  var FREE_OFFER_DIV_SELECTOR = api.FREE_OFFER_DIV_SELECTOR;
  var MODE_TOGGLE_SELECTOR = api.MODE_TOGGLE_SELECTOR;
  var CODEX_ITEM_SELECTOR = api.CODEX_ITEM_SELECTOR;
  var IMAGES_ITEM_SELECTOR = api.IMAGES_ITEM_SELECTOR;
  var LIBRARY_ITEM_SELECTOR = api.LIBRARY_ITEM_SELECTOR;
  var FREE_BADGE_SELECTOR = api.FREE_BADGE_SELECTOR;
  var FREE_BADGE_TEXT = api.FREE_BADGE_TEXT;
  var HEADER_DIV_SELECTOR = api.HEADER_DIV_SELECTOR;
  var findButtonByText = api.findButtonByText;
  var findClaimDiv = api.findClaimDiv;
  var findFreeOfferDiv = api.findFreeOfferDiv;
  var findModeToggle = api.findModeToggle;
  var findFreeBadge = api.findFreeBadge;
  var findHeaderDiv = api.findHeaderDiv;
  var hideElement = api.hideElement;
  var hideAll = api.hideAll;
  var syncDocument = api.syncDocument;

  // A renamed class leaves a finder matching nothing, and the page then shows the
  // element with no error. The DOM contract is under test beside the behaviour.
  var contract = [
    [CLAIM_TEXT, "Claim offer"],
    [CLAIM_DIV_SELECTOR, "div.col-span-full.mt-1.mb-3\\.5.px-2"],
    [FREE_OFFER_TEXT, "Free offer"],
    [FREE_OFFER_DIV_SELECTOR, "div.flex.items-center.gap-1.select-none"],
    [CODEX_ITEM_SELECTOR, 'button[data-sidebar-destination="builtin:codex"]'],
    [IMAGES_ITEM_SELECTOR, 'button[data-sidebar-destination="builtin:images"]'],
    [LIBRARY_ITEM_SELECTOR, 'button[data-sidebar-destination="builtin:library"]'],
    [FREE_BADGE_SELECTOR, "span.truncate.text-xs.text-secondary.select-none"],
    [FREE_BADGE_TEXT, "Free"],
    [MODE_TOGGLE_SELECTOR, "div.\\@container\\/home-mode-toggle"],
  ];

  var claimDiv = fakeElement();
  var freeDiv = fakeElement();
  var modeToggle = fakeElement();
  var codexItem = fakeElement();
  var imagesItem = fakeElement();
  var libraryRailItem = fakeElement();
  var libraryListItem = fakeElement();
  var freeBadge = fakeElement();
  freeBadge.textContent = " Free ";
  var paidBadge = fakeElement();
  paidBadge.textContent = "Plus";
  var headerDiv = fakeElement();
  var claimButton = {
    textContent: " Claim offer ",
    closest: function (selector) {
      return selector === CLAIM_DIV_SELECTOR ? claimDiv : null;
    },
  };
  var bareButton = {
    textContent: "Claim offer",
    closest: function () {
      return null;
    },
  };
  var freeButton = {
    textContent: " Free offer ",
    closest: function (selector) {
      return selector === FREE_OFFER_DIV_SELECTOR ? freeDiv : null;
    },
  };
  var otherButton = {
    textContent: "Free trial",
    closest: function () {
      return freeDiv;
    },
  };

  function buttonDoc(buttons) {
    return {
      querySelectorAll: function (selector) {
        return selector === "button" ? buttons : [];
      },
    };
  }
  var claimDoc = buttonDoc([otherButton, claimButton]);
  var bareDoc = buttonDoc([bareButton]);
  var freeDoc = buttonDoc([otherButton, freeButton]);
  var emptyDoc = {
    querySelector: function () {
      return null;
    },
    querySelectorAll: function () {
      return [];
    },
  };
  var modeToggleDoc = {
    querySelector: function (selector) {
      return selector === MODE_TOGGLE_SELECTOR ? modeToggle : null;
    },
  };
  var badgeDoc = {
    querySelector: function (selector) {
      return selector === FREE_BADGE_SELECTOR ? freeBadge : null;
    },
  };
  var paidBadgeDoc = {
    querySelector: function (selector) {
      return selector === FREE_BADGE_SELECTOR ? paidBadge : null;
    },
  };
  var headerDoc = {
    querySelector: function (selector) {
      return selector === HEADER_DIV_SELECTOR ? headerDiv : null;
    },
  };
  function action(text) {
    var button = fakeElement();
    button.textContent = text;
    button.getAttribute = function () { return null; };
    return button;
  }
  var headerUpgradeButton = action("Upgrade");
  var headerShareButton = action("Share");
  var sidebarUpgradeButton = action("Upgrade");
  var plusButton = action("Upgrade to Plus");
  var mixedPlusButton = action("Upgrade to Plus");
  var unrelatedShare = action("Share");
  var unrelatedUpgrade = action("Upgrade");
  var otherHeaderUpgrade = action("Upgrade project");
  var otherHeaderShare = action("Share feedback");
  var otherSidebarUpgrade = action("Upgrade guide");
  function actionGroup(buttons) {
    var group = fakeElement();
    group.textContent = buttons.map(function (button) { return button.textContent; }).join("");
    group.querySelectorAll = function (selector) { return selector === "button" ? buttons : []; };
    buttons.forEach(function (button) { button.closest = function () { return group; }; });
    return group;
  }
  var headerUpgrade = actionGroup([headerUpgradeButton]);
  var headerShare = actionGroup([headerShareButton]);
  var sharedHeaderUpgrade = action("Upgrade");
  var sharedHeaderOther = action("Keep");
  var sharedHeaderGroup = actionGroup([sharedHeaderUpgrade, sharedHeaderOther]);
  var sidebarUpgrade = actionGroup([sidebarUpgradeButton]);
  var plusRow = actionGroup([plusButton]);
  var unrelatedRow = actionGroup([action("Retry"), action("View details")]);
  var mixedRow = actionGroup([mixedPlusButton, action("View details")]);
  // One document answers every selector, so the sync pass itself is under test: a target left out of syncDocument leaves its element unhidden here.
  // The library answers twice, once for the collapsed rail and once for the open nav list.
  var fullDoc = {
    querySelector: function (selector) {
      if (selector === MODE_TOGGLE_SELECTOR) return modeToggle;
      if (selector === FREE_BADGE_SELECTOR) return freeBadge;
      if (selector === HEADER_DIV_SELECTOR) return headerDiv;
      return null;
    },
    querySelectorAll: function (selector) {
      if (selector === "button") return [claimButton, freeButton, headerUpgradeButton,
        headerShareButton, sidebarUpgradeButton, plusButton, unrelatedShare, unrelatedUpgrade];
      if (selector === "header button") return [headerUpgradeButton, headerShareButton, otherHeaderUpgrade, otherHeaderShare, sharedHeaderUpgrade, sharedHeaderOther];
      if (selector === "#app-shell-sidebar button") return [sidebarUpgradeButton, otherSidebarUpgrade];
      if (selector === "div.flex.flex-wrap.items-center.justify-center.gap-2") return [plusRow, unrelatedRow, mixedRow];
      if (selector === CODEX_ITEM_SELECTOR) return [codexItem];
      if (selector === IMAGES_ITEM_SELECTOR) return [imagesItem];
      if (selector === LIBRARY_ITEM_SELECTOR) return [libraryRailItem, libraryListItem];
      return [];
    },
  };

  hideAll(fullDoc, LIBRARY_ITEM_SELECTOR);
  hideAll(emptyDoc, LIBRARY_ITEM_SELECTOR);
  var cases = [
    [findButtonByText(claimDoc, CLAIM_TEXT), claimButton],
    [findButtonByText(emptyDoc, CLAIM_TEXT), null],
    [findClaimDiv(claimDoc), claimDiv],
    [findClaimDiv(bareDoc), null],
    [findClaimDiv(emptyDoc), null],
    [findFreeOfferDiv(freeDoc), freeDiv],
    [findFreeOfferDiv(emptyDoc), null],
    [findModeToggle(modeToggleDoc), modeToggle],
    [findModeToggle(emptyDoc), null],
    [findFreeBadge(badgeDoc), freeBadge],
    [findFreeBadge(paidBadgeDoc), null],
    [findFreeBadge(emptyDoc), null],
    [findHeaderDiv(headerDoc), headerDiv],
    [findHeaderDiv(emptyDoc), null],
    [libraryRailItem.hasAttribute("hidden"), true],
    [libraryListItem.hasAttribute("hidden"), true],
    [hideElement(claimDiv), true],
    [claimDiv.hasAttribute("hidden"), true],
    [hideElement(claimDiv), false],
    [hideElement(null), false],
  ];
  var failed = 0;
  var i;
  for (i = 0; i < contract.length; i += 1) {
    if (contract[i][0] !== contract[i][1]) {
      console.error("contract fail", i, contract[i][0], contract[i][1]);
      failed += 1;
    }
  }
  for (i = 0; i < cases.length; i += 1) {
    if (cases[i][0] !== cases[i][1]) {
      console.error("check fail", i, cases[i][0], cases[i][1]);
      failed += 1;
    }
  }
  syncDocument(fullDoc);
  var synced = [
    claimDiv,
    freeDiv,
    modeToggle,
    codexItem,
    imagesItem,
    libraryRailItem,
    libraryListItem,
    freeBadge,
    headerDiv,
    headerUpgrade,
    headerShare,
    sharedHeaderUpgrade,
    sidebarUpgrade,
    plusRow,
    mixedPlusButton,
  ];
  for (i = 0; i < synced.length; i += 1) {
    if (!synced[i].hasAttribute("hidden")) {
      console.error("sync fail", i);
      failed += 1;
    }
  }
  [unrelatedShare, unrelatedUpgrade, unrelatedRow, mixedRow, otherHeaderUpgrade, otherHeaderShare, otherSidebarUpgrade, sharedHeaderGroup, sharedHeaderOther].forEach(function (el) {
    if (el.hasAttribute("hidden")) {
      console.error("unrelated action was hidden");
      failed += 1;
    }
  });
  if (failed) {
    throw new Error(failed + " checks failed");
  }
  console.log(
    "ok hide elements " + (contract.length + cases.length + synced.length),
  );
}

function checkAutoThink(api) {
  var THINK_PILL_SELECTOR = api.THINK_PILL_SELECTOR;
  var PRESS_INTERVAL_MS = api.PRESS_INTERVAL_MS;
  var findThinkPill = api.findThinkPill;
  var pressThink = api.pressThink;

  var thinkPill = {
    textContent: " Think ",
    clicked: 0,
    click: function () {
      this.clicked += 1;
    },
  };
  var otherPill = {
    textContent: "Deep research",
    clicked: 0,
    click: function () {
      this.clicked += 1;
    },
  };
  var fullDoc = {
    querySelectorAll: function (selector) {
      return selector === THINK_PILL_SELECTOR ? [otherPill, thinkPill] : [];
    },
  };
  var emptyDoc = {
    querySelectorAll: function () {
      return [];
    },
  };
  var cases = [
    [findThinkPill(fullDoc), thinkPill],
    [findThinkPill(emptyDoc), null],
    [pressThink(fullDoc), true],
    [thinkPill.clicked, 1],
    [otherPill.clicked, 0],
    [pressThink(emptyDoc), false],
    [PRESS_INTERVAL_MS, 1000],
  ];
  var failed = 0;
  var i;
  for (i = 0; i < cases.length; i += 1) {
    if (cases[i][0] !== cases[i][1]) {
      console.error("check fail", i, cases[i][0], cases[i][1]);
      failed += 1;
    }
  }
  if (failed) {
    throw new Error(failed + " checks failed");
  }
  console.log("ok auto think " + cases.length);
}

function checkKeepAwake(api) {
  var wakeLockPlan = api.wakeLockPlan;
  assert.equal(wakeLockPlan(true, false, true), "acquire");
  assert.equal(wakeLockPlan(true, true, true), "none", "A held lock stays");
  assert.equal(wakeLockPlan(true, false, false), "none", "A hidden page cannot take the lock");
  assert.equal(wakeLockPlan(false, true, true), "release", "A finished turn drops the lock");
  assert.equal(wakeLockPlan(false, true, false), "release", "A hidden page drops a held lock");
  assert.equal(wakeLockPlan(false, false, true), "none");
  console.log("ok keep awake 6");
}

function run(name, check) {
  try {
    check();
  } catch (error) {
    throw new Error(`${name}: ${error.message}`);
  }
}

function checkStateDownload(api, session, logging) {
  var stateFileName = api.stateFileName;
  var stateDownload = api.stateDownload;
  var stateMemory = api.stateMemory;
  var stateRemembered = api.stateRemembered;
  var stateDelivery = api.stateDelivery;
  var saveMoved = api.saveMoved;
  var overwriteAsk = api.overwriteAsk;
  var overwriteLine = api.overwriteLine;
  var stateAction = api.stateAction;
  var panelNeeded = api.panelNeeded;
  var handleMatchesScope = api.handleMatchesScope;
  var stateScope = api.stateScope;
  var stateRepo = api.stateRepo;
  var stateBranch = api.stateBranch;
  var stateScopeKey = api.stateScopeKey;
  var readSlug = api.readSlug;
  var slugFromBare = api.slugFromBare;
  var pagePicker = api.pagePicker;
  var writtenName = api.writtenName;
  var STATE_LINES = api.STATE_LINES;
  var copyLine = api.copyLine;
  var getLine = api.getLine;
  var writeFailLine = api.writeFailLine;
  var managerFailLine = api.managerFailLine;
  var stateError = api.stateError;
  var downloadRoute = api.downloadRoute;
  var stateDownloadRoute = api.stateDownloadRoute;
  var counts = { notes: 12, tasks: 4 };
  var repo = "clankers";
  var branch = "main";
  // The name carries the repository, then the branch, then the server's stamp and the record
  // counts, so two repos and their branches never collide in one folder.
  assert.equal(
    stateFileName(repo, branch, "2026-10-06T06:12:33.123456+00:00", counts),
    "clankers-main-20261006T061233-n12-t4.ndjson",
  );
  assert.equal(
    stateFileName("my repo", "feat/x", "2026-10-06T06:12:33", counts),
    "my-repo-feat-x-20261006T061233-n12-t4.ndjson",
  );
  assert.equal(
    stateFileName("", "", "2026-10-06T06:12:33", counts),
    "arena-20261006T061233-n12-t4.ndjson",
  );
  assert.equal(
    stateFileName(repo, branch, "2026-10-06T06:12:33", { notes: 0, tasks: 0 }),
    "clankers-main-20261006T061233-n0-t0.ndjson",
  );
  assert.equal(stateFileName(repo, branch, null, counts), "clankers-main-n12-t4.ndjson");
  // Only a stamp that differs from the last write fills the file.
  assert.equal(stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "").kind, "download");
  assert.equal(
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "2026-10-05T20:00:00").kind,
    "download",
  );
  var repeated = stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "2026-10-06T06:12:33");
  assert.equal(repeated.kind, "unchanged");
  assert.equal(repeated.name, "clankers-main-20261006T061233-n12-t4.ndjson");
  assert.match(repeated.message, /unchanged since the last write/);
  // A stamp that goes backward is a wiped or replaced preview, so nothing overwrites the
  // owner's file with an older state.
  var stale = stateDownload(repo, branch, "2026-10-05T20:00:00", counts, "2026-10-06T06:12:33");
  assert.equal(stale.kind, "stale");
  assert.match(stale.message, /Stale preview state/);
  // A payload with no stamp says so instead of writing an undated file.
  var unstamped = stateDownload(repo, branch, null, counts, "");
  assert.equal(unstamped.kind, "error");
  assert.match(unstamped.message, /carries no stamp/);
  // The approved pair: the newest note stamp and the newest task stamp.
  // A rollback leaves older records while a new note moves the state stamp. The pair rejects that write. The owner keeps the newer state.
  var memory = stateMemory("2026-10-05T20:00:00", {
    note: "2026-10-05T20:00:00",
    task: "2026-10-05T19:00:00",
  });
  assert.equal(memory.stamp, "2026-10-05T20:00:00");
  assert.equal(memory.note, "2026-10-05T20:00:00");
  assert.equal(memory.task, "2026-10-05T19:00:00");
  var restored = stateRemembered(JSON.stringify(memory));
  assert.equal(restored.stamp, memory.stamp);
  assert.equal(restored.note, memory.note);
  assert.equal(restored.task, memory.task);
  var legacy = stateRemembered("2026-10-05T20:00:00");
  assert.equal(legacy.stamp, "2026-10-05T20:00:00");
  assert.equal(legacy.note, "");
  assert.equal(legacy.task, "");
  var rolledBackTask = stateDownload(
    repo,
    branch,
    "2026-10-06T06:12:33",
    counts,
    memory,
    { note: "2026-10-06T06:12:33", task: "2026-10-05T18:00:00" },
  );
  assert.equal(rolledBackTask.kind, "stale");
  assert.match(rolledBackTask.message, /task stamp went backward/);
  // A forced save takes the state whatever the memory says: the same stamp, an older
  // stamp and a rolled-back pair all write, and the write moves the reference.
  assert.equal(
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "2026-10-06T06:12:33", null, true).kind,
    "download",
  );
  assert.equal(
    stateDownload(repo, branch, "2026-10-05T20:00:00", counts, "2026-10-06T06:12:33", null, true).kind,
    "download",
  );
  assert.equal(
    stateDownload(
      repo,
      branch,
      "2026-10-06T06:12:33",
      counts,
      memory,
      { note: "2026-10-06T06:12:33", task: "2026-10-05T18:00:00" },
      true,
    ).kind,
    "download",
  );
  var rolledBackNote = stateDownload(
    repo,
    branch,
    "2026-10-06T06:12:33",
    counts,
    memory,
    { note: "2026-10-05T18:00:00", task: "2026-10-06T06:00:00" },
  );
  assert.equal(rolledBackNote.kind, "stale");
  assert.match(rolledBackNote.message, /note stamp went backward/);
  // Both stamps of the pair move forward: the write lands.
  var pairForward = stateDownload(
    repo,
    branch,
    "2026-10-06T06:12:33",
    counts,
    memory,
    { note: "2026-10-06T06:12:33", task: "2026-10-06T06:00:00" },
  );
  assert.equal(pairForward.kind, "download");
  var deletion = stateDownload(
    repo,
    branch,
    "2026-10-06T06:12:33",
    counts,
    {
      stamp: "2026-10-06T06:12:33",
      note: "2026-10-06T06:12:33",
      task: "2026-10-05T19:00:00",
    },
    { note: "2026-10-05T20:00:00", task: "2026-10-05T19:00:00" },
  );
  assert.equal(deletion.kind, "unchanged");
  // A payload without the pair, or a memory saved before the pair existed, keeps the old rule.
  assert.equal(
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, memory).kind,
    "download",
  );
  assert.equal(
    stateDownload(
      repo,
      branch,
      "2026-10-06T06:12:33",
      counts,
      "2026-10-05T20:00:00",
      { note: "2026-10-06T06:12:33", task: "2026-10-05T19:00:00" },
    ).kind,
    "download",
  );
  // One route per state: the chosen file, the one-time pick, or the stamped download on a
  // browser without the file picker.
  var fresh = stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "");
  assert.equal(stateDelivery(fresh, true, true), "write");
  assert.equal(stateDelivery(fresh, false, true), "pick");
  assert.equal(stateDelivery(fresh, false, false), "download");
  assert.equal(stateDelivery(repeated, true, true), "unchanged");
  assert.equal(stateDelivery(stale, true, true), "stale");
  // The repo bar carries the pair and the branch anchor, so the name scopes to this repo and
  // branch and two repos never collide in one folder.
  var branchLink = {
    getAttribute: function (name) {
      if (name === "href") return "https://github.com/nemoe7/clankers/tree/arena%2F01a0fd4f-clankers";
      if (name === "title") return "main \u2192 arena/01a0fd4f-clankers";
      return null;
    },
  };
  var bar = {
    querySelectorAll: function (selector) {
      if (selector === "span.truncate") return [{ textContent: "nemoe7/clankers" }];
      if (selector === "a, [title]") return [branchLink];
      return [];
    },
  };
  var doc = { querySelector: function () { return bar; } };
  var scope = stateScope(doc);
  assert.equal(scope.repo, "clankers");
  assert.equal(scope.branch, "arena/01a0fd4f-clankers");
  assert.equal(
    stateFileName(scope.repo, scope.branch, "2026-10-06T06:12:33", counts),
    "clankers-arena-01a0fd4f-clankers-20261006T061233-n12-t4.ndjson",
  );
  // The server stamp carries the timezone. The name keeps the seconds alone.
  assert.equal(
    stateFileName(scope.repo, scope.branch, "2026-10-06T08:33:57+00:00", null),
    "clankers-arena-01a0fd4f-clankers-20261006T083357.ndjson",
  );
  // An ongoing session renders the repository as a bare chip without its owner, so a slash-less slug-like span in the
  // bar still names the repository for the picker and the fill, instead of falling through to a header session token.
  var bareBar = {
    querySelectorAll: function (selector) {
      if (selector === "span.truncate") return [{ textContent: "daedalus" }];
      if (selector === "a, [title]") return [branchLink];
      return [];
    },
  };
  var bareDoc = {
    querySelector: function () { return bareBar; },
    querySelectorAll: function (selector) {
      return selector.indexOf("span.truncate") !== -1 ? [{ textContent: "daedalus" }] : [];
    },
  };
  assert.equal(slugFromBare("daedalus"), "daedalus");
  assert.equal(slugFromBare("nemoe7/daedalus"), null);
  assert.equal(slugFromBare("  "), null);
  assert.equal(stateRepo(bareDoc), "daedalus");
  assert.equal(readSlug(bareDoc), "daedalus");
  assert.equal(stateScope(bareDoc).repo, "daedalus");
  var promptDoc = {
    location: { href: "https://arena.ai/agent/session" },
    title: "Arena | previous",
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      return selector.includes('aria-haspopup')
        ? [{ textContent: "daedalus read ARENA.md AGENTS.md in full before your first edit" }]
        : [];
    },
  };
  assert.equal(readSlug(promptDoc), "daedalus");
  assert.equal(stateRepo(promptDoc), "daedalus");
  promptDoc.location.href = "https://arena.ai/agent";
  assert.equal(readSlug(promptDoc), "previous");
  promptDoc.location.href = "https://arena.ai/agent/session";
  promptDoc.querySelectorAll = function () {
    return [{ textContent: "not a repo read ARENA.md" }];
  };
  assert.equal(readSlug(promptDoc), "previous");
  // A new chat on /agent has no session bar, so the composer's own picker row carries the
  // repository chip ahead of the branch chip, and the fill reads it there.
  var composerDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "nemoe7/clankers" }, { textContent: "main" }];
    },
  };
  assert.equal(readSlug(composerDoc), "clankers");
  assert.equal(stateRepo(composerDoc), "clankers");
  // The leading chip is the repository, so a chip that is not the owner/repo form never
  // answers, and the title still carries the read.
  var branchChipDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "main" }, { textContent: "nemoe7/clankers" }];
    },
    title: "Arena | clankers",
  };
  assert.equal(readSlug(branchChipDoc), "clankers");
  // A branch with a slash wears the owner/repo shape too, so two such chips stay ambiguous and
  // the title decides instead of a branch.
  var branchFirstDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "arena/595e8dec-clankers" }, { textContent: "nemoe7/clankers" }];
    },
    title: "Arena | clankers",
  };
  assert.equal(readSlug(branchFirstDoc), "clankers");
  // A selected diff branch puts the session branch beside the repository chip, and the tab title stays bare on that page.
  // The branch wears the platform namespace, so the chip read still names the repository with nothing else to fall back on.
  var diffBranchDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "nemoe7/daedalus" }, { textContent: "arena/fef1ae85-daedalus" }];
    },
    title: "Arena",
  };
  assert.equal(readSlug(diffBranchDoc), "daedalus");
  assert.equal(stateRepo(diffBranchDoc), "daedalus");
  // A branch in another namespace carries no platform mark, so the pair stays ambiguous and
  // the title alone can answer.
  var otherBranchDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "nemoe7/daedalus" }, { textContent: "feature/panel" }];
    },
    title: "Arena",
  };
  assert.equal(readSlug(otherBranchDoc), null);
  // The page's own chip outranks the title, because the title can still name the previous
  // session after a new chat opens on the same tab.
  var staleTitleDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "nemoe7/daedalus" }];
    },
    title: "Arena | clankers",
  };
  assert.equal(readSlug(staleTitleDoc), "daedalus");
  // The header leaves the page while a dialog holds it, so the fill's saved slug names the
  // repository. The branch stays empty.
  session.value = "clankers";
  assert.equal(stateRepo({ querySelector: function () { return null; } }), "clankers");
  assert.equal(
    stateScope({ querySelector: function () { return null; } }).branch,
    "",
  );
  session.value = null;
  assert.equal(stateRepo({ querySelector: function () { return null; } }), "");
  // One storage scope per repo and branch, so a second tab of another session never
  // shares the stamp memory or the chosen file with this one.
  assert.equal(stateScopeKey("clankers", "main"), stateScopeKey("clankers", "main"));
  assert.notEqual(stateScopeKey("clankers", "main"), stateScopeKey("widget", "main"));
  assert.notEqual(stateScopeKey("clankers", "main"), stateScopeKey("clankers", "feat/x"));
  assert.equal(stateScopeKey("", ""), "arena");
  assert.equal(stateScopeKey("my repo", "feat/x"), "my-repo-feat-x");
  // The manager's download beats the page link, because the page policy can block a link.
  assert.equal(downloadRoute(true), "manager");
  assert.equal(downloadRoute(false), "link");
  assert.equal(stateDownloadRoute(), "manager");
  // A title without the arrow falls back to the href. A page without the bar stays empty.
  branchLink.getAttribute = function (name) {
    if (name === "href") return "https://github.com/other/repo/tree/feat%2Fx";
    return "";
  };
  assert.equal(stateScope(doc).branch, "feat/x");
  assert.equal(
    JSON.stringify(stateScope({ querySelector: function () { return null; } })),
    JSON.stringify({ repo: "", branch: "" }),
  );
  // The picker call runs on the page window. A realm without one yields no picker rather
  // than a throw, which is what keeps the download route alive.
  assert.equal(pagePicker(), null);
  // The chosen file keeps its own name, so the save line names the file the write reached.
  assert.equal(writtenName({ name: "clankers-state.ndjson" }, "generated.ndjson"), "clankers-state.ndjson");
  assert.equal(writtenName({}, "generated.ndjson"), "generated.ndjson");
  assert.equal(writtenName(null, "generated.ndjson"), "generated.ndjson");
  // The bar leaves the page while a dialog holds it. With no saved slug either, the title
  // still carries the repository this script wrote.
  session.value = null;
  assert.equal(
    stateRepo({ querySelector: function () { return null; }, title: "Arena | clankers \uD83D\uDCA4" }),
    "clankers",
  );
  assert.equal(
    stateRepo({ querySelector: function () { return null; }, title: "ChatGPT" }),
    "",
  );
  // The Arena UI moves the GitHub integration around, so the repo/branch span can vanish. The conversation header still opens with the repository name, and its first word is the repository.
  // That read comes before the tab title. The tab title is the reliable read, so it comes before the greppier header read.
  var headerSpan = { textContent: "clankers read ARENA.md AGENTS.md in full before your first edit" };
  var headerDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      return selector.indexOf("aria-haspopup") !== -1 ? [headerSpan] : [];
    },
    title: "Arena | other",
  };
  assert.equal(stateRepo(headerDoc), "other");
  // With no title at all, the header read names the repository.
  var headerOnlyDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      return selector.indexOf("aria-haspopup") !== -1 ? [headerSpan] : [];
    },
  };
  assert.equal(stateRepo(headerOnlyDoc), "clankers");
  // A header span with no slug-like first word and no title yields nothing.
  headerSpan.textContent = "";
  assert.equal(stateRepo(headerOnlyDoc), "");
  // The saved slug still wins over the header read when the title is gone.
  session.value = "saved";
  headerSpan.textContent = "clankers read ARENA.md";
  assert.equal(stateRepo(headerOnlyDoc), "saved");
  session.value = null;
  assert.equal(stateAction("pick", false), "block");
  assert.equal(stateAction("pick", true), "hint");
  assert.equal(stateAction("download", false), "block");
  assert.equal(stateAction("download", true), "download");
  assert.equal(stateAction("write", true), "write");
  // The no-file card: a manual press always shows it, and an automatic tick shows it once
  // per unconfigured period.
  assert.equal(panelNeeded(true, true), true);
  assert.equal(panelNeeded(true, false), true);
  assert.equal(panelNeeded(false, false), true);
  assert.equal(panelNeeded(false, true), false);
  assert.equal(stateAction("unchanged", false), "unchanged");
  // The failure lines name the error and the way on, and each heads the corner card too.
  assert.equal(
    writeFailLine({ name: "NotAllowedError" }),
    "write failed (NotAllowedError); press the choose entry for the file again",
  );
  assert.equal(
    writeFailLine(null),
    "write failed (unknown); press the choose entry for the file again",
  );
  assert.equal(
    managerFailLine({ error: "NETWORK" }),
    "manager download failed (NETWORK); using the link",
  );
  assert.equal(managerFailLine(null), "manager download failed (unknown); using the link");
  // The panel keeps its text, but the console carries only the error code and status.
  var errorLines = [];
  var restoreLog = console.error;
  console.error = function () { errorLines.push(JSON.stringify(Array.from(arguments))); };
  try {
    stateError("GET 500 http://localhost:8000/api/copy-state", null, null, "copy-state", 500);
  } finally {
    console.error = restoreLog;
  }
  assert.match(errorLines[0], /\[NemoUtils\]\[state\]\[error\] failed/);
  assert.match(errorLines[0], /copy-state/);
  assert.match(errorLines[0], /500/);
  assert.doesNotMatch(errorLines[0], /localhost|api\/copy-state/);
  assert.equal(getLine(200, "http://localhost:8000"), "GET 200 http://localhost:8000");
  // The owner's line texts: the no-file hint names the dialog it opens, a
  // stale state reads as a history mismatch, and a closed picker reads as a plain no-file line.
  assert.equal(STATE_LINES.hint, "no file selected; launching dialog");
  assert.equal(STATE_LINES.history, "history does not match");
  assert.equal(STATE_LINES.pickerClosed, "no file selected;");
  // The refused copy reads as a `GET` too, and the missing frame reads plainly.
  assert.equal(STATE_LINES.noPreview, "no preview detected");
  assert.equal(
    copyLine(500, "http://localhost:8000"),
    "GET 500 http://localhost:8000/api/copy-state",
  );
  // Every comparison in the save path writes its own line, so one filter shows which test
  // refused a write.
  logging.setLogLevel("debug");
  var compared = [];
  var originalLog = console.log;
  console.log = function () {
    compared.push(JSON.stringify(Array.from(arguments)));
  };
  try {
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "2026-10-06T06:12:33");
    stateDownload(repo, branch, "2026-10-05T20:00:00", counts, "2026-10-06T06:12:33");
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "");
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, {
      stamp: "2026-10-05T20:00:00",
      note: "2026-10-06T05:30:00",
      task: "2026-10-06T05:00:00",
    }, { note: "2026-10-06T05:00:00", task: "2026-10-06T06:00:00" });
    stateDownload(repo, branch, null, counts, "");
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, {
      stamp: "2026-10-06T06:12:33",
      note: "2026-10-06T06:12:33",
      task: "2026-10-06T06:12:33",
    }, { note: "2026-10-06T06:12:33", task: "2026-10-06T06:12:33" });
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, {
      stamp: "2026-10-05T20:00:00",
      note: "2026-10-06T05:30:00",
      task: "2026-10-06T05:00:00",
    }, { note: "2026-10-06T05:00:00", task: "2026-10-06T06:00:00" }, true);
  } finally {
    console.log = originalLog;
    logging.setLogLevel("info");
  }
  function comparedLine(event, fields) {
    return compared.some(function (line) {
      var parts = JSON.parse(line);
      return parts[0] === "[NemoUtils][state][debug] " + event &&
        JSON.stringify(parts[1] || {}) === JSON.stringify(fields || {});
    });
  }
  assert.ok(comparedLine("compare", { group: "note", verdict: "older" }));
  assert.ok(comparedLine("compare", { group: "task", verdict: "forward" }));
  assert.ok(comparedLine("no-stamp"));
  assert.ok(comparedLine("compare", { group: "note", verdict: "same" }));
  assert.ok(comparedLine("compare", { group: "task", verdict: "same" }));
  assert.ok(comparedLine("force-stamp", { group: "note" }));
  assert.ok(comparedLine("force-stamp", { group: "task" }));
  assert.doesNotMatch(compared.join("\n"), /2026-|http|private/);
  assert.equal(handleMatchesScope({ name: "clankers-main.ndjson" }, "clankers", "main"), true);
  assert.equal(
    handleMatchesScope({ name: "clankers-main-20261006T061233-n12-t4.ndjson" }, "clankers", "main"),
    true,
  );
  assert.equal(handleMatchesScope({ name: "f360-main.ndjson" }, "clankers", "main"), false);
  assert.equal(handleMatchesScope({ name: "clankers-mainx.ndjson" }, "clankers", "main"), false);
  assert.equal(handleMatchesScope({ name: "my-backup.ndjson" }, "clankers", "main"), false);
  assert.equal(handleMatchesScope(null, "clankers", "main"), false);
  assert.equal(handleMatchesScope({}, "clankers", "main"), false);
  assert.equal(handleMatchesScope({ name: "f360-main.ndjson" }, "", ""), false);
  assert.equal(handleMatchesScope({ name: "arena.ndjson" }, "", ""), true);
  // A save moves when the session branch is unknown, or when the preview URL differs from the one that last wrote this scope.
  // A moved save that would write asks before it writes. A forced save never asks.
  assert.equal(saveMoved("", "", "https://p.example"), true, "No branch moves the save");
  assert.equal(saveMoved("arena/x", "", "https://p.example"), false, "A first write does not move");
  assert.equal(saveMoved("arena/x", "https://p.example", "https://p.example"), false);
  assert.equal(saveMoved("arena/x", "https://p.example", "https://q.example"), true);
  assert.equal(
    saveMoved("", "https://p.example", "https://p.example", "clankers-arena-x"),
    false,
    "A remembered scope keeps the same preview after overwrite",
  );
  assert.equal(
    saveMoved("", "https://p.example", "https://q.example", "clankers-arena-x"),
    true,
    "A new preview still moves the save",
  );
  assert.equal(
    saveMoved("arena/y", "https://p.example", "https://p.example", "clankers-arena-x", "arena/x"),
    true,
    "A new branch still moves the save",
  );

  assert.equal(overwriteAsk(true, { kind: "download" }, true, false), true);
  assert.equal(overwriteAsk(true, { kind: "download" }, true, true), false, "A forced save writes");
  assert.equal(overwriteAsk(false, { kind: "download" }, true, false), false);
  assert.equal(overwriteAsk(true, { kind: "unchanged" }, true, false), false, "Nothing to write");
  assert.equal(overwriteAsk(true, { kind: "download" }, false, false), false, "No file to protect");

  // The reset window accepts a URL-only move within 150 seconds either side of the four PHT
  // boundaries. A branch move, a missing branch and an outside-window clock still ask.
  var previousBoundary = api.previousBoundary;
  var inResetWindow = api.inResetWindow;
  var resetWindowAccepts = api.resetWindowAccepts;
  assert.equal(api.resetWindowOn(), true, "the reset-window switch ships on");
  assert.equal(
    previousBoundary(new Date("2026-10-15T06:59:00Z")).toISOString(),
    "2026-10-15T06:00:00.000Z",
    "14:59 PHT sits after the 14:00 boundary",
  );
  assert.equal(
    previousBoundary(new Date("2026-10-14T17:30:00Z")).toISOString(),
    "2026-10-14T12:00:00.000Z",
    "01:30 PHT falls back to the previous 20:00 boundary",
  );
  assert.equal(inResetWindow(new Date("2026-10-15T06:02:30Z")), true, "150 seconds after 14:00 PHT");
  assert.equal(inResetWindow(new Date("2026-10-15T05:57:30Z")), true, "150 seconds before 14:00 PHT");
  assert.equal(inResetWindow(new Date("2026-10-15T06:02:31Z")), false, "151 seconds after leaves");
  assert.equal(inResetWindow(new Date("2026-10-15T05:57:29Z")), false, "151 seconds before leaves");
  assert.equal(inResetWindow(new Date("2026-10-15T00:30:00Z")), false, "08:30 PHT waits");
  var atWindow = new Date("2026-10-15T06:01:00Z");
  var outside = new Date("2026-10-15T02:00:00Z");
  assert.equal(
    resetWindowAccepts(atWindow, true, "main", "https://old.arena.site", "https://new.arena.site", "main"),
    true,
    "an in-window URL-only move writes without the prompt",
  );
  assert.equal(
    resetWindowAccepts(atWindow, false, "main", "https://old.arena.site", "https://new.arena.site", "main"),
    false,
    "the switch off keeps the prompt",
  );
  assert.equal(
    resetWindowAccepts(outside, true, "main", "https://old.arena.site", "https://new.arena.site", "main"),
    false,
    "outside the window the prompt stands",
  );
  assert.equal(
    resetWindowAccepts(atWindow, true, "dev", "https://old.arena.site", "https://new.arena.site", "main"),
    false,
    "a branch mismatch keeps the prompt",
  );
  assert.equal(
    resetWindowAccepts(atWindow, true, "", "https://old.arena.site", "https://new.arena.site", ""),
    false,
    "a missing branch keeps the prompt",
  );
  assert.equal(
    resetWindowAccepts(atWindow, true, "main", "https://new.arena.site", "https://new.arena.site", "main"),
    false,
    "a URL that did not move needs no acceptance",
  );
  assert.match(overwriteLine("clankers-main.ndjson"), /Overwrite clankers-main\.ndjson with this state\?$/);
  const overwriteContext = {
    branch: "main", rememberedBranch: "main", lastScope: "clankers-main",
    base: "https://new.arena.site", rememberedBase: "https://old.arena.site",
    memory: { stamp: "2026-10-05T20:00:00", note: "2026-10-05T19:00:00", task: "2026-10-05T18:00:00" },
    stamp: "2026-10-06T20:00:00",
    stamps: { note: "2026-10-05T19:00:00", task: "2026-10-05T18:00:00" },
  };
  const urlPrompt = overwriteLine("clankers-main.ndjson", overwriteContext);
  assert.match(urlPrompt, /Preview URL changed from https:\/\/old\.arena\.site to https:\/\/new\.arena\.site/);
  assert.doesNotMatch(urlPrompt, /Branch changed/);
  assert.match(urlPrompt, /overall forward, notes same, and tasks same/);
  assert.match(urlPrompt, /Equal stamps do not prove equal file contents/);
  assert.match(urlPrompt, /Overwrite clankers-main\.ndjson with this state\?/);
  const branchPrompt = overwriteLine("file.ndjson", {
    ...overwriteContext, base: overwriteContext.rememberedBase, branch: "dev",
  });
  assert.match(branchPrompt, /Branch changed from main to dev/);
  assert.doesNotMatch(branchPrompt, /Preview URL changed/);
  const bothPrompt = overwriteLine("file.ndjson", { ...overwriteContext, branch: "dev" });
  assert.match(bothPrompt, /Preview URL changed/);
  assert.match(bothPrompt, /Branch changed from main to dev/);
  const olderPrompt = overwriteLine("file.ndjson", {
    ...overwriteContext, stamp: "2026-10-04T20:00:00",
    stamps: { note: "2026-10-04T19:00:00", task: "2026-10-06T18:00:00" },
  });
  assert.match(olderPrompt, /overall older, notes older, and tasks forward/);
  const legacyPrompt = overwriteLine("file.ndjson", {
    ...overwriteContext, memory: overwriteContext.stamp,
  });
  assert.match(legacyPrompt, /overall same, notes unknown, and tasks unknown/);
  const unknownPrompt = overwriteLine("file.ndjson", {
    ...overwriteContext, stamp: "", stamps: null, branch: "", lastScope: "",
  });
  assert.match(unknownPrompt, /Branch and remembered scope are missing/);
  assert.doesNotMatch(unknownPrompt, /Branch changed/);
  assert.match(unknownPrompt, /overall unknown, notes unknown, and tasks unknown/);

  console.log("ok state download 32");
  // The session bar names an unpushed branch in a titled span. A pushed branch also has an
  // anchor with a /tree/ href. The repository anchor carries no branch.
  const element = (tag, title, href) => ({
    tag: tag,
    getAttribute: (name) => (name === "title" ? title || null : name === "href" ? href || null : null),
  });
  // The fake answers a selector list the way the bar does: a tag name, or any titled element.
  const matches = (el, selector) => selector.split(",").some((part) => {
    const token = part.trim();
    return token === el.tag || (token === "[title]" && el.getAttribute("title") !== null);
  });
  const docWith = (links) => ({
    querySelector: () => ({ querySelectorAll: (selector) => links.filter((el) => matches(el, selector)) }),
  });
  const repoLink = element("a", "nemoe7/clankers", "https://github.com/nemoe7/clankers");
  assert.equal(
    stateBranch(docWith([repoLink, element("span", "main \u2192 arena/1bc9bdc9-clankers")])),
    "arena/1bc9bdc9-clankers",
    "An unpushed branch reads from its titled span",
  );
  assert.equal(
    stateBranch(docWith([
      repoLink,
      element("a", "main \u2192 arena/fef1ae85-daedalus", "https://github.com/nemoe7/daedalus/tree/arena%2Ffef1ae85-daedalus"),
    ])),
    "arena/fef1ae85-daedalus",
    "A pushed branch reads from its /tree/ anchor",
  );
  assert.equal(stateBranch(docWith([repoLink])), "", "A repository link alone names no branch");
  console.log("ok state download 33");
}

const { test } = require("node:test");
const assert = require("node:assert/strict");

const arenaModule = loadChecks("arena.user.js");
const arena = arenaModule.checks;
test("prompt fill", () => checkPromptFill(arena.promptFill));
run("arena logging", () => checkArenaLogging(arena.logging, arenaModule.menus));
run("open steering", () => checkOpenSteering(arena.openSteering));
run("transcript auto-scroll", () => checkAutoScrollToggle(arena.autoScrollToggle));
run("transcript trim", () => checkTranscriptTrim(arena.transcriptTrim));
run("transcript alerts", () => checkTranscriptAlerts(arena.transcriptAlerts));
run("hide composer", () => checkHideComposer(arena.hideComposer));
run("tab title", () => checkTabTitle(arena.tabTitle, arena.logging));
run("state download", () => checkStateDownload(arena.stateDownload, arenaModule.session, arena.logging));
run("keep awake", () => checkKeepAwake(arena.keepAwake));

const chatgpt = loadChecks("chatgpt.user.js").checks;
run("hide elements", () => checkHideElements(chatgpt.hideElements));
run("chatgpt logging", () => checkLogging(chatgpt.logging));
run("auto think", () => checkAutoThink(chatgpt.autoThink));


require("node:test").test("successful state saves clear stale failure notices", async () => {
  const loaded = loadChecks("arena.user.js");
  const api = loaded.checks.stateDownload;
  let panel;
  const reset = (autoHide = false) => {
    panel = {
      getAttribute(name) { return name === "data-auto-hide" ? String(autoHide) : null; },
      parentNode: { removeChild(node) { assert.equal(node, panel); panel = null; } },
    };
  };
  loaded.context.document = {
    getElementById(id) { assert.equal(id, "clankers-state-panel"); return panel; },
  };
  const handle = fail => ({ createWritable: async () => ({
    write: async () => {},
    close: async () => { if (fail) throw new Error("close failed"); },
  }) });
  reset();
  await api.writeToHandle(handle(false), "state");
  assert.equal(panel, null, "a successful file close clears the old failure");
  reset();
  await assert.rejects(api.writeToHandle(handle(true), "state"), /close failed/);
  assert.ok(panel, "an unsuccessful save keeps the failure notice");
  let download;
  loaded.context.Blob = Blob;
  loaded.context.GM_download = options => { download = options; };
  api.writeStateDownload("state", "state.ndjson");
  assert.ok(panel, "starting a download is not a successful save");
  download.onload();
  assert.equal(panel, null, "manager completion clears the old failure");
  reset(true);
  await api.writeToHandle(handle(false), "state");
  assert.ok(panel, "a transient success message keeps its existing timeout");
});
