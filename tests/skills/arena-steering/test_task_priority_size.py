"""Priority/size ranking and the in-place task estimate migration contract."""

from __future__ import annotations

import io
import json
import sqlite3
import subprocess
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering import cli
from arena_steering.models import Task
from arena_steering.server import SteeringApp
from arena_steering.services import TaskService
from arena_steering.store import SqliteStore


@pytest.mark.parametrize("size", [None, 0, 4, 35, "5", True, 3.0, -1])
def test_task_rejects_missing_or_non_deck_size(size: object) -> None:
  with pytest.raises(ValueError, match="Task.size"):
    Task("work", "Work", size=size)


@pytest.mark.parametrize("priority", ["P0", "P6", "p2", "urgent", 1, None])
def test_task_rejects_invalid_priority(priority: object) -> None:
  with pytest.raises(ValueError, match="Task.priority"):
    Task("work", "Work", size=3, priority=priority)


@pytest.mark.parametrize(
  ("task_type", "types", "priority", "expected"),
  [
    ("report", None, None, "P3"),
    ("report", ["report", "report"], None, "P3"),
    ("code", ["code", "report"], None, "P4"),
    ("code", ["report", "code"], None, "P4"),
    ("code", None, None, "P4"),
    ("report", None, "P5", "P5"),
    ("report", None, "P1", "P1"),
  ],
)
def test_new_task_priority_default(
  task_type: str, types: list[str] | None, priority: str | None, expected: str
) -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  task = tasks.create_task(
    "work",
    "Work",
    size=1,
    type=task_type,
    types=types,
    priority=priority,
    details=["Work."],
  )
  assert task.priority == expected
  assert task.priority_explicit is (priority is not None)
  store.close()


def test_mixed_phase_default_applies_to_task_api() -> None:
  store = SqliteStore(":memory:")
  app = SteeringApp(store)
  status, payload = app.dispatch(
    "POST",
    "/tasks",
    {
      "id": "work",
      "title": "Work",
      "size": 1,
      "types": ["code", "report"],
      "details": ["Work."],
    },
  )
  assert status == HTTPStatus.CREATED
  assert payload["task"]["priority"] == "P4"
  store.close()


def test_task_fields_round_trip_and_persist_across_edits_and_reopen(
  tmp_path: Path,
) -> None:
  path = tmp_path / "tasks.sqlite3"
  store = SqliteStore(path)
  tasks = TaskService(store, store)
  created = tasks.create_task("work", "Work", size=8, priority="P2", details=["Build."])
  assert created.to_dict()["size"] == 8
  assert created.to_dict()["priority"] == "P2"
  original_order = created.insertion_order
  assert Task.from_dict(created.to_dict()) == created
  tasks.mod_deets("work", "Test.")
  tasks.rename_task("work", "renamed")
  store.close()

  reopened = SqliteStore(path)
  renamed = reopened.get_task("renamed")
  assert renamed is not None
  assert (renamed.priority, renamed.size, renamed.insertion_order) == (
    "P2",
    8,
    original_order,
  )
  reopened.close()


def test_priority_then_size_then_insertion_order_with_dependency_precedence() -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  for task_id, priority, size in (
    ("big", "P3", 13),
    ("small-a", "P3", 3),
    ("small-b", "P3", 3),
    ("urgent", "P1", 21),
    ("second", "P2", 1),
  ):
    tasks.create_task(
      task_id, task_id, priority=priority, size=size, details=["Build."]
    )
  ids = lambda: [task.id for task, _ in tasks.list_tasks()]
  assert ids() == ["urgent", "second", "small-a", "small-b", "big"]
  original_order = tasks.get_task("small-b")[0].insertion_order
  tasks.patch_task("small-b", {"priority": "P1", "size": 1})
  assert ids() == ["small-b", "urgent", "second", "small-a", "big"]
  assert tasks.get_task("small-b")[0].insertion_order == original_order
  tasks.mod_deps_add("small-b", "big")
  assert ids().index("big") < ids().index("small-b")
  tasks.mod_deps_rm("small-b", "big")
  assert ids()[0] == "small-b"
  with pytest.raises(ValueError, match="position"):
    tasks.patch_task("big", {"position": 0})
  assert ids()[-1] == "big"
  store.close()


def test_finished_history_keeps_its_existing_order_when_active_rank_changes() -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  tasks.create_task("done-first", "First", size=13, type="ops", details=["Ship."])
  tasks.finish_phase("done-first")
  tasks.create_task("done-second", "Second", size=1, type="ops", details=["Ship."])
  tasks.finish_phase("done-second")
  tasks.create_task("active", "Active", size=21, priority="P5", details=["Build."])
  tasks.patch_task("active", {"priority": "P1", "size": 1})
  assert [task.id for task, _ in tasks.list_tasks(include_finished=True)] == [
    "active",
    "done-first",
    "done-second",
  ]
  store.close()


