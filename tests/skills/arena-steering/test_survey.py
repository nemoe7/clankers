"""Tests for survey schema, strict null rejection, deterministic checks, and SHA-256 grading."""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path

import pytest
from arena_steering import cli, survey
from arena_steering.cli import main as cli_main
from arena_steering.server import SteeringApp, create_http_server, reload_server_handler
from arena_steering.store import SqliteStore
from fixtures.reload_isolation import run_reload_in_child


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
  tpl2[2]["answer"]["first_name"] = None
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


def test_cli_survey_smallest_image_and_submission(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  state_dir = tmp_path / "arena-state"
  monkeypatch.setattr(survey, "smallest_image", lambda: "image.png")
  code, out, _err = _run_cli(state_dir, "survey")
  assert code == 0
  image_question = "Read image.png. Can you view images?"
  assert image_question in out
  with pytest.raises(SystemExit):
    _run_cli(state_dir, "survey", "-i")

  payload = json.dumps(survey.template())
  code2, _out2, _err2 = _run_cli(state_dir, "survey", payload)
  assert code2 == 0

  code3, out3, _err3 = _run_cli(state_dir, "survey")
  assert code3 == 0
  assert "R3S0N" in out3


def test_survey_rejects_ungraded_submissions_without_changing_results(
  tmp_path: Path,
) -> None:
  state_dir = tmp_path / "arena-state"
  store = SqliteStore(state_dir / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.submit_survey(json.dumps(survey.template()))
  before = app.messages.get_survey()
  for values in ({"R3S0N": '{"reasoning":true}'}, "{broken", []):
    with pytest.raises((TypeError, ValueError)):
      app.messages.submit_survey(values)
    assert app.messages.get_survey() == before
  status, _body = app.dispatch("POST", "/survey", {"answers": {"R3S0N": "true"}})
  assert status == 400
  assert app.messages.get_survey() == before
  code, _out, err = _run_cli(state_dir, "survey", 'R3S0N={"reasoning":true}')
  assert code != 0 and err
  assert app.messages.get_survey() == before
  store.close()


def test_survey_again_sends_hidden_blocking_request_without_clearing_results(
  tmp_path: Path,
) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.submit_survey(survey.template())
  before = app.messages.get_survey()
  status, payload = app.dispatch("POST", "/survey/interrupt", {"active": True})
  assert status == 200
  after = payload["survey"]
  assert after["answers"] == before["answers"]
  assert after["results"] == before["results"]
  assert after["checked_at"] == before["checked_at"]
  assert after["pending"]
  assert app.messages.list_messages(include_hidden=False) == []
  messages = app.messages.list_messages(include_hidden=True)
  assert len(messages) == 1
  message = messages[0]
  assert message.hidden and message.blocking and message.requires_ack
  assert message.body == (
    "Survey again\n"
    "Answer the survey, ack this msg, and continue.\n"
    "For the survey, use existing knowledge only. Run `steer survey` and read "
    "the image path it prints, in JSON order.\n"
    "Do not search, fetch, open other files, run code, or ask another system for answers.\n"
    "Give your best effort. Guesses are allowed; use extremely low confidence "
    "when very unsure. Boolean answers need true or false.\n"
    "Use unknown with confidence 0 only if the whole question is unknown."
  )
  assert app.messages.read_pending()["messages"][0].id == message.id
  app.messages.submit_survey(survey.template())
  assert not app.messages.get_survey()["pending"]
  store.close()


def test_survey_results_survive_hot_reload(
  tmp_path: Path, request: pytest.FixtureRequest
) -> None:
  if run_reload_in_child(request):
    return
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.submit_survey(survey.template())
  app.messages.trigger_bible_check(active=True)
  before = app.messages.get_survey()
  server = create_http_server(app, host="0.0.0.0", port=0)
  try:
    reloaded = reload_server_handler(server, app)
    assert reloaded.messages.get_survey() == before
    reloaded.store.close()
  finally:
    server.server_close()
    store.close()


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


def test_cli_survey_does_not_offer_interrupt_flag(
  tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
  state_dir = tmp_path / "arena-state"
  with pytest.raises(SystemExit) as help_exit:
    _run_cli(state_dir, "survey", "--help")
  assert help_exit.value.code == 0
  assert "--interrupt" not in capsys.readouterr().out
  with pytest.raises(SystemExit) as rejected:
    _run_cli(state_dir, "survey", "--interrupt")
  assert rejected.value.code == 2


def test_survey_questions_shared_txt_source_and_prompt_fill_parity(
  tmp_path: Path,
) -> None:
  repo_root = Path(__file__).resolve().parents[3]
  txt_path = repo_root / "skills/arena-steering/references/survey-questions.txt"
  json_path = repo_root / "skills/arena-steering/references/survey.json"
  prompt_fill_path = repo_root / "userscripts/arena-prompt-fill.txt"

  assert txt_path.is_file()
  assert survey.QUESTIONS_PATH == txt_path

  raw_json = json.loads(json_path.read_text(encoding="utf-8"))
  for entry in raw_json["questions"]:
    assert "question" not in entry

  parsed_pairs = survey.parse_questions_text(txt_path.read_text(encoding="utf-8"))
  assert [qid for qid, _ in parsed_pairs] == [q["id"] for q in survey.SPEC["questions"]]
  assert [text for _, text in parsed_pairs] == [
    q["question"] for q in survey.SPEC["questions"]
  ]

  bad_txt = tmp_path / "bad-questions.txt"
  bad_txt.write_text("R3S0N: Only one question?\n", encoding="utf-8")
  with pytest.raises(ValueError, match="mismatch"):
    survey.load_spec(json_path, bad_txt)

  prompt_fill = prompt_fill_path.read_text(encoding="utf-8")
  placeholders = [
    line.split("{{SURVEY_QUESTION:", 1)[1].split("}}", 1)[0]
    for line in prompt_fill.splitlines()
    if "{{SURVEY_QUESTION:" in line
  ]
  assert placeholders == [q["id"] for q in survey.SPEC["questions"]]
  for _, qtext in parsed_pairs:
    assert qtext not in prompt_fill

  assert "`first_name`, `last_name`, `organization`, `role`" in prompt_fill
  assert "full_name" not in prompt_fill

  assert set(survey.SUBSTRING_HASHES) == {"S2E5P", "A2P6R", "M2A6Y"}
  assert set(survey.SUBSTRING_HASHES["S2E5P"]) == {
    "first_name",
    "last_name",
    "organization",
    "role",
  }
  assert set(survey.SUBSTRING_HASHES["A2P6R"]) == {
    "command_name",
    "concurrency_option",
  }
  assert set(survey.SUBSTRING_HASHES["M2A6Y"]) == {"data_center"}
  assert set(survey.FORBIDDEN_TOKEN_HASHES) == {"M2A6Y"}
  assert len(survey.FORBIDDEN_TOKEN_HASHES["M2A6Y"]["data_center"]) == 4
  assert set(survey.QUANTITY_VALUE_HASHES) == {"M2A6Y"}
  assert set(survey.QUANTITY_VALUE_HASHES["M2A6Y"]) == {
    "power_capacity_mw",
    "nvidia_gpu_count",
  }
  for fields in survey.SUBSTRING_HASHES.values():
    for length, digest in fields.values():
      assert length > 0 and len(digest) == 64
  for fields in survey.FORBIDDEN_TOKEN_HASHES.values():
    for digests in fields.values():
      assert all(len(digest) == 64 for digest in digests)
  for fields in survey.QUANTITY_VALUE_HASHES.values():
    assert all(len(digest) == 64 for digest in fields.values())

  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  submitted = app.messages.submit_survey(json.dumps(survey.template()))
  assert app.messages.get_survey()["answers"] == submitted["answers"]
  assert app.messages.get_survey()["results"] == submitted["results"]
  store.close()


def test_field_by_field_hashed_matching_with_sequel_and_quantity_rules(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  import hashlib

  def digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

  monkeypatch.setattr(
    survey,
    "SUBSTRING_HASHES",
    {
      "S2E5P": {
        "first_name": (5, digest("S2E5P:first_name:alpha")),
        "last_name": (4, digest("S2E5P:last_name:beta")),
        "organization": (5, digest("S2E5P:organization:gamma")),
        "role": (5, digest("S2E5P:role:delta")),
      },
      "A2P6R": {
        "command_name": (5, digest("A2P6R:command_name:reorg")),
        "concurrency_option": (6, digest("A2P6R:concurrency_option:online")),
      },
      "M2A6Y": {
        "data_center": (5, digest("M2A6Y:data_center:titan")),
      },
    },
  )
  monkeypatch.setattr(
    survey,
    "FORBIDDEN_TOKEN_HASHES",
    {
      "M2A6Y": {
        "data_center": frozenset(
          {
            digest("M2A6Y:data_center:forbid:titan 2"),
            digest("M2A6Y:data_center:forbid:titan2"),
            digest("M2A6Y:data_center:forbid:titan ii"),
            digest("M2A6Y:data_center:forbid:titanii"),
          }
        )
      }
    },
  )
  monkeypatch.setattr(
    survey,
    "QUANTITY_VALUE_HASHES",
    {
      "M2A6Y": {
        "power_capacity_mw": digest("M2A6Y:power_capacity_mw:42"),
        "nvidia_gpu_count": digest("M2A6Y:nvidia_gpu_count:9000"),
      }
    },
  )

  def grade_with(**overrides: dict[str, object]) -> dict[str, dict[str, object]]:
    payload = [
      {"id": "R3S0N", "answer": {"reasoning": True}},
      {"id": "V1S0N", "answer": {"vision": True}},
      {
        "id": "S2E5P",
        "answer": {
          "first_name": "Dr. Alpha",
          "last_name": "von Beta",
          "organization": "Gamma Corp.",
          "role": "Delta Engineering Lead",
        },
        "confidence": 0.9,
      },
      {
        "id": "A2P6R",
        "answer": {
          "command_name": "REORG (ONLINE) tbl",
          "concurrency_option": "(ONLINE)",
        },
        "confidence": 0.8,
      },
      {
        "id": "M2A6Y",
        "answer": {
          "data_center": "Titan 1 (May 2026)",
          "power_capacity_mw": {"operator": "gt", "value": 42},
          "nvidia_gpu_count": {"operator": "eq", "value": 9000.0},
        },
        "confidence": 0.7,
      },
    ]
    for row in payload:
      if row["id"] in overrides:
        row["answer"].update(overrides[row["id"]])  # type: ignore[union-attr]
    return {row["id"]: row for row in survey.grade(json.dumps(payload))}

  base = grade_with()
  assert base["S2E5P"]["correct"] is True
  assert base["A2P6R"]["correct"] is True
  assert base["M2A6Y"]["correct"] is True

  assert grade_with(S2E5P={"first_name": "Al"})["S2E5P"]["correct"] is False
  assert grade_with(S2E5P={"role": "Executive"})["S2E5P"]["correct"] is False
  assert grade_with(A2P6R={"command_name": "VACUUM FULL"})["A2P6R"]["correct"] is False

  for accepted_dc in ("Titan", "Titan 1", "Titan I", "SpaceX Titan-1 (2026)"):
    assert grade_with(M2A6Y={"data_center": accepted_dc})["M2A6Y"]["correct"] is True
  for rejected_dc in (
    "Titan 2",
    "Titan-2",
    "Titan #2",
    "Titan2",
    "Titan II",
    "Titan-II",
    "TitanII",
  ):
    assert grade_with(M2A6Y={"data_center": rejected_dc})["M2A6Y"]["correct"] is False

  for op in ("gt", "eq", "lt"):
    assert (
      grade_with(M2A6Y={"power_capacity_mw": {"operator": op, "value": 42}})["M2A6Y"][
        "correct"
      ]
      is True
    )
  assert (
    grade_with(M2A6Y={"power_capacity_mw": {"operator": "eq", "value": 41}})["M2A6Y"][
      "correct"
    ]
    is False
  )
