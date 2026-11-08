# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [2.2.3]

### Added

- Seed baseline prose under `skills/refs/arena-steering/` and add worked report-label examples in `references/report-labels.md`.

### Changed

- Rebind active WebSockets to the new app after Python hot reload and notify clients of state changes.

- Reuse a healthy Arena Steering server on port conflicts and leave unverified listeners untouched. Tell offline CLI users to run `steer serve`, except when they request `steer --version`.

- Require final-decision labels on report questions and options, forbidding question strings and placeholder labels.

- Decode child-process text pipes as strict UTF-8 and reconfigure CLI streams to UTF-8 on Windows.

- Align Steering modals, timestamps, edge fades, live dot, busy state, dark tooltips, and filter persistence with Nuu recipes.

- Grade survey fields with salted SHA-256 substrings, split `S2E5P` names, and simplify the survey modal.

- Parse inline code spans in report field questions and options, and align option inputs with line one.

- Retry failed browser write actions automatically three times with the same request ID, removing manual retry controls.

- Name unnamed and pasted composer uploads with epoch milliseconds and prepend `{messageID}-` on disk after send.

- Relocate task-linked files under `uploads/{taskID}/` and mark missing files `(lost)` dynamically.

- Set link color to `#299bff`, restore solid disc message markers, and lower the mobile `New reply` pill.

- Remove `855x325` from Nuu audit viewports and lock mobile orientation to portrait.

- Share parent-chip rendering, Lucide SVG icons, scroll-jump pills, and borderless button classes across Steering views.

- Remove default boxes on contained Steering buttons, gating interactive hover fills to fine pointers while keeping press fills.

- Load survey question text from `skills/arena-steering/references/survey-questions.txt` for shared consumption with Arena prompt fill.

- Move `README.md` to `docs/arena-steering/README.md` and rewrite it for human readers.

- Update the Messages unseen-reply indicator optimistically while receipts are pending, restore it on failure, and preserve newer acknowledgement revisions.

- Match Mermaid diagram appearance across thumbnails and the modal viewer, using the code-block surface in the modal.

- Enforce `{repo} - Steering` as the `start_process` name for `steer serve`.

- Require an explicit task size whenever task details are added or removed.

- Follow Steering's returned task order. Require `-z` and the 120-character cap for every task-detail change.

- Use `functions.fetch_page` instead of the GitHub job page for log retrieval. Try it before reporting failure, fetch later chunks from the same URL, and never commit, publish, or quote signed URLs.

- Suppress the mobile browser tap overlay across the v2 interface.

- Align desktop Reports sidebars with the top of the report content.

- Enlarge and inset the mobile Reports submit button, keeping it above the keyboard.

- Share ID chip styling and remove the composer Parents label.

## [2.2.2]

### Changed

- Require an atomic detail change when linking a new message to an existing task.

- Match report answer scroll fades to the report picker.

- Keep message paging consistent when search changes during an older request.

- Keep consecutive optimistic message lines in one paragraph.

- Require imperative wording for report options.

- Align the app shell with a panned mobile visual viewport while the keyboard is open.

- Show native file preparation as Edit activity.

- Cache hidden messages across visibility toggles.

- Highlight message bubbles with a subtle color transition.

- Keep Reports attention indicators inside the tab hover area.

- Use full questions and specific option labels in report fields.

- Preserve newer message acknowledgements when send confirmations arrive late.

- Match Reports header attention indicators to their picker sizes.

- Reject dependencies on lower-priority tasks while allowing larger dependencies.

- Store task creation times and raise queued task priority once after one hour.

- Use server-rendered Markdown for confirmed messages and reports, and retain optimistic message rendering.

- Format report answer history as message-style entries without an acknowledgement placeholder.

- Preserve selected parents and completed uploads across reloads, discarding unfinished uploads.

- Remove selected status, timestamp, modal-close, and scroll tooltips.

- Limit new task and report IDs to 64 characters and reject cross-type ID collisions.

- Keep message parent and task chips aligned at shared chip dimensions.

- Keep floating scroll and reply controls neutral and retain their shape on hover.

- Show timestamp tooltips in 24-hour time without receipt status.

- Render message receipt and time as one text element with a normal space.

- Reload browser assets after 10 seconds without changes, while keeping state updates live.

- Use 11 px task-chip text in Messages and Reports.

- Fade and slide tooltips from their triggers, respecting reduced motion.

- Retain visible message cards while the hidden-message filter reloads.

