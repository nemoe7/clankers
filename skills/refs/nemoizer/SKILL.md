---
name: nemoizer
description: >
  Find AI-flavored synonyms and replace them with the plain word, using one
  rotation table and a bundled linter that reads every text file, comments and
  prose included. Use when naming a variable, field, parameter, key, or prose
  term, when a draft sounds machine-written, or when asked to run or extend the
  rotation table.
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

Each row matches the stem, so `picked`, `picking`, and `picks` all rotate to <!-- nemoizer: ignore -->
`select`. Add a row here and a pattern in `scripts/nemoize.py`: one table, one
source. <!-- nemoizer: ignore -->

A word that shares the stem but stands on its own, like `pickle`, carries a <!-- nemoizer: ignore -->
marker instead of a narrower pattern. <!-- nemoizer: ignore -->

## Linter

Run it from the repository root and pass the paths to read:

```bash
python3 skills/nemoizer/scripts/nemoize.py .
python3 skills/nemoizer/scripts/nemoize.py --ignore vendor --ignore third_party .
```

- Every text file is read, including comments and Markdown prose.
- Each finding prints `path:line: word -> use`, and the exit code is 1.
- Vendored and generated trees are skipped, and `--ignore` adds a directory or
  file.
- `check.py` runs the linter with the ignore list, so a new avoided word fails the
  gate.

## Writing the rotation

`--format` rewrites the tree in place and prints every changed line twice, as it
was and as it becomes:

```bash
python3 skills/nemoizer/scripts/nemoize.py --format .
```

Each change prints as a pair: `path:line: -` and the old line, then `path:line: +`
and the new one. A row replaces its word as plain text, in lower, capital and upper
case. One stem word takes its own plain word: `picker` becomes `selector`, and <!-- nemoizer: ignore -->
`pickers` becomes `selectors`. <!-- nemoizer: ignore -->

- Ignore markers and the table's own rows are never rewritten.
- Pass a license file or a generated tree to `--ignore`; the tool reads every other
  text file.

## Ignore markers

A line that carries `nemoizer: ignore` is skipped. A marker in the first three
lines skips the whole file. The marker takes any comment syntax, because the
scan reads text, not syntax:

```python
value = "kind"  # nemoizer: ignore
```

```markdown
<!-- nemoizer: ignore -->
```

Every marker is reviewable, and none is silent:

```bash
python3 skills/nemoizer/scripts/nemoize.py --ignores .
```

That prints `path:line: text` for each marker, so a suppression never escapes
review. Delete a marker when the line no longer needs it.

## Adding a row

1. Add the row to the table above.
2. Add one pattern, its name, and its plain word to `ROTATIONS` in
   `scripts/nemoize.py`; add a stem word that takes its own plain word to
   `EXCEPTIONS`.
3. Run `python3 -m pytest skills/nemoizer/scripts/test_nemoize.py`.
