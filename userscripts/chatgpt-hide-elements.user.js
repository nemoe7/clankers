// ==UserScript==
// @name         ChatGPT Hide Elements
// @namespace    https://github.com/nemoe7/clankers
// @version      1.0.0
// @description  On chatgpt.com, add hidden to the claim, offer, toggle, Codex and header elements
// @author       nemoe7
// @license      MIT
// @match        https://chatgpt.com/*
// @updateURL    https://gist.githubusercontent.com/nemoe7/a11743bbe3fdddfa3f483a979d5d1f09/raw/chatgpt-hide-elements.user.js
// @downloadURL  https://gist.githubusercontent.com/nemoe7/a11743bbe3fdddfa3f483a979d5d1f09/raw/chatgpt-hide-elements.user.js
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  var CLAIM_BUTTON_SELECTOR = 'button[aria-label="Claim offer"]';
  var CLAIM_DIV_SELECTOR = "div.mx-3\\.5.mt-1.mb-2";
  var FREE_OFFER_TEXT = "Free offer";
  var FREE_OFFER_DIV_SELECTOR = "div.translucent-surface";
  var SURFACE_RADIO_SELECTOR = 'div[role="radiogroup"][aria-label="Select chat surface"]';
  var SURFACE_DIV_SELECTOR = "div.start-1\\/2";
  var CODEX_LINK_SELECTOR = 'a[data-sidebar-item][href="/codex"]';
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

  function findHeaderDiv(doc) {
    return doc.querySelector(HEADER_DIV_SELECTOR);
  }

  function hideElement(el) {
    if (!el || el.hasAttribute("hidden")) {
      return false;
    }
    el.setAttribute("hidden", "");
    return true;
  }

  function sync() {
    hideElement(findClaimDiv(document));
    hideElement(findFreeOfferDiv(document));
    hideElement(findSurfaceDiv(document));
    hideElement(findCodexLink(document));
    hideElement(findHeaderDiv(document));
  }

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

  function runChecks() {
    var claimDiv = fakeElement();
    var freeDiv = fakeElement();
    var surfaceDiv = fakeElement();
    var codexLink = fakeElement();
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
    if (failed) {
      throw new Error(failed + " checks failed");
    }
    console.log("ok " + cases.length);
  }

  if (typeof document === "undefined") {
    runChecks();
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
})();
