"""Tests for the shared change-detection step, against real Git repositories."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import changed_paths
import pytest


def git(repo: Path, *arguments: str) -> str:
  result = subprocess.run(
    ["git", *arguments],
    cwd=repo,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=True,
  )
  return result.stdout.strip()


def write(repo: Path, files: dict[str, str]) -> None:
  for name, text in files.items():
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def init_repo(tmp_path: Path) -> Path:
  """One repository at its first commit."""
  repo = tmp_path / "repo"
  repo.mkdir()
  git(repo, "init", "-q")
  git(repo, "config", "user.email", "tests@example.com")
  git(repo, "config", "user.name", "Tests")
  write(
    repo,
    {
      "gpt-plugins/plugin.json": "{}\n",
      "rules/core.md": "core\n",
      "rules/refs/generic.md": "generic\n",
      "docs/readme.md": "docs\n",
      "skills/arena-steering/scripts/runtime.py": "pass\n",
    },
  )
  git(repo, "add", "-A")
  git(repo, "commit", "-q", "-m", "chore: base")
  return repo


def base_of(repo: Path) -> str:
  return git(repo, "rev-parse", "HEAD")


def commit_change(repo: Path, name: str, text: str = "changed\n") -> None:
  write(repo, {name: text})
  git(repo, "add", "-A")
  git(repo, "commit", "-q", "-m", f"chore: change {name}")


def outputs(path: Path) -> str:
  return path.read_text(encoding="utf-8") if path.exists() else ""


def test_event_base_reads_each_event_payload(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "docs/readme.md")
  assert (
    changed_paths.event_base({"EVENT_NAME": "pull_request", "PR_BASE": base}, repo)
    == base
  )
  assert (
    changed_paths.event_base({"EVENT_NAME": "push", "PUSH_BEFORE": base}, repo) == base
  )


def test_event_base_rejects_a_missing_or_unreadable_base(tmp_path):
  repo = init_repo(tmp_path)
  for env in (
    {},
    {"EVENT_NAME": "push"},
    {"EVENT_NAME": "push", "PUSH_BEFORE": "0" * 40},
  ):
    assert changed_paths.event_base(env, repo) is None
  unknown = {"EVENT_NAME": "push", "PUSH_BEFORE": "a" * 40}
  assert changed_paths.event_base(unknown, repo) is None


def test_changed_files_limits_the_diff_to_the_paths(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "gpt-plugins/plugin.json")
  assert changed_paths.changed_files(base, ("gpt-plugins",), repo) == [
    "gpt-plugins/plugin.json"
  ]
  assert changed_paths.changed_files(base, ("docs",), repo) == []


def test_artifacts_step_reads_a_main_dispatch(tmp_path):
  repo = init_repo(tmp_path)
  out = tmp_path / "out.txt"
  env = {"EVENT_NAME": "workflow_dispatch", "EVENT_REF": "refs/heads/main"}
  assert changed_paths.step_artifacts(env, out, str(repo)) == 0
  text = outputs(out)
  assert "package=true\n" in text
  assert "rules=false\n" in text
  assert "egress" not in text and "preview" not in text


def test_artifacts_step_skips_the_refs_tree(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "rules/refs/generic.md", "generic  # touched\n")
  out = tmp_path / "out.txt"
  assert changed_paths.step_artifacts({"PUSH_BEFORE": base}, out, str(repo)) == 0
  assert "rules=false\n" in outputs(out)


def test_artifacts_step_flags_a_rule_change(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "rules/core.md", "core  # touched\n")
  out = tmp_path / "out.txt"
  assert changed_paths.step_artifacts({"PUSH_BEFORE": base}, out, str(repo)) == 0
  text = outputs(out)
  assert "rules=true\n" in text
  assert "package=false\n" in text


def test_artifacts_step_runs_both_checks_on_a_missing_base(tmp_path, capsys):
  repo = init_repo(tmp_path)
  out = tmp_path / "out.txt"
  assert changed_paths.step_artifacts({"PUSH_BEFORE": "0" * 40}, out, str(repo)) == 0
  text = outputs(out)
  assert "package=true\n" in text and "rules=true\n" in text
  assert "egress" not in text and "preview" not in text
  groups, notice = changed_paths.artifact_groups(
    {"PUSH_BEFORE": changed_paths.EMPTY_BASE}, str(repo)
  )
  assert notice and notice in capsys.readouterr().out
  assert groups == {
    name: name in {"package", "rules"} for name in changed_paths.ARTIFACT_ORDER
  }


def test_main_runs_a_step_from_the_environment(tmp_path, monkeypatch):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "docs/readme.md")
  out = tmp_path / "out.txt"
  monkeypatch.setenv("EVENT_NAME", "push")
  monkeypatch.setenv("PUSH_BEFORE", base)
  assert (
    changed_paths.main(
      ["--step", "module-tests", "--repo", str(repo), "--output", str(out)]
    )
    == 0
  )
  assert "run=false\n" in outputs(out)


def test_main_needs_an_output_file(tmp_path, monkeypatch):
  repo = init_repo(tmp_path)
  monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
  assert (
    changed_paths.main(["--step", "artifacts", "--repo", str(repo), "--output", ""])
    == 1
  )


def test_module_matrix_selects_owners_and_shared_changes():
  paths = (
    "tests/maintenance/test_check.py",
    "tests/github/workflows/test_artifacts.py",
    "tests/maintenance/workflows/test_gate_workflows.py",
    "tests/github/workflows/test_gemini_release.py",
  )
  for path in paths:
    owners = [
      name for name, tests in changed_paths.MODULE_TESTS.items() if path in tests
    ]
    selected = changed_paths.module_matrix([path])
    assert [row["name"] for row in selected] == owners
  for doc in (
    "docs/CHANGELOG.md",
    "docs/archive/CHANGELOG.md",
    "docs/archive/arena-skill/docs/CHANGELOG.md",
    "docs/userscripts/arena/CHANGELOG.md",
    "docs/workflows/gemini-release/CHANGELOG.md",
  ):
    assert not changed_paths.module_matrix([doc])
  all_names = set(changed_paths.MODULE_TESTS)
  assert "Proxies" not in all_names
  for shared in (
    "requirements.txt",
    "package-lock.json",
    "pyproject.toml",
    ".github/workflows/ci.yml",
  ):
    assert {row["name"] for row in changed_paths.module_matrix([shared])} == all_names


@pytest.mark.parametrize(
  "path",
  [
    "tests/skills/arena-steering/test_reports_ui.py",
    "tests/skills/arena-steering/test_messages_ui.py",
    "tests/skills/arena-steering/test_server_cli.py",
    "tests/skills/arena-steering/test_web_ui.py",
    "tests/skills/arena-steering/test_messages_views.py",
    "tests/skills/arena-steering/test_reports_views.py",
    "tests/skills/arena-steering/test_tasks_ui.py",
    "tests/skills/arena-steering/test_transport_ui.py",
  ],
)
def test_browser_test_runs_with_preview_module(path):
  selected = changed_paths.module_matrix([path])
  assert [row["name"] for row in selected] == ["Preview"]
  assert path in selected[0]["command"]


@pytest.mark.parametrize(
  "path",
  [
    "docs/archive/arena-skill/tests/arena-egress-proxy/test_arena_proxy.py",
    "docs/archive/arena-skill/tests/arena-preview-proxy/test_preview_proxy.py",
    "docs/archive/arena-skill/tests/test_minify.py",
    "docs/archive/arena-skill/tests/test_minify_workflow.py",
    "docs/archive/arena-skill/tests/client.test.cjs",
  ],
)
def test_archived_tests_never_enter_ci_matrix(path, tmp_path):
  repo = init_repo(tmp_path)
  commit_change(repo, path)
  changed_paths.check_module_ownership(str(repo))
  assert changed_paths.module_matrix([path]) == []
  assert path not in "\n".join(
    row["command"] for row in changed_paths.module_matrix(None)
  )


def test_demo_script_runs_with_preview_module():
  selected = changed_paths.module_matrix(["maintenance/demo-arena-steer.py"])
  assert [row["name"] for row in selected] == ["Preview"]
  assert "tests/skills/arena-steering/test_server_cli.py" in selected[0]["command"]


def test_v2_steering_source_runs_task_chain_regressions():
  selected = changed_paths.module_matrix(
    ["skills/arena-steering/scripts/arena_steering/services.py"]
  )
  assert [row["name"] for row in selected] == ["Preview"]
  assert "tests/skills/arena-steering/test_services.py" in selected[0]["command"]


def test_module_test_ownership_is_complete_and_unique():
  root = Path(changed_paths.__file__).resolve().parents[2]
  owned = [path for paths in changed_paths.MODULE_TESTS.values() for path in paths]
  discovered = {
    str(path.relative_to(root))
    for directory in ("tests", "maintenance", "skills", "github/workflows")
    if (root / directory).exists()
    for path in (root / directory).rglob("test_*.py")
    if not str(path.relative_to(root)).startswith(changed_paths.ARCHIVED_TEST_PREFIX)
  }
  assert set(owned) == discovered
  assert len(owned) == len(set(owned))


def test_module_step_routes_changes_and_missing_bases(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  path = "tests/maintenance/test_check.py"
  commit_change(repo, path)
  out = tmp_path / "modules.txt"
  assert changed_paths.step_module_tests({"PUSH_BEFORE": base}, out, str(repo)) == 0
  values = dict(line.split("=", 1) for line in outputs(out).splitlines())
  assert json.loads(values["matrix"])["include"] == changed_paths.module_matrix([path])
  out.unlink()
  assert changed_paths.step_module_tests({}, out, str(repo)) == 0
  values = dict(line.split("=", 1) for line in outputs(out).splitlines())
  assert json.loads(values["matrix"])["include"] == changed_paths.module_matrix(None)


def test_unknown_tests_fail_before_scheduling(tmp_path):
  repo = init_repo(tmp_path)
  path = "tests/maintenance/workflows/test_new_module.py"
  commit_change(repo, path)
  try:
    changed_paths.check_module_ownership(str(repo))
  except SystemExit as error:
    assert path in str(error)
  else:
    raise AssertionError("An unowned test must not be skipped.")


def test_renames_select_both_source_modules(tmp_path):
  repo = init_repo(tmp_path)
  old = "skills/nemoizer/scripts/example.py"
  new = "skills/nuu/scripts/example.py"
  commit_change(repo, old)
  base = base_of(repo)
  target = repo / new
  target.parent.mkdir(parents=True, exist_ok=True)
  (repo / old).rename(target)
  git(repo, "add", "-A")
  git(repo, "commit", "-q", "-m", "chore: move source")
  paths = changed_paths.changed_files(base, (), str(repo))
  assert {old, new} <= set(paths)
  assert changed_paths.module_matrix(paths) == changed_paths.module_matrix([old, new])


def test_node_test_ownership_is_complete_and_unique():
  root = Path(changed_paths.__file__).resolve().parents[2]
  owned = [path for paths in changed_paths.MODULE_NODE_TESTS.values() for path in paths]
  discovered = {
    str(path.relative_to(root))
    for directory in ("tests", "maintenance", "skills/refs")
    if (root / directory).exists()
    for suffix in ("*.test.cjs", "*.checks.cjs")
    for path in (root / directory).rglob(suffix)
  }
  assert set(owned) == discovered
  assert len(owned) == len(set(owned))


def test_root_nemoizer_config_selects_validation_tests():
  selected = changed_paths.module_matrix(["nemoizer.toml"])
  assert {row["name"] for row in selected} == {"Repository Prose and Validation"}


def test_surface_digest_tracks_selected_inputs_and_shared_lockfile(tmp_path):
  repo = init_repo(tmp_path)
  write(repo, {"requirements.txt": "ruff==1\n", "unrelated.txt": "one\n"})
  git(repo, "add", "-A")
  patterns = ("skills/arena-steering/*",)
  shared = ("requirements.txt",)
  initial = changed_paths.surface_digest(str(repo), patterns, shared)
  write(repo, {"unrelated.txt": "two\n"})
  git(repo, "add", "-A")
  assert changed_paths.surface_digest(str(repo), patterns, shared) == initial
  write(repo, {"requirements.txt": "ruff==2\n"})
  git(repo, "add", "-A")
  assert changed_paths.surface_digest(str(repo), patterns, shared) != initial
  write(repo, {"skills/arena-steering/scripts/runtime.py": "changed\n"})
  git(repo, "add", "-A")
  assert changed_paths.surface_digest(str(repo), patterns, shared) != initial


def test_surface_digest_ignores_commit_history(tmp_path):
  repo = init_repo(tmp_path)
  initial = changed_paths.surface_digest(str(repo), ("skills/*",), ())
  git(repo, "commit", "--allow-empty", "-q", "-m", "chore: new history")
  assert changed_paths.surface_digest(str(repo), ("skills/*",), ()) == initial


def test_pass_ledger_records_only_success_and_removes_failures(tmp_path):
  ledger = tmp_path / "cache" / "ci-ledger.json"
  changed_paths.record_surface(ledger, "ruff", "a" * 64, "commit-a", True)
  changed_paths.record_surface(ledger, "markdownlint", "b" * 64, "commit-a", True)
  changed_paths.record_surface(ledger, "ruff", "c" * 64, "commit-b", False)
  records = changed_paths.load_ledger(ledger)
  assert "ruff" not in records
  assert records["markdownlint"] == {"digest": "b" * 64, "commit": "commit-a"}
  assert not changed_paths.ledger_hit(records, "ruff", "c" * 64)
  assert changed_paths.ledger_hit(records, "markdownlint", "b" * 64)


def test_corrupt_ledger_is_a_miss(tmp_path):
  ledger = tmp_path / "ci-ledger.json"
  ledger.write_text("not json", encoding="utf-8")
  assert changed_paths.load_ledger(ledger) == {}
  changed_paths.record_surface(ledger, "ruff", "a" * 64, "commit", True)
  assert changed_paths.ledger_hit(changed_paths.load_ledger(ledger), "ruff", "a" * 64)


def test_collect_and_record_distinct_surfaces(tmp_path):
  repo = init_repo(tmp_path)
  ledger = tmp_path / "ci-ledger.json"
  output = tmp_path / "outputs"
  env = {"CI_LEDGER": str(ledger), "GITHUB_SHA": "abc"}
  assert changed_paths.step_collect(env, output, str(repo)) == 0
  values = dict(line.split("=", 1) for line in outputs(output).splitlines())
  assert values["run_ruff"] == "true"
  assert values["run_module_preview"] == "true"
  assert values["npm_needed"] == "true"
  env |= {
    "CI_SURFACE": "ruff",
    "CI_RESULT": "success",
    "CI_DIGEST": values["digest_ruff"],
  }
  assert changed_paths.step_record(env, output, str(repo)) == 0
  output.unlink()
  assert changed_paths.step_collect(env, output, str(repo)) == 0
  values = dict(line.split("=", 1) for line in outputs(output).splitlines())
  assert values["run_ruff"] == "false"
  assert values["run_module_preview"] == "true"
  output.unlink()
  assert (
    changed_paths.step_collect(
      env | {"CI_ENVIRONMENT": "new runner"}, output, str(repo)
    )
    == 0
  )
  values = dict(line.split("=", 1) for line in outputs(output).splitlines())
  assert values["run_ruff"] == "true"
  assert (
    changed_paths.step_record(env | {"CI_RESULT": "failure"}, output, str(repo)) == 0
  )
  assert not changed_paths.load_ledger(ledger)


def test_repo_check_digest_covers_userscripts_and_steering_assets(tmp_path):
  repo = init_repo(tmp_path)
  patterns = changed_paths.ci_surfaces()["repo_check"]
  before = changed_paths.surface_digest(
    str(repo), patterns, changed_paths.CI_SHARED_PATHS
  )
  write(repo, {"userscripts/arena.user.js": "changed\n"})
  git(repo, "add", "-A")
  after = changed_paths.surface_digest(
    str(repo), patterns, changed_paths.CI_SHARED_PATHS
  )
  assert after != before
  write(repo, {"skills/arena-steering/assets/app.js": "changed\n"})
  git(repo, "add", "-A")
  assert (
    changed_paths.surface_digest(str(repo), patterns, changed_paths.CI_SHARED_PATHS)
    != after
  )


def test_preview_digest_covers_browser_test_fixtures(tmp_path):
  repo = init_repo(tmp_path)
  patterns = changed_paths.ci_surfaces()["module_preview"]
  before = changed_paths.surface_digest(
    str(repo), patterns, changed_paths.CI_SHARED_PATHS
  )
  write(repo, {"tests/skills/arena-steering/fixtures/reload_isolation.py": "changed\n"})
  git(repo, "add", "-A")
  assert (
    changed_paths.surface_digest(str(repo), patterns, changed_paths.CI_SHARED_PATHS)
    != before
  )


def test_retired_proxy_tests_live_only_in_arena_archive():
  root = Path(changed_paths.__file__).resolve().parents[2]
  for proxy, filename in (
    ("arena-egress-proxy", "test_arena_proxy.py"),
    ("arena-preview-proxy", "test_preview_proxy.py"),
  ):
    archived = root / "docs/archive/arena-skill/tests" / proxy / filename
    former = root / "tests/skills" / proxy / filename
    assert archived.is_file()
    assert not former.exists()
    assert changed_paths.module_matrix([str(archived.relative_to(root))]) == []


def test_ci_uses_one_read_only_job_and_saves_attempt_scoped_ledger():
  import yaml

  root = Path(changed_paths.__file__).resolve().parents[2]
  workflow = yaml.safe_load(
    (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
  )
  triggers = workflow.get("on", workflow.get(True))
  assert set(triggers["pull_request"]["types"]) >= {
    "opened",
    "edited",
    "reopened",
    "synchronize",
  }
  assert not triggers["pull_request"].get("paths-ignore")
  assert workflow["permissions"] == {"contents": "read"}
  assert set(workflow["jobs"]) == {"check"}
  steps = workflow["jobs"]["check"]["steps"]
  runs = "\n".join(step.get("run", "") for step in steps)
  assert "changed_paths.py --step collect" in runs
  assert "changed_paths.py --step record" in runs
  assert "gate_pr.py" in runs and "--pr-title" in runs and "--version-bumps" in runs
  caches = [step for step in steps if "actions/cache/save@" in step.get("uses", "")]
  ledger = next(step for step in caches if "ci-ledger" in step["with"].get("key", ""))
  assert "github.run_attempt" in ledger["with"]["key"]


def test_ci_keeps_pr_plugin_validation_on_matching_changes():
  import yaml

  root = Path(changed_paths.__file__).resolve().parents[2]
  workflow = yaml.safe_load(
    (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
  )
  steps = workflow["jobs"]["check"]["steps"]
  selector = next(step for step in steps if step.get("id") == "plugin_changes")
  validation = next(step for step in steps if step.get("name") == "Validate PR Plugins")
  assert "github.event_name == 'pull_request'" in selector["if"]
  assert selector["env"]["PR_BASE"] == "${{ github.event.pull_request.base.sha }}"
  assert "steps.plugin_changes.outputs.package == 'true'" in validation["if"]
  for marker in (
    "check_artifacts.py",
    "--self-check",
    "--base-manifest",
    "gate_gpt_plugins.py",
  ):
    assert marker in validation["run"]
  assert "skills/nemoizer/references" in validation["run"]
  assert "actions/upload-artifact" not in str(steps)


def test_combined_tests_record_only_after_all_commands_pass(tmp_path, monkeypatch):
  from types import SimpleNamespace

  ledger = tmp_path / "ci-ledger.json"
  selected = "module_preview,module_userscripts"
  digests = {
    name: ("a" if name.endswith("preview") else "b") * 64
    for name in selected.split(",")
  }
  env = {
    "CI_LEDGER": str(ledger),
    "GITHUB_SHA": "abc",
    "CI_TEST_SURFACES": selected,
    "CI_DIGESTS": json.dumps(digests),
  }
  commands = []

  def run(command, **kwargs):
    commands.append(command)
    return SimpleNamespace(returncode=1 if command[0] == "node" else 0)

  monkeypatch.setattr(changed_paths.subprocess, "run", run)
  assert changed_paths.step_test(env, tmp_path / "out", str(tmp_path)) == 1
  assert not changed_paths.load_ledger(ledger)
  pytest_commands = [command for command in commands if "pytest" in command]
  assert len(pytest_commands) == 1
  assert any(command[:2] == ["node", "--test"] for command in commands)
  monkeypatch.setattr(
    changed_paths.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0)
  )
  assert changed_paths.step_test(env, tmp_path / "out", str(tmp_path)) == 0
  assert set(changed_paths.load_ledger(ledger)) == set(selected.split(","))


def test_ci_never_records_passes_after_dependency_install_fails():
  import yaml

  root = Path(changed_paths.__file__).resolve().parents[2]
  workflow = yaml.safe_load(
    (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
  )
  steps = workflow["jobs"]["check"]["steps"]
  by_id = {step.get("id"): step for step in steps if step.get("id")}
  assert "steps.dependencies.outcome == 'success'" in by_id["repo_check"]["if"]
  assert "steps.npm.outcome == 'success'" in by_id["repo_check"]["if"]
  assert "steps.dependencies.outcome == 'success'" in by_id["ruff"]["if"]
  assert "steps.npm.outcome == 'success'" in by_id["markdownlint"]["if"]
  tests = next(step for step in steps if "--step test" in step.get("run", ""))
  assert "steps.dependencies.outcome == 'success'" in tests["if"]
  assert "steps.npm.outcome == 'success'" in tests["if"]


def test_ci_versions_use_default_branch_for_stacked_prs_and_previous_default_head_for_pushes():
  import yaml

  root = Path(changed_paths.__file__).resolve().parents[2]
  workflow = yaml.safe_load(
    (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
  )
  steps = {step.get("name"): step for step in workflow["jobs"]["check"]["steps"]}
  default_ref = "refs/remotes/origin/${{ github.event.repository.default_branch }}"
  for title in ("Check PR Contract", "Validate PR Plugins", "Check Module Versions"):
    assert steps[title]["env"]["VERSION_BASE"] == default_ref
  contract = steps["Check PR Contract"]["run"]
  assert '--range "$PR_BASE..$PR_HEAD"' in contract
  assert '--version-base "$VERSION_BASE"' in contract
  plugins = steps["Validate PR Plugins"]["run"]
  assert 'git show "$VERSION_BASE:gpt-plugins/plugin.json"' in plugins
  assert 'git show "$PR_BASE:gpt-plugins/plugin.json"' not in plugins
  versions = steps["Check Module Versions"]["run"]
  assert 'BASE="$VERSION_BASE"' in versions
  assert 'BASE="$PUSH_BEFORE"' in versions
  assert 'BASE="$PR_BASE"' not in versions
