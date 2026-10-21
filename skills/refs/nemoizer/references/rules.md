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
