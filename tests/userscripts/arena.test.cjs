const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const { bundles, runBundle, loadChecks } = require("./fixtures/vm_harness.cjs");

runBundle("arena");

{
  const source = fs.readFileSync(path.join(__dirname, '../../userscripts/arena.user.js'), 'utf8');
  const events = new Map();
  const frames = new Map();
  const observers = [];
  const menus = new Map();
  let enabled = true;
  let serial = 0;
  const scroller = {
    scrollTop: 600, scrollHeight: 1000, clientHeight: 400, isConnected: true,
    addEventListener(name, fn) { events.set(name, fn); },
    removeEventListener(name) { events.delete(name); },
  };
  const content = { parentElement: scroller };
  let message = { parentElement: content, closest() { return scroller; } };
  const row = {
    inserted: null,
    querySelector() { return null; },
    insertBefore(node) { this.inserted = node; },
  };
  const stopButton = {
    getAttribute(name) { return name === 'aria-label' ? 'Stop generating' : null; },
    parentElement: row,
  };
  const makeElement = (tag) => ({
    tag, type: '', className: '', attrs: {}, listeners: {}, children: [],
    setAttribute(name, value) { this.attrs[name] = value; },
    appendChild(child) { this.children.push(child); },
    addEventListener(name, fn) { this.listeners[name] = fn; },
  });
  const context = {
    console, URL,
    location: { pathname: '/agent/one', href: 'https://arena.ai/agent/one' },
    document: {
      documentElement: {},
      querySelector() { return message; },
      querySelectorAll(selector) { return selector === 'button[aria-label]' ? [stopButton] : []; },
      createElement: (tag) => makeElement(tag),
      createElementNS: (namespace, tag) => makeElement(tag),
    },
    window: { addEventListener(name, fn) { events.set(name, fn); }, removeEventListener(name) { events.delete(name); } },
    getComputedStyle() { return { overflowY: 'auto' }; },
    MutationObserver: class { constructor(fn) { observers.push(fn); } observe() {} disconnect() {} },
    ResizeObserver: class { constructor(fn) { observers.push(fn); } observe() {} unobserve() {} disconnect() {} },
    requestAnimationFrame(fn) { frames.set(++serial, fn); return serial; },
    cancelAnimationFrame(id) { frames.delete(id); },
    GM_getValue(key) {
      if (key === 'clankers-arena-show-settings-button') return false;
      return key === 'auto-scroll' && enabled;
    },
    GM_registerMenuCommand(label, fn) { menus.set(label, fn); return label; },
    GM_unregisterMenuCommand(label) { menus.delete(label); },
    GM_setValue(key, value) { enabled = value; },
  };
  const flush = () => { for (const [id, fn] of [...frames]) { frames.delete(id); fn(); } };
  vm.runInNewContext(source, context);
  flush();
  const toggleButton = row.inserted;
  assert.ok(toggleButton, 'Toggle button is injected into the action row');
  assert.equal(toggleButton.attrs['aria-pressed'], 'true', 'Button starts pressed while follow is ON');
  scroller.scrollTop = 100;
  events.get('scroll')(); flush();
  assert.equal(scroller.scrollTop, 600, 'Enabled mode immediately returns to bottom');
  scroller.scrollHeight = 1600;
  observers[0](); flush();
  assert.equal(scroller.scrollTop, 1200, 'New content follows while pinned');
  scroller.scrollTop = 1100;
  events.get('scroll')();
  scroller.scrollHeight = 2000;
  observers[0](); flush();
  assert.equal(scroller.scrollTop, 1600, 'Enabled mode overrides upward scrolling');
  scroller.scrollTop = 1550;
  events.get('scroll')();
  scroller.scrollHeight = 2200;
  observers[1](); flush();
  assert.equal(scroller.scrollTop, 1800, 'Enabled mode follows resize');
  scroller.scrollHeight = 2500;
  observers[0]();
  context.location.pathname = '/agent/two';
  scroller.scrollTop = 20;
  observers[0](); flush();
  assert.equal(scroller.scrollTop, 2100, 'Enabled mode follows on navigation');
  const toggleMenu = () => [...menus].find(([label]) => label.startsWith('Transcript - auto-scroll ('))[1]();
  toggleButton.listeners.click();
  assert.equal(enabled, false, 'Button click turns follow off');
  assert.equal(toggleButton.attrs['aria-pressed'], 'false', 'Button shows unpressed when off');
  assert.ok(toggleButton.className.includes('hover:bg-surface-raised'), 'Off state lifts on hover');
  assert.ok(!toggleButton.className.includes('hover:bg-interactive-cta-active'), 'Off state keeps the plain hover');
  assert.equal(events.has('scroll'), false, 'OFF removes the scroll listener');
  scroller.scrollTop = 50; flush();
  assert.equal(scroller.scrollTop, 50, 'OFF cancels pending follow');
  toggleButton.listeners.click();
  assert.equal(enabled, true, 'Button click turns follow on');
  assert.equal(toggleButton.attrs['aria-pressed'], 'true', 'Button shows pressed when on');
  assert.ok(toggleButton.className.includes('hover:bg-interactive-cta-active'), 'On state has its own hover');
  assert.ok(!toggleButton.className.includes('hover:bg-surface-raised'), 'On state does not share the hover fill');
  flush();
  assert.equal(scroller.scrollTop, 2100, 'ON follows immediately without reload');
  toggleMenu();
  assert.equal(enabled, false, 'Menu toggle turns follow off');
  assert.equal(toggleButton.attrs['aria-pressed'], 'false', 'Menu toggle updates the button');
  toggleMenu();
  assert.equal(enabled, true, 'Menu toggle restores follow');
  assert.equal(toggleButton.attrs['aria-pressed'], 'true', 'Button follows the menu toggle back on');
  const latestSync = observers.at(-2);
  let generating = true;
  context.document.querySelectorAll = (selector) => selector === 'button[aria-label]' && generating ? [stopButton] : [];
  generating = false;
  scroller.scrollTop = 40;
  events.get('scroll')(); flush();
  assert.equal(scroller.scrollTop, 40, 'Idle transcript (no Stop generating) leaves the scroll alone');
  generating = true;
  latestSync(); flush();
  assert.equal(scroller.scrollTop, 2100, 'Stop generating back means follow resumes');
  message = null;
  latestSync(); flush();
  assert.equal(events.has('scroll'), false, 'Removed transcript releases its listener');
  console.log('ok auto-scroll: growth, resize, navigation, toggle button, menu sync, cleanup');
}

{
  const { test } = require("node:test");
// The tab title reads the last message root: the newest row's type carries the mark.
// A user root carries none, and every row mark ends with the stop control.
  test("tab title row mark", async () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const page = { title: "" };
    const titleMenus = new Map();
    const logged = [];
    const intervals = [];
    const timeouts = new Map();
    let nextTimeout = 0;
    const composer = { innerText: "", attrs: {}, focus() {}, getAttribute() { return null; } };
    const bar = {
      textContent: "nemoe7/clankers",
      querySelectorAll(selector) {
        return selector === "span.truncate" ? [{ textContent: "nemoe7/clankers" }] : [];
      },
    };
    const repoLink = {
      getAttribute(name) {
        if (name === "href") return "https://github.com/nemoe7/clankers";
        if (name === "aria-label") return "Open nemoe7/clankers on GitHub";
        return null;
      },
    };
    function classOf(node, name) {
      return (" " + (node.className || "") + " ").indexOf(" " + name + " ") !== -1;
    }
    // Answer tab-title selectors like a real tree.
    function matches(node, selector) {
      if (!node || !node.attrs) return false;
      if (selector === "[data-agent-transcript-message]") return node.attrs["data-agent-transcript-message"] !== undefined;
      if (selector === "svg.lucide-play") return node.tagName === "SVG" && classOf(node, "lucide-play");
      if (selector === 'p[style*="text-shimmer"]') return String(node.attrs.style || "").indexOf("text-shimmer") !== -1;
      if (selector === ".animate-pulse") return classOf(node, "animate-pulse");
      if (selector === "span.text-text-secondary") return node.tagName === "SPAN" && classOf(node, "text-text-secondary");
      if (selector === "button") return node.tagName === "BUTTON";
      if (selector === "p") return node.tagName === "P";
      if (selector === "pre") return node.tagName === "PRE";
      if (selector === "button[aria-label]") return node.tagName === "BUTTON" && node.attrs["aria-label"] !== undefined;
      return false;
    }
    function findAll(root, selector) {
      const hits = [];
      (function walk(item) {
        (item.children || []).forEach((kid) => {
          if (matches(kid, selector)) hits.push(kid);
          walk(kid);
        });
      })(root);
      return hits;
    }
    function node(tag, className, kids) {
      const el = {
        tagName: String(tag).toUpperCase(),
        className: className || "",
        children: kids || [],
        parentElement: null,
        textContent: "",
        attrs: {},
      };
      el.getAttribute = (name) => (Object.prototype.hasOwnProperty.call(el.attrs, name) ? el.attrs[name] : null);
      el.querySelectorAll = (selector) => findAll(el, selector);
      el.querySelector = (selector) => {
        const hits = findAll(el, selector);
        return hits.length ? hits[0] : null;
      };
      Object.defineProperty(el, "firstElementChild", {
        get: () => (el.children.length ? el.children[0] : null),
      });
      el.children.forEach((kid) => { kid.parentElement = el; });
      return el;
    }
    // Session dump shapes both roots: agent root ends at row container. User root ends
    // at raised card with `prose` body three levels down.
    function agentRoot(rowList) {
      const container = node("div", "flex flex-col gap-2", rowList);
      const root = node("div", "", [
        node("div", "relative overflow-hidden bg-surface-primary rounded-xl border w-full border-transparent", [
          node("div", "px-3 pb-3", [container]),
        ]),
      ]);
      root.attrs["data-agent-transcript-message"] = "true";
      root.attrs["data-chat-message-id"] = "chat-agent";
      return root;
    }
    function userRootNode() {
      const body = node("div", "prose prose-pre:bg-transparent text-wrap break-words", []);
      const card = node(
        "div",
        "relative overflow-hidden bg-surface-raised rounded-lg w-fit max-w-[min(70%,768px)] border-transparent ms-0",
        [node("div", "px-3 text-text-primary body-base py-2", [node("div", "flex flex-col gap-2", [body])])],
      );
      const root = node("div", "", [
        node("div", "", [node("div", "group flex min-w-0 flex-col items-end gap-1", [card])]),
      ]);
      root.attrs["data-agent-transcript-message"] = "true";
      root.attrs["data-chat-message-id"] = "chat-user";
      return root;
    }
    function chatRow() {
      return node("div", "prose", []);
    }
    function labelRow(label, command) {
      const span = node("span", "text-text-secondary body-sm", []);
      span.textContent = label;
      const pre = node("pre", "", []);
      pre.textContent = command || "";
      const button = node("button", "flex w-full", [span, pre]);
      button.attrs["aria-label"] = "Collapse";
      return node("div", "", [button]);
    }
    const stopButton = {
      getAttribute: (name) => (name === "aria-label" ? "Stop generating" : null),
      // The editor-content read walks every labelled button, so the mock answers closest.
      closest: () => null,
      parentElement: null,
      querySelector: () => null,
      querySelectorAll: () => [],
    };
    let roots = [agentRoot([chatRow()])];
    let stop = true;
    const context = {
      console: Object.fromEntries(["log", "warn", "error"].map((level) => [level, (...args) => logged.push(args)])),
      URL,
      location: { href: "https://arena.ai/c/one", pathname: "/c/one" },
      document: {
        documentElement: {},
        execCommand(command, show, text) { composer.innerText = text; return true; },
        createRange() { return { selectNodeContents() {} }; },
        querySelector(selector) {
          if (selector === 'div.tiptap.ProseMirror[contenteditable="true"]') return composer;
          if (selector.indexOf("div.relative.z-10") === 0) return bar;
          if (selector.indexOf('a[aria-label^="Open "]') === 0) return repoLink;
          return null;
        },
        querySelectorAll(selector) {
          if (selector === "[data-agent-transcript-message]") return roots.slice();
          if (selector === "button[aria-label]") return stop ? [stopButton] : [];
          return [];
        },
        get title() { return page.title; },
        set title(value) { page.title = value; },
      },
      window: { addEventListener() {}, removeEventListener() {} },
      getComputedStyle() { return { overflowY: "auto" }; },
      MutationObserver: class { observe() {} disconnect() {} },
      ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
      requestAnimationFrame() { return 1; },
      cancelAnimationFrame() {},
      setInterval(fn, ms) { intervals.push({ ms, fn }); return intervals.length; },
      clearInterval() {},
      setTimeout(fn) { nextTimeout += 1; timeouts.set(nextTimeout, fn); return nextTimeout; },
      clearTimeout(id) { timeouts.delete(id); },
      fetch() {
        return Promise.resolve({
          ok: false,
          status: 404,
          json: () => Promise.resolve({}),
          text: () => Promise.resolve(""),
        });
      },
      sessionStorage: { getItem() { return null; }, setItem() {} },
      prompt() { return null; },
      GM_getValue(key, fallback) {
        return key === "clankers-arena-show-settings-button" ? false : fallback;
      },
      GM_setValue() {},
      GM_registerMenuCommand(label, callback) { titleMenus.set(label, callback); return label; },
      GM_unregisterMenuCommand(label) { titleMenus.delete(label); },
      GM_xmlhttpRequest() {},
    };
    vm.runInNewContext(source, context, { filename: "arena.user.js" });
    const sync = () => intervals.forEach((item) => item.fn());
    const goto = (path) => {
      context.location.pathname = path;
      context.location.href = "https://arena.ai" + path;
    };

    sync();
    assert.equal(page.title, "Arena | clankers \uD83D\uDCAC", `The chat row raises the balloon: ${page.title}`);
    // The agent root appears when a turn starts. A user root carries no mark, and the hold
    // dies with the stop control.
    goto("/c/two");
    roots = [userRootNode()];
    stop = false;
    sync();
    assert.equal(page.title, "Arena | clankers", `The user root stays quiet: ${page.title}`);
    // A finished turn keeps its rows in the page, so a row mark needs the stop control.
    roots = [agentRoot([labelRow("Bash sleep 25", "$ npm test")])];
    sync();
    assert.equal(page.title, "Arena | clankers", `A finished turn drops the row mark: ${page.title}`);
    // Open turn on same page raises bash mark.
    stop = true;
    sync();
    assert.equal(page.title, "Arena | clankers \uD83D\uDDA5\uFE0F", `The bash row raises its mark: ${page.title}`);
    // Generating-questions action row takes question mark like card.
    roots = [agentRoot([labelRow("Generating questions\u2026", "")])];
    sync();
    assert.equal(page.title, "Arena | clankers \u2753", `The question row raises the mark: ${page.title}`);
    const titleLines = logged.filter(([line]) => line.startsWith("[NemoUtils][title]"));
    assert.ok(titleLines.length > 0, "the title path logs a line");
    assert.ok(titleLines.some(([line, data]) => line === "[NemoUtils][title][info] changed" && data.type === "action"));
    assert.ok(titleLines.every(([, data]) => !("speech" in data) && !("repo" in data)));
    assert.doesNotMatch(JSON.stringify(titleLines), /Bash sleep|npm test|Generating questions|clankers/);
    const count = titleLines.length;
    sync();
    assert.equal(logged.filter(([line]) => line.startsWith("[NemoUtils][title]")).length, count);
    // Prefix/symbol updates on an existing NemoUtils title that already carries the same emoji do not re-log emoji churn.
    page.title = "Arena | clankers \u03B1 \u2753";
    sync();
    assert.equal(page.title, "Arena | clankers \u2753");
    assert.equal(
      logged.filter(([line]) => line.startsWith("[NemoUtils][title]")).length,
      count,
      "changing prefix/symbol while current emoji already matches does not log duplicate emoji churn",
    );
    titleMenus.get("Page - tab title (ON)")();
    assert.equal(page.title, "", "disabling the feature restores the original title");
    assert.equal(logged.filter(([line]) => line === "[NemoUtils][title][info] restored").length, 1);
    console.log("ok tab title row mark: last root, row type, turn bound");
  });
}