- Keep optimistic message cards connected when their server IDs arrive.

- Restore send-button hover feedback without changing its size.

- Preserve task-reference chip shape on hover.

- Add vertical spacing between wrapped message task chips.

- Show linked tasks in report headers and avoid duplicate titles in cached reports.

- Defer scheduled instruction checks while an agent poll is active.

- Use temporary textarea selection for all copy controls, including in embedded previews.

- Reuse bounded, content-keyed browser Markdown DOM during message and report updates.

- Keep pending message ID placeholders the same width as confirmed IDs.

- Prefer placing remaining tooltips above their targets when space allows.

- Remove tooltips from ID chips, attachment thumbnails, copy controls, and report dismissal.

- Truncate attachment filenames in the middle while retaining their extensions.

- Use smaller image thumbnails and matching file icons in Messages.

- Cache repeated server Markdown rendering with bounded memory.

- Cap expanding acknowledgements against the Messages log maximum.

- Highlight a task briefly when navigating to it from an ID chip.

- Keep each message receipt and timestamp on one bottom line.

- Show violation flag updates immediately, and restore the flag and draft after failures.

- Open Mermaid diagrams from clicks anywhere on their thumbnails.

- Show report dismissals immediately, and restore reports after failures.

- Show blocked Bash log dismissals immediately, and restore entries after failures.

- Hide the Reports loading bar when reduced motion is enabled.

- Pad the bottom of the full-height desktop report picker.

- Remove the misleading checkpoint label from non-blocking message receipts.

- Rename the CLI reference to `cli.md`.

- Show report answers immediately, preserve edits after failures, and reconcile retries by request ID.

- Open survey results immediately, and refresh them without reopening a closed dialog.

- Show poll-skip feedback immediately, and surface failures.

- Run scheduled bible checks every 10 minutes.

- Select reports immediately while their contents load, and restore the previous selection on failure.

- Show outgoing messages immediately, and preserve drafts and retry IDs after failed sends.

- Cache Mermaid diagrams in the browser and server, and fit thumbnails within their code-block footprint.

- Add `steer clear` to clear database state while preserving timezone, files, and survey memory.

- Match hover surfaces and tooltips to Arena while preserving status colors and keyboard access.

- Hide the composer scrollbar when the draft fits, and retain scrolling for long drafts.

- Replace browser-owned retry and navigation prompts with HTML dialogs.

- Add an on-demand Chromium installer that reports runtime paths.

- Protect a running Steering preview from unnecessary restarts.

- Preserve survey results and the open survey modal across hot reloads.

- Keep the Messages log at the bottom when content grows while pinned.

- Require a preselected option in every radio or checkbox report field.

- Send a hidden blocking survey request from Survey Again while preserving results.

- Make bare `steer survey` print the image question and path, and retire `-i`.

- Require graded JSON survey submissions and remove the ungraded results fallback.

- `SKILL.md`: Require semantic task, report, field, and gate IDs.

- `cli.py`: Show task-link hints after message acknowledgements and nonempty inbox reads.

- `pre.py`, `cli.py`, `install.sh`: Route safe mixed command lines while preserving connectors and exit status.

- `resume-turn.md`, `install.sh`: Remove redundant login-shell instructions.

- `SKILL.md`: Publish handoffs and cross-session specifications as unfielded Steering reports.

- `markdown.py`, `services.py`, `test_server_cli.py`: Render standalone two-space-indented blocks as code and preserve acknowledgement indentation.

- Default report-only tasks to P3 and all other new tasks to P4, and document these defaults in the CLI reference. Preserve explicit and existing priorities, including when linking attachments.

- `pre.py`, `test_pre.py`: Exempt selected Steering commands from the pending-inbox count and gate, or from the count only.

- `test_reports_nuu_flows.py`: Move Reports audit fixtures out of the skill references.

- `SKILL.md`: Document ordered task phases, completion evidence, and phase blocking.

- `references/recipes/resume-turn.md`, `SKILL.md`: Rename the turn-start recipe and update its link.

- `SKILL.md`: Require specific labels for report fields and answer options.

- `SKILL.md`: Estimate task sizes relative to a reference using effort, complexity, and uncertainty.

- `references/recipes/turn-start.md`: Name every Steering preview after its checkout directory.

- `SKILL.md`: Require full reads of image and text attachments before acknowledging their notes.

