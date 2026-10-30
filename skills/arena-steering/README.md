# Arena Steering v2

Arena Steering lets an Arena.ai agent and its owner exchange messages, track dependent tasks, and answer fielded Markdown reports during a session. It includes the `steer` CLI, an HTTP and WebSocket server, a browser UI, and a SQLite store. Use it only in Arena.ai Agent Mode. See [SKILL.md](SKILL.md) for the agent entry point and [the changelog](../../docs/arena-steering/CHANGELOG.md) for changes.

## Start

Requirements: Python 3.11 or later, a persistent workspace, and a process tool that can keep the server running. Run commands from the repo root. The server defaults to port 8100 and listens on all interfaces, so expose it only in a trusted preview environment.

```cmd
python skills/arena-steering/scripts/steer --version
python skills/arena-steering/scripts/steer serve --port 8100
```

Open the preview URL supplied by the host. The demo starts a separate server with sample data:

```cmd
python skills/arena-steering/scripts/demo.py --port 8100
```

The state directory is `arena-state` in the working directory. V2 uses `steering-v2.sqlite3` there so its database does not collide with v1 `state.sqlite3`. Existing databases are not migrated or deleted. Uploaded files live in `arena-state/uploads/`.

The demo uses `arena-state/demo/` and reseeds its own database on startup.

Keep session state outside version control.

## Browser features

### Messages

- View messages oldest first, search their content and acknowledgements, load older history, and jump to the newest message or a new reply.
- See sent, seen, and acknowledged states. Show or hide hidden messages, and ask a waiting agent to skip its poll.
- Write Markdown, preview the draft, expand the composer, attach files, remove staged attachments, and drop files into the messages area.
- Open unambiguous message, report, and task references in their views. Parent navigation does not change the selected reply parents.
- Report links preload content on pointer hover or keyboard focus without marking the report seen.
- Staged files show uploading, ready, or failed states. Retry or remove failed files before sending.
- An unconfirmed send retains its draft and offers a retry. With session storage available, the retry uses the original request ID and payload after reload.
- Browser write requests use durable IDs and return the original result on retry. Discarding a retry does not undo an action that may already have succeeded.
- The browser keeps unconfirmed actions in session storage. If session storage is unavailable, it refuses to send a write rather than risk an unsafe retry.
- Selecting the same file again can resume an unconfirmed upload after reload. A separate action uses a new ID.
- Message text persists in session storage across reloads and tab changes. File objects do not persist across reloads.
- A paste over 1,500 Unicode characters or at least 15 lines becomes a text attachment. Ctrl+Shift+V pastes plain text without staging.
- Choose one or more parent messages by clicking their IDs. Shift-click copies an ID, and parent chips jump to their messages.
- Open message images and Mermaid diagrams in a lightbox. Use the wheel to zoom, drag to pan, and Escape or the close button to exit.

### Tasks

- View current, upcoming, and finished work. Search tasks, filter by type, expand details, and load more finished items by scrolling.
- Task dependencies determine order and blocking. An unanswered linked report or its latest unacknowledged answer also blocks a task.
- The task view shows scope, report links, and dependencies. The CLI and HTTP API also manage message links.

### Reports

- Select a report, navigate its headings, copy its Markdown, dismiss it, and return to the top.
- Answer radio, checkbox, and free-text fields, including custom choices. The floating submit button remains available while scrolling.
- View submitted answers and agent acknowledgements. New acknowledgements update an open report through WebSocket, and viewing an acknowledgement marks it seen.
- Open report images and Mermaid diagrams in the same lightbox as messages. Report Markdown supports tables, strikethrough, HTML, task lists, links, code copying, syntax highlighting, and Mermaid rendering.
- Mermaid needs its vendor asset. Code blocks also support diff highlighting and a Mermaid source toggle.

### Session controls

- Open survey results from the connection indicator and request a fresh bible check. The interrupt control can also request attention.
- The browser reports its timezone to the server. Displayed timestamps use that timezone.
- The client uses WebSocket for live updates, reconnects after a disconnect, and falls back to polling. Add `?transport=poll` to force the polling path.
- The active tab and selected report persist in browser session storage.

