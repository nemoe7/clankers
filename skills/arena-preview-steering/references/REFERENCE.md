# Preview transport: operation

## Runtime contract

The shared runtime is `scripts/preview.py`, relative to the steering skill. It uses Python 3.10+ standard-library HTTP, JSON and SQLite support. The report renderer imports `markdown-it-py` only when rendering; `serve` checks it at startup and exits with the install command when missing, since a page that cannot render Markdown is worse than no page. The CLI commands need no renderer. The reporting skill is a separate entry point installed beside steering, not an independent copy of the server.

The chosen `--state-dir` contains `state.sqlite3`. Normal SQLite transactions handle concurrent browser sends and CLI receipts. Reads never acknowledge; a `read` stamps `seen_at` for exactly the IDs it printed, once its output write succeeds. `seen <ids>` or `ack` marks only those IDs. Count-only notifications, truncated output and failed deliveries stay Sent. Writes are committed before the server returns success.

Notes retain IDs, server timestamps, text, optional acknowledgement timestamps and an optional acknowledgement kind, `note` or `reply`, with its answer text. Changed existing answers carry `ack_edited_at`; first answers and identical retries do not, and save/import preserve that stamp. Report answers are recorded in a separate `submissions` table with the same receipt columns plus their report ID: `read` merges both as pending items tagged `kind: note` or `kind: report`, `ack` accepts either ID, and `/api/state` serves notes only, so submissions never render as messages. Reports retain stable IDs, titles, Markdown snapshots, update timestamps and a `seq` fixed at first publish, which is the send order the UI numbers; their fields are parsed from that snapshot at every render, never stored separately. Missing columns migrate in place as nullable and `seq` is backfilled from `rowid`; no message or report is dropped. Keep the state directory Git-ignored and outside transient cache/build directories.

| Command | Purpose |
| --- | --- |
| `init` | Create state without starting HTTP |
| `serve` | Start the shared interface on `0.0.0.0`, port 8000 unless `--port` says otherwise |
| `read` | Print all unacknowledged messages and report answers; record check time; stamp `seen_at` for printed IDs; minified JSON |
| `seen <ids>` | Stamp only IDs whose full text reached the agent; unknown IDs fail the whole batch |
| `task ID TITLE [DETAIL ...]` | Add or update one task in the Tasks tab; `--status`, `--order`, or the `--task-*` flags |
| `task-remove ID` | Delete one task and echo what was stored |
| `task-import [FILE]` | Rebuild the list from JSON, a file or stdin; `--replace` clears first; note lines are skipped |
| `task-list` | Print every task as minified JSON, in the shape `task-import` reads back |
| `ack <id> [<id> ...] --reply <markdown>` | Record receipts with a rendered answer in the log |
| `ack <id> [<id> ...] --note <text>` | Record receipts with one plain answer line |
| `publish <source.md> --id <id> --title <title>` | Add/update a report snapshot |
| `import-notes <notes.ndjson>` | Import ID/text/time records, plus the receipt a line carries and its read stamp, written verbatim; a report answer line is restored in the same run, with its own receipt and read stamp; task lines are skipped; a partial receipt is refused and none is invented |

All commands take `--state-dir` before the subcommand. `--save-path` selects where the save button writes its file, `saved-state.ndjson` at the repository root by default. `--pretty` indents CLI JSON for a human eye. Commands that read existing state fail if the database is missing; they do not create a misleading empty inbox. Import is idempotent by ID and rejects an existing ID with different text.

## Read and acknowledge

Use only CLI `read` to poll; a failed delivery stays unseen, and a stamped message prints again until it is answered. Never mark count-only, truncated or failed deliveries Seen. Browser polls never stamp Seen. Pending records distinguish `kind: note` and `kind: report`; both accept `ack`. Report answers stay separate from the message log. Read errors must remain visible.

