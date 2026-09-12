# Skills

Reusable skills for AI agents. Each skill is a self-contained directory with a `SKILL.md` entry point and any supporting files it loads on demand.

| Skill | Purpose |
| --- | --- |
| [frontend-design](frontend-design/SKILL.md) | Deliberate visual design for new or substantially redesigned interfaces |
| [planning](planning/SKILL.md) | Structured planning for substantial or materially underspecified work |
| [ponytail](ponytail/SKILL.md) | The simplest implementation that meets the requirements |
| [squash](squash/SKILL.md) | Compress text to token, word, character, or byte budgets without losing meaning |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | Review an existing UI against the upstream Vercel Web Interface Guidelines |

## Format

Every skill must conform to the [Agent Skills specification](https://agentskills.io/specification). Validate any skill you add or edit against it.

- `SKILL.md` is required, with YAML frontmatter followed by Markdown instructions.
- `name` is required: 1–64 characters, lowercase letters, digits, and single internal hyphens, and it **must match the directory name**.
- `description` is required: 1–1024 characters covering both what the skill does and when to use it, since agents load only the name and description when deciding whether to activate it.
- Optional fields are `license`, `compatibility`, `metadata`, and `allowed-tools`, except that `license` is required on any skill recording `metadata.upstream`, which the validator enforces. No other top-level keys are allowed; anything else, including `argument-hint`, belongs under `metadata` as a string value.
- Optional directories follow the convention `scripts/`, `references/`, and `assets/`.
- Keep `SKILL.md` under 500 lines and move detail into `references/`, which agents load only when needed.

## Upstream sources

Skills adapted from elsewhere record their origin in `metadata.upstream`. Pull updates from that source, then re-apply the local `Precedence` section, which keeps explicit user requirements and project conventions ahead of the skill's own preferences.

| Skill | Upstream |
| --- | --- |
| [frontend-design](frontend-design/SKILL.md) | [anthropics/skills](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md) |
| [ponytail](ponytail/SKILL.md) | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) |

The remaining skills are first-party and maintained here, marked `metadata.origin`. `web-interface-guidelines` fetches its rules at review time rather than vendoring them, so it stays current without an update pass, and it bundles the upstream MIT license it is adapted under.

## Install

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
| [planning](planning/SKILL.md) | Plan mode, or substantial or materially underspecified work |
| [ponytail](ponytail/SKILL.md) | Not loaded by the rules: the core Engineering section inlines its `lite` intensity. Load the skill only for `full` or `ultra` |
| [frontend-design](frontend-design/SKILL.md) | New or substantially redesigned interfaces |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | Reviews of an existing UI against the upstream guidelines |
| [squash](squash/SKILL.md) | Text that must fit one or more token, word, character, or byte budgets |

Skills are independent of the rule files in [rules/](../rules/) and usable on their own.
