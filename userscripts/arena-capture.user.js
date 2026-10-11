// ==UserScript==
// @name         Arena.ai | DOM capture (temp)
// @namespace    https://github.com/nemoe7/clankers
// @version      1.0.0
// @description  Temp recorder for transcript DOM samples: one menu press saves arena-capture-<time>.txt
// @author       nemoe7
// @icon         https://arena.ai/favicon.ico
// @license      MIT
// @match        https://arena.ai/*
// @match        https://www.arena.ai/*
// @run-at       document-idle
// @grant        GM_download
// @grant        GM_registerMenuCommand
// @grant        GM_setClipboard
// ==/UserScript==

// A throwaway capture tool, not a feature: it watches the transcript container, so a page
// refresh that replays the agent's turns leaves one growing log behind. The log carries
// DOM text alone: a tree line per added node, with the raw outerHTML of the roots that
// matter (every chat message root and every node that holds the 16px waiting canvas).
// Structure changes record; style-only and text-only churn does not, so the log stays a
// DOM record. Nothing caps the log: save it when the page settles.

(function () {
  "use strict";

  var LOG_SELECTOR = '[role="log"]';
  var MESSAGE_SELECTOR = '[data-agent-transcript-message="true"]';
  var ROOT_SELECTOR = '[id^="chat-message-"]';
  var WAITING_SELECTOR = 'canvas[width="16"][height="16"]';
  var ATTACH_MS = 500;
  var TEXT_LIMIT = 160;

  var lines = [];
  var startedAt = Date.now();
  var recording = true;
  var seen = new WeakSet();
  var observer = null;
  var watched = null;
  var attachTimer = null;

  function mark() {
    return "[+" + ((Date.now() - startedAt) / 1000).toFixed(2) + "s]";
  }

  function stamp() {
    return new Date().toISOString().replace(/[:.]/g, "-");
  }

  function collapsed(text) {
    var value = text === undefined || text === null ? "" : String(text);
    return value.replace(/\s+/g, " ").trim();
  }

  // One line names a node: the tag, its id, its classes, then the few attributes the row
  // model reads.
  function tagLabel(node) {
    var label = node.tagName ? node.tagName.toLowerCase() : "node";
    if (node.id) label += "#" + node.id;
    if (node.classList && node.classList.length) {
      label += "." + Array.prototype.join.call(node.classList, ".");
    }
    var attrs = ["role", "aria-label", "data-agent-transcript-message", "width", "height"];
    var i;
    for (i = 0; i < attrs.length; i += 1) {
      var value = node.getAttribute ? node.getAttribute(attrs[i]) : null;
      if (value) label += "[" + attrs[i] + "=" + JSON.stringify(value) + "]";
    }
    return label;
  }

  function tree(node, depth, out) {
    var pad = new Array(depth + 1).join("  ");
    if (node.nodeType === 3) {
      var text = collapsed(node.textContent);
      if (!text) return;
      out.push(pad + '"' + (text.length > TEXT_LIMIT ? text.slice(0, TEXT_LIMIT) + "…" : text) + '"');
      return;
    }
    if (node.nodeType !== 1) return;
    out.push(pad + tagLabel(node));
    var kids = node.childNodes || [];
    var i;
    for (i = 0; i < kids.length; i += 1) {
      tree(kids[i], depth + 1, out);
    }
  }

  function isRoot(node) {
    if (!node.matches) return false;
    return (
      node.matches(ROOT_SELECTOR) ||
      node.matches(MESSAGE_SELECTOR) ||
      !!(node.querySelector && node.querySelector(WAITING_SELECTOR))
    );
  }

  function record(node) {
    if (!recording || !node || node.nodeType !== 1 || seen.has(node)) return;
    seen.add(node);
    var out = [mark() + " ADD " + tagLabel(node)];
    tree(node, 1, out);
    if (isRoot(node)) {
      out.push("  RAW outerHTML:");
      out.push(node.outerHTML);
    }
    out.push("");
    lines.push(out.join("\n"));
  }

  function forget(node) {
    if (node && node.nodeType === 1) {
      lines.push(mark() + " REMOVE " + tagLabel(node));
    }
  }

  function attach(container) {
    lines.push("== attached to " + LOG_SELECTOR + " at " + new Date().toISOString());
    var kids = container.children || [];
    var i;
    for (i = 0; i < kids.length; i += 1) {
      record(kids[i]);
    }
    if (observer) observer.disconnect();
    observer = new MutationObserver(function (records) {
      var r;
      var n;
      for (r = 0; r < records.length; r += 1) {
        for (n = 0; n < records[r].addedNodes.length; n += 1) record(records[r].addedNodes[n]);
        for (n = 0; n < records[r].removedNodes.length; n += 1) forget(records[r].removedNodes[n]);
      }
    });
    observer.observe(container, { childList: true, subtree: true });
  }

  // The app mounts the log after load and swaps it on navigation, so the watch polls for
  // the container instead of racing the first render.
  function watch() {
    var container = document.querySelector(LOG_SELECTOR);
    if (container && container !== watched) {
      watched = container;
      attach(container);
    }
    attachTimer = setTimeout(watch, ATTACH_MS);
  }

  function linkDownload(url, name) {
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1000);
  }

  function saveFile() {
    var text = lines.join("\n");
    var name = "arena-capture-" + stamp() + ".txt";
    if (typeof GM_setClipboard === "function") {
      GM_setClipboard(text, { type: "text", mimetype: "text/plain" });
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text);
    }
    var url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    if (typeof GM_download === "function") {
      GM_download({
        url: url,
        name: name,
        saveAs: false,
        onload: function () {
          URL.revokeObjectURL(url);
        },
        onerror: function () {
          linkDownload(url, name);
        },
      });
    } else {
      linkDownload(url, name);
    }
    lines.push(mark() + " SAVE " + name + ", " + text.length + " chars, clipboard holds a copy");
  }

  function menu(label, press) {
    if (typeof GM_registerMenuCommand === "function") {
      GM_registerMenuCommand(label, press);
    }
  }

  menu("DOM capture — start", function () {
    recording = true;
    lines.push(mark() + " START");
  });
  menu("DOM capture — stop", function () {
    recording = false;
    lines.push(mark() + " STOP");
  });
  menu("DOM capture — save file", saveFile);
  menu("DOM capture — clear log", function () {
    lines.length = 0;
    lines.push(mark() + " CLEAR");
  });

  lines.push(mark() + " capture loaded at " + location.href);
  watch();
})();
