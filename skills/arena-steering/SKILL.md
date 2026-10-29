---
name: arena-steering
description: Steer an Arena.ai agent mid-turn through a local preview inbox, dependency task queue, and fielded Markdown reports. Use in Arena Agent Mode when the user wants steering or a report, or when ARENA.md requires it. NEVER USE THIS SKILL OUTSIDE OF ARENA.AI.
license: MIT
compatibility: Arena.ai Agent Mode, Python 3.11+, persisted workspace and long-lived process tools.
metadata:
  version: "2.0.0"
---

# Arena Steering

Use one `steer` server and one state directory per session (`arena-state` by default).

## Server and version

```bash
skills/arena-steering/scripts/steer --version
skills/arena-steering/scripts/steer serve --port 8100
skills/arena-steering/scripts/demo.py --port 8100
```

## Messages (`Inbox`)

```bash
steer read
steer poll
steer ack <id> '<Markdown>' [-i <task-id> -t "<title>" -T <type> -S <scope> -d "<detail>"]
steer msg list [-a, --all] [-H, --hidden]
steer msg show <id>
```

- Every message ID matches `^[0-9a-f]{6}$`.
- `blocking=true` messages advance `sent -> seen -> acked`; `blocking=false` messages advance `sent -> seen` on `read` or `poll`.

## Tasks (`Tasks`)

```bash
steer tasks [-f, --full]
steer task <id>
steer task new <id> "<title>" [-T <type>] [-s <status>] [-S <scope>] [-d "<detail>"] [-m <msg-id>] [-r <report-id>] [-D <dep-id>]
steer task mod <id> deets <text>
steer task mod <id> deets rm <1-based-index>
steer task mod <id> links <msg-id|report-id>
steer task mod <id> links rm msg|report <id>
steer task mod <id> deps <task-id>
steer task mod <id> deps rm <task-id>
steer task mod <id> status|title|type|scope <value>
steer task rm <id>
```

- Tasks sit in a mutable queue where dependents automatically follow their dependencies (`deps[]`).
- Blocking state derives automatically from unanswered `report_ids[]` and unfinished `deps[]`.

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
