# Clankers

Rules and skills for AI agents.

- [rules/](rules/): shared and platform-specific agent instructions, ChatGPT custom instructions, and commit-message rules. The specification and setup details are in [rules/README.md](rules/README.md).
- [skills/](skills/): reusable skills for handoffs, planning, simpler code, frontend design, and UI reviews. Each skill has a `SKILL.md` entry point and any supporting files.

`apply_rules.py` copies the global rule files. `apply.bat` runs it on Windows.

## Instruction budgets

Latest measurements as of 2026-09-08. ARENA.md is measured by uploaded file size and CHATGPT.txt by its custom-instruction character limit; the remaining agent-facing rule files and `SKILL.md` entry files use `cl100k_base` tokens. Supporting files loaded on demand are not included.

| File | Measure | Current |
| --- | --- | --- |
| `rules/AGENTS.md` | `cl100k_base` tokens | 893 |
| `rules/ARENA.md` | UTF-8 file size | 3,718 bytes |
| `rules/CHATGPT.txt` | Unicode characters | 1,446 / 1,500 |
| `rules/CLINE.md` | `cl100k_base` tokens | 625 |
| `rules/COMMIT_SPEC.txt` | `cl100k_base` tokens | 46 |
| `skills/agent-handoff/SKILL.md` | `cl100k_base` tokens | 837 |
| `skills/frontend-design/SKILL.md` | `cl100k_base` tokens | 1,058 |
| `skills/planning/SKILL.md` | `cl100k_base` tokens | 842 |
| `skills/ponytail/SKILL.md` | `cl100k_base` tokens | 1,596 |
| `skills/web-design-guidelines/SKILL.md` | `cl100k_base` tokens | 287 |

Measurements cover complete files, including whitespace and markup.
