"""Pytest checks for the preview runtime. Run with the reporting venv's Python."""

import builtins
import hashlib
import http.client
import json
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
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
        "--state-dir",
        str(restored_dir),
        "import-notes",
        str(saved),
      ],
      check=True,
      capture_output=True,
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
      saved_lines = [json.loads(line) for line in backup.read_text().splitlines()]
      assert [line["ack_edited_seen_count"] for line in saved_lines] == [2, 2]

      restored_dir = Path(directory) / "restored"
      preview.Store(restored_dir, create=True)
      subprocess.run(
        [
          sys.executable,
          preview.__file__,
          "--state-dir",
          str(restored_dir),
          "import-notes",
          str(backup),
        ],
        check=True,
        capture_output=True,
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
    store.unpublish("pick")
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
    store = preview.Store(root, create=True, save_path=save_file)
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
      # The log filter ships in the page with its three states and its empty line.
      assert 'id="log-filter"' in page and 'id="log-empty"' in page
      # The log's jump bar ships in the page, inside the wrapper that positions it over the scroll area.
      assert 'id="log-newest"' in page and 'class="log-scroll"' in page
      assert 'aria-label="Scroll to bottom"' in page
      assert '<svg width="14" height="14" viewBox="0 0 24 24"' in page
      assert "↓ Latest message" not in page
      assert re.search(r"\.log-newest\s*\{[^}]*border-radius:\s*4px", page)
      # The bar hugs its label rather than spanning the pane.
      assert "translateX(-50%)" in page
      # The save button sits in the top bar after the theme button rather than in the log's own row, on
      # owner note 0f27a2b6; the log's row keeps the filter immediately left of copy-log, on owner notes
      # 1006cb38 and 7f52e5fe: a button moved between them is what the first note caught. The log's own
      # copy and the tasks' copy are gone, and one copy button carries the state to the clipboard.
      assert (
        page.index('id="theme"')
        < page.index('id="copy-state"')
        < page.index('id="notes-panel"')
      )
      assert page.index('id="log-filter"') < page.index('id="refresh-notes"')
      assert 'id="copy-log"' not in page and 'id="copy-tasks"' not in page
      assert "Copy the log, answers and tasks to the clipboard as NDJSON" in page
      # Every icon button carries a title that repeats its accessible name.
      for control in (
        "copy-state",
        "refresh-notes",
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
      assert 'id="fetch-url"' in page and 'id="fetch-proxy"' in page
      assert "102.4 MB per URL" in page
      assert "Keep this page open while transfers run." in page
      assert "not measured" not in page
      assert 'id="workspace-use"' in page
      assert re.search(
        r'<input[^>]*id="upload-file"[^>]*type="file"[^>]*multiple', page
      )
      assert 'id="log-newest"' in page and 'stroke="#fff"' in page
      for value in ("all", "sent", "seen", "said"):
        assert f'<option value="{value}">' in page
      assert "frame-ancestors" not in headers["Content-Security-Policy"]
      assert "connect-src 'self' https:" in headers["Content-Security-Policy"]
      assert "default-src 'none'" in headers["Content-Security-Policy"]
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
      assert request("POST", "/api/notes", "x" * (preview.MAX_BODY + 1), auth)[0] == 413
      for body in (
        "{",
        "[]",
        '{"id":"x","text":3}',
        '{"id":"x","text":" "}',
        json.dumps({"id": "x", "text": "x" * (preview.MAX_NOTE + 1)}),
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
      assert "<table>" in rendered["html"] and "<script>" not in rendered["html"]
      assert 'href="javascript:' not in rendered["html"]
      assert request("GET", "/api/reports/first/export")[0] == 404
      assert request("GET", "/api/reports/first/source")[0] == 200
      prune = root / "prune.md"
      prune.write_text("# Prune\n\nA report the tab outgrew.\n", encoding="utf-8")
      store.publish("prune", "Prune", prune)
      assert request("GET", "/api/reports/prune/html")[0] == 200
      status, _, removed = request("POST", "/api/reports/prune/unpublish", "{}", auth)
      assert status == 200 and json.loads(removed) == {"unpublished": "prune"}
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
      assert 'maxlength="2000"' in served["html"]
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
      assert re.search(
        r'code\.note-id\[data-copied="?good"?\]\{color:var\(--dot-said\)', page
      )
      assert re.search(r'code\.note-id\[data-copied="?bad"?\]\{color:#ef4444', page)
      assert "#clock{font-size:inherit;font-variant-numeric:tabular-nums" in page
      assert re.search(
        r'\.icon-button\[data-state="?good"?\]\{color:var\(--dot-said\);', page
      )
      assert re.search(r'\.icon-button\[data-state="?bad"?\]\{color:#ef4444;', page)
      assert 'id="copy-log"' not in page, "the log lost its copy button"
      # The log header is two rows tall, not three: the title stands alone and the
      # connection and last-check lines stack to its right.
      assert '<h2 id="history-title">Message log</h2>' in page
      assert page.index('id="history-title"') < page.index('class="stack"')
      assert "#history-title{margin:0" in page
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
      assert re.search(
        r"#report-pip[^{}]*\{display:inline-block;width:7px;height:7px;margin-left:6px;"
        r"border-radius:50%;background:var\(--accent\);vertical-align:middle",
        page,
      )
      assert re.search(
        r"#notes-pip[^{}]*\{display:inline-block;width:7px;height:7px;margin-left:6px;"
        r"border-radius:50%;background:var\(--accent\);vertical-align:middle",
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
      # The log filter draws its own box like the icon buttons beside it, after a second owner note
      # that the heights still differed.
      assert "appearance:none" in page and "#log-filter" in page
      assert 'class="filter-wrap"' in page
      assert "border-top:5px solid var(--muted)" in page, (
        "the filter caret needs no blocked data image"
      )
      assert "data:image/svg+xml" not in page, "the preview CSP blocks data images"
      assert re.search(r"\.topbar\{[^}]*gap:8px;", page), (
        "collapse button uses the same 8px gap"
      )
      assert page.count("#send{") == 0
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
      assert ".log-card{flex:1 1 auto;min-height:200px" in page
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
        {"id": "s1", "answers": {"name": "x" * 2001}},
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
      assert not preview.custom_answer(verdict, "Other: " + "x" * 2001)
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
      assert len(full) < preview.MAX_SUBMISSION_BODY, (
        "and stay inside the one that replaced it"
      )
      assert request("POST", "/api/reports/wide/submit", full, auth)[0] == 201
      # The application limit is untouched: an answer over the 2,000 a text field takes is still a
      # 400 from the validator, not something the wider body limit waves through.
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
        == 400
      )
      # Past the body limit, so HTTP refuses it before the answers are parsed at all.
      over_body = "x" * (preview.MAX_SUBMISSION_BODY + 1)
      assert request("POST", "/api/reports/wide/submit", over_body, auth)[0] == 413
      # Notes keep the smaller limit; report answers take the wider one.
      assert request("POST", "/api/notes", "x" * (preview.MAX_BODY + 1), auth)[0] == 413
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
      # Autosave writes what the database holds, in one file both importers can read. The page's
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
      assert written["answers"] >= 1 and saved_lines[-1]["id"] == "saved-answer"
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
      # One file, one reader for both kinds: `import-notes` restores the note and the answer, and
      # the answer keeps its receipt, its read stamp and its task marker.
      round_trip = Path(directory) / "round-trip"
      preview.Store(round_trip, create=True)
      imported = subprocess.run(
        [
          sys.executable,
          str(Path(preview.__file__)),
          "--state-dir",
          str(round_trip),
          "import-notes",
          str(save_file),
        ],
        capture_output=True,
        text=True,
        check=True,
      ).stdout
      assert "1 notes" in imported
      assert f"{written['answers']} report answers" in imported
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
      # An upload stores its bytes beside the database and its record inside it, on the owner's answers in
      # report submission c27a4dd5: any bytes, a 50,000,000-byte ceiling, and a record that outlives them.
      blob = bytes(range(256)) * 4
      status, _, created = request(
        "POST",
        "/api/uploads?name=shot%2Fmy%20file.png",
        blob,
        {**auth, "Content-Type": "image/png"},
      )
      assert status == 201
      record = json.loads(created)
      assert record["name"] == "my file.png" and record["size"] == len(blob)
      assert record["sha256"] == hashlib.sha256(blob).hexdigest() and record["present"]
      assert Path(record["path"]).read_bytes() == blob
      assert Path(record["path"]).parent.name == "uploads"
      # An upload writes a note under its own ID, so that ID carries the shape the log shows:
      # seven characters, a hyphen, the rest. A raw uuid4 reads as a different kind of identifier.
      assert re.fullmatch(r"[0-9a-f]{7}-[0-9a-f]{25}", record["id"]), record["id"]
      # An upload writes a note, so the agent's next read sees it; the note rides the upload's ID.
      upload_note = store.state()["notes"][-1]
      assert upload_note["id"] == record["id"]
      assert upload_note["text"] == (
        f"Upload: my file.png ({len(blob)} B, image/png) saved to {record['path']}"
      )
      # A declared body above the new bound is refused before buffering 50 MB in this harness.
      status, _, problem = request(
        "POST",
        "/api/uploads?name=big.bin",
        b"0",
        {
          **auth,
          "Content-Type": "application/octet-stream",
          "Content-Length": str(preview.MAX_UPLOAD + 2),
        },
      )
      assert status == 413 and "50,000,000" in json.loads(problem)["error"]
      assert (
        request(
          "POST",
          "/api/uploads?name=empty.bin",
          b"",
          {**auth, "Content-Type": "application/octet-stream"},
        )[0]
        == 413
      )
      uploads_before = store.uploads()
      notes_before = store.state()["notes"]
      files_before = set((root / "uploads").iterdir())
      for partial in (b"abc", b""):
        with socket.create_connection(
          ("127.0.0.1", app.server_port), timeout=5
        ) as client:
          client.sendall(
            (
              "POST /api/uploads?name=partial.bin HTTP/1.0\r\n"
              "Content-Type: application/octet-stream\r\n"
              f"X-Preview-Token: {auth['X-Preview-Token']}\r\n"
              "Content-Length: 10\r\n\r\n"
            ).encode()
            + partial
          )
          client.shutdown(socket.SHUT_WR)
          response = http.client.HTTPResponse(client)
          response.begin()
          assert response.status == 400
          assert "Incomplete request body" in response.read().decode()
      assert store.uploads() == uploads_before
      assert store.state()["notes"] == notes_before
      assert set((root / "uploads").iterdir()) == files_before
      status, headers, served = request("GET", f"/api/uploads/{record['id']}", raw=True)
      assert status == 200 and served == blob and headers["Content-Type"] == "image/png"
      assert "attachment" in headers["Content-Disposition"]
      assert request("GET", "/api/uploads/no-such-upload")[0] == 404
      # The record survives a restore and the bytes do not: the tab is told which is which rather than
      # shown an entry that opens nothing.
      Path(record["path"]).unlink()
      assert request("GET", f"/api/uploads/{record['id']}")[0] == 404
      assert store.upload(record["id"])["present"] is False
      assert [item["id"] for item in store.uploads()] == [record["id"]]

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
      store.publish("scoped", "Scoped", source)
      store.submission("scoped-answer", "scoped", "REPORT scoped: noted")
      assert any(
        line["id"] == "scoped-answer"
        for line in json.loads(request("GET", "/api/submissions")[2])
      ), "a live report's answers ride the copy endpoint"
      store.unpublish("scoped")
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
      note = attached.note_with_upload(
        "linked-note", "Read this file", "old name.bin", "application/octet-stream", raw
      )
    assert note["id"] == "linked-note" and note["text"] == "Read this file"
    record = attached.upload("linked-note")
    assert record["name"] == "old name.bin" and record["size"] == len(raw)
    assert Path(record["path"]).name == "linked--1760000000-old-name.bin"
    assert Path(record["path"]).read_bytes() == raw
    assert [item["id"] for item in attached.read()["pending"]] == ["linked-note"]
    assert attached.state()["notes"][0]["attachment_name"] == "old name.bin"
    assert attached.read()["pending"][0]["attachment_path"] == record["path"]
    attached.acknowledge(["linked-note"], "note", "Seen")
    again = attached.note_with_upload(
      "linked-note", "Read this file", "old name.bin", "application/octet-stream", raw
    )
    assert (
      preview.clip_stamp(again["acknowledged_at"])
      == attached.state()["notes"][0]["acknowledged_at"]
    )
    assert len(attached.uploads()) == 1 and len(attached.state()["notes"]) == 1
    for text, content in (("Different text", raw), ("Read this file", b"different")):
      try:
        attached.note_with_upload(
          "linked-note", text, "old name.bin", "application/octet-stream", content
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
      second = store.note_with_upload("abcdefg-two", "Same prefix and name", *files[0])
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
        "CREATE TABLE uploads (seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, name TEXT NOT NULL, type TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL, file TEXT NOT NULL, at TEXT NOT NULL)"
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
    assert migrated.upload("old-file")["note_id"] == "old-file"
    migrated.note("old-file", "Upload: photo.png")
    assert migrated.state()["notes"][0]["attachments"][0]["name"] == "photo.png"
    assert Path(migrated.upload("old-file")["path"]).read_bytes() == b"PNG"


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
      command = [
        sys.executable,
        preview.__file__,
        "--state-dir",
        str(queue_store.path.parent),
      ]
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
      )
      pending = json.loads(agent_request.stdout)
      assert pending["url"] == "https://example.org/review.zip"
      assert pending["allow_proxy"] is True and pending["approval"] == "pending"
      assert pending["status"] == "queued" and "claim" not in pending
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
      Path(saved["path"]).unlink()
      assert preview.Store(queue_store.path.parent).fetch_jobs()[0]["present"] is False
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

      # Both binary routes refuse a declared excess; manual uploads above 1 MB now succeed.
      medium = b"x" * 1_000_001
      status, _, created = request(
        "POST",
        "/api/uploads?name=medium.bin",
        medium,
        {**auth, "Content-Type": "application/octet-stream"},
      )
      assert status == 201 and json.loads(created)["size"] == len(medium)
      assert Path(json.loads(created)["path"]).read_bytes() == medium
      for path, limit, extra in (
        ("/api/uploads?name=large.bin", preview.MAX_UPLOAD, {}),
        (
          f"/api/fetch-jobs/{proxy['id']}/result?name=large.bin",
          preview.MAX_FETCH,
          proxy_headers,
        ),
      ):
        status, _, problem = request(
          "POST",
          path,
          b"x",
          {
            **auth,
            **extra,
            "Content-Type": "application/octet-stream",
            "Content-Length": str(limit + 2),
          },
        )
        assert status == 413 and f"{limit:,}" in json.loads(problem)["error"]
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
    autosave_task = autosave_store.write_task("autosave-task", "Track it")
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
        "--state-dir",
        str(printed_dir),
        "read",
      ],
      capture_output=True,
      text=True,
      check=True,
    )
    assert printed.state()["notes"][0]["seen_at"] == first
    printed.acknowledge(["p-1"], "note", "answered after the stamp")
    assert [row["id"] for row in printed.read()["pending"]] == ["answer-2"]


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
    tasks_store.write_task("task-a", "A")
    tasks_store.write_task("task-b", "B")
    tasks_store.write_task("task-c", "C", order=1)
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
    # An empty detail clears the list rather than storing a blank line.
    assert tasks_store.write_task("long", details=[""])["details"] == []
    assert (
      preview.echo_task(tasks_store.write_task("hostile", "<img onerror=alert(1)>"))[
        "title"
      ]
      == "<img onerror=alert(1)>"
    )


def test_task_amend():
  with tempfile.TemporaryDirectory() as amend_dir:
    amend_store = preview.Store(amend_dir, create=True)
    amend_store.write_task(
      "docz-archive", "Move to docs/archive/", ["one", "two"], "upcoming", 1
    )
    amend_store.write_task("minify", "Minify the live build")
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
    written = fresh.import_tasks(preview.parse_task_import(backup))
    assert [item["id"] for item in written] == ["docs-archive", "minify"]
    assert fresh.state()["tasks"]["upcoming"][0]["details"] == ["one", "two"]
    lines = "\n".join(json.dumps(item) for item in amend_store.list_tasks())
    (Path(amend_dir) / "lines").mkdir()
    other = preview.Store(Path(amend_dir) / "lines", create=True)
    assert len(other.import_tasks(preview.parse_task_import(lines))) == 2
    other.write_task("extra", "Extra")
    other.import_tasks(preview.parse_task_import(backup), replace=True)
    assert [item["id"] for item in other.list_tasks()] == ["docs-archive", "minify"]
    # A --replace that meets an invalid record must cost nothing. The delete and the writes are one
    # transaction, so the list that was there is still there afterwards and nothing is half applied;
    # deleting first, as this did, lost the whole list to a bad record further down.
    before = other.list_tasks()
    for bad, flaw in (
      (
        [{"id": "good", "title": "Good"}, {"id": "BAD ID", "title": "Bad"}],
        "invalid ID",
      ),
      ([{"id": "good", "title": "Good"}, {"id": "no-title"}], "missing title"),
      (
        [{"id": "good", "title": "Good"}, {"id": "late", "status": "sideways"}],
        "bad status",
      ),
      ([{"id": "good", "title": "Good"}, 7], "record that is not an object"),
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
        {"id": "second", "title": "Second", "order": 2},
        {"id": "first", "title": "First", "order": 1},
      ],
      replace=True,
    )
    assert [item["id"] for item in other.list_tasks()] == ["first", "second"]
    # One bare object is JSONL of a single record, so it parses and fails on the missing ID.
    assert preview.parse_task_import('{"id": "solo", "title": "Solo"}') == [
      {"id": "solo", "title": "Solo"}
    ]
    for call, message in (
      (lambda: preview.parse_task_import("   "), "An empty import was accepted"),
      (lambda: preview.parse_task_import("[1, 2]"), "A list of numbers was accepted"),
      (
        lambda: other.import_tasks([{"title": "no id"}]),
        "A task with no ID was imported",
      ),
      (
        lambda: other.import_tasks(preview.parse_task_import('{"title": "Solo"}')),
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
    oversized = "z" * (preview.MAX_SUBMISSION + 1)
    wide_rejections = (
      (
        lambda: preview.submission_text(oversized),
        "An oversized submission was accepted",
      ),
      (
        lambda: wide_store.submission("s-huge", "wide", oversized),
        "An oversized one was stored",
      ),
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
  # One file, two readers: the same saved-state file feeds both importers, each skipping the other's
  # lines, which is what makes one path enough for the owner's restore.
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
      # An answer line rides the same file: the notes reader restores it, and the task reader
      # skips it the way the notes reader skips a task line.
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
    notes_out = subprocess.run(
      [
        sys.executable,
        script,
        "--state-dir",
        str(mixed_root),
        "import-notes",
        str(mixed),
      ],
      capture_output=True,
      text=True,
      check=True,
    ).stdout
    assert "Imported 1 notes" in notes_out and "1 report answers" in notes_out
    # A restore reads this file twice, so the first import leaves the task lines in it.
    assert any(
      "title" in json.loads(line)
      for line in mixed.read_text(encoding="utf-8").splitlines()
      if line.strip()
    )
    tasks_out = subprocess.run(
      [
        sys.executable,
        script,
        "--state-dir",
        str(mixed_root),
        "task-import",
        str(mixed),
      ],
      capture_output=True,
      text=True,
      check=True,
    ).stdout
    assert json.loads(tasks_out)["imported"] == 1
    # Writer and reader move together: what `task-list` prints is what `task-import` reads back, so
    # minifying the output cannot strand the importer.
    script_again = str(Path(preview.__file__))
    listed = subprocess.run(
      [sys.executable, script_again, "--state-dir", str(mixed_root), "task-list"],
      capture_output=True,
      text=True,
      check=True,
    ).stdout.strip()
    assert "\n" not in listed, "agent-facing JSON is one line"
    assert json.loads(listed)[0]["id"] == "saved-task"
    reimport = subprocess.run(
      [
        sys.executable,
        script_again,
        "--state-dir",
        str(mixed_root),
        "task-import",
        "--replace",
      ],
      input=listed,
      capture_output=True,
      text=True,
      check=True,
    ).stdout.strip()
    assert json.loads(reimport)["imported"] == 1
    read_out = subprocess.run(
      [sys.executable, script_again, "--state-dir", str(mixed_root), "read"],
      capture_output=True,
      text=True,
      check=True,
    ).stdout.strip()
    assert "\n" not in read_out, "read prints one line"
    # The imported note carries its receipt, so `read` has nothing pending; the receipt is what
    # makes it acknowledged; reading alone never stamps Seen.
    assert json.loads(read_out)["pending"] == []
    pretty_out = subprocess.run(
      [
        sys.executable,
        script_again,
        "--state-dir",
        str(mixed_root),
        "--pretty",
        "read",
      ],
      capture_output=True,
      text=True,
      check=True,
    ).stdout.strip()
    assert "\n" in pretty_out, "--pretty is the human escape hatch"
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
    # import-notes does not create a state directory, so the restore target exists first.
    preview.Store(restore, create=True)
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
      [sys.executable, script, "--state-dir", str(restore), "import-notes", str(log)],
      capture_output=True,
      text=True,
      check=True,
    ).stdout
    assert "Imported 3 notes, 1 with a receipt restored verbatim" in imported
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
        "--state-dir",
        str(restore),
        "task",
        "from-note",
        "Answer the note",
        "--msg-id",
        "plain",
      ],
      capture_output=True,
      text=True,
      check=True,
    ).stdout
    assert json.loads(linked)["msg_id"] == "plain"
    assert {
      row["id"]: row["task_id"] for row in preview.Store(restore).state()["notes"]
    }["plain"] == "from-note"
    refused = subprocess.run(
      [
        sys.executable,
        script,
        "--state-dir",
        str(restore),
        "task",
        "orphan",
        "No message",
        "--msg-id",
        "0f0f0f0f-0000-4000-8000-000000000000",
      ],
      capture_output=True,
      text=True,
      check=False,
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
        "--state-dir",
        str(restore),
        "import-notes",
        str(partial),
      ],
      capture_output=True,
      text=True,
      check=False,
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
      [sys.executable, script, "--state-dir", str(restore), "import-notes", str(log)],
      capture_output=True,
      text=True,
      check=True,
    ).stdout
    assert "existing IDs are not duplicated" in again
    # Three restored notes, and a re-import adds none of them twice.
    assert len(preview.Store(restore).state()["notes"]) == 3


