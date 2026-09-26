// ==UserScript==
// @name         Arena agent prompt
// @namespace    https://github.com/nemoe7/clankers
// @version      1.1.0
// @description  Fill /agent composer from the repo slug; click {repo} - Steering on /agent/*
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
  var COMPOSER_SELECTOR = 'div.tiptap.ProseMirror[contenteditable="true"]';
  var TEMPLATE_RE = /^(\S+) read AGENTS\.md ARENA\.md$/;
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

  function isComposerUrl(urlString) {
    var url = parseArenaUrl(urlString);
    return Boolean(url) && url.pathname === "/agent";
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

  function rememberSlug(slug) {
    try {
      sessionStorage.setItem(SLUG_KEY, slug);
    } catch (err) {
      return;
    }
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
      [isComposerUrl("https://arena.ai/agent"), true],
      [isComposerUrl("https://www.arena.ai/agent"), true],
      [isComposerUrl("https://arena.ai/agent?x=1"), true],
      [isComposerUrl("https://arena.ai/agent#x"), true],
      [isComposerUrl("https://arena.ai/agent/"), false],
      [isComposerUrl("https://arena.ai/agent/foo"), false],
      [isComposerUrl("https://other.example/agent"), false],
      [isSessionUrl("https://arena.ai/agent/foo"), true],
      [isSessionUrl("https://www.arena.ai/agent/foo/bar"), true],
      [isSessionUrl("https://arena.ai/agent/foo?x=1"), true],
      [isSessionUrl("https://arena.ai/agent"), false],
      [isSessionUrl("https://arena.ai/agent/"), false],
      [isSessionUrl("https://other.example/agent/foo"), false],
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

  var lastSlug = null;
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

  function fillComposer() {
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

  function clickSteeringOnce() {
    if (clickedPath === location.pathname) {
      return;
    }
    var slug = readSlug(document) || lastSlug || recalledSlug();
    var button = findSteeringButton(document, slug);
    if (!button) {
      return;
    }
    button.click();
    clickedPath = location.pathname;
  }

  function sync() {
    var href = location.href;
    if (isComposerUrl(href)) {
      fillComposer();
    }
    if (isSessionUrl(href)) {
      clickSteeringOnce();
    } else {
      clickedPath = null;
    }
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
