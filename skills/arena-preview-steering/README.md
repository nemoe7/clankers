# Preview steering: maintainer notes

This file belongs only in the source skill at `skills/arena-preview-steering/README.md`.
It is not an agent instruction and must not ship in `.agents/skills/arena-preview-steering/`.
The distributed `SKILL.md` and `references/REFERENCE.md` contain operating instructions only.

## Runtime and stored data

The shared runtime is `scripts/preview.py`. It uses Python 3.10+ and standard-library HTTP,
JSON, and SQLite. `serve` requires `markdown-it-py` in the preview venv. CLI steering does not.
The server binds `0.0.0.0` and accepts the Arena preview host and iframe. Browser API paths are relative.

The state directory holds `state.sqlite3`, `saved-state.ndjson`, report sources, and file bytes.
SQLite transactions write notes, receipts, tasks, report snapshots, answers, uploads, and fetch jobs.
`read` prints pending items before it stamps only those delivered IDs Seen. A failed output leaves them unseen.
`ack` records one reply or plain note and keeps the first acknowledgement time on later edits.
A changed answer sets `ack_edited_at`. A report answer stays outside the Notes log.
Reports keep their first-publish sequence. Schema migrations add nullable columns and backfill sequence IDs.

The NDJSON file tracks notes, tasks, and report answers. It does not contain report snapshots,
queued jobs, or uploaded/downloaded bytes. Normal note/task/answer writes refresh it.
Fetch queue writes do not, and the two import commands leave it unchanged.
The clipboard Copy state button exports Notes and Tasks, not report answers.
A restore needs both `import-notes` and `task-import` if the database was lost.
Republish surviving report sources after restoring a database without reports.

## Reports and inputs

The renderer uses `markdown-it-py` with tables, lists, links, and emphasis.
It disables raw HTML, avoids external report resources, and does not provide Mermaid or syntax highlighting.
Reports keep Markdown snapshots. The renderer parses field markers from each snapshot, not stored field records.
The report API returns JSON with rendered HTML, not raw HTML.
Each answer POST carries the rendered report revision. A missing revision returns HTTP 400.
A stale revision returns HTTP 409. The revision check and answer write use one transaction.
Report answers live in a separate `submissions` table and appear as `kind: report` in CLI reads.
Every resend creates a new submission. An answered report ID refuses republishing.
The UI shows whether the agent answered the latest submission, not just an earlier one.

## Note attachments

The composer sends one note and one to five files together through `/api/notes/with-file`.
The note has one ID and one acknowledgement. `read` includes each file in `attachments[]`.
Files stay outside SQLite under `<state-dir>/uploads/`. Each file is at most 50,000,000 bytes.
Multiple files use `<note-id>-1`, `<note-id>-2`, and so on, plus their original extensions.
A one-file note keeps its note ID in the filename for existing links.
The legacy `/api/uploads` route can still create a separate upload note.
Records keep the owner's original filenames. `present` reports whether bytes still exist.
An identical retry repairs lost file bytes without changing the note receipt or file order.
The server limits multipart bodies and rejects files above the cap with HTTP 413.

## Browser download queue

The owner enters one HTTPS URL per job. The browser fetches directly first.
The owner can allow AllOrigins, then CodeTabs, as fallback for that URL only.
Both proxies see the full URL. The URL validator rejects embedded credentials.
The server holds `fetch_jobs` rows and five-minute claims. An active browser renews its claim.
An abandoned claim returns to the queue. Jobs run one at a time in each open browser.
The browser checks declared and streamed bytes against the 50,000,000-byte cap.
Completed bytes go under `<state-dir>/downloads/`, outside SQLite.
The saved result writes one inbox note with a path. Jobs and notes can outlive file bytes.
The NDJSON backup does not include jobs or file bytes.

Every preview page receives the same write token. It is a CSRF guard, not owner authentication.
An unauthenticated `GET /api/state` returns Notes, Reports, and that write token to a client
that can reach the server. The app itself cannot prove the client is the owner.
The owner-entered queue is not a secure agent-initiated approval flow.
Any future approval must be enforced outside agent-writable code, state, and database files.

## HTTP behavior and checks

The server uses a per-process write token. State responses return the token to the preview page.
A restart changes it. The browser refreshes it from the state poll and retries a rejected write once.
An unconfirmed write stays a failure and leaves the draft available for another attempt.
Server responses set no-sniff and a restrictive CSP.
The server does not enable CORS or arbitrary file serving.

Edit readable sources under `skills/refs/arena-preview-steering/` first.
Build both runtime copies with `python3 maintenance/minify.py --update`.
Measure budgets with `python3 maintenance/check.py --update` and check drift without `--update`.
Run `python3 skills/refs/arena-preview-steering/scripts/check_preview.py` with `markdown-it-py`.
Run `node --check skills/refs/arena-preview-steering/assets/app.js` and
`node skills/refs/arena-preview-steering/scripts/check_client.cjs` when Node is available.
Run `python3 maintenance/check_minify.py` to check generated parity and parsed behavior.
Local checks cannot prove actual browser rendering or browser download behavior.

`.github/workflows/distribute-arena.yml` copies tracked skill files to target repositories.
It must exclude this root `README.md` in both its copy list and its verification list.
A manual whole-folder copy may include the README unless the human omits it.
