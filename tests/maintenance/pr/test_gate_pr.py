"""Regression tests."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import gate_pr

VALID_BODY = """## Summary

Add a gate that validates every pull request commit and the pull request body.

## Changes

- Add the commit validator.
- Add the body validator.

## Validation

- [x] Run the gate locally.
- [ ] Run the gate in CI.
"""


def body_failures(text: str) -> list[str]:
  return [str(failure) for failure in gate_pr.validate_pr_body(text)]


def test_valid_body_passes():
  assert body_failures(VALID_BODY) == []


def test_the_two_optional_sections_may_stay_out():
  assert body_failures(VALID_BODY) == []
  text = VALID_BODY + "## Related\n\n- One bullet.\n"
  assert body_failures(text) == []


def test_a_none_section_fails():
  text = VALID_BODY + "## Breaking Changes\n\nNone\n"
  failures = body_failures(text)
  assert any("omit the heading" in failure for failure in failures)


def test_a_missing_required_section_fails():
  failures = body_failures(
    VALID_BODY.replace(
      "## Validation\n\n- [x] Run the gate locally.\n- [ ] Run the gate in CI.\n", ""
    )
  )
  assert failures and "expected the headings" in failures[0]


def test_reordered_section_fails():
  text = VALID_BODY.replace("## Changes", "## Temp").replace(
    "## Validation", "## Changes"
  )
  text = text.replace("## Temp", "## Validation")
  failures = body_failures(text)
  assert failures and "expected the headings" in failures[0]


def test_extra_section_fails():
  failures = body_failures(VALID_BODY + "## Notes\n\n- Note.\n")
  assert failures and "expected the headings" in failures[0]


def test_a_bang_commit_needs_a_filled_breaking_section():
  banged = ["feat(preview)!: drop the gate"]
  assert gate_pr.validate_breaking_crosscheck(banged, VALID_BODY)
  assert (
    gate_pr.validate_breaking_crosscheck(["feat(preview): drop the gate"], VALID_BODY)
    == []
  )
  filled = VALID_BODY + "## Breaking Changes\n\n- The gate goes.\n"
  assert gate_pr.validate_breaking_crosscheck(banged, filled) == []
  assert gate_pr.validate_breaking_crosscheck(banged, VALID_BODY)


def test_angle_brackets_pass_inside_a_fenced_block():
  text = VALID_BODY.replace(
    "Add a gate that validates every pull request commit and the pull request body.\n",
    "Add a gate that validates every pull request commit and the pull request body.\n"
    "```\n"
    "gh pr checks <PR> --watch\n"
    "```\n",
  )
  assert body_failures(text) == []


def test_angle_brackets_outside_a_fenced_block_fail():
  text = VALID_BODY.replace(
    "Add a gate that validates",
    "Run gh pr checks <PR> --watch, then add a gate that validates",
  )
  assert any("placeholder" in failure for failure in body_failures(text))


def test_content_before_the_first_section_fails():
  failures = body_failures("A heading-free sentence.\n\n" + VALID_BODY)
  assert any("content before ## Summary" in failure for failure in failures)


def test_content_after_the_final_section_fails():
  failures = body_failures(VALID_BODY + "\nTrailing content.\n")
  assert failures and "Validation" in failures[0]


def test_empty_summary_fails():
  failures = body_failures(
    VALID_BODY.replace(
      "Add a gate that validates every pull request commit and the pull request body.\n\n",
      "",
    )
  )
  assert any("Summary" in failure and "empty" in failure for failure in failures)


def test_multiple_summary_paragraphs_fail():
  text = VALID_BODY.replace(
    "Add a gate that validates every pull request commit and the pull request body.",
    "Add a gate.\n\nIt validates two contracts.",
  )
  assert any("exactly one paragraph" in failure for failure in body_failures(text))


def test_summary_list_fails():
  text = VALID_BODY.replace(
    "Add a gate that validates every pull request commit and the pull request body.",
    "- Add a gate.",
  )
  assert any("no list or heading" in failure for failure in body_failures(text))


def test_invalid_changes_entry_fails():
  text = VALID_BODY.replace("- Add the commit validator.", "A commit validator.")
  assert any(
    "Changes" in failure and "bullet" in failure for failure in body_failures(text)
  )


def test_invalid_validation_entry_fails():
  text = VALID_BODY.replace(
    "- [x] Run the gate locally.", "- [X] Run the gate locally."
  )
  assert any("Validation" in failure for failure in body_failures(text))


def test_breaking_changes_none_passes():
  assert body_failures(VALID_BODY) == []


def test_non_empty_breaking_changes_passes():
  text = VALID_BODY.replace(
    "## Breaking Changes\n\nNone", "## Breaking Changes\n\n- Drop the old flag."
  )
  assert body_failures(text) == []


def test_invalid_breaking_changes_fails():
  text = VALID_BODY + "## Breaking Changes\n\nNothing.\n"
  assert any("Breaking Changes" in failure for failure in body_failures(text))


def test_related_none_passes():
  assert body_failures(VALID_BODY) == []


def test_non_empty_related_passes():
  text = VALID_BODY.replace("## Related\n\nNone", "## Related\n\n- Closes #1.")
  assert body_failures(text) == []


def test_invalid_related_fails():
  text = VALID_BODY + "## Related\n\n#1.\n"
  assert any("Related" in failure for failure in body_failures(text))


def test_html_comment_fails():
  failures = body_failures(VALID_BODY + "<!-- hidden -->\n")
  assert any("HTML comments" in failure for failure in failures)


def test_html_comment_with_the_bang_end_tag_fails():
  failures = body_failures(VALID_BODY + "<!-- hidden --!>\n")
  assert any("HTML comments" in failure for failure in failures)


def test_placeholder_fails():
  failures = body_failures(
    VALID_BODY.replace("Add the commit validator.", "Add <the thing>.")
  )
  assert any("placeholder" in failure for failure in failures)


def test_h3_heading_fails():
  failures = body_failures(VALID_BODY.replace("## Changes", "## Changes\n\n### Detail"))
  assert any("H3 headings" in failure for failure in failures)


def test_valid_commit_passes():
  assert gate_pr.validate_commit("feat(preview): poll for notes") == []


def test_invalid_type_fails():
  failures = gate_pr.validate_commit("frobnicate(preview): poll for notes")
  assert any("unknown type" in failure.message for failure in failures)


def test_any_scope_passes():
  assert gate_pr.validate_commit("feat(nonsense): poll for notes") == []
  assert gate_pr.validate_commit("chore(changelog): note the release") == []


def test_invalid_case_fails():
  failures = gate_pr.validate_commit("feat(preview): Poll for notes")
  assert any("lowercase" in failure.message for failure in failures)


def test_trailing_period_fails():
  failures = gate_pr.validate_commit("feat(preview): poll for notes.")
  assert any("period" in failure.message for failure in failures)


def test_over_long_subject_fails():
  subject = "feat(preview): " + "a" * 70
  failures = gate_pr.validate_commit(subject)
  assert any("limit is 72" in failure.message for failure in failures)


def test_invalid_breaking_marker_fails():
  failures = gate_pr.validate_commit("feat!(preview): poll for notes")
  assert any("subject must match" in failure.message for failure in failures)


def test_valid_breaking_marker_passes():
  assert gate_pr.validate_commit("feat(preview)!: poll for notes") == []


def test_commit_body_fails():
  failures = gate_pr.validate_commit("feat(preview): poll for notes\n\nExtra detail.")
  assert any("no commit body" in failure.message for failure in failures)


def test_malformed_subject_fails():
  failures = gate_pr.validate_commit("feat(preview) poll for notes")
  assert any("subject must match" in failure.message for failure in failures)


def test_the_subject_carries_no_wording_rule():
  assert gate_pr.validate_commit("feat(preview): polling for notes") == []
  assert gate_pr.validate_commit("ci(workflows): add the security set") == []
  assert not hasattr(gate_pr, "IMPERATIVE_EXCEPTIONS")


def test_a_scope_binds_no_path_area():
  assert gate_pr.validate_commit("docs(preview): note the release") == []
  assert not hasattr(gate_pr, "SCOPE_AREAS")


def test_the_gate_holds_no_scope_list():
  assert not hasattr(gate_pr, "ALLOWED_SCOPES")


def test_pr_title_uses_the_commit_rules():
  assert gate_pr.validate_subject("feat(ci): run the gate", "PR title") == []
  failures = gate_pr.validate_subject("feat(ci): Run the gate", "PR title")
  assert any("lowercase" in failure.message for failure in failures)


def test_ste_lint_accepts_valid_text():
  passed, output = gate_pr.run_ste_lint("Start the server. Read the log.\n")
  assert passed, output


def test_ste_lint_rejects_invalid_text():
  passed, output = gate_pr.run_ste_lint("Start the server; read the log.\n")
  assert not passed
  assert "semicolon" in output


def test_ste_lint_selftest_passes():
  result = subprocess.run(
    [sys.executable, str(gate_pr.STE_LINT), "--selftest"],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr


def test_gate_propagates_the_ste_failure(tmp_path: Path):
  body = tmp_path / "body.md"
  body.write_text(
    VALID_BODY.replace("pull request body.", "pull request body. One line; two rules."),
    encoding="utf-8",
  )
  failures = gate_pr.check(None, None, str(body), True)
  assert any("STE lint failed" in failure.message for failure in failures)
  without_ste = gate_pr.check(None, None, str(body), False)
  assert not any("STE lint failed" in failure.message for failure in without_ste)


def test_main_exit_codes(tmp_path: Path, capsys):
  good = tmp_path / "good.md"
  good.write_text(VALID_BODY, encoding="utf-8")
  assert gate_pr.main(["--body-file", str(good)]) == 0
  bad = tmp_path / "bad.md"
  bad.write_text("## Summary\n\nText.\n", encoding="utf-8")
  assert gate_pr.main(["--body-file", str(bad)]) == 1
  assert "contract violation" in capsys.readouterr().out


def test_the_contract_runs_the_version_bump_checks(tmp_path: Path, monkeypatch):
  """A changed userscript without a higher version fails the contract.

  The contract and the Version Bumps job check each versioned module.
  Both require a higher version for every changed module."""
  base = tmp_path / "arena.user.js"
  base.write_text(
    "// ==UserScript==\n// @name         x | v99.0.0\n// @version      99.0.0\n"
    "// ==/UserScript==\n",
    encoding="utf-8",
  )
  seen = []

  def fake_git(*arguments: str) -> str:
    seen.append(arguments)
    if arguments[0] == "diff":
      return "userscripts/arena.user.js\n"
    if arguments[0] == "show":
      return base.read_text(encoding="utf-8")
    raise AssertionError(f"unexpected git call: {arguments}")

  monkeypatch.setattr(gate_pr, "_git", fake_git)
  failures = gate_pr.run_version_checks("base..HEAD")
  assert any("99.0.0" in str(failure) for failure in failures), failures
  assert any(call[0] == "diff" for call in seen), seen


def test_the_contract_accepts_a_bumped_userscript(tmp_path: Path, monkeypatch):
  """A change whose version rises one step above the base passes the check."""
  live_text = (gate_pr.ROOT / "userscripts" / "arena.user.js").read_text(
    encoding="utf-8"
  )
  match = re.search(r"//\s*@version\s+(\d+)\.(\d+)\.(\d+)", live_text)
  assert match is not None
  major, minor, patch = (int(part) for part in match.groups())
  if patch > 0:
    base_ver = f"{major}.{minor}.{patch - 1}"
  elif minor > 0:
    base_ver = f"{major}.{minor - 1}.0"
  else:
    base_ver = f"{max(0, major - 1)}.0.0"
  base = tmp_path / "arena.user.js"
  base.write_text(
    f"// ==UserScript==\n// @name         x | v{base_ver}\n// @version      {base_ver}\n"
    "// ==/UserScript==\n",
    encoding="utf-8",
  )

  def fake_git(*arguments: str) -> str:
    if arguments[0] == "diff":
      return "userscripts/arena.user.js\n"
    if arguments[0] == "show":
      return base.read_text(encoding="utf-8")
    raise AssertionError(f"unexpected git call: {arguments}")

  monkeypatch.setattr(gate_pr, "_git", fake_git)
  assert gate_pr.run_version_checks("base..HEAD") == []


def test_the_contract_rejects_multi_step_userscript_bump(tmp_path: Path, monkeypatch):
  """A change jumping multiple steps above the base fails the check."""
  base = tmp_path / "arena.user.js"
  base.write_text(
    "// ==UserScript==\n// @name         x | v0.0.1\n// @version      0.0.1\n"
    "// ==/UserScript==\n",
    encoding="utf-8",
  )

  def fake_git(*arguments: str) -> str:
    if arguments[0] == "diff":
      return "userscripts/arena.user.js\n"
    if arguments[0] == "show":
      return base.read_text(encoding="utf-8")
    raise AssertionError(f"unexpected git call: {arguments}")

  monkeypatch.setattr(gate_pr, "_git", fake_git)
  failures = gate_pr.run_version_checks("base..HEAD")
  assert any("one step above base" in str(failure) for failure in failures), failures


def test_the_bump_range_skips_a_missing_base():
  assert gate_pr.bump_range("0" * 40 + "..abc") is None
  assert gate_pr.bump_range("..abc") is None
  assert gate_pr.bump_range("abc..") is None
  assert gate_pr.bump_range("abc..def") == ("abc", "def")


def test_the_version_bump_mode_reports_failures(monkeypatch, capsys):
  failure = gate_pr.Failure("version bumps", "stale")
  monkeypatch.setattr(
    gate_pr,
    "run_version_checks",
    lambda value: [failure],
  )
  assert gate_pr.main(["--version-bumps", "base..HEAD"]) == 1
  output = capsys.readouterr()
  assert f"::error::{failure}" in output.out
  assert not output.err


ROOT = Path(__file__).resolve().parents[3]


INSTALLER = ROOT / "skills" / "arena-steering" / "scripts" / "install.sh"


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


def test_installed_commit_hook():
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
