"""Gate for the workflow set: required files, least-privilege permissions and job-scoped secrets.

actionlint checks the syntax and zizmor audits the security. This gate holds the repository
contract that both tools leave implicit: the exact file set, a read-only top level, no
privileged trigger for untrusted code, and credentials that stay inside their job.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

REQUIRED_FILES = (
  "ci.yml",
  "artifacts.yml",
  "distribute.yml",
  "codeql.yml",
  "dependency-review.yml",
  "secret-scan.yml",
  "workflow-security.yml",
  "pr-check.yml",
)

# A pull request can run untrusted code, so these scopes stay out of its workflows.
FORBIDDEN_PR_PERMISSIONS = ("contents", "actions", "packages", "id-token")
READ_ONLY_VALUES = ("read", "none")

# A job whose `if` names an event that is not a pull request never runs pull request code,
# so that job alone may carry a forbidden scope inside a pull request workflow.
NON_PULL_REQUEST_EVENT_RE = re.compile(
  r"github\.event_name\s*(?:!=\s*'pull_request'"
  r"|==\s*'(?:push|workflow_dispatch|schedule|release|repository_dispatch)')"
)
# A condition that admits the pull request event guards nothing, an `||` branch included.
PULL_REQUEST_EVENT_RE = re.compile(r"github\.event_name\s*==\s*'pull_request'")

SECRET_RE = re.compile(r"secrets\.([A-Za-z0-9_]+)")


def credential_names(text: str) -> set[str]:
  """Return the stored credential names in text. The automatic token is not one."""
  return {name for name in SECRET_RE.findall(text) if name != "GITHUB_TOKEN"}


def triggers_of(document: dict) -> dict:
  """Return the parsed `on` mapping. PyYAML reads an unquoted `on` key as True."""
  triggers = document.get("on", document.get(True))
  if isinstance(triggers, str):
    return {triggers: None}
  if isinstance(triggers, list):
    return {name: None for name in triggers}
  return triggers if isinstance(triggers, dict) else {}


def jobs_of(document: dict) -> dict:
  jobs = document.get("jobs")
  return jobs if isinstance(jobs, dict) else {}


def guarded_from_pull_request(job: dict) -> bool:
  """Return True when the job's `if` names an event that is not a pull request."""
  condition = job.get("if")
  if not isinstance(condition, str):
    return False
  if PULL_REQUEST_EVENT_RE.search(condition):
    return False
  return bool(NON_PULL_REQUEST_EVENT_RE.search(condition))


def job_text(job: object) -> str:
  return yaml.safe_dump(job, sort_keys=True)


def audit_document(name: str, document: object) -> list[str]:
  """Return the contract findings for one workflow document."""
  findings: list[str] = []
  if not isinstance(document, dict):
    return [f"{name}: the workflow must be a mapping"]

  triggers = triggers_of(document)
  if not triggers:
    findings.append(f"{name}: the workflow needs an `on` trigger")
  for trigger in ("workflow_run", "pull_request_target"):
    if trigger in triggers:
      findings.append(f"{name}: `{trigger}` is not allowed in this repository")

  permissions = document.get("permissions")
  if permissions is None:
    findings.append(f"{name}: the workflow needs a top-level `permissions` mapping")
  elif not isinstance(permissions, dict):
    findings.append(f"{name}: `permissions` must be a mapping, not {permissions!r}")
  else:
    for scope, value in permissions.items():
      if value not in READ_ONLY_VALUES:
        findings.append(
          f"{name}: top-level `permissions` must stay read-only, found {scope}: {value}"
        )

  top_level_env = document.get("env")
  if top_level_env and credential_names(yaml.safe_dump(top_level_env)):
    findings.append(
      f"{name}: credentials must stay inside a job, not in the workflow `env`"
    )

  runs_on_pull_request = "pull_request" in triggers
  for job_name, job in jobs_of(document).items():
    where = f"{name}:{job_name}"
    if not isinstance(job, dict):
      findings.append(f"{where}: the job must be a mapping")
      continue
    text = job_text(job)
    if credential_names(text) and runs_on_pull_request and not job.get("if"):
      findings.append(
        f"{where}: a job that uses credentials in a pull request workflow needs an `if` guard"
      )
    for step in job.get("steps", []) or []:
      if not isinstance(step, dict):
        continue
      for field in ("run", "if"):
        value = step.get(field)
        if isinstance(value, str) and credential_names(value):
          findings.append(
            f"{where}: `secrets.` must not appear in a step `{field}` string"
          )
    # The build context of an image publish is the package's own directory, so the
    # directory name and the image name stay one word.
    for step in job.get("steps", []) or []:
      if not isinstance(step, dict):
        continue
      if not str(step.get("uses", "")).startswith("docker/build-push-action@"):
        continue
      with_block = step.get("with") or {}
      context = str(with_block.get("context", "")).rstrip("/")
      directory = context.rsplit("/", 1)[-1]
      tags = with_block.get("tags")
      tag_list = tags.splitlines() if isinstance(tags, str) else list(tags or [])
      for tag in tag_list:
        image = str(tag).rsplit("/", 1)[-1].split(":", 1)[0]
        if directory and image and directory != image:
          findings.append(
            f"{where}: the build context `{context}` must be a directory named "
            f"after the image `{image}`"
          )
    if runs_on_pull_request and not guarded_from_pull_request(job):
      for scope, value in (job.get("permissions") or {}).items():
        if scope in FORBIDDEN_PR_PERMISSIONS and value not in READ_ONLY_VALUES:
          findings.append(
            f"{where}: `{scope}: {value}` is not allowed in a pull request workflow"
          )
    run_text = "\n".join(
      step.get("run", "")
      for step in job.get("steps", []) or []
      if isinstance(step, dict)
    )
    if "gate_minify.py" in run_text and "pytest" not in run_text:
      findings.append(
        f"{where}: a job that runs gate_minify.py must install pytest; the script runs pytest on the minified runtime"
      )
  return findings


def audit_paths(directory: Path = WORKFLOW_DIR) -> list[str]:
  """Return the contract findings for the workflow directory."""
  findings: list[str] = []
  files = sorted(path.name for path in directory.glob("*.y*ml"))
  for missing in sorted(set(REQUIRED_FILES) - set(files)):
    findings.append(f"{missing}: required workflow file is missing")
  for extra in sorted(set(files) - set(REQUIRED_FILES)):
    findings.append(f"{extra}: unexpected workflow file")
  for name in files:
    try:
      document = yaml.safe_load((directory / name).read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
      findings.append(f"{name}: invalid YAML: {error}")
      continue
    findings.extend(audit_document(name, document))
  return findings


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--directory", default=str(WORKFLOW_DIR))
  arguments = parser.parse_args(argv)
  findings = audit_paths(Path(arguments.directory))
  for finding in findings:
    print(f"::error::{finding}")
  if findings:
    print(f"{len(findings)} workflow contract violation(s)")
    return 1
  print(f"Workflow set passed: {', '.join(REQUIRED_FILES)}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
