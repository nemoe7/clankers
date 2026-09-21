# CLI operations and recovery

## Invocation and state

Resolve `scripts/preview.py` from this skill, not the consuming repository. Use Python 3.10+ and the session's existing ignored state directory. Put global options before the subcommand:

```text
python <skill>/scripts/preview.py --state-dir <directory> [--save-path <file>] [--pretty] <command>
```

`--state-dir` defaults to `reports/arena-preview` and contains `state.sqlite3`. `--save-path` selects the save button's file, defaulting to untracked `saved-state.ndjson` at the repository root, outside the state directory. CLI JSON is minified; `--pretty` indents it for human inspection. Missing, unreadable or corrupt existing state is an error, not an empty inbox. Only `init` and `serve` create state.

| Command | Operation |
| --- | --- |
| `init` | Create state without HTTP |
| `serve [--port 8000]` | Start the shared server on `0.0.0.0`; use Arena's long-lived process tool |
| `read` | Print all pending notes and report answers; stamp `seen_at` and check time without acknowledging |
| `ack <id> [<id> ...] --reply <markdown>` | Acknowledge those IDs with a rendered answer |
| `ack <id> [<id> ...] --note <text>` | Acknowledge those IDs with a plain answer |
| `publish <source.md> --id <id> --title <title>` | Publish or update a report snapshot |
| `task <task-id> "<title>" [details ...]` | Create or update a task; flags below |
| `task-remove <task-id>` | Delete and echo one task |
| `task-list` | Print all tasks as JSON accepted by `task-import` |
| `task-import [file] [--replace]` | Import a JSON array or one record per line; stdin if no file |
| `import-notes <file>` | Restore notes and report answers from saved records, including supplied receipts and read stamps |

`serve` requires `markdown-it-py` and fails with an install command if missing. The other commands need no renderer. Reuse the same server, port and state for steering and reporting; never start another server per report. Do not run a long-lived server in a timed shell call. A busy port requires another free port or identification of its owner, never killing an unrelated service.

## Read and acknowledge

Use only CLI `read` to poll: direct database access and browser state requests do not stamp agent reads. Follow the entry point's polling cadence. Pending records distinguish `kind: note` and `kind: report`; both accept `ack`. Report answers stay separate from the message log. Read errors must remain visible.

Acknowledge exactly the delivered IDs, never all pending blindly. Supply exactly one of `--reply` or `--note`; one call carries one answer, so separate calls when answers differ. Unknown IDs fail the receipt batch. Repeated acknowledgement keeps its first timestamp and replaces the answer. Receipt is not completion. Use full IDs in CLI arguments; cite their first seven characters in prose, never sequence numbers. Without a visible preview, acknowledge in chat with literal `ACK:` and the interpretation.

## Tasks and message links

Task IDs are 1–64 lowercase letters, digits or hyphens, starting with a letter or digit. Titles allow at most 200 characters; each task at most 40 details of 2000 characters. Existing IDs update; omitted title/details retain stored values. The echo truncates each detail to 200 characters, not the stored value. Its `prev` and `next` identify neighbors within the same status group, null at either end.

| Flag | Operation |
| --- | --- |
| `--task-id`, `--task-title`, repeatable `--task-details` | Alternatives to the positional ID, title and detail arguments |
| `--task-details ""` | Clear all details |
| `--status upcoming` or `--status finished` | Set status; new tasks default to upcoming |
| `--order N` | Place at the 1-based position within its status group, not the end; positions stay dense after changes |
| `--msg-id <full-message-id>` | Link a note or report submission to this task |
| `--amend <previous-task-id>` | Rename an existing task to the supplied task ID, retaining title, details, status and position; refuse an existing destination |

Use `--msg-id` on the `task` command to set the message's `task_id`. Task and link are written together; an unknown message ID fails both writes. A linked note shows **Task added** in its log receipt, with the task ID in the tooltip. Report-submission links are stored without adding log messages. This marker means queued, not acknowledged or complete; still use `ack`.

Examples below follow the same `python <skill>/scripts/preview.py --state-dir <directory>` prefix:

```text
task fix-preview "Fix preview" "Check and test the reported failure" --msg-id <full-message-id> --order 1
task fix-preview --status finished
task-list
task-import saved-state.ndjson
```

`task-import` merges by ID; `--replace` clears first. It validates every record before writing in one transaction, so invalid input cannot erase the existing queue. Mixed save files skip note and report-answer records. `task-list` output can be saved for later import. Tasks need no Markdown renderer.

## Publish reports

Use the companion [reporting skill](../../arena-preview-reporting/SKILL.md) for field syntax and publishing procedure. Sources must be UTF-8 `.md`, at most 2,000,000 bytes. IDs are 1–80 letters, digits, hyphens or underscores; titles 1–200 characters. Invalid fields fail before storage. Keep one ignored source per report and republish its stable ID to update it. Editing the source alone does not update the published snapshot.

Republishing preserves first-publish order, clears the report's read stamp and never deletes delivered answers. `read` delivers submissions headed `REPORT <id> <title>:`, one indented line per field, `(skipped)` for empty answers; resending creates a new answer. Publishing never acknowledges a submission. Verify the rendered report before claiming delivery. A rendered-report failure leaves its source available for inspection; report the failure instead of claiming success.

## Recovery

1. Preserve ignored state and report sources outside cache/build directories. Process IDs, venv packages and URLs are not durable. Restore the approved renderer if needed, then restart with the same state directory. Reload an old browser page if its submission token is stale; first keep/copy an unsent draft if browser storage is unavailable. Drafts are origin-local, not cross-device backups.
2. Import `saved-state.ndjson` soon after the owner saves. It stays outside the state directory so a sandbox restore that removes that directory does not remove the backup. The file holds notes, tasks and report answers, not report source snapshots or upload bytes. Restore notes/answers and tasks separately:

   ```text
   python <skill>/scripts/preview.py --state-dir <directory> init
   python <skill>/scripts/preview.py --state-dir <directory> import-notes saved-state.ndjson
   python <skill>/scripts/preview.py --state-dir <directory> task-import saved-state.ndjson
   ```

3. Imports are idempotent by record ID. Note/answer imports preserve supplied text, timestamps, read stamps and complete receipts verbatim, plus task links and note origin. Missing receipts stay unacknowledged; partial receipts and conflicting existing text are rejected. Existing IDs keep their stored receipts. Never infer an answer from a pasted log or bulk-ack imported notes. The import does not fetch ntfy messages.
4. Republish reports from their saved Markdown sources. If the task backup is gone, rebuild finished tasks from `git log --oneline`, one task per shipped change with its commit in details, then `task-import` the records. Recover upcoming work from known requests, not invented completion claims.
5. Uploaded files live under `<state-dir>/uploads/`; restore may retain a record but lose its bytes. Check that the file exists before using it. The save file does not restore missing upload bytes.
6. Writes use a per-process token. Successful polls refresh it; 401/403 triggers one fresh-page token retry. A write that never reached a server waits one second and retries once. If saving still fails, preserve browser drafts/cached state and report the failure; do not treat an unconfirmed save as durable.
7. Keep backups until restoration is verified with `read`, `task-list` and the rendered reports. Failed reads or saves are errors, never empty state. Keep preview access private and never publish secrets. Do not commit or push state, inboxes, receipts or reports.
8. If preview remains unavailable, report the observed failure and ask in chat how to continue. Do not silently revive ntfy or local report commits; another delivery method needs fresh approval.
