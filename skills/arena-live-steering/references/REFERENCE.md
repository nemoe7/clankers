# Reference - Arena Live Steering

## Steering file format

`STEERING.md`:

```markdown
# LIVE STEERING NOTES

## Current Notes:

<!-- from ntfy clankers-example, read 2026-09-17 06:15:48 -->
USER MESSAGE HERE
```

The agent reads everything after `## Current Notes:`. The file keeps its last 8,000 characters, while `STEERING_LOG.md` is append-only and keeps everything, including the per-message id that makes a restart deduplicate.

## Agent integration patterns

**Minimal (bash):**

```bash
cat reports/STEERING.md
```

**Python:**

```python
with open("reports/STEERING.md") as f:
  content = f.read()
if "STOP:" in content.upper():
  ...  # pivot
```

**With the helper:**

```python
from check_steering import check_steering

notes = check_steering()
```

**Recommended agent loop:**

```python
for step in agent_loop:
  # Pull the topic with page-fetch, at <topic>/json?poll=1&since=<lastmessage>,
  # and ingest the body; the ingester prints the id to anchor the next pull on.
  notes = check_steering()
  if "STOP:" in notes.upper():
    print("STOP detected, pivoting")
    # adjust plan
  # continue work
```

## ntfy transport

A topic on `ntfy.sh` is the channel, because the user's side needs nothing: no account, no token, no zone, no page of our own. Publishing is a POST to `https://ntfy.sh/<topic>` from ntfy's web UI, its phone app, or `curl -d "note" ntfy.sh/<topic>` on the user's own machine, and it is instant, where a DNS edit waits on a TTL; sandbox POSTs are TLS-killed. Messages are append-only, so a new note never rewrites the ones before it.

The topic name is the credential. ntfy has no sign-up, so anyone who knows the name can read and write it, which for a steering channel means anyone could inject directives. Generate a random one, give it to the user in chat, and keep it out of the repository: `reports/` is ignored, and a topic committed to a public repository is a public write access to the agent.

Reading is `https://ntfy.sh/<topic>/json?poll=1&since=<lastmessage>` only through the agent's page-fetch tool, where `<lastmessage>` is the newest message id the log already recorded and `since=all` is the form of the first read; `scripts/ntfy_steering.py` takes the returned body verbatim and prints the `Next pull:` URL for the read that follows. Never substitute curl or another in-sandbox HTTP client: the egress proxy answers ntfy GETs with HTTP 200 and an empty body even while the topic holds messages, including with cache-busting parameters and `Cache-Control: no-cache`, so a sandbox poller silently mistakes filtered messages for no messages. Use the poll form: plain `/json` is a stream that never terminates and a page fetch cannot return one, and `/atom` and `/feed.xml` are 404 on `ntfy.sh`. An empty topic returns an empty body, which the page-fetch tool can report as its own HTTP 500; an anchored read with no new messages therefore looks like a 500 rather than an OK empty result, and that artifact is not evidence ntfy is unreachable. The channel is sent to the user in chat before the first read, because a read fails until the user has published something: the agent cannot post to a topic, so that first empty-topic 500 is the expected state of a fresh channel, not a fault to debug. Messages carry an `expires` field: 12.0 hours after `time`, measured on 2026-09-16, so the notes file is the archive and the topic is not.

Anchoring is what ntfy's own docs tell a repeated poller to do: a poll without `since=` re-reads the topic's whole cache every time, a replay returns only the newest messages that fit 10 MB per topic and flags a capped response with `X-Messages-Truncated: 1`, and replayed bytes count against the visitor's daily bandwidth budget (https://docs.ntfy.sh/subscribe/api/, read 2026-09-18). An anchor that has aged out of the cache is not a hole: the server's since-ID query is `id > COALESCE((SELECT id FROM messages WHERE mid = ?), 0) AND published = 1`, so an id it no longer holds resolves to `0` and the whole cache comes back, which the message-id dedup then absorbs (`binwiederhier/ntfy` `message/cache_sqlite.go` on `main`, read 2026-09-18). Two consequences. A message recorded without an ntfy id is stamped `digest-...` and is never used as an anchor, because the server cannot resolve it, so such a body leaves the anchor where it was. And the log, not a state file, is the anchor store: losing it costs one full read, never a note.

Check at the start of every turn, after every reasoning block, before and after every tool call, and before the turn ends or anything expensive or hard to undo such as a push, rewrite, delete, or long build. Every check is a pull of the topic link: reading `STEERING.md` alone is not a check, because the notes file only holds what some earlier read delivered, and no check is skipped because the last read came back empty or because the next call looked short. After a blocking tool call such as a question, read right after it returns rather than before it, because nothing new can arrive while it blocks; a read spent just before a blocking call is wasted. The pull is anchored on the newest message id the log recorded, which returns only what is new, and that is what makes a read at every boundary affordable: the cadence is unconditional precisely because the read stopped costing the whole cache, and message-id dedup keeps an overlapping read safe. There is no background capture, so the turn-boundary check is what keeps a note from being read a turn late; the closing check is the one that makes the acknowledgment clause work, because a note sent while the agent was busy is otherwise acked later still, which from the user's side looks like the channel dropped it.

