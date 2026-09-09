# AGENTS.md

## General

- Concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats. Follow repo docs, conventions, patterns; skills specialize defaults, never weaken explicit requirements or replace conventions.

## Scope

- Plans MUST be numbered, concrete, executable without clarification, and incomplete until they define TDD (red, green, refactor, verify; say why a step is inapplicable) and each atomic commit with its message.
- MUST read all project instructions before changes, then follow the approved plan step-by-step, verifying each logical change; stop and ask if reasoning, investigation, or implementation deviates.
- Only requested work plus implementation and verification; smallest coherent change; stop when verified. Keep behavior, architecture, interfaces, intent, conventions unless change is required: no proactive refactor, optimization, redesign, rename, reformat, dependency, error-handling/security, or tests.
- Investigate just enough: no alternative-hunting past a suitable pattern, speculating on unrelated requirements or edge cases, or replanning without new evidence. Unrelated findings stay out of scope unless blocking; ask only on material scope or behavior ambiguity.

## Engineering

- KISS/YAGNI/DRY, laziest working solution: stop at the first rung that holds — needed at all; helper/pattern already here; stdlib; native feature; installed dependency; one line; minimum code. Never add a dependency for a few lines' work.
- Build what is asked, then name the lazier alternative in one line; the user picks. Never lazy about understanding: read the code, trace the flow first. Never simplify away trust-boundary validation, data-loss error handling, security, or accessibility; mark a corner-cut with a `simplified:` comment naming its ceiling and upgrade path.
- Guard clauses, early returns; cohesive modules, low coupling, small interfaces, local data/behavior; no unrequested abstraction (one-implementation interface, one-product factory, config for a constant), boilerplate, or scaffolding; seams only for tangible needs, never a parallel mechanism where an extension point fits.
- Ground choices in requirements, code, tests, docs, observations; invent no API, constraint, or requirement. Write clear, readable code.

## Debugging

Bugs, failures, regressions: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck. Falsifiable hypotheses, evidence over guessing, one variable at a time; no arbitrary fallbacks, hidden failures, or unrevised assumptions. Behavioral fixes get a focused regression test.

## Testing

New behavior, fixes, refactors: failing test first when practical, smallest passing change, refactor without behavior change, rerun checks. Test public interfaces and integration boundaries; reuse existing frameworks/fixtures/helpers/conventions. Mechanical edits get proportional checks. Never weaken or drop tests to pass; no speculative behavior or tests.

## Review

Before finishing check requirements, acceptance criteria, scope; verify behavior via tests/linters/formatters/builds, and external, version-specific, or time-sensitive facts against authoritative sources. Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs. Fix in-scope issues and recheck; never claim unperformed checks. Confirm planned changes, checks, commits, and cleanup are done.

## Code style

2-space indentation overrides formatter defaults. Markdown: markdownlint defaults + MD060, MD013 off. Python: Ruff defaults (E4, E7, E9, F). Leave unrelated code alone. MUST keep repository hygiene: scratch files, scripts, and output stay outside the repo or are deleted, including generated plan files.

## Git

- MUST print the squashed commit list before every commit: local commits and fixes folded into a clean timeline, updated as work lands. Committing without it is a violation; if a commit landed unlisted, print the corrected timeline before the next.
- Stage only task-related files, never unrelated or user-owned; respect the user's global gitignore (`core.excludesFile`); review the diff after each edit.
- Always commit on a branch other than `main`, one logical change per commit with every changed file in it. One Conventional Commit per completed feature: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, <=72 chars, no body. Types: `feat fix refactor perf style docs test build chore`. Reuse previous scopes, adding one only when none fits. Never push or open a PR.

## Responses

- Report changes/findings, checks and results, useful files/decisions, unresolved issues, assumptions, limitations; prefer numbered lists for multiple points. Never repeat the task.
- Use a mermaid diagram when structure or flow beats prose and the surface renders it; fit a narrow viewport (phone, sidebar): top-down, short labels, no wide rows.
