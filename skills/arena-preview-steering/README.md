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
Fetch queue writes do not, and the import command leaves it unchanged.
The clipboard Copy state button exports notes, tasks and answers for reports still in the tab.
A restore uses `import-state [FILE]` for notes, tasks and report answers together. The command accepts copied NDJSON, a JSON array or a state object, from a file or stdin. It merges by ID in one transaction and leaves the backup unchanged. `--replace-tasks` replaces only tasks.
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

Owner notes, draft rendering and form answers have no application length cap. Agent replies, reports, field definitions and tasks retain their limits. Request timeouts and structural checks stay. Browser, disk and proxy limits still apply.

Finished tasks show in reverse completion order. Upcoming tasks keep their stored order.

## Note attachments

The composer sends one note plus files through `/api/notes/with-file`.
Pasted clipboard images join staged attachments with epoch-millisecond names, image extensions and numeric suffixes for collisions. Text paste stays native. Images keep the same per-file limit and retry path.
Each note has one ID and acknowledgement. `read` lists files in `attachments[]`.
Files stay outside SQLite in `<state-dir>/uploads/`. Each is at most 50MB.
Name stored files with the note ID's first seven characters, Unix epoch seconds, and the original filename. Replace spaces with hyphens.
Only duplicate names add `-2`, `-3`, and so on after the timestamp. Keep existing files unchanged.
Legacy `/api/uploads` can still create a separate upload note.
Long names use a short disk name when required by the filesystem. Records keep the original filename. `present` reports if bytes exist.
Identical retries repair missing bytes without changing the note receipt or file order.
Multipart uploads stream each file to temporary storage without a total request cap. Each file keeps its 50 MB cap. The server rejects incomplete transfers before it saves the note.

## Browser download queue

The owner enters one HTTPS URL per job. That form queues immediately. An agent can run
`preview.py --state-dir arena-state download-request <https-url> [--allow-proxy]` to create a
`pending` approval record instead. The Downloads tab shows an approval dot and Approve/Deny buttons.
A pending request cannot be claimed. Approve makes it claimable and Deny prevents retry.
The browser fetches directly first. The owner can allow AllOrigins, then CodeTabs, as fallback
for that URL only. Both proxies see the full URL. The URL validator rejects embedded credentials.
The server holds `fetch_jobs` rows and five-minute claims. An active browser renews its claim.
An abandoned claim returns to the queue. Jobs run one at a time in each open browser.
Agent-requested downloads keep the 102,400,000-byte cap after approval. Owner-queued downloads have no application byte cap. Stored origin controls both browser and server checks. Older jobs retain the cap because their origin is unknown.
That cap is 80% of the documented 128,000,000-byte snapshot figure.
The figure is not measured.
It came from a workspace without GitHub.
One session reported 512 MB.
Completed bytes go under `<state-dir>/downloads/`, outside SQLite.
The saved result writes one inbox note with a path. Jobs and notes can outlive file bytes.
The NDJSON backup does not include jobs or file bytes.

**This approval is UI-only, not a security boundary.** Every preview page receives the same write
token. It guards against CSRF but does not authenticate the owner. `GET /api/state` returns the
token to a client that can reach the server. An agent can bypass the pending request by POSTing
directly to the existing immediately queued `/api/fetch-jobs` route, calling the decision route
with the shared token, or changing agent-writable code/SQLite state. A client with preview access
can click Approve or Deny. Do not rely on this gate for owner-only authorization. No password is
asked for or stored. Enforce a real approval outside agent-writable code and state if needed.

## HTTP behavior and checks

The server uses a per-process write token. State responses return the token to the preview page.
A restart changes it. The browser refreshes it from the state poll and retries a rejected write once.
An unconfirmed write stays a failure and leaves the draft available for another attempt.
Server responses set no-sniff and a restrictive CSP.
The server does not enable CORS or arbitrary file serving.

A running `poll` stamps a heartbeat once a second. The state payload carries `polling`, and the page turns its connection dot blue for the wait. The text line keeps its normal reading, so the dot is the only poll mark. The flag clears when the poll returns, and the freshness window expires it five seconds after a killed poll.

Edit readable sources under `skills/refs/arena-preview-steering/` first.
Build both runtime copies with `python3 maintenance/minify.py --update`.
Measure budgets with `python3 maintenance/check.py --update` and check drift without `--update`.
Run `python3 -m pytest` with `markdown-it-py` and `pytest`.
Run `node --check skills/refs/arena-preview-steering/assets/app.js` and
`node --test skills/refs/arena-preview-steering/scripts/client.test.cjs` when Node is available.
Run `python3 maintenance/check_minify.py` to check generated parity and parsed behavior.
Local checks cannot prove actual browser rendering or browser download behavior.

`.github/workflows/distribute.yml` copies tracked skill files to target repositories.
It must exclude this root `README.md` in both its copy list and its verification list.
A manual whole-folder copy may include the README unless the human omits it.
