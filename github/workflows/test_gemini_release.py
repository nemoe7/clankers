"Offline release-history, reduction and API-boundary tests. `pytest` runs them."

import hashlib
import io
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import gemini_release as release


def fails(call, message):
  try:
    call()
  except RuntimeError as error:
    assert message in str(error), str(error)
  else:
    raise AssertionError(f"Expected error: {message}")


@patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "1"})
def test_release_pipeline():
  original = Path.cwd()
  with tempfile.TemporaryDirectory() as directory:
    os.chdir(directory)

    def git(*args):
      return release.git(*args).strip()

    git("init", "-b", "main")
    git("config", "user.name", "Check")
    git("config", "user.email", "check@example.invalid")
    Path("data").write_text("root marker\n")
    git("add", ".")
    git("commit", "-m", "root change")
    root = git("rev-parse", "HEAD")
    git("tag", "v1")
    fails(lambda: release.tag_sha("1.0.0"), "refs/tags/1.0.0^{commit}")
    fails(lambda: release.tag_sha("1.0.0"), "fatal:")
    fails(lambda: release.tag_sha("1.0.0"), "Push that exact tag before dispatch")

    git("checkout", "-b", "side")
    Path("side").write_text("side marker\n")
    git("add", ".")
    git("commit", "-m", "side change")
    git("checkout", "main")
    Path("data").write_text("root marker\nnext marker\n")
    Path("binary").write_bytes(b"\0\1\2\3")
    git("add", ".")
    git("commit", "-m", "next change")
    git("merge", "--no-ff", "side", "-m", "merge side")
    git("tag", "-a", "v2", "-m", "annotated target")
    target = release.tag_sha("v2")
    git("update-ref", "refs/remotes/origin/main", target)
    assert release.target_commit(root, "main") == root
    assert release.target_commit("", "main") == target
    fails(lambda: release.target_commit("HEAD", "main"), "complete commit SHA")
    tag_object = git("rev-parse", "refs/tags/v2")
    fails(lambda: release.target_commit(tag_object, "main"), "not a tag object")
    rows = [
      {
        "tag_name": "v1",
        "draft": False,
        "prerelease": True,
        "published_at": "2026-01-01T00:00:00Z",
      }
    ]
    assert release.baseline(rows, target) == ("v1", root)
    assert release.baseline([], target) == ("", "")
    with patch.object(release, "releases", return_value=rows):
      fails(lambda: release.current_base("owner/repo", target), "prerelease")
    with (
      patch.object(
        release,
        "releases",
        return_value=[
          {**rows[0], "id": 5, "prerelease": False, "body": "Previous release notes"}
        ],
      ),
      patch.object(release, "remote_tag_sha", return_value=root),
    ):
      assert release.current_base("owner/repo", target) == (
        "v1",
        root,
        {
          "id": 5,
          "published_at": rows[0]["published_at"],
          "body": "Previous release notes",
        },
      )
    with (
      patch.object(
        release,
        "releases",
        return_value=[{**rows[0], "id": 5, "prerelease": False, "body": []}],
      ),
      patch.object(release, "remote_tag_sha", return_value=root),
    ):
      fails(lambda: release.current_base("owner/repo", target), "notes are invalid")
    # No published release is an ancestor of the target: the baseline refuses instead of
    # falling back to an unrelated tag.
    with patch.object(release, "ancestor", return_value=False):
      fails(lambda: release.baseline(rows, target), "No published ancestor release")
    # One item per commit: its message and its diff, or the message alone.
    units = release.history(target, root)
    all_units = release.history(target, "")
    text = "\n".join(value for _, value in units)
    assert (
      "side marker" in text
      and "next marker" in text
      and "Binary files" in text
      and "GIT binary patch" not in text
    )
    ids = [key for key, _ in units]
    assert target in ids and root not in ids
    assert root in [key for key, _ in all_units]
    # The merge commit carries one diff per parent inside its single item.
    assert dict(units)[target].count("diff --git") > 1
    messages = release.history(target, root, "commits")
    assert [key for key, _ in messages] == ids
    assert "diff --git" not in dict(messages)[target]
    fails(lambda: release.history(target, root, "everything"), "Invalid evidence input")

    # Ordered chunks use exact token counts and keep evidence order.
    def text_size(model, request):
      payload = json.loads(request["contents"][0]["parts"][0]["text"])
      return sum(len(item["text"]) for item in payload["evidence"])

    with (
      patch.object(release, "input_tokens", text_size),
      patch.object(release, "TOKEN_COUNTS", {}),
    ):
      items = [{"id": str(n), "text": "x" * 40} for n in range(8)]
      cover = {item["id"]: [item["id"]] for item in items}
      groups = release.grouped(items, {}, "test", cover, 100)
    assert [[item["id"] for item in group] for group in groups] == [
      ["0", "1"],
      ["2", "3"],
      ["4", "5"],
      ["6", "7"],
    ]

    # Ordered binary packing finds the same full groups without probing every next item.
    probes = []

    def counted_size(model, request):
      probes.append(request)
      return text_size(model, request)

    items = [{"id": str(n), "text": "x" * 10} for n in range(80)]
    cover = {item["id"]: [item["id"]] for item in items}
    with (
      patch.object(release, "input_tokens", counted_size),
      patch.object(release, "summary"),
      patch.object(release, "TOKEN_COUNTS", {}),
    ):
      groups = release.grouped(items, {}, "test", cover, 100)
    assert [[item["id"] for item in group] for group in groups] == [
      [str(n) for n in range(start, start + 10)] for start in range(0, 80, 10)
    ]
    assert len(probes) <= 45

    # A round reports its final plan and probe total, not every binary-search probe.
    round_lines = []
    cover = {item["id"]: [item["id"]] for item in items}
    with (
      patch.object(release, "input_tokens", counted_size),
      patch.object(release, "summary", round_lines.append),
      patch.object(release, "TOKEN_COUNTS", {}),
      patch.object(release, "CHUNK_TOKENS", 100),
    ):
      _, round_groups = release.round_requests(items, {}, "chunk", "test", cover, 1)
    assert [[item["id"] for item in group] for group in round_groups] == [
      [str(n) for n in range(start, start + 10)] for start in range(0, 80, 10)
    ]
    assert len(round_lines) == len(round_groups) + 1
    assert any("after 16 exact token probe(s)" in line for line in round_lines)
    assert len(probes) <= 35
    assert not any("countTokens" in line for line in round_lines)

    # One item's text halves only as a last resort, because a single item barely
    # reaches the ceiling.
    split_cover = {"big": ["big"]}
    with (
      patch.object(release, "input_tokens", text_size),
      patch.object(release, "summary") as split_log,
    ):
      halved = release.split_item(
        {"id": "big", "text": "x" * 80}, {}, "test", 20, split_cover
      )
    assert any(
      "splitting its text" in call.args[0] for call in split_log.call_args_list
    )
    assert [item["id"] for item in halved] == [
      "big:1/2:1/2",
      "big:1/2:2/2",
      "big:2/2:1/2",
      "big:2/2:2/2",
    ]
    assert all(split_cover[item["id"]] == ["big"] for item in halved)
    with patch.object(release, "input_tokens", text_size):
      fails(
        lambda: release.split_item(
          {"id": "one", "text": "x"}, {}, "test", 0, {"one": ["one"]}
        ),
        "cannot fit the token ceiling",
      )
    os.chdir(original)
  secret = "sentinel-secret-do-not-log"
  with (
    patch.dict(os.environ, {"GH_TOKEN": secret, "GEMINI_API_KEY": secret}),
    patch.object(
      release.subprocess,
      "run",
      return_value=subprocess.CompletedProcess(
        ["gh", "api"],
        1,
        b"",
        f'fatal: denied {secret} "https://storage.invalid/file?sig=private-signature"'.encode(),
      ),
    ),
  ):
    fails(
      lambda: release.run("gh", "api", "repos/owner/repo"), "fatal: denied [REDACTED]"
    )
    try:
      release.run("gh", "api", secret)
    except RuntimeError as error:
      assert secret not in str(error)
      assert "private-signature" not in str(error)
  calls = []

  def generate(context, evidence, model):
    calls.append(evidence)
    return "summary"

  units = [(str(n), "x" * 100) for n in range(8)]

  # Sizing is by counted tokens: the fake count is the evidence's character count.
  def by_size(model, request):
    payload = json.loads(request["contents"][0]["parts"][0]["text"])
    return sum(len(item["text"]) for item in payload["evidence"])

  with (
    patch.object(release, "measured", by_size),
    patch.object(release, "CHUNK_TOKENS", 350),
    patch.object(release, "summary") as steps,
  ):
    assert release.release_body(units, {}, "test", generate) == "summary"
    raw = [
      item["id"]
      for call in calls
      for item in call
      if not item["id"].startswith("summary:")
    ]
    assert raw == [identity for identity, _ in units]
    step_lines = [call.args[0] for call in steps.call_args_list]
    # The log names the packing decision: the counted payload, its ceiling and the
    # request count, so a chunked run reads as steps and not as unexplained calls.
    assert any(
      "over the 350 ceiling; packed into 3 request(s)" in line for line in step_lines
    )
    # The plan names each request's share before the requests run.
    assert any(
      "chunk 1/3: 3 evidence item(s), 300 tokens" in line for line in step_lines
    )
    fails(lambda: release.release_body([], {}, "test", generate), "No commits")
    fails(
      lambda: release.release_body(units, {}, "test", lambda *args: "x" * 1000),
      "did not shrink",
    )
  assert (
    release.response_text(
      {
        "candidates": [
          {
            "finishReason": "STOP",
            "content": {
              "parts": [{"text": "hidden", "thought": True}, {"text": "notes"}]
            },
          }
        ]
      }
    )
    == "notes"
  )
  fails(
    lambda: release.response_text({"candidates": [{"finishReason": "MAX_TOKENS"}]}),
    "incomplete",
  )
  fails(
    lambda: release.response_text({"promptFeedback": {"blockReason": "SAFETY"}}),
    "blocked",
  )
  # The chunk rounds cap the output. The compact combine round stays uncapped.
  sent = []

  def capture_call(model, action, payload, **_kwargs):
    sent.append(payload)
    return {
      "candidates": [
        {"finishReason": "STOP", "content": {"parts": [{"text": "text"}]}}
      ],
      "usageMetadata": {},
    }

  with patch.object(release, "gemini_call", capture_call):
    release.generate_once({"phase": "chunk"}, [{"id": "a", "text": "x"}], "test")
    release.generate_once({"phase": "combine"}, [{"id": "a", "text": "x"}], "test")
  assert sent[0]["generationConfig"] == {"maxOutputTokens": 8192}
  assert "generationConfig" not in sent[1]
  with (
    patch.object(release, "remote_tag_sha", return_value="abc"),
    patch.object(release, "releases", return_value=[{"id": 1, "tag_name": "v2"}]),
    patch.object(release, "api", return_value={"draft": False}) as api,
  ):
    fails(lambda: release.save_draft("owner/repo", "v2", "notes", "abc"), "published")
    assert api.call_count == 1
  phases = []

  def phased(context, evidence, model):
    phases.append(context.get("phase", "release"))
    return "summary"

  with (
    patch.object(release, "measured", by_size),
    patch.object(release, "CHUNK_TOKENS", 350),
  ):
    release.release_body([(str(n), "x" * 100) for n in range(80)], {}, "test", phased)
  # The first payload exceeds the ceiling and runs a chunk round. The final request writes the current release body.
  # A lower ceiling forces a combine round with several requests.
  assert set(phases) == {"chunk", "release"}
  assert phases[-1] == "release"
  with (
    patch.object(release, "measured", by_size),
    patch.object(release, "CHUNK_TOKENS", 150),
    patch.object(release, "summary"),
  ):
    release.release_body([(str(n), "x" * 100) for n in range(80)], {}, "test", phased)
  assert set(phases) == {"chunk", "combine", "release"}
  assert phases[-1] == "release"
  with (
    patch.object(release, "measured", by_size),
    patch.object(release, "CHUNK_TOKENS", 350),
  ):
    release.release_body([("one", "x" * 10)], {}, "test", phased)
  assert "release" in phases
  # A run sends raw commits to the chunk round once.
  # Later requests use the returned summaries.
  chunk_phases, chunk_ids = [], []

  def chunker(context, evidence, model):
    chunk_phases.append(context.get("phase", "release"))
    chunk_ids.extend(item["id"] for item in evidence)
    return "summary"

  with (
    patch.object(release, "measured", by_size),
    patch.object(release, "CHUNK_TOKENS", 350),
    patch.object(release, "summary"),
  ):
    reduced = release.prepared(
      [(str(n), "x" * 100) for n in range(8)], {}, "test", chunker
    )
  assert chunk_phases == ["chunk", "chunk", "chunk"]
  assert chunk_ids == [str(n) for n in range(8)]
  assert [item["id"] for item in reduced] == ["summary:0", "summary:1", "summary:2"]
  # release_body receives those ready items, and their text must survive the
  # hand-off: an item unpacked like a pair carries the literal keys instead.
  carried = []
  shared = [{"id": "summary:0", "text": "combined text"}]

  def carrier(context, evidence, model):
    carried.append(evidence)
    return "patch"

  with (
    patch.object(release, "measured", lambda model, request: 10),
    patch.object(release, "summary"),
  ):
    assert (
      release.release_body(shared, {"phase": "proposal"}, "test", carrier) == "patch"
    )
  assert carried == [shared]
  selected_models = []

  def tracked(context, evidence, model, on_success):
    on_success("gemini-3.6-flash")
    return "draft"

  with patch.object(release, "measured", by_size):
    assert (
      release.release_body(
        [("id", "diff")],
        {},
        ["gemini-3.8-flash", "gemini-3.6-flash"],
        tracked,
        on_success=selected_models.append,
      )
      == "draft"
    )
  assert selected_models == ["gemini-3.6-flash"]
  quota = json.dumps(
    {
      "error": {
        "code": 429,
        "message": "Quota exceeded for key AIzaSecret1",
        "status": "RESOURCE_EXHAUSTED",
      }
    }
  ).encode()
  assert (
    release.gemini_error_detail(quota)
    == "RESOURCE_EXHAUSTED Quota exceeded for key AIzaSecret1"
  )
  assert (
    release.gemini_error_detail(b"<html>bad gateway</html>")
    == "<html>bad gateway</html>"
  )
  assert release.gemini_error_detail(b"") == ""
  assert len(release.gemini_error_detail(b"x" * 900)) == 500

  class HttpResponse(io.BytesIO):
    def __init__(self, body, status):
      super().__init__(body)
      self.status = status

    def __enter__(self):
      return self

    def __exit__(self, *_):
      self.close()

  call_order = []

  def record_request(*_args, **_kwargs):
    call_order.append("request")
    return HttpResponse(b'{"ok": true}', 200)

  with (
    patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSecret1"}),
    patch.object(release.urllib.request, "urlopen", side_effect=record_request),
    patch.object(
      release,
      "summary",
      side_effect=lambda message: call_order.append(message),
    ),
  ):
    assert release.gemini_call("gemini-3.8-flash", "generateContent", {}) == {
      "ok": True
    }
  assert call_order == [
    "Gemini model attempt: gemini-3.8-flash (generateContent)",
    "request",
  ]
  with (
    patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}),
    patch("builtins.print") as print_output,
  ):
    release.summary("retry detail")
  print_output.assert_called_once_with("retry detail", flush=True)
  with tempfile.TemporaryDirectory() as directory:
    step_summary = Path(directory) / "summary.md"
    with (
      patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(step_summary)}),
      patch("builtins.print") as printed,
    ):
      release.summary("operational progress")
      assert not step_summary.exists()
      release.draft_summary("proposal result")
    assert step_summary.read_text(encoding="utf-8") == "proposal result\n"
    assert [call.args for call in printed.call_args_list] == [
      ("operational progress",),
      ("proposal result",),
    ]

  with (
    patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSecret1"}),
    patch.object(
      release.urllib.request,
      "urlopen",
      side_effect=release.urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/x",
        429,
        "Too Many",
        {},
        io.BytesIO(quota),
      ),
    ),
  ):
    fails(
      lambda: release.gemini_call("m", "generateContent", {}),
      "HTTP 429: RESOURCE_EXHAUSTED Quota exceeded for key [REDACTED]",
    )
  with (
    patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSecret1"}),
    patch.object(
      release.urllib.request,
      "urlopen",
      side_effect=TimeoutError("The read operation timed out"),
    ),
  ):
    fails(
      lambda: release.gemini_call("m", "generateContent", {}),
      "request timed out after 180s: The read operation timed out",
    )
  # The ladder moves to the next model on a request failure or blocked output, not
  # on an oversized request, and names every rung when all of them fail.
  good = {
    "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "ok"}]}}]
  }
  selected_model = []
  release.COOLDOWNS.clear()
  release.TOKEN_COUNTS.clear()
  with (
    patch.object(
      release,
      "gemini_call",
      side_effect=[
        {"totalTokens": 1},
        RuntimeError("Gemini generateContent failed: HTTP 404"),
        {"candidates": []},
        good,
      ],
    ),
    patch.object(release, "summary") as progress,
  ):
    assert release.generate({}, [], ["a", "b", "c"], selected_model.append) == "ok"
  assert selected_model == ["c"]
  lines = [call.args[0] for call in progress.call_args_list]
  assert any("HTTP 404" in line for line in lines)
  assert any("stepping down" in line for line in lines)
  assert any("cooling" in line for line in lines)
  with (
    patch.object(
      release,
      "gemini_call",
      side_effect=[
        {"totalTokens": 1},
        RuntimeError(
          "Gemini generateContent failed: request timed out after 180s: "
          "The read operation timed out"
        ),
        good,
      ],
    ),
    patch.object(release, "summary") as timeout_log,
  ):
    release.COOLDOWNS.clear()
    release.TOKEN_COUNTS.clear()
    assert release.generate({}, [], ["a", "b"]) == "ok"
  assert any(
    "request timed out after 180s" in call.args[0] and "stepping down" in call.args[0]
    for call in timeout_log.call_args_list
  )
  # A 429 cools that rung with the reported wait plus the safety margin, so the next select starts lower.
  # A model that answered cools for a minute. A fully cooling ladder waits for the earliest rung to come back.
  with (
    patch.object(
      release,
      "gemini_call",
      side_effect=[
        {"totalTokens": 1},
        RuntimeError("Gemini generateContent failed: HTTP 429: retry in 3.5s"),
        good,
      ],
    ),
    patch.object(release, "summary"),
    patch.object(release, "time") as clock,
  ):
    release.COOLDOWNS.clear()
    release.TOKEN_COUNTS.clear()
    clock.monotonic.return_value = 100.0
    assert release.generate({}, [], ["a", "b"]) == "ok"
    assert release.COOLDOWNS["a"] == 108.5
    assert release.COOLDOWNS["b"] == 165.0
  # A blocked output from a 200 response cools too: those tokens were spent.
  with (
    patch.object(
      release,
      "gemini_call",
      side_effect=[
        {"totalTokens": 1},
        {"candidates": [{"finishReason": "MAX_TOKENS"}]},
        good,
      ],
    ),
    patch.object(release, "summary") as blocked,
    patch.object(release, "time") as clock,
  ):
    release.COOLDOWNS.clear()
    release.TOKEN_COUNTS.clear()
    clock.monotonic.return_value = 50.0
    assert release.generate({}, [], ["a", "b"]) == "ok"
    assert release.COOLDOWNS["a"] == 115.0
    assert any("blocked output" in call.args[0] for call in blocked.call_args_list)
  with (
    patch.object(release, "gemini_call", side_effect=[{"totalTokens": 1}, good]),
    patch.object(release, "summary"),
    patch.object(release, "time") as clock,
  ):
    release.COOLDOWNS.clear()
    release.TOKEN_COUNTS.clear()
    release.COOLDOWNS.update({"a": 400.0, "b": 110.0})
    now = [100.0]
    clock.monotonic.side_effect = lambda: now[0]
    clock.sleep.side_effect = lambda delay: now.__setitem__(0, now[0] + delay)
    expected_wait = release.COOLDOWNS["b"] - now[0]
    assert release.generate({}, [], ["a", "b"]) == "ok"
    clock.sleep.assert_called_once_with(expected_wait)
    assert (
      release.COOLDOWNS["b"]
      == now[0] + release.SUCCESS_COOLDOWN + release.SAFETY_SECONDS
    )
    release.COOLDOWNS.clear()
  with (
    patch.object(release, "gemini_call", side_effect=RuntimeError("HTTP 503")),
    patch.object(release, "time") as clock,
  ):
    now = [0.0]
    clock.monotonic.side_effect = lambda: now[0]
    clock.sleep.side_effect = lambda delay: now.__setitem__(0, now[0] + delay)
    fails(
      lambda: release.generate({}, [], ["a", "b"]),
      "Every Gemini model failed: a: HTTP 503; b: HTTP 503",
    )
  release.TOKEN_COUNTS.clear()
  with patch.object(
    release, "gemini_call", return_value={"totalTokens": 10**7}
  ) as call:
    fails(lambda: release.generate({}, [], ["a", "b"]), "token allowance")
    assert call.call_count == 1
  assert release.model_ladder(" a-1 , b.2 ") == ["a-1", "b.2"]
  fails(lambda: release.model_ladder(","), "Model ladder is empty")
  fails(lambda: release.model_ladder("a b"), "Invalid Gemini model ID: a b")
  for phase in ("chunk", "combine", "release", "repair", "proposal"):
    with patch.object(
      release,
      "gemini_call",
      side_effect=[
        {"totalTokens": 20},
        {
          "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": "notes"}]}}
          ]
        },
      ],
    ) as call:
      release.COOLDOWNS.clear()
      assert release.generate({"phase": phase}, [], "test") == "notes"
      request = call.call_args_list[1].args[2]
      assert request["systemInstruction"]["parts"][0]["text"] == release.PROMPTS[phase]
      assert (
        request.get("generationConfig", {}).get("responseMimeType")
        == "application/json"
      ) == (phase == "proposal")
  payload = {
    "id": 2,
    "tag_name": "v2",
    "name": "v2",
    "body": "notes",
    "draft": True,
    "html_url": "https://github.com/owner/repo/releases/2",
    "target_commitish": "abc",
  }
  with (
    patch.object(release, "remote_tag_sha", return_value="abc"),
    patch.object(release, "releases", return_value=[]),
    patch.object(release, "api", return_value=payload) as api,
  ):
    assert release.save_draft("owner/repo", "v2", "notes", "abc") == payload["html_url"]
    assert api.call_args_list[0].args[1] == "POST"
    assert api.call_args_list[0].args[2]["draft"] is True
  assert release.next_version("", "minor") == "0.1.0"
  assert release.next_version("0.2.5", "major") == "0.3.0"
  assert release.next_version("0.2.5", "patch") == "0.2.6"
  assert release.next_version("0.2.5", "none") is None
  assert release.next_version("0.2.5", "minor", promote=True) == "1.0.0"
  fails(lambda: release.next_version("1.0.0-rc.1", "patch"), "prerelease")
  fails(lambda: release.next_version("1.01.0", "patch"), "stable numeric")
  fails(lambda: release.next_version("1.0.0", "review"), "review")
  sample = {
    "repository": "owner/repo",
    "target": "a" * 40,
    "previous": "",
    "base": "",
    "baseline_release": None,
    "impact": "patch",
    "promote": False,
    "version": "0.1.0",
    "tag": "v0.1.0",
    "body": release.INITIAL_TEMPLATE.replace("{{summary}}", "test").replace(
      "{{features}}", "None"
    ),
  }
  api_run = {
    "id": 42,
    "run_attempt": 1,
    "workflow_id": 9,
    "path": ".github/workflows/gemini-release.yml",
    "event": "workflow_dispatch",
    "status": "completed",
    "conclusion": "success",
    "head_branch": "main",
    "head_sha": "b" * 40,
    "repository": {"id": 7},
    "head_repository": {"id": 7},
  }
  artifact = {
    "name": "gemini-release-proposal",
    "expired": False,
    "size_in_bytes": 1000,
    "workflow_run": {
      "id": 42,
      "repository_id": 7,
      "head_repository_id": 7,
      "head_sha": "b" * 40,
      "head_branch": "main",
    },
  }

  def test_api(path, method="GET", payload=None):
    if path.endswith("/actions/runs/42"):
      return api_run
    if path.endswith("/actions/workflows/gemini-release.yml"):
      return {"id": 9}
    if path == "repos/owner/repo":
      return {"id": 7}
    if path.endswith("/artifacts?per_page=100"):
      return {"total_count": 1, "artifacts": [artifact]}
    if path.endswith("/git/refs") and method == "POST":
      assert payload == {"ref": "refs/tags/v0.1.0", "sha": "a" * 40}
      return {"ref": payload["ref"]}
    raise AssertionError(f"Unexpected API write/read: {path} {method}")

  with (
    patch.dict(os.environ, {"PROPOSAL_RUN_ID": "42"}),
    patch.object(release, "api", side_effect=test_api),
    patch.object(release, "download_proposal", side_effect=lambda *args: sample.copy()),
    patch.object(release, "check_remote_target"),
    patch.object(
      release, "generate", side_effect=AssertionError("Approval called Gemini")
    ),
    patch.object(release, "target_commit", return_value="a" * 40),
    patch.object(release, "current_base", return_value=("", "", None)),
    patch.object(release, "releases", return_value=[]),
    patch.object(release, "remote_ref", return_value=None) as ref,
    patch.object(release, "remote_tag_sha", return_value="a" * 40),
    patch.object(
      release, "save_draft", return_value="https://example.invalid/draft"
    ) as save,
    patch.object(release, "summary"),
  ):
    release.approve("owner/repo", "main")
    assert ref.call_count == 1 and save.call_count == 1
    assert save.call_args.args == ("owner/repo", "v0.1.0", sample["body"], "a" * 40)
    api_run["conclusion"] = "failure"
    fails(lambda: release.approve("owner/repo", "main"), "not a successful")
    assert ref.call_count == 1, "failed run must stop before tag lookup"
    api_run["conclusion"] = "success"
    api_run["run_attempt"] = 2
    fails(lambda: release.approve("owner/repo", "main"), "not a successful")
    api_run["run_attempt"] = 1
    artifact["expired"] = True
    fails(lambda: release.approve("owner/repo", "main"), "expired")
    artifact["expired"] = False
    sample["tag"] = "1.0.0"
    fails(lambda: release.approve("owner/repo", "main"), "does not match")
    assert ref.call_count == 1, "altered version must stop before tag lookup"
    sample["tag"] = "v0.1.0"
    with patch.object(
      release,
      "current_base",
      return_value=("v0.1.0", "c" * 40, {"id": 1, "published_at": "now"}),
    ):
      fails(lambda: release.approve("owner/repo", "main"), "baseline changed")
    with patch.object(release, "remote_tag_sha", return_value="c" * 40):
      fails(lambda: release.approve("owner/repo", "main"), "conflicts")
    with patch.object(
      release, "remote_ref", return_value={"object": {"sha": "a" * 40}}
    ):
      release.approve("owner/repo", "main")
    assert save.call_count == 2
    with patch.object(release, "save_draft", side_effect=RuntimeError("draft failure")):
      fails(lambda: release.approve("owner/repo", "main"), "draft failure")
    with patch.object(
      release, "releases", return_value=[{"tag_name": "v0.1.0", "draft": False}]
    ):
      fails(lambda: release.approve("owner/repo", "main"), "already published")

  def zipped(text, name="proposal.json"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
      archive.writestr(name, text)
    return stream.getvalue()

  for text, name, error in (
    (json.dumps(sample), "proposal.json", ""),
    (json.dumps(sample), "../proposal.json", "unexpected files"),
    ('{"tag":"a","tag":"b"}', "proposal.json", "Duplicate"),
  ):
    data = zipped(text, name)
    item = {"id": 12, "digest": "sha256:" + hashlib.sha256(data).hexdigest()}
    with patch.object(release, "run", return_value=data) as download:
      if error:
        fails(lambda item=item: release.download_proposal("owner/repo", item), error)
      else:
        assert release.download_proposal("owner/repo", item) == sample
        assert (
          download.call_args.args[-1] == "repos/owner/repo/actions/artifacts/12/zip"
        )
        assert download.call_args.kwargs["binary"] is True
      item["digest"] = "sha256:" + "0" * 64
      fails(
        lambda item=item: release.download_proposal("owner/repo", item),
        "digest or size mismatch",
      )
      item["digest"] = None
      fails(
        lambda item=item: release.download_proposal("owner/repo", item),
        "no valid digest",
      )
  assert release.PROMPTS["proposal"].startswith(
    "Task: determine the release impact and write release notes"
  )
  # GUIDELINES.md section 4: one rule per line, each a bullet, boundaries in every prompt.
  for prompt in release.PROMPTS.values():
    lines = prompt.strip().splitlines()
    assert lines[0].startswith("Task: ") and all(l.startswith("- ") for l in lines[1:])
    assert release.BOUNDARY in prompt and lines[-1].startswith("- Return only")
  assert set(release.PROMPTS) == {"chunk", "combine", "release", "repair", "proposal"}
  assert "style reference" in release.PROMPTS["release"]
  assert "NEVER use them as evidence" in release.PROMPTS["release"]
  assert release.TEMPLATE.startswith("## Summary\n")
  assert release.TEMPLATE.count("{{") == 6 and release.TEMPLATE.endswith(
    "{{comparison_url}}\n"
  )
  assert release.INITIAL_TEMPLATE.startswith("## Summary\n")
  assert release.INITIAL_TEMPLATE.count("{{") == 2
  # Sections may be dropped, never reordered or duplicated. Summary and the range link stay.
  full = {"template": release.TEMPLATE, "comparison_url": "https://x/compare/a...b"}
  release.check_body(
    "## Summary\n\ns\n\n## Fixes\n\nf\n\n## Commit comparison\n\nhttps://x/compare/a...b\n",
    full,
  )
  empty_feature = (
    "## Summary\n\ns\n\n## Features\n\n\n"
    "## Commit comparison\n\nhttps://x/compare/a...b\n"
  )
  normalized = release.omit_empty_sections(empty_feature, release.TEMPLATE)
  assert (
    normalized == "## Summary\n\ns\n\n## Commit comparison\n\nhttps://x/compare/a...b\n"
  )
  release.check_body(normalized, full)
  fails(lambda: release.check_body(empty_feature, full), "does not match")
  empty_summary = "## Summary\n\n\n## Commit comparison\n\nhttps://x/compare/a...b\n"
  assert "## Summary" in release.omit_empty_sections(empty_summary, release.TEMPLATE)
  fails(lambda: release.check_body(empty_summary, full), "does not match")
  invalid_body = "## Summary\n\ns\n\n## Features\n\nf\n"
  repaired_body = (
    "## Summary\n\ns\n\n## Features\n\nf\n\n## Commit comparison\n\n"
    "https://x/compare/a...b\n"
  )
  repair_calls = []

  def repair(context, evidence, model):
    repair_calls.append((context, evidence, model))
    return repaired_body

  with patch.object(release, "summary") as retry_log:
    assert (
      release.validated_body(
        invalid_body,
        {**full, "previous_release_notes": "style only"},
        "gemini-3.8-flash",
        repair,
      )
      == repaired_body
    )
  repair_context, repair_evidence, repair_model = repair_calls[0]
  assert repair_context["phase"] == "repair"
  assert repair_context["validation_error"]
  assert repair_context["draft"] == invalid_body
  assert "previous_release_notes" not in repair_context
  assert repair_evidence == []
  assert repair_model == "gemini-3.8-flash"
  assert "retrying same model once" in retry_log.call_args.args[0]
  invalid_calls = []

  def repair_still_invalid(context, evidence, model):
    invalid_calls.append((context, evidence, model))
    return invalid_body

  with patch.object(release, "summary"):
    fails(
      lambda: release.validated_body(
        invalid_body, full, "gemini-3.8-flash", repair_still_invalid
      ),
      "does not match",
    )
  assert len(invalid_calls) == 1
  fails(lambda: release.check_body("## Summary\n\ns\n", full), "does not match")
  fails(
    lambda: release.check_body("## Fixes\n\nf\n\nhttps://x/compare/a...b\n", full),
    "does not match",
  )
  fails(
    lambda: release.check_body(
      "## Fixes\n\nf\n\n## Summary\n\ns\n\nhttps://x/compare/a...b\n", full
    ),
    "does not match",
  )
  initial = {
    "template": release.INITIAL_TEMPLATE,
    "comparison_url": "https://x/commits/b",
  }
  release.check_body("## Summary\n\ns\n", initial)
  fails(
    lambda: release.check_body("## Summary\n\ns\n\n## Fixes\n\nf\n", initial),
    "does not match",
  )
  fails(
    lambda: release.check_body("## Summary\n\nhttps://x/commits/b\n", initial),
    "does not match",
  )
  assert release.release_template("") is release.INITIAL_TEMPLATE
  assert release.release_template("abc") is release.TEMPLATE
  workflow = (release.HERE / "gemini-release.yml").read_text()
  assert "python .github/workflows/gemini_release.py" in workflow
  assert "python github/workflows" not in workflow
  assert release.version_tag("0.2.1") == "v0.2.1"
  assert release.version_tag("") is None
  assert release.next_version("1.2.3", "major") == "2.0.0"
  assert release.next_version("1.2.3", "minor") == "1.3.0"
  fails(lambda: release.next_version("", "minor", promote=True), "Promotion requires")
  fails(
    lambda: release.next_version("1.2.3", "patch", promote=True), "Promotion requires"
  )
  empty_feature_body = release.INITIAL_TEMPLATE.replace("{{summary}}", "test").replace(
    "{{features}}", ""
  )
  with (
    tempfile.TemporaryDirectory() as directory,
    patch.dict(
      os.environ,
      {
        "PROPOSAL_PATH": str(Path(directory) / "proposal.json"),
        "IMPACT_OVERRIDE": "patch",
        "PROMOTE_TO_STABLE": "false",
      },
    ),
    patch.object(release, "target_commit", return_value="a" * 40),
    patch.object(release, "check_remote_target"),
    patch.object(release, "current_base", return_value=("", "", None)) as base,
    patch.object(release, "api", side_effect=AssertionError("Proposal made API write")),
    patch.object(release, "history", return_value=[("id", "diff")]),
    patch.object(release, "releases", return_value=[]),
    patch.object(release, "remote_ref", return_value=None),
    patch.object(release, "measured", lambda model, request: 10),
    patch.object(release, "release_body", return_value=empty_feature_body) as notes,
    patch.object(release, "summary"),
  ):
    sample["tag"] = "v0.1.0"
    release.propose("owner/repo", "main")
    stored = json.loads(Path(directory, "proposal.json").read_text())
    assert stored["target"] == "a" * 40 and stored["version"] == "0.1.0"
    assert stored["body"] == "## Summary\n\ntest\n\n"
    assert notes.call_count == 1, "the override avoids a classifier call"
    with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}):
      fails(lambda: release.propose("owner/repo", "main"), "reruns are not allowed")
    with patch.dict(os.environ, {"IMPACT_OVERRIDE": "none"}):
      release.propose("owner/repo", "main")
      assert not Path(directory, "proposal.json").exists(), "none must not upload"
    previous_notes = "Previous release body."
    baseline_record = {
      "id": 5,
      "published_at": "2026-01-01T00:00:00Z",
      "body": previous_notes,
    }
    base.return_value = ("v0.1.0", "b" * 40, baseline_record)
    compare_url = f"https://github.com/owner/repo/compare/{'b' * 40}...{'a' * 40}"
    notes.return_value = (
      f"## Summary\n\nnew change\n\n## Commit comparison\n\n{compare_url}\n"
    )
    proposal_context = []

    def capture_combined(_units, context, _model, on_success=None):
      proposal_context.append(dict(context))
      if on_success is not None:
        on_success("test")
      return {"impact": "patch", "body": notes.return_value}

    with (
      patch.dict(os.environ, {"IMPACT_OVERRIDE": "auto"}),
      patch.object(release, "combined_release", side_effect=capture_combined),
    ):
      release.propose("owner/repo", "main")
    assert len(proposal_context) == 1
    assert proposal_context[0]["previous_release_notes"] == previous_notes
    stored = json.loads(Path(directory, "proposal.json").read_text())
    assert stored["baseline_release"] == baseline_record
  # The auto proposal reduces raw evidence once, then makes one structured request for
  # both the SemVer impact and release body.
  shared = [{"id": "summary:0", "text": "combined"}]
  prepared_units, proposal_units = [], []

  def prepared_spy(
    units, context, model, generate_fn=release.generate, phase="evidence"
  ):
    prepared_units.append(list(units))
    return shared

  def proposal_spy(units, context, model, on_success=None):
    proposal_units.append(list(units))
    if on_success is not None:
      on_success("test")
    return {"impact": "patch", "body": empty_feature_body}

  with (
    tempfile.TemporaryDirectory() as directory,
    patch.dict(
      os.environ,
      {
        "PROPOSAL_PATH": str(Path(directory) / "proposal.json"),
        "IMPACT_OVERRIDE": "auto",
        "PROMOTE_TO_STABLE": "false",
      },
    ),
    patch.object(release, "target_commit", return_value="a" * 40),
    patch.object(release, "check_remote_target"),
    patch.object(release, "current_base", return_value=("", "", None)),
    patch.object(release, "history", return_value=[("id", "diff")]),
    patch.object(release, "releases", return_value=[]),
    patch.object(release, "remote_ref", return_value=None),
    patch.object(release, "prepared", prepared_spy),
    patch.object(
      release, "release_body", side_effect=AssertionError("separate body call")
    ),
    patch.object(release, "combined_release", proposal_spy),
  ):
    release.propose("owner/repo", "main")
  assert prepared_units == [[("id", "diff")]]
  assert proposal_units == [shared]
  structured = json.dumps({"impact": "minor", "body": empty_feature_body})
  selected_models = []
  with patch.object(release, "release_body", return_value=structured) as request:
    assert release.combined_release(
      [("id", "diff")], {}, "test", on_success=selected_models.append
    ) == {"impact": "minor", "body": empty_feature_body}
  assert request.call_args.args[1]["phase"] == "proposal"
  assert request.call_args.kwargs["on_success"] is not None
  fails(lambda: release.proposal_result("not JSON"), "invalid proposal JSON")
  fails(
    lambda: release.proposal_result(
      json.dumps({"impact": "minor", "body": "x", "extra": 1})
    ),
    "only impact and body",
  )
  fails(
    lambda: release.proposal_result('{"impact":"minor","impact":"patch","body":"x"}'),
    "invalid proposal JSON",
  )
  small_counts = patch.object(release, "measured", lambda model, request: 10)
  # An invalid structured answer retries on the next rung. The run stops only when
  # every rung refuses the required object.
  answers = ["not JSON", structured]
  real_release_body = release.release_body

  def flaky(context, evidence, model):
    return answers.pop(0)

  def routed(units, context, model, **options):
    return real_release_body(units, context, model, flaky, **options)

  def always_invalid(units, context, model, **options):
    return real_release_body(units, context, model, lambda *args: "not JSON", **options)

  with (
    small_counts,
    patch.object(release, "summary") as retried,
    patch.object(release, "release_body", routed),
  ):
    assert release.combined_release([("id", "diff")], {}, ["first", "second"]) == {
      "impact": "minor",
      "body": empty_feature_body,
    }
  assert any(
    "retrying on the next rung" in call.args[0] for call in retried.call_args_list
  )
  with (
    small_counts,
    patch.object(release, "summary"),
    patch.object(release, "release_body", always_invalid),
  ):
    fails(
      lambda: release.combined_release([("id", "diff")], {}, ["only"]),
      "invalid proposal answer",
    )
  with patch.object(
    release, "api", side_effect=[{"commit": {"sha": "b" * 40}}, {"status": "diverged"}]
  ):
    fails(
      lambda: release.check_remote_target("owner/repo", "main", "a" * 40),
      "no longer reachable",
    )
  with (
    patch.object(release, "git"),
    patch.object(release, "api", side_effect=RuntimeError("HTTP 401")),
  ):
    fails(lambda: release.remote_ref("owner/repo", "0.1.0"), "HTTP 401")
  with (
    patch.object(release, "git"),
    patch.object(release, "api", side_effect=RuntimeError("HTTP 404")),
  ):
    assert release.remote_ref("owner/repo", "0.1.0") is None
  print("Offline Gemini release checks passed")


