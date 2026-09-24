# GPT Plugins

One Agent Plugins 1.0.0 collection for GPT-specific skills. The manifest `plugin.json` owns the plugin metadata and version.

| Path | Purpose |
| --- | --- |
| `plugin.json` | Manifest. The checker checks it against the canonical schema at agent-plugins.org. |
| `skills/<name>/SKILL.md` | Shipped skill copies. The archive carries these. |
| `refs/skills/<name>/SKILL.md` | Readable sources. The shipped copies mirror them byte for byte. |
| `README.md` | This file. It never ships. |

## Skills

| Skill | Purpose |
| --- | --- |
| [gpt-quirks](skills/gpt-quirks/SKILL.md) | Apply verified GPT and connected tool quirks when they are relevant |
| [gpt-handoff](skills/gpt-handoff/SKILL.md) | Audit agent work and human-facing docs. Use Ponytail for code and docs audits. Own the final format or draft a handoff. |
| [gpt-planning](skills/gpt-planning/SKILL.md) | Check requirements and completion before each plan, handoff, execution, and final report. |

## Edit a skill

Edit the source under `refs/skills/`, then write the shipped copy:

```bash
python3 maintenance/check_gpt_plugins.py --update
```

The checker reports drift as a failure. An edited source without a regenerated copy breaks CI.

## Package

`.github/workflows/package-gpt-plugins.yml` checks the collection, writes `gpt-plugins.zip`, and publishes that ZIP as a direct Actions artifact. The archive carries `plugin.json` and `skills/` only, so `refs/` and this README stay out of it. The workflow runs on pushes to `main`, on pull requests, and on demand. It fails on a missing or invalid plugin file.
