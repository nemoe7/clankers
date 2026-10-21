"""Tests for the workflow set gate."""

from __future__ import annotations

import copy

import gate_workflows
import yaml

BASE = {
  "name": "Example",
  "on": {"push": {"branches": ["main"]}, "workflow_dispatch": None},
  "permissions": {"contents": "read"},
  "jobs": {
    "work": {
      "runs-on": "ubuntu-latest",
      "steps": [{"name": "Run", "run": "echo ok"}],
    }
  },
}


def findings(document: dict, name: str = "example.yml") -> list[str]:
  return gate_workflows.audit_document(name, copy.deepcopy(document))


def test_base_document_passes():
  assert findings(BASE) == []


def test_real_workflow_set_passes():
  assert gate_workflows.audit_paths() == []


def test_required_file_set_is_exact():
  assert gate_workflows.REQUIRED_FILES == (
    "ci.yml",
    "artifacts.yml",
    "distribute.yml",
    "codeql.yml",
    "dependency-review.yml",
    "secret-scan.yml",
    "workflow-security.yml",
    "pr-check.yml",
  )


def test_missing_required_file_fails(tmp_path):
  for name in gate_workflows.REQUIRED_FILES[:-1]:
    (tmp_path / name).write_text(yaml.safe_dump(BASE), encoding="utf-8")
  result = gate_workflows.audit_paths(tmp_path)
  assert any("required workflow file is missing" in finding for finding in result)


def test_extra_workflow_file_fails(tmp_path):
  for name in gate_workflows.REQUIRED_FILES:
    (tmp_path / name).write_text(yaml.safe_dump(BASE), encoding="utf-8")
  (tmp_path / "extra.yml").write_text(yaml.safe_dump(BASE), encoding="utf-8")
  result = gate_workflows.audit_paths(tmp_path)
  assert any("unexpected workflow file" in finding for finding in result)


def test_invalid_yaml_fails(tmp_path):
  (tmp_path / "ci.yml").write_text("name: [unclosed\n", encoding="utf-8")
  result = gate_workflows.audit_paths(tmp_path)
  assert any("invalid YAML" in finding for finding in result)


def test_missing_permissions_fails():
  document = copy.deepcopy(BASE)
  del document["permissions"]
  assert any("top-level `permissions`" in finding for finding in findings(document))


def test_write_all_fails():
  document = copy.deepcopy(BASE)
  document["permissions"] = "write-all"
  assert any("must be a mapping" in finding for finding in findings(document))


def test_write_scope_at_top_level_fails():
  document = copy.deepcopy(BASE)
  document["permissions"]["contents"] = "write"
  assert any("must stay read-only" in finding for finding in findings(document))


def test_workflow_run_fails():
  document = copy.deepcopy(BASE)
  document["on"]["workflow_run"] = {"workflows": ["CI"]}
  assert any("workflow_run" in finding for finding in findings(document))


def test_pull_request_target_fails():
  document = copy.deepcopy(BASE)
  document["on"]["pull_request_target"] = None
  assert any("pull_request_target" in finding for finding in findings(document))


def test_missing_trigger_fails():
  document = copy.deepcopy(BASE)
  document.pop("on")
  assert any("needs an `on` trigger" in finding for finding in findings(document))


def test_workflow_level_secret_fails():
  document = copy.deepcopy(BASE)
  document["env"] = {"TOKEN": "${{ secrets.TOKEN }}"}
  assert any("must stay inside a job" in finding for finding in findings(document))


def test_automatic_token_in_a_run_step_passes():
  document = copy.deepcopy(BASE)
  document["on"]["pull_request"] = None
  document["jobs"]["work"]["steps"] = [
    {"name": "Run", "run": 'echo "${{ secrets.GITHUB_TOKEN }}"'}
  ]
  assert findings(document) == []


def test_secret_in_a_run_step_fails():
  document = copy.deepcopy(BASE)
  document["jobs"]["work"]["steps"] = [
    {"name": "Run", "run": 'echo "${{ secrets.TOKEN }}"'}
  ]
  assert any(
    "must not appear in a step `run`" in finding for finding in findings(document)
  )


