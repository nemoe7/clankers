// The Arena and ChatGPT bundles carry no checks of their own. Outside a browser each feature
// publishes its helpers through `exposeChecks`, and this file drives them, so the installed
// scripts ship runtime code only.
//
// Run: node --test maintenance/userscripts.checks.cjs

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function loadChecks(file) {
  const source = fs.readFileSync(path.join(__dirname, "../userscripts", file), "utf8");
  // fetch resolves against the host realm at call time, so one case can drive it. The
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
  const context = {
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
  return { checks: context.CLANKERS_CHECKS, session, menus };
}

function checkLogging(api, menus) {
  var LOG_TAG = api.LOG_TAG;
  var logEvent = api.logEvent;
  var menuItem = api.menuItem;
  // One tag carries every line, so one filter shows the page's story.
  assert.equal(LOG_TAG, "[clankers]");
  var lines = [];
  var original = console.log;
  console.log = function () {
    lines.push(Array.prototype.join.call(arguments, " "));
  };
  try {
    logEvent("feature", "Prompt fill: ON");
    logEvent("fill", "wrote the initial message for clankers");
    logEvent("state", "saved", "detail");
  } finally {
    console.log = original;
  }
  // The module rides a second bracket, so one filter shows one module alone.
  assert.equal(lines[0], "[clankers][feature] Prompt fill: ON");
  assert.equal(lines[1], "[clankers][fill] wrote the initial message for clankers");
  assert.equal(lines[2], "[clankers][state] saved detail");
  // A console that rejects must never break a feature.
  console.log = function () {
    throw new Error("closed console");
  };
  try {
    logEvent("state", "saved");
  } finally {
    console.log = original;
  }
  // Every menu press writes its own line before the command runs (owner note e60e311).
  if (menuItem) {
    var ran = [];
    var list = [];
    menuItem(list, "Arena preview state — save now", function () {
      ran.push("save");
    });
    assert.equal(list.length, 1);
    var registered = menus[menus.length - 1];
    assert.equal(registered.label, "Arena preview state — save now");
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
    assert.equal(pressed[0], "[clankers][menu] Arena preview state — save now");
  }
  console.log("ok logging 3");
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
    // The repo name leads the fill; the rules file rides under the initial message.
    [promptForSlug("clankers").split("\n")[0],
      "clankers read ARENA.md AGENTS.md in full before your first edit, and follow both."],
    [promptForSlug("clankers").indexOf("here is ARENA.md"), -1],
    [promptForSlug("clankers").indexOf("red first") > 0, true],
    [ARENA_MD_URL, "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/rules/ARENA.md"],
    [promptForSlug("clankers", "# Rules\n").indexOf("here is ARENA.md:\n# Rules\n") > 0, true],
    [promptForSlug("clankers", "# Rules\n").indexOf("here is ARENA.md")
      > promptForSlug("clankers", "# Rules\n").indexOf("red first"), true],
    [shouldWrite("", "clankers", null, null), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md", "clankers", null, null), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md\nExpect screenshots to be sent via the steering channel.", "clankers", null, null), true],
    [shouldWrite("clankers read AGENTS.md ARENA.md", "clankers", null, null), true],
    [shouldWrite(promptForSlug("clankers"), "clankers", null, null), true],
    [shouldWrite("draft", "clankers", null, null), false],
    [shouldWrite("clankers read ARENA.md AGENTS.md", "other", "clankers", null), true],
    [shouldWrite("draft", "clankers", "clankers", null), false],
    [shouldWrite(promptForSlug("other"), "clankers", "other", "other"), true],
    // One fill per repo per page: the observer sees no second write, even when the
    // editor hands the text back with different whitespace or the send clears it.
    [shouldWrite(promptForSlug("clankers"), "clankers", "clankers", "clankers"), false],
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
    [promptForSlug("clankers").indexOf("http"), -1],
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
      + " skills/arena-proxy holds the map. Never print it."],
    [keyNote("ready", KEY43, "2026-10-03T15:00:00+00:00", "https://h.example"),
      "Arena proxy https://h.example key ready at 2026-10-03T15:00:00+00:00. New key: " + KEY43 +
      ". Use it as ?key= in every /v1 call. Routes: /v1/ping lists them;"
      + " skills/arena-proxy holds the map. Never print it."],
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
    [steeringSlugFromLabel("arena-preview-steering"), null],
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
    [steeringRowText([["Website", ":3000"], ["arena-preview-steering", ":8000"]], "clankers"),
      "arena-preview-steering :8000"],
    // A Start row is a transcript card; a click on one opens nothing, so it never counts.
    [steeringRowText([["Start clankers - Steering", ":8000"]], "clankers"), null],
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
      ["daedalus - preview", ":8000"], ["arena-preview-steering", ":8000"]], "clankers"),
      "arena-preview-steering :8000"],
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
  var ACTION_SELECTOR = api.ACTION_SELECTOR;
  var QUESTION_SELECTOR = api.QUESTION_SELECTOR;
  var MIN_ROWS = api.MIN_ROWS;
  var DEFAULT_ROWS = api.DEFAULT_ROWS;

  function rows(count) {
    var list = [];
    var i;
    for (i = 0; i < count; i += 1) {
      list.push({
        parentElement: {},
        removed: false,
        remove: function () {
          this.removed = true;
          this.parentElement = null;
        },
      });
    }
    return list;
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
        if (selector !== BOX) return null;
        return nested || element;
      },
    };
    return element;
  }
  function messageRoot(boxes, actions, connected) {
    actions = actions || [];
    var root = {
      isConnected: connected !== false,
      removed: false,
      remove: function () {
        this.removed = true;
        this.parentElement = null;
      },
      querySelectorAll: function (selector) {
        if (selector === BOX) return boxes;
        return selector === ACTION_SELECTOR ? actions : [];
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
  var detached = rows(4);
  detached[0].parentElement = null;
  var cases = [
    [trimRows(rows(5), 3), 2],
    [trimRows(rows(3), 3), 0],
    [trimRows(rows(2), 10), 0],
    [trimRows(detached, 2), 1],
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
    [countLabel("50", 0), "Transcript trim: 50 rows \u2014 set"],
    [countLabel("50", 3), "Transcript trim: 50 rows (3 removed) \u2014 set"],
    [ACTION_SELECTOR, ":scope > div > div > div.mt-3.flex.flex-col.gap-3"],
    [QUESTION_SELECTOR, '[role="radiogroup"]'],
    [rowsOfRoot(messageRoot([rowBox(rows(3))])).length, 3],
    [rowsOfRoot(messageRoot([rowBox(rows(2), true)])).length, 0],
    [messageRoots(logDoc([messageRoot([])], true)).length, 1],
    [messageRoots(logDoc([messageRoot([])], false)).length, 1],
    [messageRoots(logDoc([], true)).length, 0],
    [trimPlan(logDoc([messageRoot([rowBox(rows(30))])], true), "50"), 0],
    [rootRowsRemoved, 30],
    [rootRows[0][24].removed, false],
    [rootRows[1][0].removed, true],
    [rootRows[1][5].removed, true],
    [rootActions[0].removed, true],
    [rootActions[1].removed, true],
    [emptyTrim, 0],
    [emptyAction.removed, true],
    [emptyRoot.parentElement !== null, true],
    [globalRemoved, 30],
    [globalRows[0][24].removed, false],
    [globalRows[1][4].removed, true],
    [globalRows[1][5].removed, true],
    [globalRows[2][0].removed, false],
    [globalActions[0].removed, true],
    [globalActions[1].removed, true],
    [globalActions[2].removed, false],
    [staleRemoved, 0],
    [staleAction.removed, false],
    [goneRemoved, 0],
    [goneRows[0].removed, false],
    [goneRows[24].removed, false],
    [goneAction.removed, false],
    [goneRoot.parentElement !== null, true],
    [globalNodes[0].parentElement !== null, true],
    [globalNodes[1].parentElement !== null, true],
    [globalNodes[2].parentElement !== null, true],
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function () { return null; } }), true],
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function (selector) { return selector === "svg.animate-pulse" ? {} : null; } }), false],
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function (selector) { return selector === QUESTION_SELECTOR ? {} : null; } }), false],
    [isSettled({ querySelectorAll: function () { return [{ getAttribute: function () { return "Stop generating"; } }]; }, querySelector: function () { return null; } }), false],
    [isSettled({ querySelectorAll: function () { return [{ getAttribute: function () { return "Send"; } }]; }, querySelector: function () { return null; } }), true],
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

