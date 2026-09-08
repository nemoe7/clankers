# Changelog

Project history, newest first. Historical token tables are snapshots from their entries, using `cl100k_base` via `tiktoken 0.12.0`; they are not current deployment budgets. See [README.md](README.md#instruction-budgets) for current primary measurements.

## 2026-09-08 — Preview rule installs and license shared skills

- The rule installer now previews unified diffs and asks once before changing either destination.
- Planning and agent-handoff now include MIT license files; planning also declares its license in skill metadata.
- Response rules now prefer numbered lists when presenting multiple points.
- Agents may commit without separate authorization when commits are atomic, conventional, task-only, and off `main`; ChatGPT retains explicit authorization because its integration writes directly to `main`.
- Arena keeps open-PR history reviewable by folding iterative fixes when safe and using lease-protected remote rewrites.
- Generic rules always load `agent-handoff` and select other skills when their domains fit; Arena and Cline contain no handoff-specific policy.
- Skills no longer contain platform-specific exemptions or cross-skill planning requirements.
- Agent-handoff references now call it a skill and use `SKILL.md` only as its filename.
- The root README tracks all agent rule and skill entry files, using deployment-specific measures for Arena and ChatGPT and tokens for the rest.

## 2026-09-08 — Exclude Arena from agent handoff

Arena no longer loads or applies agent-handoff, including its plan-file steps and commit checkpoints. The exemption is explicit in the shared rules, Arena rules, skill discovery/entry point, protocol, planning integration, and specification. Arena still makes atomic commits when requested. Other agents retain the handoff workflow.

| File | Tokens | Change |
| --- | --- | --- |
| `rules/AGENTS.md` | 923 | +6 |
| `rules/ARENA.md` | 818 | -10 |
| `skills/agent-handoff/SKILL.md` | 873 | +39 |
| `skills/planning/SKILL.md` | 910 | +7 |

## 2026-09-08 — Compact Arena rules and atomic handoffs

- Optimized ARENA.md from 6,254 to 3,912 UTF-8 bytes (37.4% smaller), preserving core intent and removing platform-managed branch/push/PR boilerplate. The rules specification now makes file size its maintenance target.
- AGENTS.md forbids committing to main without requiring a fresh branch. Removed the redundant ChatGPT GitHub-header parenthetical.
- Moved implementation_plan.md conventions from the generic planning skill to Cline; generic file-backed plans still require a handoff-update step.
- Required atomic commits for task work and handoff checkpoints, with separate work/hand-off commit identities and explicit reporting of blocked commits.

| File | Tokens | Change |
| --- | --- | --- |
| `rules/AGENTS.md` | 917 | -26 |
| `rules/ARENA.md` | 828 | -481 |
| `rules/CHATGPT.txt` | 292 | -7 |
| `rules/CLINE.md` | 752 | +127 |
| `skills/agent-handoff/SKILL.md` | 834 | +73 |
| `skills/planning/SKILL.md` | 903 | -128 |

## 2026-09-08 — Installed skills are read-only

Moved installation guidance to the human-facing rules specification. Agents report missing or incompatible skills instead of changing their installed copies. Only changed instruction files are listed.

| File | Tokens | Change |
| --- | --- | --- |
| `rules/AGENTS.md` | 943 | +35 |
| `rules/ARENA.md` | 1,309 | +35 |
| `skills/agent-handoff/SKILL.md` | 761 | +33 |

## 2026-09-08 — Initial snapshot

Only agent-facing rule files and `SKILL.md` entry points are tracked. Documentation, supporting references and templates, scripts, configs, and licenses are excluded. Counts do not include any additional files a skill loads on demand.

| File | Tokens |
| --- | --- |
| `rules/AGENTS.md` | 908 |
| `rules/ARENA.md` | 1,274 |
| `rules/CHATGPT.txt` | 299 |
| `rules/CLINE.md` | 625 |
| `rules/COMMIT_SPEC.txt` | 46 |
| `skills/agent-handoff/SKILL.md` | 728 |
| `skills/frontend-design/SKILL.md` | 1,058 |
| `skills/planning/SKILL.md` | 1,031 |
| `skills/ponytail/SKILL.md` | 1,596 |
| `skills/web-design-guidelines/SKILL.md` | 287 |
