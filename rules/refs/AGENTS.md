# AGENTS.md

## General

- Concise, direct, practical, accurate. Preserve key details: negations, conditions, errors, commands, numbers, caveats. Follow repo docs and conventions; prefer existing patterns. Skills specialize defaults and NEVER weaken an explicit requirement or replace project conventions.

## Scope

- Plans MUST be numbered, concrete, and executable without clarification.
- Plans MUST include TDD: Red, Green, Refactor, Verify. If a step is inapplicable, state why.
- Plans MUST define exact atomic commits per logical change, including commit messages.
- Plans are incomplete until TDD and commits are defined.
- MUST read all project instructions before changes.
- MUST follow the approved plan step-by-step, verifying each logical change. MUST stop and ask if reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- MUST do only the requested task plus what it takes to implement and verify; smallest coherent change; stop when verified.
- Preserve behavior, architecture, interfaces, intent, conventions unless change is required.
- NEVER proactively refactor, optimize, redesign, rename, reformat, change a dependency or error handling/security, or add tests.
- Investigate only as needed; NEVER hunt alternatives past a suitable pattern, speculate on unrelated requirements or edge cases, or replan without new evidence.
- Unrelated findings stay out of scope unless blocking. Ask only when ambiguity materially affects safe scope or behavior.

## Engineering

- KISS/YAGNI/DRY, laziest working solution: stop at the first rung that holds — needed at all; helper/pattern already here; stdlib; native feature; installed dependency; one line; minimum code. NEVER add a dependency for a few lines' work.
- Build what is asked, then name the lazier alternative in one line; the user picks. Never lazy about understanding: read the code, trace the flow first. NEVER simplify away trust-boundary validation, error handling preventing data loss, security, or accessibility; mark a deliberate corner-cut with a `simplified:` comment naming its ceiling and upgrade path.
- Guard clauses, early returns; cohesive modules, low coupling, small interfaces, local data/behavior; NEVER an unrequested abstraction (one-implementation interface, one-product factory, config for a constant), boilerplate, or scaffolding for later; seams only for tangible needs, never a parallel mechanism where an extension point fits.
- Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement. Write clear, readable code.

## Debugging

Bugs, failures, regressions: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck. Falsifiable hypotheses, evidence over guessing, one variable at a time; NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption. Behavioral fixes get a focused regression test.

## Testing

New behavior, fixes, refactors: failing test first when practical, smallest passing change, refactor without behavior change, rerun checks. Test public interfaces and integration boundaries; reuse existing frameworks/fixtures/helpers/conventions. Mechanical-only changes: proportional verification. NEVER weaken or drop a test to pass; no speculative behavior or tests.

## Review

- Before finishing: check requirements, acceptance criteria, scope; verify behavior via tests/linters/formatters/builds.
- Verify relevant external, version-specific, or time-sensitive facts against authoritative sources.
- Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs.
- Fix in-scope issues, re-verify; NEVER claim a check you did not run; report what you skipped instead.
- Confirm planned changes, checks, commits, and cleanup are done.

## Code style

2-space indentation (overrides formatter defaults). Markdown: markdownlint defaults + MD060; MD013 disabled. Python: Ruff default selection (E4, E7, E9, F). Python uses the repo's `ruff.toml` (`required-version = "0.16.6"`, `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, Ruff defaults); if missing, create it exactly before gates. Gates before every commit: `ruff check` and `ruff format`, no CLI rule overrides. Leave unrelated code untouched. MUST maintain repository hygiene. Keep scratch files, scripts, and output outside the repo or delete them once used. Never commit or abandon them. If Plan mode was used, MUST delete all generated plan files.

## Git

- MUST stage only task-related files, NEVER unrelated or user-owned ones; respect the user's global gitignore (`core.excludesFile`); review the diff after each edit.
- MUST commit directly on a branch other than `main`, one logical change per commit with every changed file in it, each keeping checks green and independently revertible. One Conventional Commit per completed feature: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, <=72 chars, no body. Types: `feat fix refactor perf style docs test build chore`. Reuse previous scopes, adding one only when none fits. NEVER push or open a PR unless asked.

## Responses

- Report changes/findings, checks and results, useful files/decisions, unresolved issues, assumptions, limitations.
- Prefer numbered lists for multiple points.
- Never repeat the task.
- Use a mermaid diagram when structure or flow beats prose and the surface renders it; fit a narrow viewport (phone, sidebar): top-down, short labels, no wide rows.
