"""Tests for the approved grouped CLI interface."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from arena_steering import cli
from arena_steering.server import SteeringApp
from arena_steering.store import SqliteStore


@pytest.fixture
def cli_state(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Path, SteeringApp]]:
  state_dir = tmp_path / "arena-state"
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: state_dir)
  monkeypatch.setattr(
    cli, "_healthy_server_url", lambda _state_dir: "http://127.0.0.1:8000"
  )
  store = SqliteStore(state_dir / "state.sqlite3")
  try:
    yield state_dir, SteeringApp(store)
  finally:
    store.close()


def invoke(*args: str) -> tuple[int, str, str]:
  out = io.StringIO()
  err = io.StringIO()
  status = cli.main(list(args), out=out, err=err)
  return status, out.getvalue(), err.getvalue()


def test_help_shows_grouped_commands_and_legacy_top_level_forms_are_rejected() -> None:
  status, help_text, error = invoke("--help")
  assert (status, error) == (0, "")
  for command in (
    "inbox",
    "task",
    "report",
    "run",
    "ren",
    "poll",
    "job-log",
    "pr-update",
  ):
    assert command in help_text
  usage = help_text.split("\n\n", 1)[0]
  commands = usage.split("{", 1)[1].split("}", 1)[0].split(",")
  for removed in ("read", "ack", "msg", "tasks", "reports"):
    assert removed not in commands
    status, _output, error = invoke(removed)
    assert status == 2
    assert f"top-level `{removed}` was removed" in error


@pytest.mark.parametrize(
  ("args", "removed_form"),
  (
    (("task", "mod", "task-id", "title", "Old"), "task `mod` was removed"),
    (("task", "rm", "task-id"), "task `rm` was removed"),
    (("report", "pub"), "report `pub` was removed"),
    (("report", "rm", "report-id"), "report `rm` was removed"),
    (("run", "pr-checks"), "`pr-checks` was removed"),
  ),
)
def test_removed_grouped_aliases_are_rejected(
  args: tuple[str, ...], removed_form: str
) -> None:
  status, _output, error = invoke(*args)
  assert status == 2
  assert removed_form in error


def test_task_creation_accepts_repeated_multivalue_flags_and_renders_fields(
  cli_state: tuple[Path, SteeringApp],
) -> None:
  _state_dir, app = cli_state
  app.tasks.create_task(
    "base-task",
    "Base",
    size=1,
    priority="P2",
    scope="base",
    details=["Base task detail"],
  )
  app.messages.send_message("First link", msg_id="a0b1c1")
  app.messages.send_message("Second link", msg_id="a0b1c2")
  app.reports.publish_report("spec", "Spec", "Report body")

  status, output, error = invoke(
    "task",
    "new",
    "cli-task",
    "-t",
    "Grouped CLI",
    "-p",
    "2",
    "-z",
    "3",
    "-T",
    "report",
    "code",
    "docs",
    "-T",
    "ops",
    "-S",
    "frontend",
    "-d",
    "Draft the report",
    "Document the command",
    "-d",
    "Add focused tests",
    "-m",
    "a0b1c1",
    "a0b1c2",
    "-r",
    "spec",
    "-k",
    "base-task",
    "-R",
    "validation",
  )
  assert (status, error) == (0, "")
  assert "cli-task" in output
  assert "- Scope: frontend" in output
  assert "- Priority: P2" in output
  assert "- Size: 3" in output
  assert "- Messages: a0b1c1, a0b1c2" in output
  assert "- Reports: spec" in output
  assert "- Deps: base-task" in output
  assert "- Gates: validation" in output
  assert "Draft the report" in output
  assert "Document the command" in output
  assert "Add focused tests" in output

  status, output, error = invoke("task", "show", "cli-task")
  assert (status, error) == (0, "")
  assert "type report; report (current) → code → docs → ops" in output


def test_message_and_task_search_are_case_insensitive_literal_and_paginated(
  cli_state: tuple[Path, SteeringApp],
) -> None:
  _state_dir, app = cli_state
  for index in range(12):
    msg_id = f"{index + 1:06x}"
    app.messages.send_message(f"Alpha.Case match {index}", msg_id=msg_id)
  app.messages.send_message("AlphaXCase should not match", msg_id="fffffe")

  status, first_messages, error = invoke("inbox", "search", "ALPHA.CASE", "-p", "1")
  assert (status, error) == (0, "")
  assert "fffffe" not in first_messages
  assert first_messages.index("00000c") < first_messages.index("00000b")
  assert "000003" in first_messages
  assert "000002" not in first_messages

  status, second_messages, error = invoke("inbox", "search", "alpha.case", "-p", "2")
  assert (status, error) == (0, "")
  assert "000001" in second_messages
  assert "000002" in second_messages

  for index in range(12):
    task_id = f"match-task-{index:02d}"
    app.tasks.create_task(
      task_id,
      f"Task {index:02d}",
      size=1,
      scope="Needle scope" if index % 2 == 0 else "other",
      details=["supporting detail"] if index % 2 == 0 else ["needle detail"],
    )

  status, first_tasks, error = invoke("task", "search", "NEEDLE", "-p", "1")
  assert (status, error) == (0, "")
  assert "match-task-00" in first_tasks
  assert first_tasks.index("match-task-00") < first_tasks.index("match-task-01")
  assert "match-task-09" in first_tasks
  assert "match-task-10" not in first_tasks
  assert "match-task-01" in first_tasks

  status, second_tasks, error = invoke("task", "search", "needle", "-p", "2")
  assert (status, error) == (0, "")
  assert "match-task-10" in second_tasks
  assert "match-task-11" in second_tasks
  assert "match-task-09" not in second_tasks
