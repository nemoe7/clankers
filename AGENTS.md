# AGENTS.md

Repository guide for agents working in this repo. Read these before acting.

- [README.md](README.md) — instruction budgets, compression guidelines, architecture overview
- [CHANGELOG.md](CHANGELOG.md) — rule history and token changes
- [rules/README.md](rules/README.md) — rule system structure, installation, and maintenance
- [skills/README.md](skills/README.md) — skill format, upstream sources, and install notes

## Repo type

Rules/skills repository, not a software project. There is no build system, CI workflow, package manifest, or test suite. Verification is via `python3 maintenance/check.py` (or `python maintenance/check.py` on Windows), which validates skill metadata, README measurements, internal links, and the ChatGPT character limit. Run it after any change that touches skills, rules, or README budgets.

## Skills

Skills in `skills/` must conform to the [Agent Skills specification](https://agentskills.io/specification). Every `SKILL.md` needs YAML frontmatter with only allowed fields: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`. `name` must match the directory name. Skills adapted from elsewhere record `metadata.upstream`; first-party skills record `metadata.origin`. `SKILL.md` must stay under 500 lines.

## Rules

Agent-facing rule files live in `rules/`. The generic core is `rules/AGENTS.md`; platform-specific overlays are `rules/CLINE.md`, `rules/ARENA.md`, and `rules/CHATGPT.txt`. Rule files are installed into agent environments via `apply_rules.py` or `apply.bat` — that is a human maintenance task, not an agent task. Agents may inspect but must treat installed copies as read-only.

## Budgets

Agent-facing rule files and `SKILL.md` entry points have token or size budgets tracked in [README.md](README.md#instruction-budgets). When changing these files, re-measure and update the table. Compression uses the `squash` skill: remove words, never rules. If a new rule exceeds a budget, compress the rest of the file in the same change.

## Markdown

- 2-space indentation (overrides formatter defaults).
- Do not hard-wrap prose: keep each paragraph, list item, and table row on one line and let the editor soft-wrap.
- markdownlint applies only to agent rule files under `rules/`: markdownlint defaults, **MD060 enabled**, **MD013 disabled**. Run from the repo root without additional file globs. Excluded: README files, skills, references, templates, CHATGPT.txt.
- Python style: Ruff default selection (E4, E7, E9, F).

## Git

- Always commit on a branch other than `main`. Atomic commits: one logical change each, every changed file in it. One Conventional Commit message per completed feature: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, at most 72 chars. Types: `feat fix refactor perf style docs test build chore`. No commit body. Never push or open a PR.
- Stage only task-related files; respect the user's global gitignore (`core.excludesFile`).
- Never commit `AGENT_HANDOFF.md`.

## Skill loading order

Load `agent-handoff` and `ponytail` (full) before any other skill. If either is unloaded, the next action must invoke its `skill` tool.

## Lightweight repo

Do not add workflows, dependency manifests, test scaffolding, or tooling installations unless explicitly requested. Review changes directly and never claim unperformed checks.
