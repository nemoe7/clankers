"""Tests for the pre-command pipeline in `arena_steering/pre.py`."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from arena_steering import cli, pre
from arena_steering.cli import main as cli_main
from arena_steering.server import scripts_signature


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
  state_dir = tmp_path / "arena-state"
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: state_dir)
  return state_dir


def _run(*args: str) -> tuple[int, str]:
  out = io.StringIO()
  code = cli_main(list(args), out=out, err=io.StringIO())
  return code, out.getvalue()


def _seed(state_dir: Path, body: str, *, acked: bool = False) -> None:
  state_dir.mkdir(parents=True, exist_ok=True)
  store, messages, _tasks, _reports = cli.open_services(state_dir)
  messages.send_message(body)
  if acked:
    for pending_id in messages.pending_ids():
      messages.ack(pending_id, "Done.")
  store.close()


def _count(state_dir: Path) -> str | None:
  store, _messages, _tasks, _reports = cli.open_services(state_dir)
  value = store.get_meta(pre.CALL_COUNT_META)
  store.close()
  return value


def _verdict(ctx: pre.PreContext) -> int:
  return pre.run_pipeline(ctx).verdict


def test_a_push_blocks_the_moment_a_note_waits() -> None:
  ctx = pre.PreContext(
    line="git push origin main",
    command="git push origin main",
    shell="bash",
    pending_ids=["abc123"],
  )
  result = pre.run_pipeline(ctx)
  assert result.verdict == pre.BLOCK
  assert "PUSH BLOCKED" in result.messages[0]
  assert "abc123" in " ".join(result.messages)


def test_the_gate_counts_calls_before_it_blocks() -> None:
  base = pre.PreContext(line="ls", command="ls", shell="bash", pending_ids=["abc123"])
  early = pre.run_pipeline(pre.PreContext(**{**base.__dict__, "call_count": 2}))
  assert early.verdict == pre.CONTINUE

  late = pre.run_pipeline(
    pre.PreContext(**{**base.__dict__, "call_count": pre.GATE_THRESHOLD})
  )
  assert late.verdict == pre.BLOCK
  assert str(pre.GATE_THRESHOLD) in " ".join(late.messages)


def test_each_guard_holds_its_own_rule() -> None:
  clear = pre.PreContext(shell="bash")
  assert _verdict(pre.PreContext(**{**clear.__dict__, "line": "sleep 5 && x"})) == 0
  assert (
    _verdict(
      pre.PreContext(**{**clear.__dict__, "line": "sleep 5 && steer read", "shell": ""})
    )
    == pre.BLOCK
  )
  assert (
    _verdict(pre.PreContext(**{**clear.__dict__, "line": "git add shot-wireframe.png"}))
    == pre.BLOCK
  )
  assert (
    _verdict(pre.PreContext(**{**clear.__dict__, "line": "rg -n gate AGENTS.md"}))
    == pre.BLOCK
  )
  assert (
    _verdict(pre.PreContext(**{**clear.__dict__, "line": "head -20 skills/x/app.js"}))
    == 0
  )


def test_a_partial_read_of_the_bible_blocks_every_verb() -> None:
  guard = pre.BibleReadGuard()
  for line in (
    "rg -n 'gate' AGENTS.md",
    "grep -n gate ARENA.md",
    "head -20 ARENA.md",
    "tail -n 5 skills/arena-skill/SKILL.md",
    "cat skills/arena-steering/SKILL.md",
  ):
    ctx = pre.PreContext(line=line, shell="bash")
    assert guard.applies(ctx), line
    assert guard.run(ctx).verdict == pre.BLOCK, line

  for line in ("rg -n gate skills/arena-steering", "head -20 assets/app.js"):
    assert not guard.applies(pre.PreContext(line=line, shell="bash")), line


def test_the_gate_reads_the_stored_count_and_the_done_list_skips_steps(
  _isolate_state: Path,
) -> None:
  _seed(_isolate_state, "Work through this note.")
  code, first = _run("pre", "-c", "ls", "-s", "bash", "-l", "ls")
  assert code == pre.CONTINUE
  assert _count(_isolate_state) == "1"

  code, second = _run("pre", "-c", "ls", "-s", "bash", "-l", "ls", "-d", "gate")
  assert code == pre.CONTINUE
  assert second == ""
  assert _count(_isolate_state) == "1"
  assert "bash blocked in" in first


def test_a_pass_through_reports_the_finished_steps(_isolate_state: Path) -> None:
  _seed(_isolate_state, "Acked already.", acked=True)
  code, out = _run("pre", "-l", "curl https://example.test", "-s", "bash")
  assert code == pre.CONTINUE
  assert '_arena_preview_done="egress"' in out

  code, out = _run(
    "pre", "-l", "curl https://example.test", "-s", "bash", "-d", "egress"
  )
  assert code == pre.CONTINUE
  assert out == ""


def test_reading_the_inbox_preserves_the_count_while_work_remains(
  _isolate_state: Path,
) -> None:
  _seed(_isolate_state, "Note for the countdown.")
  for _ in range(3):
    _run("pre", "-c", "ls", "-s", "bash", "-l", "ls")
  assert _count(_isolate_state) == "3"

  _run("read")
  _run("pre", "-c", "ls", "-s", "bash", "-l", "ls")
  assert _count(_isolate_state) == "4"


def test_a_quiet_note_does_not_gate(_isolate_state: Path) -> None:
  _isolate_state.mkdir(parents=True, exist_ok=True)
  store, messages, _tasks, _reports = cli.open_services(_isolate_state)
  messages.send_message("Quiet note.", hidden=True, blocking=False)
  assert messages.pending_ids() == []
  store.close()

  code, out = _run("pre", "-c", "git push", "-s", "bash")
  assert code == pre.CONTINUE
  assert out == ""


def test_a_clear_inbox_passes_the_gate(_isolate_state: Path) -> None:
  _seed(_isolate_state, "Acked already.", acked=True)
  code, out = _run("pre", "-c", "git push", "-s", "bash")
  assert code == pre.CONTINUE
  assert out == ""


def test_pipeline_order_is_the_registry_order() -> None:
  names = [step.name for step in pre.PIPELINE]
  assert names.index("sleep") < names.index("gate")
  assert names.index("bible") > names.index("gate")
  assert names.index("bare") > names.index("gate")


def test_installer_places_steer_on_path_idempotently(tmp_path: Path) -> None:
  root = Path(__file__).resolve().parents[3]
  project = tmp_path / "project with spaces"
  scripts = project / ".agents" / "skills" / "arena-steering" / "scripts"
  shutil.copytree(root / "skills" / "arena-steering" / "scripts", scripts)
  shutil.copytree(
    root / "skills" / "arena-steering" / "references", scripts.parent / "references"
  )
  home = tmp_path / "home with spaces"
  python = home / ".agents" / ".steer-venv" / "bin" / "python"
  python.parent.mkdir(parents=True)
  python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
  python.chmod(0o755)
  profile = home / ".bash_profile"
  profile.write_text("# Existing profile content\n", encoding="utf-8")
  env = {**os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin"}
  install = scripts / "install.sh"
  for _ in range(2):
    result = subprocess.run(
      ["bash", str(install)],
      check=False,
      cwd=project,
      env=env,
      capture_output=True,
      text=True,
    )
    assert result.returncode == 0, result.stderr
  profile_text = profile.read_text(encoding="utf-8")
  assert profile_text.count("# Existing profile content") == 1
  result = subprocess.run(
    ["bash", "-c", 'source "$HOME/.bash_profile"; command -v steer; steer --version'],
    check=False,
    cwd=project,
    env=env,
    capture_output=True,
    text=True,
  )
  assert result.returncode == 0, result.stderr
  assert str(home / ".local" / "bin" / "steer") in result.stdout
  assert "steer 2.1.0" in result.stdout


def test_installer_does_not_overwrite_an_unrelated_steer(tmp_path: Path) -> None:
  root = Path(__file__).resolve().parents[3]
  home = tmp_path / "home"
  command = home / ".local" / "bin" / "steer"
  command.parent.mkdir(parents=True)
  command.write_text("unrelated command\n", encoding="utf-8")
  env = {**os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin"}
  result = subprocess.run(
    ["bash", str(root / "skills" / "arena-steering" / "scripts" / "install.sh")],
    check=False,
    cwd=root,
    env=env,
    capture_output=True,
    text=True,
  )
  assert result.returncode != 0
  assert "already exists" in result.stderr
  assert command.read_text(encoding="utf-8") == "unrelated command\n"
  target = home / "existing"
  target.write_text("# arena-steering-installed\nother content\n", encoding="utf-8")
  command.unlink()
  command.symlink_to(target)
  result = subprocess.run(
    ["bash", str(root / "skills" / "arena-steering" / "scripts" / "install.sh")],
    check=False,
    cwd=root,
    env=env,
    capture_output=True,
    text=True,
  )
  assert result.returncode != 0 and "already exists" in result.stderr
  assert (
    target.read_text(encoding="utf-8") == "# arena-steering-installed\nother content\n"
  )


def test_serve_uses_fixed_port_and_rejects_overrides(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  seen: list[tuple[str, int]] = []

  class FakeServer:
    server_address = ("0.0.0.0", 8000)

    def serve_forever(self) -> None:
      assert (_isolate_state / "server.json").is_file()

    def server_close(self) -> None:
      pass

  def create(_app, *, host: str, port: int):
    seen.append((host, port))
    return FakeServer()

  monkeypatch.setattr(cli, "create_http_server", create)
  code, _ = _run("serve")
  assert code == 0 and seen == [("0.0.0.0", 8000)]
  assert not (_isolate_state / "server.json").exists()
  with pytest.raises(SystemExit) as error:
    _run("serve", "--port", "8101")
  assert error.value.code == 2
  assert seen == [("0.0.0.0", 8000)]


def test_demo_lives_in_maintenance_and_retains_port_option(tmp_path: Path) -> None:
  root = Path(__file__).resolve().parents[3]
  demo = root / "maintenance" / "demo-arena-steer.py"
  assert demo.is_file()
  assert not (root / "skills" / "arena-steering" / "scripts" / "demo.py").exists()
  assert str(demo) in {item[0] for item in scripts_signature()}
  help_result = subprocess.run(
    [sys.executable, str(demo), "--help"],
    check=False,
    cwd=tmp_path,
    capture_output=True,
    text=True,
  )
  assert help_result.returncode == 0, help_result.stderr
  assert "--port" in help_result.stdout
  live_state = tmp_path / "arena-state" / "state.sqlite3"
  live_state.parent.mkdir(parents=True)
  live_state.write_bytes(b"live state is not demo data")
  seed_result = subprocess.run(
    [sys.executable, str(demo), "--seed-only", "--port", "8135"],
    check=False,
    cwd=tmp_path,
    capture_output=True,
    text=True,
  )
  assert seed_result.returncode == 0, seed_result.stderr
  assert (tmp_path / "arena-state" / "demo" / "state.sqlite3").is_file()
  assert live_state.read_bytes() == b"live state is not demo data"


def test_moved_demo_reseeds_a_demo_store_on_reload(tmp_path: Path) -> None:
  store = cli.SqliteStore(tmp_path / "arena-steering-demo-fixture" / "state.sqlite3")
  app = cli.SteeringApp(store)
  assert len(app.messages.list_messages(unread_only=False, include_hidden=True)) >= 35
  assert len(app.tasks.list_tasks(include_finished=True)) >= 40
  store.close()


def test_gate_counts_blocking_not_visibility(_isolate_state: Path) -> None:
  store, messages, _, _ = cli.open_services(_isolate_state)
  messages.send_message("Hidden blocker", msg_id="ab0001", hidden=True, blocking=True)
  messages.send_message("Visible blocker", msg_id="ab0002", blocking=True)
  messages.send_message("Visible nonblocker", msg_id="ab0003", blocking=False)
  messages.send_message(
    "Hidden nonblocker", msg_id="ab0004", hidden=True, blocking=False
  )
  assert messages.pending_ids() == ["ab0001", "ab0002"]
  store.close()
  code, out = _run("pre", "-c", "git push", "-s", "bash", "-l", "git push")
  assert code == pre.BLOCK
  assert "ab0001" in out and "ab0002" in out
  assert "ab0003" not in out and "ab0004" not in out


def test_poll_and_partial_ack_keep_count_until_last_blocker(
  _isolate_state: Path,
) -> None:
  store, messages, _, _ = cli.open_services(_isolate_state)
  messages.send_message("One", msg_id="ab0011", blocking=True)
  messages.send_message("Two", msg_id="ab0012", hidden=True, blocking=True)
  store.close()
  for _ in range(3):
    _run("pre", "-c", "ls", "-s", "bash", "-l", "ls")
  assert _count(_isolate_state) == "3"
  assert _run("poll")[0] == 0
  assert _count(_isolate_state) == "3"
  assert _run("ack", "ab0011", "Done")[0] == 0
  assert _count(_isolate_state) == "3"
  assert _run("ack", "ab0012", "Done")[0] == 0
  assert _count(_isolate_state) == "0"
  _seed(_isolate_state, "New work")
  assert _run("pre", "-c", "ls", "-s", "bash", "-l", "ls")[0] == 0
  assert _count(_isolate_state) == "1"


def test_http_answer_ack_resets_count_only_after_last_blocker(
  _isolate_state: Path,
) -> None:
  store = cli.open_services(_isolate_state)[0]
  app = cli.SteeringApp(store)
  app.reports.publish_report(
    "choice",
    "Choice",
    '<!-- question {"id":"pick","label":"Pick"} -->\n'
    'Pick\n- ( ) Yes <!-- option {"label":"Yes"} -->\n',
  )
  app.reports.submit_answer("choice", {"pick": "Yes"}, answer_id="ab0021")
  app.messages.send_message("Other blocker", msg_id="ab0022", hidden=True)
  store.set_meta(pre.CALL_COUNT_META, "5")
  status, _ = app.dispatch(
    "POST", "/reports/choice/answers/ab0021/ack", {"markdown": "Read"}
  )
  assert status == 200
  assert store.get_meta(pre.CALL_COUNT_META) == "5"
  status, _ = app.dispatch("POST", "/messages/ab0022/ack", {"markdown": "Read"})
  assert status == 200
  assert store.get_meta(pre.CALL_COUNT_META) == "0"
  store.close()


def test_gate_allows_inbox_recovery_but_not_mixed_work() -> None:
  for line in (
    "steer read",
    "steer poll",
    "steer ack ab1234 Done",
    "steer ack ab1234 Done | tee log",
  ):
    ctx = pre.PreContext(
      line=line,
      command=line,
      shell="bash",
      pending_ids=["ab1234"],
      call_count=pre.GATE_THRESHOLD,
    )
    assert _verdict(ctx) == pre.CONTINUE, line
  for line in (
    "steer read && git status",
    "steer ack ab1234 Done; git push",
    "steer ack ab1234 Done | git push",
  ):
    ctx = pre.PreContext(
      line=line,
      command=line,
      shell="bash",
      pending_ids=["ab1234"],
      call_count=pre.GATE_THRESHOLD,
    )
    assert _verdict(ctx) == pre.BLOCK, line


def test_new_blocker_still_blocks_push_after_gate_step_done() -> None:
  ctx = pre.PreContext(
    line="git push",
    command="git push",
    shell="bash",
    done=("gate",),
    pending_ids=["ab1234"],
  )
  assert _verdict(ctx) == pre.BLOCK
