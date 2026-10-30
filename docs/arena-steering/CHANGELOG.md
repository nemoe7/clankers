<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [2.0.0]

### Added

- `cli.py`, `services.py`: Block linked tasks while named runs are active.

- `models.py`: Preserve distinct report-answer snapshots on linked tasks.

- `app.js`: Preload report content on pointer or keyboard intent.

- `references.js`: Navigate known message, report, and task references.

- `store.py`: Deduplicate message retries by client request ID.

- `composer-uploads.js`: Show upload progress and recover from failed uploads.

- `store.py`: Persist reply-seen flags with atomic revision checks.

- `assets/messages-view.js`: Preserve unsent composer text in browser session storage.

- `services.py`: Require at least one detail for new and updated tasks.

- `assets/messages-view.js`: Leave Enter to the textarea on coarse-pointer devices.

- `assets/style.css`: Use the existing positive token for success icons.

- `assets/messages-view.js`: Ignore Enter during active text composition.

- `scripts/arena_steering/store.py`: Retry transient SQLite lock errors during concurrent WAL initialization.

- `skills/arena-steering/README.md`: Document the message retry duplication risk found during the parity audit.

- `assets/messages-view.js` and `scripts/arena_steering/server.py`: Match v1 paste thresholds and support Ctrl+Shift+V plain-text bypass.

- `scripts/arena_steering/cli.py`: Fix state under `arena-state` and use a separate v2 database filename while v1 remains active. Keep demo state in `arena-state/demo/`.

- `skills/arena-steering/README.md`: Document v2 features, commands, routes, and current limits. Expand interface and lifecycle contracts, and align the v1/v2 parity matrix with the feature inventory.
- `scripts/arena_steering/` and `scripts/steer`: Add the `arena-steering` skill and `steer` CLI with domain models, SQLite storage, server-cached Markdown forms, SHA-256 survey grading, and HTTP/WebSocket routes.
- `assets/`, `references/survey.json`, and `scripts/demo.py`: Add ES module web UI for Inbox, Tasks, Reports, and Survey with PrismJS, Mermaid, Arena tokens, `Basel_Grotesk` fonts, and `demo.py`.
- `scripts/arena_steering/server.py` and `assets/`: Push `report.acked` over `/api/ws` to update an open report in place, and mark `ack_seen` when the owner views it.
- `assets/reports-view.js` and `assets/style.css`: Pair fielded reports' bottom submit spacer with a fixed `#report-submit-float` that stays reachable while scrolling.
- `scripts/arena_steering/` and `assets/`: Store `parent_ids[]` on messages, toggle composer reply parents from receipt IDs, copy IDs on Shift+Click, and render clickable `↪ <id>` parent chips.
- `scripts/arena_steering/server.py` and `assets/`: Serve nested UI assets, report files and raw Markdown, and uploads under `/static/assets/`, `/static/reports/`, and `/static/uploads/`.
- `scripts/arena_steering/server.py`: Add JSON and multipart `POST /api/uploads` and `POST /api/messages/with-file`. Store uploads under `/static/uploads/` and convert long pasted text into a `.txt` attachment.
- `scripts/arena_steering/`, `assets/api.js`, and `assets/app.js`: Add `steer rename`, `steer task unlink`, `steer pr-update`, and `steer job-log`, plus browser `POST /api/timezone` instead of `init --tz`.
- `assets/`: Stage full-page file drops, `#attach-file` picks, and long pastes as removable chips in `#composer-attachments`, with `#composer-expand` for a taller composer.
- `scripts/arena_steering/cli.py`: Add native `git worktree` lifecycle commands under `.worktrees/`, detached `steer run start` with `--after` chaining and `steer run logs`, plus a `steer run pr-checks` watcher.
- `assets/messages-view.js`: Fix message rendering when a task links to a message.
- `assets/`: Open message and report images and Mermaid diagrams in a zoomable, pannable lightbox.

### Fixed

- `README.md`: Mark local image embedding as intentionally dropped.

- `README.md`: Record intentionally dropped v1 features.

- `README.md`: Correct the comparison of report-answer acknowledgement.

- `server.py`: Return report-answer acknowledgements from the message route.

- `cli.py`: Create acknowledgement tasks and replies in one transaction.

- `assets/markdown.js` and `scripts/demo.py`: Use warm Arena colors for the Mermaid theme and the demo PNG, GIF, and SVG files.