- `pre.py`, `services.py`, `server.py`, `assets/messages-view.js`: Show native `Read`, `Edit`, `Write`, and `Bash` cadence in Messages. Use Nuu compact seconds timestamps, preserve v1 metadata, ignore platform and inbox-recovery steps, and show only nonzero Bash counts.

- `SKILL.md`: Use self-identifying field labels so acknowledgements linked to tasks produce meaningful details without reopening the report.

### Removed

- `references/notices.md`: Remove the notice inventory and its README link.

### Fixed

- `style.css`, `messages-view.js`, `test_message_bubble_layout.py`: Narrow acknowledgement-driven message bubbles while preserving body-driven expansion.

- `pre.py`, `test_pre.py`: Exempt validated native process-launch wrappers from the Bash count and gate.

- `pre.py`, `test_pre.py`: Exempt exact native process-output scripts from the Bash count and gate.

- `pre.py`, `test_pre.py`: Exempt exact native stop scripts for any valid process name from the Bash count and gate.

- `cli.py`, `scripts/install.sh`, `test_pre.py`: Count each completed outer Bash shell once at `post-exit`, including mixed lines, while skipping routed children, platform steps, and inbox recovery. Preserve user `EXIT` traps and accept the managed `DEBUG` replay.

- `pre.py`: Allow quoted multiline ACK text and an initial ACK step in mixed shell lines. Recheck pending blockers before later commands without changing Bash counts or push guards.

- `pre.py`, `test_pre.py`: Normalize pinned process-probe stderr redirects, accept native read `None` ranges and direct-child checkout checks, and recognize exact snapshot and remote-health shells. Keep altered templates and later commands gated.

## [2.2.1]

### Added

- `references/nuu/reports-*.json`, `test_reports_nuu_flows.py`: Audit empty Reports and a fielded report at the top and after scrolling, across the required viewports and both motion preferences. Capture screenshots without editing or submitting answers.

- `references/cli.md`: Document direct agent CLI commands, outputs, exits, and task phases in one guide.

- `server.py`, `assets/messages-view.js`, `assets/app.js`, `assets/style.css`: Expose served image URLs, render message thumbnails, and open them in the existing viewer. Leave missing and nonimage files as labels.

- `models.py`, `services.py`, `store.py`, `server.py`, `cli.py`: Store typed message, task, and report parents on child messages. Keep legacy message parent IDs and show all parent types on child reads.

- `models.py`, `services.py`, `store.py`, `cli.py`, `server.py`, `assets/tasks-view.js`: Require Fibonacci sizes and rank upcoming tasks by priority, size, and insertion order. Keep dependencies ahead, preserve finished history, show rank fields only in details, and reject manual position edits.

- `blocked_bash.py`, `cli.py`, `scripts/install.sh`: Append unredacted blocked Bash calls to permission-restricted local JSONL, including failed hook pushes.

- `blocked_bash.py`, `server.py`, `assets/`: Show full blocked Bash entries in a local modal beside the violation flag. Render each field as text and exclude the log from state sync and reports.

- `blocked_bash.py`, `server.py`, `assets/`: Dismiss one local audit row at a time with locked, atomic JSONL replacement. Keep the remaining entries private and intact.

### Changed

- `cli.py`, `models.py`, `services.py`, `store.py`, `server.py`: Default tasks to P4 and promote linked attachments to P3. Add home-relative path details while retaining explicit priority overrides.

- `SKILL.md`: Read attached images before acknowledgment, report missing bytes, and limit complete text reads to 4 KiB.

- `SKILL.md`: Omit the task-priority flag unless the user states a priority.

- `models.py`, `store.py`, `services.py`: Lock report body changes after the first answer. Explicit removal detaches task links and orphans old answers, including pending ones.

- `store.py`, `services.py`: Start same-ID republication without inherited answers, and keep orphan acknowledgements from modifying new tasks.

- `services.py`: Detach task report links on a violation flag while keeping its dismissed report and answer-derived task details.

- `cli.py`: Limit task lists to IDs and titles while single-task inspection keeps scope, links, and details.

- `assets/messages-view.js`, `assets/style.css`: Right-align content-width bubbles, put attachments above the ID, and show parent chips beside it.

- `assets/messages-view.js`, `assets/style.css`: Show Sent or Seen before the stamp without a status dot. Keep acknowledged status screen-reader-only.

### Fixed

- `pre.py`, `test_pre.py`: Accept a spaced `> /dev/null` current step for the pinned Arena process probe. Keep altered scripts and later shell commands gated.

