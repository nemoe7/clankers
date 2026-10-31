"""Regression checks for the message log's scroll-edge fades."""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

import pytest
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "arena-steering"


def test_reduced_motion_has_static_message_edge_masks() -> None:
  css = (SKILL / "assets" / "style.css").read_text(encoding="utf-8")
  reduced = css.split("@media (prefers-reduced-motion: reduce) {", 1)[1]
  reduced = reduced.split("\n}\n", 1)[0]
  assert "#history {" in reduced
  assert "mask-image:" in reduced
  assert "--edge-start: var(--edge-stop-start);" in reduced
  assert "--edge-end: var(--edge-stop-end);" in reduced
  assert "#history[data-scrolled-start]" in reduced
  assert "--edge-start: var(--edge-fade-start);" in reduced
  assert "#history[data-scrolled-end]" in reduced
  assert "--edge-end: var(--edge-fade-end);" in reduced


def test_message_edge_flags_follow_scroll_and_resize() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { renderMessagesView } from './skills/arena-steering/assets/messages-view.js';
globalThis.document = {
  activeElement: null,
  createElement() { return { content: { querySelector() { return null; } } }; },
};
const observers = [];
globalThis.ResizeObserver = class {
  constructor(callback) { this.callback = callback; observers.push(this); }
  observe(target) { this.target = target; }
  disconnect() { this.disconnected = true; }
};
const attrs = new Set();
let pos = 0;
const history = {
  scrollHeight: 1000, clientHeight: 200, handlers: {},
  get scrollTop() { return pos; },
  set scrollTop(value) { pos = Math.max(0, Math.min(value, this.scrollHeight - this.clientHeight)); },
  toggleAttribute(name, value) { if (value) attrs.add(name); else attrs.delete(name); },
  addEventListener(type, callback) { this.handlers[type] = callback; },
  removeEventListener(type, callback) {
    assert.equal(this.handlers[type], callback);
    delete this.handlers[type];
    this.removed = (this.removed || 0) + 1;
  },
  getBoundingClientRect() { return { top: 0, bottom: 200 }; },
  querySelectorAll() { return []; },
};
let rendered = false;
const container = {
  set innerHTML(value) { rendered = true; },
  replaceChildren() { rendered = true; },
  querySelector(selector) { return rendered && selector === '#history' ? history : null; },
  querySelectorAll() { return []; },
  addEventListener() {},
};
const edges = () => [attrs.has('data-scrolled-start'), attrs.has('data-scrolled-end')];
renderMessagesView(container, { messages: [], tasks: [] }, {});
assert.deepEqual(edges(), [true, false], 'initially pinned at the bottom');
assert.equal(observers[0].target, history);
history.scrollTop = 0;
history.handlers.scroll();
assert.deepEqual(edges(), [false, true], 'top keeps first content unfaded');
history.scrollTop = 1;
history.handlers.scroll();
assert.deepEqual(edges(), [true, true], 'fade snaps on after leaving the top');
history.scrollTop = history.scrollHeight;
history.handlers.scroll();
assert.deepEqual(edges(), [true, false], 'bottom keeps last content unfaded');
history.clientHeight = history.scrollHeight;
history.scrollTop = 0;
observers[0].callback();
assert.deepEqual(edges(), [false, false], 'resize removes fades when content fits');
history.clientHeight = 200;
observers[0].callback();
assert.deepEqual(edges(), [false, true], 'resize restores the end fade on overflow');
renderMessagesView(container, { messages: [], tasks: [] }, {});
assert.equal(observers[0].disconnected, true, 'rerender disconnects the old observer');
assert.equal(history.removed, 1, 'rerender replaces the old scroll listener');
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_message_edge_fades_in_both_motion_preferences() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Synthetic scroll regression")
  for index in range(10):
    status, payload = app.dispatch(
      "POST",
      "/messages",
      {"body": f"Message {index}\n\n" + "A synthetic line of readable text.\n\n" * 5},
    )
    assert status == 201, payload
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  url = f"http://127.0.0.1:{server.server_port}/?transport=poll"
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        for motion in ("reduce", "no-preference"):
          context = browser.new_context(
            viewport={"width": 1200, "height": 700}, reduced_motion=motion
          )
          page = context.new_page()
          errors: list[str] = []
          page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
          page.goto(url, wait_until="domcontentloaded")
          page.wait_for_function(
            "() => { const e = document.querySelector('#history'); "
            "return e && e.querySelector('.message') && e.scrollHeight > e.clientHeight + 100; }"
          )

          def position(which: str, page=page) -> dict[str, object]:
            return page.evaluate(
              """async which => {
                const e = document.querySelector('#history');
                const max = e.scrollHeight - e.clientHeight;
                e.scrollTop = { top: 0, nearTop: 1, middle: max / 2, bottom: max }[which];
                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                const css = getComputedStyle(e), rect = e.getBoundingClientRect();
                const messages = e.querySelectorAll('.message');
                const length = name => parseFloat(css.getPropertyValue(name));
                return {
                  mask: css.maskImage, animation: css.animationName,
                  start: length('--edge-start'), stopStart: length('--edge-stop-start'),
                  fadeStart: length('--edge-fade-start'), end: length('--edge-end'),
                  stopEnd: length('--edge-stop-end'), fadeEnd: length('--edge-fade-end'),
                  firstTop: messages[0].getBoundingClientRect().top - rect.top,
                  lastBottom: rect.bottom - messages[messages.length - 1].getBoundingClientRect().bottom,
                };
              }""",
              which,
            )

          top = position("top")
          near_top = position("nearTop")
          middle = position("middle")
          bottom = position("bottom")
          for snapshot in (top, near_top, middle, bottom):
            assert "linear-gradient" in str(snapshot["mask"]), (motion, snapshot)
          assert top["start"] == top["stopStart"], (motion, top)
          assert top["end"] == top["fadeEnd"], (motion, top)
          assert top["firstTop"] >= top["start"], (motion, top)
          assert middle["start"] == middle["fadeStart"], (motion, middle)
          assert middle["end"] == middle["fadeEnd"], (motion, middle)
          assert bottom["start"] == bottom["fadeStart"], (motion, bottom)
          assert bottom["end"] == bottom["stopEnd"], (motion, bottom)
          assert bottom["lastBottom"] >= bottom["end"], (motion, bottom)
          if motion == "reduce":
            assert near_top["start"] == near_top["fadeStart"], near_top
            assert top["animation"] == "none", top
            page.set_viewport_size({"width": 1200, "height": 4000})
            page.wait_for_function(
              "() => { const e = document.querySelector('#history'); "
              "return e.scrollHeight <= e.clientHeight && "
              "!e.hasAttribute('data-scrolled-start') && !e.hasAttribute('data-scrolled-end'); }"
            )
            page.set_viewport_size({"width": 1200, "height": 700})
            page.wait_for_function(
              "() => { const e = document.querySelector('#history'); "
              "return e.scrollHeight > e.clientHeight && e.hasAttribute('data-scrolled-end'); }"
            )
          else:
            assert "edge-start" in str(top["animation"]), top
            assert near_top["stopStart"] < near_top["start"] < near_top["fadeStart"], (
              near_top
            )
          assert not errors, errors
          context.close()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
