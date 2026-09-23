---
name: arena-preview-steering
description: Steer an Arena.ai agent mid-turn without interruption through a persistent local live-preview inbox. Owns the shared Notes / Reports server, message log, saved versus acknowledged receipts, dark/light interface and rendered Markdown reports. Use in Arena Agent Mode when the user wants mid-turn steering, a rendered report or ARENA.md requires it; not outside Arena. NEVER USE THIS SKILL OUTSIDE OF ARENA.AI.
license: MIT
compatibility: Arena.ai Agent Mode, Python 3.10+, persisted workspace files and long-lived process tools. CLI steering commands are standard-library only; `serve` and rendered reports additionally need markdown-it-py.
metadata:
  origin: first-party, maintained in this repository
  version: "3.0.0"
  arena-only: "true"
---

# Arena Preview Steering

One server and inbox per session for steering messages and reports; never start a second server.

## Setup

1. Resolve this skill's actual path: source `skills/` and installed discovery paths differ. Report missing installed files; do not install or repair them without authorization.
2. Choose a stable, persisted, Git-ignored state directory, default `reports/arena-preview`. Verify it with `git check-ignore`; ask before adding an ignore rule if needed. Never use cache/build folders or commit/push session state, notes, receipts or reports.
3. Run `<skill>/scripts/install.sh` once per session, then start the server with Arena's long-lived process tool, not a timed shell call:

   ```bash
   ~/.agents/.arena-preview-venv/bin/python <skill>/scripts/preview.py --state-dir reports/arena-preview serve --port 8000
   ```

   The server binds `0.0.0.0`; browser URLs are relative and the preview host is accepted. `serve` refuses to start without `markdown-it-py`; `read`, `ack` and `publish` need no renderer. After a sandbox restart, rerun the installer. Reuse its process and state directory; name the process `<repo> - Steering`. If it dies, tell the owner the restart is coming before restarting with the same directory: the restart invalidates the token in the owner's tab, and an in-flight send or upload can fail. If its port belongs to another service, choose a free port; never kill that service.
4. Initial setup: start the server, name the preview in chat, then immediately block with one visibility question before normal work. The question offers the preview's status and an external-channel option. On selection the ntfy fallback transport activates for that session — an explicit user selection, never an automatic fallback; the preview server and inbox stay running. The user supplies the topic `<repo>-<branch>-<8-char unguessable secret>` (branch sanitized) and posts notes to its URL; see [the external-channel procedure](references/REFERENCE.md) for polling, markers and error handling. Notes are instructions and take the same ACK: acknowledgement. Keep ARENA.md's literal activation acknowledgement when applicable. After the visibility answer, read the inbox and continue. Never claim visibility before confirmation; if still hidden and no channel was selected, report and agree on the next step. Reusing an already-visible preview skips the question.

## Read, then acknowledge

```bash
python <skill>/scripts/preview.py --state-dir reports/arena-preview read
```

Every CLI command prints nonzero pending counts by kind, `DO NOT IGNORE. ACK ASAP.` when any are pending, and `Manage the task list.` to stderr, even with none pending. Stdout stays machine-readable; reminders never mark seen.

Prints **all pending messages** in full and records check time; a failed delivery stays unseen, and pending is the ack queue, so a note prints again until answered. Missing, unreadable or corrupt state is an error, never an empty inbox. The hook's poll covers the routine check; run it for the full listing. `seen <ids>` stamps without an answer; `ack` answers and stamps, only those IDs. NEVER mark count-only notifications, truncated items or failed deliveries seen. Browser polls never stamp. Receipt is not completion.

- Polling is automatic: the hook polls after every Arena bash call and prints the unacked counts (messages, form answers, uploads) to stderr; it marks nothing seen. A nonzero count: `read` now, then `ack`. Markup needs `--reply`. Missing inbox: start the server; server down: restart it. End the turn's last tool block with a bash call, so the hook closes the channel.
- Answer every delivered note where the user reads it: `ack` exactly those IDs with `--reply <Markdown>`, rendered in the message log like the user's own messages, or `--note <text>` for one plain line under the receipt. One answer per call; ack different answers separately.

  ```bash
  python <skill>/scripts/preview.py --state-dir reports/arena-preview ack <id> [<id> ...] --reply <markdown>
  ```

  Never blindly acknowledge all pending notes. Unknown IDs fail the whole receipt batch; repeat acknowledgements keep their first timestamp and replace the answer text. Never name a note by its sequence number: numbers only order one file, and IDs survive state rebuilds. With no visible preview, acknowledge in chat instead, opening with literal `ACK:` and your interpretation; reserve that prefix for delivered notes, never thought or ordinary status.
