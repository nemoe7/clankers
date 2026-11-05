# Arena Steering v2

Arena Steering lets an Arena.ai agent and its owner exchange messages, track dependent tasks, and answer fielded Markdown reports during a session. It includes the `steer` CLI, an HTTP and WebSocket server, a browser UI, and a SQLite store. Use it only in Arena.ai Agent Mode. See [SKILL.md](SKILL.md) for the agent entry point and [the changelog](../../docs/arena-steering/CHANGELOG.md) for changes.

## Start

Requirements: Python 3.11 or later, Bash, a persistent workspace, and a process tool that can keep the server running. After installing the skill under `.agents/skills/`, run:

```bash
.agents/skills/arena-steering/scripts/install.sh
```

The installer prepares `markdown-it-py`, initializes `arena-state/state.sqlite3` at the checkout root (preserving existing data on reinstall), installs `steer` in `~/.local/bin`, and adds that directory to `~/.bash_profile`. The pre-command gate can use the store immediately, without a first `steer read`.

The installer also replaces the repo's `commit-msg` hook with an inline validator. It refuses a custom `core.hooksPath` and does not read or ship the commit specification. Open a new login shell or source that profile, then run:

```cmd
steer --version
steer serve
```

The server listens on all interfaces at port 8000. Expose it only in a trusted preview environment, and open the preview URL supplied by the host. The repo demo starts a separate server with sample data and a configurable port:

```cmd
python maintenance/demo-arena-steer.py --port 8100
```

V2 uses `arena-state/state.sqlite3` at the checkout root, regardless of the working directory. Do not open a v1 database with v2. Existing databases are not migrated. Uploaded files live in `arena-state/uploads/`.

The demo uses `arena-state/demo/` and reseeds its own database on startup. Reset a running demo without restarting it:

```cmd
python maintenance/demo-arena-steer.py --reset --port 8100
```

Reset replaces the demo data with sample data and refreshes connected clients. It does not affect a normal steering server.

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
- Message text persists in local storage across reloads and browser tabs, with session storage as a fallback. File objects do not persist across reloads.
- A paste over 1,500 Unicode characters or at least 15 lines becomes a text attachment. Ctrl+Shift+V pastes plain text without staging.
- Choose one or more parent messages by clicking their IDs. Shift-click copies an ID, and parent chips jump to their messages.
- Open message images and Mermaid diagrams in a lightbox. Use the wheel to zoom, drag to pan, and Escape or the close button to exit.

### Tasks

- View current, upcoming, and finished work. Search tasks, filter by type, expand details, and load more finished items by scrolling.
- See ordered phase chips for each task. Finished phases fade and receive a strikethrough.
- Task dependencies, unanswered linked questions, and running gates can block work. A report used for an earlier phase does not block later work.
- The task view shows scope, report links, and dependencies. The CLI and HTTP API also manage message links.

### Reports

- Select a report, navigate its headings, copy its Markdown, dismiss it, and return to the top.
- Answer radio, checkbox, and free-text fields, including custom choices. The floating submit button remains available while scrolling.
- View submitted answers and agent acknowledgements. New acknowledgements update an open report through WebSocket, and viewing an acknowledgement marks it seen.
- Report input stays focused during view-only refreshes, even when an older refresh response arrives late.
- The Reports tab shows unread and needs-answer markers independently. The question marker takes the dot's place when shown alone.
- The tab and picker dots turn green for unseen acknowledgements unless an unread report takes precedence.
- Open report images and Mermaid diagrams in the same lightbox as messages. Report Markdown supports tables, strikethrough, HTML, task lists, links, code copying, syntax highlighting, and Mermaid rendering.
- Mermaid needs its vendor asset. Code blocks also support diff highlighting and a Mermaid source toggle.

### Session controls

