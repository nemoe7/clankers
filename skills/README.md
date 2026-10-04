# Skills

Each reusable AI skill is a self-contained directory with a `SKILL.md` entry point and supporting files loaded on demand.

| Skill | Purpose |
| --- | --- |
| [amending-violations](amending-violations/SKILL.md) | Amend a rule after a violation, with the guidelines for a rule file and the repository's proposal form |
| [arena-proxy](arena-proxy/SKILL.md) | Read privileged data outside an Arena sandbox through an owner-run backend that holds the credentials |
| [arena-preview-steering](arena-preview-steering/SKILL.md) | Steer an Arena agent through the shared preview inbox and publish rendered reports, with persistent history and receipts |
| [squash](squash/SKILL.md) | Compress text to token, word, character, or byte budgets without losing meaning |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | Review an existing UI against the upstream Vercel Web Interface Guidelines |

## Format

Every skill must follow the [Agent Skills specification](https://agentskills.io/specification). Check each added or edited skill.

- `SKILL.md` is the entry point. It holds YAML frontmatter and Markdown instructions.
- Required `name`: 1 to 64 lowercase letters, digits, or single internal hyphens, matching the directory name.
- Required `description`: 1 to 1024 characters stating the action and when to use it. Agents select skills from name and description alone.
- Optional fields: `license`, `compatibility`, `metadata`, and `allowed-tools`. The validator requires `license` with `metadata.upstream`. No other top-level keys: put others, such as `argument-hint`, under `metadata` as strings.
- The optional directories are `scripts/`, `references/`, and `assets/`.
- Keep `SKILL.md` below 500 lines. Move the detail into `references/`, which the agent loads only when necessary.
- A skill carries only what an agent needs to use it. Leave background, rationale and history to the changelog.

`skills/refs/<skill>/` holds full uncompressed baseline trees for skills that have baselines. See [maintenance/README.md](../maintenance/README.md) for source/live synchronization.

## Upstream sources

Adapted skills record `metadata.upstream`. Update from that source, then reapply local `Precedence`: explicit user requirements and project conventions outrank skill preferences.

| Skill | Upstream |
| --- | --- |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) |

This repository maintains the other, first-party skills. `squash` and the preview skill record `metadata.origin`. `web-interface-guidelines` fetches current rules at review time, without vendoring or an update pass, and includes the upstream MIT license.

## Install

Humans install, update, and remove skills. Agents may inspect installed copies but must treat them as read-only. Report missing or incompatible files, never install or repair them. Source-edit requests here do not authorize installed-copy changes.

Copy whole skill folders into a supported discovery path. Keep their names, `scripts/`, `references/`, and `assets/`. `SKILL.md` alone is insufficient.

With an agent that finds project skills under `.agents/skills/`, run:

```bash
mkdir -p .agents/skills
cp -R /path/to/clankers/skills/squash .agents/skills/
```

### Discovery notes

Check each path and its precedence against your installed release.

| Agent | Project | Global |
| --- | --- | --- |
| Antigravity for VS Code | `.agents/skills/` or legacy `.agent/skills/` | `~/.gemini/config/skills/` |
| Cline | `.cline/skills/` | `~/.cline/skills/` |
| Kilo Code | `.kilo/skills/` or `.agents/skills/` | `~/.kilo/skills/` |

The Antigravity row covers VS Code, not the CLI. Keep one active copy unless you first check precedence. Reload or restart discovery as necessary. Do not embed shell-execution syntax: permissions differ by scope.

After setup, ask the agent to name an installed `SKILL.md` and its conditional reference paths without reading all supporting files. Report missing skills, never install or silently ignore them. Supply skills explicitly without automatic discovery.

### Skill selection

| Skill | When needed |
| --- | --- |
| [arena-proxy](arena-proxy/SKILL.md) | Read-only access to a source the sandbox cannot reach, such as code scanning alerts or run logs |
| [web-interface-guidelines](web-interface-guidelines/SKILL.md) | Reviews of an existing UI against the upstream guidelines |
| [squash](squash/SKILL.md) | Text that must fit one or more token, word, character, or byte budgets |
| [arena-preview-steering](arena-preview-steering/SKILL.md) | Arena sessions needing mid-turn messages or rendered reports through the live preview |

Skills stand alone, independent of the rule files in [rules/](../rules/).

## Maintenance

See [maintenance/README.md](../maintenance/README.md) for skill synchronization, validation, and generated-copy maintenance.
