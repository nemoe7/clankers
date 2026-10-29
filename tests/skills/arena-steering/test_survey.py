"""Tests for survey schema, strict null rejection, deterministic checks, and SHA-256 grading."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from arena_steering import survey
from arena_steering.cli import main as cli_main


def _run_cli(state_dir: Path, *args: str) -> tuple[int, str, str]:
  out = io.StringIO()
  err = io.StringIO()
  code = cli_main(["--state-dir", str(state_dir), *args], out=out, err=err)
  return code, out.getvalue(), err.getvalue()


def test_template_contains_no_null_values() -> None:
  tpl = survey.template()
  raw = json.dumps(tpl)
  assert "null" not in raw
  ids = [row["id"] for row in tpl]
  assert ids == ["R3S0N", "V1S0N", "S2E5P", "A2P6R", "M2A6Y"]
  for row in tpl:
    if row["id"] in {"R3S0N", "V1S0N"}:
      assert "confidence" not in row
    else:
      assert row["confidence"] == 0


def test_grade_all_unknown_template_and_sorted_check() -> None:
  tpl = survey.template()
  results = survey.grade(json.dumps(tpl))
  by_id = {row["id"]: row for row in results}
  assert set(by_id) == {"R3S0N", "V1S0N", "S2E5P", "A2P6R", "M2A6Y", "S0R7D"}
  assert by_id["R3S0N"]["correct"] is False
  assert by_id["R3S0N"]["confidence"] is None
  assert by_id["V1S0N"]["correct"] is False
  assert by_id["V1S0N"]["confidence"] is None
  assert by_id["S2E5P"]["correct"] is None
  assert by_id["A2P6R"]["correct"] is None
  assert by_id["M2A6Y"]["correct"] is None
  assert by_id["S0R7D"]["correct"] is True
  assert by_id["S0R7D"]["confidence"] is None


def test_unsorted_submission_marks_s0r7d_false() -> None:
  tpl = list(reversed(survey.template()))
  results = survey.grade(json.dumps(tpl))
  by_id = {row["id"]: row for row in results}
  assert by_id["S0R7D"]["correct"] is False


def test_null_values_are_strictly_rejected() -> None:
  tpl = survey.template()
  tpl[4]["answer"]["power_capacity_mw"] = {"operator": "unknown", "value": None}
  with pytest.raises(ValueError, match="null"):
    survey.loads(json.dumps(tpl))

  tpl2 = survey.template()
  tpl2[2]["answer"]["full_name"] = None
  with pytest.raises(ValueError, match="null"):
    survey.loads(json.dumps(tpl2))


def test_deterministic_boolean_checks_accept_true_and_unknown() -> None:
  tpl = survey.template()
  tpl[0]["answer"]["reasoning"] = True
  tpl[1]["answer"]["vision"] = "unknown"
  results = survey.grade(json.dumps(tpl))
  by_id = {row["id"]: row for row in results}
  assert by_id["R3S0N"]["correct"] is True
  assert by_id["V1S0N"]["correct"] is None


def test_cli_survey_smallest_image_and_submission(tmp_path: Path) -> None:
  state_dir = tmp_path / "state"
  code, out, _err = _run_cli(state_dir, "survey", "-i")
  assert code == 0
  assert out.strip().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))

  payload = json.dumps(survey.template())
  code2, _out2, _err2 = _run_cli(state_dir, "survey", payload)
  assert code2 == 0

  code3, out3, _err3 = _run_cli(state_dir, "survey")
  assert code3 == 0
  assert "R3S0N" in out3