def test_evidence_scope():
  original = Path.cwd()
  with tempfile.TemporaryDirectory() as directory:
    os.chdir(directory)
    try:

      def git(*args):
        return release.git(*args).strip()

      def commit(message):
        git("add", ".")
        git("commit", "-m", message)
        return git("rev-parse", "HEAD")

      git("init", "-b", "main")
      git("config", "user.name", "Check")
      git("config", "user.email", "check@example.invalid")
      policy_path = Path("evidence.json")
      policy_path.write_text(
        json.dumps(
          {"include": ["product/**", ".agents/**"], "exclude": [".agents/**"]}
        ),
        encoding="utf-8",
      )
      blacklist_path = Path("blacklist-evidence.json")
      blacklist_path.write_text(
        json.dumps({"include": [], "exclude": ["private/**"]}), encoding="utf-8"
      )
      Path("product").mkdir()
      Path("product/root.txt").write_text("root evidence\n")
      root = commit("root change")
      Path(".agents").mkdir()
      Path(".agents/only.txt").write_text("agent-only evidence\n")
      commit("agent-only change")
      Path("product/visible.txt").write_text("visible evidence\n")
      Path(".agents/secret.txt").write_text("excluded evidence\n")
      mixed = commit("mixed change")
      Path("product/skipped.txt").write_text("skip evidence\n")
      commit("skip release\n\nRelease-note: skip")
      Path("product/not-skipped.txt").write_text("non-exact trailer evidence\n")
      not_skipped = commit("do not skip\n\nRelease-note: skipped")
      scoped_target = git("rev-parse", "HEAD")
      policy = release.load_evidence_policy(policy_path)
      blacklist = release.load_evidence_policy(blacklist_path)
      assert release.scoped_paths(["unlisted/file.txt"], blacklist, root) == [
        "unlisted/file.txt"
      ]
      lines = []
      with patch.object(release, "summary", lines.append):
        units = release.history(scoped_target, root, policy=policy)
      assert [item[0] for item in units] == [mixed, not_skipped]
      text = dict(units)[mixed]
      assert "visible evidence" in text
      assert "excluded evidence" not in text
      assert ".agents/secret.txt" not in text
      assert "Selected paths:\nproduct/visible.txt" in text
      assert lines == [
        (
          "Evidence scope: 2 selected commit(s); 2 omitted "
          "(excluded-only: 1, release-note-skip: 1)"
        )
      ]
      Path("unowned").mkdir()
      Path("unowned/change.txt").write_text("unknown evidence\n")
      unknown = commit("unknown path")
      with (
        tempfile.TemporaryDirectory() as artifacts,
        patch.dict(
          os.environ,
          {
            "PROPOSAL_PATH": str(Path(artifacts) / "proposal.json"),
            "IMPACT_OVERRIDE": "patch",
            "PROMOTE_TO_STABLE": "false",
            "EVIDENCE": "commits-and-diffs",
            "GITHUB_RUN_ATTEMPT": "1",
          },
        ),
        patch.object(release, "target_commit", return_value=unknown),
        patch.object(release, "current_base", return_value=("v1.0.0", root, None)),
        patch.object(release, "load_evidence_policy", return_value=policy),
        patch.object(
          release,
          "prepared",
          side_effect=AssertionError("Gemini received unknown-path evidence"),
        ),
      ):
        fails(
          lambda: release.propose("owner/repo", "main"),
          "Unknown evidence path: unowned/change.txt",
        )
    finally:
      os.chdir(original)


