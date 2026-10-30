<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [2.0.0]

### Added

- `scripts/arena_steering/` and `scripts/steer`: Add the `arena-steering` skill and `steer` CLI with domain models, SQLite storage, server-cached Markdown forms, SHA-256 survey grading, and HTTP/WebSocket routes.
- `assets/`, `references/survey.json`, and `scripts/demo.py`: Add ES module web UI for Inbox, Tasks, Reports, and Survey with PrismJS, Mermaid, Arena tokens, `Basel_Grotesk` fonts, and `demo.py`.
- `scripts/arena_steering/server.py` and `assets/`: Push `report.acked` over `/api/ws` to update an open report in place, and mark `ack_seen` when the owner views it.
- `assets/reports-view.js` and `assets/style.css`: Pair fielded reports' bottom submit spacer with a fixed `#report-submit-float` that stays reachable while scrolling.
- `scripts/arena_steering/` and `assets/`: Store `parent_ids[]` on messages, toggle composer reply parents from receipt IDs, copy IDs on Shift+Click, and render clickable `↪ <id>` parent chips.

### Fixed

- `assets/markdown.js` and `scripts/demo.py`: Use warm Arena colors for the Mermaid theme and the demo PNG, GIF, and SVG files.
