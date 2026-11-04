"""Local-only dismissal of blocked Bash JSONL entries."""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering import blocked_bash
from arena_steering.blocked_bash import (
  append_blocked_bash,
  dismiss_blocked_bash,
  read_blocked_bash,
)
from arena_steering.server import SteeringApp, make_request_handler
from arena_steering.store import SqliteStore


def test_dismiss_deletes_only_the_selected_raw_line_and_keeps_log_private(
  tmp_path: Path,
) -> None:
  state_dir = tmp_path / "arena-state"
  line = "printf '<script>alert(1)</script>'\nnext line"
  for _ in range(2):
    append_blocked_bash(state_dir, line=line, command="printf", blocked_by="gate")
  append_blocked_bash(state_dir, line="last", command="other", blocked_by="sleep")
  log_path = state_dir / "blocked-bash.jsonl"
  before = log_path.read_bytes().splitlines(keepends=True)
  entries = read_blocked_bash(state_dir)
  assert len(entries) == 3
  assert len({entry["id"] for entry in entries}) == 3
  assert all(len(entry["id"]) == 64 for entry in entries)
  assert [entry["line"] for entry in entries] == [line, line, "last"]

  dismiss_blocked_bash(state_dir, entries[1]["id"])
  assert log_path.read_bytes() == before[0] + before[2]
  assert [entry["line"] for entry in read_blocked_bash(state_dir)] == [line, "last"]
  assert log_path.stat().st_mode & 0o777 == 0o600
  with pytest.raises(KeyError, match="no longer present"):
    dismiss_blocked_bash(state_dir, entries[1]["id"])
  with pytest.raises(ValueError, match="entry ID"):
    dismiss_blocked_bash(state_dir, "../outside")
  assert list(state_dir.glob(".blocked-bash-*")) == []


def test_dismiss_and_append_are_locked_across_threads(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  append_blocked_bash(tmp_path, line="target", command="target", blocked_by="gate")
  target_id = read_blocked_bash(tmp_path)[0]["id"]
  started, attempting, resume = threading.Event(), threading.Event(), threading.Event()
  original_replace = os.replace
  original_flock = blocked_bash.fcntl.flock

  def pause_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
    started.set()
    assert resume.wait(3), "replacement never resumed"
    original_replace(src, dst)

  def observe_lock(fd: int, operation: int) -> None:
    if started.is_set():
      attempting.set()
    original_flock(fd, operation)

  monkeypatch.setattr(blocked_bash.os, "replace", pause_replace)
  monkeypatch.setattr(blocked_bash.fcntl, "flock", observe_lock)
  with ThreadPoolExecutor(max_workers=2) as pool:
    deleting = pool.submit(dismiss_blocked_bash, tmp_path, target_id)
    assert started.wait(3)
    adding = pool.submit(
      append_blocked_bash,
      tmp_path,
      line="new",
      command="new",
      blocked_by="gate",
    )
    assert attempting.wait(3)
    resume.set()
    deleting.result(timeout=3)
    adding.result(timeout=3)
  assert [entry["line"] for entry in read_blocked_bash(tmp_path)] == ["new"]


def test_delete_endpoint_is_local_only_and_never_exposes_log_in_state(
  tmp_path: Path,
) -> None:
  state_dir = tmp_path / "arena-state"
  store = SqliteStore(state_dir / "state.sqlite3")
  app = SteeringApp(store)
  line = "private shell line with <unsafe> text"
  append_blocked_bash(state_dir, line=line, command="private", blocked_by="gate")
  status, payload = app.dispatch("GET", "/blocked-bash")
  assert status == HTTPStatus.OK and payload["entries"][0]["line"] == line
  entry_id = payload["entries"][0]["id"]
  assert app.dispatch("DELETE", "/blocked-bash/invalid")[0] == HTTPStatus.BAD_REQUEST
  status, _ = app.dispatch("DELETE", f"/blocked-bash/{entry_id}")
  assert status == HTTPStatus.OK
  assert app.dispatch("GET", "/blocked-bash") == (HTTPStatus.OK, {"entries": []})
  assert app.dispatch("DELETE", f"/blocked-bash/{entry_id}")[0] == HTTPStatus.NOT_FOUND
  status, snapshot = app.dispatch("GET", "/state/snapshot")
  assert status == HTTPStatus.OK and line not in json.dumps(snapshot)

  handler = object.__new__(make_request_handler(app))
  replies: list[dict[str, object]] = []
  handler.ws_send = lambda _opcode, data: replies.append(json.loads(data))
  for method, path in (
    ("GET", "/blocked-bash"),
    ("DELETE", f"/blocked-bash/{entry_id}"),
  ):
    handler.ws_dispatch({"id": method, "method": method, "path": path, "body": ""})
  assert all(reply["status"] == HTTPStatus.FORBIDDEN for reply in replies)
  assert line not in json.dumps(replies)
  store.close()


def test_dismiss_fails_closed_on_symlink_and_replacement_error(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  state_dir = tmp_path / "state"
  append_blocked_bash(state_dir, line="first", command="cmd", blocked_by="gate")
  log_path = state_dir / "blocked-bash.jsonl"
  entry_id = read_blocked_bash(state_dir)[0]["id"]
  original = log_path.read_bytes()
  outside = tmp_path / "outside.jsonl"
  outside.write_bytes(b"outside must survive")
  log_path.unlink()
  log_path.symlink_to(outside)
  with pytest.raises(RuntimeError, match="unavailable"):
    dismiss_blocked_bash(state_dir, entry_id)
  assert outside.read_bytes() == b"outside must survive"

  log_path.unlink()
  log_path.write_bytes(original)

  def fail_replace(_src: str | os.PathLike[str], _dst: str | os.PathLike[str]) -> None:
    raise OSError("simulated write failure")

  monkeypatch.setattr(blocked_bash.os, "replace", fail_replace)
  with pytest.raises(RuntimeError, match="unavailable"):
    dismiss_blocked_bash(state_dir, entry_id)
  assert log_path.read_bytes() == original
  assert list(state_dir.glob(".blocked-bash-*")) == []

  invalid = original + b"not JSON\n"
  log_path.write_bytes(invalid)
  with pytest.raises(RuntimeError, match="line 2"):
    dismiss_blocked_bash(state_dir, entry_id)
  assert log_path.read_bytes() == invalid

  lock_path = state_dir / ".blocked-bash.lock"
  lock_path.unlink()
  lock_path.symlink_to(outside)
  with pytest.raises(RuntimeError, match="unavailable"):
    append_blocked_bash(
      state_dir, line="must not append", command="x", blocked_by="gate"
    )
  assert outside.read_bytes() == b"outside must survive"
