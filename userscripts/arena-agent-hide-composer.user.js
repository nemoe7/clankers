// ==UserScript==
// @name         Arena agent hide composer
// @namespace    https://github.com/nemoe7/clankers
// @version      1.3.0
// @description  On /agent/*, hide the editor while generating and lock the 24px spacer
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
  var EDITOR_CONTENT_SELECTOR = "div.editor-content";
  var HIDE_MARK = "data-clankers-hidden";
  var SPACER_SELECTOR = 'div.shrink-0[style*="height: 24px"]';
  var SPACER_HEIGHT = "24px";
  var fixedSpacers = new WeakSet();

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

  function isSpacerElement(spacer) {
    return (
      String(spacer.tagName || "").toLowerCase() === "div" &&
      spacer.classList.contains("shrink-0") &&
      !String(spacer.textContent || "").trim()
    );
  }

  function hasSpacerHeight(styleText) {
    return /(?:^|;)\s*height\s*:\s*24px\s*(?:!important\s*)?(?:;|$)/i.test(
      String(styleText || ""),
    );
  }

  function lockSpacerHeight(spacer) {
    fixedSpacers.add(spacer);
    if (
      spacer.style.getPropertyValue("height") === SPACER_HEIGHT &&
      spacer.style.getPropertyPriority("height") === "important"
    ) {
      return false;
    }
    spacer.style.setProperty("height", SPACER_HEIGHT, "important");
    return true;
  }

  function enforceSpacerHeight(doc, mutations) {
    var changes = mutations && typeof mutations.length === "number" ? mutations : null;
    var scan = !changes || changes.length === 0;
    var i;
    var change;
    if (changes) {
      for (i = 0; i < changes.length; i += 1) {
        change = changes[i];
        if (change.type === "attributes" && change.attributeName === "style") {
          if (
            fixedSpacers.has(change.target) ||
            (isSpacerElement(change.target) && hasSpacerHeight(change.oldValue))
          ) {
            lockSpacerHeight(change.target);
          }
        } else {
          scan = true;
        }
      }
    }
    if (!scan) {
      return;
    }
    var spacers = doc.querySelectorAll(SPACER_SELECTOR);
    for (i = 0; i < spacers.length; i += 1) {
      if (
        fixedSpacers.has(spacers[i]) ||
        (isSpacerElement(spacers[i]) && hasSpacerHeight(spacers[i].getAttribute("style")))
      ) {
        lockSpacerHeight(spacers[i]);
      }
    }
  }

  function runChecks() {
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
    console.log("ok " + cases.length);
  }

  if (typeof document === "undefined") {
    runChecks();
    return;
  }

  function findStopGeneratingButton(doc) {
    var buttons = doc.querySelectorAll("button[aria-label]");
    var i;
    var button;
    for (i = 0; i < buttons.length; i += 1) {
      button = buttons[i];
      if (isStopGeneratingLabel(button.getAttribute("aria-label"))) {
        return button;
      }
    }
    return null;
  }

  function findEditorContent(doc, stopButton) {
    var root = doc;
    var shell;
    if (stopButton) {
      shell = stopButton.closest(SHELL_SELECTOR);
      if (shell) {
        root = shell;
      }
    }
    return root.querySelector(EDITOR_CONTENT_SELECTOR);
  }

  function hideEditor(editor) {
    editor.setAttribute("hidden", "");
    editor.classList.add("hidden");
    editor.style.setProperty("display", "none", "important");
    editor.setAttribute(HIDE_MARK, "");
  }

  function showEditor(editor) {
    if (!editor.hasAttribute(HIDE_MARK)) {
      return;
    }
    editor.removeAttribute("hidden");
    editor.classList.remove("hidden");
    editor.style.removeProperty("display");
    editor.removeAttribute(HIDE_MARK);
  }

  function sync() {
    var session = isSessionUrl(location.href);
    var stopButton = findStopGeneratingButton(document);
    var editor = findEditorContent(document, stopButton);
    if (!editor) {
      return;
    }
    if (shouldHideComposer(session, Boolean(stopButton))) {
      hideEditor(editor);
      return;
    }
    showEditor(editor);
  }

  function enforceCurrentSpacerHeight(mutations) {
    if (isSessionUrl(location.href)) {
      enforceSpacerHeight(document, mutations);
    }
  }

  function handleMutations(mutations) {
    enforceCurrentSpacerHeight(mutations);
    var i;
    for (i = 0; i < mutations.length; i += 1) {
      if (mutations[i].type !== "attributes" || mutations[i].attributeName !== "style") {
        sync();
        return;
      }
    }
  }

  var observer = new MutationObserver(handleMutations);
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["aria-label", "style"],
    attributeOldValue: true,
  });
  window.addEventListener("popstate", function () {
    enforceCurrentSpacerHeight();
    sync();
  });
  enforceCurrentSpacerHeight();
  sync();
})();
