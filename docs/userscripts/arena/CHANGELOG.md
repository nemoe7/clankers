<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [1.13.15]

### Added

- Detect turns ending without a Steering poll and configure separate wake and violation messages.

### Fixed

- Send generated multiline violation messages only for a final prose row without a completed poll.
- Send exact Wake up drafts through the shared composer-action lookup without requiring the obsolete editor wrapper. Never click Stop generating.
- Leave the composer unfocused after a wake-up fill when the page held no focus, instead of keeping focus there.

### Changed

- Load startup survey question text from `skills/arena-steering/references/survey-questions.txt` in Arena prompt fill and align startup survey instructions with `steer survey`.
- Remove the retired key-command hint without changing proxy routes or storage keys, and correct the detached-test command.

## [1.13.13]

### Changed

- Clarify requirement wording in the setup guide.

- `userscripts/arena.user.js`: Shorten the reset-window comments for prose validation without changing behavior.
