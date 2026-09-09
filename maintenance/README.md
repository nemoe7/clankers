# Maintenance

Repository checks live in `maintenance/`.

## Validate

```bash
python3 maintenance/check.py
```

The validator checks skill discovery metadata, required `SKILL.md` files, Agent Skills naming/frontmatter limits, internal links, README skill coverage, recorded measurements, and the ChatGPT character limit.

## Update README measurements

```bash
python3 maintenance/check.py --update
```

`check.py` uses `tiktoken` for `cl100k_base` token measurements and otherwise uses the Python standard library. The `--update` option refreshes the recorded README measurements before validation.

The script is maintenance tooling, not a runtime dependency, and is not installed into agent environments.
