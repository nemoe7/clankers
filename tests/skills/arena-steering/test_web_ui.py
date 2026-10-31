"""Tests for Arena Steering web UI assets (`skills/arena-steering/assets/`) and `demo.py`."""

from __future__ import annotations

import os
import runpy
import subprocess
import threading
from pathlib import Path

import pytest
from arena_steering.server import (
  SteeringApp,
  create_http_server,
  reload_server_handler,
)
from arena_steering.store import SqliteStore

ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = ROOT / "skills" / "arena-steering"
ASSETS_DIR = SKILL_DIR / "assets"
DEMO_PATH = ROOT / "maintenance" / "demo-arena-steer.py"
DEMO = runpy.run_path(str(DEMO_PATH))
SCROLLSPY_ZONES_SVG = DEMO["SCROLLSPY_ZONES_SVG"]
TOKENS_SWATCH_SVG = DEMO["TOKENS_SWATCH_SVG"]
seed_demo_store = DEMO["seed_demo_store"]
demo_main = DEMO["main"]

EXPECTED_FONTS = (
  "Basel_Grotesk_Bold.woff2",
  "Basel_Grotesk_Book.woff2",
  "Basel_Grotesk_Medium.woff2",
  "Basel_Grotesk_Mono_Regular.woff2",
  "Basel_Grotesk_Regular.woff2",
)

EXPECTED_JS_MODULES = (
  "api.js",
  "app.js",
  "messages-view.js",
  "markdown.js",
  "modal.js",
  "reports-view.js",
  "state.js",
  "tasks-view.js",
  "timestamps.js",
)

PRELOAD_ATTR = 'rel="preload"'
MODULEPRELOAD_ATTR = 'rel="modulepreload"'
MODAL_SHELL_ID = 'id="modal-shell"'
CONFIRM_DELETE_TPL = 'data-modal-template="confirm-delete"'
SURFACE_TOKEN = "--surface-primary:"
CTA_TOKEN = "--interactive-cta:"
CODE_BG_TOKEN = "--code-bg:"
INLINE_CODE_RULE = ":not(pre) > code:not(.msg-id)"
MAIN_MAX_WIDTH = "max-width: 900px;"
MESSAGE_TEXT_FONT_SIZE = "font-size: 16px;"
STATUS_BANNER_ID = "status-banner"
THEME_TOGGLE_ID = "theme-toggle"
TOPBAR_BRAND_CLASS = "topbar-brand"
ARENA_SCROLLBAR_RULE = (
  "scrollbar-color: hsl(var(--surface-raised-alt) / 0.4) transparent;"
)
SCROLLBAR_NO_HIGHLIGHT_RULE = "::-webkit-scrollbar-thumb:hover"
FONT_DISPLAY_BLOCK = "font-display: block;"
EDGE_LOADING_KEYFRAME = "nuu-edge-loading"
CUSTOM_OPTION_MARKER = "__custom__"
HISTORY_LIST_ID = 'id="history"'
COMPOSER_SHELL_CLASS = 'class="composer-shell"'
MANUAL_BLOCKING_INPUT = "inbox-blocking"
MANUAL_HIDDEN_INPUT = "inbox-hidden"
LUCIDE_CLOSE_ICON = "lucide-x"
LUCIDE_LOCK_ICON = "lucide-lock"
LUCIDE_CHEVRON_DOWN_ICON = "lucide-chevron-down"
SELECT_CHEVRON_CLASS = "select-chevron"
LUCIDE_COPY_ICON = "lucide-copy"
LUCIDE_SEND_ICON = "lucide-send"
REPORT_TOC_ID = 'id="report-toc"'
REPORT_PICKER_ID = 'id="report-picker"'
REPORT_RAIL_ID = 'id="report-rail"'
OPTION_CUSTOM_CLASS = "option-custom"
ON_THIS_PAGE_TEXT = "On this page"
REPORT_PICKER_META_CLASS = "report-picker-meta"
TASK_SECTION_TITLE_FONT_SIZE = "font-size: 18px;"


