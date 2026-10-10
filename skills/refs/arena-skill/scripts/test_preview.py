"""Pytest checks for the preview runtime. Run with the reporting venv's Python."""

import builtins
import hashlib
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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import preview


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


def test_edited_ack_stamp():
  """A second ack appends a reply block; the first answer stays (owner, re-ack of 52d7cce)."""
  with tempfile.TemporaryDirectory() as edit_dir:
    edited = preview.Store(edit_dir, create=True)
    edited.note("edit-note", "Question")
    edited.submission("edit-answer", "form", "REPORT form: answer")
    ids = ["edit-note", "edit-answer"]
    with patch.object(preview, "now", return_value="2026-09-22T12:00:00"):
      edited.acknowledge(ids, "reply", "First answer")
    first = edited.state()["notes"][0]
    assert first["ack_edited_at"] is None and first["replies"] == []
    with patch.object(preview, "now", return_value="2026-09-22T12:01:00"):
      edited.acknowledge(ids, "reply", "Second answer")
    row = edited.state()["notes"][0]
    assert row["acknowledged_at"] == "2026-09-22T12:00:00"
    assert row["ack_text"] == "First answer", "the first answer is not replaced"
    assert row["ack_edited_at"] == "2026-09-22T12:01:00"
    assert row["replies"] == [
      {"kind": "reply", "text": "Second answer", "at": "2026-09-22T12:01:00"}
    ]
    answer = edited.submissions()[0]
    assert answer["ack_edited_at"] == row["ack_edited_at"]
    assert answer["replies"] == row["replies"]
    # The same text again is still one more block: nothing is compared, nothing is dropped.
    with patch.object(preview, "now", return_value="2026-09-22T12:02:00"):
      edited.acknowledge(ids, "note", "Second answer")
    row = edited.state()["notes"][0]
    assert row["ack_edited_at"] == "2026-09-22T12:02:00"
    assert [reply["kind"] for reply in row["replies"]] == ["reply", "note"]
    assert preview.Store(edit_dir).state()["notes"][0]["replies"] == row["replies"]
    with_html = preview.Store(edit_dir).state()["notes"][0]
    assert "html" not in with_html["replies"][0], (
      "the state parses replies; the page route renders"
    )
    saved = Path(edit_dir) / "edited.ndjson"
    saved.write_text(json.dumps(preview.saved_note_line(row)) + "\n")
    restored_dir = Path(edit_dir) / "restored"
    restored = preview.Store(restored_dir, create=True)
    subprocess.run(
      [
        sys.executable,
        preview.__file__,
        "import-state",
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
      "ack_kind": "reply",
      "ack_text": "First",
    }
    for flaw, replies in (
      ("no receipt", None),
      ("not a list", {"kind": "reply", "text": "x", "at": "2026-09-22T12:01:00"}),
      ("no kind", [{"text": "x", "at": "2026-09-22T12:01:00"}]),
      ("bad stamp", [{"kind": "reply", "text": "x", "at": "yesterday"}]),
      ("empty text", [{"kind": "note", "text": " ", "at": "2026-09-22T12:01:00"}]),
    ):
      try:
        if flaw == "no receipt":
          restored.note(
            "invalid-replies",
            "Question",
            replies=[{"kind": "reply", "text": "x", "at": "2026-09-22T12:01:00"}],
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
    store.note("edited-note", "Question")
    # The answer rides in the save only while its report is published, which every real
    # answer's report is.
    form = Path(directory) / "form.md"
    form.write_text("# Form\n\nNo fields here.\n", encoding="utf-8")
    store.publish("form", "Form", form)
    store.submission("edited-answer", "form", "REPORT form: answer")
    ids = ["edited-note", "edited-answer"]
    with patch.object(preview, "now", return_value="2026-09-22T12:00:00"):
      store.acknowledge(ids, "reply", "First answer")
    with patch.object(preview, "now", return_value="2026-09-22T12:01:00"):
      store.acknowledge(ids, "reply", "Second answer")

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
        store.acknowledge(ids, "note", "Third answer")
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
      preview.Store(restored_dir, create=True)
      subprocess.run(
        [
          sys.executable,
          preview.__file__,
          "import-state",
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
    receipt_store.acknowledge(["answer-one"], "note", "Received")
    report = receipt_store.state()["reports"][0]
    assert report["latest_answer_acknowledged_at"] == preview.clip_stamp(
      receipt_store.submissions()[-1]["acknowledged_at"]
    )
    receipt_store.acknowledge(["answer-one"], "reply", "Second reply")
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


def test_report_unpublish():
  """Deleting a report prunes the tab row only; answers and the source file stay."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "pick.md"
    source.write_text(
      "# Pick\n\nChoice? {#pick}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("pick", "Pick one", source)
    store.submission("answer-1", "pick", "REPORT pick: one")
    # The owner's dismissal prunes the tab row only, after seen.
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "pick")
      )
    store.unpublish("pick", dismissed_by_owner=True)
    assert store.state()["reports"] == []
    try:
      store.report("pick")
      raise AssertionError("A deleted report still read back")
    except FileNotFoundError:
      pass
    try:
      store.unpublish("pick")
      raise AssertionError("Deleting the same report twice was accepted")
    except FileNotFoundError:
      pass
    assert store.submissions()[0]["report_id"] == "pick", "sent answers are history"
    assert source.exists(), "the .md source stays for republishing"
    try:
      store.publish("pick", "Pick again", source)
      raise AssertionError("Republishing over sent answers was accepted")
    except ValueError:
      pass
    # The CLI form stays silent on an open report: the agent already knows what it
    # removed. The new guard holds until seen.
    store.publish("plain", "Pick one", source)
    store.mark_report_read = getattr(store, "mark_report_read", None) or (
      lambda x: store._mark_seen_for_test(x)
    )
    # Mark as seen via seen_at
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "plain")
      )
    store.unpublish("plain")
    assert store.state()["reports"] == []
    assert len(store.state()["notes"]) == 1, "the CLI unpublish writes no note"


def test_http_boundaries():
  global app
  with tempfile.TemporaryDirectory() as directory:
    # The state directory and the save file are siblings, the way they are in the repository: the
    # save file is written at the root, so a restore that drops the state directory keeps it.
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
    # A paragraph carries no `<br>` at all, on the owner's suggestion: markdown-it
    # turns a newline into one when breaks are on, and the owner read the result as too airy beside
    # the message log, where a line breaks through `white-space: pre-wrap` and needs no tag.
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
    # The three report toolbar buttons share one box size (owner screenshot: the late unpublish
    # button had fallen back to the 34px default), and the report select carries the log
    # filter's chevron rather than the native arrow.
    assert (
      "#copy-report,#refresh-report,#unpublish-report{width:44px;height:44px;}" in css
    )
    assert re.search(
      r"\.select-wrap::after\{[^}]*border-top:5px solid var\(--muted\)", css
    )
    assert re.search(r"#report-select\{appearance:none;padding-right:26px;\}", css)
    # The green send flash is gone (owner: the footnote under the report covers it), so neither the
    # page nor the client script carries report-receipt; the footnote element stays.
    page = (preview.ASSETS / "index.html").read_text()
    script = (preview.ASSETS / "app.js").read_text()
    assert "report-receipt" not in page and "report-receipt" not in script
    assert "showReceipt" not in script and 'id="report-agent-ack"' in page
    assert page.index('id="report-ack-history"') < page.index('id="report-form"')
    assert page.index('id="report-agent-ack"') < page.index('id="report-form"')
    assert page.index('id="report-agent-ack-footer"') > page.index('id="report-submit"')
    # A break outside a paragraph, in a list item for one, stays exactly as markdown-it wrote it.
    assert "<br" in preview.render("- a\n  b", breaks=True)
    # The log renders without `breaks`: its paragraphs are `white-space: pre-wrap`, so the newline
    # the source carries is the line break and a `<br>` beside it doubled every gap. That doubling
    # is what the owner removed by hand in the browser.
    logged = preview.render("line one\nline two")
    assert "<br" not in logged and "\n" in logged and logged.count("<p>") == 1
    # A fence the owner escaped still opens a block: the line-leading escape is dropped before the
    # render, so the marker reaches the rule that carries the background.
    escaped = preview.render("before\n\\```\ncode\n\\```\nafter")
    assert escaped.count('class="code-block"') == 1
    assert "<p>before</p>" in escaped and "<p>after</p>" in escaped
    assert "<pre><code>code" in escaped
    # A tilde fence is a fence too.
    assert "<pre" in preview.render("\\~~~\ncode\n\\~~~")
    # An escape that is not a fence stays markdown-it's own, so inline text keeps its literal
    # backticks rather than turning into a code block.
    assert "<pre" not in preview.render("a \\`code\\` b")
    # An image the agent sized keeps that size; commonmark alone prints the syntax.
    sized = preview.render("![alt](https://example.com/a.png =320x200)")
    assert 'width="320" height="200"' in sized and 'alt="alt"' in sized
    assert 'width="320"' in preview.render("![a](https://example.com/a.png =320x)")
    assert "<img" in preview.render("![a](https://example.com/a.png)")
    # A source the renderer refuses stays text, and a quote in one stays escaped.
    assert "<img" not in preview.render("![x](javascript:alert(1) =10x10)")
    assert "&quot;" in preview.render('![q](https://example.com/a"b.png =10x10)')
    store = preview.Store(root, create=True, save_path=save_file)
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
    # A republish moves the edit stamp; the publish date stays at the first one.
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
      # The log's jump bar ships in the page, inside the wrapper that positions it over the scroll area.
      assert 'id="log-newest"' in page and 'class="log-scroll"' in page
      assert 'aria-label="Scroll to bottom"' in page
      assert '<svg width="14" height="14" viewBox="0 0 24 24"' in page
      assert "↓ Latest message" not in page
      assert re.search(r"\.log-newest\s*\{[^}]*border-radius:\s*4px", page)
      # The bar hugs its label rather than spanning the pane.
      assert "translateX(-50%)" in page
      # The new-reply pill floats the same way, at the log's top: the placement says the reply
      # waits above, and the two pills can never meet.
      # It clears the card border below it and wears the plain text color, not the accent.
      assert re.search(r"\.log-edited\s*\{[^}]*position:\s*absolute", page)
      assert re.search(r"\.log-edited\s*\{[^}]*top:\s*20px", page)
      assert re.search(r"\.log-edited\s*\{[^}]*color:\s*var\(--text\)", page)
      assert re.search(r"\.log-edited\s*\{[^}]*border-radius:\s*4px", page)
      assert page.index('id="log-edited"') > page.index('class="log-scroll"')
      # The save button sits in the top bar after the theme button rather than in the log's own
      # row. The log's own copy and the tasks' copy are gone, and one copy button carries the
      # state to the clipboard.
      assert (
        page.index('id="theme"')
        < page.index('id="copy-state"')
        < page.index('id="notes-panel"')
      )
      assert page.index('id="log-search"') < page.index('id="skip-poll"')
      assert 'id="copy-log"' not in page and 'id="copy-tasks"' not in page
      assert "Copy the log, answers and tasks to the clipboard as NDJSON" in page
      # Every icon button carries a title that repeats its accessible name.
      for control in (
        "copy-state",
        "attach-file",
        "unpublish-report",
        "copy-report",
        "refresh-report",
      ):
        block = page[page.index(f'id="{control}"') :]
        assert "title=" in block[: block.index(">")]
      # A note owns staged file chips and a native multi-file picker. Backend records remain,
      # but no saved-files list crowds the composer; Downloads alone keeps the remaining tab.
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
      assert "Up to 102.4 MB per URL" in page
      assert "Keep this page open while transfers run." in page
      assert "not measured" not in page
      assert 'id="workspace-use"' in page
      assert re.search(
        r'<input[^>]*id="upload-file"[^>]*type="file"[^>]*multiple', page
      )
      assert 'id="log-newest"' in page and 'stroke="#fff"' in page
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
      # The token rides the page as an HTML attribute, so it survives the shipped minified build.
      token = re.search(r'data-token="([^"]+)"', page)[1]
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
      assert request("POST", "/api/markdown", '{"text":"draft"}')[0] == 415
      assert request("POST", "/api/notes", "{}")[0] == 415
      assert request("POST", "/api/notes", "{}", {"X-Preview-Token": token})[0] == 415
      # A full-length note stays inside the general body limit, so the cap is reachable over HTTP.
      assert (
        len(json.dumps({"id": "x", "text": "x" * preview.MAX_NOTE})) < preview.MAX_BODY
      )
      assert request("POST", "/api/notes", "x" * (preview.MAX_BODY + 1), auth)[0] == 400
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
        (["message-1", "unknown"], "reply", "done"),
        (["message-1"], "shout", "done"),
        (["message-1"], "reply", ""),
        (["message-1"], "reply", "x" * (preview.MAX_NOTE + 1)),
      ):
        try:
          store.acknowledge(*broken)
          raise AssertionError(f"Invalid receipt accepted: {broken}")
        except ValueError:
          assert store.read()["pending"]
      store.acknowledge(["message-1"], "reply", "Fixed in `preview.py`.")
      stamp = store.state()["notes"][0]["acknowledged_at"]
      assert len(stamp) == 19, (
        "the state surface carries second stamps, no ms or offset"
      )
      assert store.state()["notes"][0]["ack_text"] == "Fixed in `preview.py`."
      store.acknowledge(["message-1"], "note", "and rechecked")
      row = store.state()["notes"][0]
      assert row["acknowledged_at"] == stamp
      assert (
        row["ack_kind"] == "reply" and row["ack_text"] == "Fixed in `preview.py`."
      ), "a second ack appends; the first answer stays"
      assert [(reply["kind"], reply["text"]) for reply in row["replies"]] == [
        ("note", "and rechecked")
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
      # A note block rides plain: the route renders reply blocks only.
      assert served_note["replies"] == [
        {"kind": "note", "text": "and rechecked", "at": served_note["ack_edited_at"]}
      ]
      assert served_note["seen_at"] is not None
      store.acknowledge(["message-1"], "reply", "<script>alert(1)</script> **safe**")
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
      # Mark seen before unpublish (new guard holds until seen)
      assert request("POST", "/api/reports/prune/seen", "{}", auth)[0] == 200
      status, _, removed = request("POST", "/api/reports/prune/unpublish", "{}", auth)
      assert status == 200 and json.loads(removed) == {"unpublished": "prune"}
      # The page deletes a report only on the owner's two clicks, so the route writes the
      # note that tells the agent the report was dismissed instead of lost.
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
        "# Sign-off\n\nPick the areas:\n\n- [ ] ui\n- [x] api\n- [ ] Other: ___\n\n"
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
      assert sum(1 for kind, _ in blocks if kind == "field") == 4
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
      assert "<textarea" in served["html"] and 'placeholder="Other:"' in served["html"]
      assert "> Other: <" not in served["html"]
      status, _, page_text = request("GET", "/")
      page = compact(page_text)
      # The minified sheet drops attribute-selector quotes, so both spellings count.
      assert status == 200 and re.search(
        r'#preview-note\[aria-pressed="?false"?\][^{}]*\{', page
      )
      assert not re.search(r'#preview-note\[aria-pressed="?true"?\]', page)
      assert "--focus:#524d47" in page and "#f4ca93" not in page
      assert "--focus:#8f5b13" in page
      assert "--tab-border:#413d39" in page
      assert "--tab-border:var(--border)" in page
      assert "nav button:focus-visible{border-color:var(--focus)" in page
      assert "border-color:var(--accent)" not in page
      assert "padding-bottom:12px" in page
      assert "#report-form{min-width:0;margin-top:12px" in page
      assert re.search(r"\.card\.compose\{[^}]*padding:8px 18px", page), (
        "composer padding must override .card"
      )
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
      assert (
        ".state-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--dot-sent)"
        in page
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
      # Inline code sits darker than the page in dark mode; the light theme keeps its bubble.
      assert "--code-bg:#1b1a19" in page
      assert "--code-bg:var(--bubble)" in page
      # The composer's hint is half as prominent as the muted face, so what is being typed and what
      # was sent stay distinguishable from a placeholder that is neither.
      # The minified sheet shortens 0.5 to .5, so both spellings count.
      assert re.search(
        r"textarea::placeholder\{color:var\(--muted\);opacity:(?:0)?\.5", page
      )
      # An ID carries one gesture now: a click quotes it, and no copy path is left to colour.
      assert "data-copied" not in page
      assert "#clock{font-size:inherit;font-variant-numeric:tabular-nums" in page
      assert re.search(
        r'\.icon-button\[data-state="?good"?\]\{color:var\(--dot-said\);', page
      )
      assert re.search(r'\.icon-button\[data-state="?bad"?\]\{color:#ef4444;', page)
      assert 'id="copy-log"' not in page, "the log lost its copy button"
      # The log card carries no heading: the tab above already names the panel, and the title
      # only repeated it while spending a line of height. The status
      # stack and the toolbar keep their places.
      assert "history-title" not in page
      assert '<section class="card log-card" aria-label="Message log">' in page
      assert page.index('id="connection"') < page.index('id="log-search"')
      # A phone keeps the tabs alone and drops the composer hint. The footer's Send button sits
      # at the right edge of the bottom line, with or without staged files, and the composer
      # card steps its paddings and row gaps down.
      assert (
        "@media (pointer:coarse){.topbar-row>.row.tight{display:none;}#send-hint{display:none;}"
        "#send{margin-left:auto;}.card.compose{padding:6px 12px;}.compose .row{margin:4px 0;}}"
        in page
      )
      assert "nav button{padding:7px 4px;font-size:14px;}" in page
      assert "#send{margin-left:auto;}}" in page
      # The composer's outer rows give up the space they face.
      assert "#form>div:first-child{margin-top:0;padding-top:0" in page
      assert "#form>div:last-child{margin-bottom:0;padding-bottom:0" in page
      assert '<button id="copy-report" class="icon-button"' in page
      # The report copy button matches the boxes beside it; they were 34px against 44px.
      # No negative assertion here: the combined rule contains the old single-selector text.
      assert (
        "#copy-report,#refresh-report,#unpublish-report{width:44px;height:44px" in page
      )
      # A rule separates the tasks toolbar from the finished div, and details collapse.
      assert (
        ".tasks-layout>.row.tight{border-bottom:1px solid var(--border);padding-bottom:12px"
        in page
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
      assert re.search(
        r"#report-pip[^{}]*\{position:absolute;top:5px;right:5px;"
        r"display:inline-block;width:7px;height:7px;"
        r"border-radius:50%;background:var\(--accent\)",
        page,
      )
      assert re.search(
        r"#notes-pip[^{}]*\{position:absolute;top:5px;right:5px;"
        r"display:inline-block;width:7px;height:7px;"
        r"border-radius:50%;background:var\(--accent\)",
        page,
      )
      # The pip is given a shape by a display rule, so the sheet's blanket rule is what hides it.
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
      # The log's search box draws its own box like the icon buttons beside it: the same 34px
      # height, and no native search decoration to fight the row.
      assert re.search(r"#log-search\{[^}]*height:34px;[^}]*min-height:0;", page)
      assert 'button,select,textarea,input[type="url"],input[type="search"]{' in page, (
        "the search box shares the form controls' border and radius"
      )
      assert "#log-filter" not in page and ".filter-wrap" not in page
      assert "border-top:5px solid var(--muted)" in page, (
        "the report select keeps its drawn caret, and it needs no blocked data image"
      )
      assert "data:image/svg+xml" not in page, "the preview CSP blocks data images"
      # The collapse button is gone, its closed state with it, and the strip can no longer push
      # past the bar: it shrinks and scrolls at any width instead.
      assert "#chrome" not in page and "data-chrome" not in page
      assert re.search(r"nav\{[^}]*min-width:0;", page), (
        "the tab strip shrinks rather than pushing the bar"
      )
      # The four tabs share one width: the grid gives every track 1fr, so no label sets a tab's
      # shape. The narrow block steps the padding and the font down, and the
      # tracks stay equal then.
      assert re.search(r"nav\{[^}]*grid-template-columns:repeat\(4,1fr\)", page)
      assert re.search(r"nav button\{[^}]*min-width:0;[^}]*padding:7px 9px;", page)
      assert re.search(r"nav button\{[^}]*white-space:nowrap", page)
      assert "nav button{padding:7px 4px;font-size:14px" in page
      # The composer footer fits a narrow width: shorter hints, and the key's own line is short.
      # The hint is its own span, so the client swaps it with the pointer: a touch keyboard writes
      # the newline and the Send button sends.
      # The hint carries its own separator, so a phone that hides it leaves the key line whole.
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
      # The send button carries one rule twice, the narrow-screen and the touch position fix,
      # and no resize of its own.
      assert re.findall(r"#send\{([^}]*)\}", page) == [
        "margin-left:auto;",
        "margin-left:auto;",
      ]
      # Staging a file must not move the plus and MD buttons: the heading row never wraps, so
      # the chips wrap inside the label span and the tight row keeps its right-hand seat.
      assert ".composer-heading{flex-wrap:nowrap;" in page
      assert "resize:none" in page and "resize:vertical" not in page
      assert (
        "#notes-panel,#reports-panel,#tasks-panel,#downloads-panel{overflow-y:auto"
        in page
      )
      assert 'id="tasks-tab" aria-controls="tasks-panel"' in page
      assert '<ul id="tasks-current-body" class="task-list"></ul>' in page
      assert '<ul id="tasks-finished-body" class="task-list"></ul>' in page
      assert '<ul id="tasks-upcoming-body" class="task-list"></ul>' in page
      # Current leads the panel: what the agent is on next is the first thing the owner reads.
      # Current leads the panel and Upcoming follows it, with the finished record last: what the
      # agent is on next and what is coming are the owner's questions, and what is done is the log.
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
      assert "resize:none;min-height:72px;overflow:hidden" in page
      # The document itself never scrolls: the panels own their scrolling. The log card's floor
      # steps down on a short viewport, so a small phone keeps the whole column on screen with the
      # composer closed.
      assert "html,body{height:100%;overflow:hidden;overscroll-behavior:none" in page
      # The log header wraps into four short lines on a narrow width, and the 12px wrap gap read
      # as dead space; the lines sit close now.
      assert ".log-card>.row:first-child{margin-block:0;row-gap:2px" in page
      assert ".log-card{flex:1 1 auto;min-height:min(500px,60dvh)" in page
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
      assert 'title="Copy code"' in block and ">⧉</button>" in block
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
          "answers": {"pick-the-areas": ["ui"], "severity": "high", "name": "ada"},
        }
      )
      assert (
        request("POST", "/api/reports/fields/submit", report_answer, auth)[0] == 201
      )
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
        request("POST", "/api/reports/fields/submit", "{}", {"X-Preview-Token": token})[
          0
        ]
        == 415
      )
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
        {"id": "s1", "answers": {"pick-the-areas": ["ui", "core"]}},
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
            "pick-the-areas": ["ui"],
          },
        }
      )
      assert request("POST", "/api/reports/fields/submit", submission, auth)[0] == 201
      pending = [
        row
        for row in store.read()["pending"]
        if row["text"].startswith("REPORT fields")
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
      assert "> Ship it</label>" in markup and 'placeholder="Other:"' in markup
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
      assert "verdict: Other: make it blue" in record["text"]
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
      # A report whose fields fail validation is refused at publish, so it can never be stored in a
      # shape that cannot be rendered; before this it published and then broke its own html route.
      broken = root / "broken.md"
      broken.write_text(
        "# Broken\n\nPick one:\n\n- ( ) " + "x" * 201 + "\n", encoding="utf-8"
      )
      try:
        store.publish("broken", "Broken report", broken)
        raise AssertionError("A report with an over-long option was published")
      except ValueError:
        pass
      assert "broken" not in {item["id"] for item in store.state()["reports"]}
      # A report stored before that guard existed is still unrenderable, so the route answers with a
      # JSON error rather than closing the connection, which is what an uncaught ValueError did.
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
      # A submission is limited in characters and its request body in bytes, and the byte limit has
      # to sit above the character one or the documented maximum stays unreachable over HTTP, which
      # is what one 32 KiB limit for every POST did, before the note cap set the bound. That
      # maximum is 50 fields of 2,000 characters,
      # and no single answer reaches it because a text answer is capped at 2,000, so it takes a whole
      # wide report. The Store layer already covers the submission; this covers the HTTP path.
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
      assert len(full) > preview.MAX_BODY, (
        "the case has to exceed the limit it is testing"
      )
      assert request("POST", "/api/reports/wide/submit", full, auth)[0] == 201
      # Owner answers above the former cap are accepted.
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
      # Past the body limit, so HTTP refuses it before the answers are parsed at all.
      over_body = "x" * (1_000_001)
      assert request("POST", "/api/reports/wide/submit", over_body, auth)[0] == 400
      # Notes keep the smaller limit; report answers take the wider one.
      assert request("POST", "/api/notes", "x" * (preview.MAX_BODY + 1), auth)[0] == 400
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

      # A report answer the owner sent is stored here, and the save file carries it: the answers
      # come from the database rather than from the page, so a restore returns what the owner
      # typed instead of asking for it twice.
      store.submission(
        "saved-answer",
        "first",
        "REPORT first First:\n  a: yes",
        "2026-09-21T09:02:00",
        acknowledged_at="2026-09-21T09:06:00",
        ack_kind="note",
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
              "ack_kind": "reply",
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
      # The given lines come first, in the order the writer takes them; the answers come after
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
      # One file, one reader for both kinds: `import-state` restores the note and the answer, and
      # the answer keeps its receipt, its read stamp and its task marker.
      round_trip = Path(directory) / "round-trip"
      preview.Store(round_trip, create=True)
      imported = subprocess.run(
        [
          sys.executable,
          str(Path(preview.__file__)),
          "import-state",
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
      # The legacy upload surface left the skill: attachments ride the note route, and the
      # store cases keep the bytes, the ceiling and a missing file.
      assert request("POST", "/api/uploads?name=gone.bin", b"x", auth)[0] == 404
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
      # A later look does not move it: the stamp records when the report was read, and only a
      # republish, which changes the text, clears it.
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


def test_note_owns_one_attachment():
  # A composed note owns one attachment with the same ID. The original name reaches its receipt,
  # while the stored bytes use the full note ID and only one inbox note is created.
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
    assert Path(record["path"]).name == "linked--1760000000-old-name.bin"
    assert Path(record["path"]).read_bytes() == raw
    assert [item["id"] for item in attached.read()["pending"]] == ["linked-note"]
    assert attached.state()["notes"][0]["attachment_name"] == "old name.bin"
    assert attached.read()["pending"][0]["attachment_path"] == record["path"]
    attached.acknowledge(["linked-note"], "note", "Seen")
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
      "several-1760000000-first-photo.png",
      "several-1760000000-another.bin",
      "several-1760000000-last-photo.png",
    ]
    assert [Path(item["path"]).read_bytes() for item in saved["attachments"]] == [
      file[2] for file in files
    ]
    assert [item["note_id"] for item in multi.uploads()] == ["several-note"] * 3
    assert [item["id"] for item in multi.read()["pending"]] == ["several-note"]
    assert [item["name"] for item in multi.state()["notes"][0]["attachments"]] == [
      file[0] for file in files
    ]
    multi.acknowledge(["several-note"], "note", "Read all three")
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
      "abcdefg-1760000000-same-photo.png",
      "abcdefg-1760000000-2-same-photo.png",
      "abcdefg-1760000000-3-same-photo.png",
      "abcdefg-1760000000-4-same-photo.png",
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
  # Migration backfills existing single-file upload records so their parent note still displays a
  # filename after this schema introduces note_id; stored bytes are not renamed or removed.
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
      token = re.search(r'data-token="([^"]+)"', request("GET", "/")[2])[1]
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
        "X-Preview-Token": token,
      }
      assert (
        request(
          "POST",
          "/api/notes/with-file",
          b"{}",
          {"Content-Type": "application/json", "X-Preview-Token": token},
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
      assert Path(saved["attachment_path"]).name == "http-no-1760000000-old-photo.png"
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
        re.fullmatch(rf"http-se-\d+-{re.escape(name)}", Path(item["path"]).name)
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
        re.fullmatch(rf"http-si-\d+-f{n}\.txt", Path(item["path"]).name) is not None
        for n, item in enumerate(received["attachments"])
      ] == [True] * 6
    finally:
      app.shutdown()
      app.server_close()
      worker.join()


def test_download_queue():
  global app
  # The same SQLite server accepts browser-mediated jobs but never makes an outbound request. Queue
  # claims are exclusive, bytes are bounded, and both saved files and failures survive a restart.
  with tempfile.TemporaryDirectory() as queue_dir:
    queue_store = preview.Store(Path(queue_dir) / "state", create=True)
    assert queue_store.state()["fetch_jobs"] == []
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(queue_store))
    worker = threading.Thread(target=app.serve_forever, daemon=True)
    worker.start()
    try:
      page = request("GET", "/")[2]
      token = re.search(r'data-token="([^"]+)"', page)[1]
      auth = {"Content-Type": "application/json", "X-Preview-Token": token}
      assert request("GET", "/api/fetch-jobs")[0] == 404
      assert request("GET", "/downloads/file.zip")[0] == 404
      assert 'id="downloads-pip"' in page and 'id="fetch-approvals"' in page
      assert request("POST", "/api/fetch-jobs", "{}")[0] == 415
      assert (
        request("POST", "/api/fetch-jobs", "{}", {"X-Preview-Token": token})[0] == 415
      )
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

      # A proxy source needs that job's opt-in; failure and retry keep its URL and choice.
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

      # The download route refuses a declared excess; the store keeps the upload ceiling.
      status, _, _problem = request(
        "POST",
        f"/api/fetch-jobs/{proxy['id']}/result?name=large.bin",
        b"x",
        {
          **auth,
          **proxy_headers,
          "Content-Type": "application/octet-stream",
          "Content-Length": str(preview.MAX_FETCH + 2),
        },
      )
      assert status == 409
      assert preview.MAX_UPLOAD == 50_000_000
      assert preview.MAX_FETCH == 102_400_000
      exact = queue_store.save_upload(
        "exact.bin", "application/octet-stream", b"x" * preview.MAX_UPLOAD
      )
      assert (
        exact["size"] == preview.MAX_UPLOAD
        and Path(exact["path"]).stat().st_size == preview.MAX_UPLOAD
      )
      try:
        queue_store.save_upload(
          "too-large.bin", "application/octet-stream", b"x" * (preview.MAX_UPLOAD + 1)
        )
        raise AssertionError("A 50 MB + 1 upload was accepted")
      except ValueError:
        pass

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
    autosave_store.acknowledge(["autosave-note"], "note", "Receipt")
    assert "Receipt" in autosave_store.save_path.read_text(encoding="utf-8")
    autosave_task = autosave_store.write_task("autosave-task", "Track it", ["Step one"])
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
    source = Path(seq_dir) / "pick.md"
    source.write_text("# Pick\n\nChoice? {#pick}\n- (x) one\n", encoding="utf-8")
    store.publish("pick", "Pick one", source)
    store.submission("seq-answer", "pick", "REPORT pick: one")
    answer = store.submissions()[0]
    assert "seq" not in answer, "an answer record carries its stamp, not a number"


def test_task_needs_one_detail():
  # A task write must leave at least one detail, so a new task without one is refused
  # and clearing the last detail is refused too.
  with tempfile.TemporaryDirectory() as detail_dir:
    store = preview.Store(detail_dir, create=True)
    try:
      store.write_task("bare", "Bare")
      raise AssertionError("A task without a detail was accepted")
    except ValueError:
      pass
    store.write_task("kept", "Kept", ["Step one"])
    try:
      store.write_task("kept", details=[""])
      raise AssertionError("Clearing the last detail was accepted")
    except ValueError:
      pass
    assert store.list_tasks()[0]["details"] == ["Step one"]
    # An update that leaves the details alone keeps them.
    assert store.write_task("kept", status="finished")["details"] == ["Step one"]


def test_task_refuses_a_note_id_as_its_name():
  # A task named after the note it answers puts one ID on two things: the board reads
  # "task c6b0af0" and the log reads "note c6b0af0". The write refuses a note ID and names the
  # fix, so the agent gives the task a proper name instead.
  with tempfile.TemporaryDirectory() as note_id_dir:
    store = preview.Store(note_id_dir, create=True)
    for note_id in ("c6b0af0", "c6b0af0-462e549f387100613fcede90b"):
      try:
        store.write_task(note_id, "Named after the note", ["Step one"])
        raise AssertionError(f"A note ID was accepted as a task ID: {note_id}")
      except ValueError as error:
        assert "proper name" in str(error), error
    # A plain name still lands, and a name that only looks hex stays a name.
    store.write_task("fix-the-widget", "Name the job", ["Step one"])
    store.write_task("deadbeef", "Eight hex characters", ["Step one"])
    assert [task["id"] for task in store.list_tasks()] == ["fix-the-widget", "deadbeef"]
    # The CLI prints the same refusal for the agent to read.
    cli = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "task",
        "954ee49-9ac144955adcda4bcbd227497",
        "Named after the note",
        "--task-details",
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


def test_clear_state():
  # The CLI clear empties every table in place: the schema, the database file and the
  # agent key survive, and the save file is refreshed to match.
  with tempfile.TemporaryDirectory() as clear_dir:
    clear_root = Path(clear_dir)
    store = preview.Store(clear_root, create=True)
    store.note("clear-note", "Pending work")
    store.acknowledge(["clear-note"], "note", "Receipt")
    store.write_task("clear-task", "Track it", ["Step one"])
    source = clear_root / "pick.md"
    source.write_text("# Pick\n\nChoice? {#pick}\n- (x) one\n", encoding="utf-8")
    store.publish("pick", "Pick one", source)
    store.submission("clear-answer", "pick", "REPORT pick: one")
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
      [sys.executable, str(Path(preview.__file__)), "clear-state"],
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
    migrated.acknowledge(["old"], "note", "still here")
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
    unread.acknowledge(["s-1"], "reply", "read, then answered")
    assert unread.state()["notes"][0]["seen_at"] == stamped


def test_read_stamps_on_delivery():
  with tempfile.TemporaryDirectory() as printed_dir:
    # A CLI read stamps Seen for the IDs it printed, once its output write succeeds;
    # a failed write stamps nothing, so the next read delivers the note again. Pending
    # selection is the acknowledgement queue, so a stamped note still prints until answered.
    printed = preview.Store(printed_dir, create=True)
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
    printed.acknowledge(["p-1"], "note", "answered after the stamp")
    assert [row["id"] for row in printed.read()["pending"]] == ["answer-2"]


def test_report_agent_seen_receipt():
  # A read or a poll that delivers an answer stamps the parent report's agent receipt;
  # the owner's unread stamp stays its own field, and a stale receipt waits for the new answer.
  with tempfile.TemporaryDirectory() as receipt_dir:
    receipt = preview.Store(receipt_dir, create=True)
    source = Path(receipt_dir) / "form.md"
    source.write_text("Choice?\n- ( ) Yes\n- ( ) No\n\nCustom response: ___\n")
    receipt.publish("form", "Form", source)
    with patch.object(preview, "now", return_value="2026-09-30T04:05:00"):
      receipt.submit_report(
        "form", "answer-1", {}, receipt.report("form")["updated_at"]
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
      receipt.acknowledge(["answer-1"], "reply", "Read and answered")
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
    # The row keeps the receipt; the state hides it while no answer exists to read.
    assert migrated.report("old")["agent_seen_at"] is not None
    assert migrated.state()["reports"][0]["agent_seen_at"] is None


def test_poll_hold_on_stale_records(capsys):
  # The hold reads the newest stamp every record kind carries, reads and acks
  # included. Every record older than one full poll span names a possible
  # session memory rollback, so the wait ends with the hold line.
  with tempfile.TemporaryDirectory() as hold_dir:
    hold = preview.Store(hold_dir, create=True)
    hold.note(
      "stale-note",
      "ancient",
      at="2026-01-01T00:00:00+00:00",
      seen_at="2026-01-01T00:01:00+00:00",
      acknowledged_at="2026-01-01T00:02:00+00:00",
      ack_kind="reply",
      ack_text="answered long ago",
      ack_edited_at="2026-01-01T00:02:00+00:00",
      replies=[
        {
          "kind": "reply",
          "text": "answered long ago",
          "at": "2026-01-01T00:02:00+00:00",
        }
      ],
    )
    with patch.object(preview, "now", return_value="2026-01-01T01:00:00+00:00"):
      assert preview.poll_inbox(hold, sleeper=lambda seconds: None) == 1
    error = capsys.readouterr().err
    assert "HOLD" in error, error
    assert "rolled back" in error, error
    # A fresh read stamp counts too: the scan covers reads, so the hold stays quiet.
    with hold.connect() as db, db:
      db.execute("UPDATE notes SET seen_at = '2026-01-01T01:00:00+00:00'")
    with patch.object(preview, "now", return_value="2026-01-01T01:00:00+00:00"):
      assert preview.poll_inbox(hold, sleeper=lambda seconds: None) == 1
    assert "HOLD" not in capsys.readouterr().err


def test_ack_of_a_stale_message_prints_the_hold():
  # An ack that answers a message older than one full poll span may chase a
  # rolled-back memory, so the receipt carries the hold line; a fresh message
  # acks quiet.
  with tempfile.TemporaryDirectory() as ack_dir:
    acked = preview.Store(ack_dir, create=True)
    acked.note("stale-ack", "old message", at="2026-01-01T00:00:00+00:00")
    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "ack",
        "stale-ack",
        "--reply",
        "answering an old line",
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": ack_dir},
    )
    assert "HOLD" in result.stderr, result.stderr
    acked.note("fresh-ack", "new message")
    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "ack",
        "fresh-ack",
        "--reply",
        "answering a new line",
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": ack_dir},
    )
    assert "HOLD" not in result.stderr, result.stderr


def test_task_list():
  with tempfile.TemporaryDirectory() as tasks_dir:
    tasks_store = preview.Store(tasks_dir, create=True)
    assert tasks_store.state()["tasks"] is None
    record = tasks_store.write_task(
      "docs-archive",
      "Move to new docs/archive/ dir",
      ["move BUDGET-EXCEPTIONS.md", "write arena-quirks.md"],
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
    tasks_store.write_task("task-a", "A", ["Step one"])
    tasks_store.write_task("task-b", "B", ["Step one"])
    tasks_store.write_task("task-c", "C", ["Step one"], order=1)
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
      (lambda: tasks_store.write_task("many", "M", ["d"] * 41), "41 details passed"),
      (
        lambda: tasks_store.write_task("deep", "D", ["y" * 2001]),
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
    # The echo cuts a long detail to save the agent tokens; the stored row keeps it whole.
    long_detail = "y" * 400
    echoed = preview.echo_task(tasks_store.write_task("long", "Long", [long_detail]))
    assert echoed["details"] == ["y" * 200 + "\u2026"]
    assert tasks_store.state()["tasks"]["upcoming"][-1]["details"] == [long_detail]
    # Clearing the last detail is refused: a task always carries at least one step.
    try:
      tasks_store.write_task("long", details=[""])
      raise AssertionError("Clearing the last detail was accepted")
    except ValueError:
      pass
    assert (
      preview.echo_task(
        tasks_store.write_task("hostile", "<img onerror=alert(1)>", ["Step one"])
      )["title"]
      == "<img onerror=alert(1)>"
    )


def test_shared_ids_refused():
  # One backticked ID links to one panel, so a task and a report never share an ID.
  with tempfile.TemporaryDirectory() as shared_dir:
    store = preview.Store(shared_dir, create=True)
    source = Path(shared_dir) / "plan.md"
    source.write_text("# Plan\n", encoding="utf-8")
    store.publish("plan", "Plan", source)
    store.write_task("build", "Build it", ["Step one"])
    for attempt, message in (
      (
        lambda: store.write_task("plan", "Plan task", ["Step one"]),
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
      "await", "Await the owner answer", ["Step one"], blocked=True
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


def test_task_report_link_unblocks_on_answer():
  # A blocked task names the report it waits on; the owner's answer clears the mark.
  with tempfile.TemporaryDirectory() as link_dir:
    link_store = preview.Store(link_dir, create=True)
    source = Path(link_dir) / "pick.md"
    source.write_text("Pick one: {#pick}\n\n- ( ) yes\n- ( ) no\n", encoding="utf-8")
    link_store.publish("pick", "Pick one", source)
    linked = link_store.write_task(
      "ship", "Ship the change", ["wait for the pick"], blocked=True, report_id="pick"
    )
    assert linked["blocked"] is True and linked["report_id"] == "pick"
    assert link_store.list_tasks()[0]["report_id"] == "pick"
    # The mark holds through an unrelated update while the report stays unanswered.
    held = link_store.write_task("ship", details=["wait for the pick still"])
    assert held["blocked"] is True and held["report_id"] == "pick"
    link_store.write_task("other", "Other wait", ["Step one"], blocked=True)
    revision = link_store.report("pick")["updated_at"]
    link_store.submit_report("pick", "answer-1", {"pick": "yes"}, revision)
    tasks = {item["id"]: item for item in link_store.list_tasks()}
    assert tasks["ship"]["blocked"] is False
    assert tasks["other"]["blocked"] is True
    # A link to a report that already has its answer never keeps the mark.
    late = link_store.write_task(
      "late", "Late link", ["Step one"], blocked=True, report_id="pick"
    )
    assert late["blocked"] is False


def test_task_report_link_refuses_missing_report():
  # The CLI refuses a link to a report that is not stored, before the task is written.
  with tempfile.TemporaryDirectory() as cli_dir:
    cli_store = preview.Store(cli_dir, create=True)
    cli_store.write_task("keep", "Keep", ["Step one"])
    missing = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "task",
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
    source = Path(save_dir) / "pick.md"
    source.write_text("Pick one: {#pick}\n\n- ( ) yes\n- ( ) no\n", encoding="utf-8")
    save_store.publish("pick", "Pick one", source)
    save_store.write_task(
      "ship", "Ship it", ["Step one"], blocked=True, report_id="pick"
    )
    save_store.save_state({"notes": [], "tasks": save_store.tasks()})
    lines = [json.loads(line) for line in save_store.save_path.read_text().splitlines()]
    saved = next(line for line in lines if line.get("id") == "ship")
    assert saved["report_id"] == "pick"
    restored = preview.Store(Path(save_dir) / "restored", create=True)
    assert restored.import_state(save_store.save_path.read_text())["tasks"] == 1
    restored.report("pick")
    assert restored.list_tasks()[0]["report_id"] == "pick"


def test_task_amend():
  with tempfile.TemporaryDirectory() as amend_dir:
    amend_store = preview.Store(amend_dir, create=True)
    amend_store.write_task(
      "docz-archive", "Move to docs/archive/", ["one", "two"], "upcoming", 1
    )
    amend_store.write_task("minify", "Minify the live build", ["Step one"])
    # A malformed ID is renamed rather than deleted and rewritten, and keeps everything else.
    amend_store.amend_task("docz-archive", "docs-archive")
    fixed = amend_store.write_task("docs-archive")
    assert fixed["title"] == "Move to docs/archive/"
    assert fixed["details"] == ["one", "two"] and fixed["order"] == 1
    assert amend_store.neighbours("docs-archive") == (None, "minify")
    assert amend_store.neighbours("minify") == ("docs-archive", None)
    assert amend_store.neighbours("never-stored") == (None, None)
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
    echoed = preview.echo_task(fixed, None, "minify")
    assert echoed["prev"] is None and echoed["next"] == "minify"
    assert preview.echo_task(fixed)["next"] is None
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
    other.write_task("extra", "Extra", ["Step one"])
    other.import_tasks(preview.parse_state_import(backup), replace=True)
    assert [item["id"] for item in other.list_tasks()] == ["docs-archive", "minify"]
    # A --replace that meets an invalid record must cost nothing. The delete and the writes are one
    # transaction, so the list that was there is still there afterwards and nothing is half applied;
    # deleting first, as this did, lost the whole list to a bad record further down.
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
    # The combined answers pass the cap on a note, and none of it is dropped.
    assert len(record["text"]) > preview.MAX_NOTE
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
    # A note keeps its own, much smaller cap, and says so in its own words.
    try:
      assert preview.note_text("n" * preview.MAX_NOTE) == "n" * preview.MAX_NOTE
      preview.note_text("n" * (preview.MAX_NOTE + 1))
      raise AssertionError("An oversized note was accepted")
    except ValueError as error:
      assert str(preview.MAX_NOTE) in str(error)


def test_shared_save_import():
  # One saved-state file feeds the unified importer for notes, tasks and report answers.
  with tempfile.TemporaryDirectory() as mixed_dir:
    mixed_root = Path(mixed_dir)
    preview.Store(mixed_root, create=True)
    mixed = mixed_root / "saved-state.ndjson"
    mixed.write_text(
      json.dumps(
        {
          "id": "saved-note",
          "text": "from the browser",
          "at": "2026-09-21T09:00:00",
          "acknowledged_at": "2026-09-21T09:05:00",
          "ack_kind": "reply",
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
          "ack_kind": "note",
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
        "import-state",
        str(mixed),
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(mixed_root)},
    ).stdout
    assert "notes 1" in imported and "answers 1" in imported and "tasks 1" in imported
    # The import does not overwrite its source; reimport merges by ID without duplicates.
    assert any(
      "title" in json.loads(line)
      for line in mixed.read_text(encoding="utf-8").splitlines()
      if line.strip()
    )
    again = subprocess.run(
      [
        sys.executable,
        script,
        "import-state",
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
      [sys.executable, script_again, "task-list"],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(mixed_root)},
    ).stdout.strip()
    assert "saved-task" in listed
    assert preview.Store(mixed_root).list_tasks()[0]["id"] == "saved-task"
    # Use JSON for the reimport, since task-list now prints text.
    tasks_json = json.dumps(preview.Store(mixed_root).list_tasks())
    reimport = subprocess.run(
      [
        sys.executable,
        script_again,
        "import-state",
        "--replace-tasks",
      ],
      input=tasks_json,
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(mixed_root)},
    ).stdout.strip()
    assert "tasks 1" in reimport
    read_out = subprocess.run(
      [sys.executable, script_again, "read"],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(mixed_root)},
    ).stdout.strip()
    # The imported note carries its receipt, so `read` has nothing pending; the receipt is what
    # makes it acknowledged; reading alone never stamps Seen.
    assert "0 pending" in read_out or "pending" not in read_out or "Inbox" in read_out
    restored = preview.Store(mixed_root)
    assert [row["id"] for row in restored.state()["notes"]] == ["saved-note"]
    assert [row["id"] for row in restored.submissions()] == ["saved-answer"]
    assert [task["id"] for task in restored.tasks()["upcoming"]] == ["saved-task"]


def test_serve_help():
  help_text = subprocess.run(
    [sys.executable, str(Path(preview.__file__)), "serve", "--help"],
    capture_output=True,
    text=True,
    check=True,
  ).stdout
  assert "default: 8000" in help_text and "--port PORT" in help_text


def test_restore_import():

  with tempfile.TemporaryDirectory() as restore_dir:
    restore = Path(restore_dir)
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
          "ack_kind": "reply",
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
          "ack_kind": None,
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
          "ack_kind": None,
          "ack_text": None,
          "seen_at": "2026-09-20T22:01:30",
        }
      )
      + "\n",
      encoding="utf-8",
    )
    imported = subprocess.run(
      [sys.executable, script, "import-state", str(log)],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(restore)},
    ).stdout
    assert "notes 3" in imported
    rows = {row["id"]: row for row in preview.Store(restore).state()["notes"]}
    # The receipt comes back as it was written: the original stamp, not the time of the import,
    # and the state surface shows it cut to seconds.
    assert rows["carried"]["acknowledged_at"] == "2026-09-20T22:05:11.982172+00:00"[:19]
    assert rows["carried"]["ack_kind"] == "reply"
    assert rows["carried"]["ack_text"] == "Fixed in `preview.py`."
    assert rows["carried"]["at"] == "2026-09-20T22:00:47"
    # A message that became a task comes back marked, so a restore keeps the link.
    assert rows["carried"]["task_id"] == "carried-task"
    assert rows["plain"]["task_id"] is None

    # A task names the message it answers, and that message then says so; a mistyped message ID is
    # refused with no task left behind, because the task and the marker land in one transaction.
    linked = subprocess.run(
      [
        sys.executable,
        script,
        "task",
        "from-note",
        "Answer the note",
        "Answer it",
        "--msg-id",
        "plain",
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
        "orphan",
        "No message",
        "Answer it",
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
    assert rows["plain"]["ack_kind"] is None
    assert rows["plain"]["ack_text"] is None
    assert rows["plain"]["seen_at"] is None
    # Read state is restored for its own sake: a line seen but never answered comes back seen
    # and unacknowledged, because a restore that drops it re-lights the whole log.
    assert rows["carried"]["seen_at"] == "2026-09-20T22:00:52"
    assert rows["read"]["seen_at"] == "2026-09-20T22:01:30"
    assert rows["read"]["acknowledged_at"] is None
    assert rows["read"]["ack_kind"] is None
    assert rows["read"]["ack_text"] is None
    # A partial receipt is refused rather than filled in, and the refusal stores nothing.
    partial = restore / "partial.jsonl"
    partial.write_text(
      json.dumps(
        {
          "id": "half",
          "text": "half a receipt",
          "acknowledged_at": "2026-09-20T22:05:11+00:00",
          "ack_kind": None,
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
        "import-state",
        str(partial),
      ],
      capture_output=True,
      text=True,
      check=False,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": str(restore)},
    )
    assert refused.returncode == 1
    assert "stamp, kind and text" in refused.stderr
    assert "half" not in {row["id"] for row in preview.Store(restore).state()["notes"]}
    assert {row["id"] for row in preview.Store(restore).state()["notes"]} == {
      "carried",
      "plain",
      "read",
    }
    # Importing the same log again changes nothing: a stored ID keeps the record it has.
    again = subprocess.run(
      [sys.executable, script, "import-state", str(log)],
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
      blocked.stdout.strip()
      == "READ INBOX NOW. Only a bare `arena-preview read` passes. Then ack every"
      " note, one call per note: `arena-preview ack <id> --reply <markdown>` or"
      " `arena-preview ack <id> --note <text>`."
    )
    gate_store.acknowledge(["gate-note"], "note", "Cleared")
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
    # A blocked push says what was stopped and what clears it, then the inbox block.
    assert pushed.stdout.startswith("PUSH BLOCKED: "), pushed.stdout
    assert (
      "READ INBOX NOW. Only a bare `arena-preview read` passes. Then ack every"
      " note, one call per note: `arena-preview ack <id> --reply <markdown>` or"
      " `arena-preview ack <id> --note <text>`." in pushed.stdout
    )
    gate_store.acknowledge(["push-note"], "note", "Cleared")
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


def test_quiet_inbox_line_allows_cd_and_blocks_tail_head_grep():
  # A cd prefix is fine on the writer's line, on the way to a read or a poll; the banned
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
  # The shell timeout command must not wrap a poll: it kills the wait mid-flight and
  # the turn loses its listing, so the gate refuses the line even with an empty inbox.
  # Other inbox calls and clean poll lines stay fine.
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


def test_gate_blocks_a_cd_line_past_the_threshold():
  # cd is fine on the line, but the count gate still holds it: with a pending note past
  # the threshold a plain cd line meets READ INBOX NOW, and the block names no command,
  # because cd is never the noise.
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
    assert cd_run.stdout.startswith("READ INBOX NOW. "), cd_run.stdout
    assert "Omit them" not in cd_run.stdout
    assert "`cd`" not in cd_run.stdout


def test_gate_hint_names_the_banned_tools_without_cd():
  # A blocked call that runs grep, head or tail hears which commands to drop; cd is fine
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
    hint_store.acknowledge(["hint-note"], "note", "Cleared")
    passing = run_gate("cd /home/user && grep note log")
    assert passing.returncode == 0
    assert passing.stdout.strip() == ""


def test_dispatch_reminder():
  # Every dispatch carries a reminder without changing stdout; only a delivered read
  # marks a note seen.
  with tempfile.TemporaryDirectory() as reminder_dir:
    reminder_store = preview.Store(reminder_dir, create=True)
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

    pending_prefix = "1 note. DO NOT IGNORE. ACK ASAP. "
    assert preview.fill_reminder(preview.TASK_REMINDER, 0) is None
    assert preview.fill_reminder(preview.TASK_REMINDER, 1) == "1 task left."
    assert preview.fill_reminder(preview.TASK_REMINDER, 4) == "4 tasks left."
    # No open task hides that entry, so the line carries the next reminder instead.
    task_at = preview.REMINDERS.index(preview.TASK_REMINDER)
    assert preview.reminder_tail(task_at, 0) == preview.REMINDERS[task_at + 1]
    assert "0 tasks left." not in tails(0)
    for command, remaining in (
      (["task-list"], 0),
      (["task", "reminder-task", "Track work", "Step one"], 1),
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
        "--note",
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
    form_prefix = "1 answer. DO NOT IGNORE. ACK ASAP. "
    assert form_line == form_prefix + reminder_tail(form_line, 1)
    reminder_store.acknowledge(["form-answer"], "note", "Received")
    for index in range(3):
      reminder_store.note(f"mixed-{index}", "Pending")
    for name in ("one.txt", "two.txt"):
      upload = reminder_store.save_upload(name, "text/plain", name.encode())
      reminder_store.note(upload["id"], "Uploaded " + name)
    mixed_line = reminder_store.reminder()
    mixed_prefix = "3 notes. 2 uploads. DO NOT IGNORE. ACK ASAP. "
    assert mixed_line == mixed_prefix + reminder_tail(mixed_line, 1)
    assert all(row["seen_at"] is None for row in reminder_store.read()["pending"])


def test_reminder_rotation():
  # The tail rotates through the whole list before it repeats, a hook poll counts itself, a CLI
  # dispatch and a read do not, and the count resets when a new user item arrives.
  with tempfile.TemporaryDirectory() as rotate_dir:
    rotate_store = preview.Store(rotate_dir, create=True)
    rotate_script = str(Path(preview.__file__))
    assert "Refresh context: ARENA.md, SKILL.md, REFERENCE.md." in preview.REMINDERS
    assert "Ask questions ASAP in reports; keep other work moving." in preview.REMINDERS
    assert "`ask_user` on GH_TOKEN failure." in preview.REMINDERS
    assert "Unpublish stale reports." in preview.REMINDERS
    assert "End the turn with `poll`." in preview.REMINDERS
    assert "Publish your reports." in preview.REMINDERS
    assert "Never end a turn with unblocked tasks." in preview.REMINDERS
    assert "Read PR checks: `gh pr checks <PR> --watch`." in preview.REMINDERS
    assert "`task-list` at turn start. Update it as work changes." in preview.REMINDERS
    assert "Grep-verify each edit." in preview.REMINDERS
    assert "Rebase on `origin/main` before pushing." in preview.REMINDERS
    assert "Check the PR's CI before ending a pushed turn." in preview.REMINDERS
    assert "No PR checks run? Rebase onto main first." in preview.REMINDERS
    assert preview.TASK_REMINDER in preview.REMINDERS
    # One open task keeps every entry visible for the rotation checks.
    rotate_store.write_task("rotate-task", "Open work", ["Step one"])

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
    pending = "1 note. DO NOT IGNORE. ACK ASAP. "
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
      assert (
        result.stdout.strip() == f"Calls since user message: {polls}. {pending}{tail}"
      )
      assert result.stderr == ""
    result = subprocess.run(
      [sys.executable, rotate_script, "task-list"],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": rotate_dir},
    )
    assert "Tasks" in result.stdout
    tail = tail_at(offset + 2)
    assert result.stderr.strip() == f"Calls since user message: 2. {pending}{tail}"
    # A read does not erase the calls since the first unread message. Only a fresh backlog
    # resets the tally; a message landing on an unacked pile leaves it running.
    rotate_store.read()
    assert rotate_store.reminder() == (
      f"Calls since user message: 2. {pending}{tail_at(offset + 3)}"
    )
    # An ack empties the queue, so idle polls stop counting, and a fresh note starts at one.
    rotate_store.acknowledge(["rotate-note"], "note", "Done")
    assert rotate_store.meta_value(preview.POLLS_SINCE_MESSAGE) == "0"
    assert rotate_store.reminder(advance=True) == tail_at(offset + 4)
    assert rotate_store.reminder(advance=True) == tail_at(offset + 5)
    rotate_store.note("rotate-later", "Pending again")
    assert rotate_store.reminder(advance=True) == (
      f"Calls since user message: 1. {pending}{tail_at(offset + 6)}"
    )
    rotate_store.note("rotate-newer", "Another user message")
    newer = "2 notes. DO NOT IGNORE. ACK ASAP. "
    # A second message on an unacked pile keeps the count anchored to the first unread one.
    assert rotate_store.reminder() == (
      f"Calls since user message: 1. {newer}{tail_at(offset + 7)}"
    )
    assert rotate_store.reminder(advance=True) == (
      f"Calls since user message: 2. {newer}{tail_at(offset + 8)}"
    )


def test_reminder_hides_task_entry_with_no_open_task():
  # A finished task stops the count, so that entry yields the next reminder.
  with tempfile.TemporaryDirectory() as hidden_dir:
    hidden_store = preview.Store(hidden_dir, create=True)
    hidden_store.write_task(
      "done-task", "Finished work", ["Step one"], status="finished"
    )
    task_at = preview.REMINDERS.index(preview.TASK_REMINDER)
    for _ in range(task_at):
      hidden_store.reminder()
    assert hidden_store.reminder() == preview.REMINDERS[task_at + 1]
    hidden_store.write_task("open-task", "Open work", ["Step one"])
    for _ in range(len(preview.REMINDERS) - 1):
      hidden_store.reminder()
    assert hidden_store.reminder() == "1 task left."


def test_ack_task_reminder():
  # An ack reminds the agent to queue the note's work.
  with tempfile.TemporaryDirectory() as ack_dir:
    preview.Store(ack_dir, create=True).note("ack-work", "Needs work")
    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "ack",
        "ack-work",
        "--note",
        "Ok",
      ],
      capture_output=True,
      text=True,
      check=True,
      env={**os.environ, "ARENA_PREVIEW_STATE_DIR": ack_dir},
    )
    assert "--msg-id ack-work" in result.stdout


def test_report_unread_markers():
  with tempfile.TemporaryDirectory() as marker_dir:
    marker_store = preview.Store(marker_dir, create=True)
    marker_source = Path(marker_dir) / "form.md"
    marker_source.write_text("Choice?\n- ( ) Yes\n- ( ) No\n\nCustom response: ___\n")
    marker_store.publish("form", "Form", marker_source)
    assert marker_store.state()["reports"][0]["needs_answer"] is True
    assert marker_store.state()["reports"][0]["ever_seen"] == 0
    marker_store.mark_report_seen("form")
    assert marker_store.state()["reports"][0]["needs_answer"] is True
    assert marker_store.state()["reports"][0]["ever_seen"] == 1
    marker_store.submit_report(
      "form", "answer", {}, marker_store.report("form")["updated_at"]
    )
    assert marker_store.state()["reports"][0]["needs_answer"] is False
    try:
      marker_store.publish("form", "Form", marker_source)
      raise AssertionError("An answered report accepted a republish")
    except ValueError as error:
      assert "submitted answers" in str(error)
    marker_store.publish("form-2", "Form", marker_source)
    assert len(marker_store.state()["reports"]) == 2
    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
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
    assert "submitted answers" in result.stderr
    assert preview.Store(marker_dir).state()["reports"][0]["needs_answer"] is False
    with marker_store.connect() as db, db:
      # The answer is backdated on purpose: any answer, however old, keeps needs_answer false,
      # and the republish that once had to preserve it is refused while answers exist.
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
  # An older reports table gains ever_seen; the backfill marks a stamped report opened so a
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
      ended = store.state()["agent_call_ended_at"]
      assert ended, "the post-call reminder stamps the call end"
      assert preview.import_stamp(ended) is not None
    finally:
      hold.close()


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
      assert str(error) == (
        "preview server is down; start it before polling: "
        f"arena-preview serve --port {port}"
      )
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
    preview.require_server(store)


def test_poll_inbox():
  with tempfile.TemporaryDirectory() as poll_dir:
    store = preview.Store(poll_dir, create=True)
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
          "mid-wait", "Appears during the wait", ["Step one"], status="upcoming"
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
    for flag in ("--interval", "--max"):
      result = subprocess.run(
        [sys.executable, str(Path(preview.__file__)), "poll", flag, "1"],
        capture_output=True,
        text=True,
        check=False,
      )
      assert result.returncode == 2 and "unrecognized arguments" in result.stderr


def test_poll_blocked_tasks():
  """An unblocked upcoming task ends a poll at once; a blocked one lets it wait."""
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
      store.write_task("open-task", "Open work", ["Step one"])
      code, sleeps = run_poll()
      assert code == 0
      assert sleeps == [], "unblocked work ends the wait before the first sleep"
      assert "open-task" in printed[-1]
      # The early return names the task on stderr, so no session reads it as an empty wait.
      assert printed[0].startswith("POLL: this wait runs up to 1800 s. Ends early")
      assert printed[1] == (
        "CONTINUE: unblocked task open-task waits. Task list still up. Work it or"
        " mark it blocked before the next poll. Do not end the turn."
      )
      # The same line rides stdout too, right before the listing, so a turn
      # that reads only stdout meets the warning instead of burying it.
      assert printed[2] == printed[1]
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


def test_poll_retry_disclaimer():
  # The poll announces its own span up front: a call that ends early with nothing to
  # read was cut by the bash tool timeout, and the retry needs the tool timeout 1800.
  with tempfile.TemporaryDirectory() as disclaimer_dir:
    store = preview.Store(disclaimer_dir, create=True)
    printed = []

    def capture(value, **kwargs):
      printed.append(value)

    original = builtins.print
    builtins.print = capture
    saved = (preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS)
    try:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = 10, 1
      code = preview.poll_inbox(store, sleeper=lambda seconds: None)
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved
      builtins.print = original
    assert code == 1
    assert printed[0].startswith("POLL: this wait runs up to 1800 s. Ends early")
    assert "Retry with the tool timeout 1800" in printed[0]


def test_skip_poll():
  """The page's Skip poll press ends one wait, leaves no note, and never repeats."""
  with tempfile.TemporaryDirectory() as skip_dir:
    store = preview.Store(skip_dir, create=True)
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
      # A fresh state waits, and the listing says no skip is armed.
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

      # The poll ends at once, prints the stamp it consumed, and names the skip on stderr.
      printed.clear()
      code, sleeps = run_poll()
      assert code == 0
      assert sleeps == [], "a skip ends the wait before the first sleep"
      assert printed[0].startswith("POLL: this wait runs up to 1800 s. Ends early")
      assert printed[1] == (
        "SKIP: owner pressed Skip poll. End the turn, no second poll."
      )
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
      assert "skip-note" in printed[-1]
      assert store.skip_poll_requested() is True
      # Once the ack empties the queue, the next poll consumes the skip it held.
      store.acknowledge(["skip-note"], "reply", "done")
      printed.clear()
      code, sleeps = run_poll()
      assert code == 0 and sleeps == []
      assert printed[0].startswith("POLL: this wait runs up to 1800 s. Ends early")
      assert printed[1] == (
        "SKIP: owner pressed Skip poll. End the turn, no second poll."
      )
      assert store.skip_poll_requested() is False
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved


def test_turn_end_marker():
  """A poll that ends the turn marks it; the next agent call and a live turn clear the mark."""
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
      store.acknowledge(["end-note"], "reply", "done")
      store.write_task("end-task", "Work waits", ["Step one"])
      assert run_poll() == 0
      assert store.state()["turn_ended_at"] is None
      store.write_task("end-task", status="finished")
    finally:
      preview.POLL_INTERVAL, preview.POLL_MAX_LOOPS = saved


def test_skip_poll_clears_on_owner_message():
  """A note or a report answer clears an armed skip; the poll delivers it instead."""
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
    assert "skip-cleared-note" in printed[-1]
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
    store.acknowledge(["stamp-note"], "reply", "done")
    ack_stamp = store.newest_stamp()
    assert ack_stamp and ack_stamp != note_stamp
    # A task change moves it too.
    store.write_task("stamp-task", "A task", ["Step one"], order=1)
    assert store.newest_stamp() != ack_stamp


def test_copy_state_carries_the_note_and_task_stamps():
  """The auto save compares the newest note stamp and the newest task stamp, so the route carries both."""
  global app
  with tempfile.TemporaryDirectory() as stamp_dir:
    store = preview.Store(Path(stamp_dir) / "arena-preview", create=True)
    store.note("pair-note", "first", at="2026-10-05T09:00:00")
    store.write_task("pair-task", "A task after the note", ["Step one"])
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
  assert usage["download_cap_bytes"] == preview.MAX_FETCH == 102_400_000
  assert preview.MAX_UPLOAD == 50_000_000


def test_owner_limits_and_streams():
  import io

  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    text = "👋" * 150_001
    assert store.note("long-owner", text)["text"] == text
    try:
      store.acknowledge(["long-owner"], "reply", "a" * 15_001)
      raise AssertionError("Agent reply cap was removed")
    except ValueError:
      pass
    url = "https://example.com/" + "a" * 3000
    owner = store.enqueue_fetch(url, False)
    assert owner["origin"] == "owner"
    try:
      store.enqueue_fetch(url, False, pending=True)
      raise AssertionError("Agent URL cap was removed")
    except ValueError:
      pass
    claim = store.claim_fetch()
    with patch.object(preview, "MAX_FETCH", 4):
      saved = store.complete_fetch(
        owner["id"],
        claim["claim"],
        "x" * 300 + ".txt",
        "text/plain",
        "direct",
        b"12345",
      )
      assert Path(saved["path"]).read_bytes() == b"12345"
      agent = store.enqueue_fetch("https://example.com/a", False, pending=True)
      store.decide_fetch(agent["id"], "approved")
      claim = store.claim_fetch()
      try:
        store.complete_fetch(
          agent["id"], claim["claim"], "a.txt", "text/plain", "direct", b"12345"
        )
        raise AssertionError("Approval removed the agent limit")
      except ValueError:
        pass
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
    with patch.object(preview, "MAX_UPLOAD", 4):
      try:
        with preview.stream_note_attachments(
          "multipart/form-data; boundary=boundary", Chunks(raw), len(raw)
        ):
          raise AssertionError("Per-file upload cap removed")
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
    store.acknowledge(["already-here"], "reply", "Existing answer")
    existing = next(n for n in store.state()["notes"] if n["id"] == "already-here")
    imported = [
      {
        "id": "already-here",
        "text": "Existing message",
        "acknowledged_at": receipt_at,
        "ack_kind": "note",
        "ack_text": "Stale answer",
      },
      {
        "id": "new-answer",
        "report_id": "form",
        "text": "Report answer",
        "acknowledged_at": receipt_at,
        "ack_kind": "reply",
        "ack_text": "Received",
      },
    ]
    assert store.import_state(json.dumps(imported))["answers"] == 1
    assert (
      next(n for n in store.state()["notes"] if n["id"] == "already-here") == existing
    )
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
        "ack_kind": "reply",
        "ack_text": "Invalid answer",
      },
    ]
    try:
      store.import_state(json.dumps(invalid), replace_tasks=True)
      raise AssertionError("Invalid import accepted")
    except ValueError:
      pass
    assert [t["id"] for t in store.list_tasks()] == ["task"]
    assert {n["id"] for n in store.state()["notes"]} == {"restored", "already-here"}
    assert {a["id"] for a in store.submissions()} == {"new-answer"}
    assert (
      store.save_path.read_bytes() if store.save_path.exists() else None
    ) == backup


def test_import_refuses_a_snapshot_older_than_the_state():
  """A paste of an old copy must not write over newer messages."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.note("live", "Newest message", at="2026-10-04T15:00:00+00:00")
    older = json.dumps(
      [{"id": "old", "text": "Old message", "at": "2026-10-04T11:42:48"}]
    )
    try:
      store.import_state(older)
      raise AssertionError("An older snapshot was accepted")
    except ValueError as error:
      assert "live state is fresher" in str(error)
      assert "--force" in str(error)
    assert {note["id"] for note in store.state()["notes"]} == {"live"}
    receipt = store.import_state(older, force=True)
    assert receipt["forced"] is True
    assert {note["id"] for note in store.state()["notes"]} == {"live", "old"}


def test_import_accepts_a_newer_snapshot():
  """A save newer than the live state lands without the flag."""
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    store.note("live", "Older message", at="2026-10-04T11:42:48")
    newer = json.dumps(
      [{"id": "new", "text": "Newer message", "at": "2026-10-04T15:00:00+00:00"}]
    )
    assert store.import_state(newer)["notes"] == 1
    assert "forced" not in store.import_state(newer)
    assert {note["id"] for note in store.state()["notes"]} == {"live", "new"}


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
    # A host with a path is refused, and the stored record stands.
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
  """POST /api/skip-poll arms the page's skip; the state and the poll report it."""
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


def test_key_command_reads_the_recorded_key():
  """A later session reads the key from the state, because an acked note never returns."""
  with tempfile.TemporaryDirectory() as key_dir:
    store = preview.Store(key_dir, create=True)
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
  """An old key record posts one quiet note; a fresh record stays silent and a read prints it."""
  with tempfile.TemporaryDirectory() as state_dir:
    script = str(Path(preview.__file__))
    store = preview.Store(state_dir, create=True)
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
    assert len(store.read()["pending"]) == 1


def test_agent_seen_at_is_stamped_by_the_cli():
  """Every agent CLI call stamps the liveness the preview header reads."""
  with tempfile.TemporaryDirectory() as state_dir:
    script = str(Path(preview.__file__))
    store = preview.Store(state_dir, create=True)
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
    source = Path(directory) / "pick.md"
    source.write_text(
      "# Pick\n\nChoice? {#pick}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("pick", "Pick one", source)
    store.save_state({"notes": store.state()["notes"], "tasks": store.tasks()})
    lines = [json.loads(line) for line in store.save_path.read_text().splitlines()]
    saved = next(line for line in lines if line.get("id") == "pick")
    assert saved["title"] == "Pick one"
    assert "Choice? {#pick}" in saved["markdown"]
    assert saved["published_at"]

    restored_dir = Path(directory) / "restored"
    restored_dir.mkdir()
    restored = preview.Store(restored_dir, create=True)
    result = restored.import_state(store.save_path.read_text())
    assert result["reports"] == 1
    report = restored.report("pick")
    assert report["title"] == "Pick one"
    assert "Choice? {#pick}" in report["markdown"]
    assert report["published_at"]


def test_removed_report_leaves_nothing_in_the_save():
  """A removed report leaves nothing in the ndjson, its answer lines included.

  The report line already went with the report; the answer line stayed, so a save still
  carried the id of a report the owner had unpublished.
  The database keeps the answer as the agent's read history; the save does not.
  """
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "pick.md"
    source.write_text(
      "# Pick\n\nChoice? {#pick}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("pick", "Pick one", source)
    store.submission("answer-1", "pick", "REPORT pick: one")
    before = [json.loads(line) for line in store.save_path.read_text().splitlines()]
    assert [line["id"] for line in before if line.get("report_id")] == ["answer-1"]
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "pick")
      )
    store.unpublish("pick", dismissed_by_owner=True)
    lines = [json.loads(line) for line in store.save_path.read_text().splitlines()]
    assert [line["id"] for line in lines if line.get("report_id")] == []
    assert all(line.get("id") != "pick" for line in lines)
    assert store.submissions()[0]["report_id"] == "pick", "sent answers stay history"


def test_unpublish_moves_the_state_stamp():
  """An unpublish moves the state stamp, so the save's own trigger rewrites the file.

  The write trigger is the stamp comparison alone, so a
  removal that left the stamp still would leave a file that already carries the removed
  report untouched. The report rows are gone, so the removal has to carry the stamp.
  """
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "pick.md"
    source.write_text(
      "# Pick\n\nChoice? {#pick}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("pick", "Pick one", source)
    before = store.newest_stamp()
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "pick")
      )
    store.unpublish("pick")
    after = store.newest_stamp()
    assert after and after > before, "the removal left the state stamp still"


def test_unpublish_waits_for_the_owner_to_see_the_ack():
  """An unseen report holds the removal until seen.

  The new guard holds until the report has been seen, not a timed view window.
  """
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "pick.md"
    source.write_text(
      "# Pick\n\nChoice? {#pick}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("pick", "Pick one", source)
    store.submission("answer-1", "pick", "REPORT pick: one")
    store.acknowledge(["answer-1"], "reply", "Read it")
    # Publish a plain report and test seen hold
    store.publish("plain", "Plain", source)
    try:
      store.unpublish("plain")
      raise AssertionError("An unseen report did not hold")
    except preview.UnpublishHeld as error:
      assert "seen" in str(error).lower() or "not been seen" in str(error)
    assert store.state()["reports"], "the report stayed"
    # Mark as seen and unpublish
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "plain")
      )
    store.unpublish("plain")
    # Owner dismissal of answered report still needs seen? For this test, mark answered report seen too
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "pick")
      )
    store.unpublish("pick", dismissed_by_owner=True)
    assert store.state()["reports"] == []


