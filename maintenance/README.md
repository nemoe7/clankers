# Maintenance

Repository checks live in `maintenance/`.

## Validate

```bash
python3 maintenance/check.py
```

The validator checks skill discovery metadata, required `SKILL.md` files, Agent Skills naming/frontmatter limits, workflow listing and frontmatter descriptions, internal links, README skill and workflow coverage, recorded measurements, both ChatGPT custom-instruction character limits, a license declaration on every skill that records `metadata.upstream` and the `LICENSE.txt` those declarations point at, the markdownlint scope recomputed from `.markdownlint-cli2.jsonc` against the counts documented in this repository, refs/live rule parity: identical section headings in the same order, with each live section holding no more rule lines than its refs baseline, and the root `ARENA.md` copy's byte identity with `rules/ARENA.md`.

## Update README measurements

```bash
python3 maintenance/check.py --update
```

`check.py` requires two third-party packages: `markdown-it-py` to parse the README budget table and `tiktoken` for `cl100k_base` token measurements. Everything else is the Python standard library.

```bash
python3 -m pip install markdown-it-py tiktoken
```

The `--update` option regenerates the instruction-budget table from `EXPECTED_BUDGETS` before validation, including added and retired skill entries. Run `python3 maintenance/check_measurements.py` for its assert-based regression check.

The validator remains maintenance tooling. Separately, preview reporting uses `markdown-it-py` at runtime; steering itself uses only the Python standard library. The reporting skill documents its approved venv setup without adding dependencies to the consuming application.

## Offline token measurement

`tiktoken` downloads its `cl100k_base` encoding on first use. Where that host is unreachable, seed the cache from any byte-identical mirror (`tiktoken` verifies the hash itself, so a bad mirror fails loudly rather than silently):

```bash
BLOB=https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
export TIKTOKEN_CACHE_DIR="$PWD/.tiktoken-cache"
mkdir -p "$TIKTOKEN_CACHE_DIR"
gh api -H "Accept: application/vnd.github.raw" \
  repos/niieani/gpt-tokenizer/contents/data/cl100k_base.tiktoken \
  > "$TIKTOKEN_CACHE_DIR/$(echo -n "$BLOB" | sha1sum | head -c 40)"
```

Then run with the variable set, e.g. `TIKTOKEN_CACHE_DIR="$PWD/.tiktoken-cache" python3 maintenance/check.py`.

Use the raw media type, not a plain contents call: the encoding is 1,681,126 bytes, over the 1 MB limit at which the contents API stops returning base64 content. The raw accept header bypasses that. Where `gh` is not authenticated, `raw.githubusercontent.com` serves the same path, but raw hosts are blocked in some sandboxes while `api.github.com` is not, which is why the API form is the one written down here.

`.tiktoken-cache/` is gitignored and is deleted by a sandbox restore along with the rest of the ignored tree, so re-seeding is part of rebuilding a venv. Verified on 2026-09-21 against `arena/01a0be68-clankers`: the seeded cache made `maintenance/check.py` pass after it had been unrunnable for a whole session.
