"""Offline checks for the userscripts -> secret Gist workflow."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import publish_userscripts as sync

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
  "arena-agent-hide-composer.user.js",
  "arena-agent-prompt.user.js",
  "arena-agent-steering.user.js",
}


def write(root: Path, name: str, text: str) -> Path:
  path = root / "userscripts" / name
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
      assert payload["description"] == sync.DESCRIPTION and payload["files"]
      self.gist = {
        "id": "abcdef123456",
        "description": sync.DESCRIPTION,
        "public": False,
        "files": {
          name: {"content": item["content"]} for name, item in payload["files"].items()
        },
      }
      return deepcopy(self.gist)
    if method == "GET" and endpoint == "gists/abcdef123456":
      assert self.gist is not None
      return deepcopy(self.gist)
    if method == "PATCH" and endpoint == "gists/abcdef123456":
      for name, item in payload["files"].items():
        if item is None:
          self.gist["files"].pop(name)
        else:
          self.gist["files"][name] = {"content": item["content"]}
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


if os.environ.get("CHECK_CURRENT_USERSCRIPT_NAMES") == "1":
  names = set(sync.collect_sources(ROOT))
  assert names == EXPECTED, names ^ EXPECTED
  assert all(sync.collect_sources(ROOT).values())

workflow = (ROOT / ".github/workflows/publish-userscripts.yml").read_text()
for marker in (
  "branches: [main]",
  "- 'userscripts/*.user.js'",
  "group: publish-userscripts-${{ github.repository }}",
  "cancel-in-progress: false",
  "contents: read",
  "GH_TOKEN: ${{ secrets.GIST_TOKEN }}",
  "USERSCRIPTS_GIST_ID: ${{ vars.USERSCRIPTS_GIST_ID }}",
  "run: python3 maintenance/check_publish_userscripts.py",
  "run: python3 maintenance/publish_userscripts.py",
):
  assert marker in workflow, marker
assert "pull_request" not in workflow and "workflow_dispatch" not in workflow
assert "contents: write" not in workflow and "actions: write" not in workflow

with tempfile.TemporaryDirectory() as tmp:
  root = Path(tmp)
  write(root, "a.user.js", "first\n")
  write(root, "b.user.js", 'second\n"quoted" 🚀\n')
  write(root, "README.md", "not a userscript\n")
  write(root, "nested/ignored.user.js", "not included\n")
  assert sync.collect_sources(root) == {
    "a.user.js": "first\n",
    "b.user.js": 'second\n"quoted" 🚀\n',
  }
  gh = FakeGitHub()
  assert gh.run(root) == "abcdef123456"
  assert gh.gist_id == "abcdef123456"
  assert gh.gist["files"] == {
    "a.user.js": {"content": "first\n"},
    "b.user.js": {"content": 'second\n"quoted" 🚀\n'},
  }
  assert gh.operations[1] == ("variable", "set", "abcdef123456")
  before = len(gh.operations)
  gh.run(root)
  assert len(gh.operations) == before + 2 and gh.operations[-1][0] == "GET"

  write(root, "a.user.js", "changed\n")
  write(root, "c.user.js", "third\n")
  (root / "userscripts/b.user.js").unlink()
  gh.run(root)
  assert gh.operations[-2][2]["files"] == {
    "a.user.js": {"content": "changed\n"},
    "b.user.js": None,
    "c.user.js": {"content": "third\n"},
  }
  assert set(gh.gist["files"]) == {"a.user.js", "c.user.js"}

  (root / "userscripts/a.user.js").unlink()
  (root / "userscripts/c.user.js").unlink()
  assert gh.run(root) is None and gh.gist is None and gh.gist_id is None
  assert gh.operations[-2][0] == "DELETE"
  assert gh.operations[-1] == ("variable", "delete", None)
  assert gh.run(root) is None and gh.gist_id is None

with tempfile.TemporaryDirectory() as tmp:
  root = Path(tmp)
  write(root, "one.user.js", "content\n")
  gh = FakeGitHub()
  gh.fail_variable = True
  try:
    gh.run(root)
    raise AssertionError("A failed variable write was swallowed")
  except RuntimeError as error:
    assert "Variables write" in str(error)
  assert gh.gist is None and gh.gist_id is None
  assert gh.operations[-1][0] == "DELETE"

  write(root, "empty.user.js", "")
  before = len(gh.operations)
  try:
    gh.run(root)
    raise AssertionError("An empty Gist file was accepted")
  except ValueError as error:
    assert "empty source" in str(error)
  assert len(gh.operations) == before

with tempfile.TemporaryDirectory() as tmp:
  root = Path(tmp)
  write(root, "one.user.js", "content\n")
  gh = FakeGitHub()
  gh.run(root)
  for change in ({"description": "wrong"}, {"public": True}, {"truncated": True}):
    saved = deepcopy(gh.gist)
    gh.gist.update(change)
    try:
      gh.run(root)
      raise AssertionError("An unrelated or public Gist was accepted")
    except ValueError:
      pass
    gh.gist = saved
  try:
    sync.reconcile(root, "not-a-gist-id", "nemoe7/clankers", call=gh.call)
    raise AssertionError("An invalid Gist ID was accepted")
  except ValueError:
    pass

with patch.object(sync.subprocess, "run") as process:
  process.return_value = subprocess.CompletedProcess(
    [], 0, stdout='{"id":"abc"}', stderr=""
  )
  payload = {"files": {"one.user.js": {"content": 'line\n"${HOME}" 🚀\n'}}}
  assert sync.api("POST", "gists", payload) == {"id": "abc"}
  args, kwargs = process.call_args
  assert args[0] == ["gh", "api", "--method", "POST", "gists", "--input", "-"]
  assert json.loads(kwargs["input"]) == payload
  assert kwargs["encoding"] == "utf-8" and kwargs["capture_output"] is True

print(
  "PASS: main-only workflow, secret Gist create/update/delete, ID storage, file filtering, validation and API JSON"
)
