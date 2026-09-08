# Clankers

Rules and skills for AI agents.

- [rules/](rules/): shared and platform-specific agent instructions, ChatGPT custom instructions, and commit-message rules. The specification and setup details are in [rules/README.md](rules/README.md).
- [skills/](skills/): reusable skills for handoffs, planning, simpler code, frontend design, and UI reviews. Each skill has a `SKILL.md` entry point and any supporting files.

`apply_rules.py` copies the global rule files. `apply.bat` runs it on Windows.

## Token counts

Latest counts as of 2026-09-08, using `cl100k_base` via `tiktoken 0.12.0`. Counts cover complete files, including whitespace and markup—not model-specific billing.

Only agent-facing rule files and `SKILL.md` entry points are tracked. Supporting files loaded on demand are not included. See [CHANGELOG.md](CHANGELOG.md) for previous counts and changes.

| File | Tokens |
| --- | --- |
| `rules/AGENTS.md` | 923 |
| `rules/ARENA.md` | 818 |
| `rules/CHATGPT.txt` | 292 |
| `rules/CLINE.md` | 752 |
| `rules/COMMIT_SPEC.txt` | 46 |
| `skills/agent-handoff/SKILL.md` | 873 |
| `skills/frontend-design/SKILL.md` | 1,058 |
| `skills/planning/SKILL.md` | 910 |
| `skills/ponytail/SKILL.md` | 1,596 |
| `skills/web-design-guidelines/SKILL.md` | 287 |
