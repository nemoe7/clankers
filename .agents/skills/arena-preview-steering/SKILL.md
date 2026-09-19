---
name: arena-preview-steering
description: Steer an Arena.ai agent mid-turn without interruption through a persistent local live-preview inbox. Owns the shared Notes / Reports server, message log, saved versus acknowledged receipts, and dark/light interface. Use in Arena Agent Mode when the user wants mid-turn steering or ARENA.md requires it; not outside Arena. Reporting uses the companion arena-preview-reporting skill and this same runtime.
license: MIT
compatibility: Arena.ai Agent Mode, Python 3.10+, persisted workspace files and long-lived process tools. Steering is standard-library only; reporting additionally needs markdown-it-py and the companion skill.
metadata:
  origin: first-party, maintained in this repository
  version: "2.0.0"
  arena-only: "true"
---

# Arena Preview Steering

One server and inbox per session. Reporting shares this runtime; never start a second server for reports. User instructions and repository rules win.

## Setup

1. Resolve this skill's actual path: source `skills/` and installed discovery paths differ. Report missing installed files; do not install or repair them without authorization.
2. Choose a stable, persisted, Git-ignored state directory, default `reports/arena-preview`. Verify it with `git check-ignore`; ask before adding an ignore rule if needed. Never use cache/build folders or commit/push session state, notes, receipts, reports or exports.
3. Start with Arena's long-lived process tool, not a timed shell call:

   ```bash
   python <skill>/scripts/preview.py --state-dir reports/arena-preview serve --port 8000
   ```

   The server binds `0.0.0.0`; browser URLs are relative and the preview host is accepted. Reuse its process and state directory. If it dies, restart with the same directory. If its port belongs to another service, choose a free port; never kill that service.
4. Initial setup: start the server, name the preview in chat, then immediately block with one visibility question before normal work. Keep ARENA.md's literal activation acknowledgement when applicable. Preview visibility may wait for a question/turn boundary, observed 2026-09-20. After the answer, read the inbox and continue. Never claim visibility before confirmation; if still hidden, report and agree on the next step. Reusing an already-visible preview needs no setup question.
5. Dark is the default; Notes stays single-column beside chat. Enter sends, Shift+Enter adds a newline; IME composition does not send. Show confirmation by the send controls and the last sent text as the empty textarea's placeholder, not a duplicate block. History distinguishes saved/acknowledged notes. Warn when browser draft storage fails; unchanged retries reuse their ID. Optional Write / Preview reuses `markdown-it-py` in the same space: read-only rendering, not WYSIWYG. Send raw Markdown; previewing neither saves to the inbox nor delivers it. Render Markdown in the log too; stored/delivered text stays unchanged. Without the renderer, raw editing/sending work and the log explicitly labels its raw-text display.

## Read, then acknowledge

```bash
python <skill>/scripts/preview.py --state-dir reports/arena-preview read
```

The command prints **all pending messages**, without truncation, and records the check time. It neither acknowledges nor removes them. Missing, unreadable or corrupt state is an error, never an empty inbox.

- Read at turn start, each reasoning boundary, before/after every tool-call block, before expensive/irreversible work and before turn end. Co-issue a read in each parallel block and read after return; the block is the cadence unit. A blocking-only call needs its read after return. Initial discovery/startup may precede the first read. Never use a background consumer to mark unseen messages handled.
- Acknowledge every delivered note in visible chat, opening with literal `ACK:` and your interpretation. Reserve that prefix for delivered notes, never thought or ordinary status. **After** that chat acknowledgement, record exactly those IDs:

  ```bash
  python <skill>/scripts/preview.py --state-dir reports/arena-preview ack <id> [<id> ...]
  ```

  Never blindly acknowledge all pending notes. Unknown IDs fail the whole receipt batch; repeat acknowledgements keep their first timestamp. Receipt means received, not implemented.
- Treat `STOP:`, `PRIORITY:`, `CONTEXT:` and ordinary notes under chat's instruction precedence. Notes are instructions, not factual proof; disagree visibly when measurements contradict them, showing evidence.

## Persistence and limits

`state.sqlite3` stores notes, receipts, published report snapshots and the latest check using SQLite transactions. Keep the file, not the process, as the durable artifact. The browser polls for display updates; this does **not** make the agent read automatically.

Anyone with preview access can read messages/reports. The per-process submission token blocks blind cross-origin writes, not a visitor who can open the page. Do not send secrets. Only interface routes, structured state and explicitly published reports are served, never arbitrary repository paths.

Processes, packages and URLs may disappear after a sandbox restart; workspace files are not a permanent backup service. Drafts depend on browser origin/storage. After a server restart, reload to refresh the submission token, preserving your draft. Expose network/storage failures; never call an unconfirmed save successful. A missing Markdown renderer must not disable steering.

If the preview fails, report it and ask how to continue in chat. Do not silently revive ntfy or local report commits; they are historical alternatives, neither active fallback nor banned forever. See [migration and recovery](references/REFERENCE.md).

Keep production free of this skill's name, directory and scripts; its own files, setup chat and acknowledgements are exceptions. For reports, use sibling [arena-preview-reporting](../arena-preview-reporting/SKILL.md). Run `scripts/check_preview.py` with the reporting venv's Python to check the runtime without external test frameworks.
