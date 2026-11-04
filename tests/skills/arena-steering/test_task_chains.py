"""Regression checks for ordered task phases and their completion evidence."""

from __future__ import annotations

import io
import os
import sqlite3
import subprocess
import threading
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering import cli
from arena_steering.models import Task
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.services import ReportService, TaskService
from arena_steering.store import SqliteStore

QUESTION = (
  '<!-- question {"id":"choice","label":"Choice?"} -->\n'
  'Choice?\n- ( ) Yes <!-- option {"label":"Yes"} -->\n'
)
FIRST_COMMIT = "a" * 40
SECOND_COMMIT = "b" * 40


def test_ordered_phases_survive_model_store_and_sync(tmp_path: Path) -> None:
  task = Task(size=3, id="chain", title="Report then code", types=["report", "code"])
  assert task.type == "report"
  assert task.to_dict()["current_phase"] == "report"
  assert task.to_dict()["remaining_phases"] == ["code"]
  assert Task.from_dict(task.to_dict()) == task
  with pytest.raises(ValueError, match="phase|type"):
    Task(size=3, id="empty", title="Empty", types=[])

  source = SqliteStore(tmp_path / "source.sqlite3")
  source.save_task_queue(
    [
      Task(
        size=3,
        id="chain",
        title="Report then code",
        types=["report", "code"],
        phase_index=1,
        phase_evidence=["decision", None],
      )
    ]
  )
  assert source.get_task("chain").to_dict()["phase_evidence"] == ["decision", None]
  replica = SqliteStore(tmp_path / "replica.sqlite3")
  replica.merge_rows(source.export_rows())
  restored = replica.get_task("chain")
  assert restored.types == ["report", "code"]
  assert restored.type == "code"
  assert restored.phase_index == 1
  assert restored.phase_evidence == ["decision", None]
  replica.close()
  source.close()

  legacy = SqliteStore(tmp_path / "legacy.sqlite3")
  with legacy.transaction():
    legacy._conn.execute(
      "INSERT INTO tasks (position, size, insertion_order, id, title, type, status, scope, modified_at) "
      "VALUES (0, 3, 0, 'old', 'Old task', 'docs', 'finished', '', '2026-11-01T00:00:00Z')"
    )
  old = legacy.get_task("old")
  assert old.types == ["docs"]
  assert old.phase_index == 1
  legacy.close()


def test_existing_task_table_migrates_to_single_phase(tmp_path: Path) -> None:
  database = tmp_path / "old.sqlite3"
  with sqlite3.connect(database) as conn:
    conn.execute(
      "CREATE TABLE tasks (position INTEGER NOT NULL, id TEXT PRIMARY KEY, "
      "title TEXT NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL, "
      "details_json TEXT NOT NULL DEFAULT '[]', links_json TEXT NOT NULL DEFAULT '', "
      "msg_ids_json TEXT NOT NULL DEFAULT '[]', report_ids_json TEXT NOT NULL DEFAULT '[]', "
      "deps_json TEXT NOT NULL DEFAULT '[]', modified_at TEXT NOT NULL)"
    )
    conn.execute(
      "INSERT INTO tasks (position, id, title, type, status, scope, details_json, modified_at) "
      "VALUES (0, 'old', 'Old task', 'code', 'upcoming', '', '[\"Review\"]', '2026-11-01T00:00:00Z')"
    )
  store = SqliteStore(database)
  with store.transaction():
    store._conn.execute("UPDATE tasks SET size=3 WHERE id='old'")
  assert store.get_task("old").types == ["code"]
  assert store.get_task("old").phase_index == 0
  store.save_task_queue(store.list_tasks())
  assert store.get_task("old").phase_evidence == [None]
  store.close()
  reopened = SqliteStore(database)
  assert reopened.get_task("old").types == ["code"]
  reopened.close()


def test_report_then_code_advances_without_waiting_for_its_old_report() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store, commit_verifier=lambda commit: commit)
  reports.publish_report("decision", "Decision", QUESTION)
  created = tasks.create_task(
    "chain",
    "Review and build",
    size=3,
    types=["report", "code"],
    details=["Build after the report."],
    report_ids=["decision"],
  )
  assert created.phase_index == 0
  assert tasks.get_task("chain")[1] is False
  advanced = tasks.finish_phase("chain")
  assert advanced.status == "upcoming"
  assert advanced.type == "code"
  assert advanced.phase_index == 1
  assert advanced.phase_evidence == ["decision", None]
  assert tasks.get_task("chain")[1] is False

  reports.publish_report("midphase", "Midphase question", QUESTION)
  linked = tasks.mod_links_add("chain", "midphase", link_type="report")
  assert linked.phase_index == 1
  assert tasks.get_task("chain")[1] is True
  with pytest.raises(ValueError, match="block"):
    tasks.finish_phase("chain", commit_hash=FIRST_COMMIT)
  assert tasks.get_task("chain")[0].phase_index == 1
  reports.submit_answer("midphase", {"choice": "Yes"}, answer_id="ac1001")
  assert tasks.get_task("chain")[1] is False
  done = tasks.finish_phase("chain", commit_hash=FIRST_COMMIT)
  assert done.status == "finished"
  assert done.phase_index == 2
  assert done.phase_evidence == ["decision", FIRST_COMMIT]
  store.close()


