# Clankers

Rules, skills, and workflows for AI agents.

- [rules/](rules/): shared and platform-specific agent instructions, ChatGPT's two custom-instruction fields, and commit-message rules. The specification and setup details are in [rules/README.md](rules/README.md).
- [skills/](skills/README.md): reusable skills for UI reviews, text compression, and a shared Arena preview for steering and rendered reports. Each skill has a `SKILL.md` entry point and any supporting files.
- [workflows/](workflows/README.md): portable agent workflows, currently [init-docs](workflows/init-docs.md), which bootstraps repo docs for downstream users and agents. Its README gives the format that a new workflow must meet.
- [automations/](automations/DAILIES.md): prompts for recurring runs, currently the combined daily monitoring task, which runs as a ChatGPT scheduled monitoring task. Each prompt is a self-contained Markdown file executed in one pass, carrying its own state and evidence rules because the runtime keeps no reliable state.
- [maintenance/](maintenance/README.md): validation and README measurement tooling, requiring `markdown-it-py` and `tiktoken`.
- [rules/refs/](rules/refs/README.md): uncompressed rule originals and the AGENTS.md writing guidelines. Amend here first. Then mirror the amendment into the live file in compressed form, and squash it.
- [skills/refs/](skills/refs/): complete unsquashed source trees for skills with baselines. Amend here first, then squash the live `SKILL.md`.

`rules/apply.py` copies the global rule files. `apply.bat` runs it on Windows.

## Instruction budgets

Latest measurements as of 2026-09-21. `maintenance/check.py` measures ARENA.md by uploaded file size. It measures the two ChatGPT files by their custom-instruction character limits. The remaining agent-facing rule files and `SKILL.md` entry files use `cl100k_base` tokens. The two preview skills are the exception. The check measures them by UTF-8 file size instead. A byte count needs no tokenizer, so it survives a sandbox where the `tiktoken` cache cannot be seeded. This table excludes supporting files loaded on demand, including skill refs. The three `assets/` rows and three `scripts/` rows are the minified build that the preview skill ships. Their recorded size is their budget, and `maintenance/minify.py` rebuilds them from the readable refs sources.

| File | Measure | Current |
| --- | --- | --- |
| `rules/AGENTS.md` | `cl100k_base` | 1,571 `tok` |
| `rules/ARENA.md` | `UTF-8 file size` | 13,198 `B` |
| `rules/CHATGPT-CUSTOM.txt` | `Unicode chars` | 1,494 `chars` |
| `rules/CHATGPT-MORE.txt` | `Unicode chars` | 1,475 `chars` |
| `rules/CLINE.md` | `cl100k_base` | 517 `tok` |
| `rules/KILO.md` | `cl100k_base` | 72 `tok` |
| `rules/kilo/code.md` | `cl100k_base` | 232 `tok` |
| `rules/kilo/debug.md` | `cl100k_base` | 288 `tok` |
| `rules/kilo/plan.md` | `cl100k_base` | 251 `tok` |
| `rules/COMMIT-SPEC.txt` | `cl100k_base` | 129 `tok` |
| `skills/arena-preview-steering/SKILL.md` | `UTF-8 file size` | 11,361 `B` |
| `skills/arena-preview-reporting/SKILL.md` | `UTF-8 file size` | 5,482 `B` |
| `skills/arena-preview-steering/assets/app.js` | `UTF-8 file size` | 24,242 `B` |
| `skills/arena-preview-steering/assets/index.html` | `UTF-8 file size` | 6,486 `B` |
| `skills/arena-preview-steering/assets/style.css` | `UTF-8 file size` | 9,997 `B` |
| `skills/arena-preview-steering/scripts/preview.py` | `UTF-8 file size` | 51,324 `B` |
| `skills/arena-preview-steering/scripts/check_preview.py` | `UTF-8 file size` | 41,626 `B` |
| `skills/arena-preview-steering/scripts/check_client.cjs` | `UTF-8 file size` | 41,510 `B` |
| `skills/squash/SKILL.md` | `cl100k_base` | 1,265 `tok` |
| `skills/web-interface-guidelines/SKILL.md` | `cl100k_base` | 531 `tok` |
| `workflows/init-docs.md` | `cl100k_base` | 4,825 `tok` |

Measurements cover complete files, including whitespace and markup.

## Compression

Compress the agent-facing rule files against the budgets above with the [`squash` skill](skills/squash/SKILL.md). That skill is an extraction of the rules below. Amend `rules/refs/` first. Then mirror the amendment into its live counterpart in compressed form, and squash only the new or affected line. On a removal, attempt one squash and keep the lower budget. Refs stay uncompressed as the baseline. Compression is editorial, not lossy: it removes words, never rules.

1. Work in iterations. After each pass, re-measure and compare against the previous value. Keep the pass only when the budget improves. Repeat until a pass yields nothing.
2. Preserve every negation, condition, command, number, threshold, filename, and caveat. Removing a constraint is a rule change, not compression.
3. Merge related bullets, drop redundant qualifiers and restated clauses, and prefer the shorter of two equivalent phrasings. Do not invent new abbreviations or telegraphic syntax that changes how a rule reads.
4. Keep the section headings and order that the refs baseline already has. Restructuring is an amendment, and you must make it in refs first.
5. New clause: squash only that new line. Amended clause: squash only the affected line. Removed clause: attempt one squash and keep whichever budget is lower.
6. Update the budgets table above, record notable reductions in [CHANGELOG.md](CHANGELOG.md), and record a growth accepted rather than funded in [docs/archive/budget-exceptions.md](docs/archive/budget-exceptions.md).

Recorded exceptions live in [docs/archive/budget-exceptions.md](docs/archive/budget-exceptions.md). An exception is a growth that the owner accepted rather than funded, and it carries its date, its numbers, and its reason. So this page keeps the procedure and the current measurements only.
