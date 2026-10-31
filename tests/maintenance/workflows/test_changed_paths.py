"""Tests for the shared change-detection step, against real Git repositories."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import changed_paths


def git(repo: Path, *arguments: str) -> str:
  result = subprocess.run(
    ["git", *arguments], cwd=repo, capture_output=True, text=True, check=True
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
      "maintenance/minify/minify.py": "pass\n",
      "skills/arena-skill/arena-egress-proxy/Dockerfile": "FROM scratch\n",
    },
  )
  git(repo, "add", "-A")
  git(repo, "commit", "-q", "-m", "base")
  return repo


def base_of(repo: Path) -> str:
  return git(repo, "rev-parse", "HEAD")


def commit_change(repo: Path, name: str, text: str = "changed\n") -> None:
  write(repo, {name: text})
  git(repo, "add", "-A")
  git(repo, "commit", "-q", "-m", f"change {name}")


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


def test_artifacts_step_reads_the_dispatch_inputs(tmp_path):
  repo = init_repo(tmp_path)
  out = tmp_path / "out.txt"
  env = {
    "EVENT_NAME": "workflow_dispatch",
    "EVENT_REF": "refs/heads/main",
    "EGRESS_IMAGE": "true",
  }
  assert changed_paths.step_artifacts(env, out, str(repo)) == 0
  text = outputs(out)
  assert "package=true\n" in text and "egress=true\n" in text
  assert "rules=false\n" in text and "preview=false\n" in text


def test_artifacts_step_skips_the_refs_tree(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "rules/refs/generic.md", "generic  # touched\n")
  out = tmp_path / "out.txt"
  assert changed_paths.step_artifacts({"PUSH_BEFORE": base}, out, str(repo)) == 0
  assert "rules=false\n" in outputs(out)


def test_artifacts_step_flags_a_rule_and_an_image_change(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "rules/core.md", "core  # touched\n")
  commit_change(repo, "skills/arena-skill/arena-egress-proxy/Dockerfile")
  out = tmp_path / "out.txt"
  assert changed_paths.step_artifacts({"PUSH_BEFORE": base}, out, str(repo)) == 0
  text = outputs(out)
  assert "rules=true\n" in text and "egress=true\n" in text


def test_artifacts_step_runs_both_checks_on_a_missing_base(tmp_path, capsys):
  repo = init_repo(tmp_path)
  out = tmp_path / "out.txt"
  assert changed_paths.step_artifacts({"PUSH_BEFORE": "0" * 40}, out, str(repo)) == 0
  text = outputs(out)
  assert "package=true\n" in text and "rules=true\n" in text
  assert "egress=false\n" in text and "preview=false\n" in text
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
    "tests/maintenance/measurements/test_measurements.py",
    "tests/gpt-plugins/test_release_artifact.py",
    "tests/github/workflows/test_check_workflows.py",
    "tests/github/workflows/test_gemini_release.py",
    "tests/skills/arena-skill/arena-egress-proxy/test_arena_proxy.py",
    "tests/skills/arena-skill/arena-preview-proxy/test_preview_proxy.py",
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
    "docs/arena-skill/CHANGELOG.md",
    "docs/userscripts/arena/CHANGELOG.md",
    "docs/workflows/gemini-release/CHANGELOG.md",
  ):
    assert not changed_paths.module_matrix([doc])
  all_names = set(changed_paths.MODULE_TESTS)
  for shared in (
    "requirements.txt",
    "package-lock.json",
    "pyproject.toml",
    ".github/workflows/ci.yml",
  ):
    assert {row["name"] for row in changed_paths.module_matrix([shared])} == all_names


def test_report_answer_browser_test_runs_with_preview_module():
  path = "tests/skills/arena-steering/test_report_answer_ui.py"
  selected = changed_paths.module_matrix([path])
  assert [row["name"] for row in selected] == ["Preview"]
  assert path in selected[0]["command"]


def test_module_test_ownership_is_complete_and_unique():
  root = Path(changed_paths.__file__).resolve().parents[2]
  owned = [path for paths in changed_paths.MODULE_TESTS.values() for path in paths]
  discovered = {
    str(path.relative_to(root))
    for directory in ("tests", "maintenance", "skills", "github/workflows")
    if (root / directory).exists()
    for path in (root / directory).rglob("test_*.py")
  }
  assert set(owned) == discovered
  assert len(owned) == len(set(owned))


def test_module_step_routes_changes_and_missing_bases(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  path = "tests/maintenance/measurements/test_measurements.py"
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
  git(repo, "commit", "-q", "-m", "move source")
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