NOTES_PIP_ID = 'id="notes-pip"'
REPORT_PIP_ID = 'id="report-pip"'
TAB_BADGE_CLASS = "tab-badge"
REPORT_ACKED_EVENT = "report.acked"
REPORT_ACK_SEEN_API = "markReportAckSeen"
REPORT_ACK_SEEN_PATH = "/ack-seen"
REPORT_ACKED_HANDLER = "onReportAcked"
REPORT_SUBMIT_ID = 'id="report-submit"'
REPORT_SUBMIT_FLOAT_ID = 'id="report-submit-float"'
REPORT_SUBMIT_FLOAT_CLASS = "report-submit-float"
REPORT_SUBMIT_SPACER_RULE = ".report-submit-row > #report-submit"
REPORT_SUBMIT_FLOAT_RULE = ".report-submit-float {"
CLOCK_ID = 'id="clock"'
RECEIPT_ID_CLASS = "receipt-id"
REPLY_PARENT_CHIP_CLASS = "reply-parent-chip"
COMPOSER_REPLY_BAR_ID = 'id="composer-reply-bar"'
COMPOSER_REPLY_CHIP_CLASS = "composer-reply-chip"
PARENT_IDS_FIELD = "parent_ids"
REPLY_PARENT_IDS_STATE = "replyParentIds"
TOGGLE_REPLY_PARENT_HANDLER = "onToggleReplyParent"
STATIC_ASSET_PREFIX = "/static/assets/"
STATIC_STYLE_HREF = 'href="/static/assets/style.css"'
STATIC_APP_SRC = 'src="/static/assets/app.js"'
ROOT_STYLE_HREF = 'href="/style.css"'
MARK_RULE = "mark {"
COMPOSER_ATTACHMENTS_ID = 'id="composer-attachments"'
ATTACH_FILE_ID = 'id="attach-file"'
COMPOSER_EXPAND_ID = 'id="composer-expand"'
COMPOSER_ATTACHMENTS_STATE = "composerAttachments"
COMPOSER_EXPANDED_STATE = "composerExpanded"
UPLOAD_FILE_API = "uploadFile"
SEND_MESSAGE_WITH_FILE_API = "sendMessageWithFile"

# Hex values of the warm Arena tokens in `assets/style.css` `:root`
# (HSL token channels converted to sRGB, plus its literal hex tokens).
WARM_SURFACE_PRIMARY = "#252523"
WARM_SURFACE_SECONDARY = "#2c2b28"
WARM_SURFACE_TERTIARY = "#1b1a19"
WARM_SURFACE_RAISED_TERTIARY = "#292624"
WARM_TEXT_PRIMARY = "#f4f0eb"
WARM_TEXT_TERTIARY = "#c7c2bc"
WARM_BORDER_FAINT = "#413d39"
WARM_BORDER_MEDIUM = "#524c47"
WARM_ACCENT = "#e5bb8b"
WARM_DOT_SEEN = "#7fa7d1"
WARM_DOT_SAID = "#8dc07f"
WARM_ACCENT_RGB = "(229, 187, 139)"
WARM_SURFACE_PRIMARY_HSL = '"60 3% 14%"'
WARM_SURFACE_RAISED_HSL = '"24 6% 24%"'

SLATE_MERMAID_COLORS = (
  "#22252b",
  "#2b2f37",
  "#242830",
  "#68b5f8",
  "#4a505c",
  "#1b1e23",
  "#373b44",
  "#9da3ae",
  "#f3f4f6",
  "#f9fafb",
)
SLATE_DEMO_COLORS = (
  "#14171c",
  "#343944",
  "#242830",
  "#1c2026",
  "#171a20",
  "#191c22",
  "#2e3440",
  "#68b5f8",
  "#f59e0b",
  "#34d399",
  "#e5e7eb",
  '"220 15% 11%"',
  '"220 14% 16%"',
  "(20, 23, 28)",
  "(52, 57, 68)",
  "(36, 40, 48)",
  "(28, 32, 38)",
  "(104, 181, 248)",
  "(120, 128, 142)",
  "(24, 27, 32)",
  "(42, 47, 56)",
  "(245, 158, 11)",
  "(52, 211, 153)",
)