- `assets/reports-view.js`, `test_report_controls.py`: Keep the Reports picker mounted across selections without replaying panel entry. Reset report-bound form and acknowledgement scroll state.

- `assets/app.js`, `assets/style.css`, `test_report_controls.py`: Hide the Reports main-panel bottom fade while a mobile keyboard shrinks the visual viewport. Restore the fade on close without changing desktop, reduced motion, or Submit controls.

- `assets/messages-view.js`, `assets/style.css`, `test_message_bubble_layout.py`: Place one-line message text at the bubble's right inset. Keep wrapped and explicitly multiline text at the left inset, and reserve a narrow gutter beside wide bubbles.

- `pre.py`, `cli.py`, `test_pre.py`: Exempt exact native file-tool and Arena probe steps from the inbox Bash count. Count and gate later commands in mixed shells.

- `assets/style.css`: Extend the Reports fade behind Submit to the viewport bottom while preserving last-line clearance. Keep a separate dock in reduced motion and match Scroll to Top with Messages.

- `assets/messages-view.js`, `assets/style.css`: Let replies fill message-driven bubbles and cap only reply-driven expansion at two-thirds of the row.

- `assets/style.css`, `test_message_bubble_layout.py`: Remove trailing paragraph margin from the final acknowledgement. Preserve spacing between earlier replies.

- `assets/style.css`: Align parent chips, message IDs, and receipt contents with the bubble text's right inset.

- `assets/style.css`, `test_web_ui.py`: Match mobile and desktop header tab widths. Keep both Reports markers above the mobile label without crowding header actions.

- `assets/style.css`, `test_web_ui.py`: Keep the Tasks toolbar on one row across viewports. Preserve search and filter focus order.

- `assets/style.css`, `test_web_ui.py`: Anchor the Tasks top fade below its sticky toolbar after scrolling. Keep it absent at rest.

- `assets/style.css`, `test_web_ui.py`: Fade report-table edges only while more columns remain past that edge. Keep native scrolling.

- `assets/style.css`, `test_web_ui.py`: Restore a smaller shared top gap below the header in all tabs while removing the Tasks-only fade gap. Retain inline and bottom spacing.

- `assets/style.css`, `test_web_ui.py`: Fade the Reports top edge over 36 px of scroll. Leave empty and at-top views clear.

- `assets/style.css`: Match the custom Reports answer's left padding to standard answers while keeping the radio layout and input height.

- `pre.py`: Guard partial reads of any `AGENTS.md`, root `ARENA.md`, and the installed steering skill. Permit searches of the checked-in skill source and nested `ARENA.md` files.

- `assets/` and `test_web_ui.py`: Select typed parents from message IDs, task titles, and report IDs. Focus the composer after task and report selection, show IDs only in UI chips, navigate from sent-message chips, and leave ID-like Markdown as plain text.

- `cli.py`, `server.py`, `.agents/skills/arena-steering/SKILL.md`: Point v2 bible reminders and read sets to its future installed skill path. The repo-only stub directs readers to the checked-in v2 skill without releasing it.

- `server.py`, `assets/tasks-view.js`, `assets/style.css`: Show a blue task-title shimmer only for an active linked gate. Keep report blockers and finished gates static.

- `assets/style.css`: Let Reports prose use the full content width rather than stop at 72ch. Keep tables scrollable.

- `assets/style.css`: Keep the first-line composer hint on one visual line without an edge fade, while draft text still wraps.

- `pre.py`: Exempt the pinned isolated reader when the full script and hook command match, with only a canonical JSON path and positive range. Keep altered Python and shell chains gated.

- `cli.py`: List every stored parent ID when `steer read` or `steer msg ID` displays a child message. Do not embed parent text.

- `pre.py`: Exempt only the complete checkout-directory validator after confirming each path stays inside the checkout through symlinks. Reject altered tests and added commands.

- `pre.py`: Exempt a pinned platform stop script with one eight-hex process name from the sleep guard and inbox count. Keep changed scripts blocked.

- `pre.py`: Accept only a literal login-shell PATH prefix before one quoted `steer ack`. Reject changed assignments, pipes, and extra commands.

- `pre.py`: Exempt literal single-quoted `mkdir -p` paths paired with profile sourcing in the observed login shell. Reject broken quotes, changed options, and extra commands.

- `git_safety.py`, `pre.py`, `cli.py`: Point blocked commits to `steer ren` only for task or report name collisions. Keep real citations blocked, and distinguish them from matching source text.

