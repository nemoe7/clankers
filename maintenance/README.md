# Maintenance

Repository maintenance procedures and validation tools live here.

Repository checks live in `maintenance/`.

## Rule maintenance

1. Amend the appropriate file in `rules/refs/` first. Then mirror the amendment into the live file and compress only the new or affected line.
2. Optimize `rules/ARENA.md` for UTF-8 file size. Match the core in meaning, except for push and PR handling (see Arena file).
3. Keep `rules/CLINE.md` and `rules/KILO.md` platform-specific: command discipline, tool names, timeouts. Check every version-specific claim. The Kilo mode overrides pair `rules/refs/kilo/` with the live `rules/kilo/`. The maintainer compresses and budgets each live file, and both sides stay out of the lint because their required shape fails MD001 and MD041.
4. Keep the filename headings of the rule files. Keep `rules/CHATGPT-CUSTOM.txt` and `rules/CHATGPT-MORE.txt`, named for the fields they go into. ChatGPT's Personalization gives `Custom Instructions` and `More about you`, each with a 1,500 Unicode character ceiling. Keep both files plain text with inline labels, never Markdown headings or bullets, within budget, and aligned with the core where it fits. The split places work rules in `Custom Instructions`, and it places response rules plus overflow work rules in `More about you`. ChatGPT keeps nickname and occupation as structured profile fields rather than rule space, and this repository does not version them.
5. Ration the emphasis: a hard rule uses `MUST` or `NEVER`, and a file bolds two clauses at most (see Emphasis).
6. A skill specializes a default. It NEVER weakens an explicit requirement, a convention, or an acceptance criterion.
7. Keep the skill resources on demand, and keep their relative links valid. Do not move essential instructions out of `SKILL.md`.
8. Keep every skill conformant to the Agent Skills specification, with recorded provenance (see Skill rules).
9. Keep this repository light: no further CI workflow, dependency manifest or test scaffolding unless the owner asks for one. The pinned minifier manifest the preview build uses is the one exception, on the owner's approved answers. Review a change directly, and never claim a check that did not run.
10. Keep full wording in `rules/refs/` and compressed wording in the live files. On a removal, attempt one squash and keep the lower budget. Full wording stays in refs, and the compressed form stays in `rules/` (see Baselines).

### Arena file

Arena uses the `arena-preview-steering` skill for one Notes / Reports preview. Keep reports and session state ignored and uncommitted. The steering migration reference records former ntfy and local-report-commit workflows, neither an automatic fallback. Preview permanence is not guaranteed.

Compress wording and sections, not meaning. Keep every negation, condition, command, number, and caveat. Match the generic core in meaning, not byte for byte, except for push, PR, and merge authorization. ARENA.md always pushes and keeps a PR open so work survives a limit. Core forbids pushes and PRs unless asked but has no merge clause. Arena never merges without owner authorization, then uses rebase only: rebase onto the target, then merge, so no merge commit lands. Do not repeat Arena-managed branch mechanics beyond that.

The duplication of the core is deliberate. In Arena, no platform loads ARENA.md or AGENTS.md on its own. So the file stands alone instead of overlaying the core, and it takes effect only after the agent has it in context. Exploration does not gate activation. Activation is a human step, and delivery is not activation. `.github/workflows/distribute.yml` only puts the file in each target repository, and `rules/apply.py` deliberately does not install it. Put this exact line in the first message of the session. Put it in the custom-instructions field of the platform: `Read and apply AGENTS.md and ARENA.md at the repository root before your first edit. confirm in one line.` The preamble of the file then requires an Arena agent that reads it to apply it. It also requires an agent that did not receive it in context to open it before the first edit.

After each amendment, run `cp rules/ARENA.md ARENA.md`. `.github/workflows/distribute.yml` pushes the root copy to target repositories. `maintenance/check.py` rejects missing or different root copies.

### Emphasis