## CLI

Examples use the repo entry point. Run a long-lived server separately from one-shot commands.

| Command | Purpose |
| --- | --- |
| `steer serve [--host HOST] [--port PORT]` | Start the server. `STEER_PORT` sets the default port. |
| `steer read` | Deliver pending messages and report answers. |
| `steer poll` | Wait for work or a skip-poll request. |
| `steer ack [ID] MARKDOWN` | Acknowledge one message or report answer. Omit the ID only when one pending item exists. Optional `-i`, `-t`, `-T`, `-S`, and repeatable `-d` create a linked task. |
| `steer msg list [-p PAGE] [-s SIZE]` | List message history. Page size defaults to 5 and ranges from 5 to 50. |
| `steer msg ID` | Show a message and its acknowledgements and attachments. |
| `steer tasks [-f] [-p PAGE]` | List upcoming tasks, or page through finished tasks with `-f`. |
| `steer task ID` | Show a task, its details, and blocking state. |
| `steer task new ID TITLE` | Create a task. Requires at least one `-d` detail. Options include `-T` type, `-s` status, `-S` scope, `-m` message, `-r` report, `-k` dependency, and `-g` gate. |
| `steer task mod ID FIELD VALUE` | Update `status`, `title`, `type`, or `scope`. Use `deets`, `links`, or `deps` to add or remove details and links. |
| `steer task unlink ID [TYPE] LINK` | Remove an inferred or explicit `msg`, `report`, or `task` link. |
| `steer task rm ID` | Remove a task. |
| `steer reports [-s] [-p PAGE]` | List reports, or stale reports with `-s`, 10 per page. |
| `steer report ID` | Show report fields and answers. |
| `steer report pub FILE -i ID -t TITLE [-u]` | Publish and verify a UTF-8 Markdown report. `-u` allows unparsed strike markers. |
| `steer report rm ID` | Dismiss one report. Use `--stale` to remove stale reports. |
| `steer rename OLD NEW` | Rename a task or report and update its links. |
| `steer survey` | Show the survey and submission template. Use `-i` for the smallest image, `--template` for the template, `-f FILE` for a submission, or `--interrupt` to request a check. Submissions go to the running server when one is recorded. |
| `steer pr-update -n NUMBER -t TITLE -f FILE` | Update a pull request with `gh`, then verify its title and body. |
| `steer job-log -j JOB` or `steer job-log -r RUN` | Print a GitHub Actions log with `gh`. Supply exactly one ID. |
| `steer worktree add NAME [-b BRANCH]` | Add a native Git worktree under `.worktrees/`. |
| `steer worktree list`, `remove NAME`, `prune`, or `collect NAME` | List, remove, or prune worktrees, or print the patch a worktree carries against its merge base. |
| `steer run start [-t TASK] [-a NAME] NAME -- COMMAND` | Start a detached named run and optionally link it to a task. A dependency must exist and pass before its dependent starts. |
| `steer run logs NAME [-n LINES]` | Show run status and log tail. |
| `steer run pr-checks [-n NUMBER]` | Start a detached `gh pr checks --watch` run. |
| `steer gate [-p] [-l LINE]` | Refuse a command or push while a message or report answer waits for an acknowledgement. |
| `steer skills [-j]` | List skill names, sources, paths, and descriptions. Installed copies win over repo copies. |

Use `python skills/arena-steering/scripts/steer` in place of `steer` in the table when the entry point is not on `PATH`. Message and answer IDs are six lowercase hexadecimal characters. Task and report IDs use lowercase kebab-case.

## Inbox gate

`steer gate` is the pre-command check for a shell hook. It exits 1 while a message or report answer awaits an acknowledgement, prints the pending IDs, and names the blocked part of the line. Exit 0 means the inbox is clear.

```sh
trap 'skills/arena-steering/scripts/hooks/gate.sh "$BASH_COMMAND"' DEBUG
```