def test_bash_gate():
  # The gate blocks only past the threshold while the inbox stays pending.
  with tempfile.TemporaryDirectory() as gate_dir:
    gate_store = preview.Store(gate_dir, create=True)
    gate_store.note("gate-note", "Pending work")
    gate_store.set_meta(preview.POLLS_SINCE_MESSAGE, str(preview.GATE_THRESHOLD - 1))
    assert gate_store.gate()
    gate_store.set_meta(preview.POLLS_SINCE_MESSAGE, str(preview.GATE_THRESHOLD))
    assert not gate_store.gate()
    gate_store.acknowledge(["gate-note"], "note", "Cleared")
    assert gate_store.gate()
    gate_script = str(Path(preview.__file__))
    blocked = subprocess.run(
      [sys.executable, gate_script, "--state-dir", gate_dir, "gate"],
      capture_output=True,
      text=True,
      check=False,
    )
    assert blocked.returncode == 0


def test_dispatch_reminder():
  # Every dispatch carries a reminder without changing stdout; only a delivered read
  # or an explicit receipt marks a note seen.
  with tempfile.TemporaryDirectory() as reminder_dir:
    reminder_store = preview.Store(reminder_dir, create=True)
    reminder_store.note("reminder-note", "Read this")
    reminder_script = str(Path(preview.__file__))

    def reminder_tail(line):
      """Return the rotating tail one reminder line ends with, or fail."""
      stripped = line.strip()
      for candidate in preview.REMINDERS:
        if stripped.endswith(candidate):
          return candidate
      raise AssertionError(f"No rotating tail in {stripped!r}")

    pending_prefix = "1 message/s. DO NOT IGNORE. ACK ASAP. "
    for command in (["task-list"], ["task", "reminder-task", "Track work"]):
      result = subprocess.run(
        [sys.executable, reminder_script, "--state-dir", reminder_dir, *command],
        capture_output=True,
        text=True,
        check=True,
      )
      json.loads(result.stdout)
      line = result.stderr.strip()
      assert line == pending_prefix + reminder_tail(line)
      assert reminder_store.state()["notes"][0]["seen_at"] is None
    result = subprocess.run(
      [sys.executable, reminder_script, "--state-dir", reminder_dir, "read"],
      capture_output=True,
      text=True,
      check=True,
    )
    json.loads(result.stdout)
    line = result.stderr.strip()
    assert line == pending_prefix + reminder_tail(line)
    delivered = reminder_store.state()["notes"][0]["seen_at"]
    assert delivered is not None
    assert reminder_store.state()["notes"][0]["acknowledged_at"] is None
    with (
      patch.object(sys, "argv", [reminder_script, "--state-dir", reminder_dir, "read"]),
      patch.object(sys.stdout, "write", side_effect=BrokenPipeError("output failed")),
    ):
      assert preview.main() == 1
    assert reminder_store.state()["notes"][0]["seen_at"] == delivered
    result = subprocess.run(
      [
        sys.executable,
        reminder_script,
        "--state-dir",
        reminder_dir,
        "seen",
        "reminder-note",
      ],
      capture_output=True,
      text=True,
      check=True,
    )
    assert "Seen: reminder-note" in result.stdout
    assert reminder_store.state()["notes"][0]["seen_at"] is not None
    assert reminder_store.state()["notes"][0]["acknowledged_at"] is None
    result = subprocess.run(
      [
        sys.executable,
        reminder_script,
        "--state-dir",
        reminder_dir,
        "ack",
        "reminder-note",
        "--note",
        "Received",
      ],
      capture_output=True,
      text=True,
      check=True,
    )
    assert reminder_tail(result.stderr) in preview.REMINDERS
    assert reminder_store.reminder() in preview.REMINDERS
    reminder_store.submission("form-answer", "form", "REPORT form: yes")
    form_line = reminder_store.reminder()
    form_prefix = "1 form answer/s. DO NOT IGNORE. ACK ASAP. "
    assert form_line == form_prefix + reminder_tail(form_line)
    reminder_store.acknowledge(["form-answer"], "note", "Received")
    for index in range(3):
      reminder_store.note(f"mixed-{index}", "Pending")
    for name in ("one.txt", "two.txt"):
      upload = reminder_store.save_upload(name, "text/plain", name.encode())
      reminder_store.note(upload["id"], "Uploaded " + name)
    mixed_line = reminder_store.reminder()
    mixed_prefix = "3 message/s. 2 upload/s. DO NOT IGNORE. ACK ASAP. "
    assert mixed_line == mixed_prefix + reminder_tail(mixed_line)
    assert all(row["seen_at"] is None for row in reminder_store.read()["pending"])


