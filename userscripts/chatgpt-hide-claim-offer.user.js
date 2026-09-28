// ==UserScript==
// @name         ChatGPT Hide Claim Offer
// @namespace    https://github.com/nemoe7/clankers
// @version      1.0.0
// @description  On chatgpt.com, hide the div that holds the Claim offer button
// @author       nemoe7
// @license      MIT
// @match        https://chatgpt.com/*
// @updateURL    https://gist.githubusercontent.com/nemoe7/a11743bbe3fdddfa3f483a979d5d1f09/raw/chatgpt-hide-claim-offer.user.js
// @downloadURL  https://gist.githubusercontent.com/nemoe7/a11743bbe3fdddfa3f483a979d5d1f09/raw/chatgpt-hide-claim-offer.user.js
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  var CLAIM_BUTTON_SELECTOR = 'button[aria-label="Claim offer"]';
  var CLAIM_DIV_SELECTOR = "div.mx-3\\.5.mt-1.mb-2";

  function findClaimDivs(doc) {
    var buttons = doc.querySelectorAll(CLAIM_BUTTON_SELECTOR);
    var divs = [];
    var i;
    var div;
    for (i = 0; i < buttons.length; i += 1) {
      div = buttons[i].closest(CLAIM_DIV_SELECTOR);
      if (div && divs.indexOf(div) === -1) {
        divs.push(div);
      }
    }
    return divs;
  }

  function hideClaimDiv(div) {
    if (div.hasAttribute("hidden")) {
      return false;
    }
    div.setAttribute("hidden", "");
    return true;
  }

  function sync() {
    var divs = findClaimDivs(document);
    var i;
    for (i = 0; i < divs.length; i += 1) {
      hideClaimDiv(divs[i]);
    }
  }

  function runChecks() {
    var hidden = false;
    var claimDiv = {
      hasAttribute: function (name) {
        return name === "hidden" && hidden;
      },
      setAttribute: function (name) {
        if (name === "hidden") {
          hidden = true;
        }
      },
    };
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
    var fullDoc = {
      querySelectorAll: function (selector) {
        return selector === CLAIM_BUTTON_SELECTOR ? [claimButton, claimButton] : [];
      },
    };
    var bareDoc = {
      querySelectorAll: function (selector) {
        return selector === CLAIM_BUTTON_SELECTOR ? [bareButton] : [];
      },
    };
    var emptyDoc = {
      querySelectorAll: function () {
        return [];
      },
    };
    var cases = [
      [findClaimDivs(fullDoc).length, 1],
      [findClaimDivs(bareDoc).length, 0],
      [findClaimDivs(emptyDoc).length, 0],
      [hideClaimDiv(claimDiv), true],
      [claimDiv.hasAttribute("hidden"), true],
      [hideClaimDiv(claimDiv), false],
      [findClaimDivs(fullDoc).length, 1],
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
  });
  window.addEventListener("popstate", sync);
  sync();
})();
