# Nemoizer

Find and replace AI-flavored synonyms with plain words from one rotation table. The skill also guides prose and test review. Its tools check lexical matches and measurable prose limits, not meaning.

## Setup

The tools need Python 3.10 or later, with no extra Python packages. JavaScript checks need Node.js and Acorn. Use the repository paths below, or install the agent payload as described in [Skills](../README.md).

[SKILL.md](SKILL.md) holds the agent instructions. [Rule reference](references/rules.md) holds the rotations, concrete lint IDs, exclusion syntax, and prose limits.

## Quick start

From the repository root in Windows cmd:

```cmd
python skills\nemoizer\scripts\nemoizer path\to\project
python skills\nemoizer\scripts\nemoizer --ignore vendor .
python skills\nemoizer\scripts\nemoizer collect path\to\project
```

The first two commands scan without edits. The collector lists every exclusion marker: location, ID, scope, and text. Unknown markers stay visible without suppressing a known rule.

## Formatting

Formatting changes files. It is a lexical rewrite, not a code refactor, and can change identifiers, strings, comments, data, and prose.

```cmd
python skills\nemoizer\scripts\nemoizer --format path\to\project
```

The command prints each changed line before and after the rewrite. Rule-specific exceptions and the rotation table are not rewritten.

## Prose counts

```cmd
python skills\nemoizer\scripts\nemoizer prose --context instruction --paragraph-cap 4 path\to\draft.md
```

Code prose comes from comments and Python docstrings, not ordinary string literals. Escaped docstring line breaks use the physical string span for source locations.

Default scans include sentence and paragraph checks. Instruction and unclassified prose use 20 words per sentence. An explicit description scope uses 25.

The paragraph cap is four sentences. A project can set a stricter cap from one through four.

Output is JSON with review candidates and per-file coverage.

Native counters omit code spans and fences. They count ordinary pipe-table cells separately. Paragraph counts exclude headings, lists, quotes, and tables. Sentence counts join wrapped lines in ordinary prose blocks.

## Test assertion review

```cmd
python skills\nemoizer\scripts\nemoizer review-tests path\to\tests
```

Default scans review selected output-text and fixed-measurement assertion shapes in discovered tests and recognized helpers. The checker uses Python syntax trees and an existing Acorn parser for JavaScript. The checker marks unavailable or unsupported parsing as not checked.

Discovery uses pytest.ini, test names, and test declarations, without treating every imported production file as a test. `--test-helper` includes another helper.

It does not execute or rewrite tests. Findings need manual review: exact executable, protocol, and verbatim-data expectations can be valid.

## Results and limits

NMO901 (pick/select and repository/repo) and STE901-STE903 are marked for manual review. Checks report them without failure. Explicit formatting can still rewrite NMO901.

| Mode | Result |
| --- | --- |
| Scan | Text findings: exit 1 for non-advisory findings, 2 for required-parser errors, and 0 otherwise |
| Format | Changed lines, with exit 0 on completion |
| Collect | Every marker, with exit 0 on completion |
| Prose | JSON candidates and coverage, with exit 1 for candidates, 2 for parser errors, and 0 otherwise |
| Review tests | JSON candidates, coverage, and errors, with exit 1 for candidates, 2 for parser errors, and 0 otherwise |

Invalid command arguments return exit 2. Prose mode requires existing target paths. Directory scans omit configured dependency, build, and session-state paths.

Word rotations skip binary and invalid UTF-8 files. Static test discovery can miss dynamic helpers. Coverage limits remain visible.

The prose parser covers ordinary Markdown shapes, not all Markdown syntax. It does not infer instruction context or prove clarity, accuracy, or meaning preservation.

Manual review still covers unsupported claims, redundant prose, test behavior, and required protocol or verbatim-data contracts. This README is human documentation and is not part of the installed skill payload.