- `markdown.py`, `server.py`, `assets/api.js`, `assets/app.js`: Show one visual break per source line in Messages and its draft preview. Keep Reports Markdown unchanged.

- `assets/style.css`: Keep Reports markers clear of the label when the Bash log button shares a narrow header.

- `pre.py`, `scripts/install.sh`: Register DEBUG after login setup and keep approved utility shells unblocked during EXIT cleanup. Recheck pending pushes.

- `scripts/install.sh`, `test_pre.py`: Remove the managed EXIT hook and migrate existing profiles while preserving user traps. Prevent managed EXIT replay from duplicating the final visible Bash command.

- `server.py`, `test_web_ui.py`: Reload changed Python modules after 10 quiet seconds. Keep the last-good handler when a reload fails.

## [2.2.0]

### Added

- `scripts/install.sh`: Enable the Bash gate in login shells, preserve a prior DEBUG trap, and keep installation idempotent.

- `models.py`, `services.py`, `store.py`, `server.py`: Persist hidden blocking violation flags with a reason, an optional clause file, and tab context. Validate input and track acknowledgements.

- `assets/`: Show tab-specific violation forms, a pending indicator, cancellation, and retry feedback.

- `models.py`, `store.py`, `services.py`, `cli.py`, `server.py`, `assets/`: Store ordered task phases, validate report or unique pushed commit evidence before advancing, and show phase progress.

- `git_safety.py`, `services.py`, `cli.py`, `server.py`: Refuse dirty-tree completion for every task phase and persist one hidden blocking violation across CLI and browser writes.

- `services.py`, `cli.py`: Flag rapid repeated agent polls once, with worktree guidance. Keep browser polling exempt.

- `pre.py`, `services.py`, `cli.py`: Raise one blocking flag when the six-call pending-inbox gate stops Bash. Keep early reminders flag-free.

- `pre.py`, `cli.py`: Flag blocked inbox pipes, sleeps, and commit-content checks separately. Keep each flag pending until acknowledged.

- `pre.py`, `cli.py`: Store command-pattern count and threshold-block policy as editable boolean pairs while keeping immediate guards separate.

- `SKILL.md`: Check related upcoming task titles and scopes before publishing a report.

- `server.py`, `services.py`, `store.py`: Unpublish flagged reports while keeping task links and answers. Store CLI report source paths for the flag note.

- `store.py`, `server.py`: Export and merge deletion tombstones for messages, tasks, and reports. Keep the later edit or deletion for each ID.

### Changed

- `scripts/install.sh`: Initialize the default SQLite store during installation so pre-command gates work immediately. Keep existing store data on reinstall.

- `assets/style.css`: Apply the approved thin, flat scrollbar style in Chromium and other browsers. Remove redundant hover rules.

- `server.py`: Keep unprefixed REST and static paths plus `/api/ws` as canonical. Remove `/api/` REST and static aliases and the `/ws` WebSocket alias.

- `assets/references.js`: Link complete backticked IDs in messages, reports, and task details without linking plain text.

- `assets/references.js`, `assets/messages-view.js`: Put linked IDs inside code elements, including task receipts and reply-parent chips.

- `assets/style.css`: Restore the earlier blue for message links while keeping code-chip text contrast above 4.5:1.

- `assets/reports-view.js`, `assets/style.css`: Retain the Reports picker position across report changes and fade its scrollable edges on desktop and mobile.

- `assets/style.css`: Give Markdown tables in Messages and Reports GitHub-style borders and stripes with existing theme colors.

- `assets/style.css`: Let cells wrap at spaces while keeping wide tables scrollable within their views.

- `assets/messages-view.js`: Keep Messages at the bottom when new content arrives there, without moving readers who scrolled up.

- `pre.py`: Scope the governing-skill read guard to the v2 skill. Keep root governing files protected.

- `cli.py`: Count unacknowledged violations separately from notes and answers in shell reminders.

- `models.py`, `services.py`, `store.py`: Order reports by first-publication time and ID. Keep that stamp through republish, rename, and state sync.

- `assets/app.js`, `server.py`, `scripts/install.sh`: Refresh the validated IANA zone on page load. The installed Bash gate sets `TZ` only when unset.

- `cli.py`, `pre.py`: Resolve state from the installed checkout rather than the current directory. Warn on unreadable state, but refuse pushes.

- `README.md`: Correct state path wording to checkout root, not working directory, and list pre-command steps in registry order.

- `assets/app.js`: Keep survey rechecks separate from the violation button.

