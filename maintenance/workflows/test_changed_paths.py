"""Tests for the shared change-detection step, against real Git repositories."""

from __future__ import annotations

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


def read_output(path: Path, name: str) -> str:
  """Read one step output back, in either the single-line or the heredoc form."""
  text = outputs(path)
  marker = f"{name}<<EOF\n"
  if marker in text:
    return text.split(marker, 1)[1].split("\nEOF\n", 1)[0]
  for line in text.splitlines():
    if line.startswith(f"{name}="):
      return line.split("=", 1)[1]
  raise AssertionError(f"no {name} output in {text!r}")


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
  assert changed_paths.changed_files(base, changed_paths.VERSION_PATHS, repo) == [
    "gpt-plugins/plugin.json"
  ]
  assert changed_paths.changed_files(base, ("docs",), repo) == []


def test_version_bumps_step_writes_the_base_and_the_changed_list(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "gpt-plugins/plugin.json")
  out = tmp_path / "out.txt"
  assert changed_paths.step_version_bumps({"PUSH_BEFORE": base}, out, str(repo)) == 0
  assert read_output(out, "base") == base
  assert read_output(out, "changed") == "gpt-plugins/plugin.json"


def test_version_bumps_step_writes_a_multiline_changed_list(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "gpt-plugins/plugin.json")
  commit_change(repo, "userscripts/arena.user.js", "// touched\n")
  out = tmp_path / "out.txt"
  assert changed_paths.step_version_bumps({"PUSH_BEFORE": base}, out, str(repo)) == 0
  assert read_output(out, "changed").splitlines() == [
    "gpt-plugins/plugin.json",
    "userscripts/arena.user.js",
  ]
  assert "changed<<EOF\n" in outputs(out)


def test_version_bumps_step_names_a_missing_base(tmp_path, capsys):
  repo = init_repo(tmp_path)
  out = tmp_path / "out.txt"
  assert changed_paths.step_version_bumps({"PUSH_BEFORE": ""}, out, str(repo)) == 0
  text = outputs(out)
  assert "base=missing\n" in text and "changed=\n" in text
  assert "Base commit is missing" in capsys.readouterr().out


def test_preview_tests_step_flags_a_preview_change(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "maintenance/minify/minify.py", "pass  # touched\n")
  out = tmp_path / "out.txt"
  assert changed_paths.step_preview_tests({"PUSH_BEFORE": base}, out, str(repo)) == 0
  assert "run=true\n" in outputs(out)


def test_preview_tests_step_skips_an_unrelated_change(tmp_path):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "docs/readme.md")
  out = tmp_path / "out.txt"
  assert changed_paths.step_preview_tests({"PUSH_BEFORE": base}, out, str(repo)) == 0
  assert "run=false\n" in outputs(out)


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
  assert "run the package and rules checks" in capsys.readouterr().out


def test_main_runs_a_step_from_the_environment(tmp_path, monkeypatch):
  repo = init_repo(tmp_path)
  base = base_of(repo)
  commit_change(repo, "docs/readme.md")
  out = tmp_path / "out.txt"
  monkeypatch.setenv("EVENT_NAME", "push")
  monkeypatch.setenv("PUSH_BEFORE", base)
  assert (
    changed_paths.main(
      ["--step", "preview-tests", "--repo", str(repo), "--output", str(out)]
    )
    == 0
  )
  assert "run=false\n" in outputs(out)


def test_main_needs_an_output_file(tmp_path, monkeypatch):
  repo = init_repo(tmp_path)
  monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
  assert (
    changed_paths.main(["--step", "preview-tests", "--repo", str(repo), "--output", ""])
    == 1
  )