def test_secret_job_in_a_pull_request_workflow_needs_a_guard():
  document = copy.deepcopy(BASE)
  document["on"]["pull_request"] = None
  document["jobs"]["publish"] = {
    "runs-on": "ubuntu-latest",
    "env": {"TOKEN": "${{ secrets.TOKEN }}"},
    "steps": [{"name": "Publish", "run": "publish"}],
  }
  assert any("needs an `if` guard" in finding for finding in findings(document))

  document["jobs"]["publish"]["if"] = "github.event_name == 'push'"
  assert not any("needs an `if` guard" in finding for finding in findings(document))


def test_write_scope_in_a_pull_request_job_fails():
  document = copy.deepcopy(BASE)
  document["on"]["pull_request"] = None
  document["jobs"]["work"]["permissions"] = {"contents": "write"}
  assert any(
    "is not allowed in a pull request workflow" in finding
    for finding in findings(document)
  )


def test_pull_requests_write_stays_allowed_for_review_comments():
  document = copy.deepcopy(BASE)
  document["on"]["pull_request"] = None
  document["jobs"]["work"]["permissions"] = {"pull-requests": "write"}
  assert findings(document) == []


def test_minify_test_entrypoint_without_pytest_fails():
  document = copy.deepcopy(BASE)
  document["jobs"]["work"]["steps"] = [
    {"name": "Minify", "run": "python maintenance/minify/test_minify.py"}
  ]
  assert any("must use pytest" in finding for finding in findings(document))


def test_minify_test_entrypoint_with_pytest_passes():
  document = copy.deepcopy(BASE)
  document["jobs"]["work"]["steps"] = [
    {"name": "Minify", "run": "python -m pytest maintenance/minify/test_minify.py"},
  ]
  assert findings(document) == []


def test_trigger_lists_and_strings_parse():
  assert gate_workflows.triggers_of({"on": "push"}) == {"push": None}
  assert gate_workflows.triggers_of({"on": ["push", "workflow_dispatch"]}) == {
    "push": None,
    "workflow_dispatch": None,
  }
  assert gate_workflows.triggers_of({True: {"push": None}}) == {"push": None}


def test_main_exit_codes(capsys):
  assert gate_workflows.main() == 0
  assert "Workflow set passed" in capsys.readouterr().out


def load_workflow(name: str) -> dict:
  return yaml.safe_load(
    (gate_workflows.WORKFLOW_DIR / name).read_text(encoding="utf-8")
  )


def test_ci_triggers_main_push_and_all_branch_pull_requests():
  triggers = gate_workflows.triggers_of(load_workflow("ci.yml"))
  assert triggers["push"]["branches"] == ["main"]
  assert triggers["pull_request"]["branches"] == ["**"]


def test_artifacts_triggers_keep_both_path_families():
  triggers = gate_workflows.triggers_of(load_workflow("artifacts.yml"))
  push_paths = triggers["push"]["paths"]
  pr_paths = triggers["pull_request"]["paths"]
  assert "gpt-plugins/**" in push_paths and "gpt-plugins/**" in pr_paths
  assert "rules/**" in push_paths and "!rules/refs/**" in push_paths
  # Rule publishing never runs from a pull request.
  assert not any(path.startswith("rules/") for path in pr_paths)
  assert ".github/workflows/artifacts.yml" in push_paths
  assert "workflow_dispatch" in triggers


def test_artifacts_job_gating_preserves_the_original_semantics():
  jobs = load_workflow("artifacts.yml")["jobs"]
  validate = jobs["validate-gpt-plugins"]["if"]
  package = jobs["package-gpt-plugins"]["if"]
  publish = jobs["publish-clankers-rules"]["if"]
  assert "github.event_name == 'pull_request'" in validate
  assert "needs.changes.outputs.package == 'true'" in validate
  assert "github.ref == 'refs/heads/main'" in package
  assert "github.event_name != 'pull_request'" in package
  assert "needs.changes.outputs.package == 'true'" in package
  assert "github.event_name == 'push'" in publish
  assert "github.ref == 'refs/heads/main'" in publish
  assert "needs.changes.outputs.rules == 'true'" in publish
  # The publisher never runs from a manual dispatch.
  assert "workflow_dispatch" not in publish