def test_phase_evidence_is_required_unique_and_immutable() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store, commit_verifier=lambda commit: commit)
  tasks.create_task(
    "work", "Code then docs", size=3, types=["code", "docs"], details=["Ship."]
  )
  with pytest.raises(ValueError, match="commit"):
    tasks.finish_phase("work")
  first = tasks.finish_phase("work", commit_hash=FIRST_COMMIT)
  assert first.status == "upcoming" and first.type == "docs"
  with pytest.raises(ValueError, match="unique|already"):
    tasks.finish_phase("work", commit_hash=FIRST_COMMIT)
  with pytest.raises(ValueError, match="phase|progress"):
    tasks.patch_task("work", {"phase_index": 0})
  with pytest.raises(ValueError, match="phase|progress"):
    tasks.patch_task("work", {"types": ["docs"]})
  tasks.mod_deets("work", "Write release notes.")
  assert tasks.get_task("work")[0].phase_evidence == [FIRST_COMMIT, None]
  done = tasks.patch_task("work", {"status": "finished", "commit_hash": SECOND_COMMIT})
  assert done.status == "finished"
  tasks.create_task("other", "Another change", size=3, type="code", details=["Ship."])
  with pytest.raises(ValueError, match="unique|already"):
    tasks.finish_phase("other", commit_hash=SECOND_COMMIT)
  assert tasks.get_task("other")[0].status == "upcoming"
  with pytest.raises(ValueError, match="upcoming|finish"):
    tasks.create_task(
      "bypass", "Bypass", size=3, type="code", status="finished", details=["Ship."]
    )
  reports.publish_report("decision", "Decision", QUESTION)
  tasks.create_task(
    "report-work", "Report first", size=3, type="report", details=["Review."]
  )
  with pytest.raises(ValueError, match="report"):
    tasks.finish_phase("report-work")
  tasks.mod_links_add("report-work", "decision", link_type="report")
  assert tasks.finish_phase("report-work").status == "finished"
  store.close()


def test_report_rename_preserves_finished_phase_evidence() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report("decision", "Decision", QUESTION)
  tasks.create_task(
    "chain",
    "Report then operate",
    size=3,
    types=["report", "ops"],
    details=["Review."],
    report_ids=["decision"],
  )
  tasks.finish_phase("chain")
  reports.rename_report("decision", "renamed-decision")
  updated, blocked = tasks.get_task("chain")
  assert updated.report_ids == ["renamed-decision"]
  assert updated.phase_evidence == ["renamed-decision", None]
  assert blocked is False
  assert tasks.finish_phase("chain").status == "finished"
  store.close()


def test_report_id_that_looks_like_commit_is_not_duplicate_commit() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store, commit_verifier=lambda commit: commit)
  reports.publish_report(FIRST_COMMIT, "Hash-shaped report ID", QUESTION)
  tasks.create_task(
    "report-work",
    "Report",
    size=3,
    type="report",
    details=["Review."],
    report_ids=[FIRST_COMMIT],
  )
  tasks.finish_phase("report-work")
  tasks.create_task("code-work", "Code", size=3, type="code", details=["Ship."])
  assert tasks.finish_phase("code-work", commit_hash=FIRST_COMMIT).status == "finished"
  store.close()


def test_http_task_create_and_patch_expose_phase_progress(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "http.sqlite3")
  app = SteeringApp(store)
  app.tasks._commit_verifier = lambda commit: commit
  app.reports.publish_report("decision", "Decision", QUESTION)
  status, created = app.dispatch(
    "POST",
    "/tasks",
    {
      "id": "chain",
      "title": "Report then code",
      "size": 3,
      "types": ["report", "code"],
      "details": ["Build."],
      "report_ids": ["decision"],
    },
  )
  assert status == HTTPStatus.CREATED
  assert created["task"]["types"] == ["report", "code"]
  status, advanced = app.dispatch("PATCH", "/tasks/chain", {"status": "finished"})
  assert status == HTTPStatus.OK
  assert advanced["task"]["status"] == "upcoming"
  assert advanced["task"]["current_phase"] == "code"
  status, _ = app.dispatch("PATCH", "/tasks/chain", {"status": "finished"})
  assert status == HTTPStatus.BAD_REQUEST
  status, done = app.dispatch(
    "PATCH", "/tasks/chain", {"status": "finished", "commit_hash": FIRST_COMMIT}
  )
  assert status == HTTPStatus.OK
  assert done["task"]["status"] == "finished"
  status, listed = app.dispatch("GET", "/tasks")
  assert listed["tasks"][0]["phase_index"] == 2
  store.close()


