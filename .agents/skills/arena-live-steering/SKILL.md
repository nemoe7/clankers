---
name: arena-live-steering
description: "Steers a running Arena agent without interrupting its turn, through an ntfy topic the user posts to from any browser or phone: the agent reads the topic with its page-fetch tool, ingests each message into STEERING.md, and pivots on what it finds. Use only inside an Arena.ai Agent Mode session, when the user wants to correct or redirect the agent mid-turn without interrupting it, wants to steer from another browser or phone, or finds the Arena client's file sync or previews unreliable. Do not use outside Arena, and do not use when an ordinary chat reply reaches the agent just as well."
license: MIT
compatibility: Arena.ai Agent Mode sessions only. Needs Python 3+ and an agent-side page-fetch path; the user's side is ntfy's web UI or app.
metadata:
  author: arena-user
  version: "1.9.0"
  external-channel: "ntfy"
  arena-only: "true"
  use-when: "arena"
---

# Arena Live Steering - Portable Skill

Steer the Arena agent WITHOUT interrupting its turn, even when the Arena client is buggy.

## When to use this skill

- Arena client file sync or previews are buggy
- User wants to steer the agent mid-turn without clicking interrupt
- Need external control from a phone or another browser
- User says "steer without interrupting" or "live steering"
- Steering must leave no trace on any service, repository, or notification

## How it works

One channel. ntfy needs no account, no token, no zone, and no page of our own; publishing is instant, messages are append-only, and the server holds them for 12 hours. Only the agent's page-fetch path reads ntfy correctly: the egress proxy gives in-sandbox GETs a fake empty HTTP 200 even while a topic holds messages.

1. **Send the channel in chat**: generate a topic `<branch>-<secret>` (branch name with non `[A-Za-z0-9_-]` replaced by `-`, random token) and send its clickable `https://ntfy.sh/<topic>` link as the first line of the first chat reply, with the ARENA.md confirmation. First-read of ARENA.md and this skill may precede that reply. It must be visible before the first topic fetch, because a fetch fails until the user has sent something in the channel: the agent cannot publish to one, and the page-fetch tool reports an empty topic as its own HTTP 500, so that first failure is expected, not a broken channel. Never defer it to a summary or a later message, and never commit the topic, since ntfy has no sign-up and its docs call the topic essentially a password.
2. **The user publishes outside the sandbox**: to `https://ntfy.sh/<topic>` from the web UI, the phone app, or `curl -d "note" ntfy.sh/<topic>` on their own machine; sandbox POSTs are TLS-killed.
3. **The agent reads and ingests**: `https://ntfy.sh/<topic>/json?poll=1&since=<lastmessage>`, or `since=all` until the log holds an id, only through its page-fetch tool, never through curl or another in-sandbox HTTP client, then passes the returned body verbatim to `scripts/ntfy_steering.py`, which delivers each message once into the notes and log files, deduplicated by ntfy's message id, and prints the URL to pull next.

## Setup

Page-fetch the topic and ingest the body it returns, because a successful empty response can be filtered rather than empty:

```bash
STEERING_NTFY_TOPIC=<topic> STEERING_FILE=reports/STEERING.md \
  LOG_FILE=reports/STEERING_LOG.md python3 scripts/ntfy_steering.py body.ndjson
```

Point `STEERING_FILE` and `LOG_FILE` at paths the repository ignores, such as `reports/`, so notes never reach a commit; the log also holds the `since=` anchor, so losing it costs one full read rather than a note. `STEERING_NTFY_BASELINE=current` holds a topic's existing messages, recording their ids in the log so a later run does not deliver them either; the default delivers everything unseen.

## Note format and directives

```
STOP: don't use React, use vanilla JS
PRIORITY: focus on speed, not features
CONTEXT: the user actually wants X
```

`STOP:`, `PRIORITY:`, and `CONTEXT:` anywhere in a note are echoed to the ingest script's output as directives the agent must act on. Any other text is a note too.

## Agent integration

Fetch only via page-fetch, always by pulling the link, since the notes file holds only what some earlier read delivered: at turn start, after every reasoning block, before and after every tool call, and before turn end or anything expensive or hard to undo, such as push, rewrite, delete, or long build. A JSON fetch may return only the first NDJSON line: walk `since=<id>` until an empty 500. The HTML topic page keeps `<>` spans the JSON renderer deletes; pull it when checking the whole channel or when a note looks truncated. On a malformed JSON pull, fall back to that HTML page instead of ingesting the truncated JSON. Skip no check because the last read came back empty or the call looked short. Where the surface batches independent tool calls into one block, co-issue the pull inside every block as one of its parallel calls and read it again once the block returns: calls in a block issue at the same instant, so none can run before each of them in sequence, and a block is the unit of the cadence there. Batching places the pull inside the block it brackets; it is never a reason to pull less often. Use the `since=<lastmessage>` URL the ingest script prints, which returns only what is new. After a blocking call such as a question, read right after it returns, not before, because nothing new can arrive while it blocks. The closing check is not optional: a note sent while the agent was working is otherwise read a turn late. Activation is observable, not inferred: the topic named in the first reply, and a `STEERING_LOG.md` whose first check line lands on the first ingest run, so a session with no log never ran the skill, whatever it read.