- `store.py`: Order messages and pages by write time and ID. Keep old insertion order when replacing legacy sequences, and retain write times across state sync.

- `server.py`: List only uploads referenced by surviving state. After an accepted synced deletion, remove orphaned files with no surviving references, and retain staged files that were never referenced.

### Fixed

- `pre.py`, `cli.py`, `scripts/install.sh`: Avoid a second inbox check during shell exit for a standalone push admitted before a note arrived. Keep mixed pushes guarded and refresh the managed gate in existing profiles.

- `pre.py`: Exempt exact Arena process and port probes from inbox blocking and call counts. Recognize standalone `ss` and `netstat` with any flags while keeping altered mixed lines guarded.

- `pre.py`: Let standalone mkdir calls pass the pending-inbox gate and still count. Keep mixed lines guarded.

- `pre.py`: Distinguish remote Git pushes from local stash pushes in guards and post-push checks.

- `pre.py`: Hide pending IDs in six-call Bash blocks while keeping the read and acknowledgment recovery steps.

- `assets/`: Fill the Reports sidebar with the picker until answers appear, then give the picker and acknowledgements separate scrolling areas with edge fades.

- `pre.py`: Check each Bash command before blocking partial instruction reads. Filename-only inventories no longer trigger the read guard.

- `pre.py`, `cli.py`: Exempt marked detached runs and exact Arena maintenance calls from inbox cadence while keeping pushes guarded.

- `markdown.py`, `assets/markdown.js`, `assets/style.css`: Name checklist inputs, raise message reference contrast, and fit report images to their panel.

- `store.py`: Replace stale row-change triggers when an existing v2 database already has the tombstone column.

- `assets/style.css`: Keep survey tooltips within the dialog and footer actions visible in short viewports.

- `assets/dom.js`, `assets/index.html`, `assets/messages-view.js`, `assets/tasks-view.js`, `assets/reports-view.js`: Preserve live controls and focus through state updates.

- `assets/messages-view.js`: Focus the cleared composer after Send.

## [2.1.0]

### Removed

- `cli.py`: Drop the survey interrupt flag. Bible checks are blocking messages.

- `cli.py`: Drop the unused JSON option from `steer skills`.

- `scripts/hooks`: Drop the hook wrapper, because the trap line calls `steer gate` alone.

- `cli.py`, `models.py`: Drop task-answer snapshots and answer unlinking.

### Added

- `scripts/arena_steering/server.py`: Serve state snapshot, change, merge, and asset routes for an external container.
- `scripts/arena_steering/store.py`: Export, stamp, and merge stored rows.
- `scripts/arena_steering/cli.py`: Print a one-line restore notice when a merge changed state.
- `scripts/arena_steering/cli.py`: Register `steer gate` and `steer skills`.
- `scripts/arena_steering/cli.py`: Add the `gate` trap target, with no wrapper script.
- `scripts/arena_steering/cli.py`: Add `worktree collect` to print a worktree patch against its merge base.
- `assets/app.js`: Pinch the image viewer with two pointers.
- `scripts/arena_steering/server.py`: Stamp finished runs into `data_version` so clients refresh on completion.
- `scripts/arena_steering/cli.py`: Record the listening port in `server.json` while `steer serve` runs.
- `assets/markdown.js`: Nest list items and render horizontal rules.
- `assets/style.css`: Indent task items by 2ch and style horizontal rules.

- `state-backup.md`: Document the planned v2 backup and clear contract.

- `cli.py`, `services.py`: Pin or unpin reports to control stale removal.

- `cli.py`: Acknowledge multiple message and report-answer IDs atomically with one reply.

- `cli.py`: Remove multiple reports atomically in one command.

- `scripts/install.sh`: Put `steer` on PATH with its Python dependency.

- `pre.py`: Block `cat`, `grep`, `head`, `tail`, and `rg` on the bible, because those commands read a file in part.

- `pre.py`, `cli.py`: Run the shell hook through a step registry. Each check is its own class, and `PIPELINE` orders them, so a check can be added, dropped, or tweaked in one line.

- `services.py`: List pending message and answer IDs without marking them seen.

- `assets/app.js`: Filter loaded messages in the browser after the first search query.

### Changed

- `store.py`, `server.py`: Refresh connected browsers after writes from another process.

- `assets/`, `services.py`, `server.py`, `cli.py`: Show connection and agent activity states. Wake a poll for work or a skip from another process.

- `services.py`, `cli.py`, `server.py`: Add answer details only on the first acknowledgement, and report actual additions. Ignore identical latest submissions.

