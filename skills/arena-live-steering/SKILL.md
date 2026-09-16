---
name: arena-live-steering
description: Steers a running Arena agent without interrupting its turn, through an external ntfy.sh channel with a random per-session topic: a poller writes each published message to STEERING.md, and the agent reads that file between tool calls and pivots. Use only inside an Arena.ai Agent Mode session, when the user wants to correct or redirect the agent mid-turn without interrupting it, wants to steer from another browser or phone, or finds the Arena client's file sync or previews unreliable. Do not use outside Arena, and do not use when an ordinary chat reply reaches the agent just as well.
license: MIT
compatibility: Arena.ai Agent Mode sessions only. Needs Python 3+ and outbound HTTPS to ntfy.sh.
metadata:
  author: arena-user
  version: "1.0.0"
  random-topic: "true"
  external-channel: "ntfy.sh"
  arena-only: "true"
  use-when: "arena"
---

# Arena Live Steering - Portable Skill

Steer the Arena agent WITHOUT interrupting its turn, even when Arena client is buggy. Two channels carry the notes: an external ntfy.sh topic, and a GitHub issue or pull request for a sandbox whose egress is allowlisted.

## When to use this skill

- Arena client file sync or previews are buggy
- User wants to steer agent mid-turn without clicking interrupt
- Need external control from phone/browser
- User says "steer without interrupting" or "live steering"
- Need random private channel per session
- Sandbox egress cannot reach `ntfy.sh`, or steering must leave no comments behind: use the GitHub transport, which needs only `api.github.com`

## How it works

1. **Random topic generation**: On first run, generates `arena-steer-{8 hex}` via `uuid4().hex[:8]` - 4B combinations
2. **External poller**: Polls `https://ntfy.sh/TOPIC/json?poll=1` every 3s, deduplicates via seen_ids + since param
3. **Writes to STEERING.md**: Agent checks this file every 1-2 tool calls
4. **User publishes**: From any browser/phone at `https://ntfy.sh/TOPIC` - no login needed

## Transports

| Transport | Script | Egress needed | Who can steer |
| --- | --- | --- | --- |
| ntfy.sh topic | `scripts/external_steering.py` | `ntfy.sh` | Anyone who learns the topic |
| GitHub issue body | `scripts/github_steering.py` | `api.github.com` | Anyone who can edit that issue |
| GitHub comments | `scripts/github_steering.py` with `STEERING_SOURCE=comments` | `api.github.com` | Anyone with access to the repository |

All three write the same `## Current Notes:` section, so the agent side never changes. Body mode leaves nothing behind; comment mode costs one comment per note, or one comment the user keeps editing. Start the GitHub transport on an issue or pull request number, with `STEERING_FILE` on a path the repository ignores:

```bash
STEERING_REPO=owner/name STEERING_ISSUE=14 \
  STEERING_FILE=reports/STEERING.md \
  python3 -u scripts/github_steering.py
```

Prefer it where egress is allowlisted — an Arena sandbox closes the TLS connection to `ntfy.sh` and answers on `api.github.com` — and where comment noise is unwanted. Never point body mode at a description the agent itself writes, or the agent steers itself; stop the poller around such a write. The [reference guide](references/REFERENCE.md) carries the environment, endpoints, change detection, permissions, and hazards.

## Installation (portable)

This skill is self-contained. Copy folder to any project:

```bash
cp -r arena-live-steering /your/project/
cd /your/project/arena-live-steering
./scripts/install.sh
```

Or run directly:

```bash
python3 scripts/generate_topic.py  # generates random topic
python3 -u scripts/external_steering.py  # starts poller
```

## Usage

### 1. Start poller (generates random topic if not exists)

```bash
python3 -u scripts/external_steering.py
# Output:
# Topic (random): arena-steer-a1b2c3d4
# Publish URL: https://ntfy.sh/arena-steer-a1b2c3d4
```

Or with custom topic:

```bash
NTFY_TOPIC=arena-steer-custom123 python3 -u scripts/external_steering.py
```

### 2. Get your publish URL

```bash
cat .topic
# arena-steer-dd3b342e
# URL: https://ntfy.sh/arena-steer-dd3b342e
```

### 3. Steer from anywhere

Open publish URL in any browser/phone, type, hit Send:

