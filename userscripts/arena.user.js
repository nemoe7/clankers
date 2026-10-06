// ==UserScript==
// @name         Arena.ai | NemoUtils
// @namespace    https://github.com/nemoe7/clankers
// @version      1.6.16
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

  var LOG_TAG = "[clankers]";

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

  exposeChecks("logging", { logEvent: logEvent, LOG_TAG: LOG_TAG });

  // One menu entry with one guard, so a manager without a menu gets nothing.
  function menuItem(list, label, run) {
    if (typeof GM_registerMenuCommand !== "function") return;
    list.push(GM_registerMenuCommand(label, run));
  }

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

  function runFeature(key, label, run, onChange, defaultOn) {
    if (typeof document === "undefined") {
      run();
      return;
    }
    var fallback = defaultOn !== false;
    var enabled = GM_getValue(key, fallback) !== false;
    var menuId;
    var stop = null;
    logEvent("feature", label + ": " + (enabled ? "ON" : "OFF"));

    function toggle() {
      var next = GM_getValue(key, fallback) === false;
      GM_setValue(key, next);
      logEvent("feature", label + ": " + (next ? "ON" : "OFF"));
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

    // The fill writes the initial message: the repo name leads it, the rules stay in the files.
  runFeature("prompt-fill", "Prompt fill", function () {

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
        + " skills/arena-proxy holds the map. Never print it."
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
      "\n\nRead the task and every file it touches in full. Trace the real flow end to end before you plan." +
      "\n\nReuse first, one line second, new code last. Add nothing the task does not ask for." +
      "\n\nNew behavior: red first. Write the failing check, make the smallest change that passes it," +
      " refactor without a behavior change, then recheck." +
      "\n\nFor a bug: reproduce it, change one variable at a time, fix the root cause where every" +
      " caller routes through, cover the fix with a check, then recheck." +
      "\n\nState every assumption the moment you make it. Ask one question when a wrong reading" +
      " changes the result." +
      "\n\nNEVER claim a check you did not run. Print what you skipped." +
      "\n\nExpect screenshots, notes and corrections through the steering channel. Take each one in" +
      " the next reply." +
      "\n\nStop when verification holds, and finish with what changed, what you checked, and what" +
      " is open.";

    function promptForSlug(slug) {
      return slug + " read ARENA.md AGENTS.md in full before your first edit, and follow both." + TEMPLATE_TAIL;
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

    if (exposeChecks("promptFill", {
      isComposerUrl: isComposerUrl,
      slugFromOwnerRepo: slugFromOwnerRepo,
      promptForSlug: promptForSlug,
      shouldWrite: shouldWrite,
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

    var heldKey = null;
    var keyTried = false;
    var keyFetch = null;

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

    setProxyValue(PROXY_HOST_KEY, "Arena proxy host — set", GM_getValue(PROXY_HOST_KEY, ""));
    setProxyValue(PROXY_MASTER_KEY, "Arena proxy master key — set", "");

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

    menuItem(proxyMenus, "Arena proxy rotate now — run", function () {
      rotateKey(0, null);
    });
    menuItem(proxyMenus, "Arena proxy post key now — run", function () {
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

    var rotateTimer = setInterval(function () {
      rotateKey(ROTATE_MIN_SECONDS, null);
    }, ROTATE_INTERVAL_MS);

    var keyWatchTimer = setInterval(function () {
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
    }, KEY_WATCH_MS);

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
      postKeyToPreview(false);
      if (!isComposerUrl(location.href)) {
        lastSlug = null;
        return;
      }
      var slug = readSlug(document);
      if (!slug) {
        if (!slugLogged) {
          slugLogged = true;
          logEvent("fill", "no repo slug yet");
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
      var composer = document.querySelector(COMPOSER_SELECTOR);
      if (!composer || composer.getAttribute("aria-disabled") === "true") {
        if (composerLogged !== slug) {
          composerLogged = slug;
          logEvent("fill", "no composer for " + slug);
        }
        lastSlug = slug;
        return;
      }
      composerLogged = null;
      var current = composer.innerText || "";
      if (!shouldWrite(current, slug, lastSlug, filledSlug)) {
        lastSlug = slug;
        ensureAgentKey();
        return;
      }
      setComposerText(composer, promptForSlug(slug));
      logEvent("fill", "wrote the initial message for " + slug);
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
      if (typeof clearInterval === "function") {
        clearInterval(rotateTimer);
        clearInterval(keyWatchTimer);
      }
      for (var m = 0; m < proxyMenus.length; m += 1) {
        if (typeof GM_unregisterMenuCommand === "function") {
          GM_unregisterMenuCommand(proxyMenus[m]);
        }
      }
    };
  });

    // The Steering row drifts on labels, so it is found by its words.
  runFeature("open-steering", "Open Steering", function () {

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

    // A trim waits for a quiet page and keeps the newest rows.
  runFeature("transcript-trim", "Transcript trim", function () {
    var KEEP_KEY = "clankers-arena-trim-keep";
    var DEFAULT_ROWS = 50;
    var MIN_ROWS = 20;
    var LOG_SELECTOR = '[role="log"]';
    var MESSAGE_SELECTOR = '[data-agent-transcript-message="true"]';
    var ROW_BOX_SELECTOR = "div.flex.flex-col.gap-2";
    var ACTION_SELECTOR = ":scope > div > div > div.mt-3.flex.flex-col.gap-3";
    var LIVE_ICON_SELECTOR = "svg.animate-pulse";
    var QUESTION_SELECTOR = '[role="radiogroup"]';
    var SETTLE_MS = 1200;

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

    function trimPlan(doc, plan) {
      var roots = messageRoots(doc);
      var rootRows = [];
      var total = 0;
      var excess;
      var removed = 0;
      var i;
      for (i = 0; i < roots.length; i += 1) {
        var live = roots[i].isConnected !== false;
        var rows = live ? rowsOfRoot(roots[i]) : [];
        var rootAttached = 0;
        var j;
        rootRows.push(rows);
        for (j = 0; j < rows.length; j += 1) {
          if (rows[j].parentElement) {
            total += 1;
            rootAttached += 1;
          }
        }
        if (live && !rows.length) removeActionSibling(roots[i]);
      }
      excess = Math.max(0, total - planParts(plan).rows);
      for (i = 0; i < roots.length && excess > 0; i += 1) {
        var attached = 0;
        var rootList = rootRows[i];
        for (j = 0; j < rootList.length; j += 1) {
          if (rootList[j].parentElement) attached += 1;
        }
        var removedFromRoot = trimRows(rootList, Math.max(1, attached - excess));
        removed += removedFromRoot;
        excess -= removedFromRoot;
        if (removedFromRoot) removeActionSibling(roots[i]);
      }
      return removed;
    }

    function isSettled(doc) {
      if (findStopGeneratingButton(doc)) return false;
      if (doc.querySelector(QUESTION_SELECTOR)) return false;
      return !doc.querySelector(LIVE_ICON_SELECTOR);
    }

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
      QUESTION_SELECTOR: QUESTION_SELECTOR,
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

    // The composer hides while a turn runs, and its spacer height returns on show.
  runFeature("hide-composer", "Hide composer", function () {

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

  function stateFileName(repo, branch, stamp, counts) {
    function part(value) {
      return String(value || "")
        .replace(/[^A-Za-z0-9._-]+/g, "-")
        .replace(/^-+|-+$/g, "");
    }
    var scope = [part(repo), part(branch)].filter(Boolean).join("-") || "arena";
    var when = String(stamp || "")
      .replace(/[-:]/g, "")
      .replace(/\..*$/, "")
      .replace(/\+.*$/, "");
    var name = "arena-state-" + scope + (when ? "-" + when : "");
    if (counts) {
      name += "-n" + (counts.notes || 0) + "-t" + (counts.tasks || 0);
    }
    return name + ".ndjson";
  }

  function stateDownload(repo, branch, stamp, counts, remembered) {
    if (!stamp) {
      return {
        kind: "error",
        message: "The state carries no stamp; the next save names it.",
      };
    }
    var name = stateFileName(repo, branch, stamp, counts);
    if (remembered && remembered === stamp) {
      return {
        kind: "unchanged",
        name: name,
        message: "State unchanged since the last write: " + name,
      };
    }
    if (remembered && String(stamp) < String(remembered)) {
      return {
        kind: "stale",
        name: name,
        message:
          "Stale preview state (" + stamp + " is older than " + remembered + "); nothing written.",
      };
    }
    return { kind: "download", name: name, message: "Wrote " + name };
  }

  function stateDelivery(plan, hasHandle, hasPicker) {
    if (plan.kind !== "download") return plan.kind;
    if (hasHandle) return "write";
    return hasPicker ? "pick" : "download";
  }

  function stateAction(route, manual) {
    if (route === "pick" && !manual) return "download";
    return route;
  }

  function stateTick(name, stamp, saved) {
    return name + " stamp=" + (stamp || "none") + " saved=" + (saved || "none");
  }

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

  function stateRepo(doc) {
    var bar = doc.querySelector(BAR_SELECTOR);
    if (!bar) return savedSlug() || titleRepo(doc);
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
    return savedSlug() || titleRepo(doc);
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
  runFeature("state-download", "Preview state download", function () {
    if (exposeChecks("stateDownload", {
      stateFileName: stateFileName,
      stateDownload: stateDownload,
      stateDelivery: stateDelivery,
      stateAction: stateAction,
      stateTick: stateTick,
      writtenName: writtenName,
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
    var stampKey = "clankers-arena-state-stamp";
    var staleWarned = false;
    var picked = null;
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

    function stateHandle() {
      return stateDb()
        .then(function (db) {
          return new Promise(function (resolve) {
            var request = db
              .transaction("files")
              .objectStore("files")
              .get("state-file");
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

    function saveStateHandle(handle) {
      return stateDb()
        .then(function (db) {
          db.transaction("files", "readwrite")
            .objectStore("files")
            .put(handle, "state-file");
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

    function hintStateFile() {
      if (GM_getValue(STATE_HINT_KEY, false)) return;
      GM_setValue(STATE_HINT_KEY, true);
      logEvent("state", "no file chosen; the stamped download lands each new stamp");
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
          logEvent(
            "state",
            "manager download failed (" +
              ((err && err.error) || "unknown") +
              "); using the link",
          );
          linkDownload(url, name);
          setTimeout(function () {
            URL.revokeObjectURL(url);
          }, 1000);
        },
      });
    }

    function fetchStateFile(manual) {
      var base = previewBase(document);
      if (!base) {
        if (!frameLogged) {
          frameLogged = true;
          logEvent("state", "no preview frame yet");
        }
        return;
      }
      getJson(base + "/api/copy-state", function (status, body) {
        if (status !== 200 || !body) {
          logEvent("state", "copy-state answered HTTP " + status);
          return;
        }
        var scope = stateScope(document);
        var savedStamp = GM_getValue(stampKey, "");
        var plan = stateDownload(
          scope.repo,
          scope.branch,
          body.stamp,
          body.counts,
          savedStamp,
        );
        logEvent("state", "tick " + stateTick(plan.name, body.stamp, savedStamp));
        if (plan.kind !== "unchanged") {
          logEvent("state", plan.kind + ": " + plan.name);
        }
        if (plan.kind === "stale") {
          if (!staleWarned) {
            staleWarned = true;
            logEvent("state", "stale: " + plan.name);
          }
          return;
        }
        var hasPicker = Boolean(pagePicker());
        var ready = picked ? Promise.resolve(picked) : stateHandle();
        ready.then(function (handle) {
          picked = handle || null;
          var action = stateAction(stateDelivery(plan, Boolean(handle), hasPicker), manual);
          logEvent("state", "route " + action);
          if (action === "unchanged" || action === "error") {
            if (manual) logEvent("state", "no write: " + plan.kind);
            return;
          }
          if (action === "pick") {
            chooseStateFile();
            return;
          }
          if (action === "write") {
            writeToHandle(handle, body.text).then(
              function () {
                GM_setValue(stampKey, body.stamp);
                logEvent("state", "saved " + writtenName(handle, plan.name));
              },
              function (err) {
                picked = null;
                logEvent(
                  "state",
                  "write failed (" + ((err && err.name) || "unknown") + "), asking for the file again",
                );
                if (manual) chooseStateFile();
                else hintStateFile();
              },
            );
            return;
          }
          if (action === "download" && hasPicker && !handle) hintStateFile();
          logEvent("state", "stamped download: " + plan.name);
          writeStateDownload(body.text, plan.name);
          GM_setValue(stampKey, body.stamp);
        });
      });
    }

    function chooseStateFile() {
      var pick = pagePicker();
      if (!pick) {
        logEvent("state", "this browser cannot write files; the stamped download is used");
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
          return saveStateHandle(handle).then(function () {
            picked = handle;
            GM_setValue(stampKey, "");
            fetchStateFile(true);
          });
        })
        .catch(function (err) {
          var name = (err && err.name) || "unknown";
          var message = (err && err.message) || "";
          logEvent(
            "state",
            "picker closed without a file (" + name + (message ? ": " + message : "") + ")",
          );
        });
    }

    var menus = [];
    menuItem(menus, "Arena preview state — choose the file", chooseStateFile);
    menuItem(menus, "Arena preview state — save now", function () {
      fetchStateFile(true);
    });

    fetchStateFile(false);
    var timer = setInterval(function () {
      fetchStateFile(false);
    }, STATE_WATCH_MS);
    return function () {
      clearInterval(timer);
      if (typeof GM_unregisterMenuCommand === "function") {
        menus.forEach(function (id) {
          GM_unregisterMenuCommand(id);
        });
      }
      menus = [];
    };
  });

    // The title mirrors the arena state: repo, poll, bubble, hourglass and shield.
  runFeature("tab-title", "Tab title", function () {

    var REPO_LINK_SELECTOR = 'a[aria-label^="Open "][aria-label$=" on GitHub"]';
    var MESSAGE_SELECTOR = "[data-agent-transcript-message]";
    var LIVE_ICON_SELECTOR = ".animate-pulse";
    var LIVE_LABEL_SELECTOR = 'p[style*="text-shimmer"]';
    var GROUP_LABEL_SELECTOR = "span.text-text-secondary";
    var TITLE_PREFIX = "Arena | ";
    var ACTION_EMOJI = [
      ["running", "\uD83D\uDDA5\uFE0F"],
      ["bash", "\uD83D\uDDA5\uFE0F"],
      ["command", "\uD83D\uDDA5\uFE0F"],
      ["read", "\uD83D\uDCD6"],
      ["explor", "\uD83D\uDCD6"],
      ["edit", "\u270F\uFE0F"],
      ["write", "\u270F\uFE0F"],
      ["search", "\uD83D\uDD0D"],
      ["think", "\uD83D\uDCAD"],
      ["thought", "\uD83D\uDCAD"],
      ["wait", "\uD83D\uDCA4"],
    ];
    var ACTION_FALLBACK = "\u2699\uFE0F";
    var EMOJI_HOLD_MS = 5000;
    var heldEmoji = null;
    var heldEmojiAt = 0;
    var lastSpeechMark = null;
    var WAITING_EMOJI = "\uD83D\uDCA4";
    var WAITING_SELECTOR =
      'canvas[width="16"][height="16"], [aria-hidden="true"][class*="min-w-[3ch]"]';
    var HOURGLASS_EMOJI = "\u23F3";
    var CAPTCHA_SELECTOR = '.recaptcha-v2-container, iframe[title="reCAPTCHA"]';
    var CAPTCHA_EMOJI = "\uD83D\uDEE1\uFE0F";
    var SPEECH_SELECTOR = "[data-agent-word]";
    var SPEECH_EMOJI = "\uD83D\uDDE8\uFE0F";
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

    function strongRow(doc) {
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
      return row && knownLabel(liveLabel(row)) && stopSignal(doc) ? row : null;
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

    function speechLive(doc) {
      if (typeof doc.querySelectorAll !== "function") {
        return false;
      }
      var words = doc.querySelectorAll(SPEECH_SELECTOR);
      if (!words.length) {
        lastSpeechMark = null;
        return false;
      }
      var last = words[words.length - 1];
      var mark = words.length + ":" + String(last.textContent || "");
      var live = mark !== lastSpeechMark;
      lastSpeechMark = mark;
      return live;
    }

    function waitingSignal(doc) {
      if (!doc || typeof doc.querySelectorAll !== "function") {
        return false;
      }
      return doc.querySelectorAll(WAITING_SELECTOR).length > 0;
    }

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

    function heldEmojiFor(doc) {
      if (captchaSignal(doc)) {
        titleReason = "security check";
        heldEmoji = CAPTCHA_EMOJI;
        heldEmojiAt = Date.now();
        return CAPTCHA_EMOJI;
      }
      var row = strongRow(doc);
      var emoji = emojiForRow(row);
      if (emoji) {
        titleReason = rowSource(row);
      }
      if (!emoji && stopSignal(doc) && speechLive(doc)) {
        emoji = SPEECH_EMOJI;
        titleReason = "streaming words";
      }
      if (!emoji && waitingSignal(doc)) {
        emoji = HOURGLASS_EMOJI;
        titleReason = "waiting line";
      }
      if (!emoji) {
        row = liveRow(doc);
        emoji = emojiForRow(row);
        if (emoji) {
          titleReason = rowSource(row);
        }
      }
      if (emoji) {
        heldEmoji = emoji;
        heldEmojiAt = Date.now();
        return emoji;
      }
      if (heldEmoji && Date.now() - heldEmojiAt < EMOJI_HOLD_MS) {
        titleReason = "hold";
        return heldEmoji;
      }
      heldEmoji = null;
      titleReason = null;
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
    var titleReason = null;
    var lastRepo = null;
    var lastPath = null;

    function titleAnchors(doc) {
      var row = strongRow(doc) || liveRow(doc);
      return (
        "repo=" +
        (repoForTitle(doc) || "none") +
        " row=" +
        (row ? rowSource(row) : "none")
      );
    }

    var TITLE_LOG_MS = 1000;
    var titleLoggedAt = 0;

    function syncTitle(doc) {
      var desired = desiredTitle(doc);
      if (desired) {
        if (doc.title === desired) {
          if (Date.now() - titleLoggedAt >= TITLE_LOG_MS) {
            titleLoggedAt = Date.now();
            logEvent(
              "title",
              "unchanged " + (titleReason || "none"),
              titleAnchors(doc),
            );
          }
          return false;
        }
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
      stopSignal: stopSignal,
      speechLive: speechLive,
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
      REPO_LINK_SELECTOR: REPO_LINK_SELECTOR,
      SPEECH_SELECTOR: SPEECH_SELECTOR,
      SPEECH_EMOJI: SPEECH_EMOJI,
      WAITING_SELECTOR: WAITING_SELECTOR,
      HOURGLASS_EMOJI: HOURGLASS_EMOJI,
      CAPTCHA_SELECTOR: CAPTCHA_SELECTOR,
      CAPTCHA_EMOJI: CAPTCHA_EMOJI,
      captchaSignal: captchaSignal,
      openDialog: openDialog,
      rowSource: rowSource,
      expireHold: function () { heldEmojiAt = Date.now() - EMOJI_HOLD_MS - 1; },
      resetSpeech: function () { lastSpeechMark = null; },
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
    var titleTimer = setInterval(function () {
      if (document.documentElement !== observedRoot) {
        observeRoot();
      }
      syncTitle(document);
    }, 1000);
    function onRoute() {
      lastRepo = null;
      lastPath = null;
      lastSpeechMark = null;
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