def test_new_insertion_order_never_reuses_deleted_high_water_mark(
  tmp_path: Path,
) -> None:
  path = tmp_path / "tasks.sqlite3"
  store = SqliteStore(path)
  tasks = TaskService(store, store)
  tasks.create_task("first", "First", size=3, details=["Build."])
  removed = tasks.create_task("removed", "Removed", size=3, details=["Build."])
  tasks.remove_task("removed")
  store.close()

  reopened = SqliteStore(path)
  tasks = TaskService(reopened, reopened)
  newest = tasks.create_task("newest", "Newest", size=3, details=["Build."])
  assert newest.insertion_order > removed.insertion_order
  assert [task.id for task, _ in tasks.list_tasks()] == ["first", "newest"]
  reopened.close()


def test_old_database_requires_individual_estimates_instead_of_a_generic_size(
  tmp_path: Path,
) -> None:
  path = tmp_path / "legacy.sqlite3"
  with sqlite3.connect(path) as conn:
    conn.execute(
      "CREATE TABLE tasks (position INTEGER NOT NULL, id TEXT PRIMARY KEY, "
      "title TEXT NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL, "
      "details_json TEXT NOT NULL DEFAULT '[]', msg_ids_json TEXT NOT NULL DEFAULT '[]', "
      "report_ids_json TEXT NOT NULL DEFAULT '[]', deps_json TEXT NOT NULL DEFAULT '[]', "
      "modified_at TEXT NOT NULL)"
    )
    conn.execute(
      "INSERT INTO tasks (position, id, title, type, status, scope, modified_at) "
      "VALUES (7, 'legacy', 'Legacy', 'ops', 'upcoming', '', '2026-11-01T00:00:00Z')"
    )
  store = SqliteStore(path)
  with pytest.raises(ValueError, match="size|estimate"):
    store.get_task("legacy")
  with store.transaction():
    store._conn.execute("UPDATE tasks SET size=5 WHERE id='legacy'")
  assert (store.get_task("legacy").priority, store.get_task("legacy").size) == ("P3", 5)
  assert store.get_task("legacy").insertion_order == 7
  store.close()


def test_api_requires_size_and_rejects_position_mutation() -> None:
  store = SqliteStore(":memory:")
  app = SteeringApp(store)
  body = {"id": "build", "title": "Build", "details": ["Do work."]}
  assert app.dispatch("POST", "/tasks", body)[0] == HTTPStatus.BAD_REQUEST
  for invalid in (None, 0, 4, 35, "5", True, 3.0):
    assert (
      app.dispatch("POST", "/tasks", {**body, "size": invalid})[0]
      == HTTPStatus.BAD_REQUEST
    )
  assert (
    app.dispatch("POST", "/tasks", {**body, "size": 5, "priority": "P0"})[0]
    == HTTPStatus.BAD_REQUEST
  )
  status, payload = app.dispatch("POST", "/tasks", {**body, "size": 5})
  assert status == HTTPStatus.CREATED
  assert (payload["task"]["priority"], payload["task"]["size"]) == ("P4", 5)
  assert (
    app.dispatch("PATCH", "/tasks/build", {"position": 0})[0] == HTTPStatus.BAD_REQUEST
  )
  assert (
    app.dispatch("PATCH", "/tasks/build", {"insertion_order": 10})[0]
    == HTTPStatus.BAD_REQUEST
  )
  for invalid in (0, 4, True, "3"):
    assert (
      app.dispatch("PATCH", "/tasks/build", {"size": invalid})[0]
      == HTTPStatus.BAD_REQUEST
    )
  status, changed = app.dispatch("PATCH", "/tasks/build", {"priority": "P1", "size": 8})
  assert status == HTTPStatus.OK
  assert changed["task"]["priority"] == "P1" and changed["task"]["size"] == 8
  status, fetched = app.dispatch("GET", "/tasks/build")
  assert status == HTTPStatus.OK and fetched["task"]["size"] == 8
  store.close()


