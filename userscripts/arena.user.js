// ==UserScript==
// @name         Arena.ai | NemoUtils | v1.10.40
// @namespace    https://github.com/nemoe7/clankers
// @version      1.10.40
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
    fill: ["inserted", "rebuilt", "no-repo", "no-composer", "no-template", "filled"],
    trim: ["removed"],
    state: ["no-stamp", "compare", "force-stamp", "failed", "file-needed", "download", "saved", "no-preview", "moved", "forced", "confirmation", "no-write", "deferred-picker", "requested", "picker-closed"],
    wake: ["refused", "unavailable"],
    title: ["changed", "restored", "conditions"],
  };
  var LOG_VALUES = {
    feature: ["prompt-fill", "open-steering", "preview-sandbox", "auto-scroll", "transcript-trim", "transcript-alerts", "hide-composer", "state-download", "keep-awake", "tab-title"],
    group: ["note", "task"],
    verdict: ["older", "same", "forward"],
    kind: ["none", "chat", "reasoning", "poll", "play", "action", "error", "unchanged", "stale", "download"],
    route: ["link", "manager", "stamped"],
    emoji: ["", "💬", "💭", "🖥️", "📖", "✏️", "🔍", "💤", "📜", "❓", "⚙️", "⏳", "🛡️"],
    level: LOG_LEVELS,
    code: ["unknown", "manager-download", "copy-state", "missing-branch", "older-history", "wrong-file", "write", "file-api", "NotAllowedError", "AbortError", "NotFoundError", "SecurityError", "TypeError", "Error"],
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
      return "Userscript — log level (" + getLogLevel().toUpperCase() + ")";
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

  function menuRank(label) {
    var index = MENU_ORDER.indexOf(String(label).split(" — ")[0]);
    return index === -1 ? MENU_ORDER.length : index;
  }

  function menuRegister(entry) {
    if (typeof GM_registerMenuCommand !== "function") return;
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

  function menuAdd(label, press) {
    var entry = { seq: menuNextSeq, label: label, press: press, id: null };
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
    return PAUSE_LABEL + (paused ? " — resume all" : " — pause all");
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

  function jitteredTimer(run, everyMs, spreadMs) {
    var waiting = null;
    function tick() {
      waiting = setTimeout(function () {
        waiting = null;
        run();
      }, Math.floor(Math.random() * spreadMs));
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

  runFeature("prompt-fill", "Composer — fill", function () {

    var COMPOSER_SELECTOR = 'div.tiptap.ProseMirror[contenteditable="true"]';
    var TEMPLATE_RE = /^(\S+) read (?:AGENTS\.md ARENA\.md|ARENA\.md AGENTS\.md)/;

    var PROXY_HOST_KEY = "clankers-arena-proxy-host";
    var PROXY_MASTER_KEY = "clankers-arena-proxy-master";

    function proxyHost(raw) {
      var host = String(raw || "").trim().replace(/\/+$/, "").replace(/\/v1$/, "");
      return /^https:\/\/[a-z0-9.-]+$/i.test(host) ? host : null;
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

    function keyNote(kind, key, atIso, host) {
      return (
        "Arena proxy " +
        host +
        " key " +
        kind +
        " at " +
        atIso +
        ". New key: " +
        key +
        ". Use it as ?key= in every /v1 call. Routes: /v1/ping lists them;"
        + " skills/arena-skill/arena-egress-proxy holds the map. Never print it."
      );
    }

    function noteKey(key, host, kind) {
      if (GM_getValue(NOTED_KEY, "") === key) return;
      GM_setValue(NOTED_KEY, key);
      postKeyNote(keyNote(kind, key, new Date().toISOString(), host));
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
      PROXY_MASTER_KEY: PROXY_MASTER_KEY,
      proxyHost: proxyHost,
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
        ensureAgentKey();
        sync();
      });
    }

    setProxyValue(PROXY_HOST_KEY, "Proxy — host", GM_getValue(PROXY_HOST_KEY, ""));
    setProxyValue(PROXY_MASTER_KEY, "Proxy — master key", "");

    function settings() {
      return {
        host: proxyHost(GM_getValue(PROXY_HOST_KEY, "")),
        master: String(GM_getValue(PROXY_MASTER_KEY, "") || "").trim(),
      };
    }

    var postedBase = null;
    function postKeyToPreview(force) {
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

    menuItem(proxyMenus, "Proxy — post key now", function () {
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
    });

    rotateKey(ROTATE_MIN_SECONDS, null);

    var stopRotate = jitteredTimer(function () {
      rotateKey(ROTATE_MIN_SECONDS, null);
    }, ROTATE_INTERVAL_MS, HTTP_JITTER_MS);

    var stopKeyWatch = jitteredTimer(function () {
      if (captchaSignal(document)) return;
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

    function setComposerText(el, text) {
      el.focus();
      var selection = window.getSelection();
      var range = document.createRange();
      range.selectNodeContents(el);
      selection.removeAllRanges();
      selection.addRange(range);
      var ok = document.execCommand("insertText", false, text);
      var matched = String(el.innerText || "").trim() === text;
      logEvent("fill", "inserted", { ok: ok, matched: matched }, "debug");
      if (!ok || !matched) {
        while (el.firstChild) {
          el.removeChild(el.firstChild);
        }
        var lines = text.split("\n");
        for (var j = 0; j < lines.length; j += 1) {
          var paragraph = document.createElement("p");
          paragraph.textContent = lines[j];
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

  runFeature("open-steering", "Steering — open", function () {

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
      if (captchaSignal(document)) return;
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

  runFeature("preview-sandbox", "Steering — new tabs and downloads", function () {
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

  function setToggleButtonPressed() {
    if (!autoToggleButton) return;
    autoToggleButton.className = autoToggleClasses(autoScroll.isOn());
    autoToggleButton.setAttribute("aria-pressed", autoScroll.isOn() ? "true" : "false");
  }

  var autoScroll = runFeature("auto-scroll", "Transcript — auto-scroll", function () {
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
        "Transcript — keep " +
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
      return "Transcript — auto trim interval " + Math.round(tickMs() / 1000) + " s";
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
      return "Transcript \u2014 trim cap " + capValue() + " rows";
    }

    function registerCap() {
      if (capEntry !== null) menuDrop(capEntry);
      capEntry = menuAdd(capLabel, setCapByPrompt);
    }

    function setCapByPrompt() {
      if (typeof prompt !== "function") return;
      var answer = prompt("Rows cut per trim pass (1 to 1000)", String(capValue()));
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
      var answer = prompt("Auto trim interval in seconds (1 to 60)", String(Math.round(tickMs() / 1000)));
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

    runFeature("transcript-trim", "Transcript — auto trim", function () {
      registerInterval();
      observer = new MutationObserver(function () {
        settleState.mutationAt = Date.now();
      });
      observer.observe(document.documentElement, { childList: true, subtree: true });
      timer = setInterval(tick, tickMs());
      return function () {
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
    nowEntry = menuAdd(function () {
      return "Transcript — trim now";
    }, function () {
      trim();
    });
  })();

  runFeature("transcript-alerts", "Transcript — hide generation alerts", function () {
    var ALERT_SELECTOR = '[role="alert"][class~="border-red-500/30"][class~="bg-red-500/10"]';

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
          if (!generating || node.isConnected === false || !node.matches(ALERT_SELECTOR)) restore(node, prior);
          else if (!hasHiddenStyle(node)) hidden.delete(node);
        });
        if (!generating) return;
        var alerts = doc.querySelectorAll(ALERT_SELECTOR);
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

    if (exposeChecks("transcriptAlerts", { ALERT_SELECTOR: ALERT_SELECTOR, alertVisibility: alertVisibility })) return;
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

  runFeature("hide-composer", "Composer — hide", function () {

    var SHELL_SELECTOR = "div.flex.w-full.flex-col.items-start.justify-center.p-2";
    var EDITOR_CONTENT_SELECTOR = "div.editor-content";
    var HIDE_MARK = "data-clankers-hidden";
    var SPACER_SELECTOR = 'div.shrink-0[style*="height: 24px"]';
    var SPACER_HEIGHT = "24px";
    var fixedSpacers = new WeakSet();
    var spacerStyles = new Map();
    var editorStates = new Map();

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
        kind: "error",
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
        kind: "unchanged",
        name: name,
        message: "State unchanged since the last write: " + name,
      };
    }
    if (!force && memory.stamp && String(stamp) < memory.stamp) {
      return {
        kind: "stale",
        name: name,
        message:
          "Stale preview state (" + stamp + " is older than " + memory.stamp + "); nothing written.",
      };
    }
    if (held.length) {
      var phrase = held.join(" and ") + (held.length > 1 ? " stamps" : " stamp");
      return {
        kind: "stale",
        name: name,
        message: "Rolled-back preview state (" + phrase + " went backward); nothing written.",
      };
    }
    return { kind: "download", name: name, message: "Wrote " + name };
  }

  function handleMatchesScope(handle, repo, branch) {
    if (!handle || !handle.name) return false;
    var scope = stateScopeKey(repo, branch);
    var name = String(handle.name);
    if (name.slice(-7) === ".ndjson") name = name.slice(0, -7);
    return name === scope || name.indexOf(scope + "-") === 0;
  }

  function saveMoved(branch, remembered, base, rememberedScope, rememberedBranch) {
    return !(branch || rememberedScope) ||
      (Boolean(remembered) && remembered !== base) ||
      (Boolean(branch) && Boolean(rememberedBranch) && branch !== rememberedBranch);
  }

  function overwriteAsk(moved, plan, hasHandle, force) {
    return !force && Boolean(moved) && hasHandle && plan.kind === "download";
  }

  function overwriteLine(name) {
    return "Preview URL or branch changed. Overwrite " + name + " with this state?";
  }

  function stateDelivery(plan, hasHandle, hasPicker) {
    if (plan.kind !== "download") return plan.kind;
    if (hasHandle) return "write";
    return hasPicker ? "pick" : "download";
  }

  function stateAction(route, manual) {
    if (!manual) return route === "pick" || route === "download" ? "block" : route;
    return route === "pick" ? "hint" : route;
  }

  function getLine(status, base) {
    return "GET " + status + " " + base;
  }

  function copyLine(status, base) {
    return getLine(status, base + "/api/copy-state");
  }

  function writeFailLine(err) {
    return (
      "write failed (" + ((err && err.name) || "unknown") +
      "); press the choose entry for the file again"
    );
  }

  function managerFailLine(err) {
    return "manager download failed (" + ((err && err.error) || "unknown") + "); using the link";
  }

  var STATE_LINES = {
    hint: "no file selected; launching dialog",
    history: "history does not match",
    pickerClosed: "no file selected;",
    noPreview: "no preview detected",
    noBranch: "session branch not found; state save blocked",
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

  runFeature("state-download", "State — download", function () {
    if (exposeChecks("stateDownload", {
      STATE_LINES: STATE_LINES,
      copyLine: copyLine,
      getLine: getLine,
      writeFailLine: writeFailLine,
      managerFailLine: managerFailLine,
      stateError: stateError,
      stateFileName: stateFileName,
      stateScopeKey: stateScopeKey,
      stateDownload: stateDownload,
      stateMemory: stateMemory,
      stateRemembered: stateRemembered,
      stateDelivery: stateDelivery,
      stateAction: stateAction,
      panelNeeded: panelNeeded,
      writtenName: writtenName,
      handleMatchesScope: handleMatchesScope,
      saveMoved: saveMoved,
      overwriteAsk: overwriteAsk,
      overwriteLine: overwriteLine,
      stateScope: stateScope,
      stateRepo: stateRepo,
      stateBranch: stateBranch,
      readSlug: readSlug,
      slugFromBare: slugFromBare,
      pagePicker: pagePicker,
      downloadRoute: downloadRoute,
      stateDownloadRoute: stateDownloadRoute,
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
    var staleWarned = false;
    var picked = null;
    var pickedKey = null;

    function previewBase(doc) {
      var frames = doc.querySelectorAll("iframe[title]");
      var i;
      for (i = 0; i < frames.length; i += 1) {
        var title = frames[i].getAttribute("title") || "";
        if (title.indexOf("App preview on port 8000") === 0 && frames[i].src) {
          return frames[i].src.replace(/\/+$/, "");
        }
      }
      return null;
    }

    function getJson(url, done) {
      if (typeof GM_xmlhttpRequest !== "function") return;
      GM_xmlhttpRequest({
        method: "GET",
        url: url,
        headers: {},
        onload: function (answer) {
          var body = null;
          try {
            body = JSON.parse(answer.responseText);
          } catch (err) {
            body = null;
          }
          done(answer.status, body);
        },
        onerror: function () {
          done(0, null);
        },
      });
    }

    function pagePicker() {
      var page = typeof unsafeWindow !== "undefined" ? unsafeWindow : null;
      if (!page && typeof window !== "undefined") page = window;
      var picker = page && page.showSaveFilePicker;
      if (typeof picker !== "function") return null;
      return function (options) {
        return picker.call(page, options);
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
        });
      });
    }

    var STATE_PANEL_ID = "clankers-state-panel";
    var STATE_PANEL_MS = 6000;

    function panelNeeded(manual, shown) {
      return Boolean(manual) || !shown;
    }

    function removeStatePanel() {
      try {
        var node = document.getElementById ? document.getElementById(STATE_PANEL_ID) : null;
        if (node && node.parentNode) node.parentNode.removeChild(node);
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
        close.textContent = "Dismiss";
        close.style.cssText =
          "cursor:pointer;border:1px solid #56504a;border-radius:6px;padding:5px 10px;" +
          "background:transparent;color:inherit;font:inherit";
        close.addEventListener("click", removeStatePanel);
        row.appendChild(close);
        card.appendChild(row);
        document.body.appendChild(card);
        if (autoHide) setTimeout(removeStatePanel, STATE_PANEL_MS);
      } catch (err) {
        return;
      }
    }

    function stateError(line, actionLabel, action, code, status, showPanel) {
      logEvent("state", "failed", { code: code || "unknown", status: status }, code === "file-api" ? "warn" : "error");
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
          "No save file is set, so state saves are blocked.",
          "Choose file",
          chooseStateFile
        );
      }
    }

    function askOverwrite(handle, storeKey, manual) {
      var askedKey = overwriteKey(storeKey);
      var shown = GM_getValue(askedKey, false);
      if (!panelNeeded(manual, shown)) return;
      GM_setValue(askedKey, true);
      statePanel(overwriteLine(writtenName(handle, "the save file")), "Overwrite", function () {
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
        setTimeout(function () {
          URL.revokeObjectURL(url);
        }, 1000);
        return;
      }
      GM_download({
        url: url,
        name: name,
        saveAs: false,
        onload: function () {
          logEvent("state", "saved", { route: "manager", filename: name });
          URL.revokeObjectURL(url);
        },
        onerror: function (err) {
          stateError(managerFailLine(err), null, null, "manager-download");
          linkDownload(url, name);
          setTimeout(function () {
            URL.revokeObjectURL(url);
          }, 1000);
        },
      });
    }

    function fetchStateFile(manual, force) {
      var base = previewBase(document);
      if (!base) {
        logEvent("state", "no-preview", null, "debug");
        return;
      }
      getJson(base + "/api/copy-state", function (status, body) {
        if (status !== 200 || !body) {
          stateError(copyLine(status, base), null, null, "copy-state", status);
          return;
        }
        var scope = stateScope(document);
        var lastScope = GM_getValue(lastScopeKey(scope.repo), "");
        if (!scope.branch && !lastScope && !force) {
          stateError(STATE_LINES.noBranch, null, null, "missing-branch");
          return;
        }
        var storeKey = scope.branch
          ? stateScopeKey(scope.repo, scope.branch)
          : lastScope || stateScopeKey(scope.repo, "");
        var storedKey = lastScope || storeKey;
        var rememberedBase = GM_getValue(baseKey(storedKey), "");
        var rememberedBranch = GM_getValue(branchKey(storedKey), "");
        var moved = saveMoved(scope.branch, rememberedBase, base, lastScope, rememberedBranch);
        if (moved) {
          logEvent("state", "moved", { repo: scope.repo });
        }
        var memory = stateRemembered(GM_getValue(stampKey(storeKey), ""));
        if (force) {
          logEvent("state", "forced");
        }
        var plan = stateDownload(
          scope.repo,
          scope.branch,
          body.stamp,
          body.counts,
          memory,
          body.stamps,
          force,
        );
        if (plan.kind === "stale") {
          stateError(STATE_LINES.history, null, null, "older-history", undefined, !staleWarned);
          staleWarned = true;
          return;
        }
        var hasPicker = Boolean(pagePicker());
        var ready = pickedKey === storeKey && picked
          ? Promise.resolve(picked)
          : stateHandle(fileKey(storeKey));
        ready.then(function (handle) {
          if (handle && !handleMatchesScope(handle, scope.repo, scope.branch)) {
            stateError(
              "handle out of scope: " + handle.name + " is not " +
                stateFileName(scope.repo, scope.branch, "", null),
              null, null, "wrong-file",
            );
            handle = null;
          }
          if (overwriteAsk(moved, plan, Boolean(handle), force)) {
            logEvent("state", "confirmation", { filename: handle.name });
            askOverwrite(handle, storeKey, manual);
            return;
          }
          picked = handle || null;
          pickedKey = handle ? storeKey : null;
          var action = stateAction(stateDelivery(plan, Boolean(handle), hasPicker), manual);
          if (action === "unchanged") {
            logEvent("state", "no-write", { kind: plan.kind, repo: scope.repo }, "debug");
            return;
          }
          if (action === "error") {
            logEvent("state", "no-write", { kind: plan.kind }, "debug");
            return;
          }
          if (action === "block") {
            hintStateFile(manual);
            return;
          }
          if (action === "hint") {
            hintStateFile(manual);
            logEvent("state", "deferred-picker", null, "warn");
            return;
          }
          if (action === "write") {
            logEvent("state", "requested", { status: status }, "debug");
            writeToHandle(handle, body.text).then(
              function () {
                rememberState(
                  scope,
                  storeKey,
                  base,
                  scope.branch || rememberedBranch,
                  body.stamp,
                  body.stamps,
                );
                logEvent("state", "saved", { repo: scope.repo, filename: writtenName(handle, plan.name) });
                if (force) {
                  statePanel("Force save wrote " + writtenName(handle, plan.name) + ".", null, null, true);
                }
              },
              function (err) {
                picked = null;
                pickedKey = null;
                hintStateFile(true);
                stateError(writeFailLine(err), "Choose file", chooseStateFile, "write");
              },
            );
            return;
          }
          logEvent("state", "download", { route: "stamped", filename: plan.name });
          if (force) {
            statePanel("Force save downloaded " + plan.name + ".", null, null, true);
          }
          writeStateDownload(body.text, plan.name);
          rememberState(
            scope,
            storeKey,
            base,
            scope.branch || rememberedBranch,
            body.stamp,
            body.stamps,
          );
        });
      });
    }

    function chooseStateFile() {
      var pick = pagePicker();
      if (!pick) {
        stateError("this browser cannot write files; the stamped download is used", null, null, "file-api");
        return;
      }
      pick({
        suggestedName: (function () {
          var scope = stateScope(document);
          return stateFileName(scope.repo, scope.branch, "", null);
        })(),
        types: [
          {
            description: "NDJSON state",
            accept: { "application/x-ndjson": [".ndjson"] },
          },
        ],
      })
        .then(function (handle) {
          var scope = stateScope(document);
          var storeKey = stateScopeKey(scope.repo, scope.branch);
          return saveStateHandle(handle, fileKey(storeKey)).then(function () {
            picked = handle;
            pickedKey = storeKey;
            GM_setValue(stampKey(storeKey), "");
            GM_setValue(STATE_HINT_KEY, false);
            removeStatePanel();
            fetchStateFile(true);
          });
        })
        .catch(function () {
          logEvent("state", "picker-closed", null, "debug");
        });
    }

    var menus = [];
    menuItem(menus, "State — choose the file", chooseStateFile);
    menuItem(menus, "State — force save", function () {
      fetchStateFile(true, true);
    });

    fetchStateFile(false);
    var stopStateWatch = jitteredTimer(function () {
      fetchStateFile(false);
    }, STATE_WATCH_MS, HTTP_JITTER_MS);
    return function () {
      stopStateWatch();
      menus.forEach(menuDrop);
      menus = [];
    };
  });

  runFeature("keep-awake", "Page — keep awake", function () {
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

  runFeature("tab-title", "Page — tab title", function () {

    var REPO_LINK_SELECTOR = 'a[aria-label^="Open "][aria-label$=" on GitHub"]';
    var MESSAGE_SELECTOR = "[data-agent-transcript-message]";
    var LIVE_ICON_SELECTOR = ".animate-pulse";
    var LIVE_LABEL_SELECTOR = 'p[style*="text-shimmer"]';
    var GROUP_LABEL_SELECTOR = "span.text-text-secondary";
    var LABEL_SPAN_SELECTOR = "span.body-sm";
    var SUMMARY_LABEL = "Summary";
    var TITLE_PREFIX = "Arena | ";
    var VERSION = "1.10.27";
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

    function lastRoot(doc) {
      var roots =
        typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(MESSAGE_SELECTOR) : [];
      return roots.length ? roots[roots.length - 1] : null;
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

    function rowCommand(row) {
      if (!row || typeof row.querySelector !== "function") {
        return "";
      }
      var panel = row.querySelector("pre");
      return panel ? String(panel.textContent || "") : "";
    }

    function emojiForRow(row) {
      if (!row) {
        titleRowKind = "none";
        return null;
      }
      var kind = rowKind(row);
      if (kind === "chat") {
        titleRowKind = "chat";
        return AGENT_EMOJI;
      }
      if (kind === "reasoning") {
        titleRowKind = "reasoning";
        return REASONING_EMOJI;
      }
      if (POLL_RE.test(rowCommand(row).toLowerCase())) {
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
      var root = live ? lastRoot(doc) : null;
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
        logEvent("title", "changed", { kind: titleRowKind || "none", emoji: titleEmoji, repo: repoForTitle(doc) });
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
      lastRoot: lastRoot,
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
      VERSION: VERSION,
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
      return "Tab title — every " + Math.round(titleTickMs() / 1000) + " s";
    }

    function registerTitleInterval() {
      if (titleEntry !== null) menuDrop(titleEntry);
      titleEntry = menuAdd(titleIntervalLabel, setTitleTickByPrompt);
    }

    function setTitleTickByPrompt() {
      if (typeof prompt !== "function") return;
      var answer = prompt(
        "Tab title tick in seconds (1 to 60)",
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
    function onRoute() {
      lastRepo = null;
      lastPath = null;
      syncTitle(document);
    }
    window.addEventListener("popstate", onRoute);
    return function () {
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
  exposeChecks("menus", { menuRank: menuRank, MENU_ORDER: MENU_ORDER });
  exposeChecks("timers", { jitteredTimer: jitteredTimer, HTTP_JITTER_MS: HTTP_JITTER_MS });
  showPauseMenu();
  menuOpen();

})();
