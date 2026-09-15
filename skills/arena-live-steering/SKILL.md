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

Steer the Arena agent WITHOUT interrupting its turn, even when Arena client is buggy. Uses external ntfy.sh channel with random topic generation.

## When to use this skill

- Arena client file sync or previews are buggy
- User wants to steer agent mid-turn without clicking interrupt
- Need external control from phone/browser
- User says "steer without interrupting" or "live steering"
- Need random private channel per session

## How it works

1. **Random topic generation**: On first run, generates `arena-steer-{8 hex}` via `uuid4().hex[:8]` - 4B combinations
2. **External poller**: Polls `https://ntfy.sh/TOPIC/json?poll=1` every 3s, deduplicates via seen_ids + since param
3. **Writes to STEERING.md**: Agent checks this file every 1-2 tool calls
4. **User publishes**: From any browser/phone at `https://ntfy.sh/TOPIC` - no login needed

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
- `scripts/install.sh` - Installer
- `scripts/check_steering.py` - Agent helper
- `references/REFERENCE.md` - Detailed reference
- `assets/qr.png` - QR code for publish URL (generated on install)

## Environment Variables

- `NTFY_TOPIC` - Override random topic
- `STEERING_FILE` - Override STEERING.md path (default: /home/user/STEERING.md)
- `LOG_FILE` - Override log path (default: /home/user/STEERING_LOG.md)
- `PORT` - For optional web UI (if you add steering_server.py)

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
