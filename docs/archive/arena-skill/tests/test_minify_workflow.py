"""Archived tests for the retired arena-skill minification workflow check."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "minify"))

import workflow_check

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
  return workflow_check.audit_minify_workflow(name, copy.deepcopy(document))


def test_minify_test_entrypoint_without_pytest_fails():
  document = copy.deepcopy(BASE)
  document["jobs"]["work"]["steps"] = [
    {"name": "Minify", "run": "python tests/maintenance/minify/test_minify.py"}
  ]
  assert any("must use pytest" in finding for finding in findings(document))


def test_minify_test_entrypoint_with_pytest_passes():
  document = copy.deepcopy(BASE)
  document["jobs"]["work"]["steps"] = [
    {
      "name": "Minify",
      "run": "python -m pytest tests/maintenance/minify/test_minify.py",
    },
  ]
  assert findings(document) == []
