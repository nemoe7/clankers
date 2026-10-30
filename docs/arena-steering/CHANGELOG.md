<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [2.1.0] - 2026-10-30

### Added

- `cli.py`, `services.py`: Unlink one stored answer snapshot from every task that holds it, keeping the answer and its receipts.

- `assets/app.js`: Filter loaded messages in the browser after the first search query.

### Changed

- `assets/reports-view.js`: Prefill a published report with its stored answer and mark a recommended option with `*`.
- `assets/reports-view.js`: Keep an unsent answer per field in `localStorage` and clear it after submit.
- `assets/app.js`: Drop the three-second task refresh, because finished runs now push a change event.

- `scripts/arena_steering/services.py`: Keep survey answers, results, and the check stamp in memory instead of SQLite.

- `scripts/arena_steering/cli.py`: Post survey answers to the running server recorded in `server.json`.

- `assets/app.js`: Pan the image viewer without a native image drag and close it from the backdrop.

- `assets/app.js`: Keep diagram colors and scale in the image viewer.

- `assets/style.css`: Clear the image viewer close-button background and lighten its scrim.

- `assets/messages-view.js`: Use the current Lucide paperclip path for the attach button.

- `assets/style.css`: Fade the report and task columns only, leaving sidebars unblurred, and give the task toolbar its own edge fade.

- `assets/messages-view.js`, `assets/style.css`: Match the v1 composer layout, icon buttons, and text size.

### Added

- `scripts/arena_steering/server.py`: Serve state snapshot, change, merge, and asset routes for an external container.
- `scripts/arena_steering/store.py`: Export, stamp, and merge stored rows.
- `scripts/arena_steering/cli.py`: Print a one-line restore notice when a merge changed state.
- `scripts/arena_steering/cli.py`: Register `steer gate` and `steer skills`.
- `scripts/hooks/gate.sh`: Ship the pre-command hook wrapper for the inbox gate.
- `scripts/arena_steering/cli.py`: Add `worktree collect` to print a worktree patch against its merge base.
- `assets/app.js`: Pinch the image viewer with two pointers.
- `scripts/arena_steering/server.py`: Stamp finished runs into `data_version` so clients refresh on completion.
- `scripts/arena_steering/cli.py`: Record the listening port in `server.json` while `steer serve` runs.
- `assets/markdown.js`: Nest list items and render horizontal rules.
- `assets/style.css`: Indent task items by 2ch and style horizontal rules.

### Fixed

- `assets/style.css`: Inset the scrollbar thumb by 2px inside a 10px track and color links blue.

- `assets/style.css`: Dim the page behind the image viewer with a translucent backdrop.

- `assets/messages-view.js`: Fetch the older message page before the top is reached.

## [2.0.0]

### Added

- `store.py`, `assets/`: Search message history in SQLite and page browser results.

- `api.js`, `server.py`, `store.py`: Deduplicate browser writes and uploads across retries.

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

### Changed

- Reports use embedded question and option labels, trusted HTML, strike-marker checks, and post-save verification.

- `assets/`: Bundle Mermaid and its license without a v1 asset dependency.

- `steer msg list` defaults to 5 items and accepts page sizes from 5 to 50.

- `steer msg ID` inspects a message without a `show` subcommand.

### Fixed

- `README.md`: Mark local image embedding as intentionally dropped.

- `README.md`: Record intentionally dropped v1 features.

- `README.md`: Correct the comparison of report-answer acknowledgement.

- `server.py`: Return report-answer acknowledgements from the message route.

- `cli.py`: Create acknowledgement tasks and replies in one transaction.

- `assets/markdown.js` and `scripts/demo.py`: Use warm Arena colors for the Mermaid theme and the demo PNG, GIF, and SVG files.
