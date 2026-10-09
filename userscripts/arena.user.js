// ==UserScript==
// @name         Arena.ai | NemoUtils | v1.10.16
// @namespace    https://github.com/nemoe7/clankers
// @version      1.10.16
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

  // Outside a browser each feature publishes its helpers, so the checks live in maintenance/.
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

  // One tag filters the whole page story; the module rides a second bracket.
  function logEvent(module, event, detail) {
    var line = LOG_TAG + "[" + module + "] " + event;
    try {
      if (detail === undefined) {
        console.log(line);
      } else {
        console.log(line, detail);
      }
    } catch (err) {
      return;
    }
  }

  // The manager appends every command in the order it arrives, so the entries come from one
  // ordered list: each script registers an entry, and the whole list opens in module order. One
  // module's entries then sit together whatever order the features load in.
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

  // One refresh writes the whole list in module order, so a label that moved or an entry that
  // arrived after the load lands in its own group.
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

  // One menu entry with one guard, so a manager without a menu gets nothing. The press writes
  // its own line before the command runs, so one filter shows every menu press.
  function menuItem(list, label, run) {
    list.push(
      menuAdd(function () {
        return label;
      }, function () {
        logEvent("menu", label);
        run();
      }),
    );
  }

  exposeChecks("logging", { logEvent: logEvent, LOG_TAG: LOG_TAG, menuItem: menuItem });

  // The transcript bar, the saved slug key and the arena URL readers are page-wide, so one
  // copy serves every feature.
  var BAR_SELECTOR =
    "div.relative.z-10.w-full.md\\:absolute.md\\:left-0.md\\:top-full";
  var SLUG_KEY = "clankers-arena-agent-slug";

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

  // The global pause stops every feature where it stands and honors the pause on the next
  // load; the resume brings back the features whose own switch is ON (form answer 74b99a5).
  var PAUSE_KEY = "clankers-arena-userscript-paused";
  var PAUSE_LABEL = "Userscript";
  var pauseUnits = [];
  var pauseEntry = null;

  function pauseStored() {
    // The checks load this file without the manager grants, so the pause reads as off there.
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
    logEvent("pause", "all: " + (next ? "PAUSED" : "RESUMED"));
  }

  // A repeating timer that touches HTTP scatters each call inside its own band, so the requests
  // never form a fixed beat; a DOM tick keeps its steady interval. A stop clears the beat and
  // any call already waiting.
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
    logEvent("feature", label + ": " + (enabled ? "ON" : "OFF"));

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
      logEvent("feature", label + ": " + (next ? "ON" : "OFF"));
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

  // The security check owns the page while it shows, so the automatic posts wait for it.
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

  // The ask_user card: one radiogroup with an aria-label, taken from the owner's
  // captured outerHTML. It holds the title while the question waits for an answer.
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

    // The fill writes the initial message: the repo name leads it, the rules stay in the files.
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

    var TEMPLATE_TAIL =
      "\n\nBefore you implement, answer or report, run this order:" +
      "\n\n1. Read the task and every file it touches in full; trace the real flow end to end" +
      " before you plan." +
      "\n2. Name the requirements and the constraints; follow the conventions the code already uses." +
      "\n3. Take the smallest change that holds: reuse first, one line second, new code last," +
      " and add nothing the task does not ask for." +
      "\n4. Write the failing check before new behavior; reproduce a bug before you touch it." +
      "\n5. Keep the behavior, interfaces, validation and security that stand, unless the task" +
      " changes them." +
      "\n6. Verify with the project's own gate; read the result before you report it." +
      "\n\nNew behavior: red first. Write the failing check, make the smallest change that passes it," +
      " refactor without a behavior change, then recheck." +
      "\n\nFor a bug: reproduce it, change one variable at a time, fix the root cause where every" +
      " caller routes through, cover the fix with a check, then recheck. Never repeat a failed" +
      " approach without a new reason." +
      "\n\nState every assumption the moment you make it. Ask one question when a wrong reading" +
      " changes the result." +
      "\n\nNEVER claim a check you did not run. Print what you skipped, and name what stays unverified." +
      "\n\nExpect screenshots, notes and corrections through the steering channel. Read an image" +
      " itself, not only its text, and invent no visual detail. Take each one in the next reply." +
      "\n\nStop when verification holds, and finish with what changed, what you checked, and what" +
      " is open.";

    function promptForSlug(slug, arenaMd) {
      var base = slug + " read ARENA.md AGENTS.md in full before your first edit, and follow both." + TEMPLATE_TAIL;
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

    // The rules of this repository, at a fixed URL: a session in another repository
    // still receives them.
    var ARENA_MD_URL =
      "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/rules/ARENA.md";

    if (exposeChecks("promptFill", {
      isComposerUrl: isComposerUrl,
      slugFromOwnerRepo: slugFromOwnerRepo,
      promptForSlug: promptForSlug,
      shouldWrite: shouldWrite,
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

    var arenaMdCache = null;
    var heldKey = null;
    var arenaMdTried = false;
    var pendingFetch = null;
    var keyTried = false;
    var keyFetch = null;

    function fetchArenaMd() {
      return fetch(ARENA_MD_URL).then(function (r) {
        if (!r.ok) return null;
        return r.text();
      }).catch(function () { return null; });
    }

    function ensureFetch() {
      if (arenaMdTried || pendingFetch) return;
      pendingFetch = fetchArenaMd().then(function (content) {
        arenaMdCache = typeof content === "string" ? content : null;
        arenaMdTried = true;
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
    var slugLogged = false;
    var composerLogged = null;

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
      }
    }

    function sync() {
      if (captchaSignal(document)) return;
      postKeyToPreview(false);
      if (!isComposerUrl(location.href)) {
        // A route away from the composer ends that conversation's fill: a return to
        // /agent is a new chat, so the same repo fills again.
        lastSlug = null;
        filledSlug = null;
        return;
      }
      var slug = readSlug(document);
      if (!slug) {
        if (!slugLogged) {
          slugLogged = true;
          logEvent("fill", "no repo detected");
        }
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
      slugLogged = false;
      rememberSlug(slug);
      // One write per page: the fill waits for the one ARENA.md fetch, then writes the
      // message with the file under it when the fetch answered and without it when not.
      if (!arenaMdTried) {
        ensureFetch();
        ensureAgentKey();
        return;
      }
      var composer = document.querySelector(COMPOSER_SELECTOR);
      if (!composer || composer.getAttribute("aria-disabled") === "true") {
        if (composerLogged !== slug) {
          composerLogged = slug;
          logEvent("fill", "no composer detected for " + slug);
        }
        lastSlug = slug;
        return;
      }
      composerLogged = null;
      var current = composer.innerText || "";
      if (!shouldWrite(current, slug, lastSlug, filledSlug)) {
        lastSlug = slug;
        ensureFetch();
        ensureAgentKey();
        return;
      }
      setComposerText(composer, promptForSlug(slug, arenaMdCache));
      logEvent("fill", "filled composer for " + slug);
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

    // The Steering row drifts on labels, so it is found by its words.
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
      // The port switcher in the header wears the same ":8000" text. Clicking it opens a dialog, not a steering channel.
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

  // One toggle beside Stop mirrors the auto-scroll switch.
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

    // The button injector runs beside the switch: the script-wide pause stops it too.
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

    // A trim empties every older root and hides it, and keeps the newest rows of the
    // newest root, once the page settles. The switch gates the interval and the tick
    // alone: the plan line and the trim-now press stay on the menu whatever it reads.
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

    function trimMessage(removed, keep) {
      return (
        "removed " + removed + " " + (removed === 1 ? "row" : "rows") + " (kept " + keep + ")"
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

    // The budget root is the newest root that still holds rows: an answered
    // question appends an empty root behind the transcript, and the rows in
    // front of it must keep their newest count instead of clearing the page.
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

    // The budget root keeps its own newest rows; every other root empties in full
    // and takes the hidden class once empty, while the root node itself stays,
    // because that node is the part Arena needs intact.
    function trimPlan(doc, plan) {
      var roots = messageRoots(doc);
      var keep = planParts(plan).rows;
      var removed = 0;
      var holder = budgetRoot(roots);
      var i;
      for (i = 0; i < roots.length; i += 1) {
        if (roots[i].isConnected === false) continue;
        var newest = i === holder;
        var rows = rowsOfRoot(roots[i]);
        var removedFromRoot = trimRows(rows, newest ? keep : 0);
        removed += removedFromRoot;
        // The action container carries the newest rows on the live page, so it
        // leaves only with a root the trim emptied; a root that keeps rows keeps
        // its actions, and the newest rows stay with them.
        var attached = 0;
        var j;
        for (j = 0; j < rows.length; j += 1) {
          if (rowLive(rows[j])) attached += 1;
        }
        if (removedFromRoot && !attached) removeActionSibling(roots[i]);
        // Hidden cut rows still occupy the root, so the root itself never hides;
        // a page with no rows at all keeps every root the way it stands.
        if (holder !== -1 && !newest && !attached && typeof roots[i].classList !== "undefined") {
          roots[i].classList.add("hidden");
        }
      }
      return removed;
    }

    // The trim runs only while a turn is up, so a missing stop control aborts it and
    // is checked first; a visible question card aborts too; the quiet gate rides the
    // scheduler.
    function isSettled(doc) {
      if (!findStopGeneratingButton(doc)) return false;
      if (doc.querySelector(QUESTION_SELECTOR)) return false;
      return true;
    }

    // Quiet means the whole page holding still, not the row count alone: the page
    // streams into existing rows after the last row lands, so a fresh mutation keeps
    // the trim waiting even while the count holds.
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

    // A row counts while it is attached and not yet cut: a cut row stays in the
    // page as a hidden empty shell, because the page reinstates removed nodes.
    function rowLive(row) {
      if (!row.parentElement) return false;
      return !(
        row.classList &&
        typeof row.classList.contains === "function" &&
        row.classList.contains("hidden")
      );
    }

    // The cut hides the row and empties its text instead of removing the node: a
    // hidden empty shell cannot be reinstated, and its inner text is what the row
    // costs.
    function clearRow(row) {
      if (row.classList && typeof row.classList.add === "function") {
        row.classList.add("hidden");
      }
      row.textContent = "";
    }

    // The owner sets the per-pass cap; anything under one row falls back to the default.
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
      // One pass cuts at most the cap, so a big backlog drains in steps instead of
      // one blocking burst the page must reconcile at once.
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
      trimMessage: trimMessage,
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

    // The owner sets the tick in seconds; the bounds hold it between one second and a minute.
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
        // The cut is silent on the page, so the console line carries what left.
        logEvent("trim", trimMessage(removed, keep));
        refreshLabel();
      }
      return removed;
    }

    // Streaming mutates the page constantly, so a mutation-driven scheduler fired
    // on every flicker; one plain interval asks the gates at a steady 5 s instead.
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
    // The owner's button: one press runs the cut at once, whatever the switch reads.
    nowEntry = menuAdd(function () {
      return "Transcript — trim now";
    }, function () {
      trim();
    });
  })();

    // The composer hides while a turn runs, and its spacer height returns on show.
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

  // The name leads with the repository, then the branch: the bare pair,
  // and the stamp and the counts follow the branch part when the save is stamped.
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
      logEvent("state", "compare stamp: none, no stamp to compare");
      return {
        kind: "error",
        message: "The state carries no stamp; the next save names it.",
      };
    }
    var name = stateFileName(repo, branch, stamp, counts);
    var memory = stateRemembered(remembered);
    // The owner's comparison lines (answers 1fcb4bd and 9602cb5): one short line per stamp pair,
    // note then task, with hashes in place of the long stamps. The pair compares first, so a
    // quiet tick shows its two lines before the no-op. A backward stamp still refuses the plain
    // write and the newer local file stays (answer a898024). A forced save keeps no refusal, so
    // it announces the update instead: the menu entry takes the state as it stands.
    var held = [];
    var keys = ["note", "task"];
    var index;
    for (index = 0; index < keys.length; index += 1) {
      var key = keys[index];
      var was = memory[key];
      var now = pair && pair[key] ? String(pair[key]) : "";
      if (!was || !now) continue;
      if (force) {
        logEvent(
          "state",
          "updating " + key + " stamp from " + stampHash(was) + " to " + stampHash(now),
        );
        continue;
      }
      var verdict = now < was ? "older" : now === was ? "same" : "forward";
      if (verdict === "older") held.push(key);
      logEvent("state", key + " - " + verdict + " - " + stampHash(now) + " vs " + stampHash(was));
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

  // A remembered file belongs to the scope that chose it. The name carries the scope, so a handle
  // whose name lies outside the current scope is refused and the owner is asked again. Without
  // this guard a reused handle wrote one repo's state into another repo's backup.
  function handleMatchesScope(handle, repo, branch) {
    if (!handle || !handle.name) return false;
    var scope = stateScopeKey(repo, branch);
    var name = String(handle.name);
    if (name.slice(-7) === ".ndjson") name = name.slice(0, -7);
    return name === scope || name.indexOf(scope + "-") === 0;
  }

  function stateDelivery(plan, hasHandle, hasPicker) {
    if (plan.kind !== "download") return plan.kind;
    if (hasHandle) return "write";
    return hasPicker ? "pick" : "download";
  }

  // With no file set, an automatic tick blocks: a stamped download lands instead of the owner's
  // file and fills the downloads folder. A save that waited on the network
  // cannot open the picker either: the browser needs the press itself, and the wait spends it.
  // That route asks for the choose entry, which runs on the press. A manual press keeps the
  // download where no picker exists.
  function stateAction(route, manual) {
    if (!manual) return route === "pick" || route === "download" ? "block" : route;
    return route === "pick" ? "hint" : route;
  }

  // The owner's line shapes (answers 1fcb4bd and 9602cb5): the fetch on a write, the no-op on a
  // quiet tick, and short stamp hashes in place of the long stamps.
  function getLine(status, base) {
    return "GET " + status + " " + base;
  }

  // The refused read names its own route, so the copy-state failure reads as a GET (answer 2f6b5a7).
  function copyLine(status, base) {
    return getLine(status, base + "/api/copy-state");
  }

  function noopLine(repo, base) {
    return "NOOP " + repo + " " + base;
  }

  function writeLine(repo, name) {
    return "WRITE " + repo + " state to " + name;
  }

  // A failed write and a failed manager download name the error that stopped them, so the
  // console line and the page card read the same words.
  function writeFailLine(err) {
    return (
      "write failed (" + ((err && err.name) || "unknown") +
      "); press the choose entry for the file again"
    );
  }

  function managerFailLine(err) {
    return "manager download failed (" + ((err && err.error) || "unknown") + "); using the link";
  }

  function stampHash(value) {
    var text = String(value || "");
    if (!text) return "none";
    var hash = 2166136261;
    var i;
    for (i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return ("0000000" + (hash >>> 0).toString(16)).slice(-7);
  }

  // The owner's line texts for the save path (answer 5ca4f63): the no-file hint names the dialog
  // it launches, a stale state reads as a history mismatch, and a closed picker reads as a plain
  // no-file line.
  var STATE_LINES = {
    hint: "no file selected; launching dialog",
    history: "history does not match",
    pickerClosed: "no file selected;",
    noPreview: "no preview detected",
  };

  function writtenName(handle, fallback) {
    return handle && handle.name ? handle.name : fallback;
  }

  var STATE_WATCH_MS = 60 * 1000;


  var STATE_SLUG_KEY = "clankers-arena-agent-slug";

  var STATE_TITLE_RE = /^Arena \| (\S+)/;

  function titleRepo(doc) {
    var match = STATE_TITLE_RE.exec(String((doc && doc.title) || ""));
    return match ? match[1] : "";
  }

  function savedSlug() {
    try {
      return String(sessionStorage.getItem(STATE_SLUG_KEY) || "").trim();
    } catch (err) {
      return "";
    }
  }

  // The Arena UI moves the GitHub integration around, so the repo/branch span can vanish;
  // the conversation header still opens with the repository name, and its first word is the
  // repository. Read that before falling back to the tab title.
  function headerRepo(doc) {
    if (!doc || typeof doc.querySelectorAll !== "function") return "";
    var spans = doc.querySelectorAll('button[aria-haspopup="menu"] span.truncate');
    for (var i = 0; i < spans.length; i += 1) {
      var first = String(spans[i].textContent || "").trim().split(/\s+/)[0];
      if (/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(first)) return first;
    }
    return "";
  }

  function stateRepo(doc) {
    var bar = doc.querySelector(BAR_SELECTOR);
    if (!bar) return savedSlug() || headerRepo(doc) || titleRepo(doc);
    var spans = bar.querySelectorAll("span.truncate");
    var i;
    for (i = 0; i < spans.length; i += 1) {
      var text = String(spans[i].textContent || "").trim();
      var slash = text.indexOf("/");
      if (slash > 0 && slash < text.length - 1) {
        var repo = text.slice(slash + 1);
        if (repo.indexOf("/") === -1 && !/\s/.test(text)) return repo;
      }
    }
    return savedSlug() || headerRepo(doc) || titleRepo(doc);
  }

  function stateBranch(doc) {
    var bar = doc.querySelector(BAR_SELECTOR);
    if (!bar) return "";
    var links = bar.querySelectorAll("a");
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

  // The state leaves through the owner's browser: one picked file, written only when the stamp moves.
  runFeature("state-download", "State — download", function () {
    if (exposeChecks("stateDownload", {
      STATE_LINES: STATE_LINES,
      copyLine: copyLine,
      stampHash: stampHash,
      getLine: getLine,
      noopLine: noopLine,
      writeLine: writeLine,
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
      stateScope: stateScope,
      stateRepo: stateRepo,
      pagePicker: pagePicker,
      downloadRoute: downloadRoute,
      stateDownloadRoute: stateDownloadRoute,
      STATE_WATCH_MS: STATE_WATCH_MS,
    })) {
      return function () {};
    }

    var STATE_DB = "clankers-arena-state";
    var STATE_HINT_KEY = "clankers-arena-state-hinted";
    // One stamp memory and one chosen file per repo and branch, so two tabs of two
    // sessions never share either.
    function stampKey(scopeKey) {
      return "clankers-arena-state-stamp-" + scopeKey;
    }
    function fileKey(scopeKey) {
      return "state-file-" + scopeKey;
    }
    var staleWarned = false;
    var picked = null;
    var pickedKey = null;
    var frameLogged = false;

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

    // A save problem the console hides becomes a small card in the page corner. The checks
    // run without a DOM, so the card is skipped there.
    var STATE_PANEL_ID = "clankers-state-panel";
    var STATE_PANEL_MS = 6000;

    // The card appears on a manual press whatever the flag says, and once a period while
    // no file is set: the owner needs the nudge, not a nag on every watch tick.
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
          "position:fixed;right:16px;bottom:16px;z-index:2147483647;max-width:320px;" +
          "padding:12px 14px;border-radius:10px;background:#1f2430;color:#f2f4f8;" +
          "font:13px/1.45 system-ui,-apple-system,sans-serif;" +
          "box-shadow:0 6px 24px rgba(0,0,0,.35);border:1px solid #3a4152";
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
            "cursor:pointer;border:0;border-radius:6px;padding:5px 10px;" +
            "background:#4f7cff;color:#fff;font:inherit";
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
          "cursor:pointer;border:1px solid #3a4152;border-radius:6px;padding:5px 10px;" +
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

    // A failed read or write reaches the page as well as the console. The card carries the
    // same line, and it stays until a dismiss. The checks run without a
    // DOM, where the card is skipped.
    function stateError(line, actionLabel, action) {
      logEvent("state", line);
      statePanel(line, actionLabel, action);
    }

    function hintStateFile(manual) {
      var shown = GM_getValue(STATE_HINT_KEY, false);
      if (!shown) {
        GM_setValue(STATE_HINT_KEY, true);
        logEvent("state", STATE_LINES.hint);
      }
      if (panelNeeded(manual, shown)) {
        statePanel(
          "No save file is set, so state saves are blocked.",
          "Choose file",
          chooseStateFile
        );
      }
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
        logEvent("state", "link download: " + name);
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
          logEvent("state", "manager download saved: " + name);
          URL.revokeObjectURL(url);
        },
        onerror: function (err) {
          stateError(managerFailLine(err));
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
        if (!frameLogged) {
          frameLogged = true;
          logEvent("state", STATE_LINES.noPreview);
        }
        return;
      }
      getJson(base + "/api/copy-state", function (status, body) {
        if (status !== 200 || !body) {
          stateError(copyLine(status, base));
          return;
        }
        var scope = stateScope(document);
        var storeKey = stateScopeKey(scope.repo, scope.branch);
        var memory = stateRemembered(GM_getValue(stampKey(storeKey), ""));
        if (force) {
          logEvent("state", "forced save");
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
          if (!staleWarned) {
            staleWarned = true;
            stateError(STATE_LINES.history);
          }
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
            );
            handle = null;
          }
          picked = handle || null;
          pickedKey = handle ? storeKey : null;
          var action = stateAction(stateDelivery(plan, Boolean(handle), hasPicker), manual);
          if (action === "unchanged") {
            if (manual) logEvent("state", "no write: " + plan.kind);
            else logEvent("state", noopLine(scope.repo, base));
            return;
          }
          if (action === "error") {
            if (manual) logEvent("state", "no write: " + plan.kind);
            return;
          }
          if (action === "block") {
            // The card is the alert (answer 5ca4f63), so the blocked tick needs no line.
            hintStateFile(manual);
            return;
          }
          if (action === "hint") {
            hintStateFile(manual);
            // The picker needs the press itself: this save waited, so the gesture is spent.
            logEvent("state", "no picker from a deferred save; press the choose entry");
            return;
          }
          if (action === "write") {
            logEvent("state", getLine(status, base));
            writeToHandle(handle, body.text).then(
              function () {
                GM_setValue(
                  stampKey(storeKey),
                  JSON.stringify(stateMemory(body.stamp, body.stamps)),
                );
                logEvent("state", writeLine(scope.repo, writtenName(handle, plan.name)));
                if (force) {
                  statePanel("Force save wrote " + writtenName(handle, plan.name) + ".", null, null, true);
                }
              },
              function (err) {
                picked = null;
                pickedKey = null;
                // The write ran after the press, so the picker would refuse a spent gesture;
                // the card carries the choose action instead.
                hintStateFile(true);
                stateError(writeFailLine(err), "Choose file", chooseStateFile);
              },
            );
            return;
          }
          // Only a manual press reaches here, and only where the browser offers no picker.
          logEvent("state", "stamped download: " + plan.name);
          if (force) {
            statePanel("Force save downloaded " + plan.name + ".", null, null, true);
          }
          writeStateDownload(body.text, plan.name);
          GM_setValue(stampKey(storeKey), JSON.stringify(stateMemory(body.stamp, body.stamps)));
        });
      });
    }

    function chooseStateFile() {
      var pick = pagePicker();
      if (!pick) {
        stateError("this browser cannot write files; the stamped download is used");
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
            // A file is set, so the next unconfigured period may speak again.
            GM_setValue(STATE_HINT_KEY, false);
            removeStatePanel();
            fetchStateFile(true);
          });
        })
        .catch(function () {
          logEvent("state", STATE_LINES.pickerClosed);
        });
    }

    var menus = [];
    menuItem(menus, "State — choose the file", chooseStateFile);
    // A forced save writes whatever the state holds and moves the reference to it.
    menuItem(menus, "State — force save", function () {
      fetchStateFile(true, true);
    });

    fetchStateFile(false);
    // The watch asks the preview over HTTP, so it scatters like the proxy timers.
    var stopStateWatch = jitteredTimer(function () {
      fetchStateFile(false);
    }, STATE_WATCH_MS, HTTP_JITTER_MS);
    return function () {
      stopStateWatch();
      menus.forEach(menuDrop);
      menus = [];
    };
  });

    // The title mirrors the arena state: repo, poll, bubble, hourglass and shield.
  runFeature("tab-title", "Page — tab title", function () {

    var REPO_LINK_SELECTOR = 'a[aria-label^="Open "][aria-label$=" on GitHub"]';
    var MESSAGE_SELECTOR = "[data-agent-transcript-message]";
    var LIVE_ICON_SELECTOR = ".animate-pulse";
    var LIVE_LABEL_SELECTOR = 'p[style*="text-shimmer"]';
    var GROUP_LABEL_SELECTOR = "span.text-text-secondary";
    // The answered question card wears the Summary header, and its chosen answer
    // row raises no mark.
    var SUMMARY_LABEL = "Summary";
    var TITLE_PREFIX = "Arena | ";
    // The name carries the running version, the way the owner reads it: Arena | repo | v1.10.x.
    var VERSION = "1.10.16";
    // One constant for the bash mark: the start-process card takes the very emoji a bash call
    // takes.
    // One mark for the agent's words: a message that grows holds the title with the solid
    // speech balloon, whatever the turn state. The outline
    // bubble that stood for the streaming state is folded into it.
    var AGENT_EMOJI = "\uD83D\uDCAC";
    var BASH_EMOJI = "\uD83D\uDDA5\uFE0F";
    var PLAY_SELECTOR = "svg.lucide-play";
    var ACTION_EMOJI = [
      ["running", BASH_EMOJI],
      ["bash", BASH_EMOJI],
      ["command", BASH_EMOJI],
      ["read", "\uD83D\uDCD6"],
      ["explor", "\uD83D\uDCD6"],
      ["edit", "\u270F\uFE0F"],
      // Writ covers write, writing, writes and written; the owner's Writing row fell to the gear.
      ["writ", "\u270F\uFE0F"],
      ["search", "\uD83D\uDD0D"],
      // Fetch covers fetch, fetching and fetched: a web page read is a search, and the owner's
      // Fetching row fell to the gear without it.
      ["fetch", "\uD83D\uDD0D"],
      ["think", "\uD83D\uDCAD"],
      ["thought", "\uD83D\uDCAD"],
      ["wait", "\uD83D\uDCA4"],
      // The owner's pick for the process output row: the scroll reads as the log roll.
      ["process_output", "\uD83D\uDCDC"],
    ];
    var ACTION_FALLBACK = "\u2699\uFE0F";
    var EMOJI_HOLD_MS = 5000;
    var heldEmoji = null;
    var heldEmojiAt = 0;
    // Whether the held mark came from a row, the words or the waiting line: those marks end
    // with the stop control, so the hold must not outlive it.
    var heldEmojiNeedsTurn = false;
    var lastSpeechMark = null;
    var lastSpeechPath = null;
    var WAITING_EMOJI = "\uD83D\uDCA4";
    var WAITING_SELECTOR = 'canvas[width="16"][height="16"]';
    var WAITING_TEXT_SELECTOR = 'span[class*="whitespace-pre"]';
    var HOURGLASS_EMOJI = "\u23F3";
    var CAPTCHA_EMOJI = "\uD83D\uDEE1\uFE0F";
    var SPEECH_SELECTOR = "[data-agent-word]";
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

    function collapsed(node) {
      return node ? String(node.textContent || "").replace(/\s+/g, " ").trim() : "";
    }

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

    // The newest row of the newest message owns the mark: a finished row keeps
    // its shimmer label and its pulse in the page, so an older row that still
    // glows is history once a newer row lands, and never holds the title.
    function newestRow(doc) {
      var messages = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(MESSAGE_SELECTOR) : [];
      var newest = messages.length ? messages[messages.length - 1] : null;
      if (!newest || typeof newest.querySelectorAll !== "function") {
        return null;
      }
      // A live row streams under its shimmer label before a group label lands, so
      // the shimmer counts as a label too; without it the mark freezes on the last
      // labelled row. A pulsing label under done rows is news the same way, so the
      // pulse counts too; without it a live edit under older done rows never matches.
      var groups = newest.querySelectorAll(GROUP_LABEL_SELECTOR + ", " + LIVE_LABEL_SELECTOR + ", " + LIVE_ICON_SELECTOR);
      return groups.length ? rowFromLabel(groups[groups.length - 1]) : null;
    }

    function rowIsNewest(doc, row) {
      var messages = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(MESSAGE_SELECTOR) : [];
      var newestMessage = messages.length ? messages[messages.length - 1] : null;
      // A row in an older message never marks: an empty newest message used to read as
      // no newest row, and a stale row took the title back.
      if (newestMessage && typeof newestMessage.contains === "function" && !newestMessage.contains(row)) {
        return false;
      }
      var newest = newestRow(doc);
      return !newest || newest === row;
    }

    function strongRow(doc) {
      var labels = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(LIVE_LABEL_SELECTOR) : [];
      var label = labels.length ? labels[labels.length - 1] : null;
      var row = rowFromLabel(label);
      // Only a mapped label outranks the waiting line; an unmapped one falls to the gear
      // pass after the hourglass has had its say.
      if (row && knownLabel(collapsed(label)) && rowIsNewest(doc, row)) {
        return row;
      }
      var messages = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(MESSAGE_SELECTOR) : [];
      var i;
      var icons;
      for (i = messages.length - 1; i >= 0; i -= 1) {
        icons = typeof messages[i].querySelectorAll === "function" ? messages[i].querySelectorAll(LIVE_ICON_SELECTOR) : [];
        row = rowFromIcon(icons.length ? icons[icons.length - 1] : null);
        if (row && knownLabel(liveLabel(row)) && rowIsNewest(doc, row)) {
          return row;
        }
      }
      icons = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(LIVE_ICON_SELECTOR) : [];
      row = rowFromIcon(icons.length ? icons[icons.length - 1] : null);
      return row && knownLabel(liveLabel(row)) && rowIsNewest(doc, row) ? row : null;
    }

    // A row inside the answered question card raises no mark; the Summary header
    // is the card's mark in the page, so the tab stays clean of a fallback.
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

    function liveRow(doc) {
      var row = strongRow(doc);
      if (row) {
        return row;
      }
      var messages = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(MESSAGE_SELECTOR) : [];
      var lastMessage = messages.length ? messages[messages.length - 1] : null;
      var groups =
        lastMessage && typeof lastMessage.querySelectorAll === "function"
          ? lastMessage.querySelectorAll(GROUP_LABEL_SELECTOR)
          : [];
      row = rowFromLabel(groups.length ? groups[groups.length - 1] : null);
      if (row && summaryCard(row)) {
        return null;
      }
      if (row && stopSignal(doc) && (knownLabel(liveLabel(row)) || rowInMessage(doc, row))) {
        return row;
      }
      // The gear pass: the newest labelled row inside a transcript message still marks when
      // no word maps it, so rows like Agent chat earn the fallback instead of nothing.
      var gearLabels = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(LIVE_LABEL_SELECTOR) : [];
      if (!gearLabels.length) {
        gearLabels = [];
        var gearMessages = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(MESSAGE_SELECTOR) : [];
        var j;
        for (j = 0; j < gearMessages.length; j += 1) {
          if (typeof gearMessages[j].querySelectorAll === "function") {
            gearLabels = gearLabels.concat(
              Array.prototype.slice.call(gearMessages[j].querySelectorAll(LIVE_LABEL_SELECTOR)),
            );
          }
        }
      }
      row = rowFromLabel(gearLabels.length ? gearLabels[gearLabels.length - 1] : null);
      return row && liveLabel(row) && rowIsNewest(doc, row) && rowInMessage(doc, row) ? row : null;
    }

    // A started process card: a play icon in the newest message. It runs
    // with no stop control of its own, so the card alone is the news while the turn runs. A
    // finished card keeps its play icon in the page, so an older card never marks, and the
    // turn's stop control bounds the card like every other row.
    function processRow(doc) {
      if (!doc || typeof doc.querySelectorAll !== "function" || !stopSignal(doc)) {
        return null;
      }
      var messages = doc.querySelectorAll(MESSAGE_SELECTOR);
      var newest = messages.length ? messages[messages.length - 1] : null;
      if (!newest || typeof newest.querySelectorAll !== "function") {
        return null;
      }
      var icons = newest.querySelectorAll(PLAY_SELECTOR);
      var card = icons.length ? rowFromIcon(icons[icons.length - 1]) : null;
      // The card is news only while it is the newest row of the message: a later
      // row of any kind takes the title back from the start-process card.
      if (card && !rowIsNewest(doc, card)) {
        return null;
      }
      // A spoken word after the card is newer still: the message keeps speaking,
      // and its words outrank the card that opened it.
      if (card && speechFollows(newest, card)) {
        return null;
      }
      return card;
    }

    function speechFollows(message, card) {
      var words = typeof message.querySelectorAll === "function" ? message.querySelectorAll(SPEECH_SELECTOR) : [];
      var i;
      for (i = 0; i < words.length; i += 1) {
        // DOCUMENT_POSITION_PRECEDING: the card sits before this word in the page.
        if (typeof words[i].compareDocumentPosition === "function" && words[i].compareDocumentPosition(card) & 2) {
          return true;
        }
      }
      return false;
    }

    function rowInMessage(doc, row) {
      var messages = typeof doc.querySelectorAll === "function" ? doc.querySelectorAll(MESSAGE_SELECTOR) : [];
      var i;
      for (i = 0; i < messages.length; i += 1) {
        if (typeof messages[i].contains === "function" && messages[i].contains(row)) {
          return true;
        }
      }
      return false;
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

    function rowSource(row) {
      var label = liveLabel(row);
      var text = String(label || "").replace(/\s+/g, " ").trim().slice(0, 40);
      if (POLL_RE.test(rowCommand(row).toLowerCase())) {
        return "poll command" + (text ? " (" + text + ")" : "");
      }
      return "action row" + (text ? " (" + text + ")" : "");
    }

    function emojiForRow(row) {
      if (!row) {
        return null;
      }
      if (POLL_RE.test(rowCommand(row).toLowerCase())) {
        return WAITING_EMOJI;
      }
      // The start-process card wears a play icon and the process name, so it reads as the
      // bash call it starts.
      if (typeof row.querySelector === "function" && row.querySelector(PLAY_SELECTOR)) {
        return BASH_EMOJI;
      }
      return actionEmoji(liveLabel(row));
    }

    function currentPath() {
      return typeof location !== "undefined" ? String(location.pathname || "") : "";
    }

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

    // The agent's words grow: the newest data-agent-word message takes one more word. One
    // predicate covers every turn state, so a single message never
    // raises a second mark. The first look only sets the mark, so a page load or a chat
    // switch stays quiet; the count rides the mark, so appended words count as growth.
    function speechGrowth(doc) {
      if (!doc || typeof doc.querySelectorAll !== "function") {
        return false;
      }
      var words = doc.querySelectorAll(SPEECH_SELECTOR);
      if (!words.length) {
        lastSpeechMark = null;
        lastSpeechPath = null;
        return false;
      }
      var last = words[words.length - 1];
      var mark = words.length + ":" + String(last.textContent || "");
      var path = currentPath();
      // A chat switch swaps the whole transcript; its own path is not a message.
      var live = lastSpeechMark !== null && mark !== lastSpeechMark && path === lastSpeechPath;
      lastSpeechMark = mark;
      lastSpeechPath = path;
      return live;
    }

    // The waiting line is a spinner canvas beside the rotating monospace text. An action row
    // carries the very same canvas as its own icon, so the canvas alone proves
    // nothing: the row must hold the text block too, beside the icon.
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
        var j;
        for (j = 0; j < spans.length; j += 1) {
          if (collapsed(spans[j])) return true;
        }
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
      titleRowSource = null;
      if (captchaSignal(doc)) {
        titleReason = "security check";
        heldEmoji = CAPTCHA_EMOJI;
        heldEmojiAt = Date.now();
        heldEmojiNeedsTurn = false;
        return CAPTCHA_EMOJI;
      }
      if (questionSignal(doc)) {
        titleReason = "question card";
        heldEmoji = QUESTION_EMOJI;
        heldEmojiAt = Date.now();
        heldEmojiNeedsTurn = false;
        return QUESTION_EMOJI;
      }
      // A finished row keeps its shimmer label or its pulsing icon in the page, so the row
      // is news only while the stop control is up.
      var live = stopSignal(doc);
      var speaking = speechGrowth(doc);
      var speechHold =
        live && heldEmoji === AGENT_EMOJI && Date.now() - heldEmojiAt < EMOJI_HOLD_MS;
      var needsTurn = false;
      var row = null;
      var emoji = null;
      // A growing message outranks its own rows, but the hold after it does not:
      // an action row that appears during the quiet gap takes the title.
      if (speaking) {
        titleReason = "agent message";
        heldEmoji = AGENT_EMOJI;
        heldEmojiAt = Date.now();
        heldEmojiNeedsTurn = false;
        return AGENT_EMOJI;
      }
      row = live ? strongRow(doc) : null;
      emoji = live ? emojiForRow(row) : null;
      if (emoji) {
        titleReason = rowSource(row);
        titleRowSource = titleReason;
        needsTurn = true;
      }
      if (!emoji) {
        row = processRow(doc);
        emoji = emojiForRow(row);
        if (emoji) {
          titleReason = rowSource(row);
          titleRowSource = titleReason;
          needsTurn = true;
        }
      }
      if (!emoji && live && waitingSignal(doc)) {
        emoji = HOURGLASS_EMOJI;
        titleReason = "waiting line";
        needsTurn = true;
      }
      if (!emoji) {
        row = live ? liveRow(doc) : null;
        emoji = live ? emojiForRow(row) : null;
        if (emoji) {
          titleReason = rowSource(row);
          titleRowSource = titleReason;
          needsTurn = true;
        }
      }
      if (!emoji && speechHold) {
        emoji = AGENT_EMOJI;
        titleReason = "agent message";
      }
      if (emoji) {
        heldEmoji = emoji;
        heldEmojiAt = Date.now();
        heldEmojiNeedsTurn = needsTurn;
        return emoji;
      }
      // The hold bridges the gaps inside a turn; a hold taken from a turn mark ends with the
      // stop control, so a vanished button clears the title at once.
      if (
        heldEmoji &&
        Date.now() - heldEmojiAt < EMOJI_HOLD_MS &&
        (!heldEmojiNeedsTurn || live)
      ) {
        titleReason = "hold";
        return heldEmoji;
      }
      heldEmoji = null;
      heldEmojiNeedsTurn = false;
      titleReason = null;
      titleRowSource = null;
      return null;
    }

    function desiredTitle(doc) {
      var name = repoForTitle(doc);
      if (!name) {
        return null;
      }
      var emoji = heldEmojiFor(doc);
      var base = TITLE_PREFIX + name;
      return emoji ? base + " " + emoji : base;
    }

    var appliedTitle = null;
    var priorTitle = null;
    var titleReason = null;
    // The row behind the reason, snapshotted with it: the anchor logs the same row the
    // mark came from, not whatever the page re-derives at write time.
    var titleRowSource = null;
    var lastRepo = null;
    var lastPath = null;

    function titleAnchors(doc) {
      // A row mark snapshots its row at selection; a re-derived row can be another one
      // by write time, so the line cites the snapshot.
      var rowText = titleRowSource;
      if (!rowText) {
        var row = strongRow(doc) || processRow(doc) || liveRow(doc);
        rowText = row ? rowSource(row) : "none";
      }
      return "repo=" + (repoForTitle(doc) || "none") + " row=" + rowText;
    }

    function syncTitle(doc) {
      var desired = desiredTitle(doc);
      if (desired) {
        // Only a change writes a line (answer e8fc4f6); a title already in place stays quiet.
        if (doc.title === desired) return false;
        logEvent(
          "title",
          (titleReason || "title") + " -> " + desired,
          titleAnchors(doc),
        );
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
      strongRow: strongRow,
      processRow: processRow,
      stopSignal: stopSignal,
      BASH_EMOJI: BASH_EMOJI,
      PLAY_SELECTOR: PLAY_SELECTOR,
      speechGrowth: speechGrowth,
      AGENT_EMOJI: AGENT_EMOJI,
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
      REPO_LINK_SELECTOR: REPO_LINK_SELECTOR,
      SPEECH_SELECTOR: SPEECH_SELECTOR,
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
      rowSource: rowSource,
      expireHold: function () { heldEmojiAt = Date.now() - EMOJI_HOLD_MS - 1; },
      resetSpeech: function () {
        lastSpeechMark = null;
        lastSpeechPath = null;
      },
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
    // The owner sets the tick in seconds; the bounds hold it between one second and a minute.
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
      lastSpeechMark = null;
      lastSpeechPath = null;
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
      if (appliedTitle && document.title === appliedTitle) {
        document.title = priorTitle;
      }
      appliedTitle = null;
    };
  });

  // The pause entry registers once, after every feature has offered its stop closure, and the
  // list opens last so every entry lands in its module group.
  exposeChecks("pause", { PAUSE_KEY: PAUSE_KEY, pauseLabel: pauseLabel });
  exposeChecks("menus", { menuRank: menuRank, MENU_ORDER: MENU_ORDER });
  exposeChecks("timers", { jitteredTimer: jitteredTimer, HTTP_JITTER_MS: HTTP_JITTER_MS });
  showPauseMenu();
  menuOpen();

})();