An acknowledgement is chat text. The clause is satisfied only by a line in the reply the user reads: a reasoning block that weighs the note, a tool call that ingests it, a note written into `STEERING.md`, and a summary that arrives a turn late are all silent to the person who sent it, and this channel carries no receipt of its own. That is why the clause names the medium and not only the wording: the failure it prevents is an agent that read the note, acted on it, and said nothing, which from the sending side is indistinguishable from the channel dropping the message. Only a delivered note earns the line; an empty pull has nothing to confirm, so it goes unmentioned rather than reported.

Verified live on 2026-09-16 in `nemoe7/daedalus`: the agent's page-fetch path returned all 6 real messages from a populated topic on its first attempt, and `scripts/ntfy_steering.py` ingested 6/6 from that body verbatim and deduplicated them by ntfy message id. In the same minute, every in-sandbox curl GET of `/json?poll=1&since=all` returned HTTP 200 with zero bytes, including cache-busting parameters and no-cache headers.

The `since=<lastmessage>` anchor is documented by ntfy and read from its server source on 2026-09-18, not measured end to end: the read path is GET-only, so a second message cannot be published to a fresh topic to produce a two-read sequence. The ingester's own behaviour is exercised instead, by feeding it a fenced poll body twice against a scratch log.

### Environment

- `STEERING_FILE` - default `STEERING.md` in the working directory; point it at a path the repository ignores, such as `reports/`
- `LOG_FILE` - default `STEERING_LOG.md`, append-only, keeps what the notes cap discards, the message ids a restart recovers, and the `since=` anchor the next read is built from
- `STEERING_NTFY_TOPIC` - the topic name notes are attributed to; it never leaves the machine
- `STEERING_NTFY_BASELINE` - `empty` (default) delivers everything unseen; `current` holds what the topic already holds, recording those ids in the log so a later run does not deliver them either

### Behaviour

- The input is the page-fetch body verbatim, with or without the markdown code fence a fetch tool tends to wrap around it
- Messages are deduplicated by ntfy's message id, which cannot collide; a message without one falls back to a digest of its text, so it is still deduplicated rather than replayed
- Every run prints `Next pull: <url>`, anchored on the newest real id the log holds and `since=all` while it holds none, so reads chain without an id being remembered between them and a digest stamp is never offered to the server as an anchor
- `open` and `keepalive` events are skipped, and a message's title is kept above its text
- An empty body is reported as an empty topic rather than as a failure, because the fetch tool renders an empty 200 as its own HTTP 500
- Notes are attributed `<!-- from ntfy {topic}, read {utc} -->`, and `STOP:`, `PRIORITY:`, and `CONTEXT:` are echoed as directives
- A failed fetch is not an empty topic: the two are indistinguishable in-sandbox, which is why only the page-fetch path is trusted for reads

## Channels measured and not shipped

Every alternative was measured in this sandbox on 2026-09-16 and is recorded so nobody re-tries it. None is shipped.

| Channel | Result | Evidence |
| --- | --- | --- |
| `ntfy.sh` topic, from a process in the sandbox | GET is a fake empty 200; POST is TLS-closed; only page-fetch reads correctly | Measured 2026-09-16 against the same populated topic in `nemoe7/daedalus`: every in-sandbox curl GET of `/<topic>/json?poll=1&since=all` returned HTTP 200 with a zero-byte body while the agent's page-fetch path returned all 6 real messages on its first try. Cache-busting query parameters and `Cache-Control: no-cache` did not change the empty 200, so it is filtering rather than caching alone and no in-sandbox HTTP poller is trustworthy. `scripts/ntfy_steering.py` ingested that page-fetch body verbatim, delivered 6/6, and deduplicated by message id. In-sandbox publishing remains impossible: POST was TLS-killed with curl exit 35 on 3/3 attempts. An actually empty page-fetch body, including a `since=<timestamp>` poll with no new messages, still renders as the tool's HTTP 500 artifact |
| Continuous capture through a browser relay | Built, verified, then removed on instruction | The relay served a preview page from `0.0.0.0:8765`; the user's browser subscribed to the topic over SSE and forwarded each message to the sandbox, which wrote `STEERING.md`. It was the only background capture, and it needed an open preview tab to stay alive; with the rule's own cadence pulling the topic directly at every reasoning block and every tool call, a note waits at most one of those boundaries, so the extra process, port, and tab were dropped. The Arena client's previews have also proved unreliable, and a closed tab is a silent failure mode, where the page-fetch path cannot silently die |
| GitHub issue body or comments | Declined by the user | Built, verified, and removed on instruction. `api.github.com` answers 200, so it works where it is wanted |
| GitHub gist, from a process in the sandbox | Unreachable three ways, and readable by the agent anyway | `gist.github.com` and `gist.githubusercontent.com`, which is the host that serves public raw gist content, are both TLS-closed, so a record being public does not help. And `api.github.com/gists` answers 403 `Resource not accessible by integration` for GET, POST, and PATCH, with no way to drop to an anonymous read: the sandbox's network path injects the installation identity into every `api.github.com` request. The agent's own page-fetch path is not behind that allowlist: it retrieved a public gist's raw content and a DNS-over-HTTPS answer from `dns.google` without difficulty, which makes a gist a usable inbound fallback for an agent with a fetch tool and an unusable one for any process in the sandbox |
| Local web inbox on a sandbox port | Declined by the user | The Arena client's previews proved unreliable in another session. `e2b.app` is also TLS-closed from inside, so the sandbox cannot reach its own proxy |
| Paste, key-value, chat, webhook, and push hosts | Unreachable | `cl1p.net`, `kvdb.io`, `paste.rs`, `0x0.st`, `hastebin.com`, `dpaste.org`, `ix.io`, `textdb.online`, `jsonblob.com`, `api.telegram.org`, `discord.com`, `matrix.org`, `hooks.slack.com`, `api.pushover.net`, `api.pushbullet.com`, `webhook.site`, `script.google.com`, `docs.google.com`, `googleapis.com`: all exit 35 |
| DNS TXT record with an in-sandbox poller | Verified live, then removed on instruction | A TXT record over UDP/53 was the one channel a process in the sandbox could poll by itself, since DNS is not filtered there; the poller wrote notes with digest dedup. It lost its place once the page-fetch path was measured to reach ntfy directly, because it needed a zone the user could edit, a TTL of latency per edit, a running process, and a public record that anyone who knew the name could read and rewrite |
| npm or PyPI as a note carrier | Reachable, not built | Both answer 200 unauthenticated and expose versions, descriptions, and timestamps, so a published release could carry a note. Rejected as one publish per steer, needing an account and a terminal, so a phone cannot drive it |