def test_cli_requires_size_and_displays_values_only_in_details(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: tmp_path)

  def run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(args), out=out, err=err)
    return code, out.getvalue(), err.getvalue()

  for options in ((), ("-z", "4"), ("-z", "5", "-p", "P0")):
    with pytest.raises(SystemExit) as exc:
      run("task", "new", "work", "Work", "-d", "Build.", *options)
    assert exc.value.code == 2
  code, created, err = run(
    "task", "new", "work", "Work", "-d", "Build.", "-z", "5", "-p", "P2"
  )
  assert code == 0, err
  assert "Priority: P2" in created and "Size: 5" in created
  assert run("tasks")[1].strip() == "work - Work"
  assert "Priority: P2" not in run("task")[1]
  assert "Priority: P2" in run("task", "-d")[1]
  assert run("task", "mod", "work", "size", "8")[0] == 0
  assert run("task", "mod", "work", "priority", "P1")[0] == 0
  assert "Priority: P1" in run("task", "work")[1]
  assert "Size: 8" in run("task", "work")[1]


def test_acknowledgement_task_creation_requires_a_size(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: tmp_path)
  store = SqliteStore(tmp_path / "state.sqlite3")
  SteeringApp(store).messages.send_message("Create a task", msg_id="ab1200")
  store.close()

  def run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(args), out=out, err=err)
    return code, out.getvalue(), err.getvalue()

  options = (
    "ack",
    "ab1200",
    "Read",
    "-i",
    "new-work",
    "-t",
    "New work",
    "-d",
    "Build.",
  )
  code, _, err = run(*options)
  assert code != 0 and "-z/--size" in err
  store = SqliteStore(tmp_path / "state.sqlite3")
  assert store.get_task("new-work") is None
  assert store.get_message("ab1200").acks == []
  store.close()

  code, _, err = run(*options, "-z", "5", "-p", "P2")
  assert code == 0, err
  store = SqliteStore(tmp_path / "state.sqlite3")
  task = store.get_task("new-work")
  assert task is not None and (task.priority, task.size) == ("P2", 5)
  store.close()


def test_state_import_rejects_missing_estimate_but_preserves_it_on_old_peer_edit() -> (
  None
):
  source = SqliteStore(":memory:")
  TaskService(source, source).create_task(
    "work", "Work", size=8, priority="P2", details=["Build."]
  )
  document = source.export_rows()
  target = SqliteStore(":memory:")
  old_row = dict(document["tasks"][0])
  for field in ("size", "priority", "priority_explicit", "insertion_order"):
    old_row.pop(field)
  with pytest.raises(ValueError, match="size"):
    target.merge_rows({"tasks": [old_row]})
  assert target.get_task("work") is None

  target.merge_rows(document)
  before = target.get_task("work")
  assert before is not None
  old_row["modified_at"] = "2099-01-01T00:00:00Z"
  old_row["title"] = "Older client edited title"
  target.merge_rows({"tasks": [old_row]})
  after = target.get_task("work")
  assert after is not None
  assert (
    after.priority,
    after.priority_explicit,
    after.size,
    after.insertion_order,
  ) == (
    before.priority,
    before.priority_explicit,
    before.size,
    before.insertion_order,
  )
  assert after.title == "Older client edited title"
  target.close()
  source.close()


@pytest.mark.parametrize(
  "field,value",
  [
    ("size", 4),
    ("size", "3"),
    ("size", True),
    ("priority", "P0"),
    ("insertion_order", -1),
  ],
)
def test_state_import_rejects_invalid_rank_fields(field: str, value: object) -> None:
  source = SqliteStore(":memory:")
  TaskService(source, source).create_task("work", "Work", size=3, details=["Build."])
  row = dict(source.export_rows()["tasks"][0])
  row[field] = value
  target = SqliteStore(":memory:")
  with pytest.raises(ValueError, match=f"Task.{field}"):
    target.merge_rows({"tasks": [row]})
  assert target.get_task("work") is None
  target.close()
  source.close()


def test_ui_values_are_escaped_and_inside_details_only() -> None:
  task = Task("task", "Work <now>", size=5, priority="P2", details=["Build."])
  script = """
import assert from 'node:assert/strict';
import { renderTasksView } from './skills/arena-steering/assets/tasks-view.js';
const container = {
  innerHTML: '', scrollTop: 0,
  querySelector() { return null; },
  querySelectorAll() { return []; },
};
renderTasksView(container, { tasks: JSON.parse(process.argv[1]) });
const markup = container.innerHTML;
assert.doesNotMatch(markup.split('<details')[0], /Priority: P2|Size: 5/);
assert.match(markup, /<details[^>]*>[\\s\\S]*Priority: P2[\\s\\S]*Size: 5[\\s\\S]*<\\/details>/);
assert.match(markup, /Work &lt;now&gt;/);
"""
  result = subprocess.run(
    [
      "node",
      "--experimental-default-type=module",
      "--input-type=module",
      "-e",
      script,
      json.dumps([task.to_dict()]),
    ],
    cwd=Path(__file__).resolve().parents[3],
    check=False,
    capture_output=True,
    text=True,
  )
  assert result.returncode == 0, result.stderr
