// ==UserScript==
// @name         Arena.ai | NemoUtils | v1.13.6
// @namespace    https://github.com/nemoe7/clankers
// @version      1.13.6
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

  var USERSCRIPT_VERSION = "1.13.6";
  var USERSCRIPT_VERSION_HEADER = "X-Clankers-Userscript-Version";

  function userscriptVersion() {
    try {
      if (
        typeof GM_info === "object" &&
        GM_info &&
        GM_info.script &&
        typeof GM_info.script.version === "string" &&
        GM_info.script.version.trim()
      ) {
        return GM_info.script.version.trim();
      }
    } catch (err) {}
    return USERSCRIPT_VERSION;
  }

  function previewHeaders(hasJson) {
    var headers = {};
    headers[USERSCRIPT_VERSION_HEADER] = userscriptVersion();
    if (hasJson) headers["Content-Type"] = "application/json";
    return headers;
  }

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
    state: ["no-stamp", "compare", "force-stamp", "failed", "proxy-needed", "download", "saved", "no-preview", "moved", "forced", "confirmation", "no-write", "requested", "reset-accept"],
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
    route: ["link", "manager", "stamped", "proxy"],
    emoji: ["", "💬", "💭", "🖥️", "📖", "✏️", "🔍", "💤", "📜", "❓", "⚙️", "⏳", "🛡️"],
    level: LOG_LEVELS,
    code: ["unknown", "manager-download", "copy-state", "missing-branch", "older-history", "proxy-unconfigured", "proxy-get", "proxy-put", "autosave", "autosave-get", "autosave-compare", "save-receipt", "NotAllowedError", "AbortError", "NotFoundError", "SecurityError", "TypeError", "Error"],
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
  var STATE_TITLE_RE = /^(?:\* )?Arena \| (\S+)/;

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
  var PREVIEW_DRAWER_LOCK_KEY = "clankers-arena-preview-drawer-lock";
  var PREVIEW_DRAWER_WIDTH_KEY = "clankers-arena-preview-drawer-width-px";
  var PREVIEW_DRAWER_DEFAULT_PX = 1398;
  var PREVIEW_DRAWER_MIN_PX = 600;
  var PREVIEW_DRAWER_MAX_PX = 2400;
  var GREEK_LETTER_NAMES = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta",
    "eta", "theta", "iota", "kappa", "lambda", "mu",
    "nu", "xi", "omicron", "pi", "rho", "sigma",
    "tau", "upsilon", "phi", "chi", "psi", "omega"
  ];
  var GREEK_LETTER_SYMBOLS = {
    alpha: "\u03B1",
    beta: "\u03B2",
    gamma: "\u03B3",
    delta: "\u03B4",
    epsilon: "\u03B5",
    zeta: "\u03B6",
    eta: "\u03B7",
    theta: "\u03B8",
    iota: "\u03B9",
    kappa: "\u03BA",
    lambda: "\u03BB",
    mu: "\u03BC",
    nu: "\u03BD",
    xi: "\u03BE",
    omicron: "\u03BF",
    pi: "\u03C0",
    rho: "\u03C1",
    sigma: "\u03C3",
    tau: "\u03C4",
    upsilon: "\u03C5",
    phi: "\u03C6",
    chi: "\u03C7",
    psi: "\u03C8",
    omega: "\u03C9"
  };
  var featureRegistry = [];
  var restartStateWatchHook = null;
  var syncPreviewProxyHook = null;
  var syncPreviewBoardHook = null;
  var syncPreviewDrawerLockHook = null;
  var previewUiRepo = "";
  var previewUiBranch = "";
  var localSessionReportsByBranch = Object.create(null);

  function isSafeRecordKey(k) {
    return typeof k === "string" && k.length > 0 &&
      k !== "__proto__" && k !== "constructor" && k !== "prototype";
  }

  function previewDrawerLockOn() {
    if (typeof GM_getValue !== "function") return true;
    return GM_getValue(PREVIEW_DRAWER_LOCK_KEY, true) !== false;
  }

  function previewDrawerWidthPx() {
    if (typeof GM_getValue !== "function") return PREVIEW_DRAWER_DEFAULT_PX;
    var px = Number(GM_getValue(PREVIEW_DRAWER_WIDTH_KEY, PREVIEW_DRAWER_DEFAULT_PX));
    if (!isFinite(px) || px < PREVIEW_DRAWER_MIN_PX) return PREVIEW_DRAWER_DEFAULT_PX;
    return Math.min(Math.round(px), PREVIEW_DRAWER_MAX_PX);
  }

  function previewDrawerWidthCss() {
    return previewDrawerWidthPx() + "px";
  }

  function setPreviewUiBranch(sid) {
    var nextSid = boardBranch(sid || "");
    if (!nextSid || nextSid === previewUiBranch) return;
    previewUiBranch = nextSid;
    if (typeof syncPreviewProxyHook === "function") syncPreviewProxyHook();
    if (typeof syncTitleNowHook === "function") syncTitleNowHook();
  }
  var syncTitleNowHook = null;
  var syncProxySettingsHook = null;
  var postKeyNowHook = null;
  var applyTrimKeepHook = null;
  var registerTrimCapHook = null;
  var restartTrimTimerHook = null;
  var trimNowHook = null;
  var forceSaveStateHook = null;
  var setResetWindowHook = null;
  var restartTitleTimerHook = null;
  var syncSettingsModalVisibilityHook = null;
  var openSettingsModalHook = null;

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

  var SKILL_HTTP_JITTER_MAX_MS = 400;

  function isSkillPreviewUrl(url) {
    return /^https:\/\/sbx-[a-z0-9-]+\.arena\.site(?::\d+)?(?:\/|$)/i.test(
      String(url || "").trim(),
    );
  }

  function randomHttpJitterWindowMs() {
    var span = httpJitterMs();
    return span > 0 ? Math.floor(Math.random() * (span + 1)) : 0;
  }

  function randomSkillHttpJitterMs() {
    var span = Math.min(httpJitterMs(), SKILL_HTTP_JITTER_MAX_MS);
    return span > 0 ? Math.floor(Math.random() * (span + 1)) : 0;
  }

  function withSkillHttpJitter(url, send) {
    if (!isSkillPreviewUrl(url) || typeof setTimeout !== "function") {
      send();
      return null;
    }
    return setTimeout(send, randomSkillHttpJitterMs());
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

    function discoverPreviews(doc, reportedRepo, reportedBranch) {
      if (!doc || typeof doc.querySelectorAll !== "function") return [];
      var rawHeader = previewHeaderRaw(doc);
      if (isUnavailablePreviewName(rawHeader)) return [];
      var domName = isUnavailablePreviewName(rawHeader) ? "" : rawHeader;
      var docScope = stateScope(doc);
      var uiRepo = String(
        reportedRepo !== undefined ? reportedRepo : (previewUiRepo || docScope.repo || ""),
      ).trim();
      var sid = boardBranch(
        reportedBranch !== undefined
          ? reportedBranch
          : (previewUiBranch || docScope.branch || ""),
      );
      var board = readGlobalBoard();
      var hasMain = Boolean(board && board.main_session_id);
      if (sid && hasMain && boardRoleFor(board, sid) === "worker") {
        return [];
      }
      var steeringBase = previewBase(doc) || lastPreviewBase || "";
      var steeringOrigin = steeringBase ? (/^https:\/\/[^/]+/i.exec(steeringBase) || [""])[0] : "";
      var steeringRoot = steeringOrigin ? steeringOrigin + "/" : "";
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
        var isSteeringFrame = Boolean(
          (steeringRoot && root === steeringRoot) ||
          /\s-\sSteering$/i.test(domName) ||
          (reportedRepo !== undefined && uiRepo && !steeringRoot && !domName),
        );
        if (isSteeringFrame && hasMain && !sid && reportedBranch === undefined) {
          continue;
        }
        resolvedName = isSteeringFrame && uiRepo
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

    function notedKeyFor(base) {
      return base ? NOTED_KEY + "::" + base : NOTED_KEY;
    }

    function noteKey(key, host, type) {
      var base = previewBase(document);
      var scopedKey = notedKeyFor(base);
      if (GM_getValue(scopedKey, "") === key) return;
      GM_setValue(scopedKey, key);
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

    function requestJson(method, url, payload, done, includeVersion) {
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
        var reqHeaders = includeVersion === false
          ? (payload ? { "Content-Type": "application/json" } : {})
          : previewHeaders(Boolean(payload));
        withSkillHttpJitter(url, function () {
          GM_xmlhttpRequest({
            method: method,
            url: url,
            headers: reqHeaders,
            data: payload ? JSON.stringify(payload) : undefined,
            onload: function (answer) {
              finish(answer.responseText, answer.status);
            },
            onerror: function () {
              finish("", 0);
            },
          });
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
      requestJson: requestJson,
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
        requestJson("POST", endpoint, payload, function () {}, false);
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
        }, false);
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
          GM_setValue(notedKeyFor(previewBase(document)), body.key);
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
      if (typeof syncPreviewBoardHook === "function" && boardProxyConfig()) {
        var syncFromKeyWatch = function () {
          if (shouldAutoSyncBoard(readGlobalBoard(), document)) {
            syncPreviewBoardHook(boardPreviewBase(document), "", "", { passive: true });
          }
        };
        if (!proxyBoardCache) {
          pullProxyBoard(true).then(syncFromKeyWatch);
        } else {
          syncFromKeyWatch();
        }
      }
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
        withSkillHttpJitter(url, function () {
          GM_xmlhttpRequest({
            method: "POST",
            url: url,
            headers: previewHeaders(true),
            data: JSON.stringify(payload),
            onload: function (answer) {
              done(answer && answer.status ? answer.status : 0);
            },
            onerror: function () {
              done(0);
            },
          });
        });
        return;
      }
      if (typeof fetch === "function") {
        withSkillHttpJitter(url, function () {
          fetch(url, {
            method: "POST",
            headers: previewHeaders(true),
            body: JSON.stringify(payload),
          })
            .then(function (r) {
              done(r && r.status ? r.status : 0);
            })
            .catch(function () {
              done(0);
            });
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

    var PREVIEW_DRAWER_OUTER_SELECTOR =
      "body > div:nth-child(4) > div > main > div > div > div.absolute.bottom-0.end-0.top-0.z-10.overflow-clip";
    var PREVIEW_DRAWER_OUTER_FALLBACK_SELECTOR =
      "main div.absolute.bottom-0.end-0.top-0.z-10.overflow-clip";
    var PREVIEW_DRAWER_SELECTOR =
      "body > div:nth-child(4) > div > main > div > div > div.absolute.bottom-0.end-0.top-0.z-10.overflow-clip > div";
    var PREVIEW_DRAWER_FALLBACK_SELECTOR =
      "main div.absolute.bottom-0.end-0.top-0.z-10.overflow-clip > div";
    var PREVIEW_MAIN_SELECTOR =
      "body > div:nth-child(4) > div > main > div > div > div.relative.flex.min-w-0.flex-1.flex-col";
    var PREVIEW_MAIN_FALLBACK_SELECTOR =
      "main div.relative.flex.min-w-0.flex-1.flex-col";
    var PREVIEW_HEADER_OFFSET_SELECTOR = "div.absolute.start-0.top-0.z-20";
    var PREVIEW_TRANSCRIPT_LOG_SELECTOR =
      '[data-perf-target="transcript"] > div[role="log"], div[data-custom-scrollbar="true"][role="log"]';
    var PREVIEW_COMPOSER_WRAP_SELECTOR =
      "div.flex.min-h-0.flex-1.flex-col > div.shrink-0";
    var PREVIEW_OPEN_CONTENT_SELECTOR =
      'button[aria-label="Close preview"], button[aria-label="Reload preview"], iframe[title^="App preview"], input[aria-label^="Preview path"]';
    var WORKSPACE_CARDS_SELECTOR = '[aria-label="Workspace card views"]';
    var PREVIEW_DRAWER_WIDTH = "1398px";
    var PREVIEW_DRAWER_STYLE_ID = "clankers-preview-drawer-style";

    function findPreviewDrawer(doc) {
      if (!doc || typeof doc.querySelector !== "function") {
        return null;
      }
      return (
        doc.querySelector(PREVIEW_DRAWER_SELECTOR) ||
        doc.querySelector(PREVIEW_DRAWER_FALLBACK_SELECTOR) ||
        null
      );
    }

    function findPreviewDrawerOuter(doc, drawer) {
      if (drawer && drawer.parentElement && drawer.parentElement.style) {
        return drawer.parentElement;
      }
      if (!doc || typeof doc.querySelector !== "function") {
        return null;
      }
      return (
        doc.querySelector(PREVIEW_DRAWER_OUTER_SELECTOR) ||
        doc.querySelector(PREVIEW_DRAWER_OUTER_FALLBACK_SELECTOR) ||
        null
      );
    }

    function findPreviewMain(doc) {
      if (!doc || typeof doc.querySelector !== "function") {
        return null;
      }
      return (
        doc.querySelector(PREVIEW_MAIN_SELECTOR) ||
        doc.querySelector(PREVIEW_MAIN_FALLBACK_SELECTOR) ||
        null
      );
    }

    function readStyleProp(node, prop) {
      if (!node || !node.style) return "";
      if (typeof node.style.getPropertyValue === "function") {
        return String(node.style.getPropertyValue(prop) || "");
      }
      var camel = prop.replace(/-([a-z])/g, function (_, c) {
        return c.toUpperCase();
      });
      return String(node.style[camel] || node.style[prop] || "");
    }

    function applyImportantStyle(node, prop, value) {
      if (!node || !node.style) return false;
      var camel = prop.replace(/-([a-z])/g, function (_, c) {
        return c.toUpperCase();
      });
      if (
        typeof node.style.getPropertyValue === "function" &&
        typeof node.style.setProperty === "function"
      ) {
        if (
          node.style.getPropertyValue(prop) === value &&
          (typeof node.style.getPropertyPriority !== "function" ||
            node.style.getPropertyPriority(prop) === "important")
        ) {
          return false;
        }
        node.style.setProperty(prop, value, "important");
        return true;
      }
      if (node.style[camel] === value) {
        return false;
      }
      node.style[camel] = value;
      return true;
    }

    function clearForcedStyle(node, prop, fallbackValue) {
      if (!node || !node.style) return false;
      var target = fallbackValue || "0px";
      var current = readStyleProp(node, prop).trim();
      var priority =
        typeof node.style.getPropertyPriority === "function"
          ? String(node.style.getPropertyPriority(prop) || "")
          : "";
      if (current === target && priority !== "important") {
        return false;
      }
      if (
        priority !== "important" &&
        current !== PREVIEW_DRAWER_WIDTH &&
        current !== previewDrawerWidthCss()
      ) {
        return false;
      }
      var camel = prop.replace(/-([a-z])/g, function (_, c) {
        return c.toUpperCase();
      });
      if (typeof node.style.setProperty === "function") {
        node.style.setProperty(prop, target, "");
        return true;
      }
      node.style[camel] = target;
      return true;
    }

    function isInsideTranscriptLog(node) {
      var cur = node;
      while (cur) {
        if (
          cur.classList &&
          typeof cur.classList.contains === "function" &&
          cur.classList.contains("max-w-3xl")
        ) {
          return true;
        }
        if (typeof cur.getAttribute === "function") {
          var role = cur.getAttribute("role");
          var perf = cur.getAttribute("data-perf-target");
          if (role === "log" || perf === "transcript") {
            return true;
          }
          var styleAttr = String(cur.getAttribute("style") || "");
          if (/height\s*:\s*24px/i.test(styleAttr)) {
            return true;
          }
        }
        cur = cur.parentElement || cur.parentNode || null;
      }
      return false;
    }

    function clearTranscriptColumnPadding(mainCol) {
      if (!mainCol || typeof mainCol.querySelectorAll !== "function") return;
      var candidates = mainCol.querySelectorAll(PREVIEW_COMPOSER_WRAP_SELECTOR);
      for (var i = 0; i < candidates.length; i += 1) {
        var node = candidates[i];
        if (!isInsideTranscriptLog(node) || !node.style) continue;
        var current = readStyleProp(node, "padding-right").trim();
        if (!current) continue;
        var priority =
          typeof node.style.getPropertyPriority === "function"
            ? String(node.style.getPropertyPriority("padding-right") || "")
            : "";
        if (
          priority === "important" ||
          current === PREVIEW_DRAWER_WIDTH ||
          current === previewDrawerWidthCss()
        ) {
          if (typeof node.style.removeProperty === "function") {
            node.style.removeProperty("padding-right");
          } else if (typeof node.style.setProperty === "function") {
            node.style.setProperty("padding-right", "", "");
          } else {
            node.style.paddingRight = "";
          }
        }
      }
    }

    function findPreviewComposerWrap(mainCol) {
      if (!mainCol) return null;
      if (typeof mainCol.querySelectorAll === "function") {
        var candidates = mainCol.querySelectorAll(PREVIEW_COMPOSER_WRAP_SELECTOR);
        for (var i = 0; i < candidates.length; i += 1) {
          if (!isInsideTranscriptLog(candidates[i])) {
            return candidates[i];
          }
        }
        return null;
      }
      if (typeof mainCol.querySelector === "function") {
        var single = mainCol.querySelector(PREVIEW_COMPOSER_WRAP_SELECTOR);
        return single && !isInsideTranscriptLog(single) ? single : null;
      }
      return null;
    }

    function isWorkspaceCardsDrawer(doc, drawer) {
      if (drawer && typeof drawer.querySelector === "function") {
        if (drawer.querySelector(PREVIEW_OPEN_CONTENT_SELECTOR)) {
          return false;
        }
        if (drawer.querySelector(WORKSPACE_CARDS_SELECTOR)) {
          return true;
        }
      }
      if (doc && typeof doc.querySelector === "function") {
        if (doc.querySelector(PREVIEW_OPEN_CONTENT_SELECTOR)) {
          return false;
        }
        if (doc.querySelector(WORKSPACE_CARDS_SELECTOR)) {
          return true;
        }
      }
      return false;
    }

    function isPreviewDrawerOpen(doc, drawer, mainCol) {
      if (!drawer || !drawer.style) return false;
      if (typeof drawer.getAttribute === "function" && drawer.getAttribute("aria-hidden") === "true") {
        return false;
      }
      if (
        drawer.parentElement &&
        typeof drawer.parentElement.getAttribute === "function" &&
        drawer.parentElement.getAttribute("aria-hidden") === "true"
      ) {
        return false;
      }
      if (isWorkspaceCardsDrawer(doc, drawer)) {
        return false;
      }
      if (
        drawer &&
        typeof drawer.querySelector === "function" &&
        drawer.querySelector(PREVIEW_OPEN_CONTENT_SELECTOR)
      ) {
        return true;
      }
      var rawWidth = readStyleProp(drawer, "width").trim();
      if (mainCol && typeof mainCol.querySelector === "function") {
        if (mainCol.querySelector('button[aria-label="Collapse workspace sidebar"]')) {
          if (rawWidth && /^(0(px|%|rem|em)?|256px)$/i.test(rawWidth)) {
            return false;
          }
          return true;
        }
        if (
          mainCol.querySelector(
            'button[aria-label="Expand workspace sidebar"], button[aria-label="Open workspace"]',
          )
        ) {
          return false;
        }
      }
      if (rawWidth && /^(0(px|%|rem|em)?|256px)$/i.test(rawWidth)) {
        return false;
      }
      return true;
    }

    function enforcePreviewDrawerWidth(doc) {
      var drawer = findPreviewDrawer(doc);
      var outerDrawer = findPreviewDrawerOuter(doc, drawer);
      var mainCol = findPreviewMain(doc);
      clearTranscriptColumnPadding(mainCol);
      var header =
        mainCol && typeof mainCol.querySelector === "function"
          ? mainCol.querySelector(PREVIEW_HEADER_OFFSET_SELECTOR)
          : null;
      var transcript =
        mainCol && typeof mainCol.querySelector === "function"
          ? mainCol.querySelector(PREVIEW_TRANSCRIPT_LOG_SELECTOR)
          : null;
      var composer = findPreviewComposerWrap(mainCol);
      var open = isPreviewDrawerOpen(doc, drawer, mainCol);
      if (!open || !previewDrawerLockOn()) {
        var fallback = !open
          ? isWorkspaceCardsDrawer(doc, drawer)
            ? "256px"
            : "0px"
          : previewDrawerWidthCss();
        var cleared = false;
        if (clearForcedStyle(outerDrawer, "width", fallback)) cleared = true;
        if (clearForcedStyle(drawer, "width", fallback)) cleared = true;
        if (clearForcedStyle(header, "right", fallback)) cleared = true;
        if (clearForcedStyle(transcript, "padding-right", fallback)) cleared = true;
        if (clearForcedStyle(composer, "padding-right", fallback)) cleared = true;
        return cleared;
      }
      var targetWidth = previewDrawerWidthCss();
      var changed = false;
      if (applyImportantStyle(outerDrawer, "width", targetWidth)) changed = true;
      if (applyImportantStyle(drawer, "width", targetWidth)) changed = true;
      if (applyImportantStyle(header, "right", targetWidth)) changed = true;
      if (applyImportantStyle(transcript, "padding-right", targetWidth)) changed = true;
      if (applyImportantStyle(composer, "padding-right", targetWidth)) changed = true;
      return changed;
    }

    function ensurePreviewDrawerStyle(doc) {
      var targetDoc = doc || (typeof document !== "undefined" ? document : null);
      if (!targetDoc || !targetDoc.head || typeof targetDoc.createElement !== "function") return;
      var existing =
        typeof targetDoc.getElementById === "function"
          ? targetDoc.getElementById(PREVIEW_DRAWER_STYLE_ID)
          : null;
      if (!previewDrawerLockOn()) {
        if (existing) {
          if (typeof existing.remove === "function") existing.remove();
          else if (existing.parentNode) existing.parentNode.removeChild(existing);
        }
        return;
      }
      var widthCss = previewDrawerWidthCss();
      var openScope = 'main:has(button[aria-label="Close preview"], iframe[title^="App preview"]) ';
      var nextCss =
        openScope +
        "div.absolute.bottom-0.end-0.top-0.z-10.overflow-clip{width:" +
        widthCss +
        " !important}" +
        openScope +
        "div.absolute.bottom-0.end-0.top-0.z-10.overflow-clip > div{width:" +
        widthCss +
        " !important}" +
        openScope +
        "div.relative.flex.min-w-0.flex-1.flex-col > " +
        PREVIEW_HEADER_OFFSET_SELECTOR +
        "{right:" +
        widthCss +
        " !important}" +
        openScope +
        'div.relative.flex.min-w-0.flex-1.flex-col [data-perf-target="transcript"] > div[role="log"]{padding-right:' +
        widthCss +
        " !important}" +
        openScope +
        "div.relative.flex.min-w-0.flex-1.flex-col > div.flex.min-h-0.flex-1.flex-col > div.shrink-0:not(.max-w-3xl){padding-right:" +
        widthCss +
        " !important}";
      if (existing) {
        if (existing.textContent !== nextCss) {
          existing.textContent = nextCss;
        }
        return;
      }
      var style = targetDoc.createElement("style");
      style.id = PREVIEW_DRAWER_STYLE_ID;
      style.setAttribute("id", PREVIEW_DRAWER_STYLE_ID);
      style.textContent = nextCss;
      targetDoc.head.appendChild(style);
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
      sendSteeringInterrupt: sendSteeringInterrupt,
      flagSteeringLabelViolation: flagSteeringLabelViolation,
      findPreviewDrawer: findPreviewDrawer,
      findPreviewDrawerOuter: findPreviewDrawerOuter,
      findPreviewMain: findPreviewMain,
      findPreviewComposerWrap: findPreviewComposerWrap,
      isPreviewDrawerOpen: isPreviewDrawerOpen,
      enforcePreviewDrawerWidth: enforcePreviewDrawerWidth,
      ensurePreviewDrawerStyle: ensurePreviewDrawerStyle,
      PREVIEW_DRAWER_OUTER_SELECTOR: PREVIEW_DRAWER_OUTER_SELECTOR,
      PREVIEW_DRAWER_SELECTOR: PREVIEW_DRAWER_SELECTOR,
      PREVIEW_MAIN_SELECTOR: PREVIEW_MAIN_SELECTOR,
      PREVIEW_DRAWER_WIDTH: PREVIEW_DRAWER_WIDTH,
      PREVIEW_DRAWER_LOCK_KEY: PREVIEW_DRAWER_LOCK_KEY,
      PREVIEW_DRAWER_WIDTH_KEY: PREVIEW_DRAWER_WIDTH_KEY,
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
      ensurePreviewDrawerStyle();
      enforcePreviewDrawerWidth(document);
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

    syncPreviewDrawerLockHook = function () {
      ensurePreviewDrawerStyle();
      enforcePreviewDrawerWidth(document);
    };

    var observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["src", "title", "style", "aria-label", "aria-hidden"],
    });
    window.addEventListener("popstate", sync);
    sync();
    return function () {
      if (syncPreviewDrawerLockHook) syncPreviewDrawerLockHook = null;
      observer.disconnect();
      window.removeEventListener("popstate", sync);
      clearClickTimer();
      if (typeof document.getElementById === "function") {
        var styleNode = document.getElementById(PREVIEW_DRAWER_STYLE_ID);
        if (styleNode) {
          if (typeof styleNode.remove === "function") styleNode.remove();
          else if (styleNode.parentNode) styleNode.parentNode.removeChild(styleNode);
        }
      }
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

      function buildSingleRangeRow(labelText, key, curVal, minVal, maxVal, stepVal, unitLabel, onSaved) {
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
          "position:absolute;top:0;bottom:0;left:0;background:#d97757;border-radius:999px";
        rail.appendChild(fill);

        var input = document.createElement("input");
        input.type = "range";
        input.min = String(minVal);
        input.max = String(maxVal);
        input.step = String(stepVal || 1);
        input.value = String(curVal);
        input.setAttribute("data-setting-key", key);
        input.setAttribute("aria-label", labelText);
        input.style.cssText =
          "position:absolute;left:0;top:0;width:100%;height:100%;margin:0;background:transparent;" +
          "pointer-events:none;accent-color:#d97757;z-index:2";

        function updateReadout(val) {
          readout.textContent = val + (unitLabel ? " " + unitLabel : "");
          var spanRange = Math.max(1, maxVal - minVal);
          var pct = Math.min(100, Math.max(0, ((val - minVal) / spanRange) * 100));
          fill.style.width = pct + "%";
        }
        updateReadout(curVal);

        function applyVal() {
          var raw = Number(String(input.value).trim());
          if (!isFinite(raw)) return;
          var clamped = Math.min(Math.max(Math.round(raw), minVal), maxVal);
          input.value = String(clamped);
          GM_setValue(key, clamped);
          updateReadout(clamped);
          menuRefresh();
          if (typeof onSaved === "function") onSaved(clamped);
        }

        input.addEventListener("input", applyVal);
        input.addEventListener("change", applyVal);

        track.appendChild(rail);
        track.appendChild(input);
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
        if (key === PREVIEW_DRAWER_LOCK_KEY) {
          return featureStoredOn("open-steering") && previewDrawerLockOn();
        }
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
        "Force save state",
        buildActionRow("Force save", "Force save", "force-save", function () {
          if (typeof forceSaveStateHook === "function") forceSaveStateHook();
        }),
        "state-download",
      );
      addDependentSectionItem(
        "Steering",
        "Lock drawer width",
        buildCheckboxRow(
          "Lock drawer width",
          PREVIEW_DRAWER_LOCK_KEY,
          previewDrawerLockOn(),
          function (next) {
            GM_setValue(PREVIEW_DRAWER_LOCK_KEY, Boolean(next));
            if (typeof syncPreviewDrawerLockHook === "function") {
              syncPreviewDrawerLockHook();
            }
            syncDependentVisibility();
            menuRefresh();
          },
        ),
        "open-steering",
      );
      addDependentSectionItem(
        "Steering",
        "Drawer width (px)",
        buildSingleRangeRow(
          "Drawer width (px)",
          PREVIEW_DRAWER_WIDTH_KEY,
          previewDrawerWidthPx(),
          PREVIEW_DRAWER_MIN_PX,
          PREVIEW_DRAWER_MAX_PX,
          1,
          "px",
          function () {
            if (typeof syncPreviewDrawerLockHook === "function") {
              syncPreviewDrawerLockHook();
            }
          },
        ),
        PREVIEW_DRAWER_LOCK_KEY,
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
    openSettingsModalHook = openSettingsModal;

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
    var spacerStyles = new WeakMap();
    var editorStates = new WeakMap();

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

    var pendingMutations = [];
    var mutationFrame = null;
    function flushMutations() {
      mutationFrame = null;
      var batch = pendingMutations;
      pendingMutations = [];
      enforceCurrentSpacerHeight(batch);
      var i;
      for (i = 0; i < batch.length; i += 1) {
        if (batch[i].type !== "attributes" || batch[i].attributeName !== "style") {
          sync();
          return;
        }
      }
    }
    function handleMutations(mutations) {
      if (mutations && mutations.length) {
        for (var mi = 0; mi < mutations.length; mi += 1) {
          pendingMutations.push(mutations[mi]);
        }
      }
      if (typeof requestAnimationFrame === "function") {
        if (mutationFrame === null) {
          mutationFrame = requestAnimationFrame(flushMutations);
        }
        return;
      }
      flushMutations();
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
      if (mutationFrame !== null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(mutationFrame);
        mutationFrame = null;
      }
      pendingMutations = [];
      if (typeof document.querySelectorAll === "function") {
        var hiddenEditors = document.querySelectorAll("[" + HIDE_MARK + "]");
        for (var ei = 0; ei < hiddenEditors.length; ei += 1) {
          showEditor(hiddenEditors[ei]);
        }
        var markedSpacers = document.querySelectorAll("[" + SPACER_MARK + "]");
        for (var si = 0; si < markedSpacers.length; si += 1) {
          var sp = markedSpacers[si];
          var prior = spacerStyles.get(sp);
          if (typeof sp.removeAttribute === "function") sp.removeAttribute(SPACER_MARK);
          if (prior && sp.style.getPropertyValue("height") === SPACER_HEIGHT && sp.style.getPropertyPriority("height") === "important") {
            if (prior[0]) sp.style.setProperty("height", prior[0], prior[1]);
            else sp.style.removeProperty("height");
          }
          spacerStyles.delete(sp);
        }
      }
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

  function saveMoved(branch, remembered, base, rememberedScope, rememberedBranch) {
    return !(branch || rememberedScope) ||
      (Boolean(remembered) && remembered !== base) ||
      (Boolean(branch) && Boolean(rememberedBranch) && branch !== rememberedBranch);
  }

  function overwriteAsk(moved, plan, hasSavedState, force) {
    return !force && Boolean(moved) && Boolean(hasSavedState) && plan.type === "download";
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

  function getLine(status, base) {
    return "GET " + status;
  }

  function proxyStateFailLine(detail) {
    return "Proxy state sync failed (" + (detail || "unknown") + ").";
  }

  var STATE_LINES = {
    noBranch: "Missing branch.",
    noProxy: "Configure proxy host and master key in Settings.",
  };

  var BOARD_COLLECTION_KEYS_MAP = {
    sessions: true,
    entries: true,
    task_ops: true,
    report_ops: true,
    worker_tasks: true,
    worker_reports: true,
    wakes: true,
  };

  function canonicalDiffJson(val) {
    if (val === null || typeof val !== "object") return JSON.stringify(val);
    if (Array.isArray(val)) {
      return "[" + val.map(canonicalDiffJson).join(",") + "]";
    }
    var keys = Object.keys(val).sort();
    var parts = [];
    for (var i = 0; i < keys.length; i += 1) {
      var k = keys[i];
      if (val[k] !== undefined) {
        parts.push(JSON.stringify(k) + ":" + canonicalDiffJson(val[k]));
      }
    }
    return "{" + parts.join(",") + "}";
  }

  function stateRecordGroup(record) {
    if (!record || typeof record !== "object") return "notes";
    if ("markdown" in record) return "reports";
    if ("title" in record) return "tasks";
    if ("report_id" in record) return "answers";
    return "notes";
  }

  function stateRecordKey(record) {
    if (!record || typeof record !== "object") return canonicalDiffJson(record);
    var recId = String(record.id || "").trim();
    if (recId) return recId;
    if (record.seq !== undefined && record.seq !== null) return "seq:" + String(record.seq);
    return canonicalDiffJson(record);
  }

  function computeStateDiff(prevCore, nextCore, baseRev, nextRev) {
    var prevMap = Object.create(null);
    var i;
    var row;
    var pairKey;
    if (Array.isArray(prevCore)) {
      for (i = 0; i < prevCore.length; i += 1) {
        row = prevCore[i];
        if (!row || typeof row !== "object" || row.type === "userscript-autosave") continue;
        var pGrp = stateRecordGroup(row);
        var pKey = stateRecordKey(row);
        pairKey = pGrp + "\u0000" + pKey;
        prevMap[pairKey] = { grp: pGrp, key: pKey, json: canonicalDiffJson(row) };
      }
    }
    var nextSeen = Object.create(null);
    var upserts = [];
    if (Array.isArray(nextCore)) {
      for (i = 0; i < nextCore.length; i += 1) {
        row = nextCore[i];
        if (!row || typeof row !== "object" || row.type === "userscript-autosave") continue;
        var nGrp = stateRecordGroup(row);
        var nKey = stateRecordKey(row);
        pairKey = nGrp + "\u0000" + nKey;
        nextSeen[pairKey] = true;
        var enc = canonicalDiffJson(row);
        if (!prevMap[pairKey] || prevMap[pairKey].json !== enc) {
          upserts.push(row);
        }
      }
    }
    var tombstones = [];
    var prevKeys = Object.keys(prevMap).sort();
    for (i = 0; i < prevKeys.length; i += 1) {
      if (!nextSeen[prevKeys[i]]) {
        tombstones.push({ group: prevMap[prevKeys[i]].grp, key: prevMap[prevKeys[i]].key });
      }
    }
    return {
      base_rev: Number(baseRev) || 0,
      rev: Number(nextRev) || 0,
      upserts: upserts,
      tombstones: tombstones,
    };
  }

  function applyStateDiff(baseCore, diffObj) {
    if (!diffObj || typeof diffObj !== "object") return Array.isArray(baseCore) ? baseCore.slice() : [];
    var upserts = Array.isArray(diffObj.upserts) ? diffObj.upserts : [];
    var tombstones = Array.isArray(diffObj.tombstones) ? diffObj.tombstones : [];
    var index = Object.create(null);
    var order = [];
    var i;
    var row;
    var pairKey;
    if (Array.isArray(baseCore)) {
      for (i = 0; i < baseCore.length; i += 1) {
        row = baseCore[i];
        if (!row || typeof row !== "object" || row.type === "userscript-autosave") continue;
        pairKey = stateRecordGroup(row) + "\u0000" + stateRecordKey(row);
        if (!index[pairKey]) order.push(pairKey);
        index[pairKey] = Object.assign({}, row);
      }
    }
    var removed = Object.create(null);
    for (i = 0; i < tombstones.length; i += 1) {
      var tomb = tombstones[i];
      if (!tomb || typeof tomb !== "object") continue;
      var tGrp = String(tomb.group || "").trim();
      var tKey = String(tomb.key || "").trim();
      if (tGrp && tKey) {
        removed[tGrp + "\u0000" + tKey] = true;
        delete index[tGrp + "\u0000" + tKey];
      }
    }
    for (i = 0; i < upserts.length; i += 1) {
      row = upserts[i];
      if (!row || typeof row !== "object" || row.type === "userscript-autosave") continue;
      pairKey = stateRecordGroup(row) + "\u0000" + stateRecordKey(row);
      delete removed[pairKey];
      if (!index[pairKey]) order.push(pairKey);
      index[pairKey] = Object.assign({}, row);
    }
    var out = [];
    for (i = 0; i < order.length; i += 1) {
      if (index[order[i]] && !removed[order[i]]) out.push(index[order[i]]);
    }
    return out;
  }

  function decomposeBoardRecords(board) {
    var data = board && typeof board === "object" ? board : {};
    var records = Object.create(null);
    var meta = Object.create(null);
    Object.keys(data).forEach(function (k) {
      if (isSafeRecordKey(k) && !BOARD_COLLECTION_KEYS_MAP[k]) meta[k] = data[k];
    });
    records["meta\u0000scalars"] = { type: "meta", key: "scalars", value: meta };
    if (Array.isArray(data.sessions)) {
      data.sessions.forEach(function (row, idx) {
        if (!row || typeof row !== "object") return;
        var br = String(row.branch || row.session_id || ("idx:" + idx)).trim();
        if (br) records["session\u0000" + br] = { type: "session", key: br, value: row };
      });
    }
    if (Array.isArray(data.entries)) {
      data.entries.forEach(function (row, idx) {
        if (!row || typeof row !== "object") return;
        var eid = String(row.id || ("idx:" + idx)).trim();
        if (eid) records["entry\u0000" + eid] = { type: "entry", key: eid, value: row };
      });
    }
    if (Array.isArray(data.task_ops)) {
      data.task_ops.forEach(function (row, idx) {
        if (!row || typeof row !== "object") return;
        var oid = String(row.id || ("idx:" + idx)).trim();
        if (oid) records["task_op\u0000" + oid] = { type: "task_op", key: oid, value: row };
      });
    }
    if (Array.isArray(data.report_ops)) {
      data.report_ops.forEach(function (row, idx) {
        if (!row || typeof row !== "object") return;
        var oid = String(row.id || ("idx:" + idx)).trim();
        if (oid) records["report_op\u0000" + oid] = { type: "report_op", key: oid, value: row };
      });
    }
    if (data.worker_tasks && typeof data.worker_tasks === "object") {
      Object.keys(data.worker_tasks).forEach(function (sid) {
        var cleanSid = String(sid || "").trim();
        if (isSafeRecordKey(cleanSid) && Array.isArray(data.worker_tasks[sid])) {
          records["worker_tasks\u0000" + cleanSid] = {
            type: "worker_tasks",
            key: cleanSid,
            value: data.worker_tasks[sid],
          };
        }
      });
    }
    if (data.worker_reports && typeof data.worker_reports === "object") {
      Object.keys(data.worker_reports).forEach(function (sid) {
        var cleanSid = String(sid || "").trim();
        if (isSafeRecordKey(cleanSid) && Array.isArray(data.worker_reports[sid])) {
          records["worker_reports\u0000" + cleanSid] = {
            type: "worker_reports",
            key: cleanSid,
            value: data.worker_reports[sid],
          };
        }
      });
    }
    if (data.wakes && typeof data.wakes === "object") {
      Object.keys(data.wakes).forEach(function (sid) {
        var cleanSid = String(sid || "").trim();
        if (isSafeRecordKey(cleanSid) && data.wakes[sid]) {
          records["wake\u0000" + cleanSid] = { type: "wake", key: cleanSid, value: data.wakes[sid] };
        }
      });
    }
    return records;
  }

  function recomposeBoardRecords(records) {
    var out = {
      multi_repo: false,
      linked_repos: [],
      removed_sessions: [],
      worker_ids: Object.create(null),
      worker_tasks: Object.create(null),
      task_ops: [],
      worker_reports: Object.create(null),
      report_ops: [],
      allowed_sessions: [],
      main_session_id: "",
      sessions: [],
      entries: [],
      wakes: Object.create(null),
    };
    var metaEntry = records["meta\u0000scalars"];
    if (metaEntry && metaEntry.value && typeof metaEntry.value === "object") {
      Object.keys(metaEntry.value).forEach(function (k) {
        if (isSafeRecordKey(k)) out[k] = metaEntry.value[k];
      });
    }
    Object.keys(records).forEach(function (pairKey) {
      var item = records[pairKey];
      if (!item || item.type === "meta") return;
      if (item.type === "session" && item.value && typeof item.value === "object") {
        out.sessions.push(Object.assign({}, item.value));
      } else if (item.type === "entry" && item.value && typeof item.value === "object") {
        out.entries.push(Object.assign({}, item.value));
      } else if (item.type === "task_op" && item.value && typeof item.value === "object") {
        out.task_ops.push(Object.assign({}, item.value));
      } else if (item.type === "report_op" && item.value && typeof item.value === "object") {
        out.report_ops.push(Object.assign({}, item.value));
      } else if (item.type === "worker_tasks" && isSafeRecordKey(item.key) && Array.isArray(item.value)) {
        out.worker_tasks[item.key] = item.value.slice();
      } else if (item.type === "worker_reports" && isSafeRecordKey(item.key) && Array.isArray(item.value)) {
        out.worker_reports[item.key] = item.value.slice();
      } else if (item.type === "wake" && isSafeRecordKey(item.key) && item.value) {
        out.wakes[item.key] = item.value;
      }
    });
    out.entries.sort(function (a, b) {
      var ta = String((a && (a.created_at || a.at)) || "");
      var tb = String((b && (b.created_at || b.at)) || "");
      if (ta !== tb) return ta < tb ? -1 : 1;
      var ia = String((a && a.id) || "");
      var ib = String((b && b.id) || "");
      return ia < ib ? -1 : ia > ib ? 1 : 0;
    });
    out.task_ops.sort(function (a, b) {
      var ta = String((a && a.at) || "");
      var tb = String((b && b.at) || "");
      if (ta !== tb) return ta < tb ? -1 : 1;
      var ia = String((a && a.id) || "");
      var ib = String((b && b.id) || "");
      return ia < ib ? -1 : ia > ib ? 1 : 0;
    });
    out.report_ops.sort(function (a, b) {
      var ta = String((a && a.at) || "");
      var tb = String((b && b.at) || "");
      if (ta !== tb) return ta < tb ? -1 : 1;
      var ia = String((a && a.id) || "");
      var ib = String((b && b.id) || "");
      return ia < ib ? -1 : ia > ib ? 1 : 0;
    });
    return out;
  }

  function computeBoardDiff(prevBoard, nextBoard, baseRev, nextRev) {
    var prevRecs = decomposeBoardRecords(prevBoard);
    var nextRecs = decomposeBoardRecords(nextBoard);
    var upserts = [];
    Object.keys(nextRecs).forEach(function (pairKey) {
      var nItem = nextRecs[pairKey];
      var pItem = prevRecs[pairKey];
      if (!pItem || canonicalDiffJson(pItem.value) !== canonicalDiffJson(nItem.value)) {
        upserts.push({ type: nItem.type, key: nItem.key, value: nItem.value });
      }
    });
    var tombstones = [];
    Object.keys(prevRecs).sort().forEach(function (pairKey) {
      if (!nextRecs[pairKey]) {
        tombstones.push({ type: prevRecs[pairKey].type, key: prevRecs[pairKey].key });
      }
    });
    return {
      base_rev: Number(baseRev) || 0,
      rev: Number(nextRev) || 0,
      upserts: upserts,
      tombstones: tombstones,
    };
  }

  function applyBoardDiff(baseBoard, diffObj) {
    if (!diffObj || typeof diffObj !== "object") return baseBoard;
    var records = decomposeBoardRecords(baseBoard);
    var tombstones = Array.isArray(diffObj.tombstones) ? diffObj.tombstones : [];
    var upserts = Array.isArray(diffObj.upserts) ? diffObj.upserts : [];
    tombstones.forEach(function (tomb) {
      if (!tomb || typeof tomb !== "object") return;
      var recType = String(tomb.type || "").trim();
      var key = String(tomb.key || "").trim();
      if (recType && key) delete records[recType + "\u0000" + key];
    });
    upserts.forEach(function (item) {
      if (!item || typeof item !== "object") return;
      var recType = String(item.type || "").trim();
      var key = String(item.key || "").trim();
      if (recType && key && "value" in item) {
        records[recType + "\u0000" + key] = { type: recType, key: key, value: item.value };
      }
    });
    return recomposeBoardRecords(records);
  }

  var STATE_WATCH_MS = 60 * 1000;


  var STATE_SLUG_KEY = "clankers-arena-agent-slug";

  function titleRepo(doc) {
    var match = STATE_TITLE_RE.exec(String((doc && doc.title) || ""));
    return match ? match[1] : "";
  }

  function detectRepo(doc) {
    var bar = doc && typeof doc.querySelector === "function"
      ? doc.querySelector(BAR_SELECTOR)
      : null;
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
    if (hits === 1) return repo;
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
    if (!doc || typeof doc.querySelector !== "function") return "";
    var bar = doc.querySelector(BAR_SELECTOR);
    if (!bar || typeof bar.querySelectorAll !== "function") return "";
    var links = bar.querySelectorAll("a, [title]");
    var i;
    for (i = 0; i < links.length; i += 1) {
      if (!links[i] || typeof links[i].getAttribute !== "function") continue;
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
  var lastPreviewBase = "";

  function activePreviewBase(doc) {
    var current = previewBase(doc);
    if (current) {
      lastPreviewBase = current;
      var currentSid = boardBranch(previewUiBranch || (doc ? stateBranch(doc) : "") || "");
      if (currentSid) {
        try { GM_setValue("clankers-arena-preview-base-" + currentSid, current); } catch (err) {}
      }
    }
    return current || lastPreviewBase || null;
  }

  function boardPreviewBase(doc) {
    var live = activePreviewBase(doc);
    if (live) return live;
    var docSid = boardBranch(previewUiBranch || (doc ? stateBranch(doc) : "") || "");
    if (!docSid) return null;
    try {
      var remembered = String(GM_getValue("clankers-arena-preview-base-" + docSid, "") || "");
      return remembered || null;
    } catch (err) {
      return null;
    }
  }

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
    var readyMsg = { type: "clankers:userscript-ready", version: userscriptVersion() };
    try {
      frame.contentWindow.postMessage(readyMsg, target);
      lastNotifiedPreviewFrame = frame;
      lastNotifiedPreviewTarget = target;
      return true;
    } catch (err) {
      try {
        frame.contentWindow.postMessage(readyMsg, "*");
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
      withSkillHttpJitter(url, function () {
        GM_xmlhttpRequest({
          method: payload === undefined ? "GET" : "POST",
          url: url,
          headers: previewHeaders(payload !== undefined),
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
    });
  }

  var BOARD_SESSION_TTL_SECONDS = 180;
  var BOARD_PROXY_HOST_KEY = "clankers-arena-proxy-host";
  var BOARD_PROXY_MASTER_KEY = "clankers-arena-proxy-master";
  var BOARD_PROXY_POLL_MS = 3000;
  var proxyBoardCache = null;
  var proxyBoardRevision = 0;
  var proxyBoardEgressVersion = "";
  var proxyBoardPullInFlight = null;
  var lastProxyBoardPullAtMs = 0;
  var hydratedBoardFilesByBranch = new Set();
  var previewBoardPullByBase = new Map();
  var previewBoardPushByBranch = new Map();
  var previewScopedPushByBase = new Map();
  var previewAutosavePullByBase = new Map();
  var proxyStateCacheByScope = new Map();
  var MAX_ORIGIN_STATE_CACHE = 2;
  var MAX_HYDRATED_FILE_KEYS = 256;

  function setBoundedMap(map, key, value, maxSize) {
    if (map.has(key)) map.delete(key);
    map.set(key, value);
    while (map.size > maxSize) {
      var oldest = map.keys().next();
      if (oldest.done) break;
      map.delete(oldest.value);
    }
  }

  function addBoundedSet(set, value, maxSize) {
    if (set.has(value)) set.delete(value);
    set.add(value);
    while (set.size > maxSize) {
      var oldest = set.values().next();
      if (oldest.done) break;
      set.delete(oldest.value);
    }
  }

  function normalizeBoardProxyHost(raw) {
    var host = String(raw || "").trim().replace(/\/+$/, "").replace(/\/v1$/, "");
    if (/^[a-z0-9-]+(?:\.[a-z0-9-]+)+$/i.test(host)) {
      host = "https://" + host;
    }
    return /^https:\/\/[a-z0-9.-]+$/i.test(host) ? host : "";
  }

  function boardProxyConfig() {
    try {
      var host = normalizeBoardProxyHost(GM_getValue(BOARD_PROXY_HOST_KEY, ""));
      var master = String(GM_getValue(BOARD_PROXY_MASTER_KEY, "") || "").trim();
      if (host && master) return { host: host, master: master };
    } catch (err) {}
    return null;
  }

  function proxyBoardJson(path, payload) {
    var cfg = boardProxyConfig();
    if (!cfg) return Promise.resolve({ status: 0, body: null, failure: "unconfigured" });
    return new Promise(function (resolve) {
      if (typeof GM_xmlhttpRequest !== "function") {
        resolve({ status: 0, body: null, failure: "unavailable" });
        return;
      }
      var headers = { "X-Master-Key": cfg.master };
      if (payload !== undefined) headers["Content-Type"] = "application/json";
      GM_xmlhttpRequest({
        method: payload === undefined ? "GET" : "POST",
        url: cfg.host + path,
        headers: headers,
        data: payload === undefined ? undefined : JSON.stringify(payload),
        timeout: 15000,
        onload: function (answer) {
          if (answer.status === 304) {
            resolve({ status: 304, body: null, failure: null });
            return;
          }
          var body = null;
          var failure = null;
          try { body = JSON.parse(answer.responseText); } catch (err) { failure = "parse"; }
          if (body && typeof body.egress_version === "string" && body.egress_version.trim()) {
            proxyBoardEgressVersion = body.egress_version.trim();
          }
          resolve({ status: answer.status, body: body, failure: failure });
        },
        onerror: function () { resolve({ status: 0, body: null, failure: "error" }); },
        ontimeout: function () { resolve({ status: 0, body: null, failure: "timeout" }); },
      });
    });
  }

  function updateProxyBoardCache(rawBoard, revision) {
    var normalized = normalizeBoard(rawBoard);
    if (
      revision === 0 &&
      proxyBoardCache &&
      proxyBoardCache.allowed_sessions.length > 0 &&
      normalized.allowed_sessions.length === 0
    ) {
      return proxyBoardCache;
    }
    if (proxyBoardEgressVersion && !normalized.egress_version) {
      normalized.egress_version = proxyBoardEgressVersion;
    }
    proxyBoardCache = normalized;
    if (typeof revision === "number" && isFinite(revision) && revision >= 0) {
      proxyBoardRevision = revision;
    }
    if (typeof syncTitleNowHook === "function") syncTitleNowHook();
    return proxyBoardCache;
  }

  function pullProxyBoard(force) {
    if (!boardProxyConfig()) return Promise.resolve(null);
    if (proxyBoardPullInFlight) return proxyBoardPullInFlight;
    var docScope = typeof document !== "undefined" ? stateScope(document) : { repo: "", branch: "" };
    var pullBranch = boardBranch(previewUiBranch || docScope.branch || "");
    var pullRepo = cleanBoardRepo(previewUiRepo || docScope.repo || "", pullBranch);
    var params = [];
    if (!force && proxyBoardRevision > 0 && proxyBoardCache) {
      params.push("since=" + String(proxyBoardRevision));
      params.push("mode=diff");
    }
    if (pullBranch) params.push("branch=" + encodeURIComponent(pullBranch));
    if (pullRepo) params.push("repo=" + encodeURIComponent(pullRepo));
    var query = params.length ? ("?" + params.join("&")) : "";
    lastProxyBoardPullAtMs = Date.now();
    proxyBoardPullInFlight = proxyBoardJson("/v1/board" + query).then(function (res) {
      proxyBoardPullInFlight = null;
      if (res && res.status === 200 && res.body) {
        if (res.body.unchanged && proxyBoardCache) {
          if (typeof res.body.revision === "number" && isFinite(res.body.revision)) {
            proxyBoardRevision = Number(res.body.revision);
          }
          return { changed: false, board: proxyBoardCache, scoped_board: null };
        }
        if (res.body.mode === "diff" && res.body.diff && proxyBoardCache) {
          var patched = applyBoardDiff(proxyBoardCache, res.body.diff);
          return {
            changed: true,
            board: updateProxyBoardCache(patched, Number(res.body.revision)),
            scoped_board: res.body.scoped_board && typeof res.body.scoped_board === "object"
              ? res.body.scoped_board
              : null,
          };
        }
        if (res.body.board) {
          return {
            changed: true,
            board: updateProxyBoardCache(res.body.board, Number(res.body.revision)),
            scoped_board: res.body.scoped_board && typeof res.body.scoped_board === "object"
              ? res.body.scoped_board
              : null,
          };
        }
      }
      if (res && res.status === 304 && proxyBoardCache) {
        return { changed: false, board: proxyBoardCache, scoped_board: null };
      }
      return null;
    }, function () {
      proxyBoardPullInFlight = null;
      return null;
    });
    return proxyBoardPullInFlight;
  }

  function hydrateBoardFilesForTarget(scopedBoard, targetSid) {
    if (!boardProxyConfig() || !targetSid || !scopedBoard || !Array.isArray(scopedBoard.entries)) {
      return Promise.resolve({ board: scopedBoard, keys: [] });
    }
    var neededItems = [];
    var seenSha = new Set();
    var deliveredKeys = [];
    scopedBoard.entries.forEach(function (entry) {
      if (!entry || typeof entry !== "object" || !entry.file || typeof entry.file !== "object") return;
      var sha = String(entry.file.sha256 || "").trim().toLowerCase();
      if (!/^[0-9a-f]{64}$/.test(sha) || entry.file.content) return;
      var entryTo = String(entry.to || "");
      var senderBr = boardBranch(entry.branch || entry.session_id || "");
      if (entryTo && entryTo !== "*" && entryTo !== targetSid) return;
      if (senderBr === targetSid) return;
      var hKey = targetSid + ":" + String(entry.id || "") + ":" + sha;
      if (hydratedBoardFilesByBranch.has(hKey)) return;
      deliveredKeys.push(hKey);
      if (!seenSha.has(sha)) {
        seenSha.add(sha);
        neededItems.push({ sha: sha, branch: senderBr, name: String(entry.file.name || "") });
      }
    });
    if (!neededItems.length) {
      return Promise.resolve({ board: scopedBoard, keys: [] });
    }
    var fetchedBySha = new Map();
    return Promise.all(neededItems.map(function (item) {
      var q = "sha256=" + encodeURIComponent(item.sha);
      if (item.branch && item.name) {
        q += "&branch=" + encodeURIComponent(item.branch) + "&name=" + encodeURIComponent(item.name);
      }
      return proxyBoardJson("/v1/board/files?" + q).then(function (res) {
        var fileContent = res && res.status === 200 && res.body
          ? (res.body.file && typeof res.body.file.content === "string" ? res.body.file.content : res.body.content)
          : null;
        if (typeof fileContent === "string") {
          fetchedBySha.set(item.sha, fileContent);
        }
      });
    })).then(function () {
      var hydratedEntries = scopedBoard.entries.map(function (entry) {
        if (!entry || typeof entry !== "object" || !entry.file || typeof entry.file !== "object") return entry;
        var sha = String(entry.file.sha256 || "").trim().toLowerCase();
        if (!sha || entry.file.content || !fetchedBySha.has(sha)) return entry;
        var entryTo = String(entry.to || "");
        if (entryTo && entryTo !== "*" && entryTo !== targetSid) return entry;
        if (boardBranch(entry.branch || entry.session_id || "") === targetSid) return entry;
        var hKey = targetSid + ":" + String(entry.id || "") + ":" + sha;
        if (hydratedBoardFilesByBranch.has(hKey)) return entry;
        return Object.assign({}, entry, {
          file: Object.assign({}, entry.file, { content: fetchedBySha.get(sha) }),
        });
      });
      var confirmedKeys = deliveredKeys.filter(function (k) {
        var shaPart = k.slice(k.lastIndexOf(":") + 1);
        return fetchedBySha.has(shaPart);
      });
      return {
        board: Object.assign({}, scopedBoard, { entries: hydratedEntries }),
        keys: confirmedKeys,
      };
    });
  }

  function shouldAutoSyncBoard(board, doc) {
    var normalized = board && Array.isArray(board.allowed_sessions) ? board : readGlobalBoard();
    var docScope = doc ? stateScope(doc) : { repo: "", branch: "" };
    var selfSid = boardBranch(previewUiBranch || docScope.branch || "");
    if (
      isSafeRecordKey(selfSid) &&
      Array.isArray(localSessionReportsByBranch[selfSid]) &&
      boardHasWaitingReportFor(normalized, selfSid)
    ) {
      return true;
    }
    if (!normalized.allowed_sessions.length) return false;
    if (selfSid) {
      return normalized.allowed_sessions.indexOf(selfSid) !== -1;
    }
    var selfRepo = cleanBoardRepo(previewUiRepo || docScope.repo || "", selfSid);
    if (!selfRepo) return false;
    if (Array.isArray(normalized.linked_repos) && normalized.linked_repos.indexOf(selfRepo) !== -1) {
      return true;
    }
    return normalized.allowed_sessions.some(function (aSid) {
      return cleanBoardRepo("", aSid) === selfRepo;
    });
  }

  function syncPreviewBoard(base, targetSidHint, targetRepoHint, opts) {
    if (!base || !boardProxyConfig()) return Promise.resolve(null);
    var passive = Boolean(opts && opts.passive);
    var pushOnly = Boolean(opts && opts.pushOnly);
    var docScope = typeof document !== "undefined" ? stateScope(document) : { repo: "", branch: "" };
    var targetSid = boardBranch(targetSidHint || previewUiBranch || docScope.branch || "");
    if (targetSid) {
      try { GM_setValue("clankers-arena-preview-base-" + targetSid, base); } catch (err) {}
    }
    var targetRepo = cleanBoardRepo(targetRepoHint || previewUiRepo || docScope.repo || "", targetSid);
    function buildScopedSyncBoard(sidOverride, repoOverride) {
      var sid = sidOverride !== undefined ? sidOverride : targetSid;
      var repo = repoOverride !== undefined ? repoOverride : targetRepo;
      var scopedBoard = scopeBoardForTarget(readGlobalBoard(), sid, repo);
      var syncIso = new Date().toISOString();
      if (sid && Array.isArray(scopedBoard.sessions)) {
        scopedBoard.sessions = scopedBoard.sessions.map(function (row) {
          if (!row || typeof row !== "object") return row;
          var rSid = boardBranch(row.branch || row.session_id || "");
          if (rSid === sid) {
            var nextUpdatedAt = passive && row.updated_at ? row.updated_at : syncIso;
            return Object.assign({}, row, { updated_at: nextUpdatedAt });
          }
          return row;
        });
      }
      if (Array.isArray(scopedBoard.removed_sessions)) {
        var targetIsScopedAllowed = scopedBoard.allowed_sessions.indexOf(sid) !== -1;
        scopedBoard.removed_sessions = scopedBoard.removed_sessions.filter(function (remSid) {
          if (scopedBoard.allowed_sessions.indexOf(remSid) !== -1) return false;
          if (remSid === sid && targetIsScopedAllowed) return false;
          return true;
        });
      }
      return scopedBoard;
    }
    function recordMemberMetadata(body, fallbackBranch) {
      var br = boardBranch((body && body.branch) || fallbackBranch || "");
      if (br) {
        try { GM_setValue("clankers-arena-preview-base-" + br, base); } catch (err) {}
      }
      if (isSafeRecordKey(br) && body && body.worker_reports && Array.isArray(body.worker_reports[br])) {
        localSessionReportsByBranch[br] = body.worker_reports[br].slice();
        if (typeof syncTitleNowHook === "function") syncTitleNowHook();
      }
      if (body && body.branch) setPreviewUiBranch(body.branch);
      return br;
    }
    function handleMemberFailure(failedAns, br) {
      if (!br || (failedAns && failedAns.status > 0 && failedAns.status < 500)) {
        return Promise.resolve(failedAns);
      }
      return proxyBoardJson("/v1/board", {
        action: "apply",
        board_action: { type: "disconnect-session", branch: br },
      }).then(function (discProxy) {
        if (discProxy && discProxy.status === 200 && discProxy.body && discProxy.body.board) {
          writeGlobalBoard(discProxy.body.board, {
            fromProxy: true,
            revision: Number(discProxy.body.revision),
          });
        }
        return failedAns;
      });
    }
    function postConsolidatedOnce(boardToSend, hydratedKeys, sid) {
      var pullCur = previewBoardPullByBase.get(base);
      var supportsPreviewDiff = Boolean(pullCur && pullCur.rev > 0);
      var scopedCur = supportsPreviewDiff ? previewScopedPushByBase.get(base) : null;
      var syncPayload = (scopedCur && scopedCur.board)
        ? {
          action: "sync",
          board_diff: computeBoardDiff(scopedCur.board, boardToSend, scopedCur.rev, scopedCur.rev + 1),
        }
        : (supportsPreviewDiff
          ? { action: "sync", board: boardToSend, client_rev: 1 }
          : { action: "sync", board: boardToSend });
      function finishConsolidated(answer, nextPushRev) {
        if (answer && answer.status === 200 && answer.body) {
          hydratedKeys.forEach(function (k) { addBoundedSet(hydratedBoardFilesByBranch, k, MAX_HYDRATED_FILE_KEYS); });
          if (supportsPreviewDiff) {
            setBoundedMap(previewScopedPushByBase, base, { rev: nextPushRev, board: boardToSend }, MAX_ORIGIN_STATE_CACHE);
          }
          if (typeof answer.body.revision === "number" && answer.body.sessions) {
            setBoundedMap(previewBoardPullByBase, base, {
              rev: Number(answer.body.revision),
              board: answer.body,
            }, MAX_ORIGIN_STATE_CACHE);
          }
          recordMemberMetadata(answer.body, sid);
          return answer;
        }
        return handleMemberFailure(answer, sid);
      }
      return stateJson(base + "/api/board", syncPayload).then(function (answer) {
        if (
          scopedCur &&
          answer &&
          (answer.status === 409 || (answer.body && answer.body.need_full))
        ) {
          previewScopedPushByBase.delete(base);
          return stateJson(base + "/api/board", {
            action: "sync",
            board: boardToSend,
            client_rev: 1,
          }).then(function (retryAns) {
            return finishConsolidated(retryAns, 1);
          });
        }
        return finishConsolidated(answer, scopedCur ? scopedCur.rev + 1 : 1);
      });
    }
    if (pushOnly) {
      var directScoped = (opts && opts.scopedBoard && typeof opts.scopedBoard === "object")
        ? normalizeBoard(opts.scopedBoard)
        : buildScopedSyncBoard(targetSid, targetRepo);
      return hydrateBoardFilesForTarget(directScoped, targetSid).then(function (hydrated) {
        return postConsolidatedOnce(hydrated.board, hydrated.keys, targetSid);
      });
    }
    var memberPullCur = previewBoardPullByBase.get(base);
    var memberGetUrl = (memberPullCur && memberPullCur.rev > 0 && memberPullCur.board)
      ? (base + "/api/board?since=" + String(memberPullCur.rev) + "&mode=diff")
      : (base + "/api/board");
    return stateJson(memberGetUrl).then(function (memberAns) {
      if (!memberAns || memberAns.status !== 200 || !memberAns.body) {
        return handleMemberFailure(memberAns, targetSid);
      }
      var rawMemberBody = memberAns.body;
      var memberBody;
      if (rawMemberBody.unchanged && memberPullCur && memberPullCur.board) {
        memberBody = memberPullCur.board;
        if (typeof rawMemberBody.revision === "number") {
          previewBoardPullByBase.set(base, {
            rev: Number(rawMemberBody.revision),
            board: memberBody,
          });
        }
      } else if (rawMemberBody.mode === "diff" && rawMemberBody.diff && memberPullCur && memberPullCur.board) {
        memberBody = applyBoardDiff(memberPullCur.board, rawMemberBody.diff);
        previewBoardPullByBase.set(base, {
          rev: Number(rawMemberBody.revision) || (memberPullCur.rev + 1),
          board: memberBody,
        });
      } else {
        memberBody = rawMemberBody.board && typeof rawMemberBody.board === "object"
          ? rawMemberBody.board
          : rawMemberBody;
        if (typeof rawMemberBody.revision === "number" && rawMemberBody.revision > 0) {
          previewBoardPullByBase.set(base, {
            rev: Number(rawMemberBody.revision),
            board: memberBody,
          });
        } else {
          previewBoardPullByBase.delete(base);
        }
      }
      var memberSid = recordMemberMetadata(memberBody, targetSid);
      var memberRepo = cleanBoardRepo(memberBody.repo || targetRepo || "", memberSid);
      var proxyPushCur = memberSid ? previewBoardPushByBranch.get(memberSid) : null;
      var proxySyncReq = (proxyPushCur && proxyPushCur.board)
        ? {
          action: "sync",
          board_diff: computeBoardDiff(proxyPushCur.board, memberBody, proxyPushCur.rev, proxyPushCur.rev + 1),
          branch: memberSid,
          repo: memberRepo,
          passive: passive,
          reply_since: proxyBoardRevision > 0 && proxyBoardCache ? proxyBoardRevision : undefined,
          reply_mode: proxyBoardRevision > 0 && proxyBoardCache ? "diff" : undefined,
        }
        : {
          action: "sync",
          board: memberBody,
          client_rev: 1,
          branch: memberSid,
          repo: memberRepo,
          passive: passive,
        };
      function sendMemberToProxy() {
        return proxyBoardJson("/v1/board", proxySyncReq).then(function (syncRes) {
          if (
            proxyPushCur &&
            syncRes &&
            (syncRes.status === 409 || (syncRes.body && syncRes.body.need_full))
          ) {
            if (memberSid) previewBoardPushByBranch.delete(memberSid);
            proxyPushCur = null;
            return proxyBoardJson("/v1/board", {
              action: "sync",
              board: memberBody,
              client_rev: 1,
              branch: memberSid,
              repo: memberRepo,
              passive: passive,
            }).then(function (retryRes) {
              if (memberSid && retryRes && retryRes.status === 200) {
                previewBoardPushByBranch.set(memberSid, { rev: 1, board: memberBody });
              }
              return retryRes;
            });
          }
          if (memberSid && syncRes && syncRes.status === 200) {
            previewBoardPushByBranch.set(memberSid, {
              rev: proxyPushCur ? proxyPushCur.rev + 1 : 1,
              board: memberBody,
            });
          }
          return syncRes;
        });
      }
      return sendMemberToProxy().then(function (syncRes) {
        var syncedScoped = null;
        if (syncRes && syncRes.status === 200 && syncRes.body) {
          if (syncRes.body.mode === "diff" && syncRes.body.diff && proxyBoardCache) {
            var nextGlobal = applyBoardDiff(proxyBoardCache, syncRes.body.diff);
            writeGlobalBoard(nextGlobal, {
              passive: passive,
              fromProxy: true,
              revision: Number(syncRes.body.revision),
            });
          } else if (syncRes.body.board) {
            writeGlobalBoard(syncRes.body.board, {
              passive: passive,
              fromProxy: true,
              revision: Number(syncRes.body.revision),
            });
          } else if (syncRes.body.unchanged && typeof syncRes.body.revision === "number") {
            proxyBoardRevision = Number(syncRes.body.revision);
          }
          if (syncRes.body.scoped_board && typeof syncRes.body.scoped_board === "object") {
            syncedScoped = normalizeBoard(syncRes.body.scoped_board);
          }
        }
        return pullProxyBoard(false).then(function (pulled) {
          var consolidatedScoped = (pulled && pulled.changed && pulled.scoped_board)
            ? normalizeBoard(pulled.scoped_board)
            : ((!pulled || !pulled.changed) && syncedScoped)
              ? syncedScoped
              : buildScopedSyncBoard(memberSid, memberRepo);
          return hydrateBoardFilesForTarget(consolidatedScoped, memberSid).then(function (hydrated) {
            if (
              passive &&
              !hydrated.keys.length &&
              boardMaterialSignature(hydrated.board) === boardMaterialSignature(memberBody)
            ) {
              return memberAns;
            }
            return postConsolidatedOnce(hydrated.board, hydrated.keys, memberSid);
          });
        });
      });
    });
  }

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
    if (base) {
      lastPreviewBase = base;
    } else if (event.origin && typeof event.data.type === "string" && event.data.type.indexOf("clankers:") === 0) {
      lastPreviewBase = event.origin.replace(/\/+$/, "");
      base = lastPreviewBase;
    } else {
      base = lastPreviewBase || null;
    }
    if (event.data.type === "clankers:preview-ready") {
      if (typeof event.data.branch === "string" && event.data.branch.trim()) {
        setPreviewUiBranch(event.data.branch);
      }
      if (typeof event.data.repo === "string" && event.data.repo.trim()) {
        var nextRepo = event.data.repo.trim();
        if (nextRepo !== previewUiRepo) {
          previewUiRepo = nextRepo;
          if (typeof syncPreviewProxyHook === "function") syncPreviewProxyHook();
        }
      }
      notifyPreviewReady(document, true);
      syncPreviewBoard(base, event.data.branch || "", event.data.repo || "");
    } else if (event.data.type === "clankers:force-save") {
      if (typeof forceSaveStateHook === "function") {
        forceSaveStateHook(!event.data.save_id);
      }
    } else if (event.data.type === "clankers:board-request") {
      syncPreviewBoard(base, event.data.branch || "", event.data.repo || "", { passive: true });
    } else if (event.data.type === "clankers:board-action" && event.data.action && boardProxyConfig()) {
      var isHeartbeatAction = (event.data.action.action === "heartbeat" || event.data.action.type === "heartbeat");
      if (isHeartbeatAction && event.data.action.branch) {
        setPreviewUiBranch(event.data.action.branch);
      }
      var syncActionBranch = isHeartbeatAction
        ? (event.data.action.branch || "")
        : (previewUiBranch || "");
      var syncActionRepo = isHeartbeatAction
        ? (event.data.action.repo || "")
        : (previewUiRepo || event.data.action.repo || "");
      proxyBoardJson("/v1/board", {
        action: "apply",
        board_action: event.data.action,
        branch: syncActionBranch,
        repo: syncActionRepo,
      }).then(function (actRes) {
        if (actRes && actRes.status === 200 && actRes.body && actRes.body.board) {
          writeGlobalBoard(actRes.body.board, {
            passive: isHeartbeatAction,
            fromProxy: true,
            revision: Number(actRes.body.revision),
          });
          if (base) {
            syncPreviewBoard(
              base,
              syncActionBranch,
              syncActionRepo,
              {
                passive: isHeartbeatAction,
                pushOnly: true,
                scopedBoard: actRes.body.scoped_board || null,
              }
            );
          }
        }
      });
    }
  }

  syncPreviewBoardHook = syncPreviewBoard;
  if (typeof document !== "undefined" && !pauseStored()) {
    if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
      window.addEventListener("message", onPreviewMessage);
      window.addEventListener("pagehide", function () {
        if (!previewUiBranch || !boardProxyConfig()) return;
        proxyBoardJson("/v1/board", {
          action: "apply",
          board_action: { type: "disconnect-session", branch: previewUiBranch },
        });
      });
    }
    notifyPreviewReadyHook = function () {
      notifyPreviewReady(document);
    };
    notifyPreviewReady(document);
  }

  runFeature("state-download", "State - download", function () {
    var STATE_PANEL_ID = "clankers-state-panel";

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

    if (exposeChecks("stateDownload", {
      USERSCRIPT_VERSION_HEADER: USERSCRIPT_VERSION_HEADER,
      userscriptVersion: userscriptVersion,
      STATE_LINES: STATE_LINES,
      getLine: getLine,
      proxyStateFailLine: proxyStateFailLine,
      clearSavedFailure: function () { removeStatePanel(true); },
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
      panelNeeded: panelNeeded,
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
      sameSaves: sameSaves,
      computeStateDiff: computeStateDiff,
      applyStateDiff: applyStateDiff,
      previewFrame: previewFrame,
      previewBase: previewBase,
      notifyPreviewReady: notifyPreviewReady,
      isWorkerSession: isWorkerSession,
      STATE_WATCH_MS: STATE_WATCH_MS,
    })) {
      return function () {};
    }

    var STATE_HINT_KEY = "clankers-arena-state-hinted";
    function stampKey(scopeKey) {
      return "clankers-arena-state-stamp-" + scopeKey;
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
    function isWorkerSession(board, sessionSid, body) {
      if (body && body.board && body.board.role === "worker") return true;
      var active = board || readGlobalBoard();
      var sid = boardBranch(
        sessionSid ||
          (body && body.scope && body.scope.branch) ||
          previewUiBranch ||
          "",
      );
      if (!sid || !active || !active.main_session_id) return false;
      return boardRoleFor(active, sid) === "worker";
    }
    function rememberState(scope, storeKey, base, branch, stamp, stamps) {
      if (
        !isWorkerSession(
          readGlobalBoard(),
          branch || (scope && scope.branch) || previewUiBranch || "",
          null,
        )
      ) {
        GM_setValue(lastScopeKey(scope.repo), storeKey);
      }
      GM_setValue(baseKey(storeKey), base);
      GM_setValue(branchKey(storeKey), branch);
      GM_setValue(overwriteKey(storeKey), false);
      GM_setValue(stampKey(storeKey), JSON.stringify(stateMemory(stamp, stamps)));
    }
    var stateBusy = false;

    function receiptKey(storeKey) { return "clankers-arena-state-receipt-" + storeKey; }
    function pendingKey(storeKey) { return "clankers-arena-state-pending-" + storeKey; }
    function readPendingReceipt(storeKey) {
      var raw = GM_getValue(pendingKey(storeKey), null);
      if (!raw || typeof raw !== "object") return raw;
      if ("core" in raw || "text" in raw || (raw.receipt && typeof raw.receipt === "object" && "core" in raw.receipt)) {
        var nextReceipt = raw.receipt && typeof raw.receipt === "object"
          ? Object.assign({}, raw.receipt)
          : raw.receipt;
        if (nextReceipt && typeof nextReceipt === "object") delete nextReceipt.core;
        var slim = Object.assign({}, raw, { receipt: nextReceipt });
        delete slim.core;
        delete slim.text;
        GM_setValue(pendingKey(storeKey), slim);
        return slim;
      }
      return raw;
    }
    function offerKey(storeKey) { return "clankers-arena-state-offered-" + storeKey; }

    async function confirmPending(base, storeKey, pending) {
      var answer = await stateJson(base + "/api/userscript-autosave", pending.receipt);
      var receipt = pending.receipt;
      var body = answer.body;
      if ((answer.status !== 200 && answer.status !== 201) || !body ||
          body.confirmed !== true || body.save_id !== receipt.save_id || body.digest !== receipt.digest) {
        if (answer.status === 400) {
          GM_setValue(pendingKey(storeKey), null);
        }
        stateError("Failed to confirm. State saved on proxy.",
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
      logEvent("state", "saved", { route: "proxy", repo: pending.scope.repo, filename: pending.name });
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

    function panelNeeded(manual, shown) {
      return Boolean(manual) || !shown;
    }

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
      if (actionLabel !== "Retry save" && actionLabel !== "Settings") return;
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
        close.textContent = "Cancel";
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
      logEvent("state", "failed", { code: code || "unknown", status: status, detail: detail }, code === "proxy-unconfigured" ? "warn" : "error");
      if (showPanel !== false) statePanel(line, actionLabel, action);
    }

    function hintProxyNeeded(manual) {
      var shown = GM_getValue(STATE_HINT_KEY, false);
      if (!shown) {
        GM_setValue(STATE_HINT_KEY, true);
      }
      logEvent("state", "proxy-needed", null, "warn");
      if (panelNeeded(manual, shown)) {
        statePanel(STATE_LINES.noProxy, "Settings", function () {
          if (typeof openSettingsModalHook === "function") openSettingsModalHook();
        });
      }
    }

    function askOverwrite(name, storeKey, manual, context) {
      var askedKey = overwriteKey(storeKey);
      var shown = GM_getValue(askedKey, false);
      if (!panelNeeded(manual, shown)) return;
      GM_setValue(askedKey, true);
      statePanel(overwriteLine(name || "proxy state", context), "Overwrite", function () {
        fetchStateFile(true, true);
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

    function offerStateBackup(base, storeKey, scope, preferredName, known, body, backupText, summary) {
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
      var name = preferredName || stateFileName(
        scope && scope.repo,
        scope && scope.branch,
        (known && known.lastsave) || "",
        (known && known.counts) || (known && Array.isArray(known.core) ? coreCounts(known.core) : null),
      );
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

    async function pullPreviewAutosave(base, force) {
      var cur = !force ? previewAutosavePullByBase.get(base) : null;
      var url = (cur && cur.rev > 0 && Array.isArray(cur.core))
        ? (base + "/api/userscript-autosave?since=" + String(cur.rev) + "&mode=diff")
        : (base + "/api/userscript-autosave");
      var answer = await stateJson(url);
      if (!answer || answer.status !== 200 || !answer.body) return answer;
      var rawBody = answer.body;
      if (rawBody.mode === "diff" && cur && Array.isArray(cur.core)) {
        var nextCore = rawBody.unchanged
          ? cur.core
          : (rawBody.diff ? applyStateDiff(cur.core, rawBody.diff) : null);
        if (Array.isArray(nextCore)) {
          var nextRev = Number(rawBody.revision) || cur.rev;
          setBoundedMap(previewAutosavePullByBase, base, { rev: nextRev, core: nextCore }, MAX_ORIGIN_STATE_CACHE);
          return {
            status: 200,
            failure: null,
            body: Object.assign({}, rawBody, { core: nextCore }),
          };
        }
        previewAutosavePullByBase.delete(base);
        return pullPreviewAutosave(base, true);
      }
      if (Array.isArray(rawBody.core)) {
        if (typeof rawBody.revision === "number" && rawBody.revision > 0) {
          setBoundedMap(previewAutosavePullByBase, base, {
            rev: Number(rawBody.revision),
            core: rawBody.core,
          }, MAX_ORIGIN_STATE_CACHE);
        } else {
          previewAutosavePullByBase.delete(base);
        }
      }
      return answer;
    }

    async function pullProxyStateSnapshot(repo, branch, force) {
      var scopeId = stateScopeKey(repo, branch);
      var cached = !force ? proxyStateCacheByScope.get(scopeId) : null;
      var query = "?repo=" + encodeURIComponent(repo || "") +
        "&branch=" + encodeURIComponent(branch || "") +
        "&fallback_repo=1" +
        (cached && cached.rev > 0 ? ("&since=" + String(cached.rev) + "&mode=diff") : "");
      var res = await proxyBoardJson("/v1/state" + query);
      if (!res || res.status !== 200 || !res.body || res.body.ok === false) {
        proxyStateCacheByScope.delete(scopeId);
        return { ok: false, res: res, snap: null };
      }
      var rb = res.body;
      if (rb.unchanged && cached) {
        var unchangedSnap = (typeof rb.revision === "number" && rb.revision > 0)
          ? Object.assign({}, cached, { rev: Number(rb.revision) })
          : cached;
        setBoundedMap(proxyStateCacheByScope, scopeId, unchangedSnap, MAX_ORIGIN_STATE_CACHE);
        return { ok: true, res: res, snap: unchangedSnap };
      }
      if (rb.mode === "diff" && rb.diff && cached && Array.isArray(cached.core)) {
        var mergedCore = applyStateDiff(cached.core, rb.diff);
        var updatedSnap = {
          exists: true,
          rev: Number(rb.revision) || (cached.rev + 1),
          scope: rb.scope || cached.scope || { repo: repo, branch: branch },
          save_id: rb.save_id || cached.save_id || "",
          digest: rb.digest || cached.digest || "",
          stamp: rb.stamp || cached.stamp || "",
          lastsave: rb.lastsave !== undefined ? rb.lastsave : cached.lastsave,
          beforelastsave: rb.beforelastsave !== undefined ? rb.beforelastsave : cached.beforelastsave,
          counts: rb.counts || coreCounts(mergedCore),
          core: mergedCore,
          text: "",
        };
        setBoundedMap(proxyStateCacheByScope, scopeId, updatedSnap, MAX_ORIGIN_STATE_CACHE);
        return { ok: true, res: res, snap: updatedSnap };
      }
      if (rb.exists) {
        var fullCore = Array.isArray(rb.core) ? rb.core : [];
        var fullSnap = {
          exists: true,
          rev: Number(rb.revision) || 0,
          scope: rb.scope || { repo: repo, branch: branch },
          save_id: rb.save_id || "",
          digest: rb.digest || "",
          stamp: rb.stamp || "",
          lastsave: rb.lastsave !== undefined ? rb.lastsave : null,
          beforelastsave: rb.beforelastsave !== undefined ? rb.beforelastsave : null,
          counts: rb.counts || coreCounts(fullCore),
          core: fullCore,
          text: "",
        };
        setBoundedMap(proxyStateCacheByScope, scopeId, fullSnap, MAX_ORIGIN_STATE_CACHE);
        return {
          ok: true,
          res: res,
          snap: typeof rb.text === "string" && rb.text
            ? Object.assign({}, fullSnap, { text: rb.text })
            : fullSnap,
        };
      }
      proxyStateCacheByScope.delete(scopeId);
      return {
        ok: true,
        res: res,
        snap: { exists: false, rev: 0, core: [], text: "" },
      };
    }

    async function pushProxyStateSnapshot(repo, branch, prevSnap, body, force) {
      var scopeId = stateScopeKey(repo, branch);
      var targetScope = { repo: repo, branch: branch };
      var baseFields = {
        action: "put",
        scope: targetScope,
        save_id: body.save_id,
        digest: body.digest,
        stamp: body.stamp,
        lastsave: body.stamp,
        beforelastsave: body.lastsave || null,
        counts: body.counts || coreCounts(body.core),
        stamps: body.stamps || {},
      };
      var useDiff = Boolean(!force && prevSnap && prevSnap.exists && prevSnap.rev > 0 && Array.isArray(prevSnap.core));
      var putPayload = useDiff
        ? Object.assign({}, baseFields, {
          diff: computeStateDiff(prevSnap.core, body.core, prevSnap.rev, prevSnap.rev + 1),
        })
        : Object.assign({}, baseFields, {
          core: body.core,
          history: Array.isArray(body.history) ? body.history : undefined,
        });
      var putRes = await proxyBoardJson("/v1/state", putPayload);
      if (
        useDiff &&
        putRes &&
        (putRes.status === 409 || (putRes.body && putRes.body.need_full))
      ) {
        proxyStateCacheByScope.delete(scopeId);
        putRes = await proxyBoardJson("/v1/state", Object.assign({}, baseFields, {
          core: body.core,
          history: Array.isArray(body.history) ? body.history : undefined,
        }));
      }
      if (putRes && putRes.status === 200 && putRes.body && putRes.body.ok !== false) {
        setBoundedMap(proxyStateCacheByScope, scopeId, {
          exists: true,
          rev: Number(putRes.body.revision) || ((prevSnap && prevSnap.rev ? prevSnap.rev : 0) + 1),
          scope: targetScope,
          save_id: body.save_id,
          digest: body.digest,
          stamp: body.stamp,
          lastsave: body.stamp,
          beforelastsave: body.lastsave || null,
          counts: body.counts || coreCounts(body.core),
          core: body.core,
          text: "",
        }, MAX_ORIGIN_STATE_CACHE);
      }
      return putRes;
    }

    async function fetchStateFile(manual, force) {
      notifyPreviewReady(document);
      var base = activePreviewBase(document);
      if (boardProxyConfig() && !proxyBoardCache) {
        await pullProxyBoard(true);
      }
      var initialBoard = readGlobalBoard();
      var boardBase = base || boardPreviewBase(document);
      if (boardBase && shouldAutoSyncBoard(initialBoard, document)) {
        syncPreviewBoard(boardBase, "", "", { passive: true });
      }
      if (!base) return;
      if (stateBusy) return;
      stateBusy = true;
      try {
        var scope = stateScope(document);
        var initialSid = boardBranch(scope.branch || previewUiBranch || "");
        if (!manual && isWorkerSession(initialBoard, initialSid, null)) {
          return;
        }
        if (force) statePanel("Forcing save...");
        var lastScope = isWorkerSession(initialBoard, initialSid, null)
          ? ""
          : GM_getValue(lastScopeKey(scope.repo), "");
        var storeKey = scope.branch ? stateScopeKey(scope.repo, scope.branch) : lastScope || stateScopeKey(scope.repo, "");
        var pending = scope.branch ? readPendingReceipt(storeKey) : null;
        if (pending) {
          await confirmPending(base, storeKey, pending);
          return;
        }
        var answer = await pullPreviewAutosave(base, Boolean(force));
        var body = answer && answer.body;
        if (!answer || answer.status !== 200 || !body || !Array.isArray(body.core) || !body.scope ||
            !body.save_id || !body.digest) {
          stateError(getLine(answer ? answer.status : 0, base + "/api/userscript-autosave"), null, null, "autosave-get", answer ? answer.status : 0, undefined,
            (answer && answer.status === 200 ? "body" : "status" + (answer && answer.failure ? ":" + answer.failure : "")));
          return;
        }
        clearErrorPanel();
        var serverRepo = body.scope && typeof body.scope.repo === "string" ? body.scope.repo.trim() : "";
        var serverBranch = body.scope && typeof body.scope.branch === "string" ? body.scope.branch.trim() : "";
        if (serverBranch) {
          setPreviewUiBranch(serverBranch);
        }
        if (!scope.repo && (serverRepo || previewUiRepo)) {
          scope = { repo: serverRepo || previewUiRepo, branch: scope.branch };
          if (!lastScope) {
            lastScope = isWorkerSession(initialBoard, initialSid, body)
              ? ""
              : GM_getValue(lastScopeKey(scope.repo), "");
          }
          storeKey = scope.branch ? stateScopeKey(scope.repo, scope.branch) : lastScope || stateScopeKey(scope.repo, "");
        }
        var activeBoard = readGlobalBoard();
        var sessionSid = boardBranch(scope.branch || serverBranch || previewUiBranch || "");
        if (!manual && isWorkerSession(activeBoard, sessionSid, body)) {
          removeStatePanel(true);
          return;
        }
        if (isWorkerSession(activeBoard, sessionSid, body)) {
          lastScope = "";
        }
        if (!pending) {
          pending = readPendingReceipt(storeKey);
          if (pending) {
            await confirmPending(base, storeKey, pending);
            return;
          }
        }
        if (body.force === true) {
          force = true;
        }
        if (force) statePanel("Forcing save...");
        var rememberedBase = GM_getValue(baseKey(lastScope || storeKey), "");
        var rememberedBranch = GM_getValue(branchKey(lastScope || storeKey), "");
        if (!scope.branch && !lastScope && !force && !serverBranch) {
          stateError(STATE_LINES.noBranch, "Force save", function () { fetchStateFile(true, true); }, "missing-branch");
          return;
        }
        if (!boardProxyConfig()) {
          hintProxyNeeded(manual || Boolean(force));
          return;
        }
        var effectiveRepo = scope.repo || serverRepo || previewUiRepo || "";
        var effectiveBranch = scope.branch || serverBranch || rememberedBranch || "";
        var pulledState = await pullProxyStateSnapshot(effectiveRepo, effectiveBranch, Boolean(force));
        if (!pulledState.ok) {
          var getStatus = pulledState.res ? pulledState.res.status : 0;
          var getDetail = getStatus ? ("GET " + getStatus) : ((pulledState.res && pulledState.res.failure) || "unreachable");
          stateError(
            proxyStateFailLine(getDetail),
            "Retry save",
            function () { fetchStateFile(true, Boolean(force)); },
            "proxy-get",
            getStatus,
          );
          return;
        }
        var proxySnap = pulledState.snap;
        var baseline = GM_getValue(receiptKey(storeKey), null);
        var initialState = !proxySnap.exists && !baseline;
        if (proxySnap.exists) {
          baseline = {
            save_id: proxySnap.save_id || (baseline && baseline.save_id) || "",
            digest: proxySnap.digest || (baseline && baseline.digest) || "",
            scope: body.scope,
            lastsave: proxySnap.lastsave !== undefined ? proxySnap.lastsave : (baseline && baseline.lastsave) || null,
            beforelastsave: proxySnap.beforelastsave !== undefined ? proxySnap.beforelastsave : (baseline && baseline.beforelastsave) || null,
            counts: proxySnap.counts || coreCounts(proxySnap.core),
            core: proxySnap.core,
          };
        }
        var inSync = sameSaves(baseline, body);
        var name = stateFileName(effectiveRepo, effectiveBranch, body.stamp, body.counts);
        if (!force && !inSync && !initialState) {
          var mismatchLine = stateMismatchLine(baseline, body);
          stateError(mismatchLine, "Force save",
            function () { fetchStateFile(true, true); }, "autosave-compare",
            undefined, undefined, sameSaveDetail(baseline, body));
          var backupText = proxySnap.text || "";
          if (proxySnap.exists && !backupText) {
            var fullOfferRes = await proxyBoardJson(
              "/v1/state?repo=" + encodeURIComponent(effectiveRepo) +
              "&branch=" + encodeURIComponent(effectiveBranch) +
              "&fallback_repo=1&include_text=1"
            );
            if (fullOfferRes && fullOfferRes.status === 200 && fullOfferRes.body && typeof fullOfferRes.body.text === "string") {
              backupText = fullOfferRes.body.text;
            }
          }
          offerStateBackup(
            base,
            storeKey,
            { repo: effectiveRepo, branch: effectiveBranch },
            stateFileName(effectiveRepo, effectiveBranch, (baseline && baseline.lastsave) || "", baseline && baseline.counts),
            baseline,
            body,
            backupText,
            mismatchLine,
          );
          return;
        }
        if (!force && inSync && body.digest === (baseline && baseline.digest)) return;
        var plan = { type: "download", name: name };
        var moved = saveMoved(scope.branch, rememberedBase, base, lastScope, rememberedBranch);
        var asks = overwriteAsk(moved, plan, Boolean(proxySnap.exists), Boolean(force));
        var accepted = asks && resetWindowAccepts(new Date(), resetWindowOn(), effectiveBranch, rememberedBase, base, rememberedBranch);
        if (asks && !accepted) {
          askOverwrite(name, storeKey, manual, {
            branch: scope.branch, rememberedBranch: rememberedBranch, lastScope: lastScope,
            base: base, rememberedBase: rememberedBase, memory: stateRemembered(GM_getValue(stampKey(storeKey), "")),
            stamp: body.stamp, stamps: body.stamps,
          });
          return;
        }
        var putRes = await pushProxyStateSnapshot(effectiveRepo, effectiveBranch, proxySnap, body, Boolean(force));
        if (!putRes || putRes.status !== 200 || !putRes.body || putRes.body.ok === false) {
          var putStatus = putRes ? putRes.status : 0;
          var putDetail = putStatus ? ("POST " + putStatus) : ((putRes && putRes.failure) || "unreachable");
          stateError(
            proxyStateFailLine(putDetail),
            "Retry save",
            function () { fetchStateFile(true, Boolean(force)); },
            "proxy-put",
            putStatus,
          );
          return;
        }
        removeStatePanel(true);
        pending = {
          receipt: {
            save_id: body.save_id, scope: body.scope, digest: body.digest,
            lastsave: body.stamp, beforelastsave: body.lastsave,
          },
          counts: body.counts || coreCounts(body.core),
          scope: { repo: effectiveRepo, branch: effectiveBranch },
          base: base, branch: effectiveBranch, stamp: body.stamp,
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

    var menus = [];
    forceSaveStateHook = function (manual) {
      fetchStateFile(manual !== false, true);
    };
    setResetWindowHook = function (next) {
      GM_setValue(RESET_WINDOW_KEY, Boolean(next));
      logEvent("feature", "change", {
        feature: "state-download",
        enabled: resetWindowOn(),
      });
      menuRefresh();
    };
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
      forceSaveStateHook = null;
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
      var board = readGlobalBoard();
      var sid = boardBranch(previewUiBranch || stateBranch(doc) || "");
      var greek = sid ? boardGreekSymbolFor(board, sid) : "";
      var star = sid && boardHasWaitingReportFor(board, sid) ? "* " : "";
      var emoji = heldEmojiFor(doc);
      titleEmoji = emoji || "";
      var base = greek ? TITLE_PREFIX + name + " " + greek : TITLE_PREFIX + name;
      return star + (emoji ? base + " " + emoji : base);
    }

    var titleEmoji = "";
    var appliedTitle = null;
    var priorTitle = null;
    var titleConditions = {};
    var titleRowKind = null;
    var lastRepo = null;
    var lastPath = null;
    function currentTitleEmoji(rawTitle) {
      var cur = String(rawTitle || "");
      var stripped = cur.indexOf("* ") === 0 ? cur.slice(2) : cur;
      if (stripped.indexOf(TITLE_PREFIX) !== 0) return null;
      var i;
      for (i = 0; i < LOG_VALUES.emoji.length; i += 1) {
        var candidate = LOG_VALUES.emoji[i];
        if (candidate && stripped.slice(-candidate.length - 1) === " " + candidate) {
          return candidate;
        }
      }
      return "";
    }
    function syncTitle(doc) {
      var desired = desiredTitle(doc);
      if (desired) {
        if (doc.title === desired) return false;
        var prevEmoji = currentTitleEmoji(doc.title);
        if (prevEmoji !== titleEmoji) {
          logEvent("title", "changed", { type: titleRowKind || "none", emoji: titleEmoji, repo: repoForTitle(doc) });
          logEvent("title", "conditions", titleConditions, "debug");
        }
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
    var titleMutationFrame = null;
    var observer = new MutationObserver(function () {
      if (typeof requestAnimationFrame === "function") {
        if (titleMutationFrame === null) {
          titleMutationFrame = requestAnimationFrame(function () {
            titleMutationFrame = null;
            syncTitle(document);
          });
        }
        return;
      }
      syncTitle(document);
    });
    function observeRoot() {
      var targetRoot = document.body || document.documentElement;
      if (!targetRoot || targetRoot === observedRoot) return;
      if (observedRoot) {
        observer.disconnect();
      }
      observedRoot = targetRoot;
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

    var bootBoardSyncDone = false;
    var lastTitleBoardSyncMs = Date.now();
    var nextTitleBoardSyncDelayMs = 15000;
    function titleStep() {
      observeRoot();
      syncTitle(document);
      var nowTickMs = Date.now();
      if (boardProxyConfig() && (!proxyBoardCache || nowTickMs - lastProxyBoardPullAtMs >= BOARD_PROXY_POLL_MS)) {
        pullProxyBoard(!proxyBoardCache).then(function (pulled) {
          if (!pulled || !pulled.changed || typeof syncPreviewBoardHook !== "function") return;
          var pulledScope = stateScope(document);
          var pulledSid = boardBranch(previewUiBranch || pulledScope.branch || "");
          var pulledBase = boardPreviewBase(document);
          if (pulledBase && pulledSid && pulled.board.allowed_sessions.indexOf(pulledSid) !== -1) {
            var firstSync = !bootBoardSyncDone;
            bootBoardSyncDone = true;
            lastTitleBoardSyncMs = Date.now();
            nextTitleBoardSyncDelayMs = 15000 + randomHttpJitterWindowMs();
            syncPreviewBoardHook(pulledBase, pulledSid, pulledScope.repo || "", { passive: !firstSync });
          }
        });
      }
      if (typeof syncPreviewBoardHook === "function" && boardProxyConfig()) {
        var curBoard = readGlobalBoard();
        var docScopeTick = stateScope(document);
        var selfSidTick = boardBranch(previewUiBranch || docScopeTick.branch || "");
        var tickBase = boardPreviewBase(document);
        if (tickBase && selfSidTick && curBoard.allowed_sessions.indexOf(selfSidTick) !== -1) {
          if (!bootBoardSyncDone) {
            bootBoardSyncDone = true;
            lastTitleBoardSyncMs = nowTickMs;
            nextTitleBoardSyncDelayMs = 15000 + randomHttpJitterWindowMs();
            syncPreviewBoardHook(tickBase, selfSidTick, docScopeTick.repo || "", { passive: false });
          } else if (nowTickMs - lastTitleBoardSyncMs >= nextTitleBoardSyncDelayMs) {
            lastTitleBoardSyncMs = nowTickMs;
            nextTitleBoardSyncDelayMs = 15000 + randomHttpJitterWindowMs();
            syncPreviewBoardHook(tickBase, selfSidTick, docScopeTick.repo || "", { passive: true });
          }
        }
      }
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
    syncTitleNowHook = function () {
      syncTitle(document);
    };
    function onRoute() {
      lastRepo = null;
      lastPath = null;
      syncTitle(document);
    }
    window.addEventListener("popstate", onRoute);
    return function () {
      restartTitleTimerHook = null;
      syncTitleNowHook = null;
      clearInterval(titleTimer);
      if (titleEntry !== null) {
        menuDrop(titleEntry);
        titleEntry = null;
      }
      if (titleMutationFrame !== null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(titleMutationFrame);
        titleMutationFrame = null;
      }
      observer.disconnect();
      window.removeEventListener("popstate", onRoute);
      restoreTitle(document);
      appliedTitle = null;
    };
  });

  function boardBranch(branch) {
    var clean = String(branch || "").trim();
    if (
      !clean ||
      clean.indexOf("..") !== -1 ||
      clean.indexOf("\\") !== -1 ||
      clean.indexOf("//") !== -1 ||
      clean.charAt(0) === "/" ||
      clean.charAt(clean.length - 1) === "/" ||
      /\s/.test(clean)
    ) {
      return "";
    }
    return clean.slice(0, 128);
  }

  function branchSlugTail(branch) {
    var clean = boardBranch(branch);
    return clean.indexOf("/") !== -1 ? clean.split("/").pop() : clean;
  }

  function cleanWorkerId(rawValue) {
    var text = String(rawValue || "").trim();
    if (text.toLowerCase().indexOf("worker-") === 0) text = text.slice(7).trim();
    if (!text) return "";
    var lower = text.toLowerCase();
    if (GREEK_LETTER_SYMBOLS[lower]) return lower;
    return /^[A-Za-z0-9_-]{1,6}$/.test(text) ? text : null;
  }

  function isLegacyHexWorkerId(branch, workerId) {
    var wid = String(workerId || "").trim().toLowerCase();
    if (!wid || GREEK_LETTER_SYMBOLS[wid]) return false;
    var tail = branchSlugTail(branch);
    var head = tail.indexOf("-") !== -1 ? tail.split("-")[0] : tail;
    var token = head.replace(/[^A-Za-z0-9]+/g, "").slice(0, 6).toLowerCase();
    return Boolean(token && wid === token);
  }

  function boardGreekSymbolFor(board, sessionId) {
    var sid = boardBranch(sessionId);
    if (!sid) return "";
    var normalized = normalizeBoard(board);
    if (normalized.allowed_sessions.indexOf(sid) === -1) return "";
    if (boardRoleFor(normalized, sid) === "main") {
      return GREEK_LETTER_SYMBOLS.alpha;
    }
    var explicit = normalized.worker_ids && normalized.worker_ids[sid]
      ? String(normalized.worker_ids[sid]).trim()
      : "";
    if (explicit && !isLegacyHexWorkerId(sid, explicit)) {
      var lowerExp = explicit.toLowerCase();
      return GREEK_LETTER_SYMBOLS[lowerExp] || explicit;
    }
    var targetRepo = cleanBoardRepo("", sid);
    var workerRank = 0;
    for (var i = 0; i < normalized.allowed_sessions.length; i += 1) {
      var candSid = normalized.allowed_sessions[i];
      if (targetRepo && cleanBoardRepo("", candSid) !== targetRepo) continue;
      if (boardRoleFor(normalized, candSid) === "main") continue;
      workerRank += 1;
      if (candSid === sid) {
        var greekName = workerRank < GREEK_LETTER_NAMES.length
          ? GREEK_LETTER_NAMES[workerRank]
          : "";
        return (greekName && GREEK_LETTER_SYMBOLS[greekName]) || explicit || defaultWorkerId(sid, targetRepo);
      }
    }
    return GREEK_LETTER_SYMBOLS.beta;
  }

  function cleanBoardRepo(rawValue, fallbackBranch) {
    var text = String(rawValue || "").trim();
    if (text.indexOf("/") !== -1) text = text.split("/").pop();
    if (!text && fallbackBranch) {
      var tail = branchSlugTail(fallbackBranch);
      var m = /^[0-9a-f]{6,16}-([A-Za-z0-9._-]+)$/i.exec(tail);
      if (m) text = m[1];
    }
    return text.toLowerCase();
  }

  function defaultWorkerId(branch, repo) {
    var tail = branchSlugTail(branch);
    var cleanRepo = String(repo || "").trim();
    if (cleanRepo && tail.length > cleanRepo.length + 1 && tail.slice(-(cleanRepo.length + 1)) === "-" + cleanRepo) {
      tail = tail.slice(0, -(cleanRepo.length + 1));
    }
    var head = tail.indexOf("-") !== -1 ? tail.split("-")[0] : tail;
    var token = head.replace(/[^A-Za-z0-9]+/g, "").slice(0, 6);
    return token || "w1";
  }

  function formatBoardRoleId(role, repo, workerId, multiRepo, fallbackSid) {
    var cleanRepo = String(repo || "").trim();
    if (role === "main") {
      return multiRepo && cleanRepo ? "main-" + cleanRepo : "main";
    }
    if (role === "worker") {
      var wid = cleanWorkerId(workerId) || defaultWorkerId(fallbackSid, cleanRepo);
      return multiRepo && cleanRepo ? "worker-" + wid + "-" + cleanRepo : "worker-" + wid;
    }
    return String(fallbackSid || "");
  }

  function resolveBoardTarget(target, sessions, allowed, mainSid) {
    var clean = boardBranch(target);
    if (!clean) return "";
    var list = Array.isArray(sessions) ? sessions : [];
    for (var i = 0; i < list.length; i += 1) {
      var row = list[i];
      if (!row) continue;
      var rowBr = row.branch || "";
      if (rowBr === clean || row.board_id === clean) return rowBr;
      if (clean.indexOf("/") === -1 && branchSlugTail(rowBr) === clean) return rowBr;
      var wid = row.worker_id || "";
      if (wid && (clean === "worker-" + wid || clean === wid)) return rowBr;
    }
    if (clean === "main" || clean.indexOf("main-") === 0) {
      if (mainSid) return mainSid;
      if (Array.isArray(allowed) && allowed.length) return allowed[0];
    }
    return clean;
  }

  function parseBoardStampMs(value) {
    var text = String(value || "").trim();
    if (!text) return NaN;
    var match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)/.exec(text);
    if (match) text = match[1];
    var normalized = text.indexOf("Z") !== -1 || /[+-]\d{2}:\d{2}$/.test(text) ? text : (text + "Z");
    return Date.parse(normalized);
  }

  function clipBoardStamp(value) {
    var m = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})/.exec(String(value || "").trim());
    return m ? m[1] : "";
  }

  function applyBoardReportOpToList(reportList, op) {
    var items = Array.isArray(reportList) ? reportList.filter(function (r) { return r && typeof r === "object"; }) : [];
    var opName = String((op && (op.op || op.operation)) || "answer").trim().toLowerCase();
    var targetId = String((op && (op.report_id || op.id)) || "").trim();
    if (!targetId) return items;
    var opAt = clipBoardStamp(op && op.at);
    if (opName === "unpublish" || opName === "remove" || opName === "delete") {
      return items.filter(function (row) {
        if (String(row.id || "") !== targetId) return true;
        var rowStamp = clipBoardStamp(row.updated_at || row.published_at || "");
        return Boolean(opAt && rowStamp && opAt < rowStamp);
      });
    }
    if (opName === "answer" || opName === "submit") {
      var subId = String((op && (op.submission_id || op.note_id)) || "").trim();
      var subAt = opAt || new Date().toISOString().slice(0, 19);
      return items.map(function (row) {
        if (String(row.id || "") !== targetId) return row;
        var updated = Object.assign({}, row, { answered: true, needs_answer: false, latest_answer_at: subAt });
        if (subId) updated.latest_answer_id = subId;
        return updated;
      });
    }
    return items;
  }

  function normalizeBoard(raw) {
    var data = raw;
    if (typeof data === "string") {
      try { data = JSON.parse(data); } catch (err) { data = null; }
    }
    if (!data || typeof data !== "object") data = {};
    var multiRepo = Boolean(data.multi_repo);
    var egressVersion = typeof data.egress_version === "string" ? data.egress_version.trim() : "";
    var rawSessions = Array.isArray(data.sessions) ? data.sessions.slice() : [];
    var legacyAliases = Object.create(null);
    for (var la = 0; la < rawSessions.length; la += 1) {
      var laRow = rawSessions[la];
      if (!laRow || typeof laRow !== "object") continue;
      var laBr = boardBranch(laRow.branch || "");
      var laOld = boardBranch(laRow.session_id || "");
      if (laBr && laOld && laOld !== laBr) legacyAliases[laOld] = laBr;
    }
    function normBranchKey(rawKey) {
      var clean = boardBranch(rawKey);
      return clean && legacyAliases[clean] ? legacyAliases[clean] : clean;
    }
    var allowed = Array.isArray(data.allowed_sessions)
      ? data.allowed_sessions.map(normBranchKey).filter(Boolean)
      : [];
    var seenAllowed = {};
    var uniqueAllowed = [];
    for (var i = 0; i < allowed.length; i += 1) {
      if (!seenAllowed[allowed[i]]) {
        seenAllowed[allowed[i]] = true;
        uniqueAllowed.push(allowed[i]);
      }
    }
    var removedList = [];
    var removedSet = {};
    if (Array.isArray(data.removed_sessions)) {
      data.removed_sessions.forEach(function (item) {
        var normRem = normBranchKey(item);
        if (normRem && !seenAllowed[normRem] && !removedSet[normRem]) {
          removedSet[normRem] = true;
          removedList.push(normRem);
        }
      });
    }
    var workerIds = {};
    if (data.worker_ids && typeof data.worker_ids === "object" && !Array.isArray(data.worker_ids)) {
      Object.keys(data.worker_ids).forEach(function (key) {
        var normK = normBranchKey(key);
        var cleanV = cleanWorkerId(data.worker_ids[key]);
        if (normK && !removedSet[normK] && cleanV) workerIds[normK] = cleanV;
      });
    }
    for (var sIdx = 0; sIdx < rawSessions.length; sIdx += 1) {
      var sRow = rawSessions[sIdx];
      if (!sRow || typeof sRow !== "object") continue;
      var sSid = normBranchKey(sRow.branch || sRow.session_id || "");
      if (!sSid || removedSet[sSid]) continue;
      if (branchSlugTail(sSid).indexOf("probe-") === 0 && !seenAllowed[sSid]) {
        removedSet[sSid] = true;
        removedList.push(sSid);
        delete seenAllowed[sSid];
        delete workerIds[sSid];
      }
    }
    uniqueAllowed = uniqueAllowed.filter(function (sidItem) { return !removedSet[sidItem]; });
    var mainId = normBranchKey(data.main_session_id || "");
    if (mainId && (!seenAllowed[mainId] || removedSet[mainId])) mainId = "";
    if (mainId && workerIds[mainId]) {
      var mainRepoSlug = cleanBoardRepo("", mainId);
      var replacementMain = "";
      for (var uIdx = 0; uIdx < uniqueAllowed.length; uIdx += 1) {
        var candSid = uniqueAllowed[uIdx];
        if (!workerIds[candSid] && cleanBoardRepo("", candSid) === mainRepoSlug) {
          replacementMain = candSid;
          break;
        }
      }
      mainId = replacementMain;
    }
    if (mainId) delete workerIds[mainId];
    var sessions = [];
    var seenSessions = {};
    var nowMs = Date.now();
    for (var j = 0; j < rawSessions.length; j += 1) {
      var row = rawSessions[j];
      if (!row || typeof row !== "object") continue;
      var rowSid = normBranchKey(row.branch || row.session_id || "");
      if (!rowSid || seenSessions[rowSid] || removedSet[rowSid] || (branchSlugTail(rowSid).indexOf("probe-") === 0 && !seenAllowed[rowSid])) continue;
      var isPoll = Boolean(row.polling || row.status === "polling");
      var isDisc = Boolean(row.disconnected || row.status === "disconnected");
      if (!seenAllowed[rowSid] && isDisc) {
        var rowStampMs = parseBoardStampMs(row.updated_at);
        if (isNaN(rowStampMs)) {
          var fallbackStamps = ["turn_ended_at", "agent_call_ended_at", "agent_seen_at"];
          for (var fsIdx = 0; fsIdx < fallbackStamps.length; fsIdx += 1) {
            var candMs = parseBoardStampMs(row[fallbackStamps[fsIdx]]);
            if (!isNaN(candMs) && (isNaN(rowStampMs) || candMs > rowStampMs)) {
              rowStampMs = candMs;
            }
          }
        }
        if (!isNaN(rowStampMs) && (nowMs - rowStampMs) > BOARD_SESSION_TTL_SECONDS * 1000) {
          continue;
        }
      }
      seenSessions[rowSid] = true;
      if (row.worker_id && !workerIds[rowSid] && rowSid !== mainId) {
        var delegated = cleanWorkerId(row.worker_id);
        if (delegated) workerIds[rowSid] = delegated;
      }
      var rowRepo = cleanBoardRepo(row.repo, rowSid);
      var rowOut = {
        branch: rowSid,
        board_id: "",
        worker_id: "",
        allowed: Boolean(seenAllowed[rowSid]),
        role: seenAllowed[rowSid] ? "worker" : "blocked",
        repo: rowRepo,
        status: isDisc ? "disconnected" : (isPoll ? "polling" : "active"),
        polling: isPoll,
        disconnected: isDisc,
        updated_at: typeof row.updated_at === "string" && !isNaN(parseBoardStampMs(row.updated_at)) ? row.updated_at : "",
      };
      if (row.survey && typeof row.survey === "object") {
        if (rowOut.allowed) {
          rowOut.survey = row.survey;
        } else {
          var cleanSurvey = Object.assign({}, row.survey);
          if (Array.isArray(cleanSurvey.results)) {
            cleanSurvey.results = cleanSurvey.results.map(function (item) {
              if (!item || typeof item !== "object" || !Object.prototype.hasOwnProperty.call(item, "answer")) {
                return item;
              }
              var redacted = Object.assign({}, item);
              delete redacted.answer;
              return redacted;
            });
          }
          rowOut.survey = cleanSurvey;
        }
      }
      var statusKeys = [
        "polling_since",
        "waiting_for_gates",
        "checking_pr",
        "calls_since_message",
        "gate_threshold",
        "agent_seen_at",
        "turn_ended_at",
        "agent_call_ended_at",
        "remote_head",
        "origin_main_head"
      ];
      for (var sk = 0; sk < statusKeys.length; sk += 1) {
        var sKey = statusKeys[sk];
        if (row[sKey] !== undefined && row[sKey] !== null) {
          rowOut[sKey] = row[sKey];
        }
      }
      sessions.push(rowOut);
    }
    for (var k = 0; k < uniqueAllowed.length; k += 1) {
      var allowedSid = uniqueAllowed[k];
      if (!seenSessions[allowedSid]) {
        seenSessions[allowedSid] = true;
        var allowedRepo = cleanBoardRepo("", allowedSid);
        sessions.push({
          branch: allowedSid,
          board_id: "",
          worker_id: "",
          allowed: true,
          role: "worker",
          repo: allowedRepo,
          status: "active",
          polling: false,
          disconnected: false,
          updated_at: "",
        });
      }
    }
    var repoHasMain = {};
    for (var m1 = 0; m1 < sessions.length; m1 += 1) {
      if (sessions[m1].role !== "blocked" && mainId && sessions[m1].branch === mainId) {
        sessions[m1].role = "main";
        repoHasMain[sessions[m1].repo] = sessions[m1].branch;
      }
    }
    for (var m2 = 0; m2 < sessions.length; m2 += 1) {
      if (sessions[m2].role === "blocked") continue;
      var sRepo = sessions[m2].repo;
      if (!repoHasMain[sRepo] && !workerIds[sessions[m2].branch]) {
        sessions[m2].role = "main";
        repoHasMain[sRepo] = sessions[m2].branch;
      }
    }
    for (var m2b = 0; m2b < sessions.length; m2b += 1) {
      if (sessions[m2b].role === "blocked") continue;
      var sRepoB = sessions[m2b].repo;
      if (!repoHasMain[sRepoB]) {
        sessions[m2b].role = "main";
        repoHasMain[sRepoB] = sessions[m2b].branch;
      } else if (repoHasMain[sRepoB] !== sessions[m2b].branch) {
        sessions[m2b].role = "worker";
      }
    }
    for (var m3 = 0; m3 < sessions.length; m3 += 1) {
      var curRow = sessions[m3];
      curRow.worker_id = curRow.role === "worker"
        ? (workerIds[curRow.branch] || defaultWorkerId(curRow.branch, curRow.repo))
        : "";
      curRow.board_id = formatBoardRoleId(
        curRow.role,
        curRow.repo,
        curRow.worker_id,
        multiRepo,
        curRow.branch,
      );
    }
    var linkedRepos = [];
    var seenLinked = {};
    if (Array.isArray(data.linked_repos)) {
      data.linked_repos.forEach(function (item) {
        var slug = cleanBoardRepo(item, "");
        if (slug && !seenLinked[slug]) {
          seenLinked[slug] = true;
          linkedRepos.push(slug);
        }
      });
    }
    var entries = [];
    if (Array.isArray(data.entries)) {
      for (var eIdx = 0; eIdx < data.entries.length; eIdx += 1) {
        var eRaw = data.entries[eIdx];
        if (!eRaw || typeof eRaw !== "object") continue;
        var eCopy = Object.assign({}, eRaw);
        var eBr = normBranchKey(eCopy.branch || eCopy.session_id || "");
        delete eCopy.session_id;
        eCopy.branch = eBr;
        if (eCopy.to && eCopy.to !== "*" && legacyAliases[eCopy.to]) {
          eCopy.to = legacyAliases[eCopy.to];
        }
        entries.push(eCopy);
      }
    }
    var taskOps = Array.isArray(data.task_ops) ? data.task_ops.slice() : [];
    var rawReportOps = Array.isArray(data.report_ops) ? data.report_ops : [];
    var reportOps = [];
    for (var roIdx = 0; roIdx < rawReportOps.length; roIdx += 1) {
      var rOp = rawReportOps[roIdx];
      if (rOp && typeof rOp === "object") reportOps.push(rOp);
    }
    var workerTasks = {};
    if (data.worker_tasks && typeof data.worker_tasks === "object" && !Array.isArray(data.worker_tasks)) {
      Object.keys(data.worker_tasks).forEach(function (key) {
        var normK = normBranchKey(key);
        if (normK && !removedSet[normK] && Array.isArray(data.worker_tasks[key])) {
          workerTasks[normK] = data.worker_tasks[key].slice();
        }
      });
    }
    var workerReports = {};
    if (data.worker_reports && typeof data.worker_reports === "object" && !Array.isArray(data.worker_reports)) {
      Object.keys(data.worker_reports).forEach(function (key) {
        var normK = normBranchKey(key);
        if (normK && !removedSet[normK] && Array.isArray(data.worker_reports[key])) {
          workerReports[normK] = data.worker_reports[key].slice();
        }
      });
    }
    reportOps.forEach(function (op) {
      if (!op || typeof op !== "object") return;
      var opKind = String(op.op || op.operation || "").trim().toLowerCase();
      if (opKind === "entry-ack") return;
      var opTarget = resolveBoardTarget(op.target || "", sessions, uniqueAllowed, mainId);
      if (!opTarget || !Array.isArray(workerReports[opTarget])) return;
      workerReports[opTarget] = applyBoardReportOpToList(workerReports[opTarget], op);
    });
    var wakes = {};
    if (data.wakes && typeof data.wakes === "object" && !Array.isArray(data.wakes)) {
      Object.keys(data.wakes).forEach(function (wakeK) {
        var normWakeK = normBranchKey(wakeK);
        if (normWakeK && !removedSet[normWakeK]) wakes[normWakeK] = data.wakes[wakeK];
      });
    }
    return {
      egress_version: egressVersion,
      multi_repo: multiRepo,
      linked_repos: linkedRepos,
      removed_sessions: removedList.slice(),
      worker_ids: workerIds,
      worker_tasks: workerTasks,
      task_ops: taskOps,
      worker_reports: workerReports,
      report_ops: reportOps,
      allowed_sessions: uniqueAllowed,
      main_session_id: mainId,
      sessions: sessions,
      entries: entries,
      wakes: wakes,
    };
  }

  function readGlobalBoard() {
    return proxyBoardCache || normalizeBoard(null);
  }

  function boardMaterialSignature(board) {
    var norm = normalizeBoard(board);
    var sessionsSig = (norm.sessions || []).slice().sort(function (a, b) {
      return String(a.branch || "").localeCompare(String(b.branch || ""));
    }).map(function (s) {
      return {
        branch: s.branch || "",
        repo: s.repo || "",
        role: s.role || "",
        allowed: Boolean(s.allowed),
        wid: s.worker_id || "",
        status: s.status || "",
        polling: Boolean(s.polling),
        disc: Boolean(s.disconnected),
        ps: s.polling_since || "",
        wg: Boolean(s.waiting_for_gates),
        cp: Boolean(s.checking_pr),
        calls: Number(s.calls_since_message || 0),
        seen: s.agent_seen_at || "",
        tend: s.turn_ended_at || "",
        cend: s.agent_call_ended_at || "",
        rhead: s.remote_head || "",
        omhead: s.origin_main_head || "",
        surv: s.survey ? String(s.survey.answered_at || s.survey.answered || "") : "",
      };
    });
    var entriesSig = (norm.entries || []).map(function (e) {
      return {
        id: e.id || "",
        to: e.to || "",
        seen: e.seen_at || "",
        ack: e.acknowledged_at || "",
        atp: e.ack_type || "",
        atx: e.ack_text || "",
        asd: e.ack_sender || "",
        aed: e.ack_edited_at || "",
        asc: Number(e.ack_edited_seen_count || 0),
        tid: e.task_id || "",
        rlen: Array.isArray(e.replies) ? e.replies.length : 0,
      };
    });
    var wtKeys = Object.keys(norm.worker_tasks || {}).sort();
    var wtSig = wtKeys.map(function (k) {
      return [k, (norm.worker_tasks[k] || []).map(function (t) {
        return [t.id, t.status, t.order, t.updated_at || ""];
      })];
    });
    var wrKeys = Object.keys(norm.worker_reports || {}).sort();
    var wrSig = wrKeys.map(function (k) {
      return [k, (norm.worker_reports[k] || []).map(function (r) {
        return [r.id, r.updated_at || "", Boolean(r.answered), Boolean(r.needs_answer), r.latest_answer_id || ""];
      })];
    });
    return JSON.stringify({
      ev: norm.egress_version || "",
      mr: Boolean(norm.multi_repo),
      lr: norm.linked_repos || [],
      main: norm.main_session_id || "",
      allow: norm.allowed_sessions || [],
      rem: norm.removed_sessions || [],
      wids: norm.worker_ids || {},
      wakes: norm.wakes || {},
      tops: (norm.task_ops || []).map(function (o) { return o.id || ""; }),
      rops: (norm.report_ops || []).map(function (o) { return o.id || ""; }),
      sessions: sessionsSig,
      entries: entriesSig,
      wt: wtSig,
      wr: wrSig,
    });
  }

  function writeGlobalBoard(board, opts) {
    var proxyNext = updateProxyBoardCache(board, opts && opts.revision);
    if (boardProxyConfig() && (!opts || !opts.fromProxy)) {
      proxyBoardJson("/v1/board", { action: "merge", board: proxyNext }).then(function (res) {
        if (res && res.status === 200 && res.body && res.body.board) {
          updateProxyBoardCache(res.body.board, Number(res.body.revision));
        }
      });
    }
    return proxyNext;
  }

  function scopeBoardForTarget(board, sessionId, repoHint) {
    var normalized = normalizeBoard(board);
    if (proxyBoardEgressVersion && !normalized.egress_version) {
      normalized.egress_version = proxyBoardEgressVersion;
    }
    var sid = boardBranch(sessionId);
    var targetRepo = cleanBoardRepo(repoHint || "", sid);
    var isAllowed = Boolean(sid && normalized.allowed_sessions.indexOf(sid) !== -1);
    var linkedRepos = Array.isArray(normalized.linked_repos) ? normalized.linked_repos : [];
    var knownRepos = [];
    if (targetRepo) knownRepos.push(targetRepo);
    for (var kr = 0; kr < normalized.sessions.length; kr += 1) {
      var krSlug = normalized.sessions[kr].repo || "";
      if (krSlug && (normalized.sessions[kr].allowed || krSlug === targetRepo) && knownRepos.indexOf(krSlug) === -1) {
        knownRepos.push(krSlug);
      }
    }
    for (var lrIdx = 0; lrIdx < linkedRepos.length; lrIdx += 1) {
      if (linkedRepos[lrIdx] && knownRepos.indexOf(linkedRepos[lrIdx]) === -1) {
        knownRepos.push(linkedRepos[lrIdx]);
      }
    }
    var visibleSessions = normalized.sessions.filter(function (row) {
      if (row.branch === sid) return true;
      var rowRepo = row.repo || "";
      if (!targetRepo || !rowRepo || rowRepo === targetRepo) return true;
      if (linkedRepos.length) return linkedRepos.indexOf(rowRepo) !== -1;
      return Boolean(normalized.multi_repo);
    });
    var scopedMain = "";
    if (targetRepo) {
      for (var i = 0; i < normalized.sessions.length; i += 1) {
        var row = normalized.sessions[i];
        if (row.repo === targetRepo && row.allowed && row.role === "main") {
          scopedMain = row.branch;
          break;
        }
      }
      if (!scopedMain && normalized.main_session_id && cleanBoardRepo("", normalized.main_session_id) === targetRepo) {
        scopedMain = normalized.main_session_id;
      }
      if (sid && !isAllowed && scopedMain !== sid) {
        var sameRepoAllowed = normalized.allowed_sessions.some(function (aSid) {
          return cleanBoardRepo("", aSid) === targetRepo;
        });
        if (!sameRepoAllowed) scopedMain = "";
      }
    } else if (!sid || isAllowed) {
      scopedMain = normalized.main_session_id;
    }
    if (sid && !isAllowed) {
      var ownReports = {};
      if (normalized.worker_reports && Array.isArray(normalized.worker_reports[sid])) {
        ownReports[sid] = normalized.worker_reports[sid].slice();
      }
      return Object.assign({}, normalized, {
        main_session_id: scopedMain,
        known_repos: knownRepos,
        sessions: visibleSessions,
        entries: [],
        worker_tasks: {},
        worker_reports: ownReports,
        task_ops: [],
        report_ops: [],
        wakes: {},
      });
    }
    var allowedSet = {};
    normalized.allowed_sessions.forEach(function (aSid) {
      if (aSid) allowedSet[aSid] = true;
    });
    var scopedTasks = {};
    Object.keys(normalized.worker_tasks || {}).forEach(function (k) {
      if (allowedSet[k]) scopedTasks[k] = normalized.worker_tasks[k].slice();
    });
    var scopedReports = {};
    Object.keys(normalized.worker_reports || {}).forEach(function (k) {
      if (allowedSet[k]) scopedReports[k] = normalized.worker_reports[k].slice();
    });
    return Object.assign({}, normalized, {
      main_session_id: scopedMain,
      known_repos: knownRepos,
      sessions: visibleSessions,
      worker_tasks: scopedTasks,
      worker_reports: scopedReports,
    });
  }

  function boardRoleFor(board, branch) {
    var normalized = normalizeBoard(board);
    var sid = boardBranch(branch);
    if (!sid) return "main";
    for (var i = 0; i < normalized.sessions.length; i += 1) {
      if (normalized.sessions[i].branch === sid && normalized.sessions[i].role !== "blocked") {
        return normalized.sessions[i].role;
      }
    }
    var sidRepo = cleanBoardRepo("", sid);
    if (sidRepo) {
      for (var j = 0; j < normalized.sessions.length; j += 1) {
        var sRow = normalized.sessions[j];
        if (sRow.repo === sidRepo && sRow.role === "main") {
          return sRow.branch === sid ? "main" : "worker";
        }
      }
      if (!normalized.main_session_id || cleanBoardRepo("", normalized.main_session_id) !== sidRepo) {
        return "main";
      }
    }
    if (!normalized.main_session_id || normalized.main_session_id === sid) return "main";
    return "worker";
  }

  function canPushOrPr(board, sessionId) {
    return boardRoleFor(board, sessionId) === "main";
  }

  function isBoardWorkerSession(board, sessionId) {
    var normalized = normalizeBoard(board);
    var sid = boardBranch(sessionId);
    if (!sid) return false;
    if (normalized.allowed_sessions.indexOf(sid) === -1) return false;
    return boardRoleFor(normalized, sid) === "worker";
  }

  function reportWaitingOnSubmission(report, reportOps, ownerSid) {
    if (!report || typeof report !== "object") return false;
    var rid = String(report.id || "").trim();
    if (!rid) return false;
    if (Array.isArray(reportOps) && ownerSid) {
      for (var i = 0; i < reportOps.length; i += 1) {
        var op = reportOps[i];
        if (!op || typeof op !== "object") continue;
        if (boardBranch(op.target || "") !== ownerSid) continue;
        if (String(op.report_id || op.id || "").trim() !== rid) continue;
        var opKind = String(op.op || op.operation || "").trim().toLowerCase();
        if (
          opKind === "answer" ||
          opKind === "submit" ||
          opKind === "unpublish" ||
          opKind === "remove" ||
          opKind === "delete"
        ) {
          return false;
        }
      }
    }
    if (
      report.answered ||
      report.latest_answer_id ||
      report.latest_answer_at ||
      report.latest_answer_acknowledged_at
    ) {
      return false;
    }
    if (typeof report.needs_answer === "boolean") return report.needs_answer;
    if (Array.isArray(report.fields)) return report.fields.length > 0;
    if (typeof report.fields === "number") return report.fields > 0;
    return false;
  }

  function boardHasWaitingReportFor(board, sessionId, localReportsMap) {
    var normalized = normalizeBoard(board);
    var sid = boardBranch(sessionId);
    if (!isSafeRecordKey(sid) || isBoardWorkerSession(normalized, sid)) return false;
    var map = localReportsMap && typeof localReportsMap === "object" ? localReportsMap : localSessionReportsByBranch;
    var hasLocal = Object.prototype.hasOwnProperty.call(map, sid) && Array.isArray(map[sid]);
    var ownReports = hasLocal
      ? map[sid].slice()
      : (normalized.worker_reports && Object.prototype.hasOwnProperty.call(normalized.worker_reports, sid) && Array.isArray(normalized.worker_reports[sid]) ? normalized.worker_reports[sid].slice() : []);
    if (Array.isArray(normalized.report_ops)) {
      for (var ro = 0; ro < normalized.report_ops.length; ro += 1) {
        var op = normalized.report_ops[ro];
        if (!op || typeof op !== "object") continue;
        var opKind = String(op.op || op.operation || "").trim().toLowerCase();
        if (opKind === "entry-ack") continue;
        var opTarget = resolveBoardTarget(
          op.target || "",
          normalized.sessions,
          normalized.allowed_sessions,
          normalized.main_session_id,
        );
        if (opTarget === sid) {
          ownReports = applyBoardReportOpToList(ownReports, op);
        }
      }
    }
    for (var i = 0; i < ownReports.length; i += 1) {
      if (reportWaitingOnSubmission(ownReports[i], normalized.report_ops, sid)) return true;
    }
    return false;
  }

  exposeChecks("board", {
    BOARD_PROXY_HOST_KEY: BOARD_PROXY_HOST_KEY,
    BOARD_PROXY_MASTER_KEY: BOARD_PROXY_MASTER_KEY,
    BOARD_PROXY_POLL_MS: BOARD_PROXY_POLL_MS,
    BOARD_SESSION_TTL_SECONDS: BOARD_SESSION_TTL_SECONDS,
    boardProxyConfig: boardProxyConfig,
    updateProxyBoardCache: updateProxyBoardCache,
    pullProxyBoard: pullProxyBoard,
    hydrateBoardFilesForTarget: hydrateBoardFilesForTarget,
    syncPreviewBoard: syncPreviewBoard,
    computeBoardDiff: computeBoardDiff,
    applyBoardDiff: applyBoardDiff,
    computeStateDiff: computeStateDiff,
    applyStateDiff: applyStateDiff,
    resetBoardProxyCache: function () {
      proxyBoardCache = null;
      proxyBoardRevision = 0;
      proxyBoardPullInFlight = null;
      lastProxyBoardPullAtMs = 0;
      hydratedBoardFilesByBranch.clear();
      previewBoardPullByBase.clear();
      previewBoardPushByBranch.clear();
      previewScopedPushByBase.clear();
      previewAutosavePullByBase.clear();
      proxyStateCacheByScope.clear();
    },
    boardBranch: boardBranch,
    cleanWorkerId: cleanWorkerId,
    defaultWorkerId: defaultWorkerId,
    formatBoardRoleId: formatBoardRoleId,
    resolveBoardTarget: resolveBoardTarget,
    normalizeBoard: normalizeBoard,
    boardMaterialSignature: boardMaterialSignature,
    readGlobalBoard: readGlobalBoard,
    writeGlobalBoard: writeGlobalBoard,
    scopeBoardForTarget: scopeBoardForTarget,
    boardRoleFor: boardRoleFor,
    boardGreekSymbolFor: boardGreekSymbolFor,
    isBoardWorkerSession: isBoardWorkerSession,
    reportWaitingOnSubmission: reportWaitingOnSubmission,
    boardHasWaitingReportFor: boardHasWaitingReportFor,
    GREEK_LETTER_SYMBOLS: GREEK_LETTER_SYMBOLS,
    canPushOrPr: canPushOrPr,
  });
  exposeChecks("pause", { PAUSE_KEY: PAUSE_KEY, pauseLabel: pauseLabel });
  exposeChecks("menus", {
    menuRank: menuRank,
    MENU_ORDER: MENU_ORDER,
    SHOW_SETTINGS_BUTTON_KEY: SHOW_SETTINGS_BUTTON_KEY,
    showSettingsButtonLabel: showSettingsButtonLabel,
  });
  exposeChecks("timers", {
    jitteredTimer: jitteredTimer,
    HTTP_JITTER_MS: HTTP_JITTER_MS,
    SKILL_HTTP_JITTER_MAX_MS: SKILL_HTTP_JITTER_MAX_MS,
    isSkillPreviewUrl: isSkillPreviewUrl,
    randomSkillHttpJitterMs: randomSkillHttpJitterMs,
    withSkillHttpJitter: withSkillHttpJitter,
    stateJson: stateJson,
  });
  showPauseMenu();
  showSettingsMenu();
  menuOpen();

})();
