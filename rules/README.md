# Rules specification

Reference for rule structure, constraints, and installation. See [maintenance/README.md](../maintenance/README.md) for repository maintenance procedures. Do not deploy this file into an agent’s Rules folder.

Commands and code-span paths are repository-root-relative unless stated otherwise.

The installer uses only the Python standard library.

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

## Markdown lint scope

Markdownlint covers the agent rule files under `rules/`, including `rules/refs/`, plus `rules/wenyan/README.md`. The documented lint set contains 11 files in all.

