# Preview transport: operation and migration

## Runtime contract

The shared runtime is `scripts/preview.py`, relative to the steering skill. It uses Python 3.10+ standard-library HTTP, JSON and SQLite support. The report renderer imports `markdown-it-py` only when rendering or exporting. The reporting skill is a separate entry point, installed beside steering, not an independent copy of the server.

The chosen `--state-dir` contains `state.sqlite3`. Normal SQLite transactions handle concurrent browser sends and CLI receipts; no message is marked acknowledged by a read. Writes are committed before the server returns success. Notes retain IDs, server timestamps, text and optional acknowledgement timestamps. Reports retain stable IDs, titles, Markdown snapshots and update timestamps. Keep this directory Git-ignored and outside transient cache/build directories.

| Command | Purpose |
| --- | --- |
| `init` | Create state without starting HTTP |
| `serve --port 8000` | Start the shared interface on `0.0.0.0` |
| `read` | Print all unacknowledged messages; record check time |
| `ack <id> [<id> ...]` | Record receipts after visible chat acknowledgement |
| `publish <source.md> --id <id> --title <title>` | Add/update a report snapshot |
| `export <id> <output.html>` | Write a self-contained rendered report |
| `import-notes <notes.ndjson>` | Import the initial experiment's ID/text/time records without deduplicating by text or inventing receipts |

All commands take `--state-dir` before the subcommand. Commands that read existing state fail if the database is missing; they do not create a misleading empty inbox. Import is idempotent by ID and rejects an existing ID with different text. It does not import ntfy messages or claim they were acknowledged.

The UI sends the same client-generated ID on an unchanged retry. It distinguishes saving, confirmed storage and explicit agent acknowledgement; it never interprets an HTTP request or an inbox check as a chat acknowledgement. Errors preserve the draft. Switching views preserves the mounted composer. The user can send with Enter, use Shift+Enter for a newline, browse message history and switch dark/light themes. The default dark palette was supplied by the owner from Arena's UI.

## HTTP and trust boundary

Only `/`, `/api/state`, `/api/notes`, `/api/markdown` and published-report routes are exposed. `/api/markdown` accepts a bounded, token-protected draft and returns read-only HTML without writing any inbox record. It reuses the optional renderer; its absence must not prevent sending raw Markdown. The Write / Preview control is not a WYSIWYG editor. Confirmation stays beside Send, and the last sent text stays in the empty textarea's placeholder, without an extra message block. Published reports support `/api/reports/<id>/html`, `/source` and `/export`. No endpoint accepts arbitrary filesystem paths; only the agent's CLI can register a report. The browser cannot acknowledge messages. POST requires JSON, a bounded body and a per-process token. This is CSRF resistance, not authentication: anyone with preview access can read the page and obtain that token.

Treat the preview URL as private session access. Do not publish secrets. Do not enable CORS, arbitrary file serving or remote assets. Raw HTML in Markdown is disabled; renderer URL validation and the content policy constrain active content. Report titles and messages are text, not HTML. Standalone exports embed styling and a theme toggle, not runtime API calls. The server accepts the Arena proxy host and does not block iframe embedding.

## Observed transition — 2026-09-20, Asia/Manila

The owner requested the rename from `arena-live-steering` to `arena-preview-steering`, the new reporting skill and the shared tabbed page. The experiment persisted user notes while the agent was idle and delivered notes during continued work after a blocking question revealed the preview. The owner found this more usable than the prior ntfy channel. This establishes session-level evidence, not a guarantee about all clients, sandbox restarts or future Arena versions.

The owner reported that Arena's native file viewer exposed raw Markdown only after local commits. Until this migration, the reporting workflow therefore force-added ignored reports into a local `chore(reports): hold the local records` commit after real commits were pushed, never pushed that records commit, and undid it next turn. This workaround preserved visibility, not rendered Markdown. It is retired by explicit approval, not erased from history.

The old steering workflow used an external ntfy topic, agent-side page-fetch polling and a local ingestion log. Sandbox HTTP access to ntfy had produced misleading empty responses, while page-fetch could read it. Topic caching, response mangling and polling made that path fragile. The owner explicitly retired it during this session. The old instructions and implementation remain in Git history before the preview migration; they are historical, not active fallback instructions.

The owner explicitly warned that the preview may not be permanent. If it fails, report the observed failure and ask how to continue through ordinary chat. Do not silently resume ntfy, force-add report artifacts or claim a replacement was authorized forever. A future change can select another transport with fresh evidence and approval.

## Recovery and checks

- Preserve the ignored state directory and Markdown sources when restarting. Process IDs, venv packages and URLs are not durable; restore the approved renderer and restart the same state directory as needed.
- Reload an old browser page after server restart to obtain the new submission token. Keep/copy an unsent draft first if browser storage is unavailable. Browser drafts are origin-local, not a cross-device backup.
- If a port is occupied, identify its owner or select another port; never kill an unrelated service. A failed read or save must remain visible, not become an empty state.
- Run `python <skill>/scripts/check_preview.py` with `markdown-it-py` available. It checks missing state, persistence, concurrent retry deduplication, receipt transactions, multiple reports, export, unsafe Markdown, absent-renderer behavior, validation and HTTP route boundaries.
- Check `assets/app.js` with `node --check` and run `node scripts/check_client.cjs` where Node is available. The latter uses a minimal simulated DOM to check theme defaults/persistence, tabs, drafts, Enter/IME, retries and receipt display. These checks do not prove actual browser rendering, focus behavior, storage or iframe visibility; record manual browser observations separately.
- Migration of the first experiment: stop its server, import its final `notes.ndjson`, explicitly acknowledge only IDs already acknowledged in chat, and start this server with the new state directory. Keep the old file until verified; do not delete user messages to migrate.

Browser attachment links returned HTTP 200 with attachment headers during this session, but the owner observed no download. The exact browser restriction was not identified. By explicit owner choice, the UI no longer offers download/source controls; keep the CLI HTML export and report sources, and never claim embedded downloads work.

The shared renderer opens non-fragment Markdown links in a new tab with `noopener noreferrer`, so report, draft and log links do not navigate the preview. Fragment links stay in place. Browser popup restrictions remain outside the server's control.
