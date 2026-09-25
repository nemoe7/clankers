"""Offline contract checks for the rules -> secret Gist workflow; no GitHub credentials."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import publish_clankers_rules as sync

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
  "AGENTS.md",
  "ARENA.md",
  "CHATGPT-CUSTOM.txt",
  "CHATGPT-MORE.txt",
  "CLINE.md",
  "COMMIT-SPEC.txt",
  "KILO.md",
  "#clankers-rules.md",
  "kilo-code.md",
  "kilo-debug.md",
  "kilo-plan.md",
  "wenyan-CHATGPT-CUSTOM.txt",
  "wenyan-CHATGPT-MORE.txt",
}


def write(root: Path, name: str, text: str) -> Path:
  path = root / "rules" / name
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")
  return path


class FakeGitHub:
  def __init__(self):
    self.gist = None
    self.gist_id = None
    self.operations = []
    self.fail_variable = False

  def call(self, method, endpoint, payload=None):
    self.operations.append((method, endpoint, deepcopy(payload)))
    if method == "POST" and endpoint == "gists":
      assert self.gist is None and payload["public"] is False
      assert payload["description"] == sync.DESCRIPTION
      assert payload["files"]
      self.gist = {
        "id": "abcdef123456",
        "description": sync.DESCRIPTION,
        "public": False,
        "files": {
          name: {"content": record["content"]}
          for name, record in payload["files"].items()
        },
      }
      return deepcopy(self.gist)
    if method == "GET" and endpoint == "gists/abcdef123456":
      assert self.gist is not None
      return deepcopy(self.gist)
    if method == "PATCH" and endpoint == "gists/abcdef123456":
      for name, record in payload["files"].items():
        if record is None:
          self.gist["files"].pop(name)
        else:
          self.gist["files"][name] = {"content": record["content"]}
      assert self.gist["files"], "the API rejects a Gist with zero files"
      return deepcopy(self.gist)
    if method == "DELETE" and endpoint == "gists/abcdef123456":
      self.gist = None
      return None
    raise AssertionError((method, endpoint, payload))

  def variable(self, repo, action, value=None):
    assert repo == "nemoe7/clankers"
    self.operations.append(("variable", action, value))
    if self.fail_variable:
      raise RuntimeError("Variables write permission missing")
    if action == "set":
      assert value == "abcdef123456"
      self.gist_id = value
    elif action == "delete":
      self.gist_id = None
    else:
      raise AssertionError(action)

  def run(self, root):
    return sync.reconcile(
      root,
      self.gist_id or "",
      "nemoe7/clankers",
      call=self.call,
      store_id=self.variable,
    )


# Opt into a one-time snapshot check locally; future additions, moves and deletions must not
# break the workflow's fixture tests merely because the authoritative rules changed.
if os.environ.get("CHECK_CURRENT_RULE_NAMES") == "1":
  names, collisions = sync.collect_sources(ROOT)
  assert set(names) == EXPECTED and not collisions, (set(names) ^ EXPECTED, collisions)
  assert all(names[name] for name in EXPECTED)
workflow = (ROOT / ".github/workflows/publish-clankers-rules.yml").read_text()
for marker in (
  "branches: [main]",
  "- 'rules/**'",
  "- '!rules/refs/**'",
  "group: publish-clankers-rules-${{ github.repository }}",
  "cancel-in-progress: false",
  "contents: read",
  "GH_TOKEN: ${{ secrets.GIST_TOKEN }}",
  "GIST_ID: ${{ vars.GIST_ID }}",
  "run: python3 maintenance/check_publish_clankers_rules.py",
  "run: python3 maintenance/publish_clankers_rules.py",
):
  assert marker in workflow, marker
assert "contents: write" not in workflow and "actions: write" not in workflow

with tempfile.TemporaryDirectory() as tmp:
  root = Path(tmp)
  write(root, "README.md", "Root README\n")
  write(root, "a.md", "original\n")
  multiline = 'first line\nsecond "quoted" line\n🚀 last line\n'
  write(root, "nested/a.txt", multiline)
  write(root, "refs/ignore.md", "no\n")
  write(root, "refs/deep/ignore.txt", "no\n")
  write(root, "nested/README.md", "not eligible\n")
  write(root, "nested/README.txt", "not eligible\n")
  write(root, "ignored.py", "not eligible\n")
  gh = FakeGitHub()
  assert gh.run(root) == "abcdef123456"
  assert gh.gist_id == "abcdef123456"
  assert gh.gist["files"] == {
    "#clankers-rules.md": {
      "content": sync.gist_index("Root README\n", {"a.md", "nested-a.txt"})
    },
    "a.md": {"content": "original\n"},
    "nested-a.txt": {"content": multiline},
  }
  assert gh.operations[0][2]["files"]["nested-a.txt"]["content"] == multiline
  assert gh.operations[1] == ("variable", "set", "abcdef123456")
  before = len(gh.operations)
  gh.run(root)
  assert len(gh.operations) == before + 2
  assert gh.operations[-1][0] == "GET"
  # The first GET reads the current Gist. The second GET verifies the write.
  #

  gh.gist["files"]["README.md"] = {"content": "legacy root README\n"}
  gh.run(root)
  assert gh.operations[-2][2]["files"] == {
    "README.md": None,
  }, "legacy Gist README is removed"

  write(root, "a.md", "changed\n")
  write(root, "new.md", "new\n")
  write(root, "refs/also-ignored.md", "ignore\n")
  (root / "rules/nested/a.txt").unlink()
  gh.run(root)
  patch_payload = gh.operations[-2][2]["files"]
  assert patch_payload == {
    "a.md": {"content": "changed\n"},
    "new.md": {"content": "new\n"},
    "nested-a.txt": None,
    "#clankers-rules.md": {
      "content": sync.gist_index("Root README\n", {"a.md", "new.md"})
    },
  }
  assert set(gh.gist["files"]) == {"#clankers-rules.md", "a.md", "new.md"}
  (root / "rules/a.md").unlink()
  write(root, "refs/a.md", "moved into excluded refs\n")
  gh.run(root)
  assert gh.operations[-2][2]["files"] == {
    "a.md": None,
    "#clankers-rules.md": {"content": sync.gist_index("Root README\n", {"new.md"})},
  }, "moving to refs deletes old name and the index drops that file"
  write(root, "folder-a.md", "flat\n")
  write(root, "folder/a.md", "nested\n")
  gh.gist["files"]["folder-a.md"] = {"content": "Keep old Gist file\n"}
  gh.run(root)
  assert gh.gist["files"]["folder-a.md"]["content"] == "Keep old Gist file\n"
  assert gh.operations[-1][0] == "GET", "collision alone must not update or delete it"
  (root / "rules/folder-a.md").unlink()
  gh.run(root)
  assert gh.gist["files"]["folder-a.md"]["content"] == "nested\n"

  # The last eligible files can disappear: when only a collision survives, preserve its old
  # Gist file while deleting every unrelated stale name, then delete the whole empty Gist.
  write(root, "folder-a.md", "colliding again\n")
  (root / "rules/README.md").unlink()
  (root / "rules/new.md").unlink()
  gh.run(root)
  assert set(gh.gist["files"]) == {"folder-a.md"}
  assert gh.operations[-2][2]["files"] == {"#clankers-rules.md": None, "new.md": None}
  (root / "rules/folder/a.md").unlink()
  (root / "rules/folder-a.md").unlink()
  assert gh.run(root) is None and gh.gist is None and gh.gist_id is None
  assert gh.operations[-2][0] == "DELETE" and gh.operations[-1][1] == "delete"
  assert gh.run(root) is None and gh.gist_id is None, "no empty Gist is created"

  write(root, "blank.md", "")
  before = len(gh.operations)
  try:
    gh.run(root)
    raise AssertionError("Empty content was accepted by the API payload")
  except ValueError as error:
    assert "empty source" in str(error)
  assert len(gh.operations) == before, "an invalid source changes nothing"
  (root / "rules/blank.md").unlink()
  write(root, "return.md", "return\n")
  gh.fail_variable = True
  try:
    gh.run(root)
    raise AssertionError("A failed ID write was swallowed")
  except RuntimeError as error:
    assert "Variables write" in str(error)
  assert gh.gist is None and gh.gist_id is None, "an unrecorded new Gist is removed"
  assert gh.operations[-1][0] == "DELETE"

with tempfile.TemporaryDirectory() as tmp:
  root = Path(tmp)
  write(root, "README.md", "root\n")
  old = write(root, "old.md", "keep content\n")
  gh = FakeGitHub()
  gh.run(root)
  old.rename(root / "rules/renamed.md")
  gh.run(root)
  assert gh.operations[-2][2]["files"] == {
    "old.md": None,
    "renamed.md": {"content": "keep content\n"},
    "#clankers-rules.md": {"content": sync.gist_index("root\n", {"renamed.md"})},
  }, "a rename replaces the old flattened filename"
  (root / "rules/nested").mkdir()
  (root / "rules/renamed.md").rename(root / "rules/nested/README.md")
  gh.run(root)
  assert gh.operations[-2][2]["files"] == {
    "renamed.md": None,
    "#clankers-rules.md": {"content": sync.gist_index("root\n", set())},
  }, "becoming a nested README excludes and removes the old filename"
  gh.gist["files"]["#clankers-rules.md"]["truncated"] = True
  gh.run(root)
  assert gh.operations[-2][2]["files"] == {
    "#clankers-rules.md": {"content": sync.gist_index("root\n", set())}
  }

with tempfile.TemporaryDirectory() as tmp:
  root = Path(tmp)
  write(root, "valid.md", "new\n")
  gh = FakeGitHub()
  gh.run(root)
  for change in ({"description": "wrong"}, {"public": True}, {"truncated": True}):
    saved = deepcopy(gh.gist)
    gh.gist.update(change)
    try:
      gh.run(root)
      raise AssertionError("Overwrote a wrong or truncated Gist")
    except ValueError:
      pass
    gh.gist = saved
  try:
    sync.reconcile(root, "not-an-id", "nemoe7/clankers", call=gh.call)
    raise AssertionError("Invalid GIST_ID was accepted")
  except ValueError:
    pass

# JSON for arbitrary Unicode, quotes and newlines goes on stdin without shell expansion.
with patch.object(sync.subprocess, "run") as process:
  process.return_value = subprocess.CompletedProcess(
    [], 0, stdout='{"id":"abc"}', stderr=""
  )
  payload = {"files": {"weird.txt": {"content": 'hello\n"${HOME}" 🚀\n'}}}
  assert sync.api("POST", "gists", payload) == {"id": "abc"}
  args, kwargs = process.call_args
  assert args[0] == ["gh", "api", "--method", "POST", "gists", "--input", "-"]
  assert json.loads(kwargs["input"]) == payload
  assert kwargs["encoding"] == "utf-8" and kwargs["capture_output"] is True

readme = (ROOT / "rules/README.md").read_text(encoding="utf-8")
included = EXPECTED - {sync.INDEX_NAME}
index = sync.gist_index(readme, included)
for banned in (
  "apply.py",
  "apply.bat",
  "refs/",
  "maintenance/",
  "CHANGELOG",
  "Markdown lint",
  "## Install rules",
  "#arena-file",
  "rules/",
):
  assert banned not in index, banned
for name in included:
  assert f"`{name}`" in index, name
assert "Platform difference matrix" in index
assert "| Git/Hub | <ul><li>NEVER push unasked. </li>" in index
assert "Not authoritative." in index
assert "These files are the rules in this gist." in index
assert (
  sync._rewrite_links(
    "[A](a.md) [Nested](nested-a.txt) [Excluded](missing.md)", {"a.md", "nested-a.txt"}
  )
  == "[a.md](a.md) [nested-a.txt](nested-a.txt) "
)
assert (
  sync._rewrite_links("[rules/KILO.md](KILO.md) [Excluded](missing.md)", {"KILO.md"})
  == "[KILO.md](KILO.md) "
)
assert (
  sync._rewrite_links("[kilo/plan.md](kilo/plan.md)", {"kilo-plan.md"})
  == "[kilo-plan.md](kilo-plan.md)"
)
assert index != readme
assert sync.gist_index("root\n", set()) == (
  "# clankers-rules\n\n"
  "These files are the rules in this gist. This file is an index, not an agent rule.\n\n"
  "No other rule file is included.\n"
)

print(
  "PASS: workflow trigger/concurrency/permissions, secret Gist creation and ID storage, multiline JSON, authoritative update/add/delete/move/exclusions, collision preservation, empty-result cleanup, invalid input and rollback, gist index strip"
)