- `assets/`: Show independent needs-answer and unread markers. A lone question marker uses the default dot position, and unseen acknowledgements get marks on the tab and picker.
- `assets/`: Keep newer report content when delayed responses arrive, preserving focused drafts during view-only refreshes.
- `server.py`, `demo-arena-steer.py`: Preserve the demo reset action and survey state across hot reloads.

- `models.py`, `services.py`, `store.py`: Keep task details unique across edits, answer copies, and sync.

- `services.py`: Start unlinked report staleness when the user sees an acknowledgement.

- `pre.py`, `services.py`: Count blocking inbox work and retain the gate count until it clears.

- `cli.py`: Show the current task with `steer task`, and its details with `-d` or `--deets`.

- `cli.py`: Use `state.sqlite3` for normal v2 state. The demo keeps a separate database.

- `cli.py`: Block session-local IDs in PR updates and use the GitHub REST API.

- `assets/`: Match the v1 composer layout, draft preview, paste, uploads, and controls while retaining v2 retry and reply features.

- `cli.py`: Rename the `rename` command to `ren`.
- `assets/app.js`, `assets/messages-view.js`: Keep older-message errors visible through refreshes until the user retries.

- `models.py`, `store.py`, `assets/tasks-view.js`: Keep upcoming and finished task statuses, and show the first unblocked upcoming task as current.

- `models.py`, `services.py`, `store.py`, `assets/app.js`: Track report activity and task links for staleness, and retain pending answers on stale removal.

- `models.py`, `services.py`, `store.py`: Store report answers as durable hidden messages and derive report history from them.

- `server.py`: Render all acknowledgement replies in report views.

- `services.py`, `models.py`: Derive task blocking and append full report-answer details on submission and when reports are newly linked.

- `cli.py`: Bind `steer serve` to `0.0.0.0:8000` without a port option.

- `maintenance/demo-arena-steer.py`: Move the configurable demo out of the shipped skill.

- `assets/reports-view.js`: Render the stored answer as the selected option, and keep the star as a recommendation mark only.

- `assets/reports-view.js`: Prefill a published report with its stored answer and mark a recommended option with `*`.
- `assets/reports-view.js`: Keep an unsent answer per field in `localStorage` and clear it after submit.
- `assets/app.js`: Drop the three-second task refresh, because finished runs now push a change event.

- `scripts/arena_steering/services.py`: Keep survey answers, results, and the check stamp in memory instead of SQLite.

- `scripts/arena_steering/cli.py`: Post survey answers to the running server recorded in `server.json`.

- `assets/app.js`: Pan the image viewer without a native image drag and close it from the backdrop.

- `assets/app.js`: Keep diagram colors and scale in the image viewer.

- `assets/style.css`: Clear the image viewer close-button background and lighten its scrim.

- `assets/messages-view.js`: Use the current Lucide paperclip path for the attach button.

- `assets/style.css`: Fade the report and task columns only, leaving sidebars unblurred, and give the task toolbar its own edge fade.

- `assets/messages-view.js`, `assets/style.css`: Match the v1 composer layout, icon buttons, and text size.

### Fixed

- `assets/style.css`, `markdown.py`, `assets/markdown.js`: Align checklist markers and wrapped text within the 2ch list indent.

- `cli.py`: Show task, report, run, and worktree command-group help without opening state.

- `store.py`, `server.py`: Keep state changes and their cursors consistent for same-second writes and clock skew.

- `assets/style.css`: Keep report headings below the edge fade after a table-of-contents jump.

- `assets/app.js`, `assets/messages-view.js`: Keep scrolling active while older messages load, even during a refresh.

- `assets/style.css`: Keep the Tasks toolbar divider visible below the edge fade.

- `assets/messages-view.js`, `assets/style.css`: Show an instant scroll-edge fade for reduced motion and keep boundary messages visible.

- `assets/style.css`: Inset the scrollbar thumb by 2px inside a 10px track and color links blue.

- `assets/style.css`: Dim the page behind the image viewer with a translucent backdrop.

- `assets/messages-view.js`: Fetch the older message page before scrolling reaches the top.

## [2.0.0]

### Added

- `store.py`, `assets/`: Search message history in SQLite and page browser results.

- `api.js`, `server.py`, `store.py`: Deduplicate browser writes and uploads across retries.

- `cli.py`, `services.py`: Block linked tasks while named runs are active.

