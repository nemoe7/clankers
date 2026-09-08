# Changelog

Project history, newest first. One entry per pull request, not per feature or commit; extend the open entry while its pull request is unmerged. Historical token tables are snapshots from their entries, using `cl100k_base` via `tiktoken 0.12.0`, not current deployment budgets. See [README.md](README.md#instruction-budgets) for current measurements.

## 2026-09-08 — Gate pull requests, add mermaid guidance, and document compression

- Pull requests open only when the user requires it; commits still follow the atomic Conventional Commit rules. Arena also outputs a squashed commit list before committing: local commits and fixes folded into a clean timeline, updated as work lands.
- Generic rules call for a mermaid diagram when structure or flow beats prose and the surface renders it, shaped for a narrow viewport: top-down, short labels, no wide rows. ARENA.md excludes mermaid because Arena cannot render it; CHATGPT.txt keeps its guidance in the same wording.
- CHATGPT.txt mirrors AGENTS.md structure with a SCOPE section, within its 1,500-character limit.
- ARENA.md no longer restates that platform instructions take precedence; Arena applies them regardless.
- The root README documents the compression procedure beside the budgets it maintains: iterate and re-measure, never drop a constraint, keep headings, and compress the rest of a file when a new rule exceeds its budget.
- Generic rules require repository hygiene: scratch files, scripts, and command output stay outside the repo or are deleted once used. CLINE.md drops its duplicate; Arena relies on its workspace-size rules, and ChatGPT is out of scope.
- Added the `squash` skill: general-purpose iterative text compression against a chosen unit, tokens, words, characters, or bytes, preserving every claim, negation, condition, number, name, and caveat. It resolves the unit by an explicit precedence, accepts several budgets at once as simultaneous constraints, and records that units do not move together, so every governing unit is re-measured each pass and conflicts are reported rather than silently resolved. Its description triggers on requests to size specific text, not on bare words like "shorten" or "trim". It is standalone and does not depend on this repository's rules.
- Added `skills/README.md` listing every skill and its purpose, so the rules specification links to a skills index instead of a bare directory.
- Refreshed frontend-design and ponytail from their upstream sources, re-applying the local `Precedence` section that keeps explicit requirements and project conventions ahead of each skill's preferences.
- Skills adapted from elsewhere now record `metadata.upstream`, and first-party skills record `metadata.origin`, so updates can be pulled from the right place. `skills/README.md` documents the specification requirements and lists every upstream, and the rules specification requires conformance.
- ponytail bundles the MIT license it declares, attributed to its upstream author.
- All six skills now validate against the Agent Skills specification. `argument-hint` is not a specified frontmatter field, so ponytail and squash move it under `metadata`, where web-design-guidelines already kept it.
- Renamed `web-design-guidelines` to `web-interface-guidelines` to match its upstream name, and rewrote it against the current upstream command: it names the full rule coverage rather than implying an accessibility-only review, adopts the terse `file:line` output format, explains that the fetched file is a slash command whose `$ARGUMENTS` placeholder does not apply, and stops instead of reviewing from memory when the fetch fails.
- Squashed this changelog and rules/README.md with that skill: wording only, with every claim, number, and table preserved. Before adding the entries below, they measured 1,413 → 1,392 and 2,242 → 2,218 tokens.
- Rule and skill files are no longer hard-wrapped; each paragraph and list item is one line. Licenses keep their original wrapping.
- Compressed to absorb the new rules: AGENTS.md 893 → 869 tokens, CLINE.md 625 → 573 tokens, ARENA.md 3,906 → 3,899 bytes. CHATGPT.txt grew from 1,446 to 1,499 of its 1,500 characters, since the added SCOPE section outweighed the wording it recovered.

## 2026-09-08 — Preview rule installs and license shared skills

- The rule installer previews unified diffs and asks once before changing either destination.
- Planning and agent-handoff include MIT license files; planning also declares its license in skill metadata.
- Response rules prefer numbered lists for multiple points.
- Agents may commit without separate authorization when commits are atomic, conventional, task-only, and off `main`; ChatGPT still requires it because its integration writes directly to `main`.
- Arena keeps open-PR history reviewable by folding iterative fixes when safe and using lease-protected rewrites.
- Generic rules always load `agent-handoff` and select other skills when their domains fit; Arena and Cline hold no handoff-specific policy.
- Skills contain no platform-specific exemptions or cross-skill planning requirements.
- Agent-handoff references call it a skill and use `SKILL.md` only as its filename.
- The root README tracks all agent rule and skill entry files, using deployment-specific measures for Arena and ChatGPT, tokens for the rest.

## 2026-09-08 — Exclude Arena from agent handoff

Arena no longer loads or applies agent-handoff, including its plan-file steps and commit checkpoints. The exemption is explicit in the shared rules, Arena rules, skill discovery/entry point, protocol, planning integration, and specification. Arena still makes atomic commits when requested; other agents retain the handoff workflow.

| File | Tokens | Change |
| --- | --- | --- |
| `rules/AGENTS.md` | 923 | +6 |
| `rules/ARENA.md` | 818 | -10 |
| `skills/agent-handoff/SKILL.md` | 873 | +39 |
| `skills/planning/SKILL.md` | 910 | +7 |

## 2026-09-08 — Compact Arena rules and atomic handoffs

- Optimized ARENA.md from 6,254 to 3,912 UTF-8 bytes (37.4% smaller), preserving core intent and removing platform-managed branch/push/PR boilerplate. The rules specification makes file size its maintenance target.
- AGENTS.md forbids committing to main without requiring a fresh branch. Removed the redundant ChatGPT GitHub-header parenthetical.
- Moved implementation_plan.md conventions from the generic planning skill to Cline; generic file-backed plans still require a handoff-update step.
- Required atomic commits for task work and handoff checkpoints, with separate work/handoff commit identities and explicit reporting of blocked commits.

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

Only agent-facing rule files and `SKILL.md` entry points are tracked. Documentation, supporting references and templates, scripts, configs, and licenses are excluded. Counts exclude files a skill loads on demand.

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
