"""Tests for the pre-command pipeline in `arena_steering/pre.py`."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from arena_steering import cli, pre
from arena_steering.cli import main as cli_main
from arena_steering.server import scripts_signature

PENDING_ACK_PUSH_REASON = "a note or answer awaits an ack"


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
  state_dir = tmp_path / "arena-state"
  monkeypatch.delenv("ARENA_STEER_ROUTE", raising=False)
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


@pytest.mark.parametrize("failure_point", ("resolve", "open", "query"))
def test_pre_allows_work_but_blocks_pushes_when_state_is_unreadable(
  failure_point: str, _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  _seed(_isolate_state, "Acknowledged note.", acked=True)

  def unavailable(*_args: object, **_kwargs: object) -> None:
    raise sqlite3.OperationalError("state unreadable")

  if failure_point == "resolve":
    monkeypatch.setattr(cli, "resolve_state_dir", unavailable)
  elif failure_point == "open":
    monkeypatch.setattr(cli, "open_services", unavailable)
  else:
    monkeypatch.setattr(cli.MessageService, "pending_ids", unavailable)

  code, out = _run("pre", "-c", "printf ok", "-l", "printf ok", "-s", "bash")
  assert code == pre.CONTINUE
  assert "STATE UNAVAILABLE" in out

  code, out = _run(
    "pre", "-c", "git push origin branch", "-l", "git push origin branch", "-s", "bash"
  )
  assert code == pre.BLOCK
  assert "PUSH BLOCKED" in out


def test_bash_command_policy_keeps_counting_and_threshold_separate() -> None:
  base = {"shell": "bash", "pending_ids": ["abc123"], "call_count": pre.GATE_THRESHOLD}
  python = pre.PreContext(
    line="python3 -c 'print(1)'", command="python3 -c 'print(1)'", **base
  )
  assert pre.bash_command_policy(python) == (True, True)
  assert _verdict(python) == pre.BLOCK

  for line, counted in (
    ("steer read", False),
    ("mkdir -p data", True),
    ("ss -ltnp", False),
  ):
    ctx = pre.PreContext(line=line, command=line, **base)
    assert pre.bash_command_policy(ctx) == (counted, False)
    assert _verdict(ctx) == pre.CONTINUE

  mixed = pre.PreContext(line="ss -ltnp; printf after", command="ss -ltnp", **base)
  assert pre.bash_command_policy(mixed) == (True, True)
  assert _verdict(mixed) == pre.BLOCK


def test_bash_policy_can_block_without_spending_the_pending_budget(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  _seed(_isolate_state, "Pending work")
  monkeypatch.setitem(pre.BASH_COMMAND_POLICY, "python3", (False, True))
  line = "python3 --version"
  args = ("pre", "-l", line, "-c", line, "-s", "bash")
  assert _run(*args)[0] == pre.CONTINUE
  store, _messages, _tasks, _reports = cli.open_services(_isolate_state)
  assert store.get_meta(pre.CALL_COUNT_META) in (None, "0")
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD))
  store.close()
  assert _run(*args)[0] == pre.BLOCK


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


@pytest.mark.parametrize(
  "line",
  (
    "git stash push",
    "git stash push --all",
    "git stash push -m 'do not git push'",
    "git -C push stash push",
  ),
)
def test_local_stash_push_does_not_trigger_remote_push_guards(
  _isolate_state: Path, line: str
) -> None:
  _seed(_isolate_state, "Pending work")
  code, output = _run("pre", "-l", line, "-c", line, "-s", "bash")
  assert code == pre.CONTINUE, output
  assert _count(_isolate_state) == "1"
  assert (
    pre.run_pipeline(pre.PreContext(line=line, command=line)).verdict == pre.CONTINUE
  )
  assert not pre.post_push_watch(line)


@pytest.mark.parametrize(
  "line",
  (
    "git -C /workspace push origin topic",
    "git --no-pager push origin topic",
    "git --git-dir=repo.git push origin topic",
  ),
)
def test_git_global_options_keep_remote_push_guarded(line: str) -> None:
  result = pre.run_pipeline(
    pre.PreContext(line=line, command=line, shell="bash", pending_ids=["ab1234"])
  )
  assert result.verdict == pre.BLOCK
  assert result.blocked_by == "gate"
  assert "PUSH BLOCKED" in " ".join(result.messages)
  assert pre.post_push_watch(line)


def test_the_gate_counts_calls_before_it_blocks() -> None:
  base = pre.PreContext(line="ls", command="ls", shell="bash", pending_ids=["abc123"])
  early = pre.run_pipeline(pre.PreContext(**{**base.__dict__, "call_count": 2}))
  assert early.verdict == pre.CONTINUE

  late = pre.run_pipeline(
    pre.PreContext(**{**base.__dict__, "call_count": pre.GATE_THRESHOLD})
  )
  assert late.verdict == pre.BLOCK
  assert str(pre.GATE_THRESHOLD) in " ".join(late.messages)


def test_six_call_block_hides_pending_ids_but_keeps_recovery_steps() -> None:
  pending_ids = ["ab1234", "cd5678"]
  result = pre.run_pipeline(
    pre.PreContext(
      line="git status",
      command="git status",
      shell="bash",
      pending_ids=pending_ids,
      call_count=pre.GATE_THRESHOLD,
    )
  )
  output = "\n".join(result.messages)
  assert result.verdict == pre.BLOCK
  assert f"BASH BLOCKED AFTER {pre.GATE_THRESHOLD} CALLS." in output
  assert "steer read" in output and "steer ack" in output
  assert "Pending:" not in output
  assert all(message_id not in output for message_id in pending_ids)


@pytest.mark.parametrize(
  ("line", "command"),
  (
    ("/bin/bash -l -c ss -ltn", "ss -ltn"),
    ("/bin/bash -l -c ss -ltnH", "ss -ltnH"),
    ("/bin/bash -l -c netstat -ltn", "netstat -ltn"),
    ("/bin/bash -l -c netstat -ltnp", "netstat -ltnp"),
    (pre.ARENA_PORT_PROBE, "command -v ss"),
    ("/bin/bash -l -c source ~/.profile", "source ~/.profile"),
    (
      "/bin/bash -l -c 'arena-workspace read /home/user/project/README.md'",
      "arena-workspace read /home/user/project/README.md",
    ),
  ),
)
def test_arena_platform_shells_do_not_spend_inbox_call_budget(
  _isolate_state: Path, line: str, command: str
) -> None:
  _seed(_isolate_state, "Pending work")
  store, _, _, _ = cli.open_services(_isolate_state)
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD))
  store.close()

  code, out = _run("pre", "-l", line, "-c", command, "-s", "bash")
  assert code == pre.CONTINUE, out
  assert _count(_isolate_state) == str(pre.GATE_THRESHOLD)
  assert '_arena_preview_done="gate"' in out


@pytest.mark.parametrize(
  ("line", "command", "cleanup"),
  (
    ("/bin/bash -lc ss -ltnH", "ss -ltnH", "[ -f ~/.profile ]"),
    ("/bin/bash -lc netstat -ltnp", "netstat -ltnp", "unset _steer_hook"),
    ("/bin/bash -lc source ~/.profile", "source ~/.profile", "[ -f ~/.profile ]"),
    (
      "/bin/bash -lc 'arena-workspace read /home/user/project/README.md'",
      "arena-workspace read /home/user/project/README.md",
      "unset _steer_hook",
    ),
  ),
)
def test_exact_maintenance_shell_skips_its_cleanup_without_widening_the_match(
  _isolate_state: Path, line: str, command: str, cleanup: str
) -> None:
  _seed(_isolate_state, "Pending work")
  store, _, _, _ = cli.open_services(_isolate_state)
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD))
  store.close()
  code, out = _run("pre", "-l", line, "-c", command, "-s", "bash")
  assert code == pre.CONTINUE, out
  assert '_arena_preview_done="gate"' in out
  assert _count(_isolate_state) == str(pre.GATE_THRESHOLD)
  blocked, out = _run("pre", "-l", line, "-c", cleanup, "-s", "bash")
  assert blocked == pre.BLOCK, out
  count_after_block = _count(_isolate_state)
  assert count_after_block == str(pre.GATE_THRESHOLD + 1)
  code, out = _run("pre", "-l", line, "-c", cleanup, "-s", "bash", "--done", "gate")
  assert code == pre.CONTINUE, out
  assert _count(_isolate_state) == count_after_block


def test_port_probe_bypasses_inbox_gate_even_if_policy_would_block(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  probe = pre.PreContext(
    line=pre.ARENA_PORT_PROBE,
    command="command -v ss",
    pending_ids=["pending"],
    call_count=pre.GATE_THRESHOLD,
  )
  monkeypatch.setattr(pre, "bash_command_policy", lambda _ctx: (True, True))
  assert not pre.InboxGate().applies(probe)

  push = pre.PreContext(
    line="git push origin topic",
    command="git push origin topic",
    pending_ids=["pending"],
    call_count=pre.GATE_THRESHOLD,
  )
  monkeypatch.setattr(pre, "bash_command_policy", lambda _ctx: (False, False))
  assert pre.InboxGate().applies(push)
  nested_push = pre.PreContext(
    line="/bin/bash -lc ss -ltnH",
    command="git push origin topic",
    done=("gate",),
    pending_ids=["pending"],
    call_count=pre.GATE_THRESHOLD,
  )
  assert pre.InboxGate().applies(nested_push)
  assert pre.run_pipeline(nested_push).verdict == pre.BLOCK


def test_exact_arena_process_probe_skips_block_and_call_count(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  script = "ports_observed=1\necho '===ARENA_ENTRY==='\necho '===ARENA_PORTS==='"
  monkeypatch.setattr(
    pre,
    "ARENA_PROCESS_PROBE_SHA256",
    hashlib.sha256(script.encode()).hexdigest(),
    raising=False,
  )
  _seed(_isolate_state, "Pending work")
  store, _, _, _ = cli.open_services(_isolate_state)
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD))
  store.close()

  code, output = _run("pre", "-l", script, "-c", "ports_observed=1", "-s", "bash")
  assert code == pre.CONTINUE, output
  assert _count(_isolate_state) == str(pre.GATE_THRESHOLD)

  changed = script + "\necho extra"
  code, output = _run("pre", "-l", changed, "-c", "ports_observed=1", "-s", "bash")
  assert code == pre.BLOCK, output
  assert _count(_isolate_state) == str(pre.GATE_THRESHOLD + 1)


@pytest.mark.parametrize(
  ("line", "command"),
  (
    ("mkdir -p 'cache dir'", "mkdir -p 'cache dir'"),
    ("/bin/bash -l -c 'mkdir -p cache'", "mkdir -p cache"),
  ),
)
def test_standalone_mkdir_runs_but_counts_while_inbox_waits(
  _isolate_state: Path, line: str, command: str
) -> None:
  _seed(_isolate_state, "Pending work")
  store, _, _, _ = cli.open_services(_isolate_state)
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD))
  store.close()

  code, output = _run("pre", "-l", line, "-c", command, "-s", "bash")
  assert code == pre.CONTINUE, output
  assert _count(_isolate_state) == str(pre.GATE_THRESHOLD + 1)
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert messages.pending_violation() is None
  store.close()


@pytest.mark.parametrize(
  ("line", "command"),
  (
    ("mkdir -p cache && printf extra", "mkdir -p cache"),
    ("mkdir -p cache | cat", "mkdir -p cache"),
    ('mkdir "$(touch /tmp/marker)"', 'mkdir "$(touch /tmp/marker)"'),
    ("mkdir cache > /tmp/marker", "mkdir cache > /tmp/marker"),
  ),
)
def test_mixed_mkdir_lines_stay_inbox_gated(
  _isolate_state: Path, line: str, command: str
) -> None:
  _seed(_isolate_state, "Pending work")
  store, _, _, _ = cli.open_services(_isolate_state)
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD))
  store.close()

  code, output = _run("pre", "-l", line, "-c", command, "-s", "bash")
  assert code == pre.BLOCK, output
  assert _count(_isolate_state) == str(pre.GATE_THRESHOLD + 1)


def test_marked_detached_shell_does_not_spend_inbox_call_budget(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  _seed(_isolate_state, "Pending work")
  store, _, _, _ = cli.open_services(_isolate_state)
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD))
  store.close()
  monkeypatch.setenv("ARENA_STEER_ROUTE", "1")

  code, out = _run("pre", "-l", "printf ok", "-c", "printf ok", "-s", "bash")
  assert code == pre.CONTINUE, out
  assert _count(_isolate_state) == str(pre.GATE_THRESHOLD)

  code, out = _run(
    "pre", "-l", "git push origin topic", "-c", "git push origin topic", "-s", "bash"
  )
  assert code == pre.BLOCK
  assert "PUSH BLOCKED" in out


@pytest.mark.parametrize(
  ("line", "command"),
  (
    ("/bin/bash -l -c 'ss -ltn && printf extra'", "ss -ltn"),
    (pre.ARENA_PORT_PROBE + "; printf extra", "command -v ss"),
    (
      "/bin/bash -l -c 'arena-workspace read /home/user/project/README.md; printf extra'",
      "arena-workspace read /home/user/project/README.md",
    ),
  ),
)
def test_mixed_platform_probe_remains_inbox_gated(
  _isolate_state: Path, line: str, command: str
) -> None:
  _seed(_isolate_state, "Pending work")
  store, _, _, _ = cli.open_services(_isolate_state)
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD))
  store.close()

  code, out = _run("pre", "-l", line, "-c", command, "-s", "bash")
  assert code == pre.BLOCK
  assert "BASH BLOCKED" in out
  assert _count(_isolate_state) == str(pre.GATE_THRESHOLD + 1)


def test_six_call_bash_block_persists_one_violation_for_inbox_gate(
  _isolate_state: Path,
) -> None:
  store, messages, _, _ = cli.open_services(_isolate_state)
  note = messages.send_message("Pending work", msg_id="ab0091")
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD - 1))
  store.close()

  command = ("pre", "-c", "printf ok", "-l", "printf ok", "-s", "bash")
  assert _run(*command)[0] == pre.CONTINUE
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert store.get_meta(pre.CALL_COUNT_META) == str(pre.GATE_THRESHOLD)
  assert messages.pending_violation() is None
  store.close()

  assert _run(*command)[0] == pre.BLOCK
  store, messages, _, _ = cli.open_services(_isolate_state)
  flag = messages.pending_violation()
  assert flag is not None and flag.hidden and flag.requires_ack
  assert flag.violation_type == "bash-cadence"
  assert set(messages.pending_ids()) == {note.id, flag.id}
  assert _run(*command)[0] == pre.BLOCK
  assert messages.pending_violation().id == flag.id
  messages.ack(flag.id, "Read and correcting the cadence.")

  for line in ("sleep 60", "git push origin branch", "steer read"):
    code, _ = _run("pre", "-c", line, "-l", line, "-s", "bash")
    assert code == (pre.CONTINUE if line == "steer read" else pre.BLOCK)
    if line == "sleep 60":
      sleep_flag = messages.pending_violation()
      assert sleep_flag is not None and sleep_flag.violation_type == "bash-sleep"
      messages.ack(sleep_flag.id, "Avoided the sleep.")
    else:
      assert messages.pending_violation() is None
  assert _run("read")[0] == 0
  assert _run("ack", note.id, "Read and done.")[0] == 0
  assert store.get_meta(pre.CALL_COUNT_META) == "0"
  store.close()


@pytest.mark.parametrize(
  ("line", "violation_type", "guidance"),
  (
    ("steer read | cat", "bash-inbox-pipe", "Run `steer read` or `steer poll` alone"),
    ("sleep 60", "bash-sleep", "Use a worktree"),
    ("git add shot-wireframe.png", "bash-commit-content", "Remove captures"),
  ),
)
def test_blocked_bash_patterns_persist_distinct_deduplicated_flags(
  _isolate_state: Path, line: str, violation_type: str, guidance: str
) -> None:
  _seed(_isolate_state, "Ready", acked=True)
  command = ("pre", "-c", line, "-l", line, "-s", "bash")
  assert _run(*command)[0] == pre.BLOCK
  store, messages, _, _ = cli.open_services(_isolate_state)
  flag = messages.pending_violation()
  assert flag is not None and flag.hidden and flag.requires_ack
  assert flag.violation_type == violation_type
  assert guidance in flag.body
  code, out = _run(*command)
  assert code == pre.BLOCK and flag.id in out
  assert messages.pending_violation().id == flag.id
  assert messages.pending_ids() == [flag.id]
  store.close()


@pytest.mark.parametrize(
  "line", ("steer ack a1b2c3 done | cat", "sleep 59", "git add plain.png")
)
def test_allowed_bash_patterns_do_not_flag(_isolate_state: Path, line: str) -> None:
  _seed(_isolate_state, "Ready", acked=True)
  code, _ = _run("pre", "-c", line, "-l", line, "-s", "bash")
  assert code == pre.CONTINUE
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert messages.pending_violation() is None
  store.close()


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


@pytest.mark.parametrize(
  ("line", "running", "expected"),
  (
    ("sleep 60", (), pre.BLOCK),
    ("FOO=bar sleep 60", (), pre.BLOCK),
    ("time sleep 60", (), pre.BLOCK),
    ("sleep 1 && tail -n 2 verify.log", (), pre.BLOCK),
    ("sleep 59", (), pre.CONTINUE),
    ('printf "sleep 60"', (), pre.CONTINUE),
    ("sleep 1", ("verify",), pre.BLOCK),
  ),
)
def test_sleep_cases(line: str, running: tuple[str, ...], expected: int) -> None:
  ctx = pre.PreContext(line=line, command=line, shell="bash", active_runs=running)
  assert pre.run_pipeline(ctx).verdict == expected


def test_active_run_blocks_sleep_but_not_its_own_worker(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  _seed(_isolate_state, "Acknowledged note.", acked=True)
  runs = _isolate_state / "runs"
  runs.mkdir()
  exit_path = runs / "verify.exit"
  (runs / "verify.json").write_text(
    json.dumps({"exit_path": str(exit_path)}), encoding="utf-8"
  )

  code, out = _run("pre", "-l", "sleep 1", "-c", "sleep 1", "-s", "bash", "-d", "sleep")
  assert code == pre.BLOCK
  assert "verify" in out

  monkeypatch.setenv("ARENA_STEER_ROUTE", "1")
  code, _ = _run("pre", "-l", "sleep 60", "-c", "sleep 60", "-s", "bash")
  assert code == pre.CONTINUE
  monkeypatch.delenv("ARENA_STEER_ROUTE")

  exit_path.write_text("0", encoding="utf-8")
  code, _ = _run("pre", "-l", "sleep 1", "-c", "sleep 1", "-s", "bash")
  assert code == pre.CONTINUE


@pytest.mark.parametrize(
  ("line", "expected"),
  (
    ("steer read | cat", pre.BLOCK),
    ("steer poll | tee /dev/null", pre.BLOCK),
    ("bash -c steer poll | cat", pre.BLOCK),
    ("bash -c 'steer read | cat'", pre.BLOCK),
    ("env LANG=C steer poll | cat", pre.BLOCK),
    ("timeout 10 steer poll", pre.BLOCK),
    ("timeout 1800 steer poll", pre.BLOCK),
    ("timeout 10 bash -c 'steer poll'", pre.BLOCK),
    ('printf "timeout 10 steer poll"', pre.CONTINUE),
    ("timeout 10 steer read", pre.CONTINUE),
    ("timeout 10 printf steer poll", pre.CONTINUE),
    ("steer ack a1b2c3 done | cat", pre.CONTINUE),
  ),
)
def test_inbox_pipes_and_poll_timeout(line: str, expected: int) -> None:
  result = pre.run_pipeline(pre.PreContext(line=line, command=line, shell="bash"))
  assert result.verdict == expected


def test_piped_ack_remains_available_after_the_gate_limit() -> None:
  ctx = pre.PreContext(
    line="steer ack a1b2c3 done | cat",
    command="steer ack a1b2c3 done",
    shell="bash",
    pending_ids=["a1b2c3"],
    call_count=pre.GATE_THRESHOLD,
  )
  assert pre.run_pipeline(ctx).verdict == pre.CONTINUE


def test_a_partial_read_of_the_bible_blocks_every_verb() -> None:
  guard = pre.BibleReadGuard()
  assert guard.SKILL_DIRS == ("arena-steering",)
  for line in (
    "rg -n 'gate' AGENTS.md",
    "grep -n gate ARENA.md",
    "head -20 ARENA.md",
    "tail -n 5 skills/arena-steering/SKILL.md",
    "cat skills/arena-steering/SKILL.md",
    "cat AGENTS.md | head -n 5",
    "head -n 5 < ARENA.md",
    "cat .agents/skills/arena-steering/SKILL.md | tail -n 5",
    "env rg -n gate AGENTS.md",
    "bash -lc 'rg -n gate AGENTS.md'",
    "find skills -name AGENTS.md -print && rg -n gate AGENTS.md",
    "rg -n gate AGENTS.md && find skills -name ARENA.md -print",
  ):
    ctx = pre.PreContext(line=line, shell="bash")
    assert guard.applies(ctx), line
    assert guard.run(ctx).verdict == pre.BLOCK, line

  for line in (
    "rg -n gate skills/arena-steering",
    "head -20 assets/app.js",
    "tail -n 5 skills/unrelated/SKILL.md",
    "rg -n gate skills/arena-steering && find skills -name AGENTS.md -print",
    "find skills -name ARENA.md -print && rg -n gate tests/skills/arena-steering/test_pre.py",
    "printf AGENTS.md | head -n 1",
  ):
    assert not guard.applies(pre.PreContext(line=line, shell="bash")), line


@pytest.mark.parametrize(
  ("line", "blocked"),
  (
    ("gh pr merge 42 --squash", True),
    ("gh pr close 42", True),
    ("gh pr close 42 --comment '--help'", True),
    ("gh pr reopen 42", True),
    ("gh pr merge 42 --help", False),
    ("gh api repos/o/r/pulls/42/merge -X PUT", True),
    ("gh api repos/o/r/pulls/42 -X PATCH -f state=closed", True),
    (
      "gh api graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'",
      True,
    ),
    (
      (
        'gh api graphql -f query="mutation ($input: UpdatePullRequestInput!) '
        '{ updatePullRequest(input: $input) { clientMutationId } }" '
        '-f variables=\'{"input":{"state":"CLOSED"}}\''
      ),
      True,
    ),
    (
      'curl -X PATCH https://api.github.com/repos/o/r/pulls/42 -d \'{"state":"closed"}\'',
      True,
    ),
    ("git push --delete origin feature", True),
    ("git push --mirror origin", True),
    ("git push origin :feature", True),
    ("printf 'gh pr merge 42'", False),
    ("gh pr view 42", False),
    ("gh pr edit 42 --title 'Open'", False),
    ("gh api repos/o/r/pulls/42 -X PATCH -f title=closed", False),
    ("git push --dry-run origin :feature", False),
    ("git push -n origin :feature", False),
  ),
)
def test_git_and_pr_state_commands(line: str, blocked: bool) -> None:
  result = pre.run_pipeline(pre.PreContext(line=line, command=line, shell="bash"))
  assert result.verdict == (pre.BLOCK if blocked else pre.CONTINUE), line
  if blocked:
    assert "BLOCKED" in " ".join(result.messages)


def test_pr_api_file_payload_blocks_state_only(tmp_path: Path) -> None:
  body = tmp_path / "pr.json"
  line = f"gh api repos/o/r/pulls/42 -X PATCH --input {body}"
  ctx = pre.PreContext(line=line, command=line)
  body.write_text('{"state":"closed"}', encoding="utf-8")
  assert pre.run_pipeline(ctx).verdict == pre.BLOCK
  body.write_text('{"title":"New title"}', encoding="utf-8")
  assert pre.run_pipeline(ctx).verdict == pre.CONTINUE

  field = tmp_path / "state.txt"
  field.write_text("closed\n", encoding="utf-8")
  line = f"gh api repos/o/r/pulls/42 -X PATCH -F state=@{field}"
  assert pre.run_pipeline(pre.PreContext(line=line, command=line)).verdict == pre.BLOCK


@pytest.fixture
def _git_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
  repo = tmp_path / "checkout"
  repo.mkdir()

  def git(*args: str, cwd: Path = repo) -> str:
    return subprocess.run(
      ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()

  git("init", "-b", "main")
  git("config", "user.email", "steer@example.test")
  git("config", "user.name", "Steer Test")
  (repo / "note.md").write_text("initial\n", encoding="utf-8")
  git("add", "note.md")
  git("commit", "-m", "init")
  monkeypatch.chdir(repo)
  monkeypatch.setattr(pre, "repo_root", lambda: repo)
  return repo


def test_commit_refuses_staged_capture_and_new_session_id(
  _isolate_state: Path, _git_checkout: Path
) -> None:
  _seed(_isolate_state, "Read the message.", acked=True)
  store, _, _, _ = cli.open_services(_isolate_state)
  message_id = store.list_messages(include_hidden=True)[0].id
  store.close()

  def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=_git_checkout, check=True, capture_output=True)

  capture = _git_checkout / "design-wireframe.png"
  capture.write_bytes(b"image")
  git("add", capture.name)
  code, out = _run(
    "pre", "-l", "git commit -m review", "-c", "git commit -m review", "-s", "bash"
  )
  assert code == pre.BLOCK and "design-wireframe.png" in out
  store, messages, _, _ = cli.open_services(_isolate_state)
  staged_flag = messages.pending_violation()
  assert staged_flag is not None and staged_flag.violation_type == "bash-commit-content"
  messages.ack(staged_flag.id, "Removed the capture.")
  store.close()

  git("reset", "--", capture.name)
  note = _git_checkout / "note.md"
  note.write_text(f"initial\nSee {message_id}.\n", encoding="utf-8")
  git("add", "note.md")
  code, out = _run(
    "pre",
    "-l",
    "git commit -m review",
    "-c",
    "git commit -m review",
    "-s",
    "bash",
    "-d",
    "git-safe",
  )
  assert code == pre.BLOCK and message_id in out
  assert "note.md" in out
  store, messages, _, _ = cli.open_services(_isolate_state)
  session_flag = messages.pending_violation()
  assert (
    session_flag is not None and session_flag.violation_type == "bash-commit-content"
  )
  nested = "bash -c 'git commit -m review'"
  code, out = _run("pre", "-l", nested, "-c", nested, "-s", "bash")
  assert code == pre.BLOCK and message_id in out
  assert messages.pending_violation().id == session_flag.id
  messages.ack(session_flag.id, "Removed the session ID.")
  store.close()

  git("commit", "-m", "fixture")
  note.write_text("initial\n", encoding="utf-8")
  git("add", "note.md")
  code, _ = _run(
    "pre", "-l", "git commit -m review", "-c", "git commit -m review", "-s", "bash"
  )
  assert code == pre.CONTINUE

  git("commit", "-m", "remove")
  note.write_text(f"initial\nSee {message_id}.\n", encoding="utf-8")
  code, out = _run(
    "pre", "-l", "git commit -am review", "-c", "git commit -am review", "-s", "bash"
  )
  assert code == pre.BLOCK and message_id in out


def test_commit_comparison_failure_does_not_flag_content(
  _isolate_state: Path, _git_checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  _seed(_isolate_state, "Ready", acked=True)
  monkeypatch.setattr(
    pre.git_safety,
    "staged_warning",
    lambda _cwd, _ids, **_kwargs: "COMMIT BLOCKED: Git changes could not be checked.",
  )
  code, out = _run(
    "pre", "-l", "git commit -m review", "-c", "git commit -m review", "-s", "bash"
  )
  assert code == pre.BLOCK
  assert out.splitlines()[0] == "COMMIT BLOCKED: Git changes could not be checked."
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert messages.pending_violation() is None
  store.close()


def test_managed_worktree_refuses_commit_push_and_run(
  _isolate_state: Path, _git_checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  _seed(_isolate_state, "Acknowledged note.", acked=True)
  worktree = _git_checkout / ".worktrees" / "probe"
  worktree.parent.mkdir()
  subprocess.run(
    ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
    cwd=_git_checkout,
    check=True,
    capture_output=True,
  )
  monkeypatch.chdir(worktree)
  for command in (
    "git commit -m review",
    "git push origin topic",
    "steer run start verify -- true",
  ):
    code, out = _run("pre", "-l", command, "-c", command, "-s", "bash")
    assert code == pre.BLOCK and "WORKTREE BLOCKED" in out, command

  monkeypatch.chdir(_git_checkout)
  command = f"git -C {worktree} commit -m review"
  code, out = _run("pre", "-l", command, "-c", command, "-s", "bash")
  assert code == pre.BLOCK and "WORKTREE BLOCKED" in out


def test_push_uses_remote_default_and_fails_closed(
  _isolate_state: Path, _git_checkout: Path, tmp_path: Path
) -> None:
  _seed(_isolate_state, "Acknowledged note.", acked=True)
  origin = tmp_path / "origin.git"
  subprocess.run(
    ["git", "init", "--bare", "-b", "trunk", str(origin)],
    check=True,
    capture_output=True,
  )

  def git(*args: str, cwd: Path = _git_checkout) -> str:
    return subprocess.run(
      ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()

  git("remote", "add", "origin", str(origin))
  git("push", "origin", "HEAD:trunk")
  code, out = _run(
    "pre",
    "-l",
    "git push origin HEAD:trunk",
    "-c",
    "git push origin HEAD:trunk",
    "-s",
    "bash",
  )
  assert code == pre.BLOCK and "trunk" in out
  code, _ = _run(
    "pre",
    "-l",
    "git push origin HEAD:topic",
    "-c",
    "git push origin HEAD:topic",
    "-s",
    "bash",
  )
  assert code == pre.CONTINUE

  other = tmp_path / "other"
  git("clone", str(origin), str(other))
  git("config", "user.email", "steer@example.test", cwd=other)
  git("config", "user.name", "Steer Test", cwd=other)
  (other / "new.md").write_text("new\n", encoding="utf-8")
  git("add", "new.md", cwd=other)
  git("commit", "-m", "advance", cwd=other)
  git("push", "origin", "trunk", cwd=other)
  code, out = _run(
    "pre",
    "-l",
    "git push origin HEAD:topic",
    "-c",
    "git push origin HEAD:topic",
    "-s",
    "bash",
    "-d",
    "git-safe",
  )
  assert code == pre.BLOCK and "trunk" in out
  nested = "bash -c 'git push origin HEAD:topic'"
  code, out = _run("pre", "-l", nested, "-c", nested, "-s", "bash")
  assert code == pre.BLOCK and "trunk" in out

  git("remote", "set-url", "origin", str(tmp_path / "missing.git"))
  code, out = _run(
    "pre",
    "-l",
    "git push origin HEAD:topic",
    "-c",
    "git push origin HEAD:topic",
    "-s",
    "bash",
  )
  assert code == pre.BLOCK and "unavailable" in out.lower()

  extra = tmp_path / "extra.git"
  git("init", "--bare", "-b", "develop", str(extra))
  git("remote", "add", "extra", str(extra))
  git("push", "extra", "HEAD:develop")
  git("branch", "-m", "develop")
  git("config", "remote.pushDefault", "extra")
  code, out = _run("pre", "-l", "git push", "-c", "git push", "-s", "bash")
  assert code == pre.BLOCK and "develop" in out


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
  line = "/repo/skills/arena-steering/scripts/steer --version"
  code, out = _run("pre", "-l", line, "-s", "bash")
  assert code == pre.CONTINUE
  assert '_arena_preview_done="bare"' in out

  code, out = _run("pre", "-l", line, "-s", "bash", "-d", "bare")
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

  code, out = _run("pre", "-c", "git push --dry-run", "-s", "bash")
  assert code == pre.CONTINUE
  assert "BLOCKED" not in out


def test_a_clear_inbox_passes_the_gate(_isolate_state: Path) -> None:
  _seed(_isolate_state, "Acked already.", acked=True)
  code, out = _run("pre", "-c", "git push --dry-run", "-s", "bash")
  assert code == pre.CONTINUE
  assert "BLOCKED" not in out


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
  subprocess.run(
    ["git", "init", "--quiet", "-b", "main", str(project)],
    check=True,
    capture_output=True,
  )
  home = tmp_path / "home with spaces"
  python = home / ".agents" / ".steer-venv" / "bin" / "python"
  python.parent.mkdir(parents=True)
  python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
  python.chmod(0o755)
  profile = home / ".bash_profile"
  profile.write_text(
    "# Existing profile content\n"
    'trap \'printf "%s\\n" "$BASH_COMMAND" >> "$HOME/prior-debug.log"\' DEBUG\n',
    encoding="utf-8",
  )
  outside = tmp_path / "outside"
  outside.mkdir()
  env = {
    **os.environ,
    "HOME": str(home),
    "PATH": "/usr/bin:/bin",
    "STEER_STATE_DIR": str(tmp_path / "override"),
  }
  install = scripts / "install.sh"
  state_dir = project / "arena-state"
  database = state_dir / "state.sqlite3"
  for attempt in range(2):
    result = subprocess.run(
      ["bash", str(install)],
      check=False,
      cwd=project,
      env=env,
      capture_output=True,
      text=True,
    )
    assert result.returncode == 0, result.stderr
    assert database.is_file()
    if attempt == 0:
      _seed(state_dir, "Keep this note through reinstall.", acked=True)
  with sqlite3.connect(database) as connection:
    assert connection.execute("SELECT body FROM messages").fetchall() == [
      ("Keep this note through reinstall.",)
    ]
  profile_text = profile.read_text(encoding="utf-8")
  assert profile_text.count("# Existing profile content") == 1
  profile.write_text(
    profile_text.replace("_steer_single_push_approved=\n", "", 1), encoding="utf-8"
  )
  refreshed = subprocess.run(
    ["bash", str(install)],
    check=False,
    cwd=project,
    env=env,
    capture_output=True,
    text=True,
  )
  assert refreshed.returncode == 0, refreshed.stderr
  assert profile.read_text(encoding="utf-8") == profile_text
  with sqlite3.connect(database) as connection:
    assert connection.execute("SELECT body FROM messages").fetchall() == [
      ("Keep this note through reinstall.",)
    ]
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
  assert "steer 2.2.0" in result.stdout

  shell = subprocess.run(
    [
      "bash",
      "-c",
      'source "$HOME/.bash_profile"; source "$HOME/.bash_profile"; printf "safe command\\n"; trap -p DEBUG',
    ],
    check=False,
    cwd=outside,
    env=env,
    capture_output=True,
    text=True,
  )
  assert shell.returncode == 0, shell.stderr
  assert "safe command" in shell.stdout
  assert "STATE UNAVAILABLE" not in shell.stdout
  assert shell.stdout.count("arena-steering-gate") == 1
  assert "safe command" in (home / "prior-debug.log").read_text(encoding="utf-8")

  clear_inbox_push = subprocess.run(
    [
      "bash",
      "-c",
      'source "$HOME/.bash_profile"; git() { echo push-ran; }; git push --dry-run origin fake',
    ],
    check=False,
    cwd=outside,
    env=env,
    capture_output=True,
    text=True,
  )
  assert clear_inbox_push.returncode == 0, clear_inbox_push.stderr
  assert "STATE UNAVAILABLE" not in clear_inbox_push.stdout
  assert "push-ran" in clear_inbox_push.stdout

  _seed(state_dir, "Read and acknowledge this note.")
  for utility in ("ss", "netstat"):
    probe = home / ".local" / "bin" / utility
    probe.write_text('#!/bin/sh\nprintf "port-probe-ran\\n"\n', encoding="utf-8")
    probe.chmod(0o755)
  store, _messages, _tasks, _reports = cli.open_services(state_dir)
  store.set_meta(pre.CALL_COUNT_META, str(pre.GATE_THRESHOLD))
  store.close()
  for command in ("ss -ltnH", "netstat -ltnp"):
    first_probe = subprocess.run(
      ["bash", "-lc", command],
      check=False,
      cwd=outside,
      env=env,
      capture_output=True,
      text=True,
    )
    assert first_probe.returncode == 0, first_probe.stdout + first_probe.stderr
    assert "port-probe-ran" in first_probe.stdout
    assert _count(state_dir) == str(pre.GATE_THRESHOLD)
    assert command in (home / "prior-debug.log").read_text(encoding="utf-8")
  (home / ".local" / "bin" / "netstat").write_text(
    "#!/bin/sh\nexit 5\n", encoding="utf-8"
  )
  failing_probe = subprocess.run(
    ["bash", "-lc", "netstat -ltnp"],
    check=False,
    cwd=outside,
    env=env,
    capture_output=True,
    text=True,
  )
  assert failing_probe.returncode == 5, failing_probe.stdout + failing_probe.stderr
  assert _count(state_dir) == str(pre.GATE_THRESHOLD)
  store, _messages, _tasks, _reports = cli.open_services(state_dir)
  store.set_meta(pre.CALL_COUNT_META, "0")
  store.close()

  pending_push = subprocess.run(
    [
      "bash",
      "-c",
      'source "$HOME/.bash_profile"; git() { echo push-ran; }; git push --dry-run origin fake',
    ],
    check=False,
    cwd=outside,
    env=env,
    capture_output=True,
    text=True,
  )
  assert pending_push.returncode == pre.BLOCK
  assert PENDING_ACK_PUSH_REASON in pending_push.stdout
  assert "push-ran" not in pending_push.stdout

  read = subprocess.run(
    ["bash", "-c", 'source "$HOME/.bash_profile"; steer read'],
    check=False,
    cwd=outside,
    env=env,
    capture_output=True,
    text=True,
  )
  assert read.returncode == 0, read.stderr
  assert (project / "arena-state" / "state.sqlite3").is_file()
  assert not (outside / "arena-state").exists()
  assert not (tmp_path / "override").exists()

  zone_env = {key: value for key, value in env.items() if key != "TZ"}
  live_shell = subprocess.run(
    [
      "bash",
      "-c",
      (
        'source "$HOME/.bash_profile"; printf "%s" "${TZ:-}" > "$HOME/tz-before"; '
        'printf "Asia/Manila\\n" > "$_steer_repo_root/arena-state/display_tz"; '
        'printf "%s" "${TZ:-}" > "$HOME/tz-after"'
      ),
    ],
    check=False,
    cwd=outside,
    env=zone_env,
    capture_output=True,
    text=True,
  )
  assert live_shell.returncode == 0, live_shell.stderr
  assert (home / "tz-before").read_text(encoding="utf-8") == ""
  assert (home / "tz-after").read_text(encoding="utf-8") == "Asia/Manila"

  for initial, expected in ((None, "Asia/Manila"), ("UTC", "UTC")):
    zone_env = {key: value for key, value in env.items() if key != "TZ"}
    if initial is not None:
      zone_env["TZ"] = initial
    zone_shell = subprocess.run(
      [
        "bash",
        "-c",
        'source "$HOME/.bash_profile"; printf "%s" "${TZ:-}" > "$HOME/tz-result"',
      ],
      check=False,
      cwd=outside,
      env=zone_env,
      capture_output=True,
      text=True,
    )
    assert zone_shell.returncode == 0, zone_shell.stderr
    assert (home / "tz-result").read_text(encoding="utf-8") == expected

  push = subprocess.run(
    [
      "bash",
      "-c",
      'source "$HOME/.bash_profile"; git() { echo push-ran; }; git push --dry-run origin fake',
    ],
    check=False,
    cwd=outside,
    env=env,
    capture_output=True,
    text=True,
  )
  assert push.returncode == pre.BLOCK
  assert PENDING_ACK_PUSH_REASON in push.stdout
  assert "push-ran" not in push.stdout


def test_clear_inbox_single_push_arms_exit_guard_only_for_whole_line(
  _isolate_state: Path,
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  line = "/bin/bash -lc git push --dry-run"
  code, output = _run("pre", "-l", line, "-c", "git push --dry-run", "-s", "bash")
  assert code == pre.CONTINUE, output
  assert "_steer_single_push_approved=1" in output

  mixed = "git push --dry-run; printf extra"
  code, output = _run("pre", "-l", mixed, "-c", "git push --dry-run", "-s", "bash")
  assert code == pre.CONTINUE, output
  assert "_steer_single_push_approved=1" not in output


def test_installer_exit_hook_preserves_prior_trap_and_call_status(
  tmp_path: Path,
) -> None:
  root = Path(__file__).resolve().parents[3]
  project = tmp_path / "project with spaces"
  scripts = project / ".agents" / "skills" / "arena-steering" / "scripts"
  shutil.copytree(root / "skills" / "arena-steering" / "scripts", scripts)
  shutil.copytree(
    root / "skills" / "arena-steering" / "references", scripts.parent / "references"
  )
  subprocess.run(
    ["git", "init", "--quiet", "-b", "main", str(project)],
    check=True,
    capture_output=True,
  )
  home = tmp_path / "home with spaces"
  python = home / ".agents" / ".steer-venv" / "bin" / "python"
  python.parent.mkdir(parents=True)
  python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
  python.chmod(0o755)
  profile = home / ".bash_profile"
  profile.write_text(
    'trap \'printf "prior-exit:%s\\n" "$?" >> "$HOME/prior-exit.log"\' EXIT\n',
    encoding="utf-8",
  )
  env = {**os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin"}
  for _ in range(2):
    installed = subprocess.run(
      ["bash", str(scripts / "install.sh")],
      cwd=project,
      env=env,
      capture_output=True,
      text=True,
      check=False,
    )
    assert installed.returncode == 0, installed.stderr
  assert "arena-steering-exit-trap" in profile.read_text(encoding="utf-8")

  command = home / ".local" / "bin" / "steer"
  command.write_text(
    '#!/bin/sh\ncase "$1" in\n'
    '  pre) if [ -e "$HOME/late-note" ]; then printf "PUSH BLOCKED\\n"; exit 130; fi; '
    'case " $* " in *" --command git push origin topic "*) '
    'printf "_steer_single_push_approved=1\\n" ;; esac ;;\n'
    '  post-exit) printf "%s\\n" "$*" >> "$HOME/post-exit.log" ;;\n'
    "esac\n",
    encoding="utf-8",
  )
  command.chmod(0o755)
  for status in (0, 5):
    shell = subprocess.run(
      [
        "bash",
        "-c",
        (
          f'source "$HOME/.bash_profile"; source "$HOME/.bash_profile"; '
          f"git() {{ return {status}; }}; git push origin topic"
        ),
      ],
      cwd=project,
      env=env,
      capture_output=True,
      text=True,
      check=False,
    )
    assert shell.returncode == status, shell.stderr
  strict = subprocess.run(
    [
      "bash",
      "-c",
      'source "$HOME/.bash_profile"; set -e; git() { return 7; }; git push origin topic',
    ],
    cwd=project,
    env=env,
    capture_output=True,
    text=True,
    check=False,
  )
  assert strict.returncode == 7, strict.stderr
  exits = (home / "post-exit.log").read_text(encoding="utf-8").splitlines()
  assert len(exits) == 3
  assert "--rc 0" in exits[0] and "git push origin topic" in exits[0]
  assert all("--elapsed " in exit_line for exit_line in exits)
  assert "--rc 5" in exits[1] and "--rc 7" in exits[2]
  assert (home / "prior-exit.log").read_text(encoding="utf-8").splitlines() == [
    "prior-exit:0",
    "prior-exit:5",
    "prior-exit:7",
  ]

  fake_git = home / ".local" / "bin" / "git"
  fake_git.write_text(
    '#!/bin/sh\nprintf done > "$HOME/remote-updated"\n'
    'printf pending > "$HOME/late-note"\n',
    encoding="utf-8",
  )
  fake_git.chmod(0o755)
  late_note = subprocess.run(
    ["bash", "-c", "git push origin topic"],
    cwd=project,
    env={**env, "BASH_ENV": str(profile)},
    capture_output=True,
    text=True,
    check=False,
  )
  assert (home / "remote-updated").read_text(encoding="utf-8") == "done"
  assert late_note.returncode == 0, late_note.stdout
  assert "PUSH BLOCKED" not in late_note.stdout
  assert (
    "--rc 0" in (home / "post-exit.log").read_text(encoding="utf-8").splitlines()[-1]
  )


def test_installer_enforces_commit_messages_without_a_runtime_spec(
  tmp_path: Path,
) -> None:
  root = Path(__file__).resolve().parents[3]
  project = tmp_path / "project with spaces"
  scripts = project / ".agents" / "skills" / "arena-steering" / "scripts"
  shutil.copytree(root / "skills" / "arena-steering" / "scripts", scripts)
  shutil.copytree(
    root / "skills" / "arena-steering" / "references", scripts.parent / "references"
  )
  subprocess.run(
    ["git", "init", "--quiet", "-b", "main", str(project)],
    check=True,
    capture_output=True,
  )
  home = tmp_path / "home with spaces"
  python = home / ".agents" / ".steer-venv" / "bin" / "python"
  python.parent.mkdir(parents=True)
  python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
  python.chmod(0o755)
  env = {**os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin"}
  for _ in range(2):
    installed = subprocess.run(
      ["bash", str(scripts / "install.sh")],
      cwd=project,
      env=env,
      capture_output=True,
      text=True,
      check=False,
    )
    assert installed.returncode == 0, installed.stderr

  hook = project / ".git" / "hooks" / "commit-msg"
  assert hook.is_file() and os.access(hook, os.X_OK)
  config = subprocess.run(
    ["git", "config", "--local", "--get", "core.hooksPath"],
    cwd=project,
    capture_output=True,
    text=True,
    check=True,
  )
  assert config.stdout.strip() == str(hook.parent)
  hook_source = hook.read_text(encoding="utf-8")
  assert "COMMIT-SPEC.txt" not in hook_source
  (project / "rules").mkdir()
  (project / "rules" / "COMMIT-SPEC.txt").write_text("not the spec\n", encoding="utf-8")
  message_file = tmp_path / "COMMIT_EDITMSG"

  for message in (
    "feat(git): install a project commit hook\n",
    "fix!: remove old behavior\n",
    "docs: " + "a" * 66 + "\n",
  ):
    message_file.write_text(message, encoding="utf-8")
    result = subprocess.run(
      [str(hook), str(message_file)],
      cwd=project,
      env=env,
      capture_output=True,
      text=True,
      check=False,
    )
    assert result.returncode == 0, result.stderr
    assert message_file.read_text(encoding="utf-8") == message

  for message in (
    "unknown: reject this type\n",
    "fix: Add a hook\n",
    "fix: add a hook.\n",
    "fix(scope with spaces): add a hook\n",
    "docs: " + "a" * 67 + "\n",
    "fix: add a hook\n\nBody text\n",
    "fix: add a hook\n\nCo-authored-by: agent <agent@example.test>\n",
  ):
    message_file.write_text(message, encoding="utf-8")
    result = subprocess.run(
      [str(hook), str(message_file)],
      cwd=project,
      env=env,
      capture_output=True,
      text=True,
      check=False,
    )
    assert result.returncode != 0, message
    assert "commit-msg:" in result.stderr
    assert message_file.read_text(encoding="utf-8") == message

  custom_hooks = tmp_path / "custom hooks"
  custom_hooks.mkdir()
  subprocess.run(
    ["git", "config", "--local", "core.hooksPath", str(custom_hooks)],
    cwd=project,
    capture_output=True,
    check=True,
  )
  refused = subprocess.run(
    ["bash", str(scripts / "install.sh")],
    cwd=project,
    env=env,
    capture_output=True,
    text=True,
    check=False,
  )
  assert refused.returncode != 0
  assert "core.hooksPath" in refused.stderr
  assert hook.read_text(encoding="utf-8") == hook_source


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
    "steer ack ab1234 Done | git -C /workspace push origin topic",
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


@pytest.mark.parametrize(
  ("line", "name"),
  (
    ("pytest -q", "pytest"),
    (".venv/bin/python -m pytest tests -q", "pytest"),
    ("env CI=1 pytest -q", "pytest"),
    ("timeout 5 pytest -q", "pytest"),
    ("tox -q", "tox"),
    ("nox -s test", "nox"),
    ("node --test", "node-tests"),
    ("npm test", "npm-tests"),
    ("npm run test:unit", "npm-tests"),
    ("npx vitest run", "npx-tests"),
    ("go test ./...", "go-tests"),
    ("cargo test", "cargo-tests"),
    ("gh pr checks 124 --watch", "pr-checks"),
    ("gh run watch 123", "run-watch"),
  ),
)
def test_test_and_check_waits_route_to_background(
  _isolate_state: Path,
  monkeypatch: pytest.MonkeyPatch,
  line: str,
  name: str,
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  started: list[tuple[str, list[str]]] = []

  def start(_state: Path, run_name: str, command: list[str], **_kwargs: object) -> int:
    started.append((run_name, command))
    return 0

  monkeypatch.setattr(cli, "_start_detached_run", start)
  code, out = _run("pre", "-l", line, "-c", line, "-s", "bash")
  assert code == pre.END_CALL, (line, out)
  assert started == [(name, ["bash", "-c", line])]
  assert "background" in out


@pytest.mark.parametrize(
  ("line", "command"),
  (
    ("printf ready && pytest -q", "pytest -q"),
    ("gh pr checks 124 --watch | tee checks.log", "gh pr checks 124 --watch"),
    ("pytest -q; printf done", "pytest -q"),
  ),
)
def test_mixed_test_wait_lines_refuse_replay(
  _isolate_state: Path,
  monkeypatch: pytest.MonkeyPatch,
  line: str,
  command: str,
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  monkeypatch.setattr(
    cli,
    "_start_detached_run",
    lambda *_args, **_kwargs: pytest.fail("mixed line was replayed"),
  )
  code, out = _run("pre", "-l", line, "-c", command, "-s", "bash")
  assert code == pre.BLOCK, (line, out)
  assert "mixed" in out.lower()


@pytest.mark.parametrize(
  "line",
  (
    'printf "pytest -q"',
    "pytest --help",
    "command -v pytest",
    "gh pr checks --help",
    "steer run start checks -- gh pr checks --watch",
  ),
)
def test_inert_test_words_do_not_route(_isolate_state: Path, line: str) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  code, _ = _run("pre", "-l", line, "-c", line, "-s", "bash")
  assert code == pre.CONTINUE


def test_routed_test_child_does_not_route_itself(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  monkeypatch.setenv("ARENA_STEER_ROUTE", "1")
  code, _ = _run("pre", "-l", "pytest -q", "-c", "pytest -q", "-s", "bash")
  assert code == pre.CONTINUE


def test_route_rechecks_even_if_an_earlier_shell_command_marked_it_done() -> None:
  result = pre.run_pipeline(
    pre.PreContext(line="pytest -q", command="pytest -q", done=("route",))
  )
  assert result.verdict == pre.END_CALL
  assert result.route == pre.RouteRequest("run", ("pytest",))


@pytest.mark.parametrize(
  ("line", "target"),
  (
    ("gh api repos/o/r/actions/jobs/123/logs", ("123", None)),
    ("curl https://api.github.com/repos/o/r/actions/runs/456/logs", (None, "456")),
  ),
)
def test_job_log_reads_route_to_helper(
  _isolate_state: Path,
  monkeypatch: pytest.MonkeyPatch,
  line: str,
  target: tuple[str | None, str | None],
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  routed: list[tuple[str | None, str | None]] = []

  def job_log(parsed: object, out: io.StringIO) -> int:
    routed.append((parsed.job_id, parsed.run_id))
    print("https://github.com/o/r/actions/runs/1", file=out)
    return 0

  monkeypatch.setattr(cli, "_run_job_log", job_log)
  code, out = _run("pre", "-l", line, "-c", line, "-s", "bash")
  assert code == pre.END_CALL, out
  assert routed == [target]
  assert out.splitlines()[-1] == "https://github.com/o/r/actions/runs/1"


def test_pr_patch_routes_to_verified_helper(
  _isolate_state: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  body = tmp_path / "pr.md"
  body.write_text("## Summary\n\nBody.\n", encoding="utf-8")
  line = f"gh api repos/o/r/pulls/42 -X PATCH -f title='New title' -F body=@{body}"
  routed: list[tuple[int, str, str]] = []

  def pr_update(parsed: object, _store: object, out: io.StringIO) -> int:
    routed.append((parsed.number, parsed.title, parsed.body_file))
    print("Updated PR #42", file=out)
    return 0

  monkeypatch.setattr(cli, "_run_pr_update", pr_update)
  code, out = _run("pre", "-l", line, "-c", line, "-s", "bash")
  assert code == pre.END_CALL, out
  assert routed == [(42, "New title", str(body))]


def test_routing_failure_blocks_original_line(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)

  def fail(*_args: object, **_kwargs: object) -> int:
    raise ValueError("helper unavailable")

  monkeypatch.setattr(cli, "_run_pr_update", fail)
  line = "gh api repos/o/r/pulls/42 -X PATCH -f title=Updated -F body=@pr.md"
  code, out = _run("pre", "-l", line, "-c", line, "-s", "bash")
  assert code == pre.BLOCK and "helper unavailable" in out

  monkeypatch.setattr(cli, "_start_detached_run", fail)
  code, out = _run("pre", "-l", "pytest -q", "-c", "pytest -q", "-s", "bash")
  assert code == pre.BLOCK and "helper unavailable" in out


@pytest.mark.parametrize(
  "line",
  (
    "curl -X PATCH https://api.github.com/repos/o/r/pulls/42 -d title=Incomplete",
    "printf ready && gh api repos/o/r/actions/jobs/123/logs",
    "gh api repos/o/r/pulls/42 -X PATCH -f title=Updated -F body=@pr.md | cat",
    "jq -n --arg title Updated --rawfile body pr.md '{}' | gh api repos/o/r/pulls/42 -X PATCH --input -",
  ),
)
def test_incomplete_or_mixed_github_routes_block(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch, line: str
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  monkeypatch.setattr(
    cli, "_run_job_log", lambda *_args: pytest.fail("unsafe job log was routed")
  )
  monkeypatch.setattr(
    cli, "_run_pr_update", lambda *_args: pytest.fail("unsafe PR edit was routed")
  )
  code, out = _run("pre", "-l", line, "-c", line, "-s", "bash")
  assert code == pre.BLOCK, (line, out)


@pytest.mark.parametrize(
  ("line", "rc", "watch"),
  (
    ("git push origin topic", "0", True),
    ("gh pr create --title Draft", "0", True),
    ("git push --dry-run origin topic", "0", False),
    ("git push -n origin topic", "0", False),
    ("printf 'git push origin topic'", "0", False),
    ("command -v git push", "0", False),
    ("git push origin topic", "1", False),
  ),
)
def test_exit_watches_checks_only_after_successful_push_or_pr_creation(
  _isolate_state: Path,
  monkeypatch: pytest.MonkeyPatch,
  line: str,
  rc: str,
  watch: bool,
) -> None:
  started: list[tuple[str, list[str]]] = []

  def start(_state: Path, name: str, command: list[str], **_kwargs: object) -> int:
    started.append((name, command))
    return 0

  monkeypatch.setattr(cli, "_start_detached_run", start)
  code, out = _run("post-exit", "--line", line, "--rc", rc)
  assert code == 0, out
  expected = [("pr-checks", ["gh", "pr", "checks", "--watch"])] if watch else []
  assert started == expected


@pytest.mark.parametrize(
  ("line", "warn"),
  (
    ('steer ack abc123 "Read the `section`"', True),
    ('steer ack abc123 "Read the \\`section\\`"', False),
    ("steer ack abc123 'Read the `section`'", False),
    ('printf "steer ack abc123 `section`"', False),
  ),
)
def test_ack_backtick_warning_only_on_executable_double_quoted_ack(
  line: str, warn: bool
) -> None:
  result = pre.run_pipeline(pre.PreContext(line=line, command=line))
  assert result.verdict == pre.CONTINUE
  assert ("Single-quote" in " ".join(result.messages)) == warn


@pytest.mark.parametrize(
  ("line", "warn"),
  (
    ("/repo/.agents/skills/arena-steering/scripts/steer read", True),
    ("python /repo/.agents/skills/arena-steering/scripts/steer read", True),
    ("env LANG=C /repo/skills/arena-steering/scripts/steer read", True),
    ("printf '/repo/skills/arena-steering/scripts/steer'", False),
    ("rg '/repo/skills/arena-steering/scripts/steer' file.txt", False),
  ),
)
def test_bare_path_warning_checks_executable_not_arguments(
  line: str, warn: bool
) -> None:
  result = pre.run_pipeline(pre.PreContext(line=line, command=line))
  assert result.verdict == pre.CONTINUE
  assert ("Use bare `steer`" in " ".join(result.messages)) == warn


def test_network_destination_and_port_warnings_remain_deferred() -> None:
  for line in ("curl https://example.test", "steer serve --port 8123"):
    result = pre.run_pipeline(pre.PreContext(line=line, command=line))
    assert result.verdict == pre.CONTINUE
    assert not any(
      "proxy" in text.lower() or "port" in text.lower() for text in result.messages
    )


@pytest.mark.parametrize(
  ("line", "elapsed", "warn"),
  (
    ("printf ok", "10", True),
    ("printf ok", "9", False),
    ("steer poll", "11", False),
    ("steer run logs verify", "11", False),
  ),
)
def test_exit_warns_on_slow_unrouted_calls(
  _isolate_state: Path, line: str, elapsed: str, warn: bool
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  code, out = _run("post-exit", "--line", line, "--rc", "0", "--elapsed", elapsed)
  assert code == 0
  assert (">= 10s" in out) == warn


def test_exit_reminds_without_acking_or_incrementing_pending_items(
  _isolate_state: Path,
) -> None:
  store, messages, _, _ = cli.open_services(_isolate_state)
  messages.send_message("Blocking note", msg_id="ab1001", blocking=True)
  messages.send_message("Quiet note", msg_id="ab1002", blocking=False)
  store.set_meta(pre.CALL_COUNT_META, "3")
  store.close()

  code, out = _run("post-exit", "--line", "printf ok", "--rc", "0")
  assert code == 0
  assert "unacked 1 note" in out
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert messages.pending_ids() == ["ab1001"]
  assert store.get_meta(pre.CALL_COUNT_META) == "3"
  store.close()


def test_exit_counts_latest_report_answer_with_notes(_isolate_state: Path) -> None:
  store, messages, _, reports = cli.open_services(_isolate_state)
  messages.send_message("Blocking note", msg_id="ab1003")
  reports.publish_report(
    "choice",
    "Choice",
    '<!-- question {"id":"pick","label":"Pick"} -->\n'
    'Pick\n- ( ) Yes <!-- option {"label":"Yes"} -->\n',
  )
  reports.submit_answer("choice", {"pick": "Yes"}, answer_id="ab1004")
  store.close()
  code, out = _run("post-exit", "--line", "printf ok", "--rc", "0")
  assert code == 0 and "1 note" in out and "1 answer" in out


def test_exit_labels_hidden_violation_separately_from_note_and_answer(
  _isolate_state: Path,
) -> None:
  store, messages, _, reports = cli.open_services(_isolate_state)
  messages.send_message(
    "Read the violation clause",
    msg_id="ab1005",
    hidden=True,
    violation_type="bash-violation",
  )
  messages.send_message("Blocking note", msg_id="ab1006")
  reports.publish_report(
    "choice",
    "Choice",
    '<!-- question {"id":"pick","label":"Pick"} -->\n'
    'Pick\n- ( ) Yes <!-- option {"label":"Yes"} -->\n',
  )
  reports.submit_answer("choice", {"pick": "Yes"}, answer_id="ab1007")
  store.close()

  code, out = _run("post-exit", "--line", "printf ok", "--rc", "0")
  assert code == 0
  assert "1 violation" in out
  assert "1 note" in out
  assert "1 answer" in out
  assert "2 notes" not in out
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert set(messages.pending_ids()) == {"ab1005", "ab1006", "ab1007"}
  violation = store.get_message("ab1005")
  assert violation is not None and violation.hidden and violation.requires_ack
  store.close()


def test_exit_reminds_about_stale_reports(_isolate_state: Path) -> None:
  store, _, _, reports = cli.open_services(_isolate_state)
  for index in range(10):
    reports.publish_report(f"report-{index}", f"Report {index}", "Body")
  stale = reports.get_report("report-0")
  stale.ack_seen = True
  stale.ack_seen_at = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
  store.save_report(stale)
  store.close()

  code, out = _run("post-exit", "--line", "printf ok", "--rc", "0")
  assert code == 0
  assert "1 stale report" in out


def test_exit_reminds_about_unpushed_commits(
  _isolate_state: Path, _git_checkout: Path, tmp_path: Path
) -> None:
  _seed(_isolate_state, "Acknowledged", acked=True)
  remote = tmp_path / "origin.git"

  def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=_git_checkout, check=True, capture_output=True)

  subprocess.run(
    ["git", "init", "--bare", "-b", "main", str(remote)],
    check=True,
    capture_output=True,
  )
  git("remote", "add", "origin", str(remote))
  git("push", "-u", "origin", "main")
  (_git_checkout / "note.md").write_text("second\n", encoding="utf-8")
  git("add", "note.md")
  git("commit", "-m", "second")
  code, out = _run("post-exit", "--line", "git commit -m second", "--rc", "0")
  assert code == 0 and "1 commit/s unpushed" in out
  git("push", "origin", "main")
  code, out = _run("post-exit", "--line", "git push origin main", "--rc", "0")
  assert code == 0 and "unpushed" not in out


def test_instruction_checkpoints_wait_fifteen_minutes_and_deduplicate(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  root = _isolate_state.parent / "checkout"
  skill = root / ".agents" / "skills" / "arena-skill" / "SKILL.md"
  skill.parent.mkdir(parents=True)
  for path in (root / "ARENA.md", root / "AGENTS.md", skill):
    path.write_text("Read the full file.\n", encoding="utf-8")
  monkeypatch.setattr(pre, "repo_root", lambda: root)
  _seed(_isolate_state, "Acknowledged", acked=True)

  code, _ = _run("pre", "-l", "printf ok", "-c", "printf ok", "-s", "bash")
  assert code == 0
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert messages.pending_ids() == []
  store.set_meta(
    "read_set_last_at", (datetime.now(UTC) - timedelta(minutes=16)).isoformat()
  )
  store.close()

  code, _ = _run("pre", "-l", "steer poll", "-c", "steer poll", "-s", "bash")
  assert code == 0
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert messages.pending_ids() == []
  store.close()

  code, _ = _run("pre", "-l", "printf ok", "-c", "printf ok", "-s", "bash")
  assert code == 0
  store, messages, _, _ = cli.open_services(_isolate_state)
  due = [msg for msg in messages.list_messages() if msg.hidden and msg.requires_ack]
  assert len(due) == 1
  assert "15min bible check" in due[0].body
  for path in (root / "ARENA.md", root / "AGENTS.md", skill):
    assert str(path) in due[0].body
  assert messages.pending_ids() == [due[0].id]
  store.close()

  _run("pre", "-l", "printf ok", "-c", "printf ok", "-s", "bash")
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert (
    len([msg for msg in messages.list_messages() if "15min bible check" in msg.body])
    == 1
  )
  store.close()

  assert _run("ack", due[0].id, "Read in full; text already in context")[0] == 0
  store, messages, _, _ = cli.open_services(_isolate_state)
  store.set_meta(
    "read_set_last_at", (datetime.now(UTC) - timedelta(minutes=16)).isoformat()
  )
  store.close()
  _run("pre", "-l", "printf ok", "-c", "printf ok", "-s", "bash")
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert (
    len([msg for msg in messages.list_messages() if "15min bible check" in msg.body])
    == 2
  )
  store.close()


def test_concurrent_instruction_ticks_only_mint_one_checkpoint(
  _isolate_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  root = _isolate_state.parent / "checkout"
  root.mkdir()
  (root / "ARENA.md").write_text("Read in full.\n", encoding="utf-8")
  monkeypatch.setattr(pre, "repo_root", lambda: root)
  _seed(_isolate_state, "Acknowledged", acked=True)
  store, _, _, _ = cli.open_services(_isolate_state)
  store.set_meta(
    "read_set_last_at", (datetime.now(UTC) - timedelta(minutes=16)).isoformat()
  )
  store.close()
  with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(
      pool.map(
        lambda _: _run("pre", "-l", "printf ok", "-c", "printf ok", "-s", "bash"),
        range(3),
      )
    )
  assert all(code == 0 for code, _ in results)
  store, messages, _, _ = cli.open_services(_isolate_state)
  assert (
    len([msg for msg in messages.list_messages() if "15min bible check" in msg.body])
    == 1
  )
  store.close()