- The connection indicator shows connecting, connected, polling, no agent, and disconnected states.
- Open survey results from its button and request a fresh bible check. The interrupt control can also request attention.
- A poll heartbeat stays blue while the agent waits. The indicator shows no agent after 3 minutes without activity following a turn end, or 32 minutes without activity otherwise.
- The browser reports its timezone to the server. Displayed timestamps use that zone, and the installed Bash gate exports it as `TZ` only when unset.
- The client uses WebSocket for live updates, reconnects after a disconnect, and falls back to polling. Add `?transport=poll` to force the polling path.
- The active tab and selected report persist in browser session storage.

## CLI

Examples use the repo entry point. Run a long-lived server separately from one-shot commands.

| Command | Purpose |
| --- | --- |
| `steer serve` | Start the server on `0.0.0.0:8000`, the same port v1 used. |
| `steer read` | Deliver pending messages and report answers. |
| `steer poll` | Wait for an inbox item, the first ranked runnable task, or Skip poll. Print a separate ready, timeout, or skipped status. A timeout exits 1. |
| `steer ack [ID ...] MARKDOWN` | Acknowledge one or more messages or report answers with one reply. Omit IDs only when one item is pending. |
| `steer msg list [-p PAGE] [-s SIZE]` | List message history. Page size defaults to 5 and ranges from 5 to 50. |
| `steer msg ID` | Show a message and its acknowledgements and attachments. |
| `steer tasks [-f] [-p PAGE]` | List only IDs and titles for upcoming or finished tasks; print nothing when empty. |
| `steer task [-d]` | Show the first unblocked upcoming task. Add `-d` or `--deets` to include details. |
| `steer task ID` | Show a task, its details, and blocking state. |
| `steer task new ID TITLE -d DETAIL [-T TYPE ...]` | Create an upcoming task. Repeat `-T` for ordered phases such as `-T report -T code`. Options also include `-S` scope, `-m` message, `-r` report, `-k` dependency, and `-g` gate. |
| `steer task finish ID [-c COMMIT]` | Validate and advance one phase. Code and docs need a unique pushed commit hash and a clean tree. The task finishes after its last phase. |
| `steer task mod ID FIELD VALUE` | Update `title`, `type`, or `scope`; set phases with `types TYPE ...` before progress. Use `status finished [COMMIT]` to advance, or `deets`, `links`, and `deps` to edit details and links. |
| `steer task unlink ID [TYPE] LINK` | Remove an inferred or explicit `msg`, `report`, or `task` link. |
| `steer task rm ID` | Remove a task. |
| `steer reports [-s] [-p PAGE]` | List reports, or stale reports with `-s`, 10 per page. |
| `steer report ID` | Show report fields and answers. |
| `steer report pub FILE -i ID -t TITLE [-u]` | Publish and verify a UTF-8 Markdown report. `-u` allows unparsed strike markers. |
| `steer report pin ID` or `steer report unpin ID` | Exclude a report from staleness, or restore normal expiry. |
| `steer report rm ID [ID ...]` | Dismiss one or more reports. Use `--stale` alone to remove stale reports. |
| `steer ren OLD NEW` | Rename a task or report and update its links. |
| `steer survey` | Show the survey and submission template. Use `-i` for the smallest image, `--template` for the template, or `-f FILE` for a submission. Submissions go to the running server when one is recorded. |
| `steer pr-update -n NUMBER -t TITLE -f FILE` | Reject session-local IDs, update a pull request through `gh api`, then verify its title and body. |
| `steer job-log -j JOB` or `steer job-log -r RUN` | Print one GitHub log URL for the agent to fetch. When no URL exists, print the log text and the reason. Supply exactly one ID. |
| `steer worktree add NAME [-b BRANCH]` | Add a native Git worktree under `.worktrees/`. |
| `steer worktree list`, `remove NAME`, `prune`, or `collect NAME` | List, remove, or prune worktrees, or print the patch a worktree carries against its merge base. |
| `steer run start [-t TASK] [-a NAME] NAME -- COMMAND` | Start a detached named run and optionally link it to a task. A dependency must exist and pass before its dependent starts. |
| `steer run logs NAME [-n LINES]` | Show run status and log tail. |
| `steer run pr-checks [-n NUMBER]` | Start a detached `gh pr checks --watch` run. |
| `steer skills` | List skill names, sources, paths, and descriptions. Installed copies win over repo copies. |

