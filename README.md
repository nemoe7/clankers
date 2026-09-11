# Clankers

Rules, skills, and workflows for AI agents.

- [rules/](rules/): shared and platform-specific agent instructions, ChatGPT custom instructions, and commit-message rules. The specification and setup details are in [rules/README.md](rules/README.md).
- [skills/](skills/README.md): reusable skills for planning, simpler code, frontend design, UI reviews, and text compression. Each skill has a `SKILL.md` entry point and any supporting files.
- [workflows/](workflows/README.md): portable agent workflows, currently repository documentation initialization. Each workflow is a self-contained Markdown file usable as-is.
- [maintenance/](maintenance/README.md): validation and README measurement tooling, requiring `markdown-it-py` and `tiktoken`.

`rules/apply.py` copies the global rule files. `apply.bat` runs it on Windows.

## Instruction budgets

Latest measurements as of 2026-09-11. ARENA.md is measured by uploaded file size and CHATGPT.txt by its custom-instruction character limit; the remaining agent-facing rule files, `SKILL.md` entry files, and workflow files use `cl100k_base` tokens. Supporting files loaded on demand are not included.

| File | Measure | Current |
| --- | --- | --- |
| `rules/AGENTS.md` | `cl100k_base` | 1,059 `tok` |
| `rules/ARENA.md` | `UTF-8 file size` | 7,093 `B` |
| `rules/CHATGPT.txt` | `Unicode chars` | 1,495 `chars` |
| `rules/CLINE.md` | `cl100k_base` | 580 `tok` |
| `rules/COMMIT_SPEC.txt` | `cl100k_base` | 58 `tok` |
| `skills/frontend-design/SKILL.md` | `cl100k_base` | 2,011 `tok` |
| `skills/planning/SKILL.md` | `cl100k_base` | 871 `tok` |
| `skills/ponytail/SKILL.md` | `cl100k_base` | 1,675 `tok` |
| `skills/squash/SKILL.md` | `cl100k_base` | 1,263 `tok` |
| `skills/web-interface-guidelines/SKILL.md` | `cl100k_base` | 523 `tok` |
| `workflows/init-docs.md` | `cl100k_base` | 4,102 `tok` |

Measurements cover complete files, including whitespace and markup.

## Compression

Agent-facing rule files are compressed against the budgets above with the [`squash` skill](skills/squash/SKILL.md), which is an extraction of these guidelines. Compression is editorial, not lossy: it removes words, never rules.

1. Work in iterations. After each pass, re-measure and compare against the previous value; keep the pass only when the budget improves. Repeat until a pass yields nothing.
2. Preserve every negation, condition, command, number, threshold, filename, and caveat. Removing a constraint is a rule change, not compression.
3. Merge related bullets, drop redundant qualifiers and restated clauses, and prefer the shorter of two equivalent phrasings. Do not invent new abbreviations or telegraphic syntax that changes how a rule reads.
4. Keep section headings and their order. Compression does not restructure the rule set.
5. Adding a rule may exceed a budget; compress the rest of the file in the same change so the file lands at or below its prior measurement.
6. Update the budgets table above and record notable reductions in [CHANGELOG.md](CHANGELOG.md).
