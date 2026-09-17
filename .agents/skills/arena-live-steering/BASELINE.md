---
name: arena-live-steering
description: Steers a running Arena agent without interrupting its turn, through an ntfy topic the user posts to from any browser or phone: the agent reads the topic with its page-fetch tool, ingests each message into STEERING.md, and pivots on what it finds. Use only inside an Arena.ai Agent Mode session, when the user wants to correct or redirect the agent mid-turn without interrupting it, wants to steer from another browser or phone, or finds the Arena client's file sync or previews unreliable. Do not use outside Arena, and do not use when an ordinary chat reply reaches the agent just as well.
license: MIT
compatibility: Arena.ai Agent Mode sessions only. Needs Python 3+ and an agent-side page-fetch path; the user's side is ntfy's web UI or app.
metadata:
  author: arena-user
  version: "1.2.0"
  external-channel: "ntfy"
  arena-only: "true"
  use-when: "arena"
  baseline: >-
    Unsquashed original of `SKILL.md` in this directory. Amend this file first,
    then squash it into `SKILL.md` and re-measure that file against its budget
    in the repository README. This file carries no budget of its own.
---

# Arena Live Steering - Portable Skill

Steer the Arena agent WITHOUT interrupting its turn, even when the Arena client is buggy. The channel is an ntfy topic the user posts to from any browser or phone; the agent reads it with its page-fetch tool, ingests each message into `STEERING.md`, and pivots on what it finds.

## When to use this skill

- Arena client file sync or previews are buggy
- User wants to steer the agent mid-turn without clicking interrupt
- Need external control from a phone or another browser
- User says "steer without interrupting" or "live steering"
- Steering must leave no trace on any service, repository, or notification

## How it works

One channel. ntfy needs no account, no token, no zone, and no page of our own, since the user posts from ntfy's own web UI or phone app; publishing is instant, messages are append-only, and the server holds them for 12 hours. Only the agent's page-fetch path reads ntfy correctly: the sandbox egress proxy gives in-sandbox GETs a fake empty HTTP 200 even while a topic holds messages, so never read it with curl or any other in-sandbox HTTP client.

1. **Send the channel in chat**: the moment this skill is read, generate a random topic and send its full clickable `https://ntfy.sh/<topic>` link in chat, as the first line of the agent's reply, before any tool call and before any other work. The link must be visible before the agent attempts to fetch, because a fetch fails until the user has sent something in the channel: the agent cannot publish to one (GET-only fetch, TLS-killed POSTs), and the page-fetch tool reports an empty topic as its own HTTP 500, so that first failure is expected, not a broken channel. Never defer the link to a summary or a later message, and never commit the topic, since ntfy has no sign-up and its docs call the topic essentially a password.
2. **The user publishes outside the sandbox**: to `https://ntfy.sh/<topic>` from the web UI, the phone app, or `curl -d "note" ntfy.sh/<topic>` on their own machine; sandbox POSTs are TLS-killed.
3. **The agent reads and ingests**: `https://ntfy.sh/<topic>/json?poll=1&since=all` only through its page-fetch tool, never through curl or another in-sandbox HTTP client, then passes the returned body verbatim to `scripts/ntfy_steering.py`, which delivers each message once into the notes and log files, deduplicated by ntfy's message id.

## Setup

Read the topic only with the agent's page-fetch tool and ingest its returned body; do not substitute curl or another in-sandbox HTTP client, because a successful empty response can be filtered rather than empty:

```bash
STEERING_NTFY_TOPIC=<topic> STEERING_FILE=reports/STEERING.md \
  LOG_FILE=reports/STEERING_LOG.md python3 scripts/ntfy_steering.py body.ndjson
```

Point `STEERING_FILE` and `LOG_FILE` at paths the repository ignores, such as `reports/`, so notes never reach a commit. `STEERING_NTFY_BASELINE=current` marks the messages already in a topic as seen without delivering them, and records their ids in the log so a later run does not deliver them either. The default delivers everything unseen.

## Note format and directives