Use `python skills/arena-steering/scripts/steer` in place of `steer` in the table when the entry point is not on `PATH`. Message and answer IDs are six lowercase hexadecimal characters. Task and report IDs use lowercase kebab-case.

## Pre-command pipeline

`steer pre` runs the shell-hook pipeline from `arena_steering/pre.py`. Each check is a small class with `applies` and `run`. `PIPELINE` lists them in order, so adding, dropping, or reordering a check is a one-line edit there. A step returns `0` to continue, prints warnings, or returns a verdict: `2` ends the call clean and `130` blocks it.

```sh
_arena_preview_pre() {
  local reply
  reply="$(steer pre --shell "${0##*/}" --line "$_arena_preview_line" \
    --command "$BASH_COMMAND" --done "${_arena_preview_done:-}")"
  local status=$?
  while IFS= read -r step; do
    case "$step" in
      _arena_preview_done=*) eval "$step" ;;
      *) printf '%s\n' "$step" ;;
    esac
  done <<< "$reply"
  case $status in 2) exit 0 ;; 130) exit 130 ;; esac
}
trap '_arena_preview_pre' DEBUG
```

The steps, in order, are `sleep`, `inbox-pipe`, `poll-timeout`, `pr-state`, `push-refs`, `wireframe`, `gate`, `git-safe`, `bible`, `route`, `ack-quote`, and `bare`. The gate counts blocking messages, including hidden ones, and the newest unacknowledged answer per report. It blocks a `git push` at once and other work after six calls. Inbox-only reads, polls, and acknowledgements remain available, and the count resets only when no blocking work remains.

Arena-owned detached runs and exact platform utility calls do not spend the six-call budget. Ordinary Bash, mixed lines, and pushes remain guarded. The `BASH_COMMAND_POLICY` command-name-or-pattern map in `pre.py` sets `(count, block)` at the pending-inbox threshold. Immediate guards, including pending pushes, stay separate.

`bible` blocks `cat`, `grep`, `head`, `tail`, and `rg` on ARENA.md, AGENTS.md, and a skill SKILL.md. A passing step prints nothing and lands in `_arena_preview_done`, so a later command in one shell skips it. `install.sh` holds the profile block that installs the `steer pre` hook. The [notice inventory](references/notices.md) lists preflight violations, warnings, reminders, and removed legacy notices.

## Task and message contracts

- Task phases use ordered types (`report`, `code`, `docs`, `ops`, `misc`), with one type for existing single-phase tasks. Statuses are `upcoming` and `finished`.
- New tasks default to one `code` phase and `upcoming` status. Each finish request validates the current phase, advances it, and finishes the task after the last phase.
- A report phase needs a linked published report or received answer.
- Code and docs phases need a unique full commit hash and a clean Git tree. Missing remote comparison or local-only commits block completion.
- Ops and misc phases need no extra evidence.
- Unanswered linked questions block later phases, except the report that satisfied a completed report phase. Dependencies and running gates still block tasks.
- The first unblocked upcoming task is current. Legacy `in_progress` and `blocked` statuses become `upcoming` without reordering.
- New and updated tasks require at least one nonempty detail. Manually entered details have a 120-character limit.
- Existing empty tasks remain readable but need a detail on their next update.
- Dependencies must exist. Self-dependencies and cycles are rejected.
- The first acknowledgement of an answer appends missing `question label: submitted value` details to tasks linked at that time. Generated details have no length limit and remain editable after report removal.
- Repeated acknowledgements, links, and relinks do not add answer details. Later answers can add new details when first acknowledged.
- Acknowledgement output lists only details actually added to tasks.
- Existing task-answer snapshots are not migrated into task details.
- With one target, `-i ID -t TITLE -d DETAIL` commits a linked task and acknowledgement together. Repeat `-T` for ordered phases and use `-S` for scope.
- Multi-ID acknowledgement is atomic. A bad ID leaves every target unchanged.
- Removing a task removes its dependency links from other tasks.
- Task details are unique after trimming whitespace.
- Use `steer task mod ID deets TEXT` to append a detail and `steer task mod ID deets rm NUMBER` to remove one. The CLI displays detail numbers from 1.
- Use `steer task mod ID links [msg|report|task|gate] LINK` to add a link. Use `steer task mod ID links rm TYPE LINK` to remove one, or `steer task mod ID deps [rm] TASK` for dependencies.
- Message IDs use six lowercase hexadecimal characters. Legacy parent IDs name existing messages.
- Typed parent refs name existing messages, tasks, or reports. Both parent lists deduplicate in order.
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