def test_artifacts_job_concurrency_moves_to_job_level():
  jobs = load_workflow("artifacts.yml")["jobs"]
  assert jobs["validate-gpt-plugins"]["concurrency"] == {
    "group": "Validate-GPT-Plugins-${{ github.ref }}",
    "cancel-in-progress": True,
  }
  assert jobs["package-gpt-plugins"]["concurrency"] == {
    "group": "Package-GPT-Plugins-${{ github.ref }}",
    "cancel-in-progress": True,
  }
  assert jobs["publish-clankers-rules"]["concurrency"] == {
    "group": "publish-clankers-rules-${{ github.repository }}",
    "cancel-in-progress": False,
  }


def test_distribute_triggers_and_inputs():
  document = load_workflow("distribute.yml")
  triggers = gate_workflows.triggers_of(document)
  assert triggers["push"]["branches"] == ["main"]
  assert triggers["push"]["paths"] == [
    "rules/ARENA.md",
    "skills/arena-skill/**",
    "skills/nemo-ui-ux/**",
    "skills/nemoizer/**",
    "github/workflows/gemini-release.yml",
    "github/workflows/gemini_release.py",
    ".github/actions/distribute-sync/**",
    ".github/workflows/distribute.yml",
  ]
  assert triggers["schedule"] == [{"cron": "17 3 * * *"}]
  inputs = triggers["workflow_dispatch"]["inputs"]
  assert set(inputs) == {"repos", "gemini_repos", "nemo_ui_ux_repos", "nemoizer_repos"}
  assert all(value.get("default") == "" for value in inputs.values())
  # One job per target list, so the run page names each list on its own row.
  assert list(document["jobs"]) == ["arena", "gemini", "nemo-ui-ux", "nemoizer"]
  for name in document["jobs"]:
    assert document["jobs"][name]["concurrency"]["cancel-in-progress"] is False


def test_distribute_jobs_share_one_action_and_keep_their_own_lists():
  jobs = load_workflow("distribute.yml")["jobs"]
  assert [job["name"] for job in jobs.values()] == [
    "Distribute Arena",
    "Distribute Gemini",
    "Distribute nemo-ui-ux",
    "Distribute nemoizer",
  ]
  groups = [job["concurrency"]["group"] for job in jobs.values()]
  assert len(set(groups)) == len(jobs), (
    "each target list needs its own concurrency group"
  )
  for job in jobs.values():
    sync = [
      step
      for step in job["steps"]
      if step.get("uses") == "./.github/actions/distribute-sync"
    ]
    assert len(sync) == 1, "every job copies through the shared action"
    assert "CLANKERS_DIST_PAT" in sync[0]["env"]

  def copied(job: dict) -> dict:
    step = next(
      step
      for step in job["steps"]
      if step.get("uses") == "./.github/actions/distribute-sync"
    )
    return step["with"]

  arena, gemini, nemo_ui_ux, nemoizer = jobs.values()
  # Each job holds its own list, so a dispatcher override stays inside one target group.
  assert copied(arena)["repos-fallback"].split()[0] == "nemoe7/clankers"
  assert set(copied(nemo_ui_ux)["repos-fallback"].split()) == {
    "nemoe7/request-tracker",
    "nemoe7/daedalus",
    "nemoe7/clankers",
    "nemoe7/arena-cleanup",
  }
  assert copied(gemini)["repos-fallback"] == "nemoe7/daedalus nemoe7/request-tracker"
  assert copied(arena)["skills"] == "arena-skill"
  assert copied(arena)["rule-src"] == "rules/ARENA.md"
  assert copied(arena)["legacy"] == (
    "arena-live-steering arena-preview-reporting arena-preview-steering arena-proxy arena"
  )
  assert "skills" not in copied(gemini)
  assert copied(gemini)["files"] == "gemini-release.yml gemini_release.py"
  # The nemo-ui-ux skill lives in this repository, so its job copies it and fails on a gap.
  assert copied(nemo_ui_ux)["skills"] == "nemo-ui-ux"
  assert copied(nemo_ui_ux)["legacy"] == "nemo-ui"
  assert "allow-missing" not in copied(nemo_ui_ux)
  assert copied(nemoizer) == {
    "repos": "${{ inputs.nemoizer_repos }}",
    "repos-fallback": copied(nemo_ui_ux)["repos-fallback"] + " nemoe7/wiki",
    "skills": "nemoizer",
  }


