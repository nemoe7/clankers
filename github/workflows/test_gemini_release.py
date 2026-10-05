"""Offline release-history, reduction and API-boundary tests; `pytest` runs them."""

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
    assert release.baseline(rows, "v2", target) == ("v1", root)
    assert release.baseline([], "v2", target) == ("", "")
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
    fails(lambda: release.baseline(rows, "v2", target, "absent"), "no published")
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

    # An oversized evidence list is cut in half until every part fits the ceiling.
    def text_size(model, request):
      payload = json.loads(request["contents"][0]["parts"][0]["text"])
      return sum(len(item["text"]) for item in payload["evidence"])

    with patch.object(release, "input_tokens", text_size):
      items = [{"id": str(n), "text": "x" * 40} for n in range(8)]
      cover = {item["id"]: [item["id"]] for item in items}
      parts = release.split_group(items, {}, "test", 100, cover)
    assert [[piece["id"] for piece in part] for part in parts] == [
      ["0", "1"],
      ["2", "3"],
      ["4", "5"],
      ["6", "7"],
    ]
    with patch.object(release, "input_tokens", text_size):
      groups = release.grouped(items, {}, "test", cover, 100)
    assert len(groups) == 4
    # One item's text halves only as a last resort, because a single item barely
    # reaches the ceiling.
    with (
      patch.object(release, "input_tokens", text_size),
      patch.object(release, "summary") as split_log,
    ):
      halved = release.split_group(
        [{"id": "big", "text": "x" * 80}], {}, "test", 20, {"big": ["big"]}
      )
    assert any(
      "splitting its text" in call.args[0] for call in split_log.call_args_list
    )
    assert [part[0]["id"] for part in halved] == [
      "big:1/2:1/2",
      "big:1/2:2/2",
      "big:2/2:1/2",
      "big:2/2:2/2",
    ]
    with patch.object(release, "input_tokens", text_size):
      fails(
        lambda: release.split_group(
          [{"id": "one", "text": "x"}], {}, "test", 0, {"one": ["one"]}
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
  # The whole payload does not fit the ceiling in the first round: the summarize round
  # runs as chunk, and the last request writes the release body whichever round it
  # lands on. A tighter ceiling forces a combine round with several requests.
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
  selected_models = []

  def tracked(context, evidence, model, on_success):
    on_success("gemini-3.7-flash")
    return "draft"

  with patch.object(release, "measured", by_size):
    assert (
      release.release_body(
        [("id", "diff")],
        {},
        ["gemini-3.8-flash", "gemini-3.7-flash"],
        tracked,
        on_success=selected_models.append,
      )
      == "draft"
    )
  assert selected_models == ["gemini-3.7-flash"]
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

  with (
    patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSecret1"}),
    patch.object(
      release.urllib.request,
      "urlopen",
      return_value=HttpResponse(b'{"ok": true}', 200),
    ),
    patch.object(release, "summary") as status_log,
  ):
    assert release.gemini_call("gemini-3.7-flash", "generateContent", {}) == {
      "ok": True
    }
  # A successful call is silent; the ladder prints the one line that matters.
  assert status_log.call_args is None
  with (
    patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}),
    patch("builtins.print") as print_output,
  ):
    release.summary("retry detail")
  print_output.assert_called_once_with("retry detail", flush=True)

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
  # The ladder moves to the next model on an HTTP failure or blocked output, not on
  # an oversized request, and names every rung when all of them fail.
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
  # A 429 cools that rung with the reported wait plus the safety margin, so the next
  # pick starts lower; a model that answered cools for a minute; a fully cooling
  # ladder waits for the earliest rung to come back.
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
    clock.monotonic.side_effect = [100.0, 100.0] + [200.0] * 6
    assert release.generate({}, [], ["a", "b"]) == "ok"
    clock.sleep.assert_called_once_with(15.0)
    assert release.COOLDOWNS["b"] == 265.0
    release.COOLDOWNS.clear()
  with patch.object(release, "gemini_call", side_effect=RuntimeError("HTTP 503")):
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
  for phase in ("chunk", "combine", "release", "repair", "version"):
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
      assert (
        call.call_args_list[1].args[2]["systemInstruction"]["parts"][0]["text"]
        == release.PROMPTS[phase]
      )
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
  assert release.PROMPTS["version"].startswith(
    "Task: classify the release impact of the supplied commit messages"
  )
  # GUIDELINES.md section 4: one rule per line, each a bullet, boundaries in every prompt.
  for prompt in release.PROMPTS.values():
    lines = prompt.strip().splitlines()
    assert lines[0].startswith("Task: ") and all(l.startswith("- ") for l in lines[1:])
    assert release.BOUNDARY in prompt and lines[-1].startswith("- Return only")
  assert set(release.PROMPTS) == {"chunk", "combine", "release", "repair", "version"}
  assert "style reference" in release.PROMPTS["release"]
  assert "NEVER use them as evidence" in release.PROMPTS["release"]
  assert release.TEMPLATE.count("{{") == 6 and release.TEMPLATE.endswith(
    "{{comparison_url}}\n"
  )
  assert release.INITIAL_TEMPLATE.count("{{") == 2
  # Sections may be dropped, never reordered or duplicated; Summary and the range link stay.
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
        "gemini-3.7-flash",
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
  assert repair_model == "gemini-3.7-flash"
  assert "retrying same model once" in retry_log.call_args.args[0]
  invalid_calls = []

  def repair_still_invalid(context, evidence, model):
    invalid_calls.append((context, evidence, model))
    return invalid_body

  with patch.object(release, "summary"):
    fails(
      lambda: release.validated_body(
        invalid_body, full, "gemini-3.7-flash", repair_still_invalid
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
  assert release.version_tag("v0.2.0", "0.2.1") == "v0.2.1"
  assert release.version_tag("0.2.0", "0.2.1") == "v0.2.1"
  assert release.version_tag("", "0.1.0") == "v0.1.0"
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
    version_context = []

    def capture_classification(_units, context, _model):
      version_context.append(dict(context))
      return "patch"

    with (
      patch.dict(os.environ, {"IMPACT_OVERRIDE": "auto"}),
      patch.object(release, "classify", side_effect=capture_classification),
    ):
      release.propose("owner/repo", "main")
    assert notes.call_args.args[1]["previous_release_notes"] == previous_notes
    assert len(version_context) == 1
    assert "previous_release_notes" not in version_context[0]
    stored = json.loads(Path(directory, "proposal.json").read_text())
    assert stored["baseline_release"] == baseline_record
  with patch.object(release, "release_body", return_value="minor"):
    assert release.classify([("id", "diff")], {}, "test") == "minor"
  with patch.object(release, "release_body", return_value="maybe minor"):
    fails(
      lambda: release.classify([("id", "diff")], {}, "test"),
      "invalid version classification",
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


if __name__ == "__main__":
  test_release_pipeline()
