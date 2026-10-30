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
- Open report images and Mermaid diagrams in the same lightbox as messages. Markdown supports code copying, syntax highlighting, and Mermaid rendering when its vendor asset is available.

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
| `GET, POST /reports` and `GET, PATCH, DELETE /reports/{id}` | List, publish, inspect, update, and dismiss reports. |
| `POST /reports/{id}/seen` and `/reports/{id}/ack-seen` | Record owner visibility of a report and its acknowledgement. |
| `POST /reports/{id}/answers` and `/reports/{id}/answers/{answer_id}/ack` | Submit and acknowledge report answers. |
| `GET, POST /survey` and `POST /survey/interrupt` | Inspect or submit a survey and request a bible check. |
| `POST /timezone` and `POST /markdown` | Set the display timezone and render Markdown. |
| `/api/ws` | WebSocket requests, change notifications, heartbeat, reload, and `report.acked` events. |
| `/static/assets/`, `/static/reports/`, and `/static/uploads/` | Serve UI assets, report files and Markdown, and uploaded files. |

The server rejects paths that escape the relevant static directory. The server resolves Mermaid from the sibling `arena-skill/assets` directory, so that vendor asset must be present for diagram rendering.

## Implementation and verification

The [models](scripts/arena_steering/models.py) validate data. The [store](scripts/arena_steering/store.py) persists it, [services](scripts/arena_steering/services.py) implement behavior, and [server](scripts/arena_steering/server.py) exposes transport. The [browser assets](assets/) render messages, tasks, reports, and the survey. Tests live in [`tests/skills/arena-steering`](../../tests/skills/arena-steering/).