Acknowledge exactly the delivered IDs, never all pending blindly. Supply exactly one of `--reply` or `--note`; one answer per call, separate calls for different answers. Unknown IDs fail the receipt batch. Repeated acknowledgement keeps its first timestamp and replaces the answer. Receipt is not completion. Use full IDs in CLI arguments; cite their first seven characters in prose, never sequence numbers. Without a visible preview, acknowledge in chat with literal `ACK:` and the interpretation.

## Tasks

Task IDs are 1–64 lowercase letters, digits or hyphens, starting with a letter or digit. Titles allow at most 200 characters; each task at most 40 details of 2000 characters. Existing IDs update; omitted title/details keep stored values. The echo clips details to 200 characters, not stored values. Its `prev` and `next` identify neighbors within the same status group, null at either end.

| Flag | Operation |
| --- | --- |
| `--task-id`, `--task-title`, repeatable `--task-details` | Alternatives to the positional ID, title and detail arguments |
| `--task-details ""` | Clear all details |
| `--status upcoming` or `--status finished` | Set status; new tasks default to upcoming |
| `--order N` | Place at the 1-based position within its status group, not the end; positions stay dense after changes |
| `--msg-id <full-message-id>` | Link a note or report submission to this task |
| `--amend <previous-task-id>` | Rename an existing task to the supplied task ID, retaining title, details, status and position; refuse an existing destination |

Use `--msg-id` on the `task` command to set the message's `task_id`. Task/link writes are atomic; unknown message IDs fail both. Report-submission links add no log messages. The marker means queued, not acknowledged/complete; still `ack`.

`task-import` merges by ID; `--replace` clears first. It validates every record before writing in one transaction, so invalid input cannot erase the existing queue. Mixed save files skip note and report-answer records. Tasks need no Markdown renderer.

## Publish reports

Use the companion [reporting skill](../../arena-preview-reporting/SKILL.md) for field syntax and publishing procedure. Sources must be UTF-8 `.md`, at most 2,000,000 bytes. IDs are 1–80 letters, digits, hyphens or underscores; titles 1–200 characters. Invalid fields fail before storage. Keep one ignored source per report and republish its stable ID to update it. Source edits alone never update published snapshots.

Republishing preserves first-publish order, clears the report's read stamp and never deletes delivered answers. `read` delivers submissions headed `REPORT <id> <title>:`, one indented line per field, `(skipped)` for empty answers; resending creates a new answer. Publishing never acknowledges a submission. Verify the rendered report before claiming delivery. Render failures leave sources available for inspection; report failure, never success.

The rendered report endpoint returns its full `revision`; answer requests must echo it. Revision checks and answer writes share one transaction. Missing revisions return HTTP 400, stale ones HTTP 409 without saving. Reload old preview pages before sending. Automatic updates retain unsent/in-flight answers. After rejection, copy entries before explicitly refreshing and reviewing the new report.

## Fields in a report

| Marker | Control | Notes |
| --- | --- | --- |
| `- ( ) option` list | Radio group | `- (x)` preselects that option |
| `- [ ] option` list | Checkbox group | `- [x]` preselects that option |
| `- ( ) Label: ___` inside a group | Free-text slot | The typed text becomes the answer, as `Label: text` |
| `Label: ___` or a bare `___` line | Text box | At most 2000 characters |

Limits: 1–50 fields per report; prompts 1–500 characters; 1–20 unique options of 1–200 characters per group, where a group may hold a single option; each text answer 2000 characters; a whole submission 150,000 characters, checked before storage and refused with the limit named, never truncated. A duplicate option in one group is an error, and the whole report then fails to render rather than silently dropping a choice. Two free-text slots in one group may not share a label.

The prompt is the label before `___`, else the nearest non-empty line above the group, stripped of list, heading, quote and emphasis markers and a trailing colon. The field ID is a slug of that prompt, deduplicated with a numeric suffix; `{#my-id}` at the end of the prompt line sets it explicitly. Markers inside fenced code blocks are literal text.

