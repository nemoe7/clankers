# Preview transport: operation and migration

## Runtime contract

The shared runtime is `scripts/preview.py`, relative to the steering skill. It uses Python 3.10+ standard-library HTTP, JSON and SQLite support. The report renderer imports `markdown-it-py` only when rendering. The reporting skill is a separate entry point, installed beside steering, not an independent copy of the server.

The chosen `--state-dir` contains `state.sqlite3`. Normal SQLite transactions handle concurrent browser sends and CLI receipts; no message is marked acknowledged by a read. Writes are committed before the server returns success. Notes retain IDs, server timestamps, text, optional acknowledgement timestamps and an optional acknowledgement kind, `note` or `reply`, with its answer text. Report answers are recorded in a separate `submissions` table with the same receipt columns plus their report ID: `read` merges both as pending items tagged `kind: note` or `kind: report`, `ack` accepts either ID, and `/api/state` serves notes only, so submissions never render as messages. Reports retain stable IDs, titles, Markdown snapshots, update timestamps and a `seq` fixed at first publish, which is the send order the UI numbers; their fields are parsed from that snapshot at every render, never stored separately. Both additions migrate in place: missing columns are added as nullable, `seq` is backfilled from `rowid`, and no message or report is dropped. Keep this directory Git-ignored and outside transient cache/build directories.

| Command | Purpose |
| --- | --- |
| `init` | Create state without starting HTTP |
| `serve --port 8000` | Start the shared interface on `0.0.0.0` |
| `read` | Print all unacknowledged messages; record check time |
| `ack <id> [<id> ...] --reply <markdown>` | Record receipts with a rendered answer in the log |
| `ack <id> [<id> ...] --note <text>` | Record receipts with one plain answer line |
| `publish <source.md> --id <id> --title <title>` | Add/update a report snapshot |
| `import-notes <notes.ndjson>` | Import the initial experiment's ID/text/time records without deduplicating by text or inventing receipts |

All commands take `--state-dir` before the subcommand. Commands that read existing state fail if the database is missing; they do not create a misleading empty inbox. Import is idempotent by ID and rejects an existing ID with different text. It does not import ntfy messages or claim they were acknowledged.

The UI sends the same client-generated ID on an unchanged retry. It distinguishes saving, confirmed storage and explicit agent acknowledgement; it never interprets an HTTP request or an inbox check as a chat acknowledgement. Errors preserve the draft. Switching views preserves the mounted composer. The user can send with Enter, use Shift+Enter for a newline, browse message history — each entry shows its ID and, once acknowledged, the agent's reply rendered like a user message or its plain note — pick a numbered report in send order, answer a fielded report in the Reports tab and switch dark/light themes. Field options render as text nodes; an unconfirmed submission keeps the user's input and says so. The default dark palette was supplied by the owner from Arena's UI.

## Fields in a report

The renderer splits a source into prose blocks and fields before rendering. A field is written as Markdown:

| Marker | Control | Notes |
| --- | --- | --- |
| `- ( ) option` list | Radio group | `- (x)` preselects that option |
| `- [ ] option` list | Checkbox group | `- [x]` preselects that option |
| `Label: ___` or a bare `___` line | Text box | At most 2000 characters |

Consecutive marker lines of the same kind form one group. The prompt is the label before `___`, else the nearest non-empty
line above the group, stripped of list, heading, quote and emphasis markers and a trailing colon. The field ID is a slug of
that prompt, deduplicated with a numeric suffix; `{#my-id}` at the end of the prompt line sets it explicitly and is removed
from the rendered text. Markers inside fenced code blocks are literal text. Limits: 1–50 fields, prompts
1–500 characters, and 1–20 unique options of 1–200 characters, where a group may hold a single option. A duplicate option in one
group is an error, and the whole report then fails to render rather than silently dropping a choice.

`GET /api/reports/<id>/html` returns JSON with `html` and the field count, not raw HTML. `POST /api/reports/<id>/submit` pairs a
client-generated ID with per-field answers (text at most 2000 characters, `choice` one of its options, `checkbox` a unique subset of
its options) and writes one inbox note headed `REPORT <id> <title>:`, one indented line per field, `(skipped)` for absent or empty
answers. Resending is a new answer, not an update. A successful send also stores `{answers, at}` in browser storage under `answers:<report id>`; loading that report again pre-fills its controls from that record and shows a `✓ Sent <time>` receipt beside the button, so the user can amend and resend. The record is origin-local display state, never a server-side answer history: another browser shows the report's Markdown defaults. A report with no fields rejects a submission. Republishing a source does not change or delete answers already delivered.

## HTTP and trust boundary

Only `/`, `/api/state`, `/api/notes`, `/api/markdown` and published report routes are exposed. `/api/state` carries each note's `ack_kind` and `ack_text`, plus `ack_html` when a reply was rendered, and the reports in `seq` order; it never carries report submissions. `/api/markdown` accepts a bounded, token-protected draft and returns read-only HTML without writing any inbox record. It reuses the optional renderer; its absence must not prevent sending raw Markdown. The Write / Preview control is not a WYSIWYG editor. Confirmation stays beside Send, without an extra message block, and the last sent text becomes the empty textarea's placeholder with no label prefix. Published reports support `/api/reports/<id>/html`, `/source` and token-protected `/api/reports/<id>/submit`. No endpoint accepts arbitrary filesystem paths; only the agent's CLI can register a report. The browser cannot acknowledge messages. POST requires JSON, a bounded body and a per-process token. This is CSRF resistance, not authentication: anyone with preview access can read the page and obtain that token.

