// ==UserScript==
// @name         Arena agent hide composer
// @namespace    https://github.com/nemoe7/clankers
// @version      1.0.0
// @description  On /agent/*, hide the composer shell while Stop generating is present
// @author       nemoe7
// @license      MIT
// @match        https://arena.ai/*
// @match        https://www.arena.ai/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  var SHELL_SELECTOR = "div.flex.w-full.flex-col.items-start.justify-center.p-2";
  var EDITOR_SELECTOR = "div.editor-content, div.tiptap.ProseMirror";
  var HIDE_MARK = "data-clankers-hidden";

  function parseArenaUrl(urlString) {
    var url;
    try {
      url = new URL(urlString);
    } catch (err) {
      return null;
    }
    var host = url.hostname.replace(/^www\./, "");
    if (host !== "arena.ai") {
      return null;
    }
    return url;
  }

  function isSessionUrl(urlString) {
    var url = parseArenaUrl(urlString);
    return Boolean(url) && url.pathname.indexOf("/agent/") === 0 && url.pathname.length > 7;
  }

  function isStopGeneratingLabel(value) {
    return String(value || "").trim().toLowerCase() === "stop generating";
  }

  function shouldHideComposer(session, stopGenerating) {
    return Boolean(session) && Boolean(stopGenerating);
  }

  function runChecks() {
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

  function hasStopGenerating(doc) {
    var buttons = doc.querySelectorAll("button[aria-label]");
    var i;
    var label;
    for (i = 0; i < buttons.length; i += 1) {
      label = buttons[i].getAttribute("aria-label");
      if (isStopGeneratingLabel(label)) {
        return true;
      }
    }
    return false;
  }

  function findComposerShell(doc) {
    var nodes = doc.querySelectorAll(SHELL_SELECTOR);
    var i;
    var node;
    for (i = 0; i < nodes.length; i += 1) {
      node = nodes[i];
      if (node.querySelector(EDITOR_SELECTOR)) {
        return node;
      }
    }
    return null;
  }

  function hideShell(shell) {
    if (!shell.hasAttribute("hidden")) {
      shell.setAttribute("hidden", "");
    }
    if (!shell.hasAttribute(HIDE_MARK)) {
      shell.setAttribute(HIDE_MARK, "");
    }
  }

  function showShell(shell) {
    if (!shell.hasAttribute(HIDE_MARK)) {
      return;
    }
    shell.removeAttribute("hidden");
    shell.removeAttribute(HIDE_MARK);
  }

  function sync() {
    var session = isSessionUrl(location.href);
    var shell = findComposerShell(document);
    if (!shell) {
      return;
    }
    if (shouldHideComposer(session, hasStopGenerating(document))) {
      hideShell(shell);
      return;
    }
    showShell(shell);
  }

  var observer = new MutationObserver(sync);
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["aria-label"],
  });
  window.addEventListener("popstate", sync);
  sync();
})();
