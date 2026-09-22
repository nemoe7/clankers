# Rules specification

This file gives the structure, constraints, installation and maintenance of the rule system. It is reference documentation, not an agent rule file. Do not deploy it into the Rules folder of an agent.

A command or a path in a code span is relative to the repository root unless the text says otherwise.

The installation script uses only the Python standard library. The repository has no test suite. `maintenance/check.py` needs `markdown-it-py` and `tiktoken`, which CI in [.github/workflows/](../.github/workflows/) installs before running it on every push and pull request. The workflow then commits the refreshed README measurements and lints the Markdown.

## Contents and activation

| File or directory | Purpose | How to use |
| --- | --- | --- |
| [rules/AGENTS.md](AGENTS.md) | Generic core rules | Install in the supported global rules location of the agent |
| [rules/CLINE.md](CLINE.md) | Cline-specific overlay | Load it with AGENTS.md. It deliberately does not copy the core |
| [rules/KILO.md](KILO.md) | Kilo Code overlay | Load it with AGENTS.md. The per-mode overrides live in [rules/kilo/](kilo/), one per mode |
| [rules/ARENA.md](ARENA.md) | Self-contained Arena rules, optimized for file size | Upload it, or open every session with the bootstrap line in [Arena file](#arena-file). No platform loads it alone |
| [rules/CHATGPT-CUSTOM.txt](CHATGPT-CUSTOM.txt) | ChatGPT Personalization: `Custom Instructions` | Paste it into Custom Instructions, hinted "Additional behavior, style, and tone preferences". 1,500 characters at most |
| [rules/CHATGPT-MORE.txt](CHATGPT-MORE.txt) | ChatGPT Personalization: `More about you` | Paste it into More about you, hinted "Interests, values, or preferences to keep in mind". 1,500 characters at most |
| [rules/COMMIT-SPEC.txt](COMMIT-SPEC.txt) | Short commit-message reference | Use it to prepare an authorized commit or a proposed message |
| [rules/refs/](refs/README.md) | Uncompressed rule originals and the AGENTS.md writing guidelines | Amend here first. Then mirror the amendment into the live file in compressed form, and squash it |
| [skills/](../skills/README.md) | Reusable skills | Install the complete skill directories, including the supporting files |
| [workflows/](../workflows/README.md) | Portable agent workflows | Copy the workflow file into the workflow location of your platform, or run it as it is |

Rules and tools load differently across agent versions. Determine which files are active in your installed release, and never assume a filename alone enables loading. ARENA.md compresses the core because it deploys on its own. CLINE.md relies on the loader also reading AGENTS.md. If that stops holding, repair the installation or deliberately put the core back in. Do not lose it in silence.

## Install rules

From the repository root, with Python 3:

```bash
python3 rules/apply.py
```

On Windows, use `python rules\apply.py` or `apply.bat` from the repository root. The script shows unified diffs for the changed files, asks for one response, then copies two files and creates destination directories when necessary. Enter `y` or `yes` to apply. Any other response aborts. The flags `--yes`/`-y` skip the prompt, and `--dry-run` shows the diffs without a change. If both destinations are current, the script exits with no prompt.

| Source | Destination relative to the base directory |
| --- | --- |
| `rules/AGENTS.md` | `.agents/AGENTS.md` |
| `rules/CLINE.md` | `Documents/Cline/Rules/CLINE.md` |

The base defaults to `Path.home()`. A nonempty `APPLY_RULES_BASE` overrides it and needs no `USERPROFILE`. An empty override uses the home directory. These are the configured paths of the installer. Check that they match your agent setup.

To install under another base directory:

```bash
APPLY_RULES_BASE=/path/to/profile python3 rules/apply.py
```

PowerShell:

```powershell
$env:APPLY_RULES_BASE = "C:\path\to\profile"
python .\rules\apply.py
```

**The installer overwrites an existing destination file.** Back up local changes before applying it. It installs no skills, ARENA.md or ChatGPT files. Use their separate setup steps. Do not install this specification as an agent rule.

## Workflows

A workflow is portable across coding-agent platforms. Its body depends on no platform-specific tool, agent name, model, provider, UI, permission or interaction mechanism. Each workflow is one self-contained Markdown file with a `description` frontmatter field, budgeted in `cl100k_base` tokens in the [root README](../README.md#instruction-budgets). The format details are in [workflows/README.md](../workflows/README.md).

[workflows/README.md](../workflows/README.md#use) owns the installation and the selection, not this specification.

## Rule maintenance

1. Edit generic behavior in `rules/AGENTS.md` first. Then compress it into `rules/ARENA.md`.
2. Optimize `rules/ARENA.md` for UTF-8 file size. Match the core in meaning, except for push and PR handling (see Arena file).
3. Keep `rules/CLINE.md` and `rules/KILO.md` platform-specific: command discipline, tool names, timeouts. Check every version-specific claim. The Kilo mode overrides pair `rules/refs/kilo/` with the live `rules/kilo/`. The maintainer compresses and budgets each live file, and both sides stay out of the lint because their required shape fails MD001 and MD041.
4. Keep the filename headings of the rule files. Keep `rules/CHATGPT-CUSTOM.txt` and `rules/CHATGPT-MORE.txt`, named for the fields they go into. ChatGPT's Personalization gives `Custom Instructions` and `More about you`, each with a 1,500 Unicode character ceiling. Keep both files plain text with inline labels, never Markdown headings or bullets, within budget, and aligned with the core where it fits. The split places work rules in `Custom Instructions`, and it places response rules plus overflow work rules in `More about you`. ChatGPT keeps nickname and occupation as structured profile fields rather than rule space, and this repository does not version them.
5. Ration the emphasis: a hard rule uses `MUST` or `NEVER`, and a file bolds two clauses at most (see Emphasis).
6. A skill specializes a default. It NEVER weakens an explicit requirement, a convention, or an acceptance criterion.
7. Keep the skill resources on demand, and keep their relative links valid. Do not move essential instructions out of `SKILL.md`.
8. Keep every skill conformant to the Agent Skills specification, with recorded provenance (see Skill rules).
9. Keep this repository light: no further CI workflow, dependency manifest or test scaffolding unless the owner asks for one. The pinned minifier manifest the preview build uses is the one exception, on the owner's answers to report `minification-scope`. Review a change directly, and never claim a check that did not run.
10. Amend `rules/refs/` first. Then mirror the amendment into its live counterpart in compressed form, and squash only the new or affected line. On a removal, attempt one squash and keep the lower budget. Full wording stays in refs, and the compressed form stays in `rules/` (see Baselines).

### Arena file

Arena uses the sibling `arena-preview-steering` and `arena-preview-reporting` skills for one Notes / Reports preview. Reports and session state stay ignored and uncommitted. The migration reference of the steering skill records the former ntfy and local-report-commit workflows. Neither is an automatic fallback, and no one guarantees that the preview is permanent.

Compress wording and sections, not meaning. Keep every negation, condition, command, number, and caveat. Match the generic core in meaning, not byte for byte, except for push, PR, and merge handling. ARENA.md always pushes and keeps a PR open so work survives a limit. It disregards the never-push rules, and it never merges until the owner authorizes it, where the core requires a question first. The core requires fast-forward when possible. Arena merges by rebase only: rebase onto the target, then merge, so no merge commit lands. Do not repeat Arena-managed branch mechanics beyond that.

The duplication of the core is deliberate. In Arena, no platform loads ARENA.md or AGENTS.md on its own. So the file stands alone instead of overlaying the core, and it takes effect only after the agent has it in context. Verified 2026-09-13 on `nemoe7/clankers`: the injected context of an Arena session carried the sandbox, the branch, and the tool details only. The agent reached this file by opening it during repository exploration. On 2026-09-17 a session on the same repository missed it: the agent explored the skill subtree and pushed twice before it read either file. So exploration is a bet rather than a gate. The custom-instructions field, not the first message, is the only injection path that survives a forgotten bootstrap line. Activation is therefore a human step. Delivery is not activation. `.github/workflows/distribute-arena.yml` only puts the file in each target repository, and `rules/apply.py` deliberately does not install it. Put this exact line in the first message of the session. Put it in the custom-instructions field of the platform: `Read and apply AGENTS.md and ARENA.md at the repository root before your first edit; confirm in one line.` The preamble of the file then requires an Arena agent that reads it to apply it. It also requires an agent that did not receive it in context to open it before the first edit.

Root `ARENA.md` is a copy of `rules/ARENA.md`, which `.github/workflows/distribute-arena.yml` pushes to the target repositories. Refresh it with `cp rules/ARENA.md ARENA.md` after every amendment. `maintenance/check.py` gates the identity, so a drifted or missing root copy fails the check.

### Emphasis

A deployed rule file keeps two bold clauses at most, so the emphasis keeps its meaning. The bold clauses are the honesty rule in `AGENTS.md`. In `ARENA.md` they are the planned final commit list and the `-f body=@path` ban. In `CLINE.md` they are `STOP` and the self-assignment ban. In the root `AGENTS.md` they are the two markdownlint settings. The cap covers the deployed rule files and their refs baselines. It does not cover this specification, the skills, or the workflows. `MUST` and `NEVER` stay on the irreversible, the dangerous, and the honesty rules. Every other rule reads positively, because a negated rule that guards nothing costs emphasis (see [refs/GUIDELINES.md](refs/GUIDELINES.md) section 4.7). A third bold clause in a rule file means one other clause becomes plain. Do not emphasize a rule merely because it is important. Emphasize the rules that get violated.

### Persona rules

A few rules state voice rather than observable behavior. They are `Concise, direct, practical, accurate`, `Write clear, readable code`, `Never lazy about understanding`, and `Criticize all`. They are deliberate, per [refs/GUIDELINES.md](refs/GUIDELINES.md) section 2.3, which says not to fight the persona on style. Section 4.8 asks that a deliberate deviation be marked rather than defended. They cost about 60 `tok` in the core and 400 `B` in ARENA.md. They stay, and an audit reads them as marked corner cuts rather than as untestable-rule violations.

### Skill rules

A simpler scope needs approval before a substitution. The testing guidance in the reusable rules applies to the projects that use them, not to a test setup for this repository. The frontmatter of a skill uses only the specified fields, with `name` matching its directory. A skill that comes from another source records `metadata.upstream`, and the maintainer refreshes it from that source with the local `Precedence` section applied again. See [skills/README.md](../skills/README.md#format).

### Baselines

`rules/refs/` mirrors the agent-facing rule files in full, uncompressed wording for agents that work without git history. Write every amendment here first, in complete sentences, keeping every negation, condition, command, number, threshold, filename and caveat. Then mirror it into its live file compressed, squashing only the new or affected line. On a removal, attempt one squash and keep the lower budget. A refs baseline copy would exceed every live budget, so the mirroring is where compression happens. Refs stay uncompressed as the baseline. A file equals its live counterpart where the change applied no compression, so refs always hold the original wording. `GUIDELINES.md` sits beside them as the writing standard that the audits use on these baselines. It is a reference, not a rule baseline, and it has no live counterpart.

### Commit disciplines

| File | Discipline |
| --- | --- |
| `rules/AGENTS.md` | Commit on a branch other than `main`. No commit list. Merge fast-forward when possible, and rebase first on divergence |
| `rules/ARENA.md` | Print the planned final commit list before every commit. Always push and keep a PR open. Never merge until the owner authorizes it, then merge by rebase only: rebase onto the target, then merge |
| `rules/CHATGPT-CUSTOM.txt`, `rules/CHATGPT-MORE.txt` | Print the planned final commit list before a commit. Commit only when necessary |
| `rules/CLINE.md` | Follow the core: commit directly, and keep no list |
| `rules/KILO.md`, `rules/kilo/*.md` | Follow the core: commit directly, and keep no list |
| `rules/COMMIT-SPEC.txt` | Format reference only. Matches the core, with no list |

### Formatting

Markdown linting applies to the agent rule files under `rules/`, and that includes `rules/refs/`. The linted files are `AGENTS.md`, `ARENA.md`, `CLINE.md`, `KILO.md`, and the six Markdown files in `rules/refs/` — 10 files in all. The excluded files are the ChatGPT text files and this specification. The other exclusions are root-level Markdown, the skills, and the `rules/refs/kilo/` and `rules/kilo/` mode overrides. The required blank first line and `###` heading of a mode override fail MD001 and MD041.

Do not hard-wrap the prose. Keep each paragraph, list item and table row on one line, and let the editor soft-wrap. Third-party licenses keep their original wrapping.

Rule files keep one rule per line, per [refs/GUIDELINES.md](refs/GUIDELINES.md) section 4.1. The Markdown rule files use bullets. The ChatGPT files use one plain line per rule, and item 4 keeps them free of headings and bullets. A line can carry the parameters, the enumeration, or the exact command of one rule. It does not carry two rules. The core and `ARENA.md` open with a `Use` section. The overlays `CLINE.md` and `KILO.md` do not. The Markdown rule files close with a `When in doubt` section. `KILO.md` is the exception, because the core settles the doubts it would restate. The core and `ARENA.md` also carry a constitution, and `CLINE.md` and `KILO.md` inherit the core's instead of copying it. The `rules/refs/kilo/` and `rules/kilo/` mode overrides keep a different shape on purpose. They open with a blank line, then `### Native <mode> Agent Overrides`, then the conflict clause. Kilo wraps them as a mode reminder rather than loading them as a full rules file. The ChatGPT files and `COMMIT-SPEC.txt` keep their set formats instead, per item 4 and their single-purpose scope.

[.markdownlint-cli2.jsonc](../.markdownlint-cli2.jsonc) keeps the file selection, the exclusions, and the rule settings together. It keeps the markdownlint defaults, enables **MD060** for table-column consistency, and disables **MD013** so there is no line-length constraint. MD060 uses its default `any` style, and MD007 uses its default two-space list indent, so neither needs a pin. If markdownlint-cli2 is available, run it from the repository root with no additional file globs to use this scope. The workflow passes no globs either, so both use this one definition. `maintenance/check.py` recomputes the scope from this config and fails when it drifts from the counts recorded here and in the root guide. No tooling installation is necessary.

The Python style stays defined in the core rules (Ruff selection E4, E7, E9, F), with no managed Ruff dependency. Keep each ChatGPT field within 1,500 Unicode characters, including the newlines. `maintenance/check.py` checks both.
