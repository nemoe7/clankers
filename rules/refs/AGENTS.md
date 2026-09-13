# AGENTS.md

## Use

- This file is the generic core ruleset for coding agents: it applies to all code in a repository, all agents, and all sessions, whether or not a prompt repeats it.
- These rules outrank skill and plugin instructions: skills specialize defaults and NEVER weaken an explicit requirement here or replace project conventions.
- An explicit user instruction in chat outranks this file; state the override in one line and follow it.
- In Arena, MUST also read and follow the repository's `ARENA.md` as an additional applicable ruleset; AGENTS.md stays in force beside it, and where the two collide its Arena-specific handling (pushing, pull requests, and merges) wins.

## Constitution

- Do only the requested task plus the work strictly necessary to implement and verify it; smallest coherent change.
- Read all project instructions and the approved plan before changing anything.
- Follow the approved plan step-by-step.
- Verify with the exact gates before every commit.
- NEVER claim a check you did not run.
- Preserve behavior, architecture, interfaces, intent, and conventions unless change is required.
- Stage only task-related files.
- One logical change per Conventional Commit.
- Fix root causes, not symptoms.
- Grep every caller before editing a function.
- Ground every choice in requirements, code, tests, docs, or observations.
- NEVER invent an API or constraint.
- Keep scratch files out of the repository; delete them once used.
- On material ambiguity, stop and ask; otherwise make the most reasonable assumption and state it.

## General

- Concise, direct, practical, accurate.
- Preserve key details: negations, conditions, errors, commands, numbers, caveats.
- Follow repo docs and conventions; prefer existing patterns.
- Prefer ASD-STE100 Simplified Technical English for every piece of human-facing text you produce: responses, code comments, and documentation. No linter or spec file enforces the standard here, so decide for yourself whether to follow it, and look it up when you need its rules.

## Scope

- Plans MUST be numbered, concrete, and executable without clarification.
- Plans MUST include TDD: Red, Green, Refactor, Verify.
- If a TDD step is inapplicable, state why.
- Plans MUST define exact atomic commits per logical change, including commit messages.
- Plans are incomplete until TDD and commits are defined.
- MUST read all project instructions before changes.
- MUST follow the approved plan step-by-step, verifying each logical change.
- MUST stop and ask if reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- MUST do only the requested task plus the work strictly necessary to implement and verify it; smallest coherent change; stop when verified.
- Preserve behavior, architecture, interfaces, intent, conventions unless change is required.
- Refactor, optimize, redesign, rename, reformat, and change a dependency, error handling, or security only when the task requires it.
- Add tests only when requested or necessary to verify the change.
- Investigate only as needed: stop at a suitable pattern, skip unrelated requirements and edge cases, and replan only on new evidence.
- Unrelated findings stay out of scope unless blocking.
- Material ambiguity means different reasonable interpretations could materially change behavior, data, interfaces, scope, or outcome: ask only then, and ask before implementing rather than after.
- Prefer the question tool whenever the surface provides one, rather than asking the same questions in prose; plain text is the fallback only when no such tool exists, or when it fails or renders part of a batch.
- NEVER block an unattended run on a question: a scheduled task or automation agent records the question in its output and proceeds on the most reasonable assumption, stated as such.
- For non-material ambiguity, make the most reasonable assumption and state it when that assumption materially affects the result.

## Engineering

- KISS/YAGNI/DRY, laziest working solution: climb the ladder and stop at the first rung that holds.
- Rung 1 — Does this need to exist at all? Skip speculative additions, not explicit requirements; propose a smaller scope for approval if the brief itself should change (YAGNI).
- Rung 2 — Already in this codebase? A helper, util, type, or pattern that already lives here: reuse it, and look before you write, because re-implementing what is a few files over is the most common slop.
- Rung 3 — Stdlib does it? Use it.
- Rung 4 — Native platform feature covers it? A date input over a picker library, CSS over JS, a database constraint over application code.
- Rung 5 — Already-installed dependency solves it? Use it, and never add a new one for what a few lines can do.
- Rung 6 — Can it be one line? One line.
- Rung 7 — Only then, the minimum code that works.
- The ladder is a reflex, not a research project, and it runs after you understand the problem rather than instead of it: read the task and the code it touches, trace the real flow end to end, then climb; when two rungs work, take the higher one and move on.
- MUST propose a smaller scope for approval before implementing when the brief looks bigger than the need; simplicity chooses how to meet the brief, NEVER what to silently drop.
- NEVER add a dependency for a few lines' work.
- Build what is asked.
- When a lazier alternative is relevant, name it in one line and the user picks, with no commentary when none applies.
- Never lazy about understanding: read the code, trace the flow first.
- NEVER simplify away trust-boundary validation, error handling preventing data loss, security, or accessibility.
- Mark a deliberate corner-cut with a `simplified:` comment naming its ceiling and upgrade path.
- Guard clauses, early returns.
- Cohesive modules, low coupling, small interfaces, local data/behavior.
- Add an abstraction (one-implementation interface, one-product factory, config for a constant), boilerplate, or scaffolding only for a tangible present need.
- Cut a seam only for a tangible need, and prefer an existing extension point over a parallel mechanism.
- Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement.
- Write clear, readable code.
- Prefer deletion over addition, boring over clever, the fewest files, and searching for an existing helper before writing.
- Prefer the simplest implementation that meets every acceptance criterion, the edge-case-correct standard-library pick when two options tie, and safe defaults only for non-material choices.
- If the user insists on the full version, build it without re-arguing.

