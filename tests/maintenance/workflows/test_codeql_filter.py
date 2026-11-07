"""Conservative CodeQL selection keeps shared and unknown inputs covered."""

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
  "codeql_filter", ROOT / "maintenance/workflows/codeql_filter.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_known_language_changes_and_shared_inputs():
  assert module.languages_for(["app.py"]) == {"python"}
  assert module.languages_for(["client.ts", "view.html"]) == {"javascript"}
  assert module.languages_for(["app.py", "client.js"]) == {"python", "javascript"}
  for path in [
    ".github/workflows/ci.yml",
    "maintenance/workflows/codeql_filter.py",
    "requirements.txt",
    "docs/example.md",
    "unknown.ext",
  ]:
    assert module.languages_for([path]) == module.LANGUAGES


def test_missing_base_schedule_and_diff_failure_run_every_language(
  monkeypatch, tmp_path
):
  output = tmp_path / "output"
  monkeypatch.setenv("GITHUB_OUTPUT", str(output))
  monkeypatch.setenv("LANGUAGE", "actions")
  for event, base in [
    ("schedule", ""),
    ("workflow_dispatch", ""),
    ("push", "0000"),
    ("pull_request", "bad"),
  ]:
    monkeypatch.setenv("EVENT_NAME", event)
    monkeypatch.setenv("PUSH_BEFORE", base)
    monkeypatch.setenv("PR_BASE_SHA", base)
    monkeypatch.setattr(
      module.subprocess,
      "run",
      lambda *args, **kwargs: (_ for _ in ()).throw(
        subprocess.CalledProcessError(1, "git")
      ),
    )
    module.main()
  assert output.read_text().splitlines() == ["run=true"] * 4


def test_diff_selection_disables_rename_detection(monkeypatch, tmp_path):
  output = tmp_path / "output"
  monkeypatch.setenv("GITHUB_OUTPUT", str(output))
  monkeypatch.setenv("EVENT_NAME", "pull_request")
  monkeypatch.setenv("PR_BASE_SHA", "base")
  monkeypatch.setenv("LANGUAGE", "python")

  def run(args, **kwargs):
    assert "--no-renames" in args
    return subprocess.CompletedProcess(args, 0, b"client.js\0")

  monkeypatch.setattr(module.subprocess, "run", run)
  module.main()
  assert output.read_text() == "run=false\n"
