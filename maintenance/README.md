# Maintenance

Repository checks live in `maintenance/`.

## Check

```bash
python3 maintenance/check.py
```

The checker reads the repository and reports every problem it finds. It covers:

- Skill discovery metadata, required `SKILL.md` files, and the Agent Skills naming and frontmatter limits.
- Workflow listing and frontmatter descriptions.
- Internal links, README skill and workflow coverage, and recorded measurements.
- Both ChatGPT custom-instruction character limits.
- A license declaration on every skill that records `metadata.upstream`, and the `LICENSE.txt` file that the declaration points at.
- The markdownlint scope. The checker recomputes that scope from `.markdownlint-cli2.jsonc` and compares it with the counts this repository documents.
- Refs/live rule parity: identical section headings in the same order, and each live section holding no more rule lines than its refs baseline.
- The byte identity of the root `ARENA.md` copy and `rules/ARENA.md`.

## Update README measurements

```bash
python3 maintenance/check.py --update
```

`check.py` needs two third-party packages. `markdown-it-py` parses the README budget table, and `tiktoken` measures `cl100k_base` tokens. Everything else is the Python standard library.

```bash
python3 -m pip install markdown-it-py tiktoken
```

The `--update` option regenerates the instruction-budget table from `EXPECTED_BUDGETS` before the check, including added and retired skill entries. Run `python3 maintenance/check_measurements.py` for its assert-based regression check.

The checker stays maintenance tooling. Separately, preview reporting uses `markdown-it-py` at runtime, and steering itself uses only the Python standard library. The reporting skill documents its approved venv setup and adds no dependency to the consuming application.

## Offline token measurement

`tiktoken` downloads its `cl100k_base` encoding on first use. Where that host is unreachable, seed the cache from any byte-identical mirror. `tiktoken` verifies the hash itself, so a bad mirror fails loudly rather than silently.

```bash
BLOB=https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
export TIKTOKEN_CACHE_DIR="$PWD/.tiktoken-cache"
mkdir -p "$TIKTOKEN_CACHE_DIR"
gh api -H "Accept: application/vnd.github.raw" \
  repos/niieani/gpt-tokenizer/contents/data/cl100k_base.tiktoken \
  > "$TIKTOKEN_CACHE_DIR/$(echo -n "$BLOB" | sha1sum | head -c 40)"
```

Then run with the variable set, for example `TIKTOKEN_CACHE_DIR="$PWD/.tiktoken-cache" python3 maintenance/check.py`.

Use the raw media type, not a plain contents call. The encoding is 1,681,126 bytes, and the contents API stops returning base64 content above 1 MB. The raw accept header bypasses that limit. Where `gh` is not authenticated, `raw.githubusercontent.com` serves the same path. Some sandboxes block raw hosts and allow `api.github.com`, which is why this file writes down the API form.

A sandbox restore deletes `.tiktoken-cache/` with the rest of the ignored tree. Re-seed the cache when you rebuild a venv. Verified on 2026-09-21 against `arena/01a0be68-clankers`: the seeded cache made `maintenance/check.py` pass. Before that, it did not run for a whole session.
