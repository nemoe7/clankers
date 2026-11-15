# AGENTS.md

## Project Overview

**Use**:
- These rules outrank skill and plugin instructions.
- An explicit user instruction in chat outranks this file, confirmed in one line.

**Key Terms**:
- `house` = this repository; `house rules` = this AGENTS.md
- `arena suite` = ARENA.md + arena-steering files

**Primary Documentation**:
- [README.md](README.md) — budgets, compression procedure, layout
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — rule, prompt, automation, maintenance history
- [rules/README.md](rules/README.md) — rule structure, installation, maintenance
- [rules/refs/GUIDELINES.md](rules/refs/GUIDELINES.md) — standard for writing agent rules
- [system-prompts/refs/GUIDELINES.md](system-prompts/refs/GUIDELINES.md) — standard for writing system prompts
- [skills/README.md](skills/README.md) — skill format, upstream sources, install notes
- [maintenance/README.md](maintenance/README.md) — validation and measurement tooling
- Each module has its own CHANGELOG.md in `docs/`

**Rules**:
- Agent-facing rules in `rules/`; ChatGPT field copies in `rules/wenyan/` (see `rules/README.md`)
- Overlays are applied over a base and should not need to conform to the GUIDELINES skeleton.
- Baseline in `refs/` (uncompressed source); everything else including wenyan is live (compressed)

**System Prompts**:
- System prompts in `system-prompts/`; field copies in `system-prompts/wenyan/` (see `system-prompts/README.md`)
- Baseline in `refs/`; everything else is live

**GPT Plugins**:
- ChatGPT skills/plugins in `gpt-plugins/` (see `docs/gpt-plugins/README.md`)

**Userscripts**:
- Userscripts in `userscripts/`; baseline in `userscripts/refs/` (see `userscripts/AGENTS.md`)

**Skills**:
- ChatGPT-related skills ALWAYS go to gpt-plugins.
- Skills follow the [Agent Skills specification](https://agentskills.io/specification).
- A skill holds only what an agent needs to use it; design decisions, background, rationale, and history go to `docs/<skill>/CHANGELOG.md`.
- The file stays under 500 lines.

## Setup Commands

- ARENA.md's NEVER-edit-this-file clause is waived in this repository.
- Mirror task-related source changes into installed copies in this repository without separate user authorization.
- Follow the clause-proposal and approval scope in the [amendment template](maintenance/amendment-template.md).
- `npx --yes markdownlint-cli2` from repository root.
- `ruff format .`, then `ruff check .`.
- `python maintenance/check.py` (add `--update` to refresh README measurements).
- Run the full test suite of the affected module (e.g., if arena-steering changed, run arena-steering's full suite).

## Code Style

- 2-space indentation, overriding formatter defaults.
- See `.markdownlint-cli2.jsonc` for Markdown rules.
- See `pyproject.toml` for Ruff configuration.
- Use `nemoizer` for prose linting; see `nemoizer.toml` for scope and exclusions.
- Compression: squash text against a size budget, measured in tokens/words/chars/bytes, removing words but never content. Use the [squash skill](skills/squash/SKILL.md); squash every `README.md` and file in `docs/` against the [compression procedure](README.md#compression); prose is not exempt.

**Instruction Budgets**:
- Keep root `AGENTS.md` outside the instruction measurement table.
- NEVER use instruction measurements as fixed size ceilings.
- Target a smaller size than the previous version for every amended instruction file.
- Accept unavoidable size growth.
- Rule files, `SKILL.md` entry points, and other clause files have budgets tracked in [README.md](README.md#instruction-budgets).
- Re-measure and update the table when changing them.

## Testing Instructions

See Setup Commands above.

## PR Guidelines

**Changelog**:
- Keep one dated entry per date (`## YYYY-MM-DD`) for unsemver'd files.
- Group changes by [Keep a Changelog](https://keepachangelog.com/) type and then domain.
- Omit Unreleased.
- NEVER cite literal file paths; use the domain heading as the reference.

**Amendments**:
- Before editing any clause in an agent-facing file, submit a proposal using the [amendment template](maintenance/amendment-template.md).
- Pair CORE proposals with ARENA and CHATGPT proposals in the same submission.
- No clause in an agent-facing file is added, amended, or deleted until the user approves the proposal.
- Edits that change no clause — a squash that removes no rule, a typo or link fix, formatting, a re-measure — need no proposal.
- Exclude `.agents/` from proposals; unchanged third-party copies are exempt.
- Propose every clause from refs, including owner text.
- A custom answer on a clause takes a fresh proposal of the new wording; the line lands only after that proposal is approved.

**Commits**:
- One Conventional Commit subject per change: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, at most 72 chars, no body.
- Types: `feat fix refactor perf style docs test build chore`.
- Merges MUST be rebase merges: rebase onto the target, then merge; no merge commit.
- ALWAYS bump each changed module's version one step above main per PR.

## Constraints & Boundaries

- NEVER add CI workflows, dependency manifests, test scaffolding, or tooling installs unless explicitly requested.