# AGENTS.md

## General

- Concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats.
- Follow repo docs, conventions, existing patterns. Skills specialize defaults, never weaken explicit requirements or replace project conventions.
- Always load the `agent-handoff` skill; its templates and references only when needed. Use other skills when the domain fits.

## Scope

- Only the requested task plus what it takes to implement and verify; smallest coherent change; stop when verified.
- Preserve behavior, architecture, interfaces, intent, conventions unless change is required.
- No proactive refactor, optimization, redesign, rename, reformat, dependency change, error-handling/security, or test additions.
- Investigate only as needed; no alternative-hunting past a suitable pattern, speculation on unrelated requirements or edge cases, or repeated plans without new evidence.
- Unrelated findings stay out of scope unless blocking. Ask only when ambiguity materially affects safe scope or behavior.

## Engineering

- KISS/YAGNI/DRY: simplest correct solution, nothing beyond requirements, reuse logic without forced abstractions.
- Guard clauses, early returns. Cohesive modules, low coupling, small interfaces, local data/behavior.
- Abstractions/seams only for tangible requirements; no parallel mechanism where an extension point fits.
- Evidence-based: requirements, code, tests, docs, observed behavior; invent no APIs, constraints, or requirements.
- Clear, human-readable code; preserve APIs/behavior unless intentionally changed.

## Debugging (bugs, failures, regressions)

Reproduce → Hypothesize → Verify → Fix → Cover → Verify.

- Isolate first; falsifiable hypotheses; evidence over guessing; one variable at a time.
- Root cause, not symptom; no arbitrary fallbacks; never conceal failures; update disproven assumptions.
- Focused regression test for behavioral fixes; re-run checks.

## Testing (new behavior, bug fixes, refactors)

Red → Green → Refactor → Verify.

- Failing test first when practical; smallest passing change; refactor without behavior change; run tests and checks.
- Test public interfaces and integration boundaries; reuse existing frameworks/fixtures/helpers/conventions.
- Mechanical-only changes: proportional verification.
- Never weaken/remove tests to pass; no speculative behavior or tests.

## Review

- Before finishing: check requirements, acceptance criteria, scope; verify behavior via tests/linters/formatters/builds.
- Verify relevant external, version-specific, or time-sensitive facts against authoritative sources.
- Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated edits, formatting noise, debug artifacts; every changed file belongs.
- Fix in-scope issues, re-verify; never claim verification you didn't perform.

## Code style

- 2-space indentation (overrides formatter defaults).
- Markdown: markdownlint defaults + MD060; MD013 disabled. Python: Ruff default selection (E4, E7, E9, F).
- Leave unrelated code untouched.
- Repository hygiene: keep scratch files, scripts, and output outside the repo or delete them once used; never commit or abandon them.

## Git

- Stage only task-related files, never unrelated or user-owned; review the diff after each edit.
- Always commit on a branch other than `main`. Atomic commits: one logical change each, every changed file belonging to it.
- Reuse commit scopes from previous commits; add a new scope only when none fits. No commit body.
- Push or open a PR only when the user requires it. Otherwise propose one Conventional Commit message per completed feature: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, at most 72 characters. Types: `feat fix refactor perf style docs test build chore`.

## Responses

- Report what changed/found, verification run and result, relevant files/decisions, unresolved issues/assumptions/limitations.
- Prefer numbered lists for multiple points.
- Use a mermaid diagram when structure or flow beats prose and the surface renders it; fit a narrow viewport (phone, sidebar): top-down, short labels, no wide rows.
- Concise, task-focused; don't repeat the task.