function checkTabTitle(api) {
  // The bundle hooks change its state; the cases compare the call result to null.
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
  var liveRow = api.liveRow;
  var strongRow = api.strongRow;
  var stopSignal = api.stopSignal;
  var speechLive = api.speechLive;
  var waitingSignal = api.waitingSignal;
  var SPEECH_SELECTOR = api.SPEECH_SELECTOR;
  var SPEECH_EMOJI = api.SPEECH_EMOJI;
  var WAITING_SELECTOR = api.WAITING_SELECTOR;
  var WAITING_TEXT_SELECTOR = api.WAITING_TEXT_SELECTOR;
  var HOURGLASS_EMOJI = api.HOURGLASS_EMOJI;
  var rowSource = api.rowSource;
  var openDialog = api.openDialog;
  var CAPTCHA_SELECTOR = api.CAPTCHA_SELECTOR;
  var CAPTCHA_EMOJI = api.CAPTCHA_EMOJI;
  var captchaSignal = api.captchaSignal;
  var emojiForRow = api.emojiForRow;
  var actionEmoji = api.actionEmoji;
  var TITLE_PREFIX = api.TITLE_PREFIX;
  var EMOJI_HOLD_MS = api.EMOJI_HOLD_MS;
  var MESSAGE_SELECTOR = api.MESSAGE_SELECTOR;
  var LIVE_ICON_SELECTOR = api.LIVE_ICON_SELECTOR;
  var LIVE_LABEL_SELECTOR = api.LIVE_LABEL_SELECTOR;
  var GROUP_LABEL_SELECTOR = api.GROUP_LABEL_SELECTOR;
  var REPO_LINK_SELECTOR = api.REPO_LINK_SELECTOR;
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
      // The repo-memory docs stand for a page mid-turn: the stop control holds the title up.
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
  // The owner's edit row: the label span sits beside the toggle, and the row holds no p.
  function editRowDoc(stopGenerating) {
    var expand = {
      textContent: "",
      querySelector: function () {
        return null;
      },
    };
    var span = {
      textContent: "Edit",
      parentElement: null,
      closest: function () {
        return null;
      },
    };
    var row = {
      querySelector: function (selector) {
        return selector === "button" ? expand : null;
      },
      querySelectorAll: function (selector) {
        if (selector === "button") {
          return [expand];
        }
        return selector === GROUP_LABEL_SELECTOR ? [span] : [];
      },
    };
    span.parentElement = row;
    var message = {
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [span] : [];
      },
    };
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) {
          return [message];
        }
        if (selector === GROUP_LABEL_SELECTOR) {
          return [span];
        }
        if (selector === "button[aria-label]") {
          return stopGenerating
            ? [
                {
                  getAttribute: function () {
                    return "Stop generating";
                  },
                },
              ]
            : [];
        }
        return [];
      },
    };
  }

  // A read or edit group has no shimmer label and no pulsing icon; only the turn bounds it.
  function groupDoc(stopGenerating) {
    var button = {
      textContent: "Explored 2 reads",
      parentElement: null,
      querySelector: function () {
        return null;
      },
    };
    var row = {
      querySelector: function (selector) {
        return selector === "button" ? button : null;
      },
      querySelectorAll: function (selector) {
        return selector === "button" ? [button] : [];
      },
    };
    button.parentElement = row;
    var label = {
      textContent: "Explored 2 reads",
      closest: function (selector) {
        return selector === "button" ? button : null;
      },
    };
    // The finished group label and its message persist after the turn ends; only the
    // stop control leaves, and that is what the fallback now bounds itself by.
    var message = {
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [label] : [];
      },
    };
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) {
          return [message];
        }
        if (selector === GROUP_LABEL_SELECTOR) {
          return [label];
        }
        if (selector === "button[aria-label]") {
          return stopGenerating
            ? [
                {
                  getAttribute: function () {
                    return "Stop generating";
                  },
                },
              ]
            : [];
        }
        return [];
      },
    };
  }
  function liveMessage(text, command) {
    var label = { textContent: text };
    var button = {
      querySelector: function (selector) {
        return selector === "p" ? label : null;
      },
    };
    var panel = { textContent: command || "" };
    var row = {
      querySelector: function (selector) {
        if (selector === "button") return button;
        if (selector === "pre") return command === null ? null : panel;
        return null;
      },
    };
    button.parentElement = row;
    var icon = {
      closest: function (selector) {
        return selector === "button" ? button : null;
      },
    };
    return {
      row: row,
      querySelectorAll: function (selector) {
        return selector === LIVE_ICON_SELECTOR ? [icon] : [];
      },
    };
  }
  function rememberRepo() {
    return repoForTitle(setDoc);
  }
  function divMessage(text, shimmer) {
    var label = { textContent: text };
    var row = {
      textContent: text,
      querySelector: function (selector) {
        return selector === "p" ? label : null;
      },
      querySelectorAll: function (selector) {
        return selector === LIVE_LABEL_SELECTOR && shimmer ? [label] : [];
      },
    };
    var icon = {
      parentElement: row,
      closest: function () {
        return null;
      },
    };
    if (shimmer) {
      label.parentElement = row;
    }
    return {
      row: row,
      label: label,
      querySelectorAll: function (selector) {
        return selector === LIVE_ICON_SELECTOR ? [icon] : [];
      },
    };
  }
  function pulseDoc(messages, stray) {
    return {
      title: "ChatGPT",
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return messages;
        return selector === LIVE_ICON_SELECTOR ? (stray ? [stray] : []) : [];
      },
      querySelector: function () {
        return null;
      },
    };
  }
  function classMatch(selector, nodes) {
    var match = /^([a-z]*)\.([a-zA-Z-]+)$/.exec(selector);
    if (!match) return [];
    return nodes.filter(function (node) {
      var has = (" " + node.className + " ").indexOf(" " + match[2] + " ") >= 0;
      return has && (!match[1] || node.tagName === match[1]);
    });
  }
  // A collapsed edit row pulses its label span, not an svg, so the mock matches by class.
  function pulseLabelDoc(tagName) {
    var label = {
      tagName: tagName,
      className: "shrink-0 text-text-tertiary animate-pulse",
      textContent: "Editing",
      parentElement: null,
      closest: function () { return null; },
    };
    var row = {
      textContent: "Editing maintenance/check_pr.py",
      parentElement: null,
      querySelector: function () { return null; },
      querySelectorAll: function (selector) {
        return selector === LIVE_ICON_SELECTOR ? [label] : [];
      },
    };
    label.parentElement = row;
    var message = {
      querySelectorAll: function (selector) { return classMatch(selector, [label]); },
    };
    return {
      title: "ChatGPT",
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return [message];
        return classMatch(selector, [label]);
      },
      querySelector: function () { return null; },
    };
  }
  function actionDoc(element, message) {
    return {
      title: "ChatGPT",
      querySelectorAll: function (selector) {
        // busyDoc and idleDoc stand for pages mid-turn, so the stop control is present.
        if (selector === "button[aria-label]") return [stopButton("Stop generating")];
        return selector === MESSAGE_SELECTOR && message ? [message] : [];
      },
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? element : null;
      },
    };
  }
  // The owner's bug page: the turn ended, so the stop control is gone, while the repo
  // link and the finished group label in the newest message both persist.
  function endedDoc() {
    var label = {
      textContent: "Ran commands",
      parentElement: null,
      closest: function () {
        return null;
      },
    };
    var row = {
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [label] : [];
      },
    };
    label.parentElement = row;
    var message = {
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [label] : [];
      },
    };
    return {
      title: "ChatGPT",
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? repoLink : null;
      },
      querySelectorAll: function (selector) {
        return selector === MESSAGE_SELECTOR ? [message] : [];
      },
    };
  }
  // A regular-chat message streams data-agent-word spans; the mock grows them on demand.
  function speechDoc(withStop) {
    var words = [{ textContent: "Sandbox" }, { textContent: "resumed" }];
    return {
      title: "ChatGPT",
      words: words,
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? repoLink : null;
      },
      querySelectorAll: function (selector) {
        if (selector === SPEECH_SELECTOR) return words.slice();
        if (selector === "button[aria-label]") {
          return withStop ? [stopButton("Stop generating")] : [];
        }
        return [];
      },
    };
  }
  function looseStopDoc() {
    return {
      title: "ChatGPT",
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? repoLink : null;
      },
      querySelectorAll: function (selector) {
        return selector === "button[aria-label]" ? [stopButton("Stop response")] : [];
      },
    };
  }
  // The owner's two blocks (note 37b3a4e). Both rows carry the same 16px canvas; only the
  // waiting line adds the monospace text block beside it. A tree node answers the text
  // selector with its own descendants, the way a row answers a descendant selector.
  function pageTree(text, children) {
    var node = {
      text: text || "",
      textContent: text || "",
      children: children || [],
      querySelectorAll: function (selector) {
        var hits = [];
        if (selector !== WAITING_TEXT_SELECTOR) return hits;
        (function walk(item) {
          var i;
          for (i = 0; i < item.children.length; i += 1) {
            if (item.children[i].text) hits.push(item.children[i]);
            walk(item.children[i]);
          }
        })(node);
        return hits;
      },
    };
    var i;
    for (i = 0; i < node.children.length; i += 1) node.children[i].parentElement = node;
    return node;
  }
  function canvasDoc(canvases, messages, words) {
    return {
      title: "ChatGPT",
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? repoLink : null;
      },
      querySelectorAll: function (selector) {
        if (selector === WAITING_SELECTOR) return canvases;
        if (selector === MESSAGE_SELECTOR) return messages || [];
        if (selector === SPEECH_SELECTOR) return words || [];
        if (selector === "button[aria-label]") return [stopButton("Stop generating")];
        return [];
      },
    };
  }
  // One row of the owner's blocks: the icon block with the canvas, and, on the waiting
  // line alone, the text block that holds the rotating words.
  function rowCanvas(withText) {
    var canvas = pageTree("", []);
    var icon = pageTree("", [pageTree("", [canvas])]);
    var kids = [icon];
    if (withText) kids.push(pageTree("", [pageTree("The cat sat on the", [])]));
    return { canvas: canvas, row: pageTree("", kids) };
  }
  // The owner's waiting line: a 16px spinner canvas beside rotating monospace status
  // text. The words rotate, so the row carries the text and the canvas together.
  function waitingDoc(messages, words) {
    return canvasDoc([rowCanvas(true).canvas], messages, words);
  }
  // The owner's action row: the same canvas alone, with no text block beside it.
  function actionCanvasDoc(messages, words) {
    return canvasDoc([rowCanvas(false).canvas], messages, words);
  }
  // The owner's security dialog: Arena shows it over the page and it holds until the
  // check passes, so it outranks the poll row, the bubble and the waiting line.
  function captchaDoc(messages, state, parked) {
    var frame = {
      title: "reCAPTCHA",
      getAttribute: function (name) {
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
    return {
      title: "ChatGPT",
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? repoLink : null;
      },
      querySelectorAll: function (selector) {
        if (selector === CAPTCHA_SELECTOR) return [frame];
        if (selector === MESSAGE_SELECTOR) return messages || [];
        if (selector === "button[aria-label]") return [stopButton("Stop generating")];
        return [];
      },
    };
  }
  function resetSpeech() {
    api.resetSpeech();
    return null;
  }
  function addWord(doc, text) {
    doc.words.push({ textContent: text });
    return doc.words.length;
  }
  var repoLink = link("https://github.com/nemoe7/clankers", "Open nemoe7/clankers on GitHub");
  var labelOnly = link(null, "Open nemoe7/clankers on GitHub");
  var emptyLink = link("", "");
  var setDoc = docWith(repoLink, "ChatGPT");
  var keepDoc = docWith(null, "ChatGPT");
  var goneDoc = docWith(null, TITLE_PREFIX + "clankers");
  var endedPage = endedDoc();
  var talking = speechDoc(true);
  var settledChat = speechDoc(false);
  var busyMessage = liveMessage("  running\n Bash  ", "$ npm test");
  var pollMessage = liveMessage("running Bash", "$ arena-preview poll");
  var pathMessage = liveMessage("running Bash", "$ /home/user/clankers/.agents/skills/arena-preview-steering/scripts/arena-preview poll");
  var pyMessage = liveMessage("running Bash", "$ python skills/refs/arena-preview-steering/scripts/preview.py poll");
  var chainMessage = liveMessage("running Bash", "$ git fetch origin && arena-preview poll");
  var readMessage = liveMessage("running Bash", "Read the inbox");
  readMessage.row.textContent = "stderr End the turn with `poll` to wait for more work.";
  var busyDoc = actionDoc(repoLink, busyMessage);
  var idleDoc = actionDoc(repoLink, null);
  var thinkingMessage = divMessage("Thinking\u2026", true);
  var thinkingDoc = pulseDoc([thinkingMessage], null);
  var shimmerDoc = {
    title: "ChatGPT",
    querySelectorAll: function (selector) {
      return selector === LIVE_LABEL_SELECTOR ? [thinkingMessage.label] : [];
    },
    querySelector: function () {
      return null;
    },
  };
  var strayRow = {
    textContent: "Loading the sidebar",
    querySelector: function (selector) {
      return selector === "p" ? { textContent: "Loading the sidebar" } : null;
    },
    querySelectorAll: function () {
      return [];
    },
  };
  var strayIcon = {
    parentElement: strayRow,
    closest: function () {
      return null;
    },
  };
  var strayDoc = pulseDoc([], strayIcon);
  var olderPulseDoc = pulseDoc([busyMessage, divMessage("Nothing running")], null);
  setPriorTitle("ChatGPT");
  var cases = [
    [repoFromLink(repoLink), "clankers"],
    [repoFromLink(labelOnly), "clankers"],
    [repoFromLink(emptyLink), null],
    [repoFromLink(null), null],
    [desiredTitle(setDoc), TITLE_PREFIX + "clankers"],
    // The header can drop the link on a re-render; the name holds while the page stays put.
    [desiredTitle(keepDoc), TITLE_PREFIX + "clankers"],
    [syncTitle(setDoc), true],
    [setDoc.title, TITLE_PREFIX + "clankers"],
    [syncTitle(setDoc), false],
    [syncTitle(keepDoc), true],
    [keepDoc.title, TITLE_PREFIX + "clankers"],
    [syncTitle(goneDoc), false],
    [goneDoc.title, TITLE_PREFIX + "clankers"],
    // Another page drops the memory, and the next good read puts it back.
    [forgetPath(), null],
    [desiredTitle(keepDoc), null],
    [syncTitle(keepDoc), true],
    [keepDoc.title, "ChatGPT"],
    [syncTitle(keepDoc), false],
    [rememberRepo(), "clankers"],
    [desiredTitle(keepDoc), TITLE_PREFIX + "clankers"],
    [liveLabel(busyMessage.row), "running Bash"],
    [liveLabel(null), null],
    // A thinking row is not a button; the label still arrives, and a stray pulse does not.
    [liveLabel(thinkingMessage.row), "Thinking\u2026"],
    [emojiForRow(liveRow(thinkingDoc)), "\uD83D\uDCAD"],
    // A thinking row shows the shimmer label and no pulsing icon.
    [emojiForRow(liveRow(shimmerDoc)), "\uD83D\uDCAD"],
    [liveRow(strayDoc), null],
    [emojiForRow(liveRow(olderPulseDoc)), "\uD83D\uDDA5\uFE0F"],
    [emojiForRow(liveRow(pulseLabelDoc("span"))), "\u270F\uFE0F"],
    [emojiForRow(liveRow(pulseLabelDoc("svg"))), "\u270F\uFE0F"],
    [emojiForRow(busyMessage.row), "\uD83D\uDDA5\uFE0F"],
    [emojiForRow(pollMessage.row), "\uD83D\uDCA4"],
    [emojiForRow(pathMessage.row), "\uD83D\uDCA4"],
    [emojiForRow(pyMessage.row), "\uD83D\uDCA4"],
    [emojiForRow(chainMessage.row), "\uD83D\uDCA4"],
    [emojiForRow(readMessage.row), "\uD83D\uDDA5\uFE0F"],
    [emojiForRow(null), null],
    [actionEmoji("running Bash"), "\uD83D\uDDA5\uFE0F"],
    [actionEmoji("using Bash"), "\uD83D\uDDA5\uFE0F"],
    [actionEmoji("used Bash"), "\uD83D\uDDA5\uFE0F"],
    [actionEmoji("Running commands"), "\uD83D\uDDA5\uFE0F"],
    [actionEmoji("Ran commands"), "\uD83D\uDDA5\uFE0F"],
    [actionEmoji("Reading files"), "\uD83D\uDCD6"],
    [actionEmoji("Editing"), "\u270F\uFE0F"],
    // The owner's editing group: Edit, Editing, Editing files, Write.
    [actionEmoji("Edit"), "\u270F\uFE0F"],
    [actionEmoji("Editing files"), "\u270F\uFE0F"],
    [actionEmoji("Write"), "\u270F\uFE0F"],
    // The owner's reading group: Explored, Read.
    [actionEmoji("Explored"), "\uD83D\uDCD6"],
    [actionEmoji("Exploring"), "\uD83D\uDCD6"],
    [actionEmoji("Read"), "\uD83D\uDCD6"],
    [actionEmoji("Searching the web"), "\uD83D\uDD0D"],
    [actionEmoji("Thought for 2 seconds"), "\uD83D\uDCAD"],
    [actionEmoji("Thinking about the next step"), "\uD83D\uDCAD"],
    [actionEmoji("Re-thinking"), "\uD83D\uDCAD"],
    [actionEmoji("Waiting"), "\uD83D\uDCA4"],
    [actionEmoji("Doing something"), "\u2699\uFE0F"],
    [actionEmoji(null), null],
    [desiredTitle(busyDoc), TITLE_PREFIX + "clankers \uD83D\uDDA5\uFE0F"],
    [syncTitle(busyDoc), true],
    [busyDoc.title, TITLE_PREFIX + "clankers \uD83D\uDDA5\uFE0F"],
    [syncTitle(idleDoc), true],
    [idleDoc.title, TITLE_PREFIX + "clankers \uD83D\uDDA5\uFE0F"],
    [expireHold(), null],
    [desiredTitle(idleDoc), TITLE_PREFIX + "clankers"],
    [syncTitle(idleDoc), true],
    [idleDoc.title, TITLE_PREFIX + "clankers"],
    [GROUP_LABEL_SELECTOR, "span.text-text-secondary"],
    [emojiForRow(liveRow(groupDoc(true))), "\uD83D\uDCD6"],
    // The turn-end bound: the same label persists, but the stop control is gone.
    [liveRow(groupDoc(false)), null],
    [emojiForRow(liveRow(editRowDoc(true))), "\u270F\uFE0F"],
    [liveRow(editRowDoc(false)), null],
    [strongRow(groupDoc(true)), null],
    [stopSignal(groupDoc(true)), true],
    [stopSignal(groupDoc(false)), false],
    // A drifted label still opens the gate; the exact wording does not.
    [stopSignal(looseStopDoc()), true],
    [desiredTitle(looseStopDoc()), TITLE_PREFIX + "clankers"],
    // The owner's bug: the turn ends, the finished group persists, and only the emoji clears.
    [expireHold(), null],
    [desiredTitle(endedPage), TITLE_PREFIX + "clankers"],
    [syncTitle(endedPage), true],
    [endedPage.title, TITLE_PREFIX + "clankers"],
    // Streaming chat words raise the bubble while the turn is open.
    [resetSpeech(), null],
    [desiredTitle(talking), TITLE_PREFIX + "clankers " + SPEECH_EMOJI],
    // The hold bridges the pause between two bursts of words.
    [desiredTitle(talking), TITLE_PREFIX + "clankers " + SPEECH_EMOJI],
    [addWord(talking, "again"), 3],
    [desiredTitle(talking), TITLE_PREFIX + "clankers " + SPEECH_EMOJI],
    // A settled message stops changing; mid-turn the repo name holds the title.
    [resetSpeech(), null],
    [speechLive(talking), true],
    [speechLive(talking), false],
    [expireHold(), null],
    [desiredTitle(talking), TITLE_PREFIX + "clankers"],
    // After the turn no bubble rises; the title keeps the repository name and drops the emoji.
    [resetSpeech(), null],
    [desiredTitle(settledChat), TITLE_PREFIX + "clankers"],
    [
      polls("/home/user/clankers/.agents/skills/arena-preview-steering/scripts/arena-preview poll"),
      true,
    ],
    [polls("arena-preview poll --max 1"), true],
    [polls("python preview.py poll"), true],
    [polls("cat arena-preview-steering/README.md | grep polling"), false],
    [polls('cat > "$HOOK" <<EOF\n# arena-preview-hook: poll the steering inbox'), false],
    [polls("python preview.py polls"), false],
    [polls('python - <<PY\np = Path("skills/arena-preview-steering/scripts/preview.py")\nprint("The poll error names the restart command.")\nPY'), false],
    // The owner's waiting line: rotating words, one structural selector, one hourglass.
    [WAITING_SELECTOR, 'canvas[width="16"][height="16"]'],
    [WAITING_TEXT_SELECTOR, 'span[class*="whitespace-pre"]'],
    [waitingSignal(waitingDoc()), true],
    // The owner's action row carries the very same canvas as its icon (note 37b3a4e), so
    // the canvas alone never reads as a waiting line and never outranks the Bash row.
    [waitingSignal(actionCanvasDoc()), false],
    [waitingSignal(setDoc), false],
    [expireHold(), null],
    [desiredTitle(waitingDoc()), TITLE_PREFIX + "clankers " + HOURGLASS_EMOJI],
    [expireHold(), null],
    [desiredTitle(actionCanvasDoc()), TITLE_PREFIX + "clankers"],
    [expireHold(), null],
    // A named action outranks the line, so the poll row keeps its own emoji.
    [desiredTitle(waitingDoc([pollMessage])), TITLE_PREFIX + "clankers \uD83D\uDCA4"],
    // Streamed words outrank the line too; the first burst raises the bubble.
    [resetSpeech(), null],
    [
      desiredTitle(waitingDoc(null, [{ textContent: "Sandbox" }])),
      TITLE_PREFIX + "clankers " + SPEECH_EMOJI,
    ],
    [expireHold(), null],
    [desiredTitle(waitingDoc()), TITLE_PREFIX + "clankers " + HOURGLASS_EMOJI],
    [expireHold(), null],
    [desiredTitle(idleDoc), TITLE_PREFIX + "clankers"],
    // The security check beats every other mark, including a poll row and the hourglass.
    [CAPTCHA_SELECTOR, '.recaptcha-v2-container, iframe[title="reCAPTCHA"]'],
    [captchaSignal(captchaDoc()), true],
    [captchaSignal(idleDoc), false],
    // A closed dialog stays in the DOM, so the shield clears with it.
    [captchaSignal(captchaDoc(null, "closed")), false],
    [captchaSignal(captchaDoc(null, "open")), true],
    // A parked node keeps its place after the dialog closes, so the shield needs a rendered
    // node: no box, no mark.
    [captchaSignal(captchaDoc(null, null, true)), false],
    [captchaSignal(captchaDoc(null, "open", true)), false],
    [openDialog({ getAttribute: function () { return null; } }), true],
    [desiredTitle(captchaDoc()), TITLE_PREFIX + "clankers " + CAPTCHA_EMOJI],
    [desiredTitle(captchaDoc([pollMessage])), TITLE_PREFIX + "clankers " + CAPTCHA_EMOJI],
    [desiredTitle(captchaDoc()), TITLE_PREFIX + "clankers " + CAPTCHA_EMOJI],
    // Every title change prints one line: the signal, then the emoji the title takes.
    [
      loggedTitleHead(captchaDoc()),
      "[clankers][title] security check -> " + TITLE_PREFIX + "clankers " + CAPTCHA_EMOJI,
    ],
    // The anchors behind the decision ride the same line, so a title shows its cause.
    [loggedTitleTail(captchaDoc()), "repo=clankers row=none"],
    // The label behind the row rides the line, so the cause is visible.
    [
      loggedTitleHead(waitingDoc([pollMessage])),
      "[clankers][title] poll command (running Bash) -> " + TITLE_PREFIX + "clankers \uD83D\uDCA4",
    ],
    [
      loggedTitleTail(waitingDoc([pollMessage])),
      "repo=clankers row=poll command (running Bash)",
    ],
    [expireHold(), null],
    [
      loggedTitleHead(idleDoc),
      "[clankers][title] title -> " + TITLE_PREFIX + "clankers",
    ],
    [loggedTitleTail(idleDoc), "repo=clankers row=none"],
  ];
  // The title writes through syncTitle, which logs the signal that won. The capture keeps
  // the host console clean and returns the last line.
  function loggedTitle(doc) {
    var lines = [];
    var original = console.log;
    console.log = function () {
      lines.push(Array.prototype.join.call(arguments, " "));
    };
    try {
      doc.title = "ChatGPT";
      api.syncTitle(doc);
    } finally {
      console.log = original;
    }
    return lines.length ? lines[lines.length - 1] : "";
  }
  // The line carries the decision and the anchors behind it; the cases read both halves.
  function loggedTitleHead(doc) {
    return loggedTitle(doc).split(" repo=")[0];
  }
  function loggedTitleTail(doc) {
    return "repo=" + loggedTitle(doc).split(" repo=")[1];
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

  var CLAIM_BUTTON_SELECTOR = api.CLAIM_BUTTON_SELECTOR;
  var CLAIM_DIV_SELECTOR = api.CLAIM_DIV_SELECTOR;
  var FREE_OFFER_DIV_SELECTOR = api.FREE_OFFER_DIV_SELECTOR;
  var SURFACE_DIV_SELECTOR = api.SURFACE_DIV_SELECTOR;
  var SURFACE_RADIO_SELECTOR = api.SURFACE_RADIO_SELECTOR;
  var CODEX_LINK_SELECTOR = api.CODEX_LINK_SELECTOR;
  var IMAGES_LINK_SELECTOR = api.IMAGES_LINK_SELECTOR;
  var LIBRARY_LINK_SELECTOR = api.LIBRARY_LINK_SELECTOR;
  var FREE_BADGE_SELECTOR = api.FREE_BADGE_SELECTOR;
  var HEADER_DIV_SELECTOR = api.HEADER_DIV_SELECTOR;
  var findClaimDiv = api.findClaimDiv;
  var findFreeOfferDiv = api.findFreeOfferDiv;
  var findSurfaceDiv = api.findSurfaceDiv;
  var findCodexLink = api.findCodexLink;
  var findImagesLink = api.findImagesLink;
  var findLibraryLink = api.findLibraryLink;
  var findFreeBadge = api.findFreeBadge;
  var findHeaderDiv = api.findHeaderDiv;
  var hideElement = api.hideElement;
  var syncDocument = api.syncDocument;

  var claimDiv = fakeElement();
  var freeDiv = fakeElement();
  var surfaceDiv = fakeElement();
  var codexLink = fakeElement();
  var imagesLink = fakeElement();
  var libraryLink = fakeElement();
  var freeBadge = fakeElement();
  freeBadge.textContent = " Free ";
  var paidBadge = fakeElement();
  paidBadge.textContent = "Plus";
  var headerDiv = fakeElement();
  var claimButton = {
    closest: function (selector) {
      return selector === CLAIM_DIV_SELECTOR ? claimDiv : null;
    },
  };
  var bareButton = {
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
  var radio = {
    closest: function (selector) {
      return selector === SURFACE_DIV_SELECTOR ? surfaceDiv : null;
    },
  };
  var claimDoc = {
    querySelector: function (selector) {
      return selector === CLAIM_BUTTON_SELECTOR ? claimButton : null;
    },
  };
  var bareDoc = {
    querySelector: function (selector) {
      return selector === CLAIM_BUTTON_SELECTOR ? bareButton : null;
    },
  };
  var surfaceDoc = {
    querySelector: function (selector) {
      return selector === SURFACE_RADIO_SELECTOR ? radio : null;
    },
  };
  var codexDoc = {
    querySelector: function (selector) {
      return selector === CODEX_LINK_SELECTOR ? codexLink : null;
    },
  };
  var headerDoc = {
    querySelector: function (selector) {
      return selector === HEADER_DIV_SELECTOR ? headerDiv : null;
    },
  };
  var imagesDoc = {
    querySelector: function (selector) {
      return selector === IMAGES_LINK_SELECTOR ? imagesLink : null;
    },
  };
  var libraryDoc = {
    querySelector: function (selector) {
      return selector === LIBRARY_LINK_SELECTOR ? libraryLink : null;
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
  var emptyDoc = {
    querySelector: function () {
      return null;
    },
    querySelectorAll: function () {
      return [];
    },
  };
  var freeDoc = {
    querySelectorAll: function () {
      return [otherButton, freeButton];
    },
  };
  // One document answers every selector, so the sync pass itself is under test:
  // a finder left out of syncDocument leaves its element unhidden here.
  var fullDoc = {
    querySelector: function (selector) {
      if (selector === CLAIM_BUTTON_SELECTOR) return claimButton;
      if (selector === SURFACE_RADIO_SELECTOR) return radio;
      if (selector === CODEX_LINK_SELECTOR) return codexLink;
      if (selector === IMAGES_LINK_SELECTOR) return imagesLink;
      if (selector === LIBRARY_LINK_SELECTOR) return libraryLink;
      if (selector === FREE_BADGE_SELECTOR) return freeBadge;
      if (selector === HEADER_DIV_SELECTOR) return headerDiv;
      return null;
    },
    querySelectorAll: function (selector) {
      return selector === "button" ? [freeButton] : [];
    },
  };
  var cases = [
    [findClaimDiv(claimDoc), claimDiv],
    [findClaimDiv(bareDoc), null],
    [findClaimDiv(emptyDoc), null],
    [findFreeOfferDiv(freeDoc), freeDiv],
    [findFreeOfferDiv(emptyDoc), null],
    [findSurfaceDiv(surfaceDoc), surfaceDiv],
    [findSurfaceDiv(emptyDoc), null],
    [findCodexLink(codexDoc), codexLink],
    [findCodexLink(emptyDoc), null],
    [findImagesLink(imagesDoc), imagesLink],
    [findImagesLink(emptyDoc), null],
    [findLibraryLink(libraryDoc), libraryLink],
    [findLibraryLink(emptyDoc), null],
    [findFreeBadge(badgeDoc), freeBadge],
    [findFreeBadge(paidBadgeDoc), null],
    [findFreeBadge(emptyDoc), null],
    [findHeaderDiv(headerDoc), headerDiv],
    [findHeaderDiv(emptyDoc), null],
    [hideElement(claimDiv), true],
    [claimDiv.hasAttribute("hidden"), true],
    [hideElement(claimDiv), false],
    [hideElement(null), false],
  ];
  var failed = 0;
  var i;
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
    surfaceDiv,
    codexLink,
    imagesLink,
    libraryLink,
    freeBadge,
    headerDiv,
  ];
  for (i = 0; i < synced.length; i += 1) {
    if (!synced[i].hasAttribute("hidden")) {
      console.error("sync fail", i);
      failed += 1;
    }
  }
  if (failed) {
    throw new Error(failed + " checks failed");
  }
  console.log("ok hide elements " + (cases.length + synced.length));
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

function run(name, check) {
  try {
    check();
  } catch (error) {
    throw new Error(`${name}: ${error.message}`);
  }
}

function checkStateDownload(api, session) {
  var stateFileName = api.stateFileName;
  var stateDownload = api.stateDownload;
  var stateMemory = api.stateMemory;
  var stateRemembered = api.stateRemembered;
  var stateDelivery = api.stateDelivery;
  var stateAction = api.stateAction;
  var handleMatchesScope = api.handleMatchesScope;
  var stateScope = api.stateScope;
  var stateRepo = api.stateRepo;
  var stateScopeKey = api.stateScopeKey;
  var pagePicker = api.pagePicker;
  var writtenName = api.writtenName;
  var stateTick = api.stateTick;
  var downloadRoute = api.downloadRoute;
  var stateDownloadRoute = api.stateDownloadRoute;
  var counts = { notes: 12, tasks: 4 };
  var repo = "clankers";
  var branch = "main";
  // The name carries the repository, then the branch, then the server's stamp and the record
  // counts, so two repos and their branches never collide in one folder (owner note 495ae89).
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
  // The approved pair: the newest note stamp and the newest task stamp. A rollback leaves the
  // older records behind while one new note moves the state stamp forward, so the pair refuses
  // that write and the owner's file keeps the newer state.
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
  // One note deleted alone moves the note stamp back and leaves the state stamp still, so the
  // write is unchanged, never a refusal and never a rewrite.
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
      if (selector === "a") return [branchLink];
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
  // The server stamp carries the timezone; the name keeps the seconds alone.
  assert.equal(
    stateFileName(scope.repo, scope.branch, "2026-10-06T08:33:57+00:00", null),
    "clankers-arena-01a0fd4f-clankers-20261006T083357.ndjson",
  );
  // The header leaves the page while a dialog holds it, so the fill's saved slug names the
  // repository; the branch stays empty.
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
  // A title without the arrow falls back to the href; a page without the bar stays empty.
  branchLink.getAttribute = function (name) {
    if (name === "href") return "https://github.com/other/repo/tree/feat%2Fx";
    return "";
  };
  assert.equal(stateScope(doc).branch, "feat/x");
  // The structure crosses the VM realm, so it is compared as JSON.
  assert.equal(
    JSON.stringify(stateScope({ querySelector: function () { return null; } })),
    JSON.stringify({ repo: "", branch: "" }),
  );
  // The picker call runs on the page window; a realm without one yields no picker rather
  // than a throw, which is what keeps the download route alive.
  assert.equal(pagePicker(), null);
  // The chosen file keeps its own name, so the save line names the file the write reached.
  assert.equal(writtenName({ name: "clankers-state.ndjson" }, "generated.ndjson"), "clankers-state.ndjson");
  assert.equal(writtenName({}, "generated.ndjson"), "generated.ndjson");
  assert.equal(writtenName(null, "generated.ndjson"), "generated.ndjson");
  // The bar leaves the page while a dialog holds it; with no saved slug either, the title
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
  // A menu click grants no browser gesture, so the automatic path writes the stamped
  // download and the pick stays a manual action.
  assert.equal(stateAction("pick", false), "download");
  assert.equal(stateAction("pick", true), "pick");
  assert.equal(stateAction("download", false), "download");
  assert.equal(stateAction("write", true), "write");
  assert.equal(stateAction("unchanged", false), "unchanged");
  // The tick line names the file and shows the two stamps the route compared.
  assert.equal(
    stateTick("a.ndjson", "2026-10-06T09:45:05+00:00", ""),
    "a.ndjson stamp=2026-10-06T09:45:05+00:00 saved=none",
  );
  assert.equal(
    stateTick("a.ndjson", "2026-10-06T09:45:05+00:00", "2026-10-06T09:44:05+00:00"),
    "a.ndjson stamp=2026-10-06T09:45:05+00:00 saved=2026-10-06T09:44:05+00:00",
  );
  assert.equal(stateTick("a.ndjson", "", ""), "a.ndjson stamp=none saved=none");
  // Every comparison in the save path writes its own line, so one filter shows which test
  // refused a write (owner note e60e311).
  var compared = [];
  var originalLog = console.log;
  console.log = function () {
    compared.push(Array.prototype.join.call(arguments, " "));
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
  } finally {
    console.log = originalLog;
  }
  function comparedLine(expected) {
    return compared.indexOf("[clankers][state] " + expected) !== -1;
  }
  assert.ok(comparedLine("compare stamp: same as 2026-10-06T06:12:33"), compared.join("\n"));
  assert.ok(comparedLine("compare stamp: older than 2026-10-06T06:12:33"), compared.join("\n"));
  assert.ok(comparedLine("compare stamp: first write at 2026-10-06T06:12:33"), compared.join("\n"));
  assert.ok(
    comparedLine("compare note stamp: 2026-10-06T05:00:00 is older than 2026-10-06T05:30:00"),
    compared.join("\n"),
  );
  assert.ok(
    comparedLine("compare task stamp: 2026-10-06T06:00:00 is forward of 2026-10-06T05:00:00"),
    compared.join("\n"),
  );
  assert.ok(comparedLine("compare stamp: none, no stamp to compare"), compared.join("\n"));
  // A remembered file belongs to the scope that chose it: the name carries the scope, and a
  // handle outside the current scope is refused so one repo never writes into another's file
  // (owner note 1cfdedd).
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
  // An unknown scope adopts nothing: the fallback name alone passes, so the owner is asked again.
  assert.equal(handleMatchesScope({ name: "f360-main.ndjson" }, "", ""), false);
  assert.equal(handleMatchesScope({ name: "arena.ndjson" }, "", ""), true);
  console.log("ok state download 32");
}

const { test } = require("node:test");
const assert = require("node:assert/strict");

const arenaModule = loadChecks("arena.user.js");
const arena = arenaModule.checks;
test("prompt fill", () => checkPromptFill(arena.promptFill));
run("arena logging", () => checkLogging(arena.logging, arenaModule.menus));
run("open steering", () => checkOpenSteering(arena.openSteering));
run("transcript auto-scroll", () => checkAutoScrollToggle(arena.autoScrollToggle));
run("transcript trim", () => checkTranscriptTrim(arena.transcriptTrim));
run("hide composer", () => checkHideComposer(arena.hideComposer));
run("tab title", () => checkTabTitle(arena.tabTitle));
run("state download", () => checkStateDownload(arena.stateDownload, arenaModule.session));

const chatgpt = loadChecks("chatgpt.user.js").checks;
run("hide elements", () => checkHideElements(chatgpt.hideElements));
run("chatgpt logging", () => checkLogging(chatgpt.logging));
run("auto think", () => checkAutoThink(chatgpt.autoThink));
