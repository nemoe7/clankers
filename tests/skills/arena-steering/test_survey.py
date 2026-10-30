"""Tests for survey schema, strict null rejection, deterministic checks, and SHA-256 grading."""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path

import pytest
from arena_steering import cli, survey
from arena_steering.cli import main as cli_main
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


@pytest.fixture(autouse=True)
def _isolate_cli_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  state_dir = tmp_path / "arena-state"
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: state_dir)


def _run_cli(state_dir: Path, *args: str) -> tuple[int, str, str]:
  assert state_dir == cli.resolve_state_dir()
  out = io.StringIO()
  err = io.StringIO()
  code = cli_main(list(args), out=out, err=err)
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
  state_dir = tmp_path / "arena-state"
  code, out, _err = _run_cli(state_dir, "survey", "-i")
  assert code == 0
  assert out.strip().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))

  payload = json.dumps(survey.template())
  code2, _out2, _err2 = _run_cli(state_dir, "survey", payload)
  assert code2 == 0

  code3, out3, _err3 = _run_cli(state_dir, "survey")
  assert code3 == 0
  assert "R3S0N" in out3


def test_survey_results_stay_in_memory(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.submit_survey(json.dumps(survey.template()))
  assert len(app.messages.get_survey()["results"]) == 6
  assert store.get_meta("survey_results", "") == ""

  restarted = SteeringApp(store)
  fresh = restarted.messages.get_survey()
  assert fresh["results"] == []
  assert fresh["answers"] == {}
  assert fresh["checked_at"] == ""


def test_cli_survey_posts_to_the_running_server(tmp_path: Path) -> None:
  state_dir = tmp_path / "arena-state"
  state_dir.mkdir(parents=True)
  assert state_dir == cli.resolve_state_dir()
  store = SqliteStore(state_dir / "state.sqlite3")
  app = SteeringApp(store)
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    port = int(server.server_address[1])
    (state_dir / "server.json").write_text(
      json.dumps({"host": "127.0.0.1", "port": port}), encoding="utf-8"
    )
    out = io.StringIO()
    code = cli_main(
      ["survey", json.dumps(survey.template())], out=out, err=io.StringIO()
    )
    assert code == 0
    assert "survey-source=server" in out.getvalue()
    assert len(app.messages.get_survey()["results"]) == 6
  finally:
    server.shutdown()
    server.server_close()
    store.close()