A deployed rule file keeps two bold clauses at most, so the emphasis keeps its meaning. The bold clauses are the honesty rule in `AGENTS.md`. In `ARENA.md` they are the planned final commit list and the `-f body=@path` ban. In `CLINE.md` they are `STOP` and the self-assignment ban. In the root `AGENTS.md` they are the two markdownlint settings. The cap covers the deployed rule files and their refs baselines. It does not cover this specification, the skills, or the workflows. `MUST` and `NEVER` stay on the irreversible, the dangerous, and the honesty rules. Every other rule reads positively, because a negated rule that guards nothing costs emphasis (see [refs/GUIDELINES.md](../system-prompts/refs/GUIDELINES.md) section 4.7). A third bold clause in a rule file means one other clause becomes plain. Do not emphasize a rule merely because it is important. Emphasize the rules that get violated.

### Persona rules

Four deliberate voice rules describe no observable behavior: `Concise, direct, practical, accurate`, `Write clear, readable code`, `Never lazy about understanding`, and `Criticize all`. [refs/GUIDELINES.md](../system-prompts/refs/GUIDELINES.md) 2.3 says not to fight persona on style, and 4.8 requires marking deliberate deviations. These stay at about 60 `tok` in core and 400 `B` in ARENA.md. Audit them as marked exceptions, not untestable-rule violations.

### Skill rules

