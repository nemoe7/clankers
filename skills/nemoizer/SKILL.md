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

Each row matches the stem, so `picked`, `picking`, and `picks` rotate to
`select`. Add a row here and a pattern in `scripts/nemoize.py`.

```bash
python3 skills/nemoizer/scripts/nemoize.py .
python3 skills/nemoizer/scripts/nemoize.py --ignore vendor .
python3 skills/nemoizer/scripts/nemoize.py --ignores .
```

A finding prints `path:line: word -> use` and exits 1. Vendored and generated
trees are skipped, and `--ignore` adds a directory or file.

A line that carries `nemoizer: ignore` is skipped. A marker in the first three
lines skips the whole file. `--ignores` prints every marker as `path:line: text`,
so a suppression never escapes review.

The tool stays advisory until the rotation lands, so `check.py` does not run it.
