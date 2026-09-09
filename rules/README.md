# Rules specification

This file defines the rule system's structure, constraints, installation, and maintenance. It is reference documentation, not an agent rule file; do not deploy it into an agent's Rules folder.

Commands and paths in code spans are relative to the repository root unless stated otherwise.

The scripts use only Python's standard library. No package installation, test suite, or GitHub Actions workflow is required.

## Contents and activation

| File or directory | Purpose | How to use |
| --- | --- | --- |
| [rules/AGENTS.md](AGENTS.md) | Generic core rules | Install in the agent's supported global rules location; requires the `agent-handoff` skill except on Arena.ai |
| [rules/CLINE.md](CLINE.md) | Cline-specific overlay | Load alongside AGENTS.md; it deliberately does not duplicate the core |
| [rules/ARENA.md](ARENA.md) | Self-contained, file-size-optimized Arena rules | Upload or point the Arena agent to it; its preamble requires Arena agents reading it to apply it; `agent-handoff` does not apply |
| [rules/CHATGPT.txt](CHATGPT.txt) | ChatGPT custom instructions | Paste into the instructions field; at most 1,500 characters |
| [rules/COMMIT_SPEC.txt](COMMIT_SPEC.txt) | Compact commit-message reference | Use when preparing an authorized commit or proposed message |
| [skills/](../skills/README.md) | Reusable skills | Install complete skill directories, including supporting files |

Rules and tools load differently across agent versions. Verify which files are active in your installed release; never assume a filename alone enables loading. ARENA.md condenses the core because it deploys independently. CLINE.md relies on AGENTS.md also being loaded; if that stops holding, fix installation or deliberately re-embed the core rather than silently losing it.

## Install rules

From the repository root, with Python 3:

```bash
python3 apply_rules.py
```

On Windows, use `python apply_rules.py` or `apply.bat` from the repository root. The script previews unified diffs for changed files, asks once for confirmation, then copies these two files, creating destination directories as needed. Enter `y` or `yes` to apply; any other response aborts. If both destinations are current, it exits without prompting.

| Source | Destination relative to the base directory |
| --- | --- |
| `rules/AGENTS.md` | `.agents/AGENTS.md` |
| `rules/CLINE.md` | `Documents/Cline/Rules/CLINE.md` |

The base defaults to `Path.home()`. A nonempty `APPLY_RULES_BASE` overrides it, without requiring `USERPROFILE`; an empty override uses the home directory. These are the installer's configured paths; confirm they match your agent setup.

To install under another base directory:

```bash
APPLY_RULES_BASE=/path/to/profile python3 apply_rules.py
```

PowerShell:

```powershell
$env:APPLY_RULES_BASE = "C:\path\to\profile"
python .\apply_rules.py
```

**Existing destination files are overwritten.** Back up local customization before applying. The installer does not install skills, ARENA.md, or CHATGPT.txt; use their separate setup steps. Do not install this specification as an agent rule.

## Install and load skills (human maintainers)

Installation, updates, and removal are human maintenance, not agent tasks. Agents may inspect available skills but must treat installed copies as read-only, reporting missing or incompatible files rather than installing or repairing them. Requested edits to skill source in this repository do not authorize changes to an agent's installed copies.

Copy complete skill folders into a discovery path your agent supports. Install `agent-handoff` before enabling rules that require it. Keep its folder name and include `references/`, `templates/`, and `scripts/`; copying only `SKILL.md` is not enough. The checker uses Python 3 and the standard library.

For an agent that discovers project skills under `.agents/skills/`, a human maintainer can run:

```bash
mkdir -p .agents/skills
cp -R /path/to/clankers/skills/agent-handoff .agents/skills/
```

### Discovery notes

Paths and precedence are vendor/version-specific. Confirm them with your installed release; these are integration notes, not a runtime probe.

| Agent | Project | Global |
| --- | --- | --- |
| Antigravity for VS Code | `.agents/skills/` or legacy `.agent/skills/` | `~/.gemini/config/skills/` |
| Cline | `.cline/skills/` | `~/.cline/skills/` |
| Kilo Code | `.kilo/skills/` or `.agents/skills/` | `~/.kilo/skills/` |

The Antigravity row covers the VS Code extension only; it does not document Antigravity CLI paths. Keep one active copy unless you have verified precedence. Reload or restart discovery as required. Avoid embedded shell-execution syntax in skills, since execution permissions differ by scope.

For non-Arena agents, after setup ask the agent to load `agent-handoff` and identify its `SKILL.md` and conditional reference paths without opening every supporting file. A missing skill is reported to the user, not self-installed or silently ignored. Without automatic discovery, provide the skill explicitly.

### Skill selection