Set `STEER` to the entry point when `steer` is not on `PATH`. `-p` words the refusal for a push. The hook wrapper ships as `scripts/hooks/gate.sh`, and how a shell installs it is left to `install.sh`.

## Task and message contracts

- Task types are `report`, `code`, `docs`, `ops`, and `misc`. Statuses are `upcoming`, `in_progress`, `blocked`, and `finished`.
- New tasks default to `code` and `upcoming`.
- New and updated tasks require at least one nonempty detail of at most 120 characters.
- Existing empty tasks remain readable but need a detail on their next update.
- Dependencies must exist. Self-dependencies and cycles are rejected.
- Linked report answers are stored as distinct task snapshots, with their values, labels, and timestamps. They survive unlinking and report removal.
- Acknowledgement with task options creates the task first and commits both changes together. Failed validation leaves the target unacknowledged.
- On upgrade, linked historical answers are backfilled. Legacy answers use their last recorded modification time and current field labels when original metadata is unavailable.
- Removing a task removes its dependency links from other tasks.
- Use `steer task mod ID deets TEXT` to append a detail and `steer task mod ID deets rm NUMBER` to remove one. Detail numbers are displayed from 1.
- Use `steer task mod ID links [msg|report|task|gate] LINK` to add a link. Use `steer task mod ID links rm TYPE LINK` to remove one, or `steer task mod ID deps [rm] TASK` for dependencies.
- Message IDs use six lowercase hexadecimal characters. Parent IDs are deduplicated in order and must name existing messages.
- Blocking messages move from `sent` to `seen` to `acked`. Non-blocking messages need no acknowledgement.
- An acknowledgement contains nonempty Markdown. Repeated acknowledgements append replies.
- The message acknowledgement route returns an answer object when its target is a report answer.
- Reply receipts use a persisted seen flag and a reply-list digest. Viewing the end of a rendered reply list marks that revision seen.
- A newer reply resets the flag.
- Existing replies start unseen after upgrade. Stale receipt updates return HTTP 409 and do not hide newer replies.
- No unread-reply count is stored or shown.
- `read` and `poll` mark delivered items seen rather than acknowledging them.

## Runs and worktrees

Run names use letters, digits, dots, underscores, and hyphens and start with a letter or digit. Active duplicate names and missing dependencies are rejected. If a dependency fails, the waiting run exits with code 125 without starting its command.

A linked gate blocks a task while its run is active. A stopped run unblocks the task even if it failed. Review the verdict with `run logs`. A missing run is not active.

The task view refreshes linked gate state while open.

Run records, logs, and exit files live under the state directory's `runs/` folder. `run logs` defaults to 50 lines. A completed name can be reused. `poll` waits up to 1,799 seconds, while the HTTP poll accepts a `timeout` query parameter capped at the same limit.

`worktree add` uses native Git and places the named worktree in `.worktrees/` at the repo root. `remove` uses Git's normal safety checks. The commands do not collect or apply worktree patches.

## Report fields

New fielded reports use question and option comments. The question comment supplies its unique ID and submitted label. Each option comment supplies its submitted label.

```markdown
<!-- question {"id":"storage-format","label":"Storage"} -->
Choose a storage format

- (x) SQLite <!-- option {"label":"Use SQLite"} -->
- ( ) JSON <!-- option {"label":"Use JSON"} -->

<!-- question {"id":"checks","label":"Checks"} -->
Select checks

- [x] Unit tests <!-- option {"label":"Run unit tests"} -->
- [ ] Integration tests <!-- option {"label":"Run integration tests"} -->

<!-- question {"id":"notes","label":"Notes"} -->
Notes
```

Radio options use `( )`, and checkbox options use `[ ]`. A question without options is a text field. V2 adds a `Something else...` input automatically.

Selecting SQLite produces `Storage: Use SQLite`. Custom answers use the entered text.

Field options must be unique, with 1 to 20 options and at most 200 characters per option. Reports retain answer history. Like v1, the inbox requires acknowledgement only for the latest answer to each report. Earlier answers remain in history.

