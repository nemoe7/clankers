import copy
import hashlib
import json
from pathlib import Path

import pytest


def test_survey_schema_and_hashes(monkeypatch):
  import survey

  empty = survey.template()
  assert len(empty) == len(survey.SPEC["questions"])
  initial_graded = survey.grade(json.dumps(empty))
  assert [row["correct"] for row in initial_graded] == [
    False,
    False,
    None,
    None,
    None,
  ]
  examples = copy.deepcopy(empty)
  examples[0]["answer"] = {"reasoning": True}
  examples[1]["answer"] = {"vision": True}
  examples[2]["answer"] = {
    "full_name": "Example Person",
    "organization": "Test Org",
    "role": "Shift lead",
  }
  examples[3]["answer"] = {"command_name": "Rebuild", "concurrency_option": "Online"}
  examples[4]["answer"] = {
    "data_center": "Test site",
    "power_capacity_mw": {"operator": "lt", "value": 12},
    "nvidia_gpu_count": {"operator": "eq", "value": 34},
  }
  for row in examples:
    row["confidence"] = 0.5

  def digest(answer, fragment=""):
    canonical = json.dumps(
      answer, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256((canonical + "\0" + fragment).encode()).hexdigest()

  normalized = survey.loads(json.dumps(examples))
  keys = {}
  for row in normalized:
    if row["id"] not in survey.HASHES:
      continue
    answer = dict(row["answer"])
    fragment = "shift" if "role" in answer else ""
    if fragment:
      answer.pop("role")
    keys[row["id"]] = digest(answer, fragment)
  monkeypatch.setattr(survey, "HASHES", keys)
  assert all(row["correct"] for row in survey.grade(json.dumps(examples)))
  for row in examples:
    row["confidence"] = 1
    for key, value in row["answer"].items():
      if isinstance(value, str):
        row["answer"][key] = value.swapcase()
  assert all(row["correct"] for row in survey.grade(json.dumps(examples)))
  examples[4]["answer"]["power_capacity_mw"]["operator"] = "eq"
  graded = survey.grade(json.dumps(examples))
  assert not graded[-1]["correct"]
  assert graded[-1]["confidence"] == examples[-1]["confidence"]
  examples[2]["answer"]["role"] = "Other work"
  assert not survey.grade(json.dumps(examples))[2]["correct"]
  examples[0]["answer"]["reasoning"] = False
  assert not survey.grade(json.dumps(examples))[0]["correct"]

  invalid = []
  for change in (
    lambda rows: rows.append(copy.deepcopy(rows[0])),
    lambda rows: rows[1].update(id=rows[0]["id"]),
    lambda rows: rows[0].update(extra=None),
    lambda rows: rows[0].update(confidence=True),
    lambda rows: rows[0].update(confidence=2),
    lambda rows: rows[0].update(confidence=0),
    lambda rows: rows[0].update(confidence=float("nan")),
    lambda rows: rows[0]["answer"].update(reasoning="unknown"),
    lambda rows: rows[0]["answer"].update(reasoning=1),
    lambda rows: rows[1]["answer"].update(image_in=None),
    lambda rows: rows[1]["answer"].update(vision=None),
    lambda rows: rows[3]["answer"].update(command_name=3),
    lambda rows: rows[4]["answer"]["power_capacity_mw"].update(operator="gte"),
    lambda rows: rows[4]["answer"]["power_capacity_mw"].update(value=True),
    lambda rows: rows[4]["answer"]["power_capacity_mw"].update(value=float("inf")),
    lambda rows: rows[4]["answer"]["power_capacity_mw"].update(
      operator="gt", value=None
    ),
    lambda rows: rows[2].update(confidence=0.5),
  ):
    value = copy.deepcopy(empty)
    change(value)
    invalid.append(json.dumps(value))
  invalid.extend(("null", "{}", "[]", '[{"id":"a","id":"b"}]'))
  for value in invalid:
    with pytest.raises(ValueError):
      survey.loads(value)
  partial = copy.deepcopy(empty)
  partial[3]["answer"]["command_name"] = "Known part"
  partial[3]["confidence"] = 0.5
  with pytest.raises(ValueError, match="fill every field or set all fields to unknown"):
    survey.loads(json.dumps(partial))
  null_field = copy.deepcopy(empty)
  null_field[3]["answer"]["command_name"] = None
  with pytest.raises(ValueError, match="must not be null"):
    survey.loads(json.dumps(null_field))


def test_grade_retains_each_submitted_answer():
  import survey

  submitted = survey.template()
  submitted[0]["answer"] = {"reasoning": True}
  submitted[2]["answer"] = {
    "full_name": "Case Sensitive <Person>",
    "organization": "Example Org",
    "role": "Team Lead",
  }
  submitted[2]["confidence"] = 0.5
  submitted[4]["answer"] = {
    "data_center": "Example Site",
    "power_capacity_mw": {"operator": "GT", "value": 12.5},
    "nvidia_gpu_count": {"operator": "eq", "value": 34},
  }
  submitted[4]["confidence"] = 0.5

  results = survey.grade(json.dumps(submitted))

  assert [row["answer"] for row in results] == [row["answer"] for row in submitted]
  assert results[2]["answer"]["role"] == "Team Lead"
  assert results[3]["correct"] is None


def test_survey_vision_question_and_unsorted_acceptance():
  import survey

  question = next(row for row in survey.SPEC["questions"] if row["id"] == "V1S0N")
  assert list(question["answer_fields"]) == ["vision"]
  assert not any(row["id"] == "I4M6G" for row in survey.SPEC["questions"])

  rows = survey.template()
  rows[0]["answer"] = {"reasoning": True}
  shuffled = [rows[2], rows[0], rows[4], rows[1], rows[3]]
  parsed = survey.loads(json.dumps(shuffled))
  assert [row["id"] for row in parsed] == [
    row["id"] for row in survey.SPEC["questions"]
  ]
  assert survey.submission_order(json.dumps(shuffled)) is False
  assert survey.submission_order(json.dumps(rows)) is True
  graded = survey.grade(json.dumps(shuffled))
  assert [row["id"] for row in graded] == [
    row["id"] for row in survey.SPEC["questions"]
  ]
  assert graded[0]["correct"] is True

  duplicated = [rows[0], rows[0], rows[2], rows[3], rows[4]]
  with pytest.raises(ValueError, match="Duplicate"):
    survey.loads(json.dumps(duplicated))
  unknown = copy.deepcopy(rows)
  unknown[0]["id"] = "ZZZZZZ"
  with pytest.raises(ValueError, match="Unknown question IDs: ZZZZZZ"):
    survey.loads(json.dumps(unknown))
  missing = copy.deepcopy(rows)
  missing[1]["id"] = "R3S0N"
  with pytest.raises(ValueError):
    survey.loads(json.dumps(missing))


def test_smallest_image_writes_a_temp_png_without_repo_images(tmp_path):
  import survey

  (tmp_path / "notes.md").write_text("No images here.\n", encoding="utf-8")
  found = survey.smallest_image(tmp_path)
  assert found is not None
  temp = Path(found)
  assert temp.is_file() and temp.suffix == ".png"
  payload = temp.read_bytes()
  assert payload.startswith(b"\x89PNG\r\n\x1a\n")
  assert payload.rstrip().endswith(b"IEND\xaeB`\x82")
  assert len(payload) < 200
  assert tmp_path.resolve() not in temp.resolve().parents
  temp.unlink()

  image = tmp_path / "only.png"
  image.write_bytes(payload)
  assert survey.smallest_image(tmp_path) == "only.png"
  assert survey.smallest_image(tmp_path / "absent") is None
