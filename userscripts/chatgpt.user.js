// ==UserScript==
// @name         ChatGPT.com | NemoUtils
// @namespace    https://github.com/nemoe7/clankers
// @version      1.3.5
// @description  Hide interface elements and auto-click Think with saved feature switches
// @author       nemoe7
// @icon         https://chatgpt.com/favicon.ico
// @license      MIT
// @match        https://chatgpt.com/*
// @updateURL    https://raw.githubusercontent.com/nemoe7/clankers/main/userscripts/chatgpt.user.js
// @downloadURL  https://raw.githubusercontent.com/nemoe7/clankers/main/userscripts/chatgpt.user.js
// @run-at       document-idle
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM_unregisterMenuCommand
// ==/UserScript==

(function () {
  "use strict";

  // Outside a browser each feature publishes its helpers, so the checks live in
  // maintenance/ instead of shipping inside this bundle.
  function exposeChecks(name, api) {
    if (typeof document !== "undefined") {
      return false;
    }
    var store = globalThis.CLANKERS_CHECKS || {};
    store[name] = api;
    globalThis.CLANKERS_CHECKS = store;
    return true;
  }

  // One tag filters the whole story of a page in the devtools console. A line names
  // the event a person needs and never the feature's own loop.
  var LOG_TAG = "[NemoUtils]";

  // One tag carries every line, and the module rides a second bracket, so one filter shows
  // one module alone.
  function logEvent(module, event, detail) {
    var line = LOG_TAG + "[" + module + "] " + event;
    try {
      if (detail === undefined) {
        console.log(line);
      } else {
        console.log(line, detail);
      }
    } catch (err) {
      return;
    }
  }

  exposeChecks("logging", { logEvent: logEvent, LOG_TAG: LOG_TAG });

  function runFeature(key, label, run) {
    if (typeof document === "undefined") {
      run();
      return;
    }
    var enabled = GM_getValue(key, true) !== false;
    var menuId;
    var stop = null;
    logEvent("feature", label + ": " + (enabled ? "ON" : "OFF"));

    function showMenu(value) {
      menuId = GM_registerMenuCommand(
        label + ": " + (value ? "ON" : "OFF") + " — toggle",
        function () {
          var next = GM_getValue(key, true) === false;
          GM_setValue(key, next);
          logEvent("feature", label + ": " + (next ? "ON" : "OFF"));
          if (stop) stop();
          stop = next ? run() : null;
          GM_unregisterMenuCommand(menuId);
          showMenu(next);
        },
      );
    }

    showMenu(enabled);
    if (enabled) {
      stop = run();
    }
  }

  runFeature("hide-elements", "Hide elements", function () {

    var CLAIM_TEXT = "Claim offer";
    var CLAIM_DIV_SELECTOR = "div.col-span-full.mt-1.mb-3\\.5.px-2";
    var FREE_OFFER_TEXT = "Free offer";
    var FREE_OFFER_DIV_SELECTOR = "div.flex.items-center.gap-1.select-none";
    var MODE_TOGGLE_SELECTOR = "div.\\@container\\/home-mode-toggle";
    var CODEX_ITEM_SELECTOR = 'button[data-sidebar-destination="builtin:codex"]';
    var IMAGES_ITEM_SELECTOR = 'button[data-sidebar-destination="builtin:images"]';
    var LIBRARY_ITEM_SELECTOR = 'button[data-sidebar-destination="builtin:library"]';
    var FREE_BADGE_SELECTOR = "span.truncate.text-xs.text-secondary.select-none";
    var FREE_BADGE_TEXT = "Free";
    var HEADER_DIV_SELECTOR = "div[data-prompt-textarea-header]";

    function findButtonByText(doc, text) {
      var buttons = doc.querySelectorAll("button");
      var i;
      for (i = 0; i < buttons.length; i += 1) {
        if (String(buttons[i].textContent || "").trim() === text) {
          return buttons[i];
        }
      }
      return null;
    }

    function findClaimDiv(doc) {
      var button = findButtonByText(doc, CLAIM_TEXT);
      return button ? button.closest(CLAIM_DIV_SELECTOR) : null;
    }

    function findFreeOfferDiv(doc) {
      var button = findButtonByText(doc, FREE_OFFER_TEXT);
      return button ? button.closest(FREE_OFFER_DIV_SELECTOR) : null;
    }

    function findModeToggle(doc) {
      return doc.querySelector(MODE_TOGGLE_SELECTOR);
    }

    function findFreeBadge(doc) {
      var badge = doc.querySelector(FREE_BADGE_SELECTOR);
      return badge && String(badge.textContent || "").trim() === FREE_BADGE_TEXT ? badge : null;
    }

    function findHeaderDiv(doc) {
      return doc.querySelector(HEADER_DIV_SELECTOR);
    }

    var hiddenElements = new Set();

    function hideElement(el) {
      if (!el || el.hasAttribute("hidden")) {
        return false;
      }
      hiddenElements.add(el);
      el.setAttribute("hidden", "");
      return true;
    }

    // One destination keeps two live nodes: the collapsed rail and the open nav
    // list. Hiding one leaves the other visible in the other sidebar state.
    function hideAll(doc, selector) {
      var found = doc.querySelectorAll(selector);
      var i;
      for (i = 0; i < found.length; i += 1) {
        hideElement(found[i]);
      }
    }

    function syncDocument(doc) {
      hideElement(findClaimDiv(doc));
      hideElement(findFreeOfferDiv(doc));
      hideElement(findModeToggle(doc));
      hideAll(doc, CODEX_ITEM_SELECTOR);
      hideAll(doc, IMAGES_ITEM_SELECTOR);
      hideAll(doc, LIBRARY_ITEM_SELECTOR);
      hideElement(findFreeBadge(doc));
      hideElement(findHeaderDiv(doc));
    }

    function sync() {
      syncDocument(document);
    }

    if (exposeChecks("hideElements", {
      CLAIM_TEXT: CLAIM_TEXT,
      CLAIM_DIV_SELECTOR: CLAIM_DIV_SELECTOR,
      FREE_OFFER_TEXT: FREE_OFFER_TEXT,
      FREE_OFFER_DIV_SELECTOR: FREE_OFFER_DIV_SELECTOR,
      MODE_TOGGLE_SELECTOR: MODE_TOGGLE_SELECTOR,
      CODEX_ITEM_SELECTOR: CODEX_ITEM_SELECTOR,
      IMAGES_ITEM_SELECTOR: IMAGES_ITEM_SELECTOR,
      LIBRARY_ITEM_SELECTOR: LIBRARY_ITEM_SELECTOR,
      FREE_BADGE_SELECTOR: FREE_BADGE_SELECTOR,
      FREE_BADGE_TEXT: FREE_BADGE_TEXT,
      HEADER_DIV_SELECTOR: HEADER_DIV_SELECTOR,
      findButtonByText: findButtonByText,
      findClaimDiv: findClaimDiv,
      findFreeOfferDiv: findFreeOfferDiv,
      findModeToggle: findModeToggle,
      findFreeBadge: findFreeBadge,
      findHeaderDiv: findHeaderDiv,
      hideElement: hideElement,
      hideAll: hideAll,
      syncDocument: syncDocument,
    })) {
      return;
    }

    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    window.addEventListener("popstate", sync);
    sync();
    return function () {
      observer.disconnect();
      window.removeEventListener("popstate", sync);
      hiddenElements.forEach(function (el) { if (el.getAttribute("hidden") === "") el.removeAttribute("hidden"); });
      hiddenElements.clear();
    };
  });

  runFeature("auto-think", "Auto Think", function () {

    var THINK_PILL_SELECTOR = 'button[aria-pressed="false"]';
    var THINK_LABEL = "Think";
    var PRESS_INTERVAL_MS = 1000;

    function findThinkPill(doc) {
      var pills = doc.querySelectorAll(THINK_PILL_SELECTOR);
      var i;
      for (i = 0; i < pills.length; i += 1) {
        if (String(pills[i].textContent || "").trim() === THINK_LABEL) {
          return pills[i];
        }
      }
      return null;
    }

    function pressThink(doc) {
      var pill = findThinkPill(doc);
      if (!pill) {
        return false;
      }
      pill.click();
      return true;
    }

    if (exposeChecks("autoThink", {
      THINK_PILL_SELECTOR: THINK_PILL_SELECTOR,
      PRESS_INTERVAL_MS: PRESS_INTERVAL_MS,
      findThinkPill: findThinkPill,
      pressThink: pressThink,
    })) {
      return;
    }

    pressThink(document);
    var timer = setInterval(function () {
      pressThink(document);
    }, PRESS_INTERVAL_MS);
    return function () { clearInterval(timer); };
  });

})();
