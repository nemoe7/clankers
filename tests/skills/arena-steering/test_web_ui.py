"""Tests for Arena Steering web UI assets (`skills/arena-steering/assets/`) and `demo.py`."""

from __future__ import annotations

import subprocess
from pathlib import Path

from arena_steering.server import create_http_server, reload_server_handler
from arena_steering.store import SqliteStore
from demo import main as demo_main
from demo import seed_demo_store

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
  "inbox-view.js",
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
INLINE_CODE_RULE = ":not(pre) > code:not(.note-id)"
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
    assert f'rel="modulepreload" href="/{js_file}"' in index_html
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
  assert ".main-content:has(> #view-inbox:not([hidden]))" in style_css
  assert "margin-block: 0 8px;" in style_css
  assert STATUS_BANNER_ID not in style_css
  assert FONT_DISPLAY_BLOCK in style_css
  assert EDGE_LOADING_KEYFRAME in style_css
  assert SELECT_CHEVRON_CLASS in style_css

  inbox_js = (ASSETS_DIR / "inbox-view.js").read_text(encoding="utf-8")
  assert HISTORY_LIST_ID in inbox_js
  assert COMPOSER_SHELL_CLASS in inbox_js
  assert MANUAL_BLOCKING_INPUT not in inbox_js
  assert MANUAL_HIDDEN_INPUT not in inbox_js

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
