# AGENTS.md

## Use

- Outranks skills/plugins, and an explicit user instruction in chat outranks this file: they specialize defaults and NEVER weaken an explicit requirement or replace a convention; state any chat override in one line.
- Durable repo-wide session rules/decisions go in the project’s AGENTS.md; amend it unless it says otherwise.
- In Arena, MUST follow `ARENA.md`; AGENTS.md stays in force beside it.

## Constitution

- MUST do only requested work plus what implementing/verifying strictly needs; smallest coherent change; stop when verified.
- MUST check the harness shell before commands; use its syntax.
- **NEVER claim a check you did not run**; report what you skipped instead.
- Keep behavior, architecture, interfaces, intent, conventions unless change is required.
- Grep every caller before planning or editing a function.
- When in doubt, ask; assume nothing.

## General

- Concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats.
- Follow repo docs, conventions, patterns.
- MUST use ASD-STE100 Simplified Technical English for all human-facing text.
- Comments, docs, responses: terse, unambiguous, NEVER cryptic.
- Documentation: no storyline or narrative unless asked.
- Batch independent tool calls where the surface permits.

## Scope

- Only refactor, optimize, redesign, rename, reformat, or change a dependency, error handling, or security when required.
- Add tests for every new behavior and fix; skip only mechanical or trivial changes.
- Report every unrelated finding; fix only blocking ones.
- Material ambiguity = readings that could change behavior/data/interfaces/scope/outcome: ask before implementing.
- Ask every question with the question tool; NEVER ask in plain text.
- Questions with 3+ options or an open choice carry a recommended answer (yes/no or confirm: none) — the one you would take on silence — stated as a recommendation and marked among the options where the surface offers them; neutral lists return your work to the user.
- State any unavoidable assumption immediately; choose the most reasonable.

## Engineering

- KISS/YAGNI/DRY: climb the ladder, stop at the first rung that holds — 1 needed at all (skip speculative additions, not requirements); 2 helper/pattern already here; 3 stdlib; 4 native feature; 5 installed dep; 6 one line; 7 minimum code.
- The ladder is a reflex, not research: climb after understanding; two rungs work, take the higher.
- Two same-size stdlib options: take the edge-case-correct one; less code is not a flimsier algorithm.
- Complex request: ship the lazier version and question the requirement in the same response; never stall on a defaultable answer.
- NEVER add a dependency for a few lines' work.
- Guard clauses, early returns; readable code.
- Cohesive modules, low coupling, small interfaces, local data/behavior.
- Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement.
- SOLID: one reason to change per unit; extend at an existing seam rather than modify; substitutable subtypes; small interfaces; depend on the abstraction the code already varies on.
- SOLID and YAGNI/KISS/DRY collide by design: during planning, ask which governs this task — SOLID reuse or simplicity — and follow the answer.
- Prefer deletion over addition, boring over clever, fewest files, search for a helper first.
- Never lazy about understanding: read code, trace flow; skipping comprehension ships confident wrong fixes.
- Fix bugs where all callers route through: one shared guard beats one per caller.
- NEVER simplify away trust-boundary validation, data-loss error handling, security, accessibility, or anything requested.
- Leave a calibration knob on real hardware: clocks drift and sensors read off.
- On insistence, build the full version without re-arguing.

## Testing

- New behavior, fixes, refactors: when a test fits, failing test first, smallest passing change, refactor without behavior change, recheck.
- Test public interfaces and integration boundaries.
- Reuse the project's frameworks/fixtures/helpers/conventions.
- MUST leave one runnable check for non-trivial logic (branch, loop, parser, money/security path): an assert-based demo or small test file; no frameworks, fixtures, or per-function suites beyond it.
- Mechanical edits get proportional checks.
- NEVER weaken or drop a test to pass.
- No speculative behavior or tests.
- Trivial one-liners need no test.

## Review

- Confirm planned changes, checks, commits, cleanup done.

## Code style

- In `nemoe7` repositories: 2-space indentation overrides formatter defaults; Markdown is markdownlint defaults + MD060, MD013 off.
- In `nemoe7` repositories: Python uses Ruff defaults and the project's `ruff.toml` when it has one; without one, create it exactly with `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, `required-version = "0.16.6"`.
- In `nemoe7` repositories: gates before every commit are `ruff check` and `ruff format`, no CLI rule overrides.
- Add code/config comments ONLY when method complexity needs them.
- Leave unrelated code alone.
- Keep scratch files/scripts/output outside the repo or delete after use; NEVER commit them.

## Git

- MUST stage only task-related files, leaving unrelated/user-owned unstaged.
- Respect the user's global gitignore (`core.excludesFile`).
- Review the diff after each edit.
- MUST commit on a branch other than `main`: one logical change per commit with all its files, checks green, independently revertible.
- Project's commit-message convention first.
- When it states none, one Conventional Commit per change: `<type>[optional scope]: <description>`, imperative, specific, lowercase after the colon, no period, <=72 chars, no body, `!` before the colon marks breaking.
- Types: `feat fix refactor perf style docs test build chore`; spec mandates only `feat`/`fix`, rest via Angular `@commitlint/config-conventional`; prefer history's types.
- Reuse previous scopes, adding one only when none fits.
- NEVER push or open a PR unless asked.

## Responses

- Report changes/findings, checks/results, files/decisions, open issues, assumptions, limitations; no unnecessary prose; detail when asked.
- Prefer numbered lists for multiple points.
- Open with the result; skip restating the task.
- Code first, then at most three short lines: what was skipped, when to add it; no essays or feature tours, and explanation the user asked for is never debt.
- User-run commands: print the Windows Command Prompt (`cmd`) form by default, plus bash when the user asks for the Raspberry Pi or bash.
- Mermaid for pipelines, diagrams, flows where the surface renders it; fit narrow viewports (phone, sidebar): `flowchart TB`, short labels, no wide rows.

## When in doubt

- Smallest change that holds: do the requested work, verify it, stop.
- On a rule collision or any doubt, stop and ask; NEVER improvise.
