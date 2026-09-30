// ==UserScript==
// @name         Clankers Arena
// @namespace    https://github.com/nemoe7/clankers
// @version      1.1.7
// @description  Prompt fill, Steering preview, composer hiding, transcript auto-scroll, and a repository tab title with saved feature switches
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

  function runFeature(key, label, run, onChange) {
    if (typeof document === "undefined") {
      run();
      return;
    }
    var enabled = GM_getValue(key, true) !== false;
    var menuId;
    var stop = null;

    function toggle() {
      var next = GM_getValue(key, true) === false;
      GM_setValue(key, next);
      if (stop) stop();
      stop = next ? run() : null;
      GM_unregisterMenuCommand(menuId);
      showMenu(next);
      if (typeof onChange === "function") onChange();
    }

    function showMenu(value) {
      menuId = GM_registerMenuCommand(
        label + ": " + (value ? "ON" : "OFF") + " — toggle",
        toggle,
      );
    }

    showMenu(enabled);
    if (enabled) {
      stop = run();
    }
    return {
      isOn: function () {
        return stop !== null;
      },
      toggle: toggle,
    };
  }

  function isStopGeneratingLabel(value) {
    return String(value || "").trim().toLowerCase() === "stop generating";
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
    return function () {
      observer.disconnect();
      window.removeEventListener("popstate", sync);
    };
  });

  runFeature("open-steering", "Open Steering", function () {

    var BAR_SELECTOR =
      "div.relative.z-10.w-full.md\\:absolute.md\\:left-0.md\\:top-full";
    // Agents drift on the process name, so the row is found by its words, not its shape.
    var STEERING_LABEL_RE = /steering|preview/i;
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

    function isSteeringLabel(text) {
      return STEERING_LABEL_RE.test(String(text || ""));
    }

    function steeringSlugFromLabel(text) {
      var trimmed = String(text || "").trim();
      var match = STEERING_LABEL_RE.exec(trimmed);
      if (!match) {
        return null;
      }
      var head = trimmed.slice(0, match.index).replace(/[\s\-:|]+$/, "");
      var words = head.split(/[\s\-:|]+/).filter(function (word) {
        return Boolean(word);
      });
      return words.length ? words[words.length - 1] : null;
    }

    function isSteeringPort(text) {
      return String(text || "").trim() === ":8000";
    }

    function buttonMatchesSteering(label, port, expectedSlug) {
      if (!isSteeringLabel(label) || !isSteeringPort(port)) {
        return false;
      }
      var slug = steeringSlugFromLabel(label);
      if (expectedSlug && slug && slug.toLowerCase() !== expectedSlug.toLowerCase()) {
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

    function steeringRowText(rows, expectedSlug) {
      var buttons = rows.map(function (row) {
        return {
          textContent: row[0] + " " + row[1],
          querySelectorAll: function (selector) {
            return selector === "span" ? [{ textContent: row[0] }, { textContent: row[1] }] : [];
          },
        };
      });
      var doc = {
        querySelectorAll: function () {
          return buttons;
        },
      };
      var found = findSteeringButton(doc, expectedSlug);
      return found ? found.textContent : null;
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
        [steeringSlugFromLabel("clankers - preview"), "clankers"],
        [steeringSlugFromLabel("clankers preview"), "clankers"],
        [steeringSlugFromLabel("arena-preview-steering"), "arena"],
        [steeringSlugFromLabel("Steering"), null],
        [steeringSlugFromLabel("daedalus - Website"), null],
        [isSteeringLabel("CLANKERS - PREVIEW"), true],
        [isSteeringLabel("daedalus - Website"), false],
        [buttonMatchesSteering("CLANKERS - steering", ":8000", "clankers"), true],
        [buttonMatchesSteering("Steering", ":8000", "clankers"), true],
        [buttonMatchesSteering("daedalus - Steering", ":8000", "clankers"), false],
        [buttonMatchesSteering("clankers - STEERING", ":8001", "CLANKERS"), false],
        [buttonMatchesSteering("daedalus - Preview", ":8000", null), true],
        [buttonMatchesSteering("daedalus - Website", ":8000", null), false],
        [isSteeringPort(":8000"), true],
        [isSteeringPort("8000"), false],
        [steeringRowText([["Website", ":3000"], ["daedalus - Steering", ":8000"]], "clankers"),
          "daedalus - Steering :8000"],
        [steeringRowText([["clankers - Steering", ":8000"], ["daedalus - preview", ":8000"]],
          "clankers"), "clankers - Steering :8000"],
        [steeringRowText([["Website", ":3000"], ["arena-preview-steering", ":8000"]], "clankers"),
          "arena-preview-steering :8000"],
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
      var port = null;
      var i;
      var text;
      for (i = 0; i < spans.length; i += 1) {
        text = spans[i].textContent || "";
        if (!port && isSteeringPort(text)) {
          port = ":8000";
        }
      }
      var label = String(button.textContent || "").trim();
      if (!port) {
        return null;
      }
      return { label: label, slug: steeringSlugFromLabel(label), port: port };
    }

    function findSteeringButton(doc, expectedSlug) {
      var buttons = doc.querySelectorAll('button[type="button"]');
      var fallback = null;
      var i;
      var parsed;
      for (i = 0; i < buttons.length; i += 1) {
        parsed = parseSteeringButton(buttons[i]);
        if (!parsed || !buttonMatchesSteering(parsed.label, parsed.port, null)) {
          continue;
        }
        // The row that names this repository wins; a row that names nothing, or something else,
        // opens only when no better row exists. Agents rename the process, and the preview still
        // has to open.
        if (!expectedSlug || (parsed.slug && parsed.slug.toLowerCase() === expectedSlug.toLowerCase())) {
          return buttons[i];
        }
        if (!fallback) {
          fallback = buttons[i];
        }
      }
      return fallback;
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
    return function () {
      observer.disconnect();
      window.removeEventListener("popstate", sync);
      clearClickTimer();
    };
  });

  var AUTO_TOGGLE_MARK = "data-clankers-autoscroll-toggle";
  var AUTO_TOGGLE_CLASS =
    "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ring-offset-2 focus-visible:ring-offset-surface-primary disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 h-8 w-8 active:bg-interactive-cta-active rounded-[4px] font-normal touch-hitbox border-border-medium border text-text-primary";

  function hasToggleClass(classes, name) {
    return classes.split(" ").indexOf(name) !== -1;
  }

  // Each state has its own hover fill, so the on state stays visible under the pointer.
  function autoToggleClasses(on) {
    return (
      AUTO_TOGGLE_CLASS +
      (on
        ? " bg-surface-raised hover:bg-interactive-cta-active"
        : " bg-transparent hover:bg-surface-raised")
    );
  }

  var autoToggleButton = null;

  function setToggleButtonPressed() {
    if (!autoToggleButton) return;
    autoToggleButton.className = autoToggleClasses(autoScroll.isOn());
    autoToggleButton.setAttribute("aria-pressed", autoScroll.isOn() ? "true" : "false");
  }

  var autoScroll = runFeature("auto-scroll", "Transcript auto-scroll", function () {
    var scroller = null;
    var content = null;
    var frame = null;
    var route = null;
    var resize = null;

    if (typeof document === "undefined") return;

    function schedule() {
      if (frame !== null || !scroller) return;
      frame = requestAnimationFrame(function () {
        frame = null;
        if (!scroller || !scroller.isConnected || route !== location.pathname) return;
        if (!findStopGeneratingButton(document)) return;
        scroller.scrollTop = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
      });
    }

    function detach() {
      if (scroller) scroller.removeEventListener("scroll", schedule);
      if (resize) resize.disconnect();
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      scroller = content = null;
    }

    function sync() {
      var message = location.pathname.indexOf("/agent/") === 0
        ? document.querySelector('[data-agent-transcript-message="true"]') : null;
      var next = message && message.closest('[role="log"]');
      if (next && !/^(auto|scroll)$/.test(getComputedStyle(next).overflowY)) next = null;
      if (next !== scroller || route !== location.pathname) {
        detach();
        route = location.pathname;
        scroller = next;
        if (scroller) {
          scroller.addEventListener("scroll", schedule, { passive: true });
          resize = new ResizeObserver(schedule);
          resize.observe(scroller);
        }
      }
      var nextContent = message;
      while (nextContent && nextContent.parentElement !== scroller) nextContent = nextContent.parentElement;
      if (scroller && nextContent !== content) {
        if (content) resize.unobserve(content);
        content = nextContent;
        if (content) resize.observe(content);
      }
      schedule();
    }

    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
    window.addEventListener("popstate", sync);
    sync();
    return function () {
      observer.disconnect();
      window.removeEventListener("popstate", sync);
      detach();
    };
  }, setToggleButtonPressed);

  (function () {
    function runChecks() {
      var on = autoToggleClasses(true);
      var off = autoToggleClasses(false);
      var cases = [
        [hasToggleClass(on, "bg-surface-raised"), true],
        [hasToggleClass(on, "bg-transparent"), false],
        [hasToggleClass(off, "bg-transparent"), true],
        [hasToggleClass(off, "bg-surface-raised"), false],
        [hasToggleClass(on, "hover:bg-interactive-cta-active"), true],
        [hasToggleClass(off, "hover:bg-surface-raised"), true],
        [hasToggleClass(AUTO_TOGGLE_CLASS, "h-8"), true],
        [hasToggleClass(AUTO_TOGGLE_CLASS, "w-8"), true],
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

    function createButton() {
      var button = document.createElement("button");
      button.type = "button";
      button.setAttribute(AUTO_TOGGLE_MARK, "true");
      button.setAttribute("aria-label", "Toggle transcript autoscroll");
      button.setAttribute("title", "Toggle transcript autoscroll");
      autoToggleButton = button;
      setToggleButtonPressed();
      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("width", "16");
      svg.setAttribute("height", "16");
      svg.setAttribute("viewBox", "0 0 24 24");
      svg.setAttribute("fill", "none");
      svg.setAttribute("stroke-width", "1.5");
      svg.setAttribute("color", "currentColor");
      var paths = ["M12 4v12", "M6 10l6 6 6-6", "M5 20h14"];
      var i;
      for (i = 0; i < paths.length; i += 1) {
        var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", paths[i]);
        path.setAttribute("stroke", "currentColor");
        path.setAttribute("stroke-linecap", "round");
        path.setAttribute("stroke-linejoin", "round");
        svg.appendChild(path);
      }
      button.appendChild(svg);
      button.addEventListener("click", function () {
        autoScroll.toggle();
      });
      return button;
    }

    function ensureButton() {
      var stopButton = findStopGeneratingButton(document);
      var row = stopButton && stopButton.parentElement;
      if (!row || row.querySelector("[" + AUTO_TOGGLE_MARK + "]")) return;
      row.insertBefore(createButton(), stopButton);
    }

    var observer = new MutationObserver(ensureButton);
    observer.observe(document.documentElement, { childList: true, subtree: true });
    ensureButton();
  })();

  runFeature("hide-composer", "Hide composer", function () {

    var SHELL_SELECTOR = "div.flex.w-full.flex-col.items-start.justify-center.p-2";
    var EDITOR_CONTENT_SELECTOR = "div.editor-content";
    var HIDE_MARK = "data-clankers-hidden";
    var SPACER_SELECTOR = 'div.shrink-0[style*="height: 24px"]';
    var SPACER_HEIGHT = "24px";
    var fixedSpacers = new WeakSet();
    var spacerStyles = new Map();
    var editorStates = new Map();

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
      if (!spacerStyles.has(spacer)) spacerStyles.set(spacer, [spacer.style.getPropertyValue("height"), spacer.style.getPropertyPriority("height")]);
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
      if (!editorStates.has(editor)) editorStates.set(editor, { hidden: editor.getAttribute("hidden"), classHidden: editor.classList.contains("hidden"), display: editor.style.getPropertyValue("display"), priority: editor.style.getPropertyPriority("display") });
      editor.setAttribute("hidden", "");
      editor.classList.add("hidden");
      editor.style.setProperty("display", "none", "important");
      editor.setAttribute(HIDE_MARK, "");
    }

    function showEditor(editor) {
      if (!editor.hasAttribute(HIDE_MARK)) {
        return;
      }
      var prior = editorStates.get(editor);
      if (!prior) return;
      if (editor.getAttribute("hidden") === "") {
        if (prior.hidden === null) editor.removeAttribute("hidden");
        else editor.setAttribute("hidden", prior.hidden);
      }
      if (!prior.classHidden) editor.classList.remove("hidden");
      if (editor.style.getPropertyValue("display") === "none" && editor.style.getPropertyPriority("display") === "important") {
        if (prior.display) editor.style.setProperty("display", prior.display, prior.priority);
        else editor.style.removeProperty("display");
      }
      editor.removeAttribute(HIDE_MARK);
      editorStates.delete(editor);
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
    function onRoute() {
      enforceCurrentSpacerHeight();
      sync();
    }
    window.addEventListener("popstate", onRoute);
    enforceCurrentSpacerHeight();
    sync();
    return function () {
      observer.disconnect();
      window.removeEventListener("popstate", onRoute);
      editorStates.forEach(function (_, editor) { showEditor(editor); });
      spacerStyles.forEach(function (prior, spacer) {
        if (spacer.style.getPropertyValue("height") === SPACER_HEIGHT && spacer.style.getPropertyPriority("height") === "important") {
          if (prior[0]) spacer.style.setProperty("height", prior[0], prior[1]);
          else spacer.style.removeProperty("height");
        }
      });
      spacerStyles.clear();
    };
  });

  runFeature("tab-title", "Tab title", function () {

    var REPO_LINK_SELECTOR = 'a[aria-label^="Open "][aria-label$=" on GitHub"]';
    var MESSAGE_SELECTOR = "[data-agent-transcript-message]";
    var LIVE_ICON_SELECTOR = "svg.animate-pulse";
    var TITLE_PREFIX = "Arena | ";
    // The live status row names the action; the emoji carries it in the title.
    var ACTION_EMOJI = [
      ["running", "\uD83D\uDDA5\uFE0F"],
      ["read", "\uD83D\uDCD6"],
      ["edit", "\u270F\uFE0F"],
      ["search", "\uD83D\uDD0D"],
      ["think", "\uD83D\uDCAD"],
      ["thought", "\uD83D\uDCAD"],
      ["wait", "\uD83D\uDCA4"],
    ];
    var ACTION_FALLBACK = "\u2699\uFE0F";
    var WAITING_EMOJI = "\uD83D\uDCA4";
    // Any preview command that ends in poll: full paths, the extensionless script, the .py form.
    var POLL_RE = /preview[\s\S]{0,60}poll/;

    function repoFromLink(link) {
      if (!link) {
        return null;
      }
      var href = String(link.getAttribute("href") || "");
      var match = /github\.com\/[^\/]+\/([^\/?#]+)/.exec(href);
      if (match) {
        return match[1];
      }
      var label = String(link.getAttribute("aria-label") || "")
        .replace(/^Open /, "")
        .replace(/ on GitHub$/, "");
      var parts = label.split("/");
      var name = parts[parts.length - 1].trim();
      return name || null;
    }

    // The last agent message carries the live action in its pulsing status row.
    function liveRow(doc) {
      var messages = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(MESSAGE_SELECTOR) : [];
      var last = messages.length ? messages[messages.length - 1] : null;
      var icons = last && typeof last.querySelectorAll === "function" ? last.querySelectorAll(LIVE_ICON_SELECTOR) : [];
      var icon = icons.length ? icons[icons.length - 1] : null;
      var button = icon && typeof icon.closest === "function" ? icon.closest("button") : null;
      return button && button.parentElement ? button.parentElement : null;
    }

    function liveLabel(row) {
      var button = row && typeof row.querySelector === "function" ? row.querySelector("button") : null;
      var label = button ? button.querySelector("p") : null;
      var text = label ? String(label.textContent || "").replace(/\s+/g, " ").trim() : "";
      return text || null;
    }

    function actionEmoji(label) {
      if (!label) {
        return null;
      }
      var text = label.toLowerCase();
      var i;
      for (i = 0; i < ACTION_EMOJI.length; i += 1) {
        if (text.indexOf(ACTION_EMOJI[i][0]) !== -1) {
          return ACTION_EMOJI[i][1];
        }
      }
      return ACTION_FALLBACK;
    }

    // A poll command means the agent waits on the owner, whatever the row label says.
    // Only the command panel counts: command output often mentions poll in prose.
    function rowCommand(row) {
      if (!row || typeof row.querySelector !== "function") {
        return "";
      }
      var panel = row.querySelector("pre");
      return panel ? String(panel.textContent || "") : "";
    }

    function emojiForRow(row) {
      if (!row) {
        return null;
      }
      if (POLL_RE.test(rowCommand(row).toLowerCase())) {
        return WAITING_EMOJI;
      }
      return actionEmoji(liveLabel(row));
    }

    function desiredTitle(doc) {
      var name = repoFromLink(doc.querySelector(REPO_LINK_SELECTOR));
      if (!name) {
        return null;
      }
      var emoji = emojiForRow(liveRow(doc));
      return emoji ? TITLE_PREFIX + name + " " + emoji : TITLE_PREFIX + name;
    }

    var appliedTitle = null;
    var priorTitle = null;

    function syncTitle(doc) {
      var desired = desiredTitle(doc);
      if (desired) {
        if (doc.title === desired) {
          return false;
        }
        appliedTitle = desired;
        doc.title = desired;
        return true;
      }
      if (appliedTitle && doc.title === appliedTitle) {
        doc.title = priorTitle;
        appliedTitle = null;
        return true;
      }
      return false;
    }

    function runChecks() {
      function link(href, label) {
        return {
          getAttribute: function (name) {
            if (name === "href") return href;
            if (name === "aria-label") return label;
            return null;
          },
        };
      }
      function docWith(element, title) {
        return {
          title: title,
          querySelector: function (selector) {
            return selector === REPO_LINK_SELECTOR ? element : null;
          },
        };
      }
      function liveMessage(text, command) {
        var label = { textContent: text };
        var button = {
          querySelector: function (selector) {
            return selector === "p" ? label : null;
          },
        };
        var panel = { textContent: command || "" };
        var row = {
          querySelector: function (selector) {
            if (selector === "button") return button;
            if (selector === "pre") return command === null ? null : panel;
            return null;
          },
        };
        button.parentElement = row;
        var icon = {
          closest: function (selector) {
            return selector === "button" ? button : null;
          },
        };
        return {
          row: row,
          querySelectorAll: function (selector) {
            return selector === LIVE_ICON_SELECTOR ? [icon] : [];
          },
        };
      }
      function actionDoc(element, message) {
        return {
          title: "ChatGPT",
          querySelectorAll: function (selector) {
            return selector === MESSAGE_SELECTOR && message ? [message] : [];
          },
          querySelector: function (selector) {
            return selector === REPO_LINK_SELECTOR ? element : null;
          },
        };
      }
      var repoLink = link("https://github.com/nemoe7/clankers", "Open nemoe7/clankers on GitHub");
      var labelOnly = link(null, "Open nemoe7/clankers on GitHub");
      var emptyLink = link("", "");
      var setDoc = docWith(repoLink, "ChatGPT");
      var keepDoc = docWith(null, "ChatGPT");
      var goneDoc = docWith(null, TITLE_PREFIX + "clankers");
      var busyMessage = liveMessage("  running\n Bash  ", "$ npm test");
      var pollMessage = liveMessage("running Bash", "$ arena-preview poll");
      var pathMessage = liveMessage("running Bash", "$ /home/user/clankers/.agents/skills/arena-preview-steering/scripts/arena-preview poll");
      var pyMessage = liveMessage("running Bash", "$ python skills/refs/arena-preview-steering/scripts/preview.py poll");
      var chainMessage = liveMessage("running Bash", "$ git fetch origin && arena-preview poll");
      var readMessage = liveMessage("running Bash", "Read the inbox");
      readMessage.row.textContent = "stderr End the turn with `poll` to wait for more work.";
      var busyDoc = actionDoc(repoLink, busyMessage);
      var idleDoc = actionDoc(repoLink, null);
      priorTitle = "ChatGPT";
      var cases = [
        [repoFromLink(repoLink), "clankers"],
        [repoFromLink(labelOnly), "clankers"],
        [repoFromLink(emptyLink), null],
        [repoFromLink(null), null],
        [desiredTitle(setDoc), TITLE_PREFIX + "clankers"],
        [desiredTitle(keepDoc), null],
        [syncTitle(setDoc), true],
        [setDoc.title, TITLE_PREFIX + "clankers"],
        [syncTitle(setDoc), false],
        [syncTitle(keepDoc), false],
        [keepDoc.title, "ChatGPT"],
        [syncTitle(goneDoc), true],
        [goneDoc.title, "ChatGPT"],
        [syncTitle(goneDoc), false],
        [liveLabel(busyMessage.row), "running Bash"],
        [liveLabel(null), null],
        [emojiForRow(busyMessage.row), "\uD83D\uDDA5\uFE0F"],
        [emojiForRow(pollMessage.row), "\uD83D\uDCA4"],
        [emojiForRow(pathMessage.row), "\uD83D\uDCA4"],
        [emojiForRow(pyMessage.row), "\uD83D\uDCA4"],
        [emojiForRow(chainMessage.row), "\uD83D\uDCA4"],
        [emojiForRow(readMessage.row), "\uD83D\uDDA5\uFE0F"],
        [emojiForRow(null), null],
        [actionEmoji("running Bash"), "\uD83D\uDDA5\uFE0F"],
        [actionEmoji("Reading files"), "\uD83D\uDCD6"],
        [actionEmoji("Editing"), "\u270F\uFE0F"],
        [actionEmoji("Searching the web"), "\uD83D\uDD0D"],
        [actionEmoji("Thought for 2 seconds"), "\uD83D\uDCAD"],
        [actionEmoji("Waiting"), "\uD83D\uDCA4"],
        [actionEmoji("Doing something"), "\u2699\uFE0F"],
        [actionEmoji(null), null],
        [desiredTitle(busyDoc), TITLE_PREFIX + "clankers \uD83D\uDDA5\uFE0F"],
        [syncTitle(busyDoc), true],
        [busyDoc.title, TITLE_PREFIX + "clankers \uD83D\uDDA5\uFE0F"],
        [syncTitle(idleDoc), true],
        [idleDoc.title, TITLE_PREFIX + "clankers"],
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

    // Arena rewrites the tab title on navigation, so the observer re-applies it.
    priorTitle = document.title;
    syncTitle(document);
    var observer = new MutationObserver(function () {
      syncTitle(document);
    });
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    function onRoute() {
      syncTitle(document);
    }
    window.addEventListener("popstate", onRoute);
    return function () {
      observer.disconnect();
      window.removeEventListener("popstate", onRoute);
      if (appliedTitle && document.title === appliedTitle) {
        document.title = priorTitle;
      }
      appliedTitle = null;
    };
  });

})();
