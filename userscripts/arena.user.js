// ==UserScript==
// @name         Clankers Arena
// @namespace    https://github.com/nemoe7/clankers
// @version      1.1.23
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

  function runFeature(key, label, run, onChange, defaultOn) {
    if (typeof document === "undefined") {
      run();
      return;
    }
    var fallback = defaultOn !== false;
    var enabled = GM_getValue(key, fallback) !== false;
    var menuId;
    var stop = null;

    function toggle() {
      var next = GM_getValue(key, fallback) === false;
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

    if (exposeChecks("promptFill", {
      isComposerUrl: isComposerUrl,
      slugFromOwnerRepo: slugFromOwnerRepo,
      promptForSlug: promptForSlug,
      shouldWrite: shouldWrite,
    })) {
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
      var head = trimmed.slice(0, match.index);
      // A name needs a spaced separator before the term: `clankers - Steering` has one, while
      // `arena-preview-steering` is a single name and carries no separate slug.
      if (!/\s[-:|]?\s*$/.test(head)) {
        return null;
      }
      var words = head.replace(/[\s\-:|]+$/, "").split(/[\s\-:|]+/).filter(function (word) {
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

    if (exposeChecks("openSteering", {
      isSessionUrl: isSessionUrl,
      slugFromOwnerRepo: slugFromOwnerRepo,
      steeringSlugFromLabel: steeringSlugFromLabel,
      isSteeringLabel: isSteeringLabel,
      isSteeringPort: isSteeringPort,
      buttonMatchesSteering: buttonMatchesSteering,
      findSteeringButton: findSteeringButton,
      CLICK_DELAY_MS: CLICK_DELAY_MS,
    })) {
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

    // Rank a running row, best first: this project's name, then no name, then another project.
    // A Start row is a transcript card, and a click on one opens nothing, so it never counts.
    function steeringRank(label, slug, expectedSlug) {
      if (/^start\b/i.test(String(label || ""))) {
        return null;
      }
      if (expectedSlug && slug && slug.toLowerCase() === expectedSlug.toLowerCase()) {
        return 0;
      }
      return slug ? 2 : 1;
    }

    function findSteeringButton(doc, expectedSlug) {
      var buttons = doc.querySelectorAll('button[type="button"]');
      var best = null;
      var bestRank = 3;
      var i;
      var parsed;
      var rank;
      for (i = 0; i < buttons.length; i += 1) {
        parsed = parseSteeringButton(buttons[i]);
        if (!parsed || !buttonMatchesSteering(parsed.label, parsed.port, null)) {
          continue;
        }
        rank = steeringRank(parsed.label, parsed.slug, expectedSlug);
        if (rank === null) {
          continue;
        }
        // Equal ranks keep the newest row, which is the live one.
        if (rank <= bestRank) {
          best = buttons[i];
          bestRank = rank;
        }
      }
      return best;
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
    if (exposeChecks("autoScrollToggle", {
      AUTO_TOGGLE_CLASS: AUTO_TOGGLE_CLASS,
      autoToggleClasses: autoToggleClasses,
    })) {
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

  runFeature("transcript-trim", "Transcript trim", function () {
    var KEEP_KEY = "clankers-arena-trim-keep";
    var DEFAULT_ROWS = 50;
    var MIN_ROWS = 20;
    var LOG_SELECTOR = '[role="log"]';
    var MESSAGE_SELECTOR = '[data-agent-transcript-message="true"]';
    var ROW_BOX_SELECTOR = "div.flex.flex-col.gap-2";
    var ACTION_SELECTOR = ":scope > div > div > div.mt-3.flex.flex-col.gap-3";
    var LIVE_ICON_SELECTOR = "svg.animate-pulse";
    var SETTLE_MS = 1200;

    // The plan keeps one global tail of transcript rows; old saved plans keep their row value.
    function normalizePlan(value) {
      var text = String(value == null ? "" : value).trim();
      var legacy = /^(\d+)\s*,\s*(\d+)$/.exec(text);
      var rows;
      if (legacy) {
        if (Number(legacy[1]) < 1) return null;
        rows = Number(legacy[2]);
      } else if (/^\d+$/.test(text)) {
        rows = Number(text);
      } else {
        return null;
      }
      if (!isFinite(rows) || rows < MIN_ROWS) return null;
      return String(rows);
    }

    function planParts(plan) {
      var normalized = normalizePlan(plan);
      return { rows: Number(normalized === null ? DEFAULT_ROWS : normalized) };
    }

    function countLabel(plan, removed) {
      var kept = planParts(plan);
      return (
        "Transcript trim: " +
        kept.rows +
        " rows" +
        (removed ? " (" + removed + " removed)" : "") +
        " \u2014 set"
      );
    }

    // The messages sit inside the log on the session page; a page change can take the log
    // role away, so the whole document answers when no log holds one.
    function messageRoots(doc) {
      var logs = doc.querySelectorAll(LOG_SELECTOR);
      var roots = [];
      var i;
      for (i = 0; i < logs.length; i += 1) {
        roots = roots.concat(Array.prototype.slice.call(logs[i].querySelectorAll(MESSAGE_SELECTOR)));
      }
      if (!roots.length) {
        roots = Array.prototype.slice.call(doc.querySelectorAll(MESSAGE_SELECTOR));
      }
      return roots;
    }

    // A row is a part inside a message: text, tool call, thinking or status line.
    // Only the outermost row box counts, so a card inside a message is not split.
    function rowsOfRoot(root) {
      var boxes = root.querySelectorAll(ROW_BOX_SELECTOR);
      var rows = [];
      var i;
      for (i = 0; i < boxes.length; i += 1) {
        if (boxes[i].closest && boxes[i].closest(ROW_BOX_SELECTOR) !== boxes[i]) continue;
        rows = rows.concat(Array.prototype.slice.call(boxes[i].children));
      }
      return rows;
    }

    function removeActionSibling(root) {
      var actions = root.querySelectorAll(ACTION_SELECTOR);
      var i;
      for (i = 0; i < actions.length; i += 1) {
        if (actions[i].parentElement) actions[i].remove();
      }
    }

    // Remove the oldest rows across roots, and keep each message root in Arena's tree.
    function trimPlan(doc, plan) {
      var roots = messageRoots(doc);
      var rootRows = [];
      var total = 0;
      var excess;
      var removed = 0;
      var i;
      for (i = 0; i < roots.length; i += 1) {
        var rows = rowsOfRoot(roots[i]);
        var rootAttached = 0;
        var j;
        rootRows.push(rows);
        for (j = 0; j < rows.length; j += 1) {
          if (rows[j].parentElement) {
            total += 1;
            rootAttached += 1;
          }
        }
        if (!rootAttached) removeActionSibling(roots[i]);
      }
      excess = Math.max(0, total - planParts(plan).rows);
      for (i = 0; i < roots.length && excess > 0; i += 1) {
        var attached = 0;
        var rootList = rootRows[i];
        for (j = 0; j < rootList.length; j += 1) {
          if (rootList[j].parentElement) attached += 1;
        }
        var removedFromRoot = trimRows(rootList, Math.max(0, attached - excess));
        removed += removedFromRoot;
        excess -= removedFromRoot;
        if (removedFromRoot) removeActionSibling(roots[i]);
      }
      return removed;
    }

    // Arena redraws the transcript while a turn runs, and a trim mid-redraw breaks it.
    // The page settles when no turn is streaming and no live icon pulses.
    function isSettled(doc) {
      if (findStopGeneratingButton(doc)) return false;
      return !doc.querySelector(LIVE_ICON_SELECTOR);
    }

    // Only the rows still on the page count, and the oldest attached row leaves first.
    function trimRows(rows, keep) {
      var attached = 0;
      var excess = 0;
      var removed = 0;
      var i;
      for (i = 0; i < rows.length; i += 1) {
        if (rows[i].parentElement) attached += 1;
      }
      excess = attached - keep;
      for (i = 0; i < rows.length && removed < excess; i += 1) {
        if (!rows[i].parentElement) continue;
        rows[i].remove();
        removed += 1;
      }
      return removed;
    }

    if (exposeChecks("transcriptTrim", {
      normalizePlan: normalizePlan,
      planParts: planParts,
      countLabel: countLabel,
      messageRoots: messageRoots,
      rowsOfRoot: rowsOfRoot,
      trimPlan: trimPlan,
      trimRows: trimRows,
      isSettled: isSettled,
      ACTION_SELECTOR: ACTION_SELECTOR,
      MIN_ROWS: MIN_ROWS,
      DEFAULT_ROWS: DEFAULT_ROWS,
    })) {
      return;
    }

    var countMenuId;
    var timer = null;
    var scheduled = false;
    var observer = null;
    var labelTimer = null;
    var trimmedTotal = 0;

    function keepPlan() {
      var stored = String(GM_getValue(KEEP_KEY, "") || "");
      var normalized = normalizePlan(stored);
      if (!normalized) return String(DEFAULT_ROWS);
      if (normalized !== stored) GM_setValue(KEEP_KEY, normalized);
      return normalized;
    }

    function registerCount() {
      if (countMenuId) GM_unregisterMenuCommand(countMenuId);
      countMenuId = GM_registerMenuCommand(countLabel(keepPlan(), trimmedTotal), setCount);
    }

    // The menu shows the running count, refreshed once a second at most.
    function refreshLabel() {
      if (labelTimer !== null) return;
      labelTimer = setTimeout(function () {
        labelTimer = null;
        registerCount();
      }, 1000);
    }

    function setCount() {
      if (typeof prompt !== "function") return;
      var answer = prompt("Transcript rows to keep", keepPlan());
      if (answer === null) {
        registerCount();
        return;
      }
      var next = normalizePlan(answer);
      if (next === null) return;
      GM_setValue(KEEP_KEY, next);
      registerCount();
      trim();
    }

    function trim() {
      var removed = trimPlan(document, keepPlan());
      if (removed) {
        trimmedTotal += removed;
        refreshLabel();
      }
      return removed;
    }

    // A busy transcript mutates often, so the trim waits for a quiet moment, then for the
    // page to settle. A turn that keeps changing the page only re-arms the wait.
    function schedule() {
      if (scheduled) return;
      scheduled = true;
      timer = setTimeout(function () {
        scheduled = false;
        timer = null;
        if (location.pathname.indexOf("/agent/") !== 0) return;
        if (!isSettled(document)) {
          schedule();
          return;
        }
        trim();
      }, SETTLE_MS);
    }

    observer = new MutationObserver(schedule);
    observer.observe(document.documentElement, { childList: true, subtree: true });
    registerCount();
    if (location.pathname.indexOf("/agent/") === 0 && isSettled(document)) trim();
    return function () {
      if (timer !== null) clearTimeout(timer);
      if (labelTimer !== null) clearTimeout(labelTimer);
      observer.disconnect();
      if (countMenuId) GM_unregisterMenuCommand(countMenuId);
    };
  }, null, false);

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

    if (exposeChecks("hideComposer", {
      isSessionUrl: isSessionUrl,
      isStopGeneratingLabel: isStopGeneratingLabel,
      shouldHideComposer: shouldHideComposer,
      isSpacerElement: isSpacerElement,
      hasSpacerHeight: hasSpacerHeight,
      enforceSpacerHeight: enforceSpacerHeight,
      SPACER_SELECTOR: SPACER_SELECTOR,
      SPACER_HEIGHT: SPACER_HEIGHT,
    })) {
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
    // The live status text shimmers; a thinking row carries no pulsing icon, so its label leads.
    var LIVE_LABEL_SELECTOR = 'p[style*="text-shimmer"]';
    var TITLE_PREFIX = "Arena | ";
    // The live status row names the action; the emoji carries it in the title.
    var ACTION_EMOJI = [
      ["running", "\uD83D\uDDA5\uFE0F"],
      // The Bash label changes with the call: running Bash, using Bash, used Bash,
      // Running commands, Ran commands.
      ["bash", "\uD83D\uDDA5\uFE0F"],
      ["command", "\uD83D\uDDA5\uFE0F"],
      ["read", "\uD83D\uDCD6"],
      // Explored, Exploring: the read group covers what a read-only pass reports.
      ["explor", "\uD83D\uDCD6"],
      ["edit", "\u270F\uFE0F"],
      ["write", "\u270F\uFE0F"],
      ["search", "\uD83D\uDD0D"],
      ["think", "\uD83D\uDCAD"],
      ["thought", "\uD83D\uDCAD"],
      ["wait", "\uD83D\uDCA4"],
    ];
    var ACTION_FALLBACK = "\u2699\uFE0F";
    // A gap between two calls blinks the live row away; the last mark holds the title steady.
    var EMOJI_HOLD_MS = 5000;
    var heldEmoji = null;
    var heldEmojiAt = 0;
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

    function collapsed(node) {
      return node ? String(node.textContent || "").replace(/\s+/g, " ").trim() : "";
    }

    // Thinking rows are not always buttons, so the row is the nearest ancestor that carries text.
    function rowFromIcon(icon) {
      if (!icon) {
        return null;
      }
      var button = typeof icon.closest === "function" ? icon.closest("button") : null;
      if (button) {
        return button.parentElement ? button.parentElement : button;
      }
      var node = icon.parentElement || null;
      var depth = 0;
      while (node && depth < 4) {
        if (collapsed(node)) {
          return node;
        }
        node = node.parentElement || null;
        depth += 1;
      }
      return null;
    }

    function rowFromLabel(label) {
      if (!label) {
        return null;
      }
      var button = typeof label.closest === "function" ? label.closest("button") : null;
      if (button) {
        return button.parentElement ? button.parentElement : button;
      }
      return label.parentElement || label;
    }

    // The live status text is the strongest anchor: a thinking row has it and no pulsing icon.
    function liveRow(doc) {
      var labels = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(LIVE_LABEL_SELECTOR) : [];
      var row = rowFromLabel(labels.length ? labels[labels.length - 1] : null);
      if (row) {
        return row;
      }
      var messages = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(MESSAGE_SELECTOR) : [];
      var i;
      var icons;
      for (i = messages.length - 1; i >= 0; i -= 1) {
        icons = typeof messages[i].querySelectorAll === "function" ? messages[i].querySelectorAll(LIVE_ICON_SELECTOR) : [];
        row = rowFromIcon(icons.length ? icons[icons.length - 1] : null);
        if (row) {
          return row;
        }
      }
      icons = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(LIVE_ICON_SELECTOR) : [];
      row = rowFromIcon(icons.length ? icons[icons.length - 1] : null);
      return row && knownLabel(liveLabel(row)) ? row : null;
    }

    function knownLabel(text) {
      var lower = String(text || "").toLowerCase();
      var i;
      for (i = 0; i < ACTION_EMOJI.length; i += 1) {
        if (lower.indexOf(ACTION_EMOJI[i][0]) !== -1) {
          return true;
        }
      }
      return false;
    }

    function liveLabel(row) {
      if (!row || typeof row.querySelector !== "function") {
        return null;
      }
      var shimmer = typeof row.querySelectorAll === "function" ? row.querySelectorAll(LIVE_LABEL_SELECTOR) : [];
      if (shimmer.length) {
        var text = collapsed(shimmer[shimmer.length - 1]);
        if (text) {
          return text;
        }
      }
      var button = row.querySelector("button");
      var text = collapsed(button && typeof button.querySelector === "function" ? button.querySelector("p") : null);
      if (text) {
        return text;
      }
      var buttons = typeof row.querySelectorAll === "function" ? row.querySelectorAll("button") : [];
      var i;
      for (i = 0; i < buttons.length; i += 1) {
        text = collapsed(typeof buttons[i].querySelector === "function" ? buttons[i].querySelector("p") : null);
        if (text) {
          return text;
        }
      }
      text = collapsed(row.querySelector("p"));
      if (text) {
        return text;
      }
      return collapsed(button) || null;
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

    function currentPath() {
      return typeof location !== "undefined" ? String(location.pathname || "") : "";
    }

    // The session header re-renders and can take the link with it, so the last name on this page
    // holds until the page changes.
    function repoForTitle(doc) {
      var name = repoFromLink(doc.querySelector(REPO_LINK_SELECTOR));
      var path = currentPath();
      if (name) {
        lastRepo = name;
        lastPath = path;
        return name;
      }
      return lastRepo && path === lastPath ? lastRepo : null;
    }

    function heldEmojiFor(doc) {
      var emoji = emojiForRow(liveRow(doc));
      if (emoji) {
        heldEmoji = emoji;
        heldEmojiAt = Date.now();
        return emoji;
      }
      if (heldEmoji && Date.now() - heldEmojiAt < EMOJI_HOLD_MS) {
        return heldEmoji;
      }
      heldEmoji = null;
      return null;
    }

    function desiredTitle(doc) {
      var name = repoForTitle(doc);
      if (!name) {
        return null;
      }
      var emoji = heldEmojiFor(doc);
      return emoji ? TITLE_PREFIX + name + " " + emoji : TITLE_PREFIX + name;
    }

    var appliedTitle = null;
    var priorTitle = null;
    var lastRepo = null;
    var lastPath = null;

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

    if (exposeChecks("tabTitle", {
      repoFromLink: repoFromLink,
      repoForTitle: repoForTitle,
      desiredTitle: desiredTitle,
      syncTitle: syncTitle,
      liveLabel: liveLabel,
      liveRow: liveRow,
      emojiForRow: emojiForRow,
      actionEmoji: actionEmoji,
      TITLE_PREFIX: TITLE_PREFIX,
      EMOJI_HOLD_MS: EMOJI_HOLD_MS,
      MESSAGE_SELECTOR: MESSAGE_SELECTOR,
      LIVE_ICON_SELECTOR: LIVE_ICON_SELECTOR,
      LIVE_LABEL_SELECTOR: LIVE_LABEL_SELECTOR,
      REPO_LINK_SELECTOR: REPO_LINK_SELECTOR,
      expireHold: function () { heldEmojiAt = Date.now() - EMOJI_HOLD_MS - 1; },
      forgetPath: function () { lastPath = "/elsewhere"; },
      setPriorTitle: function (value) { priorTitle = value; },
    })) {
      return;
    }

    priorTitle = document.title;
    var observedRoot = null;
    var observer = new MutationObserver(function () {
      syncTitle(document);
    });
    function observeRoot() {
      if (observedRoot) {
        observer.disconnect();
      }
      observedRoot = document.documentElement;
      observer.observe(observedRoot, {
        subtree: true,
        childList: true,
        characterData: true,
      });
    }
    observeRoot();
    syncTitle(document);
    // Arena writes its own title from its renders and a full remount detaches the observer, so the
    // title is re-asserted every second; a write happens only when the value differs.
    var titleTimer = setInterval(function () {
      if (document.documentElement !== observedRoot) {
        observeRoot();
      }
      syncTitle(document);
    }, 1000);
    function onRoute() {
      lastRepo = null;
      lastPath = null;
      syncTitle(document);
    }
    window.addEventListener("popstate", onRoute);
    return function () {
      clearInterval(titleTimer);
      observer.disconnect();
      window.removeEventListener("popstate", onRoute);
      if (appliedTitle && document.title === appliedTitle) {
        document.title = priorTitle;
      }
      appliedTitle = null;
    };
  });

})();
