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


def test_the_repository_workflow_passes():
  document = workflow()
  assert findings(document) == []


def test_the_command_reports_the_workflow(capsys):
  assert check_artifacts.main([]) == 0
  output = capsys.readouterr()
  assert str(check_artifacts.WORKFLOW) in output.out
  assert not output.err


def test_manual_dispatch_without_inputs_is_valid():
  document = workflow()
  document["on"]["workflow_dispatch"] = {}
  assert findings(document) == []


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


def test_a_pull_request_trigger_fails():
  document = workflow()
  document["on"]["pull_request"] = {"branches": ["**"]}
  assert any(
    "must not run on pull requests" in finding for finding in findings(document)
  )


def test_a_reworded_job_condition_fails():
  document = workflow()
  document["jobs"]["release-gpt-plugins"]["if"] = "github.ref == 'refs/heads/main'"
  assert any(
    "release-gpt-plugins lost its event condition" in finding
    for finding in findings(document)
  )


def test_an_artifact_upload_fails():
  document = workflow()
  document["jobs"]["release-gpt-plugins"]["steps"].append(
    {"uses": "actions/upload-artifact@v7"}
  )
  assert any("locally verified archives" in finding for finding in findings(document))


def test_release_step_must_honor_changes():
  document = workflow()
  step = next(
    step
    for step in document["jobs"]["release-gpt-plugins"]["steps"]
    if "gh release upload" in step.get("run", "")
  )
  step.pop("if")
  assert any("honor the package change" in finding for finding in findings(document))


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


def test_publishing_guards_ignore_display_names():
  document = workflow()
  document["name"] = "Synthetic workflow"
  for job in document["jobs"].values():
    job["name"] = "Synthetic job"
    for step in job.get("steps", []):
      step["name"] = "Synthetic step"
  assert not findings(document)

  interrupt = copy.deepcopy(document)
  interrupt["jobs"]["publish-clankers-rules"]["concurrency"]["cancel-in-progress"] = (
    True
  )
  write_contents = copy.deepcopy(document)
  write_contents["jobs"]["publish-clankers-rules"]["permissions"] = {
    "contents": "write"
  }
  write_actions = copy.deepcopy(document)
  write_actions["jobs"]["release-gpt-plugins"]["permissions"]["actions"] = "write"
  leak_token = copy.deepcopy(document)
  leak_token["jobs"]["release-gpt-plugins"]["env"] = {
    "GH_TOKEN": "${{ secrets.GIST_TOKEN }}"
  }
  for changed in (interrupt, write_contents, write_actions, leak_token):
    assert findings(changed)
