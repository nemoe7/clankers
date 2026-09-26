// ==UserScript==
// @name         Arena agent prompt
// @namespace    https://github.com/nemoe7/clankers
// @version      1.0.0
// @description  On exact /agent, fill the composer with "{repo} read AGENTS.md ARENA.md"
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

  function isTargetUrl(urlString) {
    var url;
    try {
      url = new URL(urlString);
    } catch (err) {
      return false;
    }
    var host = url.hostname.replace(/^www\./, "");
    return host === "arena.ai" && url.pathname === "/agent";
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

  function runChecks() {
    var cases = [
      [isTargetUrl("https://arena.ai/agent"), true],
      [isTargetUrl("https://www.arena.ai/agent"), true],
      [isTargetUrl("https://arena.ai/agent?x=1"), true],
      [isTargetUrl("https://arena.ai/agent#x"), true],
      [isTargetUrl("https://arena.ai/agent/"), false],
      [isTargetUrl("https://arena.ai/agent/foo"), false],
      [isTargetUrl("https://other.example/agent"), false],
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
    if (!isTargetUrl(location.href)) {
      lastSlug = null;
      return;
    }
    var slug = readSlug(document);
    if (!slug) {
      return;
    }
    var composer = document.querySelector(COMPOSER_SELECTOR);
    if (!composer || composer.getAttribute("aria-disabled") === "true") {
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
})();
