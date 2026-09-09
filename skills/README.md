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
- Optional fields are `license`, `compatibility`, `metadata`, and `allowed-tools`. No other top-level keys are allowed; anything else, including `argument-hint`, belongs under `metadata` as a string value.
- Optional directories follow the convention `scripts/`, `references/`, and `assets/`.
- Keep `SKILL.md` under 500 lines and move detail into `references/`, which agents load only when needed.

## Upstream sources

Skills adapted from elsewhere record their origin in `metadata.upstream`. Pull updates from that source, then re-apply the local `Precedence` section, which keeps explicit user requirements and project conventions ahead of the skill's own preferences.

| Skill | Upstream |
| --- | --- |
| [frontend-design](frontend-design/SKILL.md) | [anthropics/skills](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md) |
| [ponytail](ponytail/SKILL.md) | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) |

The remaining skills are first-party and maintained here, marked `metadata.origin`. `web-interface-guidelines` fetches its rules at review time rather than vendoring them, so it stays current without an update pass and carries no bundled license.

## Install

Copy a skill's whole directory into a discovery path your agent supports; copying only `SKILL.md` is not enough. Installation and selection details are in the [rules specification](../rules/README.md#install-and-load-skills-human-maintainers).

Skills are independent of the rule files in [rules/](../rules/) and usable on their own.