### Report lifecycle

- Existing saved reports retain their original fields. New and republished fielded reports require question and option comments.
- Code fences are not parsed as fields.
- Reports allow arbitrary HTML from trusted authors. Active HTML can access the viewer's origin and data.
- Do not open untrusted reports.
- `==text==` stays plain in reports. Use `<mark>` for highlights and fenced `diff` blocks for diffs.
- Publication rejects likely unparsed paired `~~` markers unless `-u` or `allow_unparsed_markers: true` is supplied. It verifies the saved report and rendered output.
- A verification failure does not guarantee rollback.
- Each submission must answer every field. Text and choice answers must be nonempty.
- Checkbox answers need at least one selected or custom value.
- Submissions append history, mark the report seen, reset acknowledgement visibility, and add formatted answers to linked task details. An acknowledgement can be appended more than once.
- `seen` records report viewing. `ack_seen` records viewing the latest acknowledged answer and resets on a new answer or acknowledgement.
- Republish and single-report removal reject a report when its latest answer is unacknowledged. Republish preserves answer history.
- Dismissal removes report links from tasks, while archived answers remain available for republishing.
- Stale listing selects answered or dismissed reports whose latest answer is acknowledged. Removal of stale reports uses that selection.

## HTTP and WebSocket

Routes accept an optional `/api` prefix. JSON routes return JSON. File uploads accept JSON or multipart form data.

Write requests may include `_request_id` to replay the original result safely. The server retains request records with its database.

| Routes | Purpose |
| --- | --- |
| `GET /health` | Server health and timezone. |
| `GET, POST /messages` and `GET /messages/{id}` | List, create, and inspect messages. |
| `POST /messages/with-file` and `POST /uploads` | Create an attachment-bearing message or stage an upload. |
| `POST /messages/{id}/ack` | Acknowledge a message. |
| `GET /poll` and `POST /poll/skip` | Wait for work or request a skip. |
| `GET, POST /tasks` and `GET, PATCH, DELETE /tasks/{id}` | Manage tasks. |
| `GET, POST /reports` and `GET, PATCH, DELETE /reports/{id}` | List, publish, inspect, and dismiss reports. PATCH handles dismissal only. |
| `POST /reports/{id}/seen` and `/reports/{id}/ack-seen` | Record owner visibility of a report and its acknowledgement. |
| `POST /reports/{id}/answers` and `/reports/{id}/answers/{answer_id}/ack` | Submit and acknowledge report answers. |
| `GET, POST /survey` and `POST /survey/interrupt` | Inspect or submit a survey and request a bible check. |
| `POST /timezone` and `POST /markdown` | Set the display timezone and render Markdown. |
| `/api/ws` | WebSocket requests, change notifications, heartbeat, reload, and `report.acked` events. |
| `/static/assets/`, `/static/reports/`, and `/static/uploads/` | Serve UI assets, report files and Markdown, and uploaded files. |

### API payloads and responses

Successful creates return HTTP 201. Other successful route operations return 200. Unknown routes or IDs return 404, unsupported methods return 405, and value-validation errors return 400 with an `error` string.

