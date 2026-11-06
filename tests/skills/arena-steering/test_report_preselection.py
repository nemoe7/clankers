"""Report publication requires a default in each option field."""

from pathlib import Path

import pytest
from arena_steering.server import SteeringApp
from arena_steering.store import SqliteStore

CHOICE = (
  '<!-- question {"id":"choice","label":"Choice"} -->\n'
  "Choose one\n"
  '- (x) A <!-- option {"label":"A"} -->\n'
  '- ( ) B <!-- option {"label":"B"} -->\n'
)
CHECKBOX = (
  '<!-- question {"id":"checks","label":"Checks"} -->\n'
  "Choose any\n"
  '- [x] C <!-- option {"label":"C"} -->\n'
  '- [ ] D <!-- option {"label":"D"} -->\n'
)
TEXT = '<!-- question {"id":"note","label":"Note"} -->\nYour note\n'


def test_each_option_field_needs_a_default_without_changing_saved_answers(
  tmp_path: Path,
) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  body = CHOICE + "\n" + CHECKBOX + "\n" + TEXT
  app.reports.publish_report("decision", "Decision", body)
  app.reports.submit_answer("decision", {"choice": "B", "checks": ["D"], "note": "ok"})
  for invalid in (
    body.replace("(x) A", "( ) A"),
    body.replace("[x] C", "[ ] C"),
  ):
    with pytest.raises(ValueError, match="preselected"):
      app.reports.publish_report("new-decision", "Decision", invalid)
    status, payload = app.dispatch(
      "POST", "/reports", {"id": "api-decision", "title": "Decision", "body": invalid}
    )
    assert status == 400 and "preselected" in payload["error"]
    with pytest.raises(ValueError, match="preselected"):
      app.reports.publish_report("decision", "Decision", invalid)
    report = app.reports.get_report("decision")
    assert report.body == body
    assert report.answers[-1].values == {"choice": "B", "checks": ["D"], "note": "ok"}
  app.reports.publish_report("text-only", "Text", TEXT)
  app.reports.publish_report("unfielded", "Unfielded", "# No fields")
  store.close()
