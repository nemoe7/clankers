# Arena Steering v2

Arena Steering connects an Arena.ai Agent Mode session to a live browser preview for messages, tasks, and fielded reports. It bundles the `steer` CLI, an HTTP and WebSocket server, browser UI assets, and a SQLite store. [SKILL.md](../../skills/arena-steering/SKILL.md) holds the agent instructions, and [CHANGELOG.md](CHANGELOG.md) records module changes.

## Start

In Arena.ai Agent Mode, the session opens a preview tab with `Messages`, `Reports`, and `Tasks` views. Outside Arena, a local demo starts a separate server with sample data on a chosen port.

From the repo root in Windows cmd:

```cmd
python maintenance\demo-arena-steer.py --port 8100
python maintenance\demo-arena-steer.py --reset --port 8100
python -m pytest tests\skills\arena-steering
```

In Bash:

```bash
python3 maintenance/demo-arena-steer.py --port 8100
python3 maintenance/demo-arena-steer.py --reset --port 8100
python3 -m pytest tests/skills/arena-steering
```

The demo writes to `arena-state/demo/` and reseeds its database on startup or `--reset` without touching live session data. Inside an Arena container, `skills/arena-steering/scripts/install.sh` installs `steer` into `~/.local/bin`, initializes `arena-state/state.sqlite3`, and installs shell and commit hooks. `steer serve` listens on `0.0.0.0:8000` for the preview host and stores uploaded files under `arena-state/uploads/`. V2 uses its own SQLite schema and does not open or migrate v1 databases.

## Browser features

### Messages

- Messages appear oldest first with full-text search across bodies and acknowledgements, older-page loading, and unread-reply jump controls.
- Delivery badges distinguish sent, seen, and acknowledged messages, with optional hidden-message display and a poll-skip button.
- The composer supports Markdown preview, expanded editing, file staging, drag-and-drop uploads, and attachment removal.
- Clicking unambiguous message, report, or task IDs opens their view without changing selected reply parents.
- Hovering or focusing a report link preloads its content without marking the report seen.
- Staged attachments report uploading, ready, or failed states, and failed uploads support retry or removal before send.
- Write requests carry durable request IDs in session storage so reloads can safely replay unconfirmed actions.
- Draft text persists in local storage with session-storage fallback. Pastes over 1,500 characters or 15 lines stage as text attachments unless pasted with Ctrl+Shift+V.
- Clicking message IDs selects one or more parent references, Shift-click copies an ID, and images or Mermaid thumbnails open in a zoomable modal.

### Tasks

- Tasks group into current, upcoming, and finished sections with search, type filters, expandable details, and lazy-loaded history.
- Ordered phase chips (`report`, `code`, `docs`, `ops`, `misc`) show task progress, and finished phases render with a strikethrough.
- Unfinished dependencies, unanswered linked reports, and active gate runs mark a task blocked in the queue.
- Each task card displays its scope, Fibonacci size, linked reports, and task dependencies.

### Reports

- The report viewer provides a report selector, heading navigation, Markdown copy, report dismissal, and a scroll-to-top control.
- Fielded reports render radio, checkbox, and free-text inputs with built-in custom-answer inputs and a floating submit button.
- Submitted answer history and agent acknowledgements appear inline, and viewing an acknowledgement or reply marks that revision seen.
- View-only refreshes preserve focus in active form inputs, and tab indicators distinguish unread reports, unanswered questions, and unseen acknowledgements.
- Report Markdown supports tables, strikethrough, trusted HTML, task lists, syntax highlighting, diff blocks, and bundled Mermaid diagrams.

### Session controls

- The status indicator reports connecting, connected, polling, no-agent, and disconnected states from server heartbeats and agent activity.
- Header controls open survey results and send bible-check or attention interrupts to the session inbox.
- The browser sends its IANA timezone to the server for display timestamps and default shell `TZ` export.
- Live updates run over WebSocket with automatic reconnect and an HTTP polling fallback (`?transport=poll`).

## CLI reference

The `steer` entry point wraps `skills/arena-steering/scripts/steer` against the active session store. Message and answer IDs use six lowercase hex characters, while task and report IDs use lowercase kebab-case.

