# Rules specification

This file defines the rule system's structure, constraints, installation, and maintenance. It is reference documentation, not an agent rule file; do not deploy it into an agent's Rules folder.

Commands and paths in code spans are relative to the repository root unless stated otherwise.

The installation script uses only Python's standard library. There is no test suite. The validator in `maintenance/` requires `markdown-it-py` and `tiktoken`, which [.github/workflows/validate.yml](../.github/workflows/validate.yml) installs before running it on every push and pull request, committing refreshed README measurements and linting Markdown.

## Contents and activation

| File or directory | Purpose | How to use |
| --- | --- | --- |
| [rules/AGENTS.md](AGENTS.md) | Generic core rules | Install in the agent's supported global rules location |
| [rules/CLINE.md](CLINE.md) | Cline-specific overlay | Load alongside AGENTS.md; it deliberately does not duplicate the core |
| [rules/ARENA.md](ARENA.md) | Self-contained, file-size-optimized Arena rules | Upload it, or open every session with the bootstrap line in [Arena file](#arena-file); no platform loads it on its own |
| [rules/CHATGPT-CUSTOM.txt](CHATGPT-CUSTOM.txt) | ChatGPT Personalization: `Custom Instructions` | Paste into Custom Instructions, hinted "Additional behavior, style, and tone preferences"; at most 1,500 characters |
| [rules/CHATGPT-MORE.txt](CHATGPT-MORE.txt) | ChatGPT Personalization: `More about you` | Paste into More about you, hinted "Interests, values, or preferences to keep in mind"; at most 1,500 characters |
| [rules/COMMIT-SPEC.txt](COMMIT-SPEC.txt) | Compact commit-message reference | Use when preparing an authorized commit or proposed message |
| [rules/refs/](refs/README.md) | Uncompressed rule originals, plus the AGENTS.md writing guidelines | Amend here first, mirror the amendment into the live file in compressed form, then squash it |
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

**Existing destination files are overwritten.** Back up local customization before applying. The installer does not install skills, ARENA.md, or the ChatGPT files; use their separate setup steps. Do not install this specification as an agent rule.

## Workflows

Workflows are portable across coding-agent platforms: the workflow body depends on no platform-specific tool, agent name, model, provider, UI, permission, or interaction mechanism. Each workflow is one self-contained Markdown file with a `description` frontmatter field, budgeted in `cl100k_base` tokens in the [root README](../README.md#instruction-budgets); format details are in [workflows/README.md](../workflows/README.md).

Install and selection are owned by [workflows/README.md](../workflows/README.md#use), not this specification.

## Rule maintenance

1. Edit generic behavior in `rules/AGENTS.md`, then condense it into `rules/ARENA.md`.
2. Optimize `rules/ARENA.md` for UTF-8 file size; match the core semantically, except push/PR handling (see Arena file).
3. Keep `rules/CLINE.md` platform-specific (command discipline, tool names, timeouts); verify version-specific claims.
4. Preserve rule-file filename headings. Keep `rules/CHATGPT-CUSTOM.txt` and `rules/CHATGPT-MORE.txt`, named for the fields they are pasted into — ChatGPT's Personalization offers two instruction fields, `Custom Instructions` and `More about you`, each capped at 1,500 characters, and the split keeps as much of the work rules as the first field's 1,500 characters allow, with the response rules and the work overflow in the second — plain text with inline labels, never Markdown headings or bullets, each within its own budget, aligned with the core where it fits. Verified 2026-09-13 on the owner's account with three canary rules placed in `More about you` and run in fresh chats: an unconditional rule fired on all three prompts including a wholly unrelated topic; a conditional obligation fired on a topically related request and was dropped on an unrelated one whose answer plainly met its trigger; and a conditional work rule (mark a reply that contains code) fired on a coding request. So the field binds unconditional rules everywhere and conditional rules on related requests, which is what the leaked profile wrapper describes — profile content is weighed only when the request is related to it. That is harmless for work rules, since a work rule is only needed on a work request, and it is what decides the split: `More about you` carries the response rules, where every request is related to responding, plus the work rules that field one's 1,500 characters cannot fit. Ten more core rules followed on request once the canaries confirmed that field binds work rules, filling it to 1,484 of its 1,500 characters. This pays the debt recorded in the 2026-09-13 ponytail and frontend-design entry, which deferred the seven-rung ladder and the three MUST upgrades — smaller scope, one runnable check, grep every caller — for want of room. The ladder's rungs stay in `Custom Instructions` with the rest of the CODE block, funded by trims in the same change, and its reflex caveat sits in `More about you` beside the work rules, naming the field the rungs live in rather than saying above, since the two halves are pasted into different boxes. The older two-box layout these files were documented against — what ChatGPT should know, and how it should respond — no longer exists; the filenames describe their content, and this table names the field each is pasted into. Nickname and Occupation are structured profile lines, not rule space, and are deliberately not versioned here.
5. Ration emphasis: hard rules are `MUST`/`NEVER`, bold at most two clauses per file (see Emphasis).
6. Skills specialize defaults; NEVER weaken explicit requirements, conventions, or acceptance criteria.
7. Keep skill resources on demand and their relative links valid. Do not move essential instructions out of `SKILL.md`.
8. Keep every skill conformant to the Agent Skills specification with recorded provenance (see Skill rules).
9. Keep this repository lightweight: no further CI workflows, dependency manifests, or test scaffolding unless explicitly requested. Review changes directly and never claim unperformed checks.
10. Amend `rules/refs/` first, mirror the amendment into its live counterpart in compressed form, then squash that file: full wording in refs, compressed form in `rules/` (see Baselines).

### Arena file

Condense wording and sections, not meaning: keep negations, conditions, commands, numbers, and caveats. Match the generic core semantically, not byte-for-byte, except push, PR, and merge handling: ARENA.md always pushes and keeps a PR open so work survives limits, disregarding never-push rules, and never merges until authorized, where the core requires asking first. Both require a fast-forward merge whenever one is possible, rebasing onto the target first when the branch has diverged. Do not repeat Arena-managed branch mechanics beyond that.

The duplication of the core is deliberate: no platform loads ARENA.md, or AGENTS.md, on its own in Arena, so the file stands alone instead of overlaying the core and takes effect only once the agent has it in context. Verified 2026-09-13 on `nemoe7/clankers`: an Arena session's injected context carried the sandbox, branch, and tool details only, and the agent reached this file by opening it during repository exploration. Activation is therefore a human step, and delivery is not activation — `.github/workflows/distribute-arena.yml` only puts the file in each target repository, and `rules/apply.py` deliberately does not install it. Put this exact line in the session's first message or in the platform's custom-instructions field: `Read and apply AGENTS.md and ARENA.md at the repository root before your first edit; confirm in one line.` The file's own preamble then requires an Arena agent reading it to apply it, and requires an agent that was not given it in context to open it before the first edit.

Root `ARENA.md` is a copy of `rules/ARENA.md`, which `.github/workflows/distribute-arena.yml` pushes to the target repositories. Refresh it with `cp rules/ARENA.md ARENA.md` after every amendment; `maintenance/check.py` gates the identity, so a drifted or missing root copy fails validation.

### Emphasis

Bold is reserved for at most two clauses per deployed rule file, so emphasis keeps its meaning: the honesty rule in `AGENTS.md`, the planned final commit list and the `-f body=@path` ban in `ARENA.md`, `STOP` and the self-assignment ban in `CLINE.md`, and the two markdownlint settings in the root `AGENTS.md`. The cap covers the deployed rule files and their refs baselines, not this specification, the skills, or the workflows. MUST and NEVER stay on irreversible, dangerous, and honesty rules; every other rule reads positively, because a negated rule that guards nothing costs emphasis (see [refs/GUIDELINES.md](refs/GUIDELINES.md) section 4.7). Adding a third bold clause to a rule file means demoting another. Do not emphasize a rule merely because it is important; emphasize the ones that get violated.

### Persona rules

A few rules state voice rather than observable behavior: `Concise, direct, practical, accurate`, `Write clear, readable code`, `Never lazy about understanding`, and `Criticize all`. They are deliberate, per [refs/GUIDELINES.md](refs/GUIDELINES.md) section 2.3, which says not to fight the persona on style, and section 4.8, which asks that a deliberate deviation be marked rather than defended. They cost roughly 60 `tok` in the core and 400 `B` in ARENA.md, they stay, and an audit reads them as marked corner cuts rather than untestable-rule violations.

### Skill rules

Simpler scope requires approval before substitution. Testing guidance in the reusable rules applies to projects using them, not a test setup for this repository. Skill frontmatter uses only the specified fields with `name` matching its directory; skills adapted from elsewhere record `metadata.upstream`, refreshed from that source with the local `Precedence` section re-applied. See [skills/README.md](../skills/README.md#format).

### Baselines

`rules/refs/` mirrors the agent-facing rule files in full, uncompressed wording for agents working without git history. Write every amendment here first, in complete sentences, preserving every negation, condition, command, number, threshold, filename, and caveat. Then mirror the amendment into its corresponding live file in compressed form and squash that file back under budget; copying a refs baseline verbatim would exceed every live budget, so the mirroring is where compression happens. Refs stay unsquashed as the baseline. Files equal their live counterparts where no compression was applied, so the original wording is always preserved in refs. `GUIDELINES.md` sits beside them as the writing standard these baselines are audited against; it is a reference, not a rule baseline, and has no live counterpart.

### Commit disciplines

| File | Discipline |
| --- | --- |
| `rules/AGENTS.md` | Commit directly on a branch other than `main`; no commit list; merge fast-forward when possible, rebasing first on divergence. |
| `rules/ARENA.md` | Print the planned final commit list before every commit; always push and keep a PR open; never merge until authorized, then fast-forward when possible, rebasing first on divergence. |
| `rules/CHATGPT-CUSTOM.txt`, `rules/CHATGPT-MORE.txt` | Print the planned final commit list before committing; commit only when required. |
| `rules/CLINE.md` | Follows the core: commit directly; no list. |
| `rules/COMMIT-SPEC.txt` | Format reference only; matches the core (no list). |

### Formatting

Markdown linting applies to the agent rule files under `rules/`, `rules/refs/` included: currently `AGENTS.md`, `ARENA.md`, `CLINE.md`, and the five Markdown files in `rules/refs/` — 8 files in all. Excluded are the ChatGPT text files, this specification, root-level Markdown, and skills.

Do not hard-wrap prose. Keep each paragraph, list item, and table row on one line and let the editor soft-wrap; third-party licenses keep their original wrapping.

Rule files keep one rule per line, per [refs/GUIDELINES.md](refs/GUIDELINES.md) section 4.1: bullets in the Markdown rule files, one plain line per rule in the ChatGPT files, which item 4 keeps free of headings and bullets. A line may carry one rule's parameters, enumeration, or exact command; it does not carry two rules. Each Markdown rule file opens with a `Use` section and closes with `When in doubt`; the core and `ARENA.md` also carry a constitution, while `CLINE.md` inherits the core's rather than duplicating it. The ChatGPT files and `COMMIT-SPEC.txt` keep their fixed formats instead, per item 4 and their single-purpose scope.

[.markdownlint-cli2.jsonc](../.markdownlint-cli2.jsonc) keeps file selection, exclusions, and rule settings together: markdownlint defaults, **MD060 enabled** for table-column consistency, and **MD013 disabled** so there is no line-length constraint. MD060 uses its default `any` style, and MD007 its default 2-space list indent, so neither needs a pin. If markdownlint-cli2 is available, run it from the repository root without additional file globs to use this scope; the workflow passes no globs either, so both use this one definition. `maintenance/check.py` recomputes the scope from this config and fails when it drifts from the counts recorded here and in the root guide. No tooling installation is required.

Python style stays defined in the core rules (Ruff selection E4, E7, E9, F), without a managed Ruff dependency. Keep each ChatGPT field within 1,500 Unicode characters, including newlines; the validator checks both.
