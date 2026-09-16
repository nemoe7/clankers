# Clankers

Rules, skills, and workflows for AI agents.

- [rules/](rules/): shared and platform-specific agent instructions, ChatGPT's two custom-instruction fields, and commit-message rules. The specification and setup details are in [rules/README.md](rules/README.md).
- [skills/](skills/README.md): reusable skills for UI reviews, text compression, and live steering of an Arena session. Each skill has a `SKILL.md` entry point and any supporting files.
- [workflows/](workflows/README.md): portable agent workflows, currently [init-docs](workflows/init-docs.md), which bootstraps repo docs for downstream users and agents; its README defines the format one must meet.
- [automations/](automations/DAILIES.md): prompts for recurring runs, currently the combined daily monitoring task, which runs as a ChatGPT scheduled monitoring task. Each prompt is a self-contained Markdown file executed in one pass, carrying its own state and evidence rules because the runtime keeps no reliable state.
- [maintenance/](maintenance/README.md): validation and README measurement tooling, requiring `markdown-it-py` and `tiktoken`.
- [rules/refs/](rules/refs/README.md): uncompressed rule originals and the AGENTS.md writing guidelines; amend here first, mirror the amendment into the live file in compressed form, then squash it.

`rules/apply.py` copies the global rule files. `apply.bat` runs it on Windows.

## Instruction budgets

Latest measurements as of 2026-09-16. ARENA.md is measured by uploaded file size and the two ChatGPT files by their custom-instruction character limits; the remaining agent-facing rule files and `SKILL.md` entry files use `cl100k_base` tokens. Supporting files loaded on demand, including a skill's `BASELINE.md`, are not included.

| File | Measure | Current |
| --- | --- | --- |
| `rules/AGENTS.md` | `cl100k_base` | 1,785 `tok` |
| `rules/ARENA.md` | `UTF-8 file size` | 9,671 `B` |
| `rules/CHATGPT-CUSTOM.txt` | `Unicode chars` | 1,490 `chars` |
| `rules/CHATGPT-MORE.txt` | `Unicode chars` | 1,473 `chars` |
| `rules/CLINE.md` | `cl100k_base` | 572 `tok` |
| `rules/COMMIT-SPEC.txt` | `cl100k_base` | 129 `tok` |
| `skills/arena-live-steering/SKILL.md` | `cl100k_base` | 1,756 `tok` |
| `skills/squash/SKILL.md` | `cl100k_base` | 1,263 `tok` |
| `skills/web-interface-guidelines/SKILL.md` | `cl100k_base` | 531 `tok` |
| `workflows/init-docs.md` | `cl100k_base` | 4,825 `tok` |

Measurements cover complete files, including whitespace and markup.

## Compression

Agent-facing rule files are compressed against the budgets above with the [`squash` skill](skills/squash/SKILL.md), which is an extraction of the rules below. Amend `rules/refs/` first, mirror the amendment into its live counterpart in compressed form, then squash that file back under budget; refs stay uncompressed as the baseline. Compression is editorial, not lossy: it removes words, never rules.

1. Work in iterations. After each pass, re-measure and compare against the previous value; keep the pass only when the budget improves. Repeat until a pass yields nothing.
2. Preserve every negation, condition, command, number, threshold, filename, and caveat. Removing a constraint is a rule change, not compression.
3. Merge related bullets, drop redundant qualifiers and restated clauses, and prefer the shorter of two equivalent phrasings. Do not invent new abbreviations or telegraphic syntax that changes how a rule reads.
4. Keep the section headings and order the refs baseline already has; restructuring is an amendment, made in refs first.
5. Adding a rule may exceed a budget; compress the rest of the file in the same change so the file lands at or below its prior measurement.
6. Update the budgets table above and record notable reductions in [CHANGELOG.md](CHANGELOG.md).

Two deliberate exceptions are recorded, both from 2026-09-13: `rules/AGENTS.md` carries +87 `tok` (1,731 → 1,818) and `rules/ARENA.md` +636 `B` (9,205 → 9,841) for the seven-rung ladder and the three MUST upgrades voted in on request, accepted rather than squashed. Those measurements were the two files' baselines, not deferred debt. Both have since been squashed back below them (`rules/ARENA.md` to 9,716 `B`, `rules/AGENTS.md` to 1,816 `tok`, funded inside the same changes that amended them), so item 5 applies to them again at the measurements in the table above.
