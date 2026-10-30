---
name: arena-steering
description: Steer an Arena.ai agent mid-turn through a local preview inbox, dependency task queue, and fielded Markdown reports. Use in Arena Agent Mode when the user wants steering or a report, or when ARENA.md requires it. NEVER USE THIS SKILL OUTSIDE OF ARENA.AI.
license: MIT
compatibility: Arena.ai Agent Mode, Python 3.11+, persisted workspace and long-lived process tools.
metadata:
  version: "2.1.0"
---

# Arena Steering

Use one `steer` server and one state directory per session (`arena-state` by default).

## Server and version

```bash
.agents/skills/arena-steering/scripts/install.sh
steer --version
steer serve
```

## Messages (`Inbox`)

```bash
steer read
steer poll
steer ack <id> '<Markdown>' [-i <task-id> -t "<title>" -T <type> -S <scope> -d "<detail>"]
steer msg list [-p PAGE] [-s SIZE]
steer msg <id>
```

- Every message ID matches `^[0-9a-f]{6}$`.
- `blocking=true` messages advance `sent -> seen -> acked`; `blocking=false` messages advance `sent -> seen` on `read` or `poll`.

## Tasks (`Tasks`)

```bash
steer tasks [-f, --full]
steer task <id>
steer task new <id> "<title>" [-T <type>] [-s <status>] [-S <scope>] [-d "<detail>"] [-m <msg-id>] [-r <report-id>] [-k <task-id>]
steer task mod <id> deets <text>
steer task mod <id> deets rm <1-based-index>
steer task mod <id> links [msg|report|task] <id>
steer task mod <id> links rm msg|report|task <id>
steer task mod <id> status|title|type|scope <value>
steer task unlink <id> [msg|report|task] <link-id>
steer task unlink <answer-id>
steer task rm <id>
```

- Tasks sit in a mutable queue where dependents automatically follow their task links (`links.task_ids[]`).
- Blocking state derives automatically from unanswered `links.report_ids[]` and unfinished `links.task_ids[]`.
- `steer task unlink <answer-id>` drops one stored answer snapshot from every task that holds it. The answer, its text, its receipts, and the report link stay; relinking the report does not restore the snapshot.

## Reports (`Reports`)

```bash
steer reports [-s, --stale]
steer report <id>
steer report pub <source.md> -i <id> -t "<title>"
steer report rm <id|--stale>
```

- Every report field requires a statement `label` before its options (`- ( )`, `- (x)`, `- [ ]`, `- [x]`) or after `label: ___`.
- Field IDs default to kebab-case of `label` with trailing `-` stripped, or come from an optional `<!-- field-id -->` comment above the field.
- Radio (`choice`) and checkbox (`checkbox`) fields automatically render a built-in `"Something else..."` free-form input in the web UI.