Field options must be unique, with 1 to 20 options and at most 200 characters per option. Each answer is a typed hidden message in the shared message ID namespace. Reports show their answer history, and the inbox delivers an answer only if the latest submission to that report is unacknowledged. A newer answer makes earlier answers non-blocking.

Answer messages remain after report removal and reappear when that ID is republished. Answers embedded in older reports, archives, or snapshots are not migrated. Snapshot merges keep the row with the newer modification time, so a newer row can replace an acknowledgement with an older state.

### Report lifecycle

- Reports list by first publication time, then ID. Republish and rename keep that time, and state sync carries it.
- Existing saved reports retain their original fields. New and republished fielded reports require question and option comments.
- Code fences are not parsed as fields.
- Reports allow arbitrary HTML from trusted authors. Active HTML can access the viewer's origin and data.
- Do not open untrusted reports.
- `==text==` stays plain in reports. Use `<mark>` for highlights and fenced `diff` blocks for diffs.
- Publication rejects likely unparsed paired `~~` markers unless `-u` or `allow_unparsed_markers: true` is supplied. It verifies the saved report and rendered output.
- A verification failure does not guarantee rollback.
- Each submission must answer every field. Text and choice answers must be nonempty.
- Checkbox answers need at least one selected or custom value.
- A changed submission appends history, marks the report seen, and resets acknowledgement visibility. An identical latest submission creates no answer or agent inbox notification.
- An acknowledgement can be appended more than once, but only its first reply can add details to currently linked tasks.
- `seen` records report viewing, while `ack_seen` and `ack_seen_at` record when the user sees the latest acknowledgement. A new answer or another acknowledgement on the latest answer resets them.
- Republish and explicit-ID removal reject a report when its latest answer is unacknowledged. Republish preserves answer history.
- Multi-ID removal is atomic. A missing or protected report leaves every target in place.
- Explicit removal removes report links from tasks, while answer messages remain available for republishing.
- A report violation flag unpublishes its report without removing its links or answers, so waiting tasks unblock.
- CLI publication saves the source path for the flag message. Earlier or API-only reports may have no recorded path.
- An unlinked report becomes stale only 30 minutes after the user sees its latest acknowledgement. A linked report becomes stale as soon as all linked tasks finish.
- A pinned report is not stale. Pins survive server restarts, and unpinning restores the normal staleness rules.
- A visible report refreshes its view time every 30 seconds. A hidden browser tab does not refresh it.
- Stale removal can remove a report with an unacknowledged answer. The retained answer stays available in the inbox.

## State backup plan

The [backup and clear contract](../../docs/arena-steering/state-backup.md) describes planned userscript and container behavior. It is not implemented yet.

## HTTP and WebSocket

REST and static routes use the unprefixed paths below. The WebSocket endpoint is `/api/ws`. JSON routes return JSON. File uploads accept JSON or multipart form data.

Write requests may include `_request_id` to replay the original result safely. The server retains request records with its database.