- Treat `STOP:`, `PRIORITY:`, `CONTEXT:` and ordinary notes under chat's instruction precedence. Notes are instructions, not proof; disagree visibly with evidence when measurements contradict them.
- Read `task-list` at turn start. Before implementation, record approved work with `task <task-id> "<title>" [details ...]`; update the queue and details on scope or status changes. Put the current task first with `--order 1`; mark completion with `task <task-id> --status finished`. Use this skill's CLI and the same `--state-dir`.
- For inbox-note or report-submission work, add `--msg-id <full-message-id>` to `task`. Task and message link share one transaction; unknown message IDs fail both writes. Linked notes show `Task added` in log receipts; report-submission links create no log messages. The marker means queued, not acknowledged or complete; still use `ack`.

## Publishing reports

Short reports that fit in chat stay in chat; start a report only for readable rendered Markdown, multiple report documents or answerable fields. Write each report as a UTF-8 Markdown source file under an ignored, persisted workspace directory: one source per logical subject, updated in place, several subjects coexisting. Report changes, findings, checks actually run, decisions, unresolved issues and limitations. Never claim an unrun check. Follow the target repository's line-length convention, 120 characters in Clankers.

Publish with `publish <source.md> --id <id> --title <title>`, republishing the same ID after every source update; an answered report refuses a republish, so publish the update under a new ID. Installing markdown-it-py is preauthorized: keep it in the workspace venv and out of application manifests and generated requirements files. If installation fails, report it and do not claim rendered reports work. The renderer supports tables, lists, quotations, code fences, links and emphasis; raw HTML is disabled, images and other remote resources are not fetched, and neither the full GFM extension set nor syntax highlighting is available.

Delivery is the live Reports tab. Keep the Markdown source as the durable artifact, tell the user which report to select and verify the actual rendered endpoint, rather than claiming that a Markdown source in the file viewer was rendered. Publishing reports never acknowledges pending steering messages. Use fields when a questionnaire needs explanation around them; a field-only source is a bare questionnaire.

## Fields in reports

- ALWAYS pair each option set with a labeled custom-response field, e.g. `Custom response: ___`.

The preview cannot render mermaid; NEVER use it in reports.

A published report may carry live inputs, and field-only sources are questionnaires. The agent writes the markers as ordinary Markdown; the Reports tab renders them as controls under one Send answers button, with any prose around them as context:

| Marker | Control | Prompt |
| --- | --- | --- |
| `- ( ) option` lines | Radio group; `- (x)` preselects | The nearest text line above |
| `- [ ] option` lines | Checkbox group; `- [x]` preselects | The nearest text line above |
| `Label: ___` or a bare `___` line | Text box, at most 2000 characters | The label, else the line above |

Field IDs come from the prompt; add `{#my-id}` at the end of a prompt line to fix one. Markers inside fenced code blocks stay literal. Options must be unique in their group, 1–20 per group, prompts 1–500 characters, at most 50 fields per report. Answers POST to `/api/reports/<id>/submit` and are recorded apart from user messages: `read` lists them as pending items with `kind: report`, headed `REPORT <id> <title>:`, one indented line per field, `(skipped)` for empty ones, and `ack` answers them like notes. They never render in the message log. A send stores the answers in that browser, so the fields reload pre-filled and the user can amend and send again; each send is a new note, and submitted answers block a republish of that ID, so publish an update under a new ID.

## Uploads

Uploads write inbox notes with matching IDs, naming file, size, type and path. Read the file there, then ack the note. A restore can delete the bytes; the note and the record survive, and `present` says which is which.

## Persistence and limits

`state.sqlite3` stores notes, receipts, published report snapshots and the latest check using SQLite transactions. Keep the file, not the process, as the durable artifact.

Anyone with preview access can read messages/reports. The per-process token blocks blind cross-origin writes, not page visitors. Do not send secrets.

Processes, packages and URLs may disappear after a sandbox restart. After a server restart, reload to refresh the submission token, preserving your draft. Expose network/storage failures; never call an unconfirmed save successful.

If the preview fails, report it and ask how to continue in chat. Do not silently revive ntfy or local report commits. See [operation and recovery](references/REFERENCE.md).

Keep production free of this skill's name, directory and scripts; its own files, setup chat and acknowledgements are exceptions.