{
  const saved = new Map();
  const menus = new Map();
  const observers = [];
  let generating = false;
  let display = "flex";
  let priority = "";
  const alert = {
    isConnected: true,
    matches() { return true; },
    getClientRects() { return display === "none" ? [] : [{}]; },
    style: {
      getPropertyValue() { return display; },
      getPropertyPriority() { return priority; },
      setProperty(key, value, rank) { display = value; priority = rank; },
      removeProperty() { display = ""; priority = ""; },
    },
  };
  const context = {
    console, URL,
    document: {
      documentElement: {},
      querySelector() { return null; },
      querySelectorAll(selector) {
        if (selector === "button[aria-label]") return generating ? [{ getAttribute() { return "Stop generating"; } }] : [];
        if (selector.startsWith('[role="alert"]')) return [alert];
        return [];
      },
    },
    GM_getValue(key, fallback) {
      if (saved.has(key)) return saved.get(key);
      return ["transcript-alerts", "clankers-arena-userscript-paused", "clankers-arena-log-level"].includes(key) ? fallback : false;
    },
    GM_setValue(key, value) { saved.set(key, value); },
    GM_registerMenuCommand(label, callback) { menus.set(label, callback); return label; },
    GM_unregisterMenuCommand(label) { menus.delete(label); },
    MutationObserver: class {
      constructor(callback) { this.callback = callback; observers.push(this); }
      observe(target, options) { this.active = true; this.options = options; }
      disconnect() { this.active = false; }
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8"), context);
  const notify = () => observers.filter((o) => o.active).forEach((o) => o.callback());
  const toggle = () => menus.get("Transcript - hide generation alerts (" + (saved.get("transcript-alerts") === false ? "OFF" : "ON") + ")")();
  assert.ok(menus.has("Transcript - hide generation alerts (ON)"));
  assert.ok(menus.has("Transcript - auto trim (OFF)"));
  assert.equal(display, "flex");
  generating = true; notify();
  assert.equal(display, "none", "alert hiding must not require auto trim");
  assert.ok(observers.some((o) => o.active && o.options.attributes && o.options.attributeFilter.includes("aria-label")));
  toggle();
  assert.equal(saved.get("transcript-alerts"), false);
  assert.equal(display, "flex");
  toggle();
  assert.equal(display, "none");
  menus.get("Userscript - pause all")();
  assert.equal(display, "flex");
  menus.get("Userscript - resume all")();
  assert.equal(display, "none");
  generating = false; notify();
  assert.equal(display, "flex");
}

{
  const { test } = require("node:test");
  test("auto wake sends an exact visible draft once after a cancellable delay", () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const saved = new Map(Object.keys(bundles.arena.features).filter(key => key !== "auto-wake" && key !== "keep-working").map(key => [key, false]));
  saved.set("clankers-arena-show-settings-button", false);
    const timers = new Map();
    const menus = new Map();
    const listeners = new Map();
    const observers = [];
    const logged = [];
    let next = 0;
    let clicks = 0;
    let captcha = false;
    let generating = false;
    let present = true;
    let alerts = [];
    let roots = [];
    let keepWorkingVisible = false;
    let keepWorkingClicks = 0;
    let pollState = null;
    let crossOrigin = false;
    const frameWindow = { postMessage() {} };
    const frame = {src: "https://example.test/", contentWindow: frameWindow, getAttribute(name) { return name === "title" ? "App preview on port 8000" : null; }, get contentDocument() { return !crossOrigin && pollState ? {querySelector() { return {dataset: pollState}; }} : null; }};
    const spinnerRow = {
      tagName: "DIV",
      className: "flex w-fit items-center justify-start gap-1.5",
      outerHTML: '<div class="flex w-fit items-center justify-start gap-1.5"><div class="flex size-4 shrink-0 items-center justify-center"><div class="size-4"><canvas width="16" height="16" style="vertical-align: top; width: 16px; height: 16px;"></canvas></div></div></div>',
    };
    const proseRow = {
      tagName: "DIV",
      className: "prose",
      outerHTML: '<div class="prose"><p>Done.</p></div>',
    };
    const actionRow = {
      tagName: "DIV",
      className: "flex flex-col",
      outerHTML: '<div class="flex flex-col"><button aria-label="Collapse">Ran command</button></div>',
    };
    const keepWorkingButton = {
      disabled: false,
      hidden: false,
      textContent: "Keep working",
      getAttribute() { return null; },
      getClientRects() { return this.hidden ? [] : [{}]; },
      click() { keepWorkingClicks += 1; },
    };
    const messageRoot = (id, hasError, rows = []) => ({
      id,
      children: rows,
      querySelector(selector) {
        if (selector === ":scope > div > div.px-3.pb-3 > div.flex.flex-col.gap-2") return null;
        return hasError ? errorBanner : null;
      },
    });
    const errorBanner = { hidden: false, getClientRects() { return this.hidden ? [] : [{}]; } };
    const button = {
      disabled: false, hidden: false, ariaDisabled: null,
      getAttribute(name) {
        if (name === "aria-label") return "Send message";
        if (name === "data-perf-target") return "send";
        return name === "aria-disabled" ? this.ariaDisabled : null;
      },
      getClientRects() { return this.hidden ? [] : [{}]; },
      click() { clicks += 1; },
    };
    const editor = {
      innerText: "wake up", hidden: false, ariaDisabled: null,
      focus() {},
      get textContent() { return this.innerText; },
      getAttribute(name) { return name === "aria-disabled" ? this.ariaDisabled : null; },
      getClientRects() { return this.hidden ? [] : [{}]; },
      closest() { return null; },
    };
    const emit = (name, event = {}) => {
      for (const callback of [...(listeners.get(name) || [])]) callback(event);
    };
    const fire = () => { for (const observer of observers) if (observer.active) observer.callback([]); };
    const flush = (maxDelay = 5000) => {
      const pending = [...timers.entries()].filter(([, timer]) => timer.ms <= maxDelay);
      for (const [id] of pending) timers.delete(id);
      for (const [, timer] of pending) timer.callback();
    };
    const context = {
      console: { log(...args) { logged.push(args); }, warn(...args) { logged.push(args); }, error(...args) { logged.push(args); } }, URL,
      location: { href: "https://arena.ai/agent/session", pathname: "/agent/session" },
      document: {
        documentElement: {},
        createRange() { return { selectNodeContents() {} }; },
        execCommand(command, ui, text) { assert.equal(command, "insertText"); editor.innerText = text; return true; },
        querySelector(selector) {
          if (selector.includes("tiptap")) return present ? editor : null;
          if (selector.includes("button:nth-child(3)")) return keepWorkingVisible ? keepWorkingButton : null;
          return null;
        },
        querySelectorAll(selector) {
          if (selector === "iframe[title]") return pollState ? [frame] : [];
          if (selector === "button[aria-label]" || selector === "button") return generating ? [{ getAttribute() { return "Stop generating"; } }, button] : [button];
          if (selector === "[data-agent-transcript-message]") return roots;
          if (selector.includes("border-red-500")) return alerts;
          return captcha && selector.includes("recaptcha-v2") ? [{ getAttribute() { return null; } }] : [];
        },
      },
      window: {
        getSelection() { return { removeAllRanges() {}, addRange() {} }; },
        addEventListener(name, callback) {
          if (!listeners.has(name)) listeners.set(name, new Set());
          listeners.get(name).add(callback);
        },
        removeEventListener(name, callback) { listeners.get(name)?.delete(callback); },
      },
      sessionStorage: { getItem() { return null; } },
      MutationObserver: class {
        constructor(callback) { this.callback = callback; this.active = false; observers.push(this); }
        observe() { this.active = true; }
        disconnect() { this.active = false; }
      },
      setTimeout(callback, ms) { const id = ++next; timers.set(id, { callback, ms }); return id; },
      clearTimeout(id) { timers.delete(id); },
      setInterval() {}, clearInterval() {},
      GM_getValue(key, fallback) { return saved.has(key) ? saved.get(key) : fallback; },
      GM_setValue(key, value) { saved.set(key, value); },
      GM_registerMenuCommand(label, callback) { const id = ++next; menus.set(id, { label, callback }); return id; },
      GM_unregisterMenuCommand(id) { menus.delete(id); },
    };
    vm.runInNewContext(source, context);
    assert.equal(timers.size, 1, "default On schedules the matching draft");
    assert.ok([...timers.values()].every(timer => timer.ms >= 0 && timer.ms <= 5000));
    generating = true;
    fire(); flush();
    assert.equal(clicks, 0, "never click Stop generating for auto-wake");
    generating = false;
    fire(); fire();
    assert.equal(timers.size, 1, "mutations do not schedule duplicate sends");
    for (const text of ["wake upwake up", "Wake up", " wake up", "wake up ", "wake up\n", "other"]) {
      editor.innerText = text;
      emit("input", { isComposing: false });
      fire(); flush();
      assert.equal(clicks, 0, text);
      assert.equal(editor.innerText, text, "other drafts are not changed");
    }
    editor.innerText = "wake up";
    fire();
    editor.hidden = true;
    fire();
    assert.equal(timers.size, 0, "the composer-hide state cancels a pending send");
    editor.hidden = false;
    fire();
    button.disabled = true;
    flush();
    assert.equal(clicks, 0, "the timer checks the live button again");
    button.disabled = false;
    button.ariaDisabled = "true";
    fire();
    assert.equal(timers.size, 0);
    button.ariaDisabled = null;
    fire(); flush();
    assert.equal(clicks, 1);
    fire(); flush();
    assert.equal(clicks, 1, "one unchanged draft sends once");
    present = false; fire();
    present = true; fire(); flush();
    assert.equal(clicks, 1, "remounting the unchanged composer must not send again");
    editor.innerText = "";
    fire();
    captcha = true;
    editor.innerText = "wake up";
    fire();
    assert.equal(timers.size, 0, "captcha holds automatic sends");
    captcha = false;
    fire();
    emit("compositionstart");
    flush();
    assert.equal(clicks, 1, "IME composition cancels the pending send");
    emit("compositionend");
    const toggle = () => [...menus.values()].find(item => item.label.startsWith("Composer - auto-send wake up")).callback();
    toggle();
    fire(); flush();
    assert.equal(clicks, 1, "Off cancels the timer and observers");
    assert.equal(saved.get("auto-wake"), false);
    toggle();
    [...menus.values()].find(item => item.label === "Userscript - pause all").callback();
    flush();
    assert.equal(clicks, 1, "global pause cancels the send");
    [...menus.values()].find(item => item.label === "Userscript - resume all").callback();
    flush();
    assert.equal(clicks, 2);
    fire(); flush();
    assert.equal(clicks, 2);
    alerts = [errorBanner];
    roots = [messageRoot("old-root", true), messageRoot("latest-root", false)];
    editor.innerText = "";
    fire(); flush();
    assert.equal(editor.innerText, "", "errors in older roots must not trigger recovery");
    assert.equal(clicks, 2);
    roots = [messageRoot("old-root", true), messageRoot("latest-root", true)];
    errorBanner.hidden = true;
    editor.innerText = "Keep this draft";
    fire(); flush();
    assert.equal(editor.innerText, "Keep this draft");
    assert.equal(clicks, 2);
    editor.innerText = "";
    editor.hidden = true;
    fire();
    assert.equal(editor.innerText, "", "hidden composers must not be filled");
    editor.hidden = false;
    captcha = true;
    fire();
    assert.equal(editor.innerText, "", "captcha holds error recovery too");
    captcha = false;
    emit("compositionstart");
    fire();
    assert.equal(editor.innerText, "", "IME holds error recovery too");
    emit("compositionend");
    assert.equal(editor.innerText, "wake up", "the latest-root error triggers even when trim hides its banner");
    assert.equal(timers.size, 1);
    flush();
    assert.equal(clicks, 3);
    editor.innerText = "";
    fire(); flush();
    assert.equal(editor.innerText, "", "an unchanged error cannot create a retry loop");
    assert.equal(clicks, 3);
    roots = [messageRoot("latest-root", true)];
    fire(); flush();
    assert.equal(clicks, 3, "the same root ID cannot repeat after a remount");
    roots = [messageRoot("newest-root", true)];
    fire(); flush();
    assert.equal(clicks, 4, "a new latest root permits one recovery");
    roots = [messageRoot("no-button-root", false, [proseRow, actionRow])];
    present = true;
    editor.innerText = "";
    keepWorkingVisible = false;
    fire(); flush();
    assert.equal(keepWorkingClicks, 0);
    assert.equal(editor.innerText, "", "does not type wake up if Keep working never showed up");
    present = false;
    keepWorkingVisible = true;
    roots = [messageRoot("spinner-root", false, [actionRow, spinnerRow])];
    fire(); flush();
    assert.equal(keepWorkingClicks, 0, "Keep working stays idle while the last row is the 16x16 canvas spinner");
    roots = [messageRoot("prose-root", false, [actionRow, proseRow])];
    fire(); flush();
    assert.equal(keepWorkingClicks, 0, "Keep working stays idle when the last row has the prose class");
    roots = [messageRoot("stopped-root", false, [proseRow, actionRow])];
    const toggleKeepWorking = () => [...menus.values()].find(item => item.label.startsWith("Composer - keep working")).callback();
    toggleKeepWorking();
    assert.equal(saved.get("keep-working"), false);
    fire(); flush();
    assert.equal(keepWorkingClicks, 0, "Keep working toggle Off disables the click");
    toggleKeepWorking();
    assert.equal(saved.get("keep-working"), true);
    assert.equal(keepWorkingClicks, 0, "waits for the random 0-5s delay before clicking Keep working");
    assert.equal(timers.size, 1);
    assert.ok([...timers.values()].every(timer => timer.ms >= 0 && timer.ms <= 5000));
    flush();
    assert.equal(keepWorkingClicks, 1, "Keep working clicks once when the last row is neither spinner nor prose");
    assert.ok(logged.some(([line]) => line === "[NemoUtils][keep-working][info] clicked"));
    assert.equal(editor.innerText, "", "waits for the composer before typing wake up");
    fire(); flush();
    assert.equal(keepWorkingClicks, 1, "does not click Keep working repeatedly for the same root");
    keepWorkingVisible = false;
    present = true;
    fire();
    assert.equal(editor.innerText, "wake up", "types wake up once the composer mounts");
    assert.ok(logged.some(([line]) => line === "[NemoUtils][keep-working][info] filled"));
    flush();
    assert.equal(clicks, 5, "sends wake up after Keep working opens the composer");
    saved.set("clankers-arena-wake-text", "Resume now");
    saved.set("clankers-arena-no-poll-text", "Missed final poll");
    editor.innerText = "";
    keepWorkingVisible = false;
    roots = [messageRoot("ended-valid", false, [proseRow])];
    pollState = {available: "true", polling: "true", pollingGate: "false", turnEndedAt: "", updatedAt: "9999999999999"};
    generating = true; fire();
    generating = false; fire(); flush();
    assert.equal(clicks, 5, "an active final poll does not trigger violation");
    roots = [messageRoot("ended-gate", false, [proseRow])];
    pollState = {available: "true", polling: "true", pollingGate: "true", turnEndedAt: "", updatedAt: "9999999999999"};
    generating = true; fire();
    generating = false; fire(); flush();
    assert.equal(editor.innerText, "Missed final poll", "gate wait is not a final poll");
    assert.equal(clicks, 6, "the configured violation message is auto-sent");
    fire(); flush();
    assert.equal(clicks, 6, "the same turn is sent once");
    editor.innerText = ""; fire();
    editor.innerText = "Resume now"; fire(); flush();
    assert.equal(clicks, 7, "the configured wake text also auto-sends");
    editor.innerText = ""; fire();
    roots = [messageRoot("cross-origin", false, [proseRow])];
    crossOrigin = true;
    generating = true; fire();
    generating = false; fire(); flush();
    assert.equal(clicks, 7, "without a reply, no automatic message is sent");
    const reply = { type: "clankers:steering-poll-state", available: "true", polling: "false", pollingGate: "false", pollCompleted: "false", updatedAt: "9999999999999" };
    emit("message", {source: {}, origin: "https://example.test", data: reply});
    emit("message", {source: frameWindow, origin: "https://wrong.test", data: reply});
    flush();
    assert.equal(clicks, 7, "untrusted frames and origins are ignored");
    emit("message", {source: frameWindow, origin: "https://example.test", data: reply});
    flush();
    assert.equal(clicks, 8, "a fresh reply from the Steering frame triggers the violation");
    editor.innerText = ""; fire();
    crossOrigin = true;
    present = false;
    keepWorkingVisible = true;
    roots = [messageRoot("gate-keep-working", false, [proseRow, actionRow])];
    pollState = {available: "true", polling: "true", pollingGate: "true", pollCompleted: "false", updatedAt: "9999999999999"};
    generating = true; fire();
    generating = false; fire(); flush();
    assert.equal(keepWorkingClicks, 2, "opens the composer through Keep working");
    keepWorkingVisible = false;
    present = true; fire(); flush();
    assert.equal(editor.innerText, "", "waits for fresh poll state before filling the composer");
    emit("message", {source: frameWindow, origin: "https://example.test", data: {...pollState, type: "clankers:steering-poll-state"}});
    fire(); flush();
    assert.equal(editor.innerText, "Missed final poll", "Keep working carries the violation text");
    assert.equal(clicks, 9);
    editor.innerText = ""; fire();
    present = false; keepWorkingVisible = true;
    roots = [messageRoot("unreachable-steering", false, [proseRow, actionRow])];
    generating = true; fire();
    generating = false; fire(); flush();
    keepWorkingVisible = false; present = true; fire(); flush();
    assert.equal(editor.innerText, "", "waits briefly when a known Steering frame stops responding");
    flush(9000); flush();
    assert.equal(editor.innerText, "Resume now", "the existing wake resumes if Steering is unreachable");
    editor.innerText = ""; fire();
    frame.src = "https://older-preview.test/";
    present = false; keepWorkingVisible = true;
    roots = [messageRoot("legacy-preview", false, [proseRow, actionRow])];
    generating = true; fire();
    generating = false; fire(); flush();
    keepWorkingVisible = false; present = true; fire(); flush();
    assert.equal(editor.innerText, "Resume now", "unrecognized previews preserve the existing wake flow");
    assert.equal(clicks, 11);
  });
}

{
  const { test } = require("node:test");
  test("setComposerText renders inline backtick spans as code elements", () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const makeNode = (tag) => ({
      tagName: tag.toUpperCase(),
      children: [],
      _text: "",
      get firstChild() { return this.children[0] || null; },
      get textContent() {
        return this.children.length
          ? this.children.map(child => child.textContent).join("")
          : this._text;
      },
      set textContent(value) {
        this.children = [];
        this._text = String(value);
      },
      get innerText() {
        return this.children.length
          ? this.children.map(child => child.textContent).join("\n")
          : this._text;
      },
      appendChild(child) { this.children.push(child); return child; },
      removeChild(child) {
        const idx = this.children.indexOf(child);
        if (idx >= 0) this.children.splice(idx, 1);
      },
      dispatchEvent() {},
      focus() {},
      getAttribute() { return null; },
    });
    const composer = makeNode("div");
    let execCalled = false;
    const context = {
      console: { log() {}, warn() {}, error() {} },
      URL,
      InputEvent: class { constructor(type, init) { this.type = type; Object.assign(this, init); } },
      location: { href: "https://arena.ai/agent", pathname: "/agent" },
      document: {
        documentElement: {},
        createElement(tag) { return makeNode(tag); },
        createTextNode(text) { return { nodeType: 3, textContent: String(text) }; },
        createRange() { return { selectNodeContents() {} }; },
        execCommand() { execCalled = true; return true; },
        querySelector(selector) {
          if (selector === 'div.tiptap.ProseMirror[contenteditable="true"]') return composer;
          if (selector.indexOf("div.relative.z-10") === 0) {
            return {
              textContent: "nemoe7/clankers",
              querySelectorAll() {
                return [{ textContent: "nemoe7/clankers" }];
              },
            };
          }
          return null;
        },
        querySelectorAll() { return []; },
        title: "",
      },
      window: {
        addEventListener() {},
        removeEventListener() {},
        getSelection() { return { removeAllRanges() {}, addRange() {} }; },
      },
      getComputedStyle() { return { overflowY: "auto" }; },
      MutationObserver: class { observe() {} disconnect() {} },
      ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
      requestAnimationFrame() { return 1; },
      cancelAnimationFrame() {},
      setInterval() { return 1; },
      clearInterval() {},
      setTimeout() { return 1; },
      clearTimeout() {},
      fetch(url) {
        return Promise.resolve({
          ok: true,
          status: 200,
          text: () => Promise.resolve(
            url.includes("arena-prompt-fill.txt")
              ? "Run `arena-preview survey '<json>'` and `git ls-remote origin <branch>`.\nPlain line"
              : "",
          ),
        });
      },
      sessionStorage: { getItem() { return null; }, setItem() {} },
      GM_getValue(key, fallback) {
        if (key === "prompt-fill") return true;
        return false;
      },
      GM_setValue() {},
      GM_registerMenuCommand() { return 1; },
      GM_unregisterMenuCommand() {},
      GM_xmlhttpRequest() {},
    };
    vm.runInNewContext(source, context);
    return new Promise((resolve) => setImmediate(resolve)).then(() => {
      assert.equal(execCalled, false, "inline backtick spans bypass plain-text execCommand");
      assert.equal(composer.children.length, 4);
      const codeNodes = composer.children[2].children.filter(node => node.tagName === "CODE");
      assert.deepEqual(
        codeNodes.map(node => node.textContent),
        ["arena-preview survey '<json>'", "git ls-remote origin <branch>"],
      );
      assert.equal(composer.children[3].textContent, "Plain line");
    });
  });
}

{
  const { test } = require("node:test");
  test("state logs keep a bounded failure reason", () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const logged = [];
    const sink = (...args) => logged.push(args);
    const context = {
      console: { log: sink, warn: sink, error: sink },
      GM_getValue: () => "info",
      GM_setValue: () => {},
      setTimeout: () => 0,
      clearTimeout: () => {},
      setInterval: () => 0,
      clearInterval: () => {},
      URL,
      addEventListener: () => {},
      removeEventListener: () => {},
    };
    vm.runInNewContext(source, context, { filename: "arena.user.js" });
    const { sameSaves, sameSaveDetail, stateDiffCounts, stateMismatchLine, mismatchOfferId } = context.CLANKERS_CHECKS.stateDownload;
    const offerBaseline = { lastsave: "t1", beforelastsave: null, digest: "d1" };
    const offerBody = { lastsave: "t2", beforelastsave: "t1", instance_id: "container-a" };
    assert.equal(
      mismatchOfferId(offerBaseline, offerBody),
      mismatchOfferId(offerBaseline, { ...offerBody }),
      "the same live container keeps backup-offer deduplication stable"
    );
    assert.notEqual(
      mismatchOfferId(offerBaseline, offerBody),
      mismatchOfferId(offerBaseline, { ...offerBody, instance_id: "container-b" }),
      "a new container can offer the same backup again"
    );
    assert.equal(sameSaves(null, { lastsave: "a", beforelastsave: null }), false);
    assert.equal(sameSaves({ lastsave: "a", beforelastsave: null }, { lastsave: "a", beforelastsave: null }), true);
    assert.equal(sameSaves({ lastsave: "a", beforelastsave: "b" }, { lastsave: "a", beforelastsave: null }), false);
    assert.equal(sameSaves({ lastsave: "a", beforelastsave: "b" }, { lastsave: "a", beforelastsave: "b" }), true);
    assert.equal(
      sameSaveDetail({ lastsave: "t2", beforelastsave: "t1" }, { lastsave: "t9", beforelastsave: "t2" }),
      "saved t2/t1 server t9/t2 n0 t0",
      "the detail names both stamp pairs and the counts"
    );
    assert.equal(
      sameSaveDetail(
        { lastsave: "t2", beforelastsave: "t1", counts: { notes: 2, tasks: 1 } },
        { lastsave: "t9", beforelastsave: "t2", counts: { notes: 4, tasks: 1 } }
      ),
      "saved t2/t1 server t9/t2 n4 t1 dn+2 dt0",
      "the detail includes signed diff counts when baseline counts exist"
    );
    assert.equal(
      stateMismatchLine(
        { core: [{ id: "n1", text: "a" }] },
        { core: [{ id: "n1", text: "a" }, { id: "n2", text: "b" }, { id: "t1", title: "Task" }] }
      ),
      "State mismatch (notes +1, tasks +1)."
    );
    assert.deepEqual(
      JSON.parse(JSON.stringify(stateDiffCounts(
        { counts: { notes: 5, tasks: 3 } },
        { counts: { notes: 3, tasks: 4 } }
      ))).notes,
      -2
    );
    assert.equal(
      sameSaveDetail(null, { lastsave: "t9", beforelastsave: null, counts: { notes: 3, tasks: 2 } }),
      "saved none/none server t9/none n3 t2",
      "a missing baseline reads as none"
    );
    const longStamp = "2026-10-15T09:00:00";
    assert.ok(
      sameSaveDetail(
        { lastsave: longStamp, beforelastsave: longStamp },
        { lastsave: longStamp, beforelastsave: longStamp, counts: { notes: 999, tasks: 999 } }
      ).length <= 160,
      "the detail stays inside the log cap"
    );
    const { logEvent } = context.CLANKERS_CHECKS.logging;
    logEvent("state", "failed", { code: "autosave-compare", status: 200, result: "unknown-baseline", detail: "digest" }, "error");
    const [line, data] = logged.at(-1);
    assert.match(line, /\[state\]\[error\] failed/);
    assert.equal(data.code, "autosave-compare");
    assert.equal(data.status, 200);
    assert.equal(data.result, "unknown-baseline");
    assert.equal(data.detail, "digest");
    logEvent("state", "failed", { detail: "x".repeat(500) }, "error");
    assert.equal(logged.at(-1)[1].detail.length, 160);
    logEvent("state", "failed", { result: "other", detail: "" }, "error");
    assert.equal(logged.at(-1).length, 1, "unknown values and empty detail stay out of the log");
  });
}

