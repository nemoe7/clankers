# AGENTS.md

## General

- Concise, direct, practical, accurate.
- Preserve key details: negations, conditions, errors, commands, numbers, caveats.
- Follow repo docs and conventions; prefer existing patterns. Skills specialize defaults, never weaken explicit requirements or replace project conventions.
- Unless running on Arena.ai, always load the `agent-handoff` entry point; load its templates and references only when needed. Use other installed skills only when required.
- Treat your installed skills as read-only: do not install, edit, update, or delete them. Report missing or incompatible skills; leave changes to a human maintainer.

## Scope

- Only the requested task; nothing beyond what's required, needed to verify, or necessary to complete it.
- Smallest coherent change; stop when implemented and verified.
- Preserve behavior, architecture, interfaces, intent, conventions unless change is required.
- No proactive refactor, optimize, redesign, rename, reformat, dependency change, added error-handling/security, or extra test coverage.
- Investigate only as needed; stop when enough to implement and verify; re-check only when insufficient.
- No alternative-hunting after a suitable pattern exists; no speculation on unrelated requirements or edge cases.
- Unrelated findings stay out of scope unless blocking; fix incidental issues only when they block the task.
- Ask only when ambiguity materially affects safe scope or behavior.
- Task-focused reasoning; no repeated plans/hypotheses/investigation without new evidence.

## Engineering

- KISS/YAGNI/DRY: simplest correct solution; nothing beyond requirements; reuse meaningful logic without forced abstractions.
- Guard clauses, early returns. Cohesive modules, low coupling, small interfaces, local data/behavior.
- Abstractions/seams only for tangible requirements; no parallel mechanism where an extension point fits.
- Evidence-based: requirements, code, tests, docs, observed behavior; never invent APIs, constraints, requirements.
- Clear, human-readable code; preserve APIs/behavior unless intentionally changed.

## Debugging (bugs, failures, regressions)

Reproduce → Hypothesize → Verify → Fix → Cover → Verify.

- Isolate first; falsifiable hypotheses; evidence over guessing; change one variable at a time.
- Root cause, not symptom; no arbitrary fallbacks; never conceal failures; update assumptions when disproven.
- Focused regression test for meaningful behavioral fixes; re-run checks.

## Testing (new behavior, bug fixes, refactors)

Red → Green → Refactor → Verify.

- Failing test first when practical; smallest passing change; refactor without behavior change; run tests and checks.
- Test public interfaces and meaningful integration boundaries; reuse existing frameworks/fixtures/helpers/conventions.
- Mechanical-only changes: proportional verification.
- Never weaken/remove tests to pass; no speculative behavior or tests beyond the task.

## Review

- Before finishing: check requirements, acceptance criteria, scope; verify behavior via tests/linters/formatters/builds.
- Verify external/version-specific/time-sensitive facts against authoritative sources when relevant.
- Review diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated edits, formatting noise, debug artifacts. Every changed file belongs to the change.
- Fix only in-scope issues, re-verify; never claim verification you didn't perform.

## Code style

- 2-space indentation (overrides formatter defaults); simple, readable code.
- Markdown: markdownlint defaults + MD060; MD013 (line length) disabled. Python: Ruff default selection (E4, E7, E9, F).
- Preserve architecture; leave unrelated code untouched.

## Git

- Stage only task-related files; never unrelated or user-owned. Review the diff after each edit.
- Atomic commits: one logical change per commit; every changed file belongs to it.
- Never commit directly to `main`.
- Reuse commit scopes from previous commits; add a new scope only when no existing scope fits.
- No commit body.
- Never push or open a PR unless asked. Otherwise propose one Conventional Commit message: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, no more than 72 characters. Types: `feat fix refactor perf style docs test build chore`. One message per completed feature.

## Responses

- Report what changed/found; verification run and result; relevant files/decisions when useful; unresolved issues/assumptions/limitations.
- Concise, task-focused; don't repeat the task.