def test_reminder_rotation():
  # The tail rotates through the whole list before it repeats, a hook poll counts itself, a CLI
  # dispatch and a read do not, and the count resets when a new user item arrives.
  with tempfile.TemporaryDirectory() as rotate_dir:
    rotate_store = preview.Store(rotate_dir, create=True)
    rotate_script = str(Path(preview.__file__))
    assert (
      "Ask questions ASAP through fielded reports; keep other work moving."
      in preview.REMINDERS
    )
    assert "`ask_user` on GH_TOKEN failure." in preview.REMINDERS
    assert "Remove stale reports with unpublish." in preview.REMINDERS
    assert "End the turn with `poll` to wait for more work." in preview.REMINDERS
    assert "Don't forget to publish your reports." in preview.REMINDERS
    assert "Avoid ending turn if there are unblocked tasks." in preview.REMINDERS
    span = len(preview.REMINDERS)
    cycle = [rotate_store.reminder() for _ in range(span)]
    assert cycle == list(preview.REMINDERS)
    assert rotate_store.reminder() == preview.REMINDERS[0]
    # An idle queue carries the tail alone, and its polls do not count: the tally starts with
    # the pending item it reports.
    assert rotate_store.reminder(advance=True) == preview.REMINDERS[1]
    assert rotate_store.reminder(advance=True) == preview.REMINDERS[2]
    assert rotate_store.reminder() == preview.REMINDERS[3]
    rotate_store.note("rotate-note", "Pending")
    pending = "1 message/s. DO NOT IGNORE. ACK ASAP. "
    assert rotate_store.reminder() == f"{pending}{preview.REMINDERS[4]}"
    offset = span + 5
    for cursor, polls in ((offset, 1), (offset + 1, 2)):
      result = subprocess.run(
        [sys.executable, rotate_script, "--state-dir", rotate_dir, "--reminder"],
        capture_output=True,
        text=True,
        check=True,
      )
      tail = preview.REMINDERS[cursor % span]
      assert (
        result.stdout.strip() == f"{polls} call/s since user messaged. {pending}{tail}"
      )
      assert result.stderr == ""
    result = subprocess.run(
      [sys.executable, rotate_script, "--state-dir", rotate_dir, "task-list"],
      capture_output=True,
      text=True,
      check=True,
    )
    json.loads(result.stdout)
    tail = preview.REMINDERS[(offset + 2) % span]
    assert result.stderr.strip() == f"2 call/s since user messaged. {pending}{tail}"
    # A read does not erase the calls since the first unread message. Only a fresh backlog
    # resets the tally; a message landing on an unacked pile leaves it running.
    rotate_store.read()
    assert rotate_store.reminder() == (
      f"2 call/s since user messaged. {pending}{preview.REMINDERS[(offset + 3) % span]}"
    )
    # An ack empties the queue, so idle polls stop counting, and a fresh note starts at one.
    rotate_store.acknowledge(["rotate-note"], "note", "Done")
    assert rotate_store.meta_value(preview.POLLS_SINCE_MESSAGE) == "0"
    assert rotate_store.reminder(advance=True) == preview.REMINDERS[(offset + 4) % span]
    assert rotate_store.reminder(advance=True) == preview.REMINDERS[(offset + 5) % span]
    rotate_store.note("rotate-later", "Pending again")
    assert rotate_store.reminder(advance=True) == (
      f"1 call/s since user messaged. {pending}{preview.REMINDERS[(offset + 6) % span]}"
    )
    rotate_store.note("rotate-newer", "Another user message")
    newer = "2 message/s. DO NOT IGNORE. ACK ASAP. "
    # A second message on an unacked pile keeps the count anchored to the first unread one.
    assert rotate_store.reminder() == (
      f"1 call/s since user messaged. {newer}{preview.REMINDERS[(offset + 7) % span]}"
    )
    assert rotate_store.reminder(advance=True) == (
      f"2 call/s since user messaged. {newer}{preview.REMINDERS[(offset + 8) % span]}"
    )


