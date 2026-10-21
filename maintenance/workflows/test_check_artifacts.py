"""Tests for the artifacts workflow contract check."""

from __future__ import annotations

import copy

import check_artifacts
import yaml


def workflow() -> dict:
  document = yaml.safe_load(check_artifacts.WORKFLOW.read_text(encoding="utf-8"))
  # PyYAML reads the unquoted `on` key as True, so the triggers come back under `on`.
  document["on"] = document.pop(True)
  return document


def findings(document: dict) -> list[str]:
  return check_artifacts.findings_for(copy.deepcopy(document))


def upload_step(document: dict) -> dict:
  return next(
    step
    for step in document["jobs"]["package-gpt-plugins"]["steps"]
    if str(step.get("uses", "")).startswith("actions/upload-artifact")
  )


def test_the_repository_workflow_passes():
  assert findings(workflow()) == []


def test_the_command_reports_the_workflow(capsys):
  assert check_artifacts.main([]) == 0
  output = capsys.readouterr()
  assert str(check_artifacts.WORKFLOW) in output.out
  assert not output.err


def test_a_push_that_leaves_main_fails():
  document = workflow()
  document["on"]["push"]["branches"] = ["release"]
  assert any("push must target main alone" in finding for finding in findings(document))


def test_a_missing_push_path_fails():
  document = workflow()
  document["on"]["push"]["paths"].remove("!rules/refs/**")
  assert any(
    "push paths miss !rules/refs/**" in finding for finding in findings(document)
  )


def test_a_changed_pull_request_path_set_fails():
  document = workflow()
  document["on"]["pull_request"]["paths"].append("rules/**")
  assert any("pull request paths changed" in finding for finding in findings(document))


def test_a_reworded_job_condition_fails():
  document = workflow()
  document["jobs"]["package-gpt-plugins"]["if"] = "github.ref == 'refs/heads/main'"
  assert any(
    "package-gpt-plugins lost its event condition" in finding
    for finding in findings(document)
  )


def test_a_validation_job_that_packages_fails():
  document = workflow()
  document["jobs"]["validate-gpt-plugins"]["steps"].append(
    {"name": "Zip", "run": "zip -r gpt-plugins.zip gpt-plugins"}
  )
  assert any("must not zip an archive" in finding for finding in findings(document))


def test_a_named_artifact_upload_fails():
  document = workflow()
  upload_step(document)["with"]["name"] = "plugins"
  assert any(
    "filename as the artifact name" in finding for finding in findings(document)
  )


def test_a_missing_publish_check_fails():
  document = workflow()
  document["jobs"]["publish-clankers-rules"]["steps"] = [
    {"name": "Publish", "run": "echo hi"}
  ]
  assert any("runs no test_publish.py" in finding for finding in findings(document))


def test_a_missing_job_fails():
  document = workflow()
  del document["jobs"]["publish-clankers-rules"]
  assert any(
    "publish-clankers-rules lost its event condition" in finding
    for finding in findings(document)
  )


def test_main_fails_on_a_drifted_copy(tmp_path, capsys):
  document = workflow()
  document["on"]["push"]["branches"] = ["release"]
  path = tmp_path / "artifacts.yml"
  path.write_text(yaml.safe_dump(document), encoding="utf-8")
  assert check_artifacts.main(["--workflow", str(path)]) == 1
  expected = findings(document)
  assert expected
  annotations = [
    line.removeprefix("::error::")
    for line in capsys.readouterr().out.splitlines()
    if line.startswith("::error::")
  ]
  assert annotations == expected