{
  const { test } = require("node:test");
  test("configurable timers, dropped stale inner VERSION, and draggable Lucide settings modal", async () => {
    const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
    const checkSaved = new Map();
    const checkContext = {
      console,
      URL,
      GM_getValue: (k, fallback) => (checkSaved.has(k) ? checkSaved.get(k) : fallback),
      GM_setValue(k, v) { checkSaved.set(k, v); },
      setTimeout: () => 0,
      clearTimeout() {},
      setInterval: () => 0,
      clearInterval() {},
      addEventListener() {},
      removeEventListener() {},
    };
    vm.runInNewContext(source, checkContext);
    assert.equal(checkContext.CLANKERS_CHECKS.tabTitle.VERSION, undefined, "stale inner VERSION constant is dropped from tabTitle");

    const saved = new Map([
      ["auto-scroll", true],
      ["auto-wake", true],
      ["state-download", true],
      ["clankers-arena-state-watch-ms", 12000],
      ["clankers-arena-state-panel-ms", 3500],
      ["clankers-arena-wake-delay-ms", 1200],
      ["clankers-arena-http-jitter-ms", 4000],
    ]);
    const timeouts = [];
    const intervals = [];
    const windowListeners = new Map();
    let modalNode = null;

    const makeElement = (tag) => ({
      tag,
      id: "",
      type: "",
      value: "",
      checked: false,
      className: "",
      textContent: "",
      style: { cssText: "", left: "", top: "", right: "" },
      attrs: {},
      listeners: {},
      children: [],
      parentElement: null,
      isConnected: true,
      setAttribute(name, value) {
        this.attrs[name] = String(value);
        if (name === "id") this.id = String(value);
      },
      getAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
      },
      appendChild(child) {
        child.parentElement = this;
        this.children.push(child);
        if (child.id === "clankers-settings-modal") modalNode = child;
        return child;
      },
      remove() {
        this.isConnected = false;
        if (this === modalNode) modalNode = null;
        if (this.parentElement && Array.isArray(this.parentElement.children)) {
          const idx = this.parentElement.children.indexOf(this);
          if (idx >= 0) this.parentElement.children.splice(idx, 1);
        }
      },
      addEventListener(name, fn) {
        this.listeners[name] = fn;
      },
      closest() {
        return null;
      },
      getBoundingClientRect() {
        return { left: 240, top: 80, width: 380, height: 420 };
      },
      querySelector(sel) {
        for (const child of this.children) {
          if (sel === "[data-clankers-autoscroll-toggle]" && child.attrs["data-clankers-autoscroll-toggle"]) return child;
          if (sel === "[data-clankers-settings-toggle]" && child.attrs["data-clankers-settings-toggle"]) return child;
          if (sel === "[data-clankers-settings-drag]" && child.attrs["data-clankers-settings-drag"]) return child;
          if (sel === "[data-clankers-settings-close]" && child.attrs["data-clankers-settings-close"]) return child;
          if (child.querySelector) {
            const hit = child.querySelector(sel);
            if (hit) return hit;
          }
        }
        return null;
      },
      querySelectorAll(sel) {
        const out = [];
        const visit = (node) => {
          for (const child of node.children || []) {
            if (sel === "input, select, textarea" && (child.tag === "input" || child.tag === "select" || child.tag === "textarea")) out.push(child);
            if (sel === "path" && child.tag === "path") out.push(child);
            if (sel === "section" && child.tag === "section") out.push(child);
            if (sel === "button" && child.tag === "button") out.push(child);
            visit(child);
          }
        };
        visit(this);
        return out;
      },
    });

    const row = makeElement("div");
    const stopButton = makeElement("button");
    stopButton.setAttribute("aria-label", "Stop generating");
    row.appendChild(stopButton);
    row.insertBefore = function (node, ref) {
      node.parentElement = this;
      const idx = this.children.indexOf(ref);
      if (idx >= 0) this.children.splice(idx, 0, node);
      else this.children.push(node);
      return node;
    };

    const body = makeElement("body");
    const doc = {
      documentElement: makeElement("html"),
      body,
      title: "Arena",
      hidden: false,
      getElementById(id) {
        return id === "clankers-settings-modal" ? modalNode : null;
      },
      querySelector() { return null; },
      querySelectorAll(sel) {
        return sel === "button[aria-label]" ? [stopButton] : [];
      },
      createElement: (tag) => makeElement(tag),
      createElementNS: (_ns, tag) => makeElement(tag),
    };

    const context = {
      console,
      URL,
      Math: Object.assign(Object.create(Math), { random: () => 0.999999 }),
      Date: { now: () => 10000 },
      location: { pathname: "/c/session", href: "https://arena.ai/c/session", origin: "https://arena.ai", host: "arena.ai" },
      document: doc,
      window: {
        innerWidth: 1280,
        innerHeight: 800,
        addEventListener(name, fn) { windowListeners.set(name, fn); },
        removeEventListener(name) { windowListeners.delete(name); },
      },
      getComputedStyle() { return { display: "block", visibility: "visible", overflowY: "auto" }; },
      MutationObserver: class { observe() {} disconnect() {} },
      ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
      requestAnimationFrame() { return 1; },
      cancelAnimationFrame() {},
      setTimeout(fn, ms) { timeouts.push({ fn, ms }); return timeouts.length; },
      clearTimeout() {},
      setInterval(fn, ms) { intervals.push({ fn, ms }); return intervals.length; },
      clearInterval() {},
      GM_getValue(key, fallback) { return saved.has(key) ? saved.get(key) : fallback; },
      GM_setValue(key, value) { saved.set(key, value); },
      GM_registerMenuCommand() { return 1; },
      GM_unregisterMenuCommand() {},
    };

    vm.runInNewContext(source, context);

    const watchInterval = intervals.find((entry) => entry.ms === 12000);
    assert.ok(watchInterval, "state-download timer uses configured 12000ms watch interval");
    watchInterval.fn();
    assert.ok(
      timeouts.some((entry) => entry.ms === 3999),
      "jitteredTimer uses configured 4000ms jitter range",
    );

    const autoIndex = row.children.findIndex((el) => el.attrs["data-clankers-autoscroll-toggle"] === "true");
    const settingsIndex = row.children.findIndex((el) => el.attrs["data-clankers-settings-toggle"] === "true");
    const stopIndex = row.children.indexOf(stopButton);
    assert.ok(autoIndex >= 0, "auto-scroll button is in the row");
    assert.equal(settingsIndex, autoIndex + 1, "Lucide settings button sits right after the auto-scroll button");
    assert.equal(stopIndex, settingsIndex + 1, "settings button sits before Stop generating");

    const autoButton = row.children[autoIndex];
    const autoSvg = autoButton.children[0];
    assert.equal(
      autoSvg.attrs.class,
      "lucide lucide-arrow-down-to-line",
      "auto-scroll button renders the Lucide arrow-down-to-line SVG",
    );
    assert.equal(autoSvg.attrs["stroke-width"], "2", "Lucide icon uses stroke-width 2");
    const settingsButton = row.children[settingsIndex];
    const settingsSvg = settingsButton.children[0];
    assert.equal(settingsButton.attrs["aria-pressed"], "false", "settings toggle starts unpressed");
    assert.equal(
      settingsSvg.attrs.class,
      "lucide lucide-settings",
      "settings button renders the Lucide settings SVG",
    );
    assert.equal(settingsSvg.children.length, 2, "Lucide settings icon has path and circle");
    assert.equal(settingsSvg.children[1].attrs.r, "3", "Lucide settings icon uses a circle center");

    settingsButton.listeners.click();
    assert.ok(modalNode, "clicking the settings button opens the settings modal");
    assert.equal(settingsButton.attrs["aria-pressed"], "true", "settings button shows pressed while modal is open");

    const dragHeader = modalNode.querySelector("[data-clankers-settings-drag]");
    assert.ok(dragHeader, "settings modal has a draggable header");
    const closeButton = modalNode.querySelector("[data-clankers-settings-close]");
    assert.ok(closeButton, "settings modal header includes a close button");
    assert.equal(closeButton.attrs["aria-label"], "Close settings", "close button carries accessible label");
    assert.equal(
      closeButton.children[0].attrs.class,
      "lucide lucide-x",
      "close button renders the Lucide x SVG",
    );
    assert.equal(closeButton.querySelectorAll("path").length, 2, "close button renders a 2-path Lucide X icon");
    dragHeader.listeners.mousedown({ button: 0, clientX: 300, clientY: 100, preventDefault() {} });
    windowListeners.get("mousemove")({ clientX: 420, clientY: 190 });
    windowListeners.get("mouseup")();
    assert.equal(modalNode.style.left, "360px", "dragging the modal header updates left position");
    assert.equal(modalNode.style.top, "170px", "dragging the modal header updates top position");

    const sections = modalNode.querySelectorAll("section").map((sec) => sec.attrs["data-settings-section"]);
    assert.deepEqual(
      sections,
      ["Composer", "Page", "Proxy", "State", "Steering", "Transcript", "Userscript"],
      "settings modal groups settings into alphabetized sections",
    );

    const allInputs = modalNode.querySelectorAll("input, select, textarea");
    const wakeTextInput = allInputs.find(el => el.attrs["data-setting-key"] === "clankers-arena-wake-text");
    const noPollInput = allInputs.find(el => el.attrs["data-setting-key"] === "clankers-arena-no-poll-text");
    assert.ok(wakeTextInput && noPollInput, "both messages are configurable");
    assert.equal(noPollInput.tag, "textarea", "the violation message supports multiple lines");
    wakeTextInput.value = "Continue";
    wakeTextInput.listeners.change();
    noPollInput.value = "Violation\nRead the bible";
    noPollInput.listeners.change();
    assert.equal(saved.get("clankers-arena-wake-text"), "Continue");
    assert.equal(saved.get("clankers-arena-no-poll-text"), "Violation\nRead the bible");
    const allButtons = modalNode.querySelectorAll("button");
    assert.equal(
      allButtons.some((btn) => btn.attrs["data-settings-action"] === "choose-state-file"),
      false,
      "settings modal omits removed choose-state-file action",
    );
    for (const actionId of ["force-save", "trim-now", "post-key-now"]) {
      assert.ok(
        allButtons.some((btn) => btn.attrs["data-settings-action"] === actionId),
        `settings modal exposes action button ${actionId}`,
      );
    }
    for (const key of [
      "clankers-arena-preview-proxy-host",
      "clankers-arena-trim-keep",
      "clankers-arena-trim-cap",
      "clankers-arena-trim-interval-ms",
      "clankers-arena-title-interval-ms",
      "clankers-arena-state-panel-ms",
      "clankers-arena-state-reset-window",
      "clankers-arena-preview-drawer-lock",
      "clankers-arena-preview-drawer-width-px",
      "clankers-arena-log-level",
      "clankers-arena-userscript-paused",
      "clankers-arena-show-settings-button",
    ]) {
      assert.ok(
        allInputs.some((el) => el.attrs["data-setting-key"] === key),
        `settings modal exposes setting ${key}`,
      );
    }
    const drawerLockInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-preview-drawer-lock",
    );
    const drawerWidthInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-preview-drawer-width-px",
    );
    assert.ok(drawerLockInput, "settings modal exposes preview drawer width lock toggle");
    assert.equal(drawerLockInput.type, "checkbox", "preview drawer width lock uses a checkbox toggle");
    assert.equal(drawerLockInput.checked, true, "preview drawer width lock defaults to enabled");
    assert.ok(drawerWidthInput, "settings modal exposes preview drawer width slider");
    assert.equal(drawerWidthInput.type, "range", "preview drawer width uses a range slider");
    assert.equal(drawerWidthInput.value, "1398", "preview drawer width slider defaults to 1398 px");
    drawerWidthInput.value = "1240";
    drawerWidthInput.listeners.change();
    assert.equal(
      saved.get("clankers-arena-preview-drawer-width-px"),
      1240,
      "changing preview drawer width slider persists pixel width",
    );
    drawerLockInput.checked = false;
    drawerLockInput.listeners.change();
    assert.equal(
      saved.get("clankers-arena-preview-drawer-lock"),
      false,
      "toggling preview drawer width lock checkbox persists boolean",
    );
    const wakeMinInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-wake-delay-min-ms",
    );
    const wakeMaxInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-wake-delay-ms",
    );
    const keepMinInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-keep-working-delay-min-ms",
    );
    const keepMaxInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-keep-working-delay-ms",
    );
    assert.ok(wakeMinInput && wakeMaxInput, "settings modal renders min and max sliders for Wake-up delay");
    assert.equal(wakeMinInput.type, "range", "Wake-up min uses a range slider");
    assert.equal(wakeMaxInput.type, "range", "Wake-up max uses a range slider");
    assert.equal(wakeMinInput.attrs["data-range-role"], "min", "Wake-up left slider is min");
    assert.equal(wakeMaxInput.attrs["data-range-role"], "max", "Wake-up right slider is max");
    assert.ok(
      allInputs.indexOf(wakeMinInput) < allInputs.indexOf(wakeMaxInput),
      "Wake-up min slider sits on the left before max slider",
    );
    assert.ok(keepMinInput && keepMaxInput, "settings modal renders min and max sliders for Keep working delay");
    assert.equal(keepMinInput.type, "range", "Keep working min uses a range slider");
    assert.equal(keepMaxInput.type, "range", "Keep working max uses a range slider");
    assert.ok(
      allInputs.indexOf(keepMinInput) < allInputs.indexOf(keepMaxInput),
      "Keep working min slider sits on the left before max slider",
    );
    assert.equal(
      keepMinInput.parentElement,
      keepMaxInput.parentElement,
      "min and max inputs share a single dual-thumb slider track",
    );
    assert.equal(
      keepMinInput.parentElement.attrs["data-dual-slider"],
      "true",
      "shared slider track marks data-dual-slider=true",
    );
    const keepRail = keepMinInput.parentElement.children[0];
    const keepFill = keepRail.children[0];
    assert.equal(
      keepFill.attrs["data-slider-fill"],
      "true",
      "dual-thumb slider track renders a filled range bar between the two thumbs",
    );
    const keepTicks = keepRail.children[1];
    assert.equal(
      keepTicks.attrs["data-slider-ticks"],
      "true",
      "dual-thumb slider track renders integer snap point ticks",
    );
    assert.equal(
      keepTicks.children.length,
      61,
      "0..60 second slider renders 61 integer snap point ticks",
    );
    assert.equal(
      keepMinInput.attrs.list,
      "clankers-snap-clankers-arena-keep-working-delay-min-ms",
      "min slider links to integer snap datalist",
    );
    assert.equal(
      keepMaxInput.attrs.list,
      "clankers-snap-clankers-arena-keep-working-delay-min-ms",
      "max slider links to the same integer snap datalist",
    );

    keepMinInput.value = "2";
    keepMinInput.listeners.change();
    keepMaxInput.value = "9";
    keepMaxInput.listeners.change();
    assert.equal(saved.get("clankers-arena-keep-working-delay-min-ms"), 2000, "changing Keep working min slider persists ms");
    assert.equal(saved.get("clankers-arena-keep-working-delay-ms"), 9000, "changing Keep working max slider persists ms");
    assert.ok(parseFloat(keepFill.style.width) > 0, "filled range bar updates its width between min and max thumbs");

    const watchInput = allInputs.find(
      (el) => el.attrs["data-setting-key"] === "clankers-arena-state-watch-ms",
    );
    assert.ok(watchInput, "settings modal exposes configurable state watch interval input");
    watchInput.value = "25";
    watchInput.listeners.change();
    assert.equal(saved.get("clankers-arena-state-watch-ms"), 25000, "changing modal input persists milliseconds");
    assert.ok(intervals.some((entry) => entry.ms === 25000), "changing state watch interval restarts timer");

    closeButton.listeners.click();
    assert.equal(modalNode, null, "clicking the Lucide X close button closes the modal");
    assert.equal(settingsButton.attrs["aria-pressed"], "false", "settings button resets aria-pressed on close");

    for (const rel of ["userscripts/arena.user.js", "userscripts/chatgpt.user.js", "docs/userscripts/arena/README.md", "docs/userscripts/chatgpt/README.md"]) {
      const content = fs.readFileSync(path.join(__dirname, "../..", rel), "utf8");
      assert.ok(!new RegExp("[\\u2013\\u2014]|\\\\u201[34]", "i").test(content), `${rel} must not contain long dashes`);
    }

    const checks = checkContext.CLANKERS_CHECKS;
    assert.equal(
      checks.promptFill.PREVIEW_PROXY_HOST_KEY,
      "clankers-arena-preview-proxy-host",
      "exposes clankers-arena-preview-proxy-host setting key"
    );
    assert.equal(
      checks.promptFill.previewProxyHost("", "https://arena-proxy.taile06e44.ts.net"),
      "https://arena-preview.taile06e44.ts.net",
      "derives arena-preview.<tailnet>.ts.net from clankers-arena-proxy-host when unset"
    );
    assert.equal(
      checks.promptFill.previewProxyHost("https://custom-preview.taile06e44.ts.net/", "https://arena-proxy.taile06e44.ts.net"),
      "https://custom-preview.taile06e44.ts.net",
      "explicit preview proxy host overrides derived default"
    );
    assert.equal(
      checks.promptFill.previewProxyHost("custom-preview.taile06e44.ts.net", ""),
      "https://custom-preview.taile06e44.ts.net",
      "bare hostname normalizes to https"
    );
    const fakeDoc = {
      querySelectorAll(sel) {
        if (sel === "span") {
          return [
            {
              className: "text-text-secondary min-w-0 max-w-[180px] truncate text-sm leading-[1.2]",
              textContent: "clankers - Web Preview",
            },
          ];
        }
        if (sel === "iframe") {
          return [
            {
              src: "https://sbx-otherport.arena.site/",
              getAttribute(name) {
                return name === "title" ? "App preview on port 3000" : "";
              },
            },
          ];
        }
        if (sel === "a") {
          return [
            {
              href: "https://sbx-linkport.arena.site/preview",
            },
          ];
        }
        return [];
      },
    };
    assert.deepEqual(
      JSON.parse(JSON.stringify(checks.promptFill.discoverPreviews(fakeDoc))),
      [
        { url: "https://sbx-otherport.arena.site/", name: "clankers - Web Preview" },
        { url: "https://sbx-linkport.arena.site/", name: "clankers - Web Preview" },
      ],
      "discovers non-steering preview iframe and link URLs on any port along with the header span name"
    );
    const unavailableDoc = {
      querySelectorAll(sel) {
        if (sel === "span") {
          return [
            {
              className: "text-text-secondary min-w-0 max-w-[180px] truncate text-sm leading-[1.2]",
              textContent: "Preview Unavailable",
            },
          ];
        }
        if (sel === "iframe") {
          return [{ src: "https://sbx-dead.arena.site/" }];
        }
        return [];
      },
    };
    assert.deepEqual(
      JSON.parse(JSON.stringify(checks.promptFill.discoverPreviews(unavailableDoc))),
      [],
      "skips preview URLs when the header says Preview Unavailable"
    );
    const steeringAndDemoDoc = {
      querySelectorAll(sel) {
        if (sel === "span") {
          return [
            {
              className: "text-text-secondary min-w-0 max-w-[180px] truncate text-sm leading-[1.2]",
              textContent: "Demo App",
            },
          ];
        }
        if (sel === "iframe[title]" || sel === "iframe") {
          return [
            {
              src: "https://sbx-steering8000.arena.site/",
              getAttribute(name) {
                return name === "title" ? "App preview on port 8000" : "";
              },
            },
            {
              src: "https://sbx-demo3000.arena.site/",
              getAttribute(name) {
                return name === "title" ? "App preview on port 3000" : "";
              },
            },
          ];
        }
        return [];
      },
    };
    assert.deepEqual(
      JSON.parse(JSON.stringify(checks.promptFill.discoverPreviews(steeringAndDemoDoc, "clankers"))),
      [
        { url: "https://sbx-steering8000.arena.site/", name: "clankers - Steering" },
        { url: "https://sbx-demo3000.arena.site/", name: "Demo App" },
      ],
      "uses the steering preview UI repo name while keeping DOM header labels for other previews"
    );
    const reconciled = checks.promptFill.reconcileRecentPreviews(
      { "clankers - Steering": "https://sbx-old8000.arena.site/" },
      [{ url: "https://sbx-steering8000.arena.site/", name: "clankers - Steering" }]
    );
    assert.deepEqual(
      JSON.parse(JSON.stringify(reconciled)),
      {
        byName: { "clankers - Steering": "https://sbx-steering8000.arena.site/" },
        invalidated: ["https://sbx-old8000.arena.site/"],
      },
      "invalidates the previous preview URL when a new URL arrives for the same preview name"
    );
    const makePollRow = (stderrText) => {
      const pres = [{ textContent: "$ arena-preview poll" }];
      if (stderrText) {
        pres.push({ textContent: stderrText });
      }
      return {
        getAttribute: () => "",
        querySelector: (sel) => (sel === "pre" ? pres[0] : null),
        querySelectorAll: (sel) => (sel === "pre" ? pres : []),
      };
    };
    assert.equal(checks.tabTitle.emojiForRow(makePollRow("")), "\uD83D\uDCA4");
    assert.equal(
      checks.tabTitle.emojiForRow(
        makePollRow(
          "poll max 1799 s; bash timeout 1800 s.\nrun suite-readme-shot running 39s\n"
        )
      ),
      checks.tabTitle.BASH_EMOJI
    );
    assert.equal(
      checks.openSteering.PREVIEW_DRAWER_SELECTOR,
      "body > div:nth-child(4) > div > main > div > div > div.absolute.bottom-0.end-0.top-0.z-10.overflow-clip > div"
    );
    assert.equal(checks.openSteering.PREVIEW_DRAWER_WIDTH, "1398px");
    let drawerWidth = "720px";
    let drawerPriority = "";
    const drawerNode = {
      style: {
        getPropertyValue(prop) {
          return prop === "width" ? drawerWidth : "";
        },
        getPropertyPriority(prop) {
          return prop === "width" ? drawerPriority : "";
        },
        setProperty(prop, val, priority) {
          if (prop === "width") {
            drawerWidth = val;
            drawerPriority = priority || "";
          }
        },
      },
    };
    const drawerDoc = {
      querySelector(sel) {
        return sel === checks.openSteering.PREVIEW_DRAWER_SELECTOR ? drawerNode : null;
      },
    };
    assert.equal(checks.openSteering.findPreviewDrawer(drawerDoc), drawerNode);
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(drawerDoc), true);
    assert.equal(drawerWidth, "1398px");
    assert.equal(drawerPriority, "important");
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(drawerDoc), false);

    function makeStyleBox(initialProp, initialVal) {
      const props = new Map([[initialProp, { val: initialVal, priority: "" }]]);
      return {
        props,
        style: {
          getPropertyValue(prop) {
            return props.has(prop) ? props.get(prop).val : "";
          },
          getPropertyPriority(prop) {
            return props.has(prop) ? props.get(prop).priority : "";
          },
          setProperty(prop, val, priority) {
            props.set(prop, { val: String(val || ""), priority: String(priority || "") });
          },
        },
      };
    }
    let drawerOpen = true;
    const fullDrawer = makeStyleBox("width", "680px");
    const headerBox = makeStyleBox("right", "680px");
    const transcriptBox = makeStyleBox("padding-right", "680px");
    const composerBox = makeStyleBox("padding-right", "680px");
    const mainColNode = {
      querySelector(sel) {
        if (sel.includes("Collapse workspace sidebar")) {
          return drawerOpen ? {} : null;
        }
        if (sel.includes("Expand workspace sidebar") || sel.includes("Open workspace")) {
          return drawerOpen ? null : {};
        }
        if (sel === "div.absolute.start-0.top-0.z-20") return headerBox;
        if (sel.includes('[data-perf-target="transcript"]')) return transcriptBox;
        if (sel === "div.flex.min-h-0.flex-1.flex-col > div.shrink-0") return composerBox;
        return null;
      },
    };
    const fullDoc = {
      querySelector(sel) {
        if (sel === checks.openSteering.PREVIEW_DRAWER_SELECTOR) return fullDrawer;
        if (sel === checks.openSteering.PREVIEW_MAIN_SELECTOR) return mainColNode;
        return null;
      },
    };
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(fullDoc), true);
    assert.equal(fullDrawer.style.getPropertyValue("width"), "1398px");
    assert.equal(headerBox.style.getPropertyValue("right"), "1398px");
    assert.equal(transcriptBox.style.getPropertyValue("padding-right"), "1398px");
    assert.equal(composerBox.style.getPropertyValue("padding-right"), "1398px");
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(fullDoc), false);
    drawerOpen = false;
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(fullDoc), true);
    assert.equal(fullDrawer.style.getPropertyValue("width"), "0px");
    assert.equal(headerBox.style.getPropertyValue("right"), "0px");
    assert.equal(transcriptBox.style.getPropertyValue("padding-right"), "0px");
    assert.equal(composerBox.style.getPropertyValue("padding-right"), "0px");
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(fullDoc), false);

    let previewOpenInSidebar = true;
    const outerDrawerBox = makeStyleBox("width", "1153px");
    const innerDrawerBox = makeStyleBox("width", "1153px");
    innerDrawerBox.parentElement = outerDrawerBox;
    innerDrawerBox.querySelector = function (sel) {
      if (sel.includes("Close preview") || sel.includes("App preview")) {
        return previewOpenInSidebar ? {} : null;
      }
      if (sel.includes("Workspace card views")) {
        return previewOpenInSidebar ? null : {};
      }
      return null;
    };
    const transcriptMsgCol = {
      classList: {
        contains(cls) {
          return cls === "max-w-3xl" || cls === "shrink-0";
        },
      },
      parentElement: {
        getAttribute(attr) {
          return attr === "role" ? "log" : "";
        },
      },
      style: {
        val: "1398px",
        priority: "important",
        getPropertyValue(prop) {
          return prop === "padding-right" ? this.val : "";
        },
        getPropertyPriority(prop) {
          return prop === "padding-right" ? this.priority : "";
        },
        setProperty(prop, v, p) {
          if (prop === "padding-right") {
            this.val = v;
            this.priority = p || "";
          }
        },
        removeProperty(prop) {
          if (prop === "padding-right") {
            this.val = "";
            this.priority = "";
          }
        },
      },
    };
    const realHeaderBox = makeStyleBox("right", "1153px");
    const realTranscriptBox = makeStyleBox("padding-right", "1153px");
    const realComposerBox = makeStyleBox("padding-right", "1153px");
    const realMainCol = {
      querySelector(sel) {
        if (sel.includes("Collapse workspace sidebar")) return {};
        if (sel === "div.absolute.start-0.top-0.z-20") return realHeaderBox;
        if (sel.includes('[data-perf-target="transcript"]')) return realTranscriptBox;
        return null;
      },
      querySelectorAll(sel) {
        if (sel === "div.flex.min-h-0.flex-1.flex-col > div.shrink-0") {
          return [transcriptMsgCol, realComposerBox];
        }
        return [];
      },
    };
    const realDoc = {
      querySelector(sel) {
        if (sel === checks.openSteering.PREVIEW_DRAWER_SELECTOR) return innerDrawerBox;
        if (sel === checks.openSteering.PREVIEW_MAIN_SELECTOR) return realMainCol;
        return null;
      },
    };
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(realDoc), true);
    assert.equal(outerDrawerBox.style.getPropertyValue("width"), "1398px");
    assert.equal(innerDrawerBox.style.getPropertyValue("width"), "1398px");
    assert.equal(realHeaderBox.style.getPropertyValue("right"), "1398px");
    assert.equal(realTranscriptBox.style.getPropertyValue("padding-right"), "1398px");
    assert.equal(realComposerBox.style.getPropertyValue("padding-right"), "1398px");
    assert.equal(
      transcriptMsgCol.style.getPropertyValue("padding-right"),
      "",
      "transcript messages column (max-w-3xl) must never receive drawer padding-right",
    );
    previewOpenInSidebar = false;
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(realDoc), true);
    assert.equal(outerDrawerBox.style.getPropertyValue("width"), "256px");
    assert.equal(innerDrawerBox.style.getPropertyValue("width"), "256px");
    assert.equal(realHeaderBox.style.getPropertyValue("right"), "256px");
    assert.equal(realTranscriptBox.style.getPropertyValue("padding-right"), "256px");
    assert.equal(realComposerBox.style.getPropertyValue("padding-right"), "256px");
    assert.equal(
      checks.openSteering.enforcePreviewDrawerWidth(realDoc),
      false,
      "second closed-drawer pass must not mutate styles again",
    );
    previewOpenInSidebar = true;
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(realDoc), true);
    checkContext.GM_setValue("clankers-arena-preview-drawer-lock", false);
    assert.equal(checks.openSteering.enforcePreviewDrawerWidth(realDoc), true);
    assert.equal(
      checks.openSteering.enforcePreviewDrawerWidth(realDoc),
      false,
      "second unlocked-drawer pass must not mutate styles again (prevents MutationObserver loop)",
    );
    checkContext.GM_setValue("clankers-arena-preview-drawer-lock", true);

    let styleTextWrites = 0;
    let styleAttrWrites = 0;
    let storedCss = "";
    const styleEl = {
      id: "",
      setAttribute() {
        styleAttrWrites += 1;
      },
      get textContent() {
        return storedCss;
      },
      set textContent(val) {
        styleTextWrites += 1;
        storedCss = String(val || "");
      },
    };
    let headStyle = null;
    const styleDoc = {
      head: {
        appendChild(node) {
          headStyle = node;
        },
      },
      createElement() {
        return styleEl;
      },
      getElementById(id) {
        return id === "clankers-preview-drawer-style" ? headStyle : null;
      },
    };
    assert.equal(typeof checks.openSteering.ensurePreviewDrawerStyle, "function");
    checks.openSteering.ensurePreviewDrawerStyle(styleDoc);
    assert.equal(styleTextWrites, 1, "first ensurePreviewDrawerStyle writes CSS once");
    checks.openSteering.ensurePreviewDrawerStyle(styleDoc);
    assert.equal(
      styleTextWrites,
      1,
      "second ensurePreviewDrawerStyle must not rewrite textContent when CSS is unchanged",
    );
    assert.equal(
      styleAttrWrites,
      1,
      "second ensurePreviewDrawerStyle must not rewrite attributes when style node already exists",
    );


  });
}

