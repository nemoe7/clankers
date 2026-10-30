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

The default state directory is `arena-state`. Set `ARENA_STATE_DIR` or pass `--state-dir` to use another directory. The SQLite database is `state.sqlite3`. Uploaded files live in its `uploads/` directory.

Keep session state outside version control.

## Browser features

### Messages

- View messages oldest first, search their content and acknowledgements, load older history, and jump to the newest message or a new reply.
- See sent, seen, and acknowledged states. Show or hide hidden messages, and ask a waiting agent to skip its poll.
- Write Markdown, preview the draft, expand the composer, attach files, remove staged attachments, and drop files into the messages area.
- A paste over 2,400 characters or 40 lines becomes a text attachment.
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
- Open report images and Mermaid diagrams in the same lightbox as messages. Markdown supports tables, strikethrough, highlights, task lists, links, code copying, syntax highlighting, and Mermaid rendering.
- Mermaid needs its vendor asset. Code blocks also support diff highlighting and a Mermaid source toggle.

### Session controls

- Open survey results from the connection indicator and request a fresh bible check. The interrupt control can also request attention.
- The browser reports its timezone to the server. Displayed timestamps use that timezone.
- The client uses WebSocket for live updates, reconnects after a disconnect, and falls back to polling. Add `?transport=poll` to force the polling path.
- The active tab and selected report persist in browser session storage.

## CLI

Examples use the repo entry point. Use `--state-dir` with any command to select a session. Run a long-lived server separately from one-shot commands.

| Command | Purpose |
| --- | --- |
| `steer serve [--host HOST] [--port PORT]` | Start the server. `STEER_PORT` sets the default port. |
| `steer read` | Deliver pending messages and report answers. |
| `steer poll` | Wait for work or a skip-poll request. |
| `steer ack [ID] MARKDOWN` | Acknowledge one message or report answer. Omit the ID only when one pending item exists. Optional `-i`, `-t`, `-T`, `-S`, and repeatable `-d` create a linked task. |
| `steer msg list [-p PAGE]` | List message history, 10 items per page. |
| `steer msg show ID` | Show a message and its acknowledgements and attachments. |
| `steer tasks [-f] [-p PAGE]` | List upcoming tasks, or page through finished tasks with `-f`. |
| `steer task ID` | Show a task, its details, and blocking state. |
| `steer task new ID TITLE` | Create a task. Options include `-T` type, `-s` status, `-S` scope, repeatable `-d` details, `-m` message, `-r` report, and `-k` dependency. |
| `steer task mod ID FIELD VALUE` | Update `status`, `title`, `type`, or `scope`. Use `deets`, `links`, or `deps` to add or remove details and links. |
| `steer task unlink ID [TYPE] LINK` | Remove an inferred or explicit `msg`, `report`, or `task` link. |
| `steer task rm ID` | Remove a task. |
| `steer reports [-s] [-p PAGE]` | List reports, or stale reports with `-s`, 10 per page. |
| `steer report ID` | Show report fields and answers. |
| `steer report pub FILE -i ID -t TITLE` | Publish a UTF-8 Markdown report. |
| `steer report rm ID` | Dismiss one report. Use `--stale` to remove stale reports. |
| `steer rename OLD NEW` | Rename a task or report and update its links. |
| `steer survey` | Show the survey and submission template. Use `-i` for the smallest image, `--template` for the template, `-f FILE` for a submission, or `--interrupt` to request a check. |
| `steer pr-update -n NUMBER -t TITLE -f FILE` | Update a pull request with `gh`, then verify its title and body. |
| `steer job-log -j JOB` or `steer job-log -r RUN` | Print a GitHub Actions log with `gh`. Supply exactly one ID. |
| `steer worktree add NAME [-b BRANCH]` | Add a native Git worktree under `.worktrees/`. |
| `steer worktree list`, `remove NAME`, or `prune` | List, remove, or prune worktrees. |
| `steer run start NAME [--after NAME] -- COMMAND` | Start a detached named run. A dependency must exist and pass before its dependent starts. |
| `steer run logs NAME [-n LINES]` | Show run status and log tail. |
| `steer run pr-checks [-n NUMBER]` | Start a detached `gh pr checks --watch` run. |

