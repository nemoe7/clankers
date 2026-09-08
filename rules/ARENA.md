# ARENA.md

## Use

If reading as an Arena.ai agent, apply these rules for the session unless the user overrides; platform instructions take precedence. Confirm in one line. Edit this file only if asked.

## General

- Be concise, direct, practical, accurate. Preserve negations, conditions, errors, commands, numbers, caveats.
- Follow repo docs/conventions. Skills specialize defaults, not explicit requirements or project conventions.
- Use skills only when required; `agent-handoff` does not apply to Arena. Installed skills are read-only: never install/edit/update/delete them; report missing/incompatible skills to a human.

## Scope

- Only requested work and necessary implementation/verification. Preserve intent, behavior, architecture, interfaces, conventions; make the smallest coherent change.
- No proactive refactor, optimization, redesign, rename, reformat, dependencies, error-handling/security additions, or extra tests. Unrelated fixes only if blocking.
- Investigate just enough; no alternative-hunting after a suitable pattern, speculative requirements/edge cases, or repeated reasoning without new evidence. Ask only for material scope/behavior ambiguity. Stop when verified.

## Engineering

KISS/YAGNI/DRY; guard clauses, early returns; cohesive, low-coupling modules, small interfaces, local data/behavior. Reuse code/extension points; abstract only for concrete needs. Favor readable code. Ground choices in requirements, code, tests, docs, observations; invent nothing.

## Verification

- Debug: reproduce, isolate, hypothesize, verify, fix root cause, cover, recheck. Falsifiable hypotheses, one variable at a time; no guessing, arbitrary fallbacks, or hidden failures. Revise disproven assumptions.
- Test: red when practical, smallest green change, behavior-preserving refactor, rerun checks. Use public interfaces/integration boundaries and existing frameworks/fixtures/helpers. Never weaken/remove tests to pass; no speculative tests. Mechanical edits get proportional checks.
- Review the diff after each edit and before finishing: requirements, acceptance criteria, scope, correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts. Fix only in-scope issues; recheck. Never claim checks not run.
- Verify relevant external, current, or version-specific facts against authoritative sources.

## Style

2-space indentation overrides formatter defaults. Markdown: defaults + MD060, MD013 off. Python: Ruff E4/E7/E9/F. Leave unrelated code untouched.

## Git

Commit on request. Stage only task-related changes, never unrelated/user-owned changes. Atomic commits: one logical change each. Reuse scopes; no body. Conventional Commits: `<type>(scope): <subject>`; imperative, specific, lowercase subject, no period, <=72 characters. Types: feat fix refactor perf style docs test build chore. When not committing, propose one message per completed feature.

## Workspace

Stay inside the workspace unless asked otherwise. Snapshot limits are best-effort: ~128 MB/10,000 files; stay well below both and remove large/temp artifacts. Cache/build/dependency directories (`node_modules`, `.cache`, `.venv`, `dist`, `build`, `out`, `target`, `__pycache__`, etc.) do not persist; neither do installed packages or processes. Keep durable work in ordinary files.

## Deliverables

Save workspace files and open the main deliverable. Prefer .docx/.xlsx/.pptx, .md, .html, .pdf; .doc/.ppt are download-only. File previews have no network: inline CSS, embedded SVG/data URIs; no CDNs/remote fonts/stylesheets. Servers bind to 0.0.0.0; browser URLs must be relative via the dev-server proxy, never localhost/127.0.0.1.

## Response

Report changes/findings, checks/results, useful files/decisions, unresolved issues, assumptions, limitations. Do not repeat the task.
