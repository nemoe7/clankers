# Changelog

Project history, newest first. One entry per pull request, not per feature or commit; extend the open entry while its pull request is unmerged. Historical token tables are snapshots from their entries, using `cl100k_base` via `tiktoken 0.12.0`, not current deployment budgets. See [README.md](README.md#instruction-budgets) for current measurements.

## 2026-09-12 — Apply the September amendment set across the rule files

- `rules/CHATGPT.txt` takes amendments 1, 2, 3, 5, 6, and 8 inside its hard 1,500-character field limit: RESPONSE avoids unnecessary prose while allowing detail when the task requires it or the user asks (replacing `NEVER filler or essays`) and makes Mermaid the default for pipelines/diagrams/flow with `flowchart TB`, short labels, and no wide rows; SCOPE now reads as only the requested work plus work strictly necessary to implement/verify and gates tests with `NEVER add tests unless requested/needed to verify`; CODE names a lazier alternative in one line only when relevant; GITHUB prints the planned final commit list instead of the squashed one. Squash passes measured the faithful all-eight draft at 2,003 → 1,745 → 1,668 characters against a 1,494 prior measurement, funded by comma-to-slash lists, the illustrative filler enumeration that amendment 1 replaces, and `when practical` folded into SCOPE's new test gate. It ships at 1,494 characters, equal to its prior measurement, with no existing rule deleted.
- Amendments 4 and 7 (material ambiguity defined as reasonable readings that could change behavior/data/interfaces/scope/outcome; non-material ambiguity resolved by the most reasonable assumption, stated when it materially affects the result) cost 157 characters, so they are deferred from `rules/CHATGPT.txt`, which keeps `Ask only on material ambiguity.`; both are applied in full in `rules/AGENTS.md`, `rules/ARENA.md`, and their refs. Add them to ChatGPT when roughly 160 characters free up.
- `rules/AGENTS.md` gains the Arena clause (in Arena, MUST also read and follow the repo's `ARENA.md` as an additional ruleset; it supplements, NEVER replaces, AGENTS.md) plus the generally applicable amendments: strictly-necessary scope, the test gate, the material-ambiguity definition and non-material assumption rule, the relevance-conditioned lazier alternative, Mermaid by default for pipelines/diagrams/flow where the surface renders it, and `no unnecessary prose; detail when the task or user requires`. An eight-cut squash pass (`over silent trims`, `implement/verify it`, slashed ambiguity lists, `a relevant lazier alternative`, `say why inapplicable`, `Default to mermaid`) recovered 18 of the 112 added tokens; 1,263 → 1,357 `tok`. The rest is requested content: the only funding left is illustrative examples (the unrequested-abstraction and runnable-check parentheticals) or rules, so the budget rises rather than dropping a constraint.
- `rules/ARENA.md` mirrors those amendments and adds the two Arena-only clauses: Verification now requires stating a question batch's total before asking, labeling questions Q1, Q2, and on, NEVER adding one without restating the total, and ending the multi-question block with an open prompt (`Any more questions?`, `Anything else?`); Response now requires reporting the changes made in the final response after the task at a suitable high level (`X now does Y`), especially after long or multi-step tasks, and not during execution. Git's bold clause now reads `print the planned final commit list`, keeping bold at two clauses per file. Mermaid stays banned here because Arena cannot render it, so amendment 8 applies to `rules/CHATGPT.txt` and the generic core only. Squashing recovered 225 of the 758 added bytes (the `silent edit` rationale and four cache-dir examples, originals kept in refs; the final-response duty folded into the existing report sentence; tightened dependency-approval, PR-title, and generated-section wording); 7,544 → 8,077 `B`, the residual being requested content at the audited floor.
- Root `ARENA.md` is re-copied from `rules/ARENA.md` and stays byte-identical, matching what `.github/workflows/distribute-arena.yml` pushes to target repos.
- `rules/refs/` was amended first per the Baselines rule: `refs/AGENTS.md`, `refs/ARENA.md`, and `refs/CHATGPT.txt` hold the full uncompressed wording of every clause that landed live, including `before committing` and `no unnecessarily wide rows` where the live ChatGPT file compresses to `first` and `no wide rows`. `refs/CHATGPT.txt` omits amendments 4 and 7 so the baseline keeps mirroring its live file; their full wording lives in `refs/AGENTS.md` and `refs/ARENA.md`.
- `rules/README.md` renames the printed list in the Emphasis note and the commit-disciplines table (`Print the planned final commit list before committing`, `before every commit`, and `no commit list` for the core) so the specification stays truthful about amendment 6. `rules/CLINE.md`, `rules/COMMIT_SPEC.txt`, and root `AGENTS.md` are untouched: the overlay is platform-specific, the commit spec carries no list rule, and the Arena clause belongs to the distributed core by decision.
- Budget funding pass after review: `rules/AGENTS.md` drops the illustrative unrequested-abstraction examples (one-implementation interface, one-product factory, config for a constant) and the runnable-check parenthetical (assert-based demo or one small test file); `rules/ARENA.md` and root `ARENA.md` drop the criticism rationale (`docs may be stale; code may be wrong`) and the `(tables from fixtures)` example. Every cut removes illustration only, keeping its rule and full wording in `rules/refs/`. 1,357 → 1,334 `tok` and 8,077 → 8,016 `B`; root `ARENA.md` re-copied and still byte-identical. The residual over prior (1,263 `tok`, 7,544 `B`) is requested amendment content: the remaining candidates are one restated clause (`Python: Ruff defaults (E4, E7, E9, F)`, ~12 `tok`, restated by the `ruff.toml` spec in the same section) and two deterrents strengthened on purpose in earlier rounds (`Committing without printing it is a violation, not an oversight`, and the `-f` war story kept per direction), so they were left alone.
- Style specs reordered on request: the `ruff.toml` specification now reads Ruff defaults first, then `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, keeping the `required-version = "0.16.6"` pin at the end of the list, in `rules/AGENTS.md`, `rules/ARENA.md`, root `ARENA.md`, and both refs (`rules/refs/ARENA.md` folds its separate pin sentence into the list). Markdownlint specs stay `defaults + MD060, MD013 off` (ARENA also `reports MD013 120`): naming MD007 was tried and reverted because MD007's `indent` parameter already defaults to 2, so the explicit pin in `.markdownlint-cli2.jsonc` and any spec mention are both redundant. `ruff.toml` and `.markdownlint-cli2.jsonc` are unchanged. `rules/CHATGPT.txt` keeps its FORMAT line, which already opens with `2-space indent`. 1,334 → 1,335 `tok` and 8,016 → 8,017 `B`.
- `rules/refs/GUIDELINES.md` is new: the user's `Guidelines: writing an AGENTS.md` saved verbatim as the audit standard for everything in `rules/refs/`, with no provenance header (no URL, no retrieval date) per direction. Nine sections: what AGENTS.md is, the threat model (compaction, dilution, contradiction, staleness), structure, rules that survive, precedence and scope, size and economy, lint and test, a skeleton, and a checklist. It is a reference, not a rule baseline: no live counterpart, never squashed. Indexed in `rules/refs/README.md`, `rules/README.md` (contents table and Baselines), root `README.md`, and root `AGENTS.md`'s read-first list; markdownlint now lints 8 files with 0 issues.
- The refs workflow is clarified on request and documented where it contradicted itself: amendments are written to `rules/refs/` first, the amended baseline is then copied onto its corresponding live file, that live copy is squashed back under budget, and refs stay unsquashed as the baseline. This replaces `amend refs and the live rule together` in `rules/README.md` maintenance item 10 and Baselines, and is stated in `rules/refs/README.md`, root `AGENTS.md` (Rules), and root `README.md` (refs bullet and Compression).
- `rules/refs/AGENTS.md` audited against those guidelines and restructured to their skeleton: a leading `## Use` (what the file is, that it covers all code, agents, and sessions, that it outranks skill and plugin instructions, that an explicit user instruction in chat outranks it, and the Arena clause now naming `ARENA.md`'s handling of pushing and pull requests as the collision winner), a 9-rule `## Constitution` restating existing rules one per line against compaction with no new rule invented, and a closing `## When in doubt` (smallest change that holds; stop and ask on a rule collision, a plan deviation, or material ambiguity). The skills-precedence and Arena clauses moved out of `## General` into `## Use` so neither is stated twice in different words. 63 → 97 lines, inside the guidelines' ~200-line ceiling.
- Guideline 4.1 (one rule per line): `Debugging`, `Testing`, and `Code style` reflowed from paragraphs to bullets in refs and live, and live `Review` reflowed to match its refs bullets. The stray blank line that split `Engineering` into two lists is fixed in both.
- Guideline 4.7 (positive phrasing): non-dangerous negations rewritten positively in refs and live — `NEVER proactively refactor, optimize, redesign, rename, reformat, or change a dependency or error handling/security` becomes only-when-the-task-requires-it, `NEVER add tests unless requested` becomes add tests only when requested or needed to verify, `NEVER hunt alternatives past a suitable pattern, speculate ... or replan without new evidence` becomes stop at a suitable pattern, skip unrelated requirements and edge cases, replan only on new evidence, `NEVER an unrequested abstraction, boilerplate, or scaffolding` becomes add them only for a tangible present need, `NEVER unrelated or user-owned` becomes leaving unrelated and user-owned files unstaged, `Never commit or abandon them` becomes left out of every commit, and `Never repeat the task` becomes open with the result. NEVER stays on the irreversible, dangerous, and honesty rules: a dependency for a few lines' work, simplifying away trust-boundary validation, data-loss error handling, security, or accessibility, inventing an API or constraint, an arbitrary fallback, a hidden failure, an unrevised assumption, weakening or dropping a test, claiming a check not run, and pushing or opening a PR unasked. `rules/README.md`'s Emphasis note and `rules/refs/README.md`'s marker sentence now record that split.
- Budget: the live cascade costs `## Use` +64 `tok`, the 9-rule Constitution +153, and `## When in doubt` +44, and the one-rule-per-line reflow costs 45 more; a lossless squash pass (tightened Use and Constitution wording) recovered 9. 1,335 → 1,632 `tok`, accepted after the squash attempts per direction, since the only remaining funding is the constitution's deliberate redundancy (~150 `tok`, guideline 3.1), the illustrative parentheticals already cut in this pull request's funding pass, or rules the amendments added. Trimming the constitution to 7 rules (-35 `tok`) or restoring those parentheticals are the named follow-ups. `rules/ARENA.md` stays 8,017 `B` and `rules/CHATGPT.txt` stays 1,494 `chars`.
- Held this round per direction: `rules/refs/ARENA.md` already has `## Use` and needs only a Constitution and a `When in doubt` closer (byte cost to be quoted before it lands), and `rules/refs/CLINE.md` as an overlay needs a scope line and a closer; both wait until the core's shape settles. `rules/CHATGPT.txt` cannot take the skeleton inside its hard 1,500-character field limit. ASD-STE100 linting in CI (guideline 7.1) is not adopted because it needs a linter and script this repository does not carry.
- Checks run: `maintenance/check.py` passes and refreshed the README table and date; markdownlint-cli2 reports 0 issues across the 8 linted files; `ruff check` and `ruff format --diff` are clean at the pinned 0.16.6, with no Python changed.

| File | Measure | Change |
| --- | --- | --- |
| `rules/AGENTS.md` | 1,632 `tok` | +369 |
| `rules/ARENA.md` | 8,017 `B` | +473 |
| `rules/CHATGPT.txt` | 1,494 `chars` | 0 |

## 2026-09-11 — Apply Arena amendments with Ruff gates

- `rules/ARENA.md` replaces Use with the Arena-agent preamble (every chat, task, first message, explicit override confirm), and appends: Engineering per-case dependency approval; Verification grep-verify after edits with scripted splice for large replacements plus repo validation entrypoints and generated-config parsing; Style `ruff.toml` conventions and `ruff check`/`ruff format` gates; Git report/audit local-only commits, REST PR title/body updates with PATCH re-fetch verification, current titles, and squashed-timeline bodies; Deliverables regenerated doc sections. All 2,081 added bytes are requested content with no safe recovery left at the audited floor, so the budget rises from 5,012 to 7,093 bytes rather than dropping a constraint.
- Added `ruff.toml` (103 `B`, not budgeted) with exactly the amended conventions: `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, Ruff defaults, nothing else.
- `maintenance/check.py` gains the executable bit (100644 → 100755, no content change) so `ruff check` passes EXE001 under Ruff defaults; `ruff format` leaves all 18 files unchanged.
- `rules/ARENA.md` gains criticism duties in Verification (`Criticize everything: docs may be stale; code may be wrong`) and a clarified report workflow in Git (always commit report/audit artifacts locally at the end for diff-viewer visibility, NEVER push to the repo, undo that commit next turn and continue). Compressed in two squash passes to hold the budget: Use preamble (`Arena agent reading this`, `rules for`, `first message in this repo`, `Explicit user instructions`, `confirm override`), General punctuation (`docs, conventions, patterns`, `defaults, NEVER`, `requirement/convention`, `used only when domain fits`), Engineering (`then`, `the code/flow`, `with `simplified:` comment`), Verification (`root cause`, recheck `then`, `actually`, `a scripted splice`, `repo's validation`), Style (dropped the redundant `Python: Ruff E4/E7/E9/F` pin kept in the core, `Ruff uses`, `If missing`, `create it exactly`, `before gates`), Git (`a timeline`, `keep PR open`), Deliverables (`after source changes`), pass 2 (`it covers`, list comma for `or`); 7,093 → 6,965 (-128), below prior with both amendments aboard. Pass 3 found no further safe cuts.
- `.gitignore` gains `reports/` so report/audit artifacts live in a git-ignored output dir, force-added to a local-only end-of-turn commit for diff-viewer visibility and never pushed.
- `rules/ARENA.md` fixes the REST PATCH snippet (`--arg title <title>`, `repos/<owner>/<repo>` prefix), sets criticism venue to chat and reports, and caps reports at MD013 120; funded by squashing (`every chat, task`, `first message here`, `confirm in`, `whether or not repeated`, `user picks`, `naming ceiling`, `every edit`, dropping `with JSON on stdin`); 6,965 → 6,955.
- `rules/AGENTS.md` drops the squashed commit list (generic agents commit directly on their branch) and gains the user's Ruff style rules (`ruff.toml` conventions plus `ruff check`/`ruff format` gates); 1,059 → 1,096 `tok`. `rules/COMMIT_SPEC.txt` drops its MUST-print clause to match the core; 58 → 47 `tok`. ChatGPT keeps its squashed list.
- `rules/CHATGPT.txt` strengthened inside its 1,500-char ceiling: NEVER mermaid unless explicitly asked, NEVER filler or essays, and a spelled-out Conventional `<type>(scope): subject` format; 1,495 → 1,490 chars.
- `maintenance/check.py --update` now manages the README date (UTC) whenever measurements change; DTZ011 fixed timezone-aware. `rules/apply.py` gains `--yes`/`--dry-run` plus a missing-source guard (exit 1, no traceback); `apply.bat` forwards args.
- `rules/README.md` moves skill/workflow install and selection detail into `skills/README.md` and `workflows/README.md`, crisps Rule maintenance to 10 one-line items with detail subsections (Arena file, Emphasis, Skill rules, Baselines), corrects the emphasis note for the AGENTS list-drop, and documents the MD007 pin. `.markdownlint-cli2.jsonc` pins MD007 indent 2 explicitly.
- New `ref/` baseline: tracking copies of the five agent-facing rule files snapshotted from `main` (`dcea8d3`, 2026-09-10) for agents measuring without git history; refreshed on intentional rebaselines.
- `rules/ARENA.md` pins `required-version = "0.16.6"` in its `ruff.toml` spec and keeps a single report file (updated in place); funded by dropping the `rosters` example and restated `atomic`, keeping the `-f` war story per direction; 6,955 → 6,989 (+34, no safe recovery left).
- `ruff.toml` sets `required-version = "0.16.6"` so gates run the pinned defaults; `rules/AGENTS.md` style spec records the pin. `ref/` reframed as living uncompressed originals with an amend-first rule (maintenance item 10); `ref/ARENA.md` reconstructed at 7,645 B, others mirror live. Spec gains a commit-disciplines table; `maintenance/README.md` documents the `TIKTOKEN_CACHE_DIR` offline path.
- `ref/` moved to `rules/refs/` via `git mv` (history kept) with all in-repo references relinked; baselines rebuilt clause-by-clause from `main` history (`7841d84`–`dcea8d3`) so each file keeps its longest historical sentence form — restored squash victims (`without exception`, `one message per logical change`, `step-by-step`, `not the symptom`, `the branch`, `Keep architecture`, plan/TDD/commit bullets) while deleted rules (handoff, `agent-handoff`, MUST-print for agents, dropped scope items) stay deleted and MUST/NEVER markers stay as emphasis. `rules/refs/AGENTS.md` 5,653 B, `rules/refs/ARENA.md` 7,820 B; `COMMIT_SPEC.txt` equals live, never compressed.
- Squash audit (`rules/refs/` vs `rules/`) verdicts: no silent meaning loss; 9 weak wordings restored to explicit form instead of relying on cover — AGENTS regains `replace a convention`, `exact` + `per logical change` plans, `not the symptom`, `no speculative behavior or tests`, `deleted once used` (1,108 → 1,121 `tok`); ARENA regains the same plus `clean timeline`, `one message per logical change`, `updated in place` (6,989 → 7,086 `B`); CHATGPT regains `yet clear` and `detail on request`, funded by dropping illustrative `postambles` and entailed `phone-sized` (1,490 → 1,494 chars). Budgets rise rather than keep inferred-only wording.
- Rule maintenance now requires dual amendment: every rule change amends `rules/refs/` (full original) and the live file (compressed form) together, so originals are never lost; item 10, Baselines, and `refs/README.md` agree.
- Compressed the incorporated ponytail text against refs originals: AGENTS 6 cuts (articles, when-ellipsis, in-file-unique `criterion`, skill-pattern `skipped alternatives`, strict search-entails-existing) 1,269 → 1,263 (-6); ARENA restored the search object (`searching for a helper`, +13 B) after the loop flagged bare `searching first` as weak-grade inference. Refs diffs re-verified all OK-class, zero weak reintroduced.
- Incorporated ponytail ultra-as-suggested into the generic core per vote: five parts soft via consider/prefer (scope-challenge with the how-never-what guardrail, skipped/add-when reporting, shaping heuristics, decision heuristics, one-check test minimalism with no-new-frameworks reconciled against reuse-existing) plus one hard rule (MUST grep every caller of the function before editing; fix once where all callers route through); ARENA mirrors all six condensed. AGENTS 1,114 → 1,269 (+155), ARENA 6,920 → 7,531 (+611); budgets rise for the voted-in content. CHATGPT untouched (no ceiling room); the skill itself unchanged, still canonical lite/full/ultra.
- Compression Pass 1 against `rules/refs/`: AGENTS 6 cuts (bare-plural universal, order-encoded `then`, articles, possessive, strict `reuse`-entails-existing, parallel ellipsis) 1,121 → 1,114 (-7); ARENA 6 cuts (ones-ellipsis plus 5 rationale drops whose originals stay in refs) 7,086 → 6,920 (-166). Pass 2 found no further safe cuts (a borderline plan-`then` rejected to protect sequence clarity); CHATGPT/CLINE/COMMIT_SPEC already at floor. Refs comparison re-verified: every remaining difference is OK-class, zero weak items reintroduced.
- `rules/refs/README.md` drops the deleted-rules audit-trail sentence per direction; the baselines themselves are unchanged.
- Fixed `rules/refs/AGENTS.md`: dropped the MUST-print bullet the rebuild resurrected — generic agents are exempt,
  the deletion stands and the baseline now matches its own methodology note.

| File | Measure | Change |
| --- | --- | --- |
| `rules/AGENTS.md` | 1,263 `tok` | +204 |
| `rules/ARENA.md` | 7,544 `B` | +2,532 |
| `rules/CHATGPT.txt` | 1,494 `chars` | -1 |
| `rules/COMMIT_SPEC.txt` | 47 `tok` | -11 |

## 2026-09-10 — Harden atomic commit requirements

- `rules/AGENTS.md` now defines atomic commits: one logical change with every changed file, each keeping checks green and independently revertible, under the bullet MUST. Funded by trimming `replace a convention` to `convention`, `behavior or tests` to `tests`, `corrected` to `fixed`, `per completed feature` to `per change`, `root cause not the symptom` to `root cause`, and dropping `step-by-step` (numbered plans plus per-change verification entail sequence); lands at 1,059 against 1,061.
- `rules/ARENA.md` condenses the same as MUST-class `Commits MUST be atomic: one logical change with every file in it, checks green, independently revertible`, gaining the completeness half the core already had. No safe recovery remained at the audited floor, so the budget rises from 4,947 to 5,012 bytes rather than dropping a constraint.

| File | Measure | Change |
| --- | --- | --- |
| `rules/AGENTS.md` | 1,059 `tok` | -2 |
| `rules/ARENA.md` | 5,012 `B` | +65 |

## 2026-09-10 — Document and validate the workflows directory

- The `workflows/` directory is now integrated: a new `workflows/README.md` index describes the portable single-file format and usage; the root README gains a layout bullet and a budget row; the root `AGENTS.md` gains a read-first link, a Workflows section, and updated validator, budget, and lint-scope notes; the rules specification gains a contents row and a Workflows section with a selection table; `maintenance/README.md` describes the new checks.
- `maintenance/check.py` validates the workflows listing against `workflows/README.md`, requires a `description` frontmatter field in each workflow file, checks internal links in the workflows index, and budgets `workflows/init-docs.md` in `cl100k_base` tokens like the other entry files.
- The lightweight-repo rule now prohibits further CI workflows, since `workflows/` holds agent workflows and the old wording read as banning the new directory. No budgeted rule or skill file changed.
- Added a disabled `distribute-arena` workflow template (`.github/workflows/distribute-arena.yml.disabled`, 388 tokens): on manual dispatch it pushes `rules/ARENA.md` to each listed repo's `ARENA.md` over HTTPS with a short-expiry fine-grained PAT stored as `ARENA_DIST_PAT`, amending the prior sync commit when HEAD is one and committing only when the file changed. The default list holds `nemoe7/clankers`, a dispatch input overrides it, and renaming to `.yml` enables the workflow.
- Squashed `workflows/init-docs.md` from 4,153 to 4,102 `tok` (4 passes, -1.2%): merged same-subject bullets, cut filler and restated clauses; headings, order, lists, code blocks, and every rule, condition, and identifier preserved.
- `rules/ARENA.md` gains a handoff clause in Workspace: MUST maintain a handoff document (goal, done, next, key files/decisions), updated as work lands, so work resumes if limits are reached. Squashing cut 140 bytes elsewhere (dropped `As an Arena.ai agent`, `not one sweep`, `without exception`, `Keep architecture`, `one message per logical change`, `re-checking` to `rechecking`, `corrected` to `fixed`, `a commit` to `one`), so the 136-byte clause lands the file at 4,848 against a prior 4,852.
- The handoff clause now pins the document lifecycle (NEVER commit or gitignore it; stays untracked and local, downloadable), and Scope's ask rule is now MUST stop and ask on deviating reasoning or material ambiguity, only then. No safe recovery cuts remained after the prior pass, so the budget rises from 4,848 to 4,962 bytes rather than dropping a constraint.
- The handoff document now names its contents (goal, requirements fulfilled, done, next, decisions made, key files), must let work resume without re-asking, and stays always downloadable. The 55 added bytes are all requested content with no safe recovery left, so the budget rises from 4,962 to 5,017 bytes.
- Scratched the handoff document: `rules/ARENA.md` now always pushes the branch and keeps a PR open so work survives limits, folding fixes into the squashed atomic timeline, matching the PR body to it, and rewriting remotes with `--force-with-lease`, never plain `--force`. The swap nets -168 bytes (handoff removal outweighs the push rule); the budget falls from 5,017 to 4,849. The rules specification records the intentional push/PR divergence from the core.
- `rules/ARENA.md` now disregards never-push rules (Arena controlled edits make pushing safe, judged safe for now) and NEVER merges the PR until authorized. The 109 added bytes are all requested content with no safe recovery left; the budget rises from 4,849 to 4,958 bytes.
- Squashed `rules/ARENA.md` by 11 bytes (`Always push the branch` to `Always push`); the budget falls from 4,958 to 4,947 bytes.

| File | Measure | Change |
| --- | --- | --- |
| `workflows/init-docs.md` | 4,102 `tok` | +4,102 (new; squashed from 4,153) |
| `rules/ARENA.md` | 4,947 `B` | +95 |

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