`GET /api/reports/<id>/html` returns JSON with `html` and the field count, not raw HTML. `POST /api/reports/<id>/submit` pairs a client-generated ID with per-field answers (`choice` one of its options or a slot's `Label: text`, `checkbox` a unique subset of its options and slots) and writes one inbox note headed `REPORT <id> <title>:`. Resending is a new answer, not an update. A report with no fields rejects a submission. Republishing a source does not change or delete answers already delivered.

## Uploads

Uploads write inbox notes with matching IDs, naming file, size, type and path. One file is 1,000,000 bytes at most; a longer body is answered `413` before it is read. The bytes go to `<state-dir>/uploads/`, named after the upload's own UUID with the owner's extension kept, and never enter the database. A record outlives its bytes: a restore removes the files but keeps the records, and `present` on `/api/state` says which is which. Read the file at its path, then acknowledge the note. The save file does not restore missing upload bytes.

## HTTP and trust boundary

Only `/`, `/api/state`, `/api/notes`, `/api/markdown` and published report routes are exposed. `/api/state` never carries report submissions. `/api/markdown` accepts a bounded, token-protected draft and returns read-only HTML without writing any inbox record. Published reports support `/api/reports/<id>/html`, `/source` and token-protected `/api/reports/<id>/submit` and `/api/reports/<id>/seen`. `POST /api/save-state` writes the page's cached log and tasks, plus report answers appended from the database, as `saved-state.ndjson` at the repository root, outside the state directory. It also writes an inbox note, so the next `read` delivers the save. No endpoint accepts arbitrary filesystem paths; only the agent's CLI can register a report. The browser cannot acknowledge messages. POST requires JSON, a bounded body and a per-process token; the bound is per route: notes and rendered Markdown take 32,768 bytes, a report submission 1,000,000, an upload 1,000,000.

Treat the preview URL as private session access. Do not publish secrets. Do not enable CORS, arbitrary file serving or remote assets. Raw HTML in Markdown is disabled. Report titles and messages are text, not HTML. The server accepts the Arena proxy host and does not block iframe embedding.

## Recovery and checks

- Preserve the ignored state directory and Markdown sources when restarting. Process IDs, venv packages and URLs are not durable; restore the approved renderer and restart the same state directory as needed.
- Reload an old browser page after server restart to obtain the new submission token. Keep/copy an unsent draft first if browser storage is unavailable. Browser drafts are origin-local, not a cross-device backup.
- If a port is occupied, identify its owner or select another port; never kill an unrelated service. A failed read or save must remain visible, not become an empty state.
- Run `python <skill>/scripts/check_preview.py` with `markdown-it-py` available. It checks missing state, persistence, retry deduplication, receipt transactions, multiple reports, Markdown fields and their submissions, unsafe Markdown, absent-renderer behavior and HTTP route boundaries. Check `assets/app.js` with `node --check` and run `node scripts/check_client.cjs` where Node is available. These checks do not prove actual browser rendering; record manual browser observations separately.
- Import `saved-state.ndjson` soon after the owner presses save state. The file carries the notes, the tasks and the owner's report answers; a report itself rebuilds from the source that produced it.
- Rebuild the queue from Git when the task backup dies with the state directory: `git log --oneline` is one finished task per shipped change, with the commit as its detail line, and `task-import` reads the JSON that those records form. Recover upcoming work from known requests, not invented completion claims.
- Import a pasted log with `import-notes`, and never assume an answer: a line keeps the receipt it carries and a line without one stays unacknowledged.
- Writes use a per-process token. The `/api/state` poll keeps the page's token fresh; `request()` also takes the token from a fresh page and retries once on a 401 or 403, and waits a second and retries once when a write never reached a server. If saving still fails, preserve drafts and report the failure; do not treat an unconfirmed save as durable.
- Keep backups until restoration is verified with `read`, `task-list` and the rendered reports. Do not commit or push state, inboxes, receipts or reports.
- If preview remains unavailable, report the observed failure and ask in chat how to continue. Do not silently revive ntfy or local report commits; another delivery method needs fresh approval.
