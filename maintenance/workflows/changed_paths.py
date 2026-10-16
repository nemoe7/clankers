"""Resolve the base commit and the changed paths for the workflow change steps.

Three jobs asked the same question before their work: which files changed against this
event's base? The answers moved here, so one place owns the fallbacks, the path lists
and the step outputs. The jobs keep only their own gate on the result.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from collections.abc import Mapping, Sequence
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EMPTY_BASE = "0" * 40
ARTIFACTS = ".github/workflows/artifacts.yml"

# The versioned modules a bump check guards, and the preview paths a test run follows.
VERSION_PATHS = (
  "userscripts/arena.user.js",
  "userscripts/chatgpt.user.js",
  "gpt-plugins/plugin.json",
  "gpt-plugins/skills",
)
# The list carries the entries the inline step had, dead `github/workflows` entry
# included, so this move changes no trigger.
PREVIEW_PATHS = (
  "skills/refs/arena-skill",
  "skills/arena-skill",
  ".agents/skills/arena-skill",
  "maintenance/minify/minify.py",
  "maintenance/minify/test_minify.py",
  "github/workflows",
  "pytest.ini",
  "package.json",
  "package-lock.json",
  ".github/workflows/ci.yml",
)

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
  arguments = ["diff", "--name-only", base, "HEAD"]
  if paths:
    arguments += ["--", *paths]
  result = git(arguments, repo)
  if result.returncode:
    raise SystemExit(f"git diff failed: {result.stderr.strip()}")
  return [line for line in result.stdout.splitlines() if line]


def step_version_bumps(env: Mapping[str, str], output: Path, repo: str = ".") -> int:
  """Report the base and the changed versioned modules for the bump enforcement."""
  base = event_base(env, repo)
  if base is None:
    write_output(output, "base", "missing")
    write_output(output, "changed", "")
    print("Base commit is missing; version validation runs without the bump check.")
    return 0
  write_output(output, "base", base)
  files = changed_files(base, VERSION_PATHS, repo)
  if not files:
    write_output(output, "changed", "")
    print("No versioned modules changed.")
    return 0
  print("\n".join(["Affected files:", *files]))
  write_output(output, "changed", "\n".join(files))
  return 0


def step_preview_tests(env: Mapping[str, str], output: Path, repo: str = ".") -> int:
  """Report whether this change touches a preview path, so the tests may skip."""
  base = event_base(env, repo)
  if base is None:
    write_output(output, "run", "true")
    print("Base commit is missing. Run the preview tests.")
    return 0
  files = changed_files(base, PREVIEW_PATHS, repo)
  write_output(output, "run", "true" if files else "false")
  if not files:
    print("No preview paths changed. Skip the preview tests.")
    return 0
  print("\n".join(["Preview paths changed:", *files]))
  return 0


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


STEPS = {
  "version-bumps": step_version_bumps,
  "preview-tests": step_preview_tests,
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
