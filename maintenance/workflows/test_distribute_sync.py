"""Run the distribution action against local Git repositories and controlled push failures."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ACTION = (
  Path(__file__).resolve().parents[2] / ".github/actions/distribute-sync/action.yml"
)
GIT = shutil.which("git")
SUBJECT = "chore: clankers sync"
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
OWNER_DATA = "Retain unrelated target data."
ERROR_ANNOTATION = "::error::"
NOTICE_HEAD = (
  "remote: GitHub found 3 vulnerabilities on example/target's default branch"
  " (1 high, 1 moderate, 1 low). To find out more, visit:"
)
NOTICE_LINK = "remote:      https://github.com/example/target/security/dependabot"
PUSH_DIAGNOSTIC = "remote: retained push diagnostic"
WRAPPER = r"""
import json
import os
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
mode = os.environ['SYNC_MODE']
if args[0] == 'clone' and mode == 'clone_failure':
  sys.exit(7)
if args[0] == 'push':
  if mode.startswith('advisory'):
    if mode != 'advisory_orphan':
      print(os.environ['PUSH_NOTICE_HEAD'], file=sys.stderr)
    print(os.environ['PUSH_NOTICE_LINK'], file=sys.stderr)
    print(os.environ['PUSH_DIAGNOSTIC'], file=sys.stderr)
    if mode == 'advisory_failure':
      sys.exit(7)
  with open(os.environ['PUSH_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\n')
  force = any(arg.startswith('--force') for arg in args)
  if mode == 'race' and not Path(os.environ['RACE_MARK']).exists():
    subprocess.run([os.environ['REAL_GIT'], '-C', os.environ['SEED'],
                    'push', '--quiet', 'origin', 'HEAD:refs/heads/main'], check=True)
    Path(os.environ['RACE_MARK']).touch()
  if mode == 'push_failure' or (mode == 'protected' and force):
    sys.exit(7)
  if mode == 'false_success':
    sys.exit(0)
os.execv(os.environ['REAL_GIT'], [os.environ['REAL_GIT'], *args])
"""


def git(repo, *arguments):
  return subprocess.run(
    [GIT, *arguments], cwd=repo, capture_output=True, text=True, check=True
  ).stdout.strip()


def commit(repo, message, **identity):
  env = (
    os.environ
    | {
      "GIT_AUTHOR_NAME": BOT_NAME,
      "GIT_AUTHOR_EMAIL": BOT_EMAIL,
      "GIT_COMMITTER_NAME": BOT_NAME,
      "GIT_COMMITTER_EMAIL": BOT_EMAIL,
    }
    | identity
  )
  git(repo, "add", "-A")
  subprocess.run(
    [GIT, "commit", "--quiet", "--allow-empty", "-m", message],
    cwd=repo,
    env=env,
    capture_output=True,
    check=True,
  )


def fixture(tmp_path, scenario):
  remote = tmp_path / "remote.git"
  remote.mkdir()
  git(remote, "init", "--quiet", "--bare", "--initial-branch=main")
  seed = tmp_path / "seed"
  seed.mkdir()
  git(seed, "init", "--quiet", "--initial-branch=main")
  (seed / "ARENA.md").write_text("old\n")
  (seed / "owner.txt").write_text(OWNER_DATA)
  commit(seed, SUBJECT if scenario == "root" else "base")
  if scenario == "merge":
    git(seed, "checkout", "--quiet", "-b", "side")
    (seed / "side.txt").write_text("side\n")
    commit(seed, "side")
    git(seed, "checkout", "--quiet", "main")
    (seed / "main.txt").write_text("main\n")
    commit(seed, "main")
    env = os.environ | {
      "GIT_AUTHOR_NAME": BOT_NAME,
      "GIT_AUTHOR_EMAIL": BOT_EMAIL,
      "GIT_COMMITTER_NAME": BOT_NAME,
      "GIT_COMMITTER_EMAIL": BOT_EMAIL,
    }
    subprocess.run(
      [GIT, "merge", "--quiet", "--no-ff", "side", "-m", SUBJECT],
      cwd=seed,
      env=env,
      capture_output=True,
      check=True,
    )
  elif scenario != "root":
    identity = {}
    for field in ("AUTHOR_NAME", "AUTHOR_EMAIL", "COMMITTER_NAME", "COMMITTER_EMAIL"):
      if scenario == field.lower():
        identity["GIT_" + field] = (
          "Human" if field.endswith("NAME") else "human@example.test"
        )
    commit(seed, SUBJECT + " extra" if scenario == "subject" else SUBJECT, **identity)
  git(seed, "remote", "add", "origin", remote.as_uri())
  git(seed, "push", "--quiet", "origin", "HEAD:refs/heads/main")
  before = git(remote, "rev-parse", "refs/heads/main")
  parent = None if scenario in {"root", "merge"} else git(seed, "rev-parse", "HEAD^")
  if scenario == "race":
    (seed / "human.txt").write_text("Concurrent target change.\n")
    commit(seed, "human change", GIT_AUTHOR_NAME="Human", GIT_COMMITTER_NAME="Human")
  return remote, seed, before, parent


def run_action(tmp_path, remote, seed, scenario, *, validate_only=False, payload=None):
  workspace = tmp_path / "source"
  workspace.mkdir()
  (workspace / "rule.md").write_text("old\n" if scenario == "unchanged" else "new\n")
  if payload:
    for skill in payload.get("SKILLS", "").split():
      folder = workspace / "skills" / skill
      folder.mkdir(parents=True)
      (folder / "SKILL.md").write_text(skill + "\n")
    for name in payload.get("FILES", "").split():
      path = workspace / "github/workflows" / name
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(name + "\n")
    git(workspace, "init", "--quiet", "--initial-branch=main")
    git(workspace, "add", "-A")
  home = tmp_path / "home"
  home.mkdir()
  binaries = tmp_path / "bin"
  binaries.mkdir()
  wrapper = binaries / "git"
  wrapper.write_text(f"#!{sys.executable}\n" + WRAPPER)
  wrapper.chmod(0o755)
  env = os.environ | {
    "HOME": str(home),
    "XDG_CONFIG_HOME": str(home / "config"),
    "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": f"url.{remote.as_uri()}.insteadOf",
    "GIT_CONFIG_VALUE_0": "https://github.com/example/target.git",
    "GIT_ALLOW_PROTOCOL": "file",
    "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
    "REAL_GIT": GIT,
    "SYNC_MODE": scenario,
    "PUSH_NOTICE_HEAD": NOTICE_HEAD,
    "PUSH_NOTICE_LINK": NOTICE_LINK,
    "PUSH_DIAGNOSTIC": PUSH_DIAGNOSTIC,
    "PUSH_LOG": str(tmp_path / "pushes.jsonl"),
    "RACE_MARK": str(tmp_path / "race.mark"),
    "SEED": str(seed),
    "GITHUB_WORKSPACE": str(workspace),
    "CLANKERS_DIST_PAT": "" if validate_only else "unused-test-token",
    "VALIDATE_ONLY": "true" if validate_only else "false",
    "GITHUB_ACTION_PATH": str(ACTION.parent),
    "REPOS": "example/target",
    "REPOS_FALLBACK": "",
    "RULE_SRC": "" if scenario == "clone_failure" else "rule.md",
    "RULE_DEST": "ARENA.md",
    "SKILLS": "",
    "SKILL_ROOT": "skills",
    "SKILL_DEST_ROOT": ".agents/skills",
    "LEGACY": "",
    "FILES": "",
    "SRC_ROOT": "github/workflows",
    "DEST_ROOT": ".github/workflows",
  }
  env.update(payload or {})
  for name in (
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
  ):
    env.pop(name, None)
  script = yaml.safe_load(ACTION.read_text())["runs"]["steps"][0]["run"]
  result = subprocess.run(
    ["bash", "-c", script],
    cwd=workspace,
    env=env,
    capture_output=True,
    text=True,
    check=False,
    timeout=30,
  )
  log = tmp_path / "pushes.jsonl"
  pushes = (
    [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
  )
  return result, pushes


@pytest.mark.parametrize(
  "scenario",
  [
    "bot",
    "author_name",
    "author_email",
    "committer_name",
    "committer_email",
    "subject",
    "root",
    "merge",
    "protected",
    "race",
    "push_failure",
    "clone_failure",
    "false_success",
    "unchanged",
  ],
)
def test_distribution_preserves_history_and_reports_only_remote_success(
  tmp_path, scenario
):
  remote, seed, before, parent = fixture(tmp_path, scenario)
  result, pushes = run_action(tmp_path, remote, seed, scenario)
  after = git(remote, "rev-parse", "refs/heads/main")
  force = [arg for push in pushes for arg in push if arg.startswith("--force")]
  assert git(remote, "show", f"{after}:owner.txt") == OWNER_DATA
  if scenario in {"race", "push_failure", "clone_failure", "false_success"}:
    assert result.returncode != 0, result.stdout + result.stderr
    assert ERROR_ANNOTATION in result.stdout
    assert after == (git(seed, "rev-parse", "HEAD") if scenario == "race" else before)
  else:
    assert result.returncode == 0, result.stdout + result.stderr
    if scenario == "unchanged":
      assert after == before
      assert not pushes
    else:
      assert git(remote, "show", f"{after}:ARENA.md") == "new"
      assert git(remote, "rev-parse", f"{after}^") == (
        parent if scenario == "bot" else before
      )
  if scenario in {"bot", "protected", "race"}:
    assert force == [f"--force-with-lease=refs/heads/main:{before}"]
  elif scenario not in {"push_failure", "false_success"}:
    assert not force
  if scenario == "protected":
    assert not any(arg.startswith("--force") for arg in pushes[-1])


def test_matching_domain_payloads_share_one_push(tmp_path):
  remote, seed, before, _ = fixture(tmp_path, "bot")
  payload = {
    "SKILLS": "arena-skill nemo-ui-ux nemoizer",
    "FILES": "gemini-release.yml gemini_release.py",
  }
  result, pushes = run_action(tmp_path, remote, seed, "bot", payload=payload)
  assert result.returncode == 0, result.stderr
  assert len(pushes) == 1
  after = git(remote, "rev-parse", "refs/heads/main")
  assert after != before
  source = tmp_path / "source"
  for skill in payload["SKILLS"].split():
    assert (
      git(remote, "show", f"{after}:.agents/skills/{skill}/SKILL.md")
      == (source / "skills" / skill / "SKILL.md").read_text().strip()
    )
  for name in payload["FILES"].split():
    assert (
      git(remote, "show", f"{after}:.github/workflows/{name}")
      == (source / "github/workflows" / name).read_text().strip()
    )
  assert git(remote, "show", f"{after}:owner.txt") == OWNER_DATA


def test_distribution_domain_validation_is_read_only(tmp_path):
  remote, seed, before, _ = fixture(tmp_path, "bot")
  result, pushes = run_action(tmp_path, remote, seed, "bot", validate_only=True)
  assert result.returncode == 0, result.stderr
  assert not pushes
  assert git(remote, "rev-parse", "refs/heads/main") == before
  assert not (tmp_path / "home/gitconfig").exists()


@pytest.mark.parametrize(
  "scenario", ["advisory", "advisory_failure", "advisory_orphan"]
)
def test_remote_notice_filter_keeps_errors_and_exit_status(tmp_path, scenario):
  remote, seed, before, _ = fixture(tmp_path, "bot")
  result, _ = run_action(tmp_path, remote, seed, scenario)
  assert NOTICE_HEAD not in result.stderr
  assert (NOTICE_LINK in result.stderr) == (scenario == "advisory_orphan")
  assert PUSH_DIAGNOSTIC in result.stderr
  assert bool(result.returncode) == (scenario == "advisory_failure")
  after = git(remote, "rev-parse", "refs/heads/main")
  assert (after == before) == (scenario == "advisory_failure")