Use `python skills/arena-steering/scripts/steer` in place of `steer` in the table when the entry point is not on `PATH`. Message and answer IDs are six lowercase hexadecimal characters. Task and report IDs use lowercase kebab-case.

## Task and message contracts

- Task types are `report`, `code`, `docs`, `ops`, and `misc`. Statuses are `upcoming`, `in_progress`, `blocked`, and `finished`.
- New tasks default to `code` and `upcoming`.
- Each detail must be nonempty and at most 120 characters. Dependencies must exist, and self-dependencies and cycles are rejected.
- Removing a task removes its dependency links from other tasks.
- Use `steer task mod ID deets TEXT` to append a detail and `steer task mod ID deets rm NUMBER` to remove one. Detail numbers are displayed from 1.
- Use `steer task mod ID links [msg|report|task] LINK` to add a link. Use `steer task mod ID links rm TYPE LINK` to remove one, or `steer task mod ID deps [rm] TASK` for dependencies.
- Message IDs use six lowercase hexadecimal characters. Parent IDs are deduplicated in order and must name existing messages.
- Blocking messages move from `sent` to `seen` to `acked`. Non-blocking messages need no acknowledgement.
- An acknowledgement contains nonempty Markdown. Repeated acknowledgements append replies.
- `read` and `poll` mark delivered items seen rather than acknowledging them.

## Runs and worktrees

Run names use letters, digits, dots, underscores, and hyphens and start with a letter or digit. Active duplicate names and missing dependencies are rejected. If a dependency fails, the waiting run exits with code 125 without starting its command.

Run records, logs, and exit files live under the state directory's `runs/` folder. `run logs` defaults to 50 lines. A completed name can be reused. `poll` waits up to 1,799 seconds, while the HTTP poll accepts a `timeout` query parameter capped at the same limit.

`worktree add` uses native Git and places the named worktree in `.worktrees/` at the repo root. `remove` uses Git's normal safety checks. The commands do not collect or apply worktree patches.

## Report fields

A field has a label followed by radio or checkbox options, or a labeled text blank. Mark a recommended option with `x`. A choice or checkbox field also offers a custom response in the UI. Field IDs derive from labels, or from an explicit anchor.

```markdown
Choose a storage format {#storage-format}

- (x) SQLite
- ( ) JSON

Select checks {#checks}

- [x] Unit tests
- [ ] Integration tests

Notes: ___
```

Field options must be unique, with 1 to 20 options and at most 200 characters per option. Reports retain answer history. The current inbox delivers only the newest unacknowledged answer per report, so earlier unacknowledged submissions can be missed if a later answer is acknowledged first.

### Report lifecycle

- Field IDs can also come from a preceding `<!-- field-id -->` comment. Field markers inside fenced code blocks are not parsed.
- Each submission must answer every field. Text and choice answers must be nonempty.
- Checkbox answers need at least one selected or custom value.
- Submissions append history, mark the report seen, reset acknowledgement visibility, and add formatted answers to linked task details. An acknowledgement can be appended more than once.
- `seen` records report viewing. `ack_seen` records viewing the latest acknowledged answer and resets on a new answer or acknowledgement.
- Republish and single-report removal reject a report when its latest answer is unacknowledged. Republish preserves answer history.
- Dismissal removes report links from tasks, while archived answers remain available for republishing.
- Stale listing selects answered or dismissed reports whose latest answer is acknowledged. Removal of stale reports uses that selection.
- These guards share the newest-answer limitation described above.

## HTTP and WebSocket

