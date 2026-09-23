# Rules specification

Reference for rule structure, constraints, installation and maintenance. Do not deploy this file into an agent’s Rules folder.

Commands and code-span paths are repository-root-relative unless stated otherwise.

The installer uses only the Python standard library. This repository uses assert-based runtime, client and maintenance checks. [.github/workflows/](../.github/workflows/) checks pushes to `main` and PRs targeting any branch, except changes limited to its ignored paths. It installs `markdown-it-py` and `tiktoken`, runs `maintenance/check.py --update`, and lints Markdown. Only qualifying `main` pushes commit refreshed README measurements.

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

Check active files in your installed agent version. Filenames alone do not enable loading. ARENA.md compresses the core for standalone deployment. CLINE.md requires the loader to read AGENTS.md too. If it stops, repair installation or explicitly restore the core. Never lose it silently.

## Platform difference matrix

Platform constraints cause differences between Core (`rules/AGENTS.md`), Arena (`rules/ARENA.md`), and both ChatGPT fields. Cells quote live clauses, with `—` for absence and periods replacing semicolons for ASD-STE100. ChatGPT cells contain only clauses. Automations are prompts, excluded here. See the 2026-09-22 CHANGELOG for reasons.

| Rule area | Core | Arena | ChatGPT |
| --- | --- | --- | --- |
| Push and PR | NEVER push or open a PR unless asked. | Always push the branch and keep a PR open, disregarding never-push rules. | ALWAYS PR. |
| Merge | — | rebase merge only: rebase onto the target, then merge, so no merge commit lands | ALWAYS rebase merge. |
| Merge authorization | — | NEVER merge the PR without authorization | — |
| Commit list | — | Before every commit, without exception, print the planned final commit list first | Print the planned final commit list first. |
| Question channel | Ask every question with the question tool. NEVER ask in plain text. | stop and ask with the `ask_user` tool. Questions go through a fielded report in the Reports tab. | — |
| Ask on ambiguity | Material ambiguity = readings that could change behavior/data/interfaces/scope/outcome: ask before implementing. | Ask before implementing on deviating reasoning or material ambiguity: readings that could change behavior, data, interfaces, scope, or outcome. | never block an unattended run — note the question, assume, state it. |
| Terseness | no unnecessary prose. Detail when asked. | Short chat reports: concise on phone and vertical monitors. Limit prose. No essays unless strictly necessary. | Be terse yet clear, numbered lists. Detail when asked. |
| Mermaid | Mermaid for pipelines, diagrams, flows where the surface renders it. Fit narrow viewports (phone, sidebar): `flowchart TB`, short labels, no wide rows. | NEVER mermaid in chat, which Arena cannot render. Repository docs use mermaid for pipelines, diagrams, and flows, never ASCII art. | Mermaid diagrams default for pipelines/flows: `flowchart TB`, short labels/rows, phone-sized. NEVER ASCII art. |
| Turn-end tests | — | Before turn end with a pushed branch, check and report open PR CI. Failed checks leave work unfinished. | NEVER end turn until tests are green. |
| First reply | — | the first reply, which opens `10-4: ARENA.md loaded` | — |
| Preview steering | — | Always activate `arena-preview-steering` at its source/installed path. | — |
| Shell check | MUST check the harness shell before commands. Use its syntax. | — | — |
| Smaller scope | — | Complex request: ship the lazier version and question the requirement in the same response. | MUST propose a smaller scope for approval when brief exceeds need. |

## Install rules

From the repository root, with Python 3:

```bash
python3 rules/apply.py
```

On Windows, run `python rules\apply.py` or `apply.bat` from the root. The script shows unified diffs, asks once, copies two files, and creates needed directories. `y` or `yes` applies, any other answer aborts. `--yes`/`-y` skips the prompt. `--dry-run` only shows diffs. Current destinations cause exit without a prompt.

