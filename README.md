# Clankers

Rules, skills, and workflows for AI agents. 

- [rules/](rules/): shared and platform-specific instructions, both ChatGPT fields, and commit rules. See [specification and setup](rules/README.md). 
- [skills/](skills/README.md): UI reviews, text compression, and a shared Arena steering/reporting preview. Each skill has `SKILL.md` and supporting files. 
- [workflows/](workflows/README.md): portable workflows, currently [init-docs](workflows/init-docs.md) for downstream user and agent docs. The README defines the required format. 
- [github/workflows/](github/workflows/README.md): reusable AI GitHub Actions sources, without instruction budgets. The Gemini workflow proposes a version and notes from commit history. A separate approved run creates a tag and draft.
- [automations/](automations/DAILIES.md): recurring prompts, currently combined daily monitoring through ChatGPT scheduled tasks. Each self-contained Markdown prompt runs in one pass and supplies state/evidence rules because runtime state is unreliable. 
- [userscripts/](userscripts/README.md): Tampermonkey userscripts for Arena and ChatGPT. Two domain bundles provide saved feature switches. Arena fills the `/agent` composer, opens the `{repo} - Steering` preview, and hides the composer while generating. ChatGPT hides promo and nav elements and clicks Think every second.
- [maintenance/](maintenance/README.md): validation, synchronization, and README measurement tooling, requiring `markdown-it-py` and `tiktoken`. 
- [rules/refs/](rules/refs/README.md): uncompressed originals and AGENTS.md writing guidelines. 
- [skills/refs/](skills/refs/): complete unsquashed source trees for skills with baselines. 

`rules/apply.py` copies the global rule files. `apply.bat` runs it on Windows. 

## Instruction budgets

Latest measurements as of 2026-10-04. `maintenance/check.py` measures ARENA.md by uploaded size, ChatGPT files by character limits, and other rules, `SKILL.md` entries, and the live system prompt by `cl100k_base` tokens. Both preview entries instead use UTF-8 bytes, independent of tokenizer/cache access. The check excludes supporting files and skill refs except the three `assets/` and three `scripts/` rows. These minified files use their recorded sizes as budgets. `maintenance/minify.py` builds them from readable refs.

| File | Measure | Current |
| --- | --- | --- |
| `rules/AGENTS.md` | `cl100k_base` | 1,535 `tok` |
| `rules/ARENA.md` | `UTF-8 file size` | 16,465 `B` |
| `rules/CHATGPT-CUSTOM.txt` | `Unicode chars` | 1,497 `chars` |
| `rules/CHATGPT-MORE.txt` | `Unicode chars` | 1,475 `chars` |
| `rules/CLINE.md` | `cl100k_base` | 460 `tok` |
| `rules/KILO.md` | `cl100k_base` | 87 `tok` |
| `rules/kilo/code.md` | `cl100k_base` | 223 `tok` |
| `rules/kilo/debug.md` | `cl100k_base` | 272 `tok` |
| `rules/kilo/plan.md` | `cl100k_base` | 246 `tok` |
| `rules/COMMIT-SPEC.txt` | `cl100k_base` | 91 `tok` |
| `system-prompts/NEMOGPT.md` | `cl100k_base` | 2,473 `tok` |
| `skills/amending-violations/SKILL.md` | `cl100k_base` | 1,739 `tok` |
| `skills/arena-proxy/SKILL.md` | `cl100k_base` | 2,442 `tok` |
| `skills/arena-preview-steering/SKILL.md` | `UTF-8 file size` | 6,076 `B` |
| `skills/arena-preview-steering/assets/app.js` | `UTF-8 file size` | 45,318 `B` |
| `skills/arena-preview-steering/assets/index.html` | `UTF-8 file size` | 8,194 `B` |
| `skills/arena-preview-steering/assets/style.css` | `UTF-8 file size` | 12,836 `B` |
| `skills/arena-preview-steering/scripts/preview.py` | `UTF-8 file size` | 93,170 `B` |
| `skills/arena-preview-steering/scripts/install.sh` | `UTF-8 file size` | 9,463 `B` |
| `skills/squash/SKILL.md` | `cl100k_base` | 1,250 `tok` |
| `skills/web-interface-guidelines/SKILL.md` | `cl100k_base` | 531 `tok` |
| `workflows/init-docs.md` | `cl100k_base` | 4,552 `tok` |
| `gpt-plugins/skills/gpt-quirks/SKILL.md` | `cl100k_base` | 135 `tok` |
| `gpt-plugins/skills/gpt-handoff/SKILL.md` | `cl100k_base` | 1,255 `tok` |
| `gpt-plugins/skills/gpt-planning/SKILL.md` | `cl100k_base` | 371 `tok` |
| `gpt-plugins/skills/gpt-github/SKILL.md` | `cl100k_base` | 432 `tok` |

Measurements cover complete files, including whitespace and markup. 

## Compression

Use the [`squash` skill](skills/squash/SKILL.md) for compression. See [maintenance/README.md](maintenance/README.md) for repository-specific budget and synchronization procedures.
