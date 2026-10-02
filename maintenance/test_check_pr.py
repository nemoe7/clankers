"""Tests for the pull request contract gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import check_pr

VALID_BODY = """## Summary

Add a gate that validates every pull request commit and the pull request body.

## Changes

- Add the commit validator.
- Add the body validator.

## Validation

- [x] Run the gate locally.
- [ ] Run the gate in CI.

## Breaking Changes

None

## Related

None
"""


def body_failures(text: str) -> list[str]:
  return [str(failure) for failure in check_pr.validate_pr_body(text)]


def test_valid_body_passes():
  assert body_failures(VALID_BODY) == []


def test_missing_section_fails():
  failures = body_failures(VALID_BODY.replace("## Related\n\nNone\n", ""))
  assert failures and "five H2 headings" in failures[0]


def test_reordered_section_fails():
  text = VALID_BODY.replace("## Changes", "## Temp").replace(
    "## Validation", "## Changes"
  )
  text = text.replace("## Temp", "## Validation")
  failures = body_failures(text)
  assert failures and "five H2 headings" in failures[0]


def test_extra_section_fails():
  failures = body_failures(
    VALID_BODY.replace("## Related", "## Notes\n\n- Note.\n\n## Related")
  )
  assert failures and "five H2 headings" in failures[0]


def test_content_before_the_first_section_fails():
  failures = body_failures("A heading-free sentence.\n\n" + VALID_BODY)
  assert any("content before ## Summary" in failure for failure in failures)


def test_content_after_the_final_section_fails():
  failures = body_failures(VALID_BODY + "\nTrailing content.\n")
  assert any(
    "content after the final ## Related content" in failure for failure in failures
  )


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
  text = VALID_BODY.replace(
    "## Breaking Changes\n\nNone", "## Breaking Changes\n\nNothing."
  )
  assert any("Breaking Changes" in failure for failure in body_failures(text))


def test_related_none_passes():
  assert body_failures(VALID_BODY) == []


def test_non_empty_related_passes():
  text = VALID_BODY.replace("## Related\n\nNone", "## Related\n\n- Closes #1.")
  assert body_failures(text) == []


def test_invalid_related_fails():
  text = VALID_BODY.replace("## Related\n\nNone", "## Related\n\n#1.")
  assert any("Related" in failure for failure in body_failures(text))


def test_html_comment_fails():
  failures = body_failures(VALID_BODY + "<!-- hidden -->\n")
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
  assert check_pr.validate_commit("feat(preview): poll for notes") == []


def test_invalid_type_fails():
  failures = check_pr.validate_commit("frobnicate(preview): poll for notes")
  assert any("unknown type" in failure.message for failure in failures)


def test_invalid_scope_fails():
  failures = check_pr.validate_commit("feat(nonsense): poll for notes")
  assert any("unknown scope" in failure.message for failure in failures)


def test_invalid_case_fails():
  failures = check_pr.validate_commit("feat(preview): Poll for notes")
  assert any("lowercase" in failure.message for failure in failures)


def test_trailing_period_fails():
  failures = check_pr.validate_commit("feat(preview): poll for notes.")
  assert any("period" in failure.message for failure in failures)


def test_over_long_subject_fails():
  subject = "feat(preview): " + "a" * 70
  failures = check_pr.validate_commit(subject)
  assert any("limit is 72" in failure.message for failure in failures)


def test_invalid_breaking_marker_fails():
  failures = check_pr.validate_commit("feat!(preview): poll for notes")
  assert any("subject must match" in failure.message for failure in failures)


def test_valid_breaking_marker_passes():
  assert check_pr.validate_commit("feat(preview)!: poll for notes") == []


def test_commit_body_fails():
  failures = check_pr.validate_commit("feat(preview): poll for notes\n\nExtra detail.")
  assert any("no commit body" in failure.message for failure in failures)


def test_malformed_subject_fails():
  failures = check_pr.validate_commit("feat(preview) poll for notes")
  assert any("subject must match" in failure.message for failure in failures)


def test_a_scope_binds_no_path_area():
  assert check_pr.validate_commit("docs(preview): note the release") == []
  assert not hasattr(check_pr, "SCOPE_AREAS")


def test_the_changelog_scope_is_gone():
  failures = check_pr.validate_commit("chore(changelog): note the release")
  assert any("unknown scope" in failure.message for failure in failures)


def test_pr_title_uses_the_commit_rules():
  assert check_pr.validate_subject("feat(ci): run the gate", "PR title") == []
  failures = check_pr.validate_subject("feat(ci): Run the gate", "PR title")
  assert any("lowercase" in failure.message for failure in failures)


def test_ste_lint_accepts_valid_text():
  passed, output = check_pr.run_ste_lint("Start the server. Read the log.\n")
  assert passed, output


def test_ste_lint_rejects_invalid_text():
  passed, output = check_pr.run_ste_lint("Start the server; read the log.\n")
  assert not passed
  assert "semicolon" in output


def test_ste_lint_selftest_passes():
  result = subprocess.run(
    [sys.executable, str(check_pr.STE_LINT), "--selftest"],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr


def test_check_propagates_the_ste_failure(tmp_path: Path):
  body = tmp_path / "body.md"
  body.write_text(VALID_BODY.replace("None", "None;", 1), encoding="utf-8")
  failures = check_pr.check(None, None, str(body), True)
  assert any("STE lint failed" in failure.message for failure in failures)
  without_ste = check_pr.check(None, None, str(body), False)
  assert not any("STE lint failed" in failure.message for failure in without_ste)


def test_main_exit_codes(tmp_path: Path, capsys):
  good = tmp_path / "good.md"
  good.write_text(VALID_BODY, encoding="utf-8")
  assert check_pr.main(["--body-file", str(good)]) == 0
  bad = tmp_path / "bad.md"
  bad.write_text("## Summary\n\nText.\n", encoding="utf-8")
  assert check_pr.main(["--body-file", str(bad)]) == 1
  assert "contract violation" in capsys.readouterr().out
