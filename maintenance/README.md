# Maintenance

Dependency-free repository checks live in `maintenance/`.

## Validate

```bash
python3 maintenance/validate.py
```

The validator checks skill discovery metadata, required `SKILL.md` files, Agent Skills naming/frontmatter limits, referenced local files, README skill coverage, recorded byte/character measurements, and the ChatGPT character limit.

## Update README measurements

```bash
python3 maintenance/update_readme.py
```

Token measurements require `tiktoken` because the repository records `cl100k_base` counts. Other measurements use the Python standard library. Run the updater after changing any measured rule or skill entry file, then run the validator.

The scripts are maintenance tooling, not runtime dependencies and are not installed into agent environments.
