# AGENTS.md

Guide for agents in this repository. Read these first.

- [README.md](README.md) — budgets, compression procedure, layout
- [CHANGELOG.md](CHANGELOG.md) — rule history and token changes; always follow its stated entry rule, one entry per pull request, extending the open entry while its pull request is unmerged
- [rules/README.md](rules/README.md) — rule structure, installation, maintenance
- [skills/README.md](skills/README.md) — skill format, upstream sources, install notes
- [maintenance/README.md](maintenance/README.md) — validation and measurement tooling

## Repo type

A rules/skills repository, not a software project: no build system, package manifest, or test suite. Verify with `python3 maintenance/check.py` (`python` on Windows), which needs `markdown-it-py` and `tiktoken` and validates skill metadata, README measurements, internal links, and the ChatGPT character limit. Run it after changing skills, rules, or README budgets. `.github/workflows/validate.yml` runs the same check on every push and pull request, commits refreshed README measurements, and lints Markdown.

## Skills

Skills in `skills/` follow the [Agent Skills specification](https://agentskills.io/specification). Every `SKILL.md` needs YAML frontmatter using only `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`; `name` matches its directory; adapted skills record `metadata.upstream`, first-party ones `metadata.origin`; the file stays under 500 lines.

## Rules

Agent-facing rule files live in `rules/`: the generic core `AGENTS.md` and the platform overlays `CLINE.md`, `ARENA.md`, `CHATGPT.txt`. Installing them via `rules/apply.py` or `apply.bat` is human maintenance, not an agent task; treat installed copies as read-only.

## Budgets

Rule files and `SKILL.md` entry points have budgets tracked in [README.md](README.md#instruction-budgets); re-measure and update the table when changing them. Compression removes words, never rules. A new rule may exceed a budget only if the rest of the file is compressed in the same change.

## Markdown

- 2-space indentation, overriding formatter defaults.
- No hard-wrapped prose: one line per paragraph, list item, and table row, soft-wrapped by the editor.
- markdownlint covers only `rules/*.md`, **MD060 enabled**, **MD013 disabled**; run markdownlint-cli2 from the repository root with no extra globs. README files, skills, references, and CHATGPT.txt are excluded.
- Python: Ruff default selection (E4, E7, E9, F).

## Git

Commit on a branch other than `main`, one logical change per commit with every changed file in it. One Conventional Commit subject per change: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, at most 72 chars, no body. Types: `feat fix refactor perf style docs test build chore`. Stage only task-related files. Never push or open a pull request unless asked.

## Lightweight repo

Add no further workflows, dependency manifests, test scaffolding, or tooling installs unless explicitly requested. Review changes directly and never claim unperformed checks.
