# Reference - Arena Live Steering

## Steering file format

`STEERING.md`:

```markdown
# LIVE STEERING NOTES

## Current Notes:

<!-- from dns txt steering.example.com, read 2026-09-16 07:15:48 -->
USER MESSAGE HERE
```

The agent reads everything after `## Current Notes:`. The file keeps its last 8,000 characters, while `STEERING_LOG.md` is append-only and keeps everything, including the per-value digest that makes a restart deduplicate.

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
  notes = check_steering()
  if "STOP:" in notes.upper():
    print("STOP detected, pivoting")
    # adjust plan
  # continue work
```

## ntfy transport, the default

A topic on `ntfy.sh` is the default channel, because the user's side needs nothing: no account, no token, no zone, no page of our own. Publishing is a POST to `https://ntfy.sh/<topic>` from ntfy's web UI, its phone app, or `curl -d "note" ntfy.sh/<topic>`, and it is instant, where a DNS edit waits on a TTL. Messages are append-only, so a new note never rewrites the ones before it, and there is no 255-octet character-string to split.

The topic name is the credential. ntfy has no sign-up, so anyone who knows the name can read and write it, which for a steering channel means anyone could inject directives. Generate a random one, give it to the user in chat, and keep it out of the repository: `reports/` is ignored, and a topic committed to a public repository is a public write access to the agent.

Reading is `https://ntfy.sh/<topic>/json?poll=1&since=all` through the agent's page-fetch path, then `scripts/ntfy_steering.py` on the body. Use the poll form: plain `/json` is a stream that never terminates and a page fetch cannot return one, and `/atom` and `/feed.xml` are 404 on `ntfy.sh`. An empty topic returns an empty body, which a page-fetch tool can report as its own HTTP 500, and `httpbin.org/status/200` fails identically, so that error is not evidence ntfy is unreachable. Messages carry an `expires` field: 12.0 hours after `time`, measured on 2026-09-16, so the notes file is the archive and the topic is not.

Check at the start of every turn, once more before the turn ends, and before anything expensive or hard to undo; do not poll in between. A read costs a network round trip inside the turn, and waiting loses nothing, since `since=all` returns everything the cache still holds. The closing check is the one that makes the acknowledgment clause work: without it a note sent while the agent was busy is read a turn late and acked later still, which from the user's side looks like the channel dropped it.

Verified live on 2026-09-16 in `nemoe7/clankers`: seven messages published by the user from a browser were read in one poll, ingested into the same notes and log files the DNS poller writes, and a second ingest of the same body delivered nothing, which is dedup by ntfy's message id working on real ids rather than on synthetic ones.

## DNS TXT transport, the fallback

`scripts/dns_steering.py` carries notes over one DNS TXT record, for a sandbox whose egress allowlist blocks HTTP entirely. Measured in an Arena sandbox on 2026-09-16 in `nemoe7/clankers`: `ntfy.sh`, three public ntfy instances, and 23 other notification, paste, chat, webhook, Google, and `e2b.app` hosts all close the TLS connection (curl exit 35, HTTP 000), while a TXT query to the resolver answers in about 1 ms. DNS is the only external channel a *process* in the sandbox can use, which is not the same as the only channel an agent can read: the page-fetch path reached `dns.google`, `gist.githubusercontent.com`, and `ntfy.sh` on the same day, all three closed to these sockets.

```bash
STEERING_DNS_NAME=steering.example.com POLL_INTERVAL=30 \
  STEERING_FILE=reports/STEERING.md LOG_FILE=reports/STEERING_LOG.md \
  python3 -u scripts/dns_steering.py
```

### Getting a record to watch

The user needs one zone they can edit. A domain they already own works; so does a free dynamic DNS zone, which is what was used for the live verification here. The sandbox never contacts the provider, so the provider being HTTP-blocked there does not matter.

Measured from this sandbox, apexes that are delegated and therefore usable: `dynv6.com`, `nsupdate.info`, `us.kg`, `eu.org`, `pp.ua`, `is-a.dev`, `js.org`, `thedev.id`, `42web.io`. Apexes that returned NXDOMAIN, so nothing under them can resolve: `dynv6.net`, `dns.army`, `dns.navy`. A delegated apex is not required for a delegated child: `dns.army` is NXDOMAIN at its apex while `steering.vlht-mrsv.dns.army` resolves, because each hostname is its own zone with `SOA ns1.dynv6.net` and `NS ns1-3.dynv6.com`.

Check a candidate name before waiting on it, since a dead name and an empty record both read as nothing:

```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); import dns_steering as d; print(d.query_records(sys.argv[1], 16, d.read_resolvers(), 5))" steering.example.com
```

`(3, [])` is NXDOMAIN, `(0, [])` is a live name with no TXT record yet, and `(0, ['...'])` is a value. The poller prints the same distinction at startup and warns loudly on NXDOMAIN.