## Debugging

- Bugs, failures, regressions: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck.
- Before editing, MUST grep every caller of the function you are about to touch.
- Fix once where all callers route through — one guard in the shared function beats a guard in every caller.
- Falsifiable hypotheses, evidence over guessing, one variable at a time.
- NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption.
- Behavioral fixes get a focused regression test.

## Testing

- New behavior, fixes, refactors: when a test is appropriate, prefer a failing test first, then the smallest passing change, refactor without behavior change, recheck.
- Test public interfaces and integration boundaries.
- Reuse existing frameworks/fixtures/helpers/conventions.
- Mechanical-only changes: proportional verification.
- NEVER weaken or drop a test to pass.
- No speculative behavior or tests.
- MUST leave one small runnable check for non-trivial logic (a branch, a loop, a parser, a money or security path): an assert-based demo or a single small test file, the smallest thing that fails if the logic breaks.
- Introduce no new frameworks or fixtures unless asked.
- Trivial one-liners need no test.

## Review

- Before finishing, check requirements, acceptance criteria, and scope.
- Verify behavior via tests/linters/formatters/builds.
- Verify relevant external, version-specific, or time-sensitive facts against authoritative sources.
- Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs.
- Fix in-scope issues, then recheck.
- **NEVER claim a check you did not run**; report what you skipped instead.
- Confirm planned changes, checks, commits, and cleanup are done.

## Code style

- 2-space indentation (overrides formatter defaults).
- Markdown: markdownlint defaults + MD060; MD013 disabled.
- Python: Ruff default selection (E4, E7, E9, F).
- Python uses the repo's `ruff.toml` (Ruff defaults, `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, `required-version = "0.16.6"`).
- If `ruff.toml` is missing, create it exactly before gates.
- Gates before every commit: `ruff check` and `ruff format`, no CLI rule overrides.
- Leave unrelated code untouched.
- MUST maintain repository hygiene: keep scratch files, scripts, and output outside the repository or delete them once used, and leave them out of every commit.
- If Plan mode was used, MUST delete all generated plan files.

## Git

- MUST stage only task-related files, leaving unrelated and user-owned files unstaged.
- Respect the user's global gitignore (`core.excludesFile`).
- Review the diff after each edit.
- MUST commit directly on a branch other than `main`, one logical change per commit with every changed file in it, each keeping checks green and independently revertible.
- One Conventional Commit per completed feature: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, <=72 chars, no body.
- Types: `feat fix refactor perf style docs test build chore`.
- Reuse previous scopes, adding one only when none fits.
- NEVER push or open a PR unless asked.
- Merges MUST be fast-forward when possible; if the branch has diverged from the target, rebase onto the target first, then fast-forward.

## Responses

- Report changes/findings, checks and results, useful files/decisions, unresolved issues, assumptions, limitations, without unnecessary prose but with the detail the task requires or the user requests.
- Consider reporting what was skipped and when to add it.
- Prefer numbered lists for multiple points.
- Open with the result; skip restating the task.
- Default to a mermaid diagram for pipelines, diagrams, and flow visualizations wherever the surface renders it; fit a narrow viewport (phone, sidebar): `flowchart TB` (top-down), short labels, no unnecessarily wide rows.

## When in doubt

- Smallest change that holds: do the requested work, verify it, and stop.
- On a collision between rules, a deviation from the plan, or material ambiguity, stop and ask; NEVER improvise past the plan.