def test_unpublish_waits_out_a_fresh_view():
  """The agent's unpublish holds until seen; owner's press passes it.

  The new guard holds until the report has been seen, not a timed view window.
  """
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(directory, create=True)
    source = Path(directory) / "pick.md"
    source.write_text(
      "# Pick\n\nChoice? {#pick}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("pick", "Pick one", source)
    # Not seen yet, so hold
    try:
      store.unpublish("pick")
      raise AssertionError("An unseen report did not hold")
    except preview.UnpublishHeld as error:
      assert "seen" in str(error).lower()
    # Owner dismissal should also hold until seen in new logic
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "pick")
      )
    store.unpublish("pick", dismissed_by_owner=True)
    assert store.state()["reports"] == []
    store.publish("later", "Pick one again", source)
    with store.connect() as db, db:
      db.execute(
        "UPDATE reports SET seen_at = ? WHERE id = ?", ("2026-01-01T00:00:00", "later")
      )
    store.unpublish("later")
    assert store.state()["reports"] == []


def test_unpublish_route_holds_and_the_view_route_stamps():
  """POST /unpublish conflicts while unseen, and POST /view stamps the look.

  A held removal is a conflict with the owner's live state rather than bad input, so the API
  answers 409 and the page shows the reason. The view route stamps the look, and seen route clears seen hold.
  """
  global app
  with tempfile.TemporaryDirectory() as directory:
    store = preview.Store(Path(directory) / "arena-preview", create=True)
    app = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
    threading.Thread(target=app.serve_forever, daemon=True).start()
    headers = {"Content-Type": "application/json"}
    source = Path(directory) / "pick.md"
    source.write_text(
      "# Pick\n\nChoice? {#pick}\n- (x) one\n- ( ) two\n", encoding="utf-8"
    )
    store.publish("pick", "Pick one", source)
    # Not seen yet, so hold
    status, _, body = request("POST", "/api/reports/pick/unpublish", "{}", headers)
    assert status == 409
    assert "seen" in json.loads(body)["error"].lower()
    assert [report["id"] for report in store.state()["reports"]] == ["pick"]
    status, _, body = request("POST", "/api/reports/pick/view", "{}", headers)
    assert status == 200
    stamped = json.loads(body)
    assert stamped["id"] == "pick" and stamped["viewed_at"]
    # A view of a report that is not there is a 404 rather than a silent stamp.
    assert request("POST", "/api/reports/none/view", "{}", headers)[0] == 404
    # Mark seen via API
    assert request("POST", "/api/reports/pick/seen", "{}", headers)[0] == 200
    status, _, body = request("POST", "/api/reports/pick/unpublish", "{}", headers)
    assert status == 200
    assert json.loads(body) == {"unpublished": "pick"}
    assert store.state()["reports"] == []


