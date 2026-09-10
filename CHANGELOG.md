# Changelog

Project history, newest first. One entry per pull request, not per feature or commit; extend the open entry while its pull request is unmerged. Historical token tables are snapshots from their entries, using `cl100k_base` via `tiktoken 0.12.0`, not current deployment budgets. See [README.md](README.md#instruction-budgets) for current measurements.

## 2026-09-10 — Document and validate the workflows directory

- The `workflows/` directory is now integrated: a new `workflows/README.md` index describes the portable single-file format and usage; the root README gains a layout bullet and a budget row; the root `AGENTS.md` gains a read-first link, a Workflows section, and updated validator, budget, and lint-scope notes; the rules specification gains a contents row and a Workflows section with a selection table; `maintenance/README.md` describes the new checks.
- `maintenance/check.py` validates the workflows listing against `workflows/README.md`, requires a `description` frontmatter field in each workflow file, checks internal links in the workflows index, and budgets `workflows/init-docs.md` in `cl100k_base` tokens like the other entry files.
- The lightweight-repo rule now prohibits further CI workflows, since `workflows/` holds agent workflows and the old wording read as banning the new directory. No budgeted rule or skill file changed.
- Added a disabled `distribute-arena` workflow template (`.github/workflows/distribute-arena.yml.disabled`, 388 tokens): on manual dispatch it pushes `rules/ARENA.md` to each listed repo's `ARENA.md` over HTTPS with a short-expiry fine-grained PAT stored as `ARENA_DIST_PAT`, amending the prior sync commit when HEAD is one and committing only when the file changed. The default list holds `nemoe7/clankers`, a dispatch input overrides it, and renaming to `.yml` enables the workflow.
- Squashed `workflows/init-docs.md` from 4,153 to 4,102 `tok` (4 passes, -1.2%): merged same-subject bullets, cut filler and restated clauses; headings, order, lists, code blocks, and every rule, condition, and identifier preserved.
- `rules/ARENA.md` gains a handoff clause in Workspace: MUST maintain a handoff document (goal, done, next, key files/decisions), updated as work lands, so work resumes if limits are reached. Squashing cut 140 bytes elsewhere (dropped `As an Arena.ai agent`, `not one sweep`, `without exception`, `Keep architecture`, `one message per logical change`, `re-checking` to `rechecking`, `corrected` to `fixed`, `a commit` to `one`), so the 136-byte clause lands the file at 4,848 against a prior 4,852.

| File | Measure | Change |
| --- | --- | --- |
| `workflows/init-docs.md` | 4,102 `tok` | +4,102 (new; squashed from 4,153) |
| `rules/ARENA.md` | 4,848 `B` | -4 |

## 2026-09-09 — Inline ponytail lite, remove agent-handoff, refresh the guides

- `rules/AGENTS.md` Engineering carries ponytail at `lite` intensity inline: the ladder (needed at all, existing helper/pattern, stdlib, native feature, installed dependency, one line, minimum code), the lite behavior of building what is asked and naming the lazier alternative in one line for the user to pick, the "never lazy about understanding" caveat, the never-simplify list (trust-boundary validation, error handling preventing data loss, security, accessibility), a `simplified:` corner-cut comment, and the no-unrequested-abstraction rules. No rule file loads or names the skill: the corner-cut marker is `simplified:` rather than `ponytail:`, and the rules specification's skill table records that the rules no longer load it. The skill stays in `skills/ponytail/` unchanged, for `full` or `ultra`.
- Deleted the `agent-handoff` skill and every reference to it. `skills/agent-handoff/` (SKILL.md, `references/`, `templates/AGENT_HANDOFF.md`, `scripts/handoff_lint.py`, license) is gone, along with its budget row, its `skills/README.md` and `maintenance/check.py` entries, the rules specification's "Handoff components" and "Handoff document checks" sections, and the handoff clauses in `rules/AGENTS.md`: no mandatory skill load, no handoff read before changes, no handoff updates in plans, no `AGENT_HANDOFF.md` commit exclusion. Planning's own plan-to-implementation "Handoff" phase is unrelated and stays. No rule file now requires loading any skill.
- The root `AGENTS.md` is a repository guide only, independent of any skill or personal rule set: what this repo is, how to verify it, the skill specification, where rule files live, budgets, Markdown and Python style, commit format, and the lightweight-repo constraint. It no longer prescribes a skill loading order, and it requires following this changelog's own entry rule.
- `skills/planning` triggers in plan mode: its `description` says to use it whenever you are in plan mode, and "any work while in plan mode" heads its When to Use list.
- ARENA.md tracks the core again: it gains the ponytail-lite ladder, the never-simplify list, and the `simplified:` corner-cut comment, plus an Arena-specific rule to work in several passes and ask for feedback with the question tool before another round, ending with an open question. Squashing recovered 137 of the 984 bytes added, merging the General, Scope, and Verification bullet lists into paragraphs; the remaining 847 bytes are new rules, so the budget rises from 3,899 to 4,746 bytes rather than dropping a constraint. `rules/AGENTS.md` likewise absorbed 20 of the 58 tokens its commit-list rule added, ending at 1,027 against a prior 989.
- Corrected stale documentation. `maintenance/` is not dependency-free: the root README, the rules specification, and `maintenance/README.md` state that `check.py` requires `markdown-it-py` and `tiktoken`, with an install command. The installer is `rules/apply.py`, not the `apply_rules.py` the docs named. `.github/workflows/validate.yml` exists, so the "no CI workflow" claims are gone and the lightweight rule now reads as "no further workflows". The workflow no longer hardcodes lint globs, leaving `.markdownlint-cli2.jsonc` the single definition of lint scope, and the formatting section no longer excludes a `templates/` directory that no longer exists.
- Every rule file now marks its hard rules with `MUST` and `NEVER` keywords, with bold rationed to exactly two clauses per file so emphasis keeps its meaning: the honesty rule (never claim an unrun check) and the squashed commit list, except CLINE.md, where the two are stopping after a requested command and never self-assigning work. `rules/AGENTS.md` is the core the others follow; ARENA.md, CLINE.md, CHATGPT.txt, and COMMIT_SPEC.txt mirror it. The rules specification records the convention as maintenance rule 5: emphasize the rules that get violated, not merely the important ones, and a third bold clause means demoting another.
- ChatGPT gains ponytail at a "lite lite" intensity: the ladder compressed to `reuse what's here > stdlib/native > installed dep > minimal code`, no dependency for a few lines' work, no unrequested abstraction, build what's asked then name the lazier alternative in one line, and the never-simplify list. Fitting it inside 1,500 characters cost the `Prefer write-block for full markdown` UI note and the `Corrections: error and fix` line, and folded SCOPE's dependency clause into CODE's stronger one.
- ChatGPT's mermaid clause was too permissive and produced diagrams for ordinary lists. It now reads "Mermaid ONLY when structure/flow beats prose, NEVER for lists or decoration", keeping the top-down, short-label, no-wide-row, phone-sized shape constraints. CHATGPT.txt also gains the squashed commit list and the unrun-check prohibition, and was squashed to 1,495 of its 1,500 characters to fit them alongside the ponytail rules.
- The squashed commit list is now unmissable in both rule files, after being ignored in practice. `rules/ARENA.md` opens its Git section with it in bold as a standalone paragraph, and `rules/AGENTS.md` leads its Git list with a MUST bullet. Both state that committing without printing the list is a violation, not an oversight, and that a commit landing unlisted requires printing the corrected timeline before the next one.
- Compression guidance runs to exhaustion: README step 1 repeats passes until a pass yields nothing, matching the `squash` skill's loop.

| File | Measure | Change |
| --- | --- | --- |
| `AGENTS.md` | 659 `tok` | -103 |
| `rules/AGENTS.md` | 1,061 `tok` | -8 |
| `rules/ARENA.md` | 4,852 `B` | +953 |
| `rules/CLINE.md` | 580 `tok` | +7 |
| `rules/CHATGPT.txt` | 1,495 `chars` | -4 |
| `rules/COMMIT_SPEC.txt` | 58 `tok` | +12 |

## 2026-09-09 — Respect global gitignore, never commit handoff

Staging now requires respecting the user's global gitignore (`core.excludesFile`), and `AGENT_HANDOFF.md` is never committed, overriding the `agent-handoff` skill's commit requirement. A minimal root `AGENTS.md` points agents to the README and changelog for compression guidelines. The added clauses raise `rules/AGENTS.md` above its prior budget; compression of the surrounding wording was declined.

| File | Tokens | Change |
| --- | --- | --- |
| `rules/AGENTS.md` | 901 | +41 |

## 2026-09-09 — Always commit, never push

AGENTS.md now makes committing mandatory (atomic, Conventional, off `main`) by folding the push/PR allowance into the commit clause and removing the "only when the user requires it" push/PR permission. Scope: AGENTS.md only. Squashed the commit clause wording with the `squash` skill (`belonging to it` → `in it`, `characters` → `chars`) with no loss of meaning.

| File | Tokens | Change |
| --- | --- | --- |
| `rules/AGENTS.md` | 860 | -9 |

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
