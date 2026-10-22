"""Resolve bases and changed paths for artifact and module test jobs."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from fnmatch import fnmatch
from pathlib import Path

EMPTY_BASE = "0" * 40
ARTIFACTS = ".github/workflows/artifacts.yml"

# One rule per artifact path family: the package archive, the rules gist, and the two
# proxy images. The rules family skips `rules/refs/`, which no target repository sees.
ARTIFACT_RULES = (
  ("package", ("gpt-plugins/*", "maintenance/gpt_plugins/*", ARTIFACTS)),
  (
    "rules",
    (
      "rules/*",
      "maintenance/publish/publish.py",
      "maintenance/publish/test_publish.py",
      ARTIFACTS,
    ),
  ),
  ("egress", ("skills/arena-skill/arena-egress-proxy/*",)),
  ("preview", ("skills/arena-skill/arena-preview-proxy/*",)),
)
ARTIFACT_ORDER = ("package", "rules", "egress", "preview")


def write_output(output: Path, name: str, value: str) -> None:
  """Append one step output in the form GitHub reads. A multiline value takes a heredoc."""
  if "\n" in value:
    text = f"{name}<<EOF\n{value}\nEOF\n"
  else:
    text = f"{name}={value}\n"
  with output.open("a", encoding="utf-8") as handle:
    handle.write(text)


def git(arguments: Sequence[str], repo: str = ".") -> subprocess.CompletedProcess:
  """Run one git command without raising, so a missing ref stays a normal answer."""
  return subprocess.run(
    ["git", *arguments], cwd=repo, capture_output=True, text=True, check=False
  )


def event_base(env: Mapping[str, str], repo: str = ".") -> str | None:
  """Return the event's base commit, or None when the payload holds no readable one."""
  if env.get("EVENT_NAME") == "pull_request":
    base = env.get("PR_BASE", "")
  else:
    base = env.get("PUSH_BEFORE", "")
  base = (base or "").strip()
  if not base or base == EMPTY_BASE:
    return None
  if git(["cat-file", "-e", f"{base}^{{commit}}"], repo).returncode:
    return None
  return base


def changed_files(base: str, paths: Sequence[str], repo: str = ".") -> list[str]:
  """Return the paths this tree changed against base, limited to paths when given."""
  arguments = ["diff", "--no-renames", "--name-only", base, "HEAD"]
  if paths:
    arguments += ["--", *paths]
  result = git(arguments, repo)
  if result.returncode:
    raise SystemExit(f"git diff failed: {result.stderr.strip()}")
  return [line for line in result.stdout.splitlines() if line]


def artifact_groups(
  env: Mapping[str, str], repo: str = "."
) -> tuple[dict[str, bool], str]:
  """Return the four path-group flags for the artifact jobs, with one note line."""
  groups = {name: False for name in ARTIFACT_ORDER}
  if env.get("EVENT_NAME") == "workflow_dispatch":
    if env.get("EVENT_REF") == "refs/heads/main":
      groups["package"] = True
    # An image publishes on its own input, so a dispatch that repackages the
    # plugins never rebuilds a proxy image.
    groups["egress"] = env.get("EGRESS_IMAGE") == "true"
    groups["preview"] = env.get("PREVIEW_IMAGE") == "true"
    return groups, ""
  base = event_base(env, repo)
  if base is None:
    # A missing base runs both checks instead of skipping silently. An image
    # publish stays out of it: it writes a registry tag the fallback cannot justify.
    groups["package"] = True
    groups["rules"] = True
    return groups, "Base commit is missing; run the package and rules checks."
  for path in changed_files(base, (), repo):
    # The refs tree is the baseline for the rule files, so it never publishes them.
    if fnmatch(path, "rules/refs/*"):
      continue
    for name, patterns in ARTIFACT_RULES:
      if any(fnmatch(path, pattern) for pattern in patterns):
        groups[name] = True
  return groups, ""


