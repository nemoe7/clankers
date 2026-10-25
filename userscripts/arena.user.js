// ==UserScript==
// @name         Arena.ai | NemoUtils | v1.10.82
// @namespace    https://github.com/nemoe7/clankers
// @version      1.10.82
// @description  Prompt fill, Steering preview, composer hiding, transcript auto-scroll, and a repository tab title with saved feature switches
// @author       nemoe7
// @icon         https://arena.ai/favicon.ico
// @license      MIT
// @match        https://arena.ai/*
// @match        https://www.arena.ai/*
// @updateURL    https://raw.githubusercontent.com/nemoe7/clankers/main/userscripts/arena.user.js
// @downloadURL  https://raw.githubusercontent.com/nemoe7/clankers/main/userscripts/arena.user.js
// @run-at       document-idle
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        unsafeWindow
// @grant        GM_download
// @grant        GM_unregisterMenuCommand
// @connect      arena.site
// @connect      ts.net
// @connect      *
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
  var LOG_LEVEL_KEY = "clankers-arena-log-level";
  var LOG_LEVELS = ["debug", "info", "warn", "error"];
  var LOG_EVENTS = {
    logging: ["level", "setting-failed"],
    menu: ["run"],
    pause: ["change"],
    feature: ["change"],
    "auto-wake": ["clicked", "filled"],
    "keep-working": ["clicked", "filled"],
    fill: ["inserted", "rebuilt", "no-repo", "no-composer", "no-template", "filled"],
    trim: ["removed"],
    state: ["no-stamp", "compare", "force-stamp", "failed", "file-needed", "download", "saved", "no-preview", "moved", "forced", "confirmation", "no-write", "deferred-selector", "requested", "selector-closed", "reset-accept"],
    "preview-proxy": ["posted", "failed", "no-host"],
    steering: ["flagged-name"],
    wake: ["refused", "unavailable"],
    title: ["changed", "restored", "conditions"],
  };
  var LOG_VALUES = {
    feature: ["auto-wake", "keep-working", "prompt-fill", "open-steering", "preview-sandbox", "auto-scroll", "transcript-trim", "transcript-alerts", "hide-composer", "state-download", "keep-awake", "tab-title"],
    group: ["note", "task"],
    verdict: ["older", "same", "forward"],
    type: ["none", "chat", "reasoning", "poll", "play", "action", "error", "unchanged", "stale", "download"],
    route: ["link", "manager", "stamped"],
    emoji: ["", "💬", "💭", "🖥️", "📖", "✏️", "🔍", "💤", "📜", "❓", "⚙️", "⏳", "🛡️"],
    level: LOG_LEVELS,
    code: ["unknown", "manager-download", "copy-state", "missing-branch", "older-history", "wrong-file", "write", "file-api", "autosave", "autosave-get", "autosave-compare", "save-receipt", "NotAllowedError", "AbortError", "NotFoundError", "SecurityError", "TypeError", "Error"],
    result: ["equal", "different", "candidate-missing-records", "scope-mismatch", "unknown-baseline"],
  };
  var logMenuEntry = null;

  function getLogLevel() {
    try {
      var level = GM_getValue(LOG_LEVEL_KEY, "info");
      return LOG_LEVELS.indexOf(level) === -1 ? "info" : level;
    } catch (err) {
      return "info";
    }
  }

  function setLogLevel(level) {
    if (LOG_LEVELS.indexOf(level) === -1) return false;
    try {
      GM_setValue(LOG_LEVEL_KEY, level);
      return true;
    } catch (err) {
      return false;
    }
  }

  function logEvent(module, event, fields, level) {
    try {
      level = level || "info";
      var current = getLogLevel();
      if (LOG_LEVELS.indexOf(level) === -1 || LOG_LEVELS.indexOf(level) < LOG_LEVELS.indexOf(current)) return false;
      if (!Object.prototype.hasOwnProperty.call(LOG_EVENTS, module) || LOG_EVENTS[module].indexOf(event) === -1) return false;
      var data = {};
      var own = Object.prototype.hasOwnProperty;
      fields = fields || {};
      ["count", "removed", "kept", "status"].forEach(function (key) {
        if (own.call(fields, key) && typeof fields[key] === "number" && isFinite(fields[key])) data[key] = fields[key];
      });
      ["ok", "matched", "enabled", "paused", "captcha", "question", "live"].forEach(function (key) {
        if (own.call(fields, key) && typeof fields[key] === "boolean") data[key] = fields[key];
      });
      Object.keys(LOG_VALUES).forEach(function (key) {
        if (own.call(fields, key) && LOG_VALUES[key].indexOf(fields[key]) !== -1) data[key] = fields[key];
      });
      if (own.call(fields, "detail") && typeof fields.detail === "string" && fields.detail) {
        data.detail = fields.detail.slice(0, 160);
      }
      if (current === "debug") {
        ["repo", "filename"].forEach(function (key) {
          if (own.call(fields, key) && typeof fields[key] === "string") data[key] = fields[key];
        });
      }
      var line = LOG_TAG + "[" + module + "][" + level + "] " + event;
      var method = level === "warn" || level === "error" ? level : "log";
      if (Object.keys(data).length) console[method](line, data);
      else console[method](line);
      return true;
    } catch (err) {
      return false;
    }
  }

  function registerLogMenu() {
    if (logMenuEntry) return logMenuEntry;
    logMenuEntry = menuAdd(function () {
      return "Userscript - log level (" + getLogLevel().toUpperCase() + ")";
    }, function () {
      var order = ["info", "debug", "warn", "error"];
      var next = order[(order.indexOf(getLogLevel()) + 1) % order.length];
      if (setLogLevel(next)) {
        logEvent("logging", "level", { level: next });
        menuRefresh();
      } else {
        logEvent("logging", "setting-failed", null, "warn");
      }
    });
    return logMenuEntry;
  }

  var MENU_ORDER = [
    "Composer",
    "Proxy",
    "Steering",
    "Transcript",
    "State",
    "Page",
    "Tab title",
    "Userscript",
  ];
  var menuEntries = [];
  var menuNextSeq = 0;
  var menuOpened = false;
  var SHOW_SETTINGS_BUTTON_KEY = "clankers-arena-show-settings-button";
  var showSettingsEntry = null;
  var syncSettingsButtonHook = null;

  function showSettingsButtonOn() {
    if (typeof GM_getValue !== "function") return true;
    return GM_getValue(SHOW_SETTINGS_BUTTON_KEY, true) !== false;
  }

  function showSettingsButtonLabel(on) {
    return "Userscript - show settings button (" + (on ? "ON" : "OFF") + ")";
  }

  function setShowSettingsButton(next) {
    GM_setValue(SHOW_SETTINGS_BUTTON_KEY, Boolean(next));
    if (typeof syncSettingsButtonHook === "function") syncSettingsButtonHook();
    menuRefresh();
  }

  function showSettingsMenu() {
    if (showSettingsEntry !== null) return;
    showSettingsEntry = menuAdd(
      function () {
        return showSettingsButtonLabel(showSettingsButtonOn());
      },
      function () {
        setShowSettingsButton(!showSettingsButtonOn());
      },
      true,
    );
  }

  function menuRank(label) {
    var index = MENU_ORDER.indexOf(String(label).split(" - ")[0]);
    return index === -1 ? MENU_ORDER.length : index;
  }

  function menuRegister(entry) {
    if (typeof GM_registerMenuCommand !== "function") return;
    if (typeof document !== "undefined" && showSettingsButtonOn() && !entry.master) {
      entry.id = null;
      return;
    }
    entry.id = GM_registerMenuCommand(entry.label(), entry.press);
  }

  function menuUnregister(entry) {
    if (entry.id !== null && typeof GM_unregisterMenuCommand === "function") {
      GM_unregisterMenuCommand(entry.id);
    }
    entry.id = null;
  }

  function menuRefresh() {
    if (typeof GM_registerMenuCommand !== "function") return;
    var ordered = menuEntries.slice().sort(function (a, b) {
      return menuRank(a.label()) - menuRank(b.label()) || a.seq - b.seq;
    });
    menuEntries.forEach(menuUnregister);
    menuEntries = ordered;
    ordered.forEach(menuRegister);
  }

  function menuAdd(label, press, master) {
    var entry = {
      seq: menuNextSeq,
      label: label,
      press: press,
      id: null,
      master: Boolean(master),
    };
    menuNextSeq += 1;
    menuEntries.push(entry);
    menuRegister(entry);
    if (menuOpened) menuRefresh();
    return entry;
  }

  function menuDrop(entry) {
    var index = menuEntries.indexOf(entry);
    if (index !== -1) menuEntries.splice(index, 1);
    menuUnregister(entry);
  }

  function menuOpen() {
    menuOpened = true;
    menuRefresh();
  }

  function menuItem(list, label, run) {
    list.push(
      menuAdd(function () {
        return label;
      }, function () {
        logEvent("menu", "run");
        run();
      }),
    );
  }

  exposeChecks("logging", { logEvent: logEvent, LOG_TAG: LOG_TAG, menuItem: menuItem,
    getLogLevel: getLogLevel, setLogLevel: setLogLevel, registerLogMenu: registerLogMenu });
  if (typeof document !== "undefined") registerLogMenu();

  var BAR_SELECTOR =
    "div.relative.z-10.w-full.md\\:absolute.md\\:left-0.md\\:top-full";
  var CHIP_SPAN_SELECTOR =
    'button[aria-haspopup="dialog"] span.truncate, button[aria-haspopup="menu"] span.truncate';
  var SESSION_BRANCH_RE = /^arena\/[0-9a-f]{8}-/;
  var SLUG_KEY = "clankers-arena-agent-slug";
  var STATE_TITLE_RE = /^Arena \| (\S+)/;

  function arenaUrl(urlString) {
    var url;
    try {
      url = new URL(urlString);
    } catch (err) {
      return null;
    }
    return url.hostname.replace(/^www\./, "") === "arena.ai" ? url : null;
  }

  function isComposerUrl(urlString) {
    var url = arenaUrl(urlString);
    return Boolean(url) && url.pathname.replace(/\/+$/, "") === "/agent";
  }

  function isSessionUrl(urlString) {
    var url = arenaUrl(urlString);
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

  function slugFromBare(text) {
    var trimmed = String(text || "").trim();
    return /^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(trimmed) ? trimmed : null;
  }

  function readSlug(doc) {
    return detectRepo(doc) || null;
  }

  var PAUSE_KEY = "clankers-arena-userscript-paused";
  var PAUSE_LABEL = "Userscript";
  var pauseUnits = [];
  var pauseEntry = null;

  function pauseStored() {
    if (typeof GM_getValue !== "function") return false;
    return GM_getValue(PAUSE_KEY, false) === true;
  }

  function pauseLabel(paused) {
    return PAUSE_LABEL + (paused ? " - resume all" : " - pause all");
  }

  function registerPauseUnit(label, start, halt, stored) {
    pauseUnits.push({ label: label, start: start, halt: halt, stored: stored });
  }

  function showPauseMenu() {
    if (pauseEntry !== null) return;
    pauseEntry = menuAdd(function () {
      return pauseLabel(pauseStored());
    }, function () {
      setPause(!pauseStored());
    });
  }

  function setPause(next) {
    GM_setValue(PAUSE_KEY, next);
    pauseUnits.forEach(function (unit) {
      if (next) {
        unit.halt();
      } else if (unit.stored()) {
        unit.start();
      }
    });
    menuRefresh();
    logEvent("pause", "change", { paused: next });
  }

  var HTTP_JITTER_MS = 15000;
  var HTTP_JITTER_KEY = "clankers-arena-http-jitter-ms";
  var STATE_WATCH_KEY = "clankers-arena-state-watch-ms";
  var STATE_PANEL_KEY = "clankers-arena-state-panel-ms";
  var WAKE_DELAY_MIN_MS = 0;
  var WAKE_DELAY_MIN_KEY = "clankers-arena-wake-delay-min-ms";
  var WAKE_DELAY_MS = 5000;
  var WAKE_DELAY_KEY = "clankers-arena-wake-delay-ms";
  var KEEP_WORKING_DELAY_MIN_MS = 0;
  var KEEP_WORKING_DELAY_MIN_KEY = "clankers-arena-keep-working-delay-min-ms";
  var KEEP_WORKING_DELAY_MS = 5000;
  var KEEP_WORKING_DELAY_KEY = "clankers-arena-keep-working-delay-ms";
  var featureRegistry = [];
  var restartStateWatchHook = null;
  var syncPreviewProxyHook = null;
  var previewUiRepo = "";
  var syncProxySettingsHook = null;
  var postKeyNowHook = null;
  var applyTrimKeepHook = null;
  var registerTrimCapHook = null;
  var restartTrimTimerHook = null;
  var trimNowHook = null;
  var chooseStateFileHook = null;
  var forceSaveStateHook = null;
  var setResetWindowHook = null;
  var restartTitleTimerHook = null;
  var syncSettingsModalVisibilityHook = null;

  function httpJitterMs() {
    if (typeof GM_getValue !== "function") return HTTP_JITTER_MS;
    var ms = Number(GM_getValue(HTTP_JITTER_KEY, HTTP_JITTER_MS));
    if (!isFinite(ms) || ms < 0) return HTTP_JITTER_MS;
    return Math.min(Math.round(ms), 60000);
  }

  function stateWatchMs() {
    if (typeof GM_getValue !== "function") return STATE_WATCH_MS;
    var ms = Number(GM_getValue(STATE_WATCH_KEY, STATE_WATCH_MS));
    if (!isFinite(ms) || ms < 1000) return STATE_WATCH_MS;
    return Math.min(Math.round(ms), 60000);
  }

  function statePanelMs() {
    if (typeof GM_getValue !== "function") return 6000;
    var ms = Number(GM_getValue(STATE_PANEL_KEY, 6000));
    if (!isFinite(ms) || ms < 1000) return 6000;
    return Math.min(Math.round(ms), 60000);
  }

  function wakeDelayMinMs() {
    if (typeof GM_getValue !== "function") return WAKE_DELAY_MIN_MS;
    var ms = Number(GM_getValue(WAKE_DELAY_MIN_KEY, WAKE_DELAY_MIN_MS));
    if (!isFinite(ms) || ms < 0) return WAKE_DELAY_MIN_MS;
    return Math.min(Math.round(ms), 60000);
  }

  function wakeDelayMs() {
    if (typeof GM_getValue !== "function") return WAKE_DELAY_MS;
    var ms = Number(GM_getValue(WAKE_DELAY_KEY, WAKE_DELAY_MS));
    if (!isFinite(ms) || ms < 0) return WAKE_DELAY_MS;
    return Math.min(Math.round(ms), 60000);
  }

  function wakeDelayRangeMs() {
    var a = wakeDelayMinMs();
    var b = wakeDelayMs();
    return { min: Math.min(a, b), max: Math.max(a, b) };
  }

  function randomWakeDelayMs() {
    var r = wakeDelayRangeMs();
    return r.min + Math.floor(Math.random() * (r.max - r.min + 1));
  }

  function keepWorkingDelayMinMs() {
    if (typeof GM_getValue !== "function") return KEEP_WORKING_DELAY_MIN_MS;
    var ms = Number(GM_getValue(KEEP_WORKING_DELAY_MIN_KEY, KEEP_WORKING_DELAY_MIN_MS));
    if (!isFinite(ms) || ms < 0) return KEEP_WORKING_DELAY_MIN_MS;
    return Math.min(Math.round(ms), 60000);
  }

  function keepWorkingDelayMs() {
    if (typeof GM_getValue !== "function") return KEEP_WORKING_DELAY_MS;
    var ms = Number(GM_getValue(KEEP_WORKING_DELAY_KEY, KEEP_WORKING_DELAY_MS));
    if (!isFinite(ms) || ms < 0) return KEEP_WORKING_DELAY_MS;
    return Math.min(Math.round(ms), 60000);
  }

  function keepWorkingDelayRangeMs() {
    var a = keepWorkingDelayMinMs();
    var b = keepWorkingDelayMs();
    return { min: Math.min(a, b), max: Math.max(a, b) };
  }

  function randomKeepWorkingDelayMs() {
    var r = keepWorkingDelayRangeMs();
    return r.min + Math.floor(Math.random() * (r.max - r.min + 1));
  }

  function jitteredTimer(run, everyMs, spreadMs) {
    var waiting = null;
    function tick() {
      var activeSpread = spreadMs === HTTP_JITTER_MS ? httpJitterMs() : spreadMs;
      waiting = setTimeout(function () {
        waiting = null;
        run();
      }, Math.floor(Math.random() * activeSpread));
    }
    var beat = setInterval(tick, everyMs);
    return function () {
      if (typeof clearInterval === "function") clearInterval(beat);
      if (waiting !== null && typeof clearTimeout === "function") {
        clearTimeout(waiting);
      }
      waiting = null;
    };
  }

  function runFeature(key, label, run, onChange, defaultOn) {
    if (typeof document === "undefined") {
      run();
      return;
    }
    var fallback = defaultOn !== false;
    var enabled = GM_getValue(key, fallback) !== false;
    var stop = null;
    logEvent("feature", "change", { feature: key, enabled: enabled });

    function storedOn() {
      return GM_getValue(key, fallback) !== false;
    }

    function start() {
      if (stop === null) stop = run();
    }

    function halt() {
      if (stop) {
        stop();
        stop = null;
      }
    }

    function menuLabel() {
      return label + " (" + (storedOn() ? "ON" : "OFF") + ")";
    }

    function toggle() {
      var next = GM_getValue(key, fallback) === false;
      GM_setValue(key, next);
      logEvent("feature", "change", { feature: key, enabled: next });
      halt();
      if (next && !pauseStored()) start();
      menuRefresh();
      if (typeof onChange === "function") onChange();
    }

    menuAdd(menuLabel, toggle);
    registerPauseUnit(label, start, halt, storedOn);
    if (enabled && !pauseStored()) {
      stop = run();
    }
    var controller = {
      key: key,
      label: label,
      storedOn: storedOn,
      isOn: function () {
        return stop !== null;
      },
      toggle: toggle,
      set: function (next) {
        if (storedOn() !== Boolean(next)) toggle();
      },
    };
    featureRegistry.push(controller);
    return controller;
  }

  function isStopGeneratingLabel(value) {
    return String(value || "").trim().toLowerCase() === "stop generating";
  }

  function isSendMessageLabel(value) {
    var normalized = String(value || "").trim().toLowerCase();
    return normalized === "send message" || normalized === "send";
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

  function isInjectedControlButton(button) {
    if (!button || typeof button.getAttribute !== "function") return false;
    return Boolean(
      button.getAttribute("data-clankers-autoscroll-toggle") ||
        button.getAttribute("data-clankers-settings-toggle") ||
        button.getAttribute("data-clankers-prompt-fill"),
    );
  }

  function findComposerActionButton(doc) {
    var stopBtn = findStopGeneratingButton(doc);
    if (stopBtn) return stopBtn;
    if (!doc || typeof doc.querySelectorAll !== "function") return null;
    var labeled = doc.querySelectorAll("button[aria-label]");
    var i;
    for (i = 0; i < labeled.length; i += 1) {
      if (
        !isInjectedControlButton(labeled[i]) &&
        isSendMessageLabel(labeled[i].getAttribute("aria-label"))
      ) {
        return labeled[i];
      }
    }
    var buttons = doc.querySelectorAll("button");
    for (i = 0; i < buttons.length; i += 1) {
      var btn = buttons[i];
      if (isInjectedControlButton(btn)) continue;
      var typeAttr =
        typeof btn.getAttribute === "function" ? btn.getAttribute("type") : btn.type;
      if (String(typeAttr || "").toLowerCase() === "submit") {
        return btn;
      }
    }
    var composer =
      typeof doc.querySelector === "function"
        ? doc.querySelector('div.tiptap.ProseMirror[contenteditable="true"]')
        : null;
    if (!composer) return null;
    var scope =
      (composer.parentElement && composer.parentElement.parentElement) ||
      composer.parentElement;
    if (!scope || typeof scope.querySelectorAll !== "function") return null;
    var scopedButtons = scope.querySelectorAll("button");
    for (i = scopedButtons.length - 1; i >= 0; i -= 1) {
      if (!isInjectedControlButton(scopedButtons[i])) {
        return scopedButtons[i];
      }
    }
    return null;
  }

  var GENERATION_ALERT_SELECTOR = '[role="alert"][class~="border-red-500/30"][class~="bg-red-500/10"]';
  var CAPTCHA_SELECTOR = '.recaptcha-v2-container, iframe[title="reCAPTCHA"]';

  function openDialog(node) {
    var current = node;
    var depth = 0;
    while (current && depth < 8) {
      if (typeof current.getAttribute === "function") {
        var state = current.getAttribute("data-state");
        if (state === "closed") return false;
        if (state === "open") return true;
      }
      current = current.parentElement || null;
      depth += 1;
    }
    return true;
  }

  function renderedNode(node) {
    if (typeof node.getClientRects === "function") {
      return node.getClientRects().length > 0;
    }
    return !node.hidden;
  }

  var QUESTION_SELECTOR = 'div[role="radiogroup"][aria-label]';
  var QUESTION_EMOJI = "\u2753";

  function questionSignal(doc) {
    if (!doc || typeof doc.querySelectorAll !== "function") {
      return false;
    }
    var nodes = doc.querySelectorAll(QUESTION_SELECTOR);
    var i;
    for (i = 0; i < nodes.length; i += 1) {
      if (renderedNode(nodes[i])) return true;
    }
    return false;
  }

  function captchaSignal(doc) {
    if (!doc || typeof doc.querySelectorAll !== "function") {
      return false;
    }
    var nodes = doc.querySelectorAll(CAPTCHA_SELECTOR);
    var i;
    for (i = 0; i < nodes.length; i += 1) {
      if (openDialog(nodes[i]) && renderedNode(nodes[i])) return true;
    }
    return false;
  }

  function lastMessageRoot(doc) {
    var roots = typeof doc.querySelectorAll === "function"
      ? doc.querySelectorAll("[data-agent-transcript-message]") : [];
    return roots.length ? roots[roots.length - 1] : null;
  }

  function setComposerText(el, text) {
    el.focus();
    var selection = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(el);
    selection.removeAllRanges();
    selection.addRange(range);
    var hasCode =
      /`[^`\n]+`/.test(text) &&
      typeof document.createElement === "function" &&
      typeof el.appendChild === "function";
    var ok = !hasCode && document.execCommand("insertText", false, text);
    var matched = !hasCode && String(el.innerText || "").trim() === text;
    logEvent("fill", "inserted", { ok: ok, matched: matched }, "debug");
    if (!ok || !matched) {
      while (el.firstChild) {
        el.removeChild(el.firstChild);
      }
      var lines = text.split("\n");
      for (var j = 0; j < lines.length; j += 1) {
        var paragraph = document.createElement("p");
        var line = lines[j];
        var parts = line.split(/(`[^`\n]+`)/g);
        if (parts.length > 1 && typeof document.createTextNode === "function") {
          for (var k = 0; k < parts.length; k += 1) {
            var part = parts[k];
            if (!part) continue;
            if (
              part.length > 2 &&
              part.charAt(0) === "`" &&
              part.charAt(part.length - 1) === "`"
            ) {
              var code = document.createElement("code");
              code.textContent = part.slice(1, -1);
              paragraph.appendChild(code);
            } else {
              paragraph.appendChild(document.createTextNode(part));
            }
          }
        } else {
          paragraph.textContent = line;
        }
        el.appendChild(paragraph);
      }
      el.dispatchEvent(
        new InputEvent("input", {
          bubbles: true,
          cancelable: true,
          inputType: "insertText",
          data: text,
        }),
      );
      logEvent("fill", "rebuilt", { count: lines.length }, "debug");
    }
  }


  runFeature("prompt-fill", "Composer - fill", function () {

    var COMPOSER_SELECTOR = 'div.tiptap.ProseMirror[contenteditable="true"]';
    var TEMPLATE_RE = /^(\S+) read (?:AGENTS\.md ARENA\.md|ARENA\.md AGENTS\.md|ARENA\.md and AGENTS\.md)/;

    var PROXY_HOST_KEY = "clankers-arena-proxy-host";
    var PREVIEW_PROXY_HOST_KEY = "clankers-arena-preview-proxy-host";
    var PROXY_MASTER_KEY = "clankers-arena-proxy-master";

    function proxyHost(raw) {
      var host = String(raw || "").trim().replace(/\/+$/, "").replace(/\/v1$/, "");
      if (/^[a-z0-9-]+(?:\.[a-z0-9-]+)+$/i.test(host)) {
        host = "https://" + host;
      }
      return /^https:\/\/[a-z0-9.-]+$/i.test(host) ? host : null;
    }

    function previewProxyHost(raw, fallbackProxyHost) {
      var explicit = proxyHost(raw);
      if (explicit) return explicit;
      var base = proxyHost(fallbackProxyHost);
      if (!base) return null;
      var derived = base.replace(
        /^https:\/\/arena-proxy(\.[a-z0-9.-]+)$/i,
        "https://arena-preview$1",
      );
      return derived !== base ? derived : null;
    }

    function isUnavailablePreviewName(value) {
      return /\b(?:preview\s+)?unavailable\b/i.test(String(value || "").trim());
    }

    function previewHeaderRaw(doc) {
      if (!doc || typeof doc.querySelectorAll !== "function") return "";
      var spans = doc.querySelectorAll("span");
      var i;
      var cls;
      var text;
      for (i = 0; i < spans.length; i += 1) {
        cls = String(spans[i].className || "");
        if (
          cls.indexOf("text-text-secondary") !== -1 &&
          cls.indexOf("max-w-[180px]") !== -1
        ) {
          text = String(spans[i].textContent || "").trim();
          if (text) return text;
        }
      }
      return "";
    }

    function previewHeaderName(doc) {
      var text = previewHeaderRaw(doc);
      return isUnavailablePreviewName(text) ? "" : text;
    }

    function reconcileRecentPreviews(previousByName, items) {
      var nextByName = Object.assign({}, previousByName || {});
      var invalidated = [];
      var i;
      var item;
      var key;
      var prevUrl;
      for (i = 0; i < (items || []).length; i += 1) {
        item = items[i];
        if (!item || !item.url) continue;
        key = String(item.name || "").trim();
        if (!key) continue;
        prevUrl = nextByName[key];
        if (prevUrl && prevUrl !== item.url && invalidated.indexOf(prevUrl) === -1) {
          invalidated.push(prevUrl);
        }
        nextByName[key] = item.url;
      }
      return { byName: nextByName, invalidated: invalidated };
    }

    function discoverPreviews(doc, reportedRepo) {
      if (!doc || typeof doc.querySelectorAll !== "function") return [];
      var rawHeader = previewHeaderRaw(doc);
      if (isUnavailablePreviewName(rawHeader)) return [];
      var domName = isUnavailablePreviewName(rawHeader) ? "" : rawHeader;
      var uiRepo = String(
        reportedRepo !== undefined ? reportedRepo : previewUiRepo || "",
      ).trim();
      var steeringBase = previewBase(doc);
      var steeringRoot = steeringBase ? steeringBase + "/" : "";
      var frames = doc.querySelectorAll("iframe");
      var links = doc.querySelectorAll("a");
      var nodes = [];
      var seen = {};
      var found = [];
      var i;
      var raw;
      var match;
      var root;
      var resolvedName;
      for (i = 0; i < frames.length; i += 1) {
        nodes.push(
          frames[i].src ||
            (typeof frames[i].getAttribute === "function"
              ? frames[i].getAttribute("src")
              : ""),
        );
      }
      for (i = 0; i < links.length; i += 1) {
        nodes.push(
          links[i].href ||
            (typeof links[i].getAttribute === "function"
              ? links[i].getAttribute("href")
              : ""),
        );
      }
      for (i = 0; i < nodes.length; i += 1) {
        raw = String(nodes[i] || "").trim();
        match = /^(https:\/\/sbx-[a-z0-9-]+\.arena\.site)(?:\/.*)?$/i.exec(raw);
        if (!match) continue;
        root = match[1] + "/";
        if (seen[root]) continue;
        seen[root] = true;
        resolvedName =
          uiRepo && (!steeringRoot || root === steeringRoot)
            ? uiRepo + " - Steering"
            : domName;
        if (!resolvedName || isUnavailablePreviewName(resolvedName)) continue;
        found.push({ url: root, name: resolvedName });
      }
      return found;
    }

    function keyUrl(host, master) {
      return host + "/v1/key?master=" + encodeURIComponent(master);
    }

    function agentKeyFrom(body) {
      var key = body && typeof body.key === "string" ? body.key : "";
      return /^[A-Za-z0-9_-]{20,64}$/.test(key) ? key : null;
    }

    var ROTATE_MIN_SECONDS = 900;
    var ROTATE_INTERVAL_MS = ROTATE_MIN_SECONDS * 1000;
    var ROTATE_DUE_KEY = "clankers-arena-rotate-due";
    var NOTED_KEY = "clankers-arena-noted-key";
    var KEY_WATCH_MS = 60 * 1000;
    var PREVIEW_FRAME_TITLE = "App preview on port 8000";

    function previewBase(doc) {
      var frames = doc.querySelectorAll("iframe[title]");
      var i;
      var title;
      for (i = 0; i < frames.length; i += 1) {
        title = frames[i].getAttribute("title") || "";
        if (title.indexOf(PREVIEW_FRAME_TITLE) === 0 && frames[i].src) {
          return frames[i].src.replace(/\/+$/, "");
        }
      }
      return null;
    }

    function rotateUrl(host, master, min) {
      return (
        host + "/v1/rotate?master=" + encodeURIComponent(master) + "&min=" + min
      );
    }

    function keyPostUrl(base) {
      return base + "/api/key";
    }

    function keyNote(type, key, atIso, host) {
      return (
        "Arena proxy " +
        host +
        " key " +
        type +
        " at " +
        atIso +
        ". New key: " +
        key +
        ". Use it as ?key= in every /v1 call. Routes: /v1/ping lists them;"
        + " skills/arena-skill/arena-egress-proxy holds the map. Never print it."
      );
    }

    function noteKey(key, host, type) {
      if (GM_getValue(NOTED_KEY, "") === key) return;
      GM_setValue(NOTED_KEY, key);
      postKeyNote(keyNote(type, key, new Date().toISOString(), host));
    }

    function keyChanged(held, incoming) {
      return incoming && incoming !== held ? incoming : null;
    }

    function keyPostDue(base, posted, force) {
      return Boolean(base) && (force === true || base !== posted);
    }

    function rotationDueAt(nowMs, ageSeconds, minSeconds) {
      return nowMs + Math.max(0, minSeconds - ageSeconds) * 1000;
    }

    function rotationWaitMs(dueMs, nowMs) {
      return Math.max(0, dueMs - nowMs);
    }

    function requestJson(method, url, payload, done) {
      function finish(text, status) {
        var body = null;
        try {
          body = JSON.parse(text);
        } catch (err) {
          body = null;
        }
        done(status, body);
      }
      if (typeof GM_xmlhttpRequest === "function") {
        GM_xmlhttpRequest({
          method: method,
          url: url,
          headers: payload ? { "Content-Type": "application/json" } : {},
          data: payload ? JSON.stringify(payload) : undefined,
          onload: function (answer) {
            finish(answer.responseText, answer.status);
          },
          onerror: function () {
            finish("", 0);
          },
        });
        return;
      }
      done(0, null);
    }

    function fetchJson(url, done) {
      fetch(url)
        .then(function (r) {
          return r.json().then(function (body) {
            return { status: r.status, body: body };
          });
        })
        .then(function (answer) {
          done(answer.status, answer.body);
        })
        .catch(function () {
          done(0, null);
        });
    }

    function promptForSlug(slug, promptFill, arenaMd) {
      if (typeof promptFill !== "string" || !promptFill.trim()) return null;
      var base = slug + " read ARENA.md AGENTS.md in full before your first edit, and follow both." +
        "\n\n" + promptFill.trim();
      if (arenaMd) {
        return base + "\n\nhere is ARENA.md:\n" + arenaMd;
      }
      return base;
    }

    function shouldWrite(current, slug, lastSlug, filledSlug) {
      var text = String(current || "").trim();
      if (filledSlug === slug) {
        return false;
      }
      if (text === "") {
        return true;
      }
      if (TEMPLATE_RE.test(text)) {
        return true;
      }
      if (lastSlug === null) {
        return false;
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

    var PROMPT_FILL_URL =
      "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/userscripts/arena-prompt-fill.txt";
    var ARENA_MD_URL =
      "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/rules/ARENA.md";

    if (exposeChecks("promptFill", {
      isComposerUrl: isComposerUrl,
      slugFromOwnerRepo: slugFromOwnerRepo,
      promptForSlug: promptForSlug,
      shouldWrite: shouldWrite,
      PROMPT_FILL_URL: PROMPT_FILL_URL,
      ARENA_MD_URL: ARENA_MD_URL,
      PROXY_HOST_KEY: PROXY_HOST_KEY,
      PREVIEW_PROXY_HOST_KEY: PREVIEW_PROXY_HOST_KEY,
      PROXY_MASTER_KEY: PROXY_MASTER_KEY,
      proxyHost: proxyHost,
      previewProxyHost: previewProxyHost,
      previewHeaderName: previewHeaderName,
      reconcileRecentPreviews: reconcileRecentPreviews,
      discoverPreviews: discoverPreviews,
      keyUrl: keyUrl,
      agentKeyFrom: agentKeyFrom,
      PREVIEW_FRAME_TITLE: PREVIEW_FRAME_TITLE,
      ROTATE_MIN_SECONDS: ROTATE_MIN_SECONDS,
      ROTATE_DUE_KEY: ROTATE_DUE_KEY,
      NOTED_KEY: NOTED_KEY,
      KEY_WATCH_MS: KEY_WATCH_MS,
      keyNote: keyNote,
      keyChanged: keyChanged,
      keyPostDue: keyPostDue,
      rotationDueAt: rotationDueAt,
      rotationWaitMs: rotationWaitMs,
      previewBase: previewBase,
      keyPostUrl: keyPostUrl,
      fetchJson: fetchJson,
      rotateUrl: rotateUrl,
      postKeyNow: postKeyNow,
    })) {
      return;
    }

    var promptFillCache = null;
    var arenaMdCache = null;
    var heldKey = null;
    var promptResourcesTried = false;
    var pendingFetch = null;
    var keyTried = false;
    var keyFetch = null;

    function fetchText(url) {
      return fetch(url).then(function (r) {
        if (!r.ok) return null;
        return r.text();
      }).then(function (content) {
        return typeof content === "string" && content.trim() ? content : null;
      }).catch(function () { return null; });
    }

    function ensureFetch() {
      if (promptResourcesTried || pendingFetch) return;
      pendingFetch = Promise.all([fetchText(PROMPT_FILL_URL), fetchText(ARENA_MD_URL)])
        .then(function (contents) {
          promptFillCache = contents[0];
          arenaMdCache = contents[1];
          promptResourcesTried = true;
          pendingFetch = null;
          sync();
        });
    }

    function postAgentKey(key, host) {
      var base = previewBase(document);
      if (!base || !key) return;
      requestJson("POST", keyPostUrl(base), { key: key, host: host }, function () {});
    }

    function postKeyNow(state, post, fetchNow) {
      if (!state.host) {
        return;
      }
      if (state.key) {
        post(state.key, state.host);
        return;
      }
      fetchNow();
    }

    function postKeyNote(text) {
      var base = previewBase(document);
      if (!base) return;
      requestJson(
        "POST",
        base + "/api/notes",
        { text: text, quiet: true },
        function () {},
      );
    }

    function fetchAgentKey() {
      var host = proxyHost(GM_getValue(PROXY_HOST_KEY, ""));
      var master = String(GM_getValue(PROXY_MASTER_KEY, "") || "").trim();
      if (!host || !master) {
        return Promise.resolve(null);
      }
      return fetch(keyUrl(host, master))
        .then(function (r) {
          if (!r.ok) return null;
          return r.json();
        })
        .then(function (body) {
          var key = agentKeyFrom(body);
          if (key) {
            heldKey = key;
            postAgentKey(key, host);
            noteKey(key, host, "ready");
          }
          return null;
        })
        .catch(function () {
          return null;
        });
    }

    function ensureAgentKey() {
      if (keyTried || keyFetch) return;
      keyFetch = fetchAgentKey().then(function () {
        keyTried = true;
        keyFetch = null;
        sync();
      });
    }

    var proxyMenus = [];

    function setProxyValue(key, label, ask) {
      menuItem(proxyMenus, label, function () {
        var answer = window.prompt(label, ask ? String(ask) : "");
        if (answer === null) return;
        GM_setValue(key, String(answer).trim());
        keyTried = false;
        keyFetch = null;
        lastSlug = null;
        postedPreviews = {};
        ensureAgentKey();
        postRecentPreviews(document, true);
        sync();
      });
    }

    setProxyValue(PROXY_HOST_KEY, "Proxy - host", GM_getValue(PROXY_HOST_KEY, ""));
    setProxyValue(
      PREVIEW_PROXY_HOST_KEY,
      "Proxy - preview host",
      GM_getValue(PREVIEW_PROXY_HOST_KEY, ""),
    );
    setProxyValue(PROXY_MASTER_KEY, "Proxy - master key", "");

    function settings() {
      return {
        host: proxyHost(GM_getValue(PROXY_HOST_KEY, "")),
        master: String(GM_getValue(PROXY_MASTER_KEY, "") || "").trim(),
      };
    }

    var postedBase = null;
    var postedPreviews = {};
    var postedByName = {};

    function removeRecentPreview(endpoint, url) {
      var payload = { url: url, remove: true, forget: url };
      if (typeof GM_xmlhttpRequest === "function") {
        requestJson("POST", endpoint, payload, function () {});
      } else if (typeof fetch === "function") {
        fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }).catch(function () {});
      }
    }

    function sendRecentPreview(endpoint, item, stamp) {
      var payload = { url: item.url, name: item.name || "" };
      function onDone(status) {
        if (status >= 200 && status < 300) {
          logEvent("preview-proxy", "posted", { url: item.url, status: status });
        } else {
          if (postedPreviews[item.url] === stamp) {
            delete postedPreviews[item.url];
          }
          logEvent("preview-proxy", "failed", { url: item.url, status: status }, "warn");
        }
      }
      function viaFetch() {
        if (typeof fetch !== "function") {
          onDone(0);
          return;
        }
        fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
          .then(function (r) {
            onDone(r && typeof r.status === "number" ? r.status : 200);
          })
          .catch(function () {
            onDone(0);
          });
      }
      if (typeof GM_xmlhttpRequest === "function") {
        requestJson("POST", endpoint, payload, function (status) {
          if (status === 0 && typeof fetch === "function") {
            viaFetch();
          } else {
            onDone(status);
          }
        });
      } else {
        viaFetch();
      }
    }

    function postRecentPreviews(doc, force) {
      var items = discoverPreviews(doc);
      if (!items.length) return;
      var host = previewProxyHost(
        GM_getValue(PREVIEW_PROXY_HOST_KEY, ""),
        GM_getValue(PROXY_HOST_KEY, ""),
      );
      if (!host) {
        logEvent("preview-proxy", "no-host", { count: items.length }, "debug");
        return;
      }
      var reconciled = reconcileRecentPreviews(postedByName, items);
      postedByName = reconciled.byName;
      var i;
      var item;
      var stamp;
      var oldUrl;
      for (i = 0; i < reconciled.invalidated.length; i += 1) {
        oldUrl = reconciled.invalidated[i];
        delete postedPreviews[oldUrl];
        removeRecentPreview(host + "/pwa/recent", oldUrl);
      }
      for (i = 0; i < items.length; i += 1) {
        item = items[i];
        stamp = host + "|" + item.url + "|" + (item.name || "");
        if (!force && postedPreviews[item.url] === stamp) continue;
        postedPreviews[item.url] = stamp;
        sendRecentPreview(host + "/pwa/recent", item, stamp);
      }
    }

    function postKeyToPreview(force) {
      postRecentPreviews(document, false);
      var base = previewBase(document);
      if (!keyPostDue(base, postedBase, force === true)) return;
      var pair = settings();
      if (!pair.host || !heldKey) return;
      postedBase = base;
      postAgentKey(heldKey, pair.host);
    }

    function rotateKey(minSeconds, done) {
      if (captchaSignal(document)) return;
      var pair = settings();
      if (!pair.host || !pair.master) return;
      if (
        minSeconds > 0 &&
        rotationWaitMs(Number(GM_getValue(ROTATE_DUE_KEY, 0)), Date.now()) > 0
      ) {
        return;
      }
      fetchJson(
        rotateUrl(pair.host, pair.master, minSeconds),
        function (status, body) {
          if (status !== 200 || !body) {
            if (typeof done === "function") done(false);
            return;
          }
          if (body.rotated !== true || !body.key) {
            var age = typeof body.age === "number" ? body.age : ROTATE_MIN_SECONDS;
            GM_setValue(
              ROTATE_DUE_KEY,
              rotationDueAt(Date.now(), age, ROTATE_MIN_SECONDS),
            );
            if (typeof done === "function") done(false);
            return;
          }
          GM_setValue(
            ROTATE_DUE_KEY,
            rotationDueAt(Date.now(), 0, ROTATE_MIN_SECONDS),
          );
          heldKey = body.key;
          GM_setValue(NOTED_KEY, body.key);
          postAgentKey(body.key, pair.host);
          postKeyNote(
            keyNote(
              "rotated",
              body.key,
              body.at || new Date().toISOString(),
              pair.host,
            ),
          );
          sync();
          if (typeof done === "function") done(true);
        },
      );
    }

    function triggerPostKeyNow() {
      postedPreviews = {};
      postRecentPreviews(document, true);
      var pair = settings();
      postKeyNow(
        { host: pair.host, key: heldKey },
        postAgentKey,
        function () {
          keyTried = false;
          keyFetch = null;
          fetchAgentKey();
        },
      );
    }

    menuItem(proxyMenus, "Proxy - post key now", triggerPostKeyNow);

    syncProxySettingsHook = function () {
      keyTried = false;
      keyFetch = null;
      lastSlug = null;
      postedPreviews = {};
      ensureAgentKey();
      postRecentPreviews(document, true);
      sync();
    };
    postKeyNowHook = triggerPostKeyNow;
    syncPreviewProxyHook = function () {
      postedPreviews = {};
      postRecentPreviews(document, true);
    };

    rotateKey(ROTATE_MIN_SECONDS, null);

    var stopRotate = jitteredTimer(function () {
      rotateKey(ROTATE_MIN_SECONDS, null);
    }, ROTATE_INTERVAL_MS, HTTP_JITTER_MS);

    var stopKeyWatch = jitteredTimer(function () {
      if (captchaSignal(document)) return;
      postRecentPreviews(document, false);
      var pair = settings();
      if (!pair.host || !pair.master) return;
      fetch(keyUrl(pair.host, pair.master))
        .then(function (r) {
          return r.ok ? r.json() : null;
        })
        .then(function (body) {
          var key = keyChanged(heldKey, agentKeyFrom(body));
          if (key) {
            heldKey = key;
            keyTried = true;
            noteKey(key, pair.host, "replaced");
            if (isComposerUrl(location.href) && readSlug(document)) {
              sync();
            }
          }
          postKeyToPreview(true);
        })
        .catch(function () {});
    }, KEY_WATCH_MS, HTTP_JITTER_MS);

    var lastSlug = null;
    var filledSlug = null;

    function sync() {
      if (captchaSignal(document)) return;
      postKeyToPreview(false);
      if (!isComposerUrl(location.href)) {
        lastSlug = null;
        filledSlug = null;
        return;
      }
      var slug = readSlug(document);
      if (!slug) {
        logEvent("fill", "no-repo", null, "debug");
        var emptyComposer = document.querySelector(COMPOSER_SELECTOR);
        if (emptyComposer && emptyComposer.getAttribute("aria-disabled") !== "true") {
          var emptyText = String(emptyComposer.innerText || "").trim();
          if (emptyText && TEMPLATE_RE.test(emptyText)) {
            setComposerText(emptyComposer, "");
          }
        }
        lastSlug = null;
        return;
      }
      rememberSlug(slug);
      if (!promptResourcesTried) {
        ensureFetch();
        ensureAgentKey();
        return;
      }
      var composer = document.querySelector(COMPOSER_SELECTOR);
      if (!composer || composer.getAttribute("aria-disabled") === "true") {
        logEvent("fill", "no-composer", { repo: slug }, "debug");
        lastSlug = slug;
        return;
      }
      var current = composer.innerText || "";
      if (!shouldWrite(current, slug, lastSlug, filledSlug)) {
        lastSlug = slug;
        ensureFetch();
        ensureAgentKey();
        return;
      }
      var prompt = promptForSlug(slug, promptFillCache, arenaMdCache);
      if (!prompt) {
        logEvent("fill", "no-template", null, "warn");
        lastSlug = slug;
        ensureAgentKey();
        return;
      }
      setComposerText(composer, prompt);
      logEvent("fill", "filled", { repo: slug });
      lastSlug = slug;
      filledSlug = slug;
      ensureAgentKey();
    }

    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["src", "href"],
    });
    window.addEventListener("popstate", sync);
    sync();
    return function () {
      observer.disconnect();
      window.removeEventListener("popstate", sync);
      stopRotate();
      stopKeyWatch();
      for (var m = 0; m < proxyMenus.length; m += 1) {
        menuDrop(proxyMenus[m]);
      }
    };
  });

  runFeature("open-steering", "Steering - open", function () {

    var STEERING_LABEL_RE = /steering|preview/i;
    var CLICK_DELAY_MS = 1000;

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

    function steeringLabelViolation(label, expectedSlug) {
      var name = String(label || "").replace(/\s*:8000\s*$/, "").trim();
      if (!name || /^start\b/i.test(name)) {
        return null;
      }
      var slug = String(expectedSlug || "").trim();
      if (slug) {
        var expected = slug + " - Steering";
        if (name === expected) {
          return null;
        }
        return {
          actual: name,
          expected: expected,
          note:
            'Port 8000 preview process is named "' +
            name +
            '" instead of "' +
            expected +
            '" (ARENA.md requires "<repo> - Steering").',
        };
      }
      if (/^[A-Za-z0-9][A-Za-z0-9._-]* - Steering$/.test(name)) {
        return null;
      }
      return {
        actual: name,
        expected: "<repo> - Steering",
        note:
          'Port 8000 preview process is named "' +
          name +
          '" instead of "<repo> - Steering" (ARENA.md requires "<repo> - Steering").',
      };
    }

    function interruptPayloadForSteering(label, expectedSlug) {
      var violation = steeringLabelViolation(label, expectedSlug);
      if (!violation) {
        return null;
      }
      return {
        armed: true,
        tab: "notes",
        report_id: null,
        reason: "process-violation",
        clause_file: "ARENA.md",
        note: violation.note,
      };
    }

    var flaggedSteeringKey = null;
    var flaggingSteeringKey = null;

    function steeringPreviewBase(doc) {
      if (!doc || typeof doc.querySelectorAll !== "function") return null;
      var frames = doc.querySelectorAll("iframe[title]");
      var i;
      var title;
      for (i = 0; i < frames.length; i += 1) {
        title =
          (frames[i].getAttribute && frames[i].getAttribute("title")) ||
          frames[i].title ||
          "";
        if (title.indexOf("App preview on port 8000") === 0 && frames[i].src) {
          return String(frames[i].src).replace(/\/+$/, "");
        }
      }
      return null;
    }

    function sendSteeringInterrupt(url, payload, done) {
      if (typeof GM_xmlhttpRequest === "function") {
        GM_xmlhttpRequest({
          method: "POST",
          url: url,
          headers: { "Content-Type": "application/json" },
          data: JSON.stringify(payload),
          onload: function (answer) {
            done(answer && answer.status ? answer.status : 0);
          },
          onerror: function () {
            done(0);
          },
        });
        return;
      }
      if (typeof fetch === "function") {
        fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
          .then(function (r) {
            done(r && r.status ? r.status : 0);
          })
          .catch(function () {
            done(0);
          });
        return;
      }
      done(0);
    }

    function flagSteeringLabelViolation(doc, expectedSlug, sender) {
      var slug =
        expectedSlug !== undefined
          ? expectedSlug
          : previewUiRepo || readSlug(doc) || recalledSlug();
      var button = findSteeringButton(doc, slug);
      if (!button) {
        return false;
      }
      var payload = interruptPayloadForSteering(button.textContent, slug);
      if (!payload) {
        return false;
      }
      var base = steeringPreviewBase(doc);
      if (!base) {
        return false;
      }
      var key = base + "|" + payload.note;
      if (flaggedSteeringKey === key || flaggingSteeringKey === key) {
        return false;
      }
      flaggingSteeringKey = key;
      var post = typeof sender === "function" ? sender : sendSteeringInterrupt;
      post(base + "/api/agent-interrupt", payload, function (status) {
        if (flaggingSteeringKey === key) {
          flaggingSteeringKey = null;
        }
        if (status >= 200 && status < 300) {
          flaggedSteeringKey = key;
          logEvent("steering", "flagged-name", null, "warn");
        }
      });
      return true;
    }

    if (exposeChecks("openSteering", {
      isSessionUrl: isSessionUrl,
      slugFromOwnerRepo: slugFromOwnerRepo,
      steeringSlugFromLabel: steeringSlugFromLabel,
      isSteeringLabel: isSteeringLabel,
      isSteeringPort: isSteeringPort,
      buttonMatchesSteering: buttonMatchesSteering,
      findSteeringButton: findSteeringButton,
      steeringLabelViolation: steeringLabelViolation,
      interruptPayloadForSteering: interruptPayloadForSteering,
      flagSteeringLabelViolation: flagSteeringLabelViolation,
      resetFlaggedSteering: function () {
        flaggedSteeringKey = null;
        flaggingSteeringKey = null;
      },
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
      if (captchaSignal(document)) return;
      if (!isSessionUrl(location.href) || location.pathname !== path) {
        return;
      }
      if (clickedPath === path) {
        return;
      }
      var slug = previewUiRepo || readSlug(document) || recalledSlug();
      var button = findSteeringButton(document, slug);
      if (!button) {
        return;
      }
      button.click();
      clickedPath = path;
      flagSteeringLabelViolation(document, slug);
    }

    function parseSteeringButton(button) {
      if (/switch preview port/i.test(String(button.getAttribute && button.getAttribute("aria-label")))) {
        return null;
      }
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
      var slug = previewUiRepo || readSlug(document) || recalledSlug();
      flagSteeringLabelViolation(document, slug);
      if (clickedPath === location.pathname) {
        return;
      }
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
      attributes: true,
      attributeFilter: ["src", "title"],
    });
    window.addEventListener("popstate", sync);
    sync();
    return function () {
      observer.disconnect();
      window.removeEventListener("popstate", sync);
      clearClickTimer();
    };
  });

  runFeature("preview-sandbox", "Steering - new tabs and downloads", function () {
    var FRAME_TITLE = "App preview on port 8000";
    var FRAME_FLAGS = [
      "allow-popups",
      "allow-popups-to-escape-sandbox",
      "allow-downloads",
    ];

    function previewFrame(doc) {
      var frames = doc.querySelectorAll("iframe[title]");
      for (var i = 0; i < frames.length; i += 1) {
        if ((frames[i].getAttribute("title") || "").indexOf(FRAME_TITLE) === 0) {
          return frames[i];
        }
      }
      return null;
    }

    function grantFlags(frame) {
      var current = frame && frame.getAttribute("sandbox");
      if (!current) return false;
      var tokens = current.split(/\s+/).filter(Boolean);
      var added = false;
      for (var i = 0; i < FRAME_FLAGS.length; i += 1) {
        if (tokens.indexOf(FRAME_FLAGS[i]) === -1) {
          tokens.push(FRAME_FLAGS[i]);
          added = true;
        }
      }
      if (added) frame.setAttribute("sandbox", tokens.join(" "));
      return added;
    }

    function sync() {
      grantFlags(previewFrame(document));
    }

    if (exposeChecks("previewSandbox", {
      previewFrame: previewFrame,
      grantFlags: grantFlags,
      FRAME_FLAGS: FRAME_FLAGS,
    })) {
      return;
    }

    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["sandbox"],
    });
    sync();
    return function () {
      observer.disconnect();
    };
  });

  var AUTO_TOGGLE_MARK = "data-clankers-autoscroll-toggle";
  var SETTINGS_TOGGLE_MARK = "data-clankers-settings-toggle";
  var SETTINGS_DRAG_MARK = "data-clankers-settings-drag";
  var SETTINGS_MODAL_ID = "clankers-settings-modal";
  var AUTO_TOGGLE_CLASS =
    "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ring-offset-2 focus-visible:ring-offset-surface-primary disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 h-8 w-8 active:bg-interactive-cta-active rounded-[4px] font-normal touch-hitbox border-border-medium border text-text-primary";

  function autoToggleClasses(on) {
    return (
      AUTO_TOGGLE_CLASS +
      (on
        ? " bg-surface-raised hover:bg-interactive-cta-active"
        : " bg-transparent hover:bg-surface-raised")
    );
  }

  var autoToggleButton = null;
  var settingsToggleButton = null;
  var settingsModalNode = null;
  var notifyPreviewReadyHook = null;

  function setToggleButtonPressed() {
    if (!autoToggleButton) return;
    autoToggleButton.className = autoToggleClasses(autoScroll.isOn());
    autoToggleButton.setAttribute("aria-pressed", autoScroll.isOn() ? "true" : "false");
  }

  function isSettingsModalOpen() {
    if (!settingsModalNode) return false;
    return settingsModalNode.isConnected !== false;
  }

  function setSettingsButtonPressed() {
    if (!settingsToggleButton) return;
    var open = isSettingsModalOpen();
    settingsToggleButton.className = autoToggleClasses(open);
    settingsToggleButton.setAttribute("aria-pressed", open ? "true" : "false");
  }

  var autoScroll = runFeature("auto-scroll", "Transcript - auto-scroll", function () {
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
      findComposerActionButton: findComposerActionButton,
    })) {
      return;
    }

    function createLucideIcon(name, shapes) {
      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "lucide lucide-" + name);
      svg.setAttribute("width", "16");
      svg.setAttribute("height", "16");
      svg.setAttribute("viewBox", "0 0 24 24");
      svg.setAttribute("fill", "none");
      svg.setAttribute("stroke", "currentColor");
      svg.setAttribute("stroke-width", "2");
      svg.setAttribute("stroke-linecap", "round");
      svg.setAttribute("stroke-linejoin", "round");
      svg.setAttribute("aria-hidden", "true");
      svg.setAttribute("focusable", "false");
      var i;
      for (i = 0; i < shapes.length; i += 1) {
        var entry = shapes[i];
        var tag = typeof entry === "string" ? "path" : entry[0];
        var attrs = typeof entry === "string" ? { d: entry } : entry[1];
        var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
        var keys = Object.keys(attrs);
        for (var k = 0; k < keys.length; k += 1) {
          node.setAttribute(keys[k], attrs[keys[k]]);
        }
        svg.appendChild(node);
      }
      return svg;
    }

    function createButton() {
      var button = document.createElement("button");
      button.type = "button";
      button.setAttribute(AUTO_TOGGLE_MARK, "true");
      button.setAttribute("aria-label", "Toggle transcript autoscroll");
      button.setAttribute("title", "Toggle transcript autoscroll");
      autoToggleButton = button;
      setToggleButtonPressed();
      button.appendChild(
        createLucideIcon("arrow-down-to-line", [
          "M12 17V3",
          "m6 11 6 6 6-6",
          "M19 21H5",
        ]),
      );
      button.addEventListener("click", function () {
        autoScroll.toggle();
      });
      return button;
    }

    function closeSettingsModal() {
      if (settingsModalNode) {
        if (typeof settingsModalNode.remove === "function") {
          settingsModalNode.remove();
        } else if (settingsModalNode.parentNode) {
          settingsModalNode.parentNode.removeChild(settingsModalNode);
        }
        settingsModalNode = null;
      }
      setSettingsButtonPressed();
    }

    function ensureDualSliderStyle() {
      var styleId = "clankers-settings-slider-style";
      if (!document.head || typeof document.createElement !== "function") return;
      if (typeof document.getElementById === "function" && document.getElementById(styleId)) return;
      var style = document.createElement("style");
      style.id = styleId;
      style.setAttribute("id", styleId);
      style.textContent =
        "#clankers-settings-modal [data-dual-slider=\"true\"]{position:relative;height:20px;display:flex;align-items:center}" +
        "#clankers-settings-modal [data-dual-slider=\"true\"] input[type=\"range\"]{position:absolute;left:0;top:0;width:100%;height:100%;margin:0;padding:0;background:transparent;pointer-events:none;-webkit-appearance:none;appearance:none;accent-color:#d97757}" +
        "#clankers-settings-modal [data-dual-slider=\"true\"] input[type=\"range\"]::-webkit-slider-runnable-track{background:transparent;height:6px}" +
        "#clankers-settings-modal [data-dual-slider=\"true\"] input[type=\"range\"]::-moz-range-track{background:transparent;height:6px}" +
        "#clankers-settings-modal [data-dual-slider=\"true\"] input[type=\"range\"]::-webkit-slider-thumb{pointer-events:auto;-webkit-appearance:none;appearance:none;width:14px;height:14px;border-radius:50%;background:#d97757;border:1px solid #201f1d;cursor:pointer;margin-top:-4px}" +
        "#clankers-settings-modal [data-dual-slider=\"true\"] input[type=\"range\"]::-moz-range-thumb{pointer-events:auto;width:14px;height:14px;border-radius:50%;background:#d97757;border:1px solid #201f1d;cursor:pointer}";
      document.head.appendChild(style);
    }

    function openSettingsModal() {
      if (!document.body || typeof document.createElement !== "function") return;
      closeSettingsModal();
      ensureDualSliderStyle();
      var modal = document.createElement("div");
      modal.id = SETTINGS_MODAL_ID;
      modal.setAttribute("id", SETTINGS_MODAL_ID);
      modal.setAttribute("role", "dialog");
      modal.setAttribute("aria-label", "NemoUtils settings");
      modal.style.cssText =
        "position:fixed;right:16px;top:56px;z-index:2147483646;width:360px;max-height:78vh;" +
        "display:flex;flex-direction:column;border-radius:10px;background:#201f1d;color:#f0ede8;" +
        "font:12px/1.4 system-ui,-apple-system,sans-serif;" +
        "box-shadow:0 10px 32px rgba(0,0,0,.45);border:1px solid #56504a;overflow:hidden";

      var header = document.createElement("div");
      header.setAttribute(SETTINGS_DRAG_MARK, "true");
      header.style.cssText =
        "display:flex;align-items:center;justify-content:space-between;padding:10px 12px;" +
        "background:#2c2b28;border-bottom:1px solid #56504a;cursor:move;user-select:none;font-weight:600";
      var title = document.createElement("span");
      title.textContent = "NemoUtils Settings";
      header.appendChild(title);

      var closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.setAttribute("data-clankers-settings-close", "true");
      closeBtn.setAttribute("aria-label", "Close settings");
      closeBtn.setAttribute("title", "Close settings");
      closeBtn.style.cssText =
        "cursor:pointer;display:inline-flex;align-items:center;justify-content:center;" +
        "border:1px solid #56504a;border-radius:5px;padding:3px;width:24px;height:24px;" +
        "background:transparent;color:inherit;font:inherit";
      closeBtn.appendChild(createLucideIcon("x", ["M18 6 6 18", "m6 6 12 12"]));
      closeBtn.addEventListener("click", closeSettingsModal);
      header.appendChild(closeBtn);

      header.addEventListener("mousedown", function (event) {
        if (event && typeof event.button === "number" && event.button !== 0) return;
        if (!settingsModalNode) return;
        if (event && typeof event.preventDefault === "function") event.preventDefault();
        var rect =
          typeof settingsModalNode.getBoundingClientRect === "function"
            ? settingsModalNode.getBoundingClientRect()
            : { left: 240, top: 56 };
        var startX = Number(event && event.clientX) || 0;
        var startY = Number(event && event.clientY) || 0;
        var baseLeft = Number(rect.left) || 0;
        var baseTop = Number(rect.top) || 0;

        function onMove(moveEvent) {
          if (!settingsModalNode) return;
          var dx = (Number(moveEvent && moveEvent.clientX) || 0) - startX;
          var dy = (Number(moveEvent && moveEvent.clientY) || 0) - startY;
          var maxLeft = Math.max(0, (Number(window.innerWidth) || 1280) - 120);
          var maxTop = Math.max(0, (Number(window.innerHeight) || 800) - 48);
          var nextLeft = Math.min(Math.max(0, Math.round(baseLeft + dx)), maxLeft);
          var nextTop = Math.min(Math.max(0, Math.round(baseTop + dy)), maxTop);
          settingsModalNode.style.right = "auto";
          settingsModalNode.style.left = nextLeft + "px";
          settingsModalNode.style.top = nextTop + "px";
        }

        function onUp() {
          window.removeEventListener("mousemove", onMove);
          window.removeEventListener("mouseup", onUp);
        }

        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
      });
      modal.appendChild(header);

      var body = document.createElement("div");
      body.style.cssText = "padding:10px 12px;overflow-y:auto;display:flex;flex-direction:column;gap:12px";

      var sectionMap = {};
      function addSectionItem(sectionName, sortLabel, node) {
        if (!sectionMap[sectionName]) sectionMap[sectionName] = [];
        sectionMap[sectionName].push({ label: sortLabel, node: node });
      }

      function buildNumberRow(labelText, key, currentSeconds, minSec, maxSec, scale, onSaved) {
        var row = document.createElement("label");
        row.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:8px";
        var span = document.createElement("span");
        span.textContent = labelText;
        var input = document.createElement("input");
        input.type = "number";
        input.value = String(currentSeconds);
        input.setAttribute("data-setting-key", key);
        input.style.cssText =
          "width:72px;padding:3px 6px;border-radius:5px;border:1px solid #56504a;" +
          "background:#2c2b28;color:#f0ede8;font:inherit";
        input.addEventListener("change", function () {
          var raw = Number(String(input.value).trim());
          if (!isFinite(raw) || raw < minSec) return;
          var clamped = Math.min(Math.round(raw), maxSec);
          input.value = String(clamped);
          GM_setValue(key, clamped * scale);
          menuRefresh();
          if (typeof onSaved === "function") onSaved();
        });
        row.appendChild(span);
        row.appendChild(input);
        return row;
      }

      function buildDualRangeRow(labelText, minKey, maxKey, curMinSec, curMaxSec, minSec, maxSec, scale) {
        var box = document.createElement("div");
        box.style.cssText = "display:flex;flex-direction:column;gap:4px";
        var topRow = document.createElement("div");
        topRow.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:8px";
        var span = document.createElement("span");
        span.textContent = labelText;
        var readout = document.createElement("span");
        readout.style.cssText = "font-variant-numeric:tabular-nums;color:#b8b2a8";
        topRow.appendChild(span);
        topRow.appendChild(readout);

        var track = document.createElement("div");
        track.setAttribute("data-dual-slider", "true");
        track.style.cssText = "position:relative;height:20px;display:flex;align-items:center";
        var rail = document.createElement("div");
        rail.setAttribute("data-slider-rail", "true");
        rail.style.cssText =
          "position:absolute;left:0;right:0;height:6px;border-radius:999px;" +
          "background:#2c2b28;border:1px solid #56504a;overflow:hidden;pointer-events:none";
        var fill = document.createElement("div");
        fill.setAttribute("data-slider-fill", "true");
        fill.style.cssText =
          "position:absolute;top:0;bottom:0;background:#d97757;border-radius:999px";
        var ticks = document.createElement("div");
        ticks.setAttribute("data-slider-ticks", "true");
        ticks.style.cssText =
          "position:absolute;inset:0;display:flex;align-items:center;justify-content:space-between;padding:0 6px;pointer-events:none";
        var listId = "clankers-snap-" + minKey;
        var datalist = document.createElement("datalist");
        datalist.id = listId;
        datalist.setAttribute("id", listId);
        for (var s = minSec; s <= maxSec; s += 1) {
          var opt = document.createElement("option");
          opt.value = String(s);
          opt.setAttribute("value", String(s));
          datalist.appendChild(opt);
          var tick = document.createElement("span");
          tick.setAttribute("data-snap-point", String(s));
          tick.style.cssText =
            "width:2px;height:2px;border-radius:50%;background:rgba(240,237,232,.35)";
          ticks.appendChild(tick);
        }
        rail.appendChild(fill);
        rail.appendChild(ticks);

        var minInput = document.createElement("input");
        minInput.type = "range";
        minInput.min = String(minSec);
        minInput.max = String(maxSec);
        minInput.step = "1";
        minInput.value = String(curMinSec);
        minInput.setAttribute("list", listId);
        minInput.setAttribute("data-setting-key", minKey);
        minInput.setAttribute("data-range-role", "min");
        minInput.setAttribute("aria-label", labelText + " min");
        minInput.style.cssText =
          "position:absolute;left:0;top:0;width:100%;height:100%;margin:0;background:transparent;" +
          "pointer-events:none;accent-color:#d97757;z-index:2";

        var maxInput = document.createElement("input");
        maxInput.type = "range";
        maxInput.min = String(minSec);
        maxInput.max = String(maxSec);
        maxInput.step = "1";
        maxInput.value = String(curMaxSec);
        maxInput.setAttribute("list", listId);
        maxInput.setAttribute("data-setting-key", maxKey);
        maxInput.setAttribute("data-range-role", "max");
        maxInput.setAttribute("aria-label", labelText + " max");
        maxInput.style.cssText =
          "position:absolute;left:0;top:0;width:100%;height:100%;margin:0;background:transparent;" +
          "pointer-events:none;accent-color:#d97757;z-index:3";

        function updateReadout(lo, hi) {
          readout.textContent = lo + " - " + hi + " s";
          var spanSec = Math.max(1, maxSec - minSec);
          var leftPct = Math.min(100, Math.max(0, ((lo - minSec) / spanSec) * 100));
          var rightPct = Math.min(100, Math.max(leftPct, ((hi - minSec) / spanSec) * 100));
          fill.style.left = leftPct + "%";
          fill.style.width = Math.max(0, rightPct - leftPct) + "%";
          minInput.style.zIndex = lo >= maxSec - 1 ? "4" : "2";
        }
        updateReadout(curMinSec, curMaxSec);

        function applyMin() {
          var rawMin = Number(String(minInput.value).trim());
          var rawMax = Number(String(maxInput.value).trim());
          if (!isFinite(rawMin)) return;
          var lo = Math.min(Math.max(Math.round(rawMin), minSec), maxSec);
          var hi = isFinite(rawMax) ? Math.min(Math.max(Math.round(rawMax), minSec), maxSec) : maxSec;
          if (lo > hi) {
            hi = lo;
            maxInput.value = String(hi);
            GM_setValue(maxKey, hi * scale);
          }
          minInput.value = String(lo);
          GM_setValue(minKey, lo * scale);
          updateReadout(lo, hi);
          menuRefresh();
        }

        function applyMax() {
          var rawMin = Number(String(minInput.value).trim());
          var rawMax = Number(String(maxInput.value).trim());
          if (!isFinite(rawMax)) return;
          var hi = Math.min(Math.max(Math.round(rawMax), minSec), maxSec);
          var lo = isFinite(rawMin) ? Math.min(Math.max(Math.round(rawMin), minSec), maxSec) : minSec;
          if (hi < lo) {
            lo = hi;
            minInput.value = String(lo);
            GM_setValue(minKey, lo * scale);
          }
          maxInput.value = String(hi);
          GM_setValue(maxKey, hi * scale);
          updateReadout(lo, hi);
          menuRefresh();
        }

        minInput.addEventListener("input", applyMin);
        minInput.addEventListener("change", applyMin);
        maxInput.addEventListener("input", applyMax);
        maxInput.addEventListener("change", applyMax);

        track.appendChild(rail);
        track.appendChild(minInput);
        track.appendChild(maxInput);
        track.appendChild(datalist);
        box.appendChild(topRow);
        box.appendChild(track);
        return box;
      }

      var dependentNodes = [];
      function addDependentSectionItem(sectionName, sortLabel, node, depKey) {
        if (depKey) {
          node.setAttribute("data-depends-on", depKey);
          dependentNodes.push({ node: node, key: depKey, display: node.style.display || "flex" });
        }
        addSectionItem(sectionName, sortLabel, node);
      }

      function featureStoredOn(key) {
        for (var f = 0; f < featureRegistry.length; f += 1) {
          if (featureRegistry[f].key === key) return featureRegistry[f].storedOn();
        }
        return true;
      }

      function syncDependentVisibility() {
        for (var d = 0; d < dependentNodes.length; d += 1) {
          var item = dependentNodes[d];
          var on = featureStoredOn(item.key);
          item.node.hidden = !on;
          item.node.style.display = on ? item.display : "none";
        }
      }
      syncSettingsModalVisibilityHook = syncDependentVisibility;

      function buildTextRow(labelText, key, placeholder, onSaved, inputType) {
        var row = document.createElement("label");
        row.style.cssText =
          "display:flex;align-items:center;justify-content:space-between;gap:8px";
        var span = document.createElement("span");
        span.textContent = labelText;
        var input = document.createElement("input");
        input.type = inputType || "text";
        input.value = String(GM_getValue(key, "") || "");
        if (placeholder) input.placeholder = placeholder;
        input.setAttribute("data-setting-key", key);
        input.style.cssText =
          "width:160px;padding:3px 6px;border-radius:5px;border:1px solid #56504a;" +
          "background:#2c2b28;color:#f0ede8;font:inherit";
        input.addEventListener("change", function () {
          GM_setValue(key, String(input.value || "").trim());
          menuRefresh();
          if (typeof onSaved === "function") onSaved();
        });
        row.appendChild(span);
        row.appendChild(input);
        return row;
      }

      function buildCheckboxRow(labelText, key, checkedVal, onSaved) {
        var row = document.createElement("label");
        row.style.cssText =
          "display:flex;align-items:center;justify-content:space-between;gap:8px";
        var span = document.createElement("span");
        span.textContent = labelText;
        var checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = Boolean(checkedVal);
        checkbox.setAttribute("data-setting-key", key);
        checkbox.addEventListener("change", function () {
          if (typeof onSaved === "function") onSaved(Boolean(checkbox.checked));
        });
        row.appendChild(span);
        row.appendChild(checkbox);
        return row;
      }

      function buildActionRow(labelText, buttonLabel, actionId, onPress) {
        var row = document.createElement("div");
        row.style.cssText =
          "display:flex;align-items:center;justify-content:space-between;gap:8px";
        var span = document.createElement("span");
        span.textContent = labelText;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = buttonLabel;
        btn.setAttribute("data-settings-action", actionId);
        btn.style.cssText =
          "cursor:pointer;padding:3px 8px;border-radius:5px;border:1px solid #56504a;" +
          "background:#2c2b28;color:#f0ede8;font:inherit";
        btn.addEventListener("click", function () {
          if (typeof onPress === "function") onPress();
        });
        row.appendChild(span);
        row.appendChild(btn);
        return row;
      }

      var wakeRange = wakeDelayRangeMs();
      addDependentSectionItem(
        "Composer",
        "Wake-up delay (s)",
        buildDualRangeRow(
          "Wake-up delay (s)",
          WAKE_DELAY_MIN_KEY,
          WAKE_DELAY_KEY,
          Math.round(wakeRange.min / 1000),
          Math.round(wakeRange.max / 1000),
          0,
          60,
          1000,
        ),
        "auto-wake",
      );
      var keepRange = keepWorkingDelayRangeMs();
      addDependentSectionItem(
        "Composer",
        "Keep working delay (s)",
        buildDualRangeRow(
          "Keep working delay (s)",
          KEEP_WORKING_DELAY_MIN_KEY,
          KEEP_WORKING_DELAY_KEY,
          Math.round(keepRange.min / 1000),
          Math.round(keepRange.max / 1000),
          0,
          60,
          1000,
        ),
        "keep-working",
      );
      addDependentSectionItem(
        "State",
        "State autosave poll (s)",
        buildNumberRow(
          "State autosave poll (s)",
          STATE_WATCH_KEY,
          Math.round(stateWatchMs() / 1000),
          1,
          60,
          1000,
          function () {
            if (typeof restartStateWatchHook === "function") restartStateWatchHook();
          },
        ),
        "state-download",
      );
      addDependentSectionItem(
        "State",
        "State toast duration (s)",
        buildNumberRow(
          "State toast duration (s)",
          STATE_PANEL_KEY,
          Math.round(statePanelMs() / 1000),
          1,
          60,
          1000,
        ),
        "state-download",
      );
      addDependentSectionItem(
        "State",
        "reset-window overwrite",
        buildCheckboxRow(
          "reset-window overwrite",
          "clankers-arena-state-reset-window",
          GM_getValue("clankers-arena-state-reset-window", true) !== false,
          function (next) {
            if (typeof setResetWindowHook === "function") {
              setResetWindowHook(next);
            } else {
              GM_setValue("clankers-arena-state-reset-window", next);
              menuRefresh();
            }
          },
        ),
        "state-download",
      );
      addDependentSectionItem(
        "State",
        "Choose state file",
        buildActionRow("State file", "Choose file", "choose-state-file", function () {
          if (typeof chooseStateFileHook === "function") chooseStateFileHook();
        }),
        "state-download",
      );
      addDependentSectionItem(
        "State",
        "Force save state",
        buildActionRow("Force save", "Force save", "force-save", function () {
          if (typeof forceSaveStateHook === "function") forceSaveStateHook();
        }),
        "state-download",
      );
      addDependentSectionItem(
        "Proxy",
        "HTTP jitter range (s)",
        buildNumberRow(
          "HTTP jitter range (s)",
          HTTP_JITTER_KEY,
          Math.round(httpJitterMs() / 1000),
          0,
          60,
          1000,
        ),
        "prompt-fill",
      );
      addDependentSectionItem(
        "Proxy",
        "Proxy host",
        buildTextRow(
          "Proxy host",
          "clankers-arena-proxy-host",
          "https://arena-proxy.<tailnet>.ts.net",
          function () {
            if (typeof syncProxySettingsHook === "function") syncProxySettingsHook();
          },
        ),
        "prompt-fill",
      );
      addDependentSectionItem(
        "Proxy",
        "Preview proxy host",
        buildTextRow(
          "Preview proxy host",
          "clankers-arena-preview-proxy-host",
          "https://arena-preview.<tailnet>.ts.net",
          function () {
            if (typeof syncPreviewProxyHook === "function") syncPreviewProxyHook();
          },
        ),
        "prompt-fill",
      );
      addDependentSectionItem(
        "Proxy",
        "Master key",
        buildTextRow(
          "Master key",
          "clankers-arena-proxy-master",
          "Master key",
          function () {
            if (typeof syncProxySettingsHook === "function") syncProxySettingsHook();
          },
          "password",
        ),
        "prompt-fill",
      );
      addDependentSectionItem(
        "Proxy",
        "Post key now",
        buildActionRow("Post key", "Post key now", "post-key-now", function () {
          if (typeof postKeyNowHook === "function") postKeyNowHook();
        }),
        "prompt-fill",
      );

      var curKeepRows = Number(String(GM_getValue("clankers-arena-trim-keep", "50")).trim());
      if (!isFinite(curKeepRows) || curKeepRows < 20) curKeepRows = 50;
      (function () {
        var row = document.createElement("label");
        row.style.cssText =
          "display:flex;align-items:center;justify-content:space-between;gap:8px";
        var span = document.createElement("span");
        span.textContent = "Keep rows";
        var input = document.createElement("input");
        input.type = "number";
        input.value = String(Math.round(curKeepRows));
        input.setAttribute("data-setting-key", "clankers-arena-trim-keep");
        input.style.cssText =
          "width:72px;padding:3px 6px;border-radius:5px;border:1px solid #56504a;" +
          "background:#2c2b28;color:#f0ede8;font:inherit";
        input.addEventListener("change", function () {
          var raw = Number(String(input.value).trim());
          if (!isFinite(raw) || raw < 20) return;
          var clamped = Math.min(Math.round(raw), 1000);
          input.value = String(clamped);
          GM_setValue("clankers-arena-trim-keep", String(clamped));
          if (typeof applyTrimKeepHook === "function") applyTrimKeepHook();
          menuRefresh();
        });
        row.appendChild(span);
        row.appendChild(input);
        addSectionItem("Transcript", "Keep rows", row);
      })();

      var curTrimCap = Number(GM_getValue("clankers-arena-trim-cap", 200));
      if (!isFinite(curTrimCap) || curTrimCap < 1) curTrimCap = 200;
      addSectionItem(
        "Transcript",
        "Trim cap (rows)",
        buildNumberRow(
          "Trim cap (rows)",
          "clankers-arena-trim-cap",
          Math.round(curTrimCap),
          1,
          1000,
          1,
          function () {
            if (typeof registerTrimCapHook === "function") registerTrimCapHook();
          },
        ),
      );
      var curTrimSec = Math.round(
        Math.min(Math.max(Number(GM_getValue("clankers-arena-trim-interval-ms", 5000)) || 5000, 1000), 60000) /
          1000,
      );
      addDependentSectionItem(
        "Transcript",
        "Auto trim interval (s)",
        buildNumberRow(
          "Auto trim interval (s)",
          "clankers-arena-trim-interval-ms",
          curTrimSec,
          1,
          60,
          1000,
          function () {
            if (typeof restartTrimTimerHook === "function") restartTrimTimerHook();
          },
        ),
        "transcript-trim",
      );
      addSectionItem(
        "Transcript",
        "Trim now",
        buildActionRow("Trim transcript", "Trim now", "trim-now", function () {
          if (typeof trimNowHook === "function") trimNowHook();
        }),
      );

      var curTitleSec = Math.round(
        Math.min(Math.max(Number(GM_getValue("clankers-arena-title-interval-ms", 1000)) || 1000, 1000), 60000) /
          1000,
      );
      addDependentSectionItem(
        "Page",
        "Tab title interval (s)",
        buildNumberRow(
          "Tab title interval (s)",
          "clankers-arena-title-interval-ms",
          curTitleSec,
          1,
          60,
          1000,
          function () {
            if (typeof restartTitleTimerHook === "function") restartTitleTimerHook();
          },
        ),
        "tab-title",
      );

      (function () {
        var row = document.createElement("label");
        row.style.cssText =
          "display:flex;align-items:center;justify-content:space-between;gap:8px";
        var span = document.createElement("span");
        span.textContent = "Log level";
        var sel = document.createElement("select");
        sel.setAttribute("data-setting-key", LOG_LEVEL_KEY);
        sel.style.cssText =
          "padding:3px 6px;border-radius:5px;border:1px solid #56504a;" +
          "background:#2c2b28;color:#f0ede8;font:inherit";
        for (var l = 0; l < LOG_LEVELS.length; l += 1) {
          var opt = document.createElement("option");
          opt.value = LOG_LEVELS[l];
          opt.setAttribute("value", LOG_LEVELS[l]);
          opt.textContent = LOG_LEVELS[l].toUpperCase();
          if (LOG_LEVELS[l] === getLogLevel()) {
            opt.selected = true;
            opt.setAttribute("selected", "selected");
          }
          sel.appendChild(opt);
        }
        sel.value = getLogLevel();
        sel.addEventListener("change", function () {
          if (setLogLevel(String(sel.value))) {
            logEvent("logging", "level", { level: String(sel.value) });
            menuRefresh();
          }
        });
        row.appendChild(span);
        row.appendChild(sel);
        addSectionItem("Userscript", "Log level", row);
      })();
      addSectionItem(
        "Userscript",
        "Pause all",
        buildCheckboxRow("Pause all", PAUSE_KEY, pauseStored(), function (next) {
          setPause(next);
        }),
      );
      addSectionItem(
        "Userscript",
        "Show settings button",
        buildCheckboxRow(
          "Show settings button",
          SHOW_SETTINGS_BUTTON_KEY,
          showSettingsButtonOn(),
          function (next) {
            setShowSettingsButton(next);
          },
        ),
      );

      var i;
      for (i = 0; i < featureRegistry.length; i += 1) {
        (function (item) {
          var parts = String(item.label).split(" - ");
          var secName = parts.length > 1 ? parts[0] : "General";
          var shortLabel = parts.length > 1 ? parts.slice(1).join(" - ") : item.label;
          var row = document.createElement("label");
          row.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:8px";
          var span = document.createElement("span");
          span.textContent = shortLabel;
          var checkbox = document.createElement("input");
          checkbox.type = "checkbox";
          checkbox.checked = item.storedOn();
          checkbox.setAttribute("data-setting-key", item.key);
          checkbox.addEventListener("change", function () {
            item.set(Boolean(checkbox.checked));
            syncDependentVisibility();
          });
          row.appendChild(span);
          row.appendChild(checkbox);
          addSectionItem(secName, shortLabel, row);
        })(featureRegistry[i]);
      }
      syncDependentVisibility();

      var sectionNames = Object.keys(sectionMap).sort(function (a, b) {
        return a.localeCompare(b);
      });
      for (var s = 0; s < sectionNames.length; s += 1) {
        var secKey = sectionNames[s];
        var secEl = document.createElement("section");
        secEl.setAttribute("data-settings-section", secKey);
        secEl.style.cssText =
          "display:flex;flex-direction:column;gap:6px;padding-bottom:8px;border-bottom:1px solid #3a3733";
        var secTitle = document.createElement("div");
        secTitle.textContent = secKey;
        secTitle.style.cssText =
          "font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#b8b2a8";
        secEl.appendChild(secTitle);
        var entries = sectionMap[secKey].slice().sort(function (a, b) {
          return a.label.localeCompare(b.label);
        });
        for (var e = 0; e < entries.length; e += 1) {
          secEl.appendChild(entries[e].node);
        }
        body.appendChild(secEl);
      }

      modal.appendChild(body);
      settingsModalNode = modal;
      document.body.appendChild(modal);
      setSettingsButtonPressed();
    }

    function toggleSettingsModal() {
      if (isSettingsModalOpen()) {
        closeSettingsModal();
      } else {
        openSettingsModal();
      }
    }

    function createSettingsButton() {
      var button = document.createElement("button");
      button.type = "button";
      button.setAttribute(SETTINGS_TOGGLE_MARK, "true");
      button.setAttribute("aria-label", "Toggle NemoUtils settings");
      button.setAttribute("title", "Toggle NemoUtils settings");
      settingsToggleButton = button;
      setSettingsButtonPressed();
      button.appendChild(
        createLucideIcon("settings", [
          "M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915",
          ["circle", { cx: "12", cy: "12", r: "3" }],
        ]),
      );
      button.addEventListener("click", function () {
        toggleSettingsModal();
      });
      return button;
    }

    function ensureButton() {
      if (typeof notifyPreviewReadyHook === "function") notifyPreviewReadyHook();
      var actionButton = findComposerActionButton(document);
      var row = actionButton && actionButton.parentElement;
      if (!row) return;
      var settingsBtn = row.querySelector("[" + SETTINGS_TOGGLE_MARK + "]");
      var autoBtn = row.querySelector("[" + AUTO_TOGGLE_MARK + "]");
      if (!showSettingsButtonOn()) {
        if (settingsBtn) {
          if (typeof settingsBtn.remove === "function") settingsBtn.remove();
          else if (settingsBtn.parentNode) settingsBtn.parentNode.removeChild(settingsBtn);
        }
        settingsToggleButton = null;
        closeSettingsModal();
        if (!autoBtn) {
          autoBtn = createButton();
          row.insertBefore(autoBtn, actionButton);
        }
        return;
      }
      if (!settingsBtn) {
        settingsBtn = createSettingsButton();
        row.insertBefore(settingsBtn, actionButton);
      }
      if (!autoBtn) {
        autoBtn = createButton();
        row.insertBefore(autoBtn, settingsBtn);
      }
    }
    syncSettingsButtonHook = ensureButton;

    var observer = new MutationObserver(ensureButton);

    function startButtonWatch() {
      observer.observe(document.documentElement, { childList: true, subtree: true });
      ensureButton();
    }

    function haltButtonWatch() {
      observer.disconnect();
    }

    if (!pauseStored()) startButtonWatch();
    registerPauseUnit("Transcript auto-scroll button", startButtonWatch, haltButtonWatch, function () {
      return true;
    });
  })();

  (function () {
    var KEEP_KEY = "clankers-arena-trim-keep";
    var DEFAULT_ROWS = 50;
    var MIN_ROWS = 20;
    var LOG_SELECTOR = '[role="log"]';
    var MESSAGE_SELECTOR = '[data-agent-transcript-message="true"]';
    var ROW_BOX_SELECTOR = "div.flex.flex-col.gap-2";
    var ACTION_SELECTOR = ":scope > div > div > div.mt-3.flex.flex-col.gap-3";
    var LIVE_ICON_SELECTOR = "svg.animate-pulse";
    var QUESTION_SELECTOR = '[role="radiogroup"]';
    var SETTLE_MS = 5000;
    var CAP_KEY = "clankers-arena-trim-cap";
    var DEFAULT_TRIM_CAP = 200;

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
        "Transcript - keep " +
        kept.rows +
        " rows" +
        (removed ? " (" + removed + " removed)" : "")
      );
    }

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

    function rowsOfRoot(root) {
      var boxes = root.querySelectorAll(ROW_BOX_SELECTOR);
      var rows = [];
      var i;
      for (i = 0; i < boxes.length; i += 1) {
        var parent = boxes[i].parentElement;
        var outer = parent && parent.closest(ROW_BOX_SELECTOR);
        if (outer && Array.prototype.indexOf.call(boxes, outer) !== -1) continue;
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

    function budgetRoot(roots) {
      var i;
      for (i = roots.length - 1; i >= 0; i -= 1) {
        if (roots[i].isConnected === false) continue;
        if (liveRowCount(roots[i])) return i;
      }
      return -1;
    }

    function liveRowCount(root) {
      var rows = rowsOfRoot(root);
      var count = 0;
      var i;
      for (i = 0; i < rows.length; i += 1) {
        if (rowLive(rows[i])) count += 1;
      }
      return count;
    }

    function trimPlan(doc, plan) {
      var roots = messageRoots(doc);
      var keep = planParts(plan).rows;
      var removed = 0;
      var holder = budgetRoot(roots);
      var i;
      for (i = roots.length - 1; i >= 0; i -= 1) {
        if (roots[i].isConnected === false) continue;
        var newest = i === holder;
        var rows = rowsOfRoot(roots[i]);
        var removedFromRoot = trimRows(rows, keep);
        removed += removedFromRoot;
        var attached = 0;
        var j;
        for (j = 0; j < rows.length; j += 1) {
          if (rowLive(rows[j])) attached += 1;
        }
        keep = Math.max(0, keep - attached);
        if (removedFromRoot && !attached) removeActionSibling(roots[i]);
        if (holder !== -1 && !newest && !attached && typeof roots[i].classList !== "undefined") {
          roots[i].classList.add("hidden");
        }
      }
      return removed;
    }

    function isSettled(doc) {
      if (!findStopGeneratingButton(doc)) return false;
      if (doc.querySelector(QUESTION_SELECTOR)) return false;
      return true;
    }

    function quietReady(state, count, now) {
      if (count !== state.rows) {
        state.rows = count;
        state.rowsAt = now;
        return false;
      }
      if (now - state.rowsAt < SETTLE_MS) return false;
      if (now - state.mutationAt < SETTLE_MS) return false;
      return true;
    }

    function rowLive(row) {
      if (!row.parentElement) return false;
      return !(
        row.classList &&
        typeof row.classList.contains === "function" &&
        row.classList.contains("hidden")
      );
    }

    function clearRow(row) {
      if (row.classList && typeof row.classList.add === "function") {
        row.classList.add("hidden");
      }
      row.textContent = "";
    }

    function capValue() {
      if (typeof GM_getValue !== "function") return DEFAULT_TRIM_CAP;
      var cap = Number(GM_getValue(CAP_KEY, DEFAULT_TRIM_CAP));
      return isFinite(cap) && cap >= 1 ? Math.round(cap) : DEFAULT_TRIM_CAP;
    }

    function trimRows(rows, keep) {
      var attached = 0;
      var excess = 0;
      var removed = 0;
      var i;
      for (i = 0; i < rows.length; i += 1) {
        if (rowLive(rows[i])) attached += 1;
      }
      excess = attached - keep;
      var cap = capValue();
      if (excess > cap) excess = cap;
      for (i = 0; i < rows.length && removed < excess; i += 1) {
        if (!rowLive(rows[i])) continue;
        clearRow(rows[i]);
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
      quietReady: quietReady,
      ACTION_SELECTOR: ACTION_SELECTOR,
      QUESTION_SELECTOR: QUESTION_SELECTOR,
      MIN_ROWS: MIN_ROWS,
      DEFAULT_ROWS: DEFAULT_ROWS,
      DEFAULT_TRIM_CAP: DEFAULT_TRIM_CAP,
    })) {
      return;
    }

    var countEntry = null;
    var nowEntry = null;
    var intervalEntry = null;
    var capEntry = null;
    var timer = null;
    var observer = null;
    var labelTimer = null;
    var trimmedTotal = 0;
    var settleState = { rows: null, rowsAt: 0, mutationAt: 0 };

    function attachedRowCount(doc) {
      var roots = messageRoots(doc);
      var total = 0;
      var i;
      for (i = 0; i < roots.length; i += 1) {
        if (roots[i].isConnected === false) continue;
        var rows = rowsOfRoot(roots[i]);
        var j;
        for (j = 0; j < rows.length; j += 1) {
          if (rowLive(rows[j])) total += 1;
        }
      }
      return total;
    }

    function keepPlan() {
      var stored = String(GM_getValue(KEEP_KEY, "") || "");
      var normalized = normalizePlan(stored);
      if (!normalized) return String(DEFAULT_ROWS);
      if (normalized !== stored) GM_setValue(KEEP_KEY, normalized);
      return normalized;
    }

    function registerCount() {
      if (countEntry !== null) menuDrop(countEntry);
      countEntry = menuAdd(function () {
        return countLabel(keepPlan(), trimmedTotal);
      }, setCount);
    }

    function refreshLabel() {
      if (labelTimer !== null) return;
      labelTimer = setTimeout(function () {
        labelTimer = null;
        registerCount();
      }, 1000);
    }

    var INTERVAL_KEY = "clankers-arena-trim-interval-ms";
    var MAX_TICK_MS = 60000;

    function tickMs() {
      var ms = Number(GM_getValue(INTERVAL_KEY, SETTLE_MS));
      if (!isFinite(ms) || ms < 1000) return SETTLE_MS;
      return Math.min(Math.round(ms), MAX_TICK_MS);
    }

    function intervalLabel() {
      return "Transcript - auto trim interval " + Math.round(tickMs() / 1000) + " s";
    }

    function restartTick() {
      if (timer !== null) clearInterval(timer);
      timer = setInterval(tick, tickMs());
    }

    function registerInterval() {
      if (intervalEntry !== null) menuDrop(intervalEntry);
      intervalEntry = menuAdd(intervalLabel, setTickByPrompt);
    }

    function capLabel() {
      return "Transcript - trim cap " + capValue() + " rows";
    }

    function registerCap() {
      if (capEntry !== null) menuDrop(capEntry);
      capEntry = menuAdd(capLabel, setCapByPrompt);
    }

    function setCapByPrompt() {
      if (typeof prompt !== "function") return;
      var answer = prompt("How many rows should each trim pass remove? Enter 1 to 1000.", String(capValue()));
      if (answer === null) {
        registerCap();
        return;
      }
      var rows = Number(String(answer).trim());
      if (!isFinite(rows) || rows < 1) {
        registerCap();
        return;
      }
      GM_setValue(CAP_KEY, Math.min(Math.round(rows), 1000));
      registerCap();
    }

    function setTickByPrompt() {
      if (typeof prompt !== "function") return;
      var answer = prompt("How often should auto trim run? Enter 1 to 60 seconds.", String(Math.round(tickMs() / 1000)));
      if (answer === null) {
        registerInterval();
        return;
      }
      var seconds = Number(String(answer).trim());
      if (!isFinite(seconds) || seconds < 1) {
        registerInterval();
        return;
      }
      GM_setValue(INTERVAL_KEY, Math.min(Math.round(seconds), 60) * 1000);
      restartTick();
      registerInterval();
    }

    function setCount() {
      if (typeof prompt !== "function") return;
      var answer = prompt("How many transcript rows should stay?", keepPlan());
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
      var keep = keepPlan();
      var removed = trimPlan(document, keep);
      if (removed) {
        trimmedTotal += removed;
        logEvent("trim", "removed", { removed: removed, kept: planParts(keep).rows });
        refreshLabel();
      }
      return removed;
    }

    function tick() {
      if (location.pathname.indexOf("/agent/") !== 0) return;
      if (!isSettled(document)) return;
      if (!quietReady(settleState, attachedRowCount(document), Date.now())) return;
      trim();
    }

    runFeature("transcript-trim", "Transcript - auto trim", function () {
      registerInterval();
      restartTrimTimerHook = function () {
        restartTick();
        registerInterval();
      };
      observer = new MutationObserver(function () {
        settleState.mutationAt = Date.now();
      });
      observer.observe(document.documentElement, { childList: true, subtree: true });
      timer = setInterval(tick, tickMs());
      return function () {
        restartTrimTimerHook = null;
        if (timer !== null) clearInterval(timer);
        timer = null;
        observer.disconnect();
        observer = null;
        if (intervalEntry !== null) {
          menuDrop(intervalEntry);
          intervalEntry = null;
        }
      };
    }, null, false);
    registerCount();
    registerCap();
    applyTrimKeepHook = function () {
      registerCount();
      trim();
    };
    registerTrimCapHook = registerCap;
    trimNowHook = trim;
    nowEntry = menuAdd(function () {
      return "Transcript - trim now";
    }, function () {
      trim();
    });
  })();

  runFeature("transcript-alerts", "Transcript - hide generation alerts", function () {

    function alertVisibility(doc) {
      var hidden = new Map();
      function hasHiddenStyle(node) {
        return node.style.getPropertyValue("display") === "none" && node.style.getPropertyPriority("display") === "important";
      }
      function restore(node, prior) {
        if (hasHiddenStyle(node)) {
          if (prior.value) node.style.setProperty("display", prior.value, prior.priority);
          else node.style.removeProperty("display");
        }
        hidden.delete(node);
      }
      return function (generating) {
        hidden.forEach(function (prior, node) {
          if (!generating || node.isConnected === false || !node.matches(GENERATION_ALERT_SELECTOR)) restore(node, prior);
          else if (!hasHiddenStyle(node)) hidden.delete(node);
        });
        if (!generating) return;
        var alerts = doc.querySelectorAll(GENERATION_ALERT_SELECTOR);
        for (var i = 0; i < alerts.length; i += 1) {
          var node = alerts[i];
          if (hidden.has(node) || node.isConnected === false || !renderedNode(node)) continue;
          hidden.set(node, {
            value: node.style.getPropertyValue("display"),
            priority: node.style.getPropertyPriority("display"),
          });
          node.style.setProperty("display", "none", "important");
        }
      };
    }

    if (exposeChecks("transcriptAlerts", { ALERT_SELECTOR: GENERATION_ALERT_SELECTOR, alertVisibility: alertVisibility })) return;
    var sync = alertVisibility(document);
    function update() {
      sync(Boolean(findStopGeneratingButton(document)));
    }
    var observer = new MutationObserver(update);
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["aria-label", "role", "class", "hidden", "style"],
    });
    update();
    return function () {
      observer.disconnect();
      sync(false);
    };
  });

  runFeature("hide-composer", "Composer - hide", function () {

    var SHELL_SELECTOR = "div.flex.w-full.flex-col.items-start.justify-center.p-2";
    var EDITOR_CONTENT_SELECTOR = "div.editor-content";
    var HIDE_MARK = "data-clankers-hidden";
    var TRANSCRIPT_COLUMN_SELECTOR =
      "div.flex.w-full.shrink-0.flex-col.gap-4.mx-auto.max-w-3xl.px-4.pt-14.md\\:pt-12";
    var SPACER_SELECTOR = 'div.shrink-0[style*="height: 24px"]';
    var SPACER_MARK = "data-clankers-spacer";
    var SPACER_STYLE_ID = "clankers-spacer-lock";
    var SPACER_HEIGHT = "24px";
    var TRANSCRIPT_COLUMN_CLASSES = [
      "flex",
      "w-full",
      "shrink-0",
      "flex-col",
      "gap-4",
      "mx-auto",
      "max-w-3xl",
      "px-4",
      "pt-14",
      "md:pt-12",
    ];
    var fixedSpacers = new WeakSet();
    var spacerStyles = new Map();
    var editorStates = new Map();

    function shouldHideComposer(session, stopGenerating) {
      return Boolean(session) && Boolean(stopGenerating);
    }

    function isSpacerElement(spacer) {
      return Boolean(
        spacer &&
          String(spacer.tagName || "").toLowerCase() === "div" &&
          spacer.classList &&
          spacer.classList.contains("shrink-0") &&
          !String(spacer.textContent || "").trim(),
      );
    }

    function isTranscriptColumn(node) {
      if (!node || String(node.tagName || "").toLowerCase() !== "div" || !node.classList) {
        return false;
      }
      for (var i = 0; i < TRANSCRIPT_COLUMN_CLASSES.length; i += 1) {
        if (!node.classList.contains(TRANSCRIPT_COLUMN_CLASSES[i])) {
          return false;
        }
      }
      return true;
    }

    function isSpacerSibling(spacer) {
      if (!isSpacerElement(spacer)) return false;
      var parent = spacer.parentElement || spacer.parentNode;
      if (!parent || !parent.children) return false;
      var siblings = parent.children;
      for (var i = 0; i < siblings.length; i += 1) {
        if (siblings[i] !== spacer && isTranscriptColumn(siblings[i])) {
          return true;
        }
      }
      return false;
    }

    function hasSpacerHeight(styleText) {
      return /(?:^|;)\s*height\s*:\s*24px\s*(?:!important\s*)?(?:;|$)/i.test(
        String(styleText || ""),
      );
    }

    function lockSpacerHeight(spacer) {
      fixedSpacers.add(spacer);
      if (typeof spacer.setAttribute === "function") {
        spacer.setAttribute(SPACER_MARK, "true");
      }
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
              isSpacerSibling(change.target) ||
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
      var matched = [];
      if (doc && typeof doc.querySelectorAll === "function") {
        try {
          var columns = doc.querySelectorAll(TRANSCRIPT_COLUMN_SELECTOR);
          for (i = 0; i < columns.length; i += 1) {
            var parent = columns[i].parentElement || columns[i].parentNode;
            if (!parent || !parent.children) continue;
            for (var j = 0; j < parent.children.length; j += 1) {
              var sib = parent.children[j];
              if (sib !== columns[i] && isSpacerElement(sib)) {
                matched.push(sib);
              }
            }
          }
        } catch (err) {}
        var shrinkNodes = doc.querySelectorAll("div.shrink-0");
        for (i = 0; i < shrinkNodes.length; i += 1) {
          if (isSpacerSibling(shrinkNodes[i])) {
            matched.push(shrinkNodes[i]);
          }
        }
        var spacers = doc.querySelectorAll(SPACER_SELECTOR);
        for (i = 0; i < spacers.length; i += 1) {
          if (
            fixedSpacers.has(spacers[i]) ||
            isSpacerSibling(spacers[i]) ||
            (isSpacerElement(spacers[i]) && hasSpacerHeight(spacers[i].getAttribute("style")))
          ) {
            matched.push(spacers[i]);
          }
        }
      }
      for (i = 0; i < matched.length; i += 1) {
        lockSpacerHeight(matched[i]);
      }
    }

    if (exposeChecks("hideComposer", {
      isSessionUrl: isSessionUrl,
      isStopGeneratingLabel: isStopGeneratingLabel,
      shouldHideComposer: shouldHideComposer,
      isSpacerElement: isSpacerElement,
      isSpacerSibling: isSpacerSibling,
      isTranscriptColumn: isTranscriptColumn,
      hasSpacerHeight: hasSpacerHeight,
      enforceSpacerHeight: enforceSpacerHeight,
      TRANSCRIPT_COLUMN_SELECTOR: TRANSCRIPT_COLUMN_SELECTOR,
      SPACER_SELECTOR: SPACER_SELECTOR,
      SPACER_HEIGHT: SPACER_HEIGHT,
    })) {
      return;
    }

    function ensureSpacerStyle() {
      if (!document.head || typeof document.createElement !== "function") return;
      if (typeof document.getElementById === "function" && document.getElementById(SPACER_STYLE_ID)) return;
      var style = document.createElement("style");
      style.id = SPACER_STYLE_ID;
      style.setAttribute("id", SPACER_STYLE_ID);
      style.textContent =
        TRANSCRIPT_COLUMN_SELECTOR + " ~ div.shrink-0," +
        "div[" + SPACER_MARK + "=\"true\"]{height:" + SPACER_HEIGHT + " !important}";
      document.head.appendChild(style);
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
        ensureSpacerStyle();
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
      if (typeof document.getElementById === "function") {
        var styleNode = document.getElementById(SPACER_STYLE_ID);
        if (styleNode) {
          if (typeof styleNode.remove === "function") styleNode.remove();
          else if (styleNode.parentNode) styleNode.parentNode.removeChild(styleNode);
        }
      }
      editorStates.forEach(function (_, editor) { showEditor(editor); });
      spacerStyles.forEach(function (prior, spacer) {
        if (typeof spacer.removeAttribute === "function") spacer.removeAttribute(SPACER_MARK);
        if (spacer.style.getPropertyValue("height") === SPACER_HEIGHT && spacer.style.getPropertyPriority("height") === "important") {
          if (prior[0]) spacer.style.setProperty("height", prior[0], prior[1]);
          else spacer.style.removeProperty("height");
        }
      });
      spacerStyles.clear();
    };
  });

  var KEEP_WORKING_SELECTOR =
    "div.divide-border-faint.border-border-faint.bg-surface-primary.mx-3.mb-3.divide-y.overflow-hidden.rounded-md.border > button:nth-child(3)";
  var SPINNER_ROW_HTML =
    '<div class="flex w-fit items-center justify-start gap-1.5"><div class="flex size-4 shrink-0 items-center justify-center"><div class="size-4"><canvas width="16" height="16" style="vertical-align: top; width: 16px; height: 16px;"></canvas></div></div></div>';

  function hasClassToken(node, name) {
    var raw =
      node && typeof node.className === "string"
        ? node.className
        : node && typeof node.getAttribute === "function"
          ? String(node.getAttribute("class") || "")
          : "";
    return (" " + raw + " ").indexOf(" " + name + " ") !== -1;
  }

  function firstElementOf(node) {
    if (!node) return null;
    if (node.firstElementChild) return node.firstElementChild;
    return node.children && node.children.length ? node.children[0] : null;
  }

  function childSteps(node, steps) {
    var current = node;
    for (var i = 0; i < steps; i += 1) {
      if (!current) return null;
      current = firstElementOf(current);
    }
    return current;
  }

  function messageRowContainer(root) {
    var node =
      root && typeof root.querySelector === "function"
        ? root.querySelector(":scope > div > div.px-3.pb-3 > div.flex.flex-col.gap-2")
        : null;
    node = node || childSteps(root, 3);
    if (
      node &&
      hasClassToken(node, "flex") &&
      hasClassToken(node, "flex-col") &&
      hasClassToken(node, "gap-2")
    ) {
      return node;
    }
    return root && root.children && root.children.length ? root : null;
  }

  function lastMessageRow(root) {
    var container = messageRowContainer(root);
    var kids = container && container.children ? container.children : [];
    for (var i = kids.length - 1; i >= 0; i -= 1) {
      var tag = kids[i] && kids[i].tagName ? String(kids[i].tagName).toUpperCase() : "DIV";
      if (tag === "DIV") return kids[i];
    }
    return null;
  }

  function isSpinnerRow(row) {
    if (!row) return false;
    if (String(row.outerHTML || "").trim() === SPINNER_ROW_HTML) return true;
    if (
      !hasClassToken(row, "flex") ||
      !hasClassToken(row, "w-fit") ||
      !hasClassToken(row, "items-center") ||
      !hasClassToken(row, "justify-start") ||
      !hasClassToken(row, "gap-1.5")
    ) {
      return false;
    }
    var outer = firstElementOf(row);
    if (
      !outer ||
      !hasClassToken(outer, "flex") ||
      !hasClassToken(outer, "size-4") ||
      !hasClassToken(outer, "shrink-0") ||
      !hasClassToken(outer, "items-center") ||
      !hasClassToken(outer, "justify-center")
    ) {
      return false;
    }
    var inner = firstElementOf(outer);
    if (!inner || !hasClassToken(inner, "size-4")) return false;
    var canvas = firstElementOf(inner);
    if (!canvas || String(canvas.tagName || "").toUpperCase() !== "CANVAS") return false;
    var w = typeof canvas.getAttribute === "function" ? canvas.getAttribute("width") : null;
    var h = typeof canvas.getAttribute === "function" ? canvas.getAttribute("height") : null;
    w = w !== null && w !== undefined ? w : canvas.width;
    h = h !== null && h !== undefined ? h : canvas.height;
    var style = String(
      (typeof canvas.getAttribute === "function" && canvas.getAttribute("style")) ||
        (canvas.style && canvas.style.cssText) ||
        "",
    );
    return (
      String(w || "") === "16" &&
      String(h || "") === "16" &&
      (style === "" ||
        (style.indexOf("vertical-align: top") !== -1 &&
          style.indexOf("width: 16px") !== -1 &&
          style.indexOf("height: 16px") !== -1))
    );
  }

  function keepWorkingButton(doc) {
    if (!doc || typeof doc.querySelector !== "function") return null;
    var button = doc.querySelector(KEEP_WORKING_SELECTOR);
    if (
      !button ||
      button.disabled ||
      (typeof button.getAttribute === "function" && button.getAttribute("aria-disabled") === "true") ||
      !renderedNode(button)
    ) {
      return null;
    }
    var label = String(button.textContent || button.innerText || "").replace(/\s+/g, " ").trim();
    if (label !== "Keep working") return null;
    return button;
  }

  var autoWakeSentFor = null;
  var autoWakeRoots = new Set();
  var autoWakeNotify = null;
  runFeature("auto-wake", "Composer - auto-send wake up", function () {
    if (typeof document === "undefined") return function () {};
    var timer = null;
    var timerFor = null;
    var composing = false;

    function cancel() {
      if (timer !== null) clearTimeout(timer);
      timer = null;
      timerFor = null;
    }

    function target() {
      var editor = document.querySelector('div.tiptap.ProseMirror[contenteditable="true"]');
      if (!editor) return null;
      if (String(editor.innerText || "") !== "wake up") autoWakeSentFor = null;
      if ((!isComposerUrl(location.href) && !isSessionUrl(location.href)) ||
          composing || captchaSignal(document) || !renderedNode(editor) ||
          editor.getAttribute("aria-disabled") === "true") return null;
      if (editor.textContent === "") {
        var message = lastMessageRoot(document);
        if (!message || !message.id || autoWakeRoots.has(message.id) ||
            !message.querySelector(GENERATION_ALERT_SELECTOR)) return null;
        autoWakeRoots.add(message.id);
        autoWakeSentFor = null;
        setComposerText(editor, "wake up");
        if (String(editor.innerText || "") === "wake up") logEvent("auto-wake", "filled");
      }
      if (String(editor.innerText || "") !== "wake up" || autoWakeSentFor === location.href) return null;
      var box = editor.closest(".editor-content");
      var root = box && box.parentElement;
      var button = root && root.querySelector('button[aria-label="Send message"]');
      if (!button || button.disabled || button.getAttribute("aria-disabled") === "true" ||
          !renderedNode(button)) return null;
      return { button: button, url: location.href };
    }

    function sync(event) {
      if (event && event.isComposing) composing = true;
      var next = target();
      if (!next) { cancel(); return; }
      if (timer !== null && timerFor === next.url) return;
      cancel();
      timerFor = next.url;
      timer = setTimeout(function () {
        timer = null;
        timerFor = null;
        var current = target();
        if (!current || current.url !== next.url) return;
        autoWakeSentFor = current.url;
        current.button.click();
        logEvent("auto-wake", "clicked");
      }, randomWakeDelayMs());
    }

    function compositionStart() { composing = true; cancel(); }
    function compositionEnd() { composing = false; sync(); }
    autoWakeNotify = sync;
    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      subtree: true, childList: true, characterData: true, attributes: true,
      attributeFilter: ["disabled", "aria-disabled", "aria-label", "role", "hidden", "style", "class"],
    });
    window.addEventListener("input", sync, true);
    window.addEventListener("compositionstart", compositionStart, true);
    window.addEventListener("compositionend", compositionEnd, true);
    window.addEventListener("popstate", sync);
    sync();
    return function () {
      cancel();
      if (autoWakeNotify === sync) autoWakeNotify = null;
      observer.disconnect();
      window.removeEventListener("input", sync, true);
      window.removeEventListener("compositionstart", compositionStart, true);
      window.removeEventListener("compositionend", compositionEnd, true);
      window.removeEventListener("popstate", sync);
    };
  });

  var keepWorkingRoots = new Set();
  var keepWorkingWaitingComposer = false;
  runFeature("keep-working", "Composer - keep working", function () {
    if (typeof document === "undefined") return function () {};
    var timer = null;
    var timerFor = null;
    var composing = false;

    function cancel() {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
      timerFor = null;
    }

    function clickTarget() {
      if (
        (!isComposerUrl(location.href) && !isSessionUrl(location.href)) ||
        composing ||
        captchaSignal(document)
      ) {
        return null;
      }
      var message = lastMessageRoot(document);
      var rootKey =
        message &&
        (message.id ||
          (typeof message.getAttribute === "function" &&
            message.getAttribute("data-chat-message-id")) ||
          message);
      var lastRow = lastMessageRow(message);
      var keepWorking = keepWorkingButton(document);
      if (
        !message ||
        !rootKey ||
        keepWorkingRoots.has(rootKey) ||
        !lastRow ||
        isSpinnerRow(lastRow) ||
        hasClassToken(lastRow, "prose") ||
        !keepWorking
      ) {
        return null;
      }
      return { button: keepWorking, rootKey: rootKey };
    }

    function fillComposer() {
      if (
        !keepWorkingWaitingComposer ||
        (!isComposerUrl(location.href) && !isSessionUrl(location.href)) ||
        composing ||
        captchaSignal(document)
      ) {
        return;
      }
      var editor = document.querySelector('div.tiptap.ProseMirror[contenteditable="true"]');
      if (!editor || !renderedNode(editor) || editor.getAttribute("aria-disabled") === "true") {
        return;
      }
      keepWorkingWaitingComposer = false;
      if (editor.textContent === "") {
        autoWakeSentFor = null;
        setComposerText(editor, "wake up");
        if (String(editor.innerText || "") === "wake up") {
          logEvent("keep-working", "filled");
          if (typeof autoWakeNotify === "function") autoWakeNotify();
        }
      }
    }

    function sync(event) {
      if (event && event.isComposing) composing = true;
      var next = clickTarget();
      if (!next) {
        cancel();
        fillComposer();
        return;
      }
      if (timer !== null && timerFor === next.rootKey) {
        fillComposer();
        return;
      }
      cancel();
      timerFor = next.rootKey;
      timer = setTimeout(function () {
        timer = null;
        timerFor = null;
        var current = clickTarget();
        if (!current || current.rootKey !== next.rootKey) return;
        keepWorkingRoots.add(current.rootKey);
        keepWorkingWaitingComposer = true;
        current.button.click();
        logEvent("keep-working", "clicked");
        fillComposer();
      }, randomKeepWorkingDelayMs());
      fillComposer();
    }

    function compositionStart() { composing = true; cancel(); }
    function compositionEnd() { composing = false; sync(); }
    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      subtree: true, childList: true, characterData: true, attributes: true,
      attributeFilter: ["disabled", "aria-disabled", "aria-label", "role", "hidden", "style", "class"],
    });
    window.addEventListener("compositionstart", compositionStart, true);
    window.addEventListener("compositionend", compositionEnd, true);
    window.addEventListener("popstate", sync);
    sync();
    return function () {
      cancel();
      keepWorkingWaitingComposer = false;
      observer.disconnect();
      window.removeEventListener("compositionstart", compositionStart, true);
      window.removeEventListener("compositionend", compositionEnd, true);
      window.removeEventListener("popstate", sync);
    };
  });

  function stateScopeKey(repo, branch) {
    function part(value) {
      return String(value || "")
        .replace(/[^A-Za-z0-9._-]+/g, "-")
        .replace(/^-+|-+$/g, "");
    }
    return [part(repo), part(branch)].filter(Boolean).join("-") || "arena";
  }

  function stateFileName(repo, branch, stamp, counts) {
    var scope = stateScopeKey(repo, branch);
    var when = String(stamp || "")
      .replace(/[-:]/g, "")
      .replace(/\..*$/, "")
      .replace(/\+.*$/, "");
    var name = scope + (when ? "-" + when : "");
    if (counts) {
      name += "-n" + (counts.notes || 0) + "-t" + (counts.tasks || 0);
    }
    return name + ".ndjson";
  }

  function stateMemory(stamp, pair) {
    return {
      stamp: String(stamp || ""),
      note: String((pair && pair.note) || ""),
      task: String((pair && pair.task) || ""),
    };
  }

  function stateRemembered(raw) {
    if (raw && typeof raw === "object") return stateMemory(raw.stamp, raw);
    if (!raw) return stateMemory("", null);
    var text = String(raw);
    if (text.charAt(0) !== "{") return stateMemory(text, null);
    try {
      var parsed = JSON.parse(text);
      if (parsed && typeof parsed === "object") return stateMemory(parsed.stamp, parsed);
    } catch (err) {
      return stateMemory(text, null);
    }
    return stateMemory("", null);
  }

  function stateDownload(repo, branch, stamp, counts, remembered, pair, force) {
    if (!stamp) {
      logEvent("state", "no-stamp", null, "debug");
      return {
        type: "error",
        message: "The state carries no stamp; the next save names it.",
      };
    }
    var name = stateFileName(repo, branch, stamp, counts);
    var memory = stateRemembered(remembered);
    var held = [];
    var keys = ["note", "task"];
    var index;
    for (index = 0; index < keys.length; index += 1) {
      var key = keys[index];
      var was = memory[key];
      var now = pair && pair[key] ? String(pair[key]) : "";
      if (!was || !now) continue;
      if (force) {
        logEvent("state", "force-stamp", { group: key }, "debug");
        continue;
      }
      var verdict = now < was ? "older" : now === was ? "same" : "forward";
      if (verdict === "older") held.push(key);
      logEvent("state", "compare", { group: key, verdict: verdict }, "debug");
    }
    if (!force && memory.stamp && memory.stamp === stamp) {
      return {
        type: "unchanged",
        name: name,
        message: "State unchanged since the last write: " + name,
      };
    }
    if (!force && memory.stamp && String(stamp) < memory.stamp) {
      return {
        type: "stale",
        name: name,
        message:
          "Stale preview state (" + stamp + " is older than " + memory.stamp + "); nothing written.",
      };
    }
    if (held.length) {
      var phrase = held.join(" and ") + (held.length > 1 ? " stamps" : " stamp");
      return {
        type: "stale",
        name: name,
        message: "Rolled-back preview state (" + phrase + " went backward); nothing written.",
      };
    }
    return { type: "download", name: name, message: "Wrote " + name };
  }

  function handleMatchesScope(handle, repo, branch) {
    if (!handle || !handle.name) return false;
    var scope = stateScopeKey(repo, branch);
    var name = String(handle.name);
    if (name.slice(-7) === ".ndjson") name = name.slice(0, -7);
    return name === scope || name.indexOf(scope + "-") === 0;
  }

  function handleMismatchScope(handle, repo, branch) {
    if (!handle || !handle.name) return repo;
    var name = String(handle.name);
    if (name.slice(-7) === ".ndjson") name = name.slice(0, -7);
    var repoScope = stateScopeKey(repo, "");
    var branchScope = stateScopeKey(repo, branch);
    if (name === branchScope || name.indexOf(branchScope + "-") === 0) return "";
    if (name === repoScope || name.indexOf(repoScope + "-") === 0) return branch;
    return repo;
  }

  function saveMoved(branch, remembered, base, rememberedScope, rememberedBranch) {
    return !(branch || rememberedScope) ||
      (Boolean(remembered) && remembered !== base) ||
      (Boolean(branch) && Boolean(rememberedBranch) && branch !== rememberedBranch);
  }

  function overwriteAsk(moved, plan, hasHandle, force) {
    return !force && Boolean(moved) && hasHandle && plan.type === "download";
  }

  function overwriteLine(name, context) {
    var before = stateRemembered(context && context.memory);
    var after = stateMemory(context && context.stamp, context && context.stamps);
    function compare(was, now) {
      if (!was || !now) return "unknown";
      return now < was ? "older" : now === was ? "same" : "forward";
    }
    var rows = [
      ["State", compare(before.stamp, after.stamp)],
      ["Notes", compare(before.note, after.note)],
      ["Tasks", compare(before.task, after.task)],
    ].filter(function (row) { return row[1] !== "same"; });
    return rows.length
      ? rows.map(function (row) { return row[0] + ": " + row[1]; }).join(" \u00b7 ")
      : "No stamp change.";
  }

  var RESET_WINDOW_MS = 150 * 1000;
  var RESET_BOUNDARY_HOURS = [2, 8, 14, 20];
  var RESET_WINDOW_KEY = "clankers-arena-state-reset-window";

  // The window spans 150 seconds either side of 02:00, 08:00, 14:00 or 20:00 PHT, and PHT
  // holds UTC+8 all year, so the boundary math runs on fixed offsets.
  function previousBoundary(when) {
    var SHIFT = 8 * 3600000;
    var DAY = 86400000;
    var HOUR = 3600000;
    var shifted = when.getTime() + SHIFT;
    var dayStart = Math.floor(shifted / DAY) * DAY;
    var hourOfDay = Math.floor((shifted - dayStart) / HOUR);
    var boundary = null;
    for (var i = 0; i < RESET_BOUNDARY_HOURS.length; i += 1) {
      if (RESET_BOUNDARY_HOURS[i] <= hourOfDay) {
        boundary = dayStart + RESET_BOUNDARY_HOURS[i] * HOUR;
      }
    }
    if (boundary === null) boundary = dayStart - 4 * HOUR;
    return new Date(boundary - SHIFT);
  }

  function inResetWindow(when) {
    var prev = previousBoundary(when).getTime();
    var at = when.getTime();
    return at - prev <= RESET_WINDOW_MS || prev + 6 * 3600000 - at <= RESET_WINDOW_MS;
  }

  // Only a URL-only move qualifies: a branch mismatch or a missing branch keeps the prompt,
  // and a switch set to off keeps it at every hour.
  function resetWindowAccepts(when, on, branch, remembered, base, rememberedBranch) {
    if (!on) return false;
    if (!branch || !remembered || remembered === base) return false;
    if (rememberedBranch && branch !== rememberedBranch) return false;
    return true;
  }

  function resetWindowOn() {
    return GM_getValue(RESET_WINDOW_KEY, true) !== false;
  }

  function stateDelivery(plan, hasHandle, hasPicker) {
    if (plan.type !== "download") return plan.type;
    if (hasHandle) return "write";
    return hasPicker ? "select" : "download";
  }

  function stateAction(route, manual) {
    if (!manual) return route === "select" || route === "download" ? "block" : route;
    return route === "select" ? "hint" : route;
  }

  function getLine(status, base) {
    return "GET " + status;
  }

  function writeFailLine(err) {
    return (
      "The file could not be saved (" + ((err && err.name) || "unknown") +
      "). Choose the file again to retry."
    );
  }

  function managerFailLine(err) {
    return "The download manager failed (" + ((err && err.error) || "unknown") + "). Trying a browser-link download.";
  }

  var STATE_LINES = {
    noBranch: "Missing branch.",
  };

  function writtenName(handle, fallback) {
    return handle && handle.name ? handle.name : fallback;
  }

  var STATE_WATCH_MS = 60 * 1000;


  var STATE_SLUG_KEY = "clankers-arena-agent-slug";

  function titleRepo(doc) {
    var match = STATE_TITLE_RE.exec(String((doc && doc.title) || ""));
    return match ? match[1] : "";
  }

  function detectRepo(doc) {
    var bar = doc.querySelector(BAR_SELECTOR);
    var spans;
    var i;
    var repo;
    var bare = null;
    if (bar) {
      try {
        spans = bar.querySelectorAll("span.truncate");
      } catch (err) {
        spans = null;
      }
      for (i = 0; spans && i < spans.length; i += 1) {
        var text = String(spans[i].textContent || "").trim();
        repo = slugFromOwnerRepo(text);
        if (repo) return repo;
        bare = bare || slugFromBare(text);
      }
      if (bare) return bare;
    }
    return chipRepo(doc) || promptRepo(doc) || titleRepo(doc);
  }

  function promptRepo(doc) {
    if (!doc || typeof doc.querySelectorAll !== "function") return "";
    var href = (doc.location && doc.location.href) ||
      (typeof location !== "undefined" ? location.href : "");
    if (!isSessionUrl(href)) return "";
    var spans = doc.querySelectorAll(CHIP_SPAN_SELECTOR);
    for (var i = 0; i < spans.length; i += 1) {
      var text = String(spans[i].textContent || "");
      var marker = text.indexOf(" read ");
      if (marker < 0) continue;
      var repo = slugFromBare(text.slice(0, marker));
      if (repo) return repo;
    }
    return "";
  }

  function chipRepo(doc) {
    if (!doc || typeof doc.querySelectorAll !== "function") return "";
    var chips = doc.querySelectorAll(CHIP_SPAN_SELECTOR);
    var repo = "";
    var branch = "";
    var hits = 0;
    var i;
    for (i = 0; chips && i < chips.length; i += 1) {
      var text = String(chips[i].textContent || "").trim();
      var hit = slugFromOwnerRepo(text);
      if (!hit) continue;
      hits += 1;
      if (SESSION_BRANCH_RE.test(text)) {
        branch = hit;
      } else {
        repo = repo || hit;
      }
    }
    if (hits === 1) return repo || branch;
    if (hits === 2 && repo && branch) return repo;
    return "";
  }

  function savedSlug() {
    try {
      return String(sessionStorage.getItem(STATE_SLUG_KEY) || "").trim();
    } catch (err) {
      return "";
    }
  }

  function headerRepo(doc) {
    if (!doc || typeof doc.querySelectorAll !== "function") return "";
    var spans = doc.querySelectorAll(CHIP_SPAN_SELECTOR);
    for (var i = 0; i < spans.length; i += 1) {
      var first = String(spans[i].textContent || "").trim().split(/\s+/)[0];
      if (/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(first)) return first;
    }
    return "";
  }

  function stateRepo(doc) {
    return detectRepo(doc) || savedSlug() || headerRepo(doc) || "";
  }

  function stateBranch(doc) {
    var bar = doc.querySelector(BAR_SELECTOR);
    if (!bar) return "";
    var links = bar.querySelectorAll("a, [title]");
    var i;
    for (i = 0; i < links.length; i += 1) {
      var href = String(links[i].getAttribute("href") || "");
      var match = /\/tree\/([^?#]+)/.exec(href);
      if (match) {
        var decoded = "";
        try {
          decoded = decodeURIComponent(match[1]);
        } catch (err) {
          decoded = match[1];
        }
        if (decoded) return decoded;
      }
      var title = String(links[i].getAttribute("title") || "");
      var arrow = title.indexOf("\u2192");
      if (arrow !== -1) {
        var branch = title.slice(arrow + 1).trim();
        if (branch) return branch;
      }
    }
    return "";
  }

  function stateScope(doc) {
    return { repo: stateRepo(doc), branch: stateBranch(doc) };
  }

  runFeature("state-download", "State - download", function () {
    var STATE_PANEL_ID = "clankers-state-panel";
    var STATE_PANEL_MS = 6000;

    if (exposeChecks("stateDownload", {
      STATE_LINES: STATE_LINES,
      getLine: getLine,
      writeFailLine: writeFailLine,
      managerFailLine: managerFailLine,
      stateError: stateError,
      stateFileName: stateFileName,
      stateScopeKey: stateScopeKey,
      stateDownload: stateDownload,
      sameSaveDetail: sameSaveDetail,
      stateDiffCounts: stateDiffCounts,
      stateMismatchLine: stateMismatchLine,
      mismatchOfferId: mismatchOfferId,
      backupTextForOffer: backupTextForOffer,
      stateMemory: stateMemory,
      stateRemembered: stateRemembered,
      stateDelivery: stateDelivery,
      stateAction: stateAction,
      panelNeeded: panelNeeded,
      writtenName: writtenName,
      handleMatchesScope: handleMatchesScope,
      handleMismatchScope: handleMismatchScope,
      saveMoved: saveMoved,
      overwriteAsk: overwriteAsk,
      overwriteLine: overwriteLine,
      previousBoundary: previousBoundary,
      inResetWindow: inResetWindow,
      resetWindowAccepts: resetWindowAccepts,
      resetWindowOn: resetWindowOn,
      stateScope: stateScope,
      stateRepo: stateRepo,
      stateBranch: stateBranch,
      readSlug: readSlug,
      slugFromBare: slugFromBare,
      pagePicker: pagePicker,
      downloadRoute: downloadRoute,
      stateDownloadRoute: stateDownloadRoute,
      writeToHandle: writeToHandle,
      writeStateDownload: writeStateDownload,
      sameSaves: sameSaves,
      previewFrame: previewFrame,
      previewBase: previewBase,
      notifyPreviewReady: notifyPreviewReady,
      STATE_WATCH_MS: STATE_WATCH_MS,
    })) {
      return function () {};
    }

    var STATE_DB = "clankers-arena-state";
    var STATE_HINT_KEY = "clankers-arena-state-hinted";
    function stampKey(scopeKey) {
      return "clankers-arena-state-stamp-" + scopeKey;
    }
    function fileKey(scopeKey) {
      return "state-file-" + scopeKey;
    }
    function lastScopeKey(repo) {
      return "clankers-arena-state-scope-" + stateScopeKey(repo, "");
    }
    function baseKey(scopeKey) {
      return "clankers-arena-state-base-" + scopeKey;
    }
    function branchKey(scopeKey) {
      return "clankers-arena-state-branch-" + scopeKey;
    }
    function overwriteKey(scopeKey) {
      return "clankers-arena-state-ask-" + scopeKey;
    }
    function rememberState(scope, storeKey, base, branch, stamp, stamps) {
      GM_setValue(lastScopeKey(scope.repo), storeKey);
      GM_setValue(baseKey(storeKey), base);
      GM_setValue(branchKey(storeKey), branch);
      GM_setValue(overwriteKey(storeKey), false);
      GM_setValue(stampKey(storeKey), JSON.stringify(stateMemory(stamp, stamps)));
    }
    var stateBusy = false;
    var selected = null;
    var selectedKey = null;

    function previewFrame(doc) {
      if (!doc || typeof doc.querySelectorAll !== "function") return null;
      var frames = doc.querySelectorAll("iframe[title]");
      var i;
      for (i = 0; i < frames.length; i += 1) {
        var title = frames[i].getAttribute("title") || "";
        if (title.indexOf("App preview on port 8000") === 0 && frames[i].src) {
          return frames[i];
        }
      }
      return null;
    }

    function previewBase(doc) {
      var frame = previewFrame(doc);
      return frame ? frame.src.replace(/\/+$/, "") : null;
    }

    var lastNotifiedPreviewFrame = null;
    var lastNotifiedPreviewTarget = "";

    function notifyPreviewReady(doc, force) {
      var frame = previewFrame(doc);
      if (!frame || !frame.contentWindow || typeof frame.contentWindow.postMessage !== "function") {
        lastNotifiedPreviewFrame = null;
        lastNotifiedPreviewTarget = "";
        return false;
      }
      if (typeof frame.addEventListener === "function" && !frame.getAttribute("data-clankers-preview-bound")) {
        frame.setAttribute("data-clankers-preview-bound", "true");
        frame.addEventListener("load", function () {
          notifyPreviewReady(doc, true);
        });
      }
      var target = frame.src ? frame.src.replace(/\/+$/, "") : "*";
      if (!force && frame === lastNotifiedPreviewFrame && target === lastNotifiedPreviewTarget) {
        return false;
      }
      try {
        frame.contentWindow.postMessage({ type: "clankers:userscript-ready" }, target);
        lastNotifiedPreviewFrame = frame;
        lastNotifiedPreviewTarget = target;
        return true;
      } catch (err) {
        try {
          frame.contentWindow.postMessage({ type: "clankers:userscript-ready" }, "*");
          lastNotifiedPreviewFrame = frame;
          lastNotifiedPreviewTarget = target;
          return true;
        } catch (fallbackErr) {
          return false;
        }
      }
    }

    function stateJson(url, payload) {
      return new Promise(function (resolve) {
        if (typeof GM_xmlhttpRequest !== "function") {
          resolve({ status: 0, body: null, failure: "unavailable" });
          return;
        }
        GM_xmlhttpRequest({
          method: payload === undefined ? "GET" : "POST",
          url: url,
          headers: payload === undefined ? {} : { "Content-Type": "application/json" },
          data: payload === undefined ? undefined : JSON.stringify(payload),
          timeout: 15000,
          onload: function (answer) {
            var body = null;
            var failure = null;
            try { body = JSON.parse(answer.responseText); } catch (err) { failure = "parse"; }
            resolve({ status: answer.status, body: body, failure: failure });
          },
          onerror: function () { resolve({ status: 0, body: null, failure: "error" }); },
          ontimeout: function () { resolve({ status: 0, body: null, failure: "timeout" }); },
        });
      });
    }

    function receiptKey(storeKey) { return "clankers-arena-state-receipt-" + storeKey; }
    function pendingKey(storeKey) { return "clankers-arena-state-pending-" + storeKey; }
    function offerKey(storeKey) { return "clankers-arena-state-offered-" + storeKey; }

    async function confirmPending(base, storeKey, pending) {
      var answer = await stateJson(base + "/api/userscript-autosave", pending.receipt);
      var receipt = pending.receipt;
      var body = answer.body;
      if ((answer.status !== 200 && answer.status !== 201) || !body ||
          body.confirmed !== true || body.save_id !== receipt.save_id || body.digest !== receipt.digest) {
        stateError("Failed to confirm. File saved.",
          null, null, "save-receipt", answer.status, undefined,
          (answer.status === 200 || answer.status === 201 ? "body" : "status" + (answer.failure ? ":" + answer.failure : "")));
        return;
      }
      GM_setValue(receiptKey(storeKey), {
        save_id: receipt.save_id, digest: receipt.digest, scope: receipt.scope,
        lastsave: receipt.lastsave, beforelastsave: receipt.beforelastsave,
        counts: pending.counts || coreCounts(receipt.core),
      });
      GM_setValue(pendingKey(storeKey), null);
      GM_setValue(offerKey(storeKey), "");
      rememberState(pending.scope, storeKey, pending.base, pending.branch, pending.stamp, pending.stamps);
      removeStatePanel(true);
      logEvent("state", "saved", { repo: pending.scope.repo, filename: pending.name });
      if (pending.force) statePanel("Forced save of " + pending.name + ".", null, null, true);
    }

    function fileCore(text) {
      var records;
      try {
        records = JSON.parse(text);
        if (!Array.isArray(records)) records = [records];
      } catch (err) {
        records = text.split(/\r?\n/).filter(function (line) { return line.trim(); }).map(function (line) { return JSON.parse(line); });
      }
      return records.filter(function (record) {
        return record.type !== "userscript-autosave";
      });
    }

    function pagePicker() {
      var page = typeof unsafeWindow !== "undefined" ? unsafeWindow : null;
      if (!page && typeof window !== "undefined") page = window;
      var selector = page && page.showSaveFilePicker;
      if (typeof selector !== "function") return null;
      return function (options) {
        return selector.call(page, options);
      };
    }

    function stateDb() {
      return new Promise(function (resolve, reject) {
        var request = indexedDB.open(STATE_DB, 1);
        request.onupgradeneeded = function () {
          request.result.createObjectStore("files");
        };
        request.onsuccess = function () {
          resolve(request.result);
        };
        request.onerror = function () {
          reject(request.error);
        };
      });
    }

    function stateHandle(key) {
      return stateDb()
        .then(function (db) {
          return new Promise(function (resolve) {
            var request = db
              .transaction("files")
              .objectStore("files")
              .get(key);
            request.onsuccess = function () {
              resolve(request.result || null);
            };
            request.onerror = function () {
              resolve(null);
            };
          });
        })
        .catch(function () {
          return null;
        });
    }

    function saveStateHandle(handle, key) {
      return stateDb()
        .then(function (db) {
          db.transaction("files", "readwrite")
            .objectStore("files")
            .put(handle, key);
        })
        .catch(function () {});
    }

    function writeToHandle(handle, text) {
      return handle.createWritable().then(function (writable) {
        return writable.write(text).then(function () {
          return writable.close();
        }).then(function () { removeStatePanel(true); });
      });
    }

    function panelNeeded(manual, shown) {
      return Boolean(manual) || !shown;
    }

    function removeStatePanel(keepAutoHide) {
      try {
        var node = document.getElementById ? document.getElementById(STATE_PANEL_ID) : null;
        if (node && node.parentNode &&
            (keepAutoHide !== true || node.getAttribute("data-auto-hide") !== "true")) {
          node.parentNode.removeChild(node);
        }
      } catch (err) {
        return;
      }
    }

    // A healthy cycle retires an earlier get failure notice, and prompts with a button stay.
    function clearErrorPanel() {
      try {
        var node = document.getElementById ? document.getElementById(STATE_PANEL_ID) : null;
        if (node && node.parentNode && node.getAttribute("data-action") === "false" &&
            node.getAttribute("data-auto-hide") !== "true") {
          node.parentNode.removeChild(node);
        }
      } catch (err) {
        return;
      }
    }

    function statePanel(message, actionLabel, action, autoHide) {
      try {
        if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.body) return;
        removeStatePanel();
        var card = document.createElement("div");
        card.id = STATE_PANEL_ID;
        card.setAttribute("role", "status");
        card.setAttribute("data-action", String(Boolean(actionLabel && typeof action === "function")));
        card.setAttribute("data-auto-hide", String(Boolean(autoHide)));
        card.style.cssText =
          "position:fixed;right:16px;top:16px;z-index:2147483647;max-width:320px;" +
          "padding:12px 14px;border-radius:10px;background:#2c2b28;color:#f0ede8;" +
          "font:13px/1.45 system-ui,-apple-system,sans-serif;" +
          "box-shadow:0 6px 24px rgba(0,0,0,.35);border:1px solid #56504a";
        var text = document.createElement("div");
        text.textContent = message;
        card.appendChild(text);
        var row = document.createElement("div");
        row.style.cssText = "display:flex;gap:8px;margin-top:10px";
        if (actionLabel && typeof action === "function") {
          var go = document.createElement("button");
          go.type = "button";
          go.textContent = actionLabel;
          go.style.cssText =
            "cursor:pointer;border:1px solid #56504a;border-radius:6px;padding:5px 10px;" +
            "background:#2c2b28;color:#f0ede8;font:inherit";
          go.addEventListener("click", function () {
            removeStatePanel();
            action();
          });
          row.appendChild(go);
        }
        var close = document.createElement("button");
        close.type = "button";
        close.textContent = actionLabel === "Choose file" ? "Cancel" : "Dismiss";
        close.style.cssText =
          "cursor:pointer;border:1px solid #56504a;border-radius:6px;padding:5px 10px;" +
          "background:transparent;color:inherit;font:inherit";
        close.addEventListener("click", removeStatePanel);
        row.appendChild(close);
        card.appendChild(row);
        document.body.appendChild(card);
        if (autoHide) setTimeout(removeStatePanel, statePanelMs());
      } catch (err) {
        return;
      }
    }

    function stateError(line, actionLabel, action, code, status, showPanel, detail) {
      logEvent("state", "failed", { code: code || "unknown", status: status, detail: detail }, code === "file-api" ? "warn" : "error");
      if (showPanel !== false) statePanel(line, actionLabel, action);
    }

    function hintStateFile(manual) {
      var shown = GM_getValue(STATE_HINT_KEY, false);
      if (!shown) {
        GM_setValue(STATE_HINT_KEY, true);
      }
      logEvent("state", "file-needed", null, "warn");
      if (panelNeeded(manual, shown)) {
        statePanel(
          "No file selected.",
          "Choose file",
          chooseStateFile
        );
      }
    }

    function askOverwrite(handle, storeKey, manual, context) {
      var askedKey = overwriteKey(storeKey);
      var shown = GM_getValue(askedKey, false);
      if (!panelNeeded(manual, shown)) return;
      GM_setValue(askedKey, true);
      statePanel(overwriteLine(writtenName(handle, "the save file"), context), "Overwrite", function () {
        fetchStateFile(true, true);
      });
    }

    function downloadRoute(hasManagerDownload) {
      return hasManagerDownload ? "manager" : "link";
    }

    function stateDownloadRoute() {
      return downloadRoute(typeof GM_download === "function");
    }

    function linkDownload(url, name) {
      var anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = name;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
    }

    function writeStateDownload(text, name) {
      var url = URL.createObjectURL(
        new Blob([text], { type: "application/x-ndjson" }),
      );
      var route = stateDownloadRoute();
      if (route === "link") {
        logEvent("state", "download", { route: "link", filename: name });
        linkDownload(url, name);
        statePanel("Browser download requested. Completion unconfirmed.", null, null, true);
        setTimeout(function () {
          URL.revokeObjectURL(url);
        }, 1000);
        return Promise.resolve(false);
      }
      return new Promise(function (resolve) {
        GM_download({
          url: url,
          name: name,
          saveAs: false,
          onload: function () {
            removeStatePanel(true);
            logEvent("state", "saved", { route: "manager", filename: name });
            URL.revokeObjectURL(url);
            resolve(true);
          },
          onerror: function (err) {
            stateError(managerFailLine(err), null, null, "manager-download");
            linkDownload(url, name);
            setTimeout(function () {
              URL.revokeObjectURL(url);
            }, 1000);
            resolve(false);
          },
        });
      });
    }

    function sameSaves(known, body) {
      if (!known) return false;
      return (known.lastsave || null) === (body.lastsave || null) &&
        (known.beforelastsave || null) === (body.beforelastsave || null);
    }

    function saveStampPair(known) {
      return (known && known.lastsave || "none") + "/" + (known && known.beforelastsave || "none");
    }

    function recordGroup(record) {
      if (!record || typeof record !== "object") return "notes";
      if ("markdown" in record) return "reports";
      if ("title" in record) return "tasks";
      if ("report_id" in record) return "answers";
      return "notes";
    }

    function coreCounts(records) {
      var counts = { notes: 0, tasks: 0, reports: 0, answers: 0 };
      if (!Array.isArray(records)) return counts;
      for (var i = 0; i < records.length; i += 1) {
        var group = recordGroup(records[i]);
        counts[group] = (counts[group] || 0) + 1;
      }
      return counts;
    }

    function signedCount(value) {
      var num = Number(value) || 0;
      return num > 0 ? "+" + num : String(num);
    }

    function stateDiffCounts(known, body) {
      var server = body && Array.isArray(body.core)
        ? coreCounts(body.core)
        : {
          notes: (body && body.counts && body.counts.notes) || 0,
          tasks: (body && body.counts && body.counts.tasks) || 0,
          reports: (body && body.counts && body.counts.reports) || 0,
          answers: (body && body.counts && body.counts.answers) || 0,
        };
      var saved = null;
      if (known && Array.isArray(known.core)) {
        saved = coreCounts(known.core);
      } else if (known && known.counts && typeof known.counts === "object") {
        saved = {
          notes: known.counts.notes || 0,
          tasks: known.counts.tasks || 0,
          reports: known.counts.reports || 0,
          answers: known.counts.answers || 0,
        };
      }
      return {
        saved: saved,
        server: server,
        notes: saved ? server.notes - saved.notes : server.notes,
        tasks: saved ? server.tasks - saved.tasks : server.tasks,
        reports: saved ? server.reports - saved.reports : server.reports,
        answers: saved ? server.answers - saved.answers : server.answers,
      };
    }

    function stateMismatchLine(known, body) {
      var diff = stateDiffCounts(known, body);
      var parts = [
        "notes " + signedCount(diff.notes),
        "tasks " + signedCount(diff.tasks),
      ];
      if (diff.reports) parts.push("reports " + signedCount(diff.reports));
      if (diff.answers) parts.push("answers " + signedCount(diff.answers));
      return "State mismatch (" + parts.join(", ") + ").";
    }

    function sameSaveDetail(known, body) {
      var diff = stateDiffCounts(known, body);
      var detail = "saved " + saveStampPair(known) + " server " + saveStampPair(body) +
        " n" + diff.server.notes + " t" + diff.server.tasks;
      if (diff.saved) {
        detail += " dn" + signedCount(diff.notes) + " dt" + signedCount(diff.tasks);
      }
      return detail;
    }

    function mismatchOfferId(known, body) {
      return [
        saveStampPair(known),
        (known && known.digest) || "",
        saveStampPair(body),
        (body && body.digest) || "",
      ].join("|");
    }

    function backupTextForOffer(backupText, known) {
      var raw = String(backupText || "");
      if (raw.trim()) return raw;
      if (known && Array.isArray(known.core) && known.core.length) {
        return known.core.map(function (row) { return JSON.stringify(row); }).join("\n") + "\n";
      }
      return "";
    }

    function offerStateBackup(base, storeKey, scope, handle, known, body, backupText, summary) {
      var text = backupTextForOffer(backupText, known);
      if (!text) return;
      try {
        if (!fileCore(text).length) return;
      } catch (err) {
        return;
      }
      var offerId = mismatchOfferId(known, body);
      if (GM_getValue(offerKey(storeKey), "") === offerId) return;
      GM_setValue(offerKey(storeKey), offerId);
      var fallbackName = stateFileName(
        scope && scope.repo,
        scope && scope.branch,
        (known && known.lastsave) || "",
        (known && known.counts) || (known && Array.isArray(known.core) ? coreCounts(known.core) : null),
      );
      var name = writtenName(handle, fallbackName);
      stateJson(base + "/api/userscript-autosave/offer", {
        name: name,
        text: text,
        summary: summary || stateMismatchLine(known, body),
      }).then(function (answer) {
        if ((answer.status !== 200 && answer.status !== 201) || !answer.body || answer.body.offered !== true) {
          if (GM_getValue(offerKey(storeKey), "") === offerId) {
            GM_setValue(offerKey(storeKey), "");
          }
        }
      });
    }

    async function fetchStateFile(manual, force) {
      notifyPreviewReady(document);
      var base = previewBase(document);
      if (!base || stateBusy) return;
      stateBusy = true;
      if (force) statePanel("Forcing save...");
      try {
        var scope = stateScope(document);
        var lastScope = GM_getValue(lastScopeKey(scope.repo), "");
        var storeKey = scope.branch ? stateScopeKey(scope.repo, scope.branch) : lastScope || stateScopeKey(scope.repo, "");
        var pending = GM_getValue(pendingKey(storeKey), null);
        if (pending) {
          await confirmPending(base, storeKey, pending);
          return;
        }
        var answer = await stateJson(base + "/api/userscript-autosave");
        var body = answer.body;
        if (answer.status !== 200 || !body || !Array.isArray(body.core) || !body.scope ||
            !body.save_id || !body.digest || typeof body.text !== "string") {
          stateError(getLine(answer.status, base + "/api/userscript-autosave"), null, null, "autosave-get", answer.status, undefined,
            (answer.status === 200 ? "body" : "status" + (answer.failure ? ":" + answer.failure : "")));
          return;
        }
        clearErrorPanel();
        if (body.force === true) {
          force = true;
        }
        if (force) statePanel("Forcing save...");
        var rememberedBase = GM_getValue(baseKey(lastScope || storeKey), "");
        var rememberedBranch = GM_getValue(branchKey(lastScope || storeKey), "");
        var handle = selectedKey === storeKey && selected ? selected : await stateHandle(fileKey(storeKey));
        if (!scope.branch && !lastScope && !force && !handle) {
          stateError(STATE_LINES.noBranch, "Force save", function () { fetchStateFile(true, true); }, "missing-branch");
          return;
        }
        if (handle && !handleMatchesScope(handle, scope.repo, scope.branch)) {
          stateError(handle.name + " does not match this " + handleMismatchScope(handle, scope.repo, scope.branch) + ".",
            "Choose file", chooseStateFile, "wrong-file");
          return;
        }
        if (!handle && (!force || (!scope.branch && !lastScope && Boolean(pagePicker())))) {
          hintStateFile(manual || Boolean(force));
          return;
        }
        var baseline = GM_getValue(receiptKey(storeKey), null);
        var initialFile = false;
        var backupText = "";
        if (handle && !force) {
          var text = await (await handle.getFile()).text();
          backupText = text;
          initialFile = !text.trim() && !baseline;
          if (text.trim()) {
            baseline = Object.assign({}, baseline || {}, { core: fileCore(text) });
          } else if (baseline) {
            baseline = Object.assign({}, baseline, { core: [] });
          }
        }
        var inSync = sameSaves(baseline, body);
        if (!force && !inSync && !(initialFile && !baseline)) {
          var mismatchLine = stateMismatchLine(baseline, body);
          stateError(mismatchLine, "Force save",
            function () { fetchStateFile(true, true); }, "autosave-compare",
            undefined, undefined, sameSaveDetail(baseline, body));
          offerStateBackup(
            base,
            storeKey,
            scope,
            handle,
            baseline,
            body,
            backupText,
            mismatchLine,
          );
          return;
        }
        if (!force && inSync && body.digest === (baseline && baseline.digest)) return;
        var plan = { type: "download", name: stateFileName(scope.repo, scope.branch, body.stamp, body.counts) };
        var moved = saveMoved(scope.branch, rememberedBase, base, lastScope, rememberedBranch);
        var asks = overwriteAsk(moved, plan, Boolean(handle) && !initialFile, force);
        var accepted = asks && resetWindowAccepts(new Date(), resetWindowOn(), scope.branch, rememberedBase, base, rememberedBranch);
        if (asks && !accepted) {
          askOverwrite(handle, storeKey, manual, {
            branch: scope.branch, rememberedBranch: rememberedBranch, lastScope: lastScope,
            base: base, rememberedBase: rememberedBase, memory: stateRemembered(GM_getValue(stampKey(storeKey), "")),
            stamp: body.stamp, stamps: body.stamps,
          });
          return;
        }
        selected = handle || null;
        selectedKey = handle ? storeKey : null;
        var name = writtenName(handle, plan.name);
        if (handle) {
          try { await writeToHandle(handle, body.text); }
          catch (err) {
            selected = null;
            selectedKey = null;
            stateError(writeFailLine(err), "Choose file", chooseStateFile, "write");
            return;
          }
        } else if (!(await writeStateDownload(body.text, plan.name))) {
          return;
        }
        pending = {
          receipt: {
            save_id: body.save_id, scope: body.scope, digest: body.digest, core: body.core,
            lastsave: body.stamp, beforelastsave: body.lastsave,
          },
          counts: body.counts,
          scope: scope, base: base, branch: scope.branch || rememberedBranch, stamp: body.stamp,
          stamps: body.stamps, name: name, force: Boolean(force),
        };
        GM_setValue(pendingKey(storeKey), pending);
        await confirmPending(base, storeKey, pending);
      } catch (err) {
        stateError(String(err.name || "unknown"), null, null, "autosave", undefined, undefined, String(err.message || "").slice(0, 160));
      } finally {
        stateBusy = false;
      }
    }

    function chooseStateFile() {
      var select = pagePicker();
      if (!select) {
        stateError("Direct write unavailable.", "Download", function () {
          fetchStateFile(true, true);
        }, "file-api");
        return;
      }
      select({
        suggestedName: (function () {
          var scope = stateScope(document);
          return stateFileName(scope.repo, scope.branch, "", null);
        })(),
        types: [
          {
            description: "State file (NDJSON)",
            accept: { "application/x-ndjson": [".ndjson"] },
          },
        ],
      })
        .then(function (handle) {
          var scope = stateScope(document);
          var storeKey = stateScopeKey(scope.repo, scope.branch);
          return saveStateHandle(handle, fileKey(storeKey)).then(function () {
            selected = handle;
            selectedKey = storeKey;
            GM_setValue(stampKey(storeKey), "");
            GM_setValue(STATE_HINT_KEY, false);
            fetchStateFile(true);
          });
        })
        .catch(function () {
          logEvent("state", "selector-closed", null, "debug");
        });
    }

    var menus = [];
    chooseStateFileHook = chooseStateFile;
    forceSaveStateHook = function () {
      fetchStateFile(true, true);
    };
    setResetWindowHook = function (next) {
      GM_setValue(RESET_WINDOW_KEY, Boolean(next));
      logEvent("feature", "change", {
        feature: "state-download",
        enabled: resetWindowOn(),
      });
      menuRefresh();
    };
    menuItem(menus, "State - choose the file", chooseStateFile);
    menuItem(menus, "State - force save", function () {
      fetchStateFile(true, true);
    });
    menus.push(
      menuAdd(
        function () {
          return (
            "State - reset-window overwrite (" + (resetWindowOn() ? "ON" : "OFF") + ")"
          );
        },
        function () {
          logEvent("menu", "run");
          setResetWindowHook(!resetWindowOn());
        },
      ),
    );

    function onPreviewMessage(event) {
      if (!event || !event.data || typeof event.data !== "object") return;
      var frame = previewFrame(document);
      var base = previewBase(document);
      if (base && event.origin && base.indexOf(event.origin) !== 0) {
        return;
      }
      if (!event.origin && frame && frame.contentWindow && event.source && event.source !== frame.contentWindow) {
        return;
      }
      if (event.data.type === "clankers:preview-ready") {
        if (typeof event.data.repo === "string" && event.data.repo.trim()) {
          var nextRepo = event.data.repo.trim();
          if (nextRepo !== previewUiRepo) {
            previewUiRepo = nextRepo;
            if (typeof syncPreviewProxyHook === "function") syncPreviewProxyHook();
          }
        }
        notifyPreviewReady(document, !event.data.repo);
      } else if (event.data.type === "clankers:force-save") {
        fetchStateFile(true, true);
      }
    }

    if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
      window.addEventListener("message", onPreviewMessage);
    }
    notifyPreviewReadyHook = function () {
      notifyPreviewReady(document);
    };
    notifyPreviewReady(document);
    fetchStateFile(false);
    var stopStateWatch = jitteredTimer(function () {
      fetchStateFile(false);
    }, stateWatchMs(), HTTP_JITTER_MS);
    restartStateWatchHook = function () {
      stopStateWatch();
      stopStateWatch = jitteredTimer(function () {
        fetchStateFile(false);
      }, stateWatchMs(), HTTP_JITTER_MS);
    };
    return function () {
      notifyPreviewReadyHook = null;
      if (typeof window !== "undefined" && typeof window.removeEventListener === "function") {
        window.removeEventListener("message", onPreviewMessage);
      }
      restartStateWatchHook = null;
      stopStateWatch();
      menus.forEach(menuDrop);
      menus = [];
    };
  });

  runFeature("keep-awake", "Page - keep awake", function () {
    function wakeLockPlan(generating, held, visible) {
      if (generating && !held && visible) return "acquire";
      if (!generating && held) return "release";
      return "none";
    }
    if (exposeChecks("keepAwake", { wakeLockPlan: wakeLockPlan })) {
      return function () {};
    }
    var lock = null;
    var pending = false;

    function generating() {
      return Boolean(isSessionUrl(location.href) && findStopGeneratingButton(document));
    }

    function release() {
      var held = lock;
      lock = null;
      if (held) held.release().catch(function () {});
    }

    function acquire() {
      pending = true;
      navigator.wakeLock.request("screen").then(
        function (sentinel) {
          pending = false;
          if (!generating()) {
            sentinel.release().catch(function () {});
            return;
          }
          lock = sentinel;
          sentinel.addEventListener("release", function () {
            if (lock === sentinel) lock = null;
          });
        },
        function (err) {
          pending = false;
          logEvent("wake", "refused", { code: err && LOG_VALUES.code.indexOf(err.name) !== -1 ? err.name : "unknown" }, "warn");
        },
      );
    }

    function sync() {
      if (typeof navigator === "undefined" || !navigator.wakeLock) {
        logEvent("wake", "unavailable", null, "warn");
        return;
      }
      var plan = wakeLockPlan(
        generating(),
        Boolean(lock) || pending,
        document.visibilityState === "visible",
      );
      if (plan === "acquire") acquire();
      if (plan === "release") release();
    }

    var timer = setInterval(sync, 1000);
    return function () {
      clearInterval(timer);
      release();
    };
  });

  runFeature("tab-title", "Page - tab title", function () {

    var REPO_LINK_SELECTOR = 'a[aria-label^="Open "][aria-label$=" on GitHub"]';
    var MESSAGE_SELECTOR = "[data-agent-transcript-message]";
    var LIVE_ICON_SELECTOR = ".animate-pulse";
    var LIVE_LABEL_SELECTOR = 'p[style*="text-shimmer"]';
    var GROUP_LABEL_SELECTOR = "span.text-text-secondary";
    var LABEL_SPAN_SELECTOR = "span.body-sm";
    var SUMMARY_LABEL = "Summary";
    var TITLE_PREFIX = "Arena | ";
    var AGENT_EMOJI = "\uD83D\uDCAC";
    var REASONING_EMOJI = "\uD83D\uDCAD";
    var BASH_EMOJI = "\uD83D\uDDA5\uFE0F";
    var PLAY_SELECTOR = "svg.lucide-play";
    var ACTION_EMOJI = [
      ["running", BASH_EMOJI],
      ["bash", BASH_EMOJI],
      ["command", BASH_EMOJI],
      ["read", "\uD83D\uDCD6"],
      ["explor", "\uD83D\uDCD6"],
      ["edit", "\u270F\uFE0F"],
      ["writ", "\u270F\uFE0F"],
      ["search", "\uD83D\uDD0D"],
      ["fetch", "\uD83D\uDD0D"],
      ["think", "\uD83D\uDCAD"],
      ["thought", "\uD83D\uDCAD"],
      ["wait", "\uD83D\uDCA4"],
      ["process_output", "\uD83D\uDCDC"],
      ["generating question", QUESTION_EMOJI],
    ];
    var ACTION_FALLBACK = "\u2699\uFE0F";
    var EMOJI_HOLD_MS = 5000;
    var heldEmoji = null;
    var heldEmojiAt = 0;
    var heldEmojiNeedsTurn = false;
    var WAITING_EMOJI = "\uD83D\uDCA4";
    var WAITING_SELECTOR = 'canvas[width="16"][height="16"]';
    var WAITING_TEXT_SELECTOR = 'span[class*="whitespace-pre"]';
    var HOURGLASS_EMOJI = "\u23F3";
    var CAPTCHA_EMOJI = "\uD83D\uDEE1\uFE0F";
    var POLL_RE = /\b(?:arena-)?preview(?:\.py)?\s+poll\b/;
    var POLL_GATE_RUNNING_RE = /(?:^|\n)\s*run\s+[a-z0-9._-]+\s+(?:running\s+\d+s\b|progress:)/i;

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

    function squash(value) {
      return String(value || "").replace(/\s+/g, " ").trim();
    }

    function collapsed(node) {
      return node ? squash(node.textContent) : "";
    }

    function classNameOf(node) {
      if (!node) {
        return "";
      }
      var value = node.className;
      if (value && typeof value === "object") {
        value = value.baseVal;
      }
      return String(value || "");
    }

    function classOf(node, name) {
      return (" " + classNameOf(node) + " ").indexOf(" " + name + " ") !== -1;
    }

    function childChain(node, steps) {
      var current = node;
      var i;
      for (i = 0; i < steps; i += 1) {
        if (!current) {
          return null;
        }
        current = current.firstElementChild || null;
      }
      return current;
    }

    function userRoot(root) {
      var card = childChain(root, 3);
      if (!card || !classOf(card, "relative") || !classOf(card, "overflow-hidden")) {
        return false;
      }
      var body = childChain(card, 3);
      return !!(body && classOf(body, "prose"));
    }

    function rowContainer(root) {
      var node = root && root.querySelector(":scope > div > div.px-3.pb-3 > div.flex.flex-col.gap-2");
      node = node || childChain(root, 3);
      if (!node || !classOf(node, "flex") || !classOf(node, "flex-col") || !classOf(node, "gap-2")) {
        return null;
      }
      return node;
    }

    function newestRow(root) {
      var container = rowContainer(root);
      var kids = container && container.children ? container.children : [];
      var divs = [];
      var i;
      for (i = 0; i < kids.length; i += 1) {
        var tag = kids[i] && kids[i].tagName ? String(kids[i].tagName).toUpperCase() : "DIV";
        if (tag === "DIV") {
          divs.push(kids[i]);
        }
      }
      if (divs.length >= 2) {
        return divs[divs.length - 2];
      }
      return divs.length ? divs[divs.length - 1] : null;
    }

    function rowKind(row) {
      if (!row) {
        return "none";
      }
      if (classOf(row, "prose")) {
        return "chat";
      }
      if (classOf(row, "not-prose")) {
        return "reasoning";
      }
      return "action";
    }

    function stopSignal(doc) {
      var buttons =
        typeof doc.querySelectorAll === "function" ? doc.querySelectorAll("button[aria-label]") : [];
      var i;
      for (i = 0; i < buttons.length; i += 1) {
        if (/\bstop\b/i.test(String(buttons[i].getAttribute("aria-label") || ""))) {
          return true;
        }
      }
      return false;
    }

    function summaryCard(row) {
      var node = row;
      var depth = 0;
      while (node && depth < 4) {
        var labels =
          typeof node.querySelectorAll === "function" ? node.querySelectorAll(GROUP_LABEL_SELECTOR) : [];
        var i;
        for (i = 0; i < labels.length; i += 1) {
          if (collapsed(labels[i]) === SUMMARY_LABEL) {
            return true;
          }
        }
        node = node.parentElement || null;
        depth += 1;
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
      text = collapsed(button && typeof button.querySelector === "function" ? button.querySelector("p") : null);
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
      var pulsing = typeof row.querySelectorAll === "function" ? row.querySelectorAll(LIVE_ICON_SELECTOR) : [];
      text = collapsed(pulsing.length ? pulsing[pulsing.length - 1] : null);
      if (text) {
        return text;
      }
      var group = typeof row.querySelectorAll === "function" ? row.querySelectorAll(GROUP_LABEL_SELECTOR) : [];
      text = collapsed(group.length ? group[group.length - 1] : null);
      if (text) {
        return text;
      }
      var spans = typeof row.querySelectorAll === "function" ? row.querySelectorAll(LABEL_SPAN_SELECTOR) : [];
      if (spans.length) {
        var span = spans[spans.length - 1];
        text = collapsed(span);
        var link = typeof span.querySelector === "function" ? span.querySelector("a") : null;
        var linkText = collapsed(link);
        if (linkText) {
          text = squash(text.split(linkText).join(" "));
        }
        if (text) {
          return text;
        }
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

    function rowPres(row) {
      if (!row) {
        return [];
      }
      if (typeof row.querySelectorAll === "function") {
        var list = row.querySelectorAll("pre");
        if (list && list.length) {
          return list;
        }
      }
      if (typeof row.querySelector === "function") {
        var panel = row.querySelector("pre");
        if (panel) {
          return [panel];
        }
      }
      return [];
    }

    function rowCommand(row) {
      var pres = rowPres(row);
      var i;
      for (i = pres.length - 1; i >= 0; i -= 1) {
        var text = String(pres[i].textContent || "");
        if (/^\s*\$/.test(text) || POLL_RE.test(text.toLowerCase())) {
          return text;
        }
      }
      return pres.length ? String(pres[0].textContent || "") : "";
    }

    function pollWaitsOnGate(row) {
      var pres = rowPres(row);
      var cmdIndex = 0;
      var i;
      for (i = pres.length - 1; i >= 0; i -= 1) {
        var text = String(pres[i].textContent || "");
        if (/^\s*\$/.test(text) || POLL_RE.test(text.toLowerCase())) {
          cmdIndex = i;
          break;
        }
      }
      for (i = cmdIndex; i < pres.length; i += 1) {
        if (POLL_GATE_RUNNING_RE.test(String(pres[i].textContent || ""))) {
          return true;
        }
      }
      return false;
    }

    function emojiForRow(row) {
      if (!row) {
        titleRowKind = "none";
        return null;
      }
      var type = rowKind(row);
      if (type === "chat") {
        titleRowKind = "chat";
        return AGENT_EMOJI;
      }
      if (type === "reasoning") {
        titleRowKind = "reasoning";
        return REASONING_EMOJI;
      }
      if (POLL_RE.test(rowCommand(row).toLowerCase())) {
        if (pollWaitsOnGate(row)) {
          titleRowKind = "action";
          return BASH_EMOJI;
        }
        titleRowKind = "poll";
        return WAITING_EMOJI;
      }
      if (typeof row.querySelector === "function" && row.querySelector(PLAY_SELECTOR)) {
        titleRowKind = "play";
        return BASH_EMOJI;
      }
      titleRowKind = "action";
      return actionEmoji(liveLabel(row));
    }

    function currentPath() {
      return typeof location !== "undefined" ? String(location.pathname || "") : "";
    }

    function repoForTitle(doc) {
      var name = repoFromLink(doc.querySelector(REPO_LINK_SELECTOR)) || promptRepo(doc);
      var path = currentPath();
      if (name) {
        lastRepo = name;
        lastPath = path;
        return name;
      }
      return lastRepo && path === lastPath ? lastRepo : null;
    }

    function waitingText(row, canvas) {
      var kids = row && row.children ? row.children : [];
      var i;
      for (i = 0; i < kids.length; i += 1) {
        if (
          kids[i] === canvas ||
          (typeof kids[i].contains === "function" && kids[i].contains(canvas))
        ) {
          continue;
        }
        if (typeof kids[i].querySelectorAll !== "function") continue;
        var spans = kids[i].querySelectorAll(WAITING_TEXT_SELECTOR);
        if (spans && spans.length) return true;
      }
      return false;
    }

    function waitingSignal(doc) {
      if (!doc || typeof doc.querySelectorAll !== "function") {
        return false;
      }
      var canvases = doc.querySelectorAll(WAITING_SELECTOR);
      var i;
      for (i = 0; i < canvases.length; i += 1) {
        var node = canvases[i];
        var depth = 0;
        while (node && depth < 3) {
          node = node.parentElement || null;
          depth += 1;
          if (node && waitingText(node, canvases[i])) return true;
        }
      }
      return false;
    }

    function heldEmojiFor(doc) {
      titleRowKind = null;
      var captcha = captchaSignal(doc);
      titleConditions = { captcha: captcha };
      if (captcha) {
        heldEmoji = CAPTCHA_EMOJI;
        heldEmojiAt = Date.now();
        heldEmojiNeedsTurn = false;
        return CAPTCHA_EMOJI;
      }
      var question = questionSignal(doc);
      titleConditions.question = question;
      if (question) {
        heldEmoji = QUESTION_EMOJI;
        heldEmojiAt = Date.now();
        heldEmojiNeedsTurn = false;
        return QUESTION_EMOJI;
      }
      var live = stopSignal(doc);
      titleConditions.live = live;
      var needsTurn = false;
      var row = null;
      var emoji = null;
      var root = live ? lastMessageRoot(doc) : null;
      if (root && !userRoot(root)) {
        row = newestRow(root);
        if (row && summaryCard(row)) {
          row = null;
        }
        emoji = emojiForRow(row);
        if (emoji) {
          needsTurn = true;
        }
      }
      if (!emoji && live && waitingSignal(doc)) {
        emoji = HOURGLASS_EMOJI;
        needsTurn = true;
      }
      if (emoji) {
        heldEmoji = emoji;
        heldEmojiAt = Date.now();
        heldEmojiNeedsTurn = needsTurn;
        return emoji;
      }
      if (
        heldEmoji &&
        Date.now() - heldEmojiAt < EMOJI_HOLD_MS &&
        (!heldEmojiNeedsTurn || live)
      ) {
        return heldEmoji;
      }
      heldEmoji = null;
      heldEmojiNeedsTurn = false;
      return null;
    }

    function desiredTitle(doc) {
      var name = repoForTitle(doc);
      if (!name) {
        return null;
      }
      var emoji = heldEmojiFor(doc);
      titleEmoji = emoji || "";
      var base = TITLE_PREFIX + name;
      return emoji ? base + " " + emoji : base;
    }

    var titleEmoji = "";
    var appliedTitle = null;
    var priorTitle = null;
    var titleConditions = {};
    var titleRowKind = null;
    var lastRepo = null;
    var lastPath = null;
    function syncTitle(doc) {
      var desired = desiredTitle(doc);
      if (desired) {
        if (doc.title === desired) return false;
        logEvent("title", "changed", { type: titleRowKind || "none", emoji: titleEmoji, repo: repoForTitle(doc) });
        logEvent("title", "conditions", titleConditions, "debug");
        appliedTitle = desired;
        doc.title = desired;
        return true;
      }
      return restoreTitle(doc);
    }

    function restoreTitle(doc) {
      if (!appliedTitle || doc.title !== appliedTitle) return false;
      var changed = doc.title !== priorTitle;
      if (changed) {
        doc.title = priorTitle;
        logEvent("title", "restored");
      }
      appliedTitle = null;
      return changed;
    }

    if (exposeChecks("tabTitle", {
      repoFromLink: repoFromLink,
      repoForTitle: repoForTitle,
      desiredTitle: desiredTitle,
      syncTitle: syncTitle,
      restoreTitle: restoreTitle,
      liveLabel: liveLabel,
      stopSignal: stopSignal,
      classOf: classOf,
      childChain: childChain,
      lastRoot: lastMessageRoot,
      userRoot: userRoot,
      rowContainer: rowContainer,
      newestRow: newestRow,
      rowKind: rowKind,
      summaryCard: summaryCard,
      BASH_EMOJI: BASH_EMOJI,
      PLAY_SELECTOR: PLAY_SELECTOR,
      AGENT_EMOJI: AGENT_EMOJI,
      REASONING_EMOJI: REASONING_EMOJI,
      waitingSignal: waitingSignal,
      emojiForRow: emojiForRow,
      actionEmoji: actionEmoji,
      TITLE_PREFIX: TITLE_PREFIX,
      EMOJI_HOLD_MS: EMOJI_HOLD_MS,
      POLL_RE: POLL_RE,
      MESSAGE_SELECTOR: MESSAGE_SELECTOR,
      LIVE_ICON_SELECTOR: LIVE_ICON_SELECTOR,
      LIVE_LABEL_SELECTOR: LIVE_LABEL_SELECTOR,
      GROUP_LABEL_SELECTOR: GROUP_LABEL_SELECTOR,
      LABEL_SPAN_SELECTOR: LABEL_SPAN_SELECTOR,
      REPO_LINK_SELECTOR: REPO_LINK_SELECTOR,
      WAITING_SELECTOR: WAITING_SELECTOR,
      WAITING_TEXT_SELECTOR: WAITING_TEXT_SELECTOR,
      HOURGLASS_EMOJI: HOURGLASS_EMOJI,
      CAPTCHA_SELECTOR: CAPTCHA_SELECTOR,
      CAPTCHA_EMOJI: CAPTCHA_EMOJI,
      captchaSignal: captchaSignal,
      QUESTION_SELECTOR: QUESTION_SELECTOR,
      QUESTION_EMOJI: QUESTION_EMOJI,
      questionSignal: questionSignal,
      openDialog: openDialog,
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
    var titleTimer = null;
    var titleEntry = null;
    var TITLE_INTERVAL_KEY = "clankers-arena-title-interval-ms";

    function titleTickMs() {
      var ms = Number(GM_getValue(TITLE_INTERVAL_KEY, 1000));
      if (!isFinite(ms) || ms < 1000) return 1000;
      return Math.min(Math.round(ms), 60000);
    }

    function titleStep() {
      if (document.documentElement !== observedRoot) {
        observeRoot();
      }
      syncTitle(document);
    }

    function restartTitleTimer() {
      if (titleTimer !== null) clearInterval(titleTimer);
      titleTimer = setInterval(titleStep, titleTickMs());
    }

    function titleIntervalLabel() {
      return "Tab title - every " + Math.round(titleTickMs() / 1000) + " s";
    }

    function registerTitleInterval() {
      if (titleEntry !== null) menuDrop(titleEntry);
      titleEntry = menuAdd(titleIntervalLabel, setTitleTickByPrompt);
    }

    function setTitleTickByPrompt() {
      if (typeof prompt !== "function") return;
      var answer = prompt(
        "How often should the tab title update? Enter 1 to 60 seconds.",
        String(Math.round(titleTickMs() / 1000)),
      );
      if (answer === null) {
        registerTitleInterval();
        return;
      }
      var seconds = Number(String(answer).trim());
      if (!isFinite(seconds) || seconds < 1) {
        registerTitleInterval();
        return;
      }
      GM_setValue(TITLE_INTERVAL_KEY, Math.min(Math.round(seconds), 60) * 1000);
      restartTitleTimer();
      registerTitleInterval();
    }

    restartTitleTimer();
    registerTitleInterval();
    restartTitleTimerHook = function () {
      restartTitleTimer();
      registerTitleInterval();
    };
    function onRoute() {
      lastRepo = null;
      lastPath = null;
      syncTitle(document);
    }
    window.addEventListener("popstate", onRoute);
    return function () {
      restartTitleTimerHook = null;
      clearInterval(titleTimer);
      if (titleEntry !== null) {
        menuDrop(titleEntry);
        titleEntry = null;
      }
      observer.disconnect();
      window.removeEventListener("popstate", onRoute);
      restoreTitle(document);
      appliedTitle = null;
    };
  });

  exposeChecks("pause", { PAUSE_KEY: PAUSE_KEY, pauseLabel: pauseLabel });
  exposeChecks("menus", {
    menuRank: menuRank,
    MENU_ORDER: MENU_ORDER,
    SHOW_SETTINGS_BUTTON_KEY: SHOW_SETTINGS_BUTTON_KEY,
    showSettingsButtonLabel: showSettingsButtonLabel,
  });
  exposeChecks("timers", { jitteredTimer: jitteredTimer, HTTP_JITTER_MS: HTTP_JITTER_MS });
  showPauseMenu();
  showSettingsMenu();
  menuOpen();

})();
