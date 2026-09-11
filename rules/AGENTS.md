# AGENTS.md

## General

- Concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats. Follow repo docs, conventions, patterns; skills specialize defaults and NEVER weaken an explicit requirement or replace a convention.

## Scope

- Plans MUST be numbered, concrete, executable without clarification, and incomplete until they define TDD (red, green, refactor, verify; say why a step is inapplicable) and each exact atomic commit per logical change with its message.
- MUST read project instructions before changes, then follow the approved plan, verifying each logical change. MUST stop and ask if reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- MUST do only requested work plus implementation and verification; smallest coherent change; stop when verified. Keep behavior, architecture, interfaces, intent, conventions unless change is required: NEVER proactively refactor, optimize, redesign, rename, reformat, change a dependency or error handling/security, or add tests.
- Investigate just enough: NEVER hunt alternatives past a suitable pattern, speculate on unrelated requirements or edge cases, or replan without new evidence. Unrelated findings stay out of scope unless blocking; ask only on material scope or behavior ambiguity.

## Engineering

- KISS/YAGNI/DRY, laziest working solution: stop at the first rung that holds — needed at all; helper/pattern already here; stdlib; native feature; installed dependency; one line; minimum code. NEVER add a dependency for a few lines' work.
- Build what is asked, name the lazier alternative in one line; the user picks. Never lazy about understanding: read code, trace flow first. NEVER simplify away trust-boundary validation, data-loss error handling, security, or accessibility; mark a corner-cut with a `simplified:` comment naming ceiling and upgrade path.
- Guard clauses, early returns; cohesive modules, low coupling, small interfaces, local data/behavior; NEVER an unrequested abstraction (one-implementation interface, one-product factory, config for a constant), boilerplate, or scaffolding; seams only for tangible needs, never a parallel mechanism where an extension point fits.
- Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement. Write clear, readable code.

- Consider proposing a smaller scope for approval rather than silently trimming requirements; simplicity chooses how, never what. Prefer deletion over addition, boring over clever, the fewest files, and searching for an existing helper first. Prefer the simplest implementation meeting every acceptance criterion, the edge-case-correct stdlib pick on ties, and safe defaults only for non-material choices; if the user insists on the full version, build it without re-arguing.

## Debugging

Bugs, failures, regressions: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck. MUST grep every caller of the function before editing; fix once where all callers route through. Falsifiable hypotheses, evidence over guessing, one variable at a time; NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption. Behavioral fixes get a focused regression test.

## Testing

New behavior, fixes, refactors: failing test first when practical, smallest passing change, refactor without behavior change, rerun checks. Test public interfaces and integration boundaries; reuse frameworks/fixtures/helpers/conventions. Mechanical edits get proportional checks. NEVER weaken or drop a test to pass; no speculative behavior or tests. Prefer one small runnable check for non-trivial logic (assert-based demo or one small test file); introduce no new frameworks or fixtures unless asked; trivial one-liners need no test.

## Review

Before finishing check requirements, acceptance criteria, scope; verify behavior via tests/linters/formatters/builds, and external, version-specific, or time-sensitive facts against authoritative sources. Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs. Fix in-scope issues and recheck. **NEVER claim a check you did not run**; report what you skipped instead. Confirm planned changes, checks, commits, and cleanup are done.

## Code style

2-space indentation overrides formatter defaults. Markdown: markdownlint defaults + MD060, MD013 off. Python: Ruff defaults (E4, E7, E9, F). Python uses the repo's `ruff.toml` (`required-version = "0.16.6"`, `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, Ruff defaults); if missing, create it exactly before gates. Gates before every commit: `ruff check` and `ruff format`, no CLI rule overrides. Leave unrelated code alone. MUST keep repository hygiene: scratch files, scripts, and output stay outside the repo or are deleted once used, including generated plan files.

## Git

- MUST stage only task-related files, NEVER unrelated or user-owned; respect the user's global gitignore (`core.excludesFile`); review the diff after each edit.
- MUST commit directly on a branch other than `main`, one logical change per commit with every changed file in it, each keeping checks green and independently revertible. One Conventional Commit per change: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, <=72 chars, no body. Types: `feat fix refactor perf style docs test build chore`. Reuse previous scopes, adding one only when none fits. NEVER push or open a PR unless asked.

## Responses

- Report changes/findings, checks and results, useful files/decisions, unresolved issues, assumptions, limitations; prefer numbered lists for multiple points. Never repeat the task. Consider reporting what was skipped and when to add it.
- Use a mermaid diagram when structure or flow beats prose and the surface renders it; fit a narrow viewport (phone, sidebar): top-down, short labels, no wide rows.
