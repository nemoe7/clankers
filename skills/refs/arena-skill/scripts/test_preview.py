"""Pytest checks for the preview runtime. Run with the reporting venv's Python."""

import base64
import builtins
import hashlib
import html
import http.client
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

import preview
import pytest

# The installed hook shell exports both markers, and a spawned CLI would answer as if it
# sat inside the hook. Drop them here. A test that needs one sets it itself.
for _marker in ("ARENA_PREVIEW_ROUTE", "ARENA_PREVIEW_SHELL_HOOK"):
  os.environ.pop(_marker, None)

_GUARD_LISTENER = None
_GUARD_PORT = None
CHECKPOINT_INTERVAL = timedelta(minutes=15)


def test_survey_transport_keeps_grades_in_server_memory(tmp_path, monkeypatch, capsys):
  import survey

  global app
  store = preview.Store(tmp_path, create=True)
  headers = {"Content-Type": "application/json"}
  payload = json.dumps(survey.template())
  expected = [
    {"id": row["id"], "correct": index == 1, "confidence": row["confidence"]}
    for index, row in enumerate(survey.loads(payload))
  ]

  def grade(text):
    survey.loads(text)
    return expected

  monkeypatch.setattr(survey, "grade", grade)
  app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
  store.set_meta("port", str(app.server_port))
  threading.Thread(target=app.serve_forever, daemon=True).start()
  try:
    status, _, body = request("GET", "/api/survey")
    assert status == 200
    assert json.loads(body) == {"results": None, "answered_at": None}
    for _ in range(2):
      status, _, body = request("POST", "/api/survey/request", "{}", headers)
      assert status == 200
      assert json.loads(body) == {"ok": True}
    pending = store.read()["pending"]
    assert len(pending) == 1
    assert pending[0]["quiet"] and pending[0]["blocking"]
    assert all(
      token in survey.INSTRUCTIONS
      for token in ("NEVER", "web_search", "fetch_page", "image_search")
    )
    assert survey.INSTRUCTIONS in pending[0]["text"]
    snapshot = store.save_path.read_bytes()
    for body in ("[]", payload.replace('"confidence": 0', '"confidence": 2')):
      status, _, _ = request("POST", "/api/survey", body, headers)
      assert status == 400
    status, _, body = request("POST", "/api/survey", payload, headers)
    assert status == 200 and json.loads(body) == {"ok": True}
    assert store.save_path.read_bytes() == snapshot
    status, _, body = request("GET", "/api/survey")
    assert status == 200
    received = json.loads(body)
    assert received["results"] == expected
    answered_at = received["answered_at"]
    assert datetime.fromisoformat(answered_at).tzinfo is not None
    store.acknowledge([pending[0]["id"]], "Survey complete.")
    prior_notes = store.state()["notes"]
    for _ in range(2):
      status, _, _ = request("POST", "/api/survey/request", "{}", headers)
      assert status == 200
    again = store.read()["pending"]
    assert len(again) == 1 and again[0]["id"] != pending[0]["id"]
    assert again[0]["quiet"] and again[0]["blocking"]
    assert "Bible checkpoint." in again[0]["text"]
    assert survey.INSTRUCTIONS in again[0]["text"]
    assert [
      row for row in store.state()["notes"] if row["id"] != again[0]["id"]
    ] == prior_notes
    status, _, body = request("GET", "/api/survey")
    assert status == 200 and json.loads(body) == received
    for path in ("/api/state", "/api/copy-state"):
      status, _, body = request("GET", path)
      assert status == 200 and '"correct"' not in body
      assert '"answered_at"' not in body
    assert '"correct"' not in store.save_path.read_text()
    script = str(Path(preview.__file__))
    monkeypatch.setenv("ARENA_PREVIEW_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", [script, "survey"])
    assert preview.main() == 0
    printed = capsys.readouterr().out
    assert all(question["id"] in printed for question in survey.SPEC["questions"])
    assert all(digest not in printed for digest in survey.HASHES.values())
    monkeypatch.setattr(sys, "argv", [script, "survey", payload])
    assert preview.main() == 0
    receipt = capsys.readouterr().out
    assert '"correct"' not in receipt and not any(
      row["id"] in receipt for row in expected
    )
  finally:
    app.shutdown()
    app.server_close()
  fresh_handler = preview.handler(store)
  app = preview.ThreadingHTTPServer(("127.0.0.1", 0), fresh_handler)
  threading.Thread(target=app.serve_forever, daemon=True).start()
  try:
    status, _, body = request("GET", "/api/survey")
    assert status == 200
    assert json.loads(body) == {"results": None, "answered_at": None}
    status, _, body = request("POST", "/api/survey/request", "{}", headers)
    assert status == 200
    assert len(store.read()["pending"]) == len(pending)
  finally:
    app.shutdown()
    app.server_close()


@pytest.mark.parametrize(
  "violation_type", ("self-raised", "bash-violation", "legacy-type")
)
def test_survey_requests_are_not_violations(tmp_path, violation_type):
  store = preview.Store(tmp_path / "state", create=True)
  (tmp_path / "ARENA.md").write_text("# Rules\n", encoding="utf-8")
  request_id = "survey-note"
  store.note(request_id, "Answer request", quiet=True, blocking=True, type="survey")
  assert store.pending_violation_note() is None
  assert store.pending_read_set_note() is None
  assert store.pending_ack() == request_id
  store.flag_violation_note("Violation", violation_type, "ARENA.md", "Rules")
  violation = store.pending_violation_note()
  assert violation["id"] != request_id
  assert violation["type"] == violation_type
  with pytest.raises(ValueError, match="clause"):
    store.acknowledge([request_id, violation["id"]], "Received")
  assert all(row["acknowledged_at"] is None for row in store.read()["pending"])
  store.acknowledge([violation["id"]], "ARENA.md:1: Rules")
  assert store.meta_value(preview.AGENT_INTERRUPT_FLAG_META) is None
  assert store.pending_ack() == request_id
  store.acknowledge([request_id], "Received")
  assert store.read()["pending"] == []


def test_only_latest_report_submission_requires_ack(tmp_path):
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  form = tmp_path / "form.md"
  form.write_text("Choice: {#choice}\n\n- ( ) Yes\n- ( ) No\n")
  for report_id in ("first-form", "other-form"):
    store.publish(report_id, report_id, form)
  store.submission("kept-receipt", "first-form", "REPORT first-form: first")
  store.acknowledge(["kept-receipt"], "Kept reply")
  store.submission("older-answer", "first-form", "REPORT first-form: second")
  store.submission("latest-answer", "first-form", "REPORT first-form: third")
  store.submission("other-answer", "other-form", "REPORT other-form: first")
  pending_ids = {row["id"] for row in store.read()["pending"]}
  assert pending_ids == {"latest-answer", "other-answer"}
  with store.connect() as db:
    assert preview.gate_pending_count(db) == len(pending_ids)
  with pytest.raises(ValueError):
    store.pending_ack()
  store.acknowledge(["other-answer"], "Other reply")
  assert store.pending_ack() == "latest-answer"
  store.acknowledge(["latest-answer"], "Latest reply")
  assert not store.read()["pending"]
  with store.connect() as db:
    assert not preview.gate_pending_count(db)
  records = {row["id"]: row for row in store.submissions()}
  assert records["older-answer"]["acknowledged_at"] is None
  assert records["kept-receipt"]["ack_text"] == "Kept reply"
  assert records["latest-answer"]["ack_text"] == "Latest reply"
  state = store.state()
  first = next(row for row in state["reports"] if row["id"] == "first-form")
  assert {row["id"] for row in first["acknowledgements"]} == {
    "kept-receipt",
    "latest-answer",
  }
  store.write_task(
    "finished-form",
    "Done",
    ["Work"],
    status="finished",
    report_id="first-form",
    task_type="code",
  )
  assert "first-form" in {row["id"] for row in store.stale_reports()}
  store.mark_report_ack_seen("first-form")
  store.unpublish("first-form")
  assert set(records) == {row["id"] for row in store.submissions()}
  store.submission("newer-answer", "other-form", "REPORT other-form: second")
  assert store.pending_ack() == "newer-answer"


def guard_port():
  """Return a listening test port, held for the process, that passes the server guard."""
  global _GUARD_LISTENER, _GUARD_PORT
  if _GUARD_PORT is None:
    _GUARD_LISTENER = socket.socket()
    _GUARD_LISTENER.bind(("127.0.0.1", 0))
    _GUARD_LISTENER.listen(8)
    _GUARD_PORT = str(_GUARD_LISTENER.getsockname()[1])

    def drain():
      # Every guard probe connects and closes. Without an accept the pending
      # slots pile up and a later probe sees a refused port.
      while True:
        try:
          connection, _ = _GUARD_LISTENER.accept()
          connection.close()
        except OSError:
          return

    threading.Thread(target=drain, daemon=True).start()
  return _GUARD_PORT


def request(method, path, body=None, headers=None, raw=False):
  client = http.client.HTTPConnection("127.0.0.1", app.server_port, timeout=5)
  client.request(method, path, body, headers or {})
  response = client.getresponse()
  data = response.read()
  # An upload comes back as the bytes it stored, so a caller can ask for those instead of text.
  result = response.status, dict(response.getheaders()), data if raw else data.decode()
  client.close()
  return result


def compact(text):
  """Collapse the whitespace a minifier would, so one literal reads both asset forms."""
  return re.sub(r"\s*([{};:,><!])\s*", r"\1", text)


def live_detached_placeholder(state_dir, name, argv):
  """Record this test process as a live routed child."""
  path = preview.write_detached_placeholder(state_dir, name, argv)
  record = json.loads(path.read_text(encoding="utf-8"))
  record.update(
    {"pid": os.getpid(), "pid_started_at": preview.process_start_identity(os.getpid())}
  )
  preview.write_run_record(path, record)
  return path


def test_edited_ack_stamp():
  "A second ack appends a reply block. The first answer stays."
  with tempfile.TemporaryDirectory() as edit_dir:
    edited = preview.Store(edit_dir, create=True)
    edited.set_meta("port", guard_port())
    edited.note("edit-note", "Question")
    edited.submission("edit-answer", "form", "REPORT form: answer")
    ids = ["edit-note", "edit-answer"]
    with patch.object(preview, "now", return_value="2026-09-22T12:00:00"):
      edited.acknowledge(ids, "First answer")
    first = edited.state()["notes"][0]
    assert first["ack_edited_at"] is None and first["replies"] == []
    with patch.object(preview, "now", return_value="2026-09-22T12:01:00"):
      edited.acknowledge(ids, "Second answer")
    row = edited.state()["notes"][0]
    assert row["acknowledged_at"] == "2026-09-22T12:00:00"
    assert row["ack_text"] == "First answer", "the first answer is not replaced"
    assert row["ack_edited_at"] == "2026-09-22T12:01:00"
    assert row["replies"] == [
      {"type": "reply", "text": "Second answer", "at": "2026-09-22T12:01:00"}
    ]
    answer = edited.submissions()[0]
    assert answer["ack_edited_at"] == row["ack_edited_at"]
    assert answer["replies"] == row["replies"]
    with patch.object(preview, "now", return_value="2026-09-22T12:02:00"):
      edited.acknowledge(ids, "Second answer")
    row = edited.state()["notes"][0]
    assert row["ack_edited_at"] == "2026-09-22T12:02:00"
    assert [reply["type"] for reply in row["replies"]] == ["reply", "reply"]
    assert preview.Store(edit_dir).state()["notes"][0]["replies"] == row["replies"]
    with_html = preview.Store(edit_dir).state()["notes"][0]
    assert "html" not in with_html["replies"][0], (
      "the state parses replies; the page route renders"
    )
    saved = Path(edit_dir) / "edited.ndjson"
    saved.write_text(json.dumps(preview.saved_note_line(row)) + "\n")
    restored_dir = Path(edit_dir) / "restored"
    restored = preview.Store(restored_dir, create=True)
    restored.set_meta("port", guard_port())
    subprocess.run(
      [
        sys.executable,
        preview.__file__,
        "state",
        "import",
        str(saved),
      ],
      check=True,
      capture_output=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(restored_dir)},
    )
    assert restored.state()["notes"][0]["ack_edited_at"] == row["ack_edited_at"]
    assert restored.state()["notes"][0]["replies"] == row["replies"], (
      "a restore carries every appended reply block"
    )
    receipt = {
      "acknowledged_at": "2026-09-22T12:00:00",
      "ack_type": "reply",
      "ack_text": "First",
    }
    for flaw, replies in (
      ("no receipt", None),
      ("not a list", {"type": "reply", "text": "x", "at": "2026-09-22T12:01:00"}),
      ("no type", [{"text": "x", "at": "2026-09-22T12:01:00"}]),
      ("bad stamp", [{"type": "reply", "text": "x", "at": "yesterday"}]),
      ("empty text", [{"type": "note", "text": " ", "at": "2026-09-22T12:01:00"}]),
    ):
      try:
        if flaw == "no receipt":
          restored.note(
            "invalid-replies",
            "Question",
            replies=[{"type": "reply", "text": "x", "at": "2026-09-22T12:01:00"}],
          )
        else:
          restored.note("invalid-replies", "Question", replies=replies, **receipt)
        raise AssertionError(f"Invalid replies accepted: {flaw}")
      except (ValueError, TypeError):
        pass
    assert restored.note("invalid-replies", "Question")["replies"] == [], (
      "a refused restore wrote nothing"
    )
    for bad in ("not-a-date", "2026-09-22T12:00:00"):
      try:
        restored.note("invalid-edit", "No receipt", ack_edited_at=bad)
        raise AssertionError("Invalid edit receipt accepted")
      except ValueError:
        pass


def test_reply_seen_persistence():
  """Persist viewed reply counts for notes and answers, including same-second replies."""
  global app
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "arena-preview"
    backup = Path(directory) / "saved-state.ndjson"
    store = preview.Store(root, create=True, save_path=backup)
    store.set_meta("port", guard_port())
    store.note("edited-note", "Question")
    form = Path(directory) / "form.md"
    form.write_text("# Form\n\nNo fields here.\n", encoding="utf-8")
    store.publish("form", "Form", form)
    store.submission("edited-answer", "form", "REPORT form: answer")
    ids = ["edited-note", "edited-answer"]
    with patch.object(preview, "now", return_value="2026-09-22T12:00:00"):
      store.acknowledge(ids, "First answer")
    with patch.object(preview, "now", return_value="2026-09-22T12:01:00"):
      store.acknowledge(ids, "Second answer")

    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    worker = threading.Thread(target=app.serve_forever, daemon=True)
    worker.start()
    headers = {"Content-Type": "application/json"}
    try:
      for record_id in ids:
        status, _, body = request(
          "POST",
          f"/api/messages/{record_id}/replies/seen",
          json.dumps({"count": 1}),
          headers,
        )
        assert status == 200
        assert json.loads(body) == {"id": record_id, "ack_edited_seen_count": 1}

      # The next two replies share a timestamp with the previous reply. Count, not time,
      # distinguishes the unseen blocks and keeps the earlier seen marker intact.
      with patch.object(preview, "now", return_value="2026-09-22T12:01:00"):
        store.acknowledge(ids, "Third answer")
      note = preview.Store(root).state()["notes"][0]
      answer = preview.Store(root).submissions()[0]
      assert len(note["replies"]) == 2 and len(answer["replies"]) == 2
      assert note["replies"][0]["at"] == note["replies"][1]["at"]
      assert note["ack_edited_seen_count"] == answer["ack_edited_seen_count"] == 1

      for record_id in ids:
        status, _, body = request(
          "POST",
          f"/api/messages/{record_id}/replies/seen",
          json.dumps({"count": 2}),
          headers,
        )
        assert status == 200
        assert json.loads(body)["ack_edited_seen_count"] == 2
      status, _, body = request(
        "POST",
        "/api/messages/edited-note/replies/seen",
        json.dumps({"count": 1}),
        headers,
      )
      assert status == 200 and json.loads(body)["ack_edited_seen_count"] == 2, (
        "an older page cannot move the seen count backwards"
      )
      assert (
        request(
          "POST",
          "/api/messages/edited-note/replies/seen",
          json.dumps({"count": 3}),
          headers,
        )[0]
        == 400
      )
      assert (
        request(
          "POST",
          "/api/messages/missing/replies/seen",
          json.dumps({"count": 0}),
          headers,
        )[0]
        == 404
      )
      assert (
        request(
          "POST",
          "/api/messages/edited-note/replies/seen",
          json.dumps({"count": True}),
          headers,
        )[0]
        == 400
      )

      reopened = preview.Store(root)
      assert reopened.state()["notes"][0]["ack_edited_seen_count"] == 2
      assert reopened.submissions()[0]["ack_edited_seen_count"] == 2
      saved = reopened.save_state({"notes": reopened.state()["notes"]})
      assert saved["notes"] == 1 and saved["answers"] == 1
      saved_lines = [
        json.loads(line)
        for line in backup.read_text().splitlines()
        if "ack_edited_seen_count" in line
      ]
      assert [line["ack_edited_seen_count"] for line in saved_lines] == [2, 2]

      restored_dir = Path(directory) / "restored"
      preview.Store(restored_dir, create=True).set_meta("port", guard_port())
      subprocess.run(
        [
          sys.executable,
          preview.__file__,
          "state",
          "import",
          str(backup),
        ],
        check=True,
        capture_output=True,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(restored_dir)},
      )
      assert (
        preview.Store(restored_dir).state()["notes"][0]["ack_edited_seen_count"] == 2
      )
      assert preview.Store(restored_dir).submissions()[0]["ack_edited_seen_count"] == 2
    finally:
      app.shutdown()
      app.server_close()
      worker.join(timeout=5)


def test_report_receipt_ids():
  with tempfile.TemporaryDirectory() as receipts_dir:
    receipt_store = preview.Store(receipts_dir, create=True)
    report_source = Path(receipts_dir) / "receipt.md"
    report_source.write_text(
      "# Receipt\n\nDecision? {#decision}\n- (x) Yes\n- ( ) No\nCustom response: ___\n"
    )
    receipt_store.publish("receipt", "Receipt", report_source)
    report = receipt_store.state()["reports"][0]
    assert report["latest_answer_at"] is None
    assert report["latest_answer_id"] is None
    assert report["latest_answer_acknowledged_at"] is None
    receipt_store.submission("answer-one", "receipt", "REPORT receipt: Yes")
    report = receipt_store.state()["reports"][0]
    assert report["latest_answer_at"] == preview.clip_stamp(
      receipt_store.submissions()[-1]["at"]
    )
    assert report["latest_answer_id"] == "answer-one"
    assert report["latest_answer_acknowledged_at"] is None
    assert "REPORT receipt: Yes" not in json.dumps(report)
    receipt_store.acknowledge(["answer-one"], "Received")
    report = receipt_store.state()["reports"][0]
    assert report["latest_answer_acknowledged_at"] == preview.clip_stamp(
      receipt_store.submissions()[-1]["acknowledged_at"]
    )
    receipt_store.acknowledge(["answer-one"], "Second reply")
    history = receipt_store.state()["reports"][0]["acknowledgements"]
    assert history[0]["ack_text"] == "Received"
    assert history[0]["replies"][0]["text"] == "Second reply"
    assert "text" not in history[0]
    receipt_store.submission("answer-two", "receipt", "REPORT receipt: No")
    report = receipt_store.state()["reports"][0]
    assert report["latest_answer_id"] == "answer-two", "use the new submission's ID"
    assert report["latest_answer_acknowledged_at"] is None, (
      "an earlier ack must not cover a new answer"
    )


@pytest.mark.parametrize("mode", ["agent", "owner", "pending-stale", "rejected"])
def test_unpublish_releases_only_linked_tasks(tmp_path, monkeypatch, mode):
  store = preview.Store(tmp_path / "state", create=True)
  source = tmp_path / "question.md"
  source.write_text("Choose: {#choice}\n\n- ( ) Yes\n- ( ) No\n")
  for report in ("question", "other"):
    store.publish(report, report, source)
    store.write_task(
      "wait-" + report,
      report,
      ["Await the decision"],
      task_type="code",
      report_id=report,
      blocked=True,
    )
  assert store.task_record("wait-question")["blocked"] is True
  if mode == "rejected":

    def refuse(*args, **kwargs):
      raise ValueError("held")

    monkeypatch.setattr(store, "guard_report_change", refuse)
    with pytest.raises(ValueError, match="held"):
      store.unpublish("question")
  else:
    result = store.unpublish(
      "question",
      dismissed_by_owner=mode == "owner",
      stale_only=mode == "pending-stale",
    )
    if mode == "pending-stale":
      assert result is False
  released = mode in ("agent", "owner")
  task = store.task_record("wait-question")
  assert task["blocked"] is not released
  assert task["status"] == "upcoming"
  assert task["report_id"] == "question"
  assert store.task_record("wait-other")["blocked"] is True
  assert source.exists()
  assert ("question" in {r["id"] for r in store.state()["reports"]}) is not released


def test_report_unpublish():
  "Removing a report prunes the tab row only. Answers and the source file stay."
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    source = Path(directory) / "select.md"
    source.write_text(
      "# Select\n\nChoice? {#select}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("select", "Select one", source)
    store.submission("answer-1", "select", "REPORT select: one")
    # The owner can dismiss an unseen report even while its answer remains unacknowledged.
    store.unpublish("select", dismissed_by_owner=True)
    assert store.state()["reports"] == []
    try:
      store.report("select")
      raise AssertionError("A deleted report still read back")
    except FileNotFoundError:
      pass
    try:
      store.unpublish("select")
      raise AssertionError("Deleting the same report twice was accepted")
    except FileNotFoundError:
      pass
    assert store.submissions()[0]["report_id"] == "select", "sent answers are history"
    assert source.exists(), "the .md source stays for republishing"
    try:
      store.publish("select", "Select again", source)
      raise AssertionError("Republishing over sent answers was accepted")
    except ValueError:
      pass
    # The agent CLI can unpublish an unseen report and writes no dismissal note.
    store.publish("plain", "Select one", source)
    allowed = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "report", "unpublish", "plain"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": directory},
    )
    assert allowed.returncode == 0, allowed.stderr
    assert "Unpublished plain." in allowed.stdout
    assert store.state()["reports"] == []
    assert len(store.state()["notes"]) == 1, "the CLI unpublish writes no note"
    # An unacknowledged answer still holds the agent CLI path.
    store.publish("blocked", "Select one", source)
    store.submission("answer-2", "blocked", "REPORT blocked: one")
    held = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "report", "unpublish", "blocked"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": directory},
    )
    assert held.returncode == 1
    assert "unacknowledged answer" in held.stderr
    assert [report["id"] for report in store.state()["reports"]] == ["blocked"]


def test_submission_format_preserves_custom_type_and_raw_text(tmp_path):
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  source = tmp_path / "form.md"
  source.write_text(
    "Sum? {#sum}\n\n- ( ) 2\n- ( ) 3\n- ( ) custom: ___\n\n"
    "Checks? {#checks}\n\n- [ ] Unit\n- [ ] Browser\n- [ ] custom: ___\n",
    encoding="utf-8",
  )
  format = {
    "fields": {
      "sum": {"question": "What is 1+1?", "answers": {"2": "1+1=2"}},
      "checks": {"answers": {"Unit": "Run unit tests"}},
    },
    "template": "{sum.answer}\nChecks: {checks.answer}",
  }
  store.publish("mapped", "Mapped", source, submission_format=format)
  revision = store.report("mapped")["updated_at"]
  preset = {"sum": {"type": "preset", "value": "2"}}
  answer = store.submit_report("mapped", "preset", preset, revision)
  assert answer["text"] == "REPORT mapped Mapped:\n1+1=2\nChecks: (skipped)"
  raw = "  2\n{sum.answer}, <script>  "
  custom = {
    "sum": {"type": "custom", "label": "custom", "value": raw},
    "checks": [
      {"type": "preset", "value": "Unit"},
      {"type": "custom", "label": "custom", "value": "Phone, and tablet"},
    ],
  }
  answer = store.submit_report("mapped", "custom-reply", custom, revision)
  assert raw in answer["text"]
  assert "Checks: Run unit tests, Phone, and tablet" in answer["text"]
  assert answer["answer_data"] == {"revision": revision, "answers": custom}
  lines, _ = store.state_lines(store.state()["notes"], store.tasks() or {})
  restored = preview.Store(tmp_path / "restored", create=True)
  restored.import_state("\n".join(json.dumps(row) for row in lines))
  assert restored.report("mapped")["submission_format"] == format
  kept = next(row for row in restored.submissions() if row["id"] == "custom-reply")
  assert kept["text"] == answer["text"] and kept["answer_data"] == answer["answer_data"]
  with pytest.raises(ValueError):
    store.submit_report("mapped", "empty", {}, revision)
  with pytest.raises(ValueError):
    store.publish(
      "invalid", "Invalid", source, submission_format={"template": "{missing.answer}"}
    )
  assert all(row["id"] != "invalid" for row in store.report_sources())
  collision = {"sum": {"type": "custom", "label": "custom", "value": "2"}}
  answer = store.submit_report("mapped", "collision", collision, revision)
  assert answer["text"] == "REPORT mapped Mapped:\n2\nChecks: (skipped)"
  wrapped = {
    "fields": {"sum": {"custom_answer": "Raw: {custom}"}},
    "template": "{sum.answer}",
  }
  store.publish("wrapped", "Wrapped", source, submission_format=wrapped)
  answer = store.submit_report(
    "wrapped", "wrapped-answer", custom, store.report("wrapped")["updated_at"]
  )
  assert answer["text"] == "REPORT wrapped Wrapped:\nRaw: " + raw
  with (
    patch("preview.MAX_REPORT", len(raw.encode("utf-8"))),
    pytest.raises(ValueError, match="Expanded submission"),
  ):
    preview.expand_submission_template("{custom}{custom}", {"custom": raw})
  _, fields = preview.parse_fields("Choice? {#auto}\n\n- ( ) One\n- ( ) Two\n")
  assert any(
    preview.custom_label(option) is not None for option in fields[0]["options"]
  )
  assert "Something else..." in preview.field_html(fields[0])

  store.publish("unmapped", "Unmapped", source)
  with pytest.raises(ValueError, match="at least one answer"):
    store.submit_report(
      "unmapped", "empty-unmapped", {}, store.report("unmapped")["updated_at"]
    )

  for invalid in (
    {"fields": {"missing": {}}},
    {"fields": {"sum": {"answers": {"4": "Wrong preset"}}}},
    {"fields": {"sum": {"custom_answer": "{sum.answer}"}}},
    {"template": " "},
  ):
    with pytest.raises(ValueError):
      store.publish("bad-format", "Invalid", source, submission_format=invalid)
  for invalid in (
    {"type": "custom", "label": "custom", "value": " "},
    {"type": "custom", "label": "missing", "value": "2"},
    {"type": "preset", "value": "4"},
  ):
    with pytest.raises(ValueError):
      store.submit_report("mapped", "bad-answer", {"sum": invalid}, revision)

  for repeated in (
    ["Unit", {"type": "preset", "value": "Unit"}],
    [
      {"type": "custom", "label": "custom", "value": "First"},
      {"type": "custom", "label": "custom", "value": "Second"},
    ],
  ):
    with pytest.raises(ValueError, match="repeated selections"):
      store.submit_report("mapped", "repeated", {"checks": repeated}, revision)


def test_submission_format_cli(tmp_path):
  store = preview.Store(tmp_path, create=True)
  source = tmp_path / "form.md"
  source.write_text("Pick? {#pick}\n\n- ( ) One\n", encoding="utf-8")
  format = {"fields": {"pick": {"answers": {"One": "Selected one"}}}}
  metadata = tmp_path / "format.json"
  metadata.write_text(json.dumps(format), encoding="utf-8")
  server = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
  store.set_meta("port", str(server.server_port))
  worker = threading.Thread(target=server.serve_forever, daemon=True)
  worker.start()
  try:
    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "report",
        "publish",
        str(source),
        "--id",
        "cli-format",
        "--title",
        "CLI format",
        "--submission-format",
        str(metadata),
      ],
      capture_output=True,
      check=False,
      text=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert store.report("cli-format")["submission_format"] == format
  finally:
    server.shutdown()
    server.server_close()
    worker.join()


def test_stale_report_task_completion_idle_and_pins(tmp_path):
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  source = tmp_path / "report.md"
  source.write_text("Information\n", encoding="utf-8")
  store.publish("solo", "Solo", source)
  assert store.stale_reports() == [], "a fresh unlinked report stays active"
  idle = timedelta(minutes=30)
  past = (datetime.now(timezone.utc) - idle - timedelta(seconds=1)).isoformat()
  with store.connect() as db, db:
    db.execute("UPDATE reports SET updated_at = ?", (past,))
  assert {row["id"] for row in store.stale_reports()} == {"solo"}
  store.mark_report_viewed("solo")
  store.mark_report_viewed("solo", active=False)
  assert store.stale_reports() == [], "closing a user view keeps the idle interval"
  with store.connect() as db, db:
    db.execute("UPDATE reports SET viewed_at = ?, last_viewed_at = ?", (past, past))
  store.write_task("first", "First", ["Work"], report_id="solo", task_type="code")
  store.write_task("second", "Second", ["Work"], report_id="solo", task_type="code")
  store.write_task("first", status="finished")
  assert store.stale_reports() == [], "all linked tasks must finish"
  store.write_task("second", status="finished")
  assert {row["id"] for row in store.stale_reports()} == {"solo"}
  before_pin = store.report("solo")["updated_at"]
  with (
    patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": str(tmp_path)}),
    patch.object(sys, "argv", ["preview.py", "report", "pin", "solo"]),
  ):
    assert preview.main() == 0
  assert store.report("solo")["updated_at"] == before_pin
  assert store.stale_reports() == [], "a pin overrides finished tasks"
  lines, _ = store.state_lines(store.state()["notes"], store.tasks() or {})
  saved = next(row for row in lines if row.get("id") == "solo")
  assert saved["pinned"] is True
  restored = preview.Store(tmp_path / "restored", create=True)
  restored.import_state("\n".join(json.dumps(row) for row in lines))
  assert restored.stale_reports() == []
  restored.set_meta("port", guard_port())
  with (
    patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": str(tmp_path / "restored")}),
    patch.object(sys, "argv", ["preview.py", "report", "unpin", "solo"]),
  ):
    assert preview.main() == 0
  assert {row["id"] for row in restored.stale_reports()} == {"solo"}
  restored.write_task("second", status="upcoming")
  assert restored.stale_reports() == [], "reopening work keeps its report active"
  with pytest.raises(TypeError):
    restored.import_reports([dict(saved, pinned="yes")])
  with pytest.raises(FileNotFoundError):
    restored.pin_report("missing", True)
  store.publish("via-answer", "Linked answer", source)
  store.write_task("answer-task", "Answer task", ["Work"], task_type="code")
  store.submission("linked-answer", "via-answer", "Answer", task_id="answer-task")
  assert "via-answer" not in {row["id"] for row in store.stale_reports()}
  store.write_task("answer-task", status="finished")
  assert "via-answer" in {row["id"] for row in store.stale_reports()}
  with pytest.raises(preview.ReportHeld):
    store.unpublish("via-answer", stale_only=True)


def test_stale_report_reminder():
  # Ten published reports cross the reminder threshold. The finished task makes its report stale.
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    store = preview.Store(root, create=True)
    for index in range(9):
      source = root / f"form{index}.md"
      source.write_text(f"Select one: {{#f{index}}}\n\n- ( ) a\n- ( ) b\n", "utf-8")
      store.publish(f"form{index}", f"Form {index}", source)
    plain = root / "plain.md"
    plain.write_text("Information only, with no question to answer.\n", "utf-8")
    store.publish("plain", "Plain", plain)
    store.write_task(
      "plain-task",
      "Done",
      ["Work"],
      status="finished",
      report_id="plain",
      task_type="code",
    )
    stale_at = preview.REMINDERS.index("Unpublish stale reports.")
    cycle = [store.reminder() for _ in range(len(preview.REMINDERS))]
    assert cycle[stale_at] == "Unpublish 1 stale report."
    assert cycle[0] == preview.REMINDERS[0]
    assert cycle[stale_at + 1] == preview.REMINDERS[stale_at + 1]
    assert "plain" not in cycle[stale_at], "the reminder must not repeat a report ID"
    assert "form0" not in cycle[stale_at], (
      "a fresh form awaiting an answer is not stale"
    )
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "plain")
      )
    store.unpublish("plain")
    cycle = [store.reminder() for _ in range(len(preview.REMINDERS))]
    assert "Unpublish 1 stale report." not in cycle
    assert "Unpublish stale reports." in cycle


def test_stale_reports_command_lists_ids_and_reasons():
  """The list exposes only stale report IDs and their reason without changing reports."""
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    store = preview.Store(root, create=True)
    store.set_meta("port", guard_port())
    plain = root / "plain.md"
    plain.write_text("Information only, with no question to answer.\n", "utf-8")
    store.publish("plain", "Plain", plain)
    store.write_task(
      "plain-task",
      "Done",
      ["Work"],
      status="finished",
      report_id="plain",
      task_type="code",
    )
    answered = root / "answered.md"
    answered.write_text("Select one: {#answered}\n\n- ( ) a\n- ( ) b\n", "utf-8")
    store.publish("answered", "Answered", answered)
    store.submission("answered-reply", "answered", "REPORT answered: a")
    store.acknowledge(["answered-reply"], "Received")
    store.write_task(
      "answered-task",
      "Done",
      ["Work"],
      status="finished",
      report_id="answered",
      task_type="code",
    )
    before = store.state()["reports"]
    result = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "report", "stale"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(root)},
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == f"Stale reports {len(before)}"
    rows = [line.partition("\t") for line in lines[1:]]
    assert {row[0] for row in rows} == {report["id"] for report in before}
    assert all(separator and reason for _, separator, reason in rows)
    assert store.state()["reports"] == before


def test_pr_failed_check_breaks_poll():
  # The poll starts the branch check in the background and ends the wait on a failure,
  # so the turn fixes the check now.
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory), create=True)
    with (
      patch("preview.pr_failed_check", return_value="Quality"),
      patch("preview.POLL_MAX_LOOPS", 5),
    ):
      assert preview.poll_inbox(store) == 0


@pytest.mark.parametrize("initial", ["", None])
def test_poll_rechecks_pending_and_unknown_checks(initial, monkeypatch, capsys):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory), create=True)
    first_read = threading.Event()
    release_failure = threading.Event()
    failed_job = "Late preview failure"

    def check(root="."):
      if not first_read.is_set():
        first_read.set()
        return initial
      assert release_failure.wait(5)
      return failed_job

    def sleeper(seconds):
      assert first_read.wait(5)
      release_failure.set()
      time.sleep(seconds)

    monkeypatch.setattr(preview, "PR_CHECK_POLL_SECONDS", 0, raising=False)
    with (
      patch("preview.pr_failed_check", side_effect=check),
      patch("preview.POLL_INTERVAL", 0.001),
      patch("preview.POLL_MAX_LOOPS", 100),
    ):
      try:
        assert preview.poll_inbox(store, sleeper=sleeper) == 0
      finally:
        release_failure.set()
    output = capsys.readouterr().out
    assert "PR CHECKS FAILED:" in output
    assert failed_job in output
    assert store.polling() is False


def test_poll_stops_monitor_after_a_note(monkeypatch, capsys):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory), create=True)
    message = "Already waiting in the inbox"
    store.note("monitor-stop", message)
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    rechecked = threading.Event()
    errors = []
    real_thread = threading.Thread

    def check(root="."):
      if started.is_set():
        rechecked.set()
        return "Unexpected read after poll end"
      started.set()
      assert release.wait(5)
      return ""

    class ObservedThread:
      def __init__(self, target, args, daemon):
        def run():
          try:
            target(*args)
          except BaseException as error:
            errors.append(error)
          finally:
            finished.set()

        self.thread = real_thread(target=run, daemon=daemon)

      def start(self):
        self.thread.start()
        assert started.wait(5)

    monkeypatch.setattr(preview, "PR_CHECK_POLL_SECONDS", 0, raising=False)
    with (
      patch("preview.pr_failed_check", side_effect=check),
      patch("preview.threading.Thread", ObservedThread),
    ):
      try:
        assert preview.poll_inbox(store) == 0
        assert message in capsys.readouterr().out
      finally:
        release.set()
        assert finished.wait(5)
      assert not rechecked.is_set()
      assert not errors
      assert store.polling() is False


def test_pr_failed_check_does_not_outrank_a_note(capsys):
  # A note that lands while the check runs still breaks the poll: the loop reads the
  # note first, so the turn answers the owner before it reads the failure.
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory), create=True)
    note_landed = threading.Event()

    def slow_check(root="."):
      note_landed.wait(5)
      return "Quality"

    def arriving_sleeper(seconds):
      store.note("late-note", "Arrived during the wait")
      note_landed.set()

    with (
      patch("preview.pr_failed_check", side_effect=slow_check),
      patch("preview.POLL_MAX_LOOPS", 5),
    ):
      assert preview.poll_inbox(store, sleeper=arriving_sleeper) == 0
  printed = capsys.readouterr().out
  assert "Arrived during the wait" in printed
  assert "PR CHECKS FAILED" not in printed


def test_resolve_repo_root():
  # The poll worker shells out to git and gh from the repository root, so the resolver
  # returns the checkout that holds .git as a string, never a Path attribute.
  root = preview.resolve_repo_root()
  assert isinstance(root, str)
  assert (Path(root) / ".git").exists()


def test_pr_failed_check_gh_error():
  # A gh non-zero exit reads as None, a fault, not an empty all-clear, so the worker
  # retries instead of reporting a false all-clear.
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", "utf-8")
    fault = subprocess.CompletedProcess(["gh"], 1, stdout="", stderr="auth failed")
    with (
      patch("preview.repo_slug", return_value="owner/repo"),
      patch("preview.subprocess.run", return_value=fault),
    ):
      assert preview.pr_failed_check(str(root)) is None


def test_pr_failed_check_reads_the_newest_run_per_name():
  # A passed re-run of a job clears its older failure. Only another job's failure stands.
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", "utf-8")
    listed = subprocess.CompletedProcess(["gh"], 0, stdout="abc1234\n", stderr="")
    rows = subprocess.CompletedProcess(
      ["gh"],
      0,
      stdout=(
        "Quality\t2026-10-11T15:42:56Z\tfailure\n"
        "Quality\t2026-10-11T15:44:25Z\tsuccess\n"
        "Tests\t2026-10-11T15:44:00Z\tfailure\n"
      ),
      stderr="",
    )
    with (
      patch("preview.repo_slug", return_value="owner/repo"),
      patch("preview.subprocess.run", side_effect=[listed, rows]),
    ):
      assert preview.pr_failed_check(str(root)) == "Tests"


def test_pr_check_once_reports_a_failure():
  # Each read puts failed names in the poll's list, and a gh fault, read
  # as unknown, records nothing.
  result = []
  with patch("preview.pr_failed_check", return_value="Quality"):
    preview.pr_check_once(result, ".")
  assert result == ["Quality"]
  result.clear()
  with patch("preview.pr_failed_check", return_value=None):
    preview.pr_check_once(result, ".")
  assert result == []


def test_http_boundaries():
  global app
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "arena-preview"
    save_file = Path(directory) / "saved-state.ndjson"
    try:
      preview.Store(root)
      raise AssertionError("Missing inbox was treated as empty")
    except FileNotFoundError:
      pass
    linked = preview.render(
      "[PR](https://github.com/nemoe7/clankers/pull/26) [here](#here)"
    )
    assert (
      linked.count('target="_blank"') == 1 and 'rel="noopener noreferrer"' in linked
    )
    assert "<s>" in preview.render("~~gone~~")
    # Keep source newlines as text, even when the caller sets breaks.
    # CSS pre-wrap supplies the line breaks in the message log.
    chat = preview.render("line one\nline two", breaks=True)
    assert "<br" not in chat and "\n" in chat and chat.count("<p>") == 1
    css = compact((preview.ASSETS / "style.css").read_text())
    assert "border-left:2px solid var(--accent)" not in css
    assert "border-left:3px solid var(--accent)" not in css
    # The minified sheet shortens rgb(199, 194, 188) to #c7c2bc, so both spellings count.
    assert re.search(
      r"\.report \.question\{border-left:2px solid (rgb\(199,194,188\)|#c7c2bc);", css
    )
    assert re.search(r"border-left:3px solid (rgb\(199,194,188\)|#c7c2bc)", css)
    assert re.search(r"\.draft-preview p\s*\{\s*white-space:\s*pre-wrap;?\s*\}", css)
    # The report buttons ride the shared icon-button square, so no rule names a size for them.
    assert (
      "#copy-report,#refresh-report,#mark-report-acks-seen,#next-report,#unpublish-report{width:"
      not in css
    )
    select = re.search(r"select\{([^}]+)\}", css)
    assert select

    def css_px(rule, name):
      value = re.search(
        rf"(?:^|;){re.escape(name)}:"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(px)?(?=[ ;]|$)",
        rule,
      )
      assert value and (value[2] or float(value[1]) == 0)
      return float(value[1])

    def css_padding(rule):
      value = re.search(r"(?:^|;)padding:([^;]+)", rule)
      assert value
      sides = [css_px(f"padding:{part}", "padding") for part in value[1].split()]
      assert 1 <= len(sides) <= 4
      if len(sides) <= 2:
        sides *= 4 // len(sides)
      elif len(sides) == 3:
        sides.append(sides[1])
      return sides

    assert re.search(r"(?:^|;)appearance:none(?:;|$)", select[1])
    # Every select draws the same CSS chevron, so no markup needs a caret element.
    assert select[1].count("linear-gradient(") == 2
    assert "var(--muted)" in select[1]
    assert css_padding(select[1])[1] >= 24
    # The page and client script have no report-receipt flash.
    # Keep the report acknowledgement element.
    page = (preview.ASSETS / "index.html").read_text()
    script = (preview.ASSETS / "app.js").read_text()
    assert "report-receipt" not in page and "report-receipt" not in script
    assert "showReceipt" not in script and 'id="report-agent-ack"' in page
    assert page.index('id="report-ack-history"') < page.index('id="report-form"')
    assert page.index('id="report-agent-ack"') < page.index('id="report-form"')
    assert page.index('id="report-agent-ack-footer"') > page.index('id="report-submit"')
    # A break outside a paragraph, in a list item for one, stays exactly as markdown-it wrote it.
    assert "<br" in preview.render("- a\n  b", breaks=True)
    # The log uses pre-wrap paragraphs without breaks. A `<br>` would double each newline gap.
    logged = preview.render("line one\nline two")
    assert "<br" not in logged and "\n" in logged and logged.count("<p>") == 1
    escaped = preview.render("before\n\\```\ncode\n\\```\nafter")
    assert escaped.count('class="code-block"') == 1
    assert "<p>before</p>" in escaped and "<p>after</p>" in escaped
    assert "<pre><code>code" in escaped
    # A tilde fence is a fence too.
    assert "<pre" in preview.render("\\~~~\ncode\n\\~~~")
    # An escape that is not a fence stays markdown-it's own, so inline text keeps its literal
    # backticks rather than turning into a code block.
    assert "<pre" not in preview.render("a \\`code\\` b")
    # An image the agent sized keeps that size. Commonmark alone prints the syntax.
    sized = preview.render("![alt](https://example.com/a.png =320x200)")
    assert 'width="320" height="200"' in sized and 'alt="alt"' in sized
    assert 'width="320"' in preview.render("![a](https://example.com/a.png =320x)")
    assert "<img" in preview.render("![a](https://example.com/a.png)")
    # A source the renderer refuses stays text, and a quote in one stays escaped.
    assert "<img" not in preview.render("![x](javascript:alert(1) =10x10)")
    assert "&quot;" in preview.render('![q](https://example.com/a"b.png =10x10)')
    store = preview.Store(root, create=True, save_path=save_file)
    store.set_meta("port", guard_port())
    source = root / "report.md"
    source.write_text(
      "# First\n\n| A | B |\n| --- | --- |\n| C | D |\n\n<script>alert(1)</script>\n\n[bad](javascript:alert(1))",
      encoding="utf-8",
    )
    store.publish("first", "First <report>", source)
    store.publish("second", "Second", source)
    published_stamp = store.report("second")["published_at"]
    source.write_text("# Updated\n\n**Bold**", encoding="utf-8")
    store.publish("second", "Second revised", source)
    assert len(store.state()["reports"]) == 2
    assert store.report("second")["markdown"] == source.read_text()
    # A republish moves the edit stamp. The publish date stays at the first one.
    assert published_stamp, "the first publish keeps its date"
    assert store.report("second")["published_at"] == published_stamp
    assert store.report("second")["updated_at"] >= published_stamp
    assert {
      report["id"] for report in store.state()["reports"] if report["published_at"]
    } >= {
      "first",
      "second",
    }
    assert store.read()["pending"] == []
    assert store.state()["last_check"]
    assert store.state()["calls_since_message"] >= 0
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    worker = threading.Thread(target=app.serve_forever, daemon=True)
    worker.start()
    try:
      status, headers, page = request(
        "GET", "/", headers={"Host": "8000-sandbox.e2b.app"}
      )
      assert status == 200 and "__STYLE__" not in page and "__SCRIPT__" not in page
      assert 'data-theme="dark"' in page and 'role="tab"' in page
      # The log's toolbar is a search box and the skip button, with the empty line beside them.
      assert 'id="log-search"' in page and 'id="log-empty"' in page
      assert 'id="log-filter"' not in page and 'id="refresh-notes"' not in page
      assert 'id="composer-toggle"' not in page and "data-composer" not in page
      assert re.search(
        r'<p\b(?=[^>]*\bid="send-status")(?=[^>]*\brole="status")'
        r'(?=[^>]*\baria-live="polite")[^>]*>\s*</p>',
        page,
      ), "the empty composer feedback region keeps its live semantics"
      # The log's jump bar ships in the page, inside the wrapper that positions it over the scroll area.
      assert 'id="log-newest"' in page and 'class="log-scroll"' in page
      assert 'id="reports-scroll-frame"' in page
      assert re.search(r"\.report-scroll-frame\s*\{[^}]*position:\s*relative", page)
      assert 'aria-label="Scroll to bottom"' in page
      assert (
        '<svg class="lucide lucide-arrow-down" width="14" height="14" viewBox="0 0 24 24"'
        in page
      )
      assert "↓ Latest message" not in page
      newest = re.search(r"\.log-newest\s*\{([^}]+)\}", compact(page))
      edited = re.search(r"\.log-edited\s*\{([^}]+)\}", compact(page))
      assert newest and edited
      assert (
        css_px(newest[1], "border-radius") == css_px(edited[1], "border-radius") > 0
      )
      # The bar hugs its label rather than spanning the pane.
      assert "translateX(-50%)" in page
      # The reply pill floats above the log, so it cannot meet the placement pill.
      # It clears the card border and uses plain text, not accent color.
      assert re.search(r"\.log-edited\s*\{[^}]*position:\s*absolute", page)
      assert css_px(edited[1], "top") > 0
      assert re.search(r"\.log-edited\s*\{[^}]*color:\s*var\(--text\)", page)
      assert page.index('id="log-edited"') > page.index('class="log-scroll"')
      # The save button sits in the top bar after the theme button rather than in the log's own row.
      # The log's own copy and the tasks' copy are gone, and one copy button carries the state to the clipboard.
      assert (
        page.index('id="theme"')
        < page.index('id="copy-state"')
        < page.index('id="notes-panel"')
      )
      assert page.index('id="log-search"') < page.index('id="skip-poll"')
      # The Skip poll button carries Lucide's skip-forward geometry, vendored inline.
      assert 'd="M21 4v16"' in page and "M6.029 4.285" in page
      assert 'id="copy-log"' not in page and 'id="copy-tasks"' not in page
      # Every icon button carries a title that repeats its accessible name.
      controls = (
        "copy-state",
        "attach-file",
        "unpublish-report",
        "copy-report",
        "refresh-report",
        "mark-report-acks-seen",
        "next-report",
        "report-top",
      )
      labels = {}

      class IconLabels(HTMLParser):
        def handle_starttag(self, tag, attrs):
          attrs = dict(attrs)
          if tag == "button" and attrs.get("id") in controls:
            labels[attrs["id"]] = attrs

      IconLabels().feed(page)
      for control in controls:
        assert labels[control]["title"].strip()
        assert labels[control]["title"] == labels[control]["aria-label"]
      # A note owns staged file chips and a native multi-file selector. Backend records remain,
      # but no saved-files list crowds the composer. Downloads alone keeps the remaining tab.
      assert 'id="downloads-tab" aria-controls="downloads-panel"' in page
      assert (
        'id="downloads-panel" role="tabpanel" aria-labelledby="downloads-tab"' in page
      )
      assert 'id="files-tab"' not in page and 'id="files-panel"' not in page
      assert 'id="uploads-panel"' not in page and 'id="uploads-tab"' not in page
      assert 'id="upload-send"' not in page and 'id="upload-zone"' not in page
      assert page.index('id="compose"') < page.index('id="upload-file"')
      assert page.index('id="upload-file"') < page.index('id="reports-panel"')
      assert 'id="staged-files"' in page
      assert 'id="uploads-list"' not in page and 'id="uploads-history"' not in page
      assert 'id="fetch-url"' in page and 'id="fetch-proxy"' not in page
      assert "Up to 102.4 MB per URL" not in page
      assert "Keep this page open while transfers run." in page
      assert "not measured" not in page
      assert 'id="workspace-use"' in page
      assert re.search(
        r'<input[^>]*id="upload-file"[^>]*type="file"[^>]*multiple', page
      )
      # Check the arrow inside the scroll button, not an unrelated page icon.
      jump = re.search(
        r'<button[^>]*id="log-newest"[^>]*>(.*?)</button>', page, re.DOTALL
      )
      assert jump is not None
      static_icons = re.findall(r"<svg\b[^>]*>", page)
      assert static_icons and all(
        'class="lucide ' in item or 'class="markdown-icon"' in item
        for item in static_icons
      )
      arrow = jump.group(1)
      assert 'width="14" height="14"' in arrow
      assert 'stroke="currentColor"' in arrow and 'stroke-width="2"' in arrow
      assert 'class="lucide lucide-arrow-down"' in arrow
      # The search box says what it does without a visible label: the placeholder names the
      # gesture and the aria-label carries it for the screen reader.
      assert re.search(
        r'<input id="log-search" type="search" placeholder="Search messages"'
        r' aria-label="[^"]+">',
        page,
      )
      assert "frame-ancestors" not in headers["Content-Security-Policy"]
      assert "connect-src 'self' https:" in headers["Content-Security-Policy"]
      assert "default-src 'none'" in headers["Content-Security-Policy"]
      # default-src none blocks images too, so a report image needs its own directive.
      assert "img-src 'self' data: https:" in headers["Content-Security-Policy"]
      assert "data-token" not in page and "__TOKEN__" not in page
      assert "token" not in json.loads(request("GET", "/api/state")[2])
      auth = {"Content-Type": "application/json"}
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
      slash_status, _, slash_body = request(
        "POST",
        "/api/slash",
        json.dumps({"text": "/nuu help"}),
        auth,
      )
      assert slash_status == 200 and json.loads(slash_body)["mode"] == "query"
      assert store.state()["notes"] == []
      assert request("POST", "/api/markdown", '{"text":" "}', auth)[0] == 400
      assert request("POST", "/api/markdown", '{"text":"draft"}')[0] == 415
      assert request("POST", "/api/notes", "{}")[0] == 415
      assert request("POST", "/api/notes", "{}", {})[0] == 415
      assert request("POST", "/api/notes", "x" * 200_001, auth)[0] == 400
      for body in (
        "{",
        "[]",
        '{"id":"x","text":3}',
        '{"id":"x","text":" "}',
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
        (["message-1", "unknown"], "done"),
        (["message-1"], ""),
        (["message-1"], 3),
      ):
        try:
          store.acknowledge(*broken)
          raise AssertionError(f"Invalid receipt accepted: {broken}")
        except ValueError:
          assert store.read()["pending"]
      store.acknowledge(["message-1"], "Fixed in `preview.py`.")
      stamp = store.state()["notes"][0]["acknowledged_at"]
      assert len(stamp) == 19, (
        "the state surface carries second stamps, no ms or offset"
      )
      assert store.state()["notes"][0]["ack_text"] == "Fixed in `preview.py`."
      store.acknowledge(["message-1"], "and rechecked")
      row = store.state()["notes"][0]
      assert row["acknowledged_at"] == stamp
      assert (
        row["ack_type"] == "reply" and row["ack_text"] == "Fixed in `preview.py`."
      ), "a second ack appends; the first answer stays"
      assert [(reply["type"], reply["text"]) for reply in row["replies"]] == [
        ("reply", "and rechecked")
      ]
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
      assert "<code>preview.py</code>" in served_note["ack_html"]
      assert served_note["replies"] == [
        {
          "type": "reply",
          "text": "and rechecked",
          "at": served_note["ack_edited_at"],
          "html": "<p>and rechecked</p>\n",
        }
      ]
      assert served_note["seen_at"] is not None
      store.acknowledge(["message-1"], "<script>alert(1)</script> **safe**")
      status, _, state_body = request("GET", "/api/state")
      served_note = json.loads(state_body)["notes"][0]
      appended = served_note["replies"][1]
      assert "&lt;script&gt;" in appended["html"]
      assert "<strong>safe</strong>" in appended["html"]
      assert "<script>" not in appended["html"]
      status, _, rendered = request("GET", "/api/reports/first/html")
      assert status == 200
      rendered = json.loads(rendered)
      assert rendered["fields"] == 0
      # The rendered report carries both dates for the status line.
      assert rendered["published"] and rendered["edited"]
      assert "<table>" in rendered["html"] and "<script>" not in rendered["html"]
      assert 'href="javascript:' not in rendered["html"]
      assert request("GET", "/api/reports/first/export")[0] == 404
      status, headers, _ = request("GET", "/api/reports/first/source")
      assert status == 200
      assert headers["Content-Disposition"] == 'attachment; filename="first.md"'
      # The copy button asks for the report lines, so the clipboard carries the same
      # fields as the save file.
      status, _, sources = request("GET", "/api/report-sources")
      assert status == 200
      # One route hands the page the whole save file in one piece, so the copy button
      # copies the server's export instead of assembling three routes.
      status, _, copy_state = request("GET", "/api/copy-state")
      assert status == 200
      copy_payload = json.loads(copy_state)
      assert copy_payload["text"] == store.save_path.read_text(encoding="utf-8"), (
        "the copy route returns the save-file text"
      )
      assert copy_payload["counts"]["reports"] >= 1
      assert copy_payload["counts"]["notes"] == len(store.state()["notes"])
      assert sum(
        copy_payload["counts"][key] for key in ("notes", "tasks", "answers", "reports")
      ) == (len(copy_payload["text"].splitlines()))
      # The download names its file with this stamp, so the name comes from the export
      # rather than from the browser clock. A receipt can push it past the messages.
      newest = max(
        stamp
        for stamp in (
          preview.import_stamp(record.get("at"))
          for record in [*store.state()["notes"], *store.submissions()]
        )
        if stamp
      )
      assert preview.import_stamp(copy_payload["stamp"]) >= newest
      lines = json.loads(sources)
      assert "first" in [line["id"] for line in lines]
      first = next(line for line in lines if line["id"] == "first")
      assert set(first) == set(preview.REPORT_LINE_KEYS)
      assert first["markdown"].startswith("# First")
      prune = root / "prune.md"
      prune.write_text("# Prune\n\nA report the tab outgrew.\n", encoding="utf-8")
      store.publish("prune", "Prune", prune)
      assert request("GET", "/api/reports/prune/html")[0] == 200
      # Owner API dismissal can remove an unseen report immediately.
      status, _, removed = request("POST", "/api/reports/prune/unpublish", "{}", auth)
      assert status == 200 and json.loads(removed) == {"unpublished": "prune"}
      dismissed = [
        note for note in store.state()["notes"] if "dismissed" in note["text"]
      ]
      assert dismissed and "prune" in dismissed[-1]["text"]
      assert store.state()["notes"][-1]["acknowledged_at"] is None
      # Quiet: a read shows it, and a poll never wakes on it.
      assert dismissed[-1]["quiet"] == 1
      assert [item for item in store.read()["pending"] if "prune" in item["text"]]
      assert [
        item
        for item in store.read(include_quiet=False)["pending"]
        if "prune" in item["text"]
      ] == []
      assert request("GET", "/api/reports/prune/html")[0] == 404
      assert request("POST", "/api/reports/prune/unpublish", "{}", auth)[0] == 404
      assert (
        request(
          "POST",
          "/api/reports/prune/unpublish",
          "{}",
          {"Content-Type": "application/json"},
        )[0]
        == 404
      )
      assert prune.exists()
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
        "# Sign-off\n\nSelect the areas:\n\n- [ ] ui\n- [x] api\n- [ ] Other: ___\n\n"
        "Severity:\n\n"
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
      assert questions[0]["options"] == ["ui", "api", "Other: ___"]
      assert questions[0]["default"] == ["api"]
      assert questions[1]["prompt"] == "Severity" and questions[1]["default"] == [
        "high"
      ]
      assert questions[2]["prompt"] == "Name" and questions[3]["id"] == "notes"
      assert len({question["id"] for question in questions}) == 4
      assert sum(1 for type, _ in blocks if type == "field") == 4
      status, _, served = request("GET", "/api/reports/fields/html")
      served = json.loads(served)
      assert status == 200 and served["fields"] == 4
      assert served["html"].count("data-field=") == 4
      assert served["html"].count('class="question-id"') == 4
      for question in questions:
        assert f"Question ID: <code>{question['id']}</code>" in served["html"]
      assert served["html"].count('class="answer-text"') == 2
      assert 'input type="text"' not in served["html"]
      assert 'type="radio"' in served["html"] and 'type="checkbox"' in served["html"]
      assert "- [ ] not a field" in served["html"]
      assert served["html"].count("checked") == 2
      assert 'data-label="Other"' in served["html"]
      assert 'data-custom="Other"' in served["html"]
      assert 'class="custom-text"' in served["html"]
      assert "maxlength=" not in served["html"]
      assert (
        "<textarea" in served["html"]
        and 'placeholder="Something else..."' in served["html"]
      )
      assert "> Other: <" not in served["html"]
      status, _, page_text = request("GET", "/")
      page = compact(page_text)
      # The minified sheet drops attribute-selector quotes, so both spellings count.
      assert status == 200 and re.search(
        r'#preview-note\[aria-pressed="?false"?\][^{}]*\{', page
      )
      assert re.search(
        r'#preview-note\[aria-pressed="?true"?\][^{]*\{background:var\(--hover\)', page
      )
      assert "--focus:#524d47" in page and "#f4ca93" not in page
      assert "--focus:#8f5b13" in page
      assert "--tab-border:#413d39" in page
      assert "--tab-border:var(--border)" in page
      assert "nav button:focus-visible{border-color:var(--focus)" in page
      assert "border-color:var(--accent)" not in page
      assert "padding-bottom:12px" in page
      assert "#report-form{min-width:0;margin-top:12px" in page
      card = re.search(r"\.card\{([^}]+)\}", page)
      composer = re.search(r"\.card\.compose\{([^}]+)\}", page)
      assert card and composer, "composer padding must override .card"
      assert all(
        0 < compact_side < card_side
        for compact_side, card_side in zip(
          css_padding(composer[1]), css_padding(card[1])
        )
      ), "composer padding must stay positive and smaller than card padding"
      assert (
        ".message{margin-bottom:14px;background:var(--bubble);padding:8px 14px;border-radius:8px"
        in page
      )
      assert ".message:last-child{margin-bottom:0" in page
      assert re.search(
        r"\.answer\.reply\{border-left:2px solid (rgb\(199,194,188\)|#c7c2bc);"
        r"padding-left:12px;color:var\(--muted\);font-size:13px",
        page,
      )
      assert re.search(
        r"\.message-text blockquote\{margin:8px 0;padding-left:12px;color:var\(--muted\);"
        r"border-left:2px solid (rgb\(199,194,188\)|#c7c2bc)",
        page,
      )
      dot = re.search(r"\.state-dot\{([^}]+)\}", page)
      assert dot
      assert css_px(dot[1], "width") == css_px(dot[1], "height") > 0
      assert re.search(
        r"^display:inline-block;[^}]*border-radius:50%;background:var\(--dot-sent\)",
        dot[1],
      )
      assert "--dot-seen:#7fa7d1" in page and "--dot-seen:#3f6ea8" in page
      assert "--dot-said:#8dc07f" in page and "--dot-said:#4a7c3a" in page
      assert "--dot-sent:var(--muted)" in page
      # The minified sheet drops attribute-selector quotes, so both spellings count.
      assert re.search(
        r'\.state-dot\[data-state="?said"?\]\{background:var\(--dot-said\)', page
      )
      assert "--chip" not in page
      assert "code.note-id{" in page and ".receipt code" not in page
      assert ".answer.note" not in page
      assert ".answer>p:last-child{margin-bottom:0" in page
      assert (
        ":not(pre)>code{background:var(--code-bg);padding:1px 5px;border-radius:4px"
        in page
      )
      # Inline code sits darker than the page in dark mode. The light theme keeps its bubble.
      assert "--code-bg:#1b1a19" in page
      assert "--code-bg:var(--bubble)" in page
      assert re.search(
        r"textarea::placeholder\{color:var\(--muted\);opacity:(?:0)?\.5", page
      )
      assert "data-copied" not in page
      assert "#clock{font-size:inherit;font-variant-numeric:tabular-nums" in page
      assert re.search(
        r'\.icon-button\[data-state="?good"?\]\{color:var\(--dot-said\);', page
      )
      assert re.search(r'\.icon-button\[data-state="?bad"?\]\{color:#ef4444;', page)
      assert 'id="copy-log"' not in page, "the log lost its copy button"
      # The log card has no heading because its tab names the panel. The status stack and toolbar stay in place.
      assert "history-title" not in page
      assert '<section class="card log-card" aria-label="Message log">' in page
      assert page.index('id="connection"') < page.index('id="log-search"')
      # On phones, hide the composer hint and keep Send right-aligned with smaller padding and gaps.
      # Keep Copy beside Downloads with equal button gaps. Shrink labels and hide the clock and theme.
      coarse_block = re.search(
        r"@media \(pointer:coarse\)\{((?:[^{}]|\{[^}]*\})*)\}", page
      )
      assert coarse_block is not None
      coarse_rules = coarse_block[1]
      assert ".topbar-row{flex-wrap:nowrap;" in coarse_rules
      assert "#clock,#theme{display:none;}" in coarse_rules
      assert "nav{flex:1;" in coarse_rules
      assert "nav button{padding:7px 3px;font-size:13px;}" in coarse_rules
      assert "#send-hint{display:none;}#send{margin-left:auto;}" in coarse_rules
      coarse_gaps = [
        re.search(rf"{selector}\{{[^}}]*gap:([^;}}]+)", coarse_rules)
        for selector in (r"\.topbar-row", r"\.topbar-row>\.row\.tight", r"nav")
      ]
      assert all(coarse_gaps)
      assert len({match[1] for match in coarse_gaps}) == 1
      coarse_composer = re.search(
        r"@media \(pointer:coarse\)\{.*?\.card\.compose\{([^}]+)\}", page
      )
      assert coarse_composer is not None
      coarse_padding = css_padding(coarse_composer[1])
      assert len(set(coarse_padding)) == 1
      assert len(set(css_padding(composer[1]))) == 1
      assert all(
        0 < phone_side < desktop_side
        for phone_side, desktop_side in zip(coarse_padding, css_padding(composer[1]))
      )
      assert (
        page.index('id="agent-interrupt"')
        < page.index('id="downloads-tab"')
        < page.index('id="theme"')
        < page.index('id="copy-state"')
      )
      assert "grid-template-columns:repeat(3,1fr)" in page
      assert (
        '.report-scroll-frame>section[role="tabpanel"],main>section[role="tabpanel"]{padding-inline:5vw;}'
        in page
      )
      assert "nav button{padding:7px 4px;font-size:14px;}" in page
      # The phone header remains one line. Search stays above Skip. The Reports toolbar keeps buttons beside its select.
      # The status line keeps a row of its own.
      assert (
        ".log-card>.row:first-child>.stack{flex:0 1 auto;}"
        ".log-card>.row>.row.tight{flex:1 1 0;min-width:0;}"
        "#log-search,#task-search{min-width:5em;}" in page
      )
      assert (
        ".report-toolbar{gap:8px;}"
        ".select-wrap{flex:1 1 0;min-width:0;max-width:none;}}" in page
      ), "the phone block still ends with the select wrap rule"
      assert (
        "@media (max-width:40em){"
        ".log-card>.row:first-child>.stack{"
        "flex:1 1 100%;flex-direction:row;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;"
        "}" in page
      )
      assert (
        ".report .question{border-left:2px solid rgb(199,194,188);padding-left:12px;padding-right:4px;}"
        in page
      )
      # The composer's outer rows give up the space they face.
      assert "#form>div:first-child{margin-top:0;padding-top:0" in page
      assert "#form>div:last-child{margin-bottom:0;padding-bottom:0" in page
      assert '<button id="copy-report" class="icon-button"' in page
      # The report copy button matches the boxes beside it through the icon-button class,
      # and the shipped page carries no square rule of its own for the toolbar buttons.
      assert (
        "#copy-report,#refresh-report,#mark-report-acks-seen,#next-report,#unpublish-report{width:"
        not in page
      )
      # A rule separates the tasks toolbar from the finished div, and details collapse.
      assert re.search(
        r"\.tasks-layout>\.row\.tight\{[^}]*align-items:end;"
        r"border-bottom:1px solid var\(--border\);padding-bottom:12px",
        page,
      )
      assert ".task-details>summary{cursor:pointer;list-style-position:inside" in page
      assert ".task-title{cursor:pointer" in page
      assert not re.search(r"\.task-title\{[^}]*font-weight", page)
      assert 'id="copy-tasks"' not in page, "the tasks lost their copy button"
      # The Reports tab carries an unread pip rather than a count of the reports that exist.
      assert 'id="report-pip"' in page
      assert 'id="report-agent-ack"' in page
      assert "report-count" not in page
      # The minified sheet splits or reorders merged selectors, so each pip matches its own block.
      # The pip is a corner badge, so it adds no width to the tab it marks.
      for selector in ("#report-pip", "#notes-pip"):
        pip = re.search(re.escape(selector) + r"[^{}]*\{([^}]+)\}", page)
        assert pip
        assert pip[1].startswith("position:absolute;")
        assert css_px(pip[1], "top") == css_px(pip[1], "right") >= 0
        assert css_px(pip[1], "width") == css_px(pip[1], "height") > 0
        assert re.search(
          r"(?:^|;)display:inline-block;[^}]*border-radius:50%;background:var\(--accent\)",
          pip[1],
        )
      assert "[hidden]{display:none!important" in page
      assert page.index('id="copy-report"') < page.index('id="refresh-report"')
      assert '<span id="clock" class="muted" title="Local time">--:--</span>' in page
      assert page.index('id="clock"') < page.index('id="theme"')
      assert ".report :not(pre)>code" not in page
      # The minified sheet rewrites background none to 0 0, so both spellings count.
      assert re.search(r"background:(?:none|0 0);padding:0;cursor:pointer", page)
      assert "#send{border-color:var(--accent)" not in page
      assert "#report-submit{margin-top:16px" in page
      # A code block carries its background wherever markdown renders, not in a report alone: the
      # owner read a fence in a message as having no background.
      assert (
        "pre{padding:10px;border-radius:6px;overflow-x:auto;background:var(--bg)"
        in page
      )
      # Search boxes match the icon square and its minimum height.
      search = re.search(r"#log-search,#task-search\{([^}]+)\}", page)
      icon = re.search(r"\.icon-button\{([^}]+)\}", page)
      assert search and icon
      height = css_px(icon[1], "height")
      assert css_px(search[1], "height") == height == css_px(icon[1], "width") > 0
      assert (
        0 <= css_px(search[1], "min-height") == css_px(icon[1], "min-height") <= height
      )
      assert 'button,select,textarea,input[type="url"],input[type="search"]{' in page, (
        "the search box shares the form controls' border and radius"
      )
      assert "#log-filter" not in page and ".filter-wrap" not in page
      assert re.search(r"select\{[^}]*linear-gradient\(", compact(page)), (
        "the report select draws its caret in CSS, not a blocked data image"
      )
      assert "data:image/svg+xml" not in page, "the preview CSP blocks data images"
      # The collapse button is gone, its closed state with it, and the strip can no longer push
      # past the bar: it shrinks and scrolls at any width instead.
      assert "#chrome" not in page and "data-chrome" not in page
      assert re.search(r"nav\{[^}]*min-width:0;", page), (
        "the tab strip shrinks rather than pushing the bar"
      )
      # The three tabs share one width: the grid gives every track 1fr, so no label sets a tab's shape.
      # The narrow block steps the padding and the font down, and the tracks stay equal then.
      assert re.search(r"nav\{[^}]*grid-template-columns:repeat\(3,1fr\)", page)
      assert re.search(r"nav button\{[^}]*min-width:0;[^}]*padding:7px 9px;", page)
      assert re.search(r"nav button\{[^}]*white-space:nowrap", page)
      assert "nav button{padding:7px 4px;font-size:14px" in page
      # The footer has short hints and a short key line for narrow widths. Touch keyboards write a newline. Send sends.
      # The hint and its separator share a span, so hiding it leaves the key line whole.
      assert '<span id="send-hint">Enter sends · Shift+Enter:new line ·</span>' in page
      # A list in message text sits flush, matching the log's lists and the composer: the ack
      # thread under a report was the last outlier, on the browser's own step.
      assert (
        "#history li ul,#history li ol{margin:8px 0;padding-left:0;list-style-position:inside"
        in page
      )
      assert re.search(
        r"\.message-text (ol,\.message-text ul|ul,\.message-text ol)\{margin:8px 0;"
        r"padding-left:0;list-style-position:inside",
        page,
      ), "message text lists sit flush"
      report_list = re.search(
        r"\.report (?:ul,\.report ol|ol,\.report ul)\{([^}]+)\}", page
      )
      task_list = re.search(r"\.task-list\{([^}]+)\}", page)
      assert report_list and task_list
      assert css_px(report_list[1], "padding-left") > (
        css_px(task_list[1], "padding-left") + 4
      )
      # The narrow-screen and touch rules keep Send at the right.
      assert re.findall(r"#send\{(margin-left:[^}]*)\}", page) == [
        "margin-left:auto;",
        "margin-left:auto;",
      ]
      expand = re.search(r'<button\b[^>]*id="composer-expand"[^>]*>', page)
      assert expand is not None
      assert re.search(r'aria-label="[^"]+"', expand.group())
      assert 'aria-controls="note draft-preview"' in expand.group()
      assert 'aria-expanded="false"' in expand.group()
      composer = re.search(
        r'<section\b[^>]*id="compose"[^>]*>(.*?)</section>', page, re.DOTALL
      )
      assert composer is not None
      for identity in ("send-hint", "agent-key", "send-status"):
        marker = f'id="{identity}"'
        assert marker in page and marker not in composer.group(1)
      assert "resize:none" in page and "resize:vertical" not in page
      assert "#notes-panel{overflow:clip" in page
      assert "#reports-panel,#tasks-panel,#downloads-panel{overflow-y:auto" in page
      assert "padding-block:0" in page and ".key-line code{" in page
      assert '[role="tabpanel"]:not(#notes-panel)' in page
      assert 'id="tasks-tab" aria-controls="tasks-panel"' in page
      assert '<ul id="tasks-current-body" class="task-list"></ul>' in page
      assert '<ul id="tasks-finished-body" class="task-list"></ul>' in page
      assert '<ul id="tasks-upcoming-body" class="task-list"></ul>' in page
      assert store.state()["repo"] == store.repository_root().name
      assert f"<title>{store.repository_root().name} - Steering</title>" in page
      assert page.index('id="tasks-current"') < page.index('id="tasks-upcoming"')
      assert page.index('id="tasks-upcoming"') < page.index('id="tasks-finished"')
      assert ".task-list{margin:0;padding-left:20px" in page
      assert ".task-title{cursor:pointer" in page
      assert (
        ".task-details{display:block;margin-top:2px;color:var(--muted);font-size:13px"
        in page
      )
      # The details are a real list, so a marker comes from the element rather than a span's rule.
      assert ".task-detail-list{margin:2px 0 0;padding-left:18px" in page
      assert ".task-detail{display:block" not in page
      assert ".tasks-layout{display:flex;flex-direction:column;gap:18px" in page
      assert "max-height:48%" not in page
      assert "min-height:100%" not in page
      assert (
        ".notes-layout{display:flex;flex-direction:column;gap:14px;height:100%" in page
      )
      assert re.search(
        r"\.topbar-row\{[^}]*max-width:900px;margin:0 auto;",
        page,
      )
      assert (
        ":focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-color:var(--focus)"
        in page
      )
      assert "resize:none;min-height:72px;overflow:hidden" in page
      # The document does not scroll. Panels do. A short viewport lowers the log-card floor.
      # A small phone then keeps the column on screen with the composer closed.
      assert "html,body{height:100%;overflow:hidden;overscroll-behavior:none" in page
      assert "height:var(--app-height,100dvh)" in page
      # The log header wraps into four short lines on a narrow width, and the 12px wrap gap read
      # as dead space. The lines sit close now.
      assert ".log-card>.row:first-child{margin-block:0;row-gap:2px" in page
      assert ".log-card{flex:1 1 auto;min-height:0" in page
      assert re.search(
        r"#downloads-panel>\.card,#notes-panel \.log-card,#reports-panel>\.card,#tasks-panel>\.card\{"
        r"background:(?:transparent|0 0);border:0;padding-inline:0",
        page,
      )
      assert (
        "#downloads-panel>.card,#reports-panel>.card,#tasks-panel>.card{"
        "max-width:900px;width:100%;margin-inline:auto" in page
      )
      assert "h1{letter-spacing:-.035em;margin:4px 0" in page
      assert "h2{margin:0 0 8px" in page
      assert re.search(r"\.report p[^{}]*\{margin:8px 0", page)
      assert re.search(r"\.message-text p[^{}]*\{margin:8px 0", page)
      for level in ("h1", "h2", "h3", "h4", "h5", "h6"):
        assert f"{level}{{font-size" not in page

      block = preview.add_copy_buttons(preview.render("```python\nprint(1)\n```"))
      assert block.startswith(
        '<div class="code-block"><button type="button" class="copy-code"'
      )
      assert 'data-code="print(1)&#10;"' in block and "<pre><code" in block
      # The copy button carries Lucide's copy shape, vendored inline like the page's own.
      assert 'title="Copy code"' in block and 'class="lucide lucide-copy"' in block
      assert 'd="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"' in block
      assert (
        preview.add_copy_buttons(preview.render("no code here")).count("copy-code") == 0
      )
      escaped = preview.add_copy_buttons(preview.render('```text\n<a href="x">&\n```'))
      assert "&lt;a href=&quot;x&quot;&gt;&amp;" in escaped and "<a href" not in escaped
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
          json.dumps(
            {
              "id": "r1",
              "answers": {"severity": "extreme"},
              "revision": store.report("fields")["updated_at"],
            }
          ),
          auth,
        )[0]
        == 400
      )
      assert (
        request(
          "POST",
          "/api/reports/first/submit",
          json.dumps(
            {"id": "r2", "answers": {}, "revision": store.report("first")["updated_at"]}
          ),
          auth,
        )[0]
        == 400
      )
      report_answer = json.dumps(
        {
          "id": "report-sub-1",
          "revision": store.report("fields")["updated_at"],
          "answers": {"select-the-areas": ["ui"], "severity": "high", "name": "ada"},
        }
      )
      assert (
        request("POST", "/api/reports/fields/submit", report_answer, auth)[0] == 201
      )
      assert not [
        row for row in store.state()["notes"] if row["text"].startswith("REPORT")
      ]
      answered = store.submissions()[-1]["text"]
      assert "Fielded:" in answered and "Name (name): ada" in answered
      assert (
        "Severity (severity): high" in answered
        and "Notes (notes): (skipped)" in answered
      )
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
      assert request("POST", "/api/reports/fields/submit", "{}", {})[0] == 415
      assert (
        request(
          "POST",
          "/api/reports/fields/submit",
          json.dumps({"id": "s1", "answers": {"name": "x"}}),
        )[0]
        == 415
      )
      for bad in (
        {"id": "s1", "answers": {"name": "x", "nope": "unknown"}},
        {"id": "s1", "answers": {"severity": "extreme"}},
        {"id": "s1", "answers": {"select-the-areas": ["ui", "core"]}},
        {"id": "s1", "answers": "nope"},
      ):
        assert (
          request(
            "POST",
            "/api/reports/fields/submit",
            json.dumps(dict(bad, revision=store.report("fields")["updated_at"])),
            auth,
          )[0]
          == 400
        )
      sent = store.submissions()
      submission = json.dumps(
        {
          "id": "sub-1",
          "revision": store.report("fields")["updated_at"],
          "answers": {
            "name": "it broke",
            "severity": "high",
            "select-the-areas": ["ui"],
          },
        }
      )
      assert request("POST", "/api/reports/fields/submit", submission, auth)[0] == 201
      pending = [
        row
        for row in store.read()["pending"]
        if row["text"].startswith("REPORT fields")
      ]
      submitted_id = json.loads(submission)["id"]
      assert {row["id"] for row in pending} == {submitted_id}
      assert {row["id"] for row in store.submissions()} == {
        row["id"] for row in sent
      } | {submitted_id}
      assert pending[-1]["type"] == "report"
      answered = pending[-1]["text"]
      assert (
        "Fielded:" in answered
        and "Name (name): it broke" in answered
        and "Severity (severity): high" in answered
        and "Select the areas (select-the-areas): ui" in answered
        and "Notes (notes): (skipped)" in answered
      )
      assert request("POST", "/api/reports/fields/submit", submission, auth)[0] == 201
      assert len(store.submissions()) == len(sent) + 1
      store.acknowledge([pending[-1]["id"]], "read")
      assert pending[-1]["id"] not in {row["id"] for row in store.read()["pending"]}
      assert (
        request(
          "POST",
          "/api/reports/fields/submit",
          json.dumps(
            {
              "id": "sub-1",
              "answers": {"name": "changed"},
              "revision": store.report("fields")["updated_at"],
            }
          ),
          auth,
        )[0]
        == 400
      )
      custom = root / "custom.md"
      custom.write_text(
        "Verdict {#verdict}\n\n- ( ) Ship it\n- ( ) Other: ___\n", encoding="utf-8"
      )
      verdict = preview.parse_fields(custom.read_text(encoding="utf-8"))[1][0]
      assert verdict["options"] == ["Ship it", "Other: ___"]
      markup = preview.field_html(verdict)
      assert 'data-label="Other"' in markup and 'data-custom="Other"' in markup
      assert (
        "> <span>Ship it</span></label>" in markup
        and 'placeholder="Something else..."' in markup
      )
      assert " Other: " not in markup and "<textarea" in markup
      assert 'aria-label="Other"' in markup
      assert 'aria-label="Other, your own answer"' in markup
      assert preview.custom_answer(verdict, "Other: make it blue")
      assert not preview.custom_answer(verdict, "Other:   ")
      assert preview.custom_answer(verdict, "Other: " + "x" * 2000)
      assert preview.custom_answer(verdict, "Other: " + "x" * 2001)
      assert not preview.custom_answer(verdict, "nonsense")
      assert not preview.custom_answer(verdict, 7)
      record = store.submit(
        "custom",
        "Custom",
        [verdict],
        "sub-custom",
        {"verdict": "Other: make it blue"},
      )
      assert "Verdict (verdict): Other: make it blue" in record["text"], (
        "the flattened answer carries its question"
      )
      for bad in (
        {"verdict": "Other: "},
        {"verdict": "nope"},
        {"verdict": ["Other: typed"]},
      ):
        try:
          store.submit("custom", "Custom", [verdict], "sub-bad", bad)
          raise AssertionError("An answer outside the free-text slot was accepted")
        except ValueError:
          pass
      try:
        preview.Store.validate_fields(
          [dict(verdict, options=["Other: ___", "Other: ____"])]
        )
        raise AssertionError("Two free-text options shared one label")
      except ValueError:
        pass
      broken = root / "broken.md"
      broken.write_text(
        "# Broken\n\nSelect one:\n\n- ( ) " + "x" * 201 + "\n", encoding="utf-8"
      )
      try:
        store.publish("broken", "Broken report", broken)
        raise AssertionError("A report with an over-long option was published")
      except ValueError:
        pass
      assert "broken" not in {item["id"] for item in store.state()["reports"]}
      # A report stored before that guard existed is still unrenderable, so the route answers with a JSON error.
      stale = sqlite3.connect(root / "state.sqlite3")
      stale.execute(
        "INSERT INTO reports (id, title, markdown, updated_at, seq) VALUES (?, ?, ?, ?, ?)",
        (
          "stale",
          "Stale report",
          broken.read_text(encoding="utf-8"),
          "2026-09-21T00:00:00+00:00",
          999,
        ),
      )
      stale.commit()
      stale.close()
      status, _, body = request("GET", "/api/reports/stale/html")
      assert status == 500, (
        "an unrenderable report answered something other than an error"
      )
      assert "cannot be rendered" in json.loads(body)["error"]
      # Its source still serves, so the agent can read what the browser could not render.
      assert request("GET", "/api/reports/stale/source")[0] == 200
      wide = root / "wide-http.md"
      wide.write_text(
        "# Wide\n\n"
        + "\n".join(f"Question {index}: ___" for index in range(50))
        + "\n",
        encoding="utf-8",
      )
      store.publish("wide", "Wide report", wide)
      _, wide_questions = preview.render_report(wide.read_text(encoding="utf-8"))
      assert len(wide_questions) == 50
      full = json.dumps(
        {
          "id": "sub-wide",
          "revision": store.report("wide")["updated_at"],
          "answers": {q["id"]: "x" * 2000 for q in wide_questions},
        }
      )
      assert len(full) > 96_000, "the case has to exceed the limit it is testing"
      assert request("POST", "/api/reports/wide/submit", full, auth)[0] == 201
      assert (
        request(
          "POST",
          "/api/reports/wide/submit",
          json.dumps(
            {
              "id": "sub-over",
              "revision": store.report("wide")["updated_at"],
              "answers": {wide_questions[0]["id"]: "x" * 2001},
            }
          ),
          auth,
        )[0]
        == 201
      )
      over_body = "x" * (1_000_001)
      assert request("POST", "/api/reports/wide/submit", over_body, auth)[0] == 400
      assert request("POST", "/api/notes", "x" * 200_001, auth)[0] == 400
      # The note schema carries no author column: a record is just the message and its receipt.
      note = store.note("plain-note", "no author field")
      assert "origin" not in note
      assert "origin" not in store.state()["notes"][-1]
      stale_state = next(
        row for row in store.state()["reports"] if row["id"] == "stale"
      )
      assert stale_state["needs_answer"] is True
      assert "1–200 characters" in stale_state["field_error"]
      # A database that predates the removal loses `origin` when the store reopens.
      legacy = sqlite3.connect(root / "state.sqlite3")
      legacy.execute("ALTER TABLE notes ADD COLUMN origin TEXT")
      legacy.execute("UPDATE notes SET origin = 'agent' WHERE id = 'plain-note'")
      legacy.commit()
      legacy.close()
      preview.Store(root)
      reopened = sqlite3.connect(root / "state.sqlite3")
      columns = {row[1] for row in reopened.execute("PRAGMA table_info(notes)")}
      reopened.close()
      assert "origin" not in columns, "the migration drops a leftover origin column"

      store.submission(
        "saved-answer",
        "first",
        "REPORT first First:\n  a: yes",
        "2026-09-21T09:02:00",
        acknowledged_at="2026-09-21T09:06:00",
        ack_type="note",
        ack_text="read it",
        seen_at="2026-09-21T09:03:00",
        task_id="saved-task",
      )
      # Autosave writes what the database holds, in one file the importer can read. The page's
      # copy button posts nothing, so this drives the writer the way a committed mutation does.
      written = store.save_state(
        {
          "notes": [
            {
              "id": "saved-note",
              "text": "from the browser",
              "at": "2026-09-21T09:00:00",
              "acknowledged_at": "2026-09-21T09:05:00",
              "ack_type": "reply",
              "ack_text": "answered",
              "seen_at": "2026-09-21T09:01:00",
              "task_id": "saved-task",
            }
          ],
          "tasks": {
            "upcoming": [
              {
                "id": "saved-task",
                "title": "From the browser",
                "details": ["one"],
                "order": 1,
              }
            ],
            "finished": [],
          },
        }
      )
      assert written["notes"] == 1 and written["tasks"] == 1
      saved_lines = [
        json.loads(line)
        for line in Path(written["path"]).read_text(encoding="utf-8").splitlines()
      ]
      lines_by_id = {line["id"]: line for line in saved_lines}
      # The given lines come first, in the order the writer takes them. The answers come after
      # them, from the store, because the page never holds an answer it did not just send.
      assert [line["id"] for line in saved_lines][:2] == ["saved-note", "saved-task"]
      assert written["answers"] == len(
        [line for line in saved_lines if "report_id" in line]
      )
      answer_ids = [line["id"] for line in saved_lines if "report_id" in line]
      # Answers order by their arrival stamps: the restored 2026-09-21 answer sorts
      # first, and the just-sent one lands last.
      assert written["answers"] >= 1
      assert answer_ids[0] == "saved-answer"
      assert answer_ids[-1] == "sub-over"
      # Report lines follow the answers, so the last line carries a report source.
      assert written["reports"] >= 1 and "markdown" in saved_lines[-1]
      # This block passes an explicit sibling path, so the file lands outside the state
      # directory instead of inside it.
      assert written["path"] == str(save_file)
      assert save_file.is_file() and save_file.parent != root
      answer_line = lines_by_id["saved-answer"]
      assert answer_line["report_id"] == "first"
      assert (
        answer_line["ack_text"] == "read it"
        and answer_line["seen_at"] == "2026-09-21T09:03:00"
      )
      assert answer_line["task_id"] == "saved-task"
      # A note line keeps its task marker too, so the marker the receipt shows survives a restore.
      assert lines_by_id["saved-note"]["task_id"] == "saved-task"
      # One file, one reader for both types: `import-state` restores the note and the answer, and
      # the answer keeps its receipt, its read stamp and its task marker.
      round_trip = Path(directory) / "round-trip"
      preview.Store(round_trip, create=True).set_meta("port", guard_port())
      imported = subprocess.run(
        [
          sys.executable,
          str(Path(preview.__file__)),
          "state",
          "import",
          str(save_file),
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(round_trip)},
      ).stdout
      assert "notes 1" in imported
      assert f"answers {written['answers']}" in imported or "answers" in imported
      restored_store = preview.Store(round_trip)
      answers = {row["id"]: row for row in restored_store.submissions()}
      assert answers["saved-answer"]["text"] == "REPORT first First:\n  a: yes"
      assert answers["saved-answer"]["ack_text"] == "read it"
      assert answers["saved-answer"]["seen_at"] == "2026-09-21T09:03:00"
      assert answers["saved-answer"]["task_id"] == "saved-task"
      assert restored_store.state()["notes"][0]["task_id"] == "saved-task"
      # The save route is gone: autosave writes the file and the page copies to the clipboard.
      assert request("POST", "/api/save-state", "{}", auth)[0] == 404
      assert request("POST", "/api/save-state", "{}")[0] == 404
      # A note still can bind its files in one send. The staged surface takes multipart only,
      # and its other verbs stay unknown.
      assert request("POST", "/api/uploads?name=gone.bin", b"x", auth)[0] == 415
      assert request("GET", "/api/uploads/gone")[0] == 404

      # The read stamp belongs to the report rather than to one browser's storage, so the browser
      # writes it through a route of its own, and only the first look sets it.
      revision_source = root / "revision.md"
      revision_source.write_text(
        "Old plan\n\nDecision? {#decision}\n- ( ) Yes\n- ( ) No\n"
      )
      with patch.object(
        preview, "now", return_value="2026-09-22T12:00:00.100000+00:00"
      ):
        store.publish("revision", "Old plan", revision_source)
      served_revision = json.loads(request("GET", "/api/reports/revision/html")[2])[
        "revision"
      ]
      assert served_revision == store.report("revision")["updated_at"]
      revision_source.write_text(
        "Changed plan\n\nDecision? {#decision}\n- ( ) Yes\n- ( ) No\n"
      )
      with patch.object(
        preview, "now", return_value="2026-09-22T12:00:00.900000+00:00"
      ):
        store.publish("revision", "Changed plan", revision_source)
      answer = {
        "id": "revision-answer",
        "answers": {"decision": "Yes"},
        "revision": served_revision,
      }
      before_answers = store.submissions()
      assert (
        request("POST", "/api/reports/revision/submit", json.dumps(answer), auth)[0]
        == 409
      )
      assert store.submissions() == before_answers
      assert next(row for row in store.state()["reports"] if row["id"] == "revision")[
        "needs_answer"
      ]
      del answer["revision"]
      assert (
        request("POST", "/api/reports/revision/submit", json.dumps(answer), auth)[0]
        == 400
      )
      answer["revision"] = store.report("revision")["updated_at"]
      traced = []
      connect = store.connect

      def traced_connection():
        db = connect()
        own = []
        traced.append(own)
        db.set_trace_callback(own.append)
        return db

      with patch.object(store, "connect", side_effect=traced_connection):
        assert (
          request("POST", "/api/reports/revision/submit", json.dumps(answer), auth)[0]
          == 201
        )
      # One connection writes the answer, and the export's reads follow that commit.
      writers = [
        own
        for own in traced
        if any(item.startswith(("BEGIN", "INSERT", "UPDATE", "DELETE")) for item in own)
      ]
      assert len(writers) == 1 and writers[0] is traced[0]
      statements = traced[0]
      assert statements[0] == "BEGIN IMMEDIATE" and statements[-1] == "COMMIT"
      assert any("SELECT * FROM reports" in statement for statement in statements)
      assert any("INSERT INTO submissions" in statement for statement in statements)
      assert (
        request("POST", "/api/reports/revision/submit", json.dumps(answer), auth)[0]
        == 201
      )
      assert len(store.submissions()) == len(before_answers) + 1
      store.publish("seen", "Seen report", source)
      assert store.state()["reports"][-1]["seen_at"] is None
      assert request("POST", "/api/reports/seen/seen", "{}")[0] == 415
      assert request("POST", "/api/reports/missing/seen", "{}", auth)[0] == 404
      assert request("GET", "/api/reports/seen/seen")[0] == 404
      status, _, stamped = request("POST", "/api/reports/seen/seen", "{}", auth)
      first = json.loads(stamped)["seen_at"]
      assert status == 200 and first
      assert store.state()["reports"][-1]["seen_at"] == first
      assert (
        json.loads(request("POST", "/api/reports/seen/seen", "{}", auth)[2])["seen_at"]
        == first
      )
      store.publish("seen", "Seen report revised", source)
      assert store.state()["reports"][-1]["seen_at"] is None
      # The ack open stamp is its own route, and it moves on every call: the mark belongs to the
      # answer the owner just looked at, so a later ack needs its own open.
      assert request("POST", "/api/reports/seen/ack-seen", "{}")[0] == 415
      assert request("POST", "/api/reports/missing/ack-seen", "{}", auth)[0] == 404
      assert request("GET", "/api/reports/seen/ack-seen")[0] == 404
      status, _, ack_body = request("POST", "/api/reports/seen/ack-seen", "{}", auth)
      ack_stamp = json.loads(ack_body)["ack_seen_at"]
      assert status == 200 and ack_stamp
      assert store.state()["reports"][-1]["ack_seen_at"] == ack_stamp
      with patch.object(
        preview,
        "now",
        side_effect=["2026-10-08T00:00:01+00:00", "2026-10-08T00:00:02+00:00"],
      ):
        first_open = store.mark_report_ack_seen("seen")["ack_seen_at"]
        second_open = store.mark_report_ack_seen("seen")["ack_seen_at"]
      assert (first_open, second_open) == (
        "2026-10-08T00:00:01+00:00",
        "2026-10-08T00:00:02+00:00",
      ), "each open moves the stamp"
      store.publish("scoped", "Scoped", source)
      store.submission("scoped-answer", "scoped", "REPORT scoped: noted")
      assert any(
        line["id"] == "scoped-answer"
        for line in json.loads(request("GET", "/api/submissions")[2])
      ), "a live report's answers ride the copy endpoint"
      with store.connect() as db, db:
        db.execute(
          "UPDATE reports SET seen_at = ? WHERE id = ?",
          ("2026-01-01T00:00:00", "scoped"),
        )
      store.unpublish("scoped", dismissed_by_owner=True)
      assert not any(
        line["id"] == "scoped-answer"
        for line in json.loads(request("GET", "/api/submissions")[2])
      ), "a deleted report's answers stay out of the copy (owner scope)"
    finally:
      app.shutdown()
      app.server_close()
      worker.join()


def test_read_names_every_attachment():
  # A note read lists attachment names, paths, and sizes. The agent opens the right file without another state call.
  # A lost upload keeps its name and path and says the bytes are gone.
  with tempfile.TemporaryDirectory() as named_dir:
    named = preview.Store(named_dir, create=True)
    named.note_with_uploads(
      "named-note",
      "here conversation page",
      [
        ("ChatGPT.html", "text/html", b"<html></html>"),
        ("Greeting exchange.html", "text/html", b"<html>two</html>"),
      ],
    )
    listing = preview.format_read(named.read())
    for record in named.uploads():
      assert f"{record['name']}: {record['path']}" in listing
      # The size rides the path in the shortest unit, so a large read never arrives blind.
      assert f"{record['name']}: {record['path']} ({record['size']} B)" in listing
    assert "here conversation page" in listing
    # A note with no text and no attachment keeps the header alone, and the header carries
    # the ticks that keep the head exact for the copy back into an ack.
    bare = preview.format_pending_item({"id": "bare", "text": ""})
    assert bare == "`bare`"
    # A missing upload keeps its name and reports the loss.
    lost = preview.format_pending_item(
      {
        "id": "lost",
        "text": "gone",
        "attachments": [
          {"name": "saved.html", "path": "/state/uploads/saved.html", "present": False}
        ],
      }
    )
    assert (
      lost
      == "`lost`\ngone\nattachments: saved.html: /state/uploads/saved.html (missing)"
    )


def test_read_attaches_published_report_parent():
  with tempfile.TemporaryDirectory() as thread_dir:
    store = preview.Store(thread_dir, create=True)
    source = Path(thread_dir) / "guide.md"
    source.write_text("# Guide\n\nKeep the draft.\n", encoding="utf-8")
    store.publish("guide-report", "Guide", source)
    store.note("reply", "RE: guide-report\nproposal")
    listing = store.read()
    assert [item["id"] for item in listing["pending"]] == ["reply"]
    reply = listing["pending"][0]
    assert [item["id"] for item in reply.get("thread", [])] == ["guide-report"]
    assert preview.format_pending_item(reply) == (
      f"`reply`\nRE: guide-report\nSource: {source}\n\nproposal"
    )
    store.note("qreply", "RE: guide-report/next-action\nquestion note")
    question_item = next(
      item for item in store.read()["pending"] if item["id"] == "qreply"
    )
    assert preview.format_pending_item(question_item) == (
      f"`qreply`\nRE: guide-report/next-action\nSource: {source}\n\nquestion note"
    )
    assert "Keep the draft." not in json.dumps(reply)
    saved = next(
      record
      for record in map(json.loads, store.save_path.read_text().splitlines())
      if record.get("id") == "guide-report"
    )
    restored = preview.Store(Path(thread_dir) / "restored", create=True)
    restored.import_reports([saved])
    restored_source = Path(restored.report("guide-report")["source"])
    assert restored_source.resolve().is_relative_to(
      (Path(thread_dir) / "restored").resolve()
    )
    assert restored_source.read_text(encoding="utf-8") == "# Guide\n\nKeep the draft.\n"
    restored.note("again", "RE: guide-report\nfollow up")
    assert f"Source: {restored_source}" in preview.format_read(restored.read())


def test_report_reply_without_saved_path_names_stored_source():
  with tempfile.TemporaryDirectory() as thread_dir:
    store = preview.Store(thread_dir, create=True)
    store.import_reports(
      [{"id": "legacy-report", "title": "Legacy", "markdown": "Do not quote this."}]
    )
    with store.connect() as db, db:
      db.execute("ALTER TABLE reports DROP COLUMN source")
    store = preview.Store(thread_dir)
    assert store.report("legacy-report")["source"] is None
    assert store.report("legacy-report")["ack_seen_at"] is None
    for invalid_stamp in ([], "not-a-timestamp"):
      with pytest.raises(ValueError):
        store.import_reports(
          [
            {
              "id": "invalid-stamp",
              "title": "Invalid",
              "markdown": "text",
              "ack_seen_at": invalid_stamp,
            }
          ]
        )
      with pytest.raises(FileNotFoundError):
        store.report("invalid-stamp")
    with pytest.raises(ValueError, match="source path is text"):
      store.import_reports(
        [{"id": "invalid-source", "title": "Invalid", "markdown": "text", "source": []}]
      )
    store.note("reply", "RE: legacy-report\nfollow up")
    rendered = preview.format_read(store.read())
    assert "RE: legacy-report\nSource: /api/reports/legacy-report/source" in rendered
    assert "Do not quote this." not in rendered


def test_read_attaches_answer_and_task_parents():
  with tempfile.TemporaryDirectory() as thread_dir:
    store = preview.Store(thread_dir, create=True)
    source = Path(thread_dir) / "decision.md"
    source.write_text("Choice: {#choice}\n\n- ( ) keep\n- ( ) drop\n", encoding="utf-8")
    store.publish("parent-report", "Decision", source)
    store.submit_report(
      "parent-report",
      "answer",
      {"choice": "keep"},
      revision=store.report("parent-report")["updated_at"],
    )
    store.write_task("parent-task", "Task guide", ["Keep all rules."], task_type="docs")
    store.note("answer-reply", "RE: answer\nfollow answer")
    store.note("task-reply", "RE: parent-task\nfollow task")
    store.note("ambiguous", "RE: parent-\ndo not guess")
    pending = {item["id"]: item for item in store.read()["pending"]}
    assert "answer" in pending
    assert [item["id"] for item in pending["answer-reply"].get("thread", [])] == [
      "answer"
    ]
    assert ">   Choice (choice): keep\n\nfollow answer" in preview.format_pending_item(
      pending["answer-reply"]
    )
    assert [item["id"] for item in pending["task-reply"].get("thread", [])] == [
      "parent-task"
    ]
    assert (
      "> Task guide\n> Keep all rules.\n\nfollow task"
      in preview.format_pending_item(pending["task-reply"])
    )
    assert not pending["ambiguous"].get("thread")


def test_read_attaches_reply_threads():
  with tempfile.TemporaryDirectory() as thread_dir:
    store = preview.Store(thread_dir, create=True)
    store.note("root", "hello\nline two\n\nlast", at="2026-10-13T00:00:00+00:00")
    store.note("middle", "RE: root\nfrom the middle", at="2026-10-13T00:01:00+00:00")
    store.acknowledge(["root"], "read")
    store.acknowledge(["middle"], "read")
    store.note("child", "RE: middle\n\nworld", at="2026-10-13T00:02:00+00:00")
    listing = store.read()
    child = listing["pending"][0]
    assert [record["id"] for record in child["thread"]] == ["root", "middle"]
    rendered = preview.format_read(listing)
    assert (
      "`child`\n> > hello\n> > line two\n> > \n> > last\n> \n> from the middle\n\nworld"
      in rendered
    )
    assert "`root`" not in rendered and "`middle`" not in rendered
    assert "RE:" not in rendered
    store.note("pending", "already pending")
    store.note("duplicate", "RE: pending\nno duplicate")
    store.note("missing", "RE: absent\nno parent")
    store.note("cycle-a", "RE: cycle-b\na")
    store.note("cycle-b", "RE: cycle-a\nb")
    store.acknowledge(["cycle-a", "cycle-b"], "read")
    store.note("cycle-c", "RE: cycle-a\nc")
    pending = {record["id"]: record for record in store.read()["pending"]}
    assert [record["id"] for record in pending["duplicate"]["thread"]] == ["pending"]
    assert "pending" in pending
    rendered = preview.format_read(store.read())
    assert rendered.count("`pendin`") == 1
    assert "> already pending\n\nno duplicate" in rendered
    assert not pending["missing"].get("thread")
    assert preview.format_pending_item(pending["missing"]) == (
      "`missin`\nReferenced message unavailable.\n\nno parent"
    )
    assert [record["id"] for record in pending["cycle-c"]["thread"]] == [
      "cycle-b",
      "cycle-a",
    ]
    assert "> > b\n> \n> a\n\nc" in preview.format_pending_item(pending["cycle-c"])
    attached = preview.format_pending_item(
      {
        "id": "reply",
        "text": "RE: parent\nreply text",
        "thread": [
          {
            "id": "parent",
            "text": "one\n\n> two",
            "attachments": [
              {
                "name": "saved.html",
                "path": "/state/uploads/saved.html",
                "present": False,
              }
            ],
          }
        ],
      }
    )
    assert attached == (
      "`reply`\n> one\n> \n> > two\n"
      "> attachments: saved.html: /state/uploads/saved.html (missing)\n\nreply text"
    )


def test_attachment_size_reads_short():
  # A size reads in B, KB or MB, whichever keeps the line short, so the agent sees the
  # scale without a long byte count in the read.
  assert preview.format_size(0) == "0 B"
  assert preview.format_size(999) == "999 B"
  assert preview.format_size(1024) == "1 KB"
  assert preview.format_size(1536) == "1.5 KB"
  assert preview.format_size(5000000) == "4.8 MB"
  assert preview.format_size(50000000) == "47.7 MB"


def test_note_owns_one_attachment():
  with tempfile.TemporaryDirectory() as attached_dir:
    attached = preview.Store(attached_dir, create=True)
    raw = bytes(range(256)) + b"\r\nline two\x00"
    with patch.object(preview.time, "time", return_value=1_760_000_000):
      note = attached.note_with_uploads(
        "linked-note",
        "Read this file",
        [("old name.bin", "application/octet-stream", raw)],
      )
    assert note["id"] == "linked-note" and note["text"] == "Read this file"
    record = attached.uploads()[0]
    assert record["name"] == "old name.bin" and record["size"] == len(raw)
    assert Path(record["path"]).name == "linked-1760000000-old-name.bin"
    assert Path(record["path"]).read_bytes() == raw
    assert [item["id"] for item in attached.read()["pending"]] == ["linked-note"]
    assert attached.state()["notes"][0]["attachment_name"] == "old name.bin"
    assert attached.read()["pending"][0]["attachment_path"] == record["path"]
    attached.acknowledge(["linked-note"], "Seen")
    again = attached.note_with_uploads(
      "linked-note",
      "Read this file",
      [("old name.bin", "application/octet-stream", raw)],
    )
    assert (
      preview.clip_stamp(again["acknowledged_at"])
      == attached.state()["notes"][0]["acknowledged_at"]
    )
    assert len(attached.uploads()) == 1 and len(attached.state()["notes"]) == 1
    for text, content in (("Different text", raw), ("Read this file", b"different")):
      try:
        attached.note_with_uploads(
          "linked-note", text, [("old name.bin", "application/octet-stream", content)]
        )
        raise AssertionError("A reused note ID replaced an attachment or its text")
      except ValueError:
        pass
    assert Path(record["path"]).read_bytes() == raw


def test_multi_file_note():
  # A several-file send stays one note. Every file has its own record, all records point at the note,
  # and identical retries preserve the note's receipt and the stored bytes without duplicate records.
  with tempfile.TemporaryDirectory() as multi_dir:
    multi = preview.Store(multi_dir, create=True)
    files = [
      ("first photo.png", "image/png", b"PNG\x00\xff"),
      ("another.bin", "application/octet-stream", b"\x00\x01"),
      ("last photo.png", "image/png", b"raw\r\nline"),
    ]
    with patch.object(preview.time, "time", return_value=1_760_000_000):
      saved = multi.note_with_uploads("several-note", "Three files", files)
    assert saved["id"] == "several-note" and len(saved["attachments"]) == 3
    assert [item["name"] for item in saved["attachments"]] == [
      file[0] for file in files
    ]
    assert saved["attachments"][0]["id"] == "several-note"
    assert len({item["id"] for item in saved["attachments"]}) == 3
    assert [Path(item["path"]).name for item in saved["attachments"]] == [
      "severa-1760000000-first-photo.png",
      "severa-1760000000-another.bin",
      "severa-1760000000-last-photo.png",
    ]
    assert [Path(item["path"]).read_bytes() for item in saved["attachments"]] == [
      file[2] for file in files
    ]
    assert [item["note_id"] for item in multi.uploads()] == ["several-note"] * 3
    assert [item["id"] for item in multi.read()["pending"]] == ["several-note"]
    assert [item["name"] for item in multi.state()["notes"][0]["attachments"]] == [
      file[0] for file in files
    ]
    multi.acknowledge(["several-note"], "Read all three")
    again = multi.note_with_uploads("several-note", "Three files", files)
    assert (
      preview.clip_stamp(again["acknowledged_at"])
      == multi.state()["notes"][0]["acknowledged_at"]
    )
    assert len(multi.state()["notes"]) == 1 and len(multi.uploads()) == 3
    for changed in ([*files[:2], ("last photo.png", "image/png", b"other")], files[:2]):
      try:
        multi.note_with_uploads("several-note", "Three files", changed)
        raise AssertionError("A retry changed the saved file set")
      except ValueError:
        pass
    assert [Path(item["path"]).read_bytes() for item in saved["attachments"]] == [
      file[2] for file in files
    ]
    try:
      multi.note_with_uploads(
        "rejected-note", "Incomplete", [files[0], ("empty.bin", "", b"")]
      )
      raise AssertionError("An invalid file committed part of a note")
    except ValueError:
      pass
    assert len(multi.state()["notes"]) == 1 and len(multi.uploads()) == 3
    missing = Path(saved["attachments"][1]["path"])
    missing.unlink()
    assert multi.state()["notes"][0]["attachments"][1]["present"] is False
    multi.note_with_uploads("several-note", "Three files", files)
    assert missing.read_bytes() == files[1][2], (
      "an identical retry repairs missing bytes"
    )
    with patch.object(
      multi, "note", side_effect=RuntimeError("simulated note write error")
    ):
      try:
        multi.note_with_uploads("rolled-back", "Do not save", files[:2])
        raise AssertionError("The injected note error never fired")
      except RuntimeError as error:
        assert "simulated note write error" in str(error)
    assert len(multi.state()["notes"]) == 1 and len(multi.uploads()) == 3
    assert not any(Path(multi_dir, "uploads").glob("rolled-back*"))


def test_upload_filenames_are_unique():
  with tempfile.TemporaryDirectory() as name_dir:
    store = preview.Store(name_dir, create=True)
    files = [
      ("same photo.png", "image/png", b"one"),
      ("same photo.png", "image/png", b"two"),
      ("same photo.png", "image/png", b"three"),
    ]
    with patch.object(preview.time, "time", return_value=1_760_000_000):
      first = store.note_with_uploads("abcdefg-one", "Three files", files)
      second = store.note_with_uploads(
        "abcdefg-two", "Same prefix and name", [files[0]]
      )
    names = [Path(item["path"]).name for item in first["attachments"]]
    second_record = second["attachments"][0]
    names.append(Path(second_record["path"]).name)
    assert names == [
      "abcdef-1760000000-same-photo.png",
      "abcdef-1760000000-2-same-photo.png",
      "abcdef-1760000000-3-same-photo.png",
      "abcdef-1760000000-4-same-photo.png",
    ]
    assert [
      Path(item["path"]).read_bytes() for item in [*first["attachments"], second_record]
    ] == [
      b"one",
      b"two",
      b"three",
      b"one",
    ]
    assert [item["name"] for item in [*first["attachments"], second_record]] == [
      "same photo.png",
      "same photo.png",
      "same photo.png",
      "same photo.png",
    ]


def test_upload_record_migration():
  # Migration backfills existing single-file upload records so their parent note still shows a
  # filename after this schema introduces note_id. Stored bytes are not renamed or removed.
  with tempfile.TemporaryDirectory() as old_upload_dir:
    old_db = Path(old_upload_dir) / "state.sqlite3"
    with sqlite3.connect(old_db) as db:
      db.execute(
        "CREATE TABLE uploads (seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, "
        "name TEXT NOT NULL, type TEXT NOT NULL, size INTEGER NOT NULL, "
        "sha256 TEXT NOT NULL, file TEXT NOT NULL, at TEXT NOT NULL)"
      )
      db.execute(
        "INSERT INTO uploads (id, name, type, size, sha256, file, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
          "old-file",
          "photo.png",
          "image/png",
          3,
          hashlib.sha256(b"PNG").hexdigest(),
          "old-file.png",
          "2026-09-22T00:00:00+00:00",
        ),
      )
    Path(old_upload_dir, "uploads").mkdir()
    Path(old_upload_dir, "uploads", "old-file.png").write_bytes(b"PNG")
    migrated = preview.Store(old_upload_dir)
    old_record = migrated.uploads()[0]
    assert old_record["note_id"] == "old-file"
    migrated.note("old-file", "Upload: photo.png")
    assert migrated.state()["notes"][0]["attachments"][0]["name"] == "photo.png"
    assert Path(old_record["path"]).read_bytes() == b"PNG"


def test_http_note_attachment():
  global app
  with tempfile.TemporaryDirectory() as attached_http_dir:
    attached_http = preview.Store(attached_http_dir, create=True)
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(attached_http))
    worker = threading.Thread(target=app.serve_forever, daemon=True)
    worker.start()
    try:
      boundary = b"preview-attachment-test"

      def part(name, content, extra=b""):
        return (
          b"--"
          + boundary
          + b'\r\nContent-Disposition: form-data; name="'
          + name
          + b'"'
          + extra
          + b"\r\n\r\n"
          + content
          + b"\r\n"
        )

      binary = b"\x00\xff\r\nraw bytes\x00"
      body = (
        part(b"id", b"http-note")
        + part(b"text", b"Please see attachment")
        + part(
          b"file", binary, b'; filename="old photo.png"\r\nContent-Type: image/png'
        )
        + b"--"
        + boundary
        + b"--\r\n"
      )
      headers = {
        "Content-Type": "multipart/form-data; boundary=preview-attachment-test",
      }
      assert (
        request(
          "POST",
          "/api/notes/with-file",
          b"{}",
          {"Content-Type": "application/json"},
        )[0]
        == 415
      )
      invalid_header = {**headers, "Content-Type": "multipart/form-data; boundary=é"}
      assert request("POST", "/api/notes/with-file", body, invalid_header)[0] == 400
      with patch.object(preview.time, "time", return_value=1_760_000_000):
        status, _, payload = request("POST", "/api/notes/with-file", body, headers)
      saved = json.loads(payload)
      assert status == 201 and saved["id"] == "http-note"
      assert saved["attachment_name"] == "old photo.png"
      assert Path(saved["attachment_path"]).name == "http-n-1760000000-old-photo.png"
      assert Path(saved["attachment_path"]).read_bytes() == binary
      assert [item["id"] for item in attached_http.read()["pending"]] == ["http-note"]
      assert request("POST", "/api/notes/with-file", body, headers)[0] == 201
      assert len(attached_http.uploads()) == len(attached_http.state()["notes"]) == 1
      closing = b"--" + boundary + b"--\r\n"
      invalid = body[: -len(closing)] + part(b"extra", b"no") + closing
      assert request("POST", "/api/notes/with-file", invalid, headers)[0] == 400
      several = (
        part(b"id", b"http-several")
        + part(b"text", b"Several files")
        + part(b"file", b"abc", b'; filename="a.txt"\r\nContent-Type: text/plain')
        + part(
          b"file",
          b"\x00\xff",
          b'; filename="b.bin"\r\nContent-Type: application/octet-stream',
        )
        + closing
      )
      status, _, payload = request("POST", "/api/notes/with-file", several, headers)
      received = json.loads(payload)
      assert status == 201 and received["id"] == "http-several"
      assert [item["name"] for item in received["attachments"]] == ["a.txt", "b.bin"]
      assert [
        re.fullmatch(rf"http-s-\d+-{re.escape(name)}", Path(item["path"]).name)
        is not None
        for item, name in zip(received["attachments"], ("a.txt", "b.bin"))
      ] == [True, True]
      assert [Path(item["path"]).read_bytes() for item in received["attachments"]] == [
        b"abc",
        b"\x00\xff",
      ]
      assert request("POST", "/api/notes/with-file", several, headers)[0] == 201
      assert (
        len(attached_http.state()["notes"]) == 2 and len(attached_http.uploads()) == 3
      )
      bad = (
        several[: -len(closing)]
        + part(b"file", b"other", b'; filename="c.txt"')
        + closing
      )
      assert request("POST", "/api/notes/with-file", bad, headers)[0] == 400
      assert (
        len(attached_http.state()["notes"]) == 2 and len(attached_http.uploads()) == 3
      )
      six = (
        part(b"id", b"http-six")
        + part(b"text", b"Six files")
        + b"".join(
          part(
            b"file",
            f"content-{n}".encode(),
            f'; filename="f{n}.txt"\r\nContent-Type: text/plain'.encode("ascii"),
          )
          for n in range(6)
        )
        + closing
      )
      status, _, payload = request("POST", "/api/notes/with-file", six, headers)
      received = json.loads(payload)
      assert status == 201 and received["id"] == "http-six"
      assert [item["name"] for item in received["attachments"]] == [
        f"f{n}.txt" for n in range(6)
      ]
      assert [
        re.fullmatch(rf"http-s-\d+-f{n}\.txt", Path(item["path"]).name) is not None
        for n, item in enumerate(received["attachments"])
      ] == [True] * 6
    finally:
      app.shutdown()
      app.server_close()
      worker.join()


def test_download_queue():
  global app
  with tempfile.TemporaryDirectory() as queue_dir:
    queue_store = preview.Store(Path(queue_dir) / "state", create=True)
    queue_store.set_meta("port", guard_port())
    assert queue_store.state()["fetch_jobs"] == []
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(queue_store))
    worker = threading.Thread(target=app.serve_forever, daemon=True)
    worker.start()
    try:
      page = request("GET", "/")[2]
      auth = {"Content-Type": "application/json"}
      assert request("GET", "/api/fetch-jobs")[0] == 404
      assert request("GET", "/downloads/file.zip")[0] == 404
      assert 'id="downloads-pip"' in page and 'id="fetch-approvals"' in page
      assert request("POST", "/api/fetch-jobs", "{}")[0] == 415
      assert request("POST", "/api/fetch-jobs", "{}", {})[0] == 415
      for value in (
        "http://example.org/a",
        "https://user:pass@example.org/a",
        "https://x.org/a b",
        "bad",
      ):
        status, _, error = request(
          "POST", "/api/fetch-jobs", json.dumps({"url": value}), auth
        )
        assert status == 400 and json.loads(error)["error"], value
      assert (
        request(
          "POST",
          "/api/fetch-jobs",
          json.dumps({"url": "https://example.org/a", "allow_proxy": "yes"}),
          auth,
        )[0]
        == 400
      )
      # An agent CLI request is visible, but no browser worker can claim it before the preview
      # receives an Approve click. The owner-entered HTTP form below still queues immediately.
      command = [sys.executable, preview.__file__]
      queue_env = {
        **os.environ,
        "ARENA_PREVIEW_STATE_DIR": str(queue_store.path.parent),
      }
      agent_request = subprocess.run(
        [
          *command,
          "download-request",
          "https://example.org/review.zip#fragment",
          "--allow-proxy",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=queue_env,
      )
      assert "https://example.org/review.zip" in agent_request.stdout
      assert "pending" in agent_request.stdout and "queued" in agent_request.stdout
      pending_id = agent_request.stdout.split()[1]
      pending = {"id": pending_id}
      assert queue_store.claim_fetch() is None
      assert (
        json.loads(request("POST", "/api/fetch-jobs/claim", "{}", auth)[2])["job"]
        is None
      )
      assert (
        json.loads(request("GET", "/api/state")[2])["fetch_jobs"][0]["approval"]
        == "pending"
      )
      approve = f"/api/fetch-jobs/{pending['id']}/approve"
      assert request("POST", approve, "{}")[0] == 415
      assert request("POST", approve, "{}", auth)[0] == 200
      assert request("POST", approve, "{}", auth)[0] == 409, (
        "a second click must not decide twice"
      )
      assert (
        request("POST", f"/api/fetch-jobs/{pending['id']}/deny", "{}", auth)[0] == 409
      )
      approved = queue_store.claim_fetch()
      assert approved["id"] == pending["id"] and approved["approval"] == "approved"
      queue_store.fail_fetch(
        pending["id"], approved["claim"], "Test browser unavailable"
      )
      denied = queue_store.enqueue_fetch(
        "https://example.org/no.zip", False, pending=True
      )
      assert (
        request("POST", f"/api/fetch-jobs/{denied['id']}/deny", "{}", auth)[0] == 200
      )
      assert (
        request("POST", f"/api/fetch-jobs/{denied['id']}/retry", "{}", auth)[0] == 409
      )
      assert (
        request("POST", f"/api/fetch-jobs/{denied['id']}/approve", "{}", auth)[0] == 409
      )
      assert queue_store.claim_fetch() is None
      reopened = preview.Store(queue_store.path.parent).fetch_jobs()
      assert reopened[0]["approval"] == "denied" and reopened[0]["status"] == "failed"
      assert reopened[0]["error"] == "Denied in the preview"
      assert queue_store.state()["notes"] == [], "denial should not claim or save bytes"
      bad_request = subprocess.run(
        [*command, "download-request", "http://example.org/unsafe"],
        capture_output=True,
        text=True,
        check=False,
        env=queue_env,
      )
      assert bad_request.returncode != 0 and "HTTPS" in bad_request.stderr

      status, _, queued = request(
        "POST",
        "/api/fetch-jobs",
        json.dumps({"url": "https://example.org/one.zip#fragment"}),
        auth,
      )
      job = json.loads(queued)
      assert status == 201 and job["url"] == "https://example.org/one.zip"
      assert job["status"] == "queued" and job["allow_proxy"] is False
      assert "claim" not in job and queue_store.claim_fetch()["id"] == job["id"]
      assert "claim" not in json.loads(request("GET", "/api/state")[2])["fetch_jobs"][0]
      assert (
        json.loads(request("POST", "/api/fetch-jobs/claim", "{}", auth)[2])["job"]
        is None
      )
      # Reclaiming an expired browser tab changes the secret, never the job ID.
      with queue_store.connect() as db, db:
        db.execute(
          "UPDATE fetch_jobs SET lease_until = '2000-01-01T00:00:00+00:00' WHERE id = ?",
          (job["id"],),
        )
      claim = json.loads(request("POST", "/api/fetch-jobs/claim", "{}", auth)[2])["job"]
      assert claim["id"] == job["id"] and claim["claim"]
      assert queue_store.renew_fetch(job["id"], claim["claim"])["status"] == "fetching"
      result_path = f"/api/fetch-jobs/{job['id']}/result?name=one.zip"
      headers = {
        **auth,
        "Content-Type": "application/zip",
        "X-Fetch-Claim": claim["claim"],
        "X-Fetch-Source": "direct",
      }
      assert (
        request("POST", result_path, b"PK", {**headers, "X-Fetch-Claim": "bad"})[0]
        == 409
      )
      assert (
        request(
          "POST", result_path, b"PK", {**headers, "X-Fetch-Source": "allorigins"}
        )[0]
        == 400
      )
      assert queue_store.fetch_jobs()[0]["status"] == "fetching"
      status, _, completed = request("POST", result_path, b"PK", headers)
      saved = json.loads(completed)
      assert status == 201 and saved["size"] == 2 and saved["source"] == "direct"
      assert saved["sha256"] == hashlib.sha256(b"PK").hexdigest()
      assert Path(saved["path"]).read_bytes() == b"PK" and saved["present"]
      assert Path(saved["path"]).parent.name == "downloads"
      assert queue_store.state()["notes"][-1]["id"] == job["id"]
      assert request("POST", result_path, b"PK", headers)[0] == 409
      # The owner's X removes the record and the bytes it staged.
      dropped = request("POST", f"/api/fetch-jobs/{job['id']}/drop", "{}", auth)
      assert dropped[0] == 200 and json.loads(dropped[2])["dropped"] == job["id"]
      assert all(item["id"] != job["id"] for item in queue_store.fetch_jobs())
      assert not Path(saved["path"]).exists()
      assert request("POST", f"/api/fetch-jobs/{job['id']}/drop", "{}", auth)[0] == 404
      saved_again = queue_store.enqueue_fetch("https://example.org/again.zip", False)
      claim_again = json.loads(request("POST", "/api/fetch-jobs/claim", "{}", auth)[2])[
        "job"
      ]
      assert (
        request("POST", f"/api/fetch-jobs/{saved_again['id']}/drop", "{}", auth)[0]
        == 409
      ), "an active download must not drop under its worker"
      queue_store.fail_fetch(saved_again["id"], claim_again["claim"], "stopped")
      Path(saved["path"]).unlink(missing_ok=True)
      assert preview.Store(queue_store.path.parent).fetch_jobs()[-1]["present"] is False
      assert queue_store.state()["notes"][-1]["id"] == job["id"]

      # A proxy source needs that job's opt-in. Failure and retry keep its URL and choice.
      proxy = queue_store.enqueue_fetch("https://example.org/proxy.zip", True)
      claim = json.loads(request("POST", "/api/fetch-jobs/claim", "{}", auth)[2])["job"]
      assert claim["id"] == proxy["id"] and claim["allow_proxy"]
      assert (
        request("POST", f"/api/fetch-jobs/{proxy['id']}/fail", "{}", auth)[0] == 409
      )
      failure = request(
        "POST",
        f"/api/fetch-jobs/{proxy['id']}/fail",
        json.dumps({"error": "CORS blocked"}),
        {**auth, "X-Fetch-Claim": claim["claim"]},
      )
      assert failure[0] == 200 and json.loads(failure[2])["error"] == "CORS blocked"
      assert queue_store.retry_fetch(proxy["id"])["status"] == "queued"
      claimed = queue_store.claim_fetch()
      assert claimed["id"] == proxy["id"] and claimed["claim"] != claim["claim"]
      proxy_headers = {
        **auth,
        "Content-Type": "application/zip",
        "X-Fetch-Claim": claimed["claim"],
        "X-Fetch-Source": "codetabs",
      }
      status, _, completed = request(
        "POST",
        f"/api/fetch-jobs/{proxy['id']}/result?name=proxy.zip",
        b"proxy",
        proxy_headers,
      )
      assert status == 201 and json.loads(completed)["source"] == "codetabs"

      # A completed claim cannot accept another body. The store keeps a large upload.
      status, _, _problem = request(
        "POST",
        f"/api/fetch-jobs/{proxy['id']}/result?name=large.bin",
        b"x",
        {
          **auth,
          **proxy_headers,
          "Content-Type": "application/octet-stream",
          "Content-Length": str(preview.SNAPSHOT_CAP_BYTES + 2),
        },
      )
      assert status == 409
      large = queue_store.save_upload(
        "large.bin", "application/octet-stream", b"x" * 5_000_001
      )
      assert (
        large["size"] == 5_000_001 and Path(large["path"]).stat().st_size == 5_000_001
      )

      # Competing tabs claim distinct rows even when both are ready at once.
      first = queue_store.enqueue_fetch("https://example.org/a", False)
      second = queue_store.enqueue_fetch("https://example.org/b", False)
      with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: queue_store.claim_fetch(), range(2)))
      assert {item["id"] for item in claims} == {first["id"], second["id"]}
      assert all("claim" in item for item in claims)
    finally:
      app.shutdown()
      app.server_close()
      worker.join()


def test_queue_upgrade():
  # Upgrading an existing queue must not strand owner-entered jobs. Conflicting decisions from two
  # preview tabs must not turn a denied request back into an approved one.
  with tempfile.TemporaryDirectory() as old_queue_dir:
    old_db = Path(old_queue_dir) / "state.sqlite3"
    with sqlite3.connect(old_db) as connection:
      connection.executescript("""
        CREATE TABLE fetch_jobs (
          seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, url TEXT NOT NULL,
          allow_proxy INTEGER NOT NULL CHECK (allow_proxy IN (0, 1)),
          status TEXT NOT NULL CHECK (status IN ('queued', 'fetching', 'saved', 'failed')),
          claim TEXT, lease_until TEXT, error TEXT, source TEXT,
          name TEXT, type TEXT, size INTEGER, sha256 TEXT, file TEXT,
          at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO fetch_jobs (id, url, allow_proxy, status, at, updated_at)
        VALUES ('older', 'https://example.org/older.zip', 0, 'queued',
          '2026-09-22T00:00:00+00:00', '2026-09-22T00:00:00+00:00');
      """)
    upgraded = preview.Store(old_queue_dir)
    assert upgraded.fetch_jobs()[0]["approval"] == "approved"
    assert upgraded.claim_fetch()["id"] == "older"
    racing = upgraded.enqueue_fetch("https://example.org/race.zip", False, pending=True)

    def decide(choice):
      try:
        return upgraded.decide_fetch(racing["id"], choice)
      except preview.FetchChanged as error:
        return error

    with ThreadPoolExecutor(max_workers=2) as pool:
      outcomes = list(pool.map(decide, ("approved", "denied")))
    assert sum(isinstance(item, preview.FetchChanged) for item in outcomes) == 1
    assert upgraded.fetch_jobs()[0]["approval"] in {"approved", "denied"}
    try:
      upgraded.decide_fetch(racing["id"], "pending")
      raise AssertionError("An invalid decision was accepted")
    except ValueError:
      pass


def test_default_save_path():
  # The default save file sits inside the state directory, so one globally ignored directory carries
  # the database and its export, and an explicit path still wins.
  with tempfile.TemporaryDirectory() as default_dir:
    default_root = Path(default_dir) / "arena-state"
    assert (
      preview.Store(default_root, create=True).save_path
      == default_root / "saved-state.ndjson"
    )
    moved = preview.Store(default_root, create=True, save_path="elsewhere.ndjson")
    assert moved.save_path == Path("elsewhere.ndjson")


def test_autosave_export():
  # Autosave: a committed mutation refreshes the export, bookkeeping does not, and a fresh
  # database never overwrites an export that outlived it.
  with tempfile.TemporaryDirectory() as autosave_dir:
    autosave_root = Path(autosave_dir) / "arena-state"
    autosave_store = preview.Store(autosave_root, create=True)
    assert not autosave_store.save_path.is_file()
    autosave_store.reminder(advance=True)
    autosave_store.set_meta("probe", "1")
    assert not autosave_store.save_path.is_file(), "bookkeeping wrote the export"
    autosave_store.note("autosave-note", "Written")
    first = autosave_store.save_path.read_text(encoding="utf-8")
    assert "autosave-note" in first
    autosave_store.reminder(advance=True)
    assert autosave_store.save_path.read_text(encoding="utf-8") == first
    autosave_store.acknowledge(["autosave-note"], "Receipt")
    assert "Receipt" in autosave_store.save_path.read_text(encoding="utf-8")
    autosave_task = autosave_store.write_task(
      "autosave-task", "Track it", ["Step one"], task_type="misc"
    )
    assert "autosave-task" in autosave_store.save_path.read_text(encoding="utf-8")
    assert autosave_task["id"] == "autosave-task"
    # A restore drops the database and keeps the export, so rebuilding must not touch it.
    autosave_store.save_path.write_text(first, encoding="utf-8")
    autosave_store.path.unlink()
    rebuilt = preview.Store(autosave_root, create=True)
    rebuilt.reminder(advance=True)
    assert rebuilt.save_path.read_text(encoding="utf-8") == first, (
      "a fresh database overwrote the export"
    )


def test_empty_reads_do_not_autosave(tmp_path, monkeypatch):
  store = preview.Store(tmp_path, create=True)
  saves = []
  save = store.autosave

  def record_save():
    saves.append(True)
    save()

  monkeypatch.setattr(store, "autosave", record_save)
  preview.print_read(store)
  assert saves == [], "an empty CLI read wrote the export"
  assert store.meta_value("last_check")
  assert store.read(include_quiet=False)["pending"] == []
  assert saves == [], "an idle poll read wrote the export"
  store.note("saved-note", "Keep content saves")
  assert saves
  saves.clear()
  preview.print_read(store)
  assert saves, "delivery must save the Seen receipt"
  assert json.loads(store.save_path.read_text().splitlines()[0])["seen_at"]
  store.acknowledge(["saved-note"], "Keep receipts")
  assert "Keep receipts" in store.save_path.read_text()
  saves.clear()
  preview.print_read(store)
  assert saves == [], "an empty read with note history wrote the export"


def test_ndjson_omits_quiet_notes():
  """Quiet notes stay in live state but do not cross an NDJSON save and restore."""
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    store = preview.Store(root, create=True)
    store.note("quiet-note", "Do not save", quiet=True)
    store.note("visible-note", "Save this")
    saved = store.save_path.read_text(encoding="utf-8")
    assert "quiet-note" not in saved
    assert "visible-note" in saved
    restored = preview.Store(root / "restored", create=True)
    receipt = restored.import_state(saved)
    assert receipt["notes"] == 1
    assert [note["id"] for note in restored.state()["notes"]] == ["visible-note"]
    assert [note["id"] for note in store.state()["notes"]] == [
      "quiet-note",
      "visible-note",
    ]


def test_notes_carry_no_seq():
  # Note and answer records carry no seq: the arrival stamp orders and identifies a
  # note, and a surfaced sequence number only invites citing it instead of the ID.
  with tempfile.TemporaryDirectory() as seq_dir:
    store = preview.Store(seq_dir, create=True)
    store.note("seq-first", "First stamp", at="2026-10-08T05:00:00+00:00")
    store.note("seq-second", "Second stamp", at="2026-10-08T05:00:01+00:00")
    store.note("seq-late", "Later stamp", at="2026-10-08T05:00:05+00:00")
    store.note("seq-early", "Earlier stamp", at="2026-10-08T05:00:02+00:00")
    notes = store.state()["notes"]
    assert "seq" not in notes[0], (
      "a note record carries its arrival stamp, not a number"
    )
    assert [row["id"] for row in notes] == [
      "seq-first",
      "seq-second",
      "seq-early",
      "seq-late",
    ], "the order follows the timestamps"
    pending = store.read()["pending"]
    assert pending and all("seq" not in item for item in pending)
    source = Path(seq_dir) / "select.md"
    source.write_text("# Select\n\nChoice? {#select}\n- (x) one\n", encoding="utf-8")
    store.publish("select", "Select one", source)
    store.submission("seq-answer", "select", "REPORT select: one")
    answer = store.submissions()[0]
    assert "seq" not in answer, "an answer record carries its stamp, not a number"


def test_task_needs_one_detail():
  with tempfile.TemporaryDirectory() as detail_dir:
    store = preview.Store(detail_dir, create=True)
    try:
      store.write_task("bare", "Bare")
      raise AssertionError("A task without a detail was accepted")
    except ValueError:
      pass
    store.write_task("kept", "Kept", ["Step one"], task_type="misc")
    try:
      store.write_task("kept", details=[""])
      raise AssertionError("Clearing the last detail was accepted")
    except ValueError:
      pass
    assert store.list_tasks()[0]["details"] == ["Step one"]
    # An update that leaves the details alone keeps them.
    assert store.write_task("kept", status="finished")["details"] == ["Step one"]


def test_task_refuses_a_note_id_as_its_name():
  # A task named after the note it answers puts one ID on two things: the board and the log.
  # The write refuses a note ID and names the fix, so the agent gives the task a proper name instead.
  with tempfile.TemporaryDirectory() as note_id_dir:
    store = preview.Store(note_id_dir, create=True)
    store.set_meta("port", guard_port())
    for note_id in ("c6b0af0", "c6b0af0-462e549f387100613fcede90b"):
      try:
        store.write_task(
          note_id, "Named after the note", ["Step one"], task_type="misc"
        )
        raise AssertionError(f"A note ID was accepted as a task ID: {note_id}")
      except ValueError as error:
        assert "proper name" in str(error), error
    # A plain name still lands, and a name that only looks hex stays a name.
    store.write_task("fix-the-widget", "Name the job", ["Step one"], task_type="misc")
    store.write_task("deadbeef", "Eight hex characters", ["Step one"], task_type="misc")
    assert [task["id"] for task in store.list_tasks()] == ["fix-the-widget", "deadbeef"]
    # The CLI prints the same refusal for the agent to read.
    cli = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "task",
        "set",
        "954ee49-9ac144955adcda4bcbd227497",
        "Named after the note",
        "--details",
        "Step one",
      ],
      capture_output=True,
      text=True,
      check=False,
      cwd=note_id_dir,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(Path(note_id_dir))},
    )
    assert cli.returncode != 0, cli.stdout
    assert "proper name" in cli.stdout + cli.stderr


def test_task_dependencies_hold_the_cycle_and_the_order():
  """A task waits on named tasks and sorts after them. A cycle-closing edge fails."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.write_task("first", "First", ["Step one"], task_type="misc")
    store.write_task(
      "second", "Second", ["Step one"], task_type="misc", blocked_by=["first"]
    )
    second = store.task_record("second")
    assert second["blocked_by"] == ["first"]
    # The waiter follows its blocker, whatever the stored positions say.
    assert [item["id"] for item in store.list_tasks()] == ["first", "second"]
    assert preview.current_task(store.list_tasks())["id"] == "first"
    # An edge that closes a cycle names both tasks and lands nothing.
    for blocker in ("second", "third"):
      if blocker == "third":
        store.write_task(
          "third", "Third", ["Step one"], task_type="misc", blocked_by=["second"]
        )
      try:
        store.write_task(
          "first", "First", ["Step one"], task_type="misc", blocked_by=[blocker]
        )
        raise AssertionError(f"A cycle-closing edge landed: {blocker}")
      except ValueError as error:
        assert blocker in str(error) and "first" in str(error), error
    # A task may not wait on itself, and a blocker that names no task fails.
    for blocker, expected in (("first", "itself"), ("nowhere", "No task holds")):
      try:
        store.write_task("first", blocked_by=[blocker])
        raise AssertionError(f"A bad blocker landed: {blocker}")
      except ValueError as error:
        assert expected in str(error), error
    # Finishing the blocker frees the waiter for the current seat.
    store.write_task("first", status="finished")
    assert preview.current_task(store.list_tasks())["id"] == "second"
    # An empty list clears the edge.
    store.write_task("second", blocked_by=[])
    assert "blocked_by" not in store.task_record("second")


def test_task_detail_refuses_a_session_id():
  """A detail that cites a session ID names nothing a repository reader can resolve."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    note_id = "954ee49-9ac144955adcda4bcbd227497"
    store.note(note_id, "Look at this")
    for detail in (f"Fix {note_id}", "Fix 954ee49", "Copy from note 954ee49"):
      try:
        store.write_task("first-task", "First task", [detail], task_type="misc")
        raise AssertionError(f"A detail took a session ID: {detail}")
      except ValueError as error:
        assert "session-local" in str(error), error
    # A clean detail still lands, and a restore keeps the board it imports.
    task = store.write_task(
      "first-task", "First task", ["Fix the widget"], task_type="misc"
    )
    assert task["details"] == ["Fix the widget"]
    restored = store.write_task(
      "second-task", "Second task", ["Fix 954ee49"], task_type="misc", restoring=True
    )
    assert restored["details"] == ["Fix 954ee49"]
    # A written ID stays a plain word, so a detail may still describe a wait on it.
    source = Path(directory) / "select.md"
    source.write_text(
      "Select one: {#select}\n\n- ( ) yes\n- ( ) no\n", encoding="utf-8"
    )
    store.publish("select", "Select one", source)
    named = store.write_task(
      "named-task", "Named task", ["wait for the select"], task_type="misc"
    )
    assert named["details"] == ["wait for the select"]
    # An update that keeps the stored details runs the check on nothing.
    assert store.write_task("first-task", status="finished")["details"] == [
      "Fix the widget"
    ]
    # The CLI prints the same refusal for the agent to read.
    cli = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "task",
        "set",
        "third-task",
        "Third task",
        "--type",
        "misc",
        "--detail",
        "See 954ee49",
      ],
      capture_output=True,
      text=True,
      check=False,
      cwd=directory,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": directory},
    )
    assert cli.returncode != 0, cli.stdout
    assert "session-local" in cli.stdout + cli.stderr


def test_agent_line_drops_the_harness_wrapper():
  """A detached replay runs the agent's line, so the harness's working directory holds."""
  wrapped = "/bin/bash -l -c cd /home/user/repo && .venv/bin/python -m pytest -q"
  assert (
    preview.agent_line(wrapped) == "cd /home/user/repo && .venv/bin/python -m pytest -q"
  )
  assert preview.agent_line("bash -lc pytest -q") == "pytest -q"
  # A line the agent writes itself keeps its own shell.
  assert preview.agent_line("bash -c pytest -q") == "bash -c pytest -q"
  assert preview.agent_line("pytest -q") == "pytest -q"
  assert preview.agent_line("") == ""
  # The tick records the stripped line, so the child starts in the right directory.
  with tempfile.TemporaryDirectory() as wrapper_dir:
    with patch.dict(os.environ, {"ARENA_PREVIEW_DETACH_DRY": "1"}):
      assert preview.pr_check_wait(wrapper_dir, wrapped) == preview.PR_CHECK_RUNS
    record = json.loads(
      (Path(wrapper_dir) / "runs" / "pytest.json").read_text(encoding="utf-8")
    )
    assert record["argv"] == [
      "bash",
      "-c",
      "cd /home/user/repo && .venv/bin/python -m pytest -q",
    ]


def test_tick_lines_skip_the_serve_and_store_imports():
  """A tick that never renders, serves or opens state must not import those modules.

  The gate spawns this script for every line that names git or gh, so their import cost
  lands on every such command. argparse is not on the list: the tick runs main, and main
  builds the CLI before it dispatches, so that import stays.
  """
  with tempfile.TemporaryDirectory() as directory:
    result = subprocess.run(
      [
        sys.executable,
        "-X",
        "importtime",
        preview.__file__,
        "pre",
        "--line",
        "git status",
        "--command",
        "git status",
        "--done",
        "interrupt read-set remind main-local main-fresh bare proxy gate",
      ],
      capture_output=True,
      text=True,
      check=False,
      cwd=directory,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": directory},
    )
  assert result.returncode == 0, result.stderr
  for module in (
    "markdown_it",
    "http.server",
    "email.policy",
    "email.parser",
    "sqlite3",
  ):
    assert module not in result.stderr, f"{module} rides on every gated line"


def test_bare_ack_answers_the_one_pending_item():
  """A bare ack answers the one pending item, and two waiting items keep the ID required."""
  with tempfile.TemporaryDirectory() as bare_dir:
    store = preview.Store(bare_dir, create=True)
    store.set_meta("port", guard_port())
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": bare_dir}

    def cli(*arguments):
      return subprocess.run(
        [sys.executable, str(Path(preview.__file__)), *arguments],
        capture_output=True,
        text=True,
        check=False,
        env=env,
      )

    empty = cli("ack", "Nothing waits.")
    assert empty.returncode != 0, empty.stdout
    assert "No pending" in empty.stdout + empty.stderr
    store.note("bare-one", "One note waits")
    answered = cli("ack", "Answered without an ID.")
    assert answered.returncode == 0, answered.stderr
    assert answered.stdout.splitlines()[0] == "ok bare-o"
    assert store.read()["pending"] == []
    # Two pending items stay ambiguous, and the refusal names both.
    store.note("bare-two", "Second note")
    store.note("bare-three", "Third note")
    refused = cli("ack", "Which one?")
    combined = refused.stdout + refused.stderr
    assert refused.returncode != 0, combined
    assert "bare-two" in combined and "bare-three" in combined
    assert len(store.read()["pending"]) == 2


def test_bare_task_reads_the_stored_row():
  """A task ID alone prints the stored task, and the read writes nothing back."""
  with tempfile.TemporaryDirectory() as read_dir:
    store = preview.Store(read_dir, create=True)
    store.set_meta("port", guard_port())
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": read_dir}

    def cli(*arguments):
      return subprocess.run(
        [sys.executable, str(Path(preview.__file__)), *arguments],
        capture_output=True,
        text=True,
        check=False,
        env=env,
      )

    written = cli(
      "task",
      "set",
      "read-task",
      "Read the queue",
      "-S",
      "arena suite",
      "-d",
      "Step one",
      "-d",
      "Step two",
      "--type",
      "misc",
    )
    assert written.returncode == 0, written.stderr
    before = store.list_tasks()[0]
    read = cli("task", "show", "read-task")
    assert read.returncode == 0, read.stderr
    expected = (
      f"task {before['id']}, order {before['order']}, status {before['status']}, "
      f"type {before['type']}"
    )
    assert read.stdout.splitlines()[0] == expected
    assert "- Step one" in read.stdout and "- Step two" in read.stdout
    assert store.list_tasks()[0] == before
    source = Path(read_dir) / "linked.md"
    source.write_text("# Linked\n", encoding="utf-8")
    store.publish("linked", "Linked", source)
    long_detail = "A stored detail " * 30
    store.write_task("read-task", details=[long_detail], report_id="linked")
    report_text = "REPORT linked: " + "Report answer " * 30
    direct_text = "REPORT other: " + "Direct answer " * 30
    store.submission("answer-report", "linked", report_text)
    store.submission(
      "answer-both", "linked", "REPORT linked: both links", task_id="read-task"
    )
    store.submission("answer-direct", "other", direct_text, task_id="read-task")
    store.submission("answer-unrelated", "other", "Unrelated answer must stay out")

    def stored_content():
      with closing(store.connect()) as db:
        data = [
          line for line in db.iterdump() if not line.startswith('INSERT INTO "meta"')
        ]
        operational = {
          preview.REMINDER_CURSOR,
          preview.AGENT_SEEN_META,
          preview.TURN_ENDED_META,
        }
        meta = {
          row["key"]: row["value"]
          for row in db.execute("SELECT * FROM meta")
          if row["key"] not in operational
        }
      return data, meta

    before_read = stored_content()
    full_read = cli("task", "show", "read-task")
    assert full_read.returncode == 0, full_read.stderr
    assert long_detail in full_read.stdout
    assert report_text in full_read.stdout and direct_text in full_read.stdout
    linked = store.tasks()["upcoming"][0]["answers"]
    for answer in linked:
      assert full_read.stdout.count(answer["id"]) == 1
      assert answer["at"] in full_read.stdout
    assert full_read.stdout.index("answer-report") < full_read.stdout.index(
      "answer-both"
    )
    assert full_read.stdout.index("answer-both") < full_read.stdout.index(
      "answer-direct"
    )
    assert "answer-unrelated" not in full_read.stdout
    assert "Unrelated answer must stay out" not in full_read.stdout  # nonemo: NMT100
    assert stored_content() == before_read
    written_again = cli("task", "set", "read-task", "--append", "-d", "Another step")
    assert written_again.returncode == 0, written_again.stderr
    assert long_detail not in written_again.stdout
    assert report_text not in written_again.stdout
    listed = cli("task", "list")
    assert listed.returncode == 0, listed.stderr
    assert long_detail in listed.stdout
    # The listing matches the page: both linked answers show, the unrelated one stays out.
    assert report_text in listed.stdout and direct_text in listed.stdout
    assert "Unrelated answer must stay out" not in listed.stdout  # nonemo: NMT100
    store.write_task("read-task", status="finished")
    finished = cli("task", "show", "read-task")
    assert finished.returncode == 0, finished.stderr
    assert long_detail in finished.stdout and report_text in finished.stdout
    store.unpublish("linked", dismissed_by_owner=True)
    retained = cli("task", "show", "read-task")
    assert retained.returncode == 0, retained.stderr
    assert report_text in retained.stdout and direct_text in retained.stdout
    assert retained.stdout.count("answer-both") == 1
    assert "answer-unrelated" not in retained.stdout
    missing = cli("task", "show", "read-nothing")
    assert missing.returncode != 0
    assert "No task is stored under read-nothing." in missing.stdout + missing.stderr


def test_init_reports_the_state_path():
  """The command names the database it used and whether the call made it."""
  with tempfile.TemporaryDirectory() as init_dir:
    # preview.main() may bootstrap itself, so the call runs as a subprocess.
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": init_dir}
    first = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "init"],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert first.returncode == 0, first.stderr
    line = first.stdout.strip()
    assert line.startswith("state "), line
    assert line.endswith(" created"), line
    assert str(Path(init_dir) / "state.sqlite3") in line
    # A second call reports the same path and leaves it alone.
    second = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "init"],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == line.replace(" created", " present")


def test_clear_state():
  with tempfile.TemporaryDirectory() as clear_dir:
    clear_root = Path(clear_dir)
    store = preview.Store(clear_root, create=True)
    store.set_meta("port", guard_port())
    store.note("clear-note", "Pending work")
    store.acknowledge(["clear-note"], "Receipt")
    store.write_task("clear-task", "Track it", ["Step one"], task_type="misc")
    source = clear_root / "select.md"
    source.write_text("# Select\n\nChoice? {#select}\n- (x) one\n", encoding="utf-8")
    store.publish("select", "Select one", source)
    store.submission("clear-answer", "select", "REPORT select: one")
    store.set_agent_key("clear-key-0123456789abcdef", "https://example.com")
    store.set_meta("probe", "1")
    counts = store.clear_state()
    assert counts == {
      "notes": 1,
      "reports": 1,
      "submissions": 1,
      "tasks": 1,
      "uploads": 0,
      "fetch_jobs": 0,
    }
    assert store.state()["notes"] == []
    assert store.state()["reports"] == []
    assert store.list_tasks() == []
    assert store.submissions() == []
    assert store.agent_key()["key"] == "clear-key-0123456789abcdef"
    assert store.meta_value("probe") is None
    assert "clear-note" not in store.save_path.read_text(encoding="utf-8")
    # The schema survives: the cleared store still writes.
    store.note("after-clear", "Written after the clear")
    assert [row["id"] for row in store.state()["notes"]] == ["after-clear"]
    # The CLI form clears the same way and prints the counts.
    cli = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "state", "clear"],
      capture_output=True,
      text=True,
      check=False,
      cwd=clear_dir,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(clear_root)},
    )
    assert cli.returncode == 0, cli.stderr
    assert "notes 1" in cli.stdout
    assert store.state()["notes"] == []
    assert store.path.is_file(), "the clear keeps the database file"


@pytest.mark.parametrize(
  ("source", "expected"),
  [
    (r"![shot\]](https://example.test/image.png)", "shot]"),
    (
      r"![outer ![shot\]](https://example.test/inner.png)](https://example.test/outer.png)",
      "outer shot]",
    ),
    (r"![shot\"\]\<script\>](https://example.test/image.png)", 'shot"]<script>'),
  ],
)
def test_render_image_retains_escaped_alt_text(source, expected):
  rendered = preview.render(source)
  assert f'alt="{html.escape(expected, quote=True)}"' in rendered
  assert "<script>" not in rendered


@pytest.mark.parametrize(
  ("source", "expected"),
  [
    (f"![`{text}`](https://example.test/image.png)", text)
    for text in ("inline code", '"]<script>&', r"a\b")
  ]
  + [
    ("![first  \nsecond](https://example.test/image.png)", "first\nsecond"),
    ("![first\nsecond](https://example.test/image.png)", "first\nsecond"),
  ],
)
def test_render_image_alt_retains_plain_text(source, expected):
  rendered = preview.render(source)
  assert f'alt="{html.escape(expected, quote=True)}"' in rendered
  assert "<script>" not in rendered


def test_image_data_uri_marks_down_a_png():
  """A local PNG becomes one Markdown line that carries its bytes as a data URI."""
  with tempfile.TemporaryDirectory() as image_dir:
    png = Path(image_dir) / "shot.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"payload")
    cli = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "image-data-uri", str(png)],
      capture_output=True,
      text=True,
      check=False,
    )
    assert cli.returncode == 0, cli.stderr
    payload = base64.b64encode(png.read_bytes()).decode("ascii")
    assert cli.stdout.strip() == f"![shot](data:image/png;base64,{payload})"


def test_image_data_uri_preserves_brackets_in_image_names():
  with tempfile.TemporaryDirectory() as image_dir:
    for name in ("shot].png", "shot[.png", "shot[1].png"):
      png = Path(image_dir) / name
      png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"payload")
      cli = subprocess.run(
        [sys.executable, str(Path(preview.__file__)), "image-data-uri", str(png)],
        capture_output=True,
        text=True,
        check=False,
      )
      assert cli.returncode == 0, cli.stderr
      rendered = preview.render(cli.stdout)
      payload = base64.b64encode(png.read_bytes()).decode("ascii")
      assert f'src="data:image/png;base64,{payload}"' in rendered
      assert f'alt="{png.stem}"' in rendered


def test_image_data_uri_refuses_a_non_image():
  """The command refuses a file with no image magic before any encoding work."""
  with tempfile.TemporaryDirectory() as image_dir:
    other = Path(image_dir) / "notes.txt"
    other.write_text("plain words", encoding="utf-8")
    cli = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "image-data-uri", str(other)],
      capture_output=True,
      text=True,
      check=False,
    )
    assert cli.returncode == 1, cli.stdout
    assert not cli.stdout and str(other) in cli.stderr


def test_image_data_uri_refuses_a_file_over_the_cap():
  """The size check runs on a valid image before the command encodes the bytes."""
  with tempfile.TemporaryDirectory() as image_dir:
    big = Path(image_dir) / "big.png"
    big.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * preview.IMAGE_DATA_URI_MAX_BYTES)
    cli = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "image-data-uri", str(big)],
      capture_output=True,
      text=True,
      check=False,
    )
    assert cli.returncode == 1, cli.stdout
    assert not cli.stdout and "cap" in cli.stderr


def test_image_payload_refuses_growth_after_the_size_check(tmp_path, monkeypatch):
  image = tmp_path / "growing.png"
  image.write_bytes(b"\x89PNG\r\n\x1a\n")
  original_open = Path.open

  def grow_before_open(path, mode="r", *args, **kwargs):
    if path == image and mode == "rb":
      with original_open(path, "ab") as output:
        output.write(b"x" * preview.IMAGE_DATA_URI_MAX_BYTES)
    return original_open(path, mode, *args, **kwargs)

  monkeypatch.setattr(Path, "open", grow_before_open)
  try:
    preview.image_payload(image)
  except ValueError as error:
    assert "cap" in str(error)
  else:
    raise AssertionError("Image growth bypassed the byte cap")


def test_legacy_note_import():

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
    db.execute(
      "INSERT INTO notes (id, text, at, acknowledged_at)"
      " VALUES ('answered', 'kept', '2026-01-01T00:00:00+00:00', '2026-01-02T00:00:00+00:00')"
    )
    db.commit()
    db.close()
    migrated = preview.Store(legacy, create=True)
    assert [row["id"] for row in migrated.state()["notes"]] == ["old", "answered"]
    assert migrated.state()["notes"][1]["seen_at"] == "2026-01-02T00:00:00"
    migrated.acknowledge(["old"], "still here")
    assert migrated.state()["notes"][0]["ack_text"] == "still here"
    assert migrated.state()["notes"][0]["seen_at"] is not None


def test_seen_receipts():
  with tempfile.TemporaryDirectory() as seen_dir:
    unread = preview.Store(seen_dir, create=True)
    unread.note("s-1", "unread")
    assert unread.state()["notes"][0]["seen_at"] is None
    listing = unread.read()
    assert unread.state()["notes"][0]["seen_at"] is None
    assert [row["id"] for row in listing["pending"]] == ["s-1"]
    assert listing["pending"][0]["seen_at"] is None
    unread.note("s-2", "arrived after the read")
    unread.submission("answer-1", "form", "REPORT form Answers:\n  Choice: yes")
    for ids in (["s-1", "missing"], ["s-1", "invalid id"]):
      try:
        unread.mark_seen(ids)
        raise AssertionError("Invalid Seen batch accepted")
      except ValueError:
        assert unread.state()["notes"][0]["seen_at"] is None
    unread.mark_seen(["s-1", "answer-1"])
    stamped = unread.state()["notes"][0]["seen_at"]
    assert stamped is not None
    assert unread.state()["notes"][1]["seen_at"] is None
    assert unread.submissions()[0]["seen_at"] is not None
    assert unread.submissions()[0]["acknowledged_at"] is None
    with patch.object(preview, "now", return_value="2099-01-01T00:00:00"):
      unread.mark_seen(["s-1"])
    assert unread.state()["notes"][0]["seen_at"] == stamped
    unread.read()
    assert unread.state()["notes"][0]["seen_at"] == stamped
    unread.acknowledge(["s-1"], "read, then answered")
    assert unread.state()["notes"][0]["seen_at"] == stamped


def test_read_stamps_on_delivery():
  with tempfile.TemporaryDirectory() as printed_dir:
    # A successful CLI write stamps printed IDs Seen. A failed write leaves the note for the next read.
    # Pending IDs still print until acknowledgement.
    printed = preview.Store(printed_dir, create=True)
    printed.set_meta("port", guard_port())
    printed.note("p-1", "printed once")
    printed.submission("answer-2", "form", "REPORT form Answers:\n  Choice: no")
    with patch.object(builtins, "print", side_effect=OSError("dropped delivery")):
      try:
        preview.print_read(printed)
        raise AssertionError("A failed read write must raise")
      except OSError:
        pass
    assert printed.state()["notes"][0]["seen_at"] is None
    assert printed.submissions()[0]["seen_at"] is None
    preview.print_read(printed)
    first = printed.state()["notes"][0]["seen_at"]
    assert first is not None
    assert printed.submissions()[0]["seen_at"] is not None
    assert [row["id"] for row in printed.read()["pending"]] == ["p-1", "answer-2"]
    with patch.object(preview, "now", return_value="2099-01-01T00:00:00"):
      preview.print_read(printed)
    assert printed.state()["notes"][0]["seen_at"] == first
    # The dispatched command stamps what it printed, end to end.
    subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "read",
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(printed_dir)},
    )
    assert printed.state()["notes"][0]["seen_at"] == first
    printed.acknowledge(["p-1"], "answered after the stamp")
    assert [row["id"] for row in printed.read()["pending"]] == ["answer-2"]


def test_report_agent_seen_receipt():
  # A read or a poll that delivers an answer stamps the parent report's agent receipt.
  # the owner's unread stamp stays its own field, and a stale receipt waits for the new answer.
  with tempfile.TemporaryDirectory() as receipt_dir:
    receipt = preview.Store(receipt_dir, create=True)
    source = Path(receipt_dir) / "form.md"
    source.write_text("Choice?\n- ( ) Yes\n- ( ) No\n\nCustom response: ___\n")
    field = preview.parse_fields(source.read_text())[1][0]
    receipt.publish("form", "Form", source)
    with patch.object(preview, "now", return_value="2026-09-30T04:05:00"):
      receipt.submit_report(
        "form",
        "answer-1",
        {field["id"]: field["options"][0]},
        receipt.report("form")["updated_at"],
      )
    assert receipt.state()["reports"][0]["agent_seen_at"] is None
    with patch.object(preview, "now", return_value="2026-09-30T04:10:00"):
      preview.print_read(receipt)
    row = receipt.state()["reports"][0]
    assert row["agent_seen_at"] == "2026-09-30T04:10:00"
    assert row["seen_at"] is None and row["ever_seen"] == 0
    # An answer newer than the receipt hides it until a read delivers that answer.
    with receipt.connect() as db, db:
      db.execute(
        "UPDATE submissions SET at = '2099-01-01T00:00:00' WHERE id = 'answer-1'"
      )
    assert receipt.state()["reports"][0]["agent_seen_at"] is None
    with receipt.connect() as db, db:
      db.execute(
        "UPDATE submissions SET at = '2026-09-30T04:00:00' WHERE id = 'answer-1'"
      )
    with patch.object(preview, "now", return_value="2026-09-30T04:11:00"):
      preview.poll_inbox(receipt, sleeper=lambda seconds: None)
    assert receipt.state()["reports"][0]["agent_seen_at"] == "2026-09-30T04:11:00"
    # An ack implies the read: the receipt moves forward with it and the answer gains Seen.
    with patch.object(preview, "now", return_value="2026-09-30T04:12:00"):
      receipt.acknowledge(["answer-1"], "Read and answered")
    assert receipt.state()["reports"][0]["agent_seen_at"] == "2026-09-30T04:12:00"
    assert receipt.submissions()[0]["seen_at"] is not None


def test_report_agent_seen_migration():
  # An older reports table gains the receipt column, and a fresh row reports nothing.
  with tempfile.TemporaryDirectory() as receipt_migration_dir:
    old_db = Path(receipt_migration_dir) / "state.sqlite3"
    with sqlite3.connect(old_db) as db:
      db.execute(
        "CREATE TABLE reports (id TEXT PRIMARY KEY, title TEXT NOT NULL,"
        " markdown TEXT NOT NULL, updated_at TEXT NOT NULL, seq INTEGER, seen_at TEXT,"
        " ever_seen INTEGER NOT NULL DEFAULT 0)"
      )
      db.execute(
        "INSERT INTO reports (id, title, markdown, updated_at, seq) VALUES (?, ?, ?, ?, ?)",
        ("old", "Old", "Text", "2026-09-20T00:00:00+00:00", 1),
      )
    migrated = preview.Store(receipt_migration_dir)
    assert migrated.report("old")["agent_seen_at"] is None
    migrated.mark_reports_agent_seen(["old"])
    # The row keeps the receipt. The state hides it while no answer exists to read.
    assert migrated.report("old")["agent_seen_at"] is not None
    assert migrated.state()["reports"][0]["agent_seen_at"] is None


def test_bare_task_list_names_and_asks_about_the_current_task():
  # The bare list names and asks about the first unblocked task. The page gives it its own div.
  # `--full` still prints every task, finished included, so the order stays readable.
  with tempfile.TemporaryDirectory() as bare_dir:
    bare = preview.Store(bare_dir, create=True)
    bare.write_task(
      "done-one", "Finished work", ["Step one"], status="finished", task_type="misc"
    )
    bare.write_task("first", "First upcoming", ["Step one"], task_type="misc")
    bare.write_task("second", "Second upcoming", ["Step one"], task_type="misc")
    lines = preview.format_task_list(bare.list_tasks()).splitlines()
    assert lines[0] == "Tasks 2 upcoming"
    assert "current first" in lines[1]
    assert sum(line.rstrip().endswith("?") for line in lines) == 1
    assert any("upcoming second" in line for line in lines)
    assert lines.count("    Step one") == len(bare.list_tasks()) - 1
    assert "done-one" not in "\n".join(lines)
    full = preview.format_task_list(bare.list_tasks(), full=True).splitlines()
    assert full[0] == "Tasks 3"
    assert "done-one" in "\n".join(full)
    assert "current" not in "\n".join(full)
    assert not any(line.rstrip().endswith("?") for line in full)
    bare.write_task("first", blocked=True)
    held = preview.format_task_list(bare.list_tasks()).splitlines()
    assert any("upcoming first" in line and "*" in line for line in held)
    assert any("current second" in line for line in held)
    assert next(i for i, line in enumerate(held) if "current second" in line) < next(
      i for i, line in enumerate(held) if "upcoming first" in line
    )
    assert sum(line.rstrip().endswith("?") for line in held) == 1
    assert "* = blocked on a report answer or linked run" in held
    assert preview.current_task(bare.list_tasks())["id"] == "second"
    # With every upcoming task blocked, no task reads as current work.
    bare.write_task("second", blocked=True)
    waiting = preview.format_task_list(bare.list_tasks()).splitlines()
    assert "current" not in "\n".join(waiting)
    assert not any(line.rstrip().endswith("?") for line in waiting)
    assert preview.current_task(bare.list_tasks()) is None
    bare.write_task("second", blocked=False)
    # An empty queue reads as empty rather than printing a lone header count of one.
    empty = preview.Store(bare_dir + "-empty", create=True)
    assert preview.format_task_list(empty.list_tasks()).splitlines() == [
      "Tasks 0 upcoming"
    ]


def test_submission_unlink_preserves_history_and_restore(tmp_path):
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  for task_id in ("first-task", "second-task"):
    store.write_task(
      task_id, "Task", ["Keep this step"], task_type="code", report_id="review"
    )
  store.submission("old-answer", "review", "Old answer", task_id="first-task")
  store.submission("new-answer", "review", "Current answer")
  store.submission(
    "direct-answer", "removed-report", "Direct answer", task_id="first-task"
  )
  store.acknowledge(["old-answer"], "Received")
  tasks_before = [store.task_record(name) for name in ("first-task", "second-task")]
  before = {item["id"]: item for item in store.submissions()}
  env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)}

  def cli(answer_id):
    return subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "task", "unlink", answer_id],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )

  for answer_id in ("old-answer", "direct-answer", "old-answer"):
    result = cli(answer_id)
    assert result.returncode == 0, result.stderr
  for task in store.list_tasks():
    assert [answer["id"] for answer in task["answers"]] == ["new-answer"]
  after = {item["id"]: item for item in store.submissions()}
  assert after.keys() == before.keys()
  for answer_id, original in before.items():
    assert {
      key: value for key, value in after[answer_id].items() if key != "task_id"
    } == {key: value for key, value in original.items() if key != "task_id"}
  assert [
    store.task_record(name) for name in ("first-task", "second-task")
  ] == tasks_before
  ack = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "ack", "direct-answer", "Received"],
    capture_output=True,
    text=True,
    check=False,
    env=env,
  )
  assert ack.returncode == 0, ack.stderr
  expected_receipt = "ok direct"
  assert ack.stdout.strip() == expected_receipt
  restored = preview.Store(tmp_path / "restored", create=True)
  restored.import_state(store.save_path.read_text())
  assert restored.submissions() == store.submissions()
  assert [
    (row["id"], row["details"], row.get("answers")) for row in restored.list_tasks()
  ] == [(row["id"], row["details"], row.get("answers")) for row in store.list_tasks()]
  store.mark_task("old-answer", "first-task")
  assert "old-answer" in {item["id"] for item in store.list_tasks()[0]["answers"]}
  store.note("plain-note", "Keep this note")
  for invalid in ("plain-note", "unknown-answer"):
    snapshot = store.save_path.read_bytes()
    result = cli(invalid)
    assert result.returncode != 0
    assert store.save_path.read_bytes() == snapshot


def test_task_list_prints_a_linked_report_answer():
  """A report answer linked to a task prints in the list, the way the page links it."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.write_task(
      "first",
      "First upcoming",
      ["Step one"],
      task_type="misc",
      report_id="select",
    )
    store.submission("answer-1", "select", "REPORT select: one")
    listed = preview.format_task_list(store.list_tasks()).splitlines()
    assert any(line.startswith("    answer answer-1, at ") for line in listed), listed
    assert "    REPORT select: one" in listed, listed
    # The row labels the report link and the type, so neither reads as the title.
    assert any(" | waits on select | type misc" in line for line in listed), listed
    # A task with no linked answer keeps the older list shape.
    store.write_task("second", "Second upcoming", ["Step two"], task_type="misc")
    lines = preview.format_task_list(store.list_tasks()).splitlines()
    assert lines.count("    Step two") == 1
    assert sum(line.startswith("    answer ") for line in lines) == 1


def test_a_short_id_prefix_names_one_record():
  # A short prefix stands in for the full ID, and the cited form is the first six characters.
  # An ID prefix can match two records. The error lists each record and type. The caller must use a full ID.
  with tempfile.TemporaryDirectory() as short_dir:
    short = preview.Store(short_dir, create=True)
    short.set_meta("port", guard_port())
    short.note("abcd123-0289082512830518", "first note")
    assert short.resolve_id("abcd123") == "abcd123-0289082512830518"
    assert short.resolve_id("abcd123-0289082512830518") == "abcd123-0289082512830518"
    # The head reaches the agent inside ticks, so the copied form names the same record.
    assert short.resolve_id("`abcd123`") == "abcd123-0289082512830518"
    assert preview.format_pending_item(short.read()["pending"][0]).startswith(
      "`abcd12`"
    )
    short.note("abcd123-9999000011112222", "second note, same head")
    try:
      short.resolve_id("abcd123")
      raise AssertionError("a two-record prefix must fail")
    except ValueError as conflict:
      message = str(conflict)
    assert "matches 2 records" in message
    assert "abcd123-0289082512830518" in message and "first note" in message
    assert "abcd123-9999000011112222" in message and "second note" in message
    try:
      short.resolve_id("zzz9999")
      raise AssertionError("an unknown prefix must fail")
    except ValueError as missing:
      assert "zzz9999" in str(missing)
    # ack takes the prefix too, and its receipt still prints the short form.
    script = str(Path(preview.__file__))
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": short_dir}
    out = subprocess.run(
      [sys.executable, script, "ack", "abcd123-0289082512830518", "answered"],
      capture_output=True,
      text=True,
      check=True,
      env=env,
    ).stdout
    assert "abcd12" in out
    prefixed = subprocess.run(
      [sys.executable, script, "ack", "abcd123-9999", "answered too"],
      capture_output=True,
      text=True,
      check=True,
      env=env,
    ).stdout
    assert "abcd12" in prefixed


def test_short_flags_and_the_details_rename():
  # `--details` drops the redundant `--task-` head. `--details` stays an alias for stored calls and docs.
  # Every flag has a short form to reduce routine call cost.
  script = str(Path(preview.__file__))
  with tempfile.TemporaryDirectory() as flag_dir:
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": flag_dir}
    preview.Store(flag_dir, create=True)
    preview.Store(flag_dir, create=True).set_meta("port", guard_port())

    def cli(*args):
      return subprocess.run(
        [sys.executable, script, *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
      ).stdout

    for flag in ("--details", "--details", "-d"):
      out = cli(
        "task",
        "set",
        "flag-task",
        "Flags",
        "--scope",
        "arena suite",
        flag,
        "one\ntwo",
        "--type",
        "misc",
      )
      assert "one" in out and "two" in out, flag
    manual_block = subprocess.run(
      [sys.executable, script, "task", "set", "flag-task", "--blocked"],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert manual_block.returncode == 2 and "--blocked" in manual_block.stderr
    assert "blocked" not in cli(
      "task", "set", "flag-task", "Flags", "-u", "--type", "misc"
    )
    out = cli(
      "task",
      "set",
      "flag-task",
      "Flags",
      "-s",
      "finished",
      "-o",
      "1",
      "--type",
      "misc",
    )
    assert "status finished" in out and "order 1" in out
    assert cli("task", "list", "-f").splitlines()[0] == "Tasks 1"
    assert cli("task", "list").splitlines()[0] == "Tasks 0 upcoming"
    store = preview.Store(flag_dir)
    store.set_meta("port", guard_port())
    store.note("1111111-2222-3333-4444-555555555555", "a note")
    acked = cli("ack", "1111111-2222-3333-4444-555555555555", "answer")
    assert "1111111" in acked
    report = Path(flag_dir) / "report.md"
    report.write_text("# Report\n\nBody text.\n", encoding="utf-8")
    with preview.ThreadingHTTPServer(
      ("127.0.0.1", 0), preview.handler(store)
    ) as server:
      store.set_meta("port", str(server.server_port))
      thread = threading.Thread(target=server.serve_forever, daemon=True)
      thread.start()
      try:
        assert "short-report" in cli(
          "report", "publish", str(report), "-i", "short-report", "-t", "Short report"
        )
      finally:
        server.shutdown()
        thread.join()


def test_task_list():
  with tempfile.TemporaryDirectory() as tasks_dir:
    tasks_store = preview.Store(tasks_dir, create=True)
    assert tasks_store.state()["tasks"] is None
    record = tasks_store.write_task(
      "docs-archive",
      "Move to new docs/archive/ dir",
      ["move BUDGET-EXCEPTIONS.md", "write arena-quirks.md"],
      task_type="misc",
    )
    assert record["status"] == "upcoming" and record["order"] == 1
    listed = tasks_store.state()["tasks"]
    assert listed["upcoming"][0]["id"] == "docs-archive"
    assert listed["upcoming"][0]["details"] == [
      "move BUDGET-EXCEPTIONS.md",
      "write arena-quirks.md",
    ]
    assert listed["finished"] == []
    assert listed["updated_at"] == record["updated_at"][:19]
    # Moving a task between the divs keeps its title and details, so it stays one command.
    moved = tasks_store.write_task("docs-archive", status="finished")
    assert moved["title"] == "Move to new docs/archive/ dir"
    assert len(moved["details"]) == 2 and moved["order"] == 1
    assert tasks_store.state()["tasks"]["finished"][0]["id"] == "docs-archive"
    assert tasks_store.state()["tasks"]["upcoming"] == []
    tasks_store.write_task("task-a", "A", ["Step one"], task_type="misc")
    tasks_store.write_task("task-b", "B", ["Step one"], task_type="misc")
    tasks_store.write_task("task-c", "C", ["Step one"], order=1, task_type="misc")
    upcoming = tasks_store.state()["tasks"]["upcoming"]
    assert [item["id"] for item in upcoming] == ["task-c", "task-a", "task-b"]
    assert [item["order"] for item in upcoming] == [1, 2, 3]
    assert len(tasks_store.list_tasks()) == 4
    removed = tasks_store.remove_task("task-a")
    assert removed["title"] == "A"
    upcoming = tasks_store.state()["tasks"]["upcoming"]
    assert [item["id"] for item in upcoming] == ["task-c", "task-b"]
    assert [item["order"] for item in upcoming] == [1, 2]
    rejections = (
      (lambda: tasks_store.write_task("Bad ID"), "A task ID with a space was accepted"),
      (lambda: tasks_store.write_task("no-title"), "A new task without a title passed"),
      (lambda: tasks_store.write_task("huge", "x" * 201), "An oversized title passed"),
      (
        lambda: tasks_store.write_task("many", "M", ["d"] * 41, task_type="misc"),
        "41 details passed",
      ),
      (
        lambda: tasks_store.write_task("deep", "D", ["y" * 2001], task_type="misc"),
        "A huge detail passed",
      ),
      (
        lambda: tasks_store.write_task("docs-archive", status="open"),
        "A third status passed",
      ),
      (lambda: tasks_store.remove_task("never-stored"), "A missing removal passed"),
    )
    for call, message in rejections:
      try:
        call()
        raise AssertionError(message)
      except ValueError:
        pass
    # The printed task cuts a long detail to save the agent tokens. The stored row keeps
    # it whole.
    long_detail = "y" * 400
    printed = preview.format_task(
      tasks_store.write_task("long", "Long", [long_detail], task_type="misc")
    )
    assert f"- {'y' * 200}\u2026" in printed
    assert tasks_store.state()["tasks"]["upcoming"][-1]["details"] == [long_detail]
    try:
      tasks_store.write_task("long", details=[""])
      raise AssertionError("Clearing the last detail was accepted")
    except ValueError:
      pass
    assert "<img onerror=alert(1)>" in preview.format_task(
      tasks_store.write_task(
        "hostile", "<img onerror=alert(1)>", ["Step one"], task_type="misc"
      )
    )


def test_task_completion_time_tracks_transitions_and_finished_order():
  with tempfile.TemporaryDirectory() as task_dir:
    store = preview.Store(task_dir, create=True)
    for task_id in ("alpha", "bravo", "charlie"):
      store.write_task(task_id, task_id.title(), ["Step one"], task_type="misc")
    with patch.object(preview, "now", return_value="2026-10-13T01:00:00+00:00"):
      first_finish = store.write_task("alpha", status="finished")
    assert first_finish["completed_at"] == "2026-10-13T01:00:00+00:00"
    with patch.object(preview, "now", return_value="2026-10-13T02:00:00+00:00"):
      store.write_task("bravo", status="finished")
      store.write_task("charlie", status="finished")
    with patch.object(preview, "now", return_value="2026-10-13T03:00:00+00:00"):
      edited = store.write_task("alpha", details=["Edited after finish"])
    assert edited["completed_at"] == "2026-10-13T01:00:00+00:00"
    store.amend_task("alpha", "alpha-renamed")
    assert (
      store.task_record("alpha-renamed")["completed_at"] == "2026-10-13T01:00:00+00:00"
    )
    assert [item["id"] for item in store.tasks()["finished"]] == [
      "charlie",
      "bravo",
      "alpha-renamed",
    ]
    with patch.object(preview, "now", return_value="2026-10-13T04:00:00+00:00"):
      reopened = store.write_task("alpha-renamed", status="upcoming")
    assert reopened["completed_at"] is None
    with patch.object(preview, "now", return_value="2026-10-13T05:00:00+00:00"):
      finished_again = store.write_task("alpha-renamed", status="finished")
    assert finished_again["completed_at"] == "2026-10-13T05:00:00+00:00"
    assert [item["id"] for item in store.tasks()["finished"]] == [
      "alpha-renamed",
      "charlie",
      "bravo",
    ]


def test_task_completion_time_migrates_and_survives_state_import():
  with tempfile.TemporaryDirectory() as legacy_dir:
    legacy = Path(legacy_dir)
    with sqlite3.connect(legacy / "state.sqlite3") as db:
      db.execute(
        """CREATE TABLE tasks (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, details TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL, position INTEGER NOT NULL, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, blocked INTEGER NOT NULL DEFAULT 0, report_id TEXT
        )"""
      )
      db.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
          "old-finished",
          "Old finished",
          '["Step one"]',
          "finished",
          1,
          "2026-10-01T00:00:00+00:00",
          "2026-10-02T00:00:00+00:00",
          0,
          None,
        ),
      )
      db.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
          "old-upcoming",
          "Old upcoming",
          '["Step one"]',
          "upcoming",
          1,
          "2026-10-01T00:00:00+00:00",
          "2026-10-03T00:00:00+00:00",
          0,
          None,
        ),
      )
    migrated = preview.Store(legacy)
    rows = {item["id"]: item for item in migrated.list_tasks()}
    assert rows["old-finished"]["completed_at"] == "2026-10-02T00:00:00+00:00"
    assert rows["old-upcoming"]["completed_at"] is None
    migrated.autosave()
    saved = [
      json.loads(line)
      for line in migrated.save_path.read_text(encoding="utf-8").splitlines()
    ]
    saved_finished = next(item for item in saved if item["id"] == "old-finished")
    assert saved_finished["completed_at"] == "2026-10-02T00:00:00+00:00"
    restored = preview.Store(legacy / "restored", create=True)
    restored.import_state(migrated.save_path.read_text(encoding="utf-8"))
    assert (
      restored.task_record("old-finished")["completed_at"]
      == "2026-10-02T00:00:00+00:00"
    )
    imported = preview.Store(legacy / "imported", create=True)
    with patch.object(preview, "now", return_value="2026-10-13T06:00:00+00:00"):
      imported.import_tasks(
        [
          {
            "id": "old-import",
            "title": "Old import",
            "details": ["Step one"],
            "status": "finished",
          }
        ]
      )
    assert (
      imported.task_record("old-import")["completed_at"] == "2026-10-13T06:00:00+00:00"
    )


def test_shared_ids_refused():
  # One backticked ID links to one panel, so a task and a report never share an ID.
  with tempfile.TemporaryDirectory() as shared_dir:
    store = preview.Store(shared_dir, create=True)
    source = Path(shared_dir) / "plan.md"
    source.write_text("# Plan\n", encoding="utf-8")
    store.publish("plan", "Plan", source)
    store.write_task("build", "Build it", ["Step one"], task_type="misc")
    for attempt, message in (
      (
        lambda: store.write_task("plan", "Plan task", ["Step one"], task_type="misc"),
        "already names a report",
      ),
      (lambda: store.amend_task("build", "plan"), "already names a report"),
      (
        lambda: store.publish("build", "Build report", source),
        "already names a task; a report needs another ID, for example build-report",
      ),
    ):
      try:
        attempt()
        raise AssertionError("shared ID accepted")
      except ValueError as error:
        assert message in str(error), str(error)
    # Existing rows keep updating under their own IDs.
    store.write_task("build", "Build it again", ["Step one"])
    store.publish("plan", "Plan revised", source)
    assert [task["id"] for task in store.list_tasks()] == ["build"]


def test_publish_returns_field_count():
  # The CLI prints the count so a report with no parsed answer form is visible at publish time.
  with tempfile.TemporaryDirectory() as shared_dir:
    store = preview.Store(shared_dir, create=True)
    source = Path(shared_dir) / "ask.md"
    source.write_text("# Ask\n\n{#q approve|reject} rows\n", encoding="utf-8")
    assert store.publish("ask", "Ask", source) == 0
    source.write_text(
      "# Ask\n\nrows: {#q}\n\n- ( ) approve\n- ( ) reject\n", encoding="utf-8"
    )
    assert store.publish("ask", "Ask", source) == 1


def test_task_finish_blocked_refused():
  with tempfile.TemporaryDirectory() as blocked_dir:
    blocked_store = preview.Store(blocked_dir, create=True)
    blocked_store.write_task(
      "await", "Await the owner answer", ["Step one"], blocked=True, task_type="misc"
    )
    # A blocked task stays upcoming: finishing it needs the mark cleared first.
    try:
      blocked_store.write_task("await", status="finished")
      raise AssertionError("A blocked task reached the finished div")
    except ValueError as error:
      assert "--unblocked" in str(error)
    assert blocked_store.write_task("await")["status"] == "upcoming"
    # Clearing the mark in the same command lets the finish through.
    cleared = blocked_store.write_task("await", status="finished", blocked=False)
    assert cleared["status"] == "finished" and cleared["blocked"] is False


def test_task_order_write_reorders_the_queue():
  """The page's drag posts the drawn order, and the stored queue follows the reply."""
  global app
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "arena-preview"
    store = preview.Store(root, create=True)
    store.set_meta("port", guard_port())
    for task_id in ("first", "second", "third"):
      store.write_task(task_id, task_id.title(), ["A step"], task_type="code")
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    worker = threading.Thread(target=app.serve_forever, daemon=True)
    worker.start()
    headers = {"Content-Type": "application/json"}
    status, _, body = request(
      "POST",
      "/api/tasks/order",
      json.dumps({"ids": ["third", "first", "second"]}),
      headers,
    )
    assert status == 200, body
    payload = json.loads(body)
    assert [task["id"] for task in payload["upcoming"]] == ["third", "first", "second"]
    assert [task["order"] for task in payload["upcoming"]] == [1, 2, 3]
    # The reply, the page's poll payload and a stored read name the same queue.
    assert [task["id"] for task in preview.Store(root).tasks()["upcoming"]] == [
      "third",
      "first",
      "second",
    ]
    assert [task["id"] for task in preview.Store(root).list_tasks()] == [
      "third",
      "first",
      "second",
    ]
    # A filter or a search draws part of the queue, so the tasks left out keep their slots.
    filtered, _, filtered_body = request(
      "POST", "/api/tasks/order", json.dumps({"ids": ["first", "third"]}), headers
    )
    assert filtered == 200, filtered_body
    assert [task["id"] for task in json.loads(filtered_body)["upcoming"]] == [
      "first",
      "third",
      "second",
    ]
    # The route refuses a name no upcoming task holds, or a name sent twice, and writes nothing.
    for bad_ids in (["second", "gone"], ["second", "second"]):
      refused, _, _ = request(
        "POST", "/api/tasks/order", json.dumps({"ids": bad_ids}), headers
      )
      assert refused == 400, bad_ids
    assert [task["id"] for task in preview.Store(root).list_tasks()] == [
      "first",
      "third",
      "second",
    ]


def test_task_report_link_unblocks_on_answer():
  # A blocked task names the report it waits on. The owner's answer clears the mark.
  with tempfile.TemporaryDirectory() as link_dir:
    link_store = preview.Store(link_dir, create=True)
    source = Path(link_dir) / "select.md"
    source.write_text(
      "Select one: {#select}\n\n- ( ) yes\n- ( ) no\n", encoding="utf-8"
    )
    link_store.publish("select", "Select one", source)
    linked = link_store.write_task(
      "ship",
      "Ship the change",
      ["wait for the select"],
      blocked=True,
      report_id="select",
      task_type="misc",
    )
    assert linked["blocked"] is True and linked["report_id"] == "select"
    assert link_store.list_tasks()[0]["report_id"] == "select"
    # The mark holds through an unrelated update while the report stays unanswered.
    held = link_store.write_task("ship", details=["wait for the select still"])
    assert held["blocked"] is True and held["report_id"] == "select"
    link_store.write_task(
      "other", "Other wait", ["Step one"], blocked=True, task_type="misc"
    )
    revision = link_store.report("select")["updated_at"]
    link_store.submit_report("select", "answer-1", {"select": "yes"}, revision)
    tasks = {item["id"]: item for item in link_store.list_tasks()}
    assert tasks["ship"]["blocked"] is False
    assert tasks["other"]["blocked"] is True
    # A link to a report that already has its answer never keeps the mark.
    late = link_store.write_task(
      "late",
      "Late link",
      ["Step one"],
      blocked=True,
      report_id="select",
      task_type="misc",
    )
    assert late["blocked"] is False
    gate = link_store.write_task("ship", blocked=True)
    assert gate["blocked"] is True and gate["report_id"] == "select"
    updated = link_store.write_task("ship", details=["Wait for the running gate"])
    assert updated["blocked"] is True and updated["report_id"] == "select"
    assert link_store.write_task("ship", blocked=False)["blocked"] is False
    assert link_store.write_task("late", blocked=True)["blocked"] is True
    assert (
      link_store.write_task("late", blocked=True, report_id="select")["blocked"]
      is False
    )


def test_report_linked_task_sorts_ahead_in_its_status():
  # A report link has priority only while its task waits for an answer.
  with tempfile.TemporaryDirectory() as sort_dir:
    sort_store = preview.Store(sort_dir, create=True)
    source = Path(sort_dir) / "select.md"
    source.write_text(
      "Select one: {#select}\n\n- ( ) yes\n- ( ) no\n", encoding="utf-8"
    )
    sort_store.publish("select", "Select one", source)
    sort_store.write_task("plain", "Plain", ["Step one"], order=1, task_type="misc")
    sort_store.write_task(
      "linked",
      "Linked",
      ["Step one"],
      order=2,
      report_id="select",
      blocked=True,
      task_type="misc",
    )
    upcoming = [
      item["id"] for item in sort_store.list_tasks() if item["status"] == "upcoming"
    ]
    assert upcoming == ["plain", "linked"]
    assert sort_store.tasks()["upcoming"][0]["id"] == "plain"
    revision = sort_store.report("select")["updated_at"]
    sort_store.submit_report("select", "answer-1", {"select": "yes"}, revision)
    assert [item["id"] for item in sort_store.tasks()["upcoming"]] == [
      "plain",
      "linked",
    ]
    assert sort_store.tasks()["upcoming"][1]["report_id"] == "select"


def test_task_report_flag_waits_for_an_answer_by_default():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    source = Path(directory) / "select.md"
    source.write_text(
      "Select one: {#select}\n\n- ( ) yes\n- ( ) no\n", encoding="utf-8"
    )
    store.publish("select", "Select one", source)
    store.write_task("waiting", "Waiting", ["Keep this detail"], task_type="misc")

    def link(*args):
      return subprocess.run(
        [
          sys.executable,
          str(Path(preview.__file__)),
          "task",
          "set",
          "waiting",
          "--report",
          "select",
          *args,
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": directory},
      )

    result = link()
    assert result.returncode == 0, result.stderr
    assert store.task_record("waiting")["blocked"] is True
    assert store.task_record("waiting")["details"] == ["Keep this detail"]
    assert link("--unblocked").returncode == 0
    assert store.task_record("waiting")["blocked"] is False
    assert link("--msg-id", "aaaaaa").returncode != 0
    assert store.task_record("waiting")["blocked"] is False
    assert link().returncode == 0
    assert store.task_record("waiting")["blocked"] is True
    revision = store.report("select")["updated_at"]
    store.submit_report("select", "answer-1", {"select": "yes"}, revision)
    assert store.task_record("waiting")["blocked"] is False
    assert link().returncode == 0
    assert store.task_record("waiting")["blocked"] is False


def test_task_report_link_refuses_missing_report():
  with tempfile.TemporaryDirectory() as cli_dir:
    cli_store = preview.Store(cli_dir, create=True)
    cli_store.set_meta("port", guard_port())
    cli_store.write_task("keep", "Keep", ["Step one"], task_type="misc")
    missing = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "task",
        "set",
        "wait",
        "Wait",
        "--report",
        "never-published",
      ],
      capture_output=True,
      text=True,
      check=False,
      cwd=cli_dir,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": cli_dir},
    )
    assert missing.returncode == 1
    assert "never-published" in missing.stderr
    assert [item["id"] for item in cli_store.list_tasks()] == ["keep"]


def test_task_report_link_survives_save_and_import():
  # A save file carries the link, so a restore keeps the task waiting on the same report.
  with tempfile.TemporaryDirectory() as save_dir:
    save_store = preview.Store(save_dir, create=True)
    source = Path(save_dir) / "select.md"
    source.write_text(
      "Select one: {#select}\n\n- ( ) yes\n- ( ) no\n", encoding="utf-8"
    )
    save_store.publish("select", "Select one", source)
    save_store.write_task(
      "ship",
      "Ship it",
      ["Step one"],
      blocked=True,
      report_id="select",
      task_type="misc",
    )
    save_store.save_state({"notes": [], "tasks": save_store.tasks()})
    lines = [json.loads(line) for line in save_store.save_path.read_text().splitlines()]
    saved = next(line for line in lines if line.get("id") == "ship")
    assert saved["report_id"] == "select"
    restored = preview.Store(Path(save_dir) / "restored", create=True)
    assert restored.import_state(save_store.save_path.read_text())["tasks"] == 1
    restored.report("select")
    assert restored.list_tasks()[0]["report_id"] == "select"


def test_task_amend():
  with tempfile.TemporaryDirectory() as amend_dir:
    amend_store = preview.Store(amend_dir, create=True)
    amend_store.write_task(
      "docz-archive",
      "Move to docs/archive/",
      ["one", "two"],
      "upcoming",
      1,
      task_type="misc",
    )
    amend_store.write_task(
      "minify", "Minify the live build", ["Step one"], task_type="misc"
    )
    amend_store.amend_task("docz-archive", "docs-archive")
    fixed = amend_store.write_task("docs-archive")
    assert fixed["title"] == "Move to docs/archive/"
    assert fixed["details"] == ["one", "two"] and fixed["order"] == 1
    amend_rejections = (
      (
        lambda: amend_store.amend_task("docs-archive", "minify"),
        "An amend onto a stored ID passed",
      ),
      (
        lambda: amend_store.amend_task("never", "whatever"),
        "An amend of a missing ID passed",
      ),
      (
        lambda: amend_store.amend_task("docs-archive", "Bad ID"),
        "An amend to a bad ID passed",
      ),
    )
    for call, message in amend_rejections:
      try:
        call()
        raise AssertionError(message)
      except ValueError:
        pass
    # A copied list restores into an empty inbox, from an array or from one record per line.
    backup = json.dumps(amend_store.list_tasks())
    (Path(amend_dir) / "restored").mkdir()
    fresh = preview.Store(Path(amend_dir) / "restored", create=True)
    written = fresh.import_tasks(preview.parse_state_import(backup))
    assert [item["id"] for item in written] == ["docs-archive", "minify"]
    assert fresh.state()["tasks"]["upcoming"][0]["details"] == ["one", "two"]
    lines = "\n".join(json.dumps(item) for item in amend_store.list_tasks())
    (Path(amend_dir) / "lines").mkdir()
    other = preview.Store(Path(amend_dir) / "lines", create=True)
    assert len(other.import_tasks(preview.parse_state_import(lines))) == 2
    other.write_task("extra", "Extra", ["Step one"], task_type="misc")
    other.import_tasks(preview.parse_state_import(backup), replace=True)
    assert [item["id"] for item in other.list_tasks()] == ["docs-archive", "minify"]
    # An invalid --replace changes nothing: removal and writes share a transaction.
    # Remove-first logic once lost the list to a later invalid record.
    before = other.list_tasks()
    for bad, flaw in (
      (
        [
          {"id": "good", "title": "Good", "details": ["one"]},
          {"id": "BAD ID", "title": "Bad", "details": ["one"]},
        ],
        "invalid ID",
      ),
      (
        [
          {"id": "good", "title": "Good", "details": ["one"]},
          {"id": "no-title", "details": ["one"]},
        ],
        "missing title",
      ),
      (
        [
          {"id": "good", "title": "Good", "details": ["one"]},
          {"id": "late", "details": ["one"], "status": "sideways"},
        ],
        "bad status",
      ),
      (
        [{"id": "good", "title": "Good", "details": ["one"]}, 7],
        "record that is not an object",
      ),
    ):
      try:
        other.import_tasks(bad, replace=True)
        raise AssertionError(f"A replacement carrying an {flaw} was applied")
      except (ValueError, TypeError):
        pass
      assert other.list_tasks() == before, f"an {flaw} cost the existing task list"
    # A valid replacement still replaces, and still lands in the order asked for.
    other.import_tasks(
      [
        {"id": "second", "title": "Second", "details": ["two"], "order": 2},
        {"id": "first", "title": "First", "details": ["one"], "order": 1},
      ],
      replace=True,
    )
    assert [item["id"] for item in other.list_tasks()] == ["first", "second"]
    # One bare object is JSONL of a single record, so it parses and fails on the missing ID.
    assert preview.parse_state_import('{"id": "solo", "title": "Solo"}') == [
      {"id": "solo", "title": "Solo"}
    ]
    for call, message in (
      (lambda: preview.parse_state_import("   "), "An empty import was accepted"),
      (lambda: preview.parse_state_import("[1, 2]"), "A list of numbers was accepted"),
      (
        lambda: other.import_tasks([{"title": "no id"}]),
        "A task with no ID was imported",
      ),
      (
        lambda: other.import_tasks(preview.parse_state_import('{"title": "Solo"}')),
        "A record with no ID was imported",
      ),
    ):
      try:
        call()
        raise AssertionError(message)
      except ValueError:
        pass


def test_wide_report_fields():
  with tempfile.TemporaryDirectory() as wide_dir:
    wide_store = preview.Store(wide_dir, create=True)
    # The widest report the field rules allow: 50 text fields, each answered in full.
    wide = Path(wide_dir) / "wide.md"
    wide.write_text(
      "# Wide\n\n" + "\n".join(f"Question {index}: ___" for index in range(50)) + "\n",
      encoding="utf-8",
    )
    wide_store.publish("wide", "Wide report", wide)
    _, questions = preview.render_report(wide.read_text(encoding="utf-8"))
    assert len(questions) == 50
    answers = {question["id"]: "x" * 2000 for question in questions}
    record = wide_store.submit_report(
      "wide", "note-wide", answers, wide_store.report("wide")["updated_at"]
    )
    assert len(record["text"]) > 100_000
    assert record["text"].count("x" * 2000) == 50
    stored = [item for item in wide_store.submissions() if item["id"] == "note-wide"]
    assert stored and stored[0]["text"] == record["text"]
    oversized = "z" * 150_001
    assert preview.submission_text(oversized) == oversized
    assert wide_store.submission("s-huge", "wide", oversized)["text"] == oversized
    wide_rejections = (
      (lambda: preview.submission_text("   "), "An empty submission was accepted"),
      (lambda: preview.submission_text(None), "A non-string submission was accepted"),
    )
    for call, message in wide_rejections:
      try:
        call()
        raise AssertionError(message)
      except ValueError as error:
        assert "150,000" in str(error) or "at least one answer" in str(error)
    # A note carries no length cap of its own. Only blank text fails.
    long_note = "n" * 200_000
    assert preview.note_text(long_note) == long_note
    try:
      preview.note_text("   ")
      raise AssertionError("A blank note was accepted")
    except ValueError:
      pass


def test_shared_save_import():
  # One saved-state file feeds the unified importer for notes, tasks and report answers.
  with tempfile.TemporaryDirectory() as mixed_dir:
    mixed_root = Path(mixed_dir)
    preview.Store(mixed_root, create=True)
    preview.Store(mixed_root, create=True).set_meta("port", guard_port())
    mixed = mixed_root / "saved-state.ndjson"
    mixed.write_text(
      json.dumps(
        {
          "id": "saved-note",
          "text": "from the browser",
          "at": "2026-09-21T09:00:00",
          "acknowledged_at": "2026-09-21T09:05:00",
          "ack_type": "reply",
          "ack_text": "answered",
          "seen_at": "2026-09-21T09:01:00",
        }
      )
      + "\n"
      + json.dumps(
        {
          "id": "saved-task",
          "title": "From the browser",
          "details": ["one"],
          "status": "upcoming",
          "order": 1,
        }
      )
      + "\n"
      # An answer line rides the same file as notes and tasks.
      + json.dumps(
        {
          "id": "saved-answer",
          "report_id": "first",
          "text": "REPORT first First:\n  a: yes",
          "at": "2026-09-21T09:02:00",
          "acknowledged_at": "2026-09-21T09:06:00",
          "ack_type": "note",
          "ack_text": "read it",
          "seen_at": "2026-09-21T09:03:00",
        }
      )
      + "\n",
      encoding="utf-8",
    )
    script = str(Path(preview.__file__))
    imported = subprocess.run(
      [
        sys.executable,
        script,
        "state",
        "import",
        str(mixed),
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(mixed_root)},
    ).stdout
    assert "notes 1" in imported and "answers 1" in imported and "tasks 1" in imported
    # The import does not overwrite its source. A reimport never duplicates a row.
    assert any(
      "title" in json.loads(line)
      for line in mixed.read_text(encoding="utf-8").splitlines()
      if line.strip()
    )
    again = subprocess.run(
      [
        sys.executable,
        script,
        "state",
        "import",
        str(mixed),
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(mixed_root)},
    ).stdout
    assert "notes 1" in again and "tasks 1" in again
    assert len(preview.Store(mixed_root).state()["notes"]) == 1
    assert len(preview.Store(mixed_root).submissions()) == 1
    # Writer and reader move together: the store tasks round-trip via import-state.
    script_again = str(Path(preview.__file__))
    listed = subprocess.run(
      [sys.executable, script_again, "task", "list"],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(mixed_root)},
    ).stdout.strip()
    assert "saved-task" in listed
    assert preview.Store(mixed_root).list_tasks()[0]["id"] == "saved-task"
    # Every import overrides. A reimport of the same file restores all three rows.
    reimport = subprocess.run(
      [
        sys.executable,
        script_again,
        "state",
        "import",
        "-r",
        str(mixed),
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(mixed_root)},
    ).stdout.strip()
    assert "notes 1" in reimport and "answers 1" in reimport and "tasks 1" in reimport
    read_out = subprocess.run(
      [sys.executable, script_again, "read"],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(mixed_root)},
    ).stdout.strip()
    # The imported note carries its receipt, so `read` has nothing pending. The receipt is what
    # makes it acknowledged.
    assert "0 pending" in read_out or "pending" not in read_out or "Inbox" in read_out
    restored = preview.Store(mixed_root)
    restored.set_meta("port", guard_port())
    assert [row["id"] for row in restored.state()["notes"]] == ["saved-note"]
    assert [row["id"] for row in restored.submissions()] == ["saved-answer"]
    assert [task["id"] for task in restored.tasks()["upcoming"]] == ["saved-task"]


def test_serve_rejects_nondefault_port():
  with tempfile.TemporaryDirectory() as state_dir:
    try:
      result = subprocess.run(
        [sys.executable, str(Path(preview.__file__)), "serve", "--port", "8123"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": state_dir},
        timeout=5,
      )
    except subprocess.TimeoutExpired as error:
      pytest.fail(f"serve accepted port 8123: {error.stdout!r}")
    assert result.returncode == 2
    assert result.stdout == ""
    assert f"serve: error: --port must be {preview.DEFAULT_PORT}" in result.stderr
    assert not (Path(state_dir) / "state.sqlite3").exists()


def test_serve_help():
  help_text = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "serve", "--help"],
    capture_output=True,
    text=True,
    check=True,
  ).stdout
  assert preview.DEFAULT_PORT == 8000
  assert f"default: {preview.DEFAULT_PORT}" in help_text and "--port PORT" in help_text
  assert "only supported port" in help_text


def test_restore_import():

  with tempfile.TemporaryDirectory() as restore_dir:
    restore = Path(restore_dir)
    preview.Store(restore, create=True).set_meta("port", guard_port())
    script = str(Path(preview.__file__))
    # import-state creates the missing database itself, so no `init` runs first.
    log = restore / "log.jsonl"
    log.write_text(
      json.dumps(
        {
          "id": "carried",
          "text": "answered before the wipe",
          "at": "2026-09-20T22:00:47",
          "acknowledged_at": "2026-09-20T22:05:11.982172+00:00",
          "ack_type": "reply",
          "ack_text": "Fixed in `preview.py`.",
          "seen_at": "2026-09-20T22:00:52",
          "task_id": "carried-task",
        }
      )
      + "\n"
      + json.dumps(
        {
          "id": "plain",
          "text": "never answered",
          "at": "2026-09-20T22:01:00",
          "acknowledged_at": None,
          "ack_type": None,
          "ack_text": None,
          "seen_at": None,
        }
      )
      + "\n"
      + json.dumps(
        {
          "id": "read",
          "text": "read but not answered",
          "at": "2026-09-20T22:01:10",
          "acknowledged_at": None,
          "ack_type": None,
          "ack_text": None,
          "seen_at": "2026-09-20T22:01:30",
        }
      )
      + "\n",
      encoding="utf-8",
    )
    imported = subprocess.run(
      [sys.executable, script, "state", "import", str(log)],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(restore)},
    ).stdout
    assert "notes 3" in imported
    rows = {row["id"]: row for row in preview.Store(restore).state()["notes"]}
    assert rows["carried"]["acknowledged_at"] == "2026-09-20T22:05:11.982172+00:00"[:19]
    assert rows["carried"]["ack_type"] == "reply"
    assert rows["carried"]["ack_text"] == "Fixed in `preview.py`."
    assert rows["carried"]["at"] == "2026-09-20T22:00:47"
    # A message that became a task comes back marked, so a restore keeps the link.
    assert rows["carried"]["task_id"] == "carried-task"
    assert rows["plain"]["task_id"] is None

    # A task names the message it answers, and that message then says so. A mistyped message ID is
    # refused with no task left behind, because the task and the marker land in one transaction.
    linked = subprocess.run(
      [
        sys.executable,
        script,
        "task",
        "set",
        "from-note",
        "Answer the note",
        "Answer it",
        "--scope",
        "arena suite",
        "--msg-id",
        "plain",
        "--type",
        "misc",
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(restore)},
    ).stdout
    assert "plain" in linked or "task" in linked
    assert {
      row["id"]: row["task_id"] for row in preview.Store(restore).state()["notes"]
    }["plain"] == "from-note"
    refused = subprocess.run(
      [
        sys.executable,
        script,
        "task",
        "set",
        "orphan",
        "No message",
        "Answer it",
        "--scope",
        "arena suite",
        "--type",
        "misc",
        "--msg-id",
        "0f0f0f0f-0000-4000-8000-000000000000",
      ],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(restore)},
    )
    assert refused.returncode != 0 and "Unknown note" in refused.stderr
    assert "orphan" not in {item["id"] for item in preview.Store(restore).list_tasks()}
    # A line carrying no receipt stays unacknowledged, and nothing infers an answer for it.
    assert rows["plain"]["acknowledged_at"] is None
    assert rows["plain"]["ack_type"] is None
    assert rows["plain"]["ack_text"] is None
    assert rows["plain"]["seen_at"] is None
    assert rows["carried"]["seen_at"] == "2026-09-20T22:00:52"
    assert rows["read"]["seen_at"] == "2026-09-20T22:01:30"
    assert rows["read"]["acknowledged_at"] is None
    assert rows["read"]["ack_type"] is None
    assert rows["read"]["ack_text"] is None
    partial = restore / "partial.jsonl"
    partial.write_text(
      json.dumps(
        {
          "id": "half",
          "text": "half a receipt",
          "acknowledged_at": "2026-09-20T22:05:11+00:00",
          "ack_type": None,
          "ack_text": None,
        }
      )
      + "\n",
      encoding="utf-8",
    )
    refused = subprocess.run(
      [
        sys.executable,
        script,
        "state",
        "import",
        str(partial),
      ],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(restore)},
    )
    assert refused.returncode == 1
    assert all(field in refused.stderr for field in ("stamp", "type", "text"))
    assert "half" not in {row["id"] for row in preview.Store(restore).state()["notes"]}
    assert {row["id"] for row in preview.Store(restore).state()["notes"]} == {
      "carried",
      "plain",
      "read",
    }
    # Importing the same log again changes nothing: a stored ID keeps the record it has.
    again = subprocess.run(
      [sys.executable, script, "state", "import", str(log)],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(restore)},
    ).stdout
    assert "notes 3" in again
    # Three restored notes, and a re-import adds none of them twice.
    assert len(preview.Store(restore).state()["notes"]) == 3


def test_missing_inbox_error_instructs():
  # The error names the commands that rebuild the inbox after a sandbox reset.
  with tempfile.TemporaryDirectory() as missing_dir:
    try:
      preview.Store(Path(missing_dir) / "none", create=False)
    except FileNotFoundError as error:
      text = str(error)
    else:
      raise AssertionError("a missing inbox must raise")
    for fragment in (
      "install.sh",
      "start_process",
      "arena-preview serve",
      "arena-preview read",
      "reset",
    ):
      assert fragment in text


def test_unacknowledged_call_trap():
  """Calls one through three count. Calls four and five name the calls left. Call six blocks."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.note("trap-note", "Pending work")
    assert preview.GATE_THRESHOLD == 6
    # The tally counts up to the half-way mark, then names the calls left before the block.
    for calls, head in (
      (1, "calls 1"),
      (2, "calls 2"),
      (3, "calls 3"),
      (4, "bash blocked in 2"),
      (5, "bash blocked in 1"),
    ):
      store.set_meta(preview.POLLS_SINCE_MESSAGE, str(calls))
      assert store.reminder().startswith(f"{head} unacked 1 note | ")
    store.set_meta(preview.POLLS_SINCE_MESSAGE, str(preview.GATE_THRESHOLD))
    assert store.reminder().startswith("blocked unacked 1 note | ")
    result = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "gate"],
      capture_output=True,
      text=True,
      check=False,
      cwd=directory,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": directory},
    )
    assert result.returncode == 1
    assert result.stdout.startswith("BASH BLOCKED AFTER 6 CALLS.\nREAD INBOX NOW. "), (
      result.stdout
    )
    assert preview.quiet_inbox_line("arena-preview read") is True
    assert preview.quiet_inbox_line("arena-preview ack abcdef Done") is True


def test_bash_gate():
  # The gate blocks only past the threshold while the inbox stays pending.
  with tempfile.TemporaryDirectory() as gate_dir:
    gate_store = preview.Store(gate_dir, create=True)
    gate_store.note("gate-note", "Pending work")
    gate_store.set_meta(preview.POLLS_SINCE_MESSAGE, str(preview.GATE_THRESHOLD - 1))
    assert gate_store.gate()
    gate_store.set_meta(preview.POLLS_SINCE_MESSAGE, str(preview.GATE_THRESHOLD))
    assert not gate_store.gate()
    gate_script = str(Path(preview.__file__))
    blocked = subprocess.run(
      [sys.executable, gate_script, "gate"],
      capture_output=True,
      text=True,
      check=False,
      # Run outside the checkout: the push guard asks the working directory, and this
      # test covers the inbox gate alone. The push guard has its own test.
      cwd=gate_dir,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": gate_dir},
    )
    assert blocked.returncode == 1
    # The blocked line names the command that clears the block.
    assert (
      blocked.stdout.strip() == "BASH BLOCKED AFTER 6 CALLS.\n"
      "READ INBOX NOW. Only a bare `arena-preview read` passes. Then ack every"
      " note: `arena-preview ack <id> <markdown>`.\n"
      f"Pending: gate-note\n{preview.REMINDERS[0]}"
    )
    gate_store.acknowledge(["gate-note"], "Cleared")
    assert gate_store.gate()
    cleared = subprocess.run(
      [sys.executable, gate_script, "gate"],
      capture_output=True,
      text=True,
      check=False,
      # Run outside the checkout: the push guard asks the working directory, and this
      # test covers the inbox gate alone. The push guard has its own test.
      cwd=gate_dir,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": gate_dir},
    )
    assert cleared.returncode == 0
    missing = subprocess.run(
      [
        sys.executable,
        gate_script,
        "gate",
      ],
      capture_output=True,
      text=True,
      check=False,
      cwd=gate_dir,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(Path(gate_dir) / "none")},
    )
    assert missing.returncode == 0, "no inbox means nothing to read"

    # A checkpoint holds while any item stays unacked, whatever the call count, and the
    # CLI carries that mode for the profile gate.
    gate_store.note("push-note", "Late steering")
    assert gate_store.gate(pending_only=True) is False
    pushed = subprocess.run(
      [sys.executable, gate_script, "gate", "--push"],
      capture_output=True,
      text=True,
      check=False,
      # Run outside the checkout: the push guard asks the working directory, and this
      # test covers the inbox gate alone. The push guard has its own test.
      cwd=gate_dir,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": gate_dir},
    )
    assert pushed.returncode == 1
    assert pushed.stdout.startswith("PUSH BLOCKED: "), pushed.stdout
    assert (
      "READ INBOX NOW. Only a bare `arena-preview read` passes. Then ack every"
      " note: `arena-preview ack <id> <markdown>`." in pushed.stdout
    )
    gate_store.acknowledge(["push-note"], "Cleared")
    assert gate_store.gate(pending_only=True) is True
    cleared_push = subprocess.run(
      [sys.executable, gate_script, "gate", "--push"],
      capture_output=True,
      text=True,
      check=False,
      # Run outside the checkout: the push guard asks the working directory, and this
      # test covers the inbox gate alone. The push guard has its own test.
      cwd=gate_dir,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": gate_dir},
    )
    assert cleared_push.returncode == 0


def test_run_records_the_exit_and_announces_it_once(capsys):
  """A run keeps its exit and output tail, and the next gate call announces it once."""
  with tempfile.TemporaryDirectory() as directory:
    code = preview.run_command(
      directory,
      "check",
      ["--", sys.executable, "-c", "print('ok'); raise SystemExit(3)"],
    )
    assert code == 3
    out = capsys.readouterr().out
    assert "ok" in out and "run check done: exit 3" in out  # nonemo: NMT100
    preview.run_notices(directory)
    notice = capsys.readouterr().out
    assert "run check done: exit 3" in notice and notice.rstrip().endswith("ok")
    preview.run_notices(directory)
    assert capsys.readouterr().out == ""
    assert preview.run_command(directory, "bad name!", ["true"]) == 2
    assert preview.run_command(directory, "empty", ["--"]) == 2


def test_an_unstarted_check_watch_names_the_missing_checks(tmp_path, monkeypatch):
  """An empty rollup ends the run with the explicit unstarted verdict."""
  verdict = (
    "PR CHECKS NOT STARTED: no visible checks appeared on abc1234 within 30 seconds."
  )
  monkeypatch.setattr(preview, "pr_checks_command", lambda argv: True)
  monkeypatch.setattr(
    preview,
    "pr_checks_watch",
    lambda root, progress=None: ("not_started", [verdict]),
    raising=False,
  )
  assert preview.run_command(tmp_path, "pr-checks", ["--", "gh", "pr", "checks"]) == 1
  record = json.loads(
    (tmp_path / "runs" / "pr-checks.json").read_text(encoding="utf-8")
  )
  assert record["verdict"] == verdict
  assert record["tail"] == [verdict]


def test_a_failed_check_watch_names_the_failing_steps(tmp_path, monkeypatch, capsys):
  """A failed watch appends the failing step of each failed check."""
  monkeypatch.setattr(preview, "pr_checks_command", lambda argv: True)
  monkeypatch.setattr(
    preview,
    "pr_checks_watch",
    lambda root, progress=None: ("failure", ["PR CHECKS FAILED: Quality."]),
    raising=False,
  )
  monkeypatch.setattr(
    preview, "pr_failed_steps", lambda root=".": ["Quality / Update and Validate"]
  )
  argv = ["--", "gh", "pr", "checks", "116", "--watch"]
  assert preview.run_command(tmp_path, "pr-checks", argv) == 1
  out = capsys.readouterr().out
  assert "Failed: Quality / Update and Validate" in out
  record = json.loads(
    (tmp_path / "runs" / "pr-checks.json").read_text(encoding="utf-8")
  )
  assert record["verdict"] == "Failed: Quality / Update and Validate"


def test_failed_steps_map_checks_to_job_steps(monkeypatch):
  """The step helper reads failed checks, then each job's failing steps."""
  monkeypatch.setattr(preview, "repo_slug", lambda root=".": "o/r")
  monkeypatch.setattr(preview, "workspace_branch", lambda root=".": "b")
  monkeypatch.setattr(preview, "pr_head_sha", lambda root, branch, slug: "abc1234")
  seen = []

  def fake(root, path, projection):
    seen.append(path)
    if path.endswith("check-runs?per_page=100"):
      return [
        "Quality\thttps://github.com/o/r/actions/runs/9/job/42",
        "Tests\thttps://github.com/o/r/actions/runs/9/job/43",
      ]
    if path.endswith("/jobs/42"):
      return ["Update and Validate"]
    return [""]

  monkeypatch.setattr(preview, "gh_api_lines", fake)
  assert preview.pr_failed_steps(".") == ["Quality / Update and Validate"]
  assert seen == [
    "repos/o/r/commits/abc1234/check-runs?per_page=100",
    "repos/o/r/actions/jobs/42",
    "repos/o/r/actions/jobs/43",
  ]
  monkeypatch.setattr(preview, "gh_api_lines", lambda root, path, projection: None)
  assert preview.pr_failed_steps(".") == []


def test_a_logs_call_reads_the_routed_run_status_and_output():
  """A routed run reads back through the logs command, live and finished."""
  with tempfile.TemporaryDirectory() as log_dir:
    live_detached_placeholder(log_dir, "watch", ["bash", "-c", "make check"])
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": log_dir}

    def cli(*arguments):
      return subprocess.run(
        [sys.executable, str(Path(preview.__file__)), *arguments],
        capture_output=True,
        text=True,
        check=False,
        env=env,
      )

    live = cli("run", "logs", "watch")
    assert live.returncode == 0, live.stderr
    assert live.stdout.startswith("run watch running "), live.stdout
    preview.run_command(
      log_dir,
      "watch",
      ["--", sys.executable, "-c", "print('first'); raise SystemExit(3)"],
    )
    done = cli("run", "logs", "watch")
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("run watch done: exit 3 "), done.stdout
    assert "first" in done.stdout, done.stdout
    missing = cli("run", "logs", "nothing")
    assert missing.returncode == 1, missing.stdout
    assert "No routed run named nothing." in missing.stdout + missing.stderr


def test_a_failed_background_start_keeps_the_refusal(capsys, monkeypatch):
  # A spawn that never left must not read as a running wait: the tick refuses the line
  # and names the route command that takes it.
  monkeypatch.setattr(preview, "detach_run", lambda *args, **kwargs: False)
  with tempfile.TemporaryDirectory() as refused_dir:
    assert (
      preview.pr_check_wait(refused_dir, "gh pr checks 7") == preview.PR_CHECK_REFUSED
    )
    # A line that only mentions the words is not a wait, so it runs untouched.
    assert (
      preview.pr_check_wait(refused_dir, "echo gh pr checks 7")
      == preview.PR_CHECK_OTHER
    )
    refused = capsys.readouterr().err
    assert refused.startswith("RUN BLOCKED: "), refused
    assert "arena-preview run start pr-checks" in refused, refused


def test_a_failed_spawn_records_a_terminal_route_failure(monkeypatch):
  """A launcher failure becomes a visible failed verdict instead of a live placeholder."""

  def fail_spawn(*args, **kwargs):
    raise OSError("cannot spawn")

  monkeypatch.setattr(preview.subprocess, "Popen", fail_spawn)
  with tempfile.TemporaryDirectory() as directory:
    assert preview.detach_run(directory, "failed", ["true"]) is False
    record = json.loads(
      (Path(directory) / "runs" / "failed.json").read_text(encoding="utf-8")
    )
    assert record["exit"] == 1
    assert record["verdict"] == "routed child failed to start; rerun the gate"
    assert record["finished_at"] and record["announced"] is False


def test_an_orphaned_route_becomes_terminal_and_can_restart(capsys, monkeypatch):
  """A dead child cannot reserve a route name forever."""
  with tempfile.TemporaryDirectory() as directory:
    path = preview.write_detached_placeholder(directory, "orphan", ["true"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update({"pid": 999_999, "pid_started_at": "gone"})
    path.write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(preview, "process_start_identity", lambda pid: None)
    assert preview.live_runs(directory) == []
    assert preview.run_notices(directory, show_running=True) == 1
    notice = capsys.readouterr().out
    assert "run orphan done: exit 1" in notice
    record = json.loads(path.read_text(encoding="utf-8"))
    assert (
      record["verdict"]
      == "routed child exited without recording a verdict; rerun the gate"
    )
    monkeypatch.setenv(preview.DETACH_DRY_RUN, "1")
    assert preview.detach_run(directory, "orphan", ["true"])
    restarted = json.loads(path.read_text(encoding="utf-8"))
    assert restarted["exit"] is None and restarted["verdict"] is None


def test_a_second_line_keeps_the_standing_wait(monkeypatch):
  # One live wait per name: a family that already runs keeps its record, so a repeated
  # line cannot restart the same suite.
  monkeypatch.setenv("ARENA_PREVIEW_DETACH_DRY", "1")
  with tempfile.TemporaryDirectory() as standing_dir:
    assert preview.detach_run(standing_dir, "pytest", ["bash", "-c", "pytest -q"])
    record = Path(standing_dir) / "runs" / "pytest.json"
    first = json.loads(record.read_text(encoding="utf-8"))["started_at"]
    assert preview.detach_run(standing_dir, "pytest", ["bash", "-c", "pytest -q"])
    assert json.loads(record.read_text(encoding="utf-8"))["started_at"] == first


def test_routed_runs_derive_task_blocking(tmp_path, monkeypatch, capsys):
  """Live run links block without changing the saved task schema."""
  store = preview.Store(tmp_path, create=True)
  store.write_task("first", "First task", ["Run the checks"], task_type="code")
  store.write_task("second", "Second task", ["Keep working"], task_type="code")
  monkeypatch.setenv(preview.DETACH_DRY_RUN, "1")

  assert preview.detach_run(tmp_path, "alpha", ["true"])
  alpha = json.loads((tmp_path / "runs" / "alpha.json").read_text(encoding="utf-8"))
  assert alpha["task_id"] == "first"
  first, second = store.list_tasks()
  assert first["blocked"] is True and first["runs"] == ["alpha"]
  assert second["blocked"] is False
  assert preview.current_task([first, second])["id"] == "second"
  with closing(store.connect()) as db:
    assert db.execute("SELECT blocked FROM tasks WHERE id = 'first'").fetchone()[0] == 0

  assert preview.detach_run(tmp_path, "bravo", ["true"], task_id="first")
  first = store.task_record("first")
  assert first["blocked"] is True and first["runs"] == ["alpha", "bravo"]
  listed = preview.format_task_list(store.list_tasks())
  assert "runs alpha, bravo" in listed

  assert preview.run_command(tmp_path, "alpha", ["--", "true"]) == 0
  capsys.readouterr()
  first = store.task_record("first")
  assert first["blocked"] is True and first["runs"] == ["bravo"]
  assert preview.run_command(tmp_path, "bravo", ["--", "false"]) == 1
  capsys.readouterr()
  first = store.task_record("first")
  assert first["blocked"] is False and "runs" not in first

  store.autosave()
  saved = [json.loads(line) for line in store.save_path.read_text().splitlines()]
  saved_first = next(row for row in saved if row.get("id") == "first")
  assert "runs" not in saved_first and "blocked" not in saved_first


def test_route_task_selection_validation_and_repeated_name(tmp_path, monkeypatch):
  """An explicit task overrides automatic selection, while a standing run keeps its link."""
  store = preview.Store(tmp_path, create=True)
  store.write_task(
    "waiting", "Waiting", ["Wait for a report"], blocked=True, task_type="code"
  )
  store.write_task("current", "Current", ["Run the gate"], task_type="code")
  store.write_task(
    "finished", "Finished", ["Already done"], status="finished", task_type="code"
  )
  monkeypatch.setenv(preview.DETACH_DRY_RUN, "1")

  assert preview.detach_run(tmp_path, "automatic", ["true"])
  automatic = json.loads(
    (tmp_path / "runs" / "automatic.json").read_text(encoding="utf-8")
  )
  assert automatic["task_id"] == "current"
  assert preview.detach_run(tmp_path, "automatic", ["false"], task_id="waiting")
  repeated = json.loads(
    (tmp_path / "runs" / "automatic.json").read_text(encoding="utf-8")
  )
  assert repeated["task_id"] == "current" and repeated["argv"] == ["true"]

  before = sorted((tmp_path / "runs").glob("*.json"))
  for task_id in ("missing", "finished"):
    with pytest.raises(ValueError, match=task_id):
      preview.detach_run(tmp_path, f"invalid-{task_id}", ["true"], task_id=task_id)
  assert sorted((tmp_path / "runs").glob("*.json")) == before

  empty = tmp_path / "empty"
  preview.Store(empty, create=True)
  assert preview.detach_run(empty, "unlinked", ["true"])
  unlinked = json.loads((empty / "runs" / "unlinked.json").read_text(encoding="utf-8"))
  assert "task_id" not in unlinked


def test_live_run_guards_task_lifecycle_and_orphan_release(tmp_path, monkeypatch):
  """A task cannot disappear under a live run. Orphan reconciliation releases it."""
  store = preview.Store(tmp_path, create=True)
  store.write_task("linked", "Linked", ["Run the gate"], task_type="code")
  monkeypatch.setenv(preview.DETACH_DRY_RUN, "1")
  assert preview.detach_run(tmp_path, "gate", ["true"], task_id="linked")

  guarded = (
    lambda: store.write_task("linked", status="finished"),
    lambda: store.remove_task("linked"),
    lambda: store.amend_task("linked", "renamed"),
    lambda: store.rename_entity("linked", "renamed"),
  )
  for change in guarded:
    with pytest.raises(ValueError, match="gate"):
      change()
  assert store.task_record("linked")["status"] == "upcoming"

  path = tmp_path / "runs" / "gate.json"
  record = json.loads(path.read_text(encoding="utf-8"))
  record["pid_started_at"] = "orphaned"
  path.write_text(json.dumps(record), encoding="utf-8")
  monkeypatch.setattr(preview, "process_start_identity", lambda pid: None)
  released = store.task_record("linked")
  assert released["blocked"] is False and "runs" not in released
  assert json.loads(path.read_text(encoding="utf-8"))["exit"] == 1
  assert store.write_task("linked", status="finished")["status"] == "finished"


def test_live_run_guards_bulk_task_removal(tmp_path, monkeypatch):
  """State replacement and clearing cannot remove a task owned by a live run."""
  store = preview.Store(tmp_path, create=True)
  store.write_task("linked", "Linked", ["Run the gate"], task_type="code")
  monkeypatch.setenv(preview.DETACH_DRY_RUN, "1")
  assert preview.detach_run(tmp_path, "gate", ["true"], task_id="linked")
  store.autosave()
  saved = store.save_path.read_text(encoding="utf-8")

  for change in (
    lambda: store.import_tasks([], replace=True),
    lambda: store.import_state(saved),
    store.clear_state,
  ):
    with pytest.raises(ValueError, match="gate"):
      change()
  assert store.task_record("linked")["status"] == "upcoming"


def test_route_cli_accepts_task_and_task_cli_rejects_manual_block(tmp_path):
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  store.write_task("linked", "Linked", ["Run the gate"], task_type="code")
  environment = {
    **os.environ,
    "ARENA_PREVIEW_STATE_DIR": str(tmp_path),
    preview.DETACH_DRY_RUN: "1",
  }
  routed = subprocess.run(
    [
      sys.executable,
      str(Path(preview.__file__)),
      "run",
      "start",
      "--task",
      "linked",
      "checks",
      "--",
      "true",
    ],
    capture_output=True,
    text=True,
    check=False,
    env=environment,
  )
  assert routed.returncode == 0, routed.stderr
  record = json.loads((tmp_path / "runs" / "checks.json").read_text(encoding="utf-8"))
  assert record["task_id"] == "linked"

  blocked = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "task", "set", "linked", "--blocked"],
    capture_output=True,
    text=True,
    check=False,
    env=environment,
  )
  assert blocked.returncode == 2
  assert "--blocked" in blocked.stderr
  help_text = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "task", "set", "--help"],
    capture_output=True,
    text=True,
    check=True,
    env=environment,
  ).stdout
  # The manual mark is gone. The dependency flag names the task it waits on.
  assert not re.search(r"--blocked(?!-)", help_text)
  assert "--blocked-by" in help_text and "--unblocked" in help_text


def test_route_cli_rejects_task_after_run_name(tmp_path):
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  store.write_task("linked", "Linked", ["Run the gate"], task_type="code")
  environment = {**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)}

  for misplaced in (["--task", "linked"], ["--task=linked"]):
    rejected = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "run",
        "start",
        "checks",
        *misplaced,
        "--",
        "true",
      ],
      capture_output=True,
      text=True,
      check=False,
      env=environment,
    )

    assert rejected.returncode == 2
    assert (
      "Use: arena-preview run start --task <id> <name> -- <command>" in rejected.stderr
    )
    assert not (tmp_path / "runs" / "checks.json").exists()


@pytest.mark.parametrize("head_exit", [0, 7])
def test_chained_runs_wait_and_cancel_on_head_failure(tmp_path, monkeypatch, head_exit):
  store = preview.Store(tmp_path, create=True)
  store.write_task("linked", "Linked", ["Run the chain"], task_type="code")
  monkeypatch.setenv(preview.DETACH_DRY_RUN, "1")
  names = ("head", "middle", "tail")
  events = tmp_path / "events"
  events.write_text("")
  commands = {}
  for index, name in enumerate(names):
    code = (
      f"from pathlib import Path; p=Path({str(events)!r}); "
      f"assert p.read_text().splitlines() == {list(names[:index])!r}; "
      f"p.write_text(p.read_text()+{name!r}+'\\n'); "
      f"raise SystemExit({head_exit if name == 'head' else 0})"
    )
    commands[name] = [sys.executable, "-c", code]
    options = {"after": names[index - 1]} if index else {}
    assert preview.detach_run(
      tmp_path, name, commands[name], task_id="linked", **options
    )
  assert store.task_record("linked")["blocked"] is True
  waited = []

  def advance(_seconds):
    waiting = next(
      name for name in names if preview.routed_record(tmp_path, name)["exit"] is None
    )
    assert waiting != "tail"
    waited.append(waiting)
    preview.run_command(tmp_path, waiting, commands[waiting])

  monkeypatch.setattr(preview.time, "sleep", advance)
  result = preview.run_command(tmp_path, "tail", commands["tail"])
  assert waited
  assert bool(result) == bool(head_exit)
  assert events.read_text().splitlines() == (
    list(names) if not head_exit else [names[0]]
  )
  assert store.task_record("linked")["blocked"] is False
  assert all(
    preview.routed_record(tmp_path, name)["exit"] is not None for name in names
  )


def test_chained_run_cli_and_parent_validation(tmp_path, monkeypatch):
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  monkeypatch.setenv(preview.DETACH_DRY_RUN, "1")
  assert preview.detach_run(tmp_path, "head", ["true"])
  assert preview.run_command(tmp_path, "head", ["true"]) == 0
  environment = {**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)}
  result = subprocess.run(
    [
      sys.executable,
      str(Path(preview.__file__)),
      "run",
      "start",
      "--after",
      "head",
      "cli-child",
      "--",
      "true",
    ],
    capture_output=True,
    text=True,
    check=False,
    env=environment,
  )
  assert result.returncode == 0, result.stderr
  record = preview.json_record(preview.run_record_path(tmp_path, "cli-child"))
  assert record["after"]["name"] == "head"
  for parent in ("missing", "../head", "self"):
    with pytest.raises(ValueError):
      preview.detach_run(tmp_path, "self", ["true"], after=parent)
  assert not preview.run_record_path(tmp_path, "self").exists()
  assert preview.detach_run(tmp_path, "bound", ["true"], after="head")
  preview.write_detached_placeholder(tmp_path, "head", ["true"])
  assert preview.run_command(tmp_path, "head", ["true"]) == 0
  executed = tmp_path / "executed"
  assert preview.run_command(
    tmp_path, "bound", [sys.executable, "-c", f"open({str(executed)!r}, 'w').close()"]
  )
  assert not executed.exists()
  assert preview.detach_run(tmp_path, "vanished", ["true"], after="head")
  preview.run_record_path(tmp_path, "head").unlink()
  assert preview.run_command(
    tmp_path,
    "vanished",
    [sys.executable, "-c", f"open({str(executed)!r}, 'w').close()"],
  )
  assert not executed.exists()


def test_route_starts_the_run_detached(tmp_path, monkeypatch):
  # The starter shell returns before the command. Its child completes the run record.
  # The state directory travels through the environment for the child's own resolution.
  monkeypatch.setenv("ARENA_PREVIEW_STATE_DIR", str(tmp_path))
  marker = tmp_path / "late.txt"
  code = (
    "import pathlib, time; time.sleep(1.5);"
    f" pathlib.Path({str(marker)!r}).write_text('done')"
  )
  started = time.monotonic()
  assert (
    preview.route_command(str(tmp_path), "quick", ["--", sys.executable, "-c", code])
    == 0
  )
  assert time.monotonic() - started < 1.0
  record = tmp_path / "runs" / "quick.json"
  deadline = time.monotonic() + 20
  while time.monotonic() < deadline:
    if (
      record.is_file()
      and json.loads(record.read_text(encoding="utf-8")).get("exit") == 0
    ):
      break
    time.sleep(0.2)
  assert marker.is_file(), "the detached child never ran"
  finished = json.loads(record.read_text(encoding="utf-8"))
  assert finished["exit"] == 0
  assert isinstance(finished["pid"], int) and finished["pid_started_at"]


def test_worktree_gate_flow():
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "root"
    root.mkdir()

    def git(*args, cwd=root, input=None):
      result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=input,
        capture_output=True,
        text=True,
        check=False,
      )
      assert result.returncode == 0, result.stderr
      return result.stdout

    git("init", "-b", "main")
    git("config", "user.name", "Check")
    git("config", "user.email", "check@example.invalid")
    (root / "allowed").mkdir()
    (root / "allowed" / "change.txt").write_text("before\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base")
    state_dir = Path(directory) / "state"
    preview.Store(state_dir, create=True)
    live_detached_placeholder(state_dir, "task-a", ["bash", "-c", "pytest"])
    worktree = Path(directory) / "task-b"
    script = str(Path(preview.__file__))
    environment = {**os.environ, "ARENA_PREVIEW_STATE_DIR": str(state_dir)}
    invalid_gate = subprocess.run(
      [
        sys.executable,
        script,
        "worktree",
        "start",
        "invalid-gate",
        str(Path(directory) / "invalid-gate"),
        "--gate",
        "../gate",
        "--allow",
        "allowed/**",
      ],
      cwd=root,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert invalid_gate.returncode == 1 and "Gate names" in invalid_gate.stderr
    started = subprocess.run(
      [
        sys.executable,
        script,
        "worktree",
        "start",
        "task-b",
        str(worktree),
        "--gate",
        "task-a",
        "--allow",
        "allowed/**",
      ],
      cwd=root,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert started.returncode == 0, started.stderr
    nested = subprocess.run(
      [
        sys.executable,
        script,
        "worktree",
        "start",
        "nested",
        str(Path(directory) / "nested"),
        "--gate",
        "task-a",
        "--allow",
        "allowed/**",
      ],
      cwd=worktree,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert nested.returncode == 1 and "registered root" in nested.stderr
    assert git("branch", "--show-current", cwd=worktree).strip() == ""
    before_reads = set((state_dir / "runs").glob("*.json"))
    for line in (
      "git status --short",
      "rg --line-number 'pytest|ruff' allowed/change.txt",
    ):
      allowed = subprocess.run(
        [sys.executable, script, "pre", "--line", line, "--command", line],
        cwd=worktree,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
      )
      assert allowed.returncode == 0, allowed.stderr
    assert set((state_dir / "runs").glob("*.json")) == before_reads
    blocked = subprocess.run(
      [sys.executable, script, "pre", "--line", "pytest -q", "--command", "pytest -q"],
      cwd=worktree,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert blocked.returncode == 130 and "WORKTREE BLOCKED" in blocked.stderr
    for action in ("git commit -m x", "git push"):
      blocked = subprocess.run(
        [sys.executable, script, "pre", "--line", action, "--command", action],
        cwd=worktree,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
      )
      assert blocked.returncode == 130 and "WORKTREE BLOCKED" in blocked.stderr
    routed = subprocess.run(
      [sys.executable, script, "run", "start", "task-c", "--", "true"],
      cwd=worktree,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert routed.returncode == 1 and "WORKTREE BLOCKED" in routed.stderr
    committed = subprocess.run(
      [
        sys.executable,
        script,
        "pre",
        "--line",
        "git commit -m x",
        "--command",
        "git commit -m x",
      ],
      cwd=worktree,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert committed.returncode == 130 and "WORKTREE BLOCKED" in committed.stderr
    waiting = subprocess.run(
      [sys.executable, script, "worktree", "collect", "task-b"],
      cwd=root,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert waiting.returncode == 1 and "still running" in waiting.stderr
    run_path = state_dir / "runs" / "task-a.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["pid_started_at"] = "orphaned"
    run_path.write_text(json.dumps(run), encoding="utf-8")
    orphaned = subprocess.run(
      [sys.executable, script, "worktree", "collect", "task-b"],
      cwd=root,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert orphaned.returncode == 1 and "task-a" in orphaned.stderr
    run = json.loads(run_path.read_text(encoding="utf-8"))
    assert run["exit"] == 1 and "without recording" in run["verdict"]
    run.update({"exit": 0, "seconds": 1, "verdict": "passed"})
    run_path.write_text(json.dumps(run), encoding="utf-8")
    (worktree / "allowed" / "change.txt").write_text("after\n", encoding="utf-8")
    (worktree / "allowed" / "new.txt").write_text("new\n", encoding="utf-8")
    (worktree / "outside.txt").write_text("outside\n", encoding="utf-8")
    refused = subprocess.run(
      [sys.executable, script, "worktree", "collect", "task-b"],
      cwd=root,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert refused.returncode == 1 and "outside.txt" in refused.stderr
    (worktree / "outside.txt").unlink()
    collected = subprocess.run(
      [sys.executable, script, "worktree", "collect", "task-b"],
      cwd=root,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert collected.returncode == 0, collected.stderr
    assert "allowed/change.txt" in collected.stdout
    assert "allowed/new.txt" in collected.stdout
    git("apply", "--binary", "-", input=collected.stdout)
    assert (root / "allowed" / "change.txt").read_text(encoding="utf-8") == "after\n"
    assert (root / "allowed" / "new.txt").read_text(encoding="utf-8") == "new\n"


def test_worktree_start_without_a_gate_collects_at_once():
  """A worktree with no gate records no link and collects its patch without a wait."""
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "root"
    root.mkdir()

    def git(*args, cwd=root):
      result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
      )
      assert result.returncode == 0, result.stderr
      return result.stdout

    git("init", "-b", "main")
    git("config", "user.name", "Check")
    git("config", "user.email", "check@example.invalid")
    (root / "allowed").mkdir()
    (root / "allowed" / "change.txt").write_text("before\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base")
    state_dir = Path(directory) / "state"
    preview.Store(state_dir, create=True)
    worktree = Path(directory) / "task-c"
    script = str(Path(preview.__file__))
    environment = {**os.environ, "ARENA_PREVIEW_STATE_DIR": str(state_dir)}
    started = subprocess.run(
      [
        sys.executable,
        script,
        "worktree",
        "start",
        "task-c",
        str(worktree),
        "--allow",
        "allowed/**",
      ],
      cwd=root,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert started.returncode == 0, started.stderr
    record = json.loads(
      (state_dir / "worktrees" / "task-c.json").read_text(encoding="utf-8")
    )
    assert record["gate"] is None
    (worktree / "allowed" / "change.txt").write_text("after\n", encoding="utf-8")
    collected = subprocess.run(
      [sys.executable, script, "worktree", "collect", "task-c"],
      cwd=root,
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert collected.returncode == 0, collected.stderr
    assert "after" in collected.stdout


def test_a_detached_run_prints_one_status_line_per_call(capsys):
  """A detached wait reads as alive: one status line per gate call, none in a poll."""
  with tempfile.TemporaryDirectory() as detached_dir:
    live_detached_placeholder(
      detached_dir, "pr-checks", ["bash", "-c", "gh pr checks 7"]
    )
    assert preview.run_notices(detached_dir) == 0
    assert capsys.readouterr().err == ""
    preview.run_notices(detached_dir, show_running=True)
    line = capsys.readouterr().err
    assert line.startswith("run pr-checks running "), line
    assert line.rstrip().endswith("s")
    # The finished record announces once, and the status line stops.
    preview.run_command(detached_dir, "pr-checks", ["--", "true"])
    preview.run_notices(detached_dir, show_running=True)
    done = capsys.readouterr()
    assert "run pr-checks done: exit 0" in done.out, done.out  # nonemo: NMT100
    assert done.err == ""
    preview.run_notices(detached_dir, show_running=True)
    later = capsys.readouterr()
    assert later.out == "" and later.err == ""


def test_a_live_run_progress_line_prints_once_per_call(capsys):
  """A live watcher progress line reaches later calls without ending the run."""
  with tempfile.TemporaryDirectory() as detached_dir:
    live_detached_placeholder(
      detached_dir, "pr-checks", ["bash", "-c", "gh pr checks 7"]
    )
    preview.write_run_progress(detached_dir, "pr-checks", "Failed so far: Quality")
    preview.write_run_progress(detached_dir, "pr-checks", "Failed so far: Tests")

    assert preview.run_notices(detached_dir) == 1
    assert (
      "run pr-checks progress: Failed so far: Quality"  # nonemo: NMT100
      in capsys.readouterr().err
    )
    assert preview.run_notices(detached_dir) == 1
    assert (
      "run pr-checks progress: Failed so far: Tests"  # nonemo: NMT100
      in capsys.readouterr().err
    )
    assert preview.run_notices(detached_dir) == 0
    record = preview.routed_record(detached_dir, "pr-checks")
    assert record["exit"] is None
    assert record["progress_announced"] == 2


def test_a_hook_prints_only_one_routed_run_notice(capsys):
  with tempfile.TemporaryDirectory() as detached_dir:
    live_detached_placeholder(detached_dir, "alpha", ["bash", "-c", "gh pr checks 7"])
    live_detached_placeholder(detached_dir, "bravo", ["bash", "-c", "gh pr checks 8"])
    preview.run_command(detached_dir, "bravo", ["--", "true"])
    capsys.readouterr()
    assert preview.run_notices(detached_dir, show_running=True) == 1
    finished = capsys.readouterr()
    assert finished.out.strip().startswith("run bravo done: exit 0"), finished.out
    assert finished.err == ""
    assert preview.run_notices(detached_dir, show_running=True) == 1
    live = capsys.readouterr()
    assert live.out == ""
    assert live.err.strip().startswith("run alpha running "), live.err


def test_the_reminder_carries_the_running_status_line():
  """The hook reminder runs after every call, so the heartbeat reaches the agent."""
  with tempfile.TemporaryDirectory() as heartbeat_dir:
    preview.Store(heartbeat_dir, create=True)
    preview.Store(heartbeat_dir, create=True).set_meta("port", guard_port())
    live_detached_placeholder(
      heartbeat_dir, "pr-checks", ["bash", "-c", "gh pr checks 7"]
    )
    result = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "--reminder"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": heartbeat_dir},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr.strip().startswith("run pr-checks running "), result.stderr
    # The gate path stays quiet for a live run: the reminder owns the one line per call.
    gate = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "gate", "--line", "git status"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": heartbeat_dir},
    )
    assert "run pr-checks running" not in gate.stderr, gate.stderr  # nonemo: NMT100


def test_reminder_prioritizes_an_inbox_item_over_a_live_run():
  with tempfile.TemporaryDirectory() as heartbeat_dir:
    store = preview.Store(heartbeat_dir, create=True)
    store.set_meta("port", guard_port())
    store.note("owner-note", "Read this first")
    live_detached_placeholder(
      heartbeat_dir, "pr-checks", ["bash", "-c", "gh pr checks 7"]
    )
    result = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "--reminder"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": heartbeat_dir},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr.startswith("calls 1 unacked 1 note | "), result.stderr


def test_reminder_reports_a_finished_run_without_a_second_line(capsys):
  with tempfile.TemporaryDirectory() as heartbeat_dir:
    preview.Store(heartbeat_dir, create=True)
    preview.Store(heartbeat_dir, create=True).set_meta("port", guard_port())
    live_detached_placeholder(
      heartbeat_dir, "pr-checks", ["bash", "-c", "gh pr checks 7"]
    )
    preview.run_command(heartbeat_dir, "pr-checks", ["--", "true"])
    capsys.readouterr()
    result = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "--reminder"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": heartbeat_dir},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith("run pr-checks done: exit 0"), result.stdout
    assert "\n" not in result.stdout.strip(), result.stdout
    assert result.stderr == ""


def test_shell_command_text_drops_the_launcher():
  """A block names the command itself, not the bash wrapper the agent shell started it with."""
  assert (
    preview.shell_command_text("/bin/bash -l -c git log --oneline -1")
    == "git log --oneline -1"
  )
  assert preview.shell_command_text("bash -c 'npm test'") == "npm test"
  assert preview.shell_command_text("npm test") == "npm test"


def test_first_blocking_piece_names_the_part_that_blocks():
  """A blocked call names its first part that is not an inbox call or an inert prefix."""
  assert (
    preview.first_blocking_piece("arena-preview read && arena-preview ack a1 'x'")
    is None
  )
  assert preview.first_blocking_piece("arena-preview read | tail -1") == "tail -1"
  assert preview.first_blocking_piece("arena-preview read && npm test") == "npm test"


def test_mkdir_is_inert_for_the_read_set():
  """A mkdir prefix carries no work, so the bible rule judges the command beside it.

  The harness rebuilds a missing workspace root with `mkdir -p` before the agent's call.
  Git tracks files, not directories, so the directory cannot reach a commit. A write
  into it stays checked.
  """
  assert "mkdir" in preview.INERT_COMMANDS
  root = "/home/user/clankers"
  assert preview.read_set_actions(f"mkdir -p '{root}' && arena-preview read") == (
    "read",
  )
  assert (
    preview.first_blocking_piece(f"mkdir -p '{root}' && rm -rf /tmp/x")
    == "rm -rf /tmp/x"
  )
  assert preview.read_set_actions(f"mkdir -p '{root}' && npm test") is None


def test_quiet_inbox_line_allows_cd_and_blocks_tail_head_grep():
  # A cd prefix is fine on the writer's line, on the way to a read or a poll. The banned
  # readers end the quiet-line exemption, so their call blocks instead of riding along.
  clean = "cd /home/user/clankers && arena-preview read"
  poll = "cd /home/user/clankers && arena-preview poll"
  assert preview.quiet_inbox_line(clean) is True
  assert preview.quiet_inbox_line(poll) is True
  for banned in ("tail", "head", "grep"):
    line = f"cd /home/user/clankers && {banned} -5 state.jsonl && arena-preview read"
    assert preview.quiet_inbox_line(line) is False, line
  assert preview.quiet_inbox_line("arena-preview read | tail -1") is False


def test_gate_bans_timeout_on_poll():
  # A shell timeout kills a poll and drops its listing, so the gate rejects it even for an empty inbox.
  # Other inbox calls and clean poll lines pass.
  assert preview.poll_timeout_line("timeout 300 arena-preview poll") is True
  assert preview.poll_timeout_line("timeout 1800 arena-preview poll --max 1") is True
  assert (
    preview.poll_timeout_line("cd /home/user && timeout 60 preview.py poll") is True
  )
  assert preview.poll_timeout_line("arena-preview poll") is False
  assert preview.poll_timeout_line("timeout 5 arena-preview read") is False
  assert preview.poll_timeout_line("git push origin main") is False
  # A line that only mentions both words, like a script that documents the ban, is fine.
  script = "python3 - <<'PY'\nentry = \"timeout 1800\"\narena-preview poll\nPY"
  assert preview.poll_timeout_line(script) is False
  with tempfile.TemporaryDirectory() as ban_dir:
    ban_script = str(Path(preview.__file__))

    def run_gate(line):
      return subprocess.run(
        [sys.executable, ban_script, "gate", "--line", line],
        capture_output=True,
        text=True,
        check=False,
        cwd=ban_dir,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": ban_dir},
      )

    banned = run_gate("timeout 300 arena-preview poll")
    assert banned.returncode == 1
    assert banned.stdout.startswith("TIMEOUT BANNED: "), banned.stdout
    assert "1800" in banned.stdout
    clean = run_gate("arena-preview poll")
    assert clean.returncode == 0, clean.stdout


def test_a_long_run_line_detaches_the_wait():
  # A long run uses the background. The tick detaches it under a run name and writes status. The turn continues.
  # A line that only prints the words stays fine.
  assert preview.long_run_name("gh pr checks 7") == "pr-checks"
  assert preview.long_run_name("gh pr checks 7 --watch") == "pr-checks"
  assert preview.long_run_name("cd repo && gh pr checks 7") == "pr-checks"
  assert preview.long_run_name("ARENA=1 gh run watch 12345") == "run-watch"
  assert preview.long_run_name("arena-preview run ci -- gh pr checks 7") is None
  assert preview.long_run_name("echo gh pr checks 7") is None
  assert preview.long_run_name("gh pr view 7") is None
  assert preview.long_run_name("gh run list") is None
  assert preview.long_run_name("gh -R nemoe7/clankers pr checks 7") is not None
  assert preview.long_run_name("gh --repo nemoe7/clankers pr checks 7") is not None
  assert preview.long_run_name("gh -R nemoe7/clankers run watch 7") is not None
  assert preview.long_run_name("env gh pr checks 7") is not None
  assert preview.long_run_name("command gh pr checks 7") is not None
  assert preview.long_run_name("timeout 60 gh pr checks 7") is not None
  assert preview.long_run_name("xargs -n1 gh pr checks") is not None
  assert preview.long_run_name("result=$(gh pr checks 7)") is not None
  assert preview.long_run_name("(gh pr checks 7)") is not None
  # A family word inside quotes is text, never a command, so a quoted reply stays fine,
  # and a quoted substitution keeps its own hole: the body reads as text.
  assert preview.long_run_name('echo "gh pr checks 7"') is None
  assert preview.long_run_name("echo 'gh pr checks 7'") is None
  assert preview.long_run_name("gh pr view 7 --json checks") is None
  # The test runs join the check waits, because a suite can outrun the call that starts it.
  assert preview.long_run_name("pytest -q") is not None
  assert preview.long_run_name(".venv/bin/python -m pytest -q") is not None
  assert preview.long_run_name("node --test maintenance/workflows/x.cjs") is not None
  assert preview.long_run_name("pytest -q") == "pytest"
  assert preview.long_run_name("python3 -m pytest -q") == "pytest"
  assert preview.long_run_name("node --test x.cjs") == "node-tests"
  # A tool that merely names a suite is not a suite.
  # The common test runners join the suite heads, each under its own run name.
  runners = {
    "npm test": "npm-tests",
    "npm run test": "npm-tests",
    "npm run test:unit": "npm-tests",
    "yarn test": "yarn-tests",
    "pnpm test": "pnpm-tests",
    "make test": "make-tests",
    "npx jest": "npx-tests",
    "npx vitest --run": "npx-tests",
    "npx mocha tests/x.js": "npx-tests",
    "npx ava": "npx-tests",
    "go test ./...": "go-tests",
    "cargo test --all": "cargo-tests",
    "dotnet test": "dotnet-tests",
    "mvn test": "mvn-tests",
    "./mvnw test": "mvn-tests",
    "gradle test": "gradle-tests",
    "./gradlew test": "gradle-tests",
    "tox -e py311": "tox",
    "nox": "nox",
    "timeout 600 npm test": "npm-tests",
    "cd app && make test": "make-tests",
  }
  for line, name in runners.items():
    assert preview.long_run_name(line) == name, line
    assert preview.long_run_name(line) is not None, line
  # A build command in the same family stays legal, as does a runner named as text.
  builds = (
    "npm install",
    "npm run build",
    "npm run lint",
    "yarn install",
    "pnpm install",
    "make build",
    "make test-install",
    "npx tsc --noEmit",
    "go build ./...",
    "cargo build",
    "gradle build",
    "./gradlew build",
    "dotnet build",
    "mvn package",
    "echo npm test",
    'echo "make test"',
    "grep -r 'go test' .",
  )
  for line in builds:
    assert preview.long_run_name(line) is None, line
  assert preview.long_run_name("echo pytest") is None
  assert preview.long_run_name("python -m pip install pytest") is None
  assert preview.long_run_name("grep -r pytest .") is None
  assert preview.long_run_name("node --version") is None
  with tempfile.TemporaryDirectory() as checks_dir:
    checks_script = str(Path(preview.__file__))

    def run_tick(line):
      return subprocess.run(
        [
          sys.executable,
          checks_script,
          "pre",
          "--line",
          line,
          "--command",
          line,
          "--repo",
          checks_dir,
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=checks_dir,
        env={
          **os.environ,
          "ARENA_PREVIEW_STATE_DIR": checks_dir,
          "ARENA_PREVIEW_DETACH_DRY": "1",
        },
      )

    banned = run_tick("gh pr checks 7 --watch")
    assert banned.returncode == 2, banned.stderr
    assert "RUN DETACHED: " in banned.stderr, banned.stderr
    assert "`pr-checks`" in banned.stderr, banned.stderr
    watch = run_tick("gh run watch 7")
    assert watch.returncode == 2 and "`run-watch`" in watch.stderr, watch.stderr
    suite = run_tick("pytest -q")
    assert suite.returncode == 2 and "`pytest`" in suite.stderr, suite.stderr
    node = run_tick("node --test x.cjs")
    assert node.returncode == 2 and "`node-tests`" in node.stderr, node.stderr
    npm = run_tick("npm test")
    assert npm.returncode == 2 and "`npm-tests`" in npm.stderr, npm.stderr
    make = run_tick("cd app && make test")
    assert make.returncode == 2 and "`make-tests`" in make.stderr, make.stderr
    go = run_tick("go test ./...")
    assert go.returncode == 2 and "`go-tests`" in go.stderr, go.stderr
    recorded = json.loads(
      (Path(checks_dir) / "runs" / "pr-checks.json").read_text(encoding="utf-8")
    )
    assert recorded["exit"] is None and recorded["detached"] is True
    clean = run_tick("echo gh pr checks 7")
    assert clean.returncode == 0 and "RUN DETACHED" not in clean.stderr, clean.stderr


def test_route_names_the_worktree_step(capsys):
  """A routed call tells the agent to continue the next task in a worktree."""
  with (
    tempfile.TemporaryDirectory() as directory,
    patch.dict(os.environ, {"ARENA_PREVIEW_DETACH_DRY": "1"}),
  ):
    assert preview.route_command(directory, "gates", ["make", "check"]) == 0
  captured = capsys.readouterr()
  assert "routed gates:" in captured.err
  assert "arena-preview worktree start" in captured.err  # nonemo: NMT100


def test_gate_blocks_a_cd_line_past_the_threshold():
  # cd is fine on the line, but the count gate still holds it: with a pending note past the threshold a
  # plain cd line meets READ INBOX NOW, and the block names no command, because cd is never the noise.
  with tempfile.TemporaryDirectory() as cd_dir:
    cd_store = preview.Store(cd_dir, create=True)
    cd_store.note("cd-note", "Pending work")
    cd_store.set_meta(preview.POLLS_SINCE_MESSAGE, str(preview.GATE_THRESHOLD))
    cd_run = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "gate",
        "--line",
        "cd /home/user/clankers && python3 work.py",
      ],
      capture_output=True,
      text=True,
      check=False,
      cwd=cd_dir,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": cd_dir},
    )
    assert cd_run.returncode == 1
    assert cd_run.stdout.startswith("BASH BLOCKED AFTER 6 CALLS.\nREAD INBOX NOW. "), (
      cd_run.stdout
    )
    assert "Omit them" not in cd_run.stdout
    assert "`cd`" not in cd_run.stdout


def test_gate_hint_names_the_banned_tools_without_cd():
  # A blocked call that runs grep, head or tail hears which commands to drop. Cd is fine
  # on the line, so the hint never names it, and a clean line hears the plain block alone.
  with tempfile.TemporaryDirectory() as hint_dir:
    hint_store = preview.Store(hint_dir, create=True)
    hint_store.note("hint-note", "Pending work")
    hint_store.set_meta(preview.POLLS_SINCE_MESSAGE, str(preview.GATE_THRESHOLD))
    hint_script = str(Path(preview.__file__))

    def run_gate(line):
      return subprocess.run(
        [sys.executable, hint_script, "gate", "--line", line],
        capture_output=True,
        text=True,
        check=False,
        cwd=hint_dir,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": hint_dir},
      )

    noisy = run_gate("cd /home/user && grep note arena-state/log.jsonl | tail -1")
    assert noisy.returncode == 1
    for word in ("`grep`", "`tail`"):
      assert word in noisy.stdout, noisy.stdout
    assert "`cd`" not in noisy.stdout, noisy.stdout
    assert "Omit them" in noisy.stdout
    assert "`head`" not in noisy.stdout.split("Omit")[0]
    with_head = run_gate("cd /home/user && head -5 arena-state/log.jsonl")
    assert with_head.returncode == 1
    assert "`head`" in with_head.stdout, with_head.stdout
    assert "`cd`" not in with_head.stdout, with_head.stdout
    plain = run_gate("git status")
    assert plain.returncode == 1
    assert "Omit them" not in plain.stdout
    # A line that passes the gate keeps its own counsel, whatever it runs.
    hint_store.acknowledge(["hint-note"], "Cleared")
    passing = run_gate("cd /home/user && grep note log")
    assert passing.returncode == 0
    assert passing.stdout.strip() == ""


def test_dispatch_reminder():
  # Every dispatch carries a reminder without changing stdout. Only a delivered read
  # marks a note seen.
  with tempfile.TemporaryDirectory() as reminder_dir:
    reminder_store = preview.Store(reminder_dir, create=True)
    reminder_store.set_meta("port", guard_port())
    reminder_store.note("reminder-note", "Read this")
    reminder_script = str(Path(preview.__file__))

    def tails(remaining):
      """Return the visible rotating tails, in order, for that task count."""
      filled = (
        preview.fill_reminder(candidate, remaining) for candidate in preview.REMINDERS
      )
      return [text for text in filled if text]

    def reminder_tail(line, remaining):
      """Return the rotating tail one reminder line ends with, or fail."""
      stripped = line.strip()
      for candidate in tails(remaining):
        if stripped.endswith(candidate):
          return candidate
      raise AssertionError(f"No rotating tail in {stripped!r}")

    pending_prefix = "unacked 1 note | "
    assert preview.fill_reminder(preview.TASK_REMINDER, 0) is None
    assert preview.fill_reminder(preview.TASK_REMINDER, 1) == "1 task left."
    assert preview.fill_reminder(preview.TASK_REMINDER, 4) == "4 tasks left."
    # No open task hides that entry, so the line carries the next reminder instead.
    task_at = preview.REMINDERS.index(preview.TASK_REMINDER)
    assert preview.reminder_tail(task_at, 0) == preview.REMINDERS[task_at + 1]
    assert "0 tasks left." not in tails(0)
    for command, remaining in (
      (["task", "list"], 0),
      (
        [
          "task",
          "set",
          "reminder-task",
          "Track work",
          "Step one",
          "--scope",
          "arena suite",
          "--type",
          "misc",
        ],
        1,
      ),
    ):
      result = subprocess.run(
        [sys.executable, reminder_script, *command],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": reminder_dir},
      )
      assert "Tasks" in result.stdout or "task" in result.stdout
      line = result.stderr.strip()
      assert line == pending_prefix + reminder_tail(line, remaining)
      assert reminder_store.state()["notes"][0]["seen_at"] is None
    result = subprocess.run(
      [sys.executable, reminder_script, "read"],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": reminder_dir},
    )
    assert "Inbox" in result.stdout
    line = result.stderr.strip()
    assert line == pending_prefix + reminder_tail(line, 1)
    delivered = reminder_store.state()["notes"][0]["seen_at"]
    assert delivered is not None
    assert reminder_store.state()["notes"][0]["acknowledged_at"] is None
    with (
      patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": reminder_dir}),
      patch.object(sys, "argv", [reminder_script, "read"]),
      patch.object(sys.stdout, "write", side_effect=BrokenPipeError("output failed")),
    ):
      assert preview.main() == 1
    assert reminder_store.state()["notes"][0]["seen_at"] == delivered
    gone = subprocess.run(
      [sys.executable, reminder_script, "seen", "x"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": reminder_dir},
    )
    assert gone.returncode == 2, "read and poll stamp Seen; no seen subcommand remains"
    result = subprocess.run(
      [
        sys.executable,
        reminder_script,
        "ack",
        "reminder-note",
        "Received",
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": reminder_dir},
    )
    assert reminder_tail(result.stderr, 1) in tails(1)
    assert reminder_store.reminder() in tails(1)
    reminder_store.submission("form-answer", "form", "REPORT form: yes")
    form_line = reminder_store.reminder()
    form_prefix = "unacked 1 answer | "
    assert form_line == form_prefix + reminder_tail(form_line, 1)
    reminder_store.acknowledge(["form-answer"], "Received")
    for index in range(3):
      reminder_store.note(f"mixed-{index}", "Pending")
    for name in ("one.txt", "two.txt"):
      upload = reminder_store.save_upload(name, "text/plain", name.encode())
      reminder_store.note(upload["id"], "Uploaded " + name)
    mixed_line = reminder_store.reminder()
    mixed_prefix = "unacked 3 notes, 2 uploads | "
    assert mixed_line == mixed_prefix + reminder_tail(mixed_line, 1)
    assert all(row["seen_at"] is None for row in reminder_store.read()["pending"])


def test_reminder_rotation():
  # The tail rotates through the whole list before it repeats, a hook poll counts itself, a CLI
  # dispatch and a read do not, and the count resets when a new user item arrives.
  with tempfile.TemporaryDirectory() as rotate_dir:
    rotate_store = preview.Store(rotate_dir, create=True)
    rotate_store.set_meta("port", guard_port())
    rotate_script = str(Path(preview.__file__))
    assert len(preview.REMINDERS) == len(set(preview.REMINDERS))
    assert all(
      len(preview.fill_reminder(entry, 1)) <= preview.REMINDER_CHAR_CAP
      for entry in preview.REMINDERS
    )
    assert "Questions: ASAP, in reports." in preview.REMINDERS
    assert "`ask_user` on GH_TOKEN failure." in preview.REMINDERS
    assert "Unpublish stale reports." in preview.REMINDERS
    assert "End turn with `poll`." in preview.REMINDERS
    assert "Publish reports." in preview.REMINDERS
    assert "Never end turn with unblocked tasks." in preview.REMINDERS
    assert (
      "Before pushed-turn end: check PR CI; read verdict on a later call, never loop."
      in preview.REMINDERS
    )
    assert "`task list` first; update as work changes." in preview.REMINDERS
    assert "Grep-verify each edit." in preview.REMINDERS
    assert (
      "Before push: rebase `origin/main`; empty checks mean it moved."
      in preview.REMINDERS
    )
    assert preview.TASK_REMINDER in preview.REMINDERS
    assert "NEVER spam `run logs`." in preview.REMINDERS
    # One open task keeps every entry visible for the rotation checks.
    rotate_store.write_task("rotate-task", "Open work", ["Step one"], task_type="misc")

    def tail_at(index, remaining=1):
      return preview.reminder_tail(index, remaining)

    span = len(preview.REMINDERS)
    cycle = [rotate_store.reminder() for _ in range(span)]
    assert cycle == [tail_at(index) for index in range(span)]
    assert "You have 0 tasks remaining." not in cycle
    assert rotate_store.reminder() == tail_at(0)
    # An idle queue carries the tail alone, and its polls do not count: the tally starts with
    # the pending item it reports.
    assert rotate_store.reminder(advance=True) == tail_at(1)
    assert rotate_store.reminder(advance=True) == tail_at(2)
    assert rotate_store.reminder() == tail_at(3)
    rotate_store.note("rotate-note", "Pending")
    pending = "unacked 1 note | "
    assert rotate_store.reminder() == f"{pending}{tail_at(4)}"
    offset = span + 5
    for cursor, polls in ((offset, 1), (offset + 1, 2)):
      result = subprocess.run(
        [sys.executable, rotate_script, "--reminder"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": rotate_dir},
      )
      tail = tail_at(cursor)
      assert result.stdout == ""
      assert result.stderr.strip() == f"calls {polls} {pending}{tail}"
    result = subprocess.run(
      [sys.executable, rotate_script, "task", "list"],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": rotate_dir},
    )
    assert "Tasks" in result.stdout
    tail = tail_at(offset + 2)
    assert result.stderr.strip() == f"calls 2 {pending}{tail}"
    # A read does not remove the calls since the first unread message. Only a fresh backlog
    # resets the tally. A message landing on an unacked pile leaves it running.
    rotate_store.read()
    assert rotate_store.reminder() == (f"calls 2 {pending}{tail_at(offset + 3)}")
    # An ack empties the queue, so idle polls stop counting, and a fresh note starts at one.
    rotate_store.acknowledge(["rotate-note"], "Done")
    assert rotate_store.meta_value(preview.POLLS_SINCE_MESSAGE) == "0"
    assert rotate_store.reminder(advance=True) == tail_at(offset + 4)
    assert rotate_store.reminder(advance=True) == tail_at(offset + 5)
    rotate_store.note("rotate-later", "Pending again")
    assert rotate_store.reminder(advance=True) == (
      f"calls 1 {pending}{tail_at(offset + 6)}"
    )
    rotate_store.note("rotate-newer", "Another user message")
    newer = "unacked 2 notes | "
    # A second message on an unacked pile keeps the count anchored to the first unread one.
    assert rotate_store.reminder() == (f"calls 1 {newer}{tail_at(offset + 7)}")
    assert rotate_store.reminder(advance=True) == (
      f"calls 2 {newer}{tail_at(offset + 8)}"
    )


def test_reminder_hides_task_entry_with_no_open_task():
  # A finished task stops the count, so that entry yields the next reminder.
  with tempfile.TemporaryDirectory() as hidden_dir:
    hidden_store = preview.Store(hidden_dir, create=True)
    hidden_store.write_task(
      "done-task", "Finished work", ["Step one"], status="finished", task_type="misc"
    )
    task_at = preview.REMINDERS.index(preview.TASK_REMINDER)
    for _ in range(task_at):
      hidden_store.reminder()
    assert hidden_store.reminder() == preview.REMINDERS[task_at + 1]
    hidden_store.write_task("open-task", "Open work", ["Step one"], task_type="misc")
    for _ in range(len(preview.REMINDERS) - 1):
      hidden_store.reminder()
    assert hidden_store.reminder() == "1 task left."


def test_ack_task_reminder():
  # An ack reminds the agent to queue the note's work.
  with tempfile.TemporaryDirectory() as ack_dir:
    preview.Store(ack_dir, create=True).note("ack-work", "Needs work")
    preview.Store(ack_dir, create=True).set_meta("port", guard_port())
    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "ack",
        "ack-work",
        "Ok",
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": ack_dir},
    )
    assert "-m ack-work" in result.stdout  # nonemo: NMT100


def test_report_unread_markers():
  with tempfile.TemporaryDirectory() as marker_dir:
    marker_store = preview.Store(marker_dir, create=True)
    marker_store.set_meta("port", guard_port())
    marker_source = Path(marker_dir) / "form.md"
    marker_source.write_text("Choice?\n- ( ) Yes\n- ( ) No\n\nCustom response: ___\n")
    field = preview.parse_fields(marker_source.read_text())[1][0]
    marker_store.publish("form", "Form", marker_source)
    assert marker_store.state()["reports"][0]["needs_answer"] is True
    assert marker_store.state()["reports"][0]["ever_seen"] == 0
    marker_store.mark_report_seen("form")
    assert marker_store.state()["reports"][0]["needs_answer"] is True
    assert marker_store.state()["reports"][0]["ever_seen"] == 1
    marker_store.submit_report(
      "form",
      "answer",
      {field["id"]: field["options"][0]},
      marker_store.report("form")["updated_at"],
    )
    assert marker_store.state()["reports"][0]["needs_answer"] is False
    try:
      marker_store.publish("form", "Form", marker_source)
      raise AssertionError("An unanswered report accepted a republish")
    except preview.ReportHeld as error:
      assert "unacknowledged answer" in str(error)
    marker_store.publish("form-2", "Form", marker_source)
    assert len(marker_store.state()["reports"]) == 2
    # The agent CLI can revise an unread report with no held answer or active view.
    with preview.ThreadingHTTPServer(
      ("127.0.0.1", 0), preview.handler(marker_store)
    ) as server:
      marker_store.set_meta("port", str(server.server_port))
      thread = threading.Thread(target=server.serve_forever, daemon=True)
      thread.start()
      try:
        allowed = subprocess.run(
          [
            sys.executable,
            str(Path(preview.__file__)),
            "report",
            "publish",
            str(marker_source),
            "--id",
            "form-2",
            "--title",
            "Revised form",
          ],
          capture_output=True,
          text=True,
          check=False,
          env={**os.environ, "ARENA_PREVIEW_STATE_DIR": marker_dir},
        )
        assert allowed.returncode == 0, allowed.stderr
        assert "Published form-2" in allowed.stdout
        result = subprocess.run(
          [
            sys.executable,
            str(Path(preview.__file__)),
            "report",
            "publish",
            str(marker_source),
            "--id",
            "form",
            "--title",
            "Form",
          ],
          capture_output=True,
          text=True,
          check=False,
          env={**os.environ, "ARENA_PREVIEW_STATE_DIR": marker_dir},
        )
        assert result.returncode == 1
        assert "unacknowledged answer" in result.stderr
      finally:
        server.shutdown()
        thread.join()
    assert preview.Store(marker_dir).state()["reports"][0]["needs_answer"] is False
    with marker_store.connect() as db, db:
      db.execute(
        "UPDATE submissions SET at = '2020-01-01T00:00:00' WHERE id = 'answer'"
      )
    assert marker_store.state()["reports"][0]["needs_answer"] is False
    assert preview.Store(marker_dir).state()["reports"][0]["needs_answer"] is False
    marker_store.mark_report_seen("form-2")
    assert marker_store.state()["reports"][1]["seen_at"] is not None
    marker_store.publish("form-2", "Revised form", marker_source)
    assert marker_store.state()["reports"][1]["seen_at"] is None
    assert marker_store.state()["reports"][1]["ever_seen"] == 1
    assert marker_store.state()["reports"][1]["needs_answer"] is True
    marker_source.write_text("Plain report")
    marker_store.publish("plain", "Plain", marker_source)
    assert marker_store.state()["reports"][2]["needs_answer"] is False
    assert "markdown" not in marker_store.state()["reports"][0]


def test_report_ever_seen_migration():
  # An older reports table gains ever_seen. The backfill marks a stamped report opened so a
  # republish after migration still hides the tab dot for it while a fresh report keeps it.
  with tempfile.TemporaryDirectory() as old_report_dir:
    old_db = Path(old_report_dir) / "state.sqlite3"
    with sqlite3.connect(old_db) as db:
      db.execute(
        "CREATE TABLE reports (id TEXT PRIMARY KEY, title TEXT NOT NULL,"
        " markdown TEXT NOT NULL, updated_at TEXT NOT NULL, seq INTEGER, seen_at TEXT)"
      )
      for report_id, seen in (("opened", "2026-09-21T00:00:00+00:00"), ("fresh", None)):
        db.execute(
          "INSERT INTO reports (id, title, markdown, updated_at, seq, seen_at)"
          " VALUES (?, ?, ?, ?, ?, ?)",
          (
            report_id,
            report_id.title(),
            "Text",
            "2026-09-20T00:00:00+00:00",
            1 if seen else 2,
            seen,
          ),
        )
    source = Path(old_report_dir) / "fresh.md"
    source.write_text("Text")
    migrated = preview.Store(old_report_dir)
    state = {row["id"]: row for row in migrated.state()["reports"]}
    assert state["opened"]["ever_seen"] == 1
    assert state["fresh"]["ever_seen"] == 0
    # The ack open stamp arrives with the same migration and starts empty on an old store.
    assert state["opened"]["ack_seen_at"] is None
    assert migrated.mark_report_ack_seen("opened")["ack_seen_at"]
    migrated.mark_report_seen("fresh")
    migrated.publish("fresh", "Fresh", source)
    state = {row["id"]: row for row in migrated.state()["reports"]}
    assert state["fresh"]["seen_at"] is None
    assert state["fresh"]["ever_seen"] == 1


def test_reminder_stamps_the_call_end():
  # The hook runs --reminder after every bash call, so the stamp marks the call's end and
  # the page clears the long call text once a call finished.
  with tempfile.TemporaryDirectory() as end_dir:
    store = preview.Store(end_dir, create=True)
    assert store.state()["agent_call_ended_at"] is None
    hold = socket.socket()
    hold.bind(("127.0.0.1", 0))
    port = hold.getsockname()[1]
    hold.listen(1)
    try:
      store.set_meta("port", str(port))
      result = subprocess.run(
        [sys.executable, str(Path(preview.__file__)), "--reminder"],
        capture_output=True,
        text=True,
        check=False,
        cwd=end_dir,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": end_dir},
      )
      assert result.returncode == 0, result.stderr
      assert not result.stderr.startswith("arena-preview: ")
      ended = store.state()["agent_call_ended_at"]
      assert ended, "the post-call reminder stamps the call end"
      assert preview.import_stamp(ended) is not None
    finally:
      hold.close()


def test_exempted_bash_commands_refresh_timer_without_advancing_tally():
  with tempfile.TemporaryDirectory() as end_dir:
    store = preview.Store(end_dir, create=True)
    store.note("pending-note", "pending note")
    store.set_meta(preview.POLLS_SINCE_MESSAGE, "4")
    store.set_meta(preview.AGENT_CALL_ENDED_META, "2026-10-20T00:00:00+00:00")
    hold = socket.socket()
    hold.bind(("127.0.0.1", 0))
    port = hold.getsockname()[1]
    hold.listen(16)
    try:
      store.set_meta("port", str(port))
      for line in ("arena-preview read", "git status -sb", "gh pr view 119"):
        assert preview.exempted_bash_line(line) is True, line
        store.set_meta(preview.AGENT_CALL_ENDED_META, "2026-10-20T00:00:00+00:00")
        rc = preview.pre_command(end_dir, line, line, end_dir, shell="bash")
        assert rc == 0
        after_pre = store.meta_value(preview.AGENT_CALL_ENDED_META)
        assert after_pre != "2026-10-20T00:00:00+00:00"
        result = subprocess.run(
          [
            sys.executable,
            str(Path(preview.__file__)),
            "--reminder",
            "--line",
            line,
          ],
          capture_output=True,
          text=True,
          check=False,
          cwd=end_dir,
          env={**os.environ, "ARENA_PREVIEW_STATE_DIR": end_dir},
        )
        assert result.returncode == 0, result.stderr
        assert store.calls_since_message() == 4, line
      assert preview.exempted_bash_line("ss -ltn") is False
      assert preview.exempted_bash_line("python3 -c 'print(1)'") is False
    finally:
      hold.close()


def test_write_task_guards_finished_code_and_docs_until_clean_and_pushed():
  with tempfile.TemporaryDirectory() as root_dir:
    root = Path(root_dir)
    remote = root / "remote.git"
    repo = root / "repo"
    subprocess.run(
      ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    subprocess.run(
      ["git", "init", "-b", "main", str(repo)], check=True, capture_output=True
    )
    subprocess.run(
      ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(
      ["git", "commit", "-m", "chore: initial"],
      cwd=repo,
      check=True,
      capture_output=True,
    )
    subprocess.run(
      ["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True
    )
    subprocess.run(
      ["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True
    )

    store = preview.Store(repo / "arena-state", create=True)
    for tid, ttype in (
      ("code-task", "code"),
      ("docs-task", "docs"),
      ("ops-task", "ops"),
      ("report-task", "report"),
    ):
      store.write_task(tid, tid, ["Step one"], task_type=ttype, scope="arena-skill")

    tracked.write_text("dirty\n", encoding="utf-8")
    for guarded_id in ("code-task", "docs-task"):
      with pytest.raises(ValueError, match="FINISH BLOCKED"):
        store.write_task(guarded_id, status="finished")
    assert store.write_task("ops-task", status="finished")["status"] == "finished"
    assert store.write_task("report-task", status="finished")["status"] == "finished"

    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(
      ["git", "commit", "-m", "feat: local change"],
      cwd=repo,
      check=True,
      capture_output=True,
    )
    assert preview.unpushed_commit_count(repo) == 1
    assert (
      "1 commit/s unpushed. ALWAYS push. NEVER delay for batch." in store.reminder()
    )  # nonemo: NMT100
    pre_commit = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "pre",
        "--line",
        "git commit -m 'feat: local'",
        "--command",
        "git commit -m 'feat: local'",
        "--repo",
        str(repo),
      ],
      cwd=repo,
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(repo / "arena-state")},
    )
    assert pre_commit.returncode == 0
    assert "ALWAYS push. NEVER delay for batch." in pre_commit.stderr  # nonemo: NMT100
    for guarded_id in ("code-task", "docs-task"):
      with pytest.raises(ValueError, match="FINISH BLOCKED"):
        store.write_task(guarded_id, status="finished")

    subprocess.run(
      ["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True
    )
    assert preview.unpushed_commit_count(repo) == 0
    assert "commit/s unpushed" not in store.reminder()
    assert store.write_task("code-task", status="finished")["status"] == "finished"
    assert store.write_task("docs-task", status="finished")["status"] == "finished"


def test_require_server_names_the_restart_command():
  """A dead server fails the poll with the exact restart command and its port."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    hold = socket.socket()
    hold.bind(("127.0.0.1", 0))
    port = hold.getsockname()[1]
    hold.close()
    store.set_meta("port", str(port))
    try:
      preview.require_server(store)
    except ValueError as error:
      assert f"arena-preview serve --port {port}" in str(error)
    else:
      raise AssertionError("a dead server passed the poll guard")
    live = socket.socket()
    live.bind(("127.0.0.1", 0))
    live.listen(1)
    try:
      store.set_meta("port", str(live.getsockname()[1]))
      preview.require_server(store)
    finally:
      live.close()
    store.set_meta("port", "")
    try:
      preview.require_server(store)
    except ValueError as error:
      assert "arena-preview serve" in str(error)
    else:
      raise AssertionError("a state with no served port passed the guard")


def test_state_commands_break_while_the_server_is_not_up():
  """A guarded state command exits with the server-not-up message when nothing serves."""
  with tempfile.TemporaryDirectory() as directory:
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": directory}
    init = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "init"],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert init.returncode == 0, init.stderr
    cli = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "task", "list"],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert cli.returncode == 1, cli.stdout
    assert "arena-preview serve" in cli.stderr  # nonemo: NMT100


def test_poll_finishes_before_the_tool_timeout(monkeypatch, capsys):
  tool_timeout = preview.POLL_INTERVAL * preview.POLL_MAX_LOOPS
  assert 0 < preview.POLL_WAIT_SECONDS < tool_timeout
  wait_seconds = 5
  read_delay = 0.75
  with tempfile.TemporaryDirectory() as poll_dir:
    store = preview.Store(poll_dir, create=True)
    clock = [0.0]
    sleeps = []
    original_read = store.read

    def read(*args, **kwargs):
      clock[0] += read_delay
      return original_read(*args, **kwargs)

    def sleep(seconds):
      sleeps.append(seconds)
      clock[0] += seconds

    monkeypatch.setattr(preview, "POLL_WAIT_SECONDS", wait_seconds)
    monkeypatch.setattr(preview.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(preview, "pr_check_watch", lambda *args: None)
    monkeypatch.setattr(store, "read", read)
    with patch.object(store, "mark_turn_ended", wraps=store.mark_turn_ended) as ended:
      assert preview.poll_inbox(store, sleeper=sleep) == 1
    assert ended.called
    output = capsys.readouterr()
    assert str(tool_timeout) in output.err
    assert str(wait_seconds) in output.err
    assert output.out
    assert "POLL AGAIN" not in output.out
    assert wait_seconds <= clock[0] <= wait_seconds + read_delay
    assert sleeps and all(delay > 0 for delay in sleeps)
    assert sum(sleeps) <= clock[0]
    assert store.polling() is False
    assert store.state()["polling_since"] is None


def test_poll_inbox():
  with tempfile.TemporaryDirectory() as poll_dir:
    store = preview.Store(poll_dir, create=True)
    store.set_meta("port", guard_port())
    sleeps = []

    def sleeper(seconds):
      sleeps.append(seconds)

    assert (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS) == (1, 1800)
    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 3
      rc = preview.poll_inbox(store, sleeper=sleeper)
      assert rc == 1
      assert sleeps == [10, 10]
      assert store.state()["notes"] == []

      # The page lights its blue dot on a fresh poll heartbeat, and the poll clears it.
      # The wait start rides the heartbeat, so the page can time the wait.
      heartbeats = []
      waits = []

      def watching_sleeper(seconds):
        heartbeats.append(store.polling())
        waits.append(store.state()["polling_since"])
        sleeps.append(seconds)

      sleeps.clear()
      rc = preview.poll_inbox(store, sleeper=watching_sleeper)
      assert rc == 1
      assert heartbeats == [True, True]
      assert all(wait for wait in waits), waits
      assert store.polling() is False
      assert store.state()["polling"] is False
      assert store.state()["polling_since"] is None

      store.start_poll()
      start = store.state()["polling_since"]
      assert start and start == store.meta_value(preview.POLL_SINCE_META)[:19]
      store.clear_polling()
      assert store.state()["polling_since"] is None

      store.stamp_polling()
      assert store.polling() is True
      assert store.state()["polling"] is True
      stale = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
      store.set_meta(preview.POLLING_META, stale)
      assert store.polling() is False
      store.set_meta(preview.POLLING_META, "not a stamp")
      assert store.polling() is False
      store.clear_polling()
      assert store.polling() is False

      # An unblocked task appearing mid-wait breaks the span and prints the list.
      def tasking_sleeper(seconds):
        sleeps.append(seconds)
        store.write_task(
          "mid-wait",
          "Appears during the wait",
          ["Step one"],
          status="upcoming",
          task_type="misc",
        )

      sleeps.clear()
      rc = preview.poll_inbox(store, sleeper=tasking_sleeper)
      assert rc == 0
      assert sleeps == [10]
      store.write_task("mid-wait", status="finished")

      def arriving_sleeper(seconds):
        sleeps.append(seconds)
        store.note("poll-1", "arrived during wait")

      sleeps.clear()
      rc = preview.poll_inbox(store, sleeper=arriving_sleeper)
      assert rc == 0
      assert sleeps == [10]
      assert store.state()["notes"][0]["seen_at"] is not None
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved
    store.note("poll-2", "already pending")
    result = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "poll"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": poll_dir},
    )
    assert result.returncode == 0
    assert "poll-1" in result.stdout and "poll-2" in result.stdout
    assert preview.REMINDERS[0] in result.stderr
    for flag in ("--interval", "--max"):
      result = subprocess.run(
        [sys.executable, str(Path(preview.__file__)), "poll", flag, "1"],
        capture_output=True,
        text=True,
        check=False,
      )
      assert result.returncode == 2 and "unrecognized arguments" in result.stderr


def test_poll_requires_a_closing_poll_after_a_run_verdict(capsys):
  with tempfile.TemporaryDirectory() as poll_dir:
    store = preview.Store(poll_dir, create=True)
    store.set_meta(preview.POLL_REPEAT_META, preview.poll_clock())
    assert preview.run_command(poll_dir, "check", ["true"]) == 0
    capsys.readouterr()
    assert preview.poll_inbox(store) == 0
    output = capsys.readouterr().out
    assert "run check done: exit 0" in output  # nonemo: NMT100
    assert "DO NOT END TURN. POLL AGAIN." in output
    # The gate verdict breaks the poll, so the closing poll is not spam.
    assert store.meta_value(preview.POLL_REPEAT_META) == "0"


def test_poll_blocked_tasks():
  "An unblocked upcoming task ends a poll at once. A blocked one lets it wait."
  with tempfile.TemporaryDirectory() as poll_dir:
    store = preview.Store(poll_dir, create=True)
    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    printed = []

    def capture(value, **kwargs):
      printed.append(value)

    def run_poll():
      sleeps = []
      original = builtins.print
      builtins.print = capture
      try:
        code = preview.poll_inbox(store, sleeper=sleeps.append)
      finally:
        builtins.print = original
      return code, sleeps

    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 3
      store.write_task("open-task", "Open work", ["Step one"], task_type="misc")
      code, sleeps = run_poll()
      assert code == 0
      assert sleeps == [], "unblocked work ends the wait before the first sleep"
      assert "open-task" in printed[-1]
      # The early return names the task on stdout, so no session reads it as an empty wait.
      assert str(preview.POLL_WAIT_SECONDS) in printed[0]
      # One line, one stream: the agent reads both, so a duplicate only costs tokens.
      assert printed[1] == (
        "CONTINUE: UNBLOCKED TASK open-task. Start a worktree with:"
        " arena-preview worktree start --gate <gate> <name> <destination>."
      )
      assert printed[2] != printed[1]
      assert "open-task" in printed[-1]

      store.write_task("open-task", blocked=True)
      assert store.list_tasks()[0]["blocked"] is True
      printed.clear()
      code, sleeps = run_poll()
      assert code == 1, "a blocked task lets the poll run its loops"
      assert sleeps == [10, 10]
      assert "open-task" not in printed[-1]

      store.write_task("open-task", blocked=False)
      assert store.list_tasks()[0]["blocked"] is False
      code, _ = run_poll()
      assert code == 0, "clearing the mark makes the next poll return at once"
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved


def test_repeat_polls_raise_a_violation(monkeypatch):
  """A poll inside the repeat window raises the quiet violation note the next read shows."""
  with tempfile.TemporaryDirectory() as spam_dir:
    store = preview.Store(spam_dir, create=True)
    moment = [1000]
    monkeypatch.setattr(preview, "poll_clock", lambda: moment[0])
    # Only a poll that returned at once arms the repeat window.
    store.set_meta(preview.POLL_IMMEDIATE_META, "1")
    assert preview.poll_repeat(store) is None
    refusal = preview.poll_repeat(store)
    assert refusal == (
      "VIOLATION: repeat poll inside 45 seconds. Read only paths in the bible whose "
      "current full text is absent from context, then work the task."
    )
    note = store.pending_violation_note()
    assert note["type"] == "self-raised"
    assert note["quiet"] and note["blocking"]
    assert note["text"].startswith("VIOLATION")
    assert "The call-count gate blocks after 6 unacknowledged calls." in note["text"]
    assert store.meta_value(preview.AGENT_INTERRUPT_META) is None
    # A poll that waited for a run does not arm the next one.
    preview.clear_poll_repeat(store)
    store.clear_meta(preview.POLL_IMMEDIATE_META)
    assert preview.poll_repeat(store) is None
    assert preview.poll_repeat(store) is None
    # The served window lets the next poll run.
    moment[0] += 46
    store.set_meta(preview.POLL_IMMEDIATE_META, "1")
    assert preview.poll_repeat(store) is None


def test_a_repeat_poll_command_exits_2_with_the_violation():
  """The CLI refuses the repeated poll and arms the violation."""
  with tempfile.TemporaryDirectory() as spam_dir:
    store = preview.Store(spam_dir, create=True)
    store.set_meta("port", guard_port())
    store.set_meta(preview.POLL_REPEAT_META, int(time.time()))
    store.set_meta(preview.POLL_IMMEDIATE_META, "1")
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": spam_dir}
    result = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "poll"],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert result.returncode == 2, result.stderr
    assert result.stdout == (
      "VIOLATION: repeat poll inside 45 seconds. Read only paths in the bible whose "
      "current full text is absent from context, then work the task.\n"
    )
    note = store.pending_violation_note()
    assert note["type"] == "self-raised"
    assert note["text"].startswith("VIOLATION")
    assert store.meta_value(preview.AGENT_INTERRUPT_META) is None


def test_the_gate_records_the_call_group():
  """The pre hook stores the process group only for sleep calls and clears it for other commands."""
  with tempfile.TemporaryDirectory() as group_dir:
    state = Path(group_dir) / "state"
    preview.Store(state, create=True)
    sleep_result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "pre",
        "--line",
        "sleep 5",
        "--command",
        "sleep 5",
        "--repo",
        group_dir,
      ],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(state)},
    )
    assert sleep_result.returncode == 0, sleep_result.stderr
    stored = preview.Store(state).meta_value(preview.CALL_GROUP_META)
    assert int(stored) == os.getpgid(0)

    other_result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "pre",
        "--line",
        "printf hi",
        "--command",
        "printf hi",
        "--repo",
        group_dir,
      ],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(state)},
    )
    assert other_result.returncode == 0, other_result.stderr
    assert not preview.Store(state).meta_value(preview.CALL_GROUP_META)


def test_a_violation_flag_signals_the_recorded_group():
  """The watcher sends SIGINT to the recorded group and stops once the flag lands."""
  code = (
    "import signal, sys, time\n"
    "signal.signal(signal.SIGINT, lambda *args: sys.exit(42))\n"
    "print('ready', flush=True)\n"
    "time.sleep(60)\n"
  )
  with tempfile.TemporaryDirectory() as watch_dir:
    store = preview.Store(watch_dir, create=True)
    child = subprocess.Popen(
      [sys.executable, "-c", code],
      start_new_session=True,
      stdout=subprocess.PIPE,
    )
    stop = threading.Event()
    watcher = None
    try:
      assert child.stdout.readline() == b"ready\n"
      store.set_meta(preview.CALL_GROUP_META, child.pid)
      started = datetime.now(timezone.utc) - timedelta(seconds=10)
      store.set_meta(preview.CALL_STARTED_META, started.isoformat())
      watcher = threading.Thread(
        target=preview.watch_call_group,
        args=(store,),
        kwargs={"stop": stop, "interval": 0.05},
        daemon=True,
      )
      watcher.start()
      store.request_interrupt("notes", reason="bash-violation")
      assert child.wait(timeout=10) == 42
    finally:
      stop.set()
      if watcher is not None:
        watcher.join(timeout=5)
      if child.poll() is None:
        child.kill()


def test_a_short_or_other_flag_does_not_signal_the_group():
  """The stop needs a bash violation and three seconds, so any other flag waits."""
  code = (
    "import signal, sys, time\n"
    "signal.signal(signal.SIGINT, lambda *args: sys.exit(42))\n"
    "print('ready', flush=True)\n"
    "time.sleep(60)\n"
  )
  for reason, age in (("bash-violation", 1), ("format-violation", 10)):
    with tempfile.TemporaryDirectory() as watch_dir:
      store = preview.Store(watch_dir, create=True)
      child = subprocess.Popen(
        [sys.executable, "-c", code],
        start_new_session=True,
        stdout=subprocess.PIPE,
      )
      stop = threading.Event()
      watcher = None
      try:
        assert child.stdout.readline() == b"ready\n"
        store.set_meta(preview.CALL_GROUP_META, child.pid)
        started = datetime.now(timezone.utc) - timedelta(seconds=age)
        store.set_meta(preview.CALL_STARTED_META, started.isoformat())
        watcher = threading.Thread(
          target=preview.watch_call_group,
          args=(store,),
          kwargs={"stop": stop, "interval": 0.05},
          daemon=True,
        )
        watcher.start()
        tab = "notes" if reason == "bash-violation" else "reports"
        store.request_interrupt(tab, reason=reason)
        time.sleep(0.4)
        assert child.poll() is None, (reason, age)
        assert store.meta_value(preview.CALL_GROUP_META) == str(child.pid)
      finally:
        stop.set()
        if watcher is not None:
          watcher.join(timeout=5)
        if child.poll() is None:
          child.kill()


def test_poll_retry_disclaimer():
  # The poll announces its own span up front: a call that ends early with nothing to
  # read was cut by the bash tool timeout, and the retry needs the tool timeout 1800.
  with tempfile.TemporaryDirectory() as disclaimer_dir:
    store = preview.Store(disclaimer_dir, create=True)
    printed = []
    streams = []

    def capture(value, **kwargs):
      printed.append(value)
      streams.append(kwargs.get("file", sys.stdout))

    original = builtins.print
    builtins.print = capture
    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 1
      code = preview.poll_inbox(store, sleeper=lambda seconds: None)
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved
      builtins.print = original
    assert streams[0] is sys.stderr
    assert code == 1
    assert str(preview.POLL_WAIT_SECONDS) in printed[0]
    assert str(saved[0] * saved[1]) in printed[0]


def test_skip_poll():
  """The page's Skip poll press ends one wait, leaves no note, and never repeats."""
  with tempfile.TemporaryDirectory() as skip_dir:
    store = preview.Store(skip_dir, create=True)
    printed = []
    streams = []

    def capture(value, **kwargs):
      printed.append(value)
      # The stream matters here: on stderr the skip line mixed into the gate's
      # rotating hints, and an agent read it as a hint and polled again.
      streams.append("stderr" if kwargs.get("file") is sys.stderr else "stdout")

    def run_poll():
      sleeps = []
      original = builtins.print
      builtins.print = capture
      try:
        code = preview.poll_inbox(store, sleeper=sleeps.append)
      finally:
        builtins.print = original
      return code, sleeps

    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 3
      assert store.state()["skip_poll"] is None
      assert store.read()["skip_poll"] is None
      assert store.skip_poll_requested() is False
      code, sleeps = run_poll()
      assert code == 1 and sleeps == [10, 10]
      assert (
        "skip_poll" not in printed[-1]
        or "pending" in printed[-1]
        or "Inbox" in printed[-1]
      )

      # A press arms it. A read reports the stamp and leaves it armed for the poll.
      armed = store.request_skip_poll()
      stamp = armed["skip_poll"]
      assert stamp
      assert store.read()["skip_poll"] == stamp
      assert store.state()["skip_poll"] == stamp
      assert store.skip_poll_requested() is True
      assert store.state()["notes"] == [], "the press never writes a note"

      # The poll ends at once, prints the stamp it consumed, and names the skip on
      # stdout with the rest of the poll's own output.
      printed.clear()
      streams.clear()
      code, sleeps = run_poll()
      assert code == 0
      assert sleeps == [], "a skip ends the wait before the first sleep"
      assert str(preview.POLL_WAIT_SECONDS) in printed[0]
      assert printed[1] == (
        "SKIP: owner pressed Skip poll. End the turn, no second poll."
      )
      assert streams[1] == "stdout", "the skip line must not ride stderr with the hints"
      assert (
        stamp in printed[-1] or "skip_poll" in printed[-1] or "Inbox" in printed[-1]
      )
      assert store.skip_poll_requested() is False
      assert store.state()["skip_poll"] is None

      # One press ends one wait: the next poll runs its whole span.
      printed.clear()
      code, sleeps = run_poll()
      assert code == 1 and sleeps == [10, 10]
      assert (
        "skip_poll" not in printed[-1]
        or "pending" in printed[-1]
        or "Inbox" in printed[-1]
      )

      # A second press clears the flag: the agent keeps waiting, and the state says so.
      assert store.request_skip_poll()["skip_poll"]
      assert store.skip_poll_requested() is True
      assert store.request_skip_poll(False) == {"skip_poll": None}
      assert store.skip_poll_requested() is False
      assert store.state()["skip_poll"] is None
      assert store.read()["skip_poll"] is None
      # A disarm with nothing armed stays a no-op, so a stale button never fails a press.
      assert store.request_skip_poll(False) == {"skip_poll": None}

      # A pending message outranks a press: the poll delivers it, and the skip still waits.
      store.note("skip-note", "arrived before the press")
      store.request_skip_poll()
      assert store.skip_poll_requested() is True
      printed.clear()
      code, sleeps = run_poll()
      assert code == 0 and sleeps == []
      assert "skip-n" in printed[-1]
      assert store.skip_poll_requested() is True
      # Once the ack empties the queue, the next poll consumes the skip it held.
      store.acknowledge(["skip-note"], "done")
      printed.clear()
      code, sleeps = run_poll()
      assert code == 0 and sleeps == []
      assert str(preview.POLL_WAIT_SECONDS) in printed[0]
      assert printed[1] == (
        "SKIP: owner pressed Skip poll. End the turn, no second poll."
      )
      assert store.skip_poll_requested() is False
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved


def test_a_live_run_holds_the_skip_poll_press():
  "A detached run with no exit holds the press. The poll waits and the stamp stays."
  with tempfile.TemporaryDirectory() as hold_dir:
    store = preview.Store(hold_dir, create=True)
    printed = []

    def capture(value, **kwargs):
      printed.append(value)

    def run_poll():
      sleeps = []
      original = builtins.print
      builtins.print = capture
      try:
        code = preview.poll_inbox(store, sleeper=sleeps.append)
      finally:
        builtins.print = original
      return code, sleeps

    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 3
      live_detached_placeholder(hold_dir, "pr-checks", ["bash", "-c", "gh pr checks 7"])
      store.request_skip_poll()
      assert preview.live_runs(hold_dir) == ["pr-checks"]
      assert preview.skip_poll_ready(store) is False
      # The press waits armed while the run is live: the poll runs its whole span.
      printed.clear()
      code, sleeps = run_poll()
      assert code == 1 and sleeps == [10, 10]
      assert any("run pr-checks running " in value for value in printed)
      assert store.skip_poll_requested() is True
      # The run's finish outranks the press: the verdict breaks the next wait first.
      preview.run_command(hold_dir, "pr-checks", ["--", "true"])
      printed.clear()
      code, sleeps = run_poll()
      assert code == 0 and sleeps == []
      assert any("run pr-checks done: exit 0" in value for value in printed)
      assert preview.live_runs(hold_dir) == []
      assert store.skip_poll_requested() is True, "the finish leaves the press armed"
      # With nothing live and nothing pending, the held press ends the wait.
      printed.clear()
      code, sleeps = run_poll()
      assert code == 0 and sleeps == []
      assert printed[1] == (
        "SKIP: owner pressed Skip poll. End the turn, no second poll."
      )
      assert store.skip_poll_requested() is False
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved


def test_turn_end_marker():
  "A poll that ends the turn marks it. The next agent call and a live turn clear the mark."
  with tempfile.TemporaryDirectory() as end_dir:
    store = preview.Store(end_dir, create=True)
    printed = []

    def capture(value, **kwargs):
      printed.append(value)

    def run_poll():
      original = builtins.print
      builtins.print = capture
      try:
        return preview.poll_inbox(store, sleeper=lambda seconds: None)
      finally:
        builtins.print = original

    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 3
      store.touch_agent()
      assert store.state()["turn_ended_at"] is None
      # A wait that runs out with nothing to read ends the turn: the marker lands.
      assert run_poll() == 1
      assert store.state()["turn_ended_at"]
      # The agent's own call clears the mark, so a working agent never reads as gone.
      store.touch_agent()
      assert store.state()["turn_ended_at"] is None
      # A skip ends the turn too.
      store.request_skip_poll()
      assert run_poll() == 0
      assert store.state()["turn_ended_at"]
      # A note arriving continues the turn: no mark for the waking agent.
      store.touch_agent()
      store.note("end-note", "work arrived")
      assert run_poll() == 0
      assert store.state()["turn_ended_at"] is None
      # An unblocked task continues the turn as well.
      store.touch_agent()
      store.acknowledge(["end-note"], "done")
      store.write_task("end-task", "Work waits", ["Step one"], task_type="misc")
      assert run_poll() == 0
      assert store.state()["turn_ended_at"] is None
      store.write_task("end-task", status="finished")
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved


def test_skip_poll_clears_on_owner_message():
  "A note or a report answer clears an armed skip. The poll delivers it instead."
  with tempfile.TemporaryDirectory() as clear_dir:
    store = preview.Store(clear_dir, create=True)
    store.request_skip_poll()
    assert store.skip_poll_requested() is True
    # The owner writes after the press, and that item outranks the skip.
    store.note("skip-cleared-note", "sent after a Skip poll press")
    assert store.skip_poll_requested() is False
    assert store.state()["skip_poll"] is None
    assert store.read()["skip_poll"] is None
    # The poll delivers the note instead of ending on the skip line.
    printed = []
    original = builtins.print

    def capture(value, **kwargs):
      printed.append(value)

    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    sleeps = []
    builtins.print = capture
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 3
      code = preview.poll_inbox(store, sleeper=sleeps.append)
    finally:
      builtins.print = original
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved
    assert code == 0 and sleeps == []
    assert not any(str(item).startswith("SKIP") for item in printed)
    assert "skip-c" in printed[-1]
    # A report answer clears it the same way.
    store.request_skip_poll()
    assert store.skip_poll_requested() is True
    store.submission(
      "skip-cleared-answer", "answer", "REPORT answer Answer:\n  verdict: Ship it"
    )
    assert store.skip_poll_requested() is False
    assert store.state()["skip_poll"] is None


def test_newest_stamp_follows_every_mutation():
  """Any committed change moves the state stamp, so a download follows the state."""
  with tempfile.TemporaryDirectory() as stamp_dir:
    store = preview.Store(stamp_dir, create=True)
    assert store.newest_stamp() is None
    store.note("stamp-note", "first")
    note_stamp = store.newest_stamp()
    assert note_stamp
    # A receipt is a change to the state a restore carries, so an ack moves the stamp.
    store.acknowledge(["stamp-note"], "done")
    ack_stamp = store.newest_stamp()
    assert ack_stamp and ack_stamp != note_stamp
    # A task change moves it too.
    store.write_task("stamp-task", "A task", ["Step one"], order=1, task_type="misc")
    assert store.newest_stamp() != ack_stamp


def test_copy_state_carries_the_note_and_task_stamps():
  """The auto save compares the newest note stamp and the newest task stamp, so the route carries both."""
  global app
  with tempfile.TemporaryDirectory() as stamp_dir:
    store = preview.Store(Path(stamp_dir) / "arena-preview", create=True)
    store.note("pair-note", "first", at="2026-10-05T09:00:00")
    store.write_task(
      "pair-task", "A task after the note", ["Step one"], task_type="misc"
    )
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    threading.Thread(target=app.serve_forever, daemon=True).start()
    payload = json.loads(request("GET", "/api/copy-state")[2])
    assert set(payload["stamps"]) == {"note", "task"}
    note_stamp = max(
      stamp
      for stamp in (
        preview.import_stamp(note[name])
        for note in store.state()["notes"]
        for name in ("at", "acknowledged_at", "ack_edited_at", "seen_at")
      )
      if stamp
    )
    assert preview.import_stamp(payload["stamps"]["note"]) == note_stamp
    tasks = store.tasks()
    task_stamp = max(
      preview.import_stamp(task["updated_at"])
      for task in [*tasks["upcoming"], *tasks["finished"]]
    )
    assert preview.import_stamp(payload["stamps"]["task"]) == task_stamp
    assert preview.import_stamp(payload["stamp"]) >= max(note_stamp, task_stamp)


def test_notes_only_save():
  with tempfile.TemporaryDirectory() as notes_only_dir:
    backup = Path(notes_only_dir) / "saved.ndjson"
    notes_only = preview.Store(notes_only_dir, create=True, save_path=backup)
    saved_note = notes_only.note("only-note", "No task yet")
    for task_fields in ({}, {"tasks": None}, {"tasks": {}}):
      result = notes_only.save_state({"notes": [saved_note], **task_fields})
      assert result["notes"] == 1 and result["tasks"] == 0
      assert json.loads(backup.read_text())["id"] == "only-note"
    previous_backup = backup.read_bytes()
    for invalid_tasks in ([], "invalid", False, 0):
      try:
        notes_only.save_state({"notes": [saved_note], "tasks": invalid_tasks})
        raise AssertionError("Invalid task shape accepted")
      except TypeError:
        pass
      assert backup.read_bytes() == previous_backup


def test_workspace_usage():
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "keep.txt").write_bytes(b"abcd")
    skipped = root / "node_modules"
    skipped.mkdir()
    (skipped / "big.bin").write_bytes(b"x" * 20)
    usage = preview.workspace_usage(root)
  assert usage["bytes"] == 4 and usage["files"] == 1
  assert usage["documented_cap_bytes"] == 128_000_000
  assert usage["download_cap_bytes"] is None


def test_owner_limits_and_streams():
  import io

  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    text = "👋" * 150_001
    assert store.note("long-owner", text)["text"] == text
    long_reply = "a" * 15_001
    store.acknowledge(["long-owner"], long_reply)
    assert store.state()["notes"][0]["ack_text"] == long_reply
    url = "https://example.com/" + "a" * 3000
    owner = store.enqueue_fetch(url, False)
    assert owner["origin"] == "owner"
    try:
      store.enqueue_fetch(url, False, pending=True)
      raise AssertionError("Agent URL cap was removed")
    except ValueError:
      pass
    claim = store.claim_fetch()
    with tempfile.TemporaryFile() as stream:
      data = preview.FileBody(stream)
      chunk = b"x" * 65536
      while len(data) <= preview.SNAPSHOT_CAP_BYTES:
        data.write(chunk)
      saved = store.complete_fetch(
        owner["id"], claim["claim"], "x" * 300 + ".txt", "text/plain", "direct", data
      )
      assert saved["size"] == len(data) == Path(saved["path"]).stat().st_size
      agent = store.enqueue_fetch("https://example.com/a", False, pending=True)
      store.decide_fetch(agent["id"], "approved")
      claim = store.claim_fetch()
      saved = store.complete_fetch(
        agent["id"], claim["claim"], "a.txt", "text/plain", "direct", data
      )
      assert saved["size"] == len(data) == Path(saved["path"]).stat().st_size
      digest = hashlib.sha256()
      with Path(saved["path"]).open("rb") as stored:
        for part in iter(lambda: stored.read(len(chunk)), b""):
          digest.update(part)
      assert digest.hexdigest() == data.digest()
    blob = b"a" * 65525 + b"\r\n--boundaryX!" + b"\x00\xff"
    parts = [
      ("id", None, b"streamed"),
      ("text", None, text.encode()),
      ("file", "a" * 300 + ".bin", blob),
    ]
    raw = b""
    for name, filename, data in parts:
      header = f'Content-Disposition: form-data; name="{name}"'
      if filename:
        header += f'; filename="{filename}"'
      raw += b"--boundary\r\n" + header.encode() + b"\r\n\r\n" + data + b"\r\n"
    raw += b"--boundary--\r\n"

    class Chunks(io.BytesIO):
      def read(self, size=-1):
        assert 0 <= size <= 65536
        return super().read(min(size, 113))

    with preview.stream_note_attachments(
      "multipart/form-data; boundary=boundary", Chunks(raw), len(raw)
    ) as parsed:
      body = parsed[2][0][2]
      assert isinstance(body, preview.FileBody)
      record = store.note_with_uploads(*parsed)
      assert record["text"] == text
      assert Path(record["attachments"][0]["path"]).read_bytes() == blob
    assert body.stream.closed
    for data, length in ((raw[:-10], len(raw)), (raw[:-10], len(raw) - 10)):
      try:
        with preview.stream_note_attachments(
          "multipart/form-data; boundary=boundary", Chunks(data), length
        ):
          raise AssertionError("Incomplete multipart accepted")
      except ValueError:
        pass


def test_unified_import_atomicity():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    payload = {
      "notes": [{"id": "restored", "text": "hello"}],
      "tasks": {
        "upcoming": [
          {"id": "task", "title": "Task", "status": "upcoming", "details": ["one"]}
        ],
        "finished": [],
      },
    }
    assert store.import_state(json.dumps(payload)) == {
      "notes": 1,
      "answers": 0,
      "reports": 0,
      "tasks": 1,
    }
    assert not store.save_path.exists(), "Import must not overwrite the source backup"
    receipt_at = "2026-09-20T22:05:11+00:00"
    store.note("already-here", "Existing message")
    store.acknowledge(["already-here"], "Existing answer")
    imported = [
      {
        "id": "already-here",
        "text": "Existing message",
        "acknowledged_at": receipt_at,
        "ack_type": "note",
        "ack_text": "Stale answer",
      },
      {
        "id": "new-answer",
        "report_id": "form",
        "text": "Report answer",
        "acknowledged_at": receipt_at,
        "ack_type": "reply",
        "ack_text": "Received",
      },
    ]
    assert store.import_state(json.dumps(imported))["answers"] == 1
    note = next(n for n in store.state()["notes"] if n["id"] == "already-here")
    assert note["ack_text"] == "Stale answer"
    assert store.submissions()[0]["ack_text"] == "Received"
    backup = store.save_path.read_bytes()
    invalid = [
      {"id": "new-task", "title": "New"},
      {"id": "new-note", "text": "new"},
      {
        "id": "bad",
        "report_id": "form",
        "text": "",
        "acknowledged_at": receipt_at,
        "ack_type": "reply",
        "ack_text": "Invalid answer",
      },
    ]
    try:
      store.import_state(json.dumps(invalid), replace_tasks=True)
      raise AssertionError("Invalid import accepted")
    except ValueError:
      pass
    assert store.list_tasks() == []
    assert {n["id"] for n in store.state()["notes"]} == {"already-here"}
    assert {a["id"] for a in store.submissions()} == {"new-answer"}
    assert (
      store.save_path.read_bytes() if store.save_path.exists() else None
    ) == backup


def test_an_older_snapshot_replaces_the_live_state():
  """Every import overrides, so an old copy replaces newer live messages."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.note("live", "Newest message", at="2026-10-04T15:00:00+00:00")
    older = json.dumps(
      [{"id": "old", "text": "Old message", "at": "2026-10-04T11:42:48"}]
    )
    receipt = store.import_state(older)
    assert receipt == {"notes": 1, "answers": 0, "reports": 0, "tasks": 0}
    assert {note["id"] for note in store.state()["notes"]} == {"old"}


def test_import_state_has_no_force_option():
  """The command no longer exposes a freshness override."""
  with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / "state.json"
    source.write_text(
      json.dumps([{"id": "old", "text": "Old message"}]), encoding="utf-8"
    )
    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "state",
        "import",
        str(source),
        "--force",
      ],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": directory},
    )
    assert result.returncode == 2
    assert "unrecognized arguments: --force" in result.stderr  # nonemo: NMT100


def test_a_newer_snapshot_replaces_the_live_state():
  """A save newer than the live state lands and drops what it leaves out."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.note("live", "Older message", at="2026-10-04T11:42:48")
    newer = json.dumps(
      [{"id": "new", "text": "Newer message", "at": "2026-10-04T15:00:00+00:00"}]
    )
    assert store.import_state(newer)["notes"] == 1
    assert {note["id"] for note in store.state()["notes"]} == {"new"}


def test_import_replaces_the_live_state():
  "An import replaces the live notes, answers, reports and tasks."
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.note("live", "Live message", at="2026-10-04T11:42:48")
    form = Path(directory) / "old-form.md"
    form.write_text("# Old form\n\nOne question.\n", encoding="utf-8")
    store.publish("old-form", "Old form", form)
    store.import_state(
      json.dumps(
        {
          "notes": [],
          "tasks": {
            "upcoming": [
              {
                "id": "old-task",
                "title": "Old",
                "status": "upcoming",
                "details": ["one"],
              }
            ],
            "finished": [],
          },
        }
      )
    )
    snapshot = json.dumps(
      [{"id": "new", "text": "Snapshot message", "at": "2026-10-04T15:00:00+00:00"}]
    )
    store.import_state(snapshot)
    assert {note["id"] for note in store.state()["notes"]} == {"new"}
    assert store.state()["reports"] == []
    assert store.list_tasks() == []
    store.import_state(
      json.dumps(
        [{"id": "later", "text": "Later message", "at": "2026-10-04T16:00:00+00:00"}]
      )
    )
    assert {note["id"] for note in store.state()["notes"]} == {"later"}


def test_agent_key_route_records_the_key_for_the_page():
  """POST /api/key stores the key the userscript holds, and the state carries it."""
  global app
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory) / "arena-preview", create=True)
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    threading.Thread(target=app.serve_forever, daemon=True).start()
    assert json.loads(request("GET", "/api/state")[2])["agent_key"] is None
    key = "K" * 43
    status, _, body = request(
      "POST",
      "/api/key",
      json.dumps({"key": key, "host": "https://arena-proxy.example.ts.net"}),
      {"Content-Type": "application/json"},
    )
    assert status == 200
    record = json.loads(body)
    assert record["key"] == key
    assert record["host"] == "https://arena-proxy.example.ts.net"
    assert record["at"]
    state = json.loads(request("GET", "/api/state")[2])["agent_key"]
    assert state["key"] == key
    assert state["host"] == "https://arena-proxy.example.ts.net"
    status, _, body = request(
      "POST",
      "/api/key",
      json.dumps({"key": key, "host": "https://arena-proxy.example.ts.net/v1"}),
      {"Content-Type": "application/json"},
    )
    assert status == 400
    assert json.loads(request("GET", "/api/state")[2])["agent_key"]["host"] == (
      "https://arena-proxy.example.ts.net"
    )
    # A short candidate changes nothing.
    status, _, body = request(
      "POST",
      "/api/key",
      json.dumps({"key": "too short"}),
      {"Content-Type": "application/json"},
    )
    assert status == 400
    assert json.loads(request("GET", "/api/state")[2])["agent_key"]["key"] == key


def test_quiet_notes_need_no_ack():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    upload = store.save_upload("quiet.txt", "text/plain", b"Information")
    store.note(upload["id"], "Information", quiet=True)
    assert "unacked" not in store.reminder(advance=True)
    assert store.calls_since_message() == 0
    try:
      store.pending_ack()
    except ValueError as error:
      assert "No pending note" in str(error)
    else:
      raise AssertionError("A quiet note requires no acknowledgement")
    pending = store.read()["pending"]
    assert [item["id"] for item in pending] == [upload["id"]]
    assert "quiet (no ack required)" in preview.format_read(store.read())
    store.mark_seen([upload["id"]])
    assert store.read()["pending"] == []
    retained = store.notes_matching(upload["id"])[0]
    assert retained["acknowledged_at"] is None and retained["seen_at"] is not None
    store.note("owner-note", "RE: " + upload["id"] + "\nWork")
    store.mark_seen(["owner-note"])
    pending = store.read()["pending"]
    assert [item["id"] for item in pending] == ["owner-note"]
    assert pending[0]["thread"][0]["id"] == upload["id"]
    assert store.pending_ack() == "owner-note"
    assert "unacked 1 note" in store.reminder(advance=True)
    store.note("quiet-later", "More information", quiet=True)
    assert store.calls_since_message() == 1
    store.acknowledge(["owner-note"], "Done")
    assert store.calls_since_message() == 0
    assert "unacked" not in store.reminder()
    assert store.gate(pending_only=True)
    store.submission("owner-answer", "form", "Decision")
    assert store.pending_ack() == "owner-answer"
    assert "unacked 1 answer" in store.reminder(advance=True)
    store.acknowledge(["owner-answer"], "Done")
    assert store.calls_since_message() == 0


def test_quiet_note_never_wakes_the_poll():
  """A quiet note is readable and unacknowledged, yet it wakes nothing and stops nothing."""
  with tempfile.TemporaryDirectory() as quiet_dir:
    store = preview.Store(quiet_dir, create=True)
    store.note("key-note", "Arena proxy key rotated. New key: K", quiet=True)
    # A read still shows it, so the agent finds the new key when it looks.
    assert [item["id"] for item in store.read()["pending"]] == ["key-note"]
    # The poll passes over it and runs its whole span.
    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    sleeps = []
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 3
      rc = preview.poll_inbox(store, sleeper=lambda seconds: sleeps.append(seconds))
      assert rc == 1
      assert sleeps == [10, 10]
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved
    # A checkpoint lets a command through: a quiet note is not owner work.
    assert store.gate(pending_only=True) is True

    # An owner note still wakes the poll, and the quiet note rides that read.
    def arriving_sleeper(seconds):
      store.note("owner-note", "Owner work")

    rc = preview.poll_inbox(store, sleeper=arriving_sleeper)
    assert rc == 0
    seen = {note["id"]: note["seen_at"] for note in store.state()["notes"]}
    assert seen["owner-note"] is not None and seen["key-note"] is not None


def test_read_set_slots_follow_quarter_hours():
  for zone in (timezone.utc, timezone(timedelta(hours=8))):
    started = datetime(2026, 10, 19, 10, tzinfo=zone)
    for minute in (0, 15, 30, 45, 60):
      boundary = started + timedelta(minutes=minute)
      assert preview.read_set_slot(boundary) == boundary.isoformat()
      within = boundary + CHECKPOINT_INTERVAL - timedelta(microseconds=1)
      assert preview.read_set_slot(within) == boundary.isoformat()


def test_read_set_schedule_delays_first_checkpoint_and_keeps_intervals():
  with tempfile.TemporaryDirectory() as directory:
    root, state = read_set_cli_root(directory)
    store = preview.Store(state)
    started = datetime(2026, 10, 19, 10, 7, 13, tzinfo=timezone.utc)

    assert store.schedule_read_set_note(moment=started, root=root) is None
    assert store.pending_read_set_note() is None
    assert (
      store.schedule_read_set_note(
        moment=started + CHECKPOINT_INTERVAL - timedelta(seconds=1), root=root
      )
      is None
    )
    first = store.schedule_read_set_note(
      moment=started + CHECKPOINT_INTERVAL, root=root
    )
    assert first is not None
    store.acknowledge([first["id"]], "Read in full")
    assert (
      store.schedule_read_set_note(
        moment=started + CHECKPOINT_INTERVAL * 2 - timedelta(seconds=1), root=root
      )
      is None
    )
    second = store.schedule_read_set_note(
      moment=started + CHECKPOINT_INTERVAL * 2, root=root
    )
    assert second is not None and second["id"] != first["id"]


def test_scheduled_read_set_note_is_blocking_for_agent_and_quiet_for_poll(
  capsys, monkeypatch
):
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "ARENA.md").write_text("arena\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("root agents\n", encoding="utf-8")
    nested = root / "src" / "AGENTS.md"
    nested.parent.mkdir()
    nested.write_text("nested agents\n", encoding="utf-8")
    excluded = root / "node_modules" / "AGENTS.md"
    excluded.parent.mkdir()
    excluded.write_text("excluded agents\n", encoding="utf-8")
    skill = root / ".agents" / "skills" / "arena-skill" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("skill\n", encoding="utf-8")
    store = preview.Store(root / "state", create=True)
    started = datetime(2026, 10, 19, 10, 0, 4, tzinfo=timezone.utc)
    assert preview.read_set_tick(store, "git status", moment=started, root=root) is None
    at_zero = started + CHECKPOINT_INTERVAL

    assert preview.read_set_tick(store, "git status", moment=at_zero, root=root) is None
    pending = store.read()["pending"]
    assert len(pending) == 1
    checkpoint = pending[0]
    assert checkpoint["text"].startswith(
      "Bible checkpoint after a 15-minute interval. Read each listed path in full "
      "with the read tool only if its current full text is absent from context, then "
      "acknowledge this note.\n"
    )
    assert checkpoint["quiet"] == 1 and checkpoint["blocking"] == 1
    assert [str(path) for path in preview.read_set_paths(root)] == [
      str(root / "ARENA.md"),
      str(root / "AGENTS.md"),
      str(nested),
      str(skill),
    ]
    assert all(str(path) in checkpoint["text"] for path in preview.read_set_paths(root))
    assert "quiet (no ack required)" not in preview.format_read(store.read())
    assert store.pending_ack() == checkpoint["id"]
    assert store.reminder().startswith("unacked 1 note | ")
    store.set_meta(preview.POLLS_SINCE_MESSAGE, str(preview.GATE_THRESHOLD))
    assert not store.gate()
    assert (
      preview.read_set_tick(
        store, "arena-preview read && git status", moment=at_zero, root=root
      )
      is None
    )
    assert (
      preview.read_set_tick(
        store, "arena-preview poll && git status", moment=at_zero, root=root
      )
      is None
    )
    assert (
      preview.read_set_tick(
        store, f"cd {root} && arena-preview read", moment=at_zero, root=root
      )
      is None
    )
    assert (
      preview.read_set_tick(
        store,
        f"{sys.executable} {preview.__file__} read",
        moment=at_zero,
        root=root,
      )
      is None
    )
    store.mark_seen([checkpoint["id"]])
    assert [item["id"] for item in store.read()["pending"]] == [checkpoint["id"]]
    assert (
      preview.read_set_tick(store, "arena-preview read", moment=at_zero, root=root)
      is None
    )
    assert (
      preview.read_set_tick(
        store,
        f"arena-preview ack {checkpoint['id']} done",
        moment=at_zero,
        root=root,
      )
      is None
    )

    monkeypatch.setattr(preview, "pr_check_watch", lambda *args: None)
    monkeypatch.setattr(preview, "run_notices", lambda *args, **kwargs: False)
    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    sleeps = []
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 2
      assert (
        preview.poll_inbox(store, sleeper=lambda seconds: sleeps.append(seconds)) == 1
      )
      assert sleeps == [10]
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved
    assert checkpoint["id"] in [item["id"] for item in store.read()["pending"]]
    assert checkpoint["id"] not in {
      row["id"]
      for row in store.state_lines(store.state()["notes"], store.tasks() or {})[0]
    }
    capsys.readouterr()

    store.acknowledge([checkpoint["id"]], "Read in full")
    assert preview.read_set_tick(store, "git status", moment=at_zero, root=root) is None
    assert store.read()["pending"] == []
    at_next = at_zero + CHECKPOINT_INTERVAL
    assert (
      preview.read_set_tick(store, "arena-preview read", moment=at_next, root=root)
      is None
    )
    next_pending = store.read()["pending"]
    assert len(next_pending) == 1 and next_pending[0]["id"] != checkpoint["id"]
    at_later = at_zero + CHECKPOINT_INTERVAL * 2
    assert (
      preview.read_set_tick(store, "git status", moment=at_later, root=root) is None
    )
    assert len(store.read()["pending"]) == 1, "one pending checkpoint never duplicates"


def test_read_set_schedule_defers_for_polling_and_migrates_note_classes():
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for path in (
      root / "ARENA.md",
      root / "AGENTS.md",
      root / ".agents" / "skills" / "arena-skill" / "SKILL.md",
    ):
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(path.name + "\n", encoding="utf-8")
    store = preview.Store(root / "state", create=True)
    ordinary = store.note("ordinary", "Owner work")
    quiet = store.note("quiet", "Key rotated", quiet=True)
    assert ordinary["blocking"] == 1 and quiet["blocking"] == 0
    at_later = datetime(2026, 10, 19, 10, 47, tzinfo=timezone.utc)
    assert preview.read_set_slot(at_later).endswith("10:45:00+00:00")
    assert (
      preview.read_set_tick(
        store, "timeout 1 arena-preview poll", moment=at_later, root=root
      )
      is None
    )
    assert (
      preview.read_set_tick(store, "arena-preview poll", moment=at_later, root=root)
      is None
    )
    assert {item["id"] for item in store.read()["pending"]} == {
      ordinary["id"],
      quiet["id"],
    }
    store.start_poll()
    assert store.schedule_read_set_note(moment=at_later, root=root) is None
    assert (
      preview.read_set_tick(store, "git status", moment=at_later, root=root) is None
    )
    assert not any(
      item["blocking"] and item["quiet"] for item in store.read()["pending"]
    )
    store.clear_polling()
    assert (
      preview.read_set_tick(store, "git status", moment=at_later, root=root) is None
    )
    due = at_later + CHECKPOINT_INTERVAL
    assert preview.read_set_tick(store, "git status", moment=due, root=root) is None

    database = sqlite3.connect(store.path)
    database.execute("ALTER TABLE notes DROP COLUMN blocking")
    database.commit()
    database.close()
    migrated = preview.Store(root / "state")
    rows = {
      row["id"]: row
      for row in migrated.notes_matching(ordinary["id"])
      + migrated.notes_matching(quiet["id"])
    }
    assert rows[ordinary["id"]]["blocking"] == 1
    assert rows[quiet["id"]]["blocking"] == 0


def read_set_cli_root(directory):
  """Build a bible root and its empty state directory."""
  root = Path(directory)
  for path in (
    root / "ARENA.md",
    root / "AGENTS.md",
    root / ".agents" / "skills" / "arena-skill" / "SKILL.md",
  ):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(path.name + "\n", encoding="utf-8")
  state = root / "state"
  preview.Store(state, create=True)
  return root, state


def read_set_cli(state, root, line):
  """Run one bible tick under its own state, as the installed gate does."""
  return subprocess.run(
    [
      sys.executable,
      str(Path(preview.__file__)),
      "pre",
      "--line",
      line,
      "--command",
      line,
      "--repo",
      str(root),
    ],
    capture_output=True,
    text=True,
    check=False,
    env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(state)},
  )


def dead_port(store):
  """Record a port that refuses a probe: bound, then released."""
  dead = socket.socket()
  dead.bind(("127.0.0.1", 0))
  port = dead.getsockname()[1]
  dead.close()
  store.set_meta("port", str(port))
  return port


def test_read_set_tick_cli_does_not_start_the_delay_while_server_is_down():
  with tempfile.TemporaryDirectory() as directory:
    root, state = read_set_cli_root(directory)
    dead_port(preview.Store(state))
    result = read_set_cli(state, root, "git status")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    after = preview.Store(state)
    assert after.read()["pending"] == []
    assert after.meta_value(preview.READ_SET_SLOT_META) is None


def test_read_set_tick_cli_keeps_a_pending_checkpoint_while_the_server_is_down():
  with tempfile.TemporaryDirectory() as directory:
    root, state = read_set_cli_root(directory)
    store = preview.Store(state)
    started = datetime(2026, 10, 19, 10, 0, 4, tzinfo=timezone.utc)
    assert store.schedule_read_set_note(moment=started, root=root) is None
    moment = started + CHECKPOINT_INTERVAL
    checkpoint = store.schedule_read_set_note(moment=moment, root=root)
    slot = store.meta_value(preview.READ_SET_SLOT_META)
    dead_port(store)
    result = read_set_cli(state, root, "git status")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    after = preview.Store(state)
    assert after.pending_read_set_note()["id"] == checkpoint["id"]
    assert after.meta_value(preview.READ_SET_SLOT_META) == slot


def test_read_set_tick_cli_mints_a_note_with_the_server():
  with tempfile.TemporaryDirectory() as directory:
    root, state = read_set_cli_root(directory)
    store = preview.Store(state)
    store.set_meta("port", guard_port())
    store.set_meta(
      preview.READ_SET_LAST_META,
      (datetime.now(timezone.utc) - timedelta(minutes=21)).isoformat(),
    )
    minted = read_set_cli(state, root, "git status")
    assert minted.returncode == 0, minted.stderr
    assert minted.stderr == ""
    for line in ("arena-preview read", "arena-preview ack", "arena-preview poll"):
      allowed = read_set_cli(state, root, line)
      assert allowed.returncode == 0, (line, allowed.stderr)
    assert len(preview.Store(state).read()["pending"]) == 1


def test_read_set_tick_cli_acknowledgement_holds_the_slot():
  with tempfile.TemporaryDirectory() as directory:
    root, state = read_set_cli_root(directory)
    store = preview.Store(state)
    store.set_meta("port", guard_port())
    store.set_meta(
      preview.READ_SET_LAST_META,
      (datetime.now(timezone.utc) - timedelta(minutes=21)).isoformat(),
    )
    minted = read_set_cli(state, root, "git status")
    assert minted.returncode == 0, minted.stderr
    store = preview.Store(state)
    checkpoint_id = store.pending_read_set_note()["id"]
    ack = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "ack",
        checkpoint_id,
        "Read in full",
      ],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(state)},
    )
    assert ack.returncode == 0, ack.stderr
    after = preview.Store(state)
    assert after.notes_matching(checkpoint_id)[0]["acknowledged_at"]
    assert after.pending_read_set_note() is None
    assert after.read()["pending"] == []
    repeated = read_set_cli(state, root, "git status")
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stderr == ""
    assert len(after.notes_matching(checkpoint_id)) == 1
    assert after.read()["pending"] == []


def test_quiet_note_route():
  """POST /api/notes takes the quiet flag from the userscript."""
  global app
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory) / "arena-preview", create=True)
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    threading.Thread(target=app.serve_forever, daemon=True).start()
    status, _, body = request(
      "POST",
      "/api/notes",
      json.dumps({"id": "key-note", "text": "key rotated", "quiet": True}),
      {"Content-Type": "application/json"},
    )
    assert status == 201
    assert json.loads(body)["quiet"] == 1
    assert [note["id"] for note in store.read()["pending"]] == ["key-note"]
    assert store.gate(pending_only=True) is True
    # The page still shows it.
    assert [note["id"] for note in store.state()["notes"]] == ["key-note"]


def test_skip_poll_route():
  "POST /api/skip-poll arms the page's skip. The state and the poll report it."
  global app
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory) / "arena-preview", create=True)
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    threading.Thread(target=app.serve_forever, daemon=True).start()
    assert json.loads(request("GET", "/api/state")[2])["skip_poll"] is None
    # The route needs the JSON content type every write carries.
    assert request("POST", "/api/skip-poll", "{}")[0] == 415
    status, _, body = request(
      "POST", "/api/skip-poll", "{}", {"Content-Type": "application/json"}
    )
    assert status == 200
    stamp = json.loads(body)["skip_poll"]
    assert stamp
    assert json.loads(request("GET", "/api/state")[2])["skip_poll"] == stamp
    assert store.state()["notes"] == [], "the route writes no note"
    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 3
      sleeps = []
      rc = preview.poll_inbox(store, sleeper=lambda seconds: sleeps.append(seconds))
      assert rc == 0 and sleeps == []
      # The poll consumed the press, so the page paints its button unarmed again.
      assert json.loads(request("GET", "/api/state")[2])["skip_poll"] is None
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved

    # A second press carries skip false: the flag clears and the state tells the page.
    status, _, body = request(
      "POST", "/api/skip-poll", '{"skip": true}', {"Content-Type": "application/json"}
    )
    assert status == 200 and json.loads(body)["skip_poll"]
    status, _, body = request(
      "POST", "/api/skip-poll", '{"skip": false}', {"Content-Type": "application/json"}
    )
    assert status == 200
    assert json.loads(body)["skip_poll"] is None
    assert json.loads(request("GET", "/api/state")[2])["skip_poll"] is None
    # A value that is not a boolean names the field instead of arming the flag.
    status, _, body = request(
      "POST", "/api/skip-poll", '{"skip": "no"}', {"Content-Type": "application/json"}
    )
    assert status == 400 and "skip must be true or false" in body
    assert store.skip_poll_requested() is False


def test_push_gate_identical_to_main():
  """The push gate refuses a branch whose content already matches origin/main."""
  with tempfile.TemporaryDirectory() as repo:

    def git(*arguments):
      return subprocess.run(
        ["git", *arguments], cwd=repo, capture_output=True, text=True, check=False
      )

    git("init", "-q", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (Path(repo) / "file.txt").write_text("one\n", encoding="utf-8")
    git("add", "file.txt")
    git("commit", "-q", "-m", "first")
    assert preview.main_identical(repo) is False, "no origin/main means no verdict"
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    assert preview.main_identical(repo) is True
    (Path(repo) / "file.txt").write_text("two\n", encoding="utf-8")
    git("add", "file.txt")
    git("commit", "-q", "-m", "second")
    assert preview.main_identical(repo) is False
    git("reset", "--hard", "--quiet", "HEAD~1")
    blocked = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "gate", "--push"],
      cwd=repo,
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(Path(repo) / "arena-state")},
    )
    assert blocked.returncode == 1
    assert blocked.stdout.strip() == (
      "HEAD equals `origin/main`, so the push carries nothing."
      " Start new work from `origin/main`."
    )


def test_push_gate_refuses_a_branch_that_lacks_origin_main():
  """The push gate refuses a branch that does not hold the commits origin/main carries."""
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    remote, work, other = root / "remote.git", root / "work", root / "other"

    def git(*arguments, cwd=root):
      return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=False
      )

    def gate():
      return subprocess.run(
        [sys.executable, str(Path(preview.__file__)), "gate", "--push"],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(root / "arena-state")},
      )

    git("init", "-q", "-b", "main", str(work))
    git("config", "user.email", "test@example.com", cwd=work)
    git("config", "user.name", "Test", cwd=work)
    (work / "file.txt").write_text("one\n", encoding="utf-8")
    git("add", "file.txt", cwd=work)
    git("commit", "-q", "-m", "first", cwd=work)
    git("init", "-q", "--bare", "-b", "main", str(remote))
    git("remote", "add", "origin", str(remote), cwd=work)
    git("push", "-q", "origin", "main", cwd=work)
    git("switch", "-q", "-c", "topic", cwd=work)
    (work / "file.txt").write_text("topic\n", encoding="utf-8")
    git("commit", "-q", "-am", "topic work", cwd=work)
    # The branch holds the whole of origin/main, so the checkpoint passes the push.
    assert gate().returncode == 0
    # A second clone lands a commit on main that this branch lacks.
    git("clone", "-q", str(remote), str(other))
    git("config", "user.email", "test@example.com", cwd=other)
    git("config", "user.name", "Test", cwd=other)
    (other / "main.txt").write_text("main\n", encoding="utf-8")
    git("add", "main.txt", cwd=other)
    git("commit", "-q", "-m", "main moves", cwd=other)
    git("push", "-q", "origin", "main", cwd=other)
    before = git("status", "--porcelain", cwd=work).stdout
    blocked = gate()
    assert blocked.returncode == 1
    assert "origin/main" in blocked.stdout and "rebase" in blocked.stdout
    # The check reads and fetches only: HEAD, the index and the work tree stay put.
    assert git("status", "--porcelain", cwd=work).stdout == before
    assert (
      git("rev-parse", "HEAD", cwd=work).stdout.strip()
      == git("rev-parse", "topic", cwd=work).stdout.strip()
    )
    # A replay onto the fresh tip holds the ancestry, so the checkpoint opens again.
    git("fetch", "-q", "origin", cwd=work)
    git("rebase", "-q", "origin/main", cwd=work)
    assert gate().returncode == 0
    # No origin remote means no verdict, so the checkpoint stays open.
    git("remote", "remove", "origin", cwd=work)
    assert gate().returncode == 0


def test_key_command_reads_the_recorded_key():
  """A later session reads the key from the state, because an acked note never returns."""
  with tempfile.TemporaryDirectory() as key_dir:
    store = preview.Store(key_dir, create=True)
    store.set_meta("port", guard_port())
    script = str(Path(preview.__file__))

    def run():
      return subprocess.run(
        [sys.executable, script, "key"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": key_dir},
      )

    missing = run()
    assert missing.returncode == 1
    assert missing.stdout == ""
    store.set_agent_key("fresh-key-0123456789abcdef", "https://h.example")
    found = run()
    assert found.returncode == 0
    lines = found.stdout.splitlines()
    assert "key fresh-key-0123456789abcdef" in lines
    assert "host https://h.example" in lines
    # The command needs no server, so a restore reads it before the preview starts.
    store.set_meta(preview.AGENT_KEY_META, "not json")
    assert run().returncode == 1


def test_expired_agent_key_tells_the_agent_once():
  "An old key record posts one quiet note. A fresh record stays silent and a read prints it."
  with tempfile.TemporaryDirectory() as state_dir:
    script = str(Path(preview.__file__))
    store = preview.Store(state_dir, create=True)
    store.set_meta("port", guard_port())
    assert store.notice_expired_key() is None, "no key record says nothing"
    store.set_meta(
      preview.AGENT_KEY_META,
      json.dumps(
        {
          "key": "old-key-0123456789abcdef",
          "host": "https://h.example",
          "at": "2020-01-01T00:00:00+00:00",
        }
      ),
    )
    first = store.notice_expired_key()
    assert first is not None and first["quiet"] == 1
    assert [item["text"] for item in store.read()["pending"]] == [
      (
        "The recorded agent key expired (set 2020-01-01T00:00:00). Run `arena-preview key`"
        " for the live key; a new post overwrites this record by itself."
      )
    ]
    assert store.notice_expired_key() is None, "one note per record"
    assert len(store.read()["pending"]) == 1
    # A read prints the notice and a poll never wakes on it.
    assert store.read(include_quiet=False)["pending"] == []
    seen = subprocess.run(
      [sys.executable, script, "read"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": state_dir},
    )
    assert seen.returncode == 0 and "expired" in seen.stdout
    # A fresh record is silent, and its own stamp lets a later expiry speak again.
    store.set_agent_key("new-key-0123456789abcdef", "https://h.example")
    assert store.notice_expired_key() is None
    assert store.read()["pending"] == []
    retained = store.notes_matching(first["id"])[0]
    assert retained["quiet"] == 1 and retained["seen_at"] is not None
    assert retained["acknowledged_at"] is None


def test_agent_seen_at_is_stamped_by_the_cli():
  """Every agent CLI call stamps the liveness the preview header reads."""
  with tempfile.TemporaryDirectory() as state_dir:
    script = str(Path(preview.__file__))
    store = preview.Store(state_dir, create=True)
    store.set_meta("port", guard_port())
    store.set_agent_key("stamp-check-0123456789abcdef", "https://h.example")
    result = subprocess.run(
      [sys.executable, script, "key"],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": state_dir},
    )
    assert result.returncode == 0
    store = preview.Store(state_dir)
    stamp = store.state()["agent_seen_at"]
    assert isinstance(stamp, str) and stamp.count(":") == 2
    # A state that never saw an agent says so, so the header accuses nobody.
    assert preview.Store(state_dir).meta_value(preview.AGENT_SEEN_META)
    empty = preview.Store(str(Path(state_dir) / "unseen"), create=True)
    assert empty.touch_agent() is None
    assert empty.state()["agent_seen_at"]


def test_report_sources_ride_in_the_saved_state():
  """A save file carries each report's markdown, so a restore rebuilds the report page."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "select.md"
    source.write_text(
      "# Select\n\nChoice? {#select}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("select", "Select one", source)
    with patch.object(preview, "now", return_value="2026-10-13T03:12:00+00:00"):
      store.mark_report_seen("select")
    with patch.object(preview, "now", return_value="2026-10-13T03:13:00+00:00"):
      store.mark_report_ack_seen("select")
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET agent_seen_at = ?, viewed_at = ? WHERE id = ?",
        ("2026-10-13T03:14:00+00:00", "2026-10-13T03:15:00+00:00", "select"),
      )
    store.save_state({"notes": store.state()["notes"], "tasks": store.tasks()})
    lines = [json.loads(line) for line in store.save_path.read_text().splitlines()]
    saved = next(line for line in lines if line.get("id") == "select")
    assert saved["title"] == "Select one"
    assert "Choice? {#select}" in saved["markdown"]
    assert saved["published_at"]
    assert saved["seen_at"] == "2026-10-13T03:12:00+00:00"
    ack_seen_at = "2026-10-13T03:13:00+00:00"
    assert saved["ack_seen_at"] == ack_seen_at
    assert all(key not in saved for key in ("ever_seen", "agent_seen_at", "viewed_at"))

    restored_dir = Path(directory) / "restored"
    restored_dir.mkdir()
    restored = preview.Store(restored_dir, create=True)
    result = restored.import_state(store.save_path.read_text())
    assert result["reports"] == 1
    report = restored.report("select")
    assert report["title"] == "Select one"
    assert "Choice? {#select}" in report["markdown"]
    assert report["published_at"]
    assert report["seen_at"] == "2026-10-13T03:12:00+00:00"
    assert report["ever_seen"] == 1
    assert report["ack_seen_at"] == ack_seen_at
    assert report["agent_seen_at"] is None and report["viewed_at"] is None


def test_import_reports_recreates_sources_in_active_state(tmp_path):
  state = tmp_path / "restored"
  store = preview.Store(state, create=True)
  outside = tmp_path / "do-not-write.md"
  markdown = "  # Saved\r\n\r\nExact source text.\r\n"
  store.import_reports(
    [
      {
        "id": "source-copy",
        "title": "Saved",
        "markdown": markdown,
        "source": str(outside),
      }
    ]
  )
  source = Path(store.report("source-copy")["source"])
  assert source.resolve().is_relative_to(state.resolve())
  assert source.read_bytes() == markdown.encode("utf-8")
  assert not outside.exists()


def test_import_reports_without_a_source_keeps_existing_files(tmp_path):
  store = preview.Store(tmp_path, create=True)
  existing = tmp_path / "reports" / "source-copy.md"
  existing.parent.mkdir()
  existing.write_text("Keep this file.\n", encoding="utf-8")
  markdown = "# Restored\n\nSaved source.\n"
  store.import_reports([{"id": "source-copy", "title": "Saved", "markdown": markdown}])
  source = Path(store.report("source-copy")["source"])
  assert source.is_relative_to(tmp_path)
  assert source != existing
  assert source.read_text(encoding="utf-8") == markdown
  assert existing.read_text(encoding="utf-8") == "Keep this file.\n"


def test_failed_import_creates_no_report_source_files(tmp_path):
  store = preview.Store(tmp_path, create=True)
  before = set(tmp_path.rglob("*.md"))
  records = [
    {"id": "saved-report", "title": "Saved", "markdown": "# Saved\n"},
    {"id": "invalid-note", "unexpected": True},
  ]
  with pytest.raises(ValueError):
    store.import_state("\n".join(json.dumps(record) for record in records))
  assert set(tmp_path.rglob("*.md")) == before
  with pytest.raises(FileNotFoundError):
    store.report("saved-report")


def test_invalid_report_batch_creates_no_source_files(tmp_path):
  store = preview.Store(tmp_path, create=True)
  before = set(tmp_path.rglob("*.md"))
  with pytest.raises(ValueError):
    store.import_reports(
      [
        {"id": "valid-report", "title": "Saved", "markdown": "# Saved\n"},
        {"id": "invalid-report", "title": "Invalid", "markdown": " "},
      ]
    )
  assert set(tmp_path.rglob("*.md")) == before
  with pytest.raises(FileNotFoundError):
    store.report("valid-report")


def test_import_reports_does_not_follow_saved_source_symlinks(tmp_path):
  state = tmp_path / "restored"
  store = preview.Store(state, create=True)
  outside = tmp_path / "outside"
  outside.mkdir()
  original = outside / "existing.md"
  original.write_text("Keep this file.\n", encoding="utf-8")
  link = state / "old-sources"
  try:
    link.symlink_to(outside, target_is_directory=True)
  except OSError:
    pytest.skip("Directory symlinks are unavailable")
  store.import_reports(
    [
      {
        "id": "safe-source",
        "title": "Saved",
        "markdown": "# Saved\n",
        "source": str(link / "existing.md"),
      }
    ]
  )
  source = Path(store.report("safe-source")["source"])
  assert source.resolve().is_relative_to(state.resolve())
  assert source.read_text(encoding="utf-8") == "# Saved\n"
  assert original.read_text(encoding="utf-8") == "Keep this file.\n"


def test_removed_report_leaves_nothing_in_the_save():
  "A removed report leaves no report or answer lines in a state save. The database keeps the answer as inbox history."
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "select.md"
    source.write_text(
      "# Select\n\nChoice? {#select}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("select", "Select one", source)
    store.submission("answer-1", "select", "REPORT select: one")
    before = [json.loads(line) for line in store.save_path.read_text().splitlines()]
    assert [line["id"] for line in before if line.get("report_id")] == ["answer-1"]
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "select")
      )
    store.unpublish("select", dismissed_by_owner=True)
    lines = [json.loads(line) for line in store.save_path.read_text().splitlines()]
    assert [line["id"] for line in lines if line.get("report_id")] == []
    assert all(line.get("id") != "select" for line in lines)
    assert store.submissions()[0]["report_id"] == "select", "sent answers stay history"


def test_unpublish_moves_the_state_stamp():
  """An unpublish moves the state stamp, so the save's own trigger rewrites the file.

  The write trigger is the stamp comparison alone, so a
  removal that left the stamp still would leave a file that already carries the removed
  report untouched. The report rows are gone, so the removal has to carry the stamp.
  """
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "select.md"
    source.write_text(
      "# Select\n\nChoice? {#select}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("select", "Select one", source)
    before = store.newest_stamp()
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "select")
      )
    store.unpublish("select")
    after = store.newest_stamp()
    assert after and after > before, "the removal left the state stamp still"


def test_report_changes_hold_unseen_answers_and_acknowledgements():
  """Agent changes wait for an unacknowledged answer or acknowledgement."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "select.md"
    source.write_text(
      "# Select\n\nChoice? {#select}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("select", "Select one", source)
    source.write_text(
      "# Revised\n\nChoice? {#select}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.submission("answer-1", "select", "REPORT select: one")
    for change in (
      lambda: store.publish("select", "Select revised", source),
      lambda: store.unpublish("select"),
    ):
      try:
        change()
        raise AssertionError("An unseen answer allowed an agent report change")
      except preview.ReportHeld as error:
        assert "unacknowledged answer" in str(error)
    store.acknowledge(["answer-1"], "Received")
    for change in (
      lambda: store.publish("select", "Select revised", source),
      lambda: store.unpublish("select"),
    ):
      try:
        change()
        raise AssertionError("An unseen acknowledgement allowed an agent report change")
      except preview.ReportHeld as error:
        assert "acknowledgement" in str(error)
    store.mark_report_ack_seen("select")
    try:
      store.publish("select", "Select revised", source)
      raise AssertionError("An answered report allowed a republish")
    except preview.ReportHeld as error:
      assert "submitted answer" in str(error)
    store.unpublish("select")
    assert store.state()["reports"] == []


def test_report_changes_hold_a_fresh_view_of_an_answered_report():
  """Agent changes wait while the owner has a fresh view of a report with an answer."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "select.md"
    source.write_text("# Select\n", encoding="utf-8")
    store.publish("select", "Select", source)
    store.submission("answer-1", "select", "REPORT select: one")
    store.acknowledge(["answer-1"], "Received")
    store.mark_report_ack_seen("select")
    store.mark_report_viewed("select")
    with patch.object(preview, "seconds_since", return_value=0):
      try:
        store.publish("select", "Select revised", source)
        raise AssertionError("A fresh view allowed a republish")
      except preview.ReportHeld as error:
        assert "reading" in str(error)
      # The page holds the open report, so the same fresh view never blocks an unpublish.
      store.unpublish("select")
    assert store.state()["reports"] == []


def test_agent_unpublish_passes_the_view_hold():
  """An unpublished report leaves at once while the owner reads, and the answer holds stand."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "select.md"
    source.write_text("# Select\n", encoding="utf-8")
    store.publish("select", "Select", source)
    store.submission("answer-1", "select", "REPORT select: one")
    store.mark_report_viewed("select")
    with patch.object(preview, "seconds_since", return_value=0):
      # An unacknowledged answer still holds the removal.
      try:
        store.unpublish("select")
        raise AssertionError("An unacknowledged answer allowed the removal")
      except preview.ReportHeld as error:
        assert "unacknowledged" in str(error)
      store.acknowledge(["answer-1"], "Received")
      try:
        store.unpublish("select")
        raise AssertionError("An unseen acknowledgement allowed the removal")
      except preview.ReportHeld as error:
        assert "acknowledgement" in str(error)
      store.mark_report_ack_seen("select")
      # The holder has nothing left but the view, and the removal passes it.
      store.unpublish("select")
    assert store.state()["reports"] == []
    assert source.exists()


def test_report_changes_ignore_a_fresh_view_of_an_unanswered_report():
  """A report nobody answered has nothing to disturb, so a view never holds a change."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "select.md"
    source.write_text("# Select\n", encoding="utf-8")
    store.publish("select", "Select", source)
    store.mark_report_viewed("select")
    with patch.object(preview, "seconds_since", return_value=0):
      store.publish("select", "Select revised", source)
      store.unpublish("select")
    assert store.state()["reports"] == []


def test_report_view_active_false_clears_the_stamp():
  """The page clears the stamp when it hides the report, so a background look leaves none."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "select.md"
    source.write_text("# Select\n", encoding="utf-8")
    store.publish("select", "Select", source)
    store.submission("answer-1", "select", "REPORT select: one")
    store.acknowledge(["answer-1"], "Received")
    store.mark_report_ack_seen("select")
    store.mark_report_viewed("select")
    cleared = store.mark_report_viewed("select", active=False)
    assert cleared["viewed_at"] is None
    assert store.report("select")["viewed_at"] is None
    store.unpublish("select")
    assert store.state()["reports"] == []


def test_unpublish_route_allows_owner_to_remove_unseen_report():
  """The owner can remove a report before anyone sees it or its answer."""
  global app
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory) / "arena-preview", create=True)
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    threading.Thread(target=app.serve_forever, daemon=True).start()
    headers = {"Content-Type": "application/json"}
    source = Path(directory) / "select.md"
    source.write_text(
      "# Select\n\nChoice? {#select}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("select", "Select one", source)
    store.submission("answer-1", "select", "REPORT select: one")
    status, _, body = request("POST", "/api/reports/select/unpublish", "{}", headers)
    assert status == 200
    assert json.loads(body) == {"unpublished": "select"}
    assert store.state()["reports"] == []


def test_ack_accepts_inline_markdown_and_rejects_stdin():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    store.note("inline-note", "Question")
    text = "Use `arena-preview read` and 'single quotes'.\n\nA second line."
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": directory}
    argv = [sys.executable, preview.__file__, "ack", "inline-note"]
    for redirected in ("", text):
      rejected = subprocess.run(
        argv + ["-"],
        input=redirected,
        capture_output=True,
        text=True,
        env=env,
        check=False,
      )
      assert rejected.returncode != 0
      assert "inline" in rejected.stderr.lower()
      assert store.state()["notes"][0]["acknowledged_at"] is None
    result = subprocess.run(
      argv + [text],
      input="ignored stdin",
      capture_output=True,
      text=True,
      env=env,
      check=True,
    )
    assert result.stdout.startswith("ok inline")
    note = store.state()["notes"][0]
    assert note["ack_type"] == "reply" and note["ack_text"] == text
    assert note["replies"] == []


def test_tick_warning_reads_the_quoting_shape():
  """The gate's classifier names a backtick the shell will substitute, and only then.

  The trap reads the command line before expansion, so the lossy shape is visible: an inline
  ack text in double quotes with a backtick in it.
  """
  lossy = preview.tick_warning('arena-preview ack abc "see `read` now"')
  assert lossy and "backtick" in lossy and "Single-quote" in lossy
  assert "stdin" not in lossy
  assert preview.tick_warning('arena-preview ack "see `read` now"')
  # An escaped tick reaches the tool as text, so it stays quiet. An even backslash run
  # leaves the tick bare, and the shell still substitutes it.
  assert preview.tick_warning('arena-preview ack abc "see \\`read\\` now"') is None
  assert preview.tick_warning('arena-preview ack abc "see \\\\`read` now"')
  # A quoted line, a file form, a tick before the flag and a plain line all stay quiet.
  assert preview.tick_warning("arena-preview ack abc 'see `read` now'") is None
  assert preview.tick_warning("arena-preview ack abc - < reply.md") is None
  assert preview.tick_warning('echo `date` && arena-preview ack abc "plain"') is None
  assert preview.tick_warning("arena-preview task x title --details 'a `tick`'") is None
  assert preview.tick_warning("") is None and preview.tick_warning(None) is None


def test_serve_warning_reads_the_port():
  """The gate's classifier names a port other than the default, and only then.

  The poll and the owner's page follow the port the skill names, so an off-default
  serve hides both.
  """
  off = preview.serve_warning("arena-preview serve --port 8123")
  assert off and "8123" in off and "8000" in off
  assert "The page the owner has open follows the standard address" in off
  assert preview.serve_warning("arena-preview serve --port=8123")
  assert preview.serve_warning("arena-preview serve -p 8123")
  assert preview.serve_warning("arena-preview serve -p8123")
  assert preview.serve_warning("cd repo && preview.py serve --port 8123")
  # The default, an absent flag and a non-serve line all stay quiet.
  assert preview.serve_warning("arena-preview serve --port 8000") is None
  assert preview.serve_warning("arena-preview serve -p 8000") is None
  assert preview.serve_warning("arena-preview serve") is None
  assert preview.serve_warning("arena-preview read") is None
  assert preview.serve_warning("arena-preview serve-tick --help") is None
  assert preview.serve_warning("") is None and preview.serve_warning(None) is None


def test_task_detail_steps():
  script = str(Path(preview.__file__))
  with tempfile.TemporaryDirectory() as tasks_dir:
    preview.Store(tasks_dir, create=True)
    preview.Store(tasks_dir, create=True).set_meta("port", guard_port())
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": tasks_dir}
    out = subprocess.run(
      [
        sys.executable,
        script,
        "task",
        "set",
        "steps",
        "Steps",
        "--scope",
        "arena suite",
        "--details",
        "read it\n\n fix it \ncheck it",
        "--type",
        "misc",
      ],
      capture_output=True,
      text=True,
      check=True,
      env=env,
    ).stdout
    assert "read it" in out and "fix it" in out and "check it" in out
    wall = subprocess.run(
      [
        sys.executable,
        script,
        "task",
        "set",
        "wall",
        "Wall",
        "--details",
        "y" * (preview.TASK_STEP_MAX + 1),
      ],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert wall.returncode != 0 and str(preview.TASK_STEP_MAX) in wall.stderr
    assert "wall" not in {item["id"] for item in preview.Store(tasks_dir).list_tasks()}


def test_task_details_append_keeps_replacement_and_limits():
  script = str(Path(preview.__file__))
  with tempfile.TemporaryDirectory() as tasks_dir:
    store = preview.Store(tasks_dir, create=True)
    store.set_meta("port", guard_port())
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": tasks_dir}

    def cli(*args):
      return subprocess.run(
        [sys.executable, script, *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
      )

    assert (
      cli(
        "task",
        "set",
        "append-task",
        "Append",
        "one",
        "--scope",
        "arena suite",
        "--type",
        "misc",
      ).returncode
      == 0
    )
    result = cli("task", "set", "append-task", "--append", "--details", "two\nthree")
    assert result.returncode == 0, result.stderr
    assert store.task_record("append-task")["details"] == [
      "Scope: arena suite",
      "one",
      "two",
      "three",
    ]
    assert cli("task", "set", "append-task", "-A", "-d", "four").returncode == 0
    assert store.task_record("append-task")["details"] == [
      "Scope: arena suite",
      "one",
      "two",
      "three",
      "four",
    ]
    assert cli("task", "set", "append-task", "Renamed", "replacement").returncode == 0
    assert cli("task", "set", "append-task", "--status", "finished").returncode == 0
    assert store.task_record("append-task")["details"] == [
      "Scope: arena suite",
      "replacement",
    ]
    for args in [
      ("--append",),
      ("--append", "--details", ""),
      ("--append", "--details", "x" * 121),
      ("--append", "--details", "lost", "--msg-id", "aaaaaa"),
    ]:
      assert cli("task", "set", "append-task", *args).returncode != 0
      assert store.task_record("append-task")["details"] == [
        "Scope: arena suite",
        "replacement",
      ]
    store.note("bbbbbb", "Request")
    assert (
      cli(
        "task",
        "set",
        "append-task",
        "--append",
        "--details",
        "linked",
        "--msg-id",
        "bbbbbb",
      ).returncode
      == 0
    )
    assert store.task_record("append-task")["details"] == [
      "Scope: arena suite",
      "replacement",
      "linked",
    ]
    assert store.notes_matching("bbbbbb")[0]["task_id"] == "append-task"
    store.write_task("append-task", details=["kept"] * 39)
    assert (
      cli("task", "set", "append-task", "--append", "--details", "overflow").returncode
      != 0
    )
    assert (
      store.task_record("append-task")["details"]
      == ["Scope: arena suite"] + ["kept"] * 39
    )


def test_download_header_name_is_safe():
  """A CR, LF or quote in a download name never reaches the response header."""
  assert preview.header_filename('a\nb\rc"d') == "a_b_c_d"
  assert preview.header_filename("first.md") == "first.md"


def test_option_labels_join_wrapped_lines():
  """A wrapped option label joins into one option, indented or not, and a blank line ends it."""
  wrapped = (
    "Select one {#select}\n\n"
    "- (x) head tree: `ref: ${{ github.event.pull_request.head.sha || github.sha }}`. A pull\n"
    "  request can then clear its own check, and three workflow tests need the new literal.\n"
    "- ( ) undented wrap\n"
    "on the next line\n"
    "- ( ) plain\n"
    "\n"
    "Trailing prose stays a paragraph.\n"
  )
  blocks, questions = preview.parse_fields(wrapped)
  assert [question["type"] for question in questions] == ["choice"]
  assert [
    option for option in questions[0]["options"] if preview.custom_label(option) is None
  ] == [
    (
      "head tree: `ref: ${{ github.event.pull_request.head.sha || github.sha }}`. A pull "
      "request can then clear its own check, and three workflow tests need the new literal."
    ),
    "undented wrap on the next line",
    "plain",
  ]
  assert questions[0]["default"] == [questions[0]["options"][0]]
  assert [text.strip() for type, text in blocks if type == "markdown"] == [
    "Select one",
    "Trailing prose stays a paragraph.",
  ]


def test_option_join_stops_at_a_block_start():
  """A heading or a new field ends an option group instead of joining it."""
  markdown = "- ( ) only option\n## Section\n- ( ) after heading\nNote: ___\n"
  _, questions = preview.parse_fields(markdown)
  assert [question["type"] for question in questions] == ["choice", "choice", "text"]
  assert [
    option for option in questions[0]["options"] if preview.custom_label(option) is None
  ] == ["only option"]
  assert [
    option for option in questions[1]["options"] if preview.custom_label(option) is None
  ] == ["after heading"]
  assert questions[2]["prompt"] == "Note"


def test_ack_stamps_the_read_line():
  """An ack writes the header's last-read stamp, so its label stays true."""
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "arena-preview"
    store = preview.Store(root, create=True)
    store.note("stamped-note", "Question")
    with patch.object(preview, "now", return_value="2026-09-22T12:00:00"):
      store.read()
      assert store.state()["last_check"] == "2026-09-22T12:00:00"
    with patch.object(preview, "now", return_value="2026-09-22T12:05:00"):
      store.acknowledge(["stamped-note"], "Handled")
      assert store.state()["last_check"] == "2026-09-22T12:05:00"


def test_note_list_pages(tmp_path):
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  for index in (1, 2, 0):
    store.note(
      f"history-{index}",
      "Do not print note text",
      at="2026-10-13T00:00:00" if index == 0 else "2026-10-14T00:00:00",
      quiet=index == 1,
    )
  store.acknowledge(["history-2"], "Already answered")
  before = store.state()["notes"]
  saved = store.save_path.stat().st_mtime_ns

  def run(*argv):
    return subprocess.run(
      [sys.executable, preview.__file__, "note", "list", *argv],
      capture_output=True,
      text=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)},
      check=False,
    )

  first = run("--page-size", "2")
  assert first.returncode == 0, first.stderr
  assert first.stdout.splitlines() == [
    "Notes page 1/2 (3 total; newest first)",
    "history-2",
    "history-1",
  ]
  second = run("--page", "2", "--page-size", "2")
  assert second.returncode == 0
  assert second.stdout.splitlines() == [
    "Notes page 2/2 (3 total; newest first)",
    "history-0",
  ]
  last = run("--page", "3", "--page-size", "2")
  assert last.returncode == 1, last.stdout
  assert last.stdout == ""
  assert "3" in last.stderr and "(2)" in last.stderr
  default = run()
  assert default.returncode == 0
  assert default.stdout.splitlines()[1:] == ["history-2", "history-1", "history-0"]
  for flags in [("--page", "0"), ("--page-size", "0"), ("--page-size", "101")]:
    assert run(*flags).returncode != 0
  assert store.state()["notes"] == before
  assert store.save_path.stat().st_mtime_ns == saved
  store.clear_state()
  empty = run()
  assert empty.returncode == 0
  assert empty.stdout.splitlines() == ["Notes page 1/1 (0 total; newest first)"]
  page_size = 20
  for index in range(page_size + 1):
    store.note(f"page-{index}", "Stored note")
  default = run()
  assert default.returncode == 0
  assert (
    default.stdout.splitlines()[0]
    == f"Notes page 1/2 ({page_size + 1} total; newest first)"
  )
  assert default.stdout.splitlines()[1:] == [
    f"page-{index}" for index in reversed(range(1, page_size + 1))
  ]


def test_note_reread_prints_every_match():
  """The reread takes the short or the full ID, and a short ID that matches
  several notes prints every match, so an acked note stays open to the agent.
  """
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "arena-preview"
    store = preview.Store(root, create=True)
    store.set_meta("port", guard_port())
    store.note("beef001-1111111111111111111111111", "first stored note")
    store.note(
      "beef001-2222222222222222222222222",
      "second stored note",
      acknowledged_at="2026-09-22T12:00:00",
      ack_type="note",
      ack_text="done",
    )

    def run(*argv):
      return subprocess.run(
        [sys.executable, preview.__file__, *argv],
        capture_output=True,
        text=True,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(root)},
        check=False,
      )

    both = run("note", "show", "beef001")
    assert both.returncode == 0
    assert "first stored note" in both.stdout  # nonemo: NMT100
    assert "second stored note" in both.stdout  # nonemo: NMT100
    assert "acked 2026-09-22T12:00:00" in both.stdout
    assert "unacked" in both.stdout
    one = run("note", "show", "beef001-2222222222222222222222222")
    assert one.returncode == 0
    assert "second stored note" in one.stdout  # nonemo: NMT100
    assert "first stored note" not in one.stdout  # nonemo: NMT100
    gone = run("note", "show", "ffff999")
    assert gone.returncode == 1
    assert "ffff999" in gone.stderr


def test_poll_breaks_on_finished_run(capsys, monkeypatch):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    sleeps = []

    def sleeper(seconds):
      sleeps.append(seconds)
      # A gate run that ends during the wait breaks it with the verdict.
      if len(sleeps) == 1:
        preview.run_command(
          directory, "gate", ["--", sys.executable, "-c", "print('ok')"]
        )

    assert preview.poll_inbox(store, sleeper=sleeper) == 0
    assert len(sleeps) == 1
    out = capsys.readouterr().out
    assert "run gate done: exit 0" in out  # nonemo: NMT100
    assert out.rstrip().endswith("DO NOT END TURN. POLL AGAIN.")
    assert preview.run_notices(directory) == 0
    preview.write_detached_placeholder(
      directory,
      "gate",
      ["true"],
      pid=os.getpid(),
      pid_started_at=preview.process_start_identity(os.getpid()),
    )
    assert preview.run_notices(directory, show_running=True) == 1
    assert "run gate running " in capsys.readouterr().err  # nonemo: NMT100

  checks = [
    {
      "type": "check",
      "name": "Repo Checks / Markdown Lint",
      "workflow": "Repo Checks",
      "state": "CANCELLED",
      "at": "2026-10-23T02:01:00Z",
    },
    {
      "type": "check",
      "name": "Repo Checks / Markdown Lint",
      "workflow": "Repo Checks",
      "state": "IN_PROGRESS",
      "at": "2026-10-23T02:00:55Z",
    },
  ]
  monkeypatch.setattr(preview, "gh_check_json", lambda *_a, **_kw: checks)
  latest = preview.pr_check_latest("/tmp", "nemoe7/clankers", "deadbeef")
  assert len(latest) == 1
  assert latest[0]["state"] == "IN_PROGRESS"


def git_repo(directory):
  """A throwaway repository with one commit, so a staged diff exists to scan."""

  def git(*arguments):
    subprocess.run(
      ["git", *arguments],
      cwd=directory,
      capture_output=True,
      text=True,
      check=True,
    )

  git("init", "--quiet")
  git("config", "user.email", "trap@example.invalid")
  git("config", "user.name", "Trap Test")
  Path(directory, "seed.txt").write_text("seed\n", encoding="utf-8")
  git("add", "seed.txt")
  git("commit", "--quiet", "-m", "chore: seed the repository")
  return git


def test_commit_trap_names_a_staged_session_id():
  """A staged line that cites a note ID blocks, and the report names file and line."""
  with tempfile.TemporaryDirectory() as directory:
    state = Path(directory, "state")
    state.mkdir()
    store = preview.Store(str(state), create=True)
    note_id = "0000000-0000000000000000000000000"
    store.note(note_id, "a note")
    repo = Path(directory, "repo")
    repo.mkdir()
    git = git_repo(str(repo))
    Path(repo, "doc.md").write_text(
      f"# Title\n\nFixed in {note_id}.\n", encoding="utf-8"
    )
    git("add", "doc.md")

    hits = preview.staged_session_id_hits(store, str(repo))

    assert len(hits) == 2, hits
    assert {hit[2] for hit in hits} == {note_id, "0000000"}
    assert all(hit[0] == "doc.md" and hit[1] == 3 for hit in hits), hits
    report = preview.commit_id_report(hits)
    assert "COMMIT BLOCKED" in report
    assert "doc.md:3" in report and note_id in report


def test_commit_report_offers_preview_rename_for_task_and_report_collisions():
  task_id = "request-tracker"
  report_id = "release-notes"
  note_id = "a1b2c3"
  hits = [
    ("tracker.py", 1, task_id, "task", task_id),
    ("other.py", 2, task_id, "task", task_id),
    ("release.md", 3, report_id, "report", report_id),
    ("notes.md", 4, note_id, "note", note_id),
  ]
  report = preview.commit_id_report(hits)
  commands = {f"arena-preview rename {ident} NEW-ID" for ident in (task_id, report_id)}
  assert commands.issubset({line.strip() for line in report.splitlines()})
  assert len(
    [line for line in report.splitlines() if "arena-preview rename" in line]
  ) == len(commands)
  assert f"arena-preview rename {note_id} NEW-ID" not in report
  assert all(f"{path}:{number}" in report for path, number, *_ in hits)


def test_commit_trap_ignores_a_git_sha():
  """A SHA that is no session ID passes: the match list comes from the database."""
  with tempfile.TemporaryDirectory() as directory:
    state = Path(directory, "state")
    state.mkdir()
    store = preview.Store(str(state), create=True)
    store.note("0000000-0000000000000000000000000", "a note")
    repo = Path(directory, "repo")
    repo.mkdir()
    git = git_repo(str(repo))
    head = subprocess.run(
      ["git", "rev-parse", "HEAD"],
      cwd=str(repo),
      capture_output=True,
      text=True,
      check=True,
    ).stdout.strip()
    Path(repo, "doc.md").write_text(
      f"Landed {head} and its short form {head[:7]}.\n", encoding="utf-8"
    )
    git("add", "doc.md")

    assert preview.staged_session_id_hits(store, str(repo)) == []
    assert preview.commit_id_report([]) is None


def test_commit_trap_skips_a_removed_citation():
  """Only added lines count, so stripping a citation in this commit passes."""
  with tempfile.TemporaryDirectory() as directory:
    state = Path(directory, "state")
    state.mkdir()
    store = preview.Store(str(state), create=True)
    note_id = "0000000-0000000000000000000000000"
    store.note(note_id, "a note")
    repo = Path(directory, "repo")
    repo.mkdir()
    git = git_repo(str(repo))
    Path(repo, "doc.md").write_text(f"Fixed in {note_id}.\n", encoding="utf-8")
    git("add", "doc.md")
    git("commit", "--quiet", "-m", "docs: cite the note")
    Path(repo, "doc.md").write_text("Fixed.\n", encoding="utf-8")
    git("add", "doc.md")

    assert preview.staged_session_id_hits(store, str(repo)) == []


def test_commit_trap_matches_a_kebab_id_on_its_full_form_only():
  "A report ID matches whole. Its head is a word fragment, so it stays out."
  with tempfile.TemporaryDirectory() as directory:
    state = Path(directory, "state")
    state.mkdir()
    store = preview.Store(str(state), create=True)
    tokens = preview.session_id_tokens(store)
    assert "an-example-report-id" not in tokens
    source = Path(directory, "report.md")
    source.write_text("# Body\n", encoding="utf-8")
    store.publish("an-example-report-id", "A title", source)
    tokens = preview.session_id_tokens(store)
    assert "an-example-report-id" in tokens
    assert "an-example" not in tokens


def test_new_id_is_six_hex_characters():
  """The mint carries the cited length, and a taken ID steps to a free one."""
  with tempfile.TemporaryDirectory() as mint_dir:
    store = preview.Store(mint_dir, create=True)
    first = store.free_id()
    assert preview.NOTE_ID.fullmatch(first), first
    assert len(first) == 6, first
    store.note(first, "Occupied")
    assert store.free_id() != first


def test_commit_trap_names_a_six_character_citation():
  """A staged line that cites the six characters of a minted note blocks the commit."""
  with tempfile.TemporaryDirectory() as directory:
    state = Path(directory, "state")
    state.mkdir()
    store = preview.Store(str(state), create=True)
    note_id = "abcdef"
    store.note(note_id, "a note")
    repo = Path(directory, "repo")
    repo.mkdir()
    git = git_repo(str(repo))
    Path(repo, "doc.md").write_text(f"Fixed in {note_id}.\n", encoding="utf-8")
    git("add", "doc.md")

    hits = preview.staged_session_id_hits(store, str(repo))

    assert hits, hits
    assert all(hit[2] == note_id for hit in hits), hits
    assert "COMMIT BLOCKED" in preview.commit_id_report(hits)


def test_rename_repoints_a_note_and_its_uploads():
  """A renamed note keeps its uploads: the schema declares no key, so the rename moves them."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.note("aaaaaaa-1111111111111111111111111", "a note")
    store.save_upload(
      "photo.png", "image/png", b"pixels", note_id="aaaaaaa-1111111111111111111111111"
    )

    type = store.rename_entity(
      "aaaaaaa-1111111111111111111111111", "bbbbbbb-2222222222222222222222222"
    )

    assert type == "note"
    with closing(store.connect()) as db:
      assert (
        db.execute(
          "SELECT count(*) FROM notes WHERE id = 'bbbbbbb-2222222222222222222222222'"
        ).fetchone()[0]
        == 1
      )
      orphaned = db.execute(
        "SELECT count(*) FROM uploads WHERE note_id = 'aaaaaaa-1111111111111111111111111'"
      ).fetchone()[0]
      moved = db.execute(
        "SELECT count(*) FROM uploads WHERE note_id = 'bbbbbbb-2222222222222222222222222'"
      ).fetchone()[0]
    assert orphaned == 0 and moved == 1


def test_rename_repoints_a_task_from_the_records_that_name_it():
  """A renamed task keeps the note marker and the blocked report link."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.note("aaaaaaa-1111111111111111111111111", "a note")
    store.write_task("old-name", "A title", ["One step"], task_type="misc")
    store.mark_task("aaaaaaa-1111111111111111111111111", "old-name")

    type = store.rename_entity("old-name", "new-name")

    assert type == "task"
    with closing(store.connect()) as db:
      assert (
        db.execute("SELECT count(*) FROM notes WHERE task_id = 'new-name'").fetchone()[
          0
        ]
        == 1
      )
      assert (
        db.execute("SELECT count(*) FROM notes WHERE task_id = 'old-name'").fetchone()[
          0
        ]
        == 0
      )


def test_rename_refuses_an_id_another_record_holds():
  """One ID names one record, so a rename onto a taken ID fails and moves nothing."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.write_task("first-task", "A title", ["One step"], task_type="misc")
    store.write_task("second-task", "Another title", ["One step"], task_type="misc")

    try:
      store.rename_entity("first-task", "second-task")
      raise AssertionError("a rename onto a taken ID must fail")
    except ValueError as error:
      assert "second-task" in str(error)

    with closing(store.connect()) as db:
      assert (
        db.execute("SELECT count(*) FROM tasks WHERE id = 'first-task'").fetchone()[0]
        == 1
      )


def test_key_output_names_fetch_page_over_bash():
  """The key line says which tool carries it, so a session does not retry through a shell."""
  lines = preview.format_key(
    {"key": "a-key", "host": "https://proxy.example", "at": "2026-10-10T09:00Z"}
  ).splitlines()
  assert lines[0] == "key a-key"
  assert lines[1] == "host https://proxy.example"
  assert "fetch_page" in lines[2] and "never bash" in lines[2]
  assert "https://proxy.example/v1/" in lines[2]
  assert lines[3] == "at 2026-10-10T09:00Z"

  # No host means no route to name, so the line stays out.
  bare = preview.format_key({"key": "a-key"}).splitlines()
  assert bare == ["key a-key"]


# The warning's exact text, so the assertions compare whole strings. A substring test
# against a string that carries a URL reads to CodeQL as incomplete URL sanitization.
EGRESS_WARNING = (
  "arena-preview gate: {host} sits outside this sandbox's egress allowlist. The"
  " TLS handshake fails with SSL_ERROR_SYSCALL, which reads as a transient fault"
  " and never clears on a retry. Read it through the fetch_page tool instead."
)


def test_egress_warning_names_a_blocked_host():
  "A fetch to a blocked host names the tool that can reach it."
  assert preview.egress_warning("curl -sS https://httpbin.org/get") == (
    EGRESS_WARNING.format(host="httpbin.org")
  )


def test_egress_warning_stays_quiet_on_an_allowed_host():
  """The allowlist holds the hosts this sandbox reaches, so they raise nothing."""
  for line in (
    "curl -sS https://api.github.com/repos/nemoe7/clankers",
    "curl -o /tmp/f.tgz https://codeload.github.com/a/b/tar.gz/refs/heads/main",
    "git fetch origin main",
  ):
    assert preview.egress_warning(line) is None, line


def test_egress_warning_ignores_a_url_no_command_fetches():
  """A URL inside any other command is text, so it must not raise the warning."""
  for line in (
    "grep -rn https://example.com docs/",
    "echo see https://nodejs.org for details",
  ):
    assert preview.egress_warning(line) is None, line


def test_egress_warning_covers_wget_and_git_clone():
  """The trap reads the command, not one tool name."""
  assert preview.egress_warning("wget https://raw.githubusercontent.com/a/b/c.md") == (
    EGRESS_WARNING.format(host="raw.githubusercontent.com")
  )
  assert preview.egress_warning("git clone https://gitlab.com/x/y.git") == (
    EGRESS_WARNING.format(host="gitlab.com")
  )


@pytest.mark.parametrize(
  "args",
  [
    [],
    ["not-a-command"],
    ["serve", "--port"],
    ["task", "set", "demo", "--type", "not-a-type"],
  ],
)
def test_cli_argument_errors_omit_usage(args):
  cli = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), *args],
    capture_output=True,
    text=True,
    check=False,
  )
  assert cli.returncode == 2
  assert not cli.stdout
  prefix = {
    "serve": "arena-preview serve: error: ",
    "task": "arena-preview task set: error: ",
  }.get(args[0] if args else "", "error: ")
  assert cli.stderr.startswith(prefix), cli.stderr
  assert "arena-preview: " not in cli.stderr
  assert "error:" in cli.stderr and "preview.py" not in cli.stderr
  assert "usage:" not in cli.stderr.casefold()
  if not args:
    assert "arena-preview --help" in cli.stderr  # nonemo: NMT100
  if args and args[-1].startswith("not-"):
    assert args[-1] in cli.stderr


def test_cli_wrapper_errors_have_no_program_prefix():
  source = Path(preview.__file__).with_name("arena-preview").read_text(encoding="utf-8")
  with tempfile.TemporaryDirectory() as directory:
    wrapper = Path(directory) / "arena-preview"
    wrapper.write_text(source, encoding="utf-8")
    for initialize in (False, True):
      if initialize:
        subprocess.run(["git", "init", "-q", directory], check=True)
      result = subprocess.run(
        ["bash", str(wrapper)],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": directory},
      )
      assert result.returncode == 2
      if initialize:
        expected_python = (
          Path(directory) / ".agents" / ".arena-preview-venv" / "bin" / "python"
        )
        expected_installer = (
          Path(directory)
          / ".agents"
          / "skills"
          / "arena-skill"
          / "scripts"
          / "install.sh"
        )
        assert str(expected_python) in result.stderr
        assert str(expected_installer) in result.stderr
      else:
        assert "Git" in result.stderr
      assert "arena-preview: " not in result.stderr
      assert result.stdout == ""


def test_cli_missing_task_id_keeps_validation(tmp_path, monkeypatch, capsys):
  preview.Store(tmp_path, create=True)
  monkeypatch.setattr(preview, "resolve_state_dir", lambda: tmp_path)
  monkeypatch.setattr(preview, "require_server", lambda store: None)
  monkeypatch.setattr(sys, "argv", ["preview.py", "task", "set"])
  assert preview.main() == 1
  output = capsys.readouterr()
  assert not output.out
  assert (
    'A task needs an ID: arena-preview task set <id> "<title>" -m <msg-id>'
    in output.err
  )
  assert "usage:" not in output.err.casefold()


def test_cli_help_keeps_usage():
  cli = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "--help"],
    capture_output=True,
    text=True,
    check=True,
  )
  assert "usage:" in cli.stdout.casefold()
  assert not cli.stderr
  # The description names the hook's commands, so they read as hooks.
  flat = " ".join(cli.stdout.split())
  assert "The installed hook calls `pre`, `gate` and `route-run`" in flat
  task_help = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "task", "set", "--help"],
    capture_output=True,
    text=True,
    check=True,
  ).stdout
  flat_task = " ".join(task_help.split())
  assert "-A, --append" in flat_task
  assert "--type" in flat_task


def test_reference_commands_table_lists_every_agent_facing_command():
  """The commands table in the reference matches the CLI parser, internal commands aside."""
  references = Path(__file__).parents[1] / "references"
  reference = references / "COMMANDS.md"
  if not reference.is_file():
    reference = references / "REFERENCE.md"
  if not reference.is_file():
    return  # The generated runtime holds scripts only, so the reference is absent.
  section = reference.read_text(encoding="utf-8").split("## Commands", 1)[1]
  table = section.split("\n## ", 1)[0]
  documented_rows = [
    match.group(1)
    for line in table.splitlines()
    if (match := re.match(r"\| `([^`]+)`", line))
  ]
  documented = {signature.split()[0] for signature in documented_rows}
  assert len(documented_rows) == len(set(documented_rows)), (
    "CLI commands table repeats a signature"
  )
  help_text = subprocess.run(
    [sys.executable, str(Path(__file__).parent / "preview.py"), "--help"],
    capture_output=True,
    text=True,
    check=True,
  ).stdout
  actual = set(re.search(r"\{([a-z,\-]+)\}", help_text).group(1).split(","))
  internal = {"pre", "route-run", "gate"}
  assert documented <= actual, (
    f"table names unknown commands: {sorted(documented - actual)}"
  )
  missing = sorted(actual - internal - documented)
  assert not missing, f"CLI commands missing from the table: {missing}"


def test_poll_label_reports_live_routed_waits():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    live_detached_placeholder(directory, "pr-checks", ["python", "-m", "pytest"])
    assert store.state()["waiting_for_gates"] is False
    assert store.state()["checking_pr"] is False
    store.start_poll()
    assert store.state()["waiting_for_gates"] is True
    assert store.state()["checking_pr"] is False
    live_detached_placeholder(directory, "ci", ["bash", "-c", "gh pr checks 7 --watch"])
    assert store.state()["checking_pr"] is True
    preview.run_command(directory, "ci", ["true"])
    assert store.state()["waiting_for_gates"] is True
    assert store.state()["checking_pr"] is False
    preview.run_command(directory, "pr-checks", ["true"])
    assert store.state()["waiting_for_gates"] is False
    assert store.state()["checking_pr"] is False
    live_detached_placeholder(directory, "ci", ["gh", "pr", "checks", "7", "--watch"])
    assert store.state()["checking_pr"] is True
    store.clear_polling()
    assert store.state()["waiting_for_gates"] is False
    assert store.state()["checking_pr"] is False


def test_publish_embeds_a_local_image_at_publication():
  """Publication stores a local image as a data URI so the renderer reads nothing."""
  with tempfile.TemporaryDirectory() as image_dir:
    root = Path(image_dir)
    store = preview.Store(root, create=True)
    raw = b"\x89PNG\r\n\x1a\n" + b"payload"
    (root / "shot.png").write_bytes(raw)
    source = root / "report.md"
    source.write_text("# Report\n\n![shot](shot.png)\n", encoding="utf-8")
    store.publish("images", "Images", source)
    stored = store.report("images")["markdown"]
    payload = base64.b64encode(raw).decode("ascii")
    assert f"![shot](data:image/png;base64,{payload})" in stored
    # The stored text carries the bytes, so the renderer needs no file.
    (root / "shot.png").unlink()
    source.unlink()
    html, _ = preview.render_report(stored)
    assert f"data:image/png;base64,{payload}" in html


def test_publish_rejects_remote_images_and_keeps_links():
  """A remote image URL leaves the report as a hint while a plain link stays."""
  with tempfile.TemporaryDirectory() as image_dir:
    root = Path(image_dir)
    store = preview.Store(root, create=True)
    source = root / "report.md"
    source.write_text(
      "[doc](https://example.com/doc) ![pic](https://example.com/pic.png)\n",
      encoding="utf-8",
    )
    store.publish("remote", "Remote", source)
    stored = store.report("remote")["markdown"]
    assert "https://example.com/doc" in stored
    assert "![pic](https://example.com/pic.png)" not in stored
    assert "Publication skips remote image" in stored
    assert "arena-preview image-data-uri" in stored


def test_publish_skips_local_images_that_fail_the_checks():
  """Publication skips a local image that is missing or wrong, with the helper hint."""
  with tempfile.TemporaryDirectory() as image_dir:
    root = Path(image_dir)
    store = preview.Store(root, create=True)
    (root / "notes.txt").write_text("plain words", encoding="utf-8")
    source = root / "report.md"
    source.write_text("![gone](missing.png)\n\n![txt](notes.txt)\n", encoding="utf-8")
    store.publish("skips", "Skips", source)
    stored = store.report("skips")["markdown"]
    assert "![gone](" not in stored and "![txt](" not in stored
    assert "Publication skips local image" in stored
    assert "image-data-uri" in stored


def test_publish_embeds_parent_and_absolute_paths():
  """The boundary answer allows parent-directory and absolute local image paths."""
  with tempfile.TemporaryDirectory() as image_dir:
    base = Path(image_dir)
    up_raw = b"\x89PNG\r\n\x1a\n" + b"outer"
    (base / "outer.png").write_bytes(up_raw)
    report_dir = base / "nested"
    report_dir.mkdir()
    store = preview.Store(report_dir, create=True)
    abs_raw = b"\x89PNG\r\n\x1a\n" + b"abs"
    absolute = base / "abs.png"
    absolute.write_bytes(abs_raw)
    source = report_dir / "report.md"
    source.write_text(
      "![up](../outer.png)\n\n![abs](" + str(absolute) + ")\n\n"
      "![in](data:image/gif;base64,R0lGOD)\n",
      encoding="utf-8",
    )
    store.publish("paths", "Paths", source)
    stored = store.report("paths")["markdown"]
    up_payload = base64.b64encode(up_raw).decode("ascii")
    abs_payload = base64.b64encode(abs_raw).decode("ascii")
    assert "../outer.png" not in stored
    assert f"data:image/png;base64,{up_payload}" in stored
    assert f"data:image/png;base64,{abs_payload}" in stored
    assert "![in](data:image/gif;base64,R0lGOD)" in stored


def test_publish_keeps_the_size_suffix_on_an_embedded_image():
  """The sized-image syntax keeps its pixel suffix after the source becomes a data URI."""
  with tempfile.TemporaryDirectory() as image_dir:
    root = Path(image_dir)
    store = preview.Store(root, create=True)
    raw = b"\x89PNG\r\n\x1a\n" + b"sized"
    (root / "tile.png").write_bytes(raw)
    source = root / "report.md"
    source.write_text("![tile](tile.png =32x)\n", encoding="utf-8")
    store.publish("sized", "Sized", source)
    stored = store.report("sized")["markdown"]
    payload = base64.b64encode(raw).decode("ascii")
    assert f"![tile](data:image/png;base64,{payload} =32x)" in stored


def test_task_type_writes_preserves_and_round_trips():
  """One primary type rides the task through update, save and import."""
  with tempfile.TemporaryDirectory() as type_dir:
    store = preview.Store(type_dir, create=True)
    created = store.write_task("typed", "Typed work", ["Step one"], task_type="code")
    assert created["type"] == "code"
    plain = store.write_task("plain", "Plain work", ["Step one"], task_type="misc")
    assert plain["type"] == "misc"
    updated = store.write_task("typed", details=["Step one", "Step two"])
    assert updated["type"] == "code", "an omitted flag preserves the type"
    records = [
      preview.saved_task_line(store.task_record(task_id))
      for task_id in ("typed", "plain")
    ]
    assert records[0]["type"] == "code"
    assert records[1]["type"] == "misc"
    written = store.import_tasks(records, replace=True)
    assert [row["type"] for row in written] == ["code", "misc"]
    try:
      store.write_task("bad", "Bad", ["Step"], task_type="mixed")
    except ValueError as error:
      assert "type" in str(error)
    else:
      raise AssertionError("an unknown task type was accepted")


def test_task_type_cli_flag_and_print():
  """The CLI sets a type, shows it on the row, and keeps it when a later call omits the flag."""
  with tempfile.TemporaryDirectory() as type_dir:
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": type_dir}
    preview.Store(type_dir, create=True).set_meta("port", guard_port())

    def cli(*arguments):
      return subprocess.run(
        [sys.executable, str(Path(preview.__file__)), "task", "set", *arguments],
        capture_output=True,
        text=True,
        check=False,
        env=env,
      )

    made = cli(
      "typed-task", "Typed", "Step", "--scope", "arena suite", "--type", "docs"
    )
    assert made.returncode == 0, made.stderr

    missing = cli("missing-type", "Missing a type", "Step", "--scope", "arena suite")
    assert missing.returncode != 0
    assert "type" in missing.stderr.lower()
    assert "type docs" in made.stdout
    again = cli("typed-task", "Typed", "Step two")
    assert again.returncode == 0, again.stderr
    assert "type docs" in again.stdout, "a call without the flag keeps the type"
    bare = cli("typed-task")
    assert "type docs" in bare.stdout
    unknown = cli(
      "other-task", "Other", "Step", "--scope", "arena suite", "--type", "mixed"
    )
    assert unknown.returncode != 0


def test_tasks_carry_their_linked_answers():
  """A task carries its linked answers for a read-only block under its details: the report link and a named
  link both count, one entry holds per submission ID, and the entries outlive the report row. The export
  keeps an answer a task still references once its report is gone."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    source = Path(directory) / "linked.md"
    source.write_text(
      "# Linked\n\nChoice? {#select}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("linked", "Linked select", source)
    store.write_task(
      "linked-task",
      "Track the select",
      ["Read the answer"],
      report_id="linked",
      task_type="misc",
    )
    store.write_task(
      "named-task",
      "Answer named directly",
      ["Read it"],
      report_id="linked",
      task_type="misc",
    )
    store.write_task("bare-task", "No link", ["Step one"], task_type="misc")
    store.submission("answer-one", "linked", "REPORT linked: one")
    store.submission("answer-two", "linked", "REPORT linked: two", task_id="named-task")
    upcoming = store.state()["tasks"]["upcoming"]
    by_id = {row["id"]: row for row in upcoming}
    linked = by_id["linked-task"]["answers"]
    assert [entry["id"] for entry in linked] == ["answer-one", "answer-two"], linked
    assert linked[0]["text"] == "REPORT linked: one"
    assert linked[0]["at"], "the entry carries its answer time"
    assert [entry["report_id"] for entry in linked] == ["linked", "linked"]
    # The named answer matches both links and still appears once.
    named = by_id["named-task"]["answers"]
    assert [entry["id"] for entry in named] == ["answer-one", "answer-two"], named
    assert "answers" not in by_id["bare-task"], "an unlinked task keeps its old shape"
    store.unpublish("linked", dismissed_by_owner=True)
    after = {row["id"]: row for row in store.state()["tasks"]["upcoming"]}
    assert [entry["id"] for entry in after["linked-task"]["answers"]] == [
      "answer-one",
      "answer-two",
    ], "the answers outlive their report row"
    lines, counts = store.state_lines(store.state()["notes"], store.tasks())
    kept = {line.get("id") for line in lines if line.get("report_id") is not None}
    assert {"answer-one", "answer-two"} <= kept, (
      "a referenced answer stays in the export"
    )
    assert counts["answers"] == 2, counts


def pr_check_root(directory):
  """A repository root the discovery reads its branch from, with no gh calls of its own."""
  root = Path(directory)
  (root / ".git").mkdir(exist_ok=True)
  (root / ".git" / "HEAD").write_text("ref: refs/heads/arena/session\n", "utf-8")
  return root


def fake_gh(heads, counts, calls, required=3, states=("SUCCESS",)):
  """A stand-in for subprocess.run that answers the discovery reads and records every call."""

  def run(argv, **kwargs):
    calls.append([str(item) for item in argv])
    if argv[:3] == ["gh", "pr", "list"]:
      head = heads[
        min(
          len([c for c in calls if c[:3] == ["gh", "pr", "list"]]) - 1, len(heads) - 1
        )
      ]
      return subprocess.CompletedProcess(argv, 0, stdout=f"{head}\n", stderr="")
    if argv[:3] == ["gh", "pr", "view"]:
      return subprocess.CompletedProcess(
        argv, 0, stdout='{"baseRefName":"main","number":111}', stderr=""
      )
    if argv[:3] == ["gh", "api", "graphql"] and any(
      "statusCheckRollup" in arg for arg in argv
    ):
      reads = [
        c
        for c in calls
        if c[:3] == ["gh", "api", "graphql"]
        and any("statusCheckRollup" in arg for arg in c)
      ]
      count = counts[min(len(reads) - 1, len(counts) - 1)]
      state = states[min(len(reads) - 1, len(states) - 1)]
      if "--paginate" in argv:
        output = "\n".join(
          json.dumps(
            {
              "type": "check",
              "name": f"check-{i}",
              "workflow": "CI",
              "state": state,
              "at": "2026-10-18T00:00:00Z",
            }
          )
          for i in range(count)
        )
      elif any("isRequired" in arg for arg in argv):
        output = "\n".join(json.dumps(f"check-{i}") for i in range(count))
      else:
        output = json.dumps(
          {
            "statusCheckRollup": {
              "state": state,
              "contexts": {"totalCount": count},
            }
            if count
            else None
          }
        )
      return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")
    if argv[:3] == ["gh", "api", "graphql"]:
      return subprocess.CompletedProcess(
        argv, 0, stdout=json.dumps([f"check-{i}" for i in range(required)]), stderr=""
      )
    if argv[:2] == ["gh", "api"] and "/rules/branches/" in argv[2]:
      return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
    return subprocess.CompletedProcess(argv, 0, stdout="watched\n", stderr="")

  return run


def advancing_clock():
  """A monotonic clock and sleep pair for watcher tests."""
  now = [0.0]
  sleeps = []

  def sleep(seconds):
    sleeps.append(seconds)
    now[0] += seconds

  return now, sleeps, sleep


def test_the_pr_check_wait_finds_checks_before_it_watches(capsys):
  """The native watch starts after the first check appears on the pinned head."""
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    calls = []
    now, sleeps, sleep = advancing_clock()
    with (
      patch("preview.resolve_repo_root", return_value=str(root)),
      patch("preview.repo_slug", return_value="owner/repo"),
      patch(
        "preview.subprocess.run", side_effect=fake_gh(["abc1234"], [0, 0, 3], calls)
      ),
      patch("preview.time.sleep", sleep),
      patch("preview.time.monotonic", lambda: now[0]),
    ):
      code = preview.run_command(
        directory, "pr-checks", ["bash", "-c", "gh pr checks 107 --watch"]
      )
    out = capsys.readouterr().out
    assert code == 0, out
    polls = preview.PR_CHECK_DISCOVERY_SECONDS // preview.PR_CHECK_DISCOVERY_STEP
    assert sleeps == [preview.PR_CHECK_DISCOVERY_STEP] * polls, sleeps
    reads = [call for call in calls if any("statusCheckRollup" in arg for arg in call)]
    assert len(reads) == polls + 1, reads
    assert all("sha=abc1234" in call for call in reads), reads
    assert not [call for call in calls if call[0] != "gh"], "the native watch ran"
    assert "best effort" in out.lower(), out


def test_pr_check_wait_does_not_stop_on_early_green():
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    calls = []
    now, pauses, sleep = advancing_clock()
    with (
      patch("preview.repo_slug", return_value="owner/repo"),
      patch("preview.time.monotonic", lambda: now[0]),
      patch(
        "preview.subprocess.run",
        side_effect=fake_gh(["abc1234"], [1, 1, 3], calls, required=1),
      ),
    ):
      status, _lines = preview.pr_checks_watch(root, seconds=10, step=5, sleep=sleep)
    assert status == "success"
    assert pauses == [5, 5]


def test_pr_check_wait_needs_no_required_check_settings():
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    calls = []
    with (
      patch("preview.repo_slug", return_value="owner/repo"),
      patch(
        "preview.subprocess.run",
        side_effect=fake_gh(["abc1234"], [1], calls, required=0),
      ),
    ):
      status, _lines = preview.pr_checks_watch(root, seconds=0)
    assert status == "success"
    assert not any("/rules/branches/" in str(call) for call in calls)
    assert not any("refUpdateRule" in str(call) for call in calls)


def test_pr_check_rollup_uses_latest_check_and_status_runs():
  old = {
    "type": "check",
    "name": "Contract",
    "workflow": "PR Check",
    "state": "FAILURE",
    "at": "2026-10-18T08:00:00Z",
  }
  new = {**old, "state": "SUCCESS", "at": "2026-10-18T09:00:00Z"}
  for nodes, expected in [
    ([old, new], ("SUCCESS", 1)),
    ([new, old], ("SUCCESS", 1)),
    ([new, {**new, "state": "QUEUED", "at": "2026-10-18T10:00:00Z"}], ("PENDING", 1)),
    ([new, {**old, "workflow": "Other"}], ("FAILURE", 2)),
    (
      [
        {**old, "type": "status", "workflow": ""},
        {**new, "type": "status", "workflow": ""},
      ],
      ("SUCCESS", 1),
    ),
    ([old, {**new, "type": "status", "workflow": ""}], ("FAILURE", 2)),
    ([{**old, "at": "2026-10-18T10:00:00+02:00"}, new], ("SUCCESS", 1)),
  ]:
    with patch("preview.gh_check_json", return_value=nodes):
      assert preview.pr_check_rollup(".", "owner/repo", "sha") == expected


def test_pr_check_rollup_boundaries():
  for error in (OSError("gh missing"), subprocess.TimeoutExpired("gh", 5)):
    with patch("preview.subprocess.run", side_effect=error):
      assert preview.pr_head_sha(".", "branch", "owner/repo") is None
      assert preview.pr_check_rollup(".", "owner/repo", "sha") is None
  for code, output in ((1, "auth failed"), (0, "not JSON")):
    result = subprocess.CompletedProcess([], code, stdout=output, stderr="")
    with patch("preview.subprocess.run", return_value=result):
      assert preview.pr_check_rollup(".", "owner/repo", "sha") is None
  node = {
    "type": "check",
    "name": "test",
    "workflow": "CI",
    "state": "SUCCESS",
    "at": "2026-10-18T00:00:00Z",
  }
  for data, expected in [
    ([], ("PENDING", 0)),
    ([{**node, "name": f"test-{i}"} for i in range(201)], ("SUCCESS", 201)),
    (None, None),
    ({}, None),
    ([None], None),
    ([{}], None),
    ([{**node, "state": []}], None),
    ([{**node, "state": "UNKNOWN"}], ("PENDING", 1)),
    ([{**node, "at": "bad timestamp"}], None),
    ([{**node, "at": "2026-10-18T00:00:00"}], None),
    ([{**node, "workflow": []}], None),
    ([{**node, "name": 1}], None),
    ([{**node, "state": "SKIPPED"}], ("SUCCESS", 1)),
    ([{**node, "state": "NEUTRAL"}], ("SUCCESS", 1)),
  ]:
    with patch("preview.gh_check_json", return_value=data):
      assert preview.pr_check_rollup(".", "owner/repo", "sha") == expected
  output = "\n".join(json.dumps({**node, "name": f"test-{i}"}) for i in range(201))
  result = subprocess.CompletedProcess([], 0, stdout=output, stderr="")
  with patch("preview.subprocess.run", return_value=result) as run:
    assert preview.pr_check_rollup(".", "owner/repo", "sha") == ("SUCCESS", 201)
    command = run.call_args.args[0]
    assert "--paginate" in command
    assert any("pageInfo{hasNextPage endCursor}" in arg for arg in command)


def test_pr_check_watch_reports_failures_and_keeps_watching():
  """Each new failure emits progress while nonterminal checks keep the watch live."""
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    now, pauses, sleep = advancing_clock()
    progress = []

    def node(name, state, at):
      return {
        "type": "check",
        "name": name,
        "workflow": "CI",
        "state": state,
        "at": at,
      }

    quality_failed = node("Quality", "FAILURE", "2026-10-18T00:10:00Z")
    tests_failed = node("Tests", "FAILURE", "2026-10-18T00:15:00Z")
    docs_done = node("Docs", "SUCCESS", "2026-10-18T00:20:00Z")
    snapshots = [
      [],
      [
        node("Quality", "IN_PROGRESS", "2026-10-18T00:05:00Z"),
        node("Tests", "QUEUED", "2026-10-18T00:05:00Z"),
      ],
      [quality_failed, node("Tests", "IN_PROGRESS", "2026-10-18T00:05:00Z")],
      [quality_failed, tests_failed],
      [
        quality_failed,
        tests_failed,
        node("Docs", "QUEUED", "2026-10-18T00:20:00Z"),
      ],
      [quality_failed, tests_failed, docs_done],
      [quality_failed, tests_failed, docs_done],
    ]
    with (
      patch("preview.repo_slug", return_value="owner/repo"),
      patch("preview.pr_head_sha", return_value="abc1234"),
      patch("preview.pr_check_latest", side_effect=snapshots),
      patch("preview.time.monotonic", lambda: now[0]),
    ):
      status, lines = preview.pr_checks_watch(
        root, seconds=30, step=5, sleep=sleep, progress=progress.append
      )

  assert status == "failure"
  assert progress == ["Failed so far: CI / Quality", "Failed so far: CI / Tests"]
  assert lines[-1] == "PR CHECKS FAILED: CI / Quality, CI / Tests."
  assert pauses == [5] * 6


def test_pr_check_wait_counts_api_time_against_the_window():
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    now, pauses, sleep = advancing_clock()
    node = {
      "type": "check",
      "name": "Quality",
      "workflow": "CI",
      "state": "SUCCESS",
      "at": "2026-10-18T00:00:00Z",
    }

    def latest(*_args):
      now[0] += 6
      return [node]

    with (
      patch("preview.repo_slug", return_value="owner/repo"),
      patch("preview.pr_head_sha", return_value="abc1234"),
      patch("preview.pr_check_latest", side_effect=latest),
      patch("preview.time.monotonic", lambda: now[0]),
    ):
      status, _lines = preview.pr_checks_watch(root, seconds=10, step=5, sleep=sleep)
    assert status == "success"
    assert pauses == [4]


def test_pr_check_wait_rechecks_the_head_before_success():
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    with (
      patch("preview.repo_slug", return_value="owner/repo"),
      patch(
        "preview.subprocess.run",
        side_effect=fake_gh(["abc1234", "def5678"], [3, 0], []),
      ),
    ):
      status, lines = preview.pr_checks_watch(root, seconds=0)
    assert status == "not_started"
    assert "no visible checks appeared on def5678" in lines[0]


def test_the_pr_check_wait_fails_when_no_check_appears(capsys):
  """A start window that runs out fails the run as not started."""
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    calls = []
    now, sleeps, sleep = advancing_clock()
    with (
      patch("preview.resolve_repo_root", return_value=str(root)),
      patch("preview.repo_slug", return_value="owner/repo"),
      patch("preview.subprocess.run", side_effect=fake_gh(["abc1234"], [0], calls)),
      patch("preview.time.sleep", sleep),
      patch("preview.time.monotonic", lambda: now[0]),
    ):
      code = preview.run_command(
        directory, "pr-checks", ["bash", "-c", "gh pr checks 107 --watch"]
      )
    out = capsys.readouterr().out
    assert code == 1, "a timeout is a failure, never a pass"
    assert "PR CHECKS NOT STARTED" in out, out
    assert "abc1234" in out, out
    polls = preview.PR_CHECK_DISCOVERY_SECONDS // preview.PR_CHECK_DISCOVERY_STEP
    assert sleeps == [preview.PR_CHECK_DISCOVERY_STEP] * polls, (
      "the window polls to its end"
    )
    assert not [call for call in calls if call[0] != "gh"], "the watch never ran"


def test_the_pr_check_wait_hands_off_to_a_moved_head(capsys):
  """A new head receives a full start window and its own verdict."""
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    calls = []
    now, sleeps, sleep = advancing_clock()
    with (
      patch("preview.resolve_repo_root", return_value=str(root)),
      patch("preview.repo_slug", return_value="owner/repo"),
      patch(
        "preview.subprocess.run",
        side_effect=fake_gh(["abc1234", "def5678"], [0, 3], calls),
      ),
      patch("preview.time.sleep", sleep),
      patch("preview.time.monotonic", lambda: now[0]),
    ):
      code = preview.run_command(
        directory, "pr-checks", ["bash", "-c", "gh pr checks 107 --watch"]
      )
    out = capsys.readouterr().out
    assert code == 0, out
    assert "best effort" in out.lower(), out
    assert sleeps == [preview.PR_CHECK_DISCOVERY_STEP] * 7
    reads = [call for call in calls if any("statusCheckRollup" in arg for arg in call)]
    assert sum("sha=abc1234" in call for call in reads) == 1
    assert sum("sha=def5678" in call for call in reads) == 7
    assert not [call for call in calls if call[0] != "gh"]


def test_the_pr_check_wait_fails_on_a_gh_fault(capsys):
  """A gh fault fails the wait instead of passing it or watching with no checks."""
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    calls = []
    fault = subprocess.CompletedProcess(["gh"], 1, stdout="", stderr="auth failed")
    with (
      patch("preview.resolve_repo_root", return_value=str(root)),
      patch("preview.repo_slug", return_value="owner/repo"),
      patch(
        "preview.subprocess.run",
        side_effect=lambda *a, **k: calls.append(a[0]) or fault,
      ),
      patch("preview.time.sleep", lambda seconds: None),
    ):
      code = preview.run_command(
        directory, "pr-checks", ["bash", "-c", "gh pr checks 107 --watch"]
      )
    out = capsys.readouterr().out
    assert code == 1, out
    assert "gh" in out, out
    assert len(calls) == 1 and calls[0][0] == "gh", calls


def test_a_routed_line_that_is_not_a_check_wait_skips_the_watcher(capsys):
  """The pull-request watcher belongs to check waits alone, so other runs stay untouched."""
  with tempfile.TemporaryDirectory() as directory:
    root = pr_check_root(directory)
    calls = []
    with (
      patch("preview.resolve_repo_root", return_value=str(root)),
      patch("preview.repo_slug", return_value="owner/repo"),
      patch("preview.subprocess.run", side_effect=fake_gh(["abc1234"], [0], calls)),
      patch("preview.time.sleep", lambda seconds: None),
    ):
      plain = preview.run_command(directory, "gates", ["bash", "-c", "echo plain"])
      run_watch = preview.run_command(
        directory, "run-watch", ["bash", "-c", "gh run watch 12345"]
      )
    out = capsys.readouterr().out
    assert plain == 0 and run_watch == 0, out
    assert "run gates done: exit 0" in out, (  # nonemo: NMT100
      "the plain line ran at once"
    )
    assert (
      "run run-watch done: exit 0"  # nonemo: NMT100
      in out
    ), "a run watch needs no discovery"
    assert not [call for call in calls if call[0] == "gh"], (
      "no discovery read ran for either line"
    )


def test_the_worktree_reminder_shows_the_installed_start_form():
  references = Path(__file__).resolve().parent.parent / "references"
  reference = references / "commands.md"
  if not reference.exists():
    reference = references / "reference.md"
  if not reference.exists():
    pytest.skip("the compact runtime copy ships without the references directory")
  lines = reference.read_text(encoding="utf-8").splitlines()
  row = next(line for line in lines if line.startswith("| `worktree start"))
  usage = row.split("`")[1]
  assert usage in preview.WORKTREE_STEP, (
    "the reminder must show the parser's own start form"
  )


def test_logs_repeats_the_worktree_step_while_a_run_is_still_going(tmp_path, capsys):
  runs = tmp_path / "runs"
  runs.mkdir()
  pid = os.getpid()
  record = {
    "name": "gate-one",
    "detached": True,
    "exit": None,
    "started_at": None,
    "tail": [],
    "pid": pid,
    "pid_started_at": preview.process_start_identity(pid),
  }
  (runs / "gate-one.json").write_text(json.dumps(record), encoding="utf-8")
  assert preview.run_log_report(tmp_path, "gate-one") == 0
  out = capsys.readouterr().out
  assert "run gate-one running" in out  # nonemo: NMT100
  assert preview.WORKTREE_STEP in out, (
    "a live run repeats the worktree step on every logs call"
  )


def test_idle_wait_names_a_sleep_beside_a_preview_call():
  """The line decides: a sleep on its own runs, and a sleep beside a preview call waits."""
  assert preview.idle_wait("sleep 45") is None
  assert preview.idle_wait("cd /home/user/repo && sleep 5") is None
  assert preview.idle_wait("/usr/bin/sleep 2; git status") is None
  assert preview.idle_wait("for i in 1 2; do sleep 0.01; done") is None
  assert (
    preview.idle_wait("until curl -sf http://127.0.0.1:1/x; do sleep 1; done") is None
  )
  assert preview.idle_wait("grep -n sleep notes.md") is None
  assert preview.idle_wait("git status") is None
  assert preview.idle_wait("") is None
  assert preview.idle_wait("arena-preview read | tail -1") is None
  # A sleep that shares the line with a preview call holds the turn on a run.
  assert preview.idle_wait("sleep 45; arena-preview logs gate-one")
  assert preview.idle_wait("arena-preview logs gate-one; sleep 5")
  assert preview.idle_wait("sleep 1 && arena-preview poll")
  assert preview.idle_wait("until arena-preview logs gate-one; do sleep 2; done")
  # The gate hands the shell's own command line, which carries the invocation.
  assert preview.idle_wait("/bin/bash -l -c sleep 45") is None
  assert preview.idle_wait("/bin/bash -l -c sleep 45; arena-preview logs gate-one")
  assert preview.idle_wait("/bin/bash -l -c for i in 1 2; do sleep 0.01; done") is None
  assert preview.idle_wait("/bin/bash -l -c git status") is None


def test_idle_tick_blocks_a_sleep_beside_a_preview_call():
  """The hook reads the answer: a sleep alone exits 0, and a sleep beside a read exits 1."""
  with tempfile.TemporaryDirectory() as directory:
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": directory}

    def cli(line):
      return subprocess.run(
        [
          sys.executable,
          str(Path(preview.__file__)),
          "pre",
          "--line",
          line,
          "--command",
          line,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
      )

    allowed = cli("sleep 45")
    assert allowed.returncode == 0, allowed.stderr
    looped = cli("for i in 1 2; do sleep 0.01; done")
    assert looped.returncode == 0, looped.stderr
    blocked = cli("sleep 45; arena-preview logs gate-one")
    assert blocked.returncode == 130, blocked.stdout
    assert "WAIT BLOCKED" in blocked.stderr, blocked.stderr
    logged = cli("sleep 45; tail /tmp/preview.log")
    assert logged.returncode == 130, logged.stdout
    assert "SLEEP BLOCKED" in logged.stderr, logged.stderr
    reading = cli("tail -f /tmp/preview.log")
    assert reading.returncode == 0, reading.stderr


def test_pre_runs_every_rule_and_names_the_finished_steps():
  """One call answers 0 to continue, 2 to end the call and 130 to block it."""
  with tempfile.TemporaryDirectory() as directory:
    env = {
      **os.environ,
      "ARENA_PREVIEW_STATE_DIR": directory,
      "ARENA_PREVIEW_DETACH_DRY": "1",
    }

    def cli(*arguments):
      return subprocess.run(
        [sys.executable, str(Path(preview.__file__)), "pre", *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=directory,
        env=env,
      )

    platform = cli("--line", "ss -ltn", "--command", "ss -ltn")
    assert platform.returncode == 0, platform.stderr
    assert platform.stdout == ""
    plain = cli("--line", "printf hi", "--command", "printf hi")
    assert plain.returncode == 0, plain.stderr
    assert plain.stdout.strip() == '_arena_preview_done="gate"'
    again = cli("--line", "printf hi", "--command", "printf hi", "--done", "gate")
    assert again.returncode == 0, again.stderr
    assert again.stdout == ""
    blocked = cli("--line", "gh pr merge 7", "--command", "gh pr merge 7")
    assert blocked.returncode == 130
    assert "PR STATE BLOCKED" in blocked.stderr
    detached = cli("--line", "pytest -q", "--command", "pytest -q", "--repo", directory)
    assert detached.returncode == 2, detached.stderr
    assert "RUN DETACHED" in detached.stderr


def test_a_second_read_of_a_running_run_is_blocked(tmp_path, capsys):
  """One read names the live status. A second read while it runs is a wait."""
  runs = tmp_path / "runs"
  runs.mkdir()
  pid = os.getpid()
  record = {
    "name": "gate-one",
    "detached": True,
    "exit": None,
    "started_at": None,
    "tail": [],
    "pid": pid,
    "pid_started_at": preview.process_start_identity(pid),
  }
  (runs / "gate-one.json").write_text(json.dumps(record), encoding="utf-8")
  assert preview.run_log_report(tmp_path, "gate-one") == 0
  assert "run gate-one running" in capsys.readouterr().out  # nonemo: NMT100
  assert preview.run_log_report(tmp_path, "gate-one") == 130
  assert "WAIT BLOCKED" in capsys.readouterr().err
  record["exit"] = 0
  record["seconds"] = 3
  (runs / "gate-one.json").write_text(json.dumps(record), encoding="utf-8")
  assert preview.run_log_report(tmp_path, "gate-one") == 0
  assert "run gate-one done: exit 0" in capsys.readouterr().out  # nonemo: NMT100
  # A fresh run under the same name carries another stamp, so its first read stands.
  record["exit"] = None
  record["started_at"] = "2026-10-16T15:00:00+00:00"
  (runs / "gate-one.json").write_text(json.dumps(record), encoding="utf-8")
  assert preview.run_log_report(tmp_path, "gate-one") == 0
  assert "run gate-one running" in capsys.readouterr().out  # nonemo: NMT100


def test_a_blocked_read_names_the_next_task_and_its_worktree(tmp_path, capsys):
  """The blocked read says which task comes next and how to start its worktree."""
  store = preview.Store(tmp_path, create=True)
  store.write_task(
    "held-run",
    "Run under the gate",
    ["Runs under the gate."],
    status="upcoming",
    order=1,
    task_type="code",
  )
  store.write_task(
    "next-task",
    "Next file task",
    ["Waits beside the gate."],
    status="upcoming",
    order=2,
    task_type="code",
  )
  store.write_task(
    "done-task",
    "Finished task",
    ["Landed."],
    status="finished",
    order=3,
    task_type="code",
  )
  runs = tmp_path / "runs"
  runs.mkdir()
  pid = os.getpid()
  record = {
    "name": "gate-one",
    "detached": True,
    "exit": None,
    "started_at": None,
    "tail": [],
    "pid": pid,
    "pid_started_at": preview.process_start_identity(pid),
    "task": "held-run",
  }
  (runs / "gate-one.json").write_text(json.dumps(record), encoding="utf-8")
  assert preview.run_log_report(tmp_path, "gate-one") == 0
  capsys.readouterr()
  assert preview.run_log_report(tmp_path, "gate-one") == 130
  err = capsys.readouterr().err
  assert "next-task" in err
  assert "worktree start --gate gate-one" in err  # nonemo: NMT100
  assert "done-task" not in err
  assert "held-run" not in err


def test_init_tz_flag_stores_the_display_zone(tmp_path):
  store = preview.Store(tmp_path, create=True)
  store.set_meta(preview.TIMEZONE_META, "Asia/Manila")
  zone = preview.resolve_display_zone(store)
  assert zone is not None and zone.key == "Asia/Manila"


def test_the_tz_env_beats_the_stored_zone(tmp_path, monkeypatch):
  store = preview.Store(tmp_path, create=True)
  store.set_meta(preview.TIMEZONE_META, "Asia/Manila")
  monkeypatch.setenv("TZ", "UTC")
  zone = preview.resolve_display_zone(store)
  assert zone is not None and zone.key == "UTC"


def test_cli_stamps_print_in_the_display_zone_while_storage_stays_utc(monkeypatch):
  from zoneinfo import ZoneInfo

  stamp = "2026-10-15T00:39:00+00:00"
  assert preview.local_stamp(stamp) == stamp, "no zone keeps the stored UTC stamp"
  monkeypatch.setattr(preview, "DISPLAY_ZONE", ZoneInfo("Asia/Manila"))
  assert preview.local_stamp(stamp) == "2026-10-15T08:39:00+08:00"
  listing = {"checked_at": stamp, "pending": []}
  assert (
    preview.format_read(listing)
    .splitlines()[0]
    .startswith("Inbox 2026-10-15T08:39:00+08:00:")
  )
  row = {
    "id": "zone",
    "title": "Zone",
    "published_at": stamp,
    "updated_at": stamp,
    "viewed_at": stamp,
    "stale": False,
    "answers": [],
  }
  text = preview.format_report_state([row])
  for label in ("published", "updated", "viewed"):
    assert f"{label}: {preview.local_stamp(stamp)}" in text
  assert {row[key] for key in ("published_at", "updated_at", "viewed_at")} == {stamp}


def test_report_state_cli_reads_publication_and_answers(tmp_path):
  src = tmp_path / "one.md"
  src.write_text(
    "# one\n\nSelect: {#select}\n\n- ( ) yes\n- ( ) no\n", encoding="utf-8"
  )
  store = preview.Store(tmp_path / "state", create=True)
  store.publish("one", "First report", src)
  text = preview.format_report_state(store.report_state())
  assert "one First report" in text
  assert "published: 20" in text, "a published report carries its stamp"
  assert "viewed: never" in text, "an unviewed report says so"
  assert "stale: no" in text and "answers: none" in text
  solo = preview.format_report_state(store.report_state("one"))
  assert "one First report" in solo and "stale: no" in solo
  assert preview.format_report_state(store.report_state("nope")) == ""


def test_cli_hook_keeps_pending_counts_without_duplicate_routine_guidance(capsys):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    store.write_task("noise-task", "Open work", ["Keep it listed"], task_type="misc")
    script = str(Path(preview.__file__))
    for hook in ("0", "1"):
      with (
        patch.dict(
          os.environ,
          {
            "ARENA_PREVIEW_STATE_DIR": directory,
            "ARENA_PREVIEW_SHELL_HOOK": hook,
            "ARENA_PREVIEW_ROUTE": "0",
          },
        ),
        patch.object(sys, "argv", [script, "task", "list"]),
      ):
        assert preview.main() == 0
      output = capsys.readouterr()
      assert "Tasks" in output.out
      if hook == "1":
        assert output.err == "", "the active EXIT hook owns routine guidance"
      else:
        assert output.err.strip(), "standalone use retains routine guidance"
    with (
      patch.dict(
        os.environ,
        {
          "ARENA_PREVIEW_STATE_DIR": directory,
          "ARENA_PREVIEW_SHELL_HOOK": "1",
          "ARENA_PREVIEW_ROUTE": "1",
        },
      ),
      patch.object(sys, "argv", [script, "task", "list"]),
    ):
      assert preview.main() == 0
    assert capsys.readouterr().err.strip(), (
      "a detached child retains its own routine guidance"
    )
    store.note("noise-note", "Pending work")
    for hook in ("0", "1"):
      with (
        patch.dict(
          os.environ,
          {
            "ARENA_PREVIEW_STATE_DIR": directory,
            "ARENA_PREVIEW_SHELL_HOOK": hook,
            "ARENA_PREVIEW_ROUTE": "0",
          },
        ),
        patch.object(sys, "argv", [script, "task", "list"]),
      ):
        assert preview.main() == 0
      line = capsys.readouterr().err.strip()
      assert line.startswith("unacked 1 note")
      assert (" | " in line) == (hook == "0")
    with (
      patch.dict(
        os.environ,
        {
          "ARENA_PREVIEW_STATE_DIR": directory,
          "ARENA_PREVIEW_SHELL_HOOK": "1",
          "ARENA_PREVIEW_ROUTE": "0",
        },
      ),
      patch.object(sys, "argv", [script, "--reminder"]),
    ):
      assert preview.main() == 0
    line = capsys.readouterr().err.strip()
    assert "unacked 1 note | " in line, (
      "the hook still prints both urgent and routine guidance"
    )
    assert store.state()["notes"][0]["seen_at"] is None


def test_ack_task_hints_only_name_messages_without_a_task(capsys):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    store.write_task(
      "tracked-task", "Tracked work", ["Keep it tracked"], task_type="misc"
    )
    store.note("tracked-note", "Already tracked")
    store.submission("tracked-answer", "fixture-report", "Already tracked")
    store.note("free-note", "Not tracked")
    store.submission("free-answer", "fixture-report", "Not tracked")
    for record_id in ("tracked-note", "tracked-answer"):
      store.mark_task(record_id, "tracked-task")
    ids = ["tracked-note", "tracked-answer", "free-note", "free-answer"]
    script = str(Path(preview.__file__))
    with (
      patch.dict(
        os.environ,
        {"ARENA_PREVIEW_STATE_DIR": directory, "ARENA_PREVIEW_SHELL_HOOK": "0"},
      ),
      patch.object(sys, "argv", [script, "ack", *ids, "Received"]),
    ):
      assert preview.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "ok " + " ".join(record_id[:6] for record_id in ids)
    assert lines[1].startswith(
      'link it with: arena-preview task set <id> "<title>" -m '
    )
    assert "free-note" in lines[1] and "free-answer" in lines[1]
    assert "tracked-note" not in lines[1] and "tracked-answer" not in lines[1]
    with (
      patch.dict(
        os.environ,
        {"ARENA_PREVIEW_STATE_DIR": directory, "ARENA_PREVIEW_SHELL_HOOK": "0"},
      ),
      patch.object(sys, "argv", [script, "ack", "tracked-note", "Confirmed"]),
    ):
      assert preview.main() == 0
    assert capsys.readouterr().out.splitlines() == ["ok tracke"]
    assert all(
      record["acknowledged_at"]
      for record in [*store.state()["notes"], *store.submissions()]
    )


def test_skills_lists_full_yaml_descriptions_and_prefers_installed_names(capsys):
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    entries = [
      (
        ".agents/skills/shared",
        "shared",
        "description: >\n  Installed full description,\n  with a colon: preserve it.",
      ),
      ("skills/shared", "shared", 'description: "Duplicate repository entry"'),
      (
        "skills/repo-only",
        "repo-only",
        (
          "description: |\n  First line: keep it all.\n  Second line: keep this too.\n"
          "  Unicode 雙語: # metadata stays intact."
        ),
      ),
      ("skills/refs/hidden", "hidden", 'description: "Template entry"'),
    ]
    for folder, name, description in entries:
      target = root / folder / "SKILL.md"
      target.parent.mkdir(parents=True)
      target.write_text(
        f"---\nname: {name}\n{description}\n---\nDO-NOT-PRINT-THE-SKILL-BODY\n",
        encoding="utf-8",
      )
    with (
      patch.object(preview, "resolve_repo_root", return_value=str(root)),
      patch.object(
        preview, "Store", side_effect=AssertionError("listing must not open state")
      ),
      patch.object(sys, "argv", ["preview.py", "skills"]),
    ):
      assert preview.main() == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert ".agents/skills/shared/SKILL.md" in output.out
    installed = next(
      line
      for line in output.out.splitlines()
      if ".agents/skills/shared/SKILL.md" in line
    )
    repository = next(
      line for line in output.out.splitlines() if "skills/repo-only/SKILL.md" in line
    )
    assert "installed" in installed.lower(), "the source type stays beside its path"
    assert "repository" in repository.lower(), "the source type stays beside its path"
    assert (
      "Installed full description, with a colon: preserve it."  # nonemo: NMT100
      in output.out
    )
    assert "skills/repo-only/SKILL.md" in output.out
    assert "First line: keep it all." in output.out  # nonemo: NMT100
    assert "Second line: keep this too." in output.out  # nonemo: NMT100
    assert "Unicode 雙語: # metadata stays intact." in output.out  # nonemo: NMT100
    assert "Duplicate repository entry" not in output.out  # nonemo: NMT100
    assert "Template entry" not in output.out
    assert "DO-NOT-PRINT-THE-SKILL-BODY" not in output.out


def test_skills_reports_missing_yaml_dependency_instead_of_partial_parsing(capsys):
  original = builtins.__import__

  def missing_yaml(name, *args, **kwargs):
    if name == "yaml":
      raise ImportError("fixture dependency unavailable")
    return original(name, *args, **kwargs)

  with (
    patch.object(builtins, "__import__", side_effect=missing_yaml),
    patch.object(sys, "argv", ["preview.py", "skills"]),
  ):
    assert preview.main() == 1
  assert "PyYAML" in capsys.readouterr().err


def test_blocked_tasks_reject_known_reports_without_answer_fields(tmp_path):
  store = preview.Store(tmp_path / "state", create=True)
  plain = tmp_path / "plain.md"
  plain.write_text("# Information\n\nNo questions.\n", encoding="utf-8")
  store.publish("plain-report", "Information", plain)
  with pytest.raises(ValueError, match="field"):
    store.write_task(
      "new-blocked",
      "Blocked",
      ["Wait on the report"],
      blocked=True,
      report_id="plain-report",
      task_type="code",
    )
  assert store.task_record("new-blocked") is None
  linked = store.write_task(
    "linked",
    "Linked",
    ["Read the report"],
    report_id="plain-report",
    task_type="report",
  )
  assert not linked["blocked"] and linked["report_id"] == "plain-report"
  with pytest.raises(ValueError, match="field"):
    store.write_task("linked", blocked=True)
  assert not store.task_record("linked")["blocked"]
  manual = store.write_task(
    "manual",
    "Manual",
    ["Wait on an external dependency"],
    blocked=True,
    task_type="ops",
  )
  assert manual["blocked"] and manual["report_id"] is None
  questions = tmp_path / "questions.md"
  questions.write_text(
    "# Question\n\nChoose: {#select}\n\n- ( ) Yes\n- ( ) No\n", encoding="utf-8"
  )
  store.publish("question-report", "Question", questions)
  fielded = store.write_task(
    "fielded",
    "Fielded",
    ["Wait on an answer"],
    blocked=True,
    report_id="question-report",
    task_type="report",
  )
  assert fielded["blocked"]
  questions.write_text("# Information only\n", encoding="utf-8")
  store.publish("question-report", "Information now", questions)
  retained = store.write_task("fielded", title="Updated old task")
  assert retained["blocked"] and retained["report_id"] == fielded["report_id"]


def test_normal_new_task_requires_an_explicit_type():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    with pytest.raises(ValueError, match="type"):
      store.write_task("needs-type", "Needs a chosen type", ["One step"])
    assert store.list_tasks() == []


@pytest.mark.parametrize("chosen", ["report", "code", "docs", "ops", "misc"])
def test_canonical_task_type_and_omitted_update(chosen):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    record = store.write_task(
      "chosen-type", "Chosen type", ["One step"], task_type=chosen
    )
    assert record["type"] == chosen
    updated = store.write_task(record["id"], title="An amended title")
    assert updated["type"] == chosen


@pytest.mark.parametrize("legacy", ["operations", "unspecified"])
def test_normal_new_task_refuses_legacy_type_names(legacy):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    with pytest.raises(ValueError, match="type"):
      store.write_task(
        "legacy-normal", "Use the canonical name", ["One step"], task_type=legacy
      )
    assert store.list_tasks() == []


@pytest.mark.parametrize("legacy", ["operations", "unspecified"])
def test_legacy_stored_type_survives_without_other_row_changes(legacy):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    before = store.write_task(
      "legacy-type", "Preserve this row", ["One step"], task_type="report"
    )
    before = store.list_tasks()[0]
    with closing(store.connect()) as db, db:
      db.execute("UPDATE tasks SET type = ? WHERE id = ?", (legacy, before["id"]))
    migrated = preview.Store(directory)
    assert migrated.list_tasks() == [{**before, "type": legacy}]


def test_legacy_database_without_type_uses_misc():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    before = store.write_task(
      "old-schema", "Preserve this row", ["One step"], task_type="report"
    )
    before = store.list_tasks()[0]
    with closing(store.connect()) as db, db:
      db.execute("ALTER TABLE tasks DROP COLUMN type")
    migrated = preview.Store(directory)
    assert migrated.list_tasks() == [{**before, "type": "misc"}]


@pytest.mark.parametrize(
  "legacy,restored",
  [(None, "misc"), ("unspecified", "unspecified"), ("operations", "operations")],
)
def test_legacy_task_restore_preserves_supplied_types(legacy, restored):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    record = {
      "id": "old-backup",
      "title": "Restore an old task",
      "details": ["One step"],
    }
    if legacy is not None:
      record["type"] = legacy
    written = store.import_tasks([record], replace=True)
    assert written[0]["type"] == restored
    assert store.list_tasks()[0]["type"] == restored


@pytest.mark.parametrize(
  "source, expected",
  [
    ("==safe==", "<mark>safe</mark>"),
    ("==one **two**==", "<mark>one <strong>two</strong></mark>"),
    ("**==safe==**", "<strong><mark>safe</mark></strong>"),
    ("==one ~~gone~~==", "<mark>one <s>gone</s></mark>"),
    ("==[safe](https://example.com)==", '<mark><a href="https://example.com"'),
    (
      "==<script>alert(1)</script>==",
      "<mark>&lt;script&gt;alert(1)&lt;/script&gt;</mark>",
    ),
  ],
)
def test_inline_highlight_uses_safe_markdown_tokens(source, expected):
  rendered = preview.render(source)
  assert expected in rendered
  assert "<script>" not in rendered


@pytest.mark.parametrize(
  "source",
  [
    "`==code==`",
    "```text\n==code==\n```",
    r"\==literal==",
    "== unmarked ==",
    "==unclosed",
    "====",
    "[label](https://example.com/==file==)",
  ],
)
def test_inline_highlight_leaves_code_escapes_and_destinations_unchanged(source):
  rendered = preview.render(source)
  assert "<mark>" not in rendered


def test_inline_highlight_keeps_link_validation():
  rendered = preview.render("==[bad](javascript:alert(1))==")
  assert "<mark>" in rendered
  assert "href=" not in rendered


def test_report_unpublish_stale_keeps_guards_answers_and_sources(tmp_path, capsys):
  directory = tmp_path / "state"
  store = preview.Store(directory, create=True)
  store.set_meta("port", guard_port())
  plain = tmp_path / "plain.md"
  plain.write_text("# Information\n", encoding="utf-8")
  form = tmp_path / "form.md"
  form.write_text("Choose: {#select}\n\n- ( ) Yes\n- ( ) No\n", encoding="utf-8")
  store.publish("plain", "Information", plain)
  for report in ["ready", "held", "pending", "unread"]:
    store.publish(report, "Question", form)
  for report in ["ready", "held", "unread"]:
    store.submission("answer-" + report, report, "REPORT: Yes")
  for report in ["ready", "held"]:
    store.acknowledge(["answer-" + report], "Received")
  store.mark_report_ack_seen("ready")
  store.publish("tail", "More information", plain)
  for report in ("plain", "ready", "held", "tail"):
    store.write_task(
      report + "-task",
      "Done",
      ["Work"],
      status="finished",
      report_id=report,
      task_type="code",
    )
  with (
    patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": str(directory)}),
    patch.object(sys, "argv", ["preview.py", "report", "unpublish", "--stale"]),
  ):
    assert preview.main() == 1
  output = capsys.readouterr()
  assert {row["id"] for row in store.state()["reports"]} == {
    "held",
    "pending",
    "unread",
  }
  assert "ready" in output.out and "plain" in output.out
  assert any(
    line.partition("held")[2].strip(" :\t")
    for line in output.err.splitlines()
    if "held" in line
  )
  assert {row["id"] for row in store.submissions()} == {
    "answer-ready",
    "answer-held",
    "answer-unread",
  }
  assert plain.exists() and form.exists()
  with (
    patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": str(directory)}),
    patch.object(sys, "argv", ["preview.py", "report", "unpublish", "pending"]),
  ):
    assert preview.main() == 0
  assert {row["id"] for row in store.state()["reports"]} == {"held", "unread"}


def test_report_unpublish_stale_rechecks_changed_publication(tmp_path):
  directory = tmp_path / "state"
  store = preview.Store(directory, create=True)
  store.set_meta("port", guard_port())
  plain = tmp_path / "plain.md"
  plain.write_text("# Information\n", encoding="utf-8")
  form = tmp_path / "form.md"
  form.write_text("Choose: {#select}\n\n- ( ) Yes\n- ( ) No\n", encoding="utf-8")
  idle = timedelta(minutes=30)
  past = (datetime.now(timezone.utc) - idle - timedelta(seconds=1)).isoformat()
  with patch("preview.now", return_value=past):
    store.publish("changed", "Information", plain)
  original = preview.Store.stale_reports

  def changed_candidates(current):
    rows = original(current)
    current.publish("changed", "New question", form)
    return rows

  with (
    patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": str(directory)}),
    patch.object(sys, "argv", ["preview.py", "report", "unpublish", "--stale"]),
    patch.object(preview.Store, "stale_reports", changed_candidates),
  ):
    assert preview.main() == 0
  assert [row["id"] for row in store.state()["reports"]] == ["changed"]
  assert form.exists()


def test_a_missing_record_refusal_prints_on_stderr(tmp_path):
  """Every not-found line in the refusal class lands on stderr with rc 1."""
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)}

  def cli(*arguments):
    return subprocess.run(
      [sys.executable, str(Path(preview.__file__)), *arguments],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )

  report = cli("report", "state", "no-such-report")
  assert report.returncode == 1, report.stdout
  assert report.stdout == ""
  assert "no-such-report" in report.stderr
  image = cli("image-data-uri", str(tmp_path / "no-such-image.png"))
  assert image.returncode == 1, image.stdout
  assert image.stdout == ""
  assert any(line.endswith(" is not a file") for line in image.stderr.splitlines())
  renamed = cli("rename", "nope", "other")
  assert renamed.returncode == 1, renamed.stdout
  assert renamed.stdout == ""
  assert "nope" in renamed.stderr


def test_a_missing_task_names_the_task(tmp_path):
  """A task read reports its own miss, with the period the other refusals carry."""
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  cli = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "task", "show", "nothing-here"],
    capture_output=True,
    text=True,
    check=False,
    env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)},
  )
  assert cli.returncode == 1, cli.stdout
  assert cli.stdout == ""
  assert "nothing-here." in cli.stderr


def test_a_missing_state_file_names_the_path(tmp_path):
  """An unreadable import source reads as a miss, not as a raw errno."""
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  missing = tmp_path / "no-such.ndjson"
  cli = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "state", "import", str(missing)],
    capture_output=True,
    text=True,
    check=False,
    env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)},
  )
  assert cli.returncode == 1, cli.stdout
  assert cli.stdout == ""
  assert f"Preview error: No such state file: {missing}" in cli.stderr.splitlines()


def test_the_import_receipt_names_the_fate(tmp_path):
  """The receipt reports that the import replaced the live state, and merge is gone."""
  receipt = {"notes": 1, "answers": 2, "reports": 3, "tasks": 4}
  replaced = preview.format_import_receipt(receipt)
  assert replaced == (
    "Imported notes 1, answers 2, reports 3, tasks 4; the live state was replaced"
  )
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  store.note("kept-note", "Keep me")
  env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)}
  source = str(store.save_path)
  assert store.save_path.is_file(), "a state write saves the backup the import reads"
  cli = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "state", "import", source],
    capture_output=True,
    text=True,
    check=False,
    env=env,
  )
  assert cli.returncode == 0, cli.stderr
  assert cli.stdout.strip().endswith("; the live state was replaced"), cli.stdout
  rejected = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "state", "import", "--merge", source],
    capture_output=True,
    text=True,
    check=False,
    env=env,
  )
  assert rejected.returncode == 2
  assert "unrecognized arguments: --merge" in rejected.stderr  # nonemo: NMT100


def test_a_queued_download_names_the_owner_click(tmp_path):
  """The queue line reads as prose and names the Approve click that unblocks it."""
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  cli = subprocess.run(
    [
      sys.executable,
      str(Path(preview.__file__)),
      "download-request",
      "https://example.com/x",
    ],
    capture_output=True,
    text=True,
    check=False,
    env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)},
  )
  assert cli.returncode == 0, cli.stderr
  lines = cli.stdout.splitlines()
  assert re.fullmatch(
    r"Queued \S+ https://example\.com/x \(proxy off\), approval pending, status queued",
    lines[0],
  ), lines
  assert lines[1] == "Ask the owner to Approve it on the Preview page."


def test_cli_publication_persists_fields(tmp_path):
  """Publish the supplied fields and report the stored identity and count."""
  store = preview.Store(tmp_path, create=True)
  store.set_meta("port", guard_port())
  report_id = "one-report"
  source = tmp_path / "one.md"
  source.write_text("# One\n\nSelect one: {#select}\n\n- ( ) yes\n", encoding="utf-8")
  with preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store)) as server:
    store.set_meta("port", str(server.server_port))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
      cli = subprocess.run(
        [
          sys.executable,
          str(Path(preview.__file__)),
          "report",
          "publish",
          "-i",
          report_id,
          "-t",
          "One",
          str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)},
      )
      assert cli.returncode == 0, cli.stderr
      published = store.report(report_id)
      expected_fields = preview.parse_fields(source.read_text())[1]
      assert expected_fields
      assert published["id"] == report_id
      assert published["source"] == str(source.resolve())
      assert preview.parse_fields(published["markdown"])[1] == expected_fields
      assert report_id in cli.stdout
      assert str(len(expected_fields)) in cli.stdout
      assert not set(cli.stderr.splitlines()) & set(cli.stdout.splitlines())
    finally:
      server.shutdown()
      thread.join()


def test_the_run_tail_reads_one_watch_frame():
  """A repeated line keeps its last place, and the watch loop's own advice goes."""
  lines = [
    "Tests\tpending\t0\thttps://example.com/1",
    "Quality\tpass\t32s\thttps://example.com/2",
    "Refreshing checks status every 10 seconds. Press Ctrl+C to quit.",
    "Tests\tpending\t0\thttps://example.com/1",
    "Quality\tpass\t32s\thttps://example.com/2",
  ]
  assert preview.clean_run_tail(lines) == lines[:2]
  assert preview.clean_run_tail([]) == []
  assert preview.clean_run_tail(["one", "two"]) == ["one", "two"]


def test_a_repeated_run_line_prints_once(tmp_path):
  """The printed tail drops the repeated frame and the watch footer."""
  preview.Store(tmp_path, create=True).set_meta("port", guard_port())
  code = (
    "print('Tests  pass\\nQuality  pass\\nTests  pass\\nQuality  pass\\n"
    "Refreshing checks status every 10 seconds. Press Ctrl+C to quit.')"
  )
  assert (
    preview.run_command(tmp_path, "repeat", ["--", sys.executable, "-c", code]) == 0
  )
  cli = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "run", "logs", "repeat"],
    capture_output=True,
    text=True,
    check=False,
    env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(tmp_path)},
  )
  assert cli.returncode == 0, cli.stderr
  lines = cli.stdout.splitlines()
  assert lines[0].startswith("run repeat done: exit 0 "), lines
  assert lines[1:] == ["Tests  pass", "Quality  pass"], lines


def test_egress_warning_ignores_the_local_preview():
  """The preview listens on loopback, so a read of it never leaves the sandbox."""
  for line in (
    "curl -sS http://127.0.0.1:8000/api/state",
    "curl -sS http://localhost:8000/api/state",
    "curl -sS http://[::1]:8000/api/state",
  ):
    assert preview.egress_warning(line) is None, line


def test_header_interrupt_route_and_one_shot_cli(capsys):
  global app
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory) / "state", create=True)
    source = Path(directory) / "report.md"
    source.write_text("# Open report\n", encoding="utf-8")
    store.publish("open-report", "Open report", source)
    store.write_task("current-work", "Current work", ["Verify it"], task_type="code")
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    store.set_meta("port", str(app.server_port))
    threading.Thread(target=app.serve_forever, daemon=True).start()
    headers = {"Content-Type": "application/json"}
    try:
      assert request("POST", "/api/agent-interrupt", "{}")[0] == 415
      for payload, expected in [
        (
          {"tab": "notes", "report_id": "open-report"},
          "The user flagged a violation.",
        ),
        (
          {"tab": "downloads", "report_id": "open-report"},
          "The user flagged a violation.",
        ),
        (
          {"tab": "reports", "report_id": "open-report"},
          "The user flagged a violation: report open-report formatting is wrong.",
        ),
        (
          {"tab": "reports", "report_id": "missing-report"},
          "The user flagged a violation.",
        ),
        ({"tab": "reports"}, "The user flagged a violation."),
        (
          {"tab": "tasks", "report_id": "open-report"},
          "The user flagged a violation: task current-work.",
        ),
      ]:
        status, _, body = request(
          "POST", "/api/agent-interrupt", json.dumps(payload), headers
        )
        assert status == 200, body
        assert json.loads(body)["agent_interrupt_pending"]
        assert store.state()["agent_interrupt_pending"]
        note = store.pending_violation_note()
        assert note["quiet"] == 1 and note["blocking"] == 1
        assert note["text"].splitlines()[0] == expected
        capsys.readouterr()
        with (
          patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": str(store.path.parent)}),
          patch.object(
            sys,
            "argv",
            [
              str(Path(preview.__file__)),
              "pre",
              "--line",
              "printf x",
              "--command",
              "printf x",
              "--done",
              "read-set",
            ],
          ),
        ):
          # The notice no longer blocks the next call: the call-count gate does.
          assert preview.main() == 0
          message = capsys.readouterr()
          assert message.err == ""
          assert message.out.splitlines() == ['_arena_preview_done="read-set gate"']
        # The store refuses a clause-less ack, so the note stays pending.
        with pytest.raises(ValueError):
          store.acknowledge([note["id"]], "Done")
        assert store.pending_violation_note()["id"] == note["id"]
        store.acknowledge([note["id"]], "ARENA.md:1: rules")
        assert not store.state()["agent_interrupt_pending"]
        assert store.read()["pending"] == []
      store.write_task("current-work", status="finished")
      store.request_interrupt("tasks")
      note = store.pending_violation_note()
      assert note["text"].splitlines() == [
        "The user flagged a violation.",
        "The task list is empty. Maybe a task should have spawned.",
        "The call-count gate blocks after 6 unacknowledged calls.",
        "Think about which clause was violated.",
        "Read the bible if absent from context.",
        "Fix the violation, then ack with `file:ln: clause`.",
      ]
      assert store.meta_value(preview.AGENT_INTERRUPT_META) is None
      store.acknowledge([note["id"]], "ARENA.md:1: rules")
      assert (
        request("POST", "/api/agent-interrupt", '{"tab":"invalid"}', headers)[0] == 400
      )
      assert not store.state()["agent_interrupt_pending"]
      store.request_interrupt("notes")
      store.request_skip_poll()
      for payload in [
        {"tab": "notes", "armed": False},
        {"tab": "reports", "report_id": "missing-report", "armed": False},
      ]:
        status, _, body = request(
          "POST", "/api/agent-interrupt", json.dumps(payload), headers
        )
        assert status == 200, body
        assert not json.loads(body)["agent_interrupt_pending"]
        assert not store.state()["agent_interrupt_pending"]
        assert store.take_interrupt() is None
        assert store.skip_poll_requested()
      for bad in ["false", 0, None, [], {}]:
        store.request_interrupt("notes")
        status, _, _ = request(
          "POST",
          "/api/agent-interrupt",
          json.dumps({"tab": "notes", "armed": bad}),
          headers,
        )
        assert status == 400
        assert store.state()["agent_interrupt_pending"]
        store.take_interrupt()
    finally:
      app.shutdown()
      app.server_close()


def test_flag_carries_type_clause_file_and_cited_reason():
  """A flag names a page-aware type, a bible clause file and the owner's cited reason."""
  global app
  with tempfile.TemporaryDirectory() as directory:
    (Path(directory) / "ARENA.md").write_text("# Rules\n", encoding="utf-8")
    (Path(directory) / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    nested = Path(directory) / "pkg"
    nested.mkdir()
    (nested / "AGENTS.md").write_text("# Package agents\n", encoding="utf-8")
    store = preview.Store(Path(directory) / "state", create=True)
    source = Path(directory) / "report.md"
    source.write_text("# Open report\n", encoding="utf-8")
    store.publish("open-report", "Open report", source)
    store.write_task("current-work", "Current work", ["Verify it"], task_type="code")
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    threading.Thread(target=app.serve_forever, daemon=True).start()
    headers = {"Content-Type": "application/json"}
    try:
      read_set = ["ARENA.md", "AGENTS.md", "pkg/AGENTS.md"]
      assert preview.read_set_files(store.repository_root()) == read_set
      assert store.state()["read_set"] == read_set
      closing = [
        "The call-count gate blocks after 6 unacknowledged calls.",
        "Think about which clause was violated.",
        "Read the bible if absent from context.",
        "Fix the violation, then ack with `file:ln: clause`.",
      ]

      def clear_flag():
        """Ack the pending violation note, which clears the page flag with it."""
        store.acknowledge([store.pending_violation_note()["id"]], "ARENA.md:1: rules")

      status, _, body = request(
        "POST",
        "/api/agent-interrupt",
        json.dumps(
          {
            "tab": "reports",
            "report_id": "open-report",
            "reason": "format-violation",
            "clause_file": "AGENTS.md",
            "note": "  Heading\nlevels  ",
          }
        ),
        headers,
      )
      assert status == 200, body
      assert json.loads(body)["agent_interrupt_pending"]
      flag = json.loads(store.meta_value(preview.AGENT_INTERRUPT_FLAG_META))
      assert {name: flag[name] for name in ("type", "clause_file", "note")} == {
        "type": "format-violation",
        "clause_file": "AGENTS.md",
        "note": "Heading levels",
      }
      note = store.pending_violation_note()
      assert flag["id"] == note["id"]
      assert note["type"] == "format-violation"
      assert note["text"].splitlines() == [
        "User flagged violation: format-violation. Cited: Heading levels",
        "Report: open-report",
        *closing,
      ]
      clear_flag()
      assert store.meta_value(preview.AGENT_INTERRUPT_FLAG_META) is None
      for payload, lines in [
        (
          {"tab": "notes", "reason": "bash-violation"},
          ["User flagged violation: bash-violation.", *closing],
        ),
        (
          {"tab": "tasks", "reason": "current-task-violation"},
          [
            "User flagged violation: current-task-violation.",
            "Current task: current-work. Is this what you are working on?",
            *closing,
          ],
        ),
        (
          {"tab": "tasks", "reason": "empty-task-list"},
          [
            "User flagged violation: empty-task-list.",
            "The task list is empty. Maybe a task should have spawned.",
            *closing,
          ],
        ),
      ]:
        status, _, body = request(
          "POST", "/api/agent-interrupt", json.dumps(payload), headers
        )
        assert status == 200, body
        assert store.pending_violation_note()["text"].splitlines() == lines
        clear_flag()
      long_note = "x" * 500
      status, _, body = request(
        "POST",
        "/api/agent-interrupt",
        json.dumps({"tab": "notes", "reason": "bash-violation", "note": long_note}),
        headers,
      )
      assert status == 200, body
      assert long_note in store.pending_violation_note()["text"]
      clear_flag()
      for payload, field in [
        ({"tab": "notes", "reason": "not-a-type"}, "reason"),
        ({"tab": "reports", "reason": "bash-violation"}, "reason"),
        (
          {"tab": "notes", "reason": "bash-violation", "clause_file": "docs/STYLE.md"},
          "clause_file",
        ),
        ({"tab": "notes", "reason": "bash-violation", "note": 123}, "note"),
      ]:
        status, _, body = request(
          "POST", "/api/agent-interrupt", json.dumps(payload), headers
        )
        assert status == 400, body
        assert field in json.loads(body)["error"]
        assert not store.state()["agent_interrupt_pending"]
    finally:
      app.shutdown()
      app.server_close()


def test_ack_has_one_flagless_markdown_input(capsys):
  """Inline Markdown uses the same rendered receipt for notes and report answers."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    store.note("inline-note", "Question")
    store.submission("inline-answer", "form", "REPORT form: answer")
    text = "**Received** `without flags`"
    with (
      patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": directory}),
      patch.object(sys, "argv", [preview.__file__, "ack", "inline-note", text]),
    ):
      assert preview.main() == 0
    with (
      patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": directory}),
      patch.object(sys, "argv", [preview.__file__, "ack", text]),
      patch("sys.stdin.read", side_effect=AssertionError("Unexpected stdin read")),
    ):
      assert preview.main() == 0
    note = store.state()["notes"][0]
    answer = store.submissions()[0]
    assert note["ack_type"] == answer["ack_type"] == "reply"
    assert note["ack_text"] == answer["ack_text"] == text
    assert store.read()["pending"] == []
    stamp = "2026-10-17T00:00:00"
    store.note(
      "legacy-note",
      "Old question",
      acknowledged_at=stamp,
      ack_type="note",
      ack_text="**Keep plain**",
      replies=[{"type": "note", "text": "`Old plain reply`", "at": stamp}],
    )
    store.acknowledge(["legacy-note"], text)
    legacy = next(row for row in store.state()["notes"] if row["id"] == "legacy-note")
    assert legacy["ack_type"] == "note" and legacy["ack_text"] == "**Keep plain**"
    assert [row["type"] for row in legacy["replies"]] == ["note", "reply"]
    server = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
      client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
      client.request("GET", "/api/state")
      response = client.getresponse()
      assert response.status == 200
      rows = {row["id"]: row for row in json.loads(response.read())["notes"]}
      client.close()
      assert "<strong>Received</strong>" in rows["inline-note"]["ack_html"]
      old = rows["legacy-note"]
      assert "ack_html" not in old and "html" not in old["replies"][0]
      assert "<strong>Received</strong>" in old["replies"][1]["html"]
    finally:
      server.shutdown()
      server.server_close()
    for flag in [
      "--reply",
      "--note",
      "--reply-file",
      "--note-file",
      "-r",
      "-n",
      "-R",
      "-N",
    ]:
      with (
        patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": directory}),
        patch.object(sys, "argv", [preview.__file__, "ack", "inline-note", flag, text]),
        pytest.raises(SystemExit) as error,
      ):
        preview.main()
      assert error.value.code != 0
    assert store.state()["notes"][0]["replies"] == []
    capsys.readouterr()


def test_linked_upload_paths_are_complete_idempotent_and_atomic():
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / ("workspace-" + "x" * preview.TASK_STEP_MAX)
    store = preview.Store(root, create=True)
    store.set_meta("port", guard_port())
    note = store.note_with_uploads(
      "upload-note",
      "Use both files",
      [
        ("first file.txt", "text/plain", b"one"),
        ("second.bin", "application/octet-stream", b"two"),
      ],
    )
    paths = [item["path"] for item in note["attachments"]]
    assert all(len(path) > preview.TASK_STEP_MAX for path in paths)
    before_note = store.state()["notes"][0]
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": str(root)}

    def cli(*args):
      return subprocess.run(
        [sys.executable, str(Path(preview.__file__)), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
      )

    result = cli(
      "task",
      "set",
      "uploaded-work",
      "Use uploads",
      "--scope",
      "arena suite",
      "--details",
      "Keep this step",
      "--type",
      "code",
      "--msg-id",
      note["id"],
    )
    assert result.returncode == 0, result.stderr
    details = store.task_record("uploaded-work")["details"]
    assert details[:2] == ["Scope: arena suite", "Keep this step"]
    for path in paths:
      assert sum(path in step for step in details) == 1
      assert path in result.stdout
    after_note = store.state()["notes"][0]
    assert after_note["task_id"] == "uploaded-work"
    for key in ("id", "text", "acknowledged_at", "seen_at", "attachments"):
      assert after_note[key] == before_note[key]
    repeated = cli("task", "set", "uploaded-work", "--msg-id", note["id"])
    assert repeated.returncode == 0, repeated.stderr
    assert store.task_record("uploaded-work")["details"] == details
    boundary = cli(
      "task",
      "set",
      "boundary-work",
      "Boundary",
      "--scope",
      "arena suite",
      "--type",
      "code",
      "--details",
      "x" * preview.TASK_STEP_MAX,
    )
    assert boundary.returncode == 0, boundary.stderr
    assert store.task_record("boundary-work")["details"] == [
      "Scope: arena suite",
      "x" * preview.TASK_STEP_MAX,
    ]
    ordinary = cli(
      "task",
      "set",
      "ordinary-work",
      "Ordinary",
      "--scope",
      "arena suite",
      "--type",
      "code",
      "--details",
      "Attachment: " + "x" * preview.TASK_STEP_MAX,
    )
    assert ordinary.returncode != 0
    assert store.task_record("ordinary-work") is None
    store.write_task(
      "full-work",
      "Full task",
      [f"Step {i}" for i in range(preview.MAX_TASK_DETAILS)],
      task_type="code",
    )
    untouched = store.note_with_uploads(
      "full-note", "Must keep this marker empty", [("file.txt", "text/plain", b"three")]
    )
    before_task = store.task_record("full-work")
    before_full_note = next(
      item for item in store.state()["notes"] if item["id"] == untouched["id"]
    )
    refused = cli("task", "set", "full-work", "--msg-id", untouched["id"])
    assert refused.returncode != 0
    assert store.task_record("full-work") == before_task
    assert (
      next(item for item in store.state()["notes"] if item["id"] == untouched["id"])
      == before_full_note
    )

    oversized = store.note_with_uploads(
      "oversized-note", "Keep storage caps", [("file.txt", "text/plain", b"four")]
    )
    before_oversized = next(
      item for item in store.state()["notes"] if item["id"] == oversized["id"]
    )
    with (
      patch.dict(os.environ, env),
      patch.object(
        sys,
        "argv",
        [
          str(Path(preview.__file__)),
          "task",
          "set",
          "oversized-work",
          "Oversized",
          "--scope",
          "arena suite",
          "--type",
          "code",
          "--details",
          "Keep this step",
          "--msg-id",
          oversized["id"],
        ],
      ),
      patch.object(
        preview, "MAX_TASK_DETAIL", len(oversized["attachments"][0]["path"])
      ),
    ):
      assert preview.main() != 0
    assert store.task_record("oversized-work") is None
    assert (
      next(item for item in store.state()["notes"] if item["id"] == oversized["id"])
      == before_oversized
    )


def test_preview_order_survives_agent_updates_and_notifies_the_next_hook():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    for task_id in ("first", "second", "third"):
      store.write_task(task_id, task_id, ["A step"], task_type="code")
    store.write_task("third", order=1)
    store.reorder_tasks(["first", "third"])
    ordered = [task["id"] for task in store.list_tasks()]
    before = store.task_record("third")
    with pytest.raises(ValueError, match="order"):
      store.write_task("third", title="Must roll back", order=1)
    assert store.task_record("third") == before
    store.write_task("third", details=["Updated step"])
    store.write_task("third", order=store.task_record("third")["order"])
    assert [task["id"] for task in store.list_tasks()] == ordered
    store.write_task("new", "New task", ["A step"], task_type="code")
    assert [task["id"] for task in store.list_tasks()][:-1] == ordered
    assert preview.TASK_ORDER_NOTICE not in store.reminder(routine=False)
    live_detached_placeholder(directory, "order-check", ["bash", "-c", "true"])
    command = [sys.executable, str(Path(preview.__file__)), "--reminder"]
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": directory}
    listing = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "task", "list"],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert listing.returncode == 0, listing.stderr
    assert preview.TASK_ORDER_NOTICE not in listing.stdout + listing.stderr
    first = subprocess.run(
      command, capture_output=True, text=True, check=False, env=env
    )
    assert first.returncode == 0, first.stderr
    assert preview.TASK_ORDER_NOTICE in first.stderr
    assert first.stdout == ""
    second = subprocess.run(
      command, capture_output=True, text=True, check=False, env=env
    )
    assert second.returncode == 0, second.stderr
    assert preview.TASK_ORDER_NOTICE not in second.stderr + second.stdout
    rejected = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "task",
        "set",
        "third",
        "--order",
        "1",
      ],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert rejected.returncode != 0
    assert "order" in rejected.stderr.lower()
    assert [task["id"] for task in store.list_tasks()] == ordered + ["new"]
    with pytest.raises(ValueError, match="order"):
      store.write_task("third", order=1)
    store.write_task("third", status="finished", order=1)
    store.write_task("third", status="upcoming")
    store.import_tasks([store.task_record("third") | {"order": 1}])
    assert store.list_tasks()[0]["id"] == "third"


def test_ack_task_cli_commits_both_records_or_neither(capsys):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    store.note("first-note", "First request")
    store.note("second-note", "Second request")
    options = [
      "--id",
      "first-job",
      "--title",
      "First job",
      "--type",
      "code",
      "--scope",
      "arena suite",
      "--detail",
      "Do the work",
    ]

    def call(ids, extra):
      with (
        patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": directory}),
        patch.object(
          sys, "argv", [str(Path(preview.__file__)), "ack", *ids, "Received", *extra]
        ),
      ):
        result = preview.main()
      capsys.readouterr()
      return result

    for ids, extra in [
      ([], options),
      (["first-note", "second-note"], options),
      (["first-note"], options[:-2]),
      (["first-note"], options[:-4] + options[-2:]),
      (["first-note"], options[:-1] + ["x" * (preview.TASK_STEP_MAX + 1)]),
      (["missing-note"], options),
    ]:
      assert call(ids, extra) == 1
      assert store.task_record("first-job") is None
      assert all(row["acknowledged_at"] is None for row in store.state()["notes"])
    with patch.object(
      preview.Store, "mark_task", side_effect=ValueError("write failed")
    ):
      assert call(["first-note"], options) == 1
    assert store.task_record("first-job") is None
    assert all(row["acknowledged_at"] is None for row in store.state()["notes"])
    assert call(["first-note"], options) == 0
    rows = {row["id"]: row for row in store.state()["notes"]}
    assert rows["first-note"]["ack_text"] == "Received"
    assert rows["first-note"]["task_id"] == "first-job"
    assert rows["second-note"]["acknowledged_at"] is None
    assert store.task_record("first-job")["type"] == "code"
    assert call(["second-note"], []) == 0
    assert store.task_record("first-job")["details"] == [
      "Scope: arena suite",
      "Do the work",
    ]


@pytest.mark.parametrize(
  "markdown, expected",
  [
    ("~~bad ~~", [{"line": 1, "marker": "~~"}]),
    ("== bad==", [{"line": 1, "marker": "=="}]),
    ("==bad ==", [{"line": 1, "marker": "=="}]),
    ("~~good~~ ==good==", []),
    ("`~~bad ~~ == bad==`", []),
    ("```text\n~~bad ~~ == bad==\n```", []),
    (r"\~\~bad \~\~ \=\= bad\=\=", []),
    ("# Heading\n\nFirst\n~~bad ~~", [{"line": 4, "marker": "~~"}]),
    ("| A | B |\n|---|---|\n| text | ~~bad ~~ |", [{"line": 3, "marker": "~~"}]),
    ("`~~bad ~~\ncode`\n~~bad ~~", [{"line": 3, "marker": "~~"}]),
    pytest.param("\\```text\n~~bad ~~\n\\```", [], id="escaped-fence"),
    pytest.param(
      "| A | B |\n|---|---|\n| a\\|b ~~bad ~~ | text |",
      [{"line": 3, "marker": "~~"}],
      id="escaped-table-pipe",
    ),
    pytest.param(
      '| Line | Diff |\n|---|---|\n| 255 | "files==, and `cd` here==." |',
      [{"line": 3, "marker": "=="}],
      id="flanking-punctuation-and-inline-code",
    ),
  ],
)
def test_report_marker_warnings_preserve_markdown(markdown, expected):
  before = preview.render(markdown)
  assert preview.report_marker_warnings(markdown) == expected
  assert preview.render(markdown) == before


@pytest.mark.parametrize(
  "warnings, expected",
  [
    (None, []),
    ([], []),
    ("invalid", []),
    (
      [
        {"line": 3, "marker": "~~"},
        {"line": True, "marker": "~~"},
        {"line": -1, "marker": "=="},
        {"line": 3, "marker": "other"},
        None,
      ],
      [{"line": 3, "marker": "~~"}],
    ),
  ],
)
def test_publication_verification_checks_state_and_rendered_revision(
  warnings, expected
):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.set_meta("port", guard_port())
    revision = "2026-10-19T03:00:00.123456+00:00"
    state = {
      "reports": [{"id": "check-report", "updated_at": preview.clip_stamp(revision)}],
      "token": "do-not-print",
    }
    rendered = {"html": "<p>Question</p>", "fields": 1, "revision": revision}
    if warnings is not None:
      rendered["warnings"] = warnings
    for first, second, valid in [
      (state, rendered, True),
      ({"reports": []}, rendered, False),
      ({"reports": [{"id": "check-report", "updated_at": "old"}]}, rendered, False),
      (state, {**rendered, "revision": "old"}, False),
      (state, {**rendered, "fields": 0}, False),
      (state, {**rendered, "fields": True}, False),
      (state, {**rendered, "html": None}, False),
      ([], rendered, False),
      (state, [], False),
    ]:
      with patch("http.client.HTTPConnection") as factory:
        client = factory.return_value
        client.getresponse.return_value.status = 200
        client.getresponse.return_value.read.side_effect = [
          json.dumps(first).encode(),
          json.dumps(second).encode(),
        ]
        if valid:
          with patch.dict(sys.modules, {"markdown_it": None}):
            result = preview.verify_publication(store, "check-report", revision, 1)
          assert result == expected
          assert [call.args[1] for call in client.request.call_args_list] == [
            "/api/state",
            "/api/reports/check-report/html",
          ]
        else:
          with pytest.raises((ValueError, TypeError), match="verification"):
            preview.verify_publication(store, "check-report", revision, 1)


def test_publish_cli_distinguishes_rejection_from_failed_verification(capsys):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "report.md"
    source.write_text("Choose? {#choice}\n- ( ) yes\n- ( ) no\n\n~~bad ~~\n", "utf-8")
    with preview.ThreadingHTTPServer(
      ("127.0.0.1", 0), preview.handler(store)
    ) as server:
      store.set_meta("port", str(server.server_port))
      thread = threading.Thread(target=server.serve_forever, daemon=True)
      thread.start()

      def publish(path, *extra):
        with (
          patch.dict(os.environ, {"ARENA_PREVIEW_STATE_DIR": directory}),
          patch.object(
            sys,
            "argv",
            [
              str(Path(preview.__file__)),
              "report",
              "publish",
              str(path),
              "--id",
              "verified-report",
              "--title",
              "Report",
              *extra,
            ],
          ),
        ):
          result = preview.main()
        return result, capsys.readouterr()

      try:
        result, output = publish(Path(directory) / "missing.md")
        assert result == 1 and "Published" not in output.out
        assert store.state()["reports"] == []
        result, output = publish(source)
        assert result == 1 and "Published" not in output.out
        expected_location = f"{source}:5:"
        assert expected_location in output.err
        assert "--allow-unparsed-markers" in output.err
        assert store.state()["reports"] == []
        with patch(
          "preview.verify_publication",
          side_effect=ValueError("Publication verification failed"),
        ):
          result, output = publish(source, "--allow-unparsed-markers")
        assert result == 1 and "Published" not in output.out
        assert store.report("verified-report")["title"] == "Report"
        with patch(
          "preview.verify_publication", wraps=preview.verify_publication
        ) as verified:
          result, output = publish(source, "-u")
        assert result == 0 and verified.called
        assert expected_location in output.err
        assert store.report("verified-report")["markdown"] == source.read_text()
        published = store.report("verified-report")
        assert published["id"] in output.out
        assert (
          preview.parse_fields(published["markdown"])[1]
          == preview.parse_fields(source.read_text())[1]
        )
      finally:
        server.shutdown()
        thread.join()


def test_every_preview_cli_option_has_a_shorthand():
  captured = []
  original_init = preview.PreviewArgumentParser.__init__

  def track_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    captured.append(self)

  with (
    patch.object(preview.PreviewArgumentParser, "__init__", track_init),
    patch.object(
      preview.PreviewArgumentParser,
      "parse_args",
      side_effect=SystemExit(0),
    ),
    pytest.raises(SystemExit),
  ):
    preview.main()

  missing = []
  for subparser in captured:
    for action in subparser._actions:
      if not action.option_strings:
        continue
      has_short = any(
        opt.startswith("-") and not opt.startswith("--") and len(opt) == 2
        for opt in action.option_strings
      )
      has_long = any(opt.startswith("--") for opt in action.option_strings)
      if not (has_short and has_long):
        missing.append((subparser.prog, action.option_strings))
  assert not missing, f"CLI options missing short or long flag: {missing}"


def test_user_flagged_report_violation_mints_a_quiet_note(capsys):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "report.md"
    source.write_text("# Report\n", encoding="utf-8")
    store.publish("flagged-report", "Flagged report", source)
    store.request_interrupt("reports", report_id="flagged-report")

    result = preview.pre_command(
      directory, "git status", "git status", directory, shell="bash"
    )

    output = capsys.readouterr()
    assert result == 0
    assert output.err == ""
    assert output.out.startswith('_arena_preview_done="')
    note = store.pending_violation_note()
    assert note["quiet"] == 1 and note["blocking"] == 1
    assert note["text"].splitlines() == [
      "The user flagged a violation: report flagged-report formatting is wrong.",
      "The call-count gate blocks after 6 unacknowledged calls.",
      "Think about which clause was violated.",
      "Read the bible if absent from context.",
      "Fix the violation, then ack with `file:ln: clause`.",
    ]


def test_new_violation_types_cover_both_tabs():
  """The three new types land on both tabs, with the shared evidence line."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory) / "state", create=True)
    (Path(directory) / "ARENA.md").write_text("# Rules\n", encoding="utf-8")
    for tab in ("notes", "tasks"):
      for reason in ("missing-details", "out-of-scope", "task-not-created"):
        assert reason in preview.VIOLATION_TYPES[tab]
    store.write_task("current-work", "Current work", ["Verify it"], task_type="code")
    for reason in ("missing-details", "out-of-scope", "task-not-created"):
      store.request_interrupt("tasks", reason=reason)
      note = store.pending_violation_note()
      assert note["text"].splitlines()[:2] == [
        f"User flagged violation: {reason}.",
        "Current task: current-work. Is this what you are working on?",
      ]
      store.acknowledge([note["id"]], "ARENA.md:1: Rules")
      store.request_interrupt("notes", reason=reason)
      note = store.pending_violation_note()
      assert note["text"].splitlines()[0] == f"User flagged violation: {reason}."
      store.acknowledge([note["id"]], "ARENA.md:1: Rules")


def test_the_page_offers_every_type_the_server_accepts():
  """The flag modal reads app.js, so each tab's list matches the server list."""
  source = (
    Path(preview.__file__).resolve().parent.parent / "assets" / "app.js"
  ).read_text(encoding="utf-8")
  block = source[source.index("const VIOLATION_TYPES = {") :]
  block = block[: block.index("\n};")]
  parts = re.split(r"\n  (\w+): ", block)
  offered = dict(zip(parts[1::2], parts[2::2]))
  for tab, types in preview.VIOLATION_TYPES.items():
    assert re.findall(r"\['([a-z-]+)'", offered[tab]) == list(types), tab


def test_repeat_poll_notice_keeps_system_wording_and_stderr(capsys, monkeypatch):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    moment = iter((1000, 1001))
    monkeypatch.setattr(preview, "poll_clock", lambda: next(moment))
    # Only a poll that returned at once arms the repeat window.
    store.set_meta(preview.POLL_IMMEDIATE_META, "1")
    assert preview.poll_repeat(store) is None
    assert preview.poll_repeat(store).startswith("VIOLATION:")

    result = preview.pre_command(
      directory, "printf x", "printf x", directory, shell="bash"
    )

    output = capsys.readouterr()
    # The notice no longer blocks the call. The call-count gate blocks later.
    assert result == 0
    assert output.err == ""
    assert output.out.startswith('_arena_preview_done="')
    note = store.pending_violation_note()
    assert note["text"].startswith("VIOLATION\n")
    assert "This Bash call was blocked" not in note["text"]
    assert "The call-count gate blocks after 6 unacknowledged calls." in note["text"]


@pytest.mark.parametrize("already_pending", (False, True))
def test_preview_violation_wakes_poll_and_delivers_full_inbox(capsys, already_pending):
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    form = Path(directory) / "form.md"
    form.write_text("Answer: ___\n", encoding="utf-8")
    store.publish("form", "Form", form)
    delivered = []

    def flag_during_wait(_):
      store.request_interrupt("notes")
      store.note("owner-note", "Owner work")
      store.note("quiet-note", "Quiet information", quiet=True)
      store.note(
        "request-note",
        "Answer request",
        quiet=True,
        blocking=True,
        type="survey",
      )
      store.submission("report-answer", "form", "REPORT form: Answer")
      delivered.extend(store.read()["pending"])

    if already_pending:
      flag_during_wait(None)
    with (
      patch("preview.pr_check_watch"),
      patch("preview.run_notices", return_value=False),
    ):
      assert preview.poll_inbox(store, sleeper=flag_during_wait) == 0
    output = capsys.readouterr().out
    for item in delivered:
      assert preview.format_pending_item(item) in output
    assert "arena-preview read" not in output  # nonemo: NMT100
    records = store.state()["notes"] + store.submissions()
    assert {item["id"] for item in records} == {item["id"] for item in delivered}
    assert all(item["seen_at"] is not None for item in records)
    assert all(item["acknowledged_at"] is None for item in records)
    assert store.report("form")["agent_seen_at"] is not None
    assert store.pending_violation_note() is not None
    assert not store.gate(pending_only=True)
    assert not store.polling()


def test_poll_failed_delivery_leaves_violation_unseen():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.request_interrupt("notes")
    with (
      patch("preview.pr_check_watch"),
      patch("preview.run_notices", return_value=False),
      patch.object(sys.stdout, "write", side_effect=OSError("dropped delivery")),
      pytest.raises(OSError, match="dropped delivery"),
    ):
      preview.poll_inbox(store)
    assert store.pending_violation_note()["seen_at"] is None
    assert not store.polling()


def test_userscript_autosave_confirms_only_closed_file_receipts():
  global app
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.note("saved-note", "Keep this state")
    with preview.ThreadingHTTPServer(
      ("127.0.0.1", 0), preview.handler(store)
    ) as server:
      app = server
      thread = threading.Thread(target=server.serve_forever, daemon=True)
      thread.start()
      try:
        status, _, body = request("GET", "/api/state")
        auth = {
          "Content-Type": "application/json",
        }
        status, _, body = request("GET", "/api/userscript-autosave")
        assert status == 200
        first = json.loads(body)
        assert first["save_id"] and first["digest"] and first["core"]
        assert first["history"] == []
        status, _, _ = request(
          "POST", "/api/userscript-autosave", json.dumps(first), auth
        )
        assert status == 200
        assert (
          request("POST", "/api/userscript-autosave", json.dumps(first), auth)[0] == 200
        )
        status, _, body = request("GET", "/api/userscript-autosave")
        second = json.loads(body)
        assert second["save_id"] != first["save_id"]
        assert len(second["history"]) == 1
        assert second["history"][0]["save_id"] == first["save_id"]
        assert second["lastsave"] == first["stamp"]
        assert second["beforelastsave"] is None
        bad = {**second, "digest": "0" * 64}
        assert (
          request("POST", "/api/userscript-autosave", json.dumps(bad), auth)[0] == 400
        )
        for invalid in (
          {**first, "save_id": 42},
          {**first, "scope": {"repo": "other", "branch": ""}},
          {**first, "stamp": "bad timestamp"},
          {**first, "core": first["history"] + [{"type": "userscript-autosave"}]},
        ):
          assert (
            request("POST", "/api/userscript-autosave", json.dumps(invalid), auth)[0]
            == 400
          )
        comparison = {
          "baseline": {
            "lastsave": second["lastsave"],
            "beforelastsave": second["beforelastsave"],
            "scope": second["scope"],
            "core": first["core"],
          },
          "scope": second["scope"],
          "core": second["core"],
        }
        status, _, body = request(
          "POST", "/api/userscript-autosave/compare", json.dumps(comparison), auth
        )
        answer = json.loads(body)
        assert status == 200 and answer["result"] == "equal"
        assert answer["candidate_stamp"] == second["stamp"]
        assert answer["lastsave"] == first["stamp"]
        assert answer["beforelastsave"] is None
        assert set(answer) == {
          "result",
          "candidate_stamp",
          "lastsave",
          "beforelastsave",
          "baseline_stamp",
          "counts",
        }
        assert (
          len(json.loads(request("GET", "/api/userscript-autosave")[2])["history"]) == 1
        )
        assert (
          "userscript-autosave"
          not in json.loads(request("GET", "/api/copy-state")[2])["text"]
        )
        confirmed = [first["save_id"]]
        for index in range(3):
          store.note(f"later-note-{index}", f"Later state {index}")
          snapshot = json.loads(request("GET", "/api/userscript-autosave")[2])
          assert (
            request("POST", "/api/userscript-autosave", json.dumps(snapshot), auth)[0]
            == 200
          )
          confirmed.append(snapshot["save_id"])
        current = json.loads(request("GET", "/api/userscript-autosave")[2])
        assert [row["save_id"] for row in current["history"]] == confirmed[-2:]
        assert all("history" not in row for row in current["history"])
        assert (
          request("POST", "/api/userscript-autosave", json.dumps(first), auth)[0] == 200
        )
        assert (
          json.loads(request("GET", "/api/userscript-autosave")[2])["history"]
          == current["history"]
        )
        assert all(row.get("stamp") for row in current["history"])
        assert current["lastsave"] == current["history"][-1]["stamp"]
        assert current["beforelastsave"] == current["history"][-2]["stamp"]
        known = {
          "lastsave": current["lastsave"],
          "beforelastsave": current["beforelastsave"],
          "scope": current["scope"],
          "core": current["core"],
        }
        latest = {
          "baseline": known,
          "scope": current["scope"],
          "core": current["core"],
        }
        status, _, body = request(
          "POST", "/api/userscript-autosave/compare", json.dumps(latest), auth
        )
        answer = json.loads(body)
        assert status == 200 and answer["result"] == "equal"
        assert answer["candidate_stamp"] == current["stamp"]
        older = {
          "baseline": {
            **known,
            "lastsave": current["beforelastsave"],
            "beforelastsave": None,
          },
          "scope": current["scope"],
          "core": current["core"],
        }
        status, _, body = request(
          "POST", "/api/userscript-autosave/compare", json.dumps(older), auth
        )
        assert status == 200 and json.loads(body)["result"] == "unknown-baseline"
        tampered = {
          "baseline": {**known, "core": []},
          "scope": current["scope"],
          "core": current["core"],
        }
        status, _, body = request(
          "POST", "/api/userscript-autosave/compare", json.dumps(tampered), auth
        )
        assert status == 200 and json.loads(body)["result"] == "unknown-baseline"
        missing = {
          "save_id": first["save_id"],
          "scope": first["scope"],
          "digest": first["digest"],
        }
        fallback = {
          "baseline": missing,
          "scope": current["scope"],
          "core": current["core"],
        }
        status, _, body = request(
          "POST", "/api/userscript-autosave/compare", json.dumps(fallback), auth
        )
        assert status == 200 and json.loads(body)["result"] == "unknown-baseline"
        with tempfile.TemporaryDirectory() as imported_directory:
          imported = preview.Store(imported_directory, create=True)
          imported.import_state(current["text"])
          assert imported.userscript_history() == current["history"]
        original_scope = store.userscript_scope
        with patch.object(
          store, "userscript_scope", return_value={**first["scope"], "branch": "other"}
        ):
          other = json.loads(request("GET", "/api/userscript-autosave")[2])
          assert other["history"] == []
          assert (
            request("POST", "/api/userscript-autosave", json.dumps(other), auth)[0]
            == 200
          )
          assert (
            request("POST", "/api/userscript-autosave", json.dumps(first), auth)[0]
            == 400
          )
          assert (
            len(json.loads(request("GET", "/api/userscript-autosave")[2])["history"])
            == 1
          )
        assert store.userscript_scope() == original_scope()
        assert (
          json.loads(request("GET", "/api/userscript-autosave")[2])["history"]
          == current["history"]
        )
        comparison = {
          "baseline": {
            "lastsave": current["lastsave"],
            "beforelastsave": current["beforelastsave"],
            "scope": current["scope"],
          },
          "scope": current["scope"],
          "core": [],
        }
        status, _, body = request(
          "POST", "/api/userscript-autosave/compare", json.dumps(comparison), auth
        )
        assert (
          status == 200 and json.loads(body)["result"] == "candidate-missing-records"
        )
        comparison["scope"] = {"repo": "other", "branch": "other"}
        status, _, body = request(
          "POST", "/api/userscript-autosave/compare", json.dumps(comparison), auth
        )
        assert status == 200 and json.loads(body)["result"] == "scope-mismatch"
        store.import_state(first["text"])
        assert (
          json.loads(request("GET", "/api/userscript-autosave")[2])["history"]
          == current["history"]
        )
        store.import_state(second["text"])
        assert (
          json.loads(request("GET", "/api/userscript-autosave")[2])["history"]
          == second["history"]
        )
        records = [
          json.loads(line) for line in current["text"].splitlines() if line.strip()
        ]
        histories = [row for row in records if row.get("type") == "userscript-autosave"]
        assert len(histories) == 2
        baseline_text = json.loads(request("GET", "/api/copy-state")[2])["text"]
        for field, value in (("digest", "0" * 64), ("history", []), ("save_id", 42)):
          original = dict(histories[0])
          histories[0][field] = value
          with pytest.raises((ValueError, TypeError)):
            store.import_state("\n".join(json.dumps(row) for row in records))
          assert (
            json.loads(request("GET", "/api/copy-state")[2])["text"] == baseline_text
          )
          histories[0].clear()
          histories[0].update(original)
        histories[1]["receipts"][histories[0]["save_id"]] = "0" * 64
        with pytest.raises(ValueError):
          store.import_state("\n".join(json.dumps(row) for row in records))
        histories[1]["receipts"][histories[0]["save_id"]] = histories[0]["digest"]
        histories[0]["version"] = 999
        before = json.loads(request("GET", "/api/copy-state")[2])["text"]
        with pytest.raises(ValueError):
          store.import_state("\n".join(json.dumps(row) for row in records))
        assert json.loads(request("GET", "/api/copy-state")[2])["text"] == before
        store.import_state(second["text"])
        restored = json.loads(request("GET", "/api/userscript-autosave")[2])
        assert [row["save_id"] for row in restored["history"]] == [first["save_id"]]
      finally:
        server.shutdown()
        thread.join()


def test_autosave_compare_matches_each_retained_save():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    with patch("preview.now", return_value="2026-10-19T07:00:00.000001+00:00"):
      store.note("first-note", "First")
    first = store.userscript_snapshot()
    assert store.confirm_userscript_save(first)["confirmed"]
    with patch("preview.now", return_value="2026-10-19T07:00:01.000001+00:00"):
      store.note("second-note", "Second")
    second = store.userscript_snapshot()
    assert store.confirm_userscript_save(second)["confirmed"]
    history = store.userscript_history()
    assert len(history) == 2
    fresh = store.userscript_snapshot()
    assert fresh["lastsave"] == history[-1]["stamp"]
    assert fresh["beforelastsave"] == history[-2]["stamp"]
    assert fresh["lastsave"] != fresh["beforelastsave"]
    older = {
      "baseline": {
        "lastsave": fresh["beforelastsave"],
        "beforelastsave": None,
        "scope": fresh["scope"],
        "core": first["core"],
      },
      "scope": fresh["scope"],
      "core": fresh["core"],
    }
    answer = store.compare_userscript_save(older)
    assert answer["result"] == "unknown-baseline", answer
    equal = {
      "baseline": {
        "lastsave": fresh["lastsave"],
        "beforelastsave": fresh["beforelastsave"],
        "scope": fresh["scope"],
        "core": fresh["core"],
      },
      "scope": fresh["scope"],
      "core": fresh["core"],
    }
    answer = store.compare_userscript_save(equal)
    assert answer["result"] == "equal", answer
    assert answer["candidate_stamp"] == fresh["stamp"]
    assert answer["lastsave"] == fresh["lastsave"]
    assert answer["beforelastsave"] == fresh["beforelastsave"]
    with patch("preview.now", return_value="2026-10-19T07:00:02.000001+00:00"):
      store.note("third-note", "Third")
    third = store.userscript_snapshot()
    changed = {**equal, "core": third["core"]}
    answer = store.compare_userscript_save(changed)
    assert answer["result"] == "different", answer
    assert answer["candidate_stamp"] == third["stamp"]
    assert "digest" not in json.dumps(answer)


def test_task_autosave_confirmation_keeps_candidate_stamp():
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    with patch("preview.now", return_value="2026-10-19T08:34:00.000000+00:00"):
      store.write_task("task", "Task", ["Step"], task_type="misc")
    with patch("preview.now", return_value="2026-10-19T08:34:52.922405+00:00"):
      candidate = store.userscript_snapshot()
    receipt = {key: candidate[key] for key in ("save_id", "scope", "digest", "core")}
    receipt.update(lastsave=candidate["stamp"], beforelastsave=candidate["lastsave"])
    with patch("preview.now", return_value="2026-10-19T08:34:53.662658+00:00"):
      assert store.confirm_userscript_save(receipt)["confirmed"]
    current = store.userscript_snapshot()
    assert current["lastsave"] == candidate["stamp"]
    assert current["beforelastsave"] is None
    with tempfile.TemporaryDirectory() as restored_directory:
      restored = preview.Store(restored_directory, create=True)
      restored.import_state(current["text"])
      assert restored.userscript_history()[-1]["stamp"] == candidate["stamp"]


def test_report_autosave_confirmation_preserves_source_and_digest():
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / "report.md"
    source.write_text("# Report\n\nBody.\n", encoding="utf-8")
    store = preview.Store(root / "arena-state", create=True)
    with patch("preview.now", return_value="2026-10-22T09:47:00.000000+00:00"):
      store.publish("saved-report", "Saved", source)
    snapshot = store.userscript_snapshot()
    report_rows = [row for row in snapshot["core"] if row.get("id") == "saved-report"]
    assert len(report_rows) == 1
    assert report_rows[0]["source"] == str(source)
    assert preview.autosave_core(snapshot["core"]) == snapshot["core"]
    receipt = {key: snapshot[key] for key in ("save_id", "scope", "digest", "core")}
    receipt.update(lastsave=snapshot["stamp"], beforelastsave=snapshot["lastsave"])
    assert store.confirm_userscript_save(receipt)["confirmed"]


def test_autosave_core_is_idempotent_across_task_order():
  core = [
    {
      "id": f"task-{index}",
      "title": f"Task {index}",
      "details": ["Step"],
      "status": "finished",
      "completed_at": f"2026-01-0{4 - index}T00:00:00+00:00",
      "order": order,
      "type": "misc",
    }
    for index, order in enumerate((3, 4, 2, 1))
  ]
  once = preview.autosave_core(core)
  twice = preview.autosave_core(once)
  assert once == twice, "the canonical core is stable across a second pass"
  assert preview.autosave_digest(once) == preview.autosave_digest(twice)


def test_websocket_transport(tmp_path, monkeypatch):
  monkeypatch.setattr(preview, "WS_TICK_SECONDS", 0.02, raising=False)
  monkeypatch.setattr(preview, "WS_HEARTBEAT_SECONDS", 0.1, raising=False)
  store = preview.Store(tmp_path / "state", create=True)
  frame_handler = preview.handler(store)
  send_frame = frame_handler.ws_send

  def send_with_heartbeat(handler, opcode, data):
    if opcode in (8, 10):
      send_frame(handler, 1, b'{"type":"heartbeat"}')
    send_frame(handler, opcode, data)

  monkeypatch.setattr(frame_handler, "ws_send", send_with_heartbeat)
  server = preview.ThreadingHTTPServer(("127.0.0.1", 0), frame_handler)
  worker = threading.Thread(target=server.serve_forever, daemon=True)
  worker.start()
  peers = []

  def connect(origin=None):
    peer = socket.create_connection(server.server_address, timeout=3)
    peers.append(peer)
    host = f"127.0.0.1:{server.server_port}"
    nonce = base64.b64encode(bytes(range(16))).decode()
    peer.sendall(
      (
        f"GET /api/ws HTTP/1.1\r\nHost: {host}\r\n"
        "Connection: keep-alive, Upgrade\r\nUpgrade: websocket\r\n"
        f"Sec-WebSocket-Key: {nonce}\r\nSec-WebSocket-Version: 13\r\n"
        f"Origin: {origin or 'http://' + host}\r\n\r\n"
      ).encode()
    )
    stream = peer.makefile("rb")
    status = int(stream.readline().split()[1])
    headers = {}
    while (line := stream.readline()) not in (b"\r\n", b""):
      name, value = line.decode().split(":", 1)
      headers[name.lower()] = value.strip()
    return peer, stream, status, headers

  def send(peer, payload, opcode=1, final=True, masked=True):
    data = (
      payload
      if isinstance(payload, bytes)
      else json.dumps(payload, ensure_ascii=False).encode()
    )
    size = len(data)
    header = bytes([(0x80 if final else 0) | opcode])
    flag = 0x80 if masked else 0
    header += (
      bytes([flag | size])
      if size < 126
      else bytes([flag | 126]) + size.to_bytes(2, "big")
    )
    mask = b"mask"
    peer.sendall(
      header
      + (mask if masked else b"")
      + bytes(value ^ (mask[i % 4] if masked else 0) for i, value in enumerate(data))
    )

  def receive(peer, stream, type=None, request_id=None, control=False):
    for _ in range(30):
      head = stream.read(2)
      assert len(head) == 2
      opcode, size = head[0] & 15, head[1] & 127
      assert not head[1] & 128
      if size in (126, 127):
        size = int.from_bytes(stream.read(2 if size == 126 else 8), "big")
      data = stream.read(size)
      if opcode != 1:
        return opcode, data
      value = json.loads(data)
      if value.get("type") == "change" and type != "change":
        continue
      if control:
        continue
      if value.get("type") == "heartbeat":
        send(peer, {"type": "pong"})
      if (type is None or value.get("type") == type) and (
        request_id is None or value.get("id") == request_id
      ):
        return value
    raise AssertionError("Missing WebSocket event")

  try:
    for origin in ("https://elsewhere.invalid", "https://["):
      denied, stream, status, _ = connect(origin)
      assert status == 403
      stream.close()
      denied.close()
    peer, stream, status, headers = connect()
    assert status == 101
    expected = base64.b64encode(
      hashlib.sha1(
        base64.b64encode(bytes(range(16))) + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
      ).digest()
    ).decode()
    assert headers["sec-websocket-accept"] == expected
    assert receive(peer, stream, "change")["type"] == "change"
    send(
      peer,
      {
        "id": "write",
        "method": "POST",
        "path": "/api/notes",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"id": "ws-note", "text": "socket write"}),
      },
    )
    answer = receive(peer, stream, "response", "write")
    assert answer["status"] == 201 and json.loads(answer["body"])["id"] == "ws-note"
    preview.Store(tmp_path / "state").note("cli-note", "independent connection")
    receive(peer, stream, "change")
    send(peer, {"id": "read", "method": "GET", "path": "/api/state"})
    state = json.loads(receive(peer, stream, "response", "read")["body"])
    assert {"ws-note", "cli-note"} <= {note["id"] for note in state["notes"]}
    assert receive(peer, stream, "heartbeat")["type"] == "heartbeat"
    fragmented = json.dumps(
      {"id": "fragment", "method": "GET", "path": "/api/state"}
    ).encode()
    send(peer, fragmented[:8], final=False)
    send(peer, b"ping", opcode=9)
    assert receive(peer, stream, control=True) == (10, b"ping")
    send(peer, fragmented[8:], opcode=0)
    assert receive(peer, stream, "response", "fragment")["status"] == 200
    send(peer, b"{}", masked=False)
    opcode, data = receive(peer, stream, control=True)
    assert opcode == 8 and int.from_bytes(data[:2], "big") == 1002
    stream.close()
    peer.close()
    peer, stream, status, _ = connect()
    assert status == 101
    receive(peer, stream, "change")
    send(peer, b"\xff")
    opcode, data = receive(peer, stream, control=True)
    assert opcode == 8 and int.from_bytes(data[:2], "big") == 1007
    stream.close()
    for payload, opcode, expected in [
      (b"bytes", 2, 1003),
      (b"x" * 126, 9, 1002),
      (b"{}", 0, 1002),
    ]:
      peer, stream, status, _ = connect()
      assert status == 101
      receive(peer, stream, "change")
      send(peer, payload, opcode=opcode)
      code, data = receive(peer, stream, control=True)
      assert code == 8 and int.from_bytes(data[:2], "big") == expected
      stream.close()
      peer.close()
    peer, stream, status, _ = connect()
    assert status == 101
    receive(peer, stream, "change")
    peer.sendall(
      b"\x81\xff" + (preview.WS_MAX_MESSAGE + 1).to_bytes(8, "big") + b"mask"
    )
    code, data = receive(peer, stream, control=True)
    assert code == 8 and int.from_bytes(data[:2], "big") == 1009
    stream.close()
  finally:
    for peer in peers:
      peer.close()
    server.shutdown()
    worker.join()
    server.server_close()


def test_a_staged_upload_waits_for_its_note():
  """A staged file stays out of state until a note binds it."""
  with tempfile.TemporaryDirectory() as staged_dir:
    store = preview.Store(staged_dir, create=True)
    staged = store.stage_upload("plan.txt", "text/plain", b"abc", "stage01")
    assert staged["id"] == "stage01" and staged["note_id"] is None
    assert store.uploads() == [] and store.state()["uploads"] == []
    note = store.note_with_staged("note-01", "One file", ["stage01"])
    assert [item["name"] for item in note["attachments"]] == ["plan.txt"]
    assert Path(note["attachment_path"]).read_bytes() == b"abc"
    assert [item["id"] for item in store.uploads()] == ["stage01"]
    again = store.note_with_staged("note-01", "One file", ["stage01"])
    assert again["attachments"] == note["attachments"]
    assert len(store.uploads()) == 1


def test_a_staged_upload_drops_until_it_is_bound():
  """A staged file drops once, and a bound file never drops."""
  with tempfile.TemporaryDirectory() as drop_dir:
    store = preview.Store(drop_dir, create=True)
    staged = store.stage_upload("plan.txt", "text/plain", b"abc", "stage01")
    path = Path(staged["path"])
    assert store.drop_staged("stage01") == {"dropped": "stage01"}
    assert not path.exists() and store.uploads() == []
    try:
      store.drop_staged("stage01")
      raise AssertionError("A second drop must fail")
    except ValueError:
      pass
    store.stage_upload("plan.txt", "text/plain", b"abc", "stage02")
    store.note_with_staged("note-02", "One file", ["stage02"])
    try:
      store.drop_staged("stage02")
      raise AssertionError("A bound file must not drop")
    except ValueError:
      pass


def test_http_staged_upload_binds_and_drops():
  """The staged endpoints keep the file out of state until the send binds it."""
  global app
  with tempfile.TemporaryDirectory() as staged_http_dir:
    staged_http = preview.Store(staged_http_dir, create=True)
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(staged_http))
    worker = threading.Thread(target=app.serve_forever, daemon=True)
    worker.start()
    try:
      boundary = b"preview-stage-test"

      def part(name, content, extra=b""):
        return (
          b"--"
          + boundary
          + b'\r\nContent-Disposition: form-data; name="'
          + name
          + b'"'
          + extra
          + b"\r\n\r\n"
          + content
          + b"\r\n"
        )

      closing = b"--" + boundary + b"--\r\n"
      headers = {
        "Content-Type": "multipart/form-data; boundary=preview-stage-test",
      }
      body = (
        part(b"id", b"stage01")
        + part(b"file", b"abc", b'; filename="a.txt"\r\nContent-Type: text/plain')
        + closing
      )
      status, _, payload = request("POST", "/api/uploads", body, headers)
      staged = json.loads(payload)
      assert status == 201 and staged["id"] == "stage01" and staged["note_id"] is None
      assert staged_http.state()["uploads"] == []
      assert (
        request("POST", "/api/uploads", b"{}", {"Content-Type": "application/json"})[0]
        == 415
      )
      body = json.dumps(
        {"id": "note-01", "text": "One file", "upload_ids": ["stage01"]}
      ).encode()
      status, _, payload = request(
        "POST", "/api/notes", body, {"Content-Type": "application/json"}
      )
      note = json.loads(payload)
      assert status == 201 and note["attachment_name"] == "a.txt"
      assert [item["id"] for item in staged_http.uploads()] == ["stage01"]
      second = (
        part(b"id", b"stage02")
        + part(b"file", b"xyz", b'; filename="b.txt"\r\nContent-Type: text/plain')
        + closing
      )
      assert request("POST", "/api/uploads", second, headers)[0] == 201
      status, _, payload = request(
        "POST",
        "/api/uploads/stage02/drop",
        b"{}",
        {"Content-Type": "application/json"},
      )
      assert status == 200 and json.loads(payload) == {"dropped": "stage02"}
      assert [item["id"] for item in staged_http.state()["uploads"]] == ["stage01"]
    finally:
      app.shutdown()
      app.server_close()
      worker.join()


def test_bare_path_reminder_distinguishes_invocations_from_arguments(tmp_path, capsys):
  state = tmp_path / "state"
  preview.Store(state, create=True)
  source = "/workspace/skills/arena-skill/scripts/preview.py"
  wrapper = "/workspace/skills/arena-skill/scripts/arena-preview"
  cases = (
    (f"sed -n '1,20p' {source}", False),
    (f"rg -n Store {source}", False),
    (f"test -f '{source}'", False),
    (f"command -v {wrapper}", False),
    (f"printf '%s' '{source} read'", False),
    (f'''python3 -c "print('{source}')"''', False),
    (f"{wrapper} read", True),
    (f"'{wrapper}' read", True),
    (f"python3 '{source}' read", True),
    (f"env SAMPLE=1 python3 -u {source} read", True),
    (f"bash -c 'python3 {source} read'", True),
    (f"printf ready; {wrapper} read", True),
    ("'/workspace with spaces/scripts/arena-preview' read", True),
  )
  for command, expected in cases:
    result = preview.pre_command(
      state, command, command, tmp_path, done="read-set", shell="bash"
    )
    output = capsys.readouterr()
    assert result == 0, command
    assert ("bare" in output.out) == expected, command
    assert bool(output.err) == expected, command


def test_recommended_options_prefix_ui_and_print_on_publish(
  tmp_path, monkeypatch, capsys
):
  state = tmp_path / "state"
  report = tmp_path / "report.md"
  report.write_text(
    "Select a strategy: {#strategy}\n"
    "- ( ) Alpha\n"
    "- (x) Beta\n"
    "- ( ) Gamma\n\n"
    "Include extras: {#extras}\n"
    "- [x] Logs\n"
    "- [ ] Metrics\n",
    encoding="utf-8",
  )
  _blocks, questions = preview.parse_fields(report.read_text("utf-8"))
  assert len(questions) == 2
  choice_html = preview.field_html(questions[0])
  assert 'value="Beta" checked> <span>* Beta</span></label>' in choice_html
  assert 'value="Alpha"> <span>Alpha</span></label>' in choice_html
  checkbox_html = preview.field_html(questions[1])
  assert 'value="Logs" checked> <span>* Logs</span></label>' in checkbox_html
  assert 'value="Metrics"> <span>Metrics</span></label>' in checkbox_html

  preview.Store(state, create=True)
  monkeypatch.setattr(preview, "resolve_state_dir", lambda: state)
  monkeypatch.setattr(preview, "require_server", lambda store: None)
  monkeypatch.setattr(preview, "verify_publication", lambda *args: [])
  monkeypatch.setattr(
    sys,
    "argv",
    [
      "arena-preview",
      "report",
      "publish",
      str(report),
      "--id",
      "rec-report",
      "--title",
      "Recommended Report",
    ],
  )
  assert preview.main() == 0
  output = capsys.readouterr()
  assert (
    "you recommended:\nSelect a strategy: Beta\nInclude extras: Logs\n" in output.out
  )


def test_python_outline_command_parses_symbols_and_enforces_guards(
  tmp_path, monkeypatch, capsys
):
  repo = tmp_path / "repo"
  (repo / ".git").mkdir(parents=True)
  marker = tmp_path / "executed.txt"
  sample = repo / "pkg" / "sample.py"
  sample.parent.mkdir(parents=True)
  sample.write_text(
    "from pathlib import Path\n"
    f"Path({str(marker)!r}).write_text('ran', encoding='utf-8')\n\n"
    "@decorator_one\n"
    "def top_fn(alpha: int, beta: str = 'x', *args, flag: bool = True, **kwargs) -> str:\n"
    "  def inner_helper(step: int = 1) -> int:\n"
    "    return step + alpha\n"
    "  return beta\n\n"
    "class Worker(BaseWorker):\n"
    "  @classmethod\n"
    "  def build(cls, name: str) -> 'Worker':\n"
    "    return cls()\n\n"
    "  async def run(self, limit: int = 5) -> None:\n"
    "    pass\n\n"
    "  class Nested:\n"
    "    def ping(self) -> bool:\n"
    "      return True\n",
    encoding="utf-8",
  )
  monkeypatch.chdir(repo)

  result = preview.outline_file(sample, repo_root=repo)
  assert not marker.exists()
  assert result["language"] == "python"
  assert result["path"] == "pkg/sample.py"
  assert result["total"] == 7
  assert result["omitted"] == 0
  by_name = {entry["qualified_name"]: entry for entry in result["entries"]}
  assert list(by_name) == [
    "top_fn",
    "top_fn.inner_helper",
    "Worker",
    "Worker.build",
    "Worker.run",
    "Worker.Nested",
    "Worker.Nested.ping",
  ]
  assert by_name["top_fn"]["type"] == "function"
  assert by_name["top_fn"]["decorators"] == ["@decorator_one"]
  assert by_name["top_fn"]["line"] == 4
  assert by_name["top_fn"]["def_line"] == 5
  assert by_name["top_fn"]["end_line"] == 8
  assert (
    by_name["top_fn"]["signature"]
    == "def top_fn(alpha: int, beta: str = 'x', *args, flag: bool = True, **kwargs) -> str"
  )
  assert by_name["Worker"]["type"] == "class"
  assert by_name["Worker"]["signature"] == "class Worker(BaseWorker)"
  assert by_name["Worker.build"]["type"] == "method"
  assert by_name["Worker.run"]["type"] == "async_method"
  assert (
    by_name["Worker.run"]["signature"] == "async def run(self, limit: int = 5) -> None"
  )

  monkeypatch.setattr(
    sys,
    "argv",
    ["arena-preview", "outline", "pkg/sample.py", "--max-entries", "3", "--json"],
  )
  assert preview.main() == 0
  payload = json.loads(capsys.readouterr().out)
  assert payload["total"] == 7
  assert payload["omitted"] == 4
  assert [item["qualified_name"] for item in payload["entries"]] == [
    "top_fn",
    "top_fn.inner_helper",
    "Worker",
  ]

  monkeypatch.setattr(
    sys, "argv", ["arena-preview", "outline", "pkg/sample.py", "--max-entries", "2"]
  )
  assert preview.main() == 0
  text_out = capsys.readouterr().out
  assert "pkg/sample.py (python, 2/7 symbols, 5 omitted)" in text_out
  assert "4-8 top_fn" in text_out
  assert "5 more symbols omitted" in text_out

  broken = repo / "broken.py"
  broken.write_text("def broken(:\n  pass\n", encoding="utf-8")
  monkeypatch.setattr(sys, "argv", ["arena-preview", "outline", "broken.py"])
  assert preview.main() == 1
  err = capsys.readouterr().err
  assert "broken.py:1:" in err and "syntax error" in err.lower()

  outside = tmp_path / "outside.py"
  outside.write_text("def secret():\n  pass\n", encoding="utf-8")
  monkeypatch.setattr(sys, "argv", ["arena-preview", "outline", str(outside)])
  assert preview.main() == 1
  assert "repository" in capsys.readouterr().err.lower()

  escape_link = repo / "escape.py"
  escape_link.symlink_to(outside)
  monkeypatch.setattr(sys, "argv", ["arena-preview", "outline", "escape.py"])
  assert preview.main() == 1
  assert "repository" in capsys.readouterr().err.lower()

  oversized = repo / "huge.py"
  oversized.write_bytes(b"x = 1\n" * ((preview.OUTLINE_MAX_BYTES // 6) + 10))
  monkeypatch.setattr(sys, "argv", ["arena-preview", "outline", "huge.py"])
  assert preview.main() == 1
  assert str(preview.OUTLINE_MAX_BYTES) in capsys.readouterr().err


def test_html_tag_navigation_parses_landmarks_forms_and_ranges(
  tmp_path, monkeypatch, capsys
):
  repo = tmp_path / "repo"
  (repo / ".git").mkdir(parents=True)
  page = repo / "ui" / "index.html"
  page.parent.mkdir(parents=True)
  page.write_text(
    "<!doctype html>\n"
    '<html lang="en">\n'
    "  <head>\n"
    "    <title>Preview Console</title>\n"
    '    <link rel="stylesheet" href="/style.css">\n'
    "  </head>\n"
    "  <body>\n"
    '    <header id="top-bar" class="bar" role="banner">\n'
    "      <h1>Steering</h1>\n"
    '      <nav aria-label="Primary">\n'
    '        <button id="tab-inbox" class="tab active" type="button" data-tab="inbox">Inbox</button>\n'
    "      </nav>\n"
    "    </header>\n"
    '    <main id="main-view">\n'
    '      <section id="composer-panel" class="panel" aria-label="Composer">\n'
    '        <form id="note-form" action="/api/note" method="post">\n'
    '          <textarea id="note-input" name="note"></textarea>\n'
    '          <input type="hidden" name="token" value="secret">\n'
    '          <button id="send-btn" type="submit">Send</button>\n'
    "        </form>\n"
    "      </section>\n"
    '      <div id="status-toast" role="status"><span>Ignored plain span</span></div>\n'
    "      <div><p>Plain anonymous wrapper excluded</p></div>\n"
    "    </main>\n"
    "  </body>\n"
    "</html>\n",
    encoding="utf-8",
  )
  monkeypatch.chdir(repo)

  result = preview.outline_file(page, repo_root=repo)
  assert result["language"] == "html"
  assert result["path"] == "ui/index.html"
  assert result["omitted"] == 0
  by_label = {entry["label"]: entry for entry in result["entries"]}
  assert "header#top-bar.bar" in by_label
  assert by_label["header#top-bar.bar"]["type"] == "landmark"
  assert by_label["header#top-bar.bar"]["line"] == 8
  assert by_label["header#top-bar.bar"]["end_line"] == 13
  assert by_label["header#top-bar.bar"]["attributes"]["role"] == "banner"

  assert "button#tab-inbox.tab.active" in by_label
  assert by_label["button#tab-inbox.tab.active"]["type"] == "interactive"
  assert by_label["button#tab-inbox.tab.active"]["attributes"]["data-tab"] == "inbox"

  assert "form#note-form" in by_label
  assert by_label["form#note-form"]["type"] == "form"
  assert by_label["form#note-form"]["line"] == 16
  assert by_label["form#note-form"]["end_line"] == 20
  assert by_label["form#note-form"]["attributes"]["action"] == "/api/note"

  assert "input[name=token]" in by_label
  assert by_label["input[name=token]"]["line"] == 18
  assert by_label["input[name=token]"]["end_line"] == 18
  assert "value" not in by_label["input[name=token]"]["attributes"]

  assert "div#status-toast" in by_label
  assert not any(entry["tag"] in ("span", "p") for entry in result["entries"])

  monkeypatch.setattr(
    sys,
    "argv",
    ["arena-preview", "outline", "ui/index.html", "--max-entries", "4"],
  )
  assert preview.main() == 0
  text_out = capsys.readouterr().out
  assert "ui/index.html (html, 4/" in text_out
  assert "tags," in text_out
  assert "more tags omitted" in text_out


def test_javascript_outline_command_parses_symbols_and_reports_fallbacks(
  tmp_path, monkeypatch, capsys
):
  repo = tmp_path / "repo"
  repo.mkdir()
  (repo / ".git").mkdir()
  src = repo / "src"
  src.mkdir()

  mod = src / "widget.mjs"
  mod.write_text(
    'import { helper } from "./helper.mjs";\n'
    "export const DEFAULT_LIMIT = 25;\n"
    "export class Widget extends BaseWidget {\n"
    "  constructor(name, options = {}) {\n"
    "    super(name);\n"
    "  }\n"
    "  async load(url) {\n"
    "    function normalize(raw) {\n"
    "      return String(raw).trim();\n"
    "    }\n"
    "    return normalize(url);\n"
    "  }\n"
    "  [Symbol.iterator]() {\n"
    "    return [][Symbol.iterator]();\n"
    "  }\n"
    "}\n"
    "export const formatLabel = async (prefix, item = 'x') => `${prefix}:${item}`;\n"
    "export default function renderWidget(target) {\n"
    "  return target;\n"
    "}\n",
    encoding="utf-8",
  )

  cjs = src / "legacy.cjs"
  cjs.write_text(
    "const VERSION = 1;\n"
    "function buildLegacy(flag) {\n"
    "  return flag ? VERSION : 0;\n"
    "}\n"
    "module.exports = { VERSION, buildLegacy };\n",
    encoding="utf-8",
  )

  for candidate in (Path.cwd().resolve(), *Path(__file__).resolve().parents):
    if (candidate / "node_modules").is_dir():
      (repo / "node_modules").symlink_to(candidate / "node_modules")
      break
  monkeypatch.chdir(repo)
  result = preview.outline_file(mod, repo_root=repo)
  assert result["language"] == "javascript"
  assert result["path"] == "src/widget.mjs"
  assert result["omitted"] == 0
  by_qual = {entry["qualified_name"]: entry for entry in result["entries"]}

  assert "DEFAULT_LIMIT" in by_qual
  assert by_qual["DEFAULT_LIMIT"]["type"] == "binding"
  assert by_qual["DEFAULT_LIMIT"]["line"] == 2

  assert "Widget" in by_qual
  assert by_qual["Widget"]["type"] == "class"
  assert by_qual["Widget"]["line"] == 3
  assert by_qual["Widget"]["end_line"] == 16
  assert "extends BaseWidget" in by_qual["Widget"]["signature"]

  assert "Widget.constructor" in by_qual
  assert by_qual["Widget.constructor"]["type"] == "method"
  assert by_qual["Widget.constructor"]["line"] == 4
  assert by_qual["Widget.constructor"]["end_line"] == 6

  assert "Widget.load" in by_qual
  assert by_qual["Widget.load"]["type"] == "async_method"
  assert by_qual["Widget.load"]["line"] == 7
  assert by_qual["Widget.load"]["end_line"] == 12

  assert "Widget.load.normalize" in by_qual
  assert by_qual["Widget.load.normalize"]["type"] == "function"
  assert by_qual["Widget.load.normalize"]["line"] == 8
  assert by_qual["Widget.load.normalize"]["end_line"] == 10

  assert "Widget.[Symbol.iterator]" in by_qual
  assert by_qual["Widget.[Symbol.iterator]"]["type"] == "method"

  assert "formatLabel" in by_qual
  assert by_qual["formatLabel"]["type"] == "async_function"
  assert by_qual["formatLabel"]["line"] == 17

  assert "renderWidget" in by_qual
  assert by_qual["renderWidget"]["type"] == "function"
  assert by_qual["renderWidget"]["line"] == 18
  assert by_qual["renderWidget"]["end_line"] == 20

  cjs_result = preview.outline_file(cjs, repo_root=repo)
  cjs_names = {entry["qualified_name"]: entry for entry in cjs_result["entries"]}
  assert "VERSION" in cjs_names
  assert "buildLegacy" in cjs_names

  monkeypatch.setattr(
    preview,
    "discover_portable_parsers",
    lambda parser_dir=None: {
      "acorn": None,
      "css_tree": None,
      "message": "portable parsers not installed",
    },
  )
  fallback_repo_result = preview.outline_file(mod, repo_root=repo)
  assert len(fallback_repo_result["entries"]) == len(result["entries"])

  sortable_license = (
    Path(__file__).resolve().parent.parent / "assets" / "sortable.LICENSE"
  ).read_text(encoding="utf-8")
  assert "MIT License" in sortable_license
  assert "All contributors to Sortable" in sortable_license
  gsap_license = (
    Path(__file__).resolve().parent.parent / "assets" / "gsap.LICENSE"
  ).read_text(encoding="utf-8")
  assert "GreenSock" in gsap_license
  index_html = (
    Path(__file__).resolve().parent.parent / "assets" / "index.html"
  ).read_text(encoding="utf-8")
  assert 'id="image-modal"' in index_html
  assert 'id="image-modal-close"' in index_html
  assert 'id="image-modal-img" alt="" draggable="false"' in index_html
  style_css = (
    Path(__file__).resolve().parent.parent / "assets" / "style.css"
  ).read_text(encoding="utf-8")
  assert "left: 50%; transform: translateX(-50%);" in style_css
  assert ".report-toolbar .select-wrap { flex: 1 1 100%; }" not in style_css
  assert (
    '.topbar:has(~ main #reports-panel[data-loading="true"]:not([hidden]))::after'
    in style_css
  )
  assert '#modal:not([data-keyboard-nav="true"]) :focus-visible' in style_css

  mermaid_md = "# Flow\n\n```mermaid\nflowchart TD\n  A[One] --> B[Two]\n```\n"
  mermaid_html, mermaid_fields = preview.render_report(mermaid_md)
  assert not mermaid_fields
  assert 'class="language-mermaid"' in mermaid_html
  assert 'class="copy-code"' in mermaid_html
  assert "A[One] --&gt; B[Two]" in mermaid_html

  broken = src / "broken.js"
  broken.write_text("function broken( {\n  return 1;\n}\n", encoding="utf-8")
  with pytest.raises(ValueError, match=r"src/broken\.js:\d+:.*JavaScript syntax error"):
    preview.outline_file(broken, repo_root=repo)

  empty_parsers = tmp_path / "empty-parsers"
  empty_parsers.mkdir()
  with pytest.raises(ValueError, match="JavaScript outline unavailable"):
    preview.outline_file(mod, repo_root=repo, parser_dir=empty_parsers)

  monkeypatch.setattr(
    sys,
    "argv",
    ["arena-preview", "outline", "src/widget.mjs", "--max-entries", "3"],
  )
  assert preview.main() == 0
  text_out = capsys.readouterr().out
  assert "src/widget.mjs (javascript, 3/" in text_out
  assert "symbols," in text_out
  assert "more symbols omitted" in text_out


def test_survey_rejects_null_partial_and_zero_confidence_known_answers():
  import survey

  blank = survey.template()
  assert blank[0]["answer"] == {"reasoning": False}
  assert blank[1]["answer"] == {"image_in": False}
  assert blank[3]["answer"] == {
    "command_name": "unknown",
    "concurrency_option": "unknown",
  }
  parsed_blank = survey.loads(json.dumps(blank))
  assert [row["known"] for row in parsed_blank] == [
    True,
    True,
    False,
    False,
    False,
  ]

  with_null = survey.template()
  with_null[3]["answer"]["command_name"] = None
  with pytest.raises(ValueError, match="must not be null"):
    survey.loads(json.dumps(with_null))

  partial = survey.template()
  partial[2]["answer"]["organization"] = "Test Org"
  partial[2]["confidence"] = 0.5
  with pytest.raises(ValueError, match="fill every field or set all fields to unknown"):
    survey.loads(json.dumps(partial))

  zero_conf = survey.template()
  zero_conf[3]["answer"] = {
    "command_name": "Rebuild",
    "concurrency_option": "Online",
  }
  zero_conf[3]["confidence"] = 0
  with pytest.raises(ValueError, match="greater than zero"):
    survey.loads(json.dumps(zero_conf))

  lower_conf = survey.template()
  lower_conf[0]["answer"] = {"reasoning": True}
  lower_conf[2]["answer"] = {
    "full_name": "Example Person",
    "organization": "Test Org",
    "role": "Shift lead",
  }
  lower_conf[2]["confidence"] = 0.4
  graded = survey.grade(json.dumps(lower_conf))
  assert graded[0] == {"id": "R3S0N", "correct": True, "confidence": 1}
  assert graded[1] == {"id": "I4M6G", "correct": False, "confidence": 1}
  assert graded[3] == {"id": "A2P6R", "correct": None, "confidence": 0}
  assert graded[2]["id"] == "S2E5P"
  assert graded[2]["confidence"] == 0.4
  assert isinstance(graded[2]["correct"], bool)


def test_portable_parser_installer_handles_fresh_reuse_missing_npm_and_failure(
  tmp_path,
):
  tool_dir = tmp_path / "parsers"
  missing = preview.discover_portable_parsers(tool_dir)
  assert not missing["available"]
  assert "install.sh" in missing["message"]

  no_npm = preview.install_portable_parsers(tool_dir, which=lambda name: None)
  assert no_npm["status"] == "skipped"
  assert not no_npm["available"]
  assert (tool_dir / "package.json").is_file()
  assert (tool_dir / "package-lock.json").is_file()
  manifest = json.loads((tool_dir / "package.json").read_text(encoding="utf-8"))
  assert manifest["dependencies"] == {"acorn": "8.18.0", "css-tree": "3.2.1"}

  calls = []

  def fake_failed_runner(cmd, **kwargs):
    calls.append(cmd)
    return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="registry offline")

  failed = preview.install_portable_parsers(
    tool_dir,
    which=lambda name: f"/usr/bin/{name}",
    runner=fake_failed_runner,
  )
  assert failed["status"] == "failed"
  assert not failed["available"]
  assert "registry offline" in failed["message"]
  assert len(calls) == 1

  def fake_success_runner(cmd, **kwargs):
    calls.append(cmd)
    acorn_dir = tool_dir / "node_modules" / "acorn" / "dist"
    acorn_dir.mkdir(parents=True, exist_ok=True)
    (acorn_dir / "acorn.js").write_text("module.exports = {};\n", encoding="utf-8")
    (tool_dir / "node_modules" / "acorn" / "package.json").write_text(
      json.dumps({"name": "acorn", "version": "8.18.0", "main": "dist/acorn.js"}),
      encoding="utf-8",
    )
    csstree_dir = tool_dir / "node_modules" / "css-tree" / "lib"
    csstree_dir.mkdir(parents=True, exist_ok=True)
    (csstree_dir / "index.cjs").write_text("module.exports = {};\n", encoding="utf-8")
    (tool_dir / "node_modules" / "css-tree" / "package.json").write_text(
      json.dumps({"name": "css-tree", "version": "3.2.1", "main": "lib/index.cjs"}),
      encoding="utf-8",
    )
    return subprocess.CompletedProcess(cmd, 0, stdout="added 4 packages", stderr="")

  installed = preview.install_portable_parsers(
    tool_dir,
    which=lambda name: f"/usr/bin/{name}",
    runner=fake_success_runner,
  )
  assert installed["status"] == "installed"
  assert installed["available"]
  assert installed["versions"] == {"acorn": "8.18.0", "css-tree": "3.2.1"}
  assert len(calls) == 2

  reused = preview.install_portable_parsers(
    tool_dir,
    which=lambda name: f"/usr/bin/{name}",
    runner=fake_success_runner,
  )
  assert reused["status"] == "reused"
  assert reused["available"]
  assert len(calls) == 2


def test_gate_exempts_mkdir_publish_tasks_and_help(tmp_path):
  state = tmp_path / "state"
  store = preview.Store(state, create=True)
  store.note("gate-note", "Pending work")
  store.set_meta(preview.POLLS_SINCE_MESSAGE, str(preview.GATE_THRESHOLD))
  edit_file_line = (
    "/bin/bash -l -c [ -e 'ARENA.md' ] && [ ! -d 'ARENA.md' ] && "
    "{ printf 'FILE:%s\\n' \"$(readlink -f 'ARENA.md')\"; exit 0; }; "
    "[ -d 'ARENA.md' ] && { printf 'DIR\\n'; exit 0; }; printf 'OK\\n'"
  )

  for line, command in (
    (
      "/bin/bash -l -c mkdir -p '/home/user/clankers'",
      "mkdir -p '/home/user/clankers'",
    ),
    (
      "/bin/bash -l -c mkdir -p 'arena-state'",
      "mkdir -p 'arena-state'",
    ),
    ("mkdir -p custom/dir", "mkdir -p custom/dir"),
    (
      "/bin/bash -l -c [ -e '/home/user/clankers/ARENA.md' ]",
      "[ -e '/home/user/clankers/ARENA.md' ]",
    ),
    (
      edit_file_line,
      "printf 'FILE:%s\\n' \"$(readlink -f 'ARENA.md')\"",
    ),
    (
      edit_file_line,
      "exit 0",
    ),
    (
      "/bin/bash -l -c python3 -I - <<'PY'\nimport codecs\nPY",
      "python3 -I - <<'PY'\nimport codecs\nPY",
    ),
    (
      "/bin/bash -l -c cd /home/user/clankers && arena-preview report publish r.md -i r -t 'Title'",
      "cd /home/user/clankers",
    ),
    (
      '/bin/bash -l -c cd /home/user/clankers && arena-preview task set t1 "Fix `foo`"',
      "cd /home/user/clankers",
    ),
    ("/bin/bash -l -c arena-preview --help", "arena-preview --help"),
    ("/bin/bash -l -c pytest --help", "pytest --help"),
    ("/bin/bash -l -c ruff --help", "ruff --help"),
  ):
    assert preview.first_blocking_piece(line) is None, line
    assert preview.long_run_name(line) is None, line
    assert (
      preview.pre_command(state, line, command, tmp_path, done="read-set", shell="bash")
      == 0
    ), (line, command)
  installer_path = preview.ASSETS.parent / "scripts" / "install.sh"
  if not installer_path.exists():
    installer_path = (
      Path.cwd() / "skills" / "refs" / "arena-skill" / "scripts" / "install.sh"
    )
  installer = installer_path.read_text(encoding="utf-8")
  for expected in (
    "commitlint: ok",
    "gitignore: ok",
    "arena-preview: ok",
    "next action: `start_process`: `arena-preview --serve --port 8000`",
    "--reminder --rc",
  ):
    assert expected in installer


def test_field_html_renders_inline_markdown_in_option_labels():
  _blocks, questions = preview.parse_fields(
    "Select an action: {#action}\n"
    "- (x) Run `arena-preview read` first\n"
    "- ( ) Check `<input>` and `<code>` tags\n"
    "- ( ) Something else: ...\n"
  )
  assert len(questions) == 1
  rendered = preview.field_html(questions[0])
  assert (
    'value="Run `arena-preview read` first" checked> '
    "<span>* Run <code>arena-preview read</code> first</span></label>"
  ) in rendered
  assert (
    'value="Check `&lt;input&gt;` and `&lt;code&gt;` tags"> '
    "<span>Check <code>&lt;input&gt;</code> and <code>&lt;code&gt;</code> tags</span></label>"
  ) in rendered
  assert 'data-custom="Something else..."' in rendered
  style_css = (preview.ASSETS / "style.css").read_text(encoding="utf-8")
  assert ".option > span" in style_css


def test_userscript_snapshot_scopes_export_and_import_refreshes_stale_digests(
  tmp_path, monkeypatch
):
  state = tmp_path / "state"
  store = preview.Store(state, create=True)
  store.note("n1", "First note")
  store.write_task("t1", "First task", ["Step one"], task_type="code")

  monkeypatch.setattr(
    store,
    "userscript_scope",
    lambda: {"repo": "clankers", "branch": "arena/old-branch"},
  )
  old_snap = store.userscript_snapshot()
  assert store.confirm_userscript_save(old_snap)["confirmed"]

  monkeypatch.setattr(
    store,
    "userscript_scope",
    lambda: {"repo": "clankers", "branch": "arena/active-branch"},
  )
  active_snap = store.userscript_snapshot()
  assert store.confirm_userscript_save(active_snap)["confirmed"]
  exported = store.userscript_snapshot()
  exported_rows = [
    json.loads(line)
    for line in exported["text"].splitlines()
    if line.strip() and json.loads(line).get("type") == "userscript-autosave"
  ]
  assert len(exported_rows) == 1
  assert exported_rows[0]["scope"] == {
    "repo": "clankers",
    "branch": "arena/active-branch",
  }

  legacy_core = [dict(item) for item in old_snap["core"]]
  for item in legacy_core:
    if item.get("id") == "t1":
      item["details"] = "Step one"
  legacy_digest = preview.autosave_digest(legacy_core)
  assert legacy_digest != preview.autosave_digest(preview.autosave_core(legacy_core))
  legacy_record = {
    **exported_rows[0],
    "core": legacy_core,
    "digest": legacy_digest,
    "receipts": {exported_rows[0]["save_id"]: legacy_digest},
  }
  payload = "\n".join(json.dumps(row) for row in [*exported["core"], legacy_record])
  receipt = store.import_state(payload, replace_tasks=True)
  assert receipt["notes"] == 1
  restored = store.userscript_history()
  assert len(restored) == 1
  assert restored[0]["digest"] == preview.autosave_digest(restored[0]["core"])


def test_report_markdown_comments_stripped_and_comment_ids_parsed():
  markdown = (
    "Intro prose <!-- inline note --> with `<!-- kept in code -->`.\n\n"
    "<!--\nmulti-line comment\nshould not appear\n-->\n\n"
    "Decision on the amended line:\n"
    "<!-- id: rules-exceptions-line -->\n"
    "- ( ) Approve <!-- option comment -->\n"
    "- ( ) Reject\n\n"
    "Inline anchor question: <!-- id: inline-anchor -->\n"
    "- ( ) Yes\n"
    "- ( ) No\n\n"
    "```markdown\n"
    "<!-- kept in fenced code -->\n"
    "```\n"
  )
  html, questions = preview.render_report(markdown)
  assert "inline note" not in html
  assert "multi-line comment" not in html
  assert "option comment" not in html
  assert "rules-exceptions-line -->" not in html
  assert "&lt;!-- id:" not in html
  assert "<code>&lt;!-- kept in code --&gt;</code>" in html
  assert "&lt;!-- kept in fenced code --&gt;" in html
  assert len(questions) == 2
  assert questions[0]["id"] == "rules-exceptions-line"
  assert questions[0]["prompt"] == "Decision on the amended line"
  assert questions[0]["options"][:2] == ["Approve", "Reject"]
  assert questions[1]["id"] == "inline-anchor"
  assert questions[1]["prompt"] == "Inline anchor question"


def test_unescape_fences_handles_escaped_inline_code_and_state_compare_and_post_push_watcher(
  tmp_path, monkeypatch, capsys
):
  rendered_html, _ = preview.render_report(
    "`next action: \\`start_process\\`: \\`arena-preview --serve --port 8000\\``\n\n"
    "replace `\\` with `/` in `bar`\n"
  )
  assert (
    "<code>next action: `start_process`: `arena-preview --serve --port 8000`</code>"
    in rendered_html
  )
  assert (
    "replace <code>\\</code> with <code>/</code> in <code>bar</code>" in rendered_html
  )
  assert "wall-of-text" in preview.VIOLATION_TYPES["reports"]

  state_dir = tmp_path / "arena-state"
  store = preview.Store(state_dir, create=True)
  store.note("n1", "First note")
  store.write_task("t1", "First task", ["Step one"], task_type="code")
  backup_snap = store.userscript_snapshot()
  uploads = state_dir / "uploads"
  uploads.mkdir(parents=True, exist_ok=True)
  backup_file = uploads / "backup.ndjson"
  backup_file.write_text(backup_snap["text"], encoding="utf-8")

  equal_cmp = store.compare_state(backup_snap["text"])
  assert equal_cmp["verdict"] == "equal"
  assert equal_cmp["groups"]["notes"]["only_file"] == []

  store.note("n2", "Second note")
  store.write_task(
    "t1", "First task", ["Step one", "Step two"], task_type="code", append_details=True
  )
  ahead_cmp = store.compare_state(backup_snap["text"])
  assert ahead_cmp["verdict"] == "ahead"
  assert ahead_cmp["groups"]["notes"]["only_live"] == ["n2"]
  assert ahead_cmp["groups"]["tasks"]["changed"] == ["t1"]
  formatted = preview.format_state_comparison(ahead_cmp, source=backup_file)
  assert "State compare (backup.ndjson): ahead" in formatted
  assert "notes: live 2 file 1 +1 -0 ~0" in formatted
  assert "tasks: live 1 file 1 +0 -0 ~1" in formatted

  resolved = preview.resolve_compare_state_source(state_dir)
  assert resolved == backup_file
  monkeypatch.setattr(preview, "resolve_state_dir", lambda: state_dir)
  monkeypatch.setattr(preview, "require_server", lambda _store: None)
  monkeypatch.setattr(
    sys, "argv", ["arena-preview", "state", "compare", str(backup_file)]
  )
  assert preview.main() == 0
  cli_out = capsys.readouterr().out
  assert "backup.ndjson" in cli_out
  assert "ahead" in cli_out

  assert (
    preview.post_push_pr_checks_command(
      "/bin/bash -l -c git push origin arena/293da56c-clankers"
    )
    == "pr-checks"
  )
  assert (
    preview.post_push_pr_checks_command("/bin/bash -l -c gh pr create --fill")
    == "pr-checks"
  )
  assert (
    preview.post_push_pr_checks_command(
      "/bin/bash -l -c git push --dry-run origin main"
    )
    is None
  )
  assert preview.post_push_pr_checks_command("/bin/bash -l -c git status") is None

  monkeypatch.setenv(preview.DETACH_DRY_RUN, "1")
  assert (
    preview.auto_start_post_push_pr_checks(
      state_dir,
      "/bin/bash -l -c git push origin arena/293da56c-clankers",
      rc=1,
    )
    is False
  )
  assert (
    preview.auto_start_post_push_pr_checks(
      state_dir,
      "/bin/bash -l -c git push origin arena/293da56c-clankers",
      rc=0,
    )
    is True
  )
  err = capsys.readouterr().err
  assert "pr-checks" in err
  assert "pr-checks" in preview.live_runs(state_dir)
  css_text = (preview.ASSETS / "style.css").read_text(encoding="utf-8")
  assert "Basel Grotesk" in css_text
  assert "Basel Grotesk Mono" in css_text
  assert "mark a, a mark { color: var(--mark-link); }" in css_text
  assert "--edge-ramp: 192px" in css_text
  for font_file in (
    "Basel_Grotesk_Book.woff2",
    "Basel_Grotesk_Regular.woff2",
    "Basel_Grotesk_Medium.woff2",
    "Basel_Grotesk_Bold.woff2",
    "Basel_Grotesk_Mono_Regular.woff2",
  ):
    assert (preview.ASSETS / font_file).is_file()
  assert preview.inbox_pipeline_warning("arena-preview poll 2>&1 | tail -15")
  assert preview.inbox_pipeline_warning("arena-preview read 2>&1 | tail -15")
  assert (
    preview.read_set_input_warning(
      'grep -rn "docs/design\\.md" . --exclude-dir=.git --exclude-dir=arena-state --exclude=CHANGELOG.md || true'
    )
    is None
  )
  assert preview.read_set_input_warning("grep -n MUST ARENA.md")
  assert (
    preview.auto_start_post_push_pr_checks(
      state_dir,
      "/bin/bash -l -c git push origin arena/293da56c-clankers",
      rc=0,
    )
    is False
  )
  store = preview.Store(state_dir, create=True)
  scoped = store.write_task(
    "scoped-task",
    "Scoped task",
    ["First step"],
    task_type="code",
    scope="arena suite",
  )
  assert scoped["details"] == ["Scope: arena suite", "First step"]
  updated_scoped = store.write_task("scoped-task", scope="nemoizer")
  assert updated_scoped["details"] == ["Scope: nemoizer", "First step"]
  md_rendered = preview.add_copy_buttons(preview.render("```markdown\n# Title\n```"))
  assert 'class="preview-code-md"' in md_rendered
  assert 'aria-pressed="false"' in md_rendered
  py_rendered = preview.add_copy_buttons(preview.render("```python\nprint(1)\n```"))
  assert 'class="preview-code-md"' not in py_rendered
  cp_note = store.schedule_read_set_note(manual=True, root=tmp_path)
  assert cp_note is not None
  store.acknowledge([cp_note["id"]], "Bible texts in context.")
  assert store.meta_value("survey_checked_at") is not None
  slash_help = preview.resolve_slash_command("/nuu help")
  assert slash_help is not None
  assert slash_help["mode"] == "query"
  assert "search" in slash_help["markdown"]
  assert "CLI Subcommands" not in slash_help["markdown"]
  discovered = preview.discover_slash_commands()
  assert [row["cmd"].strip() for row in discovered] == sorted(
    row["cmd"].strip() for row in discovered
  )
  assert any(row["cmd"] == "/nuu recipe offline-fonts" for row in discovered)
  slash_recipes = preview.resolve_slash_command("/nuu recipes")
  assert slash_recipes is not None
  assert slash_recipes["mode"] == "query"
  assert "offline-fonts" in slash_recipes["markdown"]
  assert "scroll-edge-fade" in slash_recipes["markdown"]
  slash_nemo_help = preview.resolve_slash_command("/nemoizer help")
  assert slash_nemo_help is not None
  assert slash_nemo_help["mode"] == "query"
  assert "STE" in slash_nemo_help["markdown"]
  assert "CLI Options" not in slash_nemo_help["markdown"]
  slash_nemo_rule = preview.resolve_slash_command("/nemoizer rules ste100")
  assert slash_nemo_rule is not None
  assert slash_nemo_rule["mode"] == "query"
  assert "STE100" in slash_nemo_rule["markdown"]
  slash_nemo_rules_all = preview.resolve_slash_command("/nemoizer rules")
  assert slash_nemo_rules_all is not None
  assert not slash_nemo_rules_all["markdown"].lstrip().startswith("<!--")
  rendered_rules = preview.render(
    "<!-- nonemo: NMO100 -->\n# Rules\nKeep `<!-- nonemo: NMO100 -->` and:\n```html\n<!-- fenced -->\n```"
  )
  assert "&lt;!-- nonemo: NMO100 --&gt;\n<h1>Rules</h1>" not in rendered_rules
  assert rendered_rules.lstrip().startswith("<h1>Rules</h1>")
  assert "<code>&lt;!-- nonemo: NMO100 --&gt;</code>" in rendered_rules
  assert "&lt;!-- fenced --&gt;" in rendered_rules
  assert preview.slow_bash_hint("/bin/bash -l -c pytest -q", 12.4) is not None
  assert "arena-preview run start" in preview.slow_bash_hint(
    "/bin/bash -l -c pytest -q", 12.4
  )
  assert preview.slow_bash_hint("/bin/bash -l -c pytest -q", 4.2) is None
  assert preview.slow_bash_hint("/bin/bash -l -c arena-preview poll", 120.0) is None
  slash_nemo_collect = preview.resolve_slash_command("/nemoizer collect ARENA.md")
  assert slash_nemo_collect is not None
  assert slash_nemo_collect["mode"] == "query"
  assert ".agents" in preview.NEMOIZER_COLLECT_IGNORES
  slash_nemo_collect_all = preview.resolve_slash_command("/nemoizer collect")
  assert slash_nemo_collect_all is not None
  assert slash_nemo_collect_all["mode"] == "query"
  assert slash_nemo_collect_all["title"] == "nemoizer collect · Audit Findings"
  slash_nuu_audit = preview.resolve_slash_command("/nuu audit #compose")
  assert slash_nuu_audit is not None
  assert slash_nuu_audit["mode"] == "note"
  assert "75em" in slash_nuu_audit["text"]
  assert "60em" in slash_nuu_audit["text"]
  assert "40em" in slash_nuu_audit["text"]
  assert "30em" in slash_nuu_audit["text"]
  assert "audit-report.md" in slash_nuu_audit["text"]
  assert slash_nuu_audit["text"].endswith("#compose")
  app_js_text = (
    preview.Path(__file__).resolve().parent.parent / "assets" / "app.js"
  ).read_text(encoding="utf-8")
  fallback_cmds = re.findall(
    r"\{\s*cmd:\s*'([^']+)',\s*desc:\s*'([^']+)'\s*\}", app_js_text
  )
  assert [
    {"cmd": cmd, "desc": desc} for cmd, desc in fallback_cmds
  ] == preview.discover_slash_commands()
  slash_nuu_recipe = preview.resolve_slash_command(
    "/nuu recipe scroll-edge-fade #history"
  )
  assert slash_nuu_recipe is not None
  assert slash_nuu_recipe["mode"] == "note"
  assert "scroll-edge-fade" in slash_nuu_recipe["text"]
  assert slash_nuu_recipe["text"].endswith("#history")
  slash_nemo_audit = preview.resolve_slash_command("/nemoizer audit docs/")
  assert slash_nemo_audit is not None
  assert slash_nemo_audit["mode"] == "note"
  assert "nemoize.py --audit" in slash_nemo_audit["text"]
  assert slash_nemo_audit["text"].endswith("docs/")

  tz_store = preview.Store(tmp_path / "tz-state", create=True)
  assert tz_store.set_display_timezone("Asia/Manila") == "Asia/Manila"
  assert tz_store.state()["display_tz"] == "Asia/Manila"
  assert (tmp_path / "tz-state" / "display_tz").read_text(
    encoding="utf-8"
  ).strip() == "Asia/Manila"
  assert "X-Timezone" in app_js_text
  install_sh_text = (
    Path(preview.resolve_repo_root())
    / "skills"
    / "refs"
    / "arena-skill"
    / "scripts"
    / "install.sh"
  ).read_text(encoding="utf-8")
  assert "display_tz" in install_sh_text
  wf_img = tmp_path / "1280-light-no-preference-wireframe.png"
  wf_img.write_bytes(b"\x89PNG\r\n\x1a\n")
  with pytest.raises(ValueError, match="Wireframe image"):
    preview.embed_report_images(f"![wf]({wf_img})", tmp_path)
  assert (
    preview.pre_command(
      tmp_path / "tz-state",
      "git add 1280-light-no-preference-wireframe.png",
      "git add 1280-light-no-preference-wireframe.png",
      tmp_path,
    )
    == 130
  )
  backup_ndjson = json.dumps({"id": "b1a2c3", "text": "backed up note"}) + "\n"
  offer1 = tz_store.offer_userscript_backup(
    {
      "name": "backup.ndjson",
      "text": backup_ndjson,
      "summary": "State mismatch (notes -1, tasks 0).",
    }
  )
  assert offer1["offered"] is True
  assert offer1["duplicate"] is False
  offer2 = tz_store.offer_userscript_backup(
    {
      "name": "backup.ndjson",
      "text": backup_ndjson,
      "summary": "State mismatch (notes -1, tasks 0).",
    }
  )
  assert offer2["duplicate"] is True

  pr_body_path = tmp_path / "pr-body.md"
  pr_body_path.write_text("## Summary\n\nBody text.\n", encoding="utf-8")
  with pytest.raises(ValueError, match="/tmp"):
    preview.pr_update_command(119, "feat: title", Path("/tmp/pr.md"), root=tmp_path)
  monkeypatch.setattr(preview, "repo_slug", lambda _root=None: "nemoe7/clankers")
  gh_calls = []

  def fake_gh_run(cmd, **kwargs):
    gh_calls.append((cmd, kwargs.get("input")))
    if "-i" in cmd:
      return subprocess.CompletedProcess(
        cmd,
        0,
        stdout="HTTP/2 302\r\nLocation: https://results.actions.githubusercontent.com/signed-log\r\n\r\n",
        stderr="",
      )
    return subprocess.CompletedProcess(
      cmd,
      0,
      stdout=json.dumps({"title": "feat: title", "body": "## Summary\n\nBody text.\n"}),
      stderr="",
    )

  real_subproc_run = preview.subprocess.run
  monkeypatch.setattr(preview.subprocess, "run", fake_gh_run)
  receipt = preview.pr_update_command(119, "feat: title", pr_body_path, root=tmp_path)
  assert "119" in receipt
  assert len(gh_calls) == 2
  assert gh_calls[0][0][:4] == ["gh", "api", "repos/nemoe7/clankers/pulls/119", "-X"]
  assert (
    preview.job_log_command(tz_store, job_id="42", root=tmp_path)
    == "https://results.actions.githubusercontent.com/signed-log"
  )
  test_key = "k" * 24
  tz_store.set_agent_key(test_key, "https://proxy.example.test")
  assert (
    preview.job_log_command(tz_store, run_id="99", root=tmp_path)
    == f"https://proxy.example.test/v1/gh?key={test_key}&path=repos/nemoe7/clankers/actions/runs/99/logs"
  )
  assert (
    preview.route_recipe_command(
      tmp_path / "tz-state",
      "gh api -i /repos/nemoe7/clankers/actions/jobs/42/logs",
      root=tmp_path,
    )
    == 2
  )
  jq_patch_cmd = (
    f'jq -n --rawfile body "{pr_body_path}" --arg title "feat: title" '
    "'{body: $body, title: $title}' | "
    "gh api repos/nemoe7/clankers/pulls/119 -X PATCH --input -"
  )
  assert (
    preview.route_recipe_command(
      tmp_path / "tz-state",
      jq_patch_cmd,
      root=tmp_path,
    )
    == 2
  )
  assert (
    preview.route_recipe_command(
      tmp_path / "tz-state",
      "curl -X PATCH https://api.github.com/repos/nemoe7/clankers/pulls/119 -d '{}'",
      root=tmp_path,
    )
    == 130
  )
  monkeypatch.setattr(preview.subprocess, "run", real_subproc_run)
  style_text = (
    preview.Path(__file__).resolve().parent.parent / "assets" / "style.css"
  ).read_text(encoding="utf-8")
  assert "padding-top: 0;" in style_text
  assert "position: sticky; top: 0; z-index: 2; background: var(--bg);" in style_text
  sample_png = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
  )
  (tmp_path / ".git").mkdir(exist_ok=True)
  (tmp_path / "sample.png").write_bytes(sample_png)
  rep_dir = tmp_path / "arena-state" / "reports"
  rep_dir.mkdir(parents=True, exist_ok=True)
  (rep_dir / "local-report.png").write_bytes(sample_png)
  mime_out, raw_out, encoded_out = preview.resolve_report_image(
    "sample.png", root=rep_dir
  )
  assert mime_out == "image/png"
  assert raw_out == sample_png
  assert (
    preview.resolve_report_image("local-report.png", root=tmp_path)[1] == sample_png
  )
  inlined_md = preview.inline_report_image_urls(
    "![sample](/api/report-image?path=sample.png)", report_dir=rep_dir
  )
  assert inlined_md == f"![sample](data:image/png;base64,{encoded_out})"
  import shutil

  fake_nemo = tmp_path / ".agents" / "skills" / "nemoizer" / "scripts"
  fake_nemo.mkdir(parents=True, exist_ok=True)
  shutil.copy2(
    Path(preview.resolve_repo_root())
    / "skills"
    / "refs"
    / "nemoizer"
    / "scripts"
    / "nemoize.py",
    fake_nemo / "nemoize.py",
  )
  for helper_name in ("prose.py", "markers.py", "javascript-comments.cjs"):
    shutil.copy2(
      Path(preview.resolve_repo_root())
      / "skills"
      / "refs"
      / "nemoizer"
      / "scripts"
      / helper_name,
      fake_nemo / helper_name,
    )
  bad_rep = rep_dir / "bad-nemo.md"
  bad_rep.write_text("# Report\n\nFirst clause; second clause.\n", encoding="utf-8")
  with pytest.raises(ValueError, match="STE100"):
    tz_store.publish("bad-nemo", "Bad Report", bad_rep)
  good_rep = rep_dir / "good-nemo.md"
  good_rep.write_text(
    "# Report\n\nFirst sentence. Second sentence.\n", encoding="utf-8"
  )
  tz_store.publish("good-nemo", "Good Report", good_rep)
  shutil.rmtree(tmp_path / ".agents")
  assert offer2["note_id"] == offer1["note_id"]
  tz_read = tz_store.read(include_quiet=False)
  assert any(item["id"] == offer1["note_id"] for item in tz_read["pending"])
  tz_state_notes = tz_store.state()["notes"]
  assert not any(
    item["id"] == offer1["note_id"] for item in tz_state_notes if not item.get("quiet")
  )
  tz_store.import_state(backup_ndjson)
  tz_store.acknowledge([offer1["note_id"]], "Compared and imported backup state.")
  assert not any(item["id"] == offer1["note_id"] for item in tz_store.read()["pending"])
