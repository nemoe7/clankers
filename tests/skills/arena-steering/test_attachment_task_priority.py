"""Attachment-linked task priority, details, and explicit override integration."""

import io
import sqlite3
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering import cli
from arena_steering.models import Attachment, Task
from arena_steering.server import SteeringApp
from arena_steering.services import TaskService
from arena_steering.store import SqliteStore


def _attachments() -> list[Attachment]:
  home = Path.home() / "steer-fixture"
  return [
    Attachment("first.txt", str(home / "first.txt"), 4),
    Attachment("missing.png", str(home / "missing.png"), 0, present=False),
  ]


def test_task_defaults_and_linked_messages_preserve_explicit_priority(
  tmp_path: Path,
) -> None:
  db = tmp_path / "state.sqlite3"
  store = SqliteStore(db)
  app = SteeringApp(store)
  app.messages.send_message(
    "Inspect files", attachments=_attachments(), msg_id="ab1020"
  )
  tasks = app.tasks
  assert Task("default", "Default", size=2).priority == "P4"
  plain = tasks.create_task("plain", "Plain", size=2, details=["Inspect."])
  assert (plain.priority, plain.priority_explicit) == ("P4", False)

  paths = ["~/steer-fixture/first.txt", "~/steer-fixture/missing.png"]
  created = tasks.create_task(
    "linked", "Linked", size=2, details=["Inspect."], msg_ids=["ab1020"]
  )
  assert (created.priority, created.priority_explicit) == ("P3", False)
  assert created.details == ["Inspect.", *paths]

  tasks.create_task("explicit", "Explicit", size=2, priority="P4", details=["Inspect."])
  tasks.mod_links_add("explicit", "ab1020", link_type="msg")
  assert (
    tasks.get_task("explicit")[0].priority,
    tasks.get_task("explicit")[0].details,
  ) == ("P4", ["Inspect.", *paths])
  tasks.mod_links_add("plain", "ab1020", link_type="msg")
  tasks.mod_links_add("plain", "ab1020", link_type="msg")
  assert (tasks.get_task("plain")[0].priority, tasks.get_task("plain")[0].details) == (
    "P3",
    ["Inspect.", *paths],
  )

  patched = tasks.create_task("patched", "Patched", size=2, details=["Inspect."])
  tasks.patch_task(patched.id, {"msg_ids": ["ab1020"]})
  assert (
    tasks.get_task("patched")[0].priority,
    tasks.get_task("patched")[0].details,
  ) == ("P3", ["Inspect.", *paths])
  tasks.patch_task("plain", {"priority": "P5"})
  assert tasks.get_task("plain")[0].priority_explicit
  store.close()

  reopened = SqliteStore(db)
  tasks = TaskService(reopened, reopened, messages=reopened)
  assert (
    tasks.get_task("explicit")[0].priority_explicit,
    tasks.get_task("plain")[0].priority,
  ) == (True, "P5")
  tasks.mod_links_rm("plain", "msg", "ab1020")
  tasks.mod_links_add("plain", "ab1020", link_type="msg")
  assert (tasks.get_task("plain")[0].priority, tasks.get_task("plain")[0].details) == (
    "P5",
    ["Inspect.", *paths],
  )
  reopened.close()


def test_ack_and_api_add_multiple_attachment_paths_without_opt_in(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: tmp_path)
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  for message_id in ("ab1021", "ab1022", "ab1023"):
    app.messages.send_message(
      "Inspect files", attachments=_attachments(), msg_id=message_id
    )
  store.close()

  def run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(args), out=out, err=err)
    return code, out.getvalue(), err.getvalue()

  args = ("-t", "New work", "-z", "2", "-d", "Inspect.")
  code, output, error = run("ack", "ab1021", "Read", "-i", "via-ack", *args)
  assert code == 0, error
  assert "Priority: P3" in output

  code, _, error = run("ack", "ab1022", "Read", "-i", "explicit-ack", *args, "-p", "P5")
  assert code == 0, error
  code, _, error = run("task", "new", "-z", "2", "plain", "Plain", "-d", "Inspect.")
  assert code == 0, error

  store = SqliteStore(tmp_path / "state.sqlite3")
  assert store.get_message("ab1021").acks == ["Read"]
  assert store.get_task("via-ack").details == [
    "Inspect.",
    "~/steer-fixture/first.txt",
    "~/steer-fixture/missing.png",
  ]
  assert (
    store.get_task("via-ack").priority,
    store.get_task("explicit-ack").priority,
  ) == ("P3", "P5")
  assert store.get_task("plain").priority == "P4"

  app = SteeringApp(store)
  status, payload = app.dispatch(
    "POST",
    "/tasks",
    {"id": "via-api", "title": "Via API", "size": 2, "msg_ids": ["ab1023"]},
  )
  assert status == HTTPStatus.CREATED
  assert payload["task"]["priority"] == "P3"
  assert payload["task"]["details"] == [
    "~/steer-fixture/first.txt",
    "~/steer-fixture/missing.png",
  ]
  status, payload = app.dispatch(
    "POST",
    "/tasks",
    {"id": "api-plain", "title": "Plain API", "size": 2, "details": ["Inspect."]},
  )
  assert status == HTTPStatus.CREATED
  assert payload["task"]["priority"] == "P4"
  store.close()


def test_old_priority_override_survives_migration_and_later_links(
  tmp_path: Path,
) -> None:
  db = tmp_path / "legacy.sqlite3"
  store = SqliteStore(db)
  tasks = TaskService(store, store)
  tasks.create_task(
    "old-override", "Old override", size=2, priority="P4", details=["Inspect."]
  )
  tasks.create_task(
    "old-default", "Old default", size=2, priority="P3", details=["Inspect."]
  )
  store.close()

  with sqlite3.connect(db) as conn:
    conn.execute("ALTER TABLE tasks DROP COLUMN priority_explicit")

  reopened = SqliteStore(db)
  tasks = TaskService(reopened, reopened, messages=reopened)
  assert tasks.get_task("old-override")[0].priority_explicit
  assert not tasks.get_task("old-default")[0].priority_explicit
  SteeringApp(reopened).messages.send_message(
    "See attached file", attachments=_attachments(), msg_id="ab1024"
  )
  tasks.mod_links_add("old-override", "ab1024", link_type="msg")
  assert tasks.get_task("old-override")[0].priority == "P4"
  reopened.close()


def test_long_missing_attachment_path_is_kept_without_truncation() -> None:
  store = SqliteStore(":memory:")
  app = SteeringApp(store)
  long_path = Path.home() / "steer-fixture" / ("x" * 125 + ".txt")
  app.messages.send_message(
    "See attachment",
    attachments=[Attachment("long.txt", str(long_path), present=False)],
    msg_id="ab1025",
  )
  task = app.tasks.create_task("long-path", "Long path", size=2, msg_ids=["ab1025"])
  assert (task.priority, task.details) == ("P3", [f"~/steer-fixture/{long_path.name}"])
  app.tasks.patch_task("long-path", {"title": "Long path retained"})
  assert app.tasks.get_task("long-path")[0].details == task.details
  store.close()