| Source | Destination relative to the base directory |
| --- | --- |
| `rules/AGENTS.md` | `.agents/AGENTS.md` |
| `rules/CLINE.md` | `Documents/Cline/Rules/CLINE.md` |

The base is `Path.home()` unless `APPLY_RULES_BASE` is nonempty. The script does not need `USERPROFILE`. An empty override uses home. Check these installer paths against your agent setup.

To install under another base directory:

```bash
APPLY_RULES_BASE=/path/to/profile python3 rules/apply.py
```

PowerShell:

```powershell
$env:APPLY_RULES_BASE = "C:\path\to\profile"
python .\rules\apply.py
```

**The installer overwrites destination files.** Back up local changes first. Skills, ARENA.md and ChatGPT files need separate setup. Never install this specification as an agent rule.

## Workflows

A workflow is one portable Markdown file with a `description` frontmatter field and a `cl100k_base` budget in the [root README](../README.md#instruction-budgets). Its body has no platform-specific tool, agent, model, provider, UI, permission or interaction mechanism. See [format details](../workflows/README.md).

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
9. Keep this repository light: no further CI workflow, dependency manifest or test scaffolding unless the owner asks for one. The pinned minifier manifest the preview build uses is the one exception, on the owner's approved answers. Review a change directly, and never claim a check that did not run.
10. Amend `rules/refs/` first. Then mirror the amendment into its live counterpart in compressed form, and squash only the new or affected line. On a removal, attempt one squash and keep the lower budget. Full wording stays in refs, and the compressed form stays in `rules/` (see Baselines).

### Arena file

Arena uses the `arena-preview-steering` skill for one Notes / Reports preview. Keep reports and session state ignored and uncommitted. The steering migration reference records former ntfy and local-report-commit workflows, neither an automatic fallback. Preview permanence is not guaranteed.

Compress wording and sections, not meaning. Keep every negation, condition, command, number, and caveat. Match the generic core in meaning, not byte for byte, except for push, PR, and merge authorization. ARENA.md always pushes and keeps a PR open so work survives a limit. Core forbids pushes and PRs unless asked but has no merge clause. Arena never merges without owner authorization, then uses rebase only: rebase onto the target, then merge, so no merge commit lands. Do not repeat Arena-managed branch mechanics beyond that.

The duplication of the core is deliberate. In Arena, no platform loads ARENA.md or AGENTS.md on its own. So the file stands alone instead of overlaying the core, and it takes effect only after the agent has it in context. Exploration does not gate activation. Activation is a human step, and delivery is not activation. `.github/workflows/distribute-arena.yml` only puts the file in each target repository, and `rules/apply.py` deliberately does not install it. Put this exact line in the first message of the session. Put it in the custom-instructions field of the platform: `Read and apply AGENTS.md and ARENA.md at the repository root before your first edit. confirm in one line.` The preamble of the file then requires an Arena agent that reads it to apply it. It also requires an agent that did not receive it in context to open it before the first edit.

After each amendment, run `cp rules/ARENA.md ARENA.md`. `.github/workflows/distribute-arena.yml` pushes the root copy to target repositories. `maintenance/check.py` rejects missing or different root copies.

### Emphasis

A deployed rule file keeps two bold clauses at most, so the emphasis keeps its meaning. The bold clauses are the honesty rule in `AGENTS.md`. In `ARENA.md` they are the planned final commit list and the `-f body=@path` ban. In `CLINE.md` they are `STOP` and the self-assignment ban. In the root `AGENTS.md` they are the two markdownlint settings. The cap covers the deployed rule files and their refs baselines. It does not cover this specification, the skills, or the workflows. `MUST` and `NEVER` stay on the irreversible, the dangerous, and the honesty rules. Every other rule reads positively, because a negated rule that guards nothing costs emphasis (see [refs/GUIDELINES.md](refs/GUIDELINES.md) section 4.7). A third bold clause in a rule file means one other clause becomes plain. Do not emphasize a rule merely because it is important. Emphasize the rules that get violated.

### Persona rules

Four deliberate voice rules describe no observable behavior: `Concise, direct, practical, accurate`, `Write clear, readable code`, `Never lazy about understanding`, and `Criticize all`. [refs/GUIDELINES.md](refs/GUIDELINES.md) 2.3 says not to fight persona on style, and 4.8 requires marking deliberate deviations. These stay at about 60 `tok` in core and 400 `B` in ARENA.md. Audit them as marked exceptions, not untestable-rule violations.

### Skill rules

A simpler scope needs approval before a substitution. The testing guidance in the reusable rules applies to the projects that use them, not to a test setup for this repository. The frontmatter of a skill uses only the specified fields, with `name` matching its directory. A skill that comes from another source records `metadata.upstream`, and the maintainer refreshes it from that source with the local `Precedence` section applied again. See [skills/README.md](../skills/README.md#format).

### Baselines

`rules/refs/` keeps uncompressed baselines for agents without git history. Amend here first in complete sentences, preserving every negation, condition, command, number, threshold, filename and caveat. Compress only new or affected lines into live files. On removal, attempt one squash and keep the lower budget. Verbatim baselines would exceed live budgets. Refs preserve originals, identical to live where no compression applied. The adjacent `GUIDELINES.md` is the writing/audit reference, not a baseline, with no live counterpart.

### Formatting

Markdown linting applies to the agent rule files under `rules/`, and that includes `rules/refs/`. The linted files are `AGENTS.md`, `ARENA.md`, `CLINE.md`, `KILO.md`, and the six Markdown files in `rules/refs/` — 10 files in all. The excluded files are the ChatGPT text files and this specification. The other exclusions are root-level Markdown, the skills, and the `rules/refs/kilo/` and `rules/kilo/` mode overrides. The required blank first line and `###` heading of a mode override fail MD001 and MD041.

Soft-wrap prose: one line per paragraph, list item and table row. Keep third-party license wrapping.

Rule files keep one rule per line, per [refs/GUIDELINES.md](refs/GUIDELINES.md) section 4.1. The Markdown rule files use bullets. The ChatGPT files use one plain line per rule, and item 4 keeps them free of headings and bullets. A line can carry the parameters, the enumeration, or the exact command of one rule. It does not carry two rules. The core and `ARENA.md` open with a `Use` section. The overlays `CLINE.md` and `KILO.md` do not. The Markdown rule files close with a `When in doubt` section. `KILO.md` is the exception, because the core settles the doubts it would restate. The core and `ARENA.md` also carry a constitution, and `CLINE.md` and `KILO.md` inherit the core's instead of copying it. The `rules/refs/kilo/` and `rules/kilo/` mode overrides keep a different shape on purpose. They open with a blank line, then `### Native <mode> Agent Overrides`, then the conflict clause. Kilo wraps them as a mode reminder rather than loading them as a full rules file. The ChatGPT files and `COMMIT-SPEC.txt` keep their set formats instead, per item 4 and their single-purpose scope.

[.markdownlint-cli2.jsonc](../.markdownlint-cli2.jsonc) keeps the file selection, the exclusions, and the rule settings together. It keeps the markdownlint defaults, enables **MD060** for table-column consistency, and disables **MD013** so there is no line-length constraint. MD060 uses its default `any` style, and MD007 uses its default two-space list indent, so neither needs a pin. If markdownlint-cli2 is available, run it from the repository root with no additional file globs to use this scope. The workflow passes no globs either, so both use this one definition. `maintenance/check.py` recomputes the scope from this config and fails when it drifts from the counts recorded here and in the root guide. No tooling installation is necessary.

Core defines Python style (Ruff E4, E7, E9, F), with no managed Ruff dependency. `maintenance/check.py` checks both ChatGPT fields against 1,500 Unicode characters each, including newlines.
