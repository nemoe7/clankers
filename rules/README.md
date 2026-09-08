# Rules specification

This file defines the rule system's structure, constraints, installation, and
maintenance. It is reference documentation, not an agent rule file; do not
deploy it into an agent's Rules folder.

Commands and paths in code spans are relative to the repository root unless
stated otherwise.

The scripts use only Python's standard library. No package installation, test
suite, or GitHub Actions workflows are required.

## Contents and activation

| File or directory | Purpose | How to use |
| --- | --- | --- |
| [rules/AGENTS.md](AGENTS.md) | Generic core rules | Install in the agent's supported global rules location; requires the `agent-handoff` entry point except on Arena.ai |
| [rules/CLINE.md](CLINE.md) | Cline-specific overlay | Load alongside AGENTS.md; it deliberately does not duplicate the core |
| [rules/ARENA.md](ARENA.md) | Self-contained, file-size-optimized Arena rules | Upload or point the Arena agent to it; its preamble requires Arena agents reading it to apply it, subject to higher-priority platform instructions; `agent-handoff` does not apply |
| [rules/CHATGPT.txt](CHATGPT.txt) | ChatGPT custom instructions | Paste into the instructions field; at most 1,500 characters |
| [rules/COMMIT_SPEC.txt](COMMIT_SPEC.txt) | Compact commit-message reference | Use when preparing an authorized commit or proposed message |
| [skills/](../skills/) | Reusable skills | Install complete skill directories, including supporting files |

Rules and tools can load differently across agent versions. Verify which files
are active in your installed release; do not assume a filename alone enables
loading. ARENA.md condenses the core because it is deployed independently. CLINE.md
relies on AGENTS.md also being loaded; if that assumption stops holding, fix
installation or deliberately re-embed the core rather than silently losing it.

## Install rules

From the repository root, with Python 3:

```bash
python3 apply_rules.py
```

On Windows, use `python apply_rules.py` or `apply.bat` from the repository root.
The script previews unified diffs for changed files, asks once for confirmation,
then copies these two files, creating destination directories as needed. Enter
`y` or `yes` to apply; any other response aborts. If both destinations are
current, it exits without prompting.

| Source | Destination relative to the base directory |
| --- | --- |
| `rules/AGENTS.md` | `.agents/AGENTS.md` |
| `rules/CLINE.md` | `Documents/Cline/Rules/CLINE.md` |

The base defaults to `Path.home()`. A nonempty `APPLY_RULES_BASE` overrides it,
without requiring `USERPROFILE`. An empty override uses the home directory.
These are the installer's configured paths; confirm they match your agent setup.

To install under another base directory:

```bash
APPLY_RULES_BASE=/path/to/profile python3 apply_rules.py
```

PowerShell:

```powershell
$env:APPLY_RULES_BASE = "C:\path\to\profile"
python .\apply_rules.py
```

**Existing destination files are overwritten.** Back up any local customization
before applying. The installer does not install skills, ARENA.md, or CHATGPT.txt;
use their separate setup steps. Do not install this specification as an agent rule.

## Install and load skills (human maintainers)

Installation, updates, and removal are human maintenance, not agent tasks.
Agents may inspect available skills, but must treat their installed copies as
read-only and report missing or incompatible files rather than installing or
repairing them. Explicitly requested edits to skill source in this repository
do not authorize changes to an agent's installed copies.

Copy complete skill folders into a discovery path supported by your agent.
Install `agent-handoff` before enabling rules that require it. Keep its folder
name and include `references/`, `templates/`, and `scripts/`; copying only
`SKILL.md` is not enough. The checker uses Python 3 and the standard library.

For an agent configured to discover project skills under `.agents/skills/`,
a human maintainer can run:

```bash
mkdir -p .agents/skills
cp -R /path/to/clankers/skills/agent-handoff .agents/skills/
```

### Discovery notes

Paths and precedence are vendor/version-specific. Confirm them with your
installed release; these paths are integration notes, not a runtime probe.

| Agent | Project | Global |
| --- | --- | --- |
| Antigravity | `.agents/skills/` or legacy `.agent/skills/` | `~/.gemini/config/skills/` |
| Cline | `.cline/skills/` | `~/.cline/skills/` |
| Kilo Code | `.kilo/skills/` or `.agents/skills/` | `~/.kilo/skills/` |

Keep one active copy unless you have verified precedence. Reload or restart
discovery as required. Avoid embedded shell-execution syntax in skills because
execution permissions can differ by scope.

For non-Arena agents, after setup ask the agent to load `agent-handoff` and
identify its entry point and conditional reference paths without opening every
supporting file. A
missing skill is reported to the user, not self-installed or silently ignored.
In environments without automatic discovery, provide the entry point explicitly.

