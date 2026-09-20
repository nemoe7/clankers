"""Assert-based integration check; run with the reporting venv's Python."""

import builtins
import http.client
import json
import re
import sqlite3
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import preview


def request(method, path, body=None, headers=None):
  client = http.client.HTTPConnection("127.0.0.1", app.server_port, timeout=5)
  client.request(method, path, body, headers or {})
  response = client.getresponse()
  result = response.status, dict(response.getheaders()), response.read().decode()
  client.close()
  return result


with tempfile.TemporaryDirectory() as directory:
  root = Path(directory)
  try:
    preview.Store(root)
    raise AssertionError("Missing inbox was treated as empty")
  except FileNotFoundError:
    pass
  linked = preview.render(
    "[PR](https://github.com/nemoe7/clankers/pull/26) [here](#here)"
  )
  assert linked.count('target="_blank"') == 1 and 'rel="noopener noreferrer"' in linked
  assert "<s>" in preview.render("~~gone~~")
  chat = preview.render("line one\nline two", breaks=True)
  assert "<br" in chat and chat.count("<p>") == 1
  assert "<br" not in preview.render("line one\nline two")
  store = preview.Store(root, create=True)
  source = root / "report.md"
  source.write_text(
    "# First\n\n| A | B |\n| --- | --- |\n| C | D |\n\n<script>alert(1)</script>\n\n[bad](javascript:alert(1))",
    encoding="utf-8",
  )
  store.publish("first", "First <report>", source)
  store.publish("second", "Second", source)
  source.write_text("# Updated\n\n**Bold**", encoding="utf-8")
  store.publish("second", "Second revised", source)
  assert len(store.state()["reports"]) == 2
  assert store.report("second")["markdown"] == source.read_text()
  assert store.read()["pending"] == []
  assert store.state()["last_check"]
  app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
  worker = threading.Thread(target=app.serve_forever, daemon=True)
  worker.start()
  try:
    status, headers, page = request(
      "GET", "/", headers={"Host": "8000-sandbox.e2b.app"}
    )
    assert status == 200 and "__STYLE__" not in page and "__SCRIPT__" not in page
    assert 'data-theme="dark"' in page and 'role="tab"' in page
    assert "frame-ancestors" not in headers["Content-Security-Policy"]
    token = re.search(r"'X-Preview-Token': '([^']+)'", page)[1]
    auth = {"Content-Type": "application/json", "X-Preview-Token": token}
    status, _, draft = request(
      "POST",
      "/api/markdown",
      json.dumps({"text": "**draft** <script>alert(1)</script>"}),
      auth,
    )
    assert (
      status == 200 and "<strong>draft</strong>" in draft and "<script>" not in draft
    )
    assert store.state()["notes"] == []
    assert request("POST", "/api/markdown", '{"text":" "}', auth)[0] == 400
    assert request("POST", "/api/markdown", '{"text":"draft"}')[0] == 403
    assert request("POST", "/api/notes", "{}")[0] == 403
    assert request("POST", "/api/notes", "{}", {"X-Preview-Token": token})[0] == 415
    assert request("POST", "/api/notes", "x" * 32769, auth)[0] == 413
    for body in (
      "{",
      "[]",
      '{"id":"x","text":3}',
      '{"id":"x","text":" "}',
      json.dumps({"id": "x", "text": "x" * 4001}),
    ):
      assert request("POST", "/api/notes", body, auth)[0] == 400
    assert store.read()["pending"] == []
    text = "STOP: kumusta 👋 <script>text only</script>"
    body = json.dumps({"id": "message-1", "text": text})
    with ThreadPoolExecutor(max_workers=2) as pool:
      results = list(
        pool.map(lambda _: request("POST", "/api/notes", body, auth)[0], range(2))
      )
    assert results == [201, 201]
    assert len(store.state()["notes"]) == 1
    assert store.read()["pending"][0]["text"] == text
    assert store.read()["pending"][0]["acknowledged_at"] is None
    assert (
      request("POST", "/api/notes", '{"id":"message-1","text":"changed"}', auth)[0]
      == 400
    )
    for broken in (
      (["message-1", "unknown"], "reply", "done"),
      (["message-1"], "shout", "done"),
      (["message-1"], "reply", ""),
      (["message-1"], "reply", "x" * 4001),
    ):
      try:
        store.acknowledge(*broken)
        raise AssertionError(f"Invalid receipt accepted: {broken}")
      except ValueError:
        assert store.read()["pending"]
    store.acknowledge(["message-1"], "reply", "Fixed in `preview.py`.")
    stamp = store.state()["notes"][0]["acknowledged_at"]
    assert store.state()["notes"][0]["ack_text"] == "Fixed in `preview.py`."
    store.acknowledge(["message-1"], "note", "and rechecked")
    row = store.state()["notes"][0]
    assert row["acknowledged_at"] == stamp
    assert row["ack_kind"] == "note" and row["ack_text"] == "and rechecked"
    assert preview.Store(root).read()["pending"] == []
    assert len(preview.Store(root).state()["notes"]) == 1
    status, _, state_body = request("GET", "/api/state")
    assert status == 200
    with patch.object(preview, "HAS_RENDERER", False):
      try:
        preview.require_renderer()
        raise AssertionError("serve accepted a missing renderer")
      except SystemExit as error:
        assert "markdown-it-py" in str(error)
    served_note = json.loads(state_body)["notes"][0]
    assert "&lt;script&gt;" in served_note["html"]
    assert "ack_html" not in served_note and served_note["ack_text"] == "and rechecked"
    store.acknowledge(["message-1"], "reply", "<script>alert(1)</script> **safe**")
    status, _, state_body = request("GET", "/api/state")
    served_note = json.loads(state_body)["notes"][0]
    assert "&lt;script&gt;" in served_note["ack_html"]
    assert "<strong>safe</strong>" in served_note["ack_html"]
    assert "<script>" not in served_note["ack_html"]
    status, _, rendered = request("GET", "/api/reports/first/html")
    assert status == 200
    rendered = json.loads(rendered)
    assert rendered["fields"] == 0
    assert "<table>" in rendered["html"] and "<script>" not in rendered["html"]
    assert 'href="javascript:' not in rendered["html"]
    assert request("GET", "/api/reports/first/export")[0] == 404
    assert request("GET", "/api/reports/first/source")[0] == 200
    for path in (
      "/.git/config",
      "/state.sqlite3",
      "/../../ARENA.md",
      "/api/reports/missing/html",
    ):
      assert request("GET", path)[0] == 404
    real_import = builtins.__import__

    def without_renderer(name, *args, **kwargs):
      if name == "markdown_it":
        raise ImportError("Test: renderer absent")
      return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=without_renderer):
      assert request("GET", "/api/reports/first/html")[0] == 503
      assert request("POST", "/api/markdown", '{"text":"draft"}', auth)[0] == 503
      status, _, unavailable = request("GET", "/api/state")
      unavailable = json.loads(unavailable)
      assert status == 200 and unavailable["rendering_error"]
      assert (
        unavailable["notes"][0]["text"] == text
        and "html" not in unavailable["notes"][0]
      )
      assert (
        request(
          "POST", "/api/notes", '{"id":"no-renderer","text":"still works"}', auth
        )[0]
        == 201
      )
    with patch.object(
      store, "note", side_effect=sqlite3.OperationalError("disk failure")
    ):
      assert request("POST", "/api/notes", body, auth)[0] == 503
    fielded = root / "fielded.md"
    fielded.write_text(
      "# Sign-off\n\nPick the areas:\n\n- [ ] ui\n- [x] api\n\nSeverity:\n\n"
      "- ( ) low\n- (x) high\n\nName: ___\n\nNotes {#notes}\n\n___\n\n"
      "```text\n- [ ] not a field\n```\n",
      encoding="utf-8",
    )
    store.publish("fields", "Fielded", fielded)
    assert [row["id"] for row in store.state()["reports"]] == [
      "first",
      "second",
      "fields",
    ]
    assert [row["seq"] for row in store.state()["reports"]] == [1, 2, 3]
    store.publish("first", "First <report>", source)
    assert [row["seq"] for row in store.state()["reports"]] == [1, 2, 3]
    blocks, questions = preview.parse_fields(fielded.read_text(encoding="utf-8"))
    assert [question["type"] for question in questions] == [
      "checkbox",
      "choice",
      "text",
      "text",
    ]
    assert questions[0]["options"] == ["ui", "api"] and questions[0]["default"] == [
      "api"
    ]
    assert questions[1]["prompt"] == "Severity" and questions[1]["default"] == ["high"]
    assert questions[2]["prompt"] == "Name" and questions[3]["id"] == "notes"
    assert len({question["id"] for question in questions}) == 4
    assert sum(1 for kind, _ in blocks if kind == "field") == 4
    status, _, served = request("GET", "/api/reports/fields/html")
    served = json.loads(served)
    assert status == 200 and served["fields"] == 4
    assert served["html"].count("data-field=") == 4
    assert 'type="radio"' in served["html"] and 'type="checkbox"' in served["html"]
    assert "- [ ] not a field" in served["html"]
    assert served["html"].count("checked") == 2
    status, _, page = request("GET", "/")
    assert status == 200 and '#preview-note[aria-pressed="false"] {' in page
    assert '#preview-note[aria-pressed="true"]' not in page
    duplicate = root / "duplicate.md"
    duplicate.write_text("Areas:\n\n- [ ] ui\n- [ ] ui\n", encoding="utf-8")
    try:
      preview.parse_fields(duplicate.read_text(encoding="utf-8"))
      raise AssertionError("Duplicate options accepted")
    except ValueError:
      pass
    assert (
      request(
        "POST",
        "/api/reports/fields/submit",
        json.dumps({"id": "r1", "answers": {"severity": "extreme"}}),
        auth,
      )[0]
      == 400
    )
    assert (
      request("POST", "/api/reports/first/submit", '{"id":"r2","answers":{}}', auth)[0]
      == 400
    )
    report_answer = json.dumps(
      {
        "id": "report-sub-1",
        "answers": {"pick-the-areas": ["ui"], "severity": "high", "name": "ada"},
      }
    )
    assert request("POST", "/api/reports/fields/submit", report_answer, auth)[0] == 201
    assert not [
      row for row in store.state()["notes"] if row["text"].startswith("REPORT")
    ]
    answered = store.submissions()[-1]["text"]
    assert "Fielded:" in answered and "name: ada" in answered
    assert "severity: high" in answered and "notes: (skipped)" in answered
    for broken in (
      [],
      [{"id": "a", "type": "text", "prompt": "x"}] * 51,
      [
        {"id": "a", "type": "text", "prompt": "x"},
        {"id": "a", "type": "text", "prompt": "y"},
      ],
      [{"id": "a b", "type": "text", "prompt": "x"}],
      [{"id": "a", "type": "text", "prompt": ""}],
      [{"id": "a", "type": "text", "prompt": "x" * 501}],
      [{"id": "a", "type": "choice", "prompt": "x", "options": []}],
      [{"id": "a", "type": "choice", "prompt": "x", "options": ["o"] * 21}],
      [{"id": "a", "type": "checkbox", "prompt": "x", "options": ["ui", "ui"]}],
      [{"id": "a", "type": "checkbox", "prompt": "x", "options": [" "]}],
      [{"id": "a", "type": "checkbox", "prompt": "x", "options": ["o" * 201]}],
    ):
      try:
        preview.Store.validate_fields(broken)
        raise AssertionError(f"Invalid fields accepted: {broken}")
      except ValueError:
        pass
    preview.Store.validate_fields(
      [{"id": "a", "type": "choice", "prompt": "x", "options": ["only"]}]
    )
    assert request("GET", "/api/forms/f1")[0] == 404
    assert (
      request("POST", "/api/forms/f1/submit", '{"id":"s1","answers":{}}', auth)[0]
      == 404
    )
    assert (
      request("POST", "/api/reports/fields/submit", "{}", {"X-Preview-Token": token})[0]
      == 415
    )
    assert (
      request(
        "POST",
        "/api/reports/fields/submit",
        json.dumps({"id": "s1", "answers": {"name": "x"}}),
      )[0]
      == 403
    )
    for bad in (
      {"id": "s1", "answers": {"name": "x", "nope": "unknown"}},
      {"id": "s1", "answers": {"severity": "extreme"}},
      {"id": "s1", "answers": {"pick-the-areas": ["ui", "core"]}},
      {"id": "s1", "answers": {"name": "x" * 2001}},
      {"id": "s1", "answers": "nope"},
    ):
      assert (
        request("POST", "/api/reports/fields/submit", json.dumps(bad), auth)[0] == 400
      )
    sent = store.submissions()
    submission = json.dumps(
      {
        "id": "sub-1",
        "answers": {
          "name": "it broke",
          "severity": "high",
          "pick-the-areas": ["ui"],
        },
      }
    )
    assert request("POST", "/api/reports/fields/submit", submission, auth)[0] == 201
    pending = [
      row for row in store.read()["pending"] if row["text"].startswith("REPORT fields")
    ]
    assert len(pending) == len(sent) + 1
    assert pending[-1]["kind"] == "report"
    answered = pending[-1]["text"]
    assert (
      "Fielded:" in answered
      and "name: it broke" in answered
      and "severity: high" in answered
      and "pick-the-areas: ui" in answered
      and "notes: (skipped)" in answered
    )
    assert request("POST", "/api/reports/fields/submit", submission, auth)[0] == 201
    assert len(store.submissions()) == len(sent) + 1
    store.acknowledge([pending[-1]["id"]], "note", "read")
    assert pending[-1]["id"] not in {row["id"] for row in store.read()["pending"]}
    assert (
      request(
        "POST",
        "/api/reports/fields/submit",
        json.dumps({"id": "sub-1", "answers": {"name": "changed"}}),
        auth,
      )[0]
      == 400
    )
  finally:
    app.shutdown()
    app.server_close()
    worker.join()
print(
  "PASS: durable notes, retry dedup, receipts carrying a rendered reply or a plain note, state migration, reports, Markdown fields with inbox-answer submissions, safe rendering, errors and HTTP boundaries"
)

with tempfile.TemporaryDirectory() as legacy_dir:
  legacy = Path(legacy_dir)
  db = sqlite3.connect(legacy / "state.sqlite3")
  db.execute(
    """CREATE TABLE notes (
      seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
      text TEXT NOT NULL, at TEXT NOT NULL, acknowledged_at TEXT
    )"""
  )
  db.execute(
    "INSERT INTO notes (id, text, at) VALUES ('old', 'kept', '2026-01-01T00:00:00+00:00')"
  )
  db.commit()
  db.close()
  migrated = preview.Store(legacy, create=True)
  assert [row["id"] for row in migrated.state()["notes"]] == ["old"]
  migrated.acknowledge(["old"], "note", "still here")
  assert migrated.state()["notes"][0]["ack_text"] == "still here"