def test_ack_task_reminder():
  # An ack reminds the agent to queue the note's work.
  with tempfile.TemporaryDirectory() as ack_dir:
    preview.Store(ack_dir, create=True).note("ack-work", "Needs work")
    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "--state-dir",
        ack_dir,
        "ack",
        "ack-work",
        "--note",
        "Ok",
      ],
      capture_output=True,
      text=True,
      check=True,
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
        "--state-dir",
        marker_dir,
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
    migrated.mark_report_seen("fresh")
    migrated.publish("fresh", "Fresh", source)
    state = {row["id"]: row for row in migrated.state()["reports"]}
    assert state["fresh"]["seen_at"] is None
    assert state["fresh"]["ever_seen"] == 1


def test_poll_inbox():
  with tempfile.TemporaryDirectory() as poll_dir:
    store = preview.Store(poll_dir, create=True)
    sleeps = []

    def sleeper(seconds):
      sleeps.append(seconds)
      store.note("poll-1", "arrived during wait")

    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "--state-dir",
        poll_dir,
        "poll",
        "--interval",
        "0",
        "--max",
        "1",
      ],
      capture_output=True,
      text=True,
      check=False,
    )
    assert result.returncode == 1
    listing = json.loads(result.stdout)
    assert listing["pending"] == []
    assert store.state()["notes"] == []
    rc = preview.poll_inbox(store, interval=10, max_loops=3, sleeper=sleeper)
    assert rc == 0
    assert sleeps == [10]
    assert store.state()["notes"][0]["seen_at"] is not None
    result = subprocess.run(
      [
        sys.executable,
        str(Path(preview.__file__)),
        "--state-dir",
        poll_dir,
        "poll",
        "--interval",
        "0",
        "--max",
        "2",
      ],
      capture_output=True,
      text=True,
      check=False,
    )
    assert result.returncode == 0
    listing = json.loads(result.stdout)
    assert [item["id"] for item in listing["pending"]] == ["poll-1"]
    help_text = subprocess.run(
      [sys.executable, str(Path(preview.__file__)), "poll", "--help"],
      capture_output=True,
      text=True,
      check=True,
    ).stdout
    assert "default: 1" in help_text and "default: 900" in help_text
    try:
      preview.poll_inbox(store, interval=-1, max_loops=1)
      raise AssertionError("negative interval accepted")
    except ValueError:
      pass
    try:
      preview.poll_inbox(store, interval=0, max_loops=0)
      raise AssertionError("zero max_loops accepted")
    except ValueError:
      pass


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
