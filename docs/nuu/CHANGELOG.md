<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [0.1.69]

### Added

- **Equal-size button groups (`NUM208`, `SKILL.md` Clause 6, `measure.py`, `examples.md`)**: Require buttons in the same group to share identical width and height (`examples/button-group-equal-size.png`).

### Changed

- **CLI consolidation (`nuu.py`, `references/nuu.md`)**: Consolidate `nuu` into 7 subcommands (`lint`, `audit`, `walk`, `board`, `annotate`, `search`, `doctor`) and fold static checks into `lint`.
- **Audit report workflow (`SKILL.md` step 5, `audit-report.md`)**: Use `## Findings` and `## Visual Judgements` headings and pair open findings with cropped 2-column `nuu board` panels.
- **Recipes**: Schedule relative timestamps at unit boundaries (`relative-timestamps.md`).
- **Recipes**: Add `--scrollbar-carve`, `28px`/`36px` fade ramp, and Clause 6/21 proportional sibling clearance (`scroll-edge-fade.md`).
- **Recipes**: Extend `#history` past `.card.compose` to `100%` (`floating-overlay-scroll-fade.md`).
- **Recipes**: Add `data-loading="done"` completion fade-out on `var(--accent)` (`loading-bar.md`).
