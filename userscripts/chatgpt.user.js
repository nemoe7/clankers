// ==UserScript==
// @name         ChatGPT.com | NemoUtils
// @namespace    https://github.com/nemoe7/clankers
// @version      1.3.8
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

  function exposeChecks(name, api) {
    if (typeof document !== "undefined") {
      return false;
    }
    var store = globalThis.CLANKERS_CHECKS || {};
    store[name] = api;
    globalThis.CLANKERS_CHECKS = store;
    return true;
  }

  var LOG_TAG = "[NemoUtils]";

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
        label + ": " + (value ? "ON" : "OFF") + " - toggle",
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

  var hideOptions = {};
  var syncHidden = null;
  [
    ["claim-offer", "Claim offer"],
    ["free-offer", "Free offer"],
    ["mode-toggle", "mode toggle"],
    ["codex", "Codex"],
    ["images", "Images"],
    ["library", "Library"],
    ["free-badge", "Free badge"],
    ["prompt-header", "prompt header"],
    ["header-upgrade", "header Upgrade"],
    ["header-share", "header Share"],
    ["sidebar-upgrade", "sidebar Upgrade"],
    ["plus-upsell", "Upgrade to Plus"],
  ].forEach(function (target) {
    var key = target[0];
    hideOptions[key] = false;
    runFeature("hide-" + key, "Hide - " + target[1], function () {
      hideOptions[key] = true;
      if (syncHidden) syncHidden();
      return function () {
        hideOptions[key] = false;
        if (syncHidden) syncHidden();
      };
    });
  });

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

    var ACTION_GROUP_SELECTOR = "div.pointer-events-auto.flex.shrink-0.items-center.no-drag";
    var PLUS_ROW_SELECTOR = "div.flex.flex-wrap.items-center.justify-center.gap-2";

    function actionNode(button, selector, text) {
      var group = button.closest(selector);
      return group && group.querySelectorAll("button").length === 1 &&
        String(group.textContent || "").trim() === text ? group : button;
    }

    function collectActions(doc, selector, text, groupSelector, collect) {
      var buttons = doc.querySelectorAll(selector);
      var i;
      for (i = 0; i < buttons.length; i += 1) {
        if (String(buttons[i].textContent || "").trim() === text) {
          collect(actionNode(buttons[i], groupSelector, text));
        }
      }
    }

    function collectPlusRows(doc, collect) {
      var rows = doc.querySelectorAll(PLUS_ROW_SELECTOR);
      var i;
      for (i = 0; i < rows.length; i += 1) {
        collectActions(rows[i], "button", "Upgrade to Plus", PLUS_ROW_SELECTOR, collect);
      }
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

    function hideAll(doc, selector, apply) {
      var found = doc.querySelectorAll(selector);
      var i;
      for (i = 0; i < found.length; i += 1) {
        (apply || hideElement)(found[i]);
      }
    }

    function syncDocument(doc) {
      var wanted = new Set();
      function collect(el) { if (el) wanted.add(el); }
      if (hideOptions["claim-offer"]) collect(findClaimDiv(doc));
      if (hideOptions["free-offer"]) collect(findFreeOfferDiv(doc));
      if (hideOptions["mode-toggle"]) collect(findModeToggle(doc));
      if (hideOptions.codex) hideAll(doc, CODEX_ITEM_SELECTOR, collect);
      if (hideOptions.images) hideAll(doc, IMAGES_ITEM_SELECTOR, collect);
      if (hideOptions.library) hideAll(doc, LIBRARY_ITEM_SELECTOR, collect);
      if (hideOptions["free-badge"]) collect(findFreeBadge(doc));
      if (hideOptions["prompt-header"]) collect(findHeaderDiv(doc));
      if (hideOptions["header-upgrade"]) {
        collectActions(doc, "header button", "Upgrade", ACTION_GROUP_SELECTOR, collect);
      }
      if (hideOptions["header-share"]) {
        collectActions(doc, "header button", "Share", ACTION_GROUP_SELECTOR, collect);
      }
      if (hideOptions["sidebar-upgrade"]) {
        collectActions(doc, "#app-shell-sidebar button", "Upgrade", "div.contents", collect);
      }
      if (hideOptions["plus-upsell"]) collectPlusRows(doc, collect);
      hiddenElements.forEach(function (el) {
        if (!wanted.has(el)) {
          if (el.getAttribute("hidden") === "") el.removeAttribute("hidden");
          hiddenElements.delete(el);
        }
      });
      wanted.forEach(hideElement);
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

    syncHidden = sync;
    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    window.addEventListener("popstate", sync);
    sync();
    return function () {
      syncHidden = null;
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