| Command | Purpose |
| --- | --- |
| `steer serve` | Start the HTTP and WebSocket server on `0.0.0.0:8000`. |
| `steer read` | Print pending messages and report answers and mark them seen. |
| `steer poll` | Wait up to 1,799 seconds for inbox work, a runnable task, or a skip signal. |
| `steer ack [ID ...] MARKDOWN` | Append a Markdown acknowledgement to one or more messages or report answers, optionally creating a linked task. |
| `steer msg list [-p PAGE] [-s SIZE]` | List message history (`5` to `50` items per page). |
| `steer msg ID` | Show one message with its acknowledgements and attachments. |
| `steer tasks [-f] [-p PAGE]` | List upcoming or finished task IDs and titles. |
| `steer task [-d]` or `steer task ID` | Show the current unblocked task or a named task with details and blocking state. |
| `steer task new ID TITLE -z SIZE -d DETAIL` | Create a sized task with optional ordered phases (`-T`), priority (`-p`), scope (`-S`), links, and dependencies. |
| `steer task finish ID [-c COMMIT]` | Validate phase evidence and advance the current phase. |
| `steer task mod ID ...` | Update task metadata, ordered phases, status, sized details (`deets`), links, or dependencies (`deps`). |
| `steer task unlink ID [TYPE] LINK` | Detach a message, report, or task link from a task. |
| `steer task rm ID` | Delete a task and remove its dependency edges from other tasks. |
| `steer reports [-s] [-p PAGE]` | List active or stale (`-s`) reports, 10 per page. |
| `steer report ID` | Show a report's parsed fields and submitted answers. |
| `steer report pub FILE -i ID -t TITLE [-u]` | Parse, publish, and verify a UTF-8 Markdown report. |
| `steer report pin ID` / `unpin ID` | Exclude a report from staleness or restore normal expiry. |
| `steer report rm ID [ID ...]` or `--stale` | Dismiss named reports or all stale reports. |
| `steer ren OLD NEW` | Rename a task or report and update references to it. |
| `steer survey [-f FILE] [--template] [entries ...]` | Show survey status and template, or submit graded JSON answers (`../../skills/arena-steering/references/survey.json`). |
| `steer pr-update -n NUMBER -t TITLE -f FILE` | Reject session-local IDs, patch a PR through `gh api`, and verify the remote title and body. |
| `steer job-log -j JOB` or `-r RUN` | Retrieve GitHub Actions job or run logs through `gh`. |
| `steer worktree add`, `list`, `remove`, `prune`, or `collect` | Manage native Git worktrees under `.worktrees/` or inspect a worktree patch. |
| `steer run start [-t TASK] [-a DEP] NAME -- CMD` | Start a detached background command with optional run dependency and task-gate link. |
| `steer run logs NAME [-n LINES]` | Read status and trailing output for a detached run. |
| `steer run pr-checks [-n NUMBER]` | Start a detached `gh pr checks --watch` run. |
| `steer skills` | List discovered skills across installed and repo paths. |

## Pre-command pipeline

`steer pre` implements the Bash `DEBUG` hook in [`pre.py`](../../skills/arena-steering/scripts/arena_steering/pre.py). `install.sh` registers a shell trap that passes each command line to `steer pre` before execution. Return status `0` lets the command run, `2` routes long commands into detached runs and exits cleanly, and `130` blocks the command.

`PIPELINE` runs `sleep`, `inbox-pipe`, `poll-timeout`, `pr-state`, `push-refs`, `wireframe`, `gate`, `git-safe`, `bible`, `route`, `ack-quote`, and `bare` in order. With blocking messages or unacknowledged latest report answers, `gate` blocks `git push` at once and ordinary commands after six counted calls. Inbox reads, polls, and acknowledgements stay open. `bible` blocks partial shell reads (`cat`, `grep`, `head`, `tail`, `rg`) on bible files, and `pr-state` blocks PR close, reopen, merge, and destructive ref writes.

## Data model and lifecycles

Each task carries ordered phases (`report`, `code`, `docs`, `ops`, `misc`), a Fibonacci size, and details (up to 120 characters for manual details). Report phases require a linked report or answer, while code and docs phases require a unique pushed commit hash on a clean tree. Adding or removing details or message and attachment links requires an explicit task size.

Blocking messages progress from `sent` to `seen` to `acked`, while non-blocking messages stop at `seen`. Reply receipts store a boolean seen flag paired with a SHA-256 digest of the acknowledgement list. Viewing the latest reply marks that digest seen, and stale digests return HTTP 409.

Fielded reports define radio, checkbox, and text questions that submit typed hidden answer messages in the shared hex ID space. Only the latest unacknowledged answer on a report blocks the inbox, and its first acknowledgement appends missing `label: value` details to linked tasks. Unpinned reports turn stale once all linked tasks finish, or 30 minutes after the owner views an unlinked report's latest acknowledgement.

Detached runs store logs and exit codes under `arena-state/runs/`. An active task-linked run blocks that task until the process exits, and dependent runs exit `125` if their prerequisite run fails. Worktrees live under `.worktrees/` at the repo root.

The [state backup contract](state-backup.md) describes planned userscript and container sync behavior, which remains unimplemented.

## HTTP and WebSocket reference

REST and static routes use unprefixed paths, and `/api/ws` provides WebSocket RPC and server events. Write payloads accept `_request_id` for idempotent replay.