def test_assets_bundle_fonts_styles_and_es_modules() -> None:
  for font in EXPECTED_FONTS:
    font_path = ASSETS_DIR / font
    assert font_path.is_file(), f"Missing font {font}"
    assert font_path.stat().st_size > 10_000

  for js_file in EXPECTED_JS_MODULES:
    js_path = ASSETS_DIR / js_file
    assert js_path.is_file(), f"Missing ES module {js_file}"
    proc = subprocess.run(
      ["node", "--check", str(js_path)],
      capture_output=True,
      text=True,
      check=False,
    )
    assert proc.returncode == 0, proc.stderr

  index_html = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")
  assert PRELOAD_ATTR in index_html
  assert MODULEPRELOAD_ATTR in index_html
  for js_file in EXPECTED_JS_MODULES:
    assert f'rel="modulepreload" href="/static/assets/{js_file}"' in index_html
  assert MODAL_SHELL_ID in index_html
  assert CONFIRM_DELETE_TPL in index_html
  assert LUCIDE_CLOSE_ICON in index_html
  assert NOTES_PIP_ID not in index_html
  assert REPORT_PIP_ID in index_html
  assert TAB_BADGE_CLASS not in index_html
  assert STATUS_BANNER_ID not in index_html
  assert THEME_TOGGLE_ID not in index_html
  assert TOPBAR_BRAND_CLASS not in index_html

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert STATUS_BANNER_ID not in app_js
  assert THEME_TOGGLE_ID not in app_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert SURFACE_TOKEN in style_css
  assert CTA_TOKEN in style_css
  assert CODE_BG_TOKEN in style_css
  assert INLINE_CODE_RULE in style_css
  assert MAIN_MAX_WIDTH in style_css
  assert MESSAGE_TEXT_FONT_SIZE in style_css
  assert TASK_SECTION_TITLE_FONT_SIZE in style_css
  assert ARENA_SCROLLBAR_RULE in style_css
  assert SCROLLBAR_NO_HIGHLIGHT_RULE in style_css
  assert "grid-auto-columns: 1fr;" in style_css
  assert ".main-content:has(> #view-messages:not([hidden]))" in style_css
  assert "margin-block: 0 8px;" in style_css
  assert STATUS_BANNER_ID not in style_css
  assert FONT_DISPLAY_BLOCK in style_css
  assert EDGE_LOADING_KEYFRAME in style_css
  assert SELECT_CHEVRON_CLASS in style_css

  messages_js = (ASSETS_DIR / "messages-view.js").read_text(encoding="utf-8")
  assert HISTORY_LIST_ID in messages_js
  assert COMPOSER_SHELL_CLASS in messages_js
  assert MANUAL_BLOCKING_INPUT not in messages_js
  assert MANUAL_HIDDEN_INPUT not in messages_js

  tasks_js = (ASSETS_DIR / "tasks-view.js").read_text(encoding="utf-8")
  assert LUCIDE_LOCK_ICON not in tasks_js
  assert "Report: " in tasks_js
  assert "Needs: " in tasks_js
  assert LUCIDE_CHEVRON_DOWN_ICON in tasks_js
  assert SELECT_CHEVRON_CLASS in tasks_js

  reports_js = (ASSETS_DIR / "reports-view.js").read_text(encoding="utf-8")
  assert CUSTOM_OPTION_MARKER in reports_js
  assert LUCIDE_COPY_ICON in reports_js
  assert LUCIDE_CLOSE_ICON in reports_js
  assert LUCIDE_SEND_ICON in reports_js
  assert REPORT_TOC_ID in reports_js
  assert REPORT_PICKER_ID in reports_js
  assert REPORT_RAIL_ID in reports_js
  assert OPTION_CUSTOM_CLASS in reports_js
  assert ON_THIS_PAGE_TEXT not in reports_js
  assert REPORT_PICKER_META_CLASS not in reports_js
  assert "report-picker-markers" in reports_js
  assert "report-picker-unseen-dot" in reports_js
  assert "report-picker-unanswered" in reports_js
  assert "reportCache" in app_js
  assert "ensureReportCached" in app_js
  assert "connectWebSocket" in app_js
  assert '#view-reports[data-loading="true"]:not([hidden])' in style_css
  assert "margin: -67px calc(50% - 50vw) -84px;" in style_css
  assert "hydrateMermaidBlocks" in app_js
  assert "toggleCodeMermaid" in app_js
  assert "/mermaid.min.js" in index_html

  timestamps_js = (ASSETS_DIR / "timestamps.js").read_text(encoding="utf-8")
  assert "nextRelativeDelay" in timestamps_js
  assert "node.textContent !== nextText" in timestamps_js
  assert "setInterval" not in timestamps_js

  # Finished runs arrive as a server change event, so the Tasks tab never polls.
  assert "setInterval" not in app_js

  markdown_js = (ASSETS_DIR / "markdown.js").read_text(encoding="utf-8")
  assert "const renderList = () =>" in markdown_js
  assert "listItems.push({" in markdown_js
  assert 'html.push("<hr>")' in markdown_js
  # Tables follow the GitHub shape: a single bottom rule per row, no vertical rules.
  assert "padding: 6px 13px;" in style_css
  assert "border-right: 1px solid hsl(var(--border-faint));" not in style_css
  assert "margin-inline-start: 2ch;" in style_css

  reports_js = (ASSETS_DIR / "reports-view.js").read_text(encoding="utf-8")
  assert "storedValuesFor(" in reports_js
  assert "option-star" in reports_js
  assert "steer-report-drafts" in reports_js
  assert "clearDrafts(" in reports_js
  assert ".option-star {" in style_css


