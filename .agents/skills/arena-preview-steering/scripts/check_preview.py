"""Assert-based integration check; run with the reporting venv's Python."""

import builtins
import http.client
import json
import re
import sqlite3
import subprocess
import sys
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
    # The log filter ships in the page with its three states and its empty line.
    assert 'id="log-filter"' in page and 'id="log-empty"' in page
    # The log's jump bar ships in the page, inside the wrapper that positions it over the scroll area.
    assert 'id="log-newest"' in page and 'class="log-scroll"' in page
    for value in ("all", "sent", "seen", "said"):
      assert f'<option value="{value}">' in page
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
    assert served_note["seen_at"] is not None
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
    assert 'data-label="Other"' in served["html"]
    assert 'data-custom="Other"' in served["html"]
    assert 'class="custom-text"' in served["html"]
    assert 'maxlength="2000"' in served["html"]
    assert "<textarea" in served["html"] and 'placeholder="Other:"' in served["html"]
    assert "> Other: <" not in served["html"]
    status, _, page = request("GET", "/")
    assert status == 200 and '#preview-note[aria-pressed="false"] {' in page
    assert '#preview-note[aria-pressed="true"]' not in page
    assert "--focus: #524d47;" in page and "#f4ca93" not in page
    assert "--focus: #8f5b13;" in page
    assert "--tab-border: #413d39;" in page
    assert "--tab-border: var(--border);" in page
    assert "nav button:focus-visible { border-color: var(--focus); }" in page
    assert "border-color: var(--accent)" not in page
    assert "padding-bottom: 12px;" in page
    assert "#report-form { min-width: 0; margin-top: 12px; }" in page
    assert (
      ".message { margin-bottom: 14px; background: var(--bubble); padding: 8px 14px; border-radius: 8px; }"
      in page
    )
    assert (
      ".answer.reply { border-left: 2px solid var(--accent); padding-left: 12px; color: var(--muted); font-size: 13px; }"
      in page
    )
    assert (
      ".state-dot { display: inline-block; width: 8px; height: 8px; margin-left: 6px; border-radius: 50%; background: var(--dot-sent); }"
      in page
    )
    assert "--dot-seen: #7fa7d1;" in page and "--dot-seen: #3f6ea8;" in page
    assert "--dot-said: #8dc07f;" in page and "--dot-said: #4a7c3a;" in page
    assert "--dot-sent: var(--muted);" in page
    assert '.state-dot[data-state="said"] { background: var(--dot-said); }' in page
    assert "--chip" not in page
    assert "code.note-id {" in page and ".receipt code" not in page
    assert ".answer.note" not in page
    assert ".answer > p:last-child { margin-bottom: 0; }" in page
    assert (
      ":not(pre) > code { background: var(--code-bg); padding: 1px 5px; border-radius: 4px; }"
      in page
    )
    # Inline code sits darker than the page in dark mode; the light theme keeps its bubble.
    assert "--code-bg: #1b1a19;" in page
    assert "--code-bg: var(--bubble);" in page
    # The composer's hint is half as prominent as the muted face, so what is being typed and what
    # was sent stay distinguishable from a placeholder that is neither.
    assert "textarea::placeholder { color: var(--muted); opacity: 0.5; }" in page
    assert 'code.note-id[data-copied="good"] { color: var(--dot-said); }' in page
    assert 'code.note-id[data-copied="bad"] { color: #ef4444; }' in page
    assert "#clock { font-size: inherit; font-variant-numeric: tabular-nums; }" in page
    assert '.icon-button[data-state="good"] { color: var(--dot-said);' in page
    assert '.icon-button[data-state="bad"] { color: #ef4444;' in page
    assert '<button id="copy-log" class="icon-button"' in page
    # The log header is two rows tall, not three: the title stands alone and the
    # connection and last-check lines stack to its right, on owner note ecf7d264.
    assert '<h2 id="history-title">Message log</h2>' in page
    assert page.index('id="history-title"') < page.index('class="stack"')
    assert "#history-title { margin: 0; }" in page
    # The composer's outer rows give up the space they face, on owner notes 778a276a and 27c65cba.
    assert "#form > div:first-child { margin-top: 0; padding-top: 0; }" in page
    assert "#form > div:last-child { margin-bottom: 0; padding-bottom: 0; }" in page
    assert '<button id="copy-report" class="icon-button"' in page
    # The report copy button matches the refresh button beside it; it was 34px against 44px.
    # No negative assertion here: the combined rule contains the old single-selector text.
    assert "#copy-report, #refresh-report { width: 44px; height: 44px; }" in page
    # A rule separates the tasks toolbar from the finished div, and details collapse.
    assert (
      ".tasks-layout > .row.tight { border-bottom: 1px solid var(--border);"
      " padding-bottom: 12px; }" in page
    )
    assert (
      ".task-details > summary { cursor: pointer; list-style-position: inside; }"
      in page
    )
    assert '<button id="copy-tasks" class="icon-button"' in page
    # The Reports tab carries an unread pip rather than a count of the reports that exist.
    assert 'id="report-pip"' in page
    assert "report-count" not in page
    assert (
      "#report-pip { display: inline-block; width: 7px; height: 7px; margin-left: 6px;"
      " border-radius: 50%; background: var(--accent); vertical-align: middle; }"
      in page
    )
    # The pip is given a shape by a display rule, so the sheet's blanket rule is what hides it.
    assert "[hidden] { display: none !important; }" in page
    assert page.index('id="copy-log"') < page.index('id="refresh-notes"')
    assert page.index('id="copy-report"') < page.index('id="refresh-report"')
    assert page.index('id="tasks-status"') < page.index('id="copy-tasks"')
    assert '<span id="clock" class="muted" title="Local time">--:--</span>' in page
    assert page.index('id="clock"') < page.index('id="theme"')
    assert ".report :not(pre) > code" not in page
    assert "background: none; padding: 0; cursor: pointer; }" in page
    assert "#send { border-color: var(--accent); }" not in page
    assert "#report-submit { margin-top: 16px; }" in page
    assert page.count("#send {") == 0
    assert "resize: none;" in page and "resize: vertical" not in page
    assert "#notes-panel, #reports-panel, #tasks-panel { overflow-y: auto; }" in page
    assert 'id="tasks-tab" aria-controls="tasks-panel"' in page
    assert '<ul id="tasks-current-body" class="task-list"></ul>' in page
    assert '<ul id="tasks-finished-body" class="task-list"></ul>' in page
    assert '<ul id="tasks-upcoming-body" class="task-list"></ul>' in page
    # Current leads the panel: what the agent is on next is the first thing the owner reads.
    # Current leads the panel and Upcoming follows it, with the finished record last: what the
    # agent is on next and what is coming are the owner's questions, and what is done is the log.
    assert page.index('id="tasks-current"') < page.index('id="tasks-upcoming"')
    assert page.index('id="tasks-upcoming"') < page.index('id="tasks-finished"')
    assert ".task-list { margin: 0; padding-left: 20px; }" in page
    assert ".task-title { font-weight: 600; }" in page
    assert (
      ".task-details { display: block; margin-top: 2px; color: var(--muted);"
      " font-size: 13px; }" in page
    )
    # The details are a real list, so a marker comes from the element rather than a span's rule.
    assert ".task-detail-list { margin: 2px 0 0; padding-left: 18px; }" in page
    assert ".task-detail { display: block; }" not in page
    assert ".tasks-layout { display: flex; flex-direction: column; gap: 18px; }" in page
    assert "max-height: 48%" not in page
    assert "min-height: 100%" not in page
    assert (
      ".notes-layout { display: flex; flex-direction: column; gap: 14px; height: 100%;"
      in page
    )
    assert "resize: none; min-height: 72px; overflow: hidden; }" in page
    assert ".log-card { flex: 1 1 auto; min-height: 200px;" in page
    assert "h1 { letter-spacing: -.035em; margin: 4px 0; }" in page
    assert "h2 { margin: 0 0 8px; }" in page
    for level in ("h1", "h2", "h3", "h4", "h5", "h6"):
      assert f"{level} {{ font-size" not in page

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
    # is what one 32 KiB limit for every POST did. That maximum is 50 fields of 2,000 characters,
    # and no single answer reaches it because a text answer is capped at 2,000, so it takes a whole
    # wide report. The Store layer already covers the submission; this covers the HTTP path.
    wide = root / "wide-http.md"
    wide.write_text(
      "# Wide\n\n" + "\n".join(f"Question {index}: ___" for index in range(50)) + "\n",
      encoding="utf-8",
    )
    store.publish("wide", "Wide report", wide)
    _, wide_questions = preview.render_report(wide.read_text(encoding="utf-8"))
    assert len(wide_questions) == 50
    full = json.dumps(
      {"id": "sub-wide", "answers": {q["id"]: "x" * 2000 for q in wide_questions}}
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
          {"id": "sub-over", "answers": {wide_questions[0]["id"]: "x" * 2001}}
        ),
        auth,
      )[0]
      == 400
    )
    # Past the body limit, so HTTP refuses it before the answers are parsed at all.
    over_body = "x" * (preview.MAX_SUBMISSION_BODY + 1)
    assert request("POST", "/api/reports/wide/submit", over_body, auth)[0] == 413
    # Notes keep the small limit; only report answers were widened.
    assert request("POST", "/api/notes", "x" * (preview.MAX_BODY + 1), auth)[0] == 413
    # The save route writes what the page posts, in one file both importers can read.
    saved_status, _, saved = request(
      "POST",
      "/api/save-state",
      json.dumps(
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
      ),
      auth,
    )
    assert saved_status == 200
    written = json.loads(saved)
    assert written["notes"] == 1 and written["tasks"] == 1
    saved_lines = [
      json.loads(line)
      for line in Path(written["path"]).read_text(encoding="utf-8").splitlines()
    ]
    assert [line["id"] for line in saved_lines] == ["saved-note", "saved-task"]
    assert request("POST", "/api/save-state", "{}", auth)[0] == 400
    assert request("POST", "/api/save-state", "{}")[0] == 403
    # The read stamp belongs to the report rather than to one browser's storage, so the browser
    # writes it through a route of its own, and only the first look sets it.
    store.publish("seen", "Seen report", source)
    assert store.state()["reports"][-1]["seen_at"] is None
    assert request("POST", "/api/reports/seen/seen", "{}")[0] == 403
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
  finally:
    app.shutdown()
    app.server_close()
    worker.join()
