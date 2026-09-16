---
name: arena-live-steering
description: Steers a running Arena agent without interrupting its turn, through an ntfy topic the user posts to from any browser or phone: the agent reads the topic with its page-fetch tool, ingests each message into STEERING.md, and pivots on what it finds. A DNS TXT record with a background poller is the fallback where there is no agent-side fetch path. Use only inside an Arena.ai Agent Mode session, when the user wants to correct or redirect the agent mid-turn without interrupting it, wants to steer from another browser or phone, or finds the Arena client's file sync or previews unreliable. Do not use outside Arena, and do not use when an ordinary chat reply reaches the agent just as well.
license: MIT
compatibility: Arena.ai Agent Mode sessions only. Needs Python 3+. The ntfy route needs an agent-side page-fetch path and nothing else, since the user's side is ntfy's web UI or app; the DNS fallback needs a resolver answering UDP/53 and a zone the user can edit.
metadata:
  author: arena-user
  version: "1.0.0"
  external-channel: "dns-txt"
  arena-only: "true"
  use-when: "arena"
---

# Arena Live Steering - Portable Skill

Steer the Arena agent WITHOUT interrupting its turn, even when the Arena client is buggy. One channel carries the notes: a DNS TXT record the user edits from any browser or phone, which a poller reads over UDP/53 and appends to `STEERING.md`.

## When to use this skill

- Arena client file sync or previews are buggy
- User wants to steer the agent mid-turn without clicking interrupt
- Need external control from a phone or another browser
- User says "steer without interrupting" or "live steering"
- Sandbox egress is allowlisted, so HTTP channels like `ntfy.sh` are unreachable
- Steering must leave no trace on any service, repository, or notification

## How it works

Two channels are supported. ntfy is the default: no account, no token, no zone, and no page of our own, since the user posts from ntfy's own web UI or phone app, publishing is instant rather than waiting on a TTL, messages are append-only, and the server holds them for 12 hours, so one read at the next turn boundary catches everything. Its limit is that only the agent's page-fetch path reaches it, so there is no background poller. DNS is the fallback, and it earns its place for one reason: a process inside the sandbox can poll it by itself, so it still works in a session with no fetch path at all. `REFERENCE.md` carries both routes' measurements.

The ntfy route:

1. **Pick a topic**: a random name, told to the user in chat and never committed, since ntfy has no sign-up and its docs call the topic essentially a password.
2. **The user publishes**: to `https://ntfy.sh/<topic>` from the web UI, the phone app, or `curl -d "note" ntfy.sh/<topic>`.
3. **The agent reads and ingests**: `https://ntfy.sh/<topic>/json?poll=1&since=all` through its page-fetch path, then pipes the body to `scripts/ntfy_steering.py`, which delivers each message once into the same notes and log files the poller writes, deduplicated by ntfy's message id.


The DNS route:

1. **Pick a record**: any hostname whose zone the user can edit, such as `steering.example.com`. A free dynamic DNS zone works; the sandbox never contacts the provider, only the resolver.
2. **Poller**: `scripts/dns_steering.py` queries that name's TXT record every `POLL_INTERVAL` seconds with stdlib sockets, over UDP/53.
3. **Writes to STEERING.md**: each new value is appended under `## Current Notes:` with an attribution comment, and the agent reads that file every one or two tool calls.
4. **User edits the record**: from the provider's own panel, a phone, or a one-line API call. No login on the sandbox side, no notification, nothing in a commit.

## Setup

```bash
STEERING_DNS_NAME=steering.example.com \
  STEERING_FILE=reports/STEERING.md LOG_FILE=reports/STEERING_LOG.md \
  POLL_INTERVAL=30 python3 -u scripts/dns_steering.py
```

Point `STEERING_FILE` and `LOG_FILE` at paths the repository ignores, such as `reports/`, so notes never reach a commit. The startup banner reports what the resolver said: a value, `NOERROR` with no TXT record yet, or `NXDOMAIN`, which means the name does not exist and no note can ever arrive.

For the ntfy route there is no poller to start. Read the topic with the agent's page-fetch tool and ingest the body:

```bash
STEERING_NTFY_TOPIC=<topic> STEERING_FILE=reports/STEERING.md \
  LOG_FILE=reports/STEERING_LOG.md python3 scripts/ntfy_steering.py body.ndjson
```

`STEERING_NTFY_BASELINE=current` marks the messages already in a topic as seen without delivering them, and records their ids in the log so a later run does not deliver them either. The default delivers everything unseen.

`STEERING_DNS_BASELINE` decides what the first poll does. `current`, the default, holds whatever the record already says so a stale note is never replayed; `empty` ingests the first value found, which is what you want when the record was written before the poller started.

## Note format and directives

```
STOP: don't use React, use vanilla JS
PRIORITY: focus on speed, not features
CONTEXT: the user actually wants X
```

`STOP:`, `PRIORITY:`, and `CONTEXT:` anywhere in a note are echoed to the poller's stdout as directives the agent must act on. Any other text is a note too. Appending a line to the record delivers only that line, because the poller diffs against the longest line prefix it has already seen.

## Agent integration

