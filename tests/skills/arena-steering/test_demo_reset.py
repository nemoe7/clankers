"""Tests for resetting a running Arena Steering demo."""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
import threading
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering.server import SteeringApp, create_http_server, reload_server_handler
from arena_steering.store import SqliteStore

ROOT = Path(__file__).resolve().parents[3]
DEMO_PATH = ROOT / "maintenance" / "demo-arena-steer.py"
DEMO = runpy.run_path(str(DEMO_PATH))
KEEP_ON_FAILURE = "Keep on failure"


def test_demo_reset_command_restores_samples_without_restarting(tmp_path: Path) -> None:
  live = SqliteStore(tmp_path / "live" / "state.sqlite3")
  normal = SteeringApp(live)
  normal.messages.send_message("Live state", msg_id="fa0001")
  store = SqliteStore(tmp_path / "demo" / "state.sqlite3")
  app = DEMO["seed_demo_store"](store)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    app.messages.send_message("Demo sentinel", msg_id="fa0002")
    app.tasks.create_task("demo-sentinel", "Demo sentinel", details=["Temporary"])
    old_version = app.data_version()
    result = subprocess.run(
      [sys.executable, str(DEMO_PATH), "--reset", "--port", str(server.server_port)],
      cwd=ROOT,
      text=True,
      capture_output=True,
      timeout=15,
      check=False,
    )
    assert result.returncode == 0, result.stderr
    assert store.get_message("fa0002") is None
    assert store.get_task("demo-sentinel") is None
    assert store.get_message("a00001") is not None
    assert app.data_version() != old_version
    assert app.dispatch("GET", "/health")[0] == HTTPStatus.OK
    assert normal.dispatch("POST", "/demo/reset")[0] == HTTPStatus.NOT_FOUND
    assert live.get_message("fa0001").body == "Live state"
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
    live.close()


def test_demo_reset_rolls_back_on_seed_failure(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  store = SqliteStore(tmp_path / "demo" / "state.sqlite3")
  app = DEMO["seed_demo_store"](store)
  app.messages.send_message(KEEP_ON_FAILURE, msg_id="fa0003")
  globals_ = DEMO["reseed_demo_store"].__globals__

  def fail_media(_store: SqliteStore) -> None:
    raise RuntimeError("seed failed")

  monkeypatch.setitem(globals_, "_write_demo_media_files", fail_media)
  try:
    status, body = app.dispatch("POST", "/demo/reset")
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "seed failed" in body["error"]
    assert store.get_message("fa0003").body == KEEP_ON_FAILURE
    assert store.get_message("a00001") is not None
  finally:
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_running_demo_reset_refreshes_connected_browser(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "demo" / "state.sqlite3")
  app = DEMO["seed_demo_store"](store)
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
        page.set_default_timeout(10000)
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        response = page.request.post(
          f"http://127.0.0.1:{server.server_port}/messages",
          data={"id": "fa0004", "body": "Temporary demo message"},
        )
        assert response.ok
        page.get_by_text("Temporary demo message").wait_for()
        response = page.request.post(
          f"http://127.0.0.1:{server.server_port}/reports",
          data={
            "id": "steering-architecture",
            "title": "Temporary demo report",
            "body": "# Temporary demo report body",
          },
        )
        assert response.ok
        page.locator("#tab-reports").click()
        page.get_by_role("heading", name="Temporary demo report body").wait_for()
        old_version = app.reports.get_report("steering-architecture").modified_at
        result = subprocess.run(
          [
            sys.executable,
            str(DEMO_PATH),
            "--reset",
            "--port",
            str(server.server_port),
          ],
          cwd=ROOT,
          text=True,
          capture_output=True,
          timeout=15,
          check=False,
        )
        assert result.returncode == 0, result.stderr
        assert app.reports.get_report("steering-architecture").modified_at > old_version
        page.get_by_role("heading", name="Temporary demo report body").wait_for(
          state="detached"
        )
        page.locator("#tab-messages").click()
        page.get_by_text("Temporary demo message").wait_for(state="detached")
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_running_demo_reset_survives_server_hot_reload(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "demo" / "state.sqlite3")
  app = DEMO["seed_demo_store"](store)
  server = create_http_server(app, host="0.0.0.0", port=0)
  try:
    old_version = app.data_version()
    reloaded = reload_server_handler(server, app)
    reloaded.messages.send_message("Before reset", msg_id="fa0005")
    status, body = reloaded.dispatch("POST", "/demo/reset")
    assert status == HTTPStatus.OK and body["reset"] is True
    assert reloaded.store.get_message("fa0005") is None
    assert reloaded.store.get_message("a00001") is not None
    assert app.data_version() != old_version
    reloaded.store.close()
  finally:
    server.server_close()
    store.close()
