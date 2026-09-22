# Skills

Reusable skills for AI agents. Each skill is one self-contained directory holding a `SKILL.md` entry point and the supporting files the agent loads when necessary.

| Skill | Purpose |
| --- | --- |
| [arena-preview-steering](arena-preview-steering/SKILL.md) | Steer an Arena agent through the shared preview inbox, with persistent history and receipts |
| [arena-preview-reporting](arena-preview-reporting/SKILL.md) | Publish multiple Markdown reports and portable HTML through the same preview |
| [squash](squash/SKILL.md) | Compress text to token, word, character, or byte budgets without losing meaning |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | Review an existing UI against the upstream Vercel Web Interface Guidelines |

## Format

Every skill must obey the [Agent Skills specification](https://agentskills.io/specification). Check every skill you add or edit against it.

- `SKILL.md` is the entry point. It holds YAML frontmatter and Markdown instructions.
- The `name` field is mandatory. Use 1 to 64 characters: lowercase letters, digits, and single internal hyphens. It must agree with the directory name.
- The `description` field is mandatory. Use 1 to 1024 characters, giving the skill's action and the time to use it. Agents load only the name and description when they select a skill.
- The optional fields are `license`, `compatibility`, `metadata`, and `allowed-tools`. `license` is also mandatory on a skill recording `metadata.upstream`, and the validator enforces that. Use no other top-level keys. Put every other key, such as `argument-hint`, under `metadata` as a string value.
- The optional directories are `scripts/`, `references/`, and `assets/`.
- Keep `SKILL.md` below 500 lines. Move the detail into `references/`, which the agent loads only when necessary.

`skills/refs/<skill>/` holds the full unsquashed source tree for a skill with a baseline. Change the refs tree first, then squash its `SKILL.md` into the live `skills/<skill>/SKILL.md`. Supporting files stay unsquashed in refs and become compressed or minified in live. Refs carry no budget, and no install or distribution includes them. `squash` and the two preview skills have refs baselines. `web-interface-guidelines` has none.

## Upstream sources

A skill adapted from another source records its origin in `metadata.upstream`. Pull updates from that source, then apply the local `Precedence` section again. That section keeps explicit user requirements and project conventions ahead of the skill's preferences.

| Skill | Upstream |
| --- | --- |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) |

The remaining skills are first-party, and this repository maintains them. `squash` and the two preview skills mark `metadata.origin`. `web-interface-guidelines` fetches its rules at review time instead of vendoring them, so it stays current with no update pass. It also bundles the upstream MIT license its adaptation uses.

## Install

Installation, updates, and removal are human maintenance, not agent tasks. Agents can examine the available skills but must treat an installed copy as read-only. Report a missing or incompatible file. Do not install or repair it. A request to edit the skill source here gives no authority to change an agent's installed copies.

Copy the full skill folders into a discovery path your agent supports. Keep the folder name and include the `scripts/`, `references/` and `assets/` directories. A copy of `SKILL.md` alone is insufficient.

A human maintainer with an agent that finds project skills under `.agents/skills/` can run:

```bash
mkdir -p .agents/skills
cp -R /path/to/clankers/skills/squash .agents/skills/
```

### Discovery notes

Paths and precedence change with the vendor and version. Check them against your installed release. These are integration notes, not a runtime probe.

| Agent | Project | Global |
| --- | --- | --- |
| Antigravity for VS Code | `.agents/skills/` or legacy `.agent/skills/` | `~/.gemini/config/skills/` |
| Cline | `.cline/skills/` | `~/.cline/skills/` |
| Kilo Code | `.kilo/skills/` or `.agents/skills/` | `~/.kilo/skills/` |

The Antigravity row covers the VS Code extension only and gives no path for the Antigravity CLI. Keep one active copy unless you check precedence first. Reload or restart discovery as necessary. Use no embedded shell-execution syntax in a skill, because execution permissions differ by scope.

After setup, ask the agent to name the `SKILL.md` of an installed skill and its conditional reference paths, without reading every supporting file. Report a missing skill to the user. Do not install it, and do not ignore it in silence. Where no automatic discovery exists, give the skill explicitly.

### Skill selection

| Skill | When needed |
| --- | --- |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | Reviews of an existing UI against the upstream guidelines |
| [squash](squash/SKILL.md) | Text that must fit one or more token, word, character, or byte budgets |
| [arena-preview-steering](arena-preview-steering/SKILL.md) | Arena sessions needing mid-turn messages through the live preview |
| [arena-preview-reporting](arena-preview-reporting/SKILL.md) | Longer rendered reports, multiple reports or portable HTML delivery in Arena |

Skills stand alone, independent of the rule files in [rules/](../rules/). This repository installs the two preview skills as siblings, and reporting uses the shared runtime of steering. Steering alone needs no Markdown renderer. Their migration reference records the former ntfy and local-report-commit procedures as historical, and neither is an automatic fallback.