| Routes | Purpose |
| --- | --- |
| `GET /health` | Server health, timezone, survey summary, and agent activity timestamps. |
| `GET, POST /messages` and `GET /messages/{id}` | Paged message queries (`all`, `hidden`, `before`, `q`), creation, and single-message lookup. |
| `POST /messages/with-file` and `POST /uploads` | Attachment-bearing message creation and JSON or multipart upload staging. |
| `POST /messages/{id}/ack` and `/messages/{id}/replies-seen` | Message acknowledgement and revision-checked reply-seen receipts (`409` on mismatch). |
| `GET /poll` and `POST /poll/skip` | Long-poll inbox wait (`timeout` up to `1799` seconds) and poll-skip trigger. |
| `GET, POST /tasks` and `GET, PATCH, DELETE /tasks/{id}` | Task queue listing (`full=0` omits finished tasks), creation, updates, phase completion, and deletion. |
| `GET, POST /reports` and `GET, PATCH, DELETE /reports/{id}` | Report listing (`stale=1`, `summary=1`), publication, inspection, pin toggles, and dismissal. |
| `POST /reports/{id}/seen` and `/reports/{id}/ack-seen` | Report-viewed and acknowledgement-viewed timestamps. |
| `POST /reports/{id}/answers` and `/reports/{id}/answers/{answer_id}/ack` | Report form submission and answer acknowledgement. |
| `GET, POST /survey` and `POST /survey/interrupt` | In-memory survey status, answer grading, and bible-check interrupt flags. |
| `POST /timezone` and `POST /markdown` | Display timezone updates and server Markdown rendering. |
| `GET /state/snapshot`, `GET /state/changes?since=`, `POST /state/merge`, `GET, POST /state/assets` | Opaque `state_version` cursor sync, deletion tombstones, timestamp-ordered row merge, and hash-addressed upload storage for referenced attachments. |
| `/api/ws` | JSON RPC (`id`, `method`, `path`, `body`) plus `change`, `reload`, `heartbeat` (`pong` reply, 35s idle timeout, 16 MiB cap), and `report.acked` events. |
| `/static/assets/`, `/static/reports/`, `/static/uploads/` | Path-checked static serving for UI assets (including bundled Mermaid), report files, and uploads. |

## v1 and v2 parity

[`arena-skill`](../archive/arena-skill/SKILL.md) holds the archived v1 implementation ([v1 commands](../archive/arena-skill/references/commands.md), [v1 reports](../archive/arena-skill/references/reports.md)). V2 uses a separate CLI and SQLite schema.

| Area | v1 | v2 | Difference summary |
| --- | --- | --- | --- |
| Setup | `init --tz`, `serve`, wrapper, and restore installer | `install.sh`, `serve`, fixed `arena-state/`, and browser timezone | V2 drops `init --tz` and restore installers. |
| Inbox and composer | Notes, quiet notes, slash commands, single reply link, and unread counts | Messages, hidden/non-blocking flags, multi-parent refs, and boolean reply receipts | V2 adds multi-parent refs and drops slash commands and unread counts. |
| Tasks | Manual status, drag reorder, report waits, and linked answer lists | Ordered phases with commit or report evidence, derived blocking, and sized details | V2 drops drag reorder and appends first-ack answer details to linked tasks. |
| Reports | Local image embedding, draft persistence across tabs, and worker forward routes | Table of contents, floating submit, viewed stamps, and paired-`~~` guard | V2 omits auto-embedded local images, tab-switch draft persistence, and worker routes. |
| State, downloads, and sessions | CLI save/restore/clear, browser download queue, multi-session board, and egress proxy | HTTP snapshot/changes/merge routes, static uploads, and native Git worktrees | V2 omits browser downloads, the multi-session board, userscript autosave, and proxies. |
| Runs and GitHub helpers | Detached runs with later CLI verdict notices and job-log URLs | Detached runs with task-gate links, `pr-checks`, verified `pr-update`, and `gh` log text | V2 omits delayed CLI verdict notices and returns log text through `gh`. |

## Architecture and tests

[`models.py`](../../skills/arena-steering/scripts/arena_steering/models.py) validates records, [`store.py`](../../skills/arena-steering/scripts/arena_steering/store.py) manages SQLite persistence, [`services.py`](../../skills/arena-steering/scripts/arena_steering/services.py) implements domain rules, and [`server.py`](../../skills/arena-steering/scripts/arena_steering/server.py) serves HTTP and WebSocket routes. Browser modules live in [`skills/arena-steering/assets/`](../../skills/arena-steering/assets/), and automated suites live in [`tests/skills/arena-steering/`](../../tests/skills/arena-steering/).

This README is human documentation and is not part of the installed skill payload.
