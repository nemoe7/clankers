# Skills

Reusable skills for AI agents. Each skill is a self-contained directory. It holds a `SKILL.md` entry point and the supporting files that the agent loads when necessary.

| Skill | Purpose |
| --- | --- |
| [arena-preview-steering](arena-preview-steering/SKILL.md) | Steer an Arena agent through the shared preview inbox, with persistent history and receipts |
| [arena-preview-reporting](arena-preview-reporting/SKILL.md) | Publish multiple Markdown reports and portable HTML through the same preview |
| [squash](squash/SKILL.md) | Compress text to token, word, character, or byte budgets without losing meaning |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | Review an existing UI against the upstream Vercel Web Interface Guidelines |

## Format

Every skill must obey the [Agent Skills specification](https://agentskills.io/specification). Check every skill that you add or edit against it.

- `SKILL.md` is the entry point. It holds YAML frontmatter and Markdown instructions.
- You must give the `name` field. Use 1 to 64 characters: lowercase letters, digits, and single internal hyphens. The name must agree with the directory name.
- You must give the `description` field. Use 1 to 1024 characters. The text must give the action of the skill and the time to use it. Agents load only the name and the description when they select a skill.
- The optional fields are `license`, `compatibility`, `metadata`, and `allowed-tools`. The `license` field is also mandatory on a skill that records `metadata.upstream`. The validator enforces that rule. Do not use other top-level keys. Put every other key, such as `argument-hint`, under `metadata` as a string value.
- The optional directories are `scripts/`, `references/`, and `assets/`.
- Keep `SKILL.md` below 500 lines. Move the detail into `references/`, which the agent loads only when necessary.

`skills/refs/<skill>/` holds the full unsquashed source tree for a skill with a baseline. Change the refs tree first. Then squash its `SKILL.md` into the live `skills/<skill>/SKILL.md`. The supporting files stay unsquashed in refs and become compressed or minified in live. Refs carry no budget. No install or distribution includes them. `squash`, the two preview skills and `web-interface-guidelines` have refs baselines.

## Upstream sources

A skill that you adapt from another source records its origin in `metadata.upstream`. Pull the updates from that source. Then apply the local `Precedence` section again. That section keeps explicit user requirements and project conventions ahead of the preferences of the skill.

| Skill | Upstream |
| --- | --- |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) |

The remaining skills are first-party, and this repository maintains them. `squash` and the two preview skills mark `metadata.origin`. `web-interface-guidelines` fetches its rules at review time instead of vendoring them. So it stays current with no update pass. It also bundles the upstream MIT license that its adaptation uses.

## Install

Installation, updates, and removal are human maintenance, not agent tasks. Agents can examine the available skills. An agent must treat an installed copy as read-only. Report a missing or incompatible file. Do not install or repair it. A request to edit the skill source in this repository gives no authority for a change to the installed copies of an agent.

Copy the full skill folders into a discovery path that your agent supports. Keep the folder name. Include the `scripts/`, `references/`, and `assets/` directories. A copy of `SKILL.md` alone is insufficient.

A human maintainer with an agent that finds project skills under `.agents/skills/` can run:

```bash
mkdir -p .agents/skills
cp -R /path/to/clankers/skills/squash .agents/skills/
```

### Discovery notes

Paths and precedence change with the vendor and the version. Check them against your installed release. These notes are integration notes, not a runtime probe.

| Agent | Project | Global |
| --- | --- | --- |
| Antigravity for VS Code | `.agents/skills/` or legacy `.agent/skills/` | `~/.gemini/config/skills/` |
| Cline | `.cline/skills/` | `~/.cline/skills/` |
| Kilo Code | `.kilo/skills/` or `.agents/skills/` | `~/.kilo/skills/` |

The Antigravity row covers the VS Code extension only. It gives no path for the Antigravity CLI. Keep one active copy unless you check precedence first. Reload or restart discovery as necessary. Do not use embedded shell-execution syntax in a skill, because execution permissions differ by scope.

After the setup, ask the agent to name the `SKILL.md` of an installed skill and its conditional reference paths. The agent must do this without a read of every supporting file. Report a missing skill to the user. Do not install it, and do not ignore it in silence. If no automatic discovery is available, give the skill explicitly.

### Skill selection

| Skill | When needed |
| --- | --- |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | Reviews of an existing UI against the upstream guidelines |
| [squash](squash/SKILL.md) | Text that must fit one or more token, word, character, or byte budgets |
| [arena-preview-steering](arena-preview-steering/SKILL.md) | Arena sessions needing mid-turn messages through the live preview |
| [arena-preview-reporting](arena-preview-reporting/SKILL.md) | Longer rendered reports, multiple reports or portable HTML delivery in Arena |

Skills are independent of the rule files in [rules/](../rules/). This repository installs the two preview skills as siblings. Reporting uses the shared runtime of steering. Steering alone needs no Markdown renderer. Their migration reference records the former ntfy and local-report-commit procedures as historical. Those procedures are not an automatic fallback.