Three clauses are not optional, because the user cannot see any of this:

- **Acknowledge every note in chat.** `10-4:` plus the agent's own interpretation of the note, never a restatement of the raw text, belong in the reply the user reads, never in reasoning, a tool call, or `STEERING.md`: an ack nobody can see is a dropped note, and they will send it again.
- **Disagree out loud.** A note is an instruction about what to do, not a fact about what is true. When a note contradicts a measurement, say which of the two is wrong and show the evidence, then do the thing that survives it. Reflexive agreement is the one failure mode this channel cannot absorb.
- **Keep production clean of this skill.** Never name this skill, its directory, `SKILL.md`, or its scripts in production docs, code, or comments. The skill's own files, the chat topic link, and `10-4:` are the exceptions.

Read the notes file with the helper:

```bash
STEERING_FILE=reports/STEERING.md python3 scripts/check_steering.py
```

## Scripts

- `scripts/steering_notes.py` - shared note writer: header, append, tail cap, digest dedup, directives
- `scripts/check_steering.py` - agent-side helper that reads the notes file
- `scripts/ntfy_steering.py` - turns an ntfy poll body into notes: id dedup, titles kept, fences stripped, the next-pull URL printed, an empty body reported as an empty topic rather than as a failure

See [references/REFERENCE.md](references/REFERENCE.md) for the environment, behaviour, hazards, and channels measured and not shipped.

## Environment Variables

- `STEERING_FILE` - notes path, default `STEERING.md` in the working directory
- `LOG_FILE` - append-only log path, default `STEERING_LOG.md`
- `STEERING_NTFY_TOPIC` - the topic name notes are attributed to
- `STEERING_NTFY_ERROR` - text of a mangled read, recorded in the log's check line for that run

## Limits, and what they cost

- **A topic is not an archive, and the agent cannot write to one.** ntfy.sh serves 12 hours of cache, so an old note survives only in the notes file; the page-fetch path is GET-only, so a fresh topic's first message comes from the user.
- **The topic name is the credential.** Anyone who knows it can read and write it, so generate a random one, keep it out of the repository, and never put a secret in a note.
- **A filtered host can lie to a process while working for the agent.** In-sandbox ntfy GETs get the fake empty 200 even while the topic holds messages, so only the page-fetch path is evidence about ntfy contents.
- **The JSON renderer deletes HTML tags.** `<>` in a note vanish, so walk `since=` to the empty 500 and read the HTML topic page when checking all or when a note looks truncated. Escaped `\<` `\>` survive the JSON path. Document that escape in the skill. A truncated or tag-stripped JSON body is a malformed pull: tell the user in chat, in one line, and fall back to the HTML page instead of ingesting the truncated JSON.
- **ntfy needs repeated active reads.** Pull the link at the cadence above, with the URL the script prints; there is no background capture.
- **A quiet channel is not a mangled one.** No new messages is reported as it stands today and earns nothing in chat; a read the channel mangles - the fetch tool failing, answering with its own upstream error body, or returning something that is not the topic's JSON - is told to the user in one line naming the error, with the text passed to the ingest run as `STEERING_NTFY_ERROR` so the log's check line carries it.

## Files

- `SKILL.md` - this file (required)
- `BASELINE.md` - the unsquashed original of this file
- `scripts/steering_notes.py` - shared note writer
- `scripts/check_steering.py` - agent helper
- `scripts/ntfy_steering.py` - ntfy body ingester
- `references/REFERENCE.md` - detailed reference

## Example Session

```bash
# The user publishes from a phone, to the topic link the agent posted:
$ curl -d "STOP: use vanilla JS not React" ntfy.sh/clankers-example

# The agent page-fetches the topic, then ingests the body:
$ STEERING_NTFY_TOPIC=clankers-example STEERING_FILE=reports/STEERING.md \
    python3 scripts/ntfy_steering.py body.ndjson
1 message(s) in the body, 1 delivered, 0 already seen or held as the baseline.
Next pull: https://ntfy.sh/clankers-example/json?poll=1&since=hwQ2YpKdmg
```

The agent then reads `reports/STEERING.md`, opens the next chat reply with `10-4:` plus its own interpretation of the note, in visible text, not a thought, and pivots.