print(
  "PASS: durable notes, retry dedup, receipts carrying a rendered reply or a plain note, state migration, seen-at-read, reports and their read stamp, Markdown fields with inbox-answer submissions, safe rendering, errors and HTTP boundaries"
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
  db.execute(
    "INSERT INTO notes (id, text, at, acknowledged_at)"
    " VALUES ('answered', 'kept', '2026-01-01T00:00:00+00:00', '2026-01-02T00:00:00+00:00')"
  )
  db.commit()
  db.close()
  migrated = preview.Store(legacy, create=True)
  assert [row["id"] for row in migrated.state()["notes"]] == ["old", "answered"]
  assert migrated.state()["notes"][1]["seen_at"] == "2026-01-02T00:00:00+00:00"
  migrated.acknowledge(["old"], "note", "still here")
  assert migrated.state()["notes"][0]["ack_text"] == "still here"
  assert migrated.state()["notes"][0]["seen_at"] is not None

with tempfile.TemporaryDirectory() as seen_dir:
  unread = preview.Store(seen_dir, create=True)
  unread.note("s-1", "unread")
  assert unread.state()["notes"][0]["seen_at"] is None
  listing = unread.read()
  stamped = unread.state()["notes"][0]["seen_at"]
  assert [row["id"] for row in listing["pending"]] == ["s-1"]
  assert listing["pending"][0]["seen_at"] == stamped is not None
  unread.read()
  assert unread.state()["notes"][0]["seen_at"] == stamped
  unread.acknowledge(["s-1"], "reply", "read, then answered")
  assert unread.state()["notes"][0]["seen_at"] == stamped

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
  assert listed["updated_at"] == record["updated_at"]
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
    (lambda: tasks_store.write_task("deep", "D", ["y" * 2001]), "A huge detail passed"),
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
    ([{"id": "good", "title": "Good"}, {"id": "BAD ID", "title": "Bad"}], "invalid ID"),
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
  record = wide_store.submit_report("wide", "note-wide", answers)
  # The combined answers pass the 4000 a note is capped at, and none of it is dropped.
  assert len(record["text"]) > 4000
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
    preview.note_text("n" * 4001)
    raise AssertionError("An oversized note was accepted")
  except ValueError as error:
    assert "4000" in str(error)

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
  assert "Imported 1 notes" in notes_out
  tasks_out = subprocess.run(
    [sys.executable, script, "--state-dir", str(mixed_root), "task-import", str(mixed)],
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
  # makes it read, and `read` is the only path that stamps one.
  assert json.loads(read_out)["pending"] == []
  pretty_out = subprocess.run(
    [sys.executable, script_again, "--state-dir", str(mixed_root), "--pretty", "read"],
    capture_output=True,
    text=True,
    check=True,
  ).stdout.strip()
  assert "\n" in pretty_out, "--pretty is the human escape hatch"
  restored = preview.Store(mixed_root)
  assert [row["id"] for row in restored.state()["notes"]] == ["saved-note"]
  assert [task["id"] for task in restored.tasks()["upcoming"]] == ["saved-task"]

help_text = subprocess.run(
  [sys.executable, str(Path(preview.__file__)), "serve", "--help"],
  capture_output=True,
  text=True,
  check=True,
).stdout
assert "default: 8000" in help_text and "--port PORT" in help_text

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
  # The receipt comes back as it was written: the original stamp, not the time of the import.
  assert rows["carried"]["acknowledged_at"] == "2026-09-20T22:05:11.982172+00:00"
  assert rows["carried"]["ack_kind"] == "reply"
  assert rows["carried"]["ack_text"] == "Fixed in `preview.py`."
  assert rows["carried"]["at"] == "2026-09-20T22:00:47"
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
    [sys.executable, script, "--state-dir", str(restore), "import-notes", str(partial)],
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
