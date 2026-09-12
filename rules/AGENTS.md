# AGENTS.md

## General

- Concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats. Follow repo docs, conventions, patterns; skills specialize defaults and NEVER weaken an explicit requirement or replace a convention.
- In Arena, MUST also read and follow the repo's `ARENA.md` as an additional ruleset; it supplements, NEVER replaces, AGENTS.md.

## Scope

- Plans MUST be numbered, concrete, executable without clarification, and incomplete until they define TDD (red, green, refactor, verify; say why inapplicable) and each exact atomic commit per logical change with its message.
- MUST read project instructions before changes, then follow the approved plan, verifying each logical change. MUST stop and ask if reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- MUST do only requested work plus work strictly necessary to implement/verify it; smallest coherent change; stop when verified. Keep behavior, architecture, interfaces, intent, conventions unless change is required: NEVER proactively refactor, optimize, redesign, rename, reformat, or change a dependency or error handling/security; NEVER add tests unless requested or needed to verify.
- Investigate just enough: NEVER hunt alternatives past a suitable pattern, speculate on unrelated requirements or edge cases, or replan without new evidence. Unrelated findings stay out of scope unless blocking. Material ambiguity = reasonable readings that could change behavior/data/interfaces/scope/outcome: ask only then; else assume the most reasonable, stating it when it materially affects the result.

## Engineering

- KISS/YAGNI/DRY, laziest working solution: stop at the first rung that holds — needed at all; helper/pattern already here; stdlib; native feature; installed dependency; one line; minimum code. NEVER add a dependency for a few lines' work.
- Build what is asked; name a relevant lazier alternative in one line, user picks, no commentary when none applies. Never lazy about understanding: read code, trace flow first. NEVER simplify away trust-boundary validation, data-loss error handling, security, or accessibility; mark a corner-cut with a `simplified:` comment naming ceiling and upgrade path.
- Guard clauses, early returns; cohesive modules, low coupling, small interfaces, local data/behavior; NEVER an unrequested abstraction, boilerplate, or scaffolding; seams only for tangible needs, never a parallel mechanism where an extension point fits.
- Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement. Write clear, readable code.

- Consider proposing smaller scope for approval over silent trims; simplicity chooses how, never what. Prefer deletion over addition, boring over clever, fewest files, and searching for a helper first. Prefer the simplest implementation meeting every criterion, the edge-case-correct stdlib pick on ties, and safe defaults only when non-material; if the user insists on the full version, build it without re-arguing.

## Debugging

Bugs, failures, regressions: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck. MUST grep every caller of the function before editing; fix once where all callers route through. Falsifiable hypotheses, evidence over guessing, one variable at a time; NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption. Behavioral fixes get a focused regression test.

## Testing

New behavior, fixes, refactors: when a test is appropriate, failing test first, smallest passing change, refactor without behavior change, rerun checks. Test public interfaces and integration boundaries; reuse frameworks/fixtures/helpers/conventions. Mechanical edits get proportional checks. NEVER weaken or drop a test to pass; no speculative behavior or tests. Prefer one small runnable check for non-trivial logic; introduce no new frameworks or fixtures unless asked; trivial one-liners need no test.

## Review

Before finishing check requirements, acceptance criteria, scope; verify behavior via tests/linters/formatters/builds, and external, version-specific, or time-sensitive facts against authoritative sources. Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs. Fix in-scope issues and recheck. **NEVER claim a check you did not run**; report what you skipped instead. Confirm planned changes, checks, commits, and cleanup are done.

## Code style

2-space indentation overrides formatter defaults. Markdown: markdownlint defaults + MD060, MD007 indent 2, MD013 off. Python: Ruff defaults (E4, E7, E9, F). Python uses the repo's `ruff.toml` (Ruff defaults, `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, `required-version = "0.16.6"`); if missing, create it exactly before gates. Gates before every commit: `ruff check` and `ruff format`, no CLI rule overrides. Leave unrelated code alone. MUST keep repository hygiene: scratch files, scripts, and output stay outside the repo or are deleted once used, including generated plan files.

## Git

- MUST stage only task-related files, NEVER unrelated or user-owned; respect the user's global gitignore (`core.excludesFile`); review the diff after each edit.
- MUST commit directly on a branch other than `main`, one logical change per commit with every changed file in it, each keeping checks green and independently revertible. One Conventional Commit per change: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, <=72 chars, no body. Types: `feat fix refactor perf style docs test build chore`. Reuse previous scopes, adding one only when none fits. NEVER push or open a PR unless asked.

## Responses

- Report changes/findings, checks and results, useful files/decisions, unresolved issues, assumptions, limitations; prefer numbered lists for multiple points; no unnecessary prose; detail when the task or user requires. Never repeat the task. Consider reporting skipped alternatives with add-when triggers.
- Default to mermaid for pipelines, diagrams, and flow visualizations where the surface renders it; fit a narrow viewport (phone, sidebar): `flowchart TB`, short labels, no unnecessarily wide rows.
