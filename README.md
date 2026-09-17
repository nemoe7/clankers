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

Latest measurements as of 2026-09-17. ARENA.md is measured by uploaded file size and the two ChatGPT files by their custom-instruction character limits; the remaining agent-facing rule files and `SKILL.md` entry files use `cl100k_base` tokens, except `skills/arena-live-steering/SKILL.md`, which is measured by UTF-8 file size, since a byte count needs no tokenizer and so survives a sandbox where the `tiktoken` cache cannot be seeded. Supporting files loaded on demand, including a skill's `BASELINE.md`, are not included.

| File | Measure | Current |
| --- | --- | --- |
| `rules/AGENTS.md` | `cl100k_base` | 1,549 `tok` |
| `rules/ARENA.md` | `UTF-8 file size` | 10,307 `B` |
| `rules/CHATGPT-CUSTOM.txt` | `Unicode chars` | 1,490 `chars` |
| `rules/CHATGPT-MORE.txt` | `Unicode chars` | 1,473 `chars` |
| `rules/CLINE.md` | `cl100k_base` | 572 `tok` |
| `rules/KILO.md` | `cl100k_base` | 185 `tok` |
| `rules/kilo/code.md` | `cl100k_base` | 232 `tok` |
| `rules/kilo/debug.md` | `cl100k_base` | 288 `tok` |
| `rules/kilo/plan.md` | `cl100k_base` | 212 `tok` |
| `rules/COMMIT-SPEC.txt` | `cl100k_base` | 129 `tok` |
| `skills/arena-live-steering/SKILL.md` | `UTF-8 file size` | 8,022 `B` |
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

A third exception is recorded from 2026-09-17, after the resquash ran: `rules/AGENTS.md` lands below its prior measurement, 1,785 → 1,549 `tok`, and `skills/arena-live-steering/SKILL.md` far below its own, 13,419 → 8,132 `B`, but `rules/ARENA.md` settles at 10,307 `B` against a prior 10,129 `B`. The live ARENA file was squashed in the same change, from the 11,580 `B` its amendments first produced, recovering 1,273 `B` of wording; the residual 178 `B` is new rules this change adds on request — the SOLID pair, the tool-call batching rule, and fix-once-where-callers-route-through — and no wording remains to fund them without dropping one. Item 5 applies again once a pass can pay for them.

A fourth exception is recorded from 2026-09-17 and paid back in the same change: the steering-channel note added on request to `skills/arena-live-steering/SKILL.md` — the channel must be sent in chat before the first fetch, which fails until the user has posted in it — first lands the file at 8,473 `B` against its 8,132 `B` squashed baseline, +341 `B`, and the squash pass that moves the unsquashed wording into the skill's new `BASELINE.md` pays it back in full: 8,022 `B`, 110 `B` under its prior measurement, so no exception remains.