- `models.py`: Preserve distinct report-answer snapshots on linked tasks.

- `app.js`: Preload report content on pointer or keyboard intent.

- `references.js`: Navigate known message, report, and task references.

- `store.py`: Deduplicate message retries by client request ID.

- `composer-uploads.js`: Show upload progress and recover from failed uploads.

- `store.py`: Persist reply-seen flags with atomic revision checks.

- `assets/messages-view.js`: Preserve unsent composer text in browser session storage.

- `services.py`: Require at least one detail for new and updated tasks.

- `assets/messages-view.js`: Leave Enter to the textarea on coarse-pointer devices.

- `assets/style.css`: Use the existing positive token for success icons.

- `assets/messages-view.js`: Ignore Enter during active text composition.

- `scripts/arena_steering/store.py`: Retry transient SQLite lock errors during concurrent WAL initialization.

- `skills/arena-steering/README.md`: Document the message retry duplication risk found during the parity audit.

- `assets/messages-view.js` and `scripts/arena_steering/server.py`: Match v1 paste thresholds and support Ctrl+Shift+V plain-text bypass.

- `scripts/arena_steering/cli.py`: Fix state under `arena-state` and use a separate v2 database filename while v1 remains active. Keep demo state in `arena-state/demo/`.

- `skills/arena-steering/README.md`: Document v2 features, commands, routes, and current limits. Expand interface and lifecycle contracts, and align the v1/v2 parity matrix with the feature inventory.
- `scripts/arena_steering/` and `scripts/steer`: Add the `arena-steering` skill and `steer` CLI with domain models, SQLite storage, server-cached Markdown forms, SHA-256 survey grading, and HTTP/WebSocket routes.
- `assets/`, `references/survey.json`, and `scripts/demo.py`: Add ES module web UI for Inbox, Tasks, Reports, and Survey with PrismJS, Mermaid, Arena tokens, `Basel_Grotesk` fonts, and `demo.py`.
- `scripts/arena_steering/server.py` and `assets/`: Push `report.acked` over `/api/ws` to update an open report in place, and mark `ack_seen` when the owner views it.
- `assets/reports-view.js` and `assets/style.css`: Pair fielded reports' bottom submit spacer with a fixed `#report-submit-float` that stays reachable while scrolling.
- `scripts/arena_steering/` and `assets/`: Store `parent_ids[]` on messages, toggle composer reply parents from receipt IDs, copy IDs on Shift+Click, and render clickable `↪ <id>` parent chips.
- `scripts/arena_steering/server.py` and `assets/`: Serve nested UI assets, report files and raw Markdown, and uploads under `/static/assets/`, `/static/reports/`, and `/static/uploads/`.
- `scripts/arena_steering/server.py`: Add JSON and multipart `POST /api/uploads` and `POST /api/messages/with-file`. Store uploads under `/static/uploads/` and convert long pasted text into a `.txt` attachment.
- `scripts/arena_steering/`, `assets/api.js`, and `assets/app.js`: Add `steer ren`, `steer task unlink`, `steer pr-update`, and `steer job-log`, plus browser `POST /api/timezone` instead of `init --tz`.
- `assets/`: Stage full-page file drops, `#attach-file` picks, and long pastes as removable chips in `#composer-attachments`, with `#composer-expand` for a taller composer.
- `scripts/arena_steering/cli.py`: Add native `git worktree` lifecycle commands under `.worktrees/`, detached `steer run start` with `--after` chaining and `steer run logs`, plus a `steer run pr-checks` watcher.
- `assets/messages-view.js`: Fix message rendering when a task links to a message.
- `assets/`: Open message and report images and Mermaid diagrams in a zoomable, pannable lightbox.

### Changed

- Reports use embedded question and option labels, trusted HTML, strike-marker checks, and post-save verification.

- `assets/`: Bundle Mermaid and its license without a v1 asset dependency.

- `steer msg list` defaults to 5 items and accepts page sizes from 5 to 50.

- `steer msg ID` inspects a message without a `show` subcommand.

### Fixed

- `README.md`: Mark local image embedding as intentionally dropped.

- `README.md`: Record intentionally dropped v1 features.

- `README.md`: Correct the comparison of report-answer acknowledgement.

- `server.py`: Return report-answer acknowledgements from the message route.

- `cli.py`: Create acknowledgement tasks and replies in one transaction.

- `assets/markdown.js` and `scripts/demo.py`: Use warm Arena colors for the Mermaid theme and the demo PNG, GIF, and SVG files.
