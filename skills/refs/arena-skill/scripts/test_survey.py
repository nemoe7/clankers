import copy
import hashlib
import json

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
  examples[1]["answer"] = {"image_in": True}
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
    lambda rows: rows.reverse(),
    lambda rows: rows.append(copy.deepcopy(rows[0])),
    lambda rows: rows[0].update(extra=None),
    lambda rows: rows[0].update(confidence=True),
    lambda rows: rows[0].update(confidence=2),
    lambda rows: rows[0].update(confidence=0),
    lambda rows: rows[0].update(confidence=float("nan")),
    lambda rows: rows[0]["answer"].update(reasoning="unknown"),
    lambda rows: rows[0]["answer"].update(reasoning=1),
    lambda rows: rows[1]["answer"].update(image_in=None),
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
