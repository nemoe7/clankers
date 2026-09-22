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

The `--update` option regenerates the instruction-budget table from `EXPECTED_BUDGETS` before the check, including added and retired skill entries. Run `python3 maintenance/check_measurements.py` for its assert-based regression check.

The checker stays maintenance tooling. Preview reporting uses `markdown-it-py` at runtime, and steering uses only the standard library. The reporting skill documents its approved venv setup and adds no dependency to the consuming application.

## Minified assets and scripts

The preview skill ships minified JavaScript, CSS, HTML and Python. The readable baselines stay in `skills/refs/arena-preview-steering/`. The two distributed copies carry the build, including all three files in `scripts/`. Edit the refs sources, not the generated copies. Markdown compression stays outside this build. Compact Python has less useful traceback line numbers.

```bash
npm ci
python3 -m pip install python-minifier==3.3.0
python3 maintenance/minify.py            # report drift, write nothing
python3 maintenance/minify.py --update   # write both distributed copies
```

`package.json` pins `terser` for JavaScript and CommonJS, `clean-css-cli` for CSS, and `html-minifier-terser` for HTML. The build and CI pin `python-minifier==3.3.0` for Python. It is a build dependency, not a server one. CI uses Python 3.11 to keep the output stable. The script refuses JavaScript that Node cannot parse, unbalanced CSS braces, and markup that loses an id or a visible word. Python output must compile, keep the same parsed tree, and meet the Python 3.10 syntax limit. Names, annotations, docstrings, assertions and shebangs stay. Ordinary comments do not.

`check.py` gates each live asset and script through the README budget table. The recorded size is the budget, so any growth fails until you update the table on purpose. Run `minify.py` after each change to a refs asset or script, because the budget cannot detect a stale copy. Run `python3 maintenance/check_minify.py` for copy equality, drift, Python tree equality, the syntax limit and the generated runtime. That runtime check uses readable assets for exact page assertions, then checks page assembly with the shipped assets. Ruff checks the readable Python refs, not the generated copies.

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

Use the raw media type, not a plain contents call. The encoding is 1,681,126 bytes, and the contents API stops returning base64 content above 1 MB. The raw accept header bypasses that limit. Where `gh` carries no credentials, `raw.githubusercontent.com` serves the same path. Some sandboxes block raw hosts and allow `api.github.com`, which is why this file records the API form.

A sandbox restore deletes `.tiktoken-cache/` with the rest of the ignored tree, so re-seed the cache when you rebuild a venv. Verified on 2026-09-21 against `arena/01a0be68-clankers`: the seeded cache made `maintenance/check.py` pass. Before that, it did not run for a whole session.
