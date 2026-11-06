const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const { bundles, runBundle, loadChecks } = require("./fixtures/vm_harness.cjs");

runBundle("chatgpt");

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
    menuItem(list, "State - force save", function () {
      ran.push("save");
    });
    assert.equal(list.length, 1);
    var registered = menus.filter(function (item) {
      return item.label === "State - force save";
    }).pop();
    assert.ok(registered, "the registered entry is reachable by its label");
    assert.equal(registered.label, "State - force save");
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
    assert.equal(pressed[0], "[NemoUtils][menu] State - force save");
  }
  console.log("ok logging 3");
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
  // One document answers every selector, so the sync pass itself is under test. A target left out of syncDocument leaves its element unhidden here.
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

function run(name, check) {
  try {
    check();
  } catch (error) {
    throw new Error(`${name}: ${error.message}`);
  }
}

const chatgpt = loadChecks("chatgpt.user.js").checks;
run("hide elements", () => checkHideElements(chatgpt.hideElements));
run("chatgpt logging", () => checkLogging(chatgpt.logging));
run("auto think", () => checkAutoThink(chatgpt.autoThink));
