# Rules specification

Reference for rule structure, constraints, and installation. See [maintenance/README.md](../maintenance/README.md) for repository maintenance procedures. Do not deploy this file into an agent’s Rules folder.

Commands and code-span paths are repository-root-relative unless stated otherwise.

The installer uses only the Python standard library.

## Contents

| File or directory | Purpose |
| --- | --- |
| [rules/AGENTS.md](AGENTS.md) | Generic core rules |
| [rules/CLINE.md](CLINE.md) | Cline-specific overlay |
| [rules/KILO.md](KILO.md) | Kilo Code overlay |
| [rules/ARENA.md](ARENA.md) | Self-contained Arena rules, optimized for file size |
| [rules/CHATGPT-CUSTOM.txt](CHATGPT-CUSTOM.txt) | ChatGPT Personalization: `Custom Instructions` |
| [rules/CHATGPT-MORE.txt](CHATGPT-MORE.txt) | ChatGPT Personalization: `More about you` |
| [rules/COMMIT-SPEC.txt](COMMIT-SPEC.txt) | Short commit-message reference |
| [rules/refs/](refs/README.md) | Uncompressed rule originals and the AGENTS.md writing guidelines |

Check active files in your installed agent version. Filenames alone do not enable loading. ARENA.md compresses the core for standalone deployment. CLINE.md requires the loader to read AGENTS.md too. If it stops, fix installation or explicitly restore the core. NEVER lose it silently.

## Core rules

- MUST use ASD-STE100 for human-facing text.
- Terse and unambiguous, NEVER cryptic or vague.
- Ask if ambiguous.
- YAGNI/KISS/DRY.
- Always add tests. NEVER weaken one.
- NEVER push unless asked. MUST branch from main.

## Platform difference matrix

Platform constraints made the three rule surfaces differ, so each row names one behavior per platform and nothing identical.

| Domain | Agents | Arena | ChatGPT |
| --- | --- | --- | --- |
| Git/Hub | <ul><li>NEVER push unasked. </li><li>MUST branch from main. </li></ul> | <ul><li>ALWAYS push, PR open. </li><li>Rebase merge only. </li><li>NEVER merge unauthorized. </li><li>Planned list before commits. </li><li>GitHub reconnect after one retry. </li><li>CI reported at turn end. </li><li>Backoff polls for PR checks. </li></ul> | <ul><li>ALWAYS a PR. </li><li>ALWAYS rebase merge. </li><li>Poll all checks. </li><li>NEVER end before CI. </li><li>NEVER multiple commits. </li><li>Planned list first. </li></ul> |
| Questions | The question tool. NEVER plain text. | Fielded report forms. NEVER plain text. | — |
| Changelogs | Use Keep a Changelog unless the repository uses another format. | Use Keep a Changelog unless the repository uses another format. | — |
| Mermaid Diagrams | Default where rendered. Phone-sized. | NEVER in chat. Docs only. | MUST for pipelines/flows unless target explicitly cannot render Mermaid. NEVER ASCII. |
| Recommendation | Required on three or more options. | Required on three or more options. | — |
| Platform Specific | <ul><li>Shell check first. </li></ul> | <ul><li>10-4 opens the first reply. </li><li>ALWAYS activate preview steering. </li><li>Negative rating on noncompliance. </li><li>Reports through the preview skill. </li><li>NEVER end with open tasks. </li><li>ALWAYS smallest task next. </li><li>Visibility question after first start. </li><li>Protected files, waiver only. </li><li>ALWAYS amend on violation. </li></ul> | <ul><li>ALWAYS think longer. </li></ul> |

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

**The installer overwrites destination files.** Back up local changes first. Skills, ARENA.md and ChatGPT files need separate setup. NEVER install this specification as an agent rule.

## Markdown lint scope

Markdownlint covers the agent rule files under `rules/`, including `rules/refs/`, plus `rules/wenyan/README.md`. The documented lint set contains 11 files in all.