From a process in the sandbox the reachable hosts are exactly `github.com`, `api.github.com`, `pypi.org`, and `registry.npmjs.org`, and nothing was done to route around that, since an egress allowlist is a security control rather than an obstacle. The agent's page-fetch tool is a different path and is not confined the same way: it reached `dns.google` and `gist.githubusercontent.com`, both closed to the sandbox's own sockets, on 2026-09-16. That makes it the read path for this channel, and it is why an empty answer from an in-sandbox client is not evidence that a topic is empty.

The ntfy route, measured on 2026-09-16, has three hard edges. GET and POST fail differently inside the sandbox: the egress proxy gives GETs a fake empty HTTP 200 even for a topic with messages, while POSTs are TLS-killed with curl exit 35. Only the agent's page-fetch path reads correctly, so use it at the cadence above; never infer that a topic is empty from an in-sandbox HTTP response. The agent cannot publish through its GET-only fetch path, so the first message still comes from the user. Use the poll form of the endpoint, `<topic>/json?poll=1&since=<lastmessage>`, because the plain `<topic>/json` is a stream that stays open forever and a page fetch cannot return one; `/atom` and `/feed.xml` are 404 on `ntfy.sh`, and a no-new-messages body can render as the fetch tool's HTTP 500 artifact, which an anchored read makes the common case rather than the rare one: an empty result says nothing new arrived, not that the channel is down. `scripts/ntfy_steering.py` ingests the body, strips the markdown fence a page-fetch tool wraps around it, skips `open` and `keepalive` events, keeps a message's title, and deduplicates by ntfy's message id, falling back to a digest of the text for a message that has none.

## Security

- The topic name is a capability: obscure, not encrypted, and public to anyone who learns it
- Notes are plaintext in the topic, so they must never carry a secret, a token, or a private path
- Anyone who knows the topic can read and post notes; there is no authentication beyond the name itself
- The scripts write only to the two files they are given, and both belong under a path the repository ignores

## Portable skill compliance

Follows https://agentskills.io/specification.md:

- Directory name matches the skill name: `arena-live-steering`
- `SKILL.md` carries the required frontmatter, `name` and `description`, and the description states when to use it and when not to
- The frontmatter states the Arena-only scope in `description` and `compatibility`
- Scripts live in `scripts/`, references in `references/`
- Stdlib only, so there is nothing to install

## Troubleshooting

**No note arrives:**

- Confirm the user published to the topic the agent posted, and read the same topic name
- An empty page-fetch body renders as the tool's HTTP 500, so retry once and check the topic through the agent's page-fetch path before concluding anything
- Because an in-sandbox GET returns a fake empty 200, never test the channel with curl inside the sandbox

**The same note arrives twice:**

- Id dedup suppresses repeats, so the usual cause is a `LOG_FILE` that moved: the ids live there, and losing them replays what the log already recorded. A moved log resets the anchor to `since=all` too, which is one full read, not a lost note

**Agent not seeing steering:**

- Ensure the agent pulls the link at the card's cadence: turn start, every reasoning block, before and after every tool call, and before turn end. Reading `STEERING.md` is not a check; only a pull asks the topic whether anything is new
- Check the ingest step ran and its `STEERING_FILE` is the path the agent reads
- If a note is believed missing, pull once with `since=all`: dedup makes the replay harmless, and it rules the anchor out as the cause
