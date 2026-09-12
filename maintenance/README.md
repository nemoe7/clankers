# Maintenance

Repository checks live in `maintenance/`.

## Validate

```bash
python3 maintenance/check.py
```

The validator checks skill discovery metadata, required `SKILL.md` files, Agent Skills naming/frontmatter limits, workflow listing and frontmatter descriptions, internal links, README skill and workflow coverage, recorded measurements, the ChatGPT character limit, byte-identity between the distributed root `ARENA.md` and `rules/ARENA.md`, the markdownlint scope recomputed from `.markdownlint-cli2.jsonc` against the counts documented in this repository, and refs/live rule parity: identical section headings in the same order, with each live section holding no more rule lines than its refs baseline.

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

## Offline token measurement

`tiktoken` downloads its `cl100k_base` encoding on first use. Where that host is unreachable, seed the cache from any byte-identical mirror (`tiktoken` verifies the hash itself):

```bash
BLOB=https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
mkdir -p "$TIKTOKEN_CACHE_DIR"
curl -sL -o "$TIKTOKEN_CACHE_DIR/$(echo -n "$BLOB" | sha1sum | head -c 40)" <mirror-url>
```

Then run with `TIKTOKEN_CACHE_DIR` set, e.g. `TIKTOKEN_CACHE_DIR=/path/to/cache python3 maintenance/check.py`. A known mirror is `niieani/gpt-tokenizer` `data/cl100k_base.tiktoken`, fetchable raw or via the GitHub contents API where raw hosts are blocked.
