# Clankers

Rules, skills, and workflows for AI agents. 

- [rules/](rules/): shared and platform-specific instructions, both ChatGPT fields, and commit rules. See [specification and setup](rules/README.md). 
- [skills/](skills/README.md): UI reviews, text compression, and a shared Arena steering/reporting preview. Each skill has `SKILL.md` and supporting files. 
- [workflows/](workflows/README.md): portable workflows, currently [init-docs](workflows/init-docs.md) for downstream user and agent docs. The README defines the required format. 
- [automations/](automations/DAILIES.md): recurring prompts, currently combined daily monitoring through ChatGPT scheduled tasks. Each self-contained Markdown prompt runs in one pass and supplies state/evidence rules because runtime state is unreliable. 
- [maintenance/](maintenance/README.md): validation and README measurement tooling, requiring `markdown-it-py` and `tiktoken`. 
- [rules/refs/](rules/refs/README.md): uncompressed originals and AGENTS.md writing guidelines. Amend refs first, then compress only new or affected lines into live files. 
- [skills/refs/](skills/refs/): complete unsquashed source trees for skills with baselines. Amend here first, then squash the live `SKILL.md`. 

`rules/apply.py` copies the global rule files. `apply.bat` runs it on Windows. 

## Instruction budgets

Latest measurements as of 2026-09-23. `maintenance/check.py` measures ARENA.md by uploaded size, ChatGPT files by character limits, and other rules and `SKILL.md` entries by `cl100k_base` tokens. Both preview entries instead use UTF-8 bytes, independent of tokenizer/cache access. The check excludes supporting files and skill refs except the three `assets/` and three `scripts/` rows. These minified files use their recorded sizes as budgets. `maintenance/minify.py` builds them from readable refs. 

| File | Measure | Current |
| --- | --- | --- |
| `rules/AGENTS.md` | `cl100k_base` | 1,540 `tok` |
| `rules/ARENA.md` | `UTF-8 file size` | 14,100 `B` |
| `rules/CHATGPT-CUSTOM.txt` | `Unicode chars` | 1,495 `chars` |
| `rules/CHATGPT-MORE.txt` | `Unicode chars` | 1,495 `chars` |
| `rules/CLINE.md` | `cl100k_base` | 501 `tok` |
| `rules/KILO.md` | `cl100k_base` | 69 `tok` |
| `rules/kilo/code.md` | `cl100k_base` | 223 `tok` |
| `rules/kilo/debug.md` | `cl100k_base` | 272 `tok` |
| `rules/kilo/plan.md` | `cl100k_base` | 246 `tok` |
| `rules/COMMIT-SPEC.txt` | `cl100k_base` | 119 `tok` |
| `skills/arena-preview-steering/SKILL.md` | `UTF-8 file size` | 10,851 `B` |
| `skills/arena-preview-reporting/SKILL.md` | `UTF-8 file size` | 5,985 `B` |
| `skills/arena-preview-steering/assets/app.js` | `UTF-8 file size` | 27,060 `B` |
| `skills/arena-preview-steering/assets/index.html` | `UTF-8 file size` | 6,678 `B` |
| `skills/arena-preview-steering/assets/style.css` | `UTF-8 file size` | 9,968 `B` |
| `skills/arena-preview-steering/scripts/preview.py` | `UTF-8 file size` | 56,416 `B` |
| `skills/arena-preview-steering/scripts/install.sh` | `UTF-8 file size` | 1,843 `B` |
| `skills/squash/SKILL.md` | `cl100k_base` | 1,289 `tok` |
| `skills/web-interface-guidelines/SKILL.md` | `cl100k_base` | 531 `tok` |
| `workflows/init-docs.md` | `cl100k_base` | 4,821 `tok` |

Measurements cover complete files, including whitespace and markup. 

## Compression

Use the [`squash` skill](skills/squash/SKILL.md), extracted from the rules below, against these budgets. Amend `rules/refs/` first, then compress only new or affected lines into live files. On removal, attempt one squash and keep the lower budget. Refs remain uncompressed. Remove words, never rules. 

1. Work in iterations. After each pass, re-measure and compare against the previous value. Keep the pass only when the budget improves, and repeat until a pass yields nothing. 
2. Preserve every negation, condition, command, number, threshold, filename, and caveat. Removing a constraint is a rule change, not compression. 
3. Merge related bullets, drop redundant qualifiers and restated clauses, and prefer the shorter of two equivalent phrasings. Do not invent new abbreviations or telegraphic syntax that changes how a rule reads. 
4. Keep the section headings and order the refs baseline already has. Restructuring is an amendment, so make it in refs first. 
5. New clause: squash only that new line. Amended clause: squash only the affected line. Removed clause: attempt one squash and keep whichever budget is lower. 
6. Update the budgets table above, record notable reductions in [CHANGELOG.md](CHANGELOG.md), and record a growth accepted rather than funded in [docs/archive/budget-exceptions.md](docs/archive/budget-exceptions.md). 

[docs/archive/budget-exceptions.md](docs/archive/budget-exceptions.md) records growth the owner accepted rather than funded, with dates, numbers and reasons. This page holds only the procedure and current measurements. 