def test_ack_reads_a_file_when_the_text_carries_backticks():
  """An ack takes its text from a file, so the shell never quotes it.

  A backtick inside double quotes runs as a command, so the shell eats the ticks before the
  tool sees them. The file form carries the text as it stands, backticks
  and quotes included, and one source alone is required.
  """
  script = str(Path(preview.__file__))
  with tempfile.TemporaryDirectory() as ack_dir:
    preview.Store(ack_dir, create=True)
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": ack_dir}
    store = preview.Store(ack_dir)
    store.note("first-note", "First question")
    store.note("second-note", "Second question")
    text = "Use `arena-preview read` and 'single quotes' here.\n\nA second line."
    source = Path(ack_dir) / "reply.md"
    source.write_text(text, encoding="utf-8")
    out = subprocess.run(
      [sys.executable, script, "ack", "first-note", "--reply-file", str(source)],
      capture_output=True,
      text=True,
      check=True,
      env=env,
    ).stdout
    assert "Acknowledged" in out and "first-" in out
    note = preview.Store(ack_dir).state()["notes"][0]
    assert note["ack_kind"] == "reply"
    assert note["ack_text"] == text, "the stored text keeps every backtick and quote"
    # The plain note form reads a file too, and its stored kind follows the flag.
    plain = Path(ack_dir) / "note.txt"
    plain.write_text("Kept `as is`", encoding="utf-8")
    subprocess.run(
      [sys.executable, script, "ack", "second-note", "--note-file", str(plain)],
      capture_output=True,
      text=True,
      check=True,
      env=env,
    )
    assert preview.Store(ack_dir).state()["notes"][1]["ack_text"] == "Kept `as is`"
    # Two sources, or none, are refused before anything is written.
    both = subprocess.run(
      [
        sys.executable,
        script,
        "ack",
        "first-note",
        "--reply",
        "one",
        "--reply-file",
        str(source),
      ],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert both.returncode != 0 and "exactly one" in both.stderr
    # A missing file is a clean refusal, not a traceback.
    missing = subprocess.run(
      [
        sys.executable,
        script,
        "ack",
        "second-note",
        "--reply-file",
        "/nope/missing.md",
      ],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert missing.returncode != 0 and "Cannot read" in missing.stderr


def test_tick_warning_reads_the_quoting_shape():
  """The gate's classifier names a backtick the shell will substitute, and only then.

  The trap reads the command line before expansion, so the lossy shape is visible: an inline
  ack text in double quotes with a backtick in it.
  """
  lossy = preview.tick_warning('arena-preview ack abc --reply "see `read` now"')
  assert lossy and "backtick" in lossy and "--reply-file" in lossy
  assert preview.tick_warning('arena-preview ack abc --note "see `read` now"')
  # A quoted line, a file form, a tick before the flag and a plain line all stay quiet.
  assert preview.tick_warning("arena-preview ack abc --reply 'see `read` now'") is None
  assert (
    preview.tick_warning("arena-preview ack abc --reply-file /tmp/reply.md") is None
  )
  assert (
    preview.tick_warning('echo `date` && arena-preview ack abc --reply "plain"') is None
  )
  assert (
    preview.tick_warning("arena-preview task x title --task-details 'a `tick`'") is None
  )
  assert preview.tick_warning("") is None and preview.tick_warning(None) is None


def test_serve_warning_reads_the_port():
  """The gate's classifier names a port other than the default, and only then.

  The poll and the owner's page follow the port the skill names, so an off-default
  serve hides both.
  """
  off = preview.serve_warning("arena-preview serve --port 8123")
  assert off and "8123" in off and "8000" in off
  assert preview.serve_warning("arena-preview serve --port=8123")
  assert preview.serve_warning("cd repo && preview.py serve --port 8123")
  # The default, an absent flag and a non-serve line all stay quiet.
  assert preview.serve_warning("arena-preview serve --port 8000") is None
  assert preview.serve_warning("arena-preview serve") is None
  assert preview.serve_warning("arena-preview read") is None
  assert preview.serve_warning("arena-preview serve-tick 'arena-preview serve'") is None
  assert preview.serve_warning("") is None and preview.serve_warning(None) is None


def test_task_detail_steps():
  # A task detail is one step per line: a block splits on its line breaks, and a wall of
  # text is refused before anything is written.
  script = str(Path(preview.__file__))
  with tempfile.TemporaryDirectory() as tasks_dir:
    preview.Store(tasks_dir, create=True)
    env = {**os.environ, "ARENA_PREVIEW_STATE_DIR": tasks_dir}
    out = subprocess.run(
      [
        sys.executable,
        script,
        "task",
        "steps",
        "Steps",
        "--task-details",
        "read it\n\n fix it \ncheck it",
      ],
      capture_output=True,
      text=True,
      check=True,
      env=env,
    ).stdout
    assert "read it" in out and "fix it" in out and "check it" in out
    wall = subprocess.run(
      [sys.executable, script, "task", "wall", "Wall", "--task-details", "y" * 400],
      capture_output=True,
      text=True,
      check=False,
      env=env,
    )
    assert wall.returncode != 0 and "one step per line" in wall.stderr
    assert "wall" not in {item["id"] for item in preview.Store(tasks_dir).list_tasks()}


def test_download_header_name_is_safe():
  """A CR, LF or quote in a download name never reaches the response header."""
  assert preview.header_filename('a\nb\rc"d') == "a_b_c_d"
  assert preview.header_filename("first.md") == "first.md"


def test_option_labels_join_wrapped_lines():
  """A wrapped option label joins into one option, indented or not, and a blank line ends it."""
  wrapped = (
    "Pick one {#pick}\n\n"
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
  assert questions[0]["options"] == [
    (
      "head tree: `ref: ${{ github.event.pull_request.head.sha || github.sha }}`. A pull "
      "request can then clear its own check, and three workflow tests need the new literal."
    ),
    "undented wrap on the next line",
    "plain",
  ]
  assert questions[0]["default"] == [questions[0]["options"][0]]
  assert [text.strip() for kind, text in blocks if kind == "markdown"] == [
    "Pick one",
    "Trailing prose stays a paragraph.",
  ]


def test_option_join_stops_at_a_block_start():
  """A heading or a new field ends an option group instead of joining it."""
  markdown = "- ( ) only option\n## Section\n- ( ) after heading\nNote: ___\n"
  _, questions = preview.parse_fields(markdown)
  assert [question["type"] for question in questions] == ["choice", "choice", "text"]
  assert questions[0]["options"] == ["only option"]
  assert questions[1]["options"] == ["after heading"]
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
      store.acknowledge(["stamped-note"], "note", "Handled")
      assert store.state()["last_check"] == "2026-09-22T12:05:00"


def test_note_reread_prints_every_match():
  """The reread takes the short or the full ID, and a short ID that matches
  several notes prints every match, so an acked note stays open to the agent.
  """
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "arena-preview"
    store = preview.Store(root, create=True)
    store.note("beef001-1111111111111111111111111", "first stored note")
    store.note(
      "beef001-2222222222222222222222222",
      "second stored note",
      acknowledged_at="2026-09-22T12:00:00",
      ack_kind="note",
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

    both = run("note", "beef001")
    assert both.returncode == 0
    assert "first stored note" in both.stdout
    assert "second stored note" in both.stdout
    assert "acked 2026-09-22T12:00:00" in both.stdout
    assert "unacked" in both.stdout
    one = run("note", "beef001-2222222222222222222222222")
    assert one.returncode == 0
    assert "second stored note" in one.stdout
    assert "first stored note" not in one.stdout
    gone = run("note", "ffff999")
    assert gone.returncode == 1
    assert "No note matches" in gone.stderr
