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
