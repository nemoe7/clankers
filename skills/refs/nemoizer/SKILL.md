---
name: nemoizer
description: >
  Find AI-flavored synonyms and replace them with the plain word, using one
  rotation table and a bundled linter that reads every text file, comments and
  prose included. Use when naming a variable, field, parameter, key, or prose
  term, when a draft sounds machine-written, or when asked to run or extend the
  rotation table.
compatibility: Python 3.10+, with Node.js and Acorn for JavaScript checks.
---

# Nemoizer

One table, one plain word per row. Read the table before you name something, and
run the linter before you hand work over.

## Rotation table

| Avoid | Use |
| --- | --- |
| `transmit` | send |
| `pick` | select |
| `kind` | type |

Read references/rules.md for lint IDs and their meanings.

## Linter

Run it from the repository root and pass the paths to read:

```bash
python3 skills/nemoizer/scripts/nemoize.py .
python3 skills/nemoizer/scripts/nemoize.py --ignore vendor --ignore third_party .
```

- Every text file is read, including comments and Markdown prose.
- Print each finding as `path:line: ID word -> use`, and exit 1 only for non-advisory findings. Mark P004 findings as advisory.
- Vendored and generated trees are skipped, and `--ignore` adds a directory or
  file.

- Run word rotations, sentence-length checks, and paragraph-length checks by default.
- Use 20 words per sentence for unclassified prose and 25 for an explicit description scope.

## Writing the rotation

`--format` rewrites the tree in place and prints every changed line twice, as it
was and as it becomes:

```bash
python3 skills/nemoizer/scripts/nemoize.py --format .
```

Each change prints as a pair: `path:line: -` and the old line, then `path:line: +`
and the new one.

- Do not rewrite exclusion markers or the rotation table, and apply only unsuppressed rotations.
- Pass a license file or a generated tree to `--ignore`; the tool reads every other
  text file.

## Ignore markers

- Use `nonemo: <id>` to suppress only the named rule on that line.
- For file scope, place `nonemo: <id>` in the first three lines with no avoided word before the marker.
- Use any comment syntax for `nonemo: <id>`; the scanner reads text, not syntax.
- Apply an exclusion only to a known matching rule ID.
- Print every nonemo marker with its path, line, rule ID, scope, and text when `nemoizer collect` or `--ignores` is used.

```bash
python skills/nemoizer/scripts/nemoizer collect .
python3 skills/nemoizer/scripts/nemoize.py --ignores .
```

Delete a marker when the line no longer needs it.

## Adding a row

1. Add the row to the table above.
2. Add one pattern, its name, and its plain word to `ROTATIONS` in
   `scripts/nemoize.py`; add a stem word that takes its own plain word to
   `EXCEPTIONS`.
3. Run `python3 -m pytest skills/nemoizer/scripts/test_nemoize.py`.

## Prose review

- Prefer removing “the” only when the phrase or sentence stays complete and natural, with unchanged meaning.
- Replace wordy action phrases with plain verbs only when actor, timing, and meaning stay unchanged.
- Remove stock openers and closers from prose only when they add no claim or required action.
- State the supported claim directly unless both sides of a contrast carry distinct facts.
- Preserve facts, negations, conditions, numbers, names, commands, citations, and confidence in every prose rewrite.
- Remove a closer only when it repeats earlier content and adds no fact, consequence, or required action.
- Replace an aphorism or claim of importance with its supported concrete claim.
- Remove an objection only when it answers no real claim and carries no independent information.
- Keep each list item that adds a distinct fact, and merge only redundant items.
- Vary repeated sentence openings only when repetition is unintended and every claim survives.
- Replace prose dashes unless the requested writing sample uses them, preserving each clause relation.
- Remove a redundant qualifier only when the remaining wording preserves confidence, scope, and every safety or legal condition.
- Remove unsupported claims of importance or future success while preserving concrete facts and stated plans.
- Name a relationship only when the source states it, otherwise retain its uncertainty.
- Keep an attached explanatory phrase only when the source supports its claim.
- Replace an unsupported quality claim with a supported measurement, or remove only the unsupported claim.
- Name the source and its claim when available, otherwise remove only unsupported appeals to authority.
- Use is, are, or has only when it preserves the relation expressed by a longer verb phrase.
- Remove bold labels only when the labels add no information or necessary structure.
- Match the requested quotation style without changing quoted content.
- State a missing source fact without inventing a plausible replacement or hiding a relevant knowledge limit.
- Remove a sentence that repeats its heading only when it adds no information.
- Remove redundant document narration while retaining useful source credits, action-changing caveats, and change history.
- Lead a contextual reply with its decision while retaining required evidence and reasoning that can change that decision.
- Limit instructions to 20 words and descriptions to 25 unless a longer form is necessary to preserve meaning.
- Rewrite noun clusters longer than three words when the rewrite preserves the technical term and its meaning.
- Keep one topic per paragraph within four sentences or the stricter project limit.
- Use a list for three or more steps or conditions while preserving their order and grouping.
- Define an uncommon technical term when needed, and use that term consistently.
- Prefer simple tenses unless a compound form carries confidence or current relevance that must survive.

## Test assertions

- Assert test behavior and relations instead of prose wording.
- Prefer named constants to literals when they define expected contract values.
- Assert pixel, configuration, and implementation measurements through growth, presence, or absence relations.
- Keep exact expected text only for executable, protocol, or verbatim-data contracts.
