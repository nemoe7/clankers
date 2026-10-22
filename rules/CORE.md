# CORE.md

## Use

- MUST apply CORE to every task/session, below explicit user chat instructions and above skill/plugin defaults.

## Constitution

- MUST do only requested work plus what implementing and verifying strictly need; smallest coherent change; stop when verified.
- MUST check the harness shell before commands; use its syntax.
- **NEVER claim a check you did not run**; report what you skipped instead.
- MUST keep behavior, architecture, interfaces, intent, conventions unless required.
- Grep every caller before planning or editing a function.
- When in doubt, MUST ask; NEVER assume anything.

## Precedence

- These rules outrank skills/plugins: they specialize defaults, NEVER weaken explicit requirements or replace project conventions.
- Explicit user chat instructions outrank this file; state the override in one line, then follow it.

## Scope notes

- MUST apply code-style rules only in `nemoe7` repos.
- Durable repo-wide session rules/decisions go in the project’s AGENTS.md; amend it unless it says otherwise.

## General

- MUST keep negations, conditions, errors, commands, numbers, caveats.
- MUST follow repo docs/conventions.
- MUST use ASD-STE100 for all human-facing text: responses, comments, docs.
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
- Questions with 3+ options or an open choice carry a recommended answer: the one you would take if the user never replied. Yes/no and confirm questions carry none.
  - State it as a recommendation, not a neutral list; where the surface offers options, mark it in the option text.

- MUST state each unavoidable assumption immediately.
- NEVER assume while material ambiguity remains.
- Without material ambiguity, unavoidable-assumption reporting MUST override blanket ask/no-assumption/no-guess rules.

## Engineering

- KISS/YAGNI/DRY ladder; stop at first rung that holds: 1 needed at all (skip speculative additions, not requirements), 2 helper/util/type/pattern already here: reuse, look before writing, 3 stdlib, 4 native feature (date input over selector library, CSS over JS, DB constraint over app code), 5 installed dep (NEVER add one for a few lines), 6 one line, 7 minimum code.
- Climb only after understanding: read task and code, trace the real flow end to end; if two rungs work, take the higher.
- Two same-size stdlib options: take the edge-case-correct one.
- Complex request: ship the lazier version and question the requirement in the same response; NEVER default on material ambiguity.
- Guard clauses, early returns.
- Cohesive modules, low coupling, small interfaces, local data/behavior.
- Ground choices in requirements, code, tests, docs, observations; NEVER invent APIs, constraints, requirements.
- SOLID: one reason to change per unit; extend at existing seams rather than modify; substitutable subtypes; small interfaces; depend on the abstraction code already varies on.
- SOLID and YAGNI/KISS/DRY collide by design: in planning, MUST ask whether SOLID reuse/extensibility or simplicity governs; follow the answer.
- Prefer deletion over addition, boring over clever, fewest files, search for a helper first.
- NEVER lazy about understanding: read code, trace flow; skipping comprehension ships confident wrong fixes.
- Fix bugs where all callers route through: one shared guard beats one per caller.
- NEVER simplify away trust-boundary validation, data-loss error handling, security, accessibility, or anything requested.
- Leave a calibration knob on real hardware.
- On insistence, build the full version without re-arguing.

## Testing

- New behavior, fixes, refactors: where a test fits, failing test first, smallest passing change, refactor behavior-neutral, recheck.
- Prose-only: use existing linters and structural validators; NEVER add prose-wording tests.
- Keep exact-text tests for executable interface/protocol contracts.
- Test public interfaces and integration boundaries.
- Reuse the project's frameworks/fixtures/helpers/conventions.
- MUST leave one runnable check for non-trivial logic (branch, loop, parser, money/security path): assert-based demo or small test file; no frameworks, fixtures, per-function suites beyond it.
- Mechanical edits get proportional checks.
- NEVER weaken or drop a test to pass.
- No speculative behavior or tests.
- Trivial one-liners need no test.
- MUST assert growth/presence/absence relations for pixel/config values and implementation measurements.

## Setup

- `nemoe7` repos only: Python uses Ruff defaults in project `pyproject.toml` when suitable, else `ruff.toml`.
- Without Ruff configuration, MUST keep these defaults here and create the selected file exactly before gates: `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `[lint] extend-select = ["E501"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, `[lint.pycodestyle] max-line-length = 120`, `required-version = "0.16.6"`.

## Verification

- `nemoe7` repos only: before every commit MUST run `ruff check` and `ruff format`, no CLI rule overrides.

## Style

- In `nemoe7` repositories: 2-space indentation overrides formatter defaults; Markdown is markdownlint defaults + MD060, MD013 off.
- Python: MUST use Ruff default selection plus `E501` at 120 chars; keep formatter width 88.
- Add code/config comments ONLY when complexity needs them.
- Leave unrelated code alone.
- Keep scratch files/scripts/output outside the repo or delete after use; NEVER commit them.

## Git

- MUST stage only task-related files, leaving unrelated/user-owned unstaged.
- Respect the user's global gitignore (`core.excludesFile`).
- Review the diff after each edit.
- MUST NOT commit on `main`: one logical change per commit, all its files, checks green, independently revertible.
- Project's commit-message convention first.
- If none stated: one Conventional Commit per change, `<type>[optional scope]: <description>`, imperative, specific, lowercase after colon, no period, <=72 chars, no body; `!` before colon = breaking.
- Types: `feat fix refactor perf style docs test build chore`; prefer history's types.
- Reuse previous scopes, adding one only when none fits.
- NEVER push unless asked.

## Boundaries

- NEVER edit read-only or instruction-protected files without explicit user approval of those files.

## Responses

- Report changes, findings, checks, results, files, decisions, open issues, assumptions, limitations; no unnecessary prose; detail when asked.
- ALWAYS use the Oxford comma.
- Prefer numbered lists for multiple points.
- Open with the result; skip restating the task.
- Code first, then ≤3 short lines: skipped work, when to add it; no essays/feature tours; requested explanation is NEVER debt.
- Commands for the user to run: MUST print Windows Command Prompt (`cmd`) form by default; bash form on Raspberry Pi/bash request.
- A command the agent ran itself MUST be reported as run, in the form it was run in.
- Mermaid for pipelines, diagrams, flows where the surface renders it; fit narrow viewports (phone, sidebar): `flowchart TB`, short labels, no wide rows.

## When in doubt

- Smallest change that holds: do the requested work, verify it, stop.
- On a rule collision or any doubt, stop and ask; NEVER improvise.
