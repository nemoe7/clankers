// ==UserScript==
// @name         Clankers Arena
// @namespace    https://github.com/nemoe7/clankers
// @version      1.0.0
// @description  Prompt fill, Steering preview, and composer hiding with saved feature switches
// @author       nemoe7
// @license      MIT
// @match        https://arena.ai/*
// @match        https://www.arena.ai/*
// @updateURL    https://raw.githubusercontent.com/nemoe7/clankers/main/userscripts/arena.user.js
// @downloadURL  https://raw.githubusercontent.com/nemoe7/clankers/main/userscripts/arena.user.js
// @run-at       document-idle
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM_unregisterMenuCommand
// ==/UserScript==

(function () {
  "use strict";

  function runFeature(key, label, run) {
    if (typeof document === "undefined") {
      run();
      return;
    }
    var enabled = GM_getValue(key, true) !== false;
    var menuId;

    function showMenu(value) {
      menuId = GM_registerMenuCommand(
        label + ": " + (value ? "ON" : "OFF") + " — toggle; reload to apply",
        function () {
          var next = GM_getValue(key, true) === false;
          GM_setValue(key, next);
          GM_unregisterMenuCommand(menuId);
          showMenu(next);
        },
      );
    }

    showMenu(enabled);
    if (enabled) {
      run();
    }
  }

  runFeature("prompt-fill", "Prompt fill", function () {

    var BAR_SELECTOR =
      "div.relative.z-10.w-full.md\\:absolute.md\\:left-0.md\\:top-full";
    var COMPOSER_SELECTOR = 'div.tiptap.ProseMirror[contenteditable="true"]';
    var TEMPLATE_RE = /^(\S+) read AGENTS\.md ARENA\.md$/;
    var SLUG_KEY = "clankers-arena-agent-slug";

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

    function isComposerUrl(urlString) {
      var url = parseArenaUrl(urlString);
      return Boolean(url) && url.pathname === "/agent";
    }

    function slugFromOwnerRepo(text) {
      var trimmed = String(text || "").trim();
      var slash = trimmed.indexOf("/");
      if (slash <= 0 || slash === trimmed.length - 1) {
        return null;
      }
      var owner = trimmed.slice(0, slash);
      var repo = trimmed.slice(slash + 1);
      if (!owner || !repo || repo.indexOf("/") !== -1 || /\s/.test(trimmed)) {
        return null;
      }
      return repo;
    }

    function promptForSlug(slug) {
      return slug + " read AGENTS.md ARENA.md";
    }

    function shouldWrite(current, slug, lastSlug) {
      var desired = promptForSlug(slug);
      var text = String(current || "").trim();
      if (text === desired) {
        return false;
      }
      if (lastSlug === null) {
        return text === "" || TEMPLATE_RE.test(text);
      }
      return slug !== lastSlug;
    }

    function rememberSlug(slug) {
      try {
        sessionStorage.setItem(SLUG_KEY, slug);
      } catch (err) {
        return;
      }
    }

    function runChecks() {
      var cases = [
        [isComposerUrl("https://arena.ai/agent"), true],
        [isComposerUrl("https://www.arena.ai/agent"), true],
        [isComposerUrl("https://arena.ai/agent?x=1"), true],
        [isComposerUrl("https://arena.ai/agent#x"), true],
        [isComposerUrl("https://arena.ai/agent/"), false],
        [isComposerUrl("https://arena.ai/agent/foo"), false],
        [isComposerUrl("https://other.example/agent"), false],
        [slugFromOwnerRepo("nemoe7/clankers"), "clankers"],
        [slugFromOwnerRepo("  org/repo  "), "repo"],
        [slugFromOwnerRepo("main"), null],
        [slugFromOwnerRepo("a/"), null],
        [slugFromOwnerRepo("/b"), null],
        [slugFromOwnerRepo("a/b/c"), null],
        [promptForSlug("clankers"), "clankers read AGENTS.md ARENA.md"],
        [shouldWrite("", "clankers", null), true],
        [shouldWrite("clankers read AGENTS.md ARENA.md", "clankers", null), false],
        [shouldWrite("draft", "clankers", null), false],
        [shouldWrite("clankers read AGENTS.md ARENA.md", "other", "clankers"), true],
        [shouldWrite("draft", "clankers", "clankers"), false],
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

    var lastSlug = null;

    function readSlug(doc) {
      var bar = doc.querySelector(BAR_SELECTOR);
      if (!bar) {
        return null;
      }
      if (!String(bar.textContent || "").trim()) {
        return null;
      }
      var spans = bar.querySelectorAll("span.truncate");
      var i;
      var slug;
      for (i = 0; i < spans.length; i += 1) {
        slug = slugFromOwnerRepo(spans[i].textContent || "");
        if (slug) {
          return slug;
        }
      }
      return null;
    }

    function setComposerText(el, text) {
      el.focus();
      var selection = window.getSelection();
      var range = document.createRange();
      range.selectNodeContents(el);
      selection.removeAllRanges();
      selection.addRange(range);
      var ok = document.execCommand("insertText", false, text);
      if (!ok || String(el.innerText || "").trim() !== text) {
        while (el.firstChild) {
          el.removeChild(el.firstChild);
        }
        var paragraph = document.createElement("p");
        paragraph.textContent = text;
        el.appendChild(paragraph);
        el.dispatchEvent(
          new InputEvent("input", {
            bubbles: true,
            cancelable: true,
            inputType: "insertText",
            data: text,
          }),
        );
      }
    }

    function sync() {
      if (!isComposerUrl(location.href)) {
        lastSlug = null;
        return;
      }
      var slug = readSlug(document);
      if (!slug) {
        return;
      }
      rememberSlug(slug);
      var composer = document.querySelector(COMPOSER_SELECTOR);
      if (!composer || composer.getAttribute("aria-disabled") === "true") {
        lastSlug = slug;
        return;
      }
      var current = composer.innerText || "";
      if (!shouldWrite(current, slug, lastSlug)) {
        lastSlug = slug;
        return;
      }
      setComposerText(composer, promptForSlug(slug));
      lastSlug = slug;
    }

    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    window.addEventListener("popstate", sync);
    sync();
  });

  runFeature("open-steering", "Open Steering", function () {

    var BAR_SELECTOR =
      "div.relative.z-10.w-full.md\\:absolute.md\\:left-0.md\\:top-full";
    var STEERING_LABEL_RE = /^(\S+) - Steering$/;
    var SLUG_KEY = "clankers-arena-agent-slug";
    var CLICK_DELAY_MS = 1000;

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

    function slugFromOwnerRepo(text) {
      var trimmed = String(text || "").trim();
      var slash = trimmed.indexOf("/");
      if (slash <= 0 || slash === trimmed.length - 1) {
        return null;
      }
      var owner = trimmed.slice(0, slash);
      var repo = trimmed.slice(slash + 1);
      if (!owner || !repo || repo.indexOf("/") !== -1 || /\s/.test(trimmed)) {
        return null;
      }
      return repo;
    }

    function steeringSlugFromLabel(text) {
      var match = STEERING_LABEL_RE.exec(String(text || "").trim());
      return match ? match[1] : null;
    }

    function isSteeringPort(text) {
      return String(text || "").trim() === ":8000";
    }

    function buttonMatchesSteering(label, port, expectedSlug) {
      var slug = steeringSlugFromLabel(label);
      if (!slug || !isSteeringPort(port)) {
        return false;
      }
      if (expectedSlug && slug !== expectedSlug) {
        return false;
      }
      return true;
    }

    function recalledSlug() {
      try {
        return sessionStorage.getItem(SLUG_KEY);
      } catch (err) {
        return null;
      }
    }

    function runChecks() {
      var cases = [
        [isSessionUrl("https://arena.ai/agent/foo"), true],
        [isSessionUrl("https://www.arena.ai/agent/foo/bar"), true],
        [isSessionUrl("https://arena.ai/agent/foo?x=1"), true],
        [isSessionUrl("https://arena.ai/agent"), false],
        [isSessionUrl("https://arena.ai/agent/"), false],
        [isSessionUrl("https://other.example/agent/foo"), false],
        [slugFromOwnerRepo("nemoe7/clankers"), "clankers"],
        [steeringSlugFromLabel("daedalus - Steering"), "daedalus"],
        [steeringSlugFromLabel("clankers - Steering"), "clankers"],
        [steeringSlugFromLabel("daedalus - Website"), null],
        [isSteeringPort(":8000"), true],
        [isSteeringPort("8000"), false],
        [buttonMatchesSteering("daedalus - Steering", ":8000", null), true],
        [buttonMatchesSteering("daedalus - Steering", ":8000", "daedalus"), true],
        [buttonMatchesSteering("daedalus - Steering", ":8000", "clankers"), false],
        [buttonMatchesSteering("daedalus - Steering", ":3000", null), false],
        [buttonMatchesSteering("Website", ":8000", null), false],
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
      console.log("ok " + cases.length);
    }

    if (typeof document === "undefined") {
      runChecks();
      return;
    }

    var clickedPath = null;
    var clickTimer = null;
    var pendingPath = null;

    function clearClickTimer() {
      if (clickTimer !== null) {
        clearTimeout(clickTimer);
        clickTimer = null;
      }
      pendingPath = null;
    }

    function fireClick(path) {
      clickTimer = null;
      pendingPath = null;
      if (!isSessionUrl(location.href) || location.pathname !== path) {
        return;
      }
      if (clickedPath === path) {
        return;
      }
      var slug = readSlug(document) || recalledSlug();
      var button = findSteeringButton(document, slug);
      if (!button) {
        return;
      }
      button.click();
      clickedPath = path;
    }

    function readSlug(doc) {
      var bar = doc.querySelector(BAR_SELECTOR);
      if (!bar) {
        return null;
      }
      if (!String(bar.textContent || "").trim()) {
        return null;
      }
      var spans = bar.querySelectorAll("span.truncate");
      var i;
      var slug;
      for (i = 0; i < spans.length; i += 1) {
        slug = slugFromOwnerRepo(spans[i].textContent || "");
        if (slug) {
          return slug;
        }
      }
      return null;
    }

    function parseSteeringButton(button) {
      var spans = button.querySelectorAll("span");
      var slug = null;
      var port = null;
      var i;
      var text;
      for (i = 0; i < spans.length; i += 1) {
        text = spans[i].textContent || "";
        if (!slug) {
          slug = steeringSlugFromLabel(text);
        }
        if (!port && isSteeringPort(text)) {
          port = ":8000";
        }
      }
      if (!slug || !port) {
        return null;
      }
      return { slug: slug, port: port };
    }

    function findSteeringButton(doc, expectedSlug) {
      var buttons = doc.querySelectorAll('button[type="button"]');
      var i;
      var button;
      var parsed;
      for (i = 0; i < buttons.length; i += 1) {
        button = buttons[i];
        parsed = parseSteeringButton(button);
        if (!parsed) {
          continue;
        }
        if (buttonMatchesSteering(parsed.slug + " - Steering", parsed.port, expectedSlug)) {
          return button;
        }
      }
      return null;
    }

    function sync() {
      if (!isSessionUrl(location.href)) {
        clickedPath = null;
        clearClickTimer();
        return;
      }
      if (clickedPath === location.pathname) {
        return;
      }
      var slug = readSlug(document) || recalledSlug();
      var button = findSteeringButton(document, slug);
      if (!button) {
        return;
      }
      if (pendingPath === location.pathname && clickTimer !== null) {
        return;
      }
      clearClickTimer();
      var path = location.pathname;
      pendingPath = path;
      clickTimer = setTimeout(function () {
        fireClick(path);
      }, CLICK_DELAY_MS);
    }

    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    window.addEventListener("popstate", sync);
    sync();
  });

  runFeature("hide-composer", "Hide composer", function () {

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
  });

})();