def test_distribute_keeps_the_owner_run_packages_home():
  action = (
    gate_workflows.ROOT / ".github" / "actions" / "distribute-sync" / "action.yml"
  )
  script = "\n".join(
    step.get("run", "")
    for step in yaml.safe_load(action.read_text(encoding="utf-8"))["runs"]["steps"]
  )
  # The owner pages and the docker packages stay in this repository. Only files
  # a session loads at runtime ride to the target repositories.
  assert "grep -vFx -e README.md -e INSTALL.md" in script
  assert "grep -vE '^(arena-egress-proxy|arena-preview-proxy)/'" in script


def build_push_document(context: str, image: str) -> dict:
  document = copy.deepcopy(BASE)
  document["jobs"]["work"]["steps"] = [
    {
      "name": "Build and Push",
      "uses": "docker/build-push-action@v6",
      "with": {
        "context": context,
        "tags": "ghcr.io/${{ github.repository_owner }}/" + image + ":latest",
      },
    }
  ]
  return document


def test_a_publish_image_context_carries_the_image_name():
  document = build_push_document("skills/arena-skill/proxy", "arena-egress-proxy")
  result = findings(document)
  assert any(
    "arena-egress-proxy" in finding and "context" in finding for finding in result
  ), "A build context that misses the image name must fail the gate"


def test_a_matching_publish_image_context_passes():
  document = build_push_document(
    "skills/arena-skill/arena-egress-proxy", "arena-egress-proxy"
  )
  assert findings(document) == []


def build_matrix_document() -> dict:
  document = copy.deepcopy(BASE)
  document["jobs"]["work"]["steps"] = [
    {
      "name": "Build and Push",
      "uses": "docker/build-push-action@v6",
      "with": {
        "context": "skills/arena-skill/${{ matrix.directory }}",
        "file": "skills/arena-skill/${{ matrix.directory }}/Dockerfile",
        "tags": "ghcr.io/${{ github.repository_owner }}/${{ matrix.directory }}:latest",
      },
    }
  ]
  return document


def test_a_build_step_matrix_variable_must_be_declared():
  document = build_matrix_document()
  result = findings(document)
  assert any(
    "matrix.directory" in finding and "does not declare" in finding
    for finding in result
  ), "An undeclared matrix variable builds an empty path, so the gate must catch it"
  document["jobs"]["work"]["strategy"] = {
    "matrix": {"include": [{"directory": "arena-egress-proxy"}]}
  }
  assert findings(document) == []


def test_a_plain_matrix_list_declares_its_variable():
  document = build_matrix_document()
  document["jobs"]["work"]["strategy"] = {
    "matrix": {"directory": ["arena-egress-proxy"]}
  }
  assert findings(document) == []


def pull_request_document(job: dict) -> dict:
  document = copy.deepcopy(BASE)
  document["on"]["pull_request"] = None
  document["jobs"]["work"] = job
  return document


def write_scope_job(condition: str, scope: str = "contents") -> dict:
  return {
    "runs-on": "ubuntu-latest",
    "if": condition,
    "permissions": {scope: "write"},
    "steps": [{"name": "Publish", "run": "publish"}],
  }


def test_write_scope_in_a_job_guarded_from_pull_requests_passes():
  document = pull_request_document(
    write_scope_job(
      "needs.changes.outputs.package == 'true' && github.event_name != 'pull_request'"
    )
  )
  assert findings(document) == []


def test_write_scope_guarded_by_a_named_non_pull_request_event_passes():
  for condition in (
    "github.event_name == 'push'",
    "github.event_name == 'workflow_dispatch'",
    "${{ github.event_name == 'schedule' }}",
  ):
    document = pull_request_document(write_scope_job(condition, "packages"))
    assert findings(document) == [], condition


def test_write_scope_without_a_non_pull_request_event_still_fails():
  for condition in (
    "github.event_name == 'pull_request'",
    "needs.changes.outputs.package == 'true'",
    "github.ref == 'refs/heads/main'",
    "github.event_name == 'push' || github.event_name == 'pull_request'",
  ):
    document = pull_request_document(write_scope_job(condition))
    assert any(
      "is not allowed in a pull request workflow" in finding
      for finding in findings(document)
    ), condition


