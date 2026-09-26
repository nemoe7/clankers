// ==UserScript==
// @name         Arena agent steering
// @namespace    https://github.com/nemoe7/clankers
// @version      1.0.0
// @description  On /agent/*, click {repo} - Steering on port 8000 once per page
// @author       nemoe7
// @license      MIT
// @match        https://arena.ai/*
// @match        https://www.arena.ai/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  var BAR_SELECTOR =
    "div.relative.z-10.w-full.md\\:absolute.md\\:left-0.md\\:top-full";
  var STEERING_LABEL_RE = /^(\S+) - Steering$/;
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
    button.click();
    clickedPath = location.pathname;
  }

  var observer = new MutationObserver(sync);
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    characterData: true,
  });
  window.addEventListener("popstate", sync);
  sync();
})();