| Operation | Request or query | Response |
| --- | --- | --- |
| Mark message replies seen | `revision` is the rendered reply-list digest. | `message` and `matched`. Stale revisions return HTTP 409. |
| List messages | `all=1`, `hidden=1`, `before=ID`, and `q=TEXT` are optional. Pages contain at most 20 messages. | `messages`, `total`, and `has_more`. |
| Create message | `body`, optional `id`, `request_id`, `hidden`, `blocking`, `parent_ids`, and `attachments`. | `message`, including rendered body and acknowledgement HTML. |
| Upload | JSON `file` object with `name` and `content_base64` or `text`, or multipart `file`. | `attachment` with name, path, size, presence, and static URL. |
| Message with file | Message fields plus `file`, `attachments`, or `pasted_text`. | `message`. A long paste uses `pasted-text.txt`. |
| Acknowledge | `markdown` or `ack`. | `message` or `answer`, depending on the route. |
| List tasks | `full=0` excludes finished tasks. | `tasks`, each with derived `blocked`. |
| Create or patch task | `id`, `title`, `type`, `status`, `scope`, `details`, and link lists. PATCH also accepts zero-based `position`. | `task`. Dependency ordering is enforced. |
| List reports | `stale=1` selects stale reports. `summary=1` omits report bodies. | `reports`. |
| Publish report | `id`, `title`, Markdown `body`, and optional boolean `allow_unparsed_markers`. | Verified `report`, including parsed fields and rendered blocks. |
| Patch report | `status` set to `dismissed`. Other values leave it unchanged. | `report`. |
| Submit answers | `values` keyed by field ID, with an optional answer `id`. | `answer` and updated `report`. |
| Set timezone | `timezone`, an IANA zone such as `Asia/Manila`. | `timezone`. |
| Render Markdown | `markdown` and optional `breaks`. | Rendered `html` and `headings`. |
| Survey | POST accepts `answers` or a direct array or object. The interrupt accepts optional `active`. | `survey`. |

For example, send this JSON body to `POST /api/messages`:

```json
{"body":"Please review the report.","blocking":true,"parent_ids":[]}
```

For `POST /api/reports/example/answers`, a choice, checkbox, and text response can use this shape:

```json
{"values":{"storage-format":"SQLite","checks":["Unit tests"],"notes":"Ready"}}
```

The IDs and options must match the published report. A custom choice can use `{"selected":"Something else...","custom":"value"}`. A checkbox custom response can use `{"selected":["Unit tests"],"custom":"value"}`.

### WebSocket and survey details

WebSocket RPC requests carry an `id`, `method`, `path`, and JSON-encoded string `body`. Responses carry `type: response`, the same `id`, HTTP `status`, `contentType`, and a JSON-encoded string `body`. Supported methods are GET, POST, PATCH, and DELETE.

The server sends `change`, `reload`, `heartbeat`, and `report.acked` events. Respond to a heartbeat with `{"type":"pong"}`. Messages are limited to 16 MiB, and an idle connection closes after 35 seconds.

A survey takes a graded JSON array, a JSON array string, or a nonempty key-value object. Array submissions follow [`references/survey.json`](references/survey.json). Answers, graded results, and a check stamp live only in server memory, so a restart clears them.

`steer serve` writes its port to `server.json` inside a state directory, and the CLI posts submissions there. When no server answers, grading happens in that CLI process. Submitting clears a bible-check interrupt.

The server rejects paths that escape the relevant static directory. The v2 assets include Mermaid and its license.

## v1 and v2 parity

V1 is [`arena-skill`](../arena-skill/SKILL.md). V2 is this skill. This table describes the current repo implementations, not identical interfaces.

