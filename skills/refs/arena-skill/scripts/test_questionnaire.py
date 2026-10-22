import copy
import hashlib
import json

import pytest


def test_questionnaire_schema_and_hashes(monkeypatch):
  import questionnaire

  empty = questionnaire.template()
  assert len(empty) == len(questionnaire.SPEC["questions"])
  assert all(row["correct"] is None for row in questionnaire.grade(json.dumps(empty)))
  examples = copy.deepcopy(empty)
  examples[0]["answer"] = {"command_name": "Rebuild", "concurrency_option": "Online"}
  examples[1]["answer"] = {
    "full_name": "Example Person",
    "organization": "Test Org",
    "role": "Shift lead",
  }
  examples[2]["answer"] = {
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

  normalized = questionnaire.loads(json.dumps(examples))
  keys = {}
  for index, row in enumerate(normalized):
    answer = dict(row["answer"])
    fragment = "shift" if index == 1 else ""
    if fragment:
      answer.pop("role")
    keys[row["id"]] = digest(answer, fragment)
  monkeypatch.setattr(questionnaire, "HASHES", keys)
  assert all(row["correct"] for row in questionnaire.grade(json.dumps(examples)))
  for row in examples:
    row["confidence"] = 1
    for key, value in row["answer"].items():
      if isinstance(value, str):
        row["answer"][key] = value.swapcase()
  assert all(row["correct"] for row in questionnaire.grade(json.dumps(examples)))
  examples[2]["answer"]["power_capacity_mw"]["operator"] = "eq"
  graded = questionnaire.grade(json.dumps(examples))
  assert not graded[-1]["correct"]
  assert graded[-1]["confidence"] == examples[-1]["confidence"]
  examples[1]["answer"]["role"] = "Other work"
  assert not questionnaire.grade(json.dumps(examples))[1]["correct"]

  invalid = []
  for change in (
    lambda rows: rows.reverse(),
    lambda rows: rows.append(copy.deepcopy(rows[0])),
    lambda rows: rows[0].update(extra=None),
    lambda rows: rows[0].update(confidence=True),
    lambda rows: rows[0].update(confidence=2),
    lambda rows: rows[0].update(confidence=float("nan")),
    lambda rows: rows[0]["answer"].update(command_name=3),
    lambda rows: rows[2]["answer"]["power_capacity_mw"].update(operator="gte"),
    lambda rows: rows[2]["answer"]["power_capacity_mw"].update(value=True),
    lambda rows: rows[2]["answer"]["power_capacity_mw"].update(value=float("inf")),
    lambda rows: rows[2]["answer"]["power_capacity_mw"].update(
      operator="gt", value=None
    ),
    lambda rows: rows[0].update(confidence=0.5),
  ):
    value = copy.deepcopy(empty)
    change(value)
    invalid.append(json.dumps(value))
  invalid.extend(("null", "{}", "[]", '[{"id":"a","id":"b"}]'))
  for value in invalid:
    with pytest.raises(ValueError):
      questionnaire.loads(value)
  partial = copy.deepcopy(empty)
  partial[0]["answer"]["command_name"] = "Known part"
  partial[0]["confidence"] = 0.5
  with pytest.raises(ValueError, match="fill every field or set all fields to unknown"):
    questionnaire.loads(json.dumps(partial))
  null_field = copy.deepcopy(empty)
  null_field[0]["answer"]["command_name"] = None
  with pytest.raises(ValueError, match="must not be null"):
    questionnaire.loads(json.dumps(null_field))
