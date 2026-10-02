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
  const context = { console, URL };
  vm.runInNewContext(source, context, { filename: file });
  return context.CLANKERS_CHECKS;
}

function checkPromptFill(api) {
  var isComposerUrl = api.isComposerUrl;
  var slugFromOwnerRepo = api.slugFromOwnerRepo;
  var promptForSlug = api.promptForSlug;
  var shouldWrite = api.shouldWrite;
  var ARENA_MD_URL = api.ARENA_MD_URL;

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
    [ARENA_MD_URL, "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/rules/ARENA.md"],
    [promptForSlug("clankers"), "clankers read ARENA.md AGENTS.md"],
    [promptForSlug("clankers", "arena content here"), "clankers read ARENA.md AGENTS.md\nhere is ARENA.md:\narena content here"],
    [shouldWrite("", "clankers", null), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md", "clankers", null), false],
    [shouldWrite("clankers read AGENTS.md ARENA.md", "clankers", null), true],
    [shouldWrite("draft", "clankers", null), false],
    [shouldWrite("clankers read ARENA.md AGENTS.md", "other", "clankers"), true],
    [shouldWrite("draft", "clankers", "clankers"), false],
    [shouldWrite("clankers read ARENA.md AGENTS.md", "clankers", "clankers", "arena content"), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md\nhere is ARENA.md:\narena content", "clankers", "clankers", "arena content"), false],
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
  console.log("ok prompt fill " + cases.length);
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
      // liveRow now probes the Stop generating button on every path, as a real document allows.
      querySelectorAll: function () {
        return [];
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
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
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
    return {
      title: "ChatGPT",
      querySelector: function () {
        return null;
      },
      querySelectorAll: function (selector) {
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
        return selector === MESSAGE_SELECTOR && message ? [message] : [];
      },
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? element : null;
      },
    };
  }
  var repoLink = link("https://github.com/nemoe7/clankers", "Open nemoe7/clankers on GitHub");
  var labelOnly = link(null, "Open nemoe7/clankers on GitHub");
  var emptyLink = link("", "");
  var setDoc = docWith(repoLink, "ChatGPT");
  var keepDoc = docWith(null, "ChatGPT");
  var goneDoc = docWith(null, TITLE_PREFIX + "clankers");
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
    [liveRow(groupDoc(false)), null],
    [emojiForRow(liveRow(editRowDoc(true))), "\u270F\uFE0F"],
    [liveRow(editRowDoc(false)), null],
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
  ];
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

const arena = loadChecks("arena.user.js");
run("prompt fill", () => checkPromptFill(arena.promptFill));
run("open steering", () => checkOpenSteering(arena.openSteering));
run("transcript auto-scroll", () => checkAutoScrollToggle(arena.autoScrollToggle));
run("transcript trim", () => checkTranscriptTrim(arena.transcriptTrim));
run("hide composer", () => checkHideComposer(arena.hideComposer));
run("tab title", () => checkTabTitle(arena.tabTitle));

const chatgpt = loadChecks("chatgpt.user.js");
run("hide elements", () => checkHideElements(chatgpt.hideElements));
run("auto think", () => checkAutoThink(chatgpt.autoThink));