### Sending a note from your own machine

The provider's own panel is the sending UI, and a one-line API call is the fast path. A single-file page of our own was built for this route and then removed: a browser cannot call the provider's API at all, since dynv6 answers the CORS preflight with an empty `Access-Control-Allow-Origin`, and its `GET /api/update` is the dyndns2 protocol, which carries `ipv4` and `ipv6` and never a TXT value, so the page could only ever render a terminal command for the user to run elsewhere. What it did uniquely was verify over DNS-over-HTTPS, and with ntfy as the default route the verification is the provider's own UI confirming the post instantly. If this route is ever needed again, the sending side is:

```bash
curl -sS -X PATCH "https://dynv6.com/api/v2/zones/$ZONE/records/$RECORD" \
  -H "Authorization: Bearer $DYNV6_TOKEN" -H "Content-Type: application/json" \
  --data-binary "$(python3 -c 'import json,sys; print(json.dumps({"data":sys.argv[1]}))' "$NOTE")"
```

The note travels as `argv` rather than through a pipe or a heredoc, since the stdin form appends a newline to every note. That quoting was tested against a note carrying an apostrophe, a newline, a double quote, a backslash, an unexpanded `$VAR`, an unexecuted backtick, and a non-ASCII character, all of which round-tripped byte-exact.

### Environment

- `STEERING_DNS_NAME` - required, the record to watch; underscores are allowed, so `_steer.example.com` works too
- `STEERING_FILE` - default `STEERING.md` in the working directory; point it at a path the repository ignores, such as `reports/`
- `LOG_FILE` - default `STEERING_LOG.md`, append-only, keeps what the notes cap discards and the digests a restart recovers
- `POLL_INTERVAL` - seconds, default 30, and see the query-volume hazard below before making it faster
- `DNS_RESOLVER` - override the resolver; by default the `nameserver` lines of `/etc/resolv.conf` are tried in order, with 8.8.8.8 as the fallback
- `DNS_TIMEOUT` - seconds per query, default 5
- `STEERING_DNS_BASELINE` - `current` (default) or `empty`

### Behaviour

- The value is every TXT record on the name, sorted and joined by newlines, so a multi-string record reads as one note and record order cannot churn the digest
- `current` holds the value found at startup without ingesting it, so a stale note is never replayed. `empty` ingests whatever the record holds on the first poll, which is what you want when you set the record before starting the agent
- A change delivers the lines after the longest line prefix already seen: appending a line delivers that line alone, replacing the record delivers the new text, clearing it delivers nothing
- Each delivered value's digest is written to the log and recovered on restart, so a value seen once is never delivered twice. That is what makes the cache disagreement below survivable, and it means re-setting an old value does nothing: change one character to send a note again
- Notes are attributed `<!-- from dns txt {name}, read {utc} -->`, and `STOP:`, `PRIORITY:`, and `CONTEXT:` are echoed as directives
- A failed query prints one line and retries next interval; it never exits, never clears the notes, and never moves the baseline, so a transient failure cannot replay the whole record as one note on the next answer. `query_records` returns the rcode with the values, and `query_txt` returns `None` when no resolver answered versus an empty string when the name holds no TXT record, because the two are not the same fact
- Labels are checked against the 63-octet DNS limit before the query, so a typo fails loudly rather than sending a malformed packet
- The startup probe retries NXDOMAIN up to three times before telling the user the channel is dead, because one answer is not trustworthy: a name that had just delivered three notes answered NXDOMAIN once at startup and NOERROR on the twelve queries around it. Any other rcode is believed at once, so a healthy start costs one query and no sleep

### Hazards

- A TXT record is public: anyone who knows the name can read every note, and anyone who can edit the zone can steer the agent. Treat the name as a capability, and never steer with a secret in the text
- The resolver caches for the TTL, so latency is the TTL and not the poll interval. Measured on a dynv6 zone: a 60s record TTL and a 180s SOA minimum, so an edit takes up to a minute and a newly created name up to three
- Two caches can disagree. Measured live: 40 queries of one name returned the current value 22 times and the previous value 18 times, six minutes after the edit, which delivered the same note repeatedly until digest dedup was added. Expect it after every edit and rely on the dedup
- DNS carries no author, so a note is attributed to the record name, not to a person
- One character-string is 255 octets. Providers split longer values and the poller rejoins them, which a 370-character multi-line note confirmed live, but a provider that rejects long values will cap the note
- Only the configured resolver answers in a sandbox like this: 8.8.8.8 replied in about 1 ms, while 1.1.1.1, 8.8.4.4, and 9.9.9.9 timed out, as did all three authoritative `ns*.dynv6.com` servers. So the channel is read-only from the sandbox: no RFC 2136 update, no TSIG, and no way for the agent to write a question back into DNS
- A resolver that answers inconsistently can also fake an NXDOMAIN at startup, which is why the probe confirms it, and can fake a cleared record mid-run, which is why the dedup and the untouched baseline exist
- Polling a free provider's zone hard may cost the zone. Measured 2026-09-16: after roughly 500 queries of one name in 25 minutes, at 8-10s intervals plus four ad-hoc test loops, every name under that zone began answering NOERROR with no records of any type, including names that had never been queried and the zone's own SOA, while random names under three other zones still returned NXDOMAIN correctly and every control name still resolved. So the zone stayed delegated and went empty. Whether that is provider-side throttling or a policy in the sandbox's resolver path cannot be told from inside, and the user had deleted nothing. The mitigations are the slower default poll, checking the provider's panel or DoH from a browser before blaming the poller, and treating a suddenly empty zone as a rate limit to wait out rather than a channel to rebuild

