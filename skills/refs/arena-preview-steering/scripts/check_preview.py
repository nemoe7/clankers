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
    try:
      store.acknowledge(["message-1", "unknown"])
      raise AssertionError("Unknown receipt accepted")
    except ValueError:
      assert store.read()["pending"]
    store.acknowledge(["message-1"])
    stamp = store.state()["notes"][0]["acknowledged_at"]
    store.acknowledge(["message-1"])
    assert store.state()["notes"][0]["acknowledged_at"] == stamp
    assert preview.Store(root).read()["pending"] == []
    assert len(preview.Store(root).state()["notes"]) == 1
    status, _, state_body = request("GET", "/api/state")
    assert status == 200
    assert "&lt;script&gt;" in json.loads(state_body)["notes"][0]["html"]
    status, _, rendered = request("GET", "/api/reports/first/html")
    assert status == 200 and "<table>" in rendered and "<script>" not in rendered
    assert 'href="javascript:' not in rendered
    status, headers, exported = request("GET", "/api/reports/first/export")
    assert status == 200 and "<!doctype html>" in exported and "<style>" in exported
    assert (
      "First &lt;report&gt;" in exported
      and "attachment;" in headers["Content-Disposition"]
    )
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
    form_source = root / "form.json"
    form_source.write_text(
      json.dumps(
        {
          "questions": [
            {"id": "q1", "type": "text", "prompt": "What happened?"},
            {
              "id": "q2",
              "type": "choice",
              "prompt": "Severity",
              "options": ["low", "high"],
            },
            {
              "id": "q3",
              "type": "checkbox",
              "prompt": "Areas",
              "options": ["ui", "api"],
            },
          ]
        }
      ),
      encoding="utf-8",
    )
    store.publish_form("f1", "Smoke <test>", form_source)
    assert len(store.state()["forms"]) == 1
    for broken in (
      {"questions": []},
      {"questions": [{"id": "a", "type": "rating", "prompt": "x"}]},
      {
        "questions": [{"id": "a", "type": "choice", "prompt": "x", "options": ["only"]}]
      },
      {
        "questions": [{"id": "a", "type": "text", "prompt": "x", "options": ["a", "b"]}]
      },
      {
        "questions": [
          {"id": "a", "type": "text", "prompt": "x"},
          {"id": "a", "type": "text", "prompt": "y"},
        ]
      },
    ):
      try:
        preview.Store.validate_form(broken)
        raise AssertionError(f"Invalid form accepted: {broken}")
      except ValueError:
        pass
    bad_source = root / "bad.json"
    bad_source.write_text("not json", encoding="utf-8")
    try:
      store.publish_form("f2", "Bad", bad_source)
      raise AssertionError("Non-JSON form accepted")
    except ValueError:
      pass
    status, _, form_body = request("GET", "/api/forms/f1")
    assert status == 200
    served = json.loads(form_body)
    assert served["title"] == "Smoke <test>" and len(served["questions"]) == 3
    assert request("GET", "/api/forms/missing")[0] == 404
    assert (
      request("POST", "/api/forms/f1/submit", "{}", {"X-Preview-Token": token})[0]
      == 415
    )
    assert (
      request(
        "POST", "/api/forms/f1/submit", json.dumps({"id": "s1", "answers": {"q1": "x"}})
      )[0]
      == 403
    )
    for bad in (
      {"id": "s1", "answers": {"q1": "x", "q9": "nope"}},
      {"id": "s1", "answers": {"q2": "severe"}},
      {"id": "s1", "answers": {"q3": ["ui", "core"]}},
      {"id": "s1", "answers": {"q1": "x" * 2001}},
      {"id": "s1", "answers": "nope"},
    ):
      assert request("POST", "/api/forms/f1/submit", json.dumps(bad), auth)[0] == 400
    answers = {"q1": "it broke", "q2": "high", "q3": ["ui"]}
    submission = json.dumps({"id": "sub-1", "answers": answers})
    assert request("POST", "/api/forms/f1/submit", submission, auth)[0] == 201
    form_notes = [
      row for row in store.read()["pending"] if row["text"].startswith("FORM f1")
    ]
    assert len(form_notes) == 1
    form_text = form_notes[0]["text"]
    assert (
      "Smoke <test>:" in form_text
      and "q1: it broke" in form_text
      and "q2: high" in form_text
      and "q3: ui" in form_text
    )
    assert request("POST", "/api/forms/f1/submit", submission, auth)[0] == 201
    assert (
      len([row for row in store.state()["notes"] if row["text"].startswith("FORM f1")])
      == 1
    )
    assert (
      request(
        "POST",
        "/api/forms/f1/submit",
        json.dumps({"id": "sub-1", "answers": {"q1": "changed"}}),
        auth,
      )[0]
      == 400
    )
  finally:
    app.shutdown()
    app.server_close()
    worker.join()
print(
  "PASS: durable notes, retry dedup, explicit receipts, reports, export, safe rendering, forms with inbox-answer submissions, errors and HTTP boundaries"
)
