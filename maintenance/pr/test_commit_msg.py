"""Test the commit-msg hook embedded in the preview installer."""

import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "skills" / "arena-skill" / "scripts" / "install.sh"
SPEC = ROOT / "rules" / "COMMIT-SPEC.txt"


def installed_hook_source():
  installer = INSTALLER.read_text(encoding="utf-8")
  match = re.search(
    r'cat > "\$GIT_HOOK" <<\'COMMIT_MSG_HOOK\'[^\n]*\n(.*?)\nCOMMIT_MSG_HOOK',
    installer,
    re.DOTALL,
  )
  assert match, "installer must contain the commit-msg hook body"
  return match.group(1) + "\n"


def run_hook(hook, repo, message_path, message):
  message_path.write_text(message, encoding="utf-8")
  result = subprocess.run(
    [str(hook), str(message_path)],
    cwd=repo,
    capture_output=True,
    text=True,
    check=False,
  )
  return result, message_path.read_text(encoding="utf-8")


def main():
  hook_source = installed_hook_source()
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text(hook_source, encoding="utf-8")
    hook.chmod(0o755)
    message_path = root / "COMMIT_EDITMSG"

    valid = [
      "feat(git): install a project commit hook\n",
      "fix!: remove the old behavior\n",
      "docs: clarify commit message rules\n",
      "ci: validate commit messages\n",
      "revert: restore earlier behavior\n",
      "docs: " + "a" * 66 + "\n",
    ]
    invalid = [
      "unknown: reject this type\n",
      "Feature: add a hook\n",
      "fix: Add a hook\n",
      "fix: add a hook.\n",
      "fix(scope with spaces): add a hook\n",
      "docs: " + "a" * 67 + "\n",
      "fix: add a hook\n\nBody text\n",
      "fix: add a hook\n\nCo-authored-by: arena-agent <agent@example.test>\n",
    ]
    for message in valid:
      result, after = run_hook(hook, repo, message_path, message)
      assert result.returncode == 0, result.stderr
      assert after == message
      assert "Co-authored-by: arena-agent" not in after
    for message in invalid:
      result, after = run_hook(hook, repo, message_path, message)
      assert result.returncode != 0, message
      assert result.stderr.startswith("commit-msg: ")
      assert after == message

    (repo / "rules").mkdir()
    (repo / "rules" / "COMMIT-SPEC.txt").write_text(
      "invalid specification\n", encoding="utf-8"
    )
    result, after = run_hook(hook, repo, message_path, valid[0])
    assert result.returncode == 0, result.stderr
    assert after == valid[0]

  specification = SPEC.read_text(encoding="utf-8")
  spec_types = re.search(r"\ballowed types: ([a-z ]+);", specification)
  hook_types = re.search(
    r'^allowed_types = "([a-z ]+)"\.split\(\)$', hook_source, re.MULTILINE
  )
  spec_limit = re.search(r"<=\s*(\d+)\s+chars\b", specification)
  hook_limit = re.search(r"^subject_limit = (\d+)$", hook_source, re.MULTILINE)
  assert spec_types and hook_types, "allowed types must be in the spec and hook"
  assert spec_types.group(1).split() == hook_types.group(1).split()
  assert spec_limit and hook_limit, "subject limits must be in the spec and hook"
  assert int(spec_limit.group(1)) == int(hook_limit.group(1))
  print("Commit message hook checks passed without a runtime specification")


if __name__ == "__main__":
  main()
