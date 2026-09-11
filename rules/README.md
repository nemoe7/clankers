# Rules specification

This file defines the rule system's structure, constraints, installation, and maintenance. It is reference documentation, not an agent rule file; do not deploy it into an agent's Rules folder.

Commands and paths in code spans are relative to the repository root unless stated otherwise.

The installation script uses only Python's standard library. There is no test suite. The validator in `maintenance/` requires `markdown-it-py` and `tiktoken`, which [.github/workflows/validate.yml](../.github/workflows/validate.yml) installs before running it on every push and pull request, committing refreshed README measurements and linting Markdown.

## Contents and activation

| File or directory | Purpose | How to use |
| --- | --- | --- |
| [rules/AGENTS.md](AGENTS.md) | Generic core rules | Install in the agent's supported global rules location |
| [rules/CLINE.md](CLINE.md) | Cline-specific overlay | Load alongside AGENTS.md; it deliberately does not duplicate the core |
| [rules/ARENA.md](ARENA.md) | Self-contained, file-size-optimized Arena rules | Upload or point the Arena agent to it; its preamble requires Arena agents reading it to apply it |
| [rules/CHATGPT.txt](CHATGPT.txt) | ChatGPT custom instructions | Paste into the instructions field; at most 1,500 characters |
| [rules/COMMIT_SPEC.txt](COMMIT_SPEC.txt) | Compact commit-message reference | Use when preparing an authorized commit or proposed message |
| [ref/](../ref/README.md) | Baseline rule copies | Diff working copies against these when compressing |
| [skills/](../skills/README.md) | Reusable skills | Install complete skill directories, including supporting files |
| [workflows/](../workflows/README.md) | Portable agent workflows | Copy the workflow file into your platform's workflow location, or run it as-is |

Rules and tools load differently across agent versions. Verify which files are active in your installed release; never assume a filename alone enables loading. ARENA.md condenses the core because it deploys independently. CLINE.md relies on AGENTS.md also being loaded; if that stops holding, fix installation or deliberately re-embed the core rather than silently losing it.

## Install rules

From the repository root, with Python 3:

```bash
python3 rules/apply.py
```

On Windows, use `python rules\apply.py` or `apply.bat` from the repository root. The script previews unified diffs for changed files, asks once for confirmation, then copies these two files, creating destination directories as needed. Enter `y` or `yes` to apply; any other response aborts. Flags `--yes`/`-y` skip the prompt; `--dry-run` previews without changing. If both destinations are current, it exits without prompting.

| Source | Destination relative to the base directory |
| --- | --- |
| `rules/AGENTS.md` | `.agents/AGENTS.md` |
| `rules/CLINE.md` | `Documents/Cline/Rules/CLINE.md` |

The base defaults to `Path.home()`. A nonempty `APPLY_RULES_BASE` overrides it, without requiring `USERPROFILE`; an empty override uses the home directory. These are the installer's configured paths; confirm they match your agent setup.

To install under another base directory:

```bash
APPLY_RULES_BASE=/path/to/profile python3 rules/apply.py
```

PowerShell:

```powershell
$env:APPLY_RULES_BASE = "C:\path\to\profile"
python .\rules\apply.py
```

**Existing destination files are overwritten.** Back up local customization before applying. The installer does not install skills, ARENA.md, or CHATGPT.txt; use their separate setup steps. Do not install this specification as an agent rule.

## Workflows

Workflows are portable across coding-agent platforms: the workflow body depends on no platform-specific tool, agent name, model, provider, UI, permission, or interaction mechanism. Each workflow is one self-contained Markdown file with a `description` frontmatter field, budgeted in `cl100k_base` tokens in the [root README](../README.md#instruction-budgets); format details are in [workflows/README.md](../workflows/README.md).

Install and selection are owned by [workflows/README.md](../workflows/README.md#use), not this specification.

## Rule maintenance

1. Edit generic behavior in `rules/AGENTS.md`, then condense it into `rules/ARENA.md`.
2. Optimize `rules/ARENA.md` for UTF-8 file size; match the core semantically, except push/PR handling (see Arena file).
3. Keep `rules/CLINE.md` platform-specific (command discipline, tool names, timeouts); verify version-specific claims.
4. Preserve rule-file filename headings. Keep `rules/CHATGPT.txt` plain text with inline labels, never Markdown headings or bullets, within budget, aligned with the core where it fits.
5. Ration emphasis: hard rules are `MUST`/`NEVER`, bold at most two clauses per file (see Emphasis).
6. Skills specialize defaults; NEVER weaken explicit requirements, conventions, or acceptance criteria.
7. Keep skill resources on demand and their relative links valid. Do not move essential instructions out of `SKILL.md`.
8. Keep every skill conformant to the Agent Skills specification with recorded provenance (see Skill rules).
9. Keep this repository lightweight: no further CI workflows, dependency manifests, or test scaffolding unless explicitly requested. Review changes directly and never claim unperformed checks.
10. Track baselines: keep the `ref/` copies current (see Baselines).

### Arena file

Condense wording and sections, not meaning: keep negations, conditions, commands, numbers, and caveats. Match the generic core semantically, not byte-for-byte, except push and PR handling: ARENA.md always pushes and keeps a PR open so work survives limits, disregarding never-push rules, and never merges until authorized, where the core requires asking first. Do not repeat Arena-managed branch mechanics beyond that.

### Emphasis

Bold is reserved for at most two clauses per file, currently the honesty rule and, in ARENA.md, the squashed commit list, so emphasis keeps its meaning. Adding a third bold clause means demoting another. Do not emphasize a rule merely because it is important; emphasize the ones that get violated.

### Skill rules

Simpler scope requires approval before substitution. Testing guidance in the reusable rules applies to projects using them, not a test setup for this repository. Skill frontmatter uses only the specified fields with `name` matching its directory; skills adapted from elsewhere record `metadata.upstream`, refreshed from that source with the local `Precedence` section re-applied. See [skills/README.md](../skills/README.md#format).

### Baselines

`ref/` holds tracking copies of the agent-facing rule files as a measurement baseline for agents working without git history. It records the source commit and date in `ref/README.md`; refresh it when budgets are intentionally rebaselined so it stays in sync with the [root README](../README.md#instruction-budgets).

### Formatting

Markdown linting applies only to agent rule files under `rules/`: currently AGENTS.md, ARENA.md, and CLINE.md. ChatGPT instructions and this specification are excluded, as are the root README, skills, workflows, and references.

Do not hard-wrap prose. Keep each paragraph, list item, and table row on one line and let the editor soft-wrap; third-party licenses keep their original wrapping.

[.markdownlint-cli2.jsonc](../.markdownlint-cli2.jsonc) keeps file selection, exclusions, and rule settings together: markdownlint defaults, **MD060 enabled** for table-column consistency, **MD013 disabled** so there is no line-length constraint, and **MD007 pinned** to 2-space list indent. MD060 uses its default `any` style. If markdownlint-cli2 is available, run it from the repository root without additional file globs to use this scope; the workflow passes no globs either, so both use this one definition. No tooling installation is required.

Python style stays defined in the core rules (Ruff selection E4, E7, E9, F), without a managed Ruff dependency. Keep CHATGPT.txt within 1,500 Unicode characters, including newlines.