### Verified

In an Arena sandbox on 2026-09-16 in `nemoe7/clankers`, against a real dynv6 zone the user edited from their own browser:

- The full loop, human end included. `STEERING TEST` became an attributed note within one poll interval, a second edit 30s later became a second note, and a third, longer edit arrived with its blank lines and a 370-character multi-string value intact
- Deduplication under a live cache disagreement: 25 polls while the resolver alternated between two values delivered one note, and a warm restart that recovered the digest from the log delivered nothing
- A fourteen-check assert demo over the read path (`_dmarc.gmail.com`, an absent name, a multi-string record, the label guard), the change semantics (first, unchanged, append, clear, replace), the failure semantics (a failed query leaves the baseline intact; a late baseline in both modes; unreachable versus empty), the notes and log round trip, and the shared log format still parsing for the digest recovery
- The startup report telling NXDOMAIN, an empty record, and a value apart, retrying a lone NXDOMAIN before believing it, and both error paths exiting 1 with a clear message
- Four further checks over the probe: a lying NXDOMAIN retried into the truth, a genuinely dead name still warning after three agreeing queries, a healthy name costing one query and no sleep, and the live name answering NOERROR with no record on the first attempt

## Channels measured and not shipped

Every alternative was measured in this sandbox on 2026-09-16 and is recorded so nobody re-tries it. None is shipped.

| Channel | Result | Evidence |
| --- | --- | --- |
| `ntfy.sh` topic, from a process in the sandbox | TLS-closed to sockets, readable by the agent | Every instance closed the TLS handshake for the sandbox's own connections, curl exit 35, HTTP 000, while TCP to port 443 connected, so it is a filter and not a dead network; `ntfy.envs.net` and `ntfy.tilde.team` are closed too, which is why the channel was dropped. The agent's page-fetch path is not confined the same way and loaded `https://ntfy.sh/<topic>`, returning that topic's empty state on 2026-09-16, so an external message channel is readable agent-side. The JSON form `/<topic>/json?poll=1&since=all` reported HTTP 500 on an empty topic, and that is an artifact of the read path rather than of ntfy: the same tool reports HTTP 500 for `httpbin.org/status/200`, a 200 with an empty body, so an empty topic and an unreachable host look identical from in here. What has not been proven is a topic with a message in it, which needs one publish from outside the sandbox. Reading happens only when the agent acts, so no poller can be built on it |
| GitHub issue body or comments | Declined by the user | Built, verified, and removed on instruction. `api.github.com` answers 200, so it works where it is wanted |
| GitHub gist, from a process in the sandbox | Unreachable three ways, and readable by the agent anyway | `gist.github.com` and `gist.githubusercontent.com`, which is the host that serves public raw gist content, are both TLS-closed, so a record being public does not help. And `api.github.com/gists` answers 403 `Resource not accessible by integration` for GET, POST, and PATCH, with no way to drop to an anonymous read: the sandbox's network path injects the installation identity into every `api.github.com` request, measured by sending both an invalid and an empty `Authorization` header and getting the App's 5,400-request limit and the same 403 each time. What that verdict got wrong, measured the same day: the agent's own page-fetch path does not sit behind the same allowlist, and it retrieved a public gist's raw content and a DNS-over-HTTPS answer from `dns.google` without difficulty. So a gist is a usable inbound fallback for an agent that has a fetch tool and an unusable one for any process in the sandbox, which is also why no poller can be built on either |
| Local web inbox on a sandbox port | Declined by the user | The Arena client's previews proved unreliable in another session. `e2b.app` is also TLS-closed from inside, so the sandbox cannot reach its own proxy |
| Paste, key-value, chat, webhook, and push hosts | Unreachable | `cl1p.net`, `kvdb.io`, `paste.rs`, `0x0.st`, `hastebin.com`, `dpaste.org`, `ix.io`, `textdb.online`, `jsonblob.com`, `api.telegram.org`, `discord.com`, `matrix.org`, `hooks.slack.com`, `api.pushover.net`, `api.pushbullet.com`, `webhook.site`, `script.google.com`, `docs.google.com`, `googleapis.com`: all exit 35 |
| npm or PyPI as a note carrier | Reachable, not built | Both answer 200 unauthenticated and expose versions, descriptions, and timestamps, so a published release could carry a note. Rejected as one publish per steer, needing an account and a terminal, so a phone cannot drive it |

