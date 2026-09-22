# Maintenance

Repository checks live in `maintenance/`.

## Check

```bash
python3 maintenance/check.py
```

The checker reports every problem it finds in:

- Skill discovery metadata, required `SKILL.md` files, and the Agent Skills naming and frontmatter limits.
- Workflow listing and frontmatter descriptions.
- Internal links, README skill and workflow coverage, and recorded measurements.
- Both ChatGPT custom-instruction character limits.
- A license declaration on every skill that records `metadata.upstream`, and the `LICENSE.txt` file that the declaration points at.
- The markdownlint scope, recomputed from `.markdownlint-cli2.jsonc` and compared with the counts this repository documents.
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

`--update` rebuilds the budget table from `EXPECTED_BUDGETS` before checking, including added and retired skills. Test it with `python3 maintenance/check_measurements.py`.

The checker is maintenance tooling. Reporting uses `markdown-it-py` at runtime, steering only the standard library. The reporting skill documents approved venv setup without consuming-application dependencies.

## Minified assets and scripts

The preview ships minified JavaScript, CSS, HTML and Python in two distributed copies, including all three `scripts/` files. Edit readable `skills/refs/arena-preview-steering/` sources, never generated copies. Markdown compression is separate. Compact Python gives less useful traceback line numbers.

```bash
npm ci
python3 -m pip install python-minifier==3.3.0
python3 maintenance/minify.py            # report drift, write nothing
python3 maintenance/minify.py --update   # write both distributed copies
```

`package.json` pins `terser` for JavaScript/CommonJS, `clean-css-cli` for CSS, and `html-minifier-terser` for HTML. Build and CI pin `python-minifier==3.3.0`, not a server dependency. CI uses Python 3.11 for stable output. The script rejects unparseable JavaScript, unbalanced CSS braces, and HTML missing ids or visible words. Python must compile with the same parsed tree and Python 3.10 syntax. Names, annotations, docstrings, assertions and shebangs remain, not ordinary comments.

`check.py` rejects asset/script growth beyond recorded README budgets until an explicit table update. After each refs asset/script edit, run `minify.py`: budgets cannot detect stale copies. `python3 maintenance/check_minify.py` checks copy equality, drift, Python tree equality, syntax limits and generated runtime. It uses readable assets for exact page assertions, then shipped assets for page assembly. Ruff checks readable Python refs, not generated copies.

## Offline token measurement

`tiktoken` downloads `cl100k_base` on first use. If its host is unreachable, seed from a byte-identical mirror. Its hash check rejects bad copies.

```bash
BLOB=https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
export TIKTOKEN_CACHE_DIR="$PWD/.tiktoken-cache"
mkdir -p "$TIKTOKEN_CACHE_DIR"
gh api -H "Accept: application/vnd.github.raw" \
  repos/niieani/gpt-tokenizer/contents/data/cl100k_base.tiktoken \
  > "$TIKTOKEN_CACHE_DIR/$(echo -n "$BLOB" | sha1sum | head -c 40)"
```

Then run with the variable set, for example `TIKTOKEN_CACHE_DIR="$PWD/.tiktoken-cache" python3 maintenance/check.py`.

Use raw media type: this 1,681,126-byte encoding exceeds the contents API’s 1 MB base64 limit. Without `gh` credentials, use the same path at `raw.githubusercontent.com`. Some sandboxes block raw hosts but allow `api.github.com`, hence the API command here.

Restores delete ignored `.tiktoken-cache/`, so seed it again with venv recovery. Verified on 2026-09-21, `arena/01a0be68-clankers`: seeding made `maintenance/check.py` pass after a session without the gate.
