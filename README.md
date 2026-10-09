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

Latest measurements as of 2026-10-09. `maintenance/check.py` measures ARENA.md by uploaded size, ChatGPT files by character limits, and other rules, `SKILL.md` entries, and the live system prompt by `o200k_base` tokens. The shipped preview assets and scripts instead use UTF-8 bytes, independent of tokenizer/cache access. The table covers the arena suite: ARENA.md and every arena-skill file, one row per file. Skill refs stay out. These minified files use their recorded sizes as budgets. `maintenance/minify.py` builds them from readable refs.

| File | Measure | Current |
| --- | --- | --- |
| `rules/AGENTS.md` | `o200k_base` | 1,550 `tok` |
| `rules/ARENA.md` | `UTF-8 file size` | 19,345 `B` |
| `rules/CHATGPT-CUSTOM.txt` | `Unicode chars` | 1,499 `chars` |
| `rules/CHATGPT-MORE.txt` | `Unicode chars` | 1,475 `chars` |
| `rules/CLINE.md` | `o200k_base` | 462 `tok` |
| `rules/KILO.md` | `o200k_base` | 87 `tok` |
| `rules/kilo/code.md` | `o200k_base` | 222 `tok` |
| `rules/kilo/debug.md` | `o200k_base` | 270 `tok` |
| `rules/kilo/plan.md` | `o200k_base` | 247 `tok` |
| `rules/COMMIT-SPEC.txt` | `o200k_base` | 93 `tok` |
| `system-prompts/NEMOGPT.md` | `o200k_base` | 2,996 `tok` |
| `skills/amending-violations/SKILL.md` | `o200k_base` | 1,598 `tok` |
| `skills/arena-skill/SKILL.md` | `o200k_base` | 3,755 `tok` |
| `skills/arena-skill/README.md` | `o200k_base` | 1,657 `tok` |
| `skills/arena-skill/references/REFERENCE.md` | `o200k_base` | 2,745 `tok` |
| `skills/arena-skill/assets/app.js` | `UTF-8 file size` | 48,211 `B` |
| `skills/arena-skill/assets/index.html` | `UTF-8 file size` | 7,684 `B` |
| `skills/arena-skill/assets/style.css` | `UTF-8 file size` | 13,371 `B` |
| `skills/arena-skill/arena-egress-proxy/Dockerfile` | `UTF-8 file size` | 619 `B` |
| `skills/arena-skill/arena-egress-proxy/INSTALL.md` | `o200k_base` | 855 `tok` |
| `skills/arena-skill/arena-egress-proxy/docker-compose.yml` | `UTF-8 file size` | 2,111 `B` |
| `skills/arena-skill/arena-egress-proxy/scripts/arena_proxy/__init__.py` | `UTF-8 file size` | 396 `B` |
| `skills/arena-skill/arena-egress-proxy/scripts/arena_proxy/__main__.py` | `UTF-8 file size` | 111 `B` |
| `skills/arena-skill/arena-egress-proxy/scripts/arena_proxy/core.py` | `UTF-8 file size` | 16,768 `B` |
| `skills/arena-skill/arena-egress-proxy/scripts/arena_proxy/github_api.py` | `UTF-8 file size` | 3,048 `B` |
| `skills/arena-skill/arena-egress-proxy/scripts/arena_proxy/llm.py` | `UTF-8 file size` | 5,265 `B` |
| `skills/arena-skill/arena-egress-proxy/scripts/arena_proxy/store.py` | `UTF-8 file size` | 1,957 `B` |
| `skills/arena-skill/arena-egress-proxy/scripts/arena_proxy/transfers.py` | `UTF-8 file size` | 4,050 `B` |
| `skills/arena-skill/arena-egress-proxy/scripts/server.py` | `UTF-8 file size` | 385 `B` |
| `skills/arena-skill/arena-egress-proxy/tailscale-serve.json` | `UTF-8 file size` | 265 `B` |
| `skills/arena-skill/arena-preview-proxy/Dockerfile` | `UTF-8 file size` | 476 `B` |
| `skills/arena-skill/arena-preview-proxy/INSTALL.md` | `o200k_base` | 900 `tok` |
| `skills/arena-skill/arena-preview-proxy/assets/icon.svg` | `UTF-8 file size` | 318 `B` |
| `skills/arena-skill/arena-preview-proxy/assets/register.js` | `UTF-8 file size` | 954 `B` |
| `skills/arena-skill/arena-preview-proxy/assets/service-worker.js` | `UTF-8 file size` | 380 `B` |
| `skills/arena-skill/arena-preview-proxy/docker-compose.yml` | `UTF-8 file size` | 1,298 `B` |
| `skills/arena-skill/arena-preview-proxy/server.js` | `UTF-8 file size` | 14,298 `B` |
| `skills/arena-skill/arena-preview-proxy/tailscale-serve.json` | `UTF-8 file size` | 266 `B` |
| `skills/arena-skill/scripts/arena-preview` | `UTF-8 file size` | 574 `B` |
| `skills/arena-skill/scripts/install.sh` | `UTF-8 file size` | 13,714 `B` |
| `skills/arena-skill/scripts/preview.py` | `UTF-8 file size` | 109,631 `B` |
| `skills/squash/SKILL.md` | `o200k_base` | 1,389 `tok` |
| `skills/web-interface-guidelines/SKILL.md` | `o200k_base` | 528 `tok` |
| `workflows/init-docs.md` | `o200k_base` | 4,536 `tok` |
| `gpt-plugins/skills/gpt-quirks/SKILL.md` | `o200k_base` | 134 `tok` |
| `gpt-plugins/skills/gpt-handoff/SKILL.md` | `o200k_base` | 1,301 `tok` |
| `gpt-plugins/skills/gpt-planning/SKILL.md` | `o200k_base` | 367 `tok` |
| `gpt-plugins/skills/gpt-github/SKILL.md` | `o200k_base` | 434 `tok` |

Measurements cover complete files, including whitespace and markup. 

## Compression

Use the [`squash` skill](skills/squash/SKILL.md) for compression. See [maintenance/README.md](maintenance/README.md) for repository-specific budget and synchronization procedures.
