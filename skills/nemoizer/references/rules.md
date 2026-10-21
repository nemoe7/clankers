<!-- nonemo: N001; nonemo: N002; nonemo: N003 -->
# Nemoizer rules

| ID | Avoid | Use |
| --- | --- | --- |
| `N001` | `transmit` | send |
| `N002` | `pick` | select |
| `N003` | `kind` | type |

## Rotations

Each row matches the stem, so `picked`, `picking`, and `picks` all rotate to `select`. Add a row to the skill's rotation table and a pattern in `scripts/nemoize.py`: one table, one source.

A word that shares the stem but stands on its own, like `pickle`, carries a marker instead of a narrower pattern.

A row replaces its word as plain text, in lower, capital, and upper case. One stem word takes its own plain word: `picker` becomes `selector`, and `pickers` becomes `selectors`.

## Exclusions

- Use `nonemo: <id>` to suppress only the named rule on that line.
- For file scope, place `nonemo: <id>` in the first three lines with no avoided word before the marker.
- Use any comment syntax for `nonemo: <id>`; the scanner reads text, not syntax.
- Apply an exclusion only to a known matching rule ID.
- Do not rewrite exclusion markers or the rotation table, and apply only unsuppressed rotations.
- Print every nonemo marker with its path, line, rule ID, scope, and text when `nemoizer collect` or `--ignores` is used.

```python
value = "kind"  # nonemo: N003
```

```markdown
<!-- nonemo: N002 -->
```

## Prose measurements

| ID | Measurement | Cap |
| --- | --- | --- |
| `N004` | Words per line-level sentence | Instruction: 20; description: 25; unknown: not checked |
| `N005` | Sentences per covered paragraph | General: 6; stricter project override, such as 4 |

`nemoizer prose --context instruction --paragraph-cap 4 <paths>` returns JSON findings and per-file coverage. Paths are required; the sentence context is instruction, description, or unknown.

Findings carry rule, path, line, column, count, cap, and review status. Over-cap counts are review candidates, not meaning judgments; this command does not rewrite text or change the default rotation scan.

Native counters exclude inline code and fenced code, and count ordinary pipe-table cells separately. Paragraph counts cover prose blocks outside tables, headings, lists, and quotes; this is not a complete Markdown parser.

Existing exclusions apply at the reported line, or at file scope. Unknown IDs remain visible in the collector without suppressing a known rule; an unreadable or non-text file is marked not checked.

## Test assertion review

| ID | Candidate |
| --- | --- |
| `N006` | Direct prose-literal comparison or membership check against a named output channel |
| `N007` | Literal equality-style assertion against a known measurement name |

`nemoizer review-tests <paths>` is opt-in. It reports review candidates, per-file parser coverage, and parser errors without executing or rewriting tests.

The Python parser covers bare assertions and selected `self` or `cls` assertion methods. JavaScript uses an existing Acorn parser for selected Node `assert` calls. An unavailable parser is marked not checked without an installation.

Parser resolution starts at the linter directory, not at a target path or the current working directory.

Known output names include stdout, stderr, output, out, and err. Measurement names include geometry, timeout, duration, token count, and byte count fields. Configured expectations and growth comparisons are not flagged.

Assertion diagnostic messages and quoted fixture inputs are not expected-output checks. A reported literal can still be required executable, protocol, or verbatim data. These patterns do not prove a semantic violation.

Existing rule-specific exclusions and the collector apply. Exit status is 1 for candidates, 2 for parser errors or invalid arguments, and 0 otherwise. Not-checked coverage is not proof of a complete review.