### Skill selection

| Skill | When needed |
| --- | --- |
| [agent-handoff](../skills/agent-handoff/SKILL.md) | Non-Arena agents load its small entry point; prepare or update documents only at the boundaries it defines |
| [planning](../skills/planning/SKILL.md) | Substantial or materially underspecified work |
| [ponytail](../skills/ponytail/SKILL.md) | Simpler implementations within the user's requirements and existing project conventions |
| [frontend-design](../skills/frontend-design/SKILL.md) | New or substantially redesigned interfaces |
| [web-design-guidelines](../skills/web-design-guidelines/SKILL.md) | Reviews of an existing UI against the upstream guidelines |

### Handoff components

Arena.ai is exempt from `agent-handoff`: no skill loading, canonical handoff,
plan-file handoff step, or skill-triggered commit checkpoint. Arena's own atomic
commit rules still apply independently.

For other agents, only `skills/agent-handoff/SKILL.md` belongs in always-loaded
context. It states the triggers, essential safety and identity rules, and which
component to read.
Supporting paths below are relative to `skills/agent-handoff/`:

- `references/protocol.md`: lifecycle, history, sender/receiver procedures, and validation; load when operating on a handoff.
- `templates/AGENT_HANDOFF.md`: load when creating a document, not on routine skill activation.
- `references/examples.md`: load only when an example is useful.
- `scripts/handoff_lint.py`: execute against prepared documents; do not load its source merely to activate the skill.

Acceptance and resumption keep the same transfer ID and append lifecycle events.
`BLOCKED` is resumable; only `DONE` is terminal. Superseded evidence stays in the
audit sections, not current context. Non-Arena agents with file-backed plan
mode must include an explicit handoff-update step in the plan file, not only
in chat.
Required handoff updates must be committed atomically, even though the core
rules also require atomic commits. Commit task work first and the handoff
checkpoint separately; report blocked commits rather than claiming a transfer
is complete. This does not grant push/PR permission.

## Rule maintenance

1. Edit generic behavior in `rules/AGENTS.md`, then preserve its intent in the condensed `rules/ARENA.md`.
2. **Optimize ARENA.md for file size (UTF-8 bytes).** Condense wording and sections, not meaning: preserve negations, conditions, commands, numbers, and caveats. Match the generic core semantically, not byte-for-byte. Do not repeat Arena-managed branch, push, or PR lifecycle instructions or apply `agent-handoff` to Arena.
3. Keep CLINE.md platform-specific. Its command discipline, tool names, timeout behavior, and `implementation_plan.md` conventions live there. The generic planning skill must not assume that filename. Verify version-specific claims before changing them.
4. Preserve rule-file filename headings. Keep CHATGPT.txt as plain text with inline section labels, not Markdown headings or bullets, and within its character budget.
5. Skills may specialize defaults, but must not weaken explicit acceptance criteria or replace project conventions. Simpler scope requires approval before substitution. Testing guidance in the reusable rules applies to projects using them, not a test setup for this repository.
6. Keep handoff resources on demand and their relative links valid. Do not move essential boundary or plan-file instructions out of the entry point.
7. Keep this repository lightweight: do not add workflows, dependency manifests, or test scaffolding unless explicitly requested. Review changes directly and never claim checks that were not performed.

### Formatting

Markdown linting applies only to agent rule files under `rules/`: currently
AGENTS.md, ARENA.md, and CLINE.md. ChatGPT instructions and this specification
are explicitly excluded. The root README, skills, references, and templates
are also outside this linting scope.

[.markdownlint-cli2.jsonc](../.markdownlint-cli2.jsonc) keeps file selection,
exclusions, and rule settings together: markdownlint defaults, **MD060 enabled**
for table-column consistency, and **MD013 disabled** so there is no line-length
constraint. MD060 uses its default `any` style. If markdownlint-cli2 is already
available, run it from the repository root without additional file globs to use
this scope. No tooling installation is required.

Python style remains defined in the core rules (Ruff selection E4, E7, E9, F),
without a managed Ruff dependency. Keep CHATGPT.txt within 1,500 Unicode
characters, including newlines.

## Handoff document checks

The dependency-free handoff checker remains part of the skill for checking
prepared documents, not as a repository test suite:

```bash
python3 skills/agent-handoff/scripts/handoff_lint.py AGENT_HANDOFF.md
```

A zero exit code means automated checks passed, not that a handoff is safe,
accurate, or complete. Follow the manual checklist in the
[protocol](../skills/agent-handoff/references/protocol.md).