| Area | v1 | v2 | Parity |
| --- | --- | --- | --- |
| Start and configuration | `init`, `serve`, state directory, installed wrapper, and restore installer | `serve`, fixed `arena-state` directory, and browser timezone | No v2 `init --tz` or equivalent install and restore workflow. |
| Inbox | Read and poll, note history, quiet notes, seen receipts, and acknowledgement receipts | Read and poll, message history, hidden messages, non-blocking messages, and acknowledgement replies | Names and paging differ. |
| Message composer | Markdown preview, staging, paste, drop, expansion, reply links, search, and jumps | Preview, staging, paste, drop, expansion, multi-parent replies, search, and jumps | Parity for the paste thresholds, Ctrl+Shift+V bypass, IME guard, and touch Enter. V2 adds multi-parent replies. |
| Message extras | Slash commands, reference navigation, and persisted reply-seen counts | Reference navigation, multi-parent replies, and persisted boolean reply receipts | V2 omits slash commands and does not store or show unread-reply counts. |
| Tasks | Typed queue, status, details, report waits, dependencies, ordering, drag reorder, filters, and linked answers | Typed queue, derived report, dependency, and running-gate blocking, details, search, and filters | Both require task details. V2 intentionally drops drag reorder. Both retain answer snapshots. V2 creates tasks and acknowledges their targets atomically. |
| Reports | Fielded Markdown, recommended choices, custom choices, locally saved drafts, submissions, and acknowledgements | Fielded reports, custom choices, history, acknowledgements, seen stamps, table of contents, and floating submit | V2 loses an unsent answer on a tab round trip. Both require acknowledgement only for the latest answer. |
| Report lifecycle | Stale listing, pin and unpin, state and visibility, guarded unpublish, and worker answer and forward | Stale listing and removal | No pin, visibility-state, worker answer, or forward routes. Guards and republish contract differ. |
| Report publication | Local image embedding, diff marker validation, optional submission format, and publication verification | Markdown publication and field parsing | Local image embedding is intentionally dropped. No marker-validation flag, schema option, or explicit rendered verification step is present. |
| Markdown and images | Markdown, code controls, Mermaid, images, and zoomable preview | Markdown, code copying, Mermaid, images, and a lightbox | V2 bundles Mermaid. Renderer compatibility needs verification. |
| State recovery | Import, compare, save, restore, clear, size status, clean, and userscript autosave | SQLite persists normal state | No matching state-management or userscript-autosave CLI commands. Backups do not imply attachment bytes are preserved. |
| Downloads | Browser download queue, approval for agent requests, retries, and optional proxy fallback | Upload staging and static attachment serving | V2 intentionally drops browser downloads and agent download requests. |
| Multi-session | Board, allowlist, main session, heartbeat, messages, attachments, and wake | Native Git worktrees | V2 intentionally drops the multi-session board. Worktrees do not replace coordination. |
| Runs | Detached named runs, dependency gating, task links, and later verdict notifications | Detached named runs, task links, logs, dependencies, and PR check watching | Both block linked tasks while a run is active. V2 does not provide later CLI verdict notices. |
| Worktrees | Tracked detached worktrees with gate and allowed-patch collection | Native Git add, list, remove, and prune under `.worktrees` | Different contract from gated patch collection. |
| Rename and unlink | Rename note, answer, task, or report. Unlink submissions from task answer lists | Rename task or report and unlink task links by ID and type | Note and answer rename and v1 submission-unlink semantics differ. |
| GitHub helpers | PR update with verification and job-log URL resolution, including proxy fallback | PR update with verification and job-log output via `gh` | Log return format and proxy fallback differ. |
| Utilities and gate | `skills`, `agents`, `key`, `gate`, `outline`, and `image-data-uri` | No corresponding v2 commands registered | Utilities and gate are separate from the core inbox. |
| Live transport | WebSocket, heartbeat, and polling fallback | WebSocket, heartbeat, reconnect, polling fallback, and typed report acknowledgement events | V2 deduplicates browser writes and uploads by request ID. Other clients must supply an ID to get the same protection. |
| Survey and interrupt | Survey, image prompt, results, and bible check | Survey CLI, image prompt, results modal, and interrupt | Storage, timing, and schema behavior need a contract-level comparison. |
| Appearance and navigation | Theme control, tab state, mobile navigation, and pinch zoom | Responsive tabs, image wheel zoom, and drag | V1 theme control and pinch gesture are not present in v2 page controls. |
| Proxy and external channel | Separate egress proxy routes and an opt-in external-channel recipe | No egress proxy or external-channel recipe | Separate from the browser steering server. |

V2 is not a drop-in CLI or state-format replacement for v1. Consult [v1 commands](../arena-skill/references/commands.md), [v1 reports](../arena-skill/references/reports.md), and the v2 source and tests for edge cases.

## Implementation and verification

The [models](scripts/arena_steering/models.py) validate data. The [store](scripts/arena_steering/store.py) persists it, [services](scripts/arena_steering/services.py) implement behavior, and [server](scripts/arena_steering/server.py) exposes transport. The [browser assets](assets/) render messages, tasks, reports, and the survey. Tests live in [`tests/skills/arena-steering`](../../tests/skills/arena-steering/).
