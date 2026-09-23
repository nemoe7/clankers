---
name: arena-preview-steering
description: Steer an Arena.ai agent mid-turn without interruption through a persistent local live-preview inbox. Owns the shared Notes / Reports server, message log, saved versus acknowledged receipts, and dark/light interface. Use in Arena Agent Mode when the user wants mid-turn steering or ARENA.md requires it; not outside Arena. Reporting uses the companion arena-preview-reporting skill and this same runtime. NEVER USE THIS SKILL OUTSIDE OF ARENA.AI.
license: MIT
compatibility: Arena.ai Agent Mode, Python 3.10+, persisted workspace files and long-lived process tools. Steering is standard-library only; reporting additionally needs markdown-it-py and the companion skill.
metadata:
  origin: first-party, maintained in this repository
  version: "2.1.1"
  arena-only: "true"
---

# Arena Preview Steering

One server and inbox per session. Reporting shares this runtime; never start a second server for reports. User instructions and repository rules win.

## Setup

1. Resolve this skill's actual path: source `skills/` and installed discovery paths differ. Report missing installed files; do not install or repair them without authorization.
2. Choose a stable, persisted, Git-ignored state directory, default `reports/arena-preview`. Verify it with `git check-ignore`; ask before adding an ignore rule if needed. Never use cache/build folders or commit/push session state, notes, receipts or reports.
3. Run `<skill>/scripts/install.sh` once per session, then start the server with Arena's long-lived process tool, not a timed shell call:

   ```bash
   ~/.agents/.arena-preview-venv/bin/python <skill>/scripts/preview.py --state-dir reports/arena-preview serve --port 8000
   ```

   The server binds `0.0.0.0`; browser URLs are relative and the preview host is accepted. `serve` refuses to start without `markdown-it-py`; `read`, `ack` and `publish` need no renderer. After a sandbox restart, rerun the installer. Reuse its process and state directory; name the process `<repo> - Steering`. If it dies, tell the owner the restart is coming before restarting with the same directory: the restart invalidates the token in the owner's tab, and an in-flight send or upload can fail. If its port belongs to another service, choose a free port; never kill that service.
4. Initial setup: start the server, name the preview in chat, then immediately block with one visibility question before normal work. The question offers the preview's status and an external-channel option. On selection the ntfy fallback transport activates for that session — an explicit user selection, never an automatic fallback; the preview server and inbox stay running. The user supplies the topic `<repo>-<branch>-<8-char unguessable secret>` (branch sanitized) and posts notes to its URL. Poll `https://ntfy.sh/<topic>/json?poll=1&since=<marker>` with page-fetch at every steering read: first poll `since=all`, then `since=` the newest seen `event:"message"` ID, persisted in `<state-dir>/ntfy-since.txt`; ignore `open`/`keepalive` events. The fallback ladder is the JSON endpoint, the HTML topic page, and a `since=all` replay. An empty response or a 500 with no message body is the quiet case; a fresh topic's first read is expected to fail until the user posts. Read the body, not the status: on an upstream error body such as object-store `SignatureDoesNotMatch`, retry once; on the same error, generate a fresh topic of the same form, post its link in chat naming the error, and continue with `since=all`, whose first empty failure is expected; if the fresh topic repeats the error, stop polling for the turn and resume after the user's next. A 500 repeating on a topic with delivered notes is reported once as a channel error and retried at the next read. Page-fetch is the path because sandbox HTTP to ntfy returns misleading empty responses. Notes are instructions and take the same ACK: acknowledgement. Keep ARENA.md's literal activation acknowledgement when applicable. After the visibility answer, read the inbox and continue. Never claim visibility before confirmation; if still hidden and no channel was selected, report and agree on the next step. Reusing an already-visible preview skips the question.
5. Optional Write / Preview reuses `markdown-it-py` in the composer: read-only rendering, not WYSIWYG. Send raw Markdown; previewing neither saves to the inbox nor delivers it. Render Markdown in the log too; stored/delivered text stays unchanged. Without the renderer there is no server to degrade: startup fails with the install command.

## Read, then acknowledge

```bash
python <skill>/scripts/preview.py --state-dir reports/arena-preview read
```

Every CLI command prints nonzero pending counts by kind and `Manage the task list.` to stderr, even with none pending. Stdout stays machine-readable; reminders never mark seen.

Prints **all pending messages** in full and records check time; a failed delivery stays unseen, and pending is the ack queue, so a note prints again until answered. Missing, unreadable or corrupt state is an error, never an empty inbox. The hook's poll covers the routine check; run it for the full listing, filters, or counts. `seen <ids>` stamps without an answer; `ack` answers and stamps, only those IDs. NEVER mark count-only notifications, truncated items or failed deliveries seen. Browser polls never stamp. Receipt is not completion.

