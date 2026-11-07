"""Archived workflow check for the retired arena-skill minification suite."""

from __future__ import annotations


def audit_minify_workflow(name: str, document: object) -> list[str]:
  """Require pytest whenever a workflow job runs the retired test_minify.py suite."""
  if not isinstance(document, dict):
    return [f"{name}: the workflow must be a mapping"]
  jobs = document.get("jobs")
  if not isinstance(jobs, dict):
    return []
  findings: list[str] = []
  for job_name, job in jobs.items():
    if not isinstance(job, dict):
      continue
    where = f"{name}:{job_name}"
    run_text = "\n".join(
      step.get("run", "")
      for step in job.get("steps", []) or []
      if isinstance(step, dict)
    )
    if "test_minify.py" in run_text and "pytest" not in run_text:
      findings.append(
        f"{where}: a job that runs test_minify.py must use pytest; the test checks the minified runtime"
      )
  return findings