def step_artifacts(env: Mapping[str, str], output: Path, repo: str = ".") -> int:
  """Report which artifact path groups changed, so their jobs may run."""
  groups, note = artifact_groups(env, repo)
  if note:
    print(note)
  for name in ARTIFACT_ORDER:
    write_output(output, name, "true" if groups[name] else "false")
  print(" ".join(f"{name}={str(groups[name]).lower()}" for name in ARTIFACT_ORDER))
  return 0


MODULE_TESTS = {
  "Preview": (
    "skills/refs/arena-skill/scripts/test_preview.py",
    "skills/refs/arena-skill/scripts/test_questionnaire.py",
    "maintenance/workflows/test_preview_gate.py",
  ),
  "Nemoizer": ("skills/refs/nemoizer/scripts/test_nemoize.py",),
  "UI/UX": (
    "skills/refs/nemo-ui-ux/scripts/test_uiux.py",
    "maintenance/test_nemo_ui_ux.py",
  ),
  "Userscripts": (),
  "GPT Plugins": (
    "maintenance/gpt_plugins/test_individual_assets.py",
    "maintenance/gpt_plugins/test_release_artifact.py",
  ),
  "Gemini Release": ("github/workflows/test_gemini_release.py",),
  "Measurements": ("maintenance/measurements/test_measurements.py",),
  "Minifier": ("maintenance/minify/test_minify.py",),
  "PR Checks": (
    "maintenance/pr/test_check_pr.py",
    "maintenance/pr/test_commit_msg.py",
  ),
  "Rules Publishing": ("maintenance/publish/test_publish.py",),
  "Workflow and Distribution": (
    "maintenance/workflows/test_changed_paths.py",
    "maintenance/workflows/test_check_artifacts.py",
    "maintenance/workflows/test_check_workflows.py",
    "maintenance/workflows/test_distribute_sync.py",
  ),
  "Proxies": (
    "maintenance/workflows/test_arena_proxy.py",
    "maintenance/workflows/test_preview_proxy.py",
  ),
  "Repository Prose and Validation": (
    "maintenance/test_lint_prose.py",
    "maintenance/workflows/test_check.py",
  ),
}
ARENA_SKILL_PATHS = (
  "skills/refs/arena-skill",
  "skills/arena-skill",
  ".agents/skills/arena-skill",
)
ARENA_RUNTIME_PATHS = tuple(
  f"{root}/{directory}/*"
  for root in ARENA_SKILL_PATHS
  for directory in ("scripts", "assets", "references")
)
MODULE_PATHS = {
  "Preview": ARENA_RUNTIME_PATHS,
  "Nemoizer": ("skills/*nemoizer/*", ".agents/skills/nemoizer/*"),
  "UI/UX": ("skills/*nemo-ui-ux/*", ".agents/skills/nemo-ui-ux/*"),
  "Userscripts": ("userscripts/*", "maintenance/workflows/userscripts*"),
  "GPT Plugins": (
    "gpt-plugins/*",
    "maintenance/gpt_plugins/*",
    ".github/workflows/artifacts.yml",
  ),
  "Gemini Release": ("github/workflows/*",),
  "Measurements": ("maintenance/measurements/*",),
  "Minifier": (*ARENA_RUNTIME_PATHS, "maintenance/minify/*"),
  "PR Checks": ("maintenance/pr/*",),
  "Rules Publishing": ("maintenance/publish/*", "rules/*"),
  "Workflow and Distribution": (
    ".github/workflows/*",
    ".github/actions/distribute-sync/*",
    "maintenance/workflows/check_artifacts.py",
    "maintenance/workflows/gate_workflows.py",
  ),
  "Proxies": tuple(f"{root}/arena-*-proxy/*" for root in ARENA_SKILL_PATHS),
  "Repository Prose and Validation": (
    "maintenance/check.py",
    "maintenance/lint_prose.py",
    "maintenance/extract_prose.py",
    "ruff.toml",
    ".markdownlint*",
    "README.md",
    "rules/*",
    "skills/*/SKILL.md",
  ),
}
MODULE_NODE_TESTS = {
  "Preview": ("skills/refs/arena-skill/scripts/client.test.cjs",),
  "Userscripts": (
    "maintenance/workflows/userscripts.checks.cjs",
    "maintenance/workflows/userscripts.test.cjs",
  ),
}
MODULE_COMMANDS = {
  "Userscripts": ("node userscripts/arena.user.js", "node userscripts/chatgpt.user.js"),
  "PR Checks": ("python maintenance/pr/test_commit_msg.py",),
}
SHARED_TEST_PATHS = (
  "requirements.txt",
  "pytest.ini",
  "package.json",
  "package-lock.json",
  ".github/workflows/ci.yml",
  ".github/actions/prepare/*",
  "maintenance/workflows/changed_paths.py",
)


