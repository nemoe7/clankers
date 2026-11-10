"""Steering browser regression tests."""

from __future__ import annotations

import base64
import os
import struct
import subprocess
import threading
import zlib
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering.server import (
  SteeringApp,
  create_http_server,
)
from arena_steering.store import SqliteStore

ROOT = Path(__file__).resolve().parents[3]


SKILL_DIR = ROOT / "skills" / "arena-steering"


ASSETS_DIR = SKILL_DIR / "assets"


SHARED_PARENT_CHIP_FN = "renderParentChip"


RECEIPT_ID_CLASS = "receipt-id"


REPLY_PARENT_CHIP_CLASS = "reply-parent-chip"


COMPOSER_REPLY_BAR_ID = 'id="composer-reply-bar"'


COMPOSER_REPLY_CHIP_CLASS = "composer-reply-chip"


PARENT_IDS_FIELD = "parent_ids"


PARENT_REFS_FIELD = "parent_refs"


REPLY_PARENT_REFS_STATE = "replyParentRefs"


TOGGLE_REPLY_PARENT_HANDLER = "onToggleReplyParent"


COMPOSER_ATTACHMENTS_ID = 'id="composer-attachments"'


ATTACH_FILE_ID = 'id="attach-file"'


COMPOSER_EXPAND_ID = 'id="composer-expand"'


COMPOSER_ATTACHMENTS_STATE = "composerAttachments"


COMPOSER_EXPANDED_STATE = "composerExpanded"


UPLOAD_FILE_API = "uploadFile"


SEND_MESSAGE_WITH_FILE_API = "sendMessageWithFile"


def test_answer_blocks_share_one_renderer() -> None:
  dom_js = (ASSETS_DIR / "dom.js").read_text(encoding="utf-8")
  assert "export function renderAnswerBlock" in dom_js
  assert 'class="answer reply message-text' in dom_js
  for name in ("messages-view.js", "reports-view.js"):
    view_js = (ASSETS_DIR / name).read_text(encoding="utf-8")
    assert "renderAnswerBlock" in view_js, name
    assert '<div class="answer reply message-text' not in view_js, name


