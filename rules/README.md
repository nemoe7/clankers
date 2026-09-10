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
| [skills/](../skills/README.md) | Reusable skills | Install complete skill directories, including supporting files |
| [workflows/](../workflows/README.md) | Portable agent workflows | Copy the workflow file into your platform's workflow location, or run it as-is |

Rules and tools load differently across agent versions. Verify which files are active in your installed release; never assume a filename alone enables loading. ARENA.md condenses the core because it deploys independently. CLINE.md relies on AGENTS.md also being loaded; if that stops holding, fix installation or deliberately re-embed the core rather than silently losing it.

## Install rules

From the repository root, with Python 3:

```bash
python3 rules/apply.py
```

On Windows, use `python rules\apply.py` or `apply.bat` from the repository root. The script previews unified diffs for changed files, asks once for confirmation, then copies these two files, creating destination directories as needed. Enter `y` or `yes` to apply; any other response aborts. If both destinations are current, it exits without prompting.

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

## Install and load skills (human maintainers)

Installation, updates, and removal are human maintenance, not agent tasks. Agents may inspect available skills but must treat installed copies as read-only, reporting missing or incompatible files rather than installing or repairing them. Requested edits to skill source in this repository do not authorize changes to an agent's installed copies.

Copy complete skill folders into a discovery path your agent supports. Keep the folder name and include any `scripts/`, `references/`, and `assets/`; copying only `SKILL.md` is not enough.

For an agent that discovers project skills under `.agents/skills/`, a human maintainer can run:

```bash
mkdir -p .agents/skills
cp -R /path/to/clankers/skills/planning .agents/skills/
```

### Discovery notes

Paths and precedence are vendor/version-specific. Confirm them with your installed release; these are integration notes, not a runtime probe.

| Agent | Project | Global |
| --- | --- | --- |
| Antigravity for VS Code | `.agents/skills/` or legacy `.agent/skills/` | `~/.gemini/config/skills/` |
| Cline | `.cline/skills/` | `~/.cline/skills/` |
| Kilo Code | `.kilo/skills/` or `.agents/skills/` | `~/.kilo/skills/` |

The Antigravity row covers the VS Code extension only; it does not document Antigravity CLI paths. Keep one active copy unless you have verified precedence. Reload or restart discovery as required. Avoid embedded shell-execution syntax in skills, since execution permissions differ by scope.

After setup, ask the agent to identify an installed skill's `SKILL.md` and conditional reference paths without opening every supporting file. A missing skill is reported to the user, not self-installed or silently ignored. Without automatic discovery, provide the skill explicitly.

### Skill selection

| Skill | When needed |
| --- | --- |
| [planning](../skills/planning/SKILL.md) | Plan mode, or substantial or materially underspecified work |
| [ponytail](../skills/ponytail/SKILL.md) | Not loaded by the rules: the core Engineering section inlines its `lite` intensity. Load the skill only for `full` or `ultra` |
| [frontend-design](../skills/frontend-design/SKILL.md) | New or substantially redesigned interfaces |
| [web-interface-guidelines](../skills/web-interface-guidelines/SKILL.md) | Reviews of an existing UI against the upstream guidelines |
| [squash](../skills/squash/SKILL.md) | Text that must fit one or more token, word, character, or byte budgets |

## Workflows

Workflows are portable across coding-agent platforms: the workflow body depends on no platform-specific tool, agent name, model, provider, UI, permission, or interaction mechanism. Each workflow is one self-contained Markdown file with a `description` frontmatter field, budgeted by UTF-8 file size in the [root README](../README.md#instruction-budgets); format details are in [workflows/README.md](../workflows/README.md).

| Workflow | When needed |
| --- | --- |
| [init-docs](../workflows/init-docs.md) | Initializing or reconciling repository documentation from user-selected templates, in PLAN or APPLY mode |

Installation is human maintenance, not an agent task: copy the workflow file into your platform's workflow location, or run it as-is where the platform accepts a file path. The installer does not deploy workflows. Agents treat installed copies as read-only, reporting problems rather than repairing them.

## Rule maintenance

1. Edit generic behavior in `rules/AGENTS.md`, then preserve its intent in the condensed `rules/ARENA.md`.
2. **Optimize ARENA.md for file size (UTF-8 bytes).** Condense wording and sections, not meaning: keep negations, conditions, commands, numbers, and caveats. Match the generic core semantically, not byte-for-byte. Do not repeat Arena-managed branch or push lifecycle instructions; PR creation stays user-required, as in the core rules.
3. Keep CLINE.md platform-specific. Its command discipline, tool names, and timeout behavior live there. Verify version-specific claims before changing them.
4. Preserve rule-file filename headings. Keep CHATGPT.txt as plain text with inline section labels, not Markdown headings or bullets, within its character budget, and aligned with AGENTS.md where the instruction field allows.
5. **Emphasis is rationed.** Hard rules read as `MUST` or `NEVER`; ordinary guidance stays plain. Bold is reserved for at most two clauses per file, currently the honesty rule and the squashed commit list, so emphasis keeps its meaning. Adding a third bold clause means demoting another. Do not emphasize a rule merely because it is important; emphasize the ones that get violated.
6. Skills may specialize defaults but must not weaken explicit acceptance criteria or replace project conventions. Simpler scope requires approval before substitution. Testing guidance in the reusable rules applies to projects using them, not a test setup for this repository.
7. Keep skill resources on demand and their relative links valid. Do not move essential instructions out of `SKILL.md`.
8. Keep every skill conformant to the [Agent Skills specification](https://agentskills.io/specification): `name` matches its directory, and frontmatter uses only the specified fields. Skills adapted from elsewhere record `metadata.upstream`; refresh them from that source, then re-apply the local `Precedence` section. See [skills/README.md](../skills/README.md#format).
9. Keep this repository lightweight: beyond the existing validation workflow, add no CI workflows, dependency manifests, or test scaffolding unless explicitly requested. Review changes directly and never claim unperformed checks.

### Formatting

Markdown linting applies only to agent rule files under `rules/`: currently AGENTS.md, ARENA.md, and CLINE.md. ChatGPT instructions and this specification are excluded, as are the root README, skills, workflows, and references.

Do not hard-wrap prose. Keep each paragraph, list item, and table row on one line and let the editor soft-wrap; third-party licenses keep their original wrapping.

[.markdownlint-cli2.jsonc](../.markdownlint-cli2.jsonc) keeps file selection, exclusions, and rule settings together: markdownlint defaults, **MD060 enabled** for table-column consistency, and **MD013 disabled** so there is no line-length constraint. MD060 uses its default `any` style. If markdownlint-cli2 is available, run it from the repository root without additional file globs to use this scope; the workflow passes no globs either, so both use this one definition. No tooling installation is required.

Python style stays defined in the core rules (Ruff selection E4, E7, E9, F), without a managed Ruff dependency. Keep CHATGPT.txt within 1,500 Unicode characters, including newlines.