```
STOP: don't use React, use vanilla JS
PRIORITY: focus on speed, not features
TEST: hello from phone
CONTEXT: user actually wants X
```

Via curl:

```bash
TOPIC=$(cat .topic)
curl -d "STOP: change direction" https://ntfy.sh/$TOPIC
curl -d "PRIORITY: focus on speed" https://ntfy.sh/$TOPIC
```

### 4. Agent integration

Agent must poll STEERING.md every 1-2 tool calls:

```python
# Minimal
with open("/home/user/STEERING.md") as f:
  notes = f.read()
if "STOP:" in notes.upper():
  # pivot immediately
  print("STOP detected, changing direction")
```

Or use helper script:

```bash
./scripts/check_steering.sh
# or
python3 scripts/check_steering.py
```

## Scripts

- `scripts/generate_topic.py` - Generates random topic `arena-steer-{8 hex}`, saves to multiple locations for portability
- `scripts/external_steering.py` - Main poller, deduplicates, handles 429 backoff, writes to STEERING.md
- `scripts/github_steering.py` - GitHub poller: issue body edits by default, comments opt-in
- `scripts/steering_notes.py` - Shared note writer: one header, append, tail cap
- `scripts/install.sh` - One-click install, generates topic, QR code
- `scripts/check_steering.py` - Helper for agents to check steering file

See [reference guide](references/REFERENCE.md) for detailed API.

## Random Topic Generation

Topic format: `arena-steer-{8 hex chars}` e.g. `arena-steer-dd3b342e`

- Generated via `uuid.uuid4().hex[:8]` - cryptographically random
- 16^8 = 4,294,967,296 combinations
- Saved to:
  - `./.topic` (skill local)
  - `/home/user/.steering_topic` (user home)
  - `/home/user/STEERING_TOPIC` (workspace root)
  - `./.steering_topic` (cwd)

First existing valid topic is reused, otherwise new random generated.

To force new random topic:

```bash
rm .topic ~/.steering_topic ~/STEERING_TOPIC ./.steering_topic
python3 scripts/generate_topic.py
```

## Security

Topic is obscure but not encrypted. Anyone with topic can publish. For private use, keep topic secret.

To make more private, generate longer random in `generate_topic.py`:

```python
f"arena-steer-{uuid.uuid4().hex}{uuid.uuid4().hex}"  # 32 chars
```

## Why external?

Arena client file sync and previews are buggy as of 2026-09. This bypasses Arena entirely - works from phone, no login, no Arena UI needed. File-based steering still works as backup.

## Files

- `SKILL.md` - This file (required)
- `scripts/generate_topic.py` - Random topic generator
- `scripts/external_steering.py` - External poller
- `scripts/github_steering.py` - GitHub poller
- `scripts/steering_notes.py` - Shared note writer
- `scripts/install.sh` - Installer
- `scripts/check_steering.py` - Agent helper
- `references/REFERENCE.md` - Detailed reference
- `assets/qr.png` - QR code for publish URL (generated on install)

## Environment Variables

- `NTFY_TOPIC` - Override random topic
- `STEERING_FILE` - Override STEERING.md path (default: /home/user/STEERING.md)
- `LOG_FILE` - Override log path (default: /home/user/STEERING_LOG.md)
- `PORT` - For optional web UI (if you add steering_server.py)
- GitHub transport: `GH_TOKEN` or `GITHUB_TOKEN`, `STEERING_REPO`, `STEERING_ISSUE`, `STEERING_SOURCE`, `POLL_INTERVAL`, `STEERING_IGNORE_AUTHORS` - defaults and endpoints in the reference guide

## Example Session

```bash
# Terminal 1: Start poller (generates random topic)
$ python3 -u scripts/external_steering.py
🌍 EXTERNAL STEERING ACTIVE - Portable Skill
Topic (random): arena-steer-dd3b342e
Publish URL: https://ntfy.sh/arena-steer-dd3b342e

# Terminal 2: Steer from anywhere
$ curl -d "STOP: use vanilla JS not React" https://ntfy.sh/arena-steer-dd3b342e

# Terminal 1: Shows
🚨 STEERING RECEIVED at 20:15:14 [ktSc2uCA8njd]
STOP: use vanilla JS not React
```

Agent then reads STEERING.md and pivots.
