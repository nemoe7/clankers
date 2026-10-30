<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [0.1.69]

### Added

- **Equal-size button groups (`HRC102`, `SKILL.md` Clause 6, `measure.py`, `examples.md`)**: Require buttons in the same group to share identical width and height (`examples/button-group-equal-size.png`).
- **UI/UX guideline checks (`SKILL.md`, `style.css`, `measure.py`, `browser.cjs`)**: Add `--size-32` (`32px`) and check alignment, card hierarchy, proximity, padding, italic body, and button fills.

### Changed

- **2026-10-30, study-backed guidance**: Update the principles, type defaults, examples, and checks.
- **2026-10-30, measurement policy**: Make `TYP101` and `TYP201` review findings by default, with opt-in errors.

- **Semantic rule IDs (`SKILL.md`, `nuu.py`, `measure.py`, `browser.cjs`)**: Reorganize rule codes into `TYP`, `SPC`, `HRC`, `ACC`, `ICN`, `DOC`, and `RUN` with `nonuu:` alias support.
- **CLI consolidation (`nuu.py`, `references/nuu.md`)**: Consolidate `nuu` into 7 subcommands (`lint`, `audit`, `walk`, `board`, `annotate`, `search`, `doctor`) and fold static checks into `lint`.
- **Audit report workflow (`SKILL.md` step 5, `audit-report.md`)**: Use `## Findings` and `## Visual Judgements` headings and pair open findings with cropped 2-column `nuu board` panels.
- **Recipes**: Schedule relative timestamps at unit boundaries (`relative-timestamps.md`).
- **Proportional spacing (`SKILL.md` Clause 21, `scroll-edge-fade.md`)**: Match sibling gaps across axes within a group and use Clause 6/21 clearance beside scroll fades.
- **Recipes**: Add `--scrollbar-carve` and `28px`/`36px` fade ramp (`scroll-edge-fade.md`).
- **Recipes**: Extend `#history` past `.card.compose` to `100%` (`floating-overlay-scroll-fade.md`).
- **Recipes**: Add `data-loading="done"` completion fade-out on `var(--accent)` (`loading-bar.md`).