{
    const { test } = require("node:test");

    test("normalizeBoard, boardMaterialSignature, and scopeBoardForTarget isolate unopted and cross-repo sessions without BOARD_KEY", () => {
      const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
      assert.equal(source.includes("clankers_global_board_v1"), false, "arena.user.js removes BOARD_KEY storage key");
      assert.equal(source.includes("GM_addValueChangeListener"), false, "arena.user.js removes GM_addValueChangeListener");
      const checkBox = { globalThis: {} };
      checkBox.globalThis = checkBox;
      vm.runInNewContext(source, checkBox, { filename: "arena.user.js" });
      const boardApi = checkBox.CLANKERS_CHECKS.board;
      assert.equal(boardApi.BOARD_KEY, undefined);
      assert.equal(boardApi.mergePreviewBoard, undefined);
      assert.equal(boardApi.applyBoardAction, undefined);
      const baseBoard = boardApi.normalizeBoard({
        multi_repo: true,
        linked_repos: ["other-repo"],
        allowed_sessions: ["alpha111-clankers", "beta2222-clankers"],
        main_session_id: "alpha111-clankers",
        worker_ids: { "beta2222-clankers": "beta" },
        sessions: [
          {
            branch: "alpha111-clankers",
            repo: "clankers",
            status: "active",
            polling: false,
            updated_at: "2026-10-27T02:00:00Z",
            agent_seen_at: "2026-10-27T02:00:00Z",
          },
          {
            branch: "beta2222-clankers",
            repo: "clankers",
            status: "polling",
            polling: true,
            updated_at: "top-corrupted-wake-id",
            polling_since: "2026-10-27T01:59:00Z",
          },
        ],
        entries: [
          {
            id: "p11111",
            branch: "alpha111-clankers",
            to: "beta2222-clankers",
            at: "2026-10-27T02:01:00Z",
            payload: { text: "hello beta" },
          },
        ],
        wakes: { "beta2222-clankers": "p11111" },
      });

      const betaBefore = baseBoard.sessions.find(s => s.branch === "beta2222-clankers");
      assert.equal(betaBefore.updated_at, "", "corrupted non-ISO updated_at string is stripped by normalizeBoard");

      // boardMaterialSignature ignores updated_at churn and tracks agent_call_ended_at:
      const sigA = boardApi.boardMaterialSignature({
        allowed_sessions: ["alpha111-clankers", "beta2222-clankers"],
        main_session_id: "alpha111-clankers",
        sessions: [
          { branch: "alpha111-clankers", repo: "clankers", updated_at: "2026-10-27T03:00:00Z", agent_call_ended_at: "2026-10-27T03:00:00Z" },
        ],
      });
      const sigB = boardApi.boardMaterialSignature({
        allowed_sessions: ["alpha111-clankers", "beta2222-clankers"],
        main_session_id: "alpha111-clankers",
        sessions: [
          { branch: "alpha111-clankers", repo: "clankers", updated_at: "2026-10-27T03:00:05Z", agent_call_ended_at: "2026-10-27T03:00:00Z" },
        ],
      });
      const sigC = boardApi.boardMaterialSignature({
        allowed_sessions: ["alpha111-clankers", "beta2222-clankers"],
        main_session_id: "alpha111-clankers",
        sessions: [
          { branch: "alpha111-clankers", repo: "clankers", updated_at: "2026-10-27T03:00:05Z", agent_call_ended_at: "2026-10-27T03:00:05Z", calls_since_message: 3, agent_seen_at: "2026-10-27T03:00:05Z" },
        ],
      });
      const sigD = boardApi.boardMaterialSignature({
        allowed_sessions: ["alpha111-clankers", "beta2222-clankers"],
        main_session_id: "alpha111-clankers",
        sessions: [
          { branch: "alpha111-clankers", repo: "clankers", updated_at: "2026-10-27T03:00:05Z", turn_ended_at: "2026-10-27T03:00:05Z" },
        ],
      });
      assert.equal(sigA, sigB, "boardMaterialSignature ignores synthetic updated_at churn");
      assert.equal(sigB, sigC, "boardMaterialSignature ignores non-material heartbeat call counters and timestamps");
      assert.notEqual(sigB, sigD, "boardMaterialSignature changes when turn_ended_at advances");

      // normalizeBoard strips unpublished worker_reports via report_ops:
      const withUnpubOp = boardApi.normalizeBoard({
        allowed_sessions: ["alpha111-clankers", "beta2222-clankers"],
        main_session_id: "alpha111-clankers",
        worker_reports: {
          "beta2222-clankers": [
            { id: "stale-worker-rep", title: "Old", updated_at: "2026-10-27T03:00:00", published_at: "2026-10-27T03:00:00", answered: false, needs_answer: true },
          ],
        },
        report_ops: [
          { id: "rop-unpub1", target: "beta2222-clankers", op: "unpublish", report_id: "stale-worker-rep", from_owner: true, at: "2026-10-27T03:05:00" },
        ],
        sessions: [{ branch: "alpha111-clankers", repo: "clankers", updated_at: "2026-10-27T03:05:00Z" }],
      });
      assert.deepEqual(Array.from(withUnpubOp.worker_reports["beta2222-clankers"] || []), [], "report_ops unpublish strips stale worker report immediately");

      // scopeBoardForTarget strips board entries/queues for unopted chats and prunes unopted queues for opted-in chats:
      const scopedUnopted = boardApi.scopeBoardForTarget(
        {
          allowed_sessions: ["alpha111-clankers", "beta2222-clankers"],
          main_session_id: "alpha111-clankers",
          entries: [{ id: "p54321", branch: "alpha111-clankers", payload: { text: "secret" } }],
          worker_tasks: {
            "alpha111-clankers": [{ id: "t1", title: "T1", status: "upcoming" }],
            "unopted99-daedalus": [{ id: "t2", title: "T2", status: "upcoming" }],
          },
          worker_reports: {
            "beta2222-clankers": [{ id: "r1", title: "R1" }],
            "unopted99-daedalus": [{ id: "own-r", title: "Own" }],
          },
          wakes: { "unopted99-daedalus": "w1" },
        },
        "unopted99-daedalus",
        "daedalus",
      );
      assert.deepEqual(Array.from(scopedUnopted.entries), [], "unopted chat receives empty entries");
      assert.deepEqual(Object.keys(scopedUnopted.worker_tasks), [], "unopted chat receives empty worker_tasks");
      assert.deepEqual(Object.keys(scopedUnopted.worker_reports), ["unopted99-daedalus"], "unopted chat sees only its own report metadata");
      const scopedOpted = boardApi.scopeBoardForTarget(
        {
          allowed_sessions: ["alpha111-clankers"],
          main_session_id: "alpha111-clankers",
          worker_tasks: { "unopted99-daedalus": [{ id: "t2", title: "T2", status: "upcoming" }] },
          worker_reports: { "unopted99-daedalus": [{ id: "own-r", title: "Own" }] },
        },
        "alpha111-clankers",
        "clankers",
      );
      assert.deepEqual(Object.keys(scopedOpted.worker_tasks), [], "opted-in chat strips unopted worker_tasks");
      assert.deepEqual(Object.keys(scopedOpted.worker_reports), [], "opted-in chat strips unopted worker_reports");

      const allowOutranksRemoval = boardApi.normalizeBoard({
        main_session_id: "alpha111-clankers",
        allowed_sessions: ["alpha111-clankers", "beta2222-clankers"],
        removed_sessions: ["alpha111-clankers"],
        sessions: [
          { branch: "alpha111-clankers", repo: "clankers", updated_at: "2026-10-27T03:00:00Z" },
        ],
      });
      assert.ok(allowOutranksRemoval.allowed_sessions.includes("alpha111-clankers"), "normalizeBoard keeps allowlisted session over stale removed_sessions");
      assert.ok(!allowOutranksRemoval.removed_sessions.includes("alpha111-clankers"), "normalizeBoard drops allowlisted session from removed_sessions");
      assert.equal(allowOutranksRemoval.main_session_id, "alpha111-clankers");
    });


    test("skill HTTP calls to sbx-*.arena.site apply randomized jitter while non-skill URLs run immediately", async () => {
      const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
      const scheduled = [];
      const wireCalls = [];
      const gmStore = new Map([["clankers-arena-http-jitter-ms", 15000]]);
      let fakeNowMs = Date.now();
      const checkBox = {
        globalThis: {},
        Date: Object.assign(function (...args) { return new Date(...args); }, {
          now: () => fakeNowMs,
          parse: Date.parse,
        }),
        setTimeout: (fn, ms) => {
          scheduled.push({ fn, ms });
          return scheduled.length;
        },
        clearTimeout: () => {},
        GM_getValue: (key, fallback) => (gmStore.has(key) ? gmStore.get(key) : fallback),
        GM_setValue: (key, val) => gmStore.set(key, val),
        GM_xmlhttpRequest: (req) => {
          wireCalls.push({ method: req.method, url: req.url });
          if (req.onload) req.onload({ status: 200, responseText: '{"ok":true}' });
        },
      };
      checkBox.globalThis = checkBox;
      checkBox.CLANKERS_CHECKS = {};
      vm.runInNewContext(source, checkBox, { filename: "arena.user.js" });

      const timersApi = checkBox.CLANKERS_CHECKS.timers;
      assert.equal(timersApi.isSkillPreviewUrl("https://sbx-abc123.arena.site/api/board"), true);
      assert.equal(timersApi.isSkillPreviewUrl("https://preview.example/api/key"), false);

      let keyDoneStatus = null;
      checkBox.CLANKERS_CHECKS.promptFill.requestJson(
        "POST",
        "https://sbx-abc123.arena.site/api/key",
        { key: "k", host: "h" },
        (status) => { keyDoneStatus = status; },
      );
      assert.equal(wireCalls.length, 1, "first POST to sbx-*.arena.site fires immediately with no artificial wait");
      assert.equal(keyDoneStatus, 200);

      const statePromise = timersApi.stateJson("https://sbx-abc123.arena.site/api/board");
      let interruptDoneStatus = null;
      checkBox.CLANKERS_CHECKS.openSteering.sendSteeringInterrupt(
        "https://sbx-abc123.arena.site/api/agent-interrupt",
        { note: "test" },
        (status) => { interruptDoneStatus = status; },
      );
      assert.equal(wireCalls.length, 1, "GET jitter and burst POST pacing wait on scheduled timers");
      assert.equal(scheduled.length, 2, "GET schedules jitter and burst POST schedules pacing from lastPost");
      assert.ok(
        scheduled[0].ms >= 0 && scheduled[0].ms <= timersApi.SKILL_HTTP_JITTER_MAX_MS,
        `expected GET jitter delay inside 0..${timersApi.SKILL_HTTP_JITTER_MAX_MS}ms, got ${scheduled[0].ms}`,
      );
      assert.ok(
        scheduled[1].ms >= timersApi.SKILL_POST_INTERVAL_MS &&
          scheduled[1].ms <= timersApi.SKILL_POST_INTERVAL_MS + timersApi.SKILL_HTTP_JITTER_MAX_MS,
        `expected burst POST delay inside ${timersApi.SKILL_POST_INTERVAL_MS}..${timersApi.SKILL_POST_INTERVAL_MS + timersApi.SKILL_HTTP_JITTER_MAX_MS}ms, got ${scheduled[1].ms}`,
      );
      while (scheduled.length) {
        scheduled.shift().fn();
      }
      const stateRes = await statePromise;
      assert.equal(stateRes.status, 200);
      assert.equal(interruptDoneStatus, 200);
      assert.equal(wireCalls.length, 3, "all scheduled sbx-*.arena.site requests fire once timers drain");

      // Once interval + jitter elapses since lastPost, the next POST fires immediately again.
      fakeNowMs += timersApi.SKILL_POST_INTERVAL_MS * 3 + timersApi.SKILL_HTTP_JITTER_MAX_MS * 3;
      const immediatePostRes = await timersApi.stateJson(
        "https://sbx-abc123.arena.site/api/board",
        { action: "sync" },
      );
      assert.equal(scheduled.length, 0, "POST after elapsed interval + jitter does not schedule a timer");
      assert.equal(immediatePostRes.status, 200);
      assert.equal(wireCalls.length, 4, "POST after elapsed interval + jitter fires immediately");

      wireCalls.length = 0;
      checkBox.CLANKERS_CHECKS.promptFill.requestJson(
        "POST",
        "https://preview-proxy.example.ts.net/pwa/recent",
        { url: "https://sbx-abc123.arena.site/", name: "clankers - Steering" },
        () => {},
        false,
      );
      assert.equal(scheduled.length, 0, "non-sbx URLs do not schedule extra skill HTTP jitter");
      assert.equal(wireCalls.length, 1, "non-sbx URL fires immediately");

      const boardCheck = checkBox.CLANKERS_CHECKS.board;
      const nowEpochMs = fakeNowMs;
      const expiredIso = new Date(nowEpochMs - (boardCheck.BOARD_SESSION_TTL_SECONDS + 30) * 1000).toISOString();
      const freshIso = new Date(nowEpochMs - Math.floor(boardCheck.BOARD_SESSION_TTL_SECONDS / 3) * 1000).toISOString();
      const normalizedMixed = boardCheck.normalizeBoard({
        multi_repo: false,
        allowed_sessions: ["alpha111-clankers", "opt33333-otherrepo"],
        main_session_id: "alpha111-clankers",
        sessions: [
          { branch: "alpha111-clankers", repo: "clankers", updated_at: freshIso },
          { branch: "dead9999-daedalus", repo: "daedalus", status: "disconnected", disconnected: true, updated_at: expiredIso },
          { branch: "fresh888-clankers", repo: "clankers", status: "disconnected", disconnected: true, updated_at: freshIso },
          { branch: "opt33333-otherrepo", repo: "otherrepo", status: "disconnected", disconnected: true, updated_at: expiredIso },
        ],
      });
      const normIds = normalizedMixed.sessions.map((row) => row.branch);
      assert.ok(!normIds.includes("dead9999-daedalus"), "expired unopted disconnected row is pruned");
      assert.ok(normIds.includes("fresh888-clankers"), "fresh unopted disconnected row stays within TTL");
      assert.ok(normIds.includes("opt33333-otherrepo"), "opted disconnected row is retained");
      const scopedClankers = boardCheck.scopeBoardForTarget(normalizedMixed, "alpha111-clankers", "clankers");
      const scopedIds = scopedClankers.sessions.map((row) => row.branch);
      assert.ok(!scopedIds.includes("opt33333-otherrepo"), "unlinked cross-repo row hides when multi_repo is false");
      assert.ok(scopedClankers.sessions.length < normalizedMixed.sessions.length);
      assert.ok(scopedClankers.known_repos.includes("otherrepo"));
      assert.ok(!scopedClankers.known_repos.includes("daedalus"));
    });

    test("DOM caches use WeakMap, state caches stay bounded without storing core in pendingKey, and observers coalesce via rAF", async () => {
      const source = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
      assert.match(source, /var\s+spacerStyles\s*=\s*new\s+WeakMap\(\)/);
      assert.match(source, /var\s+editorStates\s*=\s*new\s+WeakMap\(\)/);
      assert.match(source, /function\s+setBoundedMap\(/);
      assert.match(source, /function\s+readPendingReceipt\(/);
      assert.match(source, /titleMutationFrame\s*=\s*requestAnimationFrame\(/);
      assert.match(source, /mutationFrame\s*=\s*requestAnimationFrame\(/);
      assert.equal(/[\u2013\u2014]/.test(source), false, "arena.user.js contains no en-dash or em-dash");
    });




  }

function checkArenaLogging(api, menus) {
  assert.equal(typeof api.setLogLevel, "function");
  assert.equal(api.getLogLevel(), "info");
  const lines = [];
  const original = { log: console.log, warn: console.warn, error: console.error };
  for (const method of Object.keys(original)) {
    console[method] = (...args) => lines.push({ method, text: JSON.stringify(args) });
  }
  try {
    const fields = {
      count: 2, repo: "private-repo", filename: "private.ndjson",
      key: "secret-key", message: "secret-message", url: "secret-url", error: "raw-error",
    };
    api.logEvent("state", "saved", fields);
    api.logEvent("state", "saved", fields);
    assert.equal(lines.length, 2, "identical events must remain visible");
    assert.match(lines[0].text, /\[NemoUtils\]\[state\]\[info\] saved/);
    assert.match(lines[0].text, /count/);
    assert.doesNotMatch(lines[0].text, /private|secret|raw-error/);
    api.logEvent("state", "compare", fields, "debug");
    assert.equal(lines.length, 2, "debug must be off by default");
    assert.equal(api.setLogLevel("debug"), true);
    api.logEvent("state", "compare", fields, "debug");
    assert.match(lines.at(-1).text, /private-repo/);
    assert.match(lines.at(-1).text, /private.ndjson/);
    assert.doesNotMatch(lines.at(-1).text, /secret|raw-error/);
    const safeCount = lines.length;
    assert.equal(api.logEvent("state", "secret-message", fields), false);
    assert.equal(lines.length, safeCount, "unknown event names must not reach the console");
    api.logEvent("state", "saved", Object.create({ repo: "secret-message", filename: "secret-key", count: 666 }));
    assert.doesNotMatch(lines.at(-1).text, /secret|666/);
    api.logEvent("state", "saved", { count: "secret-message", code: "raw-error" });
    assert.doesNotMatch(lines.at(-1).text, /secret|raw-error/);
    assert.equal(api.setLogLevel("warn"), true);
    const count = lines.length;
    api.logEvent("state", "saved", fields);
    api.logEvent("state", "failed", fields, "warn");
    api.logEvent("state", "failed", fields, "error");
    assert.equal(lines.length, count + 2);
    assert.equal(lines.at(-2).method, "warn");
    assert.equal(lines.at(-1).method, "error");
    assert.equal(api.setLogLevel("invalid"), false);
    assert.equal(api.getLogLevel(), "warn");
    api.setLogLevel("info");
    let ran = false;
    api.menuItem([], "State - secret-message", () => { ran = true; });
    menus.findLast((entry) => entry.label === "State - secret-message").run();
    assert.equal(ran, true);
    assert.doesNotMatch(lines.at(-1).text, /secret-message/);
    api.registerLogMenu();
    menus.findLast((entry) => entry.label.startsWith("Userscript - log level")).run();
    assert.equal(api.getLogLevel(), "debug");
    for (const method of Object.keys(original)) console[method] = () => { throw Error("closed"); };
    assert.doesNotThrow(() => api.logEvent("state", "failed", fields, "error"));
  } finally {
    Object.assign(console, original);
    api.setLogLevel("info");
  }
  console.log("ok arena logging");
}

function checkTranscriptAlerts(api) {
  assert.ok(api, "the independent alert submodule must be exposed");
  const selector = '[role="alert"][class~="border-red-500/30"][class~="bg-red-500/10"]';
  assert.equal(api.ALERT_SELECTOR, selector);
  function alert(value = "", priority = "", visible = true) {
    return {
      isConnected: true,
      target: true,
      hidden: false,
      getClientRects() { return visible ? [{}] : []; },
      matches(s) { assert.equal(s, selector); return this.target; },
      style: {
        getPropertyValue() { return value; },
        getPropertyPriority() { return priority; },
        setProperty(key, next, rank) { assert.equal(key, "display"); value = next; priority = rank; },
        removeProperty(key) { assert.equal(key, "display"); value = ""; priority = ""; },
      },
    };
  }
  const first = alert("flex", "important");
  const priorHidden = alert("none", "", false);
  const unrelated = alert(); unrelated.target = false;
  let nodes = [first, priorHidden, unrelated];
  const sync = api.alertVisibility({
    querySelectorAll(s) { assert.equal(s, selector); return nodes.filter((n) => n.target); },
  });
  sync(false);
  assert.equal(first.style.getPropertyValue("display"), "flex");
  sync(true);
  assert.equal(first.style.getPropertyValue("display"), "none");
  assert.equal(first.style.getPropertyPriority("display"), "important");
  assert.equal(priorHidden.style.getPropertyPriority("display"), "");
  assert.equal(unrelated.style.getPropertyValue("display"), "");
  const later = alert(); nodes.push(later);
  first.textContent = "A different error message";
  sync(true); sync(true);
  assert.equal(later.style.getPropertyValue("display"), "none");
  sync(false);
  assert.equal(first.style.getPropertyValue("display"), "flex");
  assert.equal(first.style.getPropertyPriority("display"), "important");
  assert.equal(later.style.getPropertyValue("display"), "");
  assert.equal(priorHidden.style.getPropertyValue("display"), "none");
  const externalHidden = alert("inline", "");
  nodes.push(externalHidden);
  sync(true);
  externalHidden.style.setProperty("display", "none", "");
  sync(false);
  assert.equal(externalHidden.style.getPropertyValue("display"), "none");
  assert.equal(externalHidden.style.getPropertyPriority("display"), "");
  nodes = nodes.filter((n) => n !== externalHidden);
  sync(true);
  later.style.setProperty("display", "grid", "");
  first.target = false;
  sync(true);
  assert.equal(first.style.getPropertyValue("display"), "flex");
  sync(false);
  assert.equal(later.style.getPropertyValue("display"), "grid", "preserve an external style change");
  sync(true); later.isConnected = false; sync(true);
  assert.equal(later.style.getPropertyValue("display"), "grid");
}

function checkPromptFill(api) {
  var isComposerUrl = api.isComposerUrl;
  var slugFromOwnerRepo = api.slugFromOwnerRepo;
  var promptForSlug = api.promptForSlug;
  var shouldWrite = api.shouldWrite;
  var ARENA_MD_URL = api.ARENA_MD_URL;
  var previewBase = api.previewBase;
  var keyPostUrl = api.keyPostUrl;
  var keyPostDue = api.keyPostDue;
  var PREVIEW_FRAME_TITLE = api.PREVIEW_FRAME_TITLE;
  var PROMPT_FILL_URL = api.PROMPT_FILL_URL;
  var SURVEY_QUESTIONS_URL = api.SURVEY_QUESTIONS_URL;
  assert.equal(PROMPT_FILL_URL,
    "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/userscripts/arena-prompt-fill.txt");
  assert.equal(SURVEY_QUESTIONS_URL,
    "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/skills/arena-steering/references/survey-questions.txt");
  var promptFillText = fs.readFileSync(
    path.join(__dirname, "../../userscripts/arena-prompt-fill.txt"), "utf8").trimEnd();
  var surveyQuestionsText = fs.readFileSync(
    path.join(__dirname, "../../skills/arena-steering/references/survey-questions.txt"), "utf8").trimEnd();
  var promptSource = fs.readFileSync(path.join(__dirname, "../../userscripts/arena.user.js"), "utf8");
  assert.equal(promptSource.includes("TEMPLATE_TAIL"), false);
  assert.equal(promptForSlug("clankers", ""), null);
  assert.equal(promptForSlug("clankers", promptFillText), null);
  var prompt = promptForSlug("clankers", promptFillText, null, surveyQuestionsText);
  var promptWithRules = promptForSlug("clankers", promptFillText, "# Rules\n", surveyQuestionsText);

  function frames(rows) {
    return {
      querySelectorAll: function (selector) {
        if (selector !== "iframe[title]") return [];
        return rows.map(function (row) {
          return {
            getAttribute: function () {
              return row[0];
            },
            src: row[1],
          };
        });
      },
    };
  }

  var cases = [
    [isComposerUrl("https://arena.ai/agent"), true],
    [isComposerUrl("https://www.arena.ai/agent"), true],
    [isComposerUrl("https://arena.ai/agent?x=1"), true],
    [isComposerUrl("https://arena.ai/agent#x"), true],
    [isComposerUrl("https://arena.ai/agent/"), true],
    [isComposerUrl("https://arena.ai/agent//"), true],
    [isComposerUrl("https://arena.ai/agent/foo"), false],
    [isComposerUrl("https://arena.ai/agent/foo/"), false],
    [isComposerUrl("https://other.example/agent"), false],
    [slugFromOwnerRepo("nemoe7/clankers"), "clankers"],
    [slugFromOwnerRepo("  org/repo  "), "repo"],
    [slugFromOwnerRepo("main"), null],
    [slugFromOwnerRepo("a/"), null],
    [slugFromOwnerRepo("/b"), null],
    [slugFromOwnerRepo("a/b/c"), null],
    // Repo name leads fetched template. Rules file follows when available.
    [prompt.split("\n")[0],
      "clankers read ARENA.md AGENTS.md in full before your first edit, and follow both."],
    [prompt.includes("{{SURVEY_QUESTION:"), false],
    [prompt.indexOf("here is ARENA.md"), -1],
    [prompt.indexOf("Pareto"), -1],
    [ARENA_MD_URL, "https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/rules/ARENA.md"],
    [promptWithRules.indexOf("here is ARENA.md:\n# Rules\n") > 0, true],
    [shouldWrite("", "clankers", null, null), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md", "clankers", null, null), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md\nExpect screenshots to be sent via the steering channel.", "clankers", null, null), true],
    [shouldWrite("clankers read AGENTS.md ARENA.md", "clankers", null, null), true],
    [shouldWrite(prompt, "clankers", null, null), true],
    [shouldWrite("draft", "clankers", null, null), false],
    [shouldWrite("clankers read ARENA.md AGENTS.md", "other", "clankers", null), true],
    [shouldWrite("draft", "clankers", "clankers", null), false],
    [shouldWrite(promptForSlug("other", promptFillText, null, surveyQuestionsText), "clankers", "other", "other"), true],
    // One fill per repo per page: the observer sees no second write. This holds even when the
    // editor hands the text back with different whitespace or the send clears it.
    [shouldWrite(prompt, "clankers", "clankers", "clankers"), false],
    [shouldWrite("clankers read ARENA.md AGENTS.md in full before your first edit, and follow both.\n", "clankers", "clankers", "clankers"), false],
    [shouldWrite("", "clankers", "clankers", "clankers"), false],
    [shouldWrite("draft", "clankers", "clankers", "clankers"), false],
    // Composer carries only prompt fill. Proxy rides preview.
    [prompt.indexOf("http"), -1],
    [PREVIEW_FRAME_TITLE, "App preview on port 8000"],
    [previewBase(frames([["App preview on port 8000", "https://sbx.example/"]])),
      "https://sbx.example"],
    [previewBase(frames([["Website", "https://x.example/"], ["App preview on port 8000", "https://sbx.example"]]))
      ? "https://sbx.example" : null, "https://sbx.example"],
    [previewBase(frames([["Website", "https://x.example/"]])) , null],
    [previewBase(frames([["App preview on port 8000", ""]])), null],
    [keyPostUrl("https://sbx.example"), "https://sbx.example/api/key"],
    // Key posts when frame appears, and each minute tick posts it again.
    [keyPostDue(null, null, true), false],
    [keyPostDue("https://sbx.example", null, false), true],
    [keyPostDue("https://sbx.example", "https://sbx.example", false), false],
    [keyPostDue("https://sbx.example", "https://sbx.example", true), true],
    // The older two-line fill is rebuilt once, without the rules text.
    [shouldWrite("clankers read ARENA.md AGENTS.md.\nExpect screenshots to be sent via the steering channel.", "clankers", "clankers", null), true],
    [shouldWrite("clankers read ARENA.md AGENTS.md.\nExpect screenshots to be sent via the steering channel.", "clankers", "clankers", "clankers"), false],
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
  console.log("ok prompt fill " + cases.length);
}

function checkOpenSteering(api) {
  function steeringRowText(rows, expectedSlug) {
    var buttons = rows.map(function (row) {
      return {
        textContent: row[0] + " " + row[1],
        getAttribute: function (name) {
          return name === "aria-label" && row[2] ? row[2] : null;
        },
        querySelectorAll: function (selector) {
          return selector === "span" ? [{ textContent: row[0] }, { textContent: row[1] }] : [];
        },
      };
    });
    var doc = {
      querySelectorAll: function () {
        return buttons;
      },
    };
    var found = findSteeringButton(doc, expectedSlug);
    return found ? found.textContent : null;
  }

  var isSessionUrl = api.isSessionUrl;
  var slugFromOwnerRepo = api.slugFromOwnerRepo;
  var steeringSlugFromLabel = api.steeringSlugFromLabel;
  var isSteeringLabel = api.isSteeringLabel;
  var isSteeringPort = api.isSteeringPort;
  var buttonMatchesSteering = api.buttonMatchesSteering;
  var findSteeringButton = api.findSteeringButton;
  var CLICK_DELAY_MS = api.CLICK_DELAY_MS;

  var cases = [
    [isSessionUrl("https://arena.ai/agent/foo"), true],
    [isSessionUrl("https://www.arena.ai/agent/foo/bar"), true],
    [isSessionUrl("https://arena.ai/agent/foo?x=1"), true],
    [isSessionUrl("https://arena.ai/agent"), false],
    [isSessionUrl("https://arena.ai/agent/"), false],
    [isSessionUrl("https://other.example/agent/foo"), false],
    [slugFromOwnerRepo("nemoe7/clankers"), "clankers"],
    [steeringSlugFromLabel("daedalus - Steering"), "daedalus"],
    [steeringSlugFromLabel("clankers - preview"), "clankers"],
    [steeringSlugFromLabel("clankers preview"), "clankers"],
    [steeringSlugFromLabel("arena"), null],
    [steeringSlugFromLabel("Steering"), null],
    [steeringSlugFromLabel("daedalus - Website"), null],
    [isSteeringLabel("CLANKERS - PREVIEW"), true],
    [isSteeringLabel("daedalus - Website"), false],
    [buttonMatchesSteering("CLANKERS - steering", ":8000", "clankers"), true],
    [buttonMatchesSteering("Steering", ":8000", "clankers"), true],
    [buttonMatchesSteering("daedalus - Steering", ":8000", "clankers"), false],
    [buttonMatchesSteering("clankers - STEERING", ":8001", "CLANKERS"), false],
    [buttonMatchesSteering("daedalus - Preview", ":8000", null), true],
    [buttonMatchesSteering("daedalus - Website", ":8000", null), false],
    [isSteeringPort(":8000"), true],
    [isSteeringPort("8000"), false],
    [steeringRowText([["Website", ":3000"], ["daedalus - Steering", ":8000"]], "clankers"),
      "daedalus - Steering :8000"],
    [steeringRowText([["clankers - Steering", ":8000"], ["daedalus - preview", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["Website", ":3000"], ["arena - preview", ":8000"]], "clankers"),
      "arena - preview :8000"],
    // A Start row is a transcript card. A click on one opens nothing, so it never counts.
    [steeringRowText([["Start clankers - Steering", ":8000"]], "clankers"), null],
    [steeringRowText([["Arena preview", ":8000", "Switch preview port"]], null), null],
    [steeringRowText([["Arena preview", ":8000", "Switch preview port"],
      ["clankers - Steering", ":8000"]], "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["Start clankers - Steering", ":8000"], ["daedalus - preview", ":8000"]],
      "clankers"), "daedalus - preview :8000"],
    // The running row wins over history cards, wherever they sit.
    [steeringRowText([["Start clankers - Steering", ":8000"], ["clankers - Steering", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["clankers - Steering", ":8000"], ["Start clankers - Steering", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["clankers - Steering", ":8000"], ["Start preview", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    // This project's running row outranks a newer row for another project. A nameless
    // running row outranks a named one for another project.
    [steeringRowText([["clankers - Steering", ":8000"], ["daedalus - preview", ":8000"]],
      "clankers"), "clankers - Steering :8000"],
    [steeringRowText([["Steering", ":8000"], ["daedalus - preview", ":8000"]], "clankers"),
      "Steering :8000"],
    // A renamed live row still wins, and it is the only running row here.
    [steeringRowText([["Start clankers - Steering", ":8000"],
      ["daedalus - preview", ":8000"], ["arena - preview", ":8000"]], "clankers"),
      "arena - preview :8000"],
    [CLICK_DELAY_MS, 1000],
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
  assert.equal(api.steeringLabelViolation("clankers - Steering :8000", "clankers"), null);
  assert.equal(api.steeringLabelViolation("clankers - Steering :8000", null), null);
  assert.equal(api.steeringLabelViolation("Start Preview server :8000", "clankers"), null);
  var violation = api.steeringLabelViolation("Preview server :8000", "clankers");
  assert.equal(violation.actual, "Preview server");
  assert.equal(violation.expected, "clankers - Steering");
  var payload = api.interruptPayloadForSteering("Preview server :8000", "clankers");
  assert.equal(payload.armed, true);
  assert.equal(payload.tab, "notes");
  assert.equal(payload.reason, "process-violation");
  assert.equal(payload.clause_file, "ARENA.md");
  assert.match(payload.note, /Preview server/);
  assert.match(payload.note, /clankers - Steering/);
  var sent = [];
  var violationDoc = {
    querySelectorAll: function (selector) {
      if (selector === 'button[type="button"]') {
        return [
          {
            textContent: "Preview server :8000",
            getAttribute: function () { return null; },
            querySelectorAll: function (sel) {
              return sel === "span"
                ? [{ textContent: "Preview server" }, { textContent: ":8000" }]
                : [];
            },
          },
        ];
      }
      if (selector === "iframe[title]") {
        return [
          {
            title: "App preview on port 8000",
            src: "https://sbx-port8000.arena.site/",
            getAttribute: function (name) {
              return name === "title" ? "App preview on port 8000" : null;
            },
          },
        ];
      }
      return [];
    },
  };
  api.resetFlaggedSteering();
  assert.equal(
    api.flagSteeringLabelViolation(violationDoc, "clankers", function (url, body, done) {
      sent.push({ url: url, body: body });
      done(200);
    }),
    true,
  );
  assert.equal(sent.length, 1);
  assert.equal(sent[0].url, "https://sbx-port8000.arena.site/api/agent-interrupt");
  assert.equal(sent[0].body.reason, "process-violation");
  assert.equal(sent[0].body.clause_file, "ARENA.md");
  assert.equal(
    api.flagSteeringLabelViolation(violationDoc, "clankers", function (url, body, done) {
      sent.push({ url: url, body: body });
      done(200);
    }),
    false,
  );
  assert.equal(sent.length, 1);
  console.log("ok open steering " + cases.length);
}

function checkAutoScrollToggle(api) {
  function hasToggleClass(classes, name) {
    return classes.split(" ").indexOf(name) !== -1;
  }

  var AUTO_TOGGLE_CLASS = api.AUTO_TOGGLE_CLASS;
  var autoToggleClasses = api.autoToggleClasses;
  var findComposerActionButton = api.findComposerActionButton;

  var stopBtn = {
    getAttribute: function (name) {
      return name === "aria-label" ? "Stop generating" : null;
    },
  };
  var sendBtn = {
    getAttribute: function (name) {
      return name === "aria-label" ? "Send message" : null;
    },
  };
  var submitBtn = {
    getAttribute: function (name) {
      return name === "type" ? "submit" : null;
    },
  };
  var injectedBtn = {
    getAttribute: function (name) {
      return name === "data-clankers-settings-toggle"
        ? "true"
        : name === "type"
          ? "submit"
          : null;
    },
  };
  var docWithStop = {
    querySelectorAll: function (sel) {
      return sel === "button[aria-label]" ? [sendBtn, stopBtn] : [sendBtn, stopBtn];
    },
  };
  var docWithSend = {
    querySelectorAll: function (sel) {
      return sel === "button[aria-label]" ? [sendBtn] : [sendBtn];
    },
  };
  var docWithSubmit = {
    querySelectorAll: function (sel) {
      return sel === "button[aria-label]" ? [] : [injectedBtn, submitBtn];
    },
  };

  var on = autoToggleClasses(true);
  var off = autoToggleClasses(false);
  var cases = [
    [hasToggleClass(on, "bg-surface-raised"), true],
    [hasToggleClass(on, "bg-transparent"), false],
    [hasToggleClass(off, "bg-transparent"), true],
    [hasToggleClass(off, "bg-surface-raised"), false],
    [hasToggleClass(on, "hover:bg-interactive-cta-active"), true],
    [hasToggleClass(off, "hover:bg-surface-raised"), true],
    [hasToggleClass(AUTO_TOGGLE_CLASS, "h-8"), true],
    [hasToggleClass(AUTO_TOGGLE_CLASS, "w-8"), true],
    [findComposerActionButton(docWithStop), stopBtn],
    [findComposerActionButton(docWithSend), sendBtn],
    [findComposerActionButton(docWithSubmit), submitBtn],
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
  console.log("ok transcript auto-scroll " + cases.length);
}

function checkTranscriptTrim(api) {
  var normalizePlan = api.normalizePlan;
  var planParts = api.planParts;
  var countLabel = api.countLabel;
  var messageRoots = api.messageRoots;
  var rowsOfRoot = api.rowsOfRoot;
  var trimPlan = api.trimPlan;
  var trimRows = api.trimRows;
  var isSettled = api.isSettled;
  var quietReady = api.quietReady;
  var ACTION_SELECTOR = api.ACTION_SELECTOR;
  var QUESTION_SELECTOR = api.QUESTION_SELECTOR;
  var MIN_ROWS = api.MIN_ROWS;
  var DEFAULT_ROWS = api.DEFAULT_ROWS;
  var DEFAULT_TRIM_CAP = api.DEFAULT_TRIM_CAP;

  function rows(count) {
    var list = [];
    var i;
    for (i = 0; i < count; i += 1) {
      var row = {
        parentElement: {},
        removed: false,
        textContent: "row",
        remove: function () {
          this.removed = true;
          this.parentElement = null;
        },
      };
      row.classList = {
        names: {},
        add: function (name) {
          this.names[name] = true;
        },
        contains: function (name) {
          return Boolean(this.names[name]);
        },
      };
      list.push(row);
    }
    return list;
  }
  function cleared(row) {
    return row.classList.contains("hidden") && row.textContent === "";
  }
  function actionContainer() {
    return {
      removed: false,
      parentElement: {},
      remove: function () {
        this.removed = true;
        this.parentElement = null;
      },
    };
  }
  var BOX = "div.flex.flex-col.gap-2";
  function rowBox(pageRows, nested) {
    var element = {
      children: pageRows,
      closest: function (selector) {
        return selector === BOX ? element : null;
      },
      parentElement: {
        closest: function (selector) {
          return selector === BOX ? nested || null : null;
        },
      },
    };
    return element;
  }
  function messageRoot(boxes, actions, connected) {
    actions = actions || [];
    var root = {
      isConnected: connected !== false,
      removed: false,
      hiddenClass: false,
      remove: function () {
        this.removed = true;
        this.parentElement = null;
      },
      querySelectorAll: function (selector) {
        if (selector === BOX) return boxes;
        return selector === ACTION_SELECTOR ? actions : [];
      },
    };
    root.classList = {
      add: function (name) {
        if (name === "hidden") root.hiddenClass = true;
      },
    };
    root.parentElement = { children: [root] };
    return root;
  }
  function logDoc(roots, withLog) {
    var log = {
      querySelectorAll: function (selector) {
        return selector === '[data-agent-transcript-message="true"]' ? roots : [];
      },
    };
    return {
      querySelectorAll: function (selector) {
        if (selector === '[role="log"]') return withLog ? [log] : [];
        if (selector === '[data-agent-transcript-message="true"]') return withLog ? [] : roots;
        return [];
      },
    };
  }
  var rootActions = [actionContainer(), actionContainer()];
  var rootRows = [rows(25), rows(25)];
  var rootNodes = [
    messageRoot([rowBox(rootRows[0])], [rootActions[0]]),
    messageRoot([rowBox(rootRows[1])], [rootActions[1]]),
  ];
  var rootRowsRemoved = trimPlan(logDoc(rootNodes, true), "20");
  var emptyAction = actionContainer();
  var emptyRoot = messageRoot([rowBox([])], [emptyAction]);
  var emptyTrim = trimPlan(logDoc([emptyRoot], true), "50");
  var globalActions = [actionContainer(), actionContainer(), actionContainer()];
  var globalRows = [rows(25), rows(20), rows(25)];
  var globalNodes = [
    messageRoot([rowBox(globalRows[0])], [globalActions[0]]),
    messageRoot([rowBox(globalRows[1])], [globalActions[1]]),
    messageRoot([rowBox(globalRows[2])], [globalActions[2]]),
  ];
  var globalRemoved = trimPlan(logDoc(globalNodes, true), "40");
  var sparseRows = [rows(30), rows(1)];
  var sparseRoots = sparseRows.map(function (items) {
    return messageRoot([rowBox(items)]);
  });
  assert.equal(trimPlan(logDoc(sparseRoots, true), "50"), 0);
  assert.equal(cleared(sparseRows[0][29]), false);
  var staleRows = rows(3);
  var staleAction = actionContainer();
  var k;
  for (k = 0; k < staleRows.length; k += 1) staleRows[k].parentElement = null;
  var staleRoot = messageRoot([rowBox(staleRows)], [staleAction]);
  var staleRemoved = trimPlan(logDoc([staleRoot], true), "50");
  var goneRows = rows(30);
  var goneAction = actionContainer();
  var goneRoot = messageRoot([rowBox(goneRows)], [goneAction], false);
  var goneRemoved = trimPlan(logDoc([goneRoot], true), "20");
  // An answered question appends a fresh empty root behind the rows. The keep
  // budget must stay with those rows instead of clearing the page.
  var questionRows = rows(30);
  var questionAction = actionContainer();
  var questionRoot = messageRoot([rowBox(questionRows)], [questionAction]);
  var questionTail = messageRoot([rowBox([])], []);
  var questionRemoved = trimPlan(logDoc([questionRoot, questionTail], true), "20");
  var detached = rows(4);
  detached[0].parentElement = null;
  // One pass cuts at most the cap, so a large backlog drains in steps. The page
  // then never reconciles one blocking burst at once.
  var cappedTrim = trimRows(rows(300), 50);
  var outerBox = rowBox(rows(1));
  var nestedBox = rowBox(rows(2), outerBox);
  var cases = [
    [trimRows(rows(5), 3), 2],
    [trimRows(rows(3), 3), 0],
    [trimRows(rows(2), 10), 0],
    [trimRows(detached, 2), 1],
    [cappedTrim, DEFAULT_TRIM_CAP],
    [normalizePlan("50"), "50"],
    [normalizePlan(" 50 "), "50"],
    [normalizePlan("5,80"), "80"],
    [normalizePlan("5"), null],
    [normalizePlan("5,5"), null],
    [normalizePlan("0,80"), null],
    [normalizePlan("80 rows"), null],
    [normalizePlan("later"), null],
    [normalizePlan(null), null],
    [planParts("").rows, DEFAULT_ROWS],
    [planParts("4,75").rows, 75],
    [MIN_ROWS, 20],
    [countLabel("50", 0), "Transcript - keep 50 rows"],
    [countLabel("50", 3), "Transcript - keep 50 rows (3 removed)"],
    [ACTION_SELECTOR, ":scope > div > div > div.mt-3.flex.flex-col.gap-3"],
    [QUESTION_SELECTOR, '[role="radiogroup"]'],
    [rowsOfRoot(messageRoot([rowBox(rows(3))])).length, 3],
    [rowsOfRoot(messageRoot([outerBox, nestedBox])).length, 1],
    [rowsOfRoot(messageRoot([rowBox(rows(2), outerBox)])).length, 2],
    [messageRoots(logDoc([messageRoot([])], true)).length, 1],
    [messageRoots(logDoc([messageRoot([])], false)).length, 1],
    [messageRoots(logDoc([], true)).length, 0],
    // A lone root is the newest: under its own keep count nothing leaves.
    [trimPlan(logDoc([messageRoot([rowBox(rows(30))])], true), "50"), 0],
    // The newest root keeps exactly its K newest rows: the ten oldest hide and empty.
    [trimPlan(logDoc([messageRoot([rowBox(rows(30))])], true), "20"), 10],
    [rootRowsRemoved, 30],
    // Cut rows stay as hidden empty shells: the page reinstates removed nodes. The trim hides and empties instead of deleting.
    // The older root hides in full while the newest root keeps its 20 newest rows.
    [cleared(rootRows[0][24]), true],
    [rootRows[0][24].parentElement !== null, true],
    [rootNodes[0].hiddenClass, true],
    [cleared(rootRows[1][0]), true],
    [cleared(rootRows[1][4]), true],
    [cleared(rootRows[1][5]), false],
    [rootRows[1][5].textContent, "row"],
    [rootNodes[1].hiddenClass, false],
    [rootActions[0].removed, true],
    // The action container leaves only with a root that lost every row. The newest
    // root keeps its rows, so its actions, and the newest rows inside them, stay.
    [rootActions[1].removed, false],
    // A lone root is the newest one: it keeps every row and never hides.
    [emptyTrim, 0],
    [emptyAction.removed, false],
    [emptyRoot.hiddenClass, false],
    [emptyRoot.parentElement !== null, true],
    // The newest root keeps 25 rows, and the previous root keeps 15.
    [globalRemoved, 30],
    [cleared(globalRows[0][24]), true],
    [globalNodes[0].hiddenClass, true],
    [cleared(globalRows[1][4]), true],
    [globalNodes[1].hiddenClass, false],
    [cleared(globalRows[2][0]), false],
    [globalNodes[2].hiddenClass, false],
    [globalActions[0].removed, true],
    [globalActions[1].removed, false],
    [globalActions[2].removed, false],
    [staleRemoved, 0],
    [staleAction.removed, false],
    [goneRemoved, 0],
    [goneRows[0].removed, false],
    [goneRows[24].removed, false],
    [goneAction.removed, false],
    [goneRoot.parentElement !== null, true],
    // The empty root an answered question appends takes no keep budget. The rows
    // behind it keep their 20 newest, their action stays, and the page does not clear.
    [questionRemoved, 10],
    [cleared(questionRows[0]), true],
    [cleared(questionRows[9]), true],
    [cleared(questionRows[10]), false],
    [questionRows[29].textContent, "row"],
    [questionAction.removed, false],
    [questionRoot.hiddenClass, false],
    [questionTail.hiddenClass, true],
    [globalNodes[0].parentElement !== null, true],
    [globalNodes[1].parentElement !== null, true],
    [globalNodes[2].parentElement !== null, true],
    // No stop control means no turn, and the trim aborts. It runs only while a turn
    // is up. A question card aborts too. The pulsing icon no longer gates anything.
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function () { return null; } }), false],
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function (selector) { return selector === "svg.animate-pulse" ? {} : null; } }), false],
    [isSettled({ querySelectorAll: function () { return []; }, querySelector: function (selector) { return selector === QUESTION_SELECTOR ? {} : null; } }), false],
    [isSettled({ querySelectorAll: function () { return [{ getAttribute: function () { return "Stop generating"; } }]; }, querySelector: function () { return null; } }), true],
    [isSettled({ querySelectorAll: function () { return [{ getAttribute: function () { return "Send"; } }]; }, querySelector: function () { return null; } }), false],
    // Quiet means the whole page holding still, not the row count alone. The page streams into existing
    // rows after the last row lands. A fresh mutation keeps the trim waiting even while the count holds.
    [quietReady({ rows: null, rowsAt: 0, mutationAt: 0 }, 10, 100000), false],
    [quietReady({ rows: 10, rowsAt: 100000, mutationAt: 0 }, 10, 100500), false],
    [(function () {
      var state = { rows: 10, rowsAt: 0, mutationAt: 100900 };
      return quietReady(state, 10, 101500);
    })(), false],
    [(function () {
      var state = { rows: 10, rowsAt: 0, mutationAt: 0 };
      return quietReady(state, 10, 101500);
    })(), true],
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
  console.log("ok transcript trim " + cases.length);
}

function checkHideComposer(api) {
  var isSessionUrl = api.isSessionUrl;
  var isStopGeneratingLabel = api.isStopGeneratingLabel;
  var shouldHideComposer = api.shouldHideComposer;
  var isSpacerElement = api.isSpacerElement;
  var isSpacerSibling = api.isSpacerSibling;
  var isTranscriptColumn = api.isTranscriptColumn;
  var hasSpacerHeight = api.hasSpacerHeight;
  var enforceSpacerHeight = api.enforceSpacerHeight;
  var TRANSCRIPT_COLUMN_SELECTOR = api.TRANSCRIPT_COLUMN_SELECTOR;
  var SPACER_SELECTOR = api.SPACER_SELECTOR;
  var SPACER_HEIGHT = api.SPACER_HEIGHT;

  var styleState = { height: SPACER_HEIGHT, priority: "", writes: 0 };
  var spacerStyle = {
    getPropertyValue: function (name) {
      return name === "height" ? styleState.height : "";
    },
    getPropertyPriority: function (name) {
      return name === "height" ? styleState.priority : "";
    },
    setProperty: function (name, value, priority) {
      if (name === "height") {
        styleState.height = value;
        styleState.priority = priority;
        styleState.writes += 1;
      }
    },
  };
  var spacer = {
    tagName: "DIV",
    classList: {
      contains: function (name) {
        return name === "shrink-0";
      },
    },
    textContent: "",
    style: spacerStyle,
    getAttribute: function (name) {
      return name === "style" ? "height: 24px;" : null;
    },
  };
  var columnClasses = [
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
  var transcriptColumn = {
    tagName: "DIV",
    classList: {
      contains: function (name) {
        return columnClasses.indexOf(name) !== -1;
      },
    },
    textContent: "message",
  };
  var siblingStyleState = { height: "706px", priority: "", writes: 0 };
  var siblingSpacer = {
    tagName: "DIV",
    classList: {
      contains: function (name) {
        return name === "shrink-0";
      },
    },
    textContent: "",
    style: {
      getPropertyValue: function (name) {
        return name === "height" ? siblingStyleState.height : "";
      },
      getPropertyPriority: function (name) {
        return name === "height" ? siblingStyleState.priority : "";
      },
      setProperty: function (name, value, priority) {
        if (name === "height") {
          siblingStyleState.height = value;
          siblingStyleState.priority = priority;
          siblingStyleState.writes += 1;
        }
      },
    },
    getAttribute: function (name) {
      return name === "style" ? "height: 706px;" : null;
    },
  };
  var scrollParent = { children: [transcriptColumn, siblingSpacer] };
  transcriptColumn.parentElement = scrollParent;
  siblingSpacer.parentElement = scrollParent;

  var spacerDoc = {
    querySelectorAll: function (selector) {
      if (selector === SPACER_SELECTOR) return [spacer];
      if (selector === TRANSCRIPT_COLUMN_SELECTOR) return [transcriptColumn];
      if (selector === "div.shrink-0") return [transcriptColumn, siblingSpacer, spacer];
      return [];
    },
  };
  var candidate = isSpacerElement(spacer) && hasSpacerHeight(spacer.getAttribute("style"));
  enforceSpacerHeight(spacerDoc);
  var initialPriority = styleState.priority;
  var initialSiblingHeight = siblingStyleState.height;
  var initialSiblingPriority = siblingStyleState.priority;
  styleState.height = "18px";
  styleState.priority = "";
  siblingStyleState.height = "706px";
  siblingStyleState.priority = "";
  enforceSpacerHeight(spacerDoc, [
    {
      type: "attributes",
      attributeName: "style",
      oldValue: "height: 24px !important;",
      target: spacer,
    },
    {
      type: "attributes",
      attributeName: "style",
      oldValue: "height: 706px;",
      target: siblingSpacer,
    },
  ]);
  var cases = [
    [isSessionUrl("https://arena.ai/agent/foo"), true],
    [isSessionUrl("https://www.arena.ai/agent/foo/bar"), true],
    [isSessionUrl("https://arena.ai/agent/foo?x=1"), true],
    [isSessionUrl("https://arena.ai/agent"), false],
    [isSessionUrl("https://arena.ai/agent/"), false],
    [isSessionUrl("https://other.example/agent/foo"), false],
    [isStopGeneratingLabel("Stop generating"), true],
    [isStopGeneratingLabel("Stop Generating"), true],
    [isStopGeneratingLabel("stop generating"), true],
    [isStopGeneratingLabel("Send"), false],
    [shouldHideComposer(true, true), true],
    [shouldHideComposer(true, false), false],
    [shouldHideComposer(false, true), false],
    [
      TRANSCRIPT_COLUMN_SELECTOR,
      "div.flex.w-full.shrink-0.flex-col.gap-4.mx-auto.max-w-3xl.px-4.pt-14.md\\:pt-12",
    ],
    [SPACER_SELECTOR, 'div.shrink-0[style*="height: 24px"]'],
    [SPACER_HEIGHT, "24px"],
    [candidate, true],
    [isTranscriptColumn(transcriptColumn), true],
    [isTranscriptColumn(siblingSpacer), false],
    [isSpacerSibling(siblingSpacer), true],
    [isSpacerSibling(spacer), false],
    [hasSpacerHeight("height: 24px;"), true],
    [hasSpacerHeight("height: 24px !important;"), true],
    [hasSpacerHeight("height: 25px;"), false],
    [hasSpacerHeight("height: 10675px;"), false],
    [initialPriority, "important"],
    [initialSiblingHeight, SPACER_HEIGHT],
    [initialSiblingPriority, "important"],
    [styleState.height, SPACER_HEIGHT],
    [styleState.priority, "important"],
    [styleState.writes, 2],
    [siblingStyleState.height, SPACER_HEIGHT],
    [siblingStyleState.priority, "important"],
    [siblingStyleState.writes, 2],
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
  console.log("ok hide composer " + cases.length);
}

function checkTabTitle(api, logging) {
  // Bundle hooks change state. Cases compare each call result to null.
  function expireHold() {
    api.expireHold();
    return null;
  }

  function forgetPath() {
    api.forgetPath();
    return null;
  }

  var repoFromLink = api.repoFromLink;
  var repoForTitle = api.repoForTitle;
  var desiredTitle = api.desiredTitle;
  var syncTitle = api.syncTitle;
  var liveLabel = api.liveLabel;
  var stopSignal = api.stopSignal;
  var childChain = api.childChain;
  var lastRoot = api.lastRoot;
  var userRoot = api.userRoot;
  var rowContainer = api.rowContainer;
  var newestRow = api.newestRow;
  var rowKind = api.rowKind;
  var summaryCard = api.summaryCard;
  var BASH_EMOJI = api.BASH_EMOJI;
  var PLAY_SELECTOR = api.PLAY_SELECTOR;
  var AGENT_EMOJI = api.AGENT_EMOJI;
  var REASONING_EMOJI = api.REASONING_EMOJI;
  var waitingSignal = api.waitingSignal;
  var emojiForRow = api.emojiForRow;
  var actionEmoji = api.actionEmoji;
  var TITLE_PREFIX = api.TITLE_PREFIX;
  var vtag = "";
  var EMOJI_HOLD_MS = api.EMOJI_HOLD_MS;
  var MESSAGE_SELECTOR = api.MESSAGE_SELECTOR;
  var LIVE_ICON_SELECTOR = api.LIVE_ICON_SELECTOR;
  var LIVE_LABEL_SELECTOR = api.LIVE_LABEL_SELECTOR;
  var GROUP_LABEL_SELECTOR = api.GROUP_LABEL_SELECTOR;
  var LABEL_SPAN_SELECTOR = api.LABEL_SPAN_SELECTOR;
  var REPO_LINK_SELECTOR = api.REPO_LINK_SELECTOR;
  var WAITING_SELECTOR = api.WAITING_SELECTOR;
  var WAITING_TEXT_SELECTOR = api.WAITING_TEXT_SELECTOR;
  var HOURGLASS_EMOJI = api.HOURGLASS_EMOJI;
  var CAPTCHA_SELECTOR = api.CAPTCHA_SELECTOR;
  var CAPTCHA_EMOJI = api.CAPTCHA_EMOJI;
  var captchaSignal = api.captchaSignal;
  var QUESTION_SELECTOR = api.QUESTION_SELECTOR;
  var QUESTION_EMOJI = api.QUESTION_EMOJI;
  var questionSignal = api.questionSignal;
  var openDialog = api.openDialog;
  var setPriorTitle = api.setPriorTitle;

  function link(href, label) {
    return {
      getAttribute: function (name) {
        if (name === "href") return href;
        if (name === "aria-label") return label;
        return null;
      },
    };
  }
  function docWith(element, title) {
    return {
      title: title,
      querySelector: function (selector) {
        return selector === REPO_LINK_SELECTOR ? element : null;
      },
      querySelectorAll: function (selector) {
        return selector === "button[aria-label]" ? [stopButton("Stop generating")] : [];
      },
    };
  }
  function stopButton(label) {
    return {
      getAttribute: function (name) {
        return name === "aria-label" ? label : null;
      },
    };
  }
  // The root-bounded model reads a real tree, so the checks build one. Every node answers
  // the selectors the feature uses, and the chain walks land on real children.
  function matches(node, selector) {
    if (!node || !node.attrs) {
      return false;
    }
    if (selector === MESSAGE_SELECTOR) {
      return node.attrs["data-agent-transcript-message"] !== undefined;
    }
    if (selector === PLAY_SELECTOR) {
      return node.tagName === "SVG" && api.classOf(node, "lucide-play");
    }
    if (selector === LIVE_LABEL_SELECTOR) {
      return String(node.attrs.style || "").indexOf("text-shimmer") !== -1;
    }
    if (selector === LIVE_ICON_SELECTOR) {
      return api.classOf(node, "animate-pulse");
    }
    if (selector === GROUP_LABEL_SELECTOR) {
      return node.tagName === "SPAN" && api.classOf(node, "text-text-secondary");
    }
    if (selector === LABEL_SPAN_SELECTOR) {
      return node.tagName === "SPAN" && api.classOf(node, "body-sm");
    }
    if (selector === "a") return node.tagName === "A";
    if (selector === "button") return node.tagName === "BUTTON";
    if (selector === "p") return node.tagName === "P";
    if (selector === "pre") return node.tagName === "PRE";
    if (selector === "button[aria-label]") {
      return node.tagName === "BUTTON" && node.attrs["aria-label"] !== undefined;
    }
    return false;
  }
  function findAll(root, selector) {
    var hits = [];
    (function walk(item) {
      var kids = item.children || [];
      var i;
      for (i = 0; i < kids.length; i += 1) {
        if (matches(kids[i], selector)) hits.push(kids[i]);
        walk(kids[i]);
      }
    })(root);
    return hits;
  }
  function node(tag, className, kids) {
    var el = {
      tagName: String(tag).toUpperCase(),
      className: className || "",
      children: kids || [],
      parentElement: null,
      textContent: "",
      attrs: {},
    };
    el.getAttribute = function (name) {
      return Object.prototype.hasOwnProperty.call(el.attrs, name) ? el.attrs[name] : null;
    };
    el.querySelector = function (selector) {
      var hits = findAll(el, selector);
      return hits.length ? hits[0] : null;
    };
    el.querySelectorAll = function (selector) {
      return findAll(el, selector);
    };
    el.contains = function (candidate) {
      if (candidate === el) return true;
      var i;
      for (i = 0; i < el.children.length; i += 1) {
        if (el.children[i].contains && el.children[i].contains(candidate)) return true;
      }
      return false;
    };
    el.closest = function (selector) {
      var current = el;
      while (current) {
        if (matches(current, selector)) return current;
        current = current.parentElement;
      }
      return null;
    };
    Object.defineProperty(el, "firstElementChild", {
      get: function () {
        return el.children.length ? el.children[0] : null;
      },
    });
    var i;
    for (i = 0; i < el.children.length; i += 1) el.children[i].parentElement = el;
    return el;
  }
  var ROW_CONTAINER_CLASS = "flex flex-col gap-2";
  // Session dump agent root: bubble card, then `px-3 pb-3`, then row container.
  // Every root carries transcript attributes.
  function agentRoot(rows) {
    var container = node("div", ROW_CONTAINER_CLASS, rows);
    var root = node("div", "", [
      node("div", "relative overflow-hidden bg-surface-primary rounded-xl border w-full border-transparent", [
        node("div", "px-3 pb-3", [container]),
      ]),
    ]);
    root.attrs["data-agent-transcript-message"] = "true";
    root.attrs["data-chat-message-id"] = "chat-agent";
    return root;
  }
  // Session dump user root: layout div, body row, raised card, then `px-3`,
  // container, and `prose` body. Agent root negates this chain.
  function userRootNode() {
    var body = node("div", "prose prose-pre:bg-transparent text-wrap break-words", []);
    var card = node("div", "relative overflow-hidden bg-surface-raised rounded-lg w-fit max-w-[min(70%,768px)] border-transparent ms-0", [
      node("div", "px-3 text-text-primary body-base py-2", [
        node("div", ROW_CONTAINER_CLASS, [body]),
      ]),
    ]);
    var root = node("div", "", [
      node("div", "", [node("div", "group flex min-w-0 flex-col items-end gap-1", [card])]),
    ]);
    root.attrs["data-agent-transcript-message"] = "true";
    root.attrs["data-chat-message-id"] = "chat-user";
    return root;
  }
  function actionRow(label) {
    var span = node("span", "text-text-secondary body-sm", []);
    span.textContent = label;
    var button = node("button", "flex w-full", [span]);
    button.attrs["aria-label"] = "Collapse";
    return node("div", "", [button]);
  }
  function commandRow(label, command, stderr) {
    var row = actionRow(label);
    if (command) {
      var pre = node("pre", "", []);
      pre.textContent = command;
      row.children[0].children.push(pre);
    }
    if (stderr) {
      var errPre = node("pre", "", []);
      errPre.textContent = stderr;
      row.children[0].children.push(errPre);
    }
    return row;
  }
  // The buttonless rows: a size-4 icon beside a single body-sm span. The fetch row keeps the
  // page's URL in an anchor inside that span. The anchor's copy never joins the label.
  function fetchRow(iconClass, text, url) {
    var icon = node("svg", iconClass, []);
    var span = node("span", "body-sm text-text-tertiary min-w-0 flex-1 truncate leading-4", []);
    if (url) {
      var linkNode = node("a", "text-interactive-link hover:underline", []);
      linkNode.textContent = url;
      span.children.push(linkNode);
    }
    span.textContent = url ? text + " " + url : text;
    return node("div", "flex items-center gap-1.5", [icon, span]);
  }
  function fetchRunningRow() {
    var icon = node("svg", "text-text-tertiary size-4 shrink-0 animate-pulse", []);
    var p = node("p", "relative inline-block", []);
    p.attrs.style = "animation: 2s linear 0s infinite normal none running text-shimmer;";
    p.textContent = "Fetching";
    var linkNode = node("a", "text-interactive-link ms-1 hover:underline", []);
    linkNode.textContent = "https://example.test/page";
    var span = node("span", "body-sm min-w-0 flex-1 truncate leading-4", [p, linkNode]);
    span.textContent = "Fetching https://example.test/page";
    return node("div", "flex items-center gap-1.5", [icon, span]);
  }
  // The process-output row: a size-3 icon beside a plain secondary span, no button.
  function processOutputRow() {
    var icon = node("svg", "text-text-tertiary size-3 shrink-0", []);
    var label = node("span", "text-text-secondary", []);
    label.textContent = "get_process_output";
    return node("div", "body-sm flex items-center gap-1.5", [icon, label]);
  }
  function loneSearchRow(label) {
    var span = node("span", "body-sm text-text-tertiary min-w-0 truncate leading-4", []);
    span.textContent = label;
    var inner = node("span", "flex min-w-0 items-center gap-1.5", [node("svg", "text-text-tertiary size-4 shrink-0", []), span]);
    var head = node("div", "flex select-none items-center gap-1", [inner]);
    head.attrs["aria-expanded"] = "false";
    return node("div", "", [head]);
  }
  function batchFetchRow() {
    var chevron = node("svg", "text-text-tertiary size-3 shrink-0 transition-transform duration-200 rotate-90", []);
    var icon = node("svg", "text-text-tertiary size-4 shrink-0", []);
    var pulse = node("span", "animate-pulse", []);
    pulse.textContent = "Searching the web";
    var label = node("span", "text-text-secondary shrink-0", [pulse]);
    var button = node("button", "body-sm group flex w-full cursor-pointer items-center gap-1.5 leading-[1]", [chevron, icon, label]);
    button.attrs["aria-expanded"] = "true";
    var body = node("div", "flex flex-col gap-2 py-1 ps-[22px]", [fetchRow("text-text-tertiary size-4 shrink-0", "Fetched", "https://example.test/page")]);
    return node("div", "", [button, body]);
  }
  function batchFetchDoneRow() {
    var chevron = node("svg", "text-text-tertiary size-3 shrink-0 transition-transform duration-200", []);
    var icon = node("svg", "text-text-tertiary size-4 shrink-0", []);
    var label = node("span", "text-text-secondary shrink-0", []);
    label.textContent = "Searched the web";
    var button = node("button", "body-sm group flex w-full cursor-pointer items-center gap-1.5 leading-[1]", [chevron, icon, label]);
    button.attrs["aria-expanded"] = "false";
    return node("div", "", [button]);
  }
  function chatRow() {
    var row = node("div", "prose", []);
    row.textContent = "A chat answer";
    return row;
  }
  function reasoningRow() {
    var row = node("div", "not-prose", []);
    row.textContent = "Thinking it over";
    return row;
  }
  function playRow() {
    var play = node("svg", "lucide-play size-4", []);
    var name = node("span", "text-text-secondary", []);
    name.textContent = "Start PR checks";
    var button = node("button", "flex w-full", [play, name]);
    return node("div", "", [button]);
  }
  function summaryRow() {
    var label = node("span", "text-text-secondary", []);
    label.textContent = "Summary";
    var button = node("button", "", [label]);
    return node("div", "", [button]);
  }
  function page(roots, options) {
    options = options || {};
    return {
      title: options.title || "ChatGPT",
      querySelector: function (selector) {
        if (selector !== REPO_LINK_SELECTOR) return null;
        return options.repo === undefined ? repoLink : options.repo;
      },
      querySelectorAll: function (selector) {
        if (selector === MESSAGE_SELECTOR) return roots || [];
        if (selector === "button[aria-label]") {
          return options.stop === false ? [] : [stopButton(options.stopLabel || "Stop generating")];
        }
        if (selector === WAITING_SELECTOR) return options.canvas ? [options.canvas] : [];
        if (selector === CAPTCHA_SELECTOR) return options.captcha ? [options.captcha] : [];
        if (selector === QUESTION_SELECTOR) return options.question ? [options.question] : [];
        return [];
      },
    };
  }
  // The waiting line is a spinner canvas beside the rotating monospace text.
  // An action row also uses the spinner canvas as its icon. The canvas alone does not prove an action row. Require text beside it.
  function pageTree(text, children) {
    var el = {
      text: text || "",
      textContent: text || "",
      children: children || [],
      querySelectorAll: function (selector) {
        var hits = [];
        if (selector !== WAITING_TEXT_SELECTOR) return hits;
        (function walk(item) {
          var i;
          for (i = 0; i < item.children.length; i += 1) {
            if (item.children[i].text || item.children[i].span) hits.push(item.children[i]);
            walk(item.children[i]);
          }
        })(el);
        return hits;
      },
    };
    var i;
    for (i = 0; i < el.children.length; i += 1) el.children[i].parentElement = el;
    return el;
  }
  function rowCanvas(withText, blank) {
    var canvas = pageTree("", []);
    var icon = pageTree("", [pageTree("", [canvas])]);
    var kids = [icon];
    if (withText) {
      var span = pageTree(blank ? "" : "The cat sat on the", []);
      if (blank) span.span = true;
      kids.push(pageTree("", [span]));
    }
    return { canvas: canvas, row: pageTree("", kids) };
  }
  function waitingDoc() {
    // The row carries no mark of its own, so the waiting line is the only news.
    return page([agentRoot([summaryRow()])], { canvas: rowCanvas(true).canvas });
  }
  function blankWaitingDoc() {
    return page([agentRoot([summaryRow()])], { canvas: rowCanvas(true, true).canvas });
  }
  function actionCanvasDoc() {
    return page([agentRoot([actionRow("Bash sleep 25")])], { canvas: rowCanvas(false).canvas });
  }
  function questionCard(label) {
    return {
      getAttribute: function (name) {
        return name === "aria-label" ? label || "Select one" : null;
      },
    };
  }
  function questionDoc(card, withCaptcha) {
    var options = { question: card || null };
    if (withCaptcha) options.captcha = captchaFrame();
    return page([agentRoot([chatRow()])], options);
  }
  function captchaFrame(state, parked) {
    var frame = {
      title: "reCAPTCHA",
      getAttribute: function () {
        return null;
      },
    };
    if (parked) {
      // A parked node keeps its place in the page after the widget closes: no box renders.
      frame.getClientRects = function () {
        return [];
      };
    }
    if (state) {
      // Radix keeps the dialog in the page after it closes, one data-state away.
      var dialog = {
        getAttribute: function (name) {
          return name === "data-state" ? state : null;
        },
      };
      var middle = { parentElement: dialog, getAttribute: function () { return null; } };
      frame.parentElement = middle;
    }
    return frame;
  }
  function captchaDoc(state, parked) {
    return page([agentRoot([chatRow()])], { captcha: captchaFrame(state, parked) });
  }
  function looseStopDoc() {
    return page([agentRoot([chatRow()])], { stopLabel: "Stop response" });
  }

  var repoLink = link("https://github.com/nemoe7/clankers", "Open nemoe7/clankers on GitHub");
  var labelOnly = link(null, "Open nemoe7/clankers on GitHub");
  var emptyLink = link("", "");
  var setDoc = docWith(repoLink, "ChatGPT");
  // One message per fixture: the same mark read twice would resurface as the hold.
  var chatPage = page([agentRoot([chatRow()])]);
  var reasoningPage = page([agentRoot([reasoningRow()])]);
  var bashPage = page([agentRoot([commandRow("Bash sleep 25", "$ npm test")])]);
  var editPage = page([agentRoot([commandRow("Edit main.py")])]);
  var readPage = page([agentRoot([commandRow("Read main.py")])]);
  var searchPage = page([agentRoot([commandRow("Searching the web")])]);
  var fetchPage = page([agentRoot([commandRow("Fetching web page")])]);
  // The buttonless rows and the group three batched fetches collapse into.
  var fetchDonePage = page([agentRoot([fetchRow("text-text-tertiary size-4 shrink-0", "Fetched", "https://example.test/page")])]);
  var fetchFailedPage = page([agentRoot([fetchRow("text-text-tertiary size-4 shrink-0", "Fetch failed", null)])]);
  var searchLonePage = page([agentRoot([loneSearchRow('Searched for "node test runner"')])]);
  var processOutputPage = page([agentRoot([processOutputRow()])]);
  var outputPage = page([agentRoot([commandRow("get_process_output")])]);
  var gearPage = page([agentRoot([commandRow("Agent chat")])]);
  var questionsPage = page([agentRoot([commandRow("Generating questions\u2026")])]);
  var pollPage = page([agentRoot([commandRow("running Bash", "$ arena-preview poll")])]);
  var playPage = page([agentRoot([playRow()])]);
  var summaryPage = page([agentRoot([summaryRow()])]);
  var userPage = page([userRootNode()]);
  var endedPage = page([agentRoot([chatRow()])], { stop: false });
  var quietPage = page([]);
  // `:nth-last-of-type(2)`: the trailing div is never the row.
  var trailingPage = page([agentRoot([commandRow("Bash sleep 25", "$ npm test"), chatRow()])]);
  var thirdPage = page([agentRoot([commandRow("Bash sleep 25", "$ npm test"), chatRow(), reasoningRow()])]);
  var olderRootPage = page([agentRoot([chatRow()]), agentRoot([commandRow("Bash sleep 25", "$ npm test")])]);
  var bashLogLine = loggedTitleLine(bashPage);
  var chatLogLine = loggedTitleLine(chatPage);
  var questionsLogLine = loggedTitleLine(questionsPage);
  var reasoningLogLine = loggedTitleLine(reasoningPage);
  var pollLogLine = loggedTitleLine(pollPage);
  var syncChatPage = page([agentRoot([chatRow()])]);
  var directChat = chatRow();
  var directReasoning = reasoningRow();
  var directAction = commandRow("Bash sleep 25");
  var directPoll = commandRow("running Bash", "$ arena-preview poll");
  var twoRows = [commandRow("Bash sleep 25"), chatRow()];
  var twoRowRoot = agentRoot(twoRows);
  var agentShape = agentRoot([]);
  var userShape = userRootNode();
  var headerChat = chatRow();
  var headerShape = agentRoot([headerChat, node("div", "flex w-fit items-center", [])]);
  var headerCard = headerShape.firstElementChild;
  var headerBody = headerCard.firstElementChild;
  var header = node("div", "flex min-h-[40px] items-center", [node("div", "flex size-4", [])]);
  header.parentElement = headerCard;
  headerCard.children.unshift(header);
  var originalHeaderQuery = headerShape.querySelector;
  headerShape.querySelector = function (selector) {
    if (selector === ":scope > div > div.px-3.pb-3 > div.flex.flex-col.gap-2") {
      return headerBody.firstElementChild;
    }
    return originalHeaderQuery(selector);
  };
  assert.equal(rowContainer(headerShape), headerBody.firstElementChild);
  assert.equal(newestRow(headerShape), headerChat);
  expireHold();
  assert.equal(desiredTitle(page([headerShape])), TITLE_PREFIX + "clankers " + AGENT_EMOJI);

  var promptPage = docWith(null, "Arena");
  promptPage.location = { href: "https://arena.ai/agent/session" };
  promptPage.querySelectorAll = function (selector) {
    return selector.includes('aria-haspopup')
      ? [{ textContent: "daedalus read ARENA.md AGENTS.md in full" }]
      : [];
  };
  assert.equal(repoForTitle(promptPage), "daedalus");
  promptPage.querySelector = function (selector) {
    return selector === REPO_LINK_SELECTOR ? repoLink : null;
  };
  assert.equal(repoForTitle(promptPage), "clankers");

  var cases = [
    // Repo name still comes from GitHub link, with memory answering while path holds.
    [repoFromLink(repoLink), "clankers"],
    [repoFromLink(labelOnly), "clankers"],
    [repoFromLink(emptyLink), null],
    [repoFromLink(null), null],
    [repoForTitle(docWith(repoLink, "ChatGPT")), "clankers"],
    [forgetPath(), null],
    [repoForTitle(docWith(null, "ChatGPT")), null],
    [repoForTitle(docWith(repoLink, "ChatGPT")), "clankers"],
    [repoForTitle(docWith(null, "ChatGPT")), "clankers"],
    // Root reads: agent root negates user-root chain. Row container and newest row
    // come from last root alone.
    [userRoot(userShape), true],
    [userRoot(agentShape), false],
    [lastRoot(page([agentShape])), agentShape],
    [lastRoot(quietPage), null],
    [rowContainer(userShape), null],
    [rowContainer(agentShape) === childChain(agentShape, 3), true],
    [newestRow(twoRowRoot) === twoRows[0], true],
    [rowKind(directChat), "chat"],
    [rowKind(directReasoning), "reasoning"],
    [rowKind(directAction), "action"],
    [rowKind(null), "none"],
    // Row type carries its mark: chat body takes balloon, reasoning block takes
    // thinking mark, and action rows keep label words.
    [expireHold(), null],
    [desiredTitle(chatPage), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [expireHold(), null],
    [desiredTitle(reasoningPage), TITLE_PREFIX + "clankers" + vtag + " " + REASONING_EMOJI],
    [expireHold(), null],
    [desiredTitle(bashPage), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    [expireHold(), null],
    [desiredTitle(editPage), TITLE_PREFIX + "clankers" + vtag + " \u270F\uFE0F"],
    [expireHold(), null],
    [desiredTitle(readPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCD6"],
    [expireHold(), null],
    [desiredTitle(searchPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(fetchPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(fetchDonePage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(fetchFailedPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(searchLonePage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDD0D"],
    [expireHold(), null],
    [desiredTitle(processOutputPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCDC"],
    [expireHold(), null],
    [desiredTitle(outputPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCDC"],
    [expireHold(), null],
    [desiredTitle(gearPage), TITLE_PREFIX + "clankers" + vtag + " \u2699\uFE0F"],
    [expireHold(), null],
    [desiredTitle(questionsPage), TITLE_PREFIX + "clankers" + vtag + " " + QUESTION_EMOJI],
    [expireHold(), null],
    [desiredTitle(pollPage), TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCA4"],
    [expireHold(), null],
    [desiredTitle(playPage), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    // The trailing div is never the row: with two rows the first one marks. The
    // third row lands only when it takes the second-to-last place.
    [expireHold(), null],
    [desiredTitle(trailingPage), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    [expireHold(), null],
    [desiredTitle(thirdPage), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    // Every row read starts at the last root, so an older root never marks.
    [expireHold(), null],
    [desiredTitle(olderRootPage), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    // The user root carries no mark, and a finished turn drops every row mark.
    [expireHold(), null],
    [desiredTitle(userPage), TITLE_PREFIX + "clankers" + vtag],
    [desiredTitle(endedPage), TITLE_PREFIX + "clankers" + vtag],
    // The answered question card raises no mark of its own.
    [expireHold(), null],
    [summaryCard(summaryRow()), true],
    [desiredTitle(summaryPage), TITLE_PREFIX + "clankers" + vtag],
    // The emoji selector and structured logs identify the row type.
    [emojiForRow(directChat), AGENT_EMOJI],
    [emojiForRow(directReasoning), REASONING_EMOJI],
    [emojiForRow(directPoll), "\uD83D\uDCA4"],
    [
      emojiForRow(
        commandRow(
          "running Bash",
          "$ arena-preview poll",
          "poll max 1799 s; bash timeout 1800 s.\nrun suite-readme-shot running 39s\n"
        )
      ),
      BASH_EMOJI,
    ],
    [
      emojiForRow(
        commandRow(
          "running Bash",
          "$ arena-preview poll",
          "poll max 1799 s; bash timeout 1800 s.\n"
        )
      ),
      "\uD83D\uDCA4",
    ],
    [emojiForRow(null), null],
    [chatLogLine.data.type, "chat"],
    [reasoningLogLine.data.type, "reasoning"],
    [bashLogLine.data.type, "action"],
    [pollLogLine.data.type, "poll"],
    // Hold bridges gaps inside a turn and ends with stop control.
    [expireHold(), null],
    [desiredTitle(chatPage), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [desiredTitle(quietPage), TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [expireHold(), null],
    [desiredTitle(quietPage), TITLE_PREFIX + "clankers" + vtag],
    // A drifted stop label still opens the gate. The exact wording does not.
    [stopSignal(looseStopDoc()), true],
    [stopSignal(page([], { stop: false })), false],
    // The waiting line is a turn mark too: no control, no hourglass.
    [expireHold(), null],
    [desiredTitle(page([agentRoot([chatRow()])], { stop: false, canvas: rowCanvas(true).canvas })),
      TITLE_PREFIX + "clankers" + vtag],
    // A named action outranks the line, so the poll row keeps its own emoji. The row read
    // runs before the waiting line on the same page.
    [expireHold(), null],
    [
      desiredTitle(page([agentRoot([commandRow("running Bash", "$ arena-preview poll")])], {
        canvas: rowCanvas(true).canvas,
      })),
      TITLE_PREFIX + "clankers" + vtag + " \uD83D\uDCA4",
    ],
    [expireHold(), null],
    [waitingSignal(waitingDoc()), true],
    [waitingSignal(blankWaitingDoc()), true],
    // The owner's action row carries the very same canvas as its icon. The canvas alone
    // never reads as a waiting line and never outranks the Bash row.
    [waitingSignal(actionCanvasDoc()), false],
    [waitingSignal(setDoc), false],
    [expireHold(), null],
    [desiredTitle(waitingDoc()), TITLE_PREFIX + "clankers" + vtag + " " + HOURGLASS_EMOJI],
    [expireHold(), null],
    [desiredTitle(actionCanvasDoc()), TITLE_PREFIX + "clankers" + vtag + " " + BASH_EMOJI],
    [WAITING_SELECTOR, 'canvas[width="16"][height="16"]'],
    [WAITING_TEXT_SELECTOR, 'span[class*="whitespace-pre"]'],
    // The ask_user card holds the title with a question mark, and the security check beats
    // it, like every other mark.
    [questionSignal(questionDoc(questionCard())), true],
    [questionSignal(questionDoc(null)), false],
    [expireHold(), null],
    [desiredTitle(questionDoc(questionCard())), TITLE_PREFIX + "clankers" + vtag + " " + QUESTION_EMOJI],
    [expireHold(), null],
    [desiredTitle(questionDoc(questionCard(), true)), TITLE_PREFIX + "clankers" + vtag + " " + CAPTCHA_EMOJI],
    [captchaSignal(captchaDoc()), true],
    [captchaSignal(captchaDoc("closed")), false],
    [captchaSignal(captchaDoc(null, true)), false],
    [openDialog(node("div", "", [])), true],
    // Every mark keeps its own label words, so the map stands.
    [actionEmoji("running Bash"), BASH_EMOJI],
    [actionEmoji("used Bash"), BASH_EMOJI],
    [actionEmoji("Running commands"), BASH_EMOJI],
    [actionEmoji("Ran commands"), BASH_EMOJI],
    [actionEmoji("Reading files"), "\uD83D\uDCD6"],
    [actionEmoji("Explored"), "\uD83D\uDCD6"],
    [actionEmoji("Edit"), "\u270F\uFE0F"],
    [actionEmoji("Writing"), "\u270F\uFE0F"],
    [actionEmoji("Searching the web"), "\uD83D\uDD0D"],
    [actionEmoji("Fetching web page"), "\uD83D\uDD0D"],
    [actionEmoji("Thought for 2 seconds"), "\uD83D\uDCAD"],
    [actionEmoji("Waiting"), "\uD83D\uDCA4"],
    [actionEmoji("get_process_output"), "\uD83D\uDCDC"],
    [actionEmoji("Agent chat"), "\u2699\uFE0F"],
    [actionEmoji(null), null],
    [liveLabel(directAction), "Bash sleep 25"],
    // The buttonless rows keep their label in a body-sm span. The fetch row's URL anchor
    // never joins the label words.
    [liveLabel(fetchRunningRow()), "Fetching"],
    [liveLabel(fetchRow("text-text-tertiary size-4 shrink-0", "Fetched", "https://example.test/page")), "Fetched"],
    [liveLabel(fetchRow("text-text-tertiary size-4 shrink-0", "Fetch failed", null)), "Fetch failed"],
    [liveLabel(loneSearchRow('Searched for "node test runner"')), 'Searched for "node test runner"'],
    [liveLabel(fetchRow("text-text-tertiary size-4 shrink-0", "https://example.test/page", "https://example.test/page")), null],
    [liveLabel(batchFetchRow()), "Searching the web"],
    [liveLabel(batchFetchDoneRow()), "Searched the web"],
    [liveLabel(processOutputRow()), "get_process_output"],
    [liveLabel(null), null],
    [polls("arena-preview poll --max 1"), true],
    [polls("python preview.py poll"), true],
    [polls("cat skills/arena-steering/README.md | grep polling"), false],
    // Title writes through syncTitle, and line carries row anchors.
    [setPriorTitle("ChatGPT"), undefined],
    [expireHold(), null],
    [syncTitle(syncChatPage), true],
    [syncChatPage.title, TITLE_PREFIX + "clankers" + vtag + " " + AGENT_EMOJI],
    [syncTitle(syncChatPage), false],
    // The hold is still warm from the mark above. The quiet write needs its own window.
    [expireHold(), null],
    [syncTitle(quietPage), true],
    [quietPage.title, TITLE_PREFIX + "clankers" + vtag],
    [bashLogLine.text, "[NemoUtils][title][info] changed"],
    [bashLogLine.data.type, "action"],
    [bashLogLine.data.emoji, BASH_EMOJI],
    [bashLogLine.data.repo, undefined],
    [chatLogLine.text, "[NemoUtils][title][info] changed"],
    [chatLogLine.data.type, "chat"],
    [chatLogLine.data.emoji, AGENT_EMOJI],
    [questionsLogLine.text, "[NemoUtils][title][info] changed"],
    [questionsLogLine.data.type, "action"],
    [questionsLogLine.data.emoji, QUESTION_EMOJI],
    [api.VERSION, undefined],
  ];
  // Title writes through syncTitle, which logs winning signal. Capture keeps host
  // console clean and returns last line.
  function loggedTitle(doc) {
    var lines = [];
    var original = console.log;
    console.log = function (text, data) {
      lines.push({ text: text, data: JSON.parse(JSON.stringify(data || {})) });
    };
    try {
      doc.title = "ChatGPT";
      api.syncTitle(doc);
    } finally {
      console.log = original;
    }
    return lines;
  }
  function loggedTitleLine(doc) {
    var lines = loggedTitle(doc);
    assert.equal(lines.length, 1, "normal title output must omit debug conditions");
    return lines[0];
  }

  function polls(text) {
    return api.POLL_RE.test(text.toLowerCase());
  }
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
  api.setPriorTitle(quietPage.title);
  var restoreLines = [];
  var restoreConsole = console.log;
  console.log = (...args) => restoreLines.push(args);
  try {
    assert.equal(api.restoreTitle(quietPage), false);
    assert.equal(restoreLines.length, 0, "restoring an equal title must stay silent");
    quietPage.title = "External title";
    api.syncTitle(quietPage);
    api.setPriorTitle("Original title");
    restoreLines.length = 0;
    assert.equal(api.restoreTitle(quietPage), true);
    assert.equal(quietPage.title, "Original title");
    assert.equal(restoreLines.length, 1);
    assert.equal(restoreLines[0][0], "[NemoUtils][title][info] restored");
    api.syncTitle(quietPage);
  } finally {
    console.log = restoreConsole;
  }
  // One line per change stays, and the plain unchanged line is gone. A second
  // sync with the title already in place writes nothing at all.
  var quiet = [];
  var louder = console.log;
  console.log = function () {
    quiet.push(Array.prototype.join.call(arguments, " "));
  };
  try {
    api.syncTitle(quietPage);
    logging.setLogLevel("debug");
    api.syncTitle(quietPage);
  } finally {
    console.log = louder;
    logging.setLogLevel("info");
  }
  if (quiet.length) {
    console.error("check fail", "unchanged title line", quiet.join(" | "));
    throw new Error("the unchanged title line still fires: " + quiet.join(" | "));
  }
  logging.setLogLevel("debug");
  try {
    expireHold();
    var firstChange = loggedTitle(bashPage);
    var secondChange = loggedTitle(bashPage);
    assert.equal(firstChange.length, 2);
    assert.equal(secondChange.length, 2, "real title changes must not use a time throttle");
    assert.equal(firstChange[1].text, "[NemoUtils][title][debug] conditions");
    assert.deepEqual(firstChange[1].data, { captcha: false, question: false, live: true });
    assert.doesNotMatch(JSON.stringify(firstChange), /Bash sleep|row=/);
  } finally {
    logging.setLogLevel("info");
  }
  console.log("ok tab title " + cases.length);
}

function checkKeepAwake(api) {
  var wakeLockPlan = api.wakeLockPlan;
  assert.equal(wakeLockPlan(true, false, true), "acquire");
  assert.equal(wakeLockPlan(true, true, true), "none", "A held lock stays");
  assert.equal(wakeLockPlan(true, false, false), "none", "A hidden page cannot take the lock");
  assert.equal(wakeLockPlan(false, true, true), "release", "A finished turn drops the lock");
  assert.equal(wakeLockPlan(false, true, false), "release", "A hidden page drops a held lock");
  assert.equal(wakeLockPlan(false, false, true), "none");
  console.log("ok keep awake 6");
}

function run(name, check) {
  try {
    check();
  } catch (error) {
    throw new Error(`${name}: ${error.message}`);
  }
}

function checkStateDownload(api, session, logging) {
  var stateFileName = api.stateFileName;
  var stateDownload = api.stateDownload;
  var stateMemory = api.stateMemory;
  var stateRemembered = api.stateRemembered;
  var saveMoved = api.saveMoved;
  var overwriteAsk = api.overwriteAsk;
  var overwriteLine = api.overwriteLine;
  var panelNeeded = api.panelNeeded;
  var stateScope = api.stateScope;
  var stateRepo = api.stateRepo;
  var stateBranch = api.stateBranch;
  var stateScopeKey = api.stateScopeKey;
  var readSlug = api.readSlug;
  var slugFromBare = api.slugFromBare;
  var getLine = api.getLine;
  var stateError = api.stateError;
  assert.equal(api.computeStateDiff, undefined);
  assert.equal(api.applyStateDiff, undefined);
  assert.equal(api.backupTextForOffer, undefined);
  assert.equal(api.pagePicker, undefined);
  assert.equal(api.writeToHandle, undefined);
  assert.equal(api.writeStateDownload, undefined);
  assert.equal(api.handleMatchesScope, undefined);
  var counts = { notes: 12, tasks: 4 };
  var repo = "clankers";
  var branch = "main";
  // The name carries the repository, then the branch, then the server's stamp and the record
  // counts. Two repos and their branches never collide in one folder.
  assert.equal(
    stateFileName(repo, branch, "2026-10-06T06:12:33.123456+00:00", counts),
    "clankers-main-20261006T061233-n12-t4.ndjson",
  );
  assert.equal(
    stateFileName("my repo", "feat/x", "2026-10-06T06:12:33", counts),
    "my-repo-feat-x-20261006T061233-n12-t4.ndjson",
  );
  assert.equal(
    stateFileName("", "", "2026-10-06T06:12:33", counts),
    "arena-20261006T061233-n12-t4.ndjson",
  );
  assert.equal(
    stateFileName(repo, branch, "2026-10-06T06:12:33", { notes: 0, tasks: 0 }),
    "clankers-main-20261006T061233-n0-t0.ndjson",
  );
  assert.equal(stateFileName(repo, branch, null, counts), "clankers-main-n12-t4.ndjson");
  // Only a stamp that differs from the last write fills the file.
  assert.equal(stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "").type, "download");
  assert.equal(
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "2026-10-05T20:00:00").type,
    "download",
  );
  var repeated = stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "2026-10-06T06:12:33");
  assert.equal(repeated.type, "unchanged");
  assert.equal(repeated.name, "clankers-main-20261006T061233-n12-t4.ndjson");
  assert.match(repeated.message, /unchanged since the last write/);
  // A stamp that goes backward is a wiped or replaced preview. Nothing overwrites the
  // owner's file with an older state.
  var stale = stateDownload(repo, branch, "2026-10-05T20:00:00", counts, "2026-10-06T06:12:33");
  assert.equal(stale.type, "stale");
  assert.match(stale.message, /Stale preview state/);
  // A payload with no stamp says so instead of writing an undated file.
  var unstamped = stateDownload(repo, branch, null, counts, "");
  assert.equal(unstamped.type, "error");
  assert.match(unstamped.message, /carries no stamp/);
  // The approved pair: the newest note stamp and the newest task stamp.
  // A rollback leaves older records while a new note moves the state stamp. The pair rejects that write. The owner keeps the newer state.
  var memory = stateMemory("2026-10-05T20:00:00", {
    note: "2026-10-05T20:00:00",
    task: "2026-10-05T19:00:00",
  });
  assert.equal(memory.stamp, "2026-10-05T20:00:00");
  assert.equal(memory.note, "2026-10-05T20:00:00");
  assert.equal(memory.task, "2026-10-05T19:00:00");
  var restored = stateRemembered(JSON.stringify(memory));
  assert.equal(restored.stamp, memory.stamp);
  assert.equal(restored.note, memory.note);
  assert.equal(restored.task, memory.task);
  var legacy = stateRemembered("2026-10-05T20:00:00");
  assert.equal(legacy.stamp, "2026-10-05T20:00:00");
  assert.equal(legacy.note, "");
  assert.equal(legacy.task, "");
  var rolledBackTask = stateDownload(
    repo,
    branch,
    "2026-10-06T06:12:33",
    counts,
    memory,
    { note: "2026-10-06T06:12:33", task: "2026-10-05T18:00:00" },
  );
  assert.equal(rolledBackTask.type, "stale");
  assert.match(rolledBackTask.message, /task stamp went backward/);
  // A forced save takes the state whatever the memory says. The same stamp, an older
  // stamp and a rolled-back pair all write, and the write moves the reference.
  assert.equal(
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "2026-10-06T06:12:33", null, true).type,
    "download",
  );
  assert.equal(
    stateDownload(repo, branch, "2026-10-05T20:00:00", counts, "2026-10-06T06:12:33", null, true).type,
    "download",
  );
  assert.equal(
    stateDownload(
      repo,
      branch,
      "2026-10-06T06:12:33",
      counts,
      memory,
      { note: "2026-10-06T06:12:33", task: "2026-10-05T18:00:00" },
      true,
    ).type,
    "download",
  );
  var rolledBackNote = stateDownload(
    repo,
    branch,
    "2026-10-06T06:12:33",
    counts,
    memory,
    { note: "2026-10-05T18:00:00", task: "2026-10-06T06:00:00" },
  );
  assert.equal(rolledBackNote.type, "stale");
  assert.match(rolledBackNote.message, /note stamp went backward/);
  // Both stamps of the pair move forward: the write lands.
  var pairForward = stateDownload(
    repo,
    branch,
    "2026-10-06T06:12:33",
    counts,
    memory,
    { note: "2026-10-06T06:12:33", task: "2026-10-06T06:00:00" },
  );
  assert.equal(pairForward.type, "download");
  var deletion = stateDownload(
    repo,
    branch,
    "2026-10-06T06:12:33",
    counts,
    {
      stamp: "2026-10-06T06:12:33",
      note: "2026-10-06T06:12:33",
      task: "2026-10-05T19:00:00",
    },
    { note: "2026-10-05T20:00:00", task: "2026-10-05T19:00:00" },
  );
  assert.equal(deletion.type, "unchanged");
  // A payload without the pair, or a memory saved before the pair existed, keeps the old rule.
  assert.equal(
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, memory).type,
    "download",
  );
  assert.equal(
    stateDownload(
      repo,
      branch,
      "2026-10-06T06:12:33",
      counts,
      "2026-10-05T20:00:00",
      { note: "2026-10-06T06:12:33", task: "2026-10-05T19:00:00" },
    ).type,
    "download",
  );
  // The repo bar carries the pair and the branch anchor, so the name scopes to this repo and
  // branch. Two repos never collide in one folder.
  var branchLink = {
    getAttribute: function (name) {
      if (name === "href") return "https://github.com/nemoe7/clankers/tree/arena%2F01a0fd4f-clankers";
      if (name === "title") return "main \u2192 arena/01a0fd4f-clankers";
      return null;
    },
  };
  var bar = {
    querySelectorAll: function (selector) {
      if (selector === "span.truncate") return [{ textContent: "nemoe7/clankers" }];
      if (selector === "a, [title]") return [branchLink];
      return [];
    },
  };
  var doc = { querySelector: function () { return bar; } };
  var scope = stateScope(doc);
  assert.equal(scope.repo, "clankers");
  assert.equal(scope.branch, "arena/01a0fd4f-clankers");
  assert.equal(
    stateFileName(scope.repo, scope.branch, "2026-10-06T06:12:33", counts),
    "clankers-arena-01a0fd4f-clankers-20261006T061233-n12-t4.ndjson",
  );
  // Server stamp carries timezone. Name keeps seconds alone.
  assert.equal(
    stateFileName(scope.repo, scope.branch, "2026-10-06T08:33:57+00:00", null),
    "clankers-arena-01a0fd4f-clankers-20261006T083357.ndjson",
  );
  // An ongoing session renders the repository as a bare chip without its owner. A slash-less slug-like span in the
  // bar still names the repository for the selector and the fill. It never falls through to a header session token.
  var bareBar = {
    querySelectorAll: function (selector) {
      if (selector === "span.truncate") return [{ textContent: "daedalus" }];
      if (selector === "a, [title]") return [branchLink];
      return [];
    },
  };
  var bareDoc = {
    querySelector: function () { return bareBar; },
    querySelectorAll: function (selector) {
      return selector.indexOf("span.truncate") !== -1 ? [{ textContent: "daedalus" }] : [];
    },
  };
  assert.equal(slugFromBare("daedalus"), "daedalus");
  assert.equal(slugFromBare("nemoe7/daedalus"), null);
  assert.equal(slugFromBare("  "), null);
  assert.equal(stateRepo(bareDoc), "daedalus");
  assert.equal(readSlug(bareDoc), "daedalus");
  assert.equal(stateScope(bareDoc).repo, "daedalus");
  var promptDoc = {
    location: { href: "https://arena.ai/agent/session" },
    title: "Arena | previous",
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      return selector.includes('aria-haspopup')
        ? [{ textContent: "daedalus read ARENA.md AGENTS.md in full before your first edit" }]
        : [];
    },
  };
  assert.equal(readSlug(promptDoc), "daedalus");
  assert.equal(stateRepo(promptDoc), "daedalus");
  promptDoc.location.href = "https://arena.ai/agent";
  assert.equal(readSlug(promptDoc), "previous");
  promptDoc.location.href = "https://arena.ai/agent/session";
  promptDoc.querySelectorAll = function () {
    return [{ textContent: "not a repo read ARENA.md" }];
  };
  assert.equal(readSlug(promptDoc), "previous");
  // A new chat on /agent has no session bar. The composer's own selector row carries the
  // repository chip ahead of the branch chip, and the fill reads it there.
  var composerDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "nemoe7/clankers" }, { textContent: "main" }];
    },
  };
  assert.equal(readSlug(composerDoc), "clankers");
  assert.equal(stateRepo(composerDoc), "clankers");
  // The leading chip is the repository, so a chip that is not the owner/repo form never
  // answers. The title still carries the read.
  var branchChipDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "main" }, { textContent: "nemoe7/clankers" }];
    },
    title: "Arena | clankers",
  };
  assert.equal(readSlug(branchChipDoc), "clankers");
  // A branch with a slash wears the owner/repo shape too, so two such chips stay ambiguous. The
  // title decides instead of a branch.
  var branchFirstDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "arena/595e8dec-clankers" }, { textContent: "nemoe7/clankers" }];
    },
    title: "Arena | clankers",
  };
  assert.equal(readSlug(branchFirstDoc), "clankers");
  // A selected diff branch puts the session branch beside the repository chip. The tab title stays bare on that page.
  // The branch wears the platform namespace. The chip read still names the repository with nothing else to fall back on.
  var diffBranchDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "nemoe7/daedalus" }, { textContent: "arena/fef1ae85-daedalus" }];
    },
    title: "Arena",
  };
  assert.equal(readSlug(diffBranchDoc), "daedalus");
  assert.equal(stateRepo(diffBranchDoc), "daedalus");
  // A branch in another namespace carries no platform mark, so the pair stays ambiguous and
  // the title alone can answer.
  var otherBranchDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "nemoe7/daedalus" }, { textContent: "feature/panel" }];
    },
    title: "Arena",
  };
  assert.equal(readSlug(otherBranchDoc), null);
  // The page's own chip outranks the title. The title can still name the previous
  // session after a new chat opens on the same tab.
  var staleTitleDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      if (selector.indexOf("aria-haspopup") === -1) return [];
      return [{ textContent: "nemoe7/daedalus" }];
    },
    title: "Arena | clankers",
  };
  assert.equal(readSlug(staleTitleDoc), "daedalus");
  // While dialog holds page, header disappears and fill's saved slug names repository.
  // Branch stays empty.
  session.value = "clankers";
  assert.equal(stateRepo({ querySelector: function () { return null; } }), "clankers");
  assert.equal(
    stateScope({ querySelector: function () { return null; } }).branch,
    "",
  );
  session.value = null;
  assert.equal(stateRepo({ querySelector: function () { return null; } }), "");
  // One storage scope per repo and branch. A second tab of another session never
  // shares the stamp memory or the chosen file with this one.
  assert.equal(stateScopeKey("clankers", "main"), stateScopeKey("clankers", "main"));
  assert.notEqual(stateScopeKey("clankers", "main"), stateScopeKey("widget", "main"));
  assert.notEqual(stateScopeKey("clankers", "main"), stateScopeKey("clankers", "feat/x"));
  assert.equal(stateScopeKey("", ""), "arena");
  assert.equal(stateScopeKey("my repo", "feat/x"), "my-repo-feat-x");
  assert.equal(api.downloadRoute, undefined);
  assert.equal(api.stateDownloadRoute, undefined);
  // A title without the arrow falls back to the href. A page without the bar stays empty.
  branchLink.getAttribute = function (name) {
    if (name === "href") return "https://github.com/other/repo/tree/feat%2Fx";
    return "";
  };
  assert.equal(stateScope(doc).branch, "feat/x");
  assert.equal(
    JSON.stringify(stateScope({ querySelector: function () { return null; } })),
    JSON.stringify({ repo: "", branch: "" }),
  );
  // The bar leaves the page while a dialog holds it. With no saved slug either, the title
  // still carries the repository this script wrote.
  session.value = null;
  assert.equal(
    stateRepo({ querySelector: function () { return null; }, title: "Arena | clankers \uD83D\uDCA4" }),
    "clankers",
  );
  assert.equal(
    stateRepo({ querySelector: function () { return null; }, title: "ChatGPT" }),
    "",
  );
  // The Arena UI moves the GitHub integration around, so the repo/branch span can vanish. The conversation header still opens with the repository name, and its first word is the repository.
  // The tab title is the reliable read, so it comes before the greppier header read.
  var headerSpan = { textContent: "clankers read ARENA.md AGENTS.md in full before your first edit" };
  var headerDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      return selector.indexOf("aria-haspopup") !== -1 ? [headerSpan] : [];
    },
    title: "Arena | other",
  };
  assert.equal(stateRepo(headerDoc), "other");
  // With no title at all, the header read names the repository.
  var headerOnlyDoc = {
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
      return selector.indexOf("aria-haspopup") !== -1 ? [headerSpan] : [];
    },
  };
  assert.equal(stateRepo(headerOnlyDoc), "clankers");
  // A header span with no slug-like first word and no title yields nothing.
  headerSpan.textContent = "";
  assert.equal(stateRepo(headerOnlyDoc), "");
  // Saved slug still wins over header read when title disappears.
  session.value = "saved";
  headerSpan.textContent = "clankers read ARENA.md";
  assert.equal(stateRepo(headerOnlyDoc), "saved");
  session.value = null;
  // The proxy-config card: a manual press always shows it, and an automatic tick stays quiet.
  assert.equal(panelNeeded(true, true), true);
  assert.equal(panelNeeded(true, false), true);
  assert.equal(panelNeeded(false, false), true);
  assert.equal(panelNeeded(false, true), false);
  // The panel keeps its text, but the console carries only the error code and status.
  var errorLines = [];
  var restoreLog = console.error;
  console.error = function () { errorLines.push(JSON.stringify(Array.from(arguments))); };
  try {
    stateError("GET 500 http://localhost:8000/api/copy-state", null, null, "copy-state", 500);
  } finally {
    console.error = restoreLog;
  }
  assert.match(errorLines[0], /\[NemoUtils\]\[state\]\[error\] failed/);
  assert.match(errorLines[0], /copy-state/);
  assert.match(errorLines[0], /500/);
  assert.doesNotMatch(errorLines[0], /localhost|api\/copy-state/);
  assert.match(getLine(200, "http://localhost:8000"), /^GET 200$/);
  // Every comparison in the save path writes its own line, so one filter shows which test
  // refused a write.
  logging.setLogLevel("debug");
  var compared = [];
  var originalLog = console.log;
  console.log = function () {
    compared.push(JSON.stringify(Array.from(arguments)));
  };
  try {
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "2026-10-06T06:12:33");
    stateDownload(repo, branch, "2026-10-05T20:00:00", counts, "2026-10-06T06:12:33");
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, "");
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, {
      stamp: "2026-10-05T20:00:00",
      note: "2026-10-06T05:30:00",
      task: "2026-10-06T05:00:00",
    }, { note: "2026-10-06T05:00:00", task: "2026-10-06T06:00:00" });
    stateDownload(repo, branch, null, counts, "");
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, {
      stamp: "2026-10-06T06:12:33",
      note: "2026-10-06T06:12:33",
      task: "2026-10-06T06:12:33",
    }, { note: "2026-10-06T06:12:33", task: "2026-10-06T06:12:33" });
    stateDownload(repo, branch, "2026-10-06T06:12:33", counts, {
      stamp: "2026-10-05T20:00:00",
      note: "2026-10-06T05:30:00",
      task: "2026-10-06T05:00:00",
    }, { note: "2026-10-06T05:00:00", task: "2026-10-06T06:00:00" }, true);
  } finally {
    console.log = originalLog;
    logging.setLogLevel("info");
  }
  function comparedLine(event, fields) {
    return compared.some(function (line) {
      var parts = JSON.parse(line);
      return parts[0] === "[NemoUtils][state][debug] " + event &&
        JSON.stringify(parts[1] || {}) === JSON.stringify(fields || {});
    });
  }
  assert.ok(comparedLine("compare", { group: "note", verdict: "older" }));
  assert.ok(comparedLine("compare", { group: "task", verdict: "forward" }));
  assert.ok(comparedLine("no-stamp"));
  assert.ok(comparedLine("compare", { group: "note", verdict: "same" }));
  assert.ok(comparedLine("compare", { group: "task", verdict: "same" }));
  assert.ok(comparedLine("force-stamp", { group: "note" }));
  assert.ok(comparedLine("force-stamp", { group: "task" }));
  assert.doesNotMatch(compared.join("\n"), /2026-|http|private/);
  // A save moves when the session branch is unknown. It also moves when the preview URL differs from the one that last wrote this scope.
  // A moved save that would write asks before it writes. A forced save never asks.
  assert.equal(saveMoved("", "", "https://p.example"), true, "No branch moves the save");
  assert.equal(saveMoved("arena/x", "", "https://p.example"), false, "A first write does not move");
  assert.equal(saveMoved("arena/x", "https://p.example", "https://p.example"), false);
  assert.equal(saveMoved("arena/x", "https://p.example", "https://q.example"), true);
  assert.equal(
    saveMoved("", "https://p.example", "https://p.example", "clankers-arena-x"),
    false,
    "A remembered scope keeps the same preview after overwrite",
  );
  assert.equal(
    saveMoved("", "https://p.example", "https://q.example", "clankers-arena-x"),
    true,
    "A new preview still moves the save",
  );
  assert.equal(
    saveMoved("arena/y", "https://p.example", "https://p.example", "clankers-arena-x", "arena/x"),
    true,
    "A new branch still moves the save",
  );

  assert.equal(overwriteAsk(true, { type: "download" }, true, false), true);
  assert.equal(overwriteAsk(true, { type: "download" }, true, true), false, "A forced save writes");
  assert.equal(overwriteAsk(false, { type: "download" }, true, false), false);
  assert.equal(overwriteAsk(true, { type: "unchanged" }, true, false), false, "Nothing to write");
  assert.equal(overwriteAsk(true, { type: "download" }, false, false), false, "No file to protect");

  // The reset window accepts a URL-only move within 150 seconds either side of the four PHT
  // boundaries. A branch move, a missing branch and an outside-window clock still ask.
  var previousBoundary = api.previousBoundary;
  var inResetWindow = api.inResetWindow;
  var resetWindowAccepts = api.resetWindowAccepts;
  assert.equal(api.resetWindowOn(), true, "the reset-window switch ships on");
  assert.equal(
    previousBoundary(new Date("2026-10-15T06:59:00Z")).toISOString(),
    "2026-10-15T06:00:00.000Z",
    "14:59 PHT sits after the 14:00 boundary",
  );
  assert.equal(
    previousBoundary(new Date("2026-10-14T17:30:00Z")).toISOString(),
    "2026-10-14T12:00:00.000Z",
    "01:30 PHT falls back to the previous 20:00 boundary",
  );
  assert.equal(inResetWindow(new Date("2026-10-15T06:02:30Z")), true, "150 seconds after 14:00 PHT");
  assert.equal(inResetWindow(new Date("2026-10-15T05:57:30Z")), true, "150 seconds before 14:00 PHT");
  assert.equal(inResetWindow(new Date("2026-10-15T06:02:31Z")), false, "151 seconds after leaves");
  assert.equal(inResetWindow(new Date("2026-10-15T05:57:29Z")), false, "151 seconds before leaves");
  assert.equal(inResetWindow(new Date("2026-10-15T00:30:00Z")), false, "08:30 PHT waits");
  var atWindow = new Date("2026-10-15T06:01:00Z");
  var outside = new Date("2026-10-15T02:00:00Z");
  assert.equal(
    resetWindowAccepts(atWindow, true, "main", "https://old.arena.site", "https://new.arena.site", "main"),
    true,
    "an in-window URL-only move writes without the prompt",
  );
  assert.equal(
    resetWindowAccepts(atWindow, false, "main", "https://old.arena.site", "https://new.arena.site", "main"),
    false,
    "the switch off keeps the prompt",
  );
  assert.equal(
    resetWindowAccepts(outside, true, "main", "https://old.arena.site", "https://new.arena.site", "main"),
    true,
    "outside the window a URL-only move still writes without the prompt",
  );
  assert.equal(
    resetWindowAccepts(atWindow, true, "dev", "https://old.arena.site", "https://new.arena.site", "main"),
    false,
    "a branch mismatch keeps the prompt",
  );
  assert.equal(
    resetWindowAccepts(atWindow, true, "", "https://old.arena.site", "https://new.arena.site", ""),
    false,
    "a missing branch keeps the prompt",
  );
  assert.equal(
    resetWindowAccepts(atWindow, true, "main", "https://new.arena.site", "https://new.arena.site", "main"),
    false,
    "a URL that did not move needs no acceptance",
  );
  const overwriteContext = {
    branch: "main", rememberedBranch: "main", lastScope: "clankers-main",
    base: "https://new.arena.site", rememberedBase: "https://old.arena.site",
    memory: { stamp: "2026-10-05T20:00:00", note: "2026-10-05T19:00:00", task: "2026-10-05T18:00:00" },
    stamp: "2026-10-06T20:00:00",
    stamps: { note: "2026-10-05T19:00:00", task: "2026-10-05T18:00:00" },
  };
  const FILE = "clankers-main.ndjson";
  const forwardOnly = overwriteLine(FILE, overwriteContext);
  assert.match(forwardOnly, /State: forward/);
  assert.equal(/Notes|Tasks/.test(forwardOnly), false, "same comparisons are omitted");
  for (const hidden of [FILE, overwriteContext.base, overwriteContext.rememberedBase, "URL", "Branch", "main"]) {
    assert.equal(forwardOnly.includes(hidden), false, hidden + " stays out of the body");
  }
  assert.equal(
    overwriteLine("other.ndjson", { ...overwriteContext, base: "https://x.example", branch: "dev" }),
    forwardOnly,
    "only stamp comparisons shape the body",
  );
  const mixed = overwriteLine(FILE, {
    ...overwriteContext, stamp: "2026-10-04T20:00:00",
    stamps: { note: "2026-10-04T19:00:00", task: "2026-10-06T18:00:00" },
  });
  assert.match(mixed, /State: older/);
  assert.match(mixed, /Notes: older/);
  assert.match(mixed, /Tasks: forward/);
  const unchanged = overwriteLine(FILE, {
    ...overwriteContext, stamp: overwriteContext.memory.stamp,
    stamps: { note: overwriteContext.memory.note, task: overwriteContext.memory.task },
  });
  assert.equal(/same|State|Notes|Tasks/.test(unchanged), false, "an all-same body names no comparison");
  assert.ok(unchanged.length > 0 && unchanged.length < mixed.length);
  const legacyStamp = overwriteLine(FILE, { ...overwriteContext, memory: overwriteContext.stamp });
  assert.match(legacyStamp, /Notes: unknown/);
  assert.match(legacyStamp, /Tasks: unknown/);
  assert.equal(legacyStamp.includes("State"), false, "the same overall stamp is omitted");
  const unknown = overwriteLine(FILE);
  assert.match(unknown, /State: unknown/);
  assert.match(unknown, /Notes: unknown/);
  assert.match(unknown, /Tasks: unknown/);
  assert.equal(unknown.includes(FILE), false);

  console.log("ok state download 32");
  // The session bar names an unpushed branch in a titled span. A pushed branch also has an
  // anchor with a /tree/ href. The repository anchor carries no branch.
  const element = (tag, title, href) => ({
    tag: tag,
    getAttribute: (name) => (name === "title" ? title || null : name === "href" ? href || null : null),
  });
  // The fake answers a selector list the way the bar does: a tag name, or any titled element.
  const matches = (el, selector) => selector.split(",").some((part) => {
    const token = part.trim();
    return token === el.tag || (token === "[title]" && el.getAttribute("title") !== null);
  });
  const docWith = (links) => ({
    querySelector: () => ({ querySelectorAll: (selector) => links.filter((el) => matches(el, selector)) }),
  });
  const repoLink = element("a", "nemoe7/clankers", "https://github.com/nemoe7/clankers");
  assert.equal(
    stateBranch(docWith([repoLink, element("span", "main \u2192 arena/1bc9bdc9-clankers")])),
    "arena/1bc9bdc9-clankers",
    "An unpushed branch reads from its titled span",
  );
  assert.equal(
    stateBranch(docWith([
      repoLink,
      element("a", "main \u2192 arena/fef1ae85-daedalus", "https://github.com/nemoe7/daedalus/tree/arena%2Ffef1ae85-daedalus"),
    ])),
    "arena/fef1ae85-daedalus",
    "A pushed branch reads from its /tree/ anchor",
  );
  assert.equal(stateBranch(docWith([repoLink])), "", "A repository link alone names no branch");
  var posted = [];
  var previewFrameNode = {
    src: "https://sbx-test.arena.site/",
    getAttribute: function (name) {
      return name === "title" ? "App preview on port 8000" : "";
    },
    contentWindow: {
      postMessage: function (payload, target) {
        posted.push([payload, target]);
      },
    },
  };
  var previewDoc = {
    querySelectorAll: function () {
      return [previewFrameNode];
    },
  };
  assert.equal(api.notifyPreviewReady(previewDoc), true);
  assert.equal(api.notifyPreviewReady(previewDoc), false);
  assert.equal(api.notifyPreviewReady(previewDoc, true), true);
  assert.equal(posted.length, 2);
  assert.equal(posted[0][0].type, "clankers:userscript-ready");
  assert.equal(posted[0][1], "https://sbx-test.arena.site");
  console.log("ok state download 34");
}

const arenaModule = loadChecks("arena.user.js");
const arena = arenaModule.checks;
test("prompt fill", () => checkPromptFill(arena.promptFill));
run("arena logging", () => checkArenaLogging(arena.logging, arenaModule.menus));
run("open steering", () => checkOpenSteering(arena.openSteering));
run("transcript auto-scroll", () => checkAutoScrollToggle(arena.autoScrollToggle));
run("transcript trim", () => checkTranscriptTrim(arena.transcriptTrim));
run("transcript alerts", () => checkTranscriptAlerts(arena.transcriptAlerts));
run("hide composer", () => checkHideComposer(arena.hideComposer));
run("tab title", () => checkTabTitle(arena.tabTitle, arena.logging));
run("state download", () => checkStateDownload(arena.stateDownload, arenaModule.session, arena.logging));
run("keep awake", () => checkKeepAwake(arena.keepAwake));