def test_served_app_pushes_finished_runs(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  before = app.data_version()
  runs = tmp_path / "runs"
  runs.mkdir()
  exit_path = runs / "gate-1.exit"
  exit_path.write_text("0\n", encoding="utf-8")
  assert app.data_version() != before

  after_first = app.data_version()
  (runs / "gate-2.exit").write_text("0\n", encoding="utf-8")
  assert app.data_version() != after_first


def test_demo_script_seeds_messages_tasks_and_reports(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  monkeypatch.chdir(tmp_path)
  code = demo_main(["--seed-only"])
  assert code == 0

  store = SqliteStore(tmp_path / "arena-state/demo/state.sqlite3")
  app = seed_demo_store(store)
  assert len(app.messages.list_messages(unread_only=False, include_hidden=True)) >= 35
  assert len(app.tasks.list_tasks(include_finished=True)) >= 40
  survey = app.messages.get_survey()
  assert len(survey["results"]) == 6
  reports = app.reports.list_reports(stale_only=False)
  assert len(reports) >= 4
  assert reports[0].seen is False
  assert reports[0].needs_answer is True
  assert reports[1].seen is True
  assert reports[1].needs_answer is False
  assert app.resolve_asset("/reports/layout-board.png") is not None
  assert app.resolve_asset("/reports/scroll-fade-demo.gif") is not None
  assert app.resolve_asset("/reports/loading-bar-demo.gif") is not None
  assert app.resolve_asset("/reports/tokens-swatch.svg") is not None
  assert app.resolve_asset("/reports/scrollspy-zones.svg") is not None
  assert app.resolve_asset("/uploads/inbox-capture.png") is not None
  assert app.resolve_asset("/uploads/ui-motion-preview.gif") is not None
  status_seen, payload_seen = app.dispatch("POST", f"/reports/{reports[0].id}/seen")
  assert status_seen == 200
  assert payload_seen["report"]["seen"] is True
  root_asset = app.resolve_asset("/")
  assert root_asset is not None
  assert f"<title>{tmp_path.name} - Steering</title>".encode() in root_asset[0]

  server = create_http_server(app, host="127.0.0.1", port=0)
  try:
    sock_fd = server.socket.fileno()
    reloaded_app = reload_server_handler(server, app)
    assert server.socket.fileno() == sock_fd
    status, health = reloaded_app.dispatch("GET", "/health")
    assert status == 200
    assert health["ok"] is True
    assert "asset_version" in health
  finally:
    server.server_close()
  store.close()


def test_mermaid_and_demo_media_use_warm_arena_tokens() -> None:
  markdown_js = (ASSETS_DIR / "markdown.js").read_text(encoding="utf-8")
  theme_start = markdown_js.index("themeVariables:")
  theme_end = markdown_js.index("flowchart:", theme_start)
  theme = markdown_js[theme_start:theme_end]
  for colour in (
    WARM_SURFACE_PRIMARY,
    WARM_SURFACE_SECONDARY,
    WARM_SURFACE_TERTIARY,
    WARM_SURFACE_RAISED_TERTIARY,
    WARM_TEXT_PRIMARY,
    WARM_TEXT_TERTIARY,
    WARM_BORDER_FAINT,
    WARM_BORDER_MEDIUM,
    WARM_ACCENT,
  ):
    assert colour in theme
  for colour in SLATE_MERMAID_COLORS:
    assert colour not in theme

  demo_py = DEMO_PATH.read_text(encoding="utf-8")
  for colour in (
    WARM_SURFACE_PRIMARY,
    WARM_SURFACE_SECONDARY,
    WARM_SURFACE_TERTIARY,
    WARM_TEXT_PRIMARY,
    WARM_BORDER_FAINT,
    WARM_ACCENT,
    WARM_ACCENT_RGB,
    WARM_SURFACE_PRIMARY_HSL,
    WARM_SURFACE_RAISED_HSL,
  ):
    assert colour in demo_py
  for colour in SLATE_DEMO_COLORS:
    assert colour not in demo_py

  assert WARM_SURFACE_PRIMARY in TOKENS_SWATCH_SVG
  assert WARM_ACCENT in TOKENS_SWATCH_SVG
  assert WARM_DOT_SEEN in TOKENS_SWATCH_SVG
  assert WARM_DOT_SAID in TOKENS_SWATCH_SVG
  assert WARM_ACCENT in SCROLLSPY_ZONES_SVG
  assert WARM_DOT_SAID in SCROLLSPY_ZONES_SVG


def test_report_ack_seen_live_update_assets() -> None:
  api_js = (ASSETS_DIR / "api.js").read_text(encoding="utf-8")
  assert REPORT_ACKED_EVENT in api_js
  assert REPORT_ACK_SEEN_API in api_js
  assert REPORT_ACK_SEEN_PATH in api_js
  assert REPORT_ACKED_HANDLER in api_js

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert REPORT_ACKED_HANDLER in app_js
  assert REPORT_ACK_SEEN_API in app_js
  assert "ack_seen" in app_js


def test_report_floating_submit_assets() -> None:
  reports_js = (ASSETS_DIR / "reports-view.js").read_text(encoding="utf-8")
  assert REPORT_SUBMIT_ID in reports_js
  assert REPORT_SUBMIT_FLOAT_ID in reports_js
  assert REPORT_SUBMIT_FLOAT_CLASS in reports_js
  assert "requestSubmit" in reports_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert REPORT_SUBMIT_SPACER_RULE in style_css
  assert "visibility: hidden;" in style_css
  assert REPORT_SUBMIT_FLOAT_RULE in style_css
  assert "position: fixed;" in style_css

  index_html = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")
  assert CLOCK_ID not in index_html


def test_multi_message_reply_assets() -> None:
  messages_js = (ASSETS_DIR / "messages-view.js").read_text(encoding="utf-8")
  assert RECEIPT_ID_CLASS in messages_js
  assert REPLY_PARENT_CHIP_CLASS in messages_js
  assert COMPOSER_REPLY_BAR_ID in messages_js
  assert COMPOSER_REPLY_CHIP_CLASS in messages_js
  assert PARENT_IDS_FIELD in messages_js
  assert "↪" in messages_js

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert REPLY_PARENT_IDS_STATE in app_js
  assert TOGGLE_REPLY_PARENT_HANDLER in app_js
  assert "event.shiftKey" in app_js

  api_js = (ASSETS_DIR / "api.js").read_text(encoding="utf-8")
  assert PARENT_IDS_FIELD in api_js

  state_js = (ASSETS_DIR / "state.js").read_text(encoding="utf-8")
  assert REPLY_PARENT_IDS_STATE in state_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert ".composer-reply-bar" in style_css
  assert ".reply-parent-chip" in style_css
  assert ".receipt-id" in style_css


def test_static_asset_contract_assets() -> None:
  index_html = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")
  assert STATIC_STYLE_HREF in index_html
  assert STATIC_APP_SRC in index_html
  assert ROOT_STYLE_HREF not in index_html

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert STATIC_ASSET_PREFIX in style_css
  assert MARK_RULE in style_css
  assert "--dot-said" not in style_css

  markdown_js = (ASSETS_DIR / "markdown.js").read_text(encoding="utf-8")
  assert "<mark>$1</mark>" in markdown_js


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
  assert "pasted-text.txt" in messages_js
  assert 'addEventListener("paste"' in messages_js
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
    check=False,
  )
  assert result.returncode == 0, result.stderr


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
await uploads.retry(firstId);
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
    check=False,
  )
  assert result.returncode == 0, result.stderr