def test_guarded_from_pull_request_reads_the_condition():
  assert gate_workflows.guarded_from_pull_request({"if": "github.event_name == 'push'"})
  assert not gate_workflows.guarded_from_pull_request({})
  assert not gate_workflows.guarded_from_pull_request({"if": True})
  # An `||` branch that admits the pull request event guards nothing.
  assert not gate_workflows.guarded_from_pull_request(
    {"if": "github.event_name == 'push' || github.event_name == 'pull_request'"}
  )


def test_artifacts_push_paths_carry_both_proxy_directories():
  triggers = gate_workflows.triggers_of(load_workflow("artifacts.yml"))
  push_paths = triggers["push"]["paths"]
  pr_paths = triggers["pull_request"]["paths"]
  for entry in (
    "skills/arena-skill/arena-egress-proxy/**",
    "skills/arena-skill/arena-preview-proxy/**",
  ):
    assert entry in push_paths
    # An image publish never runs from a pull request.
    assert entry not in pr_paths


def test_artifacts_dispatch_inputs_name_both_images():
  triggers = gate_workflows.triggers_of(load_workflow("artifacts.yml"))
  inputs = triggers["workflow_dispatch"]["inputs"]
  assert set(inputs) == {"egress_image", "preview_image"}
  for value in inputs.values():
    assert value["type"] == "boolean" and value["default"] is False


def test_changes_job_reports_the_image_groups():
  job = load_workflow("artifacts.yml")["jobs"]["changes"]
  assert set(job["outputs"]) == {"package", "rules", "egress", "preview"}
  script = "\n".join(step.get("run", "") for step in job["steps"])
  # The path rules moved to one script, so the job carries no path case block.
  assert "maintenance/workflows/changed_paths.py --step artifacts" in script
  assert "case " not in script


def test_artifacts_release_job_keeps_the_release_semantics():
  job = load_workflow("artifacts.yml")["jobs"]["release-gpt-plugins"]
  assert job["permissions"] == {"contents": "write"}
  assert "needs.changes.outputs.package == 'true'" in job["if"]
  assert "github.event_name != 'pull_request'" in job["if"]
  assert job["concurrency"] == {
    "group": "Release-GPT-Plugins-${{ github.repository }}",
    "cancel-in-progress": False,
  }
  script = "\n".join(step.get("run", "") for step in job["steps"])
  assert "gate_gpt_plugins.py --archive gpt-plugins.zip" in script
  assert "gh release create" in script and "--clobber" in script


def test_artifacts_publishes_both_proxy_images_from_one_matrix():
  jobs = load_workflow("artifacts.yml")["jobs"]
  # The two image jobs differ in path, context and tag alone, so one matrix carries both.
  assert [name for name in jobs if "image" in name] == ["publish-proxy-images"]
  job = jobs["publish-proxy-images"]
  assert "github.event_name != 'pull_request'" in job["if"]
  assert job["permissions"] == {"contents": "read", "packages": "write"}
  assert job["concurrency"] == {
    "group": "Publish-Proxy-Images-${{ github.repository }}",
    "cancel-in-progress": False,
  }
  rows = job["strategy"]["matrix"]["include"]
  assert [row["directory"] for row in rows] == [
    "arena-egress-proxy",
    "arena-preview-proxy",
  ]
  assert [row["changed"] for row in rows] == [
    "${{ needs.changes.outputs.egress }}",
    "${{ needs.changes.outputs.preview }}",
  ]
  # One row builds one image, so every step waits for its own row's flag.
  assert all(step.get("if") == "matrix.changed == 'true'" for step in job["steps"])
  build = next(
    step
    for step in job["steps"]
    if str(step.get("uses", "")).startswith("docker/build-push-action@")
  )
  assert build["with"]["context"] == "skills/arena-skill/${{ matrix.directory }}"
  assert build["with"]["file"] == (
    "skills/arena-skill/${{ matrix.directory }}/Dockerfile"
  )
  assert build["with"]["tags"] == (
    "ghcr.io/${{ github.repository_owner }}/${{ matrix.directory }}:latest"
  )