| Routes | Purpose |
| --- | --- |
| `GET /health` | Server health, timezone, survey, and agent activity. |
| `GET, POST /messages` and `GET /messages/{id}` | List, create, and inspect messages. |
| `POST /messages/with-file` and `POST /uploads` | Create an attachment-bearing message or stage an upload. |
| `POST /messages/{id}/ack` | Acknowledge a message. |
| `GET /poll` and `POST /poll/skip` | Wait for work or request a skip. |
| `GET, POST /tasks` and `GET, PATCH, DELETE /tasks/{id}` | Manage tasks. |
| `GET, POST /reports` and `GET, PATCH, DELETE /reports/{id}` | List, publish, inspect, dismiss, pin, and unpin reports. |
| `POST /reports/{id}/seen` and `/reports/{id}/ack-seen` | Record owner visibility of a report and its acknowledgement. |
| `POST /reports/{id}/answers` and `/reports/{id}/answers/{answer_id}/ack` | Submit and acknowledge report answers. |
| `GET, POST /survey` and `POST /survey/interrupt` | Inspect or submit a survey and request a bible check. |
| `POST /timezone` and `POST /markdown` | Set the display timezone and render Markdown. |
| `GET /state/snapshot`, `GET /state/changes?since=`, and `POST /state/merge` | Export every row, export changed rows, and merge a document by ID. |
| `GET, POST /state/assets` | List upload paths with sizes and hashes, and store one asset by hash. |
| `/api/ws` | WebSocket requests, change notifications, heartbeat, reload, and `report.acked` events. |
| `/static/assets/`, `/static/reports/`, and `/static/uploads/` | Serve UI assets, report files and Markdown, and uploaded files. |

For state sync, treat `state_version` as an opaque cursor for one database. Pass the last returned value as `since` and replace it with the next response's value.

Older cursors can return a full snapshot once. State responses include a `deleted` map for `messages`, `tasks`, and `reports`, with `id` and `modified_at` per tombstone. Merges keep the later edit or deletion for each ID.

`GET /state/assets` lists only uploads referenced by surviving state rows, not staged files. A synced deletion removes a formerly referenced upload only if no surviving row references it. Keep never-referenced staged files local and transfer listed attachment bytes separately.

### API payloads and responses

Successful creates return HTTP 201. Other successful route operations return 200. Unknown routes or IDs return 404, unsupported methods return 405, and value-validation errors return 400 with an `error` string.

| Operation | Request or query | Response |
| --- | --- | --- |
| Mark message replies seen | `revision` is the rendered reply-list digest. | `message` and `matched`. Stale revisions return HTTP 409. |
| List messages | `all=1`, `hidden=1`, `before=ID`, and `q=TEXT` are optional. Pages contain at most 20 messages. | `messages`, `total`, and `has_more`. |
| Create message | `body`, optional `id`, `request_id`, `hidden`, `blocking`, `parent_ids`, `parent_refs`, and `attachments`. | `message`, including rendered body and acknowledgement HTML. |
| Upload | JSON `file` object with `name` and `content_base64` or `text`, or multipart `file`. | `attachment` with name, path, size, presence, and static URL. |
| Message with file | Message fields plus `file`, `attachments`, or `pasted_text`. | `message`. A long paste uses `pasted-text.txt`. |
| Acknowledge | `markdown` or `ack`. | `message` or `answer`, depending on the route. `task_details_added` appears only when an answer acknowledgement adds details. |
| List tasks | `full=0` excludes finished tasks. | `tasks`, each with derived `blocked` and `running_gate` booleans. Only an active linked run sets `running_gate`. |
| Create or patch task | `id`, `title`, single `type` or ordered `types`, `scope`, `details`, and link lists. PATCH accepts zero-based `position`, or `status: "finished"` to advance with `commit_hash` for code or docs. | `task` includes `type`, `types`, `current_phase`, `remaining_phases`, `phase_index`, and `phase_evidence`. Progress cannot be patched directly. |
| List reports | `stale=1` selects stale reports. `summary=1` omits report bodies. | `reports`. |
| Publish report | `id`, `title`, Markdown `body`, and optional boolean `allow_unparsed_markers`. | Verified `report`, including parsed fields and rendered blocks. |
| Patch report | `status` set to `dismissed`, or boolean `pinned`. | `report`. |
| Submit answers | `values` keyed by field ID, with an optional answer `id`. | `answer` and updated `report`. |
| Set timezone | `timezone`, an IANA zone such as `Asia/Manila`. | `timezone`. |
| Render Markdown | `markdown` and optional `breaks`. | Rendered `html` and `headings`. |
| Survey | POST accepts `answers` or a direct array or object. The interrupt accepts optional `active`. | `survey`. |

