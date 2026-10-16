"""Contract check for the artifacts workflow, which its own jobs run.

The validation and packaging jobs each asserted this contract in an inline heredoc.
Both now call this script, so one copy of the rule covers the pull request check and
the main-branch package run.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "artifacts.yml"
PUSH_PATHS = (
  "gpt-plugins/**",
  "rules/**",
  "!rules/refs/**",
  ".github/workflows/artifacts.yml",
)
PULL_PATHS = (
  "gpt-plugins/**",
  "maintenance/gpt_plugins/**",
  ".github/workflows/artifacts.yml",
)
VALIDATE_IF = (
  "github.event_name == 'pull_request' && needs.changes.outputs.package == 'true'"
)
PACKAGE_IF = (
  "needs.changes.outputs.package == 'true' && github.ref == 'refs/heads/main'"
  " && github.event_name != 'pull_request'"
)
PUBLISH_IF = (
  "github.event_name == 'push' && github.ref == 'refs/heads/main'"
  " && needs.changes.outputs.rules == 'true'"
)


def triggers_of(document: dict) -> dict:
  """Return the parsed `on` mapping. PyYAML reads an unquoted `on` key as True."""
  triggers = document.get("on", document.get(True))
  return triggers if isinstance(triggers, dict) else {}


def step_runs(job: dict) -> str:
  return "\n".join(
    str(step.get("run", ""))
    for step in job.get("steps", []) or []
    if isinstance(step, dict)
  )


def findings_for(document: dict) -> list[str]:
  """Return the contract findings for one parsed artifacts workflow."""
  findings: list[str] = []
  triggers = triggers_of(document)
  push = triggers.get("push") or {}
  pull = triggers.get("pull_request") or {}
  if push.get("branches") != ["main"]:
    findings.append(f"push must target main alone, found {push.get('branches')}")
  for entry in PUSH_PATHS:
    if entry not in (push.get("paths") or []):
      findings.append(f"push paths miss {entry}")
  if set(pull.get("paths") or []) != set(PULL_PATHS):
    findings.append(f"pull request paths changed, found {pull.get('paths')}")
  if not triggers.get("workflow_dispatch"):
    findings.append("workflow_dispatch is missing")

  jobs = document.get("jobs") or {}
  expected = (
    ("validate-gpt-plugins", VALIDATE_IF),
    ("package-gpt-plugins", PACKAGE_IF),
    ("publish-clankers-rules", PUBLISH_IF),
  )
  for name, condition in expected:
    job = jobs.get(name) or {}
    if job.get("if") != condition:
      findings.append(f"{name} lost its event condition, found {job.get('if')}")
  for name in ("package-gpt-plugins", "publish-clankers-rules"):
    if (jobs.get(name) or {}).get("needs") != "changes":
      findings.append(f"{name} must need the changes job")

  validate = jobs.get("validate-gpt-plugins") or {}
  validate_runs = step_runs(validate)
  for marker in ("gate_gpt_plugins.py", "--base-manifest", "--self-check"):
    if marker not in validate_runs:
      findings.append(f"the validation job runs no {marker}")
  for step in validate.get("steps", []) or []:
    if not isinstance(step, dict):
      continue
    if str(step.get("run", "")).strip().startswith("zip -r "):
      findings.append("the validation job must not zip an archive")
    if str(step.get("uses", "")).startswith("actions/upload-artifact"):
      findings.append("the validation job must not upload an artifact")

  package = jobs.get("package-gpt-plugins") or {}
  uploads = [
    step
    for step in package.get("steps", []) or []
    if isinstance(step, dict)
    and str(step.get("uses", "")).startswith("actions/upload-artifact")
  ]
  if not uploads:
    findings.append("the package job uploads nothing")
  else:
    first = uploads[0]
    with_block = first.get("with") or {}
    if first.get("uses") != "actions/upload-artifact@v7":
      findings.append(f"the archive upload must use @v7, found {first.get('uses')}")
    if with_block.get("path") != "gpt-plugins.zip":
      findings.append(
        f"the archive upload must name gpt-plugins.zip, found {with_block.get('path')}"
      )
    if with_block.get("archive") is not False:
      findings.append("a direct upload keeps `archive: false`")
    if "name" in with_block:
      findings.append("a direct upload keeps the filename as the artifact name")
  if not any(
    str(step.get("run", ""))
    .strip()
    .startswith("python maintenance/gpt_plugins/gate_gpt_plugins.py --package-dir ")
    for step in package.get("steps", []) or []
    if isinstance(step, dict)
  ):
    findings.append("the package job runs no packaging step")
  for marker in ("test_publish.py", "pytest", "publish.py"):
    if marker not in step_runs(jobs.get("publish-clankers-rules") or {}):
      findings.append(f"the publish job runs no {marker}")
  return findings


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--workflow", default=str(WORKFLOW))
  arguments = parser.parse_args(argv)
  path = Path(arguments.workflow)
  document = yaml.safe_load(path.read_text(encoding="utf-8"))
  findings = findings_for(document)
  for finding in findings:
    print(f"::error::{finding}")
  if findings:
    print(f"{len(findings)} artifacts contract violation(s)")
    return 1
  print(f"{path}: PR validation, main package, and rules publish are as required.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