def test_capacity_retry_budget():
  from collections import Counter

  now, waits, calls, answered = [0.0], [], [], []

  def sleep(delay):
    assert 0 < delay <= release.REQUEST_DEADLINE_SECONDS - now[0]
    waits.append(delay)
    now[0] += delay

  def attempt(_context, _evidence, rung, **kwargs):
    calls.append((rung, kwargs.get("timeout")))
    if len(calls) == 1:
      raise RuntimeError("Gemini generateContent failed: HTTP 503")
    if rung == "b":
      raise RuntimeError("Gemini generateContent failed: HTTP 400")
    return "recovered"

  with (
    patch.object(release, "measured", return_value=1),
    patch.object(release, "summary"),
    patch.object(release.time, "monotonic", side_effect=lambda: now[0]),
    patch.object(release.time, "sleep", side_effect=sleep),
    patch("random.uniform", return_value=0.0),
    patch.object(release, "generate_once", side_effect=attempt) as send,
  ):
    release.COOLDOWNS.clear()
    assert release.generate({}, [], ["a", "b"], answered.append) == "recovered"
    assert [rung for rung, _ in calls] == ["a", "b", "a"]
    assert answered == ["a"]
    assert waits == [release.CAPACITY_BACKOFF_SECONDS]
    assert all(0 < timeout <= release.API_TIMEOUT_SECONDS for _, timeout in calls)

    now[0] = 0.0
    waits.clear()
    answered.clear()
    release.COOLDOWNS.clear()
    send.side_effect = RuntimeError("Gemini generateContent failed: HTTP 503")
    send.reset_mock()
    for _ in range(2):
      fails(
        lambda: release.generate({}, [], ["a", "b"], answered.append),
        "Every Gemini model failed",
      )
    attempts = Counter(call.args[2] for call in send.call_args_list)
    assert attempts == {rung: 2 * (release.CAPACITY_RETRIES + 1) for rung in ("a", "b")}
    assert not answered
    first = release.CAPACITY_BACKOFF_SECONDS
    second = min(first * 2, release.CAPACITY_MAX_BACKOFF_SECONDS)
    assert waits == [first, second] * 2

    now[0] = 0.0
    waits.clear()
    release.COOLDOWNS.clear()
    budget = release.REQUEST_DEADLINE_SECONDS
    send.reset_mock()
    with (
      patch.object(
        release, "CAPACITY_BACKOFF_SECONDS", release.CAPACITY_MAX_BACKOFF_SECONDS * 2
      ),
      patch("random.uniform", return_value=release.CAPACITY_JITTER_SECONDS),
    ):
      fails(
        lambda: release.generate({}, [], ["a"], answered.append),
        "Every Gemini model failed",
      )
    assert (
      waits
      == [release.CAPACITY_MAX_BACKOFF_SECONDS + release.CAPACITY_JITTER_SECONDS]
      * release.CAPACITY_RETRIES
    )
    elapsed = 0.0
    for call, wait in zip(send.call_args_list, [0.0] + waits):
      elapsed += wait
      assert call.kwargs["timeout"] == min(
        release.API_TIMEOUT_SECONDS, budget - elapsed
      )

    now[0] = 0.0
    waits.clear()
    release.COOLDOWNS.clear()
    send.reset_mock()
    send.side_effect = RuntimeError(
      "Gemini generateContent failed: HTTP 503: earlier HTTP 429"
    )
    fails(
      lambda: release.generate({}, [], ["a"], answered.append),
      "Every Gemini model failed",
    )
    assert send.call_count == release.CAPACITY_RETRIES + 1

    now[0] = 0.0
    waits.clear()
    release.COOLDOWNS.clear()
    send.side_effect = [
      RuntimeError("Gemini generateContent failed: HTTP 400: upstream HTTP 503"),
      "valid",
    ]
    assert release.generate({}, [], ["a", "b"]) == "valid"
    assert "a" not in release.COOLDOWNS

    now[0] = 0.0
    waits.clear()
    release.COOLDOWNS.clear()
    hint = budget * 2
    send.reset_mock()
    send.side_effect = RuntimeError(
      f"Gemini generateContent failed: HTTP 429: retry in {hint}s"
    )
    try:
      release.generate({}, [], ["a"], answered.append)
    except RuntimeError as error:
      assert "deadline" in str(error) and "HTTP 429" in str(error)
    else:
      raise AssertionError("The deadline must stop a cooling request")
    assert now[0] == budget and sum(waits) == budget
    assert send.call_count == 1 and not answered
    assert release.COOLDOWNS["a"] == hint + release.SAFETY_SECONDS

    def late(_context, _evidence, _rung, **kwargs):
      now[0] += budget
      raise RuntimeError("Gemini generateContent failed: HTTP 503")

    now[0] = 0.0
    waits.clear()
    release.COOLDOWNS.clear()
    send.reset_mock()
    send.side_effect = late
    fails(lambda: release.generate({}, [], ["a"], answered.append), "deadline")
    assert send.call_count == 1 and not waits and not answered

    def late_success(_context, _evidence, _rung, **kwargs):
      now[0] += budget + release.CAPACITY_BACKOFF_SECONDS
      return "too late"

    now[0] = 0.0
    release.COOLDOWNS.clear()
    send.side_effect = late_success
    fails(lambda: release.generate({}, [], ["a"], answered.append), "deadline")
    assert not answered

    now[0] = 0.0
    release.COOLDOWNS.clear()
    send.reset_mock()
    send.side_effect = [
      RuntimeError("Gemini generateContent failed: HTTP 400"),
      "valid",
    ]
    assert release.generate({}, [], ["a", "b"], answered.append) == "valid"
    assert [call.args[2] for call in send.call_args_list] == ["a", "b"]
    assert not waits and answered == ["b"]
  release.COOLDOWNS.clear()