Treat the preview URL as private session access. Do not publish secrets. Do not enable CORS, arbitrary file serving or remote assets. Raw HTML in Markdown is disabled; renderer URL validation and the content policy constrain active content. Report titles and messages are text, not HTML. The server accepts the Arena proxy host and does not block iframe embedding.

## Observed transition — 2026-09-20, Asia/Manila

The owner requested the rename from `arena-live-steering` to `arena-preview-steering`, the new reporting skill and the shared tabbed page. The experiment persisted user notes while the agent was idle and delivered notes during continued work after a blocking question revealed the preview. The owner found this more usable than the prior ntfy channel. This establishes session-level evidence, not a guarantee about all clients, sandbox restarts or future Arena versions.

The owner reported that Arena's native file viewer exposed raw Markdown only after local commits. Until this migration, the reporting workflow therefore force-added ignored reports into a local `chore(reports): hold the local records` commit after real commits were pushed, never pushed that records commit, and undid it next turn. This workaround preserved visibility, not rendered Markdown. It is retired by explicit approval, not erased from history.

The old steering workflow used an external ntfy topic, agent-side page-fetch polling and a local ingestion log. Sandbox HTTP access to ntfy had produced misleading empty responses, while page-fetch could read it. Topic caching, response mangling and polling made that path fragile. The owner explicitly retired it during this session. The old instructions and implementation remain in Git history before the preview migration; they are historical, not active fallback instructions.

The owner explicitly warned that the preview may not be permanent. If it fails, report the observed failure and ask how to continue through ordinary chat. Do not silently resume ntfy, force-add report artifacts or claim a replacement was authorized forever. A future change can select another transport with fresh evidence and approval.

## Recovery and checks

- Preserve the ignored state directory and Markdown sources when restarting. Process IDs, venv packages and URLs are not durable; restore the approved renderer and restart the same state directory as needed.
- Reload an old browser page after server restart to obtain the new submission token. Keep/copy an unsent draft first if browser storage is unavailable. Browser drafts are origin-local, not a cross-device backup.
- If a port is occupied, identify its owner or select another port; never kill an unrelated service. A failed read or save must remain visible, not become an empty state.
- Run `python <skill>/scripts/check_preview.py` with `markdown-it-py` available. It checks missing state, persistence, concurrent retry deduplication, receipt transactions, multiple reports, Markdown fields and their answer submissions, unsafe Markdown, absent-renderer behavior, validation, the retired form and export routes and HTTP route boundaries.
- Check `assets/app.js` with `node --check` and run `node scripts/check_client.cjs` where Node is available. The latter uses a minimal simulated DOM to check theme defaults/persistence, tabs, drafts, Enter/IME, retries, receipt display and report-field answers. These checks do not prove actual browser rendering, focus behavior, storage or iframe visibility; record manual browser observations separately.
- Migration of the first experiment: stop its server, import its final `notes.ndjson`, explicitly acknowledge only IDs already acknowledged in chat, and start this server with the new state directory. Keep the old file until verified; do not delete user messages to migrate.

Browser attachment links returned HTTP 200 with attachment headers during this session, but the owner observed no download in the Arena sandbox preview. The exact browser restriction was not identified. By explicit owner choice, the UI offers no download/source controls, and the standalone HTML export was removed on 2026-09-20 because it never worked in that preview. The Markdown source and the live Reports tab are the delivery path; never claim embedded downloads work.

The JSON form path — `publish-form`, the `forms` table, `/api/forms/<id>` and `/api/forms/<id>/submit`, the Forms tab and the `FORM <id> <title>:` note header — was removed on 2026-09-20 by explicit owner choice, once report fields covered the same three control types with rendered Markdown context around them. A questionnaire is now a report whose source is only field markers, and every answer arrives as a `REPORT` note. `/api/forms/*` returns 404; do not document, publish or promise a form.

The shared renderer opens non-fragment Markdown links in a new tab with `noopener noreferrer`, so report, draft and log links do not navigate the preview. Fragment links stay in place. Browser popup restrictions remain outside the server's control.

Acknowledgements moved into the log on 2026-09-20 at the owner's request: `ack` now requires `--reply <markdown>` or `--note <text>`, the reply renders with the same message CSS as a user note, and each log entry shows its ID so the owner can match it to an agent acknowledgement. With a visible preview that in-log answer replaces the chat `ACK:` line; chat acknowledgement remains the fallback when no preview is visible. The former bare `ack <ids>` form is gone: an acknowledgement without an answer text is rejected.

Report answers left the message log on 2026-09-20 at the owner's request: the `✓ Sent` receipt in the Reports tab is the user's confirmation, and answers now live in their own table so the log shows only what the user wrote. Receipts show a 7-character ID prefix, `ACK-ed` and `Awaiting ACK`, to fit narrow screens. Existing REPORT notes written before the move stay in the log as history.