| Skill | When needed |
| --- | --- |
| [agent-handoff](../skills/agent-handoff/SKILL.md) | Non-Arena agents load the skill; prepare or update documents only at the boundaries it defines |
| [planning](../skills/planning/SKILL.md) | Substantial or materially underspecified work |
| [ponytail](../skills/ponytail/SKILL.md) | Simpler implementations within the user's requirements and existing project conventions |
| [frontend-design](../skills/frontend-design/SKILL.md) | New or substantially redesigned interfaces |
| [web-interface-guidelines](../skills/web-interface-guidelines/SKILL.md) | Reviews of an existing UI against the upstream guidelines |
| [squash](../skills/squash/SKILL.md) | Text that must fit one or more token, word, character, or byte budgets |

### Handoff components

Arena.ai is exempt from `agent-handoff`: no skill loading, canonical handoff, plan-file handoff step, or skill-triggered commit checkpoint. Arena's own atomic commit rules still apply.

For other agents, only `skills/agent-handoff/SKILL.md` belongs in always-loaded context. It states the triggers, essential safety and identity rules, and which component to read. Supporting paths below are relative to `skills/agent-handoff/`:

- `references/protocol.md`: lifecycle, history, sender/receiver procedures, and validation; load when operating on a handoff.
- `templates/AGENT_HANDOFF.md`: load when creating a document, not on routine skill activation.
- `references/examples.md`: load only when an example is useful.
- `scripts/handoff_lint.py`: execute against prepared documents; do not load its source merely to activate the skill.

Acceptance and resumption keep the same transfer ID and append lifecycle events. `BLOCKED` is resumable; only `DONE` is terminal. Superseded evidence stays in the audit sections, not current context. Non-Arena agents with file-backed plan mode must include an explicit handoff-update step in the plan file, not only in chat. Required handoff updates must be committed atomically, even though the core rules also require atomic commits. Commit task work first and the handoff checkpoint separately; report blocked commits rather than claiming a transfer is complete. This grants no push/PR permission.

## Rule maintenance

1. Edit generic behavior in `rules/AGENTS.md`, then preserve its intent in the condensed `rules/ARENA.md`.
2. **Optimize ARENA.md for file size (UTF-8 bytes).** Condense wording and sections, not meaning: keep negations, conditions, commands, numbers, and caveats. Match the generic core semantically, not byte-for-byte. Do not repeat Arena-managed branch or push lifecycle instructions or apply `agent-handoff` to Arena; PR creation stays user-required, as in the core rules.
3. Keep CLINE.md platform-specific. Its command discipline, tool names, and timeout behavior live there; implementation-plan rules delegate to `agent-handoff`. Verify version-specific claims before changing them.
4. Preserve rule-file filename headings. Keep CHATGPT.txt as plain text with inline section labels, not Markdown headings or bullets, within its character budget, and aligned with AGENTS.md where the instruction field allows.
5. Skills may specialize defaults but must not weaken explicit acceptance criteria or replace project conventions. Simpler scope requires approval before substitution. Testing guidance in the reusable rules applies to projects using them, not a test setup for this repository.
6. Keep handoff resources on demand and their relative links valid. Do not move essential boundary or plan-file instructions out of `SKILL.md`.
7. Keep every skill conformant to the [Agent Skills specification](https://agentskills.io/specification): `name` matches its directory, and frontmatter uses only the specified fields. Skills adapted from elsewhere record `metadata.upstream`; refresh them from that source, then re-apply the local `Precedence` section. See [skills/README.md](../skills/README.md#format).
8. Keep this repository lightweight: add no workflows, dependency manifests, or test scaffolding unless explicitly requested. Review changes directly and never claim unperformed checks.

### Formatting

Markdown linting applies only to agent rule files under `rules/`: currently AGENTS.md, ARENA.md, and CLINE.md. ChatGPT instructions and this specification are excluded, as are the root README, skills, references, and templates.

Do not hard-wrap prose. Keep each paragraph, list item, and table row on one line and let the editor soft-wrap; third-party licenses keep their original wrapping.

[.markdownlint-cli2.jsonc](../.markdownlint-cli2.jsonc) keeps file selection, exclusions, and rule settings together: markdownlint defaults, **MD060 enabled** for table-column consistency, and **MD013 disabled** so there is no line-length constraint. MD060 uses its default `any` style. If markdownlint-cli2 is available, run it from the repository root without additional file globs to use this scope. No tooling installation is required.

Python style stays defined in the core rules (Ruff selection E4, E7, E9, F), without a managed Ruff dependency. Keep CHATGPT.txt within 1,500 Unicode characters, including newlines.

## Handoff document checks

The dependency-free handoff checker is part of the skill, for checking prepared documents rather than as a repository test suite:

```bash
python3 skills/agent-handoff/scripts/handoff_lint.py AGENT_HANDOFF.md
```

A zero exit code means automated checks passed, not that a handoff is safe, accurate, or complete. Follow the manual checklist in the [protocol](../skills/agent-handoff/references/protocol.md).