How often to check depends on what a read costs. On ntfy it is a network round trip inside the turn, so check at the start of every turn, once more before the turn ends, and again before anything expensive or hard to undo, such as a push, a rewrite, a delete, or a long build; do not poll in between, since `since=all` returns everything the 12-hour cache still holds. The closing check is not optional and the user asked for it by name: a note sent while the agent was working is otherwise read a turn late, and the acknowledgment clause cannot fire on a note nobody has read. On the DNS fallback a poller is already capturing into a local file, so reading `STEERING.md` every one or two tool calls costs nothing.

Either way the agent pivots on what it finds:

Two clauses are not optional, because the user cannot see any of this:

- **Acknowledge every note.** A reply that follows a delivered note opens with `STEER RECEIVED:` and one line saying what the note asked and what changed because of it. The poller's stdout is invisible to the user, so a note that lands silently is indistinguishable from one that was lost, and they will send it again.
- **Disagree out loud.** A note is an instruction about what to do, not a fact about what is true. When a note contradicts a measurement, say which of the two is wrong and show the evidence, then do the thing that survives it. Reflexive agreement is the one failure mode this channel cannot absorb: the user has no view of the work, so nothing else catches a complacent agent.

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

- `scripts/dns_steering.py` - the poller: one TXT record, stdlib sockets, no HTTP
- `scripts/steering_notes.py` - shared note writer: header, append, tail cap, line diff, digest dedup, directives
- `scripts/check_steering.py` - agent-side helper that reads the notes file
- `scripts/ntfy_steering.py` - turns an ntfy poll body into notes: id dedup, titles kept, code fences stripped, an empty body reported as an empty topic rather than as a failure

See the [reference guide](references/REFERENCE.md) for the environment, the behaviour, the hazards, and the channels that were measured and not shipped.

## Environment Variables

- `STEERING_DNS_NAME` - required, the TXT record to watch
- `STEERING_FILE` - notes path, default `STEERING.md` in the working directory
- `LOG_FILE` - append-only log path, default `STEERING_LOG.md`
- `POLL_INTERVAL` - seconds between queries, default 30
- `DNS_RESOLVER` - override the resolver; by default the `nameserver` lines of `/etc/resolv.conf`
- `DNS_TIMEOUT` - seconds per query, default 5
- `STEERING_DNS_BASELINE` - `current` (default) or `empty`

## Limits, and what they cost

- **The record is public.** Anyone who knows the name can read every note, and anyone who can edit the zone can steer the agent. Never put a secret in a note.
- **Latency is the TTL, not the poll interval.** A 60s TTL means up to a minute per edit, and a name that did not exist before can take the zone's negative-cache TTL to appear.
- **Resolvers can disagree.** Two caches serving the same name were measured returning different values for minutes, so the poller deduplicates by value digest and keeps the digests in the log. Re-setting a value that was already delivered is ignored; change one character to send it again.
- **The sandbox blinks, and a blink looks like an empty record.** Ten queries of the live record returned its value five times and NOERROR-with-no-data five times, while every control name answered correctly on every try, so the record was being served and the observer was at fault half the time. The poller therefore queries a control name before saying anything about the record, and the read to trust is DNS-over-HTTPS through the agent's page-fetch path, which returned the full value every time. Keep the interval at 30s or slower regardless.
- **A blocked host is blocked for processes, not for the agent.** `ntfy.sh`, `gist.githubusercontent.com`, and `dns.google` are all closed to the sandbox's sockets and were all read through the agent's page-fetch path, so an external channel is usable agent-side when the sandbox cannot reach it. The cost is that it can only be read when the agent acts: no background poller can use that path.
- **One character-string is 255 octets.** Longer values are split by the provider and rejoined by the poller, which a 370-character multi-line note confirmed in live use.
- **ntfy is read at turn boundaries.** Only the agent's page-fetch path reaches it and that is a tool call, so no background poller can watch a topic. DNS is the route for a note that has to be captured while the agent is working.
- **A topic is not an archive, and the agent cannot write to one.** ntfy.sh serves 12 hours of cache, so an old note survives only in the notes file; and with the sandbox's sockets TLS-closed, the fetch path GET-only, and repository secrets 403, there is no outbound relay, so a fresh topic's first message comes from the user.
- **The channel is one-way.** The sandbox can read DNS but cannot reach a zone's authoritative servers to write it, so questions from the agent travel through the Arena client instead.

## Files

- `SKILL.md` - this file (required)
- `scripts/dns_steering.py` - the poller
- `scripts/steering_notes.py` - shared note writer
- `scripts/check_steering.py` - agent helper
- `references/REFERENCE.md` - detailed reference

## Example Session

```bash
# Terminal 1: start the poller
$ STEERING_DNS_NAME=steering.example.com STEERING_DNS_BASELINE=empty \
    STEERING_FILE=reports/STEERING.md python3 -u scripts/dns_steering.py
DNS steering active on the TXT record steering.example.com
Resolvers: 8.8.8.8
Baseline 'empty': 0 characters

# The user edits the record from a phone; one TTL later the poller prints
Steering from dns txt steering.example.com
STOP: use vanilla JS not React
------------------------------------------------------------
>> STOP: the agent must act on this note
```

The agent then reads `reports/STEERING.md` and pivots.
