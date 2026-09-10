# Maintenance

Repository checks live in `maintenance/`.

## Validate

```bash
python3 maintenance/check.py
```

The validator checks skill discovery metadata, required `SKILL.md` files, Agent Skills naming/frontmatter limits, workflow listing and frontmatter descriptions, internal links, README skill and workflow coverage, recorded measurements, and the ChatGPT character limit.

## Update README measurements

```bash
python3 maintenance/check.py --update
```

`check.py` requires two third-party packages: `markdown-it-py` to parse the README budget table and `tiktoken` for `cl100k_base` token measurements. Everything else is the Python standard library.

```bash
python3 -m pip install markdown-it-py tiktoken
```

The `--update` option refreshes the recorded README measurements before validation.

The script is maintenance tooling, not a runtime dependency, and is not installed into agent environments.
