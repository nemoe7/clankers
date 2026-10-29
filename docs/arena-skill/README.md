# Arena Skill

Steer Arena coding sessions through one live preview inbox, task queue, and report viewer. Agents read mid-turn notes, publish interactive reports, and synchronize cross-session board state. Companion proxies handle outbound reads, state persistence, and installable preview links.

## Setup

Load [SKILL.md](../../skills/arena-skill/SKILL.md) in an agent that supports skills. See [Skills](../../skills/README.md) for installation layout. The preview server needs Python 3.11+ and its standard library, plus `markdown-it-py` and `PyYAML`.

```bash
bash .agents/skills/arena-skill/scripts/install.sh
arena-preview serve --port 8000
```

The installer creates the preview virtual environment, configures shell hooks, and adds `arena-preview` to `PATH`. Start the server on `0.0.0.0:8000` so Arena exposes the live preview tab.

## Working flow

1. Read pending owner notes and report answers with `arena-preview read`.
2. Acknowledge every read item with `arena-preview ack <id> "<reply>"`.
3. Track upcoming and finished work with `arena-preview task list` and `arena-preview task set`.
4. Publish Markdown reports and structured input fields with `arena-preview report publish`.
5. Run long checks in the background with `arena-preview run start` and wait at turn end with `arena-preview poll`.

## Preview surfaces

| Tab | Purpose |
| --- | --- |
| Messages | Live note composer, file attachments, read receipts, and agent replies |
| Tasks | Ordered task queue, linked report answers, and finished commit status |
| Reports | Rendered Markdown reports with interactive approval, radio, checkbox, and text fields |
| Survey | Session calibration status and hoverable submission details |
| Downloads | Owner-approved browser URL download queue |
| Board | Optional multi-session task and worker view backed by `arena-egress-proxy` |

## Companion proxies

Two optional Docker services sit beside the skill for features beyond the sandbox. [arena-egress-proxy](../../skills/arena-skill/arena-egress-proxy/INSTALL.md) provides authenticated GitHub and HTTP reads plus SQLite board and state sync. [arena-preview-proxy](../../skills/arena-skill/arena-preview-proxy/INSTALL.md) serves an installable web app for opening shared Arena preview URLs.

## Limits

Preview state lives in ignored local files and resets when the sandbox resets unless restored. State sync and board sharing require a configured `arena-egress-proxy` host and master key in the Arena userscript. Browser download approvals guard the UI workflow rather than enforcing a server security boundary. Complete operating rules live in [SKILL.md](../../skills/arena-skill/SKILL.md) and [references/reference.md](../../skills/arena-skill/references/reference.md).

This README is human documentation and is not part of the installed skill payload.