From a process in the sandbox the reachable hosts are exactly `github.com`, `api.github.com`, `pypi.org`, and `registry.npmjs.org`, and nothing was done to route around that, since an egress allowlist is a security control rather than an obstacle. The agent's page-fetch tool is a different path and is not confined the same way: it reached `dns.google` and `gist.githubusercontent.com`, both closed to the sandbox's own sockets, on 2026-09-16. That makes it the fallback read for this channel when the sandbox's resolver path goes blind, as `https://dns.google/resolve?name=<record>&type=TXT`, and it is why an empty answer from a poller is not evidence that a record is empty.

Reading the record when the sandbox cannot see it is a two-step procedure, both steps measured on 2026-09-16. Fetch `https://dns.google/resolve?name=<record>&type=TXT` through the agent's page-fetch path, which returns the JSON answer even though `dns.google` is closed to the sandbox's sockets, and parse `Answer[].data` with the same presentation-format unescaping the sending page does. Do this at a turn boundary instead of trusting a poller that reported no data: ten queries from inside the sandbox returned the live record's value five times and NOERROR-with-no-data five times, every answer inside two milliseconds, while `_dmarc.google.com`, the zone apex, and `example.com` answered correctly on every attempt. An empty answer from the sandbox is evidence about the observer rather than about the record, and a note can sit undelivered through a run of blinks when the poller is the only reader.

The ntfy route, measured on 2026-09-16, is the portable alternative and has three hard edges. `ntfy.sh` is TLS-closed to every socket in the sandbox, curl exit 35 with HTTP 000 while TCP to port 443 connects, so no poller can watch a topic and the read happens through the agent's page-fetch path at a turn boundary. That path is GET-only, so the agent can never publish: there is no outbound relay, no way to acknowledge a note through the same channel, and no way to prefill a fresh topic, which leaves the first message to the user. A relay through CI was considered and rejected on two grounds: repository secrets answer 403 for this installation token, so the topic would have to be committed, and ntfy's own documentation says the topic is essentially a password, since anyone who knows it can both read and write. Use the poll form of the endpoint, `<topic>/json?poll=1&since=all`, because the plain `<topic>/json` is a stream that stays open forever and a page fetch cannot return one; `/atom` and `/feed.xml` are 404 on `ntfy.sh`. `scripts/ntfy_steering.py` ingests the body, strips the markdown fence a page-fetch tool wraps around it, skips `open` and `keepalive` events, keeps a message's title, and deduplicates by ntfy's message id, falling back to a digest of the text for a message that has none.

## Security

- The record name is a capability: obscure, not encrypted, and public to anyone who learns it
- Notes are plaintext in a public DNS record, so they must never carry a secret, a token, or a private path
- Anyone who can edit the zone can steer the agent; the zone's own account is the only authentication there is
- The poller writes only to the two files it is given, and both belong under a path the repository ignores

## Portable skill compliance

Follows https://agentskills.io/specification.md:

- Directory name matches the skill name: `arena-live-steering`
- `SKILL.md` carries the required frontmatter, `name` and `description`, and the description states when to use it and when not to
- The frontmatter states the Arena-only scope in `description` and `compatibility`
- Scripts live in `scripts/`, references in `references/`
- Stdlib only, so there is nothing to install

## Troubleshooting

**No note arrives after an edit:**

- Check the name matches `STEERING_DNS_NAME` exactly, including any leading `steering.` inside the zone
- Check the TTL has expired; a 60s record needs up to a minute, and a name created moments ago needs the zone's negative-cache TTL, 180s on dynv6
- Read the poller's startup lines: `NXDOMAIN` means the name does not exist, and `resolves (NOERROR) but holds no TXT record yet` means the record type or host field is wrong
- Confirm from the sandbox with the `query_records` one-liner above; if it sees the value and the poller does not, the digest was already delivered, so change one character

**The same note arrives twice:**

- Two caches disagreeing is normal after an edit; digest dedup suppresses it, so an old poller process is the usual cause. Restart it after changing the script

**Nothing resolves at all:**

- Only the resolver in `/etc/resolv.conf` answers here. Set `DNS_RESOLVER` to that address if the file is unreadable, and do not expect 1.1.1.1 to work

**Agent not seeing steering:**

- Ensure the agent reads `STEERING.md` every one or two steps
- Check the poller is running and its `STEERING_FILE` is the path the agent reads