def test_daedalus_regressions():
  assert release.CHUNK_TOKENS == 150_000
  assert release.CHUNK_TIMEOUT_SECONDS == 90

  # 1. Untried rungs win over a previously failed top rung whose short cooldown expired.
  now, calls, waits = [0.0], [], []

  def sleep(delay):
    waits.append(delay)
    now[0] += delay

  def ping_pong_attempt(_context, _evidence, rung, **kwargs):
    calls.append((rung, kwargs.get("timeout")))
    if rung == "gemini-3.8-flash":
      now[0] += 3.0
      raise RuntimeError("Gemini generateContent failed: HTTP 503")
    if rung == "gemini-3.6-flash":
      now[0] += 75.0
      raise RuntimeError("Gemini generateContent failed: HTTP 503")
    return "lite-summary"

  with (
    patch.object(release, "measured", return_value=229_389),
    patch.object(release, "summary"),
    patch.object(release.time, "monotonic", side_effect=lambda: now[0]),
    patch.object(release.time, "sleep", side_effect=sleep),
    patch("random.uniform", return_value=0.0),
    patch.object(release, "generate_once", side_effect=ping_pong_attempt),
  ):
    release.COOLDOWNS.clear()
    # Start with all models cooling for 44s from previous requests: initial wait extends deadline.
    for model_name in release.MODELS:
      release.COOLDOWNS[model_name] = 44.0
    result = release.generate({"phase": "chunk"}, [], list(release.MODELS))
    assert result == "lite-summary"
    assert [rung for rung, _ in calls] == [
      "gemini-3.8-flash",
      "gemini-3.6-flash",
      "gemini-3.5-flash-lite",
    ]
    assert all(timeout == release.CHUNK_TIMEOUT_SECONDS for _, timeout in calls)
    # Large payload (> 125k tokens) 503 cools for at least SUCCESS_COOLDOWN + SAFETY_SECONDS (65s).
    assert release.COOLDOWNS["gemini-3.8-flash"] >= 47.0 + 65.0

  # 2. Diff-aware splitting splits on `diff --git` and `@@` boundaries before raw char midpoints.
  def char_tokens(_model, request):
    payload = json.loads(request["contents"][0]["parts"][0]["text"])
    return sum(len(item["text"]) for item in payload["evidence"])

  diff_text = (
    "commit abcdef1234567890\nAuthor: Test\n\n"
    "diff --git a/one.py b/one.py\n@@ -1 +1 @@\n-old1\n+new1\n"
    "diff --git a/two.py b/two.py\n@@ -1 +1 @@\n-old2\n+new2\n"
  )
  cover = {"commit1": ["commit1"]}
  with (
    patch.object(release, "input_tokens", char_tokens),
    patch.object(release, "TOKEN_COUNTS", {}),
    patch.object(release, "summary"),
  ):
    parts = release.split_item(
      {"id": "commit1", "text": diff_text}, {}, "test", 110, cover
    )
  assert len(parts) == 2
  assert "diff --git a/one.py" in parts[0]["text"]
  assert "diff --git a/two.py" not in parts[0]["text"]
  assert "diff --git a/two.py" in parts[1]["text"]
  assert parts[1]["text"].startswith("commit abcdef1234567890\n")

  hunk_text = (
    "diff --git a/big.py b/big.py\n"
    "@@ -1,2 +1,2 @@\n-" + "a" * 30 + "\n+" + "b" * 30 + "\n"
    "@@ -10,2 +10,2 @@\n-" + "c" * 30 + "\n+" + "d" * 30 + "\n"
  )
  hunk_cover = {"commit2": ["commit2"]}
  with (
    patch.object(release, "input_tokens", char_tokens),
    patch.object(release, "TOKEN_COUNTS", {}),
    patch.object(release, "summary"),
  ):
    hunk_parts = release.split_item(
      {"id": "commit2", "text": hunk_text}, {}, "test", 120, hunk_cover
    )
  assert len(hunk_parts) == 2
  assert "@@ -1,2 +1,2 @@" in hunk_parts[0]["text"]
  assert "@@ -10,2 +10,2 @@" in hunk_parts[1]["text"]


if __name__ == "__main__":
  test_release_pipeline()
  test_evidence_scope()
  test_capacity_retry_budget()
  test_daedalus_regressions()
