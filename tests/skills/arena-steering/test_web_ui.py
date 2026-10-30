"""Tests for Arena Steering web UI assets (`skills/arena-steering/assets/`) and `demo.py`."""

from __future__ import annotations

import subprocess
from pathlib import Path

from arena_steering.server import create_http_server, reload_server_handler
from arena_steering.store import SqliteStore
from demo import SCROLLSPY_ZONES_SVG, TOKENS_SWATCH_SVG, seed_demo_store
from demo import main as demo_main

SKILL_DIR = Path(__file__).resolve().parents[3] / "skills" / "arena-steering"
ASSETS_DIR = SKILL_DIR / "assets"

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


def test_demo_script_seeds_messages_tasks_and_reports(tmp_path: Path) -> None:
  code = demo_main(["--seed-only", "--state-dir", str(tmp_path)])
  assert code == 0

  store = SqliteStore(tmp_path / "state.sqlite3")
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
  assert b"<title>clankers - Steering</title>" in root_asset[0]

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

  demo_py = (SKILL_DIR / "scripts" / "demo.py").read_text(encoding="utf-8")
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

  markdown_js = (ASSETS_DIR / "markdown.js").read_text(encoding="utf-8")
  assert "<mark>$1</mark>" in markdown_js


def test_composer_upload_drop_expand_assets() -> None:
  messages_js = (ASSETS_DIR / "messages-view.js").read_text(encoding="utf-8")
  assert COMPOSER_ATTACHMENTS_ID in messages_js
  assert ATTACH_FILE_ID in messages_js
  assert COMPOSER_EXPAND_ID in messages_js
  assert "data-remove-composer-attachment" in messages_js
  assert "composer-attachment-chip" in messages_js
  assert "PASTE_ATTACHMENT_CHAR_THRESHOLD = 2400" in messages_js
  assert "PASTE_ATTACHMENT_LINE_THRESHOLD = 40" in messages_js
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
  assert COMPOSER_ATTACHMENTS_STATE in app_js
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