`parent_refs` takes objects with an `id` and a `type` of `message`, `task`, or `report`. The server checks that each target exists. Legacy `parent_ids` contains message IDs only, and child responses include both fields.

For example, send this JSON body to `POST /messages`:

```json
{"body":"Please review the report.","blocking":true,"parent_ids":[]}
```

For `POST /reports/example/answers`, a choice, checkbox, and text response can use this shape:

```json
{"values":{"storage-format":"SQLite","checks":["Unit tests"],"notes":"Ready"}}
```

The IDs and options must match the published report. A custom choice can use `{"selected":"Something else...","custom":"value"}`. A checkbox custom response can use `{"selected":["Unit tests"],"custom":"value"}`.

### WebSocket and survey details

WebSocket RPC requests carry an `id`, `method`, `path`, and JSON-encoded string `body`. Responses carry `type: response`, the same `id`, HTTP `status`, `contentType`, and a JSON-encoded string `body`. Supported methods are GET, POST, PATCH, and DELETE.

The server sends `change`, `reload`, `heartbeat`, and `report.acked` events. Respond to a heartbeat with `{"type":"pong"}`. Messages are limited to 16 MiB, and an idle connection closes after 35 seconds.

A survey takes a graded JSON array, a JSON array string, or a nonempty key-value object. Array submissions follow [`references/survey.json`](references/survey.json). Answers, graded results, and a check stamp live only in server memory, so a restart clears them.

`steer serve` writes its port to `server.json` inside a state directory, and the CLI posts submissions there. When no server answers, grading happens in that CLI process.

The server rejects paths that escape the relevant static directory. The v2 assets include Mermaid and its license.

## v1 and v2 parity

V1 is archived at [`arena-skill`](../../docs/archive/arena-skill/SKILL.md). V2 is this skill. This table describes the current repo implementations, not identical interfaces.

