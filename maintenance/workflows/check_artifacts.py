"""Contract check for the privileged artifacts workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from gate_workflows import (
  READ_ONLY_VALUES,
  audit_document,
  credential_names,
  job_text,
  triggers_of,
)

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "artifacts.yml"
PUSH_PATHS = (
  "gpt-plugins/**",
  "rules/**",
  "!rules/refs/**",
  ".github/workflows/artifacts.yml",
)
RELEASE_IF = "github.ref == 'refs/heads/main' && github.event_name != 'pull_request'"
PUBLISH_IF = "github.event_name == 'push' && github.ref == 'refs/heads/main'"


def step_runs(job: dict) -> str:
  return "\n".join(
    str(step.get("run", ""))
    for step in job.get("steps", []) or []
    if isinstance(step, dict)
  )


def findings_for(document: dict) -> list[str]:
  """Return the contract findings for one parsed artifacts workflow."""
  findings = audit_document(WORKFLOW.name, document)
  triggers = triggers_of(document)
  push = triggers.get("push") or {}
  if push.get("branches") != ["main"]:
    findings.append(f"push must target main alone, found {push.get('branches')}")
  for entry in PUSH_PATHS:
    if entry not in (push.get("paths") or []):
      findings.append(f"push paths miss {entry}")
  if "pull_request" in triggers:
    findings.append("artifact publication must not run on pull requests")
  if "workflow_dispatch" not in triggers:
    findings.append("workflow_dispatch is missing")

  jobs = document.get("jobs") or {}
  publish = jobs.get("publish-clankers-rules") or {}
  concurrency = publish.get("concurrency") or {}
  if not concurrency.get("group") or concurrency.get("cancel-in-progress") is not False:
    findings.append(
      "rules publishing must serialize without interrupting a running job"
    )
  for name, job in jobs.items():
    permissions = job.get("permissions") or {}
    if permissions.get("actions", "none") not in READ_ONLY_VALUES:
      findings.append(f"{name} must not write actions")
    if (
      name != "release-gpt-plugins"
      and permissions.get("contents", "none") not in READ_ONLY_VALUES
    ):
      findings.append(f"{name} must not write contents")
    if name != "publish-clankers-rules" and "GIST_TOKEN" in credential_names(
      job_text(job)
    ):
      findings.append(f"{name} must not use the rules publishing token")
  if set(jobs) != {"release-gpt-plugins", "publish-clankers-rules"}:
    findings.append("artifact workflow must keep exactly two secret-isolated jobs")
  expected = (
    ("release-gpt-plugins", RELEASE_IF),
    ("publish-clankers-rules", PUBLISH_IF),
  )
  for name, condition in expected:
    job = jobs.get(name) or {}
    if job.get("if") != condition:
      findings.append(f"{name} lost its event condition, found {job.get('if')}")
    steps = job.get("steps", []) or []
    detect = [
      step for step in steps if isinstance(step, dict) and step.get("id") == "detect"
    ]
    if len(detect) != 1 or "changed_paths.py --step artifacts" not in detect[0].get(
      "run", ""
    ):
      findings.append(f"{name} must detect changed path groups")
    group = "package" if name == "release-gpt-plugins" else "rules"
    if detect:
      position = steps.index(detect[0])
      for step in steps[position + 1 :]:
        if step.get("if") != f"steps.detect.outputs.{group} == 'true'":
          findings.append(f"{name} steps must honor the {group} change result")
          break
  release = jobs.get("release-gpt-plugins") or {}
  steps = release.get("steps", []) or []
  if (release.get("permissions") or {}).get("contents") != "write":
    findings.append("release job needs contents write")
  if any(
    "actions/upload-artifact" in str(step.get("uses", ""))
    or "actions/download-artifact" in str(step.get("uses", ""))
    for step in steps
  ):
    findings.append("release must use its locally verified archives")
  markers = (
    "gate_gpt_plugins.py --package-dir",
    "gate_gpt_plugins.py --archive",
    "gh release upload",
  )
  positions = [
    next(
      (index for index, step in enumerate(steps) if marker in step.get("run", "")), -1
    )
    for marker in markers
  ]
  if (
    -1 in positions
    or positions != sorted(positions)
    or len(set(positions)) != len(positions)
  ):
    findings.append("release must build and verify archives before publishing")
  for marker in ("test_publish.py", "pytest", "publish.py"):
    if marker not in step_runs(jobs.get("publish-clankers-rules") or {}):
      findings.append(f"the publish job runs no {marker}")
  return findings


def main(argv: list[str] | None = None) -> int:
  for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
      stream.reconfigure(encoding="utf-8", errors="replace")
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
  print(f"{path}: Main package and rules publish are as required.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