A simpler scope needs approval before a substitution. The testing guidance in the reusable rules applies to the projects that use them, not to a test setup for this repository. The frontmatter of a skill uses only the specified fields, with `name` matching its directory. A skill that comes from another source records `metadata.upstream`, and the maintainer refreshes it from that source with the local `Precedence` section applied again. See [skills/README.md](../skills/README.md#format).

### Baselines

`rules/refs/` keeps uncompressed baselines for agents without git history. Amend here first in complete sentences, preserving every negation, condition, command, number, threshold, filename and caveat. Compress only new or affected lines into live files. On removal, attempt one squash and keep the lower budget. Verbatim baselines would exceed live budgets. Refs preserve originals, identical to live where no compression applied. The adjacent `GUIDELINES.md` is the writing/audit reference, not a baseline, with no live counterpart.

### Formatting

Markdown linting applies to the agent rule files under `rules/`, and that includes `rules/refs/`. The linted files are `AGENTS.md`, `ARENA.md`, `CLINE.md`, `KILO.md`, and the six Markdown files in `rules/refs/`, plus `rules/wenyan/README.md` — 11 files in all. The excluded files are the ChatGPT text files and this specification. The other exclusions are root-level Markdown, the skills, and the `rules/refs/kilo/` and `rules/kilo/` mode overrides. The required blank first line and `###` heading of a mode override fail MD001 and MD041.

Soft-wrap prose: one line per paragraph, list item and table row. Keep third-party license wrapping.

Rule files keep one rule per line, per [refs/GUIDELINES.md](../system-prompts/refs/GUIDELINES.md) section 4.1. The Markdown rule files use bullets. The ChatGPT files use one plain line per rule, and item 4 keeps them free of headings and bullets. A line can carry the parameters, the enumeration, or the exact command of one rule. It does not carry two rules. The core and `ARENA.md` open with a `Use` section. The overlays `CLINE.md` and `KILO.md` do not. The Markdown rule files close with a `When in doubt` section. `KILO.md` is the exception, because the core settles the doubts it would restate. The core and `ARENA.md` also carry a constitution, and `CLINE.md` and `KILO.md` inherit the core's instead of copying it. The `rules/refs/kilo/` and `rules/kilo/` mode overrides keep a different shape on purpose. They open with a blank line, then `### Native <mode> Agent Overrides`, then the conflict clause. Kilo wraps them as a mode reminder rather than loading them as a full rules file. The ChatGPT files and `COMMIT-SPEC.txt` keep their set formats instead, per item 4 and their single-purpose scope.

[.markdownlint-cli2.jsonc](../.markdownlint-cli2.jsonc) keeps the file selection, the exclusions, and the rule settings together. It keeps the markdownlint defaults, enables **MD060** for table-column consistency, and disables **MD013** so there is no line-length constraint. MD060 uses its default `any` style, and MD007 uses its default two-space list indent, so neither needs a pin. If markdownlint-cli2 is available, run it from the repository root with no additional file globs to use this scope. The workflow passes no globs either, so both use this one definition. `maintenance/check.py` recomputes the scope from this config and fails when it drifts from the counts recorded here and in the root guide. No tooling installation is necessary.

Core defines Python style (Ruff E4, E7, E9, F), with no managed Ruff dependency. `maintenance/check.py` checks both ChatGPT fields against 1,500 Unicode characters each, including newlines.

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

## Prose lint

```bash
python3 maintenance/lint_prose.py
```

The prose linter runs the ste-lint rules over the covered scope: `docs/`, every `README.md`, and `CHANGELOG.md`. It also runs them on the Python comments in `maintenance/` and `rules/`. `CHANGELOG.md` bullets cap at 3 sentences. `skills/` stays out of the target set.

## Update README measurements

```bash
python3 maintenance/check.py --update
```

`check.py` needs two third-party packages. `markdown-it-py` parses the README budget table, and `tiktoken` measures `cl100k_base` tokens. Everything else is the Python standard library.

```bash
python3 -m pip install markdown-it-py tiktoken
```

`--update` rebuilds the budget table from `EXPECTED_BUDGETS` before checking, including added and retired skills. Test it with `python3 maintenance/check_measurements.py`.

The checker is maintenance tooling.

## Minified assets and scripts

The preview ships minified JavaScript, CSS, HTML and Python in two distributed copies, including all three `scripts/` files. Edit readable `skills/refs/arena-preview-steering/` sources, never generated copies. Markdown compression is separate. A dispatch workflow writes the `.agents/skills/arena-preview-steering/` copy in each target repository. `.github/workflows/distribute.yml` carries it, so markdown drift there ends at the next dispatch. Compact Python gives less useful traceback line numbers.

```bash
npm ci
python3 -m pip install python-minifier==3.3.0
python3 maintenance/minify.py            # report drift, write nothing
python3 maintenance/minify.py --update   # write both distributed copies
```

`package.json` pins `terser` for JavaScript/CommonJS, `clean-css` for CSS, and `html-minifier-terser` for HTML. Build and CI pin `python-minifier==3.3.0`, not a server dependency. CI uses Python 3.11 for stable output. The script rejects unparseable JavaScript, unbalanced CSS braces, and HTML missing ids or visible words. Python must compile with the same parsed tree and Python 3.10 syntax. Names, annotations, assertions and shebangs remain. Ordinary comments and docstrings go, so a shipped script keeps no prose. Help text that a script prints lives in a string constant, not in a docstring.

`check.py` rejects asset/script growth beyond recorded README budgets until an explicit table update. After each refs asset/script edit, run `minify.py`: budgets cannot detect stale copies. `python3 maintenance/check_minify.py` checks copy equality, drift, Python tree equality, syntax limits and generated runtime. It uses readable assets for exact page assertions, then shipped assets for page assembly. Ruff checks readable Python refs, not generated copies.

## Plugin collection

`gpt-plugins/` is one Agent Plugins collection. It holds `plugin.json` and the shipped skills under `skills/`. The readable skill sources live under `refs/skills/`, and the shipped copies use manually compressed wording with the same meaning and headings. Review every clause against refs. Structural checks do not prove semantic parity.

```bash
python3 -m pip install jsonschema
python3 maintenance/check_gpt_plugins.py            # report drift, write nothing
```

The checker checks `plugin.json` against the canonical schema at `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`, which it downloads on every run. Pass `--schema <path>` to check against a local copy offline. It also checks the plugin name, shipped skill names, the Agent Skills frontmatter limits, and the collection tree. `gpt-plugins/README.md` documents the collection and never ships.

`--archive <zip>` compares a packaged archive with the collection. The archive must carry `plugin.json` and `skills/` only, with byte-identical content, so `refs/` never ships. On pull requests, `.github/workflows/artifacts.yml` runs the collection check and requires a higher `plugin.json` version when shipped files change. On `main`, it packages and publishes `gpt-plugins.zip`.

The four shipped `SKILL.md` files join the budget table in the root `README.md`. `plugin.json` does not, because it is metadata and not instruction text.

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
