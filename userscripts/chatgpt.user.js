// ==UserScript==
// @name         Clankers ChatGPT
// @namespace    https://github.com/nemoe7/clankers
// @version      1.2.2
// @description  Hide interface elements and auto-click Think with saved feature switches
// @author       nemoe7
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

  function runFeature(key, label, run) {
    if (typeof document === "undefined") {
      run();
      return;
    }
    var enabled = GM_getValue(key, true) !== false;
    var menuId;
    var stop = null;

    function showMenu(value) {
      menuId = GM_registerMenuCommand(
        label + ": " + (value ? "ON" : "OFF") + " — toggle",
        function () {
          var next = GM_getValue(key, true) === false;
          GM_setValue(key, next);
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

    var CLAIM_BUTTON_SELECTOR = 'button[aria-label="Claim offer"]';
    var CLAIM_DIV_SELECTOR = "div.mx-3\\.5.mt-1.mb-2";
    var FREE_OFFER_TEXT = "Free offer";
    var FREE_OFFER_DIV_SELECTOR = "div.translucent-surface";
    var SURFACE_RADIO_SELECTOR = 'div[role="radiogroup"][aria-label="Select chat surface"]';
    var SURFACE_DIV_SELECTOR = "div.start-1\\/2";
    var CODEX_LINK_SELECTOR = 'a[data-sidebar-item][href="/codex"]';
    var IMAGES_LINK_SELECTOR = 'a[data-sidebar-item][href="/images"]';
    var LIBRARY_LINK_SELECTOR = 'a[data-sidebar-item][href^="/library"]';
    var FREE_BADGE_SELECTOR = "span.text-caption-regular.text-token-text-tertiary";
    var FREE_BADGE_TEXT = "Free";
    var HEADER_DIV_SELECTOR = "div[data-prompt-textarea-header]";

    function findClaimDiv(doc) {
      var button = doc.querySelector(CLAIM_BUTTON_SELECTOR);
      return button ? button.closest(CLAIM_DIV_SELECTOR) : null;
    }

    function findFreeOfferDiv(doc) {
      var buttons = doc.querySelectorAll("button");
      var i;
      for (i = 0; i < buttons.length; i += 1) {
        if (String(buttons[i].textContent || "").trim() === FREE_OFFER_TEXT) {
          return buttons[i].closest(FREE_OFFER_DIV_SELECTOR);
        }
      }
      return null;
    }

    function findSurfaceDiv(doc) {
      var radio = doc.querySelector(SURFACE_RADIO_SELECTOR);
      return radio ? radio.closest(SURFACE_DIV_SELECTOR) : null;
    }

    function findCodexLink(doc) {
      return doc.querySelector(CODEX_LINK_SELECTOR);
    }

    function findImagesLink(doc) {
      return doc.querySelector(IMAGES_LINK_SELECTOR);
    }

    function findLibraryLink(doc) {
      return doc.querySelector(LIBRARY_LINK_SELECTOR);
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

    function syncDocument(doc) {
      hideElement(findClaimDiv(doc));
      hideElement(findFreeOfferDiv(doc));
      hideElement(findSurfaceDiv(doc));
      hideElement(findCodexLink(doc));
      hideElement(findImagesLink(doc));
      hideElement(findLibraryLink(doc));
      hideElement(findFreeBadge(doc));
      hideElement(findHeaderDiv(doc));
    }

    function sync() {
      syncDocument(document);
    }

    if (exposeChecks("hideElements", {
      CLAIM_BUTTON_SELECTOR: CLAIM_BUTTON_SELECTOR,
      CLAIM_DIV_SELECTOR: CLAIM_DIV_SELECTOR,
      FREE_OFFER_DIV_SELECTOR: FREE_OFFER_DIV_SELECTOR,
      SURFACE_DIV_SELECTOR: SURFACE_DIV_SELECTOR,
      SURFACE_RADIO_SELECTOR: SURFACE_RADIO_SELECTOR,
      CODEX_LINK_SELECTOR: CODEX_LINK_SELECTOR,
      IMAGES_LINK_SELECTOR: IMAGES_LINK_SELECTOR,
      LIBRARY_LINK_SELECTOR: LIBRARY_LINK_SELECTOR,
      FREE_BADGE_SELECTOR: FREE_BADGE_SELECTOR,
      HEADER_DIV_SELECTOR: HEADER_DIV_SELECTOR,
      findClaimDiv: findClaimDiv,
      findFreeOfferDiv: findFreeOfferDiv,
      findSurfaceDiv: findSurfaceDiv,
      findCodexLink: findCodexLink,
      findImagesLink: findImagesLink,
      findLibraryLink: findLibraryLink,
      findFreeBadge: findFreeBadge,
      findHeaderDiv: findHeaderDiv,
      hideElement: hideElement,
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

    var THINK_PILL_SELECTOR = 'button.__composer-pill[aria-pressed="false"]';
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