def module_matrix(files: Sequence[str] | None) -> list[dict[str, str]]:
  """Select test owners. Shared inputs and a missing base select all groups."""
  all_groups = files is None or any(
    fnmatch(path, pattern) for path in files for pattern in SHARED_TEST_PATHS
  )
  rows = []
  for name, tests in MODULE_TESTS.items():
    patterns = (*tests, *MODULE_NODE_TESTS.get(name, ()), *MODULE_PATHS[name])
    if not all_groups and not any(
      fnmatch(path, pattern) for path in files for pattern in patterns
    ):
      continue
    commands = ["python -m pytest -q " + shlex.join(tests)] if tests else []
    if node_tests := MODULE_NODE_TESTS.get(name):
      arguments = ["node", "--test"]
      if name == "Preview":
        arguments += ["--test-reporter=dot", "--test-concurrency=4"]
      commands.append(shlex.join([*arguments, *node_tests]))
    commands.extend(MODULE_COMMANDS.get(name, ()))
    rows.append({"name": name, "command": "\n".join(commands)})
  return rows


def check_module_ownership(repo: str) -> None:
  """Fail before scheduling if a tracked test has no unique owner."""
  result = git(["ls-files", "-z"], repo)
  if result.returncode:
    raise SystemExit(f"git ls-files failed: {result.stderr.strip()}")
  owned = [path for tests in MODULE_TESTS.values() for path in tests]
  owned += [path for tests in MODULE_NODE_TESTS.values() for path in tests]
  discovered = {
    path
    for path in result.stdout.split("\0")
    if path
    and (
      (Path(path).name.startswith("test_") and path.endswith(".py"))
      or path.endswith((".test.cjs", ".checks.cjs"))
    )
  }
  if missing := discovered - set(owned):
    raise SystemExit("Tests need a module owner: " + ", ".join(sorted(missing)))
  if len(owned) != len(set(owned)):
    raise SystemExit("Each test must have one module owner.")


def step_module_tests(env: Mapping[str, str], output: Path, repo: str = ".") -> int:
  """Write the selected matrix before GitHub schedules its runtime jobs."""
  check_module_ownership(repo)
  base = event_base(env, repo)
  files = changed_files(base, (), repo) if base is not None else None
  rows = module_matrix(files)
  write_output(output, "run", str(bool(rows)).lower())
  write_output(output, "matrix", json.dumps({"include": rows}, separators=(",", ":")))
  print("Selected test groups: " + ", ".join(row["name"] for row in rows))
  return 0


STEPS = {
  "module-tests": step_module_tests,
  "artifacts": step_artifacts,
}


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--step", required=True, choices=sorted(STEPS))
  parser.add_argument("--repo", default=".")
  parser.add_argument("--output", default=os.environ.get("GITHUB_OUTPUT", ""))
  arguments = parser.parse_args(argv)
  if not arguments.output:
    print("GITHUB_OUTPUT is not set, so a step output has nowhere to go.")
    return 1
  return STEPS[arguments.step](os.environ, Path(arguments.output), arguments.repo)


if __name__ == "__main__":
  raise SystemExit(main())
