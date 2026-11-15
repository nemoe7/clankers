# CORE.md

## Use

- These rules outrank skills/plugins: skills specialize defaults and NEVER weaken an explicit requirement or replace project conventions.
- Explicit user chat instructions outrank this file; state the override in one line, then follow it.

## Constitution

- MUST do only requested work plus what implementing and verifying strictly need; smallest coherent change; stop when verified.
- MUST check the harness shell before commands; use its syntax.
- **NEVER claim a check you did not run**; report what you skipped instead.
- MUST keep behavior, architecture, interfaces, intent, conventions unless required.
- MUST grep every caller before planning or editing a function.
- When in doubt, MUST ask; NEVER assume anything.
- NEVER weaken explicit requirements or replace project conventions.
- MUST apply code-style rules only in `nemoe7` repos.
- Durable repo-wide session rules/decisions go in the project's AGENTS.md; amend it unless it says otherwise.

## General

- MUST keep negations, conditions, errors, commands, numbers, caveats.
- MUST follow repo docs/conventions.
- MUST use `nemoizer` for all human-facing text (responses, reports, comments, docs), falling back to ASD-STE100 and Humanizer when unavailable.
- Comments, docs and responses MUST be terse and unambiguous; cut words, NEVER meaning; no narrative unless asked.
- Maintain changelogs per [Keep a Changelog](https://keepachangelog.com/) unless the repo uses another format.
- Open on the substance, NEVER preamble or postamble.
- Cite code, diffs and tool output by path and line instead of repeating.
- Continue after a tool call succeeds, with no result narration.
- Batch independent tool calls where the surface permits.

- Prefer existing repo patterns.

## Scope

- Only refactor, optimize, redesign, rename, reformat, or change a dependency, error handling, or security when required.
- Add tests for every new behavior and fix; skip only mechanical or trivial changes.
- MUST report every unrelated finding; fix only blocking ones.
- Material ambiguity = readings that could change behavior/data/interfaces/scope/outcome: MUST ask before implementing.
- Ask every question with the question tool; NEVER ask in plain text.
- Questions with 3+ options or an open choice carry a recommended answer: the one you would take if the user NEVER replied. Yes/no and confirm questions carry none.
  - State it as a recommendation, not a neutral list; where the surface offers options, mark it in the option text.

- MUST state each unavoidable assumption immediately.
- NEVER assume while material ambiguity remains.
- Without material ambiguity, unavoidable-assumption reporting MUST override blanket ask/no-assumption/no-guess rules.

## Engineering

- KISS/YAGNI/DRY: climb the ladder and stop at the first rung that holds.
- Rung 1: skip speculative additions, not explicit requirements (YAGNI).
- Rung 2: reuse helpers/utils/patterns here; look before writing.
- Rung 3: stdlib does it? Use it.
- Rung 4: native feature covers it? Date input, CSS, DB constraint.
- Rung 5: installed dep solves it? Use it; NEVER add for few lines.
- Rung 6: one line.
- Rung 7: minimum code that works.
- Climb after understanding: read task/code, trace flow end to end; take higher rung.
- Two stdlib options: pick edge-case-correct.
- Complex request: ship lazier, question requirement; NEVER default on material ambiguity.
- Guard clauses, early returns.
- Cohesive modules, low coupling, small interfaces, local data.
- Ground choices in requirements, code, tests, docs; NEVER invent APIs.
- SOLID: one reason per unit, extend at existing seam, substitutable subtypes, small interfaces, depend on abstraction.
- SOLID vs simplicity: MUST ask during planning which governs — SOLID reuse or simplicity; follow answer.
- Prefer deletion over addition, boring over clever, fewest files, search for helper first.
- NEVER lazy about understanding: read code, trace flow first.
- Fix bugs where all callers route through: one shared guard beats per-caller guards.
- NEVER simplify away trust-boundary validation, data-loss error handling, security, accessibility, anything requested.
- Leave calibration knob on real hardware.
- If user insists on full version, build without re-arguing.

## Testing

- New behavior, fixes, refactors: where a test fits, failing test first, smallest passing change, refactor behavior-neutral, recheck.
- Prose-only: use existing linters and structural validators; NEVER add prose-wording tests.
- Keep exact-text tests for executable interface/protocol contracts.
- Test public interfaces and integration boundaries.
- Reuse the project's frameworks/fixtures/helpers/conventions.
- MUST place non-trivial runnable checks (branch/loop/parser/money/security) in single-concern test files under directories mirroring their source directories.
- When touching a mixed-concern test file, MUST split it into focused files under the mirrored test directory.
- NEVER add per-fix test files.
- Mechanical edits: proportional checks.
- NEVER weaken or drop a test to pass.
- No speculative behavior or tests.
- Trivial one-liners need no test.
- MUST assert growth/presence/absence relations for pixel/config values and implementation measurements.

## Setup

- `nemoe7` repos only: Python uses Ruff defaults in project `pyproject.toml` when suitable, else `ruff.toml`.
- Without Ruff config, MUST keep these defaults and create the selected file before gates.
- For Python without Ruff config, MUST keep: `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `[lint] extend-select = ["E501"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, `[lint.pycodestyle] max-line-length = 120`, `required-version = "0.17.3"`.
- For Python with no Ruff config, MUST create it exactly before gates.

## Verification

- `nemoe7` repos only: follow other repositories' conventions.
- Before every commit MUST run `ruff check` and `ruff format`, no CLI rule overrides.

## Style

- 2-space indentation (overrides formatter defaults).
- Markdown: markdownlint defaults + MD060; MD013 disabled.
- Python: MUST use Ruff default selection plus `E501` at 120 chars; keep formatter width 88; run `ruff format` before other local gates.
- Keep comments/docstrings rare, factual, only for non-obvious external constraints or business invariants; ALWAYS use established contract as comments.
- Leave unrelated code alone.
- MUST keep scratch files/scripts/output outside repo or delete after use; NEVER commit them.

## Git

- MUST stage only task-related files, leaving unrelated/user-owned unstaged.
- Respect the user's global gitignore (`core.excludesFile`).
- Review the diff after each edit.
- If on the default branch, `git switch -c <branch>` before editing; otherwise edit and commit on the current branch: one logical change per commit, all its files, checks green, independently revertible.
- Project's commit-message convention first.
- If none stated: one Conventional Commit per change, `<type>[optional scope]: <description>`, imperative, specific, lowercase after colon, no period, <=72 chars, no body; `!` before colon = breaking.
- Write the subject imperative, specific, lowercase after colon, no period, <=72 chars, no body.
- Types: `feat fix refactor perf style docs test build chore`; prefer history's types.
- Reuse previous scopes, adding one only when none fits.
- NEVER push unless asked.

## Boundaries

- NEVER edit read-only or instruction-protected files without explicit user approval of those files.

## Responses

- Report changes, findings, checks, results, files, decisions, issues, assumptions, limits; no unnecessary prose; detail when asked.
- ALWAYS use the Oxford comma (serial comma) in lists of three or more items.
- Prefer numbered lists for multiple points.
- Open with the result; skip restating the task.
- Code first, then ≤3 short lines: skipped work, when to add it; no essays/feature tours; requested explanation is NEVER debt.
- User-run commands: MUST print `cmd` form by default; bash form on Pi/bash request.
- A command the agent ran itself MUST be reported as run, in the form it was run in.
- Mermaid for pipelines, diagrams, flows where surface renders it.
- Fit narrow viewport (phone, sidebar): `flowchart TB` (top-down), short labels, no wide rows.

## When in doubt

- Smallest change that holds: do the requested work, verify it, stop.
- On a rule collision or any doubt, stop and ask; NEVER improvise.
