# Reference - Arena Live Steering

## API

### Topic Generation

```python
from scripts.generate_topic import get_or_create_topic, generate_topic

# Generates random arena-steer-{8 hex}
topic = generate_topic()  # e.g. arena-steer-a1b2c3d4

# Gets existing or creates new, saves to multiple locations
topic = get_or_create_topic()
```

Locations checked/saved:
- `~/.steering_topic`
- `~/STEERING_TOPIC`
- `./.topic` (skill local)
- `./.steering_topic` (cwd)

### External Polling

```bash
# Start with random topic (auto-generated)
python3 -u scripts/external_steering.py

# Start with specific topic
NTFY_TOPIC=arena-steer-custom python3 -u scripts/external_steering.py

# Custom file locations
STEERING_FILE=/tmp/steering.md LOG_FILE=/tmp/log.md python3 -u scripts/external_steering.py
```

Polling details:
- Endpoint: `https://ntfy.sh/{TOPIC}/json?poll=1&since={last_id}`
- Interval: 3s normal, 10s backoff on 429
- Deduplication: seen_ids set + since param
- Writes to STEERING.md with header

### Steering File Format

`STEERING.md`:

```markdown
# LIVE STEERING NOTES

## Current Notes:

<!-- from ntfy:ID at TIMESTAMP -->
USER MESSAGE HERE
```

Agent should extract content after `## Current Notes:`.

### Agent Integration Patterns

**Minimal (bash):**
```bash
cat /home/user/STEERING.md
```

**Python:**
```python
with open("/home/user/STEERING.md") as f:
    content = f.read()
if "STOP:" in content.upper():
    # pivot
```

**With helper:**
```python
from scripts.check_steering import check_steering

notes = check_steering()
```

**Recommended agent loop:**
```python
for step in agent_loop:
  notes = check_steering()
  if "STOP:" in notes.upper():
    print("STOP detected, pivoting")
    # adjust plan
  # continue work
```

### ntfy.sh API

Publish:
```bash
curl -d "your message" https://ntfy.sh/TOPIC
curl -d "STOP: change" https://ntfy.sh/TOPIC -H "Title: Steering"
```

Poll (JSON):
```bash
curl -H "Accept: application/json" https://ntfy.sh/TOPIC/json?poll=1
# Returns JSON lines: {"id":"...","message":"...","time":...}
```

Web UI:
- https://ntfy.sh/TOPIC - publish from browser

Rate limits:
- ntfy.sh free tier: ~ 1 request per second per IP, 429 on exceed
- Our poller handles 429 with 10s backoff

### Security

- Topic is obscure, not encrypted
- Anyone with topic can publish
- Keep topic secret
- For private: generate longer random `uuid4().hex * 4` = 128 chars
- ntfy supports auth via `NTFY_AUTH` env (not implemented here, add if needed)

### Portable Skill Compliance

Follows https://agentskills.io/specification.md:

- Directory name matches skill name: `arena-live-steering`
- SKILL.md has required frontmatter: name, description
- Description includes when to use
- Frontmatter states the Arena-only scope in `description` and `compatibility`
- Scripts in `scripts/`
- References in `references/`
- No external deps (stdlib only)
- Random generation on first run

### Troubleshooting

**Arena client buggy:**
- File sync lag: Use external ntfy, not file explorer
- Preview not loading: No preview needed, use external URL
- 429 errors: Normal, poller backs off 10s

**Topic not working:**
- Check `cat .topic` exists
- Regenerate: `rm .topic ~/.steering_topic && python3 scripts/generate_topic.py`
- Test publish: `curl -d "TEST" https://ntfy.sh/$(cat .topic)`

**Agent not seeing steering:**
- Ensure agent reads STEERING.md every 1-2 steps
- Check poller running: `ps aux | grep external_steering`
- Check STEERING.md updated: `cat /home/user/STEERING.md`
