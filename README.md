# Clankers

Rules, skills, and workflows for AI agents. 

- [rules/](rules/): shared and platform-specific instructions, both ChatGPT fields, and commit rules. See [specification and setup](rules/README.md). 
- [skills/](skills/README.md): UI reviews, text compression, and a shared Arena steering/reporting preview. Each skill has `SKILL.md` and supporting files. 
- [workflows/](workflows/README.md): portable workflows, currently [init-docs](workflows/init-docs.md) for downstream user and agent docs. The README defines the required format. 
- [automations/](automations/DAILIES.md): recurring prompts, currently combined daily monitoring through ChatGPT scheduled tasks. Each self-contained Markdown prompt runs in one pass and supplies state/evidence rules because runtime state is unreliable. 
- [userscripts/](userscripts/README.md): Tampermonkey userscripts for Arena and ChatGPT. Separate scripts fill the `/agent` composer, click the `{repo} - Steering` preview, and hide the composer while Stop generating is present. Two scripts hide promo and nav elements on chatgpt.com and click Think every second. 
- [maintenance/](maintenance/README.md): validation, synchronization, and README measurement tooling, requiring `markdown-it-py` and `tiktoken`. 
- [rules/refs/](rules/refs/README.md): uncompressed originals and AGENTS.md writing guidelines. 
- [skills/refs/](skills/refs/): complete unsquashed source trees for skills with baselines. 

`rules/apply.py` copies the global rule files. `apply.bat` runs it on Windows. 

## Instruction budgets

Latest measurements as of 2026-09-28. `maintenance/check.py` measures ARENA.md by uploaded size, ChatGPT files by character limits, and other rules and `SKILL.md` entries by `cl100k_base` tokens. Both preview entries instead use UTF-8 bytes, independent of tokenizer/cache access. The check excludes supporting files and skill refs except the three `assets/` and three `scripts/` rows. These minified files use their recorded sizes as budgets. `maintenance/minify.py` builds them from readable refs.

| File | Measure | Current |
| --- | --- | --- |
| `rules/AGENTS.md` | `cl100k_base` | 1,589 `tok` |
| `rules/ARENA.md` | `UTF-8 file size` | 14,375 `B` |
| `rules/CHATGPT-CUSTOM.txt` | `Unicode chars` | 1,436 `chars` |
| `rules/CHATGPT-MORE.txt` | `Unicode chars` | 1,401 `chars` |
| `rules/CLINE.md` | `cl100k_base` | 501 `tok` |
| `rules/KILO.md` | `cl100k_base` | 87 `tok` |
| `rules/kilo/code.md` | `cl100k_base` | 223 `tok` |
| `rules/kilo/debug.md` | `cl100k_base` | 272 `tok` |
| `rules/kilo/plan.md` | `cl100k_base` | 246 `tok` |
| `rules/COMMIT-SPEC.txt` | `cl100k_base` | 119 `tok` |
| `skills/arena-preview-steering/SKILL.md` | `UTF-8 file size` | 5,995 `B` |
| `skills/arena-preview-steering/assets/app.js` | `UTF-8 file size` | 40,542 `B` |
| `skills/arena-preview-steering/assets/index.html` | `UTF-8 file size` | 7,996 `B` |
| `skills/arena-preview-steering/assets/style.css` | `UTF-8 file size` | 12,266 `B` |
| `skills/arena-preview-steering/scripts/preview.py` | `UTF-8 file size` | 74,002 `B` |
| `skills/arena-preview-steering/scripts/install.sh` | `UTF-8 file size` | 3,504 `B` |
| `skills/squash/SKILL.md` | `cl100k_base` | 1,289 `tok` |
| `skills/web-interface-guidelines/SKILL.md` | `cl100k_base` | 531 `tok` |
| `workflows/init-docs.md` | `cl100k_base` | 4,552 `tok` |
| `gpt-plugins/skills/gpt-quirks/SKILL.md` | `cl100k_base` | 142 `tok` |
| `gpt-plugins/skills/gpt-handoff/SKILL.md` | `cl100k_base` | 1,090 `tok` |
| `gpt-plugins/skills/gpt-planning/SKILL.md` | `cl100k_base` | 398 `tok` |
| `gpt-plugins/skills/gpt-github/SKILL.md` | `cl100k_base` | 275 `tok` |

Measurements cover complete files, including whitespace and markup. 

## Compression

Use the [`squash` skill](skills/squash/SKILL.md) for compression. See [maintenance/README.md](maintenance/README.md) for repository-specific budget and synchronization procedures.