| Area | v1 | v2 | Parity |
| --- | --- | --- | --- |
| Start and configuration | `init`, `serve`, state directory, installed wrapper, and restore installer | `serve`, fixed `arena-state` directory, and browser timezone | No v2 `init --tz` or equivalent install and restore workflow. |
| Inbox | Read and poll, note history, quiet notes, seen receipts, and acknowledgement receipts | Read and poll, message history, hidden messages, non-blocking messages, and acknowledgement replies | Names and paging differ. |
| Message composer | Markdown preview, staging, paste, drop, expansion, reply links, search, and jumps | Preview, staging, paste, drop, expansion, multi-parent replies, search, and jumps | Parity for the paste thresholds, Ctrl+Shift+V bypass, IME guard, and touch Enter. V2 adds multi-parent replies. |
| Message extras | Slash commands, reference navigation, and persisted reply-seen counts | Reference navigation, multi-parent replies, and persisted boolean reply receipts | V2 omits slash commands and does not store or show unread-reply counts. |
| Tasks | Typed queue, status, details, report waits, dependencies, ordering, drag reorder, filters, and linked answers | Ordered phases with report or pushed-commit evidence, derived blocking, details, search, and filters | No drag reorder. First answer ack adds missing details. Linked task creation and acknowledgement are atomic. |
| Reports | Fielded Markdown, recommended choices, custom choices, locally saved drafts, submissions, and acknowledgements | Fielded reports, custom choices, history, acknowledgements, seen stamps, table of contents, and floating submit | V2 loses an unsent answer on a tab round trip. Both require acknowledgement only for the latest answer. |
| Report lifecycle | Stale listing, pin and unpin, state and visibility, guarded unpublish, and worker answer and forward | Stale listing and removal, pin and unpin, and viewed stamps | Worker answer and forward routes are absent. Guards and republish contract differ. |
| Report publication | Local image embedding, diff marker validation, optional submission format, and publication verification | Fielded Markdown, `-u` marker override, and saved/rendered verification | No automatic local-image embedding or v1 submission schema option. Likely unparsed paired `~~` markers fail by default. |
| Markdown and images | Markdown, code controls, Mermaid, images, and zoomable preview | Markdown, code copying, Mermaid, images, and a lightbox | V2 bundles Mermaid. Renderer compatibility needs verification. |
| State recovery | Import, compare, save, restore, clear, size status, clean, and userscript autosave | SQLite plus snapshot, changes, merge, deletion tombstones, and referenced-upload HTTP routes | No v1 import/clear CLI or userscript autosave. Transfer referenced attachment bytes separately. Never-referenced staged uploads do not sync. |
| Downloads | Browser download queue, approval for agent requests, retries, and optional proxy fallback | Upload staging and static attachment serving | V2 intentionally drops browser downloads and agent download requests. |
| Multi-session | Board, allowlist, main session, heartbeat, messages, attachments, and wake | Native Git worktrees | V2 intentionally drops the multi-session board. Worktrees do not replace coordination. |
| Runs | Detached named runs, dependency gating, task links, and later verdict notifications | Detached named runs, task links, logs, dependencies, and PR check watching | Both block linked tasks while a run is active. V2 does not provide later CLI verdict notices. |
| Worktrees | Tracked detached worktrees with gate and allowed-patch collection | Native Git add, list, remove, and prune under `.worktrees` | Different contract from gated patch collection. |
| Rename and unlink | Rename note, answer, task, or report. Unlink submissions from task answer lists | Rename task or report and unlink task links by ID and type | Note and answer rename and v1 submission-unlink semantics differ. |
| GitHub helpers | PR update with verification, and a job-log URL for the agent to fetch | PR update with verification, and job-log text via `gh` | Log return format differs. |
| Utilities and gate | `skills`, `agents`, `key`, `gate`, `outline`, and `image-data-uri` | `skills` listing and standalone `gate` checks | No `agents`, `key`, `outline`, or `image-data-uri` counterpart. |
| Live transport | WebSocket, heartbeat, and polling fallback | WebSocket, heartbeat, reconnect, polling fallback, and typed report acknowledgement events | V2 deduplicates browser writes and uploads by request ID. Other clients must supply an ID to get the same protection. |
| Survey and interrupt | Survey, image prompt, results, and bible check | Survey CLI, image prompt, results modal, and interrupt | Storage, timing, and schema behavior need a contract-level comparison. |
| Appearance and navigation | Theme control, tab state, mobile navigation, and pinch zoom | Responsive tabs and image viewer with touch pinch, wheel zoom, and drag | No v1 theme control. |
| Proxy and external channel | Separate egress proxy routes and an opt-in external-channel recipe | No egress proxy or external-channel recipe | Separate from the browser steering server. |

V2 rewrites CLI and state formats. Use isolated state, not a v1 database. See [v1 commands](../../docs/archive/arena-skill/references/commands.md), [v1 reports](../../docs/archive/arena-skill/references/reports.md), and v2 source/tests for edge cases.

## Implementation and verification

The [models](scripts/arena_steering/models.py) validate data. The [store](scripts/arena_steering/store.py) persists it, [services](scripts/arena_steering/services.py) implement behavior, and [server](scripts/arena_steering/server.py) exposes transport. The [browser assets](assets/) render messages, tasks, reports, and the survey. Tests live in [`tests/skills/arena-steering`](../../tests/skills/arena-steering/).