Routes accept an optional `/api` prefix. JSON routes return JSON. File uploads accept JSON or multipart form data.

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
| List messages | `all=1`, `hidden=1`, `before=ID`, and `limit=N` are optional. | `messages`, `total`, and `has_more`. |
| Create message | `body`, optional `id`, `hidden`, `blocking`, `parent_ids`, and `attachments`. | `message`, including rendered body and acknowledgement HTML. |
| Upload | JSON `file` object with `name` and `content_base64` or `text`, or multipart `file`. | `attachment` with name, path, size, presence, and static URL. |
| Message with file | Message fields plus `file`, `attachments`, or `pasted_text`. | `message`. A long paste uses `pasted-text.txt`. |
| Acknowledge | `markdown` or `ack`. | `message` or `answer`, depending on the route. |
| List tasks | `full=0` excludes finished tasks. | `tasks`, each with derived `blocked`. |
| Create or patch task | `id`, `title`, `type`, `status`, `scope`, `details`, and link lists. PATCH also accepts zero-based `position`. | `task`. Dependency ordering is enforced. |
| List reports | `stale=1` selects stale reports. `summary=1` omits report bodies. | `reports`. |
| Publish report | `id`, `title`, and Markdown `body`. | `report`, including parsed fields and rendered blocks. |
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

The survey accepts a graded JSON array, a JSON array string, or a nonempty key-value object. Array submissions use the schema in [`references/survey.json`](references/survey.json). Submitting clears the bible-check interrupt. The CLI also accepts `key=value` entries or a JSON array.

The server rejects paths that escape the relevant static directory. The server loads Mermaid from sibling `arena-skill/assets`, which must be present for diagram rendering.

## v1 and v2 parity

V1 is [`arena-skill`](../arena-skill/SKILL.md). V2 is this skill. This table describes the current repo implementations, not identical interfaces.

| Area | v1 | v2 |
| --- | --- | --- |
| Inbox and composer | Notes, acknowledgement receipts, search, Markdown preview, uploads, paste, and reply navigation. | Messages, acknowledgement replies, search, Markdown preview, uploads, paste, and multiple reply parents. |
| Tasks | Queue, task types, dependencies, report waits, filtering, and drag reorder. | Queue, types, dependencies, report waits, filtering, and API position updates. The browser view does not offer drag reorder. |
| Reports | Fielded reports, drafts, answer history, acknowledgements, stale listing, pinning, and visibility state. | Fielded reports, answer history, acknowledgements, seen states, and stale listing. No pin command or equivalent visibility-state command is exposed. |
| Report publication | CLI publication supports local-image embedding, marker checks, and optional submission schema. | CLI publication parses Markdown fields. It does not expose those publication options. |
| State recovery | Import, compare, save, restore, clear, status, cleanup, and userscript autosave. | SQLite persistence and uploaded files. No equivalent state-management CLI or userscript autosave is exposed. |
| Downloads and board | Browser download queue with agent approval and a multi-session board. | No Downloads or Board tab, or corresponding routes. |
| Runs and worktrees | Task-linked detached runs and tracked worktrees with allowed-patch collection. | Named detached runs with dependencies and logs, plus native Git worktree lifecycle commands. |
| Other CLI tools | Skill and agent discovery, inbox gate, key, outline, image data URI, and broader rename. | Task and report rename, task unlink, PR update, and job-log helpers. It does not expose those v1 discovery and gate utilities. |
| Rendering and transport | Markdown, Mermaid, image preview, WebSocket, and polling fallback. | Markdown, Mermaid, a lightbox, WebSocket, and polling fallback. Mermaid uses the sibling v1 vendor asset. |
| Survey and session | Survey results in server memory, interrupt, browser timezone, theme control, and mobile controls. | Survey data persists in SQLite. V2 has an interrupt and responsive views, but no theme selector. |
| Egress | Separate proxy routes and an opt-in external-channel recipe. | Neither is included in this skill. |

V2 is not a drop-in CLI or state-format replacement for v1. Its current multiple-answer delivery limitation is described above. Consult [v1 commands](../arena-skill/references/commands.md), [v1 reports](../arena-skill/references/reports.md), and the v2 source and tests for edge cases.

## Implementation and verification

The [models](scripts/arena_steering/models.py) validate data. The [store](scripts/arena_steering/store.py) persists it, [services](scripts/arena_steering/services.py) implement behavior, and [server](scripts/arena_steering/server.py) exposes transport. The [browser assets](assets/) render messages, tasks, reports, and the survey. Tests live in [`tests/skills/arena-steering`](../../tests/skills/arena-steering/).
