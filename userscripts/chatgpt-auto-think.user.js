// ==UserScript==
// @name         ChatGPT Auto Think
// @namespace    https://github.com/nemoe7/clankers
// @version      1.0.0
// @description  On chatgpt.com, click the Think pill every second while unpressed
// @author       nemoe7
// @license      MIT
// @match        https://chatgpt.com/*
// @updateURL    https://gist.githubusercontent.com/nemoe7/a11743bbe3fdddfa3f483a979d5d1f09/raw/chatgpt-auto-think.user.js
// @downloadURL  https://gist.githubusercontent.com/nemoe7/a11743bbe3fdddfa3f483a979d5d1f09/raw/chatgpt-auto-think.user.js
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

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

  function runChecks() {
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
    console.log("ok " + cases.length);
  }

  if (typeof document === "undefined") {
    runChecks();
    return;
  }

  pressThink(document);
  setInterval(function () {
    pressThink(document);
  }, PRESS_INTERVAL_MS);
})();