def test_multi_message_reply_assets() -> None:
  dom_js = (ASSETS_DIR / "dom.js").read_text(encoding="utf-8")
  assert REPLY_PARENT_CHIP_CLASS in dom_js
  assert "data-reference-type" in dom_js

  messages_js = (ASSETS_DIR / "messages-view.js").read_text(encoding="utf-8")
  assert RECEIPT_ID_CLASS in messages_js
  assert SHARED_PARENT_CHIP_FN in messages_js
  assert COMPOSER_REPLY_BAR_ID in messages_js
  assert COMPOSER_REPLY_CHIP_CLASS in messages_js
  assert PARENT_IDS_FIELD in messages_js
  assert PARENT_REFS_FIELD in messages_js

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert REPLY_PARENT_REFS_STATE in app_js
  assert TOGGLE_REPLY_PARENT_HANDLER in app_js
  assert "event.shiftKey" in app_js

  api_js = (ASSETS_DIR / "api.js").read_text(encoding="utf-8")
  assert PARENT_IDS_FIELD in api_js
  assert PARENT_REFS_FIELD in api_js

  state_js = (ASSETS_DIR / "state.js").read_text(encoding="utf-8")
  assert REPLY_PARENT_REFS_STATE in state_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert ".composer-reply-bar" in style_css
  assert ".reply-parent-chip" in style_css
  assert ".parent-id-button" in style_css


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 900])
def test_composer_hint_stays_on_one_line_without_fading_or_changing_draft(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  first_line = "First line " + "details " * 30
  app.messages.send_message(first_line + "\nSecond line must stay out", msg_id="abc123")
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        composer = page.locator("#msg")
        composer.wait_for()
        assert composer.get_attribute("placeholder") == first_line
        geometry = composer.evaluate("""element => ({
          height: element.clientHeight,
          scrollHeight: element.scrollHeight,
          wrap: getComputedStyle(element).whiteSpace,
          mask: getComputedStyle(element).maskImage,
        })""")
        assert geometry["wrap"] == "nowrap", geometry
        assert geometry["scrollHeight"] <= geometry["height"] + 1, geometry
        assert geometry["mask"] == "none", geometry
        page.screenshot(path=str(tmp_path / f"composer-hint-{width}.png"))

        composer.fill("A draft that wraps as needed")
        assert (
          composer.evaluate("element => getComputedStyle(element).whiteSpace")
          != "nowrap"
        )
        assert composer.input_value() == "A draft that wraps as needed"
        assert composer.evaluate("element => document.activeElement === element")
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    store.close()


def test_composer_upload_drop_expand_assets() -> None:
  messages_js = (ASSETS_DIR / "messages-view.js").read_text(encoding="utf-8")
  assert "readComposerDraft" in messages_js
  assert "writeComposerDraft" in messages_js
  assert "submittedDraft" in messages_js
  assert "reply-seen-sentinel" in messages_js
  assert "replies_revision" in messages_js
  assert "seenAckCounts" not in messages_js
  assert COMPOSER_ATTACHMENTS_ID in messages_js
  assert ATTACH_FILE_ID in messages_js
  assert COMPOSER_EXPAND_ID in messages_js
  assert "data-remove-composer-attachment" in messages_js
  assert "composer-attachment-chip" in messages_js
  assert 'event.key === "Enter" && !event.shiftKey && !event.isComposing' in messages_js
  assert 'window.matchMedia?.("(pointer: coarse)")?.matches' in messages_js
  assert "PASTE_ATTACHMENT_CHAR_THRESHOLD = 1500" in messages_js
  assert "PASTE_ATTACHMENT_LINE_THRESHOLD = 15" in messages_js
  assert "-pasted-lines-" in messages_js
  assert 'listen(msgEl, "paste"' in messages_js
  assert 'addEventListener("drop"' in messages_js
  assert 'addEventListener("dragover"' in messages_js
  assert "attachments" in messages_js

  api_js = (ASSETS_DIR / "api.js").read_text(encoding="utf-8")
  assert UPLOAD_FILE_API in api_js
  assert SEND_MESSAGE_WITH_FILE_API in api_js
  assert '"/uploads"' in api_js
  assert '"/messages/with-file"' in api_js
  assert "FormData" in api_js

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  uploads_js = (ASSETS_DIR / "composer-uploads.js").read_text(encoding="utf-8")
  assert COMPOSER_ATTACHMENTS_STATE in uploads_js
  assert "onStageComposerFiles" in app_js
  assert "onRemoveComposerAttachment" in app_js
  assert "onToggleComposerExpanded" in app_js
  assert SEND_MESSAGE_WITH_FILE_API in app_js

  state_js = (ASSETS_DIR / "state.js").read_text(encoding="utf-8")
  assert COMPOSER_ATTACHMENTS_STATE in state_js
  assert COMPOSER_EXPANDED_STATE in state_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert ".composer-attachments" in style_css
  assert ".composer-attachment-chip" in style_css
  assert ".composer-expanded" in style_css
  assert ".composer-drop-active" in style_css


def test_linked_tasks_do_not_break_message_rendering() -> None:
  script = """
import assert from 'node:assert/strict';
import { renderMessagesView } from './skills/arena-steering/assets/messages-view.js';
globalThis.document = { activeElement: null };
const container = {
  innerHTML: '',
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
};
renderMessagesView(container, {
  messages: [{ id: 'abc123', body: 'hello', acks: [], created_at: '2026-01-01T00:00:00Z' }],
  tasks: [{ id: 'linked-task', links: { msg_ids: ['abc123'] } }],
}, {});
assert.match(container.innerHTML, /linked-task/);
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr


def test_messages_status_shows_native_tool_cadence() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { renderMessagesView } from './skills/arena-steering/assets/messages-view.js';
globalThis.document = { activeElement: null };
const container = {
  innerHTML: '',
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
};
const at = new Date(Date.now() - 3000).toISOString();
function render(lastTool, callsSinceMessage, survey = {}) {
  container.innerHTML = '';
  renderMessagesView(container, {
    messages: [], tasks: [], survey, lastTool, callsSinceMessage,
  }, {});
  return container.innerHTML;
}
let html = render({ tool: 'read', at }, 4);
assert.match(html, /<p id="last-check" class="muted">Read <time/);
assert.doesNotMatch(html, /Read 4/);
assert.match(html, /data-include-seconds="true"/);
assert.match(html, /data-compact="true"/);
for (const [tool, label] of [['edit', 'Edit'], ['write', 'Write']]) {
  html = render({ tool, at }, 3);
  assert.match(html, new RegExp(`<p id="last-check" class="muted">${label} <time`));
  assert.doesNotMatch(html, new RegExp(`${label} 3`));
}
html = render({ tool: 'bash', at }, 2);
assert.match(html, /<p id="last-check" class="muted">Bash 2 <time/);
html = render({ tool: 'bash', at }, 0);
assert.match(html, /<p id="last-check" class="muted">Bash <time/);
assert.doesNotMatch(html, /Bash 0/);
html = render(null, 0, { checked_at: at });
assert.match(html, /<p id="last-check" class="muted">Checked <time/);
html = render(null, 0);
assert.match(html, /<p id="last-check" class="muted"><\/p>/);
assert.doesNotMatch(html, /Live steering active/);
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert "health.last_tool" in app_js
  assert "health.calls_since_message" in app_js
  signature = app_js.partition("const nextSignature = JSON.stringify({")[2].partition(
    "});"
  )[0]
  assert "lastTool," in signature
  assert "callsSinceMessage," in signature
  state_update = app_js.partition("lastDataSignature = nextSignature;")[2].partition(
    "});"
  )[0]
  assert "lastTool," in state_update
  assert "callsSinceMessage," in state_update


def test_message_receipts_show_sent_and_seen_and_name_acked_state() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { renderMessagesView } from './skills/arena-steering/assets/messages-view.js';
globalThis.document = { activeElement: null };
const container = {
  innerHTML: '',
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
};
renderMessagesView(container, {
  showHidden: true,
  messages: [
    {id: 'aa0001', body: 'Hidden seen', status: 'seen', hidden: true, blocking: false},
    {id: 'aa0002', body: 'Seen', status: 'seen', hidden: false, blocking: true},
    {id: 'aa0003', body: 'Sent', status: 'sent', hidden: false, blocking: false},
    {id: 'aa0004', body: 'Acked', status: 'acked', hidden: false, blocking: true, acks: ['Done']},
  ],
}, {});
const card = id => container.innerHTML.match(
  new RegExp(`<li class="message" data-msg-id="${id}"[\\s\\S]*?</li>`)
)?.[0];
const hidden = card('aa0001'), seen = card('aa0002'), sent = card('aa0003'), acked = card('aa0004');
assert.ok(hidden && seen && sent && acked);
assert.match(hidden, /data-hidden="true"/);
assert.match(hidden, /data-state-label="Hidden message. Status: seen" data-prefix="Seen"/);
assert.doesNotMatch(hidden, /· hidden|· checkpoint/);
assert.match(seen, /data-state-label="Status: seen" data-prefix="Seen"/);
assert.match(sent, /data-state-label="Status: sent" data-prefix="Sent"/);
assert.doesNotMatch(sent, /· checkpoint/);
assert.match(acked, /data-state-label="Status: acked" data-prefix=""/);
for (const item of [hidden, seen, sent, acked]) {
  assert.doesNotMatch(item, /state-dot/);
  assert.match(item, /<time class="receipt-bottom receipt-status"[^>]*>[^<]*<\/time>/);
}
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr


def test_image_lightbox_assets() -> None:
  index = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")
  app = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  image_modal_id = 'id="image-modal"'
  assert image_modal_id in index
  assert "image-modal" in app
  assert "wheel" in app
  assert "pointerdown" in app
  assert ".mermaid-diagram svg" in app
  assert ".mermaid-block svg" in app
  assert ".image-modal" in css


def test_image_lightbox_interactions() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync('skills/arena-steering/assets/app.js', 'utf8');
const code = source.slice(source.indexOf('function initImageModal()'), source.indexOf('function initEvents()'));
function element() {
  return { handlers: {}, addEventListener(type, fn) { this.handlers[type] = fn; },
    setPointerCapture() {}, replaceChildren(...children) { this.firstElementChild = children[0] || null; } };
}
const dialog = element(), stage = element(), close = element(), doc = element();
dialog.showModal = () => { dialog.open = true; };
dialog.close = () => { dialog.open = false; dialog.handlers.close(); };
doc.getElementById = id => ({ 'image-modal': dialog, 'image-modal-stage': stage, 'image-modal-close': close })[id];
vm.runInNewContext(code + '\ninitImageModal();', { document: doc, Math });
const clone = { style: {}, removeAttribute() {}, setAttribute() {},
  getAttribute() { return null; }, querySelector() { return null; } };
const media = { tagName: 'IMG', cloneNode() { return clone; } };
const target = { closest(selector) { return selector.startsWith('#') ? {} : media; } };
doc.handlers.click({ target, preventDefault() {} });
assert.equal(dialog.open, true);
assert.equal(stage.firstElementChild, clone);
const initial = clone.style.transform;
stage.handlers.wheel({ preventDefault() {}, deltaY: -200 });
assert.notEqual(clone.style.transform, initial);
const zoomed = clone.style.transform;
stage.handlers.pointerdown({ button: 0, pointerId: 11, clientX: 100, clientY: 100 });
stage.handlers.pointerdown({ button: 0, pointerId: 12, clientX: 200, clientY: 100 });
stage.handlers.pointermove({ pointerId: 12, clientX: 300, clientY: 100 });
const pinched = clone.style.transform;
const wheelScale = Number(/scale\(([\d.]+)\)/.exec(zoomed)[1]);
const pinchScale = Number(/scale\(([\d.]+)\)/.exec(pinched)[1]);
assert.ok(Math.abs(pinchScale - wheelScale * 2) < 1e-9, `spreading two pointers doubles the scale, got ${pinched}`);
stage.handlers.pointerup({ pointerId: 11 });
stage.handlers.pointerup({ pointerId: 12 });
stage.handlers.wheel({ preventDefault() {}, deltaY: 0 });
stage.handlers.pointerdown({ button: 0, pointerId: 1, clientX: 10, clientY: 10 });
stage.handlers.pointermove({ pointerId: 1, clientX: 50, clientY: 35 });
assert.notEqual(clone.style.transform, zoomed);
let prevented = false;
stage.handlers.dragstart({ preventDefault() { prevented = true; } });
assert.equal(prevented, true);
stage.handlers.pointerdown({ button: 0, pointerId: 2, clientX: 200, clientY: 200 });
stage.handlers.pointermove({ pointerId: 2, clientX: 260, clientY: 240 });
stage.handlers.pointerup({ pointerId: 2 });
dialog.handlers.click({ target: stage });
assert.equal(dialog.open, true, 'a pan must not close the viewer');
const styleNode = { textContent: '#mermaid-x .node{fill:red}' };
const svgClone = { style: {}, removeAttribute() {}, setAttribute(name, value) { this[name] = value; },
  getAttribute(name) { return name === 'id' ? 'mermaid-x' : null; },
  querySelector(selector) { return selector === 'style' ? styleNode : null; } };
const svgMedia = { tagName: 'svg', getBoundingClientRect() { return { width: 866 }; },
  cloneNode() { return svgClone; } };
const svgTarget = { closest(selector) { return selector.startsWith('#') ? {} : svgMedia; } };
doc.handlers.click({ target: svgTarget, preventDefault() {} });
assert.equal(svgClone.class, 'mermaid-svg');
assert.equal(svgClone.style.width, '866px');
assert.equal(svgClone.id, 'mermaid-x-viewer-1');
assert.equal(styleNode.textContent, '#mermaid-x-viewer-1 .node{fill:red}');
const markerAttr = { name: 'id', value: 'm-end' };
const markerNode = { localName: 'marker', id: 'm-end', attributes: [markerAttr],
  getAttribute(name) { return name === 'id' ? this.id : null; },
  setAttribute(name, value) { if (name === 'id') { this.id = value; markerAttr.value = value; } } };
const edgeAttr = { name: 'marker-end', value: 'url(#m-end)' };
const edgeNode = { localName: 'path', attributes: [edgeAttr],
  getAttribute() { return null; },
  setAttribute(name, value) { if (name === 'marker-end') edgeAttr.value = value; } };
const flowStyle = { localName: 'style', attributes: [], textContent: '#mermaid-y .node{filter:url(#m-end)}',
  getAttribute() { return null; }, setAttribute() {} };
const flowAttrs = [
  { name: 'id', value: 'mermaid-y' },
  { name: 'class', value: 'mermaid-svg flowchart' },
  { name: 'viewBox', value: '4 4 520 180' },
];
const flowClone = {
  localName: 'svg', id: 'mermaid-y', attributes: flowAttrs,
  style: { maxWidth: '520px', removeProperty(prop) { if (prop === 'max-width') delete this.maxWidth; } },
  removeAttribute(name) { if (name === 'id') this.id = ''; },
  setAttribute(name, value) {
    this[name] = value;
    const found = flowAttrs.find(a => a.name === name);
    if (found) found.value = value; else flowAttrs.push({ name, value });
  },
  getAttribute(name) { return flowAttrs.find(a => a.name === name)?.value ?? null; },
  querySelector(selector) { return selector === 'style' ? flowStyle : null; },
  querySelectorAll(selector) { return selector === '[id]' ? [markerNode] : [markerNode, edgeNode, flowStyle]; },
};
const flowMedia = {
  tagName: 'svg', getBoundingClientRect() { return { width: 320 }; }, cloneNode() { return flowClone; },
};
const flowTarget = { closest(selector) { return selector.startsWith('#') ? {} : flowMedia; } };
doc.handlers.click({ target: flowTarget, preventDefault() {} });
assert.equal(flowClone.class, 'mermaid-svg flowchart');
assert.equal(flowClone.style.width, '520px');
assert.equal(flowClone.style.maxWidth, undefined);
assert.equal(flowClone.id, 'mermaid-y-viewer-2');
assert.NotEqual?.(markerNode.id, 'm-end');
assert.equal(markerNode.id, 'mermaid-y-viewer-2-m-end');
assert.equal(edgeAttr.value, 'url(#mermaid-y-viewer-2-m-end)');
assert.equal(flowStyle.textContent, '#mermaid-y-viewer-2 .node{filter:url(#mermaid-y-viewer-2-m-end)}');
close.handlers.click();
stage.handlers.pointerdown({ button: 0, pointerId: 3, clientX: 300, clientY: 300 });
stage.handlers.pointerup({ pointerId: 3 });
dialog.handlers.click({ target: stage });
assert.equal(dialog.open, false, 'a click on the backdrop closes the viewer');
dialog.showModal();
close.handlers.click();
assert.equal(dialog.open, false);
assert.equal(stage.firstElementChild, null);
"""
  result = subprocess.run(
    ["node", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_message_image_attachment_uses_existing_modal_and_keeps_other_files(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)

  def png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
      struct.pack(">I", len(data))
      + tag
      + data
      + struct.pack(">I", zlib.crc32(tag + data))
    )

  png = (
    b"\x89PNG\r\n\x1a\n"
    + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    + png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x80\x40\xff"))
    + png_chunk(b"IEND", b"")
  )
  _, uploaded = app.dispatch(
    "POST",
    "/uploads",
    {"name": "evidence.png", "content_base64": base64.b64encode(png).decode("ascii")},
  )
  image = {**uploaded["attachment"], "name": 'A "photo" <today>.png'}
  _, uploaded_text = app.dispatch(
    "POST", "/uploads", {"name": "notes.txt", "text": "Keep as text."}
  )
  _, created = app.dispatch(
    "POST",
    "/messages/with-file",
    {
      "body": "See attached files.",
      "attachments": [
        image,
        uploaded_text["attachment"],
        {"name": "gone.png", "path": image["path"], "present": False},
      ],
    },
  )
  msg_id = created["message"]["id"]
  _, wrapping = app.dispatch(
    "POST",
    "/messages/with-file",
    {"body": "Wrap attached files.", "attachments": [uploaded_text["attachment"]] * 5},
  )
  wrapping_id = wrapping["message"]["id"]
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        card = page.locator(f'.message[data-msg-id="{msg_id}"]')
        thumb = card.get_by_role("button", name='View image A "photo" <today>.png')
        thumb.wait_for()
        assert thumb.get_attribute("title") is None
        assert card.locator(".message-attachment-file[title]").count() == 0
        assert card.locator(".parent-id-button[title]").count() == 0
        assert card.locator(".message-attachment-preview").count() == 1
        assert thumb.locator("img").evaluate(
          "image => image.complete && image.naturalWidth === 1"
        )
        assert card.locator(".receipt-filename").all_text_contents() == [
          "notes.txt",
          "gone.png (lost)",
        ]
        assert card.locator('img[src$=".txt"]').count() == 0
        assert thumb.locator(".attachment-name-tail").inner_text() == "ay>.png"
        assert (
          card.locator(".message-attachment-file")
          .first.locator(".attachment-name-tail")
          .inner_text()
          == "tes.txt"
        )
        assert thumb.locator(".attachment-name-head").evaluate(
          "el => el.scrollWidth > el.clientWidth"
        )
        bounds, card_bounds = thumb.bounding_box(), card.bounding_box()
        assert bounds and card_bounds
        assert bounds["width"] <= 100
        assert (
          card.locator(".message-attachment-file svg.lucide-file-text").count() == 2
        )
        assert card.locator(".message-attachment-file").count() == 2
        assert bounds["x"] >= card_bounds["x"] - 1
        assert (
          bounds["x"] + bounds["width"] <= card_bounds["x"] + card_bounds["width"] + 1
        )

        thumb.click()
        viewer = page.locator("#image-modal")
        viewer.wait_for(state="visible")
        assert (
          page.locator("#image-modal-stage > img").get_attribute("src")
          == created["message"]["attachments"][0]["url"]
        )
        page.keyboard.press("Escape")
        viewer.wait_for(state="hidden")
        thumb.focus()
        page.keyboard.press("Enter")
        viewer.wait_for(state="visible")
        page.locator("#image-modal-close").click()
        viewer.wait_for(state="hidden")
        wrapping_card = page.locator(f'.message[data-msg-id="{wrapping_id}"]')
        files = wrapping_card.locator(".message-attachment-file")
        assert files.count() == 5
        layout = files.evaluate_all("""elements => elements.map(element => {
          const rect = element.getBoundingClientRect();
          const parent = element.closest('.message-attachments').getBoundingClientRect();
          return { x: rect.x, y: rect.y, right: rect.right, parentRight: parent.right };
        })""")
        assert layout[0]["y"] == layout[1]["y"], layout
        assert layout[0]["x"] < layout[1]["x"], layout
        assert all(item["right"] <= item["parentRight"] for item in layout), layout
        if width == 390:
          assert layout[-1]["y"] > layout[0]["y"], layout
        else:
          assert all(item["y"] == layout[0]["y"] for item in layout), layout
        page.screenshot(path=str(tmp_path / f"attachment-{width}.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    store.close()


def test_composer_upload_manager_handles_failures_and_concurrent_changes():
  script = r"""
import assert from 'node:assert/strict';
import { createComposerUploads } from './skills/arena-steering/assets/composer-uploads.js';
let state = { composerAttachments: [] }, rejectFirst, calls = 0;
const store = { getState: () => state, setState: (patch) => { state = {...state, ...patch}; } };
const uploads = createComposerUploads(store, async (file) => {
  calls++;
  if (file.name === 'first' && calls === 1) return new Promise((resolve, reject) => { rejectFirst = reject; });
  return {name: file.name};
});
const first = uploads.stage([{name:'first'}]);
assert.equal(state.composerAttachments[0].status, 'uploading');
const firstId = state.composerAttachments[0].id;
await uploads.stage([{name:'second'}]);
const secondId = state.composerAttachments[1].id;
assert.deepEqual(state.composerAttachments.map(x => x.status), ['uploading', 'ready']);
rejectFirst(new Error('offline'));
await first;
assert.equal(state.composerAttachments[0].status, 'failed');
assert.equal('retry' in uploads, false);
await uploads.readyForSend([firstId]);
assert.deepEqual(state.composerAttachments.map(x => x.status), ['ready', 'ready']);
uploads.clearSent([firstId]);
assert.deepEqual(state.composerAttachments.map(x => x.name), ['second']);
uploads.remove(secondId);
assert.equal(state.composerAttachments.length, 0);
const pending = uploads.stage([{name:'first'}]);
uploads.remove(state.composerAttachments[0].id);
await pending;
assert.equal(state.composerAttachments.length, 0);
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr


def test_message_search_narrows_loaded_results_without_requerying():
  script = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync('skills/arena-steering/assets/app.js', 'utf8');
const start = source.indexOf('export function messageMatchesQuery');
const end = source.indexOf('async function fetchMessagePage');
const code = source.slice(start, end).replace('export ', '');
const context = {};
vm.runInNewContext(`${code}\nthis.messageMatchesQuery = messageMatchesQuery;`, context);
const message = { id: 'a1b2c3', body: 'Refactor the composer', parent_ids: ['dd0001'], acks: ['Agreed'] };
assert.equal(context.messageMatchesQuery(message, ''), true);
assert.equal(context.messageMatchesQuery(message, 'C'), true);
assert.equal(context.messageMatchesQuery(message, 'KK'), false);
assert.equal(context.messageMatchesQuery(message, 'com'), true);
assert.equal(context.messageMatchesQuery(message, 'dd00'), true);
assert.equal(context.messageMatchesQuery(message, 'agreed'), true);
assert.equal(context.messageMatchesQuery(message, 'zzz'), false);
"""
  result = subprocess.run(
    ["node", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr
  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert "searchBase && needle.startsWith(searchBase.query)" in app_js
  assert "searchBase = { query: activeQuery, messages: merged, hasMore }" in app_js


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_displayed_ids_choose_typed_composer_parents(
  width: int, tmp_path: Path
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="Typed composer parents")
  app.messages.send_message(
    "Parent note. Plain task-parent stays text.", msg_id="aa1001", blocking=False
  )
  app.tasks.create_task("task-parent", "Task title", size=3, details=["Review"])
  app.reports.publish_report(
    "report-parent", "Report title", "# Report title\n\n`task-parent` stays code."
  )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-tasks").click()
        task_row = page.locator('.task[data-task-id="task-parent"]')
        assert "task-parent" not in task_row.inner_text()
        task_title = task_row.locator('button.task-title[data-parent-type="task"]')
        task_title.hover()
        assert page.get_by_role("tooltip").filter(has_text="task-parent").is_visible()
        page.evaluate("""() => {
          for (const [id, top] of [['tip-top', 2], ['tip-middle', 300], ['tip-bottom', 790]]) {
            const button = document.createElement('button');
            button.id = id; button.title = 'Placement test';
            button.textContent = id;
            Object.assign(button.style, {position: 'fixed', top: `${top}px`, left: '200px', zIndex: 10000});
            document.body.append(button);
          }
        }""")
        for button_id, above in [
          ("tip-top", False),
          ("tip-middle", True),
          ("tip-bottom", True),
        ]:
          button = page.locator(f"#{button_id}")
          button.hover()
          tooltip = page.locator("#arena-title-tooltip")
          assert tooltip.is_visible()
          button_box, tip_box = button.bounding_box(), tooltip.bounding_box()
          assert button_box and tip_box
          if above:
            assert tip_box["y"] + tip_box["height"] <= button_box["y"]
          else:
            assert tip_box["y"] >= button_box["y"] + button_box["height"]
        page.evaluate(
          "document.querySelectorAll('[id^=tip-]').forEach(el => el.remove())"
        )
        assert "task-parent" in (task_title.get_attribute("aria-label") or "")
        page.screenshot(path=str(tmp_path / f"task-id-hover-{width}.png"))
        task_title.click()
        page.locator('#tab-messages[aria-selected="true"]').wait_for()
        assert page.locator("#msg").evaluate("el => document.activeElement === el")
        page.locator("#tab-reports").click()
        report_button = page.locator(
          'button[data-parent-type="report"][data-parent-id="report-parent"]'
        )
        assert report_button.get_attribute("title") is None
        assert page.locator("#copy-report-btn").get_attribute("title") is None
        assert page.locator("#dismiss-report-btn").get_attribute("title") is None
        report_button.click(modifiers=["Shift"])
        assert page.locator('#tab-reports[aria-selected="true"]').count() == 1
        assert page.locator(
          "#composer-reply-bar .composer-reply-chip"
        ).all_text_contents() == ["task-parent"]
        report_button.click()
        page.locator('#tab-messages[aria-selected="true"]').wait_for()
        assert page.locator("#msg").evaluate("el => document.activeElement === el")
        page.locator("#tab-reports").click()
        assert (
          page.locator('article#report button[data-reference-id="task-parent"]').count()
          == 0
        )
        page.locator("#tab-messages").click()
        receipt_button = page.locator(
          'button[data-parent-type="message"][data-parent-id="aa1001"]'
        ).first
        receipt_button.click(modifiers=["Shift"])
        assert page.locator(
          "#composer-reply-bar .composer-reply-chip"
        ).all_text_contents() == [
          "task-parent",
          "report-parent",
        ]
        receipt_button.click()
        chips = page.locator("#composer-reply-bar .composer-reply-chip")
        assert chips.all_text_contents() == [
          "task-parent",
          "report-parent",
          "aa1001",
        ]
        message_text = page.locator('.message[data-msg-id="aa1001"] .message-text')
        assert message_text.get_by_text("task-parent", exact=False).count() == 1
        assert message_text.locator("button").count() == 0
        page.screenshot(path=str(tmp_path / f"typed-composer-parents-{width}.png"))
        page.locator("#msg").fill("Child from browser")
        page.locator("#send").click()
        page.locator(".message").filter(has_text="Child from browser").wait_for()
        child = next(
          msg
          for msg in app.messages.list_messages(unread_only=False, include_hidden=True)
          if msg.body == "Child from browser"
        )
        assert child.parent_refs == [
          {"type": "task", "id": "task-parent"},
          {"type": "report", "id": "report-parent"},
          {"type": "message", "id": "aa1001"},
        ]
        assert child.parent_ids == ["aa1001"]
        child_row = page.locator(f'.message[data-msg-id="{child.id}"]')
        child_row.wait_for()
        assert child_row.locator(
          ".message-parents .reply-parent-chip"
        ).all_text_contents() == [
          "task-parent",
          "report-parent",
          "aa1001",
        ]
        nav = child_row.locator(
          'button.reply-parent-chip[data-reference-type="task"][data-reference-id="task-parent"]'
        )
        assert nav.get_attribute("aria-label") == "Open task task-parent"
        nav.focus()
        page.keyboard.press("Enter")
        page.locator('#tab-tasks[aria-selected="true"]').wait_for()
        highlighted_task = page.locator(
          '.task[data-task-id="task-parent"][data-highlight="true"]'
        )
        highlighted_task.wait_for()
        highlighted_color = highlighted_task.evaluate(
          "el => getComputedStyle(el).backgroundColor"
        )
        page.screenshot(path=str(tmp_path / f"task-highlight-{width}.png"))
        highlighted_task.wait_for(state="detached")
        normal_color = task_row.evaluate("el => getComputedStyle(el).backgroundColor")
        assert highlighted_color != normal_color
        page.locator("#tab-messages").click()
        child_row.locator(
          'button.reply-parent-chip[data-reference-type="report"][data-reference-id="report-parent"]'
        ).click()
        page.locator('#tab-reports[aria-selected="true"]').wait_for()
        assert (
          page.locator(
            'button[data-parent-type="report"][data-parent-id="report-parent"]'
          ).count()
          == 1
        )
        page.locator("#tab-messages").click()
        child_row.locator(
          'button.reply-parent-chip[data-reference-type="message"][data-reference-id="aa1001"]'
        ).click()
        page.locator('.message[data-msg-id="aa1001"][data-highlight="true"]').wait_for()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width,height", [(390, 844), (1200, 700)])
def test_messages_stay_at_bottom_after_send_and_reply_only_when_already_there(
  width: int, height: int, tmp_path: Path
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Messages bottom pinning")
  for idx in range(12):
    app.messages.send_message(
      f"Older message {idx}. " + "Long scrolling content. " * 40,
      msg_id=f"{idx + 1:06x}",
      blocking=False,
    )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_default_timeout(6000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        history = page.locator("#history")
        history.locator(".message").last.wait_for()
        assert history.evaluate("el => el.scrollHeight > el.clientHeight")
        page.locator("#msg").fill("Sent at bottom")
        history.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        assert (
          history.evaluate("el => el.scrollHeight - el.scrollTop - el.clientHeight")
          <= 1
        )
        page.locator("#send").click()
        sent = history.locator(".message").filter(has_text="Sent at bottom")
        sent.wait_for()
        assert (
          history.evaluate("el => el.scrollHeight - el.scrollTop - el.clientHeight")
          <= 24
        )
        sent_id = sent.get_attribute("data-msg-id")
        assert sent_id
        app.messages.ack(sent_id, "Reply at bottom. " + "Long reply content. " * 40)
        sent.locator(".reply").get_by_text("Reply at bottom", exact=False).wait_for()
        assert (
          history.evaluate("el => el.scrollHeight - el.scrollTop - el.clientHeight")
          <= 24
        )
        page.screenshot(path=str(tmp_path / f"messages-pinned-{width}.png"))

        page.locator("#msg").fill("Sent while reading earlier messages")
        history.evaluate("el => { el.scrollTop = el.scrollHeight / 2; }")
        assert history.evaluate("el => el.scrollTop") > 100
        anchor = history.evaluate("""element => {
          const viewport = element.getBoundingClientRect();
          const card = [...element.querySelectorAll('.message')].reverse().find(item => {
            const rect = item.getBoundingClientRect();
            return rect.bottom > viewport.top + 40 && rect.top < viewport.bottom - 40;
          });
          return card && {
            id: card.dataset.msgId,
            offset: card.getBoundingClientRect().top - viewport.top,
          };
        }""")
        assert anchor
        page.locator("#send").click()
        history.locator(".message").filter(
          has_text="Sent while reading earlier messages"
        ).wait_for()
        after = history.evaluate(
          """(element, id) => {
          const card = [...element.querySelectorAll('.message')].find(item => item.dataset.msgId === id);
          return {
            distance: element.scrollHeight - element.scrollTop - element.clientHeight,
            offset: card?.getBoundingClientRect().top - element.getBoundingClientRect().top,
          };
        }""",
          anchor["id"],
        )
        assert abs(after["offset"] - anchor["offset"]) <= 30, (anchor, after)
        assert after["distance"] > 100, after
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width,height", [(390, 844), (1200, 700)])
def test_message_content_growth_preserves_bottom_pin(
  tmp_path: Path, width: int, height: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  for idx in range(12):
    app.messages.send_message(
      f"Message {idx}. " + "Long content. " * 30, blocking=False
    )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        history = page.locator("#history")
        bubble = history.locator(".message-bubble").last
        bubble.wait_for()
        history.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        at_bottom = (
          "() => { const el = document.querySelector('#history'); "
          "return el.scrollHeight - el.scrollTop - el.clientHeight <= 1; }"
        )
        page.wait_for_function(at_bottom)
        bubble.evaluate("el => { el.style.minHeight = `${el.offsetHeight + 500}px`; }")
        page.wait_for_function(at_bottom, timeout=3000)
        history.evaluate("el => { el.scrollTop = el.scrollHeight / 2; }")
        page.wait_for_function(
          "() => { const el = document.querySelector('#history'); "
          "return el.scrollHeight - el.scrollTop - el.clientHeight > 100; }"
        )
        page.locator("#log-newest").wait_for(state="visible")
        old_top = history.evaluate("el => el.scrollTop")
        bubble.evaluate("el => { el.style.minHeight = `${el.offsetHeight + 500}px`; }")
        page.evaluate(
          "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
        )
        assert abs(history.evaluate("el => el.scrollTop") - old_top) <= 2
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize(
  ("wait_for_poll", "gesture"),
  [(False, "wheel"), (True, "wheel"), (False, "scrollbar"), (False, "touch")],
  ids=["quick-wheel", "slow-wheel", "scrollbar-drag", "touch-swipe"],
)
def test_messages_keep_scroll_target_while_older_page_loads(
  wait_for_poll: bool,
  gesture: str,
  tmp_path: Path,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Older message scroll regression")
  for index in range(45):
    app.messages.send_message(
      f"Message {index}\n\n" + "Long scrolling content. " * 40,
      msg_id=f"{index:06x}",
      blocking=False,
    )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
        ignore_default_args=["--hide-scrollbars"],
      )
      try:
        page = browser.new_page(
          viewport={"width": 411, "height": 800}
          if gesture == "touch"
          else {"width": 1200, "height": 700},
          is_mobile=gesture == "touch",
          has_touch=gesture == "touch",
        )
        page.set_default_timeout(6000)
        page.add_init_script("""(() => {
          const originalFetch = window.fetch.bind(window);
          window.refreshesWhileOlder = 0;
          window.fetch = async (...args) => {
            const response = await originalFetch(...args);
            const url = String(args[0]);
            if (url.includes('/messages?') && url.includes('before=') && !window.olderWasHeld) {
              window.olderWasHeld = true;
              window.olderPending = true;
              await new Promise(resolve => {
                window.releaseOlderPage = () => { window.olderPending = false; resolve(); };
              });
            } else if (url.includes('/health') && window.olderPending) {
              window.refreshesWhileOlder += 1;
            }
            return response;
          };
        })();""")
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        page.wait_for_load_state("networkidle")
        history = page.locator("#history")
        bounds = history.bounding_box()
        assert bounds
        page.evaluate("""() => {
          const history = document.querySelector('#history');
          history.scrollTop = 400;
          window.olderScrollTarget = history;
        }""")
        page.mouse.move(
          bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
        )
        page.mouse.wheel(0, -150)
        page.wait_for_function("typeof window.releaseOlderPage === 'function'")
        if wait_for_poll:
          page.wait_for_function("window.refreshesWhileOlder > 0")
          app.messages.send_message(
            "Arrived during pagination.", msg_id="aa1234", blocking=False
          )
        before_wheel = history.evaluate("element => element.scrollTop")
        page.mouse.wheel(0, 60)
        page.wait_for_function(
          "before => document.querySelector('#history').scrollTop > before",
          arg=before_wheel,
        )
        cdp = None
        drag_x = drag_y = touch_x = touch_y = 0.0
        if gesture in {"scrollbar", "touch"}:
          history.evaluate("element => { element.scrollTop = 1200; }")
          page.wait_for_function("document.querySelector('#history').scrollTop > 1000")
          start_gesture = history.evaluate("element => element.scrollTop")
          if gesture == "scrollbar":
            metrics = history.evaluate("""element => {
              const rect = element.getBoundingClientRect();
              const track = rect.height - 16;
              const thumb = Math.max(18, track * element.clientHeight / element.scrollHeight);
              return {x: rect.right - 5, y: rect.top + 8 + thumb / 2 +
                (track - thumb) * element.scrollTop / (element.scrollHeight - element.clientHeight)};
            }""")
            drag_x, drag_y = metrics["x"], metrics["y"]
            page.screenshot(path=str(tmp_path / "scrollbar-before.png"))
            page.mouse.move(drag_x, drag_y)
            page.mouse.down()
            page.mouse.move(drag_x, drag_y + 8, steps=4)
          else:
            cdp = page.context.new_cdp_session(page)
            touch_x = bounds["x"] + bounds["width"] / 2
            touch_y = max(150, min(bounds["y"] + bounds["height"] / 2, 650))
            cdp.send(
              "Input.dispatchTouchEvent",
              {"type": "touchStart", "touchPoints": [{"x": touch_x, "y": touch_y}]},
            )
            cdp.send(
              "Input.dispatchTouchEvent",
              {"type": "touchMove", "touchPoints": [{"x": touch_x, "y": touch_y - 60}]},
            )
          page.wait_for_function(
            "before => document.querySelector('#history').scrollTop > before",
            arg=start_gesture,
          )
          page.evaluate("""() => new Promise(resolve => {
            const history = document.querySelector('#history');
            let last = history.scrollTop;
            let stable = 0;
            let frames = 0;
            function tick() {
              stable = history.scrollTop === last ? stable + 1 : 0;
              last = history.scrollTop;
              if (stable >= 3 || ++frames >= 120) resolve(); else requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
          })""")
        anchor = page.evaluate("""() => {
          const history = document.querySelector('#history');
          const rect = history.getBoundingClientRect();
          const card = Array.from(history.querySelectorAll('.message')).filter(item => {
            const box = item.getBoundingClientRect();
            return box.bottom > rect.top + 40 && box.top < rect.bottom - 40;
          }).at(-1);
          window.olderAnchorCard = card;
          return {id: card.dataset.msgId, top: card.getBoundingClientRect().top - rect.top};
        }""")
        page.evaluate("window.releaseOlderPage()")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length > 20"
        )
        assert page.evaluate(
          "window.olderScrollTarget === document.querySelector('#history')"
        )
        assert page.evaluate("window.olderAnchorCard.isConnected")
        after = page.evaluate(
          """id => {
          const history = document.querySelector('#history');
          const card = history.querySelector(`[data-msg-id="${id}"]`);
          return card.getBoundingClientRect().top - history.getBoundingClientRect().top;
        }""",
          anchor["id"],
        )
        assert abs(after - anchor["top"]) <= 2
        if wait_for_poll:
          page.locator('.message[data-msg-id="aa1234"]').wait_for(timeout=6000)
        if gesture in {"scrollbar", "touch"}:
          page.screenshot(path=str(tmp_path / f"scroll-{gesture}-after.png"))
        start = history.evaluate("element => element.scrollTop")
        if gesture == "scrollbar":
          page.mouse.move(drag_x, drag_y + 28, steps=4)
          page.wait_for_function(
            "before => document.querySelector('#history').scrollTop > before", arg=start
          )
          page.mouse.up()
        elif gesture == "touch":
          assert cdp is not None
          cdp.send(
            "Input.dispatchTouchEvent",
            {"type": "touchMove", "touchPoints": [{"x": touch_x, "y": touch_y - 130}]},
          )
          page.wait_for_function(
            "before => document.querySelector('#history').scrollTop > before", arg=start
          )
          cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        else:
          page.mouse.wheel(0, -120)
          page.wait_for_function(
            "before => document.querySelector('#history').scrollTop < before", arg=start
          )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_message_search_can_page_while_an_old_query_is_loading() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Message search paging regression")
  for index in range(45):
    app.messages.send_message(
      f"Searchable message {index}\n\n" + "Long scrolling content. " * 40,
      msg_id=f"{index:06x}",
      blocking=False,
    )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.set_default_timeout(6000)
        page.add_init_script("""(() => {
          const originalFetch = window.fetch.bind(window);
          window.searchPagingRequests = [];
          window.fetch = async (...args) => {
            const url = String(args[0]);
            if (url.includes('/messages?') && url.includes('q=Searchable')) {
              window.searchPagingRequests.push(url);
            }
            const response = await originalFetch(...args);
            if (url.includes('/messages?') && url.includes('before=') && !window.heldOldPage) {
              window.heldOldPage = true;
              await new Promise(resolve => { window.releaseOldPage = resolve; });
              const json = response.json.bind(response);
              response.json = async () => {
                const result = await json();
                requestAnimationFrame(() => { window.oldPageConsumed = true; });
                return result;
              };
            }
            return response;
          };
        })();""")
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        page.wait_for_load_state("networkidle")
        page.locator("#history").evaluate("element => { element.scrollTop = 300; }")
        page.wait_for_function("typeof window.releaseOldPage === 'function'")
        page.locator("#log-search").fill("Searchable")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        page.locator("#history").evaluate("element => { element.scrollTop = 300; }")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length > 20"
        )
        page.evaluate("window.releaseOldPage()")
        page.wait_for_function("window.oldPageConsumed")
        assert page.locator("#log-search").input_value() == "Searchable"
        assert page.locator("#history .message").count() == 40
        requests = page.evaluate("window.searchPagingRequests")
        assert requests and "before=" not in requests[0], requests
        ids = page.locator("#history .message").evaluate_all(
          "elements => elements.map(element => element.dataset.msgId)"
        )
        assert ids == [f"{index:06x}" for index in range(5, 45)]
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_message_page_error_keeps_scroll_target_and_can_retry() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Message page retry regression")
  for index in range(25):
    app.messages.send_message(
      f"Message {index}\n\n" + "Long scrolling content. " * 40,
      msg_id=f"{index:06x}",
      blocking=False,
    )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.add_init_script("""(() => {
          const originalFetch = window.fetch.bind(window);
          window.fetch = async (...args) => {
            const url = String(args[0]);
            if (url.includes('/messages?') && url.includes('before=') && !window.failedOlderOnce) {
              window.failedOlderOnce = true;
              return new Response(JSON.stringify({error: 'try again'}), {
                status: 503, headers: {'content-type': 'application/json'}
              });
            }
            return originalFetch(...args);
          };
        })();""")
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        page.evaluate("""() => {
          window.retryScrollTarget = document.querySelector('#history');
          window.retryScrollTarget.scrollTop = 300;
        }""")
        error = page.locator('#history [role="alert"]')
        error.wait_for(timeout=6000)
        assert page.evaluate(
          "window.retryScrollTarget === document.querySelector('#history')"
        )
        page.evaluate("document.querySelector('#load-older-messages').click()")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 25"
        )
        assert page.locator('#history [role="alert"]').is_hidden()
        assert page.evaluate(
          "window.retryScrollTarget === document.querySelector('#history')"
        )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
@pytest.mark.parametrize("transport", ["ws", "poll"])
def test_seen_reply_receipt_keeps_message_height(
  tmp_path: Path, width: int, transport: str
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  msg_id = "aa1234"
  app.messages.send_message("Review the reply layout", msg_id=msg_id)
  receipt_requested = threading.Event()
  release_receipt = threading.Event()
  mark_seen = app.messages.mark_replies_seen

  def delayed_receipt(id_: str, revision: str) -> bool:
    receipt_requested.set()
    if not release_receipt.wait(10):
      raise RuntimeError("Seen receipt was not released")
    return mark_seen(id_, revision)

  app.messages.mark_replies_seen = delayed_receipt
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(
          viewport={"width": width, "height": 844},
          is_mobile=width == 390,
          has_touch=width == 390,
        )
        sockets: list[str] = []
        page.on("websocket", lambda socket: sockets.append(socket.url))
        url = f"http://127.0.0.1:{server.server_port}/"
        if transport == "poll":
          url += "?transport=poll"
        page.goto(url)
        card = page.locator(f'.message[data-msg-id="{msg_id}"]')
        card.wait_for()
        before = card.bounding_box()
        assert before is not None
        bottom = card.locator(".receipt-bottom")
        assert bottom.locator("*").count() == 0
        assert bottom.inner_text().startswith("Sent ")
        page.screenshot(path=str(tmp_path / f"receipt-bottom-{width}-{transport}.png"))
        assert (
          app.dispatch(
            "POST", f"/messages/{msg_id}/ack", {"markdown": "Acknowledged."}
          )[0]
          == HTTPStatus.OK
        )
        assert receipt_requested.wait(8), (
          "Reply intersection did not request a seen receipt"
        )
        sentinel = card.locator(".reply-seen-sentinel")
        sentinel.wait_for()
        pending = card.bounding_box()
        receipt_pending = card.locator(".receipt").bounding_box()
        assert pending is not None and receipt_pending is not None
        assert card.locator(".state-dot").count() == 0
        assert (
          card.locator(".receipt-status")
          .get_attribute("aria-label")
          .startswith("Status: acked, ")
        )
        assert (
          not card.locator(".receipt-status")
          .inner_text()
          .startswith(("Sent ", "Seen "))
        )
        release_receipt.set()
        sentinel.wait_for(state="detached")
        seen = card.bounding_box()
        receipt_seen = card.locator(".receipt").bounding_box()
        assert seen is not None and receipt_seen is not None
        assert app.messages.get_message(msg_id).replies_seen
        assert seen["height"] > before["height"]
        assert abs(pending["height"] - seen["height"]) < 0.5
        assert abs(receipt_pending["y"] - receipt_seen["y"]) < 0.5
        assert card.locator(".state-dot").count() == 0
        assert (
          card.locator(".receipt-status")
          .get_attribute("aria-label")
          .startswith("Status: acked, ")
        )
        card.locator(".receipt-status").hover()
        assert card.locator(".receipt-status").get_attribute("title") is None
        assert page.locator("#arena-title-tooltip").count() == 0
        page.screenshot(
          path=str(tmp_path / f"receipt-no-tooltip-{width}-{transport}.png")
        )
        assert bool(sockets) == (transport == "ws")
      finally:
        release_receipt.set()
        browser.close()
  finally:
    release_receipt.set()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("motion", ["no-preference", "reduce"])
def test_message_reference_highlights_bubble_not_row(
  tmp_path: Path, motion: str
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.messages.send_message("Target message", msg_id="aa0001")
  app.messages.send_message("Child message", msg_id="aa0002", parent_ids=["aa0001"])
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.emulate_media(reduced_motion=motion)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        row = page.locator('.message[data-msg-id="aa0001"]')
        bubble = row.locator(".message-bubble")
        bubble.wait_for()
        normal = bubble.evaluate("el => getComputedStyle(el).backgroundColor")
        row_color = row.evaluate("el => getComputedStyle(el).backgroundColor")
        page.locator(
          '.message[data-msg-id="aa0002"] .reply-parent-chip[data-reference-id="aa0001"]'
        ).click()
        row.locator(".message-bubble").wait_for()
        page.wait_for_function(
          """normal => getComputedStyle(document.querySelector(
            '.message[data-msg-id="aa0001"] .message-bubble'
          )).backgroundColor !== normal""",
          arg=normal,
        )
        assert row.evaluate("el => getComputedStyle(el).backgroundColor") == row_color
        duration = bubble.evaluate("el => getComputedStyle(el).transitionDuration")
        assert (duration != "0s") == (motion == "no-preference")
        page.screenshot(path=str(tmp_path / f"bubble-transition-{motion}.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_hidden_messages_are_cached_across_toggles(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.messages.send_message("Visible", msg_id="aa0001")
  app.messages.send_message("Hidden", msg_id="aa0002", hidden=True)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page()
        calls: list[str] = []
        page.on(
          "request",
          lambda request: (
            calls.append(request.url) if "/messages?" in request.url else None
          ),
        )
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator('.message[data-msg-id="aa0001"]').wait_for()
        toggle = page.locator("#quiet-msgs")
        toggle.click()
        hidden = page.locator('.message[data-msg-id="aa0002"]')
        hidden.wait_for()
        calls.clear()
        toggle.click()
        hidden.wait_for(state="detached")
        toggle.click()
        hidden.wait_for()
        assert calls == []
        toggle.click()
        hidden.wait_for(state="detached")
        with page.expect_response(lambda response: "/messages?" in response.url):
          pass
        calls.clear()
        toggle.click()
        hidden.wait_for()
        assert calls == []
        toggle.click()
        hidden.wait_for(state="detached")
        app.messages.send_message("New hidden", msg_id="aa0003", hidden=True)
        with page.expect_request(lambda request: "/messages?" in request.url):
          pass
        toggle.click()
        page.locator('.message[data-msg-id="aa0003"]').wait_for()
        page.screenshot(path=str(tmp_path / "hidden-cache.png"))
        toggle.click()
        page.locator('.message[data-msg-id="aa0003"]').wait_for(state="detached")
        page.evaluate("""() => {
          const original = window.fetch;
          window.holdNextMessage = true;
          window.fetch = async (url, options) => {
            if (window.holdNextMessage && String(url).startsWith('/messages?')) {
              window.holdNextMessage = false;
              await new Promise(resolve => { window.releaseMessage = resolve; });
            }
            return original(url, options);
          };
        }""")
        app.messages.send_message("Racing hidden", msg_id="aa0004", hidden=True)
        page.wait_for_function("() => typeof window.releaseMessage === 'function'")
        toggle.click()
        page.locator('.message[data-msg-id="aa0004"]').wait_for()
        page.evaluate("() => window.releaseMessage()")
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
