# Vendored skills

The skills here are third-party tools the repository uses to audit and lint itself. They are not
owner skills: nothing in `skills/` mirrors them, `skills/refs/` holds no baseline for them, and
`maintenance/check.py` does not read this directory. A copy keeps the upstream files verbatim, so a
diff against a later release is meaningful and a local fix belongs upstream instead.

A copy keeps the upstream layout, so a later release diffs against it: ponytail's six skills sit
under its own `skills/` directory. Style gates skip them, deliberately: `ruff.toml` excludes `.agents/skills`, and markdownlint's
scope is `rules/**/*.md` with `skills/**` ignored, so vendored Markdown is outside the linted count
that `check.py` guards.

| Skill | Upstream | Commit | Vendored | Licence | Why it is here |
| --- | --- | --- | --- | --- | --- |
| `asd-ste100` | `danyuchn/asd-ste100-skill` | `7d4a135`, 2026-09-08 | 2026-09-21 | MIT | Simplified Technical English: rewrite rules and a report-only linter for human-facing text |
| `ponytail` | `DietrichGebert/ponytail` | `e3ba2aa`, 2026-09-14 | 2026-09-21 | MIT | Over-engineering audit: ranked `delete:`/`stdlib:`/`native:`/`yagni:`/`shrink:` findings and a verdict. The tool is `.agents/skills/ponytail/skills/ponytail-audit/SKILL.md` |