def test_task_view_renders_all_phase_chips_in_order() -> None:
  repo = Path(__file__).resolve().parents[3]
  script = """
import assert from 'node:assert/strict';
import { renderTasksView } from './skills/arena-steering/assets/tasks-view.js';
const container = {
  innerHTML: '', scrollTop: 0,
  querySelector() { return null; },
  querySelectorAll() { return []; },
};
renderTasksView(container, { tasks: [{
  id: 'chain', title: 'Deliver', status: 'upcoming',
  type: 'code', types: ['report', 'code', 'docs'], phase_index: 1,
  details: [], links: {}, blocked: false,
}] });
const row = container.innerHTML.split('data-task-id="chain"')[1].split('</li>')[0];
assert.match(row, /data-task-type="report"[^>]*data-phase-state="finished"/);
assert.match(row, /data-task-type="code"[^>]*data-phase-state="current"/);
assert.match(row, /data-task-type="docs"[^>]*data-phase-state="upcoming"/);
assert.ok(row.indexOf('Report') < row.indexOf('Code'));
assert.ok(row.indexOf('Code') < row.indexOf('Docs'));
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=repo,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  style = (repo / "skills/arena-steering/assets/style.css").read_text()
  assert '.task-type[data-phase-state="finished"]' in style
  assert "text-decoration: line-through" in style
  assert "opacity:" in style


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_browser_shows_faded_finished_phase_chip(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "browser.sqlite3")
  app = SteeringApp(store, repo_name="Task phases")
  app.reports.publish_report("decision", "Decision", "# Decision")
  app.tasks.create_task(
    "chain",
    "Review then operate",
    size=3,
    types=["report", "ops"],
    details=["Review."],
    report_ids=["decision"],
  )
  app.tasks.finish_phase("chain")
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
        page.set_default_timeout(5000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-tasks").click()
        chips = page.locator('.task[data-task-id="chain"] .task-type')
        assert chips.count() == 2
        assert [chip.inner_text() for chip in chips.all()] == ["Report", "Ops"]
        assert [chip.get_attribute("data-phase-state") for chip in chips.all()] == [
          "finished",
          "current",
        ]
        assert (
          chips.nth(0).evaluate("el => getComputedStyle(el).textDecorationLine")
          == "line-through"
        )
        assert float(chips.nth(0).evaluate("el => getComputedStyle(el).opacity")) < 1
        screenshot = Path(".cache/v2-task-chain-browser.png")
        screenshot.parent.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=True)
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
def test_browser_shimmers_only_for_active_task_gates(tmp_path: Path) -> None:
  import json

  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "gates.sqlite3")
  app = SteeringApp(store, repo_name="Task gate indicators")
  runs = tmp_path / "runs"
  runs.mkdir()
  for name, exit_code in (("active", None), ("failed", "7"), ("passed", "0")):
    marker = runs / f"{name}.exit"
    (runs / f"{name}.json").write_text(json.dumps({"exit_path": str(marker)}))
    if exit_code is not None:
      marker.write_text(exit_code)
    app.tasks.create_task(
      name, name.title(), size=3, details=["Verify."], gate_names=[name]
    )
  app.reports.publish_report("decision", "Decision", QUESTION)
  app.tasks.create_task(
    "waiting", "Waiting", size=3, details=["Answer."], report_ids=["decision"]
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
        page = browser.new_page(viewport={"width": 390, "height": 800})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-tasks").click()
        for name in ("active", "failed", "passed", "waiting"):
          title = page.locator(f'.task[data-task-id="{name}"] .task-title')
          title.wait_for()
          expected = name == "active"
          assert title.get_attribute("data-gate-running") == str(expected).lower()
          animation = title.evaluate(
            "element => getComputedStyle(element).animationName"
          )
          assert (animation != "none") is expected, (name, animation)
        page.screenshot(path=str(tmp_path / "task-gate-shimmer.png"))
        page.emulate_media(reduced_motion="reduce")
        title = page.locator('.task[data-task-id="active"] .task-title')
        assert (
          title.evaluate("element => getComputedStyle(element).animationName") == "none"
        )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_dirty_checkout_finish_raises_one_persisted_violation(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  checkout = tmp_path / "checkout"
  checkout.mkdir()

  def git(*args: str) -> str:
    result = subprocess.run(
      ["git", *args], cwd=checkout, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

  git("init", "-b", "test")
  git("config", "user.name", "Test")
  git("config", "user.email", "test@example.com")
  (checkout / ".gitignore").write_text("arena-state/\n")
  git("add", ".gitignore")
  git("commit", "-m", "test: ignore installed state")

  state_dir = checkout / "arena-state"
  from arena_steering.git_safety import DirtyTreeError

  store, messages, tasks, _ = cli.open_services(state_dir)
  tasks.create_task("review", "Review", size=3, type="misc", details=["Review."])
  for phase_type in ("ops", "report", "code", "docs"):
    tasks.create_task(
      phase_type, phase_type, size=3, type=phase_type, details=["Review."]
    )
  assert not git("status", "--porcelain=v1", "--untracked-files=all")
  (checkout / "unfinished.txt").write_text("dirty")
  for task_id in ("review", "ops", "report", "code", "docs"):
    with pytest.raises(DirtyTreeError, match="clean Git tree"):
      tasks.finish_phase(task_id, commit_hash=FIRST_COMMIT)
  assert tasks.get_task("review")[0].status == "upcoming"
  flag = messages.pending_violation()
  assert flag is not None and flag.hidden and flag.requires_ack
  assert flag.violation_type == "dirty-task-finish"

  with pytest.raises(DirtyTreeError, match="clean Git tree"):
    tasks.mod_scalar("review", "status", "finished")
  with pytest.raises(DirtyTreeError, match="clean Git tree"):
    tasks.patch_task("review", {"status": "finished"})
  assert messages.pending_ids() == [flag.id]
  messages.ack(flag.id, "Read; investigating the dirty tree.")
  app = SteeringApp(store)
  status, response = app.dispatch(
    "PATCH", "/tasks/review", {"status": "finished", "_request_id": "dirty-finish"}
  )
  assert status == HTTPStatus.BAD_REQUEST
  assert "clean Git tree" in response["error"]
  http_flag = messages.pending_violation()
  assert http_flag is not None and http_flag.id != flag.id
  other_store, other_messages, _, _ = cli.open_services(state_dir)
  assert other_messages.pending_violation().id == http_flag.id
  other_store.close()
  messages.ack(http_flag.id, "Read; checking the CLI finish.")
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: state_dir)
  errors = io.StringIO()
  assert cli.main(["task", "finish", "review"], out=io.StringIO(), err=errors) == 1
  assert "clean Git tree" in errors.getvalue()
  cli_flag = messages.pending_violation()
  assert cli_flag is not None and cli_flag.id not in {flag.id, http_flag.id}
  assert messages.pending_ids() == [cli_flag.id]

  (checkout / "unfinished.txt").unlink()
  assert not git("status", "--porcelain=v1", "--untracked-files=all")
  messages.ack(cli_flag.id, "Read and corrected.")
  (checkout / ".gitignore").write_text("arena-state/\n# tracked change\n")
  with pytest.raises(DirtyTreeError, match="clean Git tree"):
    tasks.finish_phase("review")
  tracked_flag = messages.pending_violation()
  assert tracked_flag is not None and tracked_flag.id != cli_flag.id
  git("restore", ".gitignore")
  messages.ack(tracked_flag.id, "Read and corrected.")
  assert tasks.finish_phase("review").status == "finished"
  store.close()


def test_git_completion_checks_clean_tree_and_remote(tmp_path: Path) -> None:
  from arena_steering.git_safety import GitCheckError, verify_completion_commit

  def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
      ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

  remote = tmp_path / "remote.git"
  checkout = tmp_path / "checkout"
  git(tmp_path, "init", "--bare", str(remote))
  git(tmp_path, "init", "-b", "task-check", str(checkout))
  git(checkout, "config", "user.name", "Test")
  git(checkout, "config", "user.email", "test@example.com")
  (checkout / "work.txt").write_text("first")
  git(checkout, "add", "work.txt")
  git(checkout, "commit", "-m", "test: first")
  first = git(checkout, "rev-parse", "HEAD")
  git(checkout, "remote", "add", "origin", str(remote))
  git(checkout, "push", "-u", "origin", "HEAD")
  assert verify_completion_commit(checkout, first) == first
  (checkout / "work.txt").write_text("dirty")
  with pytest.raises(GitCheckError, match="clean|dirty"):
    verify_completion_commit(checkout, first)
  (checkout / "work.txt").write_text("first")
  (checkout / "work.txt").write_text("second")
  git(checkout, "add", "work.txt")
  git(checkout, "commit", "-m", "test: second")
  second = git(checkout, "rev-parse", "HEAD")
  with pytest.raises(GitCheckError, match="push|local-only|remote"):
    verify_completion_commit(checkout, second)
  git(checkout, "push", "origin", "HEAD")
  assert verify_completion_commit(checkout, second) == second
  git(checkout, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
  with pytest.raises(GitCheckError, match="Remote branch comparison unavailable"):
    verify_completion_commit(checkout, second)
