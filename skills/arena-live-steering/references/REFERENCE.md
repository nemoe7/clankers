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

### GitHub transport

`scripts/github_steering.py` carries the same notes over one GitHub issue or pull request, for a sandbox whose egress allowlist blocks `ntfy.sh`. Observed in an Arena sandbox on 2026-09-16 in `nemoe7/clankers`: `ntfy.sh` and `gist.github.com` close the TLS connection (curl exit 35, HTTP 000), while `github.com` and `api.github.com` answer 200.

Body mode, the default, leaves nothing behind: the user edits one issue description from any browser or phone, and each change becomes a note. Comment mode is opt-in and costs one comment per note, unless the user keeps editing a single comment, which the poller also picks up.

```bash
# body mode, the default
STEERING_REPO=owner/name STEERING_ISSUE=14 \
  STEERING_FILE=reports/STEERING.md LOG_FILE=reports/STEERING_LOG.md \
  POLL_INTERVAL=5 python3 -u scripts/github_steering.py

# comment mode
STEERING_SOURCE=comments STEERING_REPO=owner/name STEERING_ISSUE=14 \
  STEERING_FILE=reports/STEERING.md python3 -u scripts/github_steering.py
```

Environment:

- `GH_TOKEN` or `GITHUB_TOKEN` - required, any token that can read the repository; an Arena session already carries one
- `STEERING_REPO` - required, `owner/name`
- `STEERING_ISSUE` - required, issue or pull request number
- `STEERING_SOURCE` - `body` (default) or `comments`
- `STEERING_FILE` - default `STEERING.md` in the working directory; point it at a path the repository ignores, such as `reports/`
- `LOG_FILE` - default `STEERING_LOG.md`, append-only, keeps what the notes cap discards, and in comment mode carries the per-comment digest that makes a restart edit-aware
- `POLL_INTERVAL` - seconds, default 5
- `STEERING_IGNORE_AUTHORS` - comment mode only: comma separated logins skipped on top of the default rule that skips every `[bot]` login, so the agent's own comments never steer it

Behaviour:

- Body mode polls `GET /repos/{owner}/{name}/issues/{number}` and comment mode `GET .../issues/{number}/comments?per_page=50&since={last created_at}`, both with `If-None-Match` from the previous ETag, so an unchanged poll returns 304 and costs nothing against the 5,400-request hourly limit measured for an installation token
- Body mode baselines the description at startup, then ingests the lines after the longest line prefix it has already seen: appending a line, replacing the whole description, and rewriting the middle all deliver the new tail, while deleting lines delivers nothing
- Comment mode ingests a comment when its body digest is new or changed, so an edited comment is a note, and recovers its digest table from the log on restart
- Notes are attributed: `<!-- from gh issue body, read {utc} -->`, or `<!-- from gh:{id} by {login} at {created}, read {utc} -->` with ` edited` when a known comment changed
- `STOP:`, `PRIORITY:`, and `CONTEXT:` in a note are echoed to the poller's stdout as directives
- `scripts/steering_notes.py` writes the notes for every GitHub mode, so the header, the append, and the 8,000-character cap cannot drift between them
- 401 and 404 exit with GitHub's answer rather than retrying silently; 403 waits 60s; a network error backs off in steps to 60s

Permissions measured for an Arena installation token in `nemoe7/clankers`, which decide how a channel is set up:

- Issues: read yes, write no. `POST /repos/{owner}/{name}/issues` answers 403 `Resource not accessible by integration`, so a human creates the inbox and the agent only reads it
- Pull requests: read and write yes, including the description through `PATCH /repos/{owner}/{name}/pulls/{number}`
- Contents: write yes, so the agent can push a branch
- That split is useful: on an issue channel the agent cannot write the body it reads, so it cannot steer itself

Hazards:

- Never point body mode at a description the agent itself writes, such as the pull request it is updating. A body carries no editor attribution, so the agent's own edit arrives as a note and steers it. Stop the poller around such a write, or watch a different issue
- A note written while the poller is down is not replayed, because body mode baselines whatever it finds at startup. Keep the poller running for the whole session and restart it only around a write
- The channel needs a human with edit access to the repository; the poller only reads

Verified in an Arena sandbox on 2026-09-16 in `nemoe7/clankers`: a seven-check assert demo over `added_lines`, `digest`, the note and log round trip through `load_seen`, a body-mode log line not colliding with the comment seen set, `ignored`, and the tail cap; and one live run against pull request 13, in which a description edit became an attributed note in `reports/STEERING.md` within 12s with its `STOP:` directive echoed, and restoring the description produced no note. Not exercised: an edit made by a human from a browser or phone, which is GitHub's own behaviour rather than this skill's.

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

**ntfy.sh unreachable:**
- Sandbox egress is allowlisted: `curl https://ntfy.sh` fails with exit 35 and HTTP 000
- Use `scripts/github_steering.py` in body mode instead: it needs only `api.github.com` and leaves no comments

**Topic not working:**
- Check `cat .topic` exists
- Regenerate: `rm .topic ~/.steering_topic && python3 scripts/generate_topic.py`
- Test publish: `curl -d "TEST" https://ntfy.sh/$(cat .topic)`

**Agent not seeing steering:**
- Ensure agent reads STEERING.md every 1-2 steps
- Check poller running: `ps aux | grep external_steering`
- Check STEERING.md updated: `cat /home/user/STEERING.md`
