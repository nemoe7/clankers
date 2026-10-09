// The Arena and ChatGPT bundles carry no checks of their own. Outside a browser each feature
// publishes its helpers through `exposeChecks`, and this file drives them, so the installed
// scripts ship runtime code only.
//
// Run: node --test maintenance/workflows/userscripts.checks.cjs

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
    // The registry reopens the list in module order, so the entry is found by its label rather
    // than by sitting last in the array.
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
    // The checklist leads the tail; the dropped model paragraph never returns.
    [promptForSlug("clankers").indexOf("run this order:") > 0, true],
    [promptForSlug("clankers").indexOf("run this order:")
      < promptForSlug("clankers").indexOf("red first"), true],
    [promptForSlug("clankers").indexOf("1. Read the task and every file it touches in full") > 0, true],
    [promptForSlug("clankers").indexOf("6. Verify with the project's own gate") > 0, true],
    [promptForSlug("clankers").indexOf("add nothing the task does not ask for") > 0, true],
    [promptForSlug("clankers").indexOf("Keep the behavior, interfaces, validation and security") > 0, true],
    [promptForSlug("clankers").indexOf("Never repeat a failed approach without a new reason.") > 0, true],
    [promptForSlug("clankers").indexOf("invent no visual detail") > 0, true],
    [promptForSlug("clankers").indexOf("name what stays unverified") > 0, true],
    [promptForSlug("clankers").indexOf("Pareto"), -1],
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
    // A Start row is a transcript card; a click on one opens nothing, so it never counts.
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
  var trimMessage = api.trimMessage;
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
    [trimMessage(12, "50"), "removed 12 rows (kept 50)"],
    [trimMessage(1, "20"), "removed 1 row (kept 20)"],
    [ACTION_SELECTOR, ":scope > div > div > div.mt-3.flex.flex-col.gap-3"],
    [QUESTION_SELECTOR, '[role="radiogroup"]'],
    [rowsOfRoot(messageRoot([rowBox(rows(3))])).length, 3],
    [rowsOfRoot(messageRoot([rowBox(rows(2), true)])).length, 0],
    [messageRoots(logDoc([messageRoot([])], true)).length, 1],
    [messageRoots(logDoc([messageRoot([])], false)).length, 1],
    [messageRoots(logDoc([], true)).length, 0],
    // A lone root is the newest: under its own keep count nothing leaves.
    [trimPlan(logDoc([messageRoot([rowBox(rows(30))])], true), "50"), 0],
    // The newest root keeps exactly its K newest rows: the ten oldest hide and empty.
    [trimPlan(logDoc([messageRoot([rowBox(rows(30))])], true), "20"), 10],
    [rootRowsRemoved, 30],
    // Cut rows stay as hidden empty shells: the page reinstates removed nodes, so the
    // trim hides and empties instead of deleting; the older root hides in full while
    // the newest root keeps its 20 newest rows.
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
    // Two older roots empty and hide; the newest keeps all of its 25 rows.
    [globalRemoved, 45],
    [cleared(globalRows[0][24]), true],
    [globalNodes[0].hiddenClass, true],
    [cleared(globalRows[1][4]), true],
    [globalNodes[1].hiddenClass, true],
    [cleared(globalRows[2][0]), false],
    [globalNodes[2].hiddenClass, false],
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
    // No stop control means no turn, and the trim aborts; it runs only while a turn
    // is up. A question card aborts too; the pulsing icon no longer gates anything.
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function () { return null; } }), false],
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function (selector) { return selector === "svg.animate-pulse" ? {} : null; } }), false],
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function (selector) { return selector === QUESTION_SELECTOR ? {} : null; } }), false],
    [isSettled({ querySelectorAll: function () { return [{ getAttribute: function () { return "Stop generating"; } }]; }, querySelector: function () { return null; } }), true],
    [isSettled({ querySelectorAll: function () { return [{ getAttribute: function () { return "Send"; } }]; }, querySelector: function () { return null; } }), false],
    // Quiet means the whole page holding still, not the row count alone: the page
    // streams into existing rows after the last row lands, so a fresh mutation
    // keeps the trim waiting even while the count holds.
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
  var processRow = api.processRow;
  var PLAY_SELECTOR = api.PLAY_SELECTOR;
  var speechGrowth = api.speechGrowth;
  var AGENT_EMOJI = api.AGENT_EMOJI;
  var BASH_EMOJI = api.BASH_EMOJI;
  var waitingSignal = api.waitingSignal;
  var SPEECH_SELECTOR = api.SPEECH_SELECTOR;
  var WAITING_SELECTOR = api.WAITING_SELECTOR;
  var WAITING_TEXT_SELECTOR = api.WAITING_TEXT_SELECTOR;
  var HOURGLASS_EMOJI = api.HOURGLASS_EMOJI;
  var rowSource = api.rowSource;
  var openDialog = api.openDialog;
  var CAPTCHA_SELECTOR = api.CAPTCHA_SELECTOR;
  var CAPTCHA_EMOJI = api.CAPTCHA_EMOJI;
  var captchaSignal = api.captchaSignal;
  var questionSignal = api.questionSignal;
  var QUESTION_SELECTOR = api.QUESTION_SELECTOR;
  var QUESTION_EMOJI = api.QUESTION_EMOJI;
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
      contains: function (candidate) {
        return candidate === row;
      },
      querySelectorAll: function (selector) {
        if (selector === LIVE_ICON_SELECTOR) return [icon];
        return selector === LIVE_LABEL_SELECTOR && shimmer ? [label] : [];
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
  function pulseLabelDoc(tagName, text) {
    var label = {
      tagName: tagName,
      className: "shrink-0 text-text-tertiary animate-pulse",
      textContent: text || "Editing",
      parentElement: null,
      closest: function () { return null; },
    };
    var row = {
      textContent: "Editing maintenance/pr/gate_pr.py",
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
  // The owner's live page: the newest row pulses its Editing span while a done row
  // above it already carries its group label, so the pulse must outnewest the label.
  function editingUnderDoneDoc() {
    var doneLabel = {
      tagName: "SPAN",
      className: "shrink-0 text-text-secondary",
      textContent: "Bash sleep 25",
      parentElement: null,
      closest: function () {
        return null;
      },
    };
    var doneRow = {
      textContent: "Bash sleep 25",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function () {
        return [];
      },
    };
    doneLabel.parentElement = doneRow;
    var pulse = {
      tagName: "SPAN",
      className: "shrink-0 text-text-tertiary animate-pulse",
      textContent: "Editing",
      parentElement: null,
      closest: function () {
        return null;
      },
    };
    var editRow = {
      textContent: "Editing userscripts/arena.user.js",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        return classMatch(selector, [pulse]);
      },
    };
    pulse.parentElement = editRow;
    var message = {
      contains: function (candidate) {
        return candidate === doneRow || candidate === editRow;
      },
      querySelectorAll: function (selector) {
        if (selector === GROUP_LABEL_SELECTOR) return [doneLabel];
        if (selector === GROUP_LABEL_SELECTOR + ", " + LIVE_LABEL_SELECTOR + ", " + LIVE_ICON_SELECTOR) {
          return [doneLabel, pulse];
        }
        return classMatch(selector, [pulse]);
      },
    };
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return [message];
        if (selector === "button[aria-label]") return [stopButton("Stop generating")];
        if (selector === LIVE_ICON_SELECTOR) return [pulse];
        return [];
      },
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
  // The owner's bug page: the finished row keeps its shimmer label after the
  // turn, and the stop control is the only thing that leaves. The same page, one flag apart.
  function lingeringRowDoc(stopGenerating) {
    var message = divMessage("Thinking\u2026", true);
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return [message];
        if (selector === "button[aria-label]") {
          return stopGenerating ? [stopButton("Stop generating")] : [];
        }
        return [];
      },
    };
  }
  // The same end for a row whose only live mark is the pulsing icon.
  function lingeringPulseDoc(stopGenerating) {
    var icon = {
      textContent: "Running bash",
      parentElement: null,
      closest: function () {
        return null;
      },
    };
    var row = {
      textContent: "Running bash",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        return selector === LIVE_ICON_SELECTOR ? [icon] : [];
      },
    };
    icon.parentElement = row;
    var message = {
      querySelectorAll: function (selector) {
        return selector === LIVE_ICON_SELECTOR ? [icon] : [];
      },
    };
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return [message];
        if (selector === "button[aria-label]") {
          return stopGenerating ? [stopButton("Stop generating")] : [];
        }
        return [];
      },
    };
  }
  // The owner's captured start-process card: a button holding the play icon,
  // the process name and the success check beside it. It runs with no stop control. `behind`
  // adds a newer plain message, so the card sits in the transcript's history.
  function processDoc(stopGenerating, behind) {
    var play = {
      closest: function (selector) {
        return selector === "button" ? button : null;
      },
    };
    var name = { textContent: "Start PR checks" };
    var button = {
      textContent: "Start PR checks",
      parentElement: null,
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [name] : [];
      },
    };
    var card = {
      textContent: "Start PR checks",
      querySelector: function (selector) {
        return selector === PLAY_SELECTOR ? play : null;
      },
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [name] : [];
      },
    };
    button.parentElement = card;
    var message = {
      querySelectorAll: function (selector) {
        return selector === PLAY_SELECTOR ? [play] : [];
      },
    };
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) {
          return behind
            ? [message, { querySelectorAll: function () { return []; } }]
            : [message];
        }
        if (selector === "button[aria-label]") {
          return stopGenerating ? [stopButton("Stop generating")] : [];
        }
        return [];
      },
    };
  }
  // The owner's mixed page: a start-process card wins the
  // mark while a finished Explored group label sits in the very same message.
  function processDocExplored() {
    var play = {
      closest: function (selector) {
        return selector === "button" ? button : null;
      },
    };
    var name = { textContent: "Start PR checks" };
    var button = {
      textContent: "Start PR checks",
      parentElement: null,
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [name] : [];
      },
    };
    var card = {
      textContent: "Start PR checks",
      querySelector: function (selector) {
        return selector === PLAY_SELECTOR ? play : null;
      },
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [name] : [];
      },
    };
    button.parentElement = card;
    var exploredButton = {
      textContent: "Explored 2 reads",
      parentElement: null,
      querySelector: function () {
        return null;
      },
    };
    var exploredRow = {
      querySelector: function (selector) {
        return selector === "button" ? exploredButton : null;
      },
      querySelectorAll: function (selector) {
        return selector === "button" ? [exploredButton] : [];
      },
    };
    exploredButton.parentElement = exploredRow;
    var exploredLabel = {
      textContent: "Explored 2 reads",
      closest: function (selector) {
        return selector === "button" ? exploredButton : null;
      },
    };
    var message = {
      querySelectorAll: function (selector) {
        if (selector === PLAY_SELECTOR) return [play];
        if (selector === GROUP_LABEL_SELECTOR) return [name, exploredLabel];
        if (selector === GROUP_LABEL_SELECTOR + ", " + LIVE_LABEL_SELECTOR + ", " + LIVE_ICON_SELECTOR) {
          return [name, exploredLabel];
        }
        return [];
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
        if (selector === "button[aria-label]") {
          return [stopButton("Stop generating")];
        }
        return [];
      },
    };
  }
  // The owner's 1.10.1 bug: the turn ran on past the start-process card, and a
  // later Bash row of the very same message owns the title instead of the card.
  function processDocLaterRow() {
    var play = {
      closest: function (selector) {
        return selector === "button" ? button : null;
      },
    };
    var name = { textContent: "Start PR checks" };
    var button = {
      textContent: "Start PR checks",
      parentElement: null,
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [name] : [];
      },
    };
    var card = {
      textContent: "Start PR checks",
      querySelector: function (selector) {
        return selector === PLAY_SELECTOR ? play : null;
      },
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [name] : [];
      },
    };
    button.parentElement = card;
    var bashButton = {
      textContent: "Bash sleep 25",
      parentElement: null,
      querySelector: function () {
        return null;
      },
    };
    var bashRow = {
      querySelector: function (selector) {
        return selector === "button" ? bashButton : null;
      },
      querySelectorAll: function (selector) {
        return selector === "button" ? [bashButton] : [];
      },
    };
    bashButton.parentElement = bashRow;
    var bashLabel = {
      textContent: "Bash sleep 25",
      closest: function (selector) {
        return selector === "button" ? bashButton : null;
      },
    };
    var message = {
      querySelectorAll: function (selector) {
        if (selector === PLAY_SELECTOR) return [play];
        if (selector === GROUP_LABEL_SELECTOR) return [name, bashLabel];
        if (selector === GROUP_LABEL_SELECTOR + ", " + LIVE_LABEL_SELECTOR + ", " + LIVE_ICON_SELECTOR) {
          return [name, bashLabel];
        }
        return [];
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
        if (selector === "button[aria-label]") {
          return [stopButton("Stop generating")];
        }
        return [];
      },
    };
  }
  // The owner's flip-flop: the watcher card keeps taking the title back from the
  // message that started it while that message keeps speaking. One spoken word
  // after the card outranks it.
  function processDocSpeaking() {
    var play = {
      closest: function (selector) {
        return selector === "button" ? button : null;
      },
    };
    var name = {
      textContent: "Start PR checks watcher",
      closest: function (selector) {
        return selector === "button" ? button : null;
      },
    };
    var button = {
      textContent: "Start PR checks watcher",
      parentElement: null,
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [name] : [];
      },
    };
    var card = {
      textContent: "Start PR checks watcher",
      querySelector: function (selector) {
        return selector === PLAY_SELECTOR ? play : null;
      },
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [name] : [];
      },
    };
    button.parentElement = card;
    // The spoken word sits after the card in the page, the way the agent's speech
    // follows the tool row that started it.
    var word = {
      textContent: "Waiting",
      compareDocumentPosition: function (other) {
        return other === card ? 2 : 0;
      },
    };
    var message = {
      querySelectorAll: function (selector) {
        if (selector === PLAY_SELECTOR) return [play];
        if (selector === SPEECH_SELECTOR) return [word];
        if (selector === GROUP_LABEL_SELECTOR + ", " + LIVE_LABEL_SELECTOR + ", " + LIVE_ICON_SELECTOR) {
          return [name];
        }
        return [];
      },
    };
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return [message];
        if (selector === "button[aria-label]") return [stopButton("Stop generating")];
        return [];
      },
    };
  }
  // A labelled row in an older message never marks once a newer message exists,
  // even when the newer message carries no label of its own.
  function labeledBehindEmptyDoc() {
    var busy = liveMessage("  running\n Bash  ", "$ npm test");
    var older = {
      querySelectorAll: function (selector) {
        if (selector === LIVE_ICON_SELECTOR) return busy.querySelectorAll(LIVE_ICON_SELECTOR);
        return [];
      },
      contains: function () {
        return true;
      },
    };
    var newer = {
      querySelectorAll: function () {
        return [];
      },
      contains: function () {
        return false;
      },
    };
    return pulseDoc([older, newer], null);
  }
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
  // The live row carries the shimmer label in place of a group label until it
  // finishes; the newest-row gate must still recognise it as the newest row, or
  // the mark freezes on the last labelled row.
  function titleDocStreaming() {
    var liveRow = {};
    var liveButton = {
      textContent: "Searching the docs",
      parentElement: liveRow,
      querySelector: function () {
        return null;
      },
    };
    var shimmer = {
      textContent: "Searching the docs",
      closest: function (selector) {
        return selector === "button" ? liveButton : null;
      },
    };
    var oldRow = {};
    var oldButton = {
      textContent: "Bash sleep 25",
      parentElement: oldRow,
      querySelector: function () {
        return null;
      },
    };
    var oldLabel = {
      textContent: "Bash sleep 25",
      closest: function (selector) {
        return selector === "button" ? oldButton : null;
      },
    };
    var message = {
      querySelectorAll: function (selector) {
        if (selector === GROUP_LABEL_SELECTOR) return [oldLabel];
        if (selector === LIVE_LABEL_SELECTOR) return [shimmer];
        if (selector === GROUP_LABEL_SELECTOR + ", " + LIVE_LABEL_SELECTOR + ", " + LIVE_ICON_SELECTOR) {
          return [oldLabel, shimmer];
        }
        return [];
      },
    };
    var doc = {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return [message];
        if (selector === LIVE_LABEL_SELECTOR) return [shimmer];
        if (selector === "button[aria-label]") return [stopButton("Stop generating")];
        return [];
      },
    };
    return { doc: doc, liveRow: liveRow };
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
  // The owner's two blocks. Both rows carry the same 16px canvas; only the
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
  function canvasDoc(canvases, messages, words, withStop) {
    return {
      title: "ChatGPT",
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? repoLink : null;
      },
      querySelectorAll: function (selector) {
        if (selector === WAITING_SELECTOR) return canvases;
        if (selector === MESSAGE_SELECTOR) return messages || [];
        if (selector === SPEECH_SELECTOR) return words || [];
        if (selector === "button[aria-label]") {
          return withStop === false ? [] : [stopButton("Stop generating")];
        }
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
  // The ask_user card from the owner's captured outerHTML: a radiogroup with an aria-label.
  function questionCard(label) {
    return {
      getAttribute: function (name) {
        return name === "aria-label" ? label || "Pick one" : null;
      },
    };
  }
  function questionDoc(card, withCaptcha) {
    var frame = {
      title: "reCAPTCHA",
      getAttribute: function () {
        return null;
      },
    };
    return {
      title: "ChatGPT",
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? repoLink : null;
      },
      querySelectorAll: function (selector) {
        if (selector === QUESTION_SELECTOR) return card ? [card] : [];
        if (selector === CAPTCHA_SELECTOR) return withCaptcha ? [frame] : [];
        if (selector === MESSAGE_SELECTOR) return [];
        if (selector === "button[aria-label]") return [stopButton("Stop generating")];
        return [];
      },
    };
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
  var goneDoc = docWith(null, TITLE_PREFIX + "clankers" + vtag);
  var endedPage = endedDoc();
  var talking = speechDoc(true);
  var settledChat = speechDoc(false);
  var busyMessage = liveMessage("  running\n Bash  ", "$ npm test");
  var pollMessage = liveMessage("running Bash", "$ arena-preview poll");
  var pathMessage = liveMessage("running Bash", "$ /home/user/clankers/.agents/skills/arena-skill/scripts/arena-preview poll");
  var pyMessage = liveMessage("running Bash", "$ python skills/refs/arena-skill/scripts/preview.py poll");
  var chainMessage = liveMessage("running Bash", "$ git fetch origin && arena-preview poll");
  var readMessage = liveMessage("running Bash", "Read the inbox");
  readMessage.row.textContent = "stderr End the turn with `poll`.";
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
  // The owner's captured card: an answered question wears the Summary header, and the
  // chosen answer sits beside a check. The chosen row raises no mark.
  function summaryDoc() {
    var header = { textContent: "Summary" };
    var answer = { textContent: "Yes, rendered fine" };
    var answerRow = {
      querySelector: function () {
        return null;
      },
    };
    answer.parentElement = answerRow;
    var card = {
      querySelectorAll: function (selector) {
        return selector === GROUP_LABEL_SELECTOR ? [header, answer] : [];
      },
    };
    header.parentElement = card;
    answerRow.parentElement = card;
    var message = {
      querySelectorAll: function (selector) {
        if (selector === GROUP_LABEL_SELECTOR) return [header, answer];
        return [];
      },
      contains: function (candidate) {
        return candidate === answerRow || candidate === card;
      },
    };
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return [message];
        if (selector === "button[aria-label]") return [stopButton("Stop generating")];
        return [];
      },
    };
  }
  // A live Bash row with a pulsing icon stands beside words that keep growing.
  // The growing message outranks its own row mark, and the mark waits out the
  // quiet gap after the last burst.
  function speechOverBashDoc() {
    var words = [{ textContent: "Watching" }, { textContent: "the" }];
    var label = { textContent: "Bash" };
    var button = {
      querySelector: function (selector) {
        return selector === "p" ? label : null;
      },
    };
    var row = {
      querySelector: function (selector) {
        return selector === "button" ? button : null;
      },
    };
    button.parentElement = row;
    var icon = {
      closest: function (selector) {
        return selector === "button" ? button : null;
      },
    };
    var message = {
      querySelectorAll: function (selector) {
        if (selector === SPEECH_SELECTOR) return words.slice();
        if (selector === LIVE_ICON_SELECTOR) return [icon];
        if (selector === GROUP_LABEL_SELECTOR + ", " + LIVE_LABEL_SELECTOR + ", " + LIVE_ICON_SELECTOR) {
          return [icon];
        }
        return [];
      },
      contains: function (candidate) {
        return candidate === row || candidate === icon;
      },
    };
    return {
      title: "ChatGPT",
      words: words,
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? repoLink : null;
      },
      querySelectorAll: function (selector) {
        if (selector === SPEECH_SELECTOR) return words.slice();
        if (selector === MESSAGE_SELECTOR) return [message];
        if (selector === "button[aria-label]") return [stopButton("Stop generating")];
        return [];
      },
    };
  }
  var speechOverBash = speechOverBashDoc();
  var agentChatDoc = pulseDoc([divMessage("Agent chat", true)], null);
  var rocketsDoc = pulseDoc([divMessage("Deploying rockets", true)], null);
  var olderPulseDoc = pulseDoc([busyMessage, divMessage("Nothing running")], null);
  setPriorTitle("ChatGPT");
  var userscriptText = fs.readFileSync(
    path.join(__dirname, "..", "userscripts", "arena.user.js"),
    "utf8",
  );
  var cases = [
    // The name carries the running version; the constant and the header agree.
    [VERSION, /@version\s+(\S+)/.exec(userscriptText)[1]],
    ["Arena.ai | NemoUtils | v" + VERSION, /@name\s+(.*)/.exec(userscriptText)[1].trim()],
    [repoFromLink(repoLink), "clankers"],
    [repoFromLink(labelOnly), "clankers"],
    [repoFromLink(emptyLink), null],
    [repoFromLink(null), null],
    [desiredTitle(setDoc), TITLE_PREFIX + "clankers" + vtag],
    // The header can drop the link on a re-render; the name holds while the page stays put.
    [desiredTitle(keepDoc), TITLE_PREFIX + "clankers" + vtag],
    [syncTitle(setDoc), true],
    [setDoc.title, TITLE_PREFIX + "clankers" + vtag],
    [syncTitle(setDoc), false],
    [syncTitle(keepDoc), true],
    [keepDoc.title, TITLE_PREFIX + "clankers" + vtag],
    [syncTitle(goneDoc), false],
    [goneDoc.title, TITLE_PREFIX + "clankers" + vtag],
    // Another page drops the memory, and the next good read puts it back.
    [forgetPath(), null],
    [desiredTitle(keepDoc), null],
    [syncTitle(keepDoc), true],
    [keepDoc.title, "ChatGPT"],
    [syncTitle(keepDoc), false],
    [rememberRepo(), "clankers"],
    [desiredTitle(keepDoc), TITLE_PREFIX + "clankers" + vtag],
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
    // The owner's bug: the Writing row fell to the gear emoji through the unmatched label.
    [emojiForRow(liveRow(pulseLabelDoc("span", "Writing"))), "\u270F\uFE0F"],
    // The next owner's bug: a Fetching row (a web page read) fell to the gear emoji.
    [emojiForRow(liveRow(pulseLabelDoc("span", "Fetching"))), "\uD83D\uDD0D"],
    [actionEmoji("Fetching web page"), "\uD83D\uDD0D"],
    [emojiForRow(liveRow(pulseLabelDoc("svg"))), "\u270F\uFE0F"],
    [emojiForRow(liveRow(editingUnderDoneDoc())), "\u270F\uFE0F"],
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
    [actionEmoji("Writing"), "\u270F\uFE0F"],
    // The owner's reading group: Explored, Read.
    [actionEmoji("Explored"), "\uD83D\uDCD6"],
    [actionEmoji("Exploring"), "\uD83D\uDCD6"],
    [actionEmoji("Read"), "\uD83D\uDCD6"],
    [actionEmoji("Searching the web"), "\uD83D\uDD0D"],
    [actionEmoji("Thought for 2 seconds"), "\uD83D\uDCAD"],
    [actionEmoji("Thinking about the next step"), "\uD83D\uDCAD"],
    [actionEmoji("Re-thinking"), "\uD83D\uDCAD"],
    [actionEmoji("Waiting"), "\uD83D\uDCA4"],
    // The owner's pick for the process output row: the scroll reads as the log roll.
    [actionEmoji("get_process_output"), "\uD83D\uDCDC"],
    // The owner keeps the gear: an unmatched label inside a message still marks the
    // row, so Agent chat earns the fallback instead of dropping out of the title.
    [actionEmoji("Doing something"), "\u2699\uFE0F"],
    [actionEmoji("Agent chat"), "\u2699\uFE0F"],
    [emojiForRow(liveRow(agentChatDoc)), "\u2699\uFE0F"],
    [emojiForRow(liveRow(rocketsDoc)), "\u2699\uFE0F"],
    // The answered question card wears the Summary header and raises no mark; every
    // other unmatched row keeps the gear fallback.
    [liveRow(summaryDoc()), null],
    [actionEmoji(null), null],
    [desiredTitle(busyDoc), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDDA5\uFE0F"],
    [syncTitle(busyDoc), true],
    [busyDoc.title, TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDDA5\uFE0F"],
    [syncTitle(idleDoc), true],
    [idleDoc.title, TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDDA5\uFE0F"],
    [expireHold(), null],
    [desiredTitle(idleDoc), TITLE_PREFIX + "clankers" + vtag],
    [syncTitle(idleDoc), true],
    [idleDoc.title, TITLE_PREFIX + "clankers" + vtag],
    // The ask_user card holds the title with a question mark, and the security
    // check beats it, like every other mark.
    [questionSignal(questionDoc(questionCard())), true],
    [questionSignal(questionDoc(null)), false],
    [expireHold(), null],
    [desiredTitle(questionDoc(questionCard())), TITLE_PREFIX + "clankers" + vtag + " " + QUESTION_EMOJI],
    [loggedTitleHead(questionDoc(questionCard())),
      "[NemoUtils][title] question card -> " + TITLE_PREFIX + "clankers" + vtag + " " + QUESTION_EMOJI],
    [expireHold(), null],
    [desiredTitle(questionDoc(questionCard(), true)), TITLE_PREFIX + "clankers" + vtag + " " + CAPTCHA_EMOJI],
    // Drop the shield hold, so the next cases start from a quiet title.
    [expireHold(), null],
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
    [desiredTitle(looseStopDoc()), TITLE_PREFIX + "clankers" + vtag],
    // The owner's bug: the turn ends, the finished group persists, and only the emoji clears.
    [expireHold(), null],
    [desiredTitle(endedPage), TITLE_PREFIX + "clankers" + vtag],
    [syncTitle(endedPage), true],
    [endedPage.title, TITLE_PREFIX + "clankers" + vtag],
    // The owner's newer bug: a finished row keeps its shimmer label or its
    // pulsing icon, and the stop control is the only thing that leaves. Without the control
    // no row holds the title, and a row's hold dies with the control instead of bridging it.
    [expireHold(), null],
    [desiredTitle(lingeringRowDoc(true)), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCAD"],
    [desiredTitle(lingeringRowDoc(false)), TITLE_PREFIX + "clankers" + vtag],
    [expireHold(), null],
    [desiredTitle(lingeringPulseDoc(true)), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDDA5\uFE0F"],
    [desiredTitle(lingeringPulseDoc(false)), TITLE_PREFIX + "clankers" + vtag],
    // The waiting line is a turn mark too: no control, no hourglass.
    [expireHold(), null],
    [desiredTitle(canvasDoc([rowCanvas(true).canvas], null, null, false)), TITLE_PREFIX + "clankers" + vtag],
    // The start-process card: a play icon and the process name, so the
    // card alone raises the bash emoji while the turn runs. A finished card keeps its play icon
    // in the page, so it marks no longer once the stop control leaves, and a newer message
    // takes the title.
    [expireHold(), null],
    [desiredTitle(processDoc(true)), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDDA5\uFE0F"],
    [desiredTitle(processDoc(false)), TITLE_PREFIX + "clankers" + vtag],
    [desiredTitle(processDoc(true, true)), TITLE_PREFIX + "clankers" + vtag],
    [typeof processRow(processDoc(true)), "object"],
    [processRow(processDoc(false)), null],
    [processRow(processDoc(true, true)), null],
    [processRow(idleDoc), null],
    // One mark for the agent's words: growth of the newest
    // data-agent-word message raises the solid balloon, whatever the turn state. The first
    // look only sets the mark in silence, so a page load or a chat switch stays quiet.
    [expireHold(), null],
    [resetSpeech(), null],
    [speechGrowth(talking), false],
    [addWord(talking, "again"), 3],
    [speechGrowth(talking), true],
    [speechGrowth(talking), false],
    [desiredTitle(talking), TITLE_PREFIX + "clankers" + vtag],
    // The next burst raises the one mark, and the same message keeps that one emoji: no
    // second mark ever replaces it.
    [resetSpeech(), null],
    [desiredTitle(talking), TITLE_PREFIX + "clankers" + vtag],
    [addWord(talking, "later"), 4],
    [desiredTitle(talking), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    // The hold bridges the pause between two bursts of words.
    [desiredTitle(talking), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [addWord(talking, "again"), 5],
    [desiredTitle(talking), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [expireHold(), null],
    [desiredTitle(talking), TITLE_PREFIX + "clankers" + vtag],
    // Speech wins over its own rows: while the newest message grows, the balloon
    // outranks the pulsing Bash row, and it keeps the title through the quiet gap
    // right after the burst. The first look only sets the speech baseline, so the
    // row mark still marks that one tick.
    [resetSpeech(), null],
    [desiredTitle(speechOverBash), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    [addWord(speechOverBash, "title"), 3],
    [desiredTitle(speechOverBash), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [desiredTitle(speechOverBash), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [expireHold(), null],
    [resetSpeech(), null],
    // A message that lands with no turn open takes the very same mark and emoji: one
    // condition, one balloon.
    [resetSpeech(), null],
    [desiredTitle(settledChat), TITLE_PREFIX + "clankers" + vtag],
    [addWord(settledChat, "later"), 3],
    [desiredTitle(settledChat), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [expireHold(), null],
    [desiredTitle(settledChat), TITLE_PREFIX + "clankers" + vtag],
    [
      polls("/home/user/clankers/.agents/skills/arena-skill/scripts/arena-preview poll"),
      true,
    ],
    [polls("arena-preview poll --max 1"), true],
    [polls("python preview.py poll"), true],
    [polls("cat skills/arena-skill/README.md | grep polling"), false],
    [polls('cat > "$HOOK" <<EOF\n# arena-preview-hook: poll the steering inbox'), false],
    [polls("python preview.py polls"), false],
    [polls('python - <<PY\np = Path("skills/arena-skill/scripts/preview.py")\nprint("The poll error names the restart command.")\nPY'), false],
    // The owner's waiting line: rotating words, one structural selector, one hourglass.
    [WAITING_SELECTOR, 'canvas[width="16"][height="16"]'],
    [WAITING_TEXT_SELECTOR, 'span[class*="whitespace-pre"]'],
    [waitingSignal(waitingDoc()), true],
    // The owner's action row carries the very same canvas as its icon, so
    // the canvas alone never reads as a waiting line and never outranks the Bash row.
    [waitingSignal(actionCanvasDoc()), false],
    [waitingSignal(setDoc), false],
    [expireHold(), null],
    [desiredTitle(waitingDoc()), TITLE_PREFIX + "clankers" + vtag + " " + HOURGLASS_EMOJI],
    [expireHold(), null],
    [desiredTitle(actionCanvasDoc()), TITLE_PREFIX + "clankers" + vtag],
    [expireHold(), null],
    // A named action outranks the line, so the poll row keeps its own emoji.
    [desiredTitle(waitingDoc([pollMessage])), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCA4"],
    // Streamed words outrank the line too: the first burst sets the mark, and the next one
    // raises the same balloon over the line.
    [expireHold(), null],
    [resetSpeech(), null],
    [desiredTitle(waitingDoc(null, [{ textContent: "Sandbox" }])),
      TITLE_PREFIX + "clankers" + vtag + " " + HOURGLASS_EMOJI],
    [expireHold(), null],
    [
      desiredTitle(waitingDoc(null, [{ textContent: "Sandbox" }, { textContent: "again" }])),
      TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI,
    ],
    [expireHold(), null],
    [desiredTitle(waitingDoc()), TITLE_PREFIX + "clankers" + vtag + " " + HOURGLASS_EMOJI],
    [expireHold(), null],
    // The gear row never blocks the line: an unmapped chat row sits in the transcript,
    // and the waiting line still raises the hourglass.
    [
      desiredTitle(waitingDoc([divMessage("Agent chat", true)])),
      TITLE_PREFIX + "clankers" + vtag + " " + HOURGLASS_EMOJI,
    ],
    [expireHold(), null],
    [desiredTitle(idleDoc), TITLE_PREFIX + "clankers" + vtag],
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
    [desiredTitle(captchaDoc()), TITLE_PREFIX + "clankers" + vtag + " " + CAPTCHA_EMOJI],
    [desiredTitle(captchaDoc([pollMessage])), TITLE_PREFIX + "clankers" + vtag + " " + CAPTCHA_EMOJI],
    [desiredTitle(captchaDoc()), TITLE_PREFIX + "clankers" + vtag + " " + CAPTCHA_EMOJI],
    // Every title change prints one line: the signal, then the emoji the title takes.
    [
      loggedTitleHead(captchaDoc()),
      "[NemoUtils][title] security check -> " + TITLE_PREFIX + "clankers" + vtag + " " + CAPTCHA_EMOJI,
    ],
    // The anchors behind the decision ride the same line, so a title shows its cause.
    [loggedTitleTail(captchaDoc()), "repo=clankers row=none"],
    // The label behind the row rides the line, so the cause is visible.
    [
      loggedTitleHead(waitingDoc([pollMessage])),
      "[NemoUtils][title] poll command (running Bash) -> " + TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCA4",
    ],
    [
      loggedTitleTail(waitingDoc([pollMessage])),
      "repo=clankers row=poll command (running Bash)",
    ],
    // The anchor cites the row that won the mark, not the row the page re-derives at
    // write time: the reason and the row half name one row.
    [expireHold(), null],
    // The newest row owns the mark: a later Explored row, or a later Bash row,
    // takes the title back from a start-process card in the same message.
    [
      loggedTitleHead(processDocExplored()),
      "[NemoUtils][title] action row (Explored 2 reads) -> " +
        TITLE_PREFIX +
        "clankers" + vtag + " \uD83D\uDCD6",
    ],
    [
      loggedTitleTail(processDocExplored()),
      "repo=clankers row=action row (Explored 2 reads)",
    ],
    [
      loggedTitleHead(processDocLaterRow()),
      "[NemoUtils][title] action row (Bash sleep 25) -> " +
        TITLE_PREFIX +
        "clankers" + vtag + " \uD83D\uDDA5\uFE0F",
    ],
    [
      loggedTitleTail(processDocLaterRow()),
      "repo=clankers row=action row (Bash sleep 25)",
    ],
    [processRow(processDocLaterRow()), null],
    // The owner's flip-flop: the watcher card loses the title once the message that
    // started it keeps speaking; a spoken word after the card outranks it.
    [processRow(processDocSpeaking()), null],
    // A labelled row in an older message never marks once a newer message exists,
    // even when the newer message carries no label of its own.
    [strongRow(labeledBehindEmptyDoc()), null],
    // A live row streams under its shimmer label before a group label lands; the
    // mark follows it instead of freezing on the last labelled row.
    [(function () {
      var f = titleDocStreaming();
      return strongRow(f.doc) === f.liveRow;
    })(), true],
    [expireHold(), null],
    [
      loggedTitleHead(idleDoc),
      "[NemoUtils][title] title -> " + TITLE_PREFIX + "clankers" + vtag,
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
  // One line per change stays, and the plain unchanged line is gone (answer e8fc4f6): a second
  // sync with the title already in place writes nothing at all.
  var quiet = [];
  var louder = console.log;
  console.log = function () {
    quiet.push(Array.prototype.join.call(arguments, " "));
  };
  try {
    // The line carried a one-second throttle while it existed, and the module keeps its own
    // Date, so the check waits the window out before the second sync.
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 1100);
    api.syncTitle(idleDoc);
  } finally {
    console.log = louder;
  }
  if (quiet.length) {
    console.error("check fail", "unchanged title line", quiet.join(" | "));
    throw new Error("the unchanged title line still fires: " + quiet.join(" | "));
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
  var panelNeeded = api.panelNeeded;
  var handleMatchesScope = api.handleMatchesScope;
  var stateScope = api.stateScope;
  var stateRepo = api.stateRepo;
  var stateScopeKey = api.stateScopeKey;
  var pagePicker = api.pagePicker;
  var writtenName = api.writtenName;
  var STATE_LINES = api.STATE_LINES;
  var copyLine = api.copyLine;
  var stampHash = api.stampHash;
  var getLine = api.getLine;
  var noopLine = api.noopLine;
  var writeLine = api.writeLine;
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
  // The Arena UI moves the GitHub integration around, so the repo/branch span can vanish;
  // the conversation header still opens with the repository name, and its first word is the
  // repository. That read comes before the tab title.
  var headerSpan = { textContent: "clankers read ARENA.md AGENTS.md in full before your first edit" };
  var headerDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      return selector.indexOf("aria-haspopup") !== -1 ? [headerSpan] : [];
    },
    title: "Arena | other",
  };
  assert.equal(stateRepo(headerDoc), "clankers");
  // A header span with no slug-like first word falls through to the tab title.
  headerSpan.textContent = "";
  assert.equal(stateRepo(headerDoc), "other");
  // The saved slug still wins over the header read.
  session.value = "saved";
  headerSpan.textContent = "clankers read ARENA.md";
  assert.equal(stateRepo(headerDoc), "saved");
  session.value = null;
  // A menu click grants no browser gesture, so the automatic path writes the stamped
  // download and the pick stays a manual action.
  // No file is set: an automatic tick blocks instead of dropping a stamped download on the
  // owner. A deferred save never opens the picker, because the browser needs the
  // press itself and a save that waited on the network has spent it: it asks for
  // the choose entry instead. A manual press keeps the download where no picker exists.
  assert.equal(stateAction("pick", false), "block");
  assert.equal(stateAction("pick", true), "hint");
  assert.equal(stateAction("download", false), "block");
  assert.equal(stateAction("download", true), "download");
  assert.equal(stateAction("write", true), "write");
  // The no-file card: a manual press always gets it, and an automatic tick gets it once
  // per unconfigured period.
  assert.equal(panelNeeded(true, true), true);
  assert.equal(panelNeeded(true, false), true);
  assert.equal(panelNeeded(false, false), true);
  assert.equal(panelNeeded(false, true), false);
  assert.equal(stateAction("unchanged", false), "unchanged");
  // The owner's line shapes: the fetch on a write, the no-op on a quiet tick, and short
  // stamp hashes in place of the long stamps (answers 1fcb4bd and 9602cb5).
  assert.equal(writeLine("clankers", "clankers.ndjson"), "WRITE clankers state to clankers.ndjson");
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
  // The card does not replace the console line: the same words reach both, and a card-less
  // run (the checks) still logs.
  var errorLines = [];
  var restoreLog = console.log;
  console.log = function () {
    errorLines.push(Array.prototype.join.call(arguments, " "));
  };
  try {
    stateError("GET 500 http://localhost:8000/api/copy-state");
  } finally {
    console.log = restoreLog;
  }
  assert.ok(
    errorLines.indexOf("[NemoUtils][state] GET 500 http://localhost:8000/api/copy-state") !== -1,
    errorLines.join("\n"),
  );
  assert.equal(noopLine("clankers", "http://localhost:8000"), "NOOP clankers http://localhost:8000");
  assert.equal(getLine(200, "http://localhost:8000"), "GET 200 http://localhost:8000");
  assert.match(stampHash("2026-10-06T09:45:05+00:00"), /^[0-9a-f]{7}$/);
  assert.equal(stampHash(""), "none");
  assert.equal(stampHash("2026-10-06T09:45:05+00:00"), stampHash("2026-10-06T09:45:05+00:00"));
  // The owner's line texts (answer 5ca4f63): the no-file hint names the dialog it launches, a
  // stale state reads as a history mismatch, and a closed picker reads as a plain no-file line.
  assert.equal(STATE_LINES.hint, "no file selected; launching dialog");
  assert.equal(STATE_LINES.history, "history does not match");
  assert.equal(STATE_LINES.pickerClosed, "no file selected;");
  // The refused copy reads as a GET too, and the missing frame reads plainly (answer 2f6b5a7).
  assert.equal(STATE_LINES.noPreview, "no preview detected");
  assert.equal(
    copyLine(500, "http://localhost:8000"),
    "GET 500 http://localhost:8000/api/copy-state",
  );
  // Every comparison in the save path writes its own line, so one filter shows which test
  // refused a write.
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
  }
  function comparedLine(expected) {
    return compared.indexOf("[NemoUtils][state] " + expected) !== -1;
  }
  assert.ok(
    comparedLine(
      "note - older - " + stampHash("2026-10-06T05:00:00") + " vs " + stampHash("2026-10-06T05:30:00"),
    ),
    compared.join("\n"),
  );
  assert.ok(
    comparedLine(
      "task - forward - " + stampHash("2026-10-06T06:00:00") + " vs " + stampHash("2026-10-06T05:00:00"),
    ),
    compared.join("\n"),
  );
  assert.ok(comparedLine("compare stamp: none, no stamp to compare"), compared.join("\n"));
  // A quiet tick with the pair at rest shows both lines as `same` (answer 1fcb4bd).
  assert.ok(
    comparedLine(
      "note - same - " + stampHash("2026-10-06T06:12:33") + " vs " + stampHash("2026-10-06T06:12:33"),
    ),
    compared.join("\n"),
  );
  assert.ok(
    comparedLine(
      "task - same - " + stampHash("2026-10-06T06:12:33") + " vs " + stampHash("2026-10-06T06:12:33"),
    ),
    compared.join("\n"),
  );
  // A forced save announces the update from the old stamp to the new one (answer 86ba0cc).
  assert.ok(
    comparedLine(
      "updating note stamp from " + stampHash("2026-10-06T05:30:00") + " to " + stampHash("2026-10-06T05:00:00"),
    ),
    compared.join("\n"),
  );
  assert.ok(
    comparedLine(
      "updating task stamp from " + stampHash("2026-10-06T05:00:00") + " to " + stampHash("2026-10-06T06:00:00"),
    ),
    compared.join("\n"),
  );
  // The long stamp lines and the route words are gone from the state watch.
  var leftovers = compared.filter(function (line) {
    return (
      line.indexOf("[NemoUtils][state] tick ") !== -1 ||
      line.indexOf("[NemoUtils][state] route ") !== -1 ||
      line.indexOf("[NemoUtils][state] download: ") !== -1 ||
      line.indexOf("[NemoUtils][state] saved ") !== -1 ||
      line.indexOf("[NemoUtils][state] compare stamp") !== -1 &&
        line.indexOf("no stamp to compare") === -1
    );
  });
  assert.deepEqual(leftovers, [], compared.join("\n"));
  // A remembered file belongs to the scope that chose it: the name carries the scope, and a
  // handle outside the current scope is refused so one repo never writes into another's file.
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
