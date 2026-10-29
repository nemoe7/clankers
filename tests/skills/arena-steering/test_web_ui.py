"""Tests for Arena Steering web UI assets (`skills/arena-steering/assets/`) and `demo.py`."""

from __future__ import annotations

import subprocess
from pathlib import Path

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
FONT_DISPLAY_BLOCK = "font-display: block;"
EDGE_LOADING_KEYFRAME = "nuu-edge-loading"
CUSTOM_OPTION_MARKER = "__custom__"
HISTORY_LIST_ID = 'id="history"'
COMPOSER_SHELL_CLASS = 'class="composer-shell"'
MANUAL_BLOCKING_INPUT = "inbox-blocking"
MANUAL_HIDDEN_INPUT = "inbox-hidden"
LUCIDE_SUN_ICON = "lucide-sun"
LUCIDE_MOON_ICON = "lucide-moon"
LUCIDE_CLOSE_ICON = "lucide-x"
LUCIDE_PLUS_ICON = "lucide-plus"
LUCIDE_PENCIL_ICON = "lucide-pencil"
LUCIDE_TRASH_ICON = "lucide-trash-2"
LUCIDE_LOCK_ICON = "lucide-lock"
LUCIDE_COPY_ICON = "lucide-copy"
LUCIDE_SEND_ICON = "lucide-send"


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
  assert LUCIDE_SUN_ICON in index_html
  assert LUCIDE_CLOSE_ICON in index_html

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert LUCIDE_SUN_ICON in app_js
  assert LUCIDE_MOON_ICON in app_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert SURFACE_TOKEN in style_css
  assert CTA_TOKEN in style_css
  assert FONT_DISPLAY_BLOCK in style_css
  assert EDGE_LOADING_KEYFRAME in style_css

  inbox_js = (ASSETS_DIR / "inbox-view.js").read_text(encoding="utf-8")
  assert HISTORY_LIST_ID in inbox_js
  assert COMPOSER_SHELL_CLASS in inbox_js
  assert MANUAL_BLOCKING_INPUT not in inbox_js
  assert MANUAL_HIDDEN_INPUT not in inbox_js

  tasks_js = (ASSETS_DIR / "tasks-view.js").read_text(encoding="utf-8")
  assert LUCIDE_PLUS_ICON in tasks_js
  assert LUCIDE_PENCIL_ICON in tasks_js
  assert LUCIDE_TRASH_ICON in tasks_js
  assert LUCIDE_LOCK_ICON in tasks_js

  reports_js = (ASSETS_DIR / "reports-view.js").read_text(encoding="utf-8")
  assert CUSTOM_OPTION_MARKER in reports_js
  assert LUCIDE_COPY_ICON in reports_js
  assert LUCIDE_CLOSE_ICON in reports_js
  assert LUCIDE_SEND_ICON in reports_js


def test_demo_script_seeds_messages_tasks_and_reports(tmp_path: Path) -> None:
  code = demo_main(["--seed-only", "--state-dir", str(tmp_path)])
  assert code == 0

  store = SqliteStore(tmp_path / "state.sqlite3")
  app = seed_demo_store(store)
  assert len(app.messages.list_messages(unread_only=False)) >= 2
  assert len(app.tasks.list_tasks(include_finished=True)) >= 2
  assert len(app.reports.list_reports(stale_only=False)) >= 1
  store.close()
