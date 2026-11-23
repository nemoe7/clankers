"""Resolve bases and changed paths for artifact and module test jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from fnmatch import fnmatch
from functools import cache
from pathlib import Path

EMPTY_BASE = "0" * 40
ARTIFACTS = ".github/workflows/artifacts.yml"

# One rule per artifact path family: the package archive and the rules gist.
# The rules family skips `rules/refs/`, which no target repo sees.
ARTIFACT_RULES = (
  (
    "package",
    (
      "gpt-plugins/*",
      "maintenance/gpt_plugins/*",
      "skills/nemoizer/*",
      "skills/refs/nemoizer/*",
      ARTIFACTS,
    ),
  ),
  (
    "rules",
    (
      "rules/*",
      "maintenance/publish/publish.py",
      "tests/maintenance/publish/test_publish.py",
      ARTIFACTS,
    ),
  ),
)
ARTIFACT_ORDER = ("package", "rules")


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
    ["git", *arguments],
    cwd=repo,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )


def surface_digest(repo: str, patterns: Sequence[str], shared: Sequence[str]) -> str:
  """Hash tracked index entries for a surface without consulting commit history."""
  paths = (*patterns, *shared)
  if not paths:
    raise ValueError("A digest surface needs explicit paths")
  result = subprocess.run(
    ["git", "ls-files", "-s", "-z", "--", *paths],
    cwd=repo,
    capture_output=True,
    check=True,
  )
  return hashlib.sha256(result.stdout).hexdigest()


def load_ledger(path: Path) -> dict[str, dict[str, str]]:
  """Treat missing, incompatible, or malformed cached ledgers as misses."""
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, ValueError):
    return {}
  if not isinstance(data, dict) or data.get("version") != 1:
    return {}
  entries = data.get("surfaces")
  if not isinstance(entries, dict):
    return {}
  return {
    name: entry
    for name, entry in entries.items()
    if isinstance(name, str)
    and isinstance(entry, dict)
    and isinstance(entry.get("digest"), str)
    and re.fullmatch(r"[0-9a-f]{64}", entry["digest"])
    and isinstance(entry.get("commit"), str)
    and entry["commit"]
  }


def ledger_hit(entries: Mapping[str, dict[str, str]], name: str, digest: str) -> bool:
  return entries.get(name, {}).get("digest") == digest


def record_surface(
  path: Path, name: str, digest: str, commit: str, passed: bool
) -> None:
  """Save a pass atomically, or remove the old entry after a failure."""
  if not name or not re.fullmatch(r"[0-9a-f]{64}", digest) or not commit:
    raise ValueError("A surface, SHA-256 digest, and commit are required")
  entries = load_ledger(path)
  if passed:
    entries[name] = {"digest": digest, "commit": commit}
  else:
    entries.pop(name, None)
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = None
  try:
    with tempfile.NamedTemporaryFile(
      "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
      temporary = Path(handle.name)
      json.dump({"version": 1, "surfaces": entries}, handle, sort_keys=True)
      handle.write("\n")
    temporary.replace(path)
  finally:
    if temporary is not None:
      temporary.unlink(missing_ok=True)


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
  """Return the two path-group flags for the artifact jobs, with one note line."""
  groups = {name: False for name in ARTIFACT_ORDER}
  if env.get("EVENT_NAME") == "workflow_dispatch":
    if env.get("EVENT_REF") == "refs/heads/main":
      groups["package"] = True
    return groups, ""
  base = event_base(env, repo)
  if base is None:
    # A missing base runs both checks instead of skipping silently.
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


# Each module owns a test directory tree, so a new test file needs no registration.
MODULE_TEST_DIRS = {
  "Preview": ("tests/skills/arena-steering/",),
  "nemoize": ("tests/skills/nemoizer/",),
  "UI/UX": ("tests/skills/nuu/",),
  "Userscripts": ("tests/userscripts/",),
  "GPT Plugins": ("tests/maintenance/gpt_plugins/",),
  "Gemini Release": ("tests/github/workflows/",),
  "PR Checks": ("tests/maintenance/pr/",),
  "Rules Publishing": ("tests/maintenance/publish/",),
  "Workflow and Distribution": ("tests/maintenance/workflows/",),
  "Repository Prose and Validation": ("tests/maintenance/checks/",),
}
# Archived tests remain available for historical reference but are not CI owners.
ARCHIVED_TEST_PREFIX = "docs/archive/"
MODULE_PATHS = {
  "Preview": (
    "skills/arena-steering/*",
    "maintenance/demo-arena-steer.py",
  ),
  "nemoize": (
    "skills/*nemoizer/*",
    ".agents/skills/nemoizer/*",
  ),
  "UI/UX": ("skills/*nuu/*", ".agents/skills/nuu/*"),
  "Userscripts": ("userscripts/*",),
  "GPT Plugins": (
    "gpt-plugins/*",
    "maintenance/gpt_plugins/*",
    ".github/workflows/artifacts.yml",
  ),
  "Gemini Release": ("github/workflows/*",),
  "PR Checks": ("maintenance/pr/*",),
  "Rules Publishing": (
    "maintenance/publish/*",
    "rules/*",
  ),
  "Workflow and Distribution": (
    ".github/workflows/*",
    ".github/actions/distribute-sync/*",
    "maintenance/workflows/check_artifacts.py",
    "maintenance/workflows/codeql_filter.py",
    "maintenance/workflows/gate_workflows.py",
  ),
  "Repository Prose and Validation": (
    "maintenance/check.py",
    "maintenance/checks/*",
    "nemoizer.toml",
    "pyproject.toml",
    ".markdownlint*",
    "README.md",
    "rules/*",
    "skills/*/SKILL.md",
  ),
}
MODULE_NODE_TESTS = {
  "Userscripts": (
    "tests/userscripts/arena.test.cjs",
    "tests/userscripts/chatgpt.test.cjs",
  ),
}
MODULE_COMMANDS = {
  "Userscripts": ("node userscripts/arena.user.js", "node userscripts/chatgpt.user.js"),
}


def test_file_name(path: str) -> bool:
  """True for tracked files CI treats as module tests."""
  return (
    Path(path).name.startswith("test_")
    and path.endswith(".py")
    or path.endswith((".test.cjs", ".checks.cjs"))
  )


@cache
def derived_test_files(repo: str = ".") -> dict[str, tuple[str, ...]]:
  """Group tracked test files by their owning module directory."""
  result = git(["ls-files", "-z"], repo)
  if result.returncode:
    raise SystemExit(f"git ls-files failed: {result.stderr.strip()}")
  grouped: dict[str, list[str]] = {name: [] for name in MODULE_TEST_DIRS}
  for path in result.stdout.split("\0"):
    if not path or path.startswith(ARCHIVED_TEST_PREFIX) or not test_file_name(path):
      continue
    owners = [
      name
      for name, roots in MODULE_TEST_DIRS.items()
      if any(path.startswith(root) for root in roots)
    ]
    if len(owners) > 1:
      raise SystemExit("Each test must have one module owner.")
    if owners:
      grouped[owners[0]].append(path)
  return {name: tuple(sorted(paths)) for name, paths in grouped.items()}


def derived_pytest_files(repo: str = ".") -> dict[str, tuple[str, ...]]:
  """Keep only Python test files, since pytest cannot collect node test files."""
  return {
    name: tuple(path for path in paths if path.endswith(".py"))
    for name, paths in derived_test_files(repo).items()
  }


SHARED_TEST_PATHS = (
  "requirements.txt",
  "pyproject.toml",
  "package.json",
  "package-lock.json",
  ".github/workflows/ci.yml",
  ".github/actions/prepare/*",
  "maintenance/workflows/changed_paths.py",
)


# Gate code, dependencies, and runner setup invalidate every cached result.
CI_SHARED_PATHS = (
  *SHARED_TEST_PATHS,
  "tests/conftest.py",
  "tests/*/conftest.py",
)


def surface_key(name: str) -> str:
  return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def ci_surfaces() -> dict[str, tuple[str, ...]]:
  surfaces = {
    "ruff": ("*.py", "*.pyi", "*.ipynb", "pyproject.toml", "ruff.toml", ".ruff.toml"),
    "markdownlint": ("*.md", ".markdownlint*", "package.json", "package-lock.json"),
    # The repo gate scans all text, validates paths, and checks parity.
    "repo_check": (".",),
  }
  for name, roots in MODULE_TEST_DIRS.items():
    extra = {
      "GPT Plugins": ("skills/nemoizer/*", "skills/refs/nemoizer/*"),
      "Repository Prose and Validation": (".",),
    }.get(name, ())
    surfaces["module_" + surface_key(name)] = (
      *MODULE_PATHS[name],
      *roots,
      *MODULE_NODE_TESTS.get(name, ()),
      *extra,
    )
  return surfaces


def step_collect(env: Mapping[str, str], output: Path, repo: str = ".") -> int:
  check_module_ownership(repo)
  path = Path(env.get("CI_LEDGER", ".cache/ci-ledger.json"))
  entries = load_ledger(path)
  if env.get("GITHUB_ACTIONS") == "true" and not env.get("CI_ENVIRONMENT"):
    raise ValueError("CI_ENVIRONMENT is required on GitHub Actions")
  misses = {}
  digests = {}
  for name, patterns in ci_surfaces().items():
    inputs = surface_digest(repo, patterns, CI_SHARED_PATHS)
    fingerprint = env.get("CI_ENVIRONMENT", "")
    digest = hashlib.sha256(f"{inputs}\0{fingerprint}".encode()).hexdigest()
    misses[name] = not ledger_hit(entries, name, digest)
    digests[name] = digest
    write_output(output, "digest_" + name, digest)
    write_output(output, "run_" + name, str(misses[name]).lower())
  test_surfaces = [
    name for name in misses if name.startswith("module_") and misses[name]
  ]
  write_output(output, "test_surfaces", ",".join(test_surfaces))
  write_output(output, "digests", json.dumps(digests, separators=(",", ":")))
  # Test suites can invoke the bundled Node parser or tokenizer.
  npm_needed = bool(test_surfaces) or misses["markdownlint"] or misses["repo_check"]
  write_output(output, "npm_needed", str(npm_needed).lower())
  return 0


def step_record(env: Mapping[str, str], output: Path, repo: str = ".") -> int:
  name = env.get("CI_SURFACE", "")
  status = env.get("CI_RESULT", "")
  if name not in ci_surfaces() or status not in ("success", "failure", "skipped"):
    raise ValueError("Expected a known surface and step outcome")
  if status != "skipped":
    record_surface(
      Path(env.get("CI_LEDGER", ".cache/ci-ledger.json")),
      name,
      env.get("CI_DIGEST", ""),
      env.get("GITHUB_SHA", ""),
      status == "success",
    )
  return 0


def step_test(env: Mapping[str, str], output: Path, repo: str = ".") -> int:
  """Run selected suites together and record them only when the whole union passes."""
  selected = env.get("CI_TEST_SURFACES", "").split(",")
  selected = [name for name in selected if name]
  names = {"module_" + surface_key(name): name for name in MODULE_TEST_DIRS}
  if len(selected) != len(set(selected)) or any(name not in names for name in selected):
    raise ValueError("Unknown or duplicate test surface")
  digests = json.loads(env.get("CI_DIGESTS", "{}"))
  if not isinstance(digests, dict) or any(name not in digests for name in selected):
    raise ValueError("Missing test-surface digest")
  derived = derived_pytest_files(repo)
  python_tests = []
  node_tests = []
  extra_commands = []
  for key in selected:
    name = names[key]
    python_tests.extend(derived[name])
    node_tests.extend(MODULE_NODE_TESTS.get(name, ()))
    extra_commands.extend(
      shlex.split(command) for command in MODULE_COMMANDS.get(name, ())
    )
  commands = []
  if python_tests:
    commands.append([sys.executable, "-m", "pytest", "-q", *python_tests])
  if node_tests:
    commands.append(["node", "--test", *node_tests])
  commands.extend(extra_commands)
  failed = False
  for command in commands:
    print("$ " + shlex.join(command), flush=True)
    failed |= subprocess.run(command, cwd=repo, check=False).returncode != 0
  for name in selected:
    record_surface(
      Path(env.get("CI_LEDGER", ".cache/ci-ledger.json")),
      name,
      digests[name],
      env.get("GITHUB_SHA", ""),
      not failed,
    )
  return int(failed)


def module_matrix(files: Sequence[str] | None, repo: str = ".") -> list[dict[str, str]]:
  """Select test owners. Shared inputs and a missing base select all groups."""
  all_groups = files is None or any(
    fnmatch(path, pattern) for path in files for pattern in SHARED_TEST_PATHS
  )
  derived = derived_pytest_files(repo)
  rows = []
  for name, roots in MODULE_TEST_DIRS.items():
    patterns = (*MODULE_PATHS[name], *MODULE_NODE_TESTS.get(name, ()))
    if not (
      all_groups
      or any(fnmatch(path, pattern) for path in files for pattern in patterns)
      or any(path.startswith(root) for path in files for root in roots)
    ):
      continue
    commands = (
      ["python -m pytest -q " + shlex.join(derived[name])] if derived[name] else []
    )
    if node_tests := MODULE_NODE_TESTS.get(name):
      arguments = ["node", "--test"]
      commands.append(shlex.join([*arguments, *node_tests]))
    commands.extend(MODULE_COMMANDS.get(name, ()))
    rows.append({"name": name, "command": "\n".join(commands)})
  return rows


def check_module_ownership(repo: str = ".") -> None:
  """Fail before scheduling if a tracked test has no unique owner directory."""
  result = git(["ls-files", "-z"], repo)
  if result.returncode:
    raise SystemExit(f"git ls-files failed: {result.stderr.strip()}")
  discovered = {
    path
    for path in result.stdout.split("\0")
    if path and not path.startswith(ARCHIVED_TEST_PREFIX) and test_file_name(path)
  }
  owned = {path for paths in derived_test_files(repo).values() for path in paths}
  if missing := sorted(discovered - owned):
    raise SystemExit("Tests need a module owner: " + ", ".join(missing))


def step_module_tests(env: Mapping[str, str], output: Path, repo: str = ".") -> int:
  """Write the selected matrix before GitHub schedules its runtime jobs."""
  check_module_ownership(repo)
  base = event_base(env, repo)
  files = changed_files(base, (), repo) if base is not None else None
  rows = module_matrix(files, repo)
  write_output(output, "run", str(bool(rows)).lower())
  write_output(output, "matrix", json.dumps({"include": rows}, separators=(",", ":")))
  print("Selected test groups: " + ", ".join(row["name"] for row in rows))
  return 0


STEPS = {
  "module-tests": step_module_tests,
  "artifacts": step_artifacts,
  "collect": step_collect,
  "record": step_record,
  "test": step_test,
}


def main(argv: list[str] | None = None) -> int:
  for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
      stream.reconfigure(encoding="utf-8", errors="replace")
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