- Polling is automatic: the hook polls after every Arena bash call and prints the unacked counts (messages, form answers, uploads) to stderr; it marks nothing seen. A nonzero count: `read` now, then `ack`. Markup needs `--reply`. Missing inbox: start the server; server down: restart it. End the turn's last tool block with a bash call, so the hook closes the channel.
- Answer every delivered note where the user reads it: `ack` exactly those IDs with `--reply <Markdown>`, rendered in the message log like the user's own messages, or `--note <text>` for one plain line under the receipt. One answer per call; ack different answers separately.

  ```bash
  python <skill>/scripts/preview.py --state-dir reports/arena-preview ack <id> [<id> ...] --reply <markdown>
  ```

  Never blindly acknowledge all pending notes. Unknown IDs fail the whole receipt batch; repeat acknowledgements keep their first timestamp and replace the answer text. Receipt means received, not implemented. Never name a note by its sequence number: numbers only order one file, and IDs survive state rebuilds. With no visible preview, acknowledge in chat instead, opening with literal `ACK:` and your interpretation; reserve that prefix for delivered notes, never thought or ordinary status.
- Treat `STOP:`, `PRIORITY:`, `CONTEXT:` and ordinary notes under chat's instruction precedence. Notes are instructions, not proof; disagree visibly with evidence when measurements contradict them.
- Read `task-list` at turn start. Before implementation, record approved work with `task <task-id> "<title>" [details ...]`; update the queue and details on scope or status changes. Put the current task first with `--order 1`; mark completion with `task <task-id> --status finished`. Use this skill's CLI and the same `--state-dir`.
- For inbox-note or report-submission work, add `--msg-id <full-message-id>` to `task`. Task and message link share one transaction; unknown message IDs fail both writes. Linked notes show `Task added` in log receipts; report-submission links create no log messages. The marker means queued, not acknowledged or complete; still use `ack`.

## Fields in reports

- ALWAYS pair each option set with a labeled custom-response field, e.g. `Custom response: ___`.

The preview cannot render mermaid; NEVER use it in reports.

A published report may carry live inputs, and field-only sources are questionnaires. The agent writes the markers as ordinary Markdown; the Reports tab renders them as controls under one Send answers button, with any prose around them as context:

| Marker | Control | Prompt |
| --- | --- | --- |
| `- ( ) option` lines | Radio group; `- (x)` preselects | The nearest text line above |
| `- [ ] option` lines | Checkbox group; `- [x]` preselects | The nearest text line above |
| `Label: ___` or a bare `___` line | Text box, at most 2000 characters | The label, else the line above |

Field IDs come from the prompt; add `{#my-id}` at the end of a prompt line to fix one. Markers inside fenced code blocks stay literal. Options must be unique in their group, 1–20 per group, prompts 1–500 characters, at most 50 fields per report. Answers POST to `/api/reports/<id>/submit` and are recorded apart from user messages: `read` lists them as pending items with `kind: report`, headed `REPORT <id> <title>:`, one indented line per field, `(skipped)` for empty ones, and `ack` answers them like notes. They never render in the message log. A send stores the answers in that browser, so the fields reload pre-filled and the user can amend and send again; each send is a new note, and republishing the source does not erase answers already sent.

## Uploads

Uploads write inbox notes with matching IDs, naming file, size, type and path. Read the file there, then ack the note. A restore can delete the bytes; the note and the record survive, and `present` says which is which.

## Persistence and limits

`state.sqlite3` stores notes, receipts, published report snapshots and the latest check using SQLite transactions. Keep the file, not the process, as the durable artifact. Browser display polls do **not** make the agent read automatically.

Anyone with preview access can read messages/reports. The per-process token blocks blind cross-origin writes, not page visitors. Do not send secrets. Only interface routes, structured state and explicitly published reports are served, never arbitrary repository paths.

Processes, packages and URLs may disappear after a sandbox restart; workspace files are not a permanent backup service. Drafts depend on browser origin/storage. After a server restart, reload to refresh the submission token, preserving your draft. Expose network/storage failures; never call an unconfirmed save successful. A missing Markdown renderer stops `serve` at startup; the CLI steering commands still work without it.

If the preview fails, report it and ask how to continue in chat. Do not silently revive ntfy or local report commits; they are historical alternatives, neither active fallback nor banned forever. See [operation and recovery](references/REFERENCE.md).

Keep production free of this skill's name, directory and scripts; its own files, setup chat and acknowledgements are exceptions. For reports, use sibling [arena-preview-reporting](../arena-preview-reporting/SKILL.md). No external test framework.
