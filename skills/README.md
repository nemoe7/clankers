# Skills

Reusable skills for AI agents. Each skill is a self-contained directory with a `SKILL.md` entry point and any supporting files it loads on demand.

| Skill | Purpose |
| --- | --- |
| [arena-live-steering](arena-live-steering/SKILL.md) | Steer a running Arena agent from a DNS TXT record without interrupting its turn |
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
- A skill may carry `BASELINE.md`, the unsquashed original of its `SKILL.md`. Amend the baseline first, then squash it into `SKILL.md` and re-measure that entry point against its budget; the baseline itself carries no budget. `squash` is the first skill to use one, mirroring the way `rules/refs/` holds the rule originals.

## Upstream sources

Skills adapted from elsewhere record their origin in `metadata.upstream`. Pull updates from that source, then re-apply the local `Precedence` section, which keeps explicit user requirements and project conventions ahead of the skill's own preferences.

| Skill | Upstream |
| --- | --- |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) |

The remaining skills are first-party and maintained here; `squash` marks `metadata.origin`, and `arena-live-steering` does not carry that marker yet. `web-interface-guidelines` fetches its rules at review time rather than vendoring them, so it stays current without an update pass, and it bundles the upstream MIT license it is adapted under.

## Install

Installation, updates, and removal are human maintenance, not agent tasks. Agents may inspect available skills but must treat installed copies as read-only, reporting missing or incompatible files rather than installing or repairing them. Requested edits to skill source in this repository do not authorize changes to an agent's installed copies.

Copy complete skill folders into a discovery path your agent supports. Keep the folder name and include any `scripts/`, `references/`, and `assets/`; copying only `SKILL.md` is not enough.

For an agent that discovers project skills under `.agents/skills/`, a human maintainer can run:

```bash
mkdir -p .agents/skills
cp -R /path/to/clankers/skills/squash .agents/skills/
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
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | Reviews of an existing UI against the upstream guidelines |
| [squash](squash/SKILL.md) | Text that must fit one or more token, word, character, or byte budgets |
| [arena-live-steering](arena-live-steering/SKILL.md) | Arena sessions that need steering from outside the client, mid-turn and without an interrupt |

Skills are independent of the rule files in [rules/](../rules/) and usable on their own.