```
STOP: don't use React, use vanilla JS
PRIORITY: focus on speed, not features
CONTEXT: the user actually wants X
```

`STOP:`, `PRIORITY:`, and `CONTEXT:` anywhere in a note are echoed to the ingest script's output as directives the agent must act on. Any other text is a note too.

## Agent integration

Fetch only through the page-fetch tool, with `poll=1&since=all` every time, because id dedup makes repeated full reads safe. Check at the start of every turn, after every reasoning block, after every three tool calls, and before the turn ends or anything expensive or hard to undo, such as a push, a rewrite, a delete, or a long build. After a blocking tool call such as a question, read right after it returns rather than before it, because nothing new can arrive while it blocks; a read spent just before a blocking call is wasted. The closing check is not optional: a note sent while the agent was working is otherwise read a turn late.

The agent pivots on what it finds. Two clauses are not optional, because the user cannot see any of this:

- **Acknowledge every note.** A reply that follows a delivered note opens with `STEER RECEIVED:` and one line saying what the note asked and what changed because of it. A note that lands silently is indistinguishable from one that was lost, and the user will send it again.
- **Disagree out loud.** A note is an instruction about what to do, not a fact about what is true. When a note contradicts a measurement, say which of the two is wrong and show the evidence, then do the thing that survives it. Reflexive agreement is the one failure mode this channel cannot absorb.

```python
from check_steering import check_steering

notes = check_steering()
if "STOP:" in notes.upper():
  ...  # pivot immediately
```

Or from a shell:

```bash
STEERING_FILE=reports/STEERING.md python3 scripts/check_steering.py
```

## Scripts

- `scripts/steering_notes.py` - shared note writer: header, append, tail cap, digest dedup, directives
- `scripts/check_steering.py` - agent-side helper that reads the notes file
- `scripts/ntfy_steering.py` - turns an ntfy poll body into notes: id dedup, titles kept, code fences stripped, an empty body reported as an empty topic rather than as a failure

See the [reference guide](references/REFERENCE.md) for the environment, the behaviour, the hazards, and the channels that were measured and not shipped.

## Environment Variables

- `STEERING_FILE` - notes path, default `STEERING.md` in the working directory
- `LOG_FILE` - append-only log path, default `STEERING_LOG.md`
- `STEERING_NTFY_TOPIC` - the topic name notes are attributed to
- `STEERING_NTFY_BASELINE` - `empty` (default) delivers everything unseen; `current` holds what the topic already has

## Limits, and what they cost

- **A topic is not an archive, and the agent cannot write to one.** ntfy.sh serves 12 hours of cache, so an old note survives only in the notes file; sandbox POSTs are TLS-killed and the page-fetch path is GET-only, so a fresh topic's first message comes from the user.
- **The topic name is the credential.** Anyone who knows it can read and write it, so generate a random one, keep it out of the repository, and never put a secret in a note.
- **A filtered host can lie to a process while working for the agent.** The sandbox egress proxy returns HTTP 200 and zero bytes for ntfy GETs even while the topic holds messages, so only the page-fetch path is evidence about ntfy contents.
- **ntfy needs repeated active reads.** Only the agent's page-fetch path reads it correctly, so fetch at the cadence above; there is no background capture.

## Files

- `SKILL.md` - this file (required)
- `scripts/steering_notes.py` - shared note writer
- `scripts/check_steering.py` - agent helper
- `scripts/ntfy_steering.py` - ntfy body ingester
- `references/REFERENCE.md` - detailed reference

## Example Session

```bash
# The user publishes from a phone, to the topic link the agent posted:
$ curl -d "STOP: use vanilla JS not React" ntfy.sh/clankers-example

# The agent fetches the topic through its page-fetch tool, then ingests the body:
$ STEERING_NTFY_TOPIC=clankers-example STEERING_FILE=reports/STEERING.md \
    python3 scripts/ntfy_steering.py body.ndjson
1 message(s) in the body, 1 delivered, 0 already seen or held as the baseline.
```

The agent then reads `reports/STEERING.md`, opens its next reply with `STEER RECEIVED:`, and pivots.
