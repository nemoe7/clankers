---
name: nemoizer
description: >
  Replace AI-flavored synonyms with the plain word, using one rotation table and
  a bundled linter that reads every text file, comments and prose included.
---

# Nemoizer

| Avoid | Use |
| --- | --- |
| `transmit` | send |
| `pick` | select |
| `kind` | type |

Each row matches the stem, so `picked`, `picking`, and `picks` rotate to <!-- nemoizer: ignore -->
`select`. Add a row here and a pattern in `scripts/nemoize.py`. <!-- nemoizer: ignore -->

A word that shares the stem but stands on its own, like `pickle`, carries a <!-- nemoizer: ignore -->
marker instead of a narrower pattern. <!-- nemoizer: ignore -->

```bash
python3 skills/nemoizer/scripts/nemoize.py .
python3 skills/nemoizer/scripts/nemoize.py --ignore vendor .
python3 skills/nemoizer/scripts/nemoize.py --ignores .
```

A finding prints `path:line: word -> use` and exits 1. Vendored and generated
trees are skipped, and `--ignore` adds a directory or file.

`--format` rewrites the tree and prints each changed line as it was and as it
becomes:

```bash
python3 skills/nemoizer/scripts/nemoize.py --format .
```

A row replaces its word as plain text, in lower, capital and upper case. One stem
word takes its own plain word: `picker` becomes `selector`. <!-- nemoizer: ignore -->

A line that carries `nemoizer: ignore` is skipped. A marker in the first three
lines skips the whole file. `--ignores` prints every marker as `path:line: text`,
so a suppression never escapes review.

The rotation has landed, so `check.py` runs the linter and a new avoided word fails
the gate.

## Prose review

- Replace wordy action phrases with plain verbs only when actor, timing, and meaning stay unchanged.
- Remove stock prose openers and closers only if they add no claim or required action.
- State supported claims directly unless both contrast sides carry distinct facts.
- Preserve facts, negations, conditions, numbers, names, commands, citations, and confidence in every prose rewrite.
- Remove a closer only when it repeats earlier content and adds no fact, consequence, or required action.
- Replace aphorisms or importance claims with their supported concrete claims.
- Remove objections only if they answer no real claim and carry no independent information.
- Keep list items that add distinct facts, and merge only redundant items.
- Vary repeated sentence openings only when repetition is unintended and every claim survives.
- Replace prose dashes unless the requested writing sample uses them, preserving each clause relation.
- Remove redundant qualifiers only if confidence, scope, and every safety or legal condition survive.
- Remove unsupported importance or future-success claims, retaining concrete facts and stated plans.
- Name relationships only when the source states them, otherwise retain their uncertainty.
- Keep an attached explanatory phrase only when the source supports its claim.
- Replace unsupported quality claims with supported measurements, or remove only unsupported claims.
- Name the source and its claim when available, otherwise remove only unsupported appeals to authority.
- Use is, are, or has only if it preserves the longer verb phrase's relation.
- Remove bold labels only if they add no information or necessary structure.
- Match requested quotation style without changing quoted content.
- State missing source facts without inventing plausible replacements or hiding relevant knowledge limits.
- Remove sentences that repeat their headings only if they add no information.
- Remove redundant document narration while retaining useful source credits, action-changing caveats, and change history.
- Lead contextual replies with their decisions, retaining required evidence and reasoning that can change those decisions.
- Limit instructions to 20 words and descriptions to 25 unless preserving meaning requires more.
- Rewrite noun clusters over three words when the technical term and its meaning survive.
- Keep one topic per paragraph within six sentences or the stricter project limit.
- List three or more steps or conditions, preserving their order and grouping.
- Define uncommon technical terms when needed, and use them consistently.
- Prefer simple tenses unless compound forms carry confidence or current relevance that must survive.
