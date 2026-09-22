# Vendored skills

These third-party tools audit and lint the repository. They are not owner skills: `skills/` has no mirrors, `skills/refs/` has no baselines, and `maintenance/check.py` skips this directory. Copies keep upstream files verbatim for release comparisons. Local fixes belong upstream.

Copies keep upstream layouts for release comparisons: ponytail’s six skills sit under its own `skills/` directory. Style gates deliberately skip them. `ruff.toml` excludes `.agents/skills`. Markdownlint covers `rules/**/*.md`, ignores `skills/**`, and excludes vendored Markdown from the count `check.py` guards.

| Skill | Upstream | Commit | Vendored | Licence | Why it is here |
| --- | --- | --- | --- | --- | --- |
| `asd-ste100` | `danyuchn/asd-ste100-skill` | `7d4a135`, 2026-09-08 | 2026-09-21 | MIT | Simplified Technical English: rewrite rules and a report-only linter for human-facing text |
| `ponytail` | `DietrichGebert/ponytail` | `e3ba2aa`, 2026-09-14 | 2026-09-21 | MIT | Over-engineering audit: ranked `delete:`/`stdlib:`/`native:`/`yagni:`/`shrink:` findings and a verdict. The tool is `.agents/skills/ponytail/skills/ponytail-audit/SKILL.md` |