def test_reference_index_omits_ambiguous_ids():
  script = r"""
import assert from 'node:assert/strict';
import { referenceTargets } from './skills/arena-steering/assets/references.js';
const index = referenceTargets({
  messages: [{id:'a1b2c3'}, {id:'shared'}],
  reports: [{id:'report-one'}, {id:'shared'}],
  tasks: [{id:'task-one'}],
});
assert.equal(index.get('a1b2c3'), 'message');
assert.equal(index.get('report-one'), 'report');
assert.equal(index.get('task-one'), 'task');
assert.equal(index.get('shared'), null);
assert.equal(index.has('unknown'), false);
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr


def test_report_navigation_preloads_on_pointer_and_keyboard_intent():
  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert 'addEventListener("pointerover", preloadReport)' in app_js
  assert 'addEventListener("focusin", preloadReport)' in app_js
  assert "pendingReportLoads" in app_js
  assert "quiet: true" in app_js


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
def test_task_answer_details_render_once_and_wrap_on_mobile(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Task detail regression")
  answer = "A" * 180
  app.reports.publish_report(
    "choice",
    "Choice",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      f'- ( ) {answer} <!-- option {{"label": "{answer}"}} -->\n'
    ),
  )
  app.tasks.create_task(
    "work", "Review choice", details=["Review"], report_ids=["choice"]
  )
  app.reports.submit_answer("choice", {"choice": answer}, answer_id="ba2001")
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
        for name, width, height in (("desktop", 1200, 700), ("mobile", 390, 844)):
          context = browser.new_context(viewport={"width": width, "height": height})
          page = context.new_page()
          errors: list[str] = []
          page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-tasks").click()
          row = page.locator('[data-task-id="work"]').first
          row.locator("summary").click()
          page.wait_for_function(
            """() => {
              const details = document.querySelector('details.task-details[open]');
              const list = details?.querySelector('.task-detail-list');
              return list && details.getBoundingClientRect().bottom >=
                list.getBoundingClientRect().bottom - 1;
            }"""
          )
          details = row.locator("li.task-detail").all_text_contents()
          assert details == ["Report: choice", "Review", f"Choice?: {answer}"]
          assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
          assert not errors
          page.screenshot(path=str(tmp_path / f"task-details-{name}.png"))
          context.close()
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
def test_tasks_toolbar_divider_remains_visible(tmp_path: Path) -> None:
  import base64

  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Task divider regression")
  app.tasks.create_task("work", "Work", details=["Review"])
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
        for name, width, height in (("desktop", 1200, 700), ("mobile", 390, 844)):
          page = browser.new_page(viewport={"width": width, "height": height})
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-tasks").click()
          toolbar = page.locator(".tasks-toolbar")
          rect = toolbar.bounding_box()
          assert rect is not None
          screenshot = page.screenshot(path=str(tmp_path / f"tasks-divider-{name}.png"))
          color = page.evaluate(
            """async ({png, x, y}) => {
              const image = new Image();
              image.src = `data:image/png;base64,${png}`;
              await image.decode();
              const canvas = document.createElement('canvas');
              canvas.width = image.width;
              canvas.height = image.height;
              const ctx = canvas.getContext('2d');
              ctx.drawImage(image, 0, 0);
              return Array.from(ctx.getImageData(x, y, 1, 1).data).slice(0, 3);
            }""",
            {
              "png": base64.b64encode(screenshot).decode("ascii"),
              "x": round(rect["x"] + rect["width"] / 2),
              "y": round(rect["y"] + rect["height"]) - 1,
            },
          )
          colors = toolbar.evaluate(
            """e => {
              const style = getComputedStyle(e);
              const rgb = value => value.match(/\\d+/g).slice(0, 3).map(Number);
              return {border: rgb(style.borderBottomColor), background: rgb(style.backgroundColor)};
            }"""
          )
          expected_contrast = sum(
            abs(border - background)
            for border, background in zip(colors["border"], colors["background"])
          )
          visible_contrast = sum(
            abs(actual - background)
            for actual, background in zip(color, colors["background"])
          )
          assert expected_contrast > 0
          assert visible_contrast >= expected_contrast / 2
          assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
          page.close()
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
def test_messages_keep_scroll_target_during_unchanged_polling() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Message scroll regression")
  for index in range(20):
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
          window.messageResponses = 0;
          const originalFetch = window.fetch.bind(window);
          window.fetch = async (...args) => {
            const response = await originalFetch(...args);
            if (String(args[0]).includes('/messages?')) {
              const json = response.json.bind(response);
              response.json = async () => {
                const value = await json();
                requestAnimationFrame(() => { window.messageResponses += 1; });
                return value;
              };
            }
            return response;
          };
        })();""")
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "window.messageResponses > 0 && document.querySelectorAll('#history .message').length > 1"
        )
        page.wait_for_load_state("networkidle")
        history = page.locator("#history")
        bounds = history.bounding_box()
        assert bounds
        page.evaluate("""() => {
          const history = document.querySelector('#history');
          history.scrollTop = history.scrollHeight / 2;
        }""")
        start = history.evaluate("element => element.scrollTop")
        assert start > 320
        page.mouse.move(
          bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
        )
        page.mouse.wheel(0, -120)
        page.wait_for_function(
          "before => document.querySelector('#history').scrollTop < before", arg=start
        )
        page.evaluate(
          "window.scrollTargetBeforePoll = document.querySelector('#history')"
        )
        count = page.evaluate("window.messageResponses")
        page.wait_for_function(
          "count => window.messageResponses > count", arg=count, timeout=6000
        )
        assert page.evaluate(
          "window.scrollTargetBeforePoll === document.querySelector('#history')"
        )
        start = history.evaluate("element => element.scrollTop")
        page.mouse.wheel(0, -120)
        page.wait_for_function(
          "before => document.querySelector('#history').scrollTop < before", arg=start
        )

        app.messages.send_message(
          "A new message arrives.", msg_id="aa1234", blocking=False
        )
        new_message = page.locator('.message[data-msg-id="aa1234"]')
        new_message.wait_for(timeout=6000)
        app.messages.ack("aa1234", "A reply arrives.")
        new_message.locator(".reply").get_by_text("A reply arrives.").wait_for(
          timeout=6000
        )
        assert page.evaluate(
          "window.scrollTargetBeforePoll === document.querySelector('#history')"
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
          window.fetch = async (...args) => {
            const response = await originalFetch(...args);
            const url = String(args[0]);
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
def test_retained_message_references_follow_loaded_targets() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Message reference paging regression")
  app.tasks.create_task("00000a", "Referenced task", details=["Review"])
  for index in range(45):
    body = f"Message {index}\n\n" + "Long scrolling content. " * 40
    if index == 44:
      body += "\n\nReferences 00000a and 00000b."
    app.messages.send_message(body, msg_id=f"{index:06x}", blocking=False)
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
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        card = page.locator('.message[data-msg-id="00002c"]')
        old_task_link = card.locator(
          '[data-auto-reference][data-reference-id="00000a"]'
        )
        old_task_link.wait_for()
        assert old_task_link.get_attribute("data-reference-type") == "task"
        assert (
          card.locator('[data-auto-reference][data-reference-id="00000b"]').count() == 0
        )
        page.evaluate(
          "window.retainedReferenceCard = document.querySelector('.message[data-msg-id=\"00002c\"]')"
        )
        page.locator("#history").evaluate("element => { element.scrollTop = 300; }")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 40"
        )
        assert page.evaluate("window.retainedReferenceCard.isConnected")
        assert old_task_link.count() == 0
        new_message_link = card.locator(
          '[data-auto-reference][data-reference-id="00000b"]'
        )
        assert new_message_link.get_attribute("data-reference-type") == "message"
        assert "00000a" in card.inner_text()
        app.tasks.remove_task("00000a")
        page.wait_for_function(
          """() => {
          const card = document.querySelector('.message[data-msg-id="00002c"]');
          const link = card?.querySelector('[data-auto-reference][data-reference-id="00000a"]');
          return link?.dataset.referenceType === 'message';
        }""",
          timeout=6000,
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
def test_report_toc_jump_keeps_heading_below_fade(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Report TOC regression")
  text = "\n\n".join(
    ["A paragraph with enough content to make the report scroll."] * 25
  )
  app.reports.publish_report(
    "long-report",
    "Long report",
    f"# First section\n\n{text}\n\n## Middle section\n\n{text}",
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
        for name, width, height in (("desktop", 1372, 700), ("mobile", 390, 844)):
          page = browser.new_page(viewport={"width": width, "height": height})
          page.add_init_script("""(() => {
            const original = Element.prototype.scrollIntoView;
            Element.prototype.scrollIntoView = function(options) {
              return original.call(this, {...options, behavior: 'instant'});
            };
          })();""")
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-reports").click()
          link = page.locator(".report-toc-link").filter(has_text="Middle section")
          link.wait_for(state="attached")
          target = link.get_attribute("data-toc-target")
          assert target
          if name == "desktop":
            link.click()
          else:
            link.evaluate("element => element.click()")
          result = page.evaluate(
            """id => {
            const pane = document.querySelector('#view-reports');
            const heading = document.getElementById(id);
            return {
              offset: heading.getBoundingClientRect().top - pane.getBoundingClientRect().top,
              fade: parseFloat(getComputedStyle(pane).getPropertyValue('--edge-fade')),
              scrollTop: pane.scrollTop,
            };
          }""",
            target,
          )
          assert result["scrollTop"] > 0
          assert result["offset"] >= result["fade"] - 1
          assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
          page.screenshot(path=str(tmp_path / f"report-toc-{name}.png"))
          page.close()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
