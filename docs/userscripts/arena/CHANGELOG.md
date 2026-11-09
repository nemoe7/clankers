<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [1.13.14]

### Fixed

- Send exact Wake up drafts through the shared composer-action lookup without requiring the obsolete editor wrapper. Never click Stop generating.

### Changed

- Load startup survey question text from `skills/arena-steering/references/survey-questions.txt` in Arena prompt fill and align startup survey instructions with `steer survey`.
- Remove the retired key-command hint without changing proxy routes or storage keys, and correct the detached-test command.

## [1.13.13]

### Changed

- Clarify requirement wording in the setup guide.

- `userscripts/arena.user.js`: Shorten the reset-window comments for prose validation without changing behavior.
