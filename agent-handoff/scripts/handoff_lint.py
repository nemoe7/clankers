#!/usr/bin/env python3
"""Lint an AGENT_HANDOFF.md against the agent-handoff model.

  handoff_lint.py DOC.md ...     lint; exit 0 = safe to send
  handoff_lint.py --template T   structure only, placeholders allowed
  handoff_lint.py --self-test    check the linter against built-in fixtures
"""

import re
import sys

SECTIONS = [
  "1. Handoff metadata", "2. Objective", "3. Current state", "4. Context",
  "5. Resources", "6. Completed work", "7. Decisions", "8. Attempts",
  "9. Do not repeat", "10. Unknowns, blockers, risks, decision triggers",
  "11. Next actions", "12. Definition of Done", "13. Validation",
  "14. Rollback / recovery", "15. Handoff history",
]
REQ = ["workstream-id", "handoff-id", "state", "from", "to"]
STATES = {"ACTIVE", "PREPARING", "HANDED OFF", "ACCEPTED", "BLOCKED", "DONE"}
WS_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
ID_RE = re.compile(r"^HANDOFF-(\d{3,})$")
PH = re.compile(r"<[A-Za-z][^<>\n]{0,78}>")
ALLOWED_PH = {"<sha>", "<commit>", "<pr>", "<issue>", "<date>", "<owner>"}
SECRET = [
  ("AWS key id", r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
  ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
  ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
  ("bearer token", r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}"),
  ("assigned secret",
   r"(?i)\b\w*(?:api[_-]?key|secret|passw(?:or)?d|token)\w*\b\s*[:=]\s*"
   r"""['"]?(?![<\s])[A-Za-z0-9+/_~.-]*[0-9+/_~=.-][A-Za-z0-9+/_~.-]{3,}"""),
]
VAGUE = r"(?i)investigate (this |the issue )?further|look into (it|this)|\bTBD\b"
ATTEMPT_FIELDS = ["Action", "Expected", "Observed", "Conclusion", "Evidence"]


def frontmatter(text):
  if not text.startswith("---"):
    return {}, text
  end = text.find("\n---", 3)
  if end < 0:
    return {}, text
  meta = {}
  for line in text[3:end].splitlines():
    if ":" in line and not line.startswith(" "):
      key, _, val = line.partition(":")
      meta[key.strip()] = val.strip().strip("\"'")
  return meta, text[end + 4:].lstrip("\n")


def slice_ids(sec, prefix):
  """Return (id, flattened text) for each `- <prefix>N.` entry in a section."""
  out = []
  for match in re.finditer(rf"(?m)^\s*-\s*({prefix}\d+)\.", sec):
    nxt = re.search(r"(?m)^\s*-\s*(?:A|DR)\d+\.", sec[match.end():])
    stop = match.end() + nxt.start() if nxt else len(sec)
    out.append((match.group(1), re.sub(r"\s+", " ", sec[match.end():stop])))
  return out


def lint(text, template=False):
  """Return (errors, warnings). `template` checks structure only."""
  text = text.lstrip("\ufeff")
  err, warn = [], []
  meta, body = frontmatter(text)
  if not meta:
    err.append("missing YAML frontmatter")
  for key in REQ:
    if key not in meta:
      err.append(f"missing frontmatter field `{key}`")
  for key, ok in (("state", lambda v: v in STATES),
                  ("workstream-id", lambda v: bool(WS_RE.match(v))),
                  ("handoff-id", lambda v: bool(ID_RE.match(v)))):
    val = meta.get(key, "")
    if val and not PH.search(val) and not ok(val):
      err.append(f"invalid {key}: `{val}`")
  found = [(body.find(f"## {s}"), s) for s in SECTIONS]
  for pos, sec in found:
    if pos < 0:
      err.append(f"missing section `## {sec}`")
  present = [s for p, s in sorted(found) if p >= 0]
  if present != [s for s in SECTIONS if s in present]:
    err.append("sections out of order")
  if template:
    return err, warn
  left = sorted({p for p in PH.findall(body) if p not in ALLOWED_PH})
  if left:
    err.append(f"unfilled placeholders: {', '.join(left[:4])}")
  ids = re.findall(r"HANDOFF-\d{3,}", body.rsplit("## 15.", 1)[-1])
  nums = [int(i.split("-")[1]) for i in ids]
  if not ids:
    err.append("handoff history has no HANDOFF-NNN entry")
  elif nums != sorted(set(nums)):
    err.append("history ids must be unique and increasing")
  elif meta.get("handoff-id") and ids[-1] != meta["handoff-id"]:
    err.append(f"newest history `{ids[-1]}` != frontmatter `{meta['handoff-id']}`")
  attempts = body.split("## 8. Attempts", 1)[-1].split("\n## ", 1)[0]
  if not slice_ids(attempts, "A"):
    err.append("no attempts recorded (A1, A2, ...)")
  for aid, block in slice_ids(attempts, "A"):
    missing = [f for f in ATTEMPT_FIELDS
               if not re.search(rf"(?:^|-)\s*{f}:", block)]
    if missing:
      err.append(f"{aid} missing {', '.join(missing)}")
  repeat = body.split("## 9. Do not repeat", 1)[-1].split("\n## ", 1)[0]
  for drid, block in slice_ids(repeat, "DR"):
    if "Reason ruled out" not in block or "Evidence" not in block:
      err.append(f"{drid} needs Reason ruled out and Evidence")
  actions = body.split("## 11. Next actions", 1)[-1].split("\n## ", 1)[0]
  if not re.search(r"(?m)^1\.\s*N\d+", actions):
    err.append("next actions need an ordered `1. N1` entry")
  else:
    first = actions.split("N1", 1)[1]
    for field in ("Command", "Expected", "Validation", "Stop"):
      if not re.search(rf"(?:^|-)\s*{field}[^\n:]*:", first):
        err.append(f"action 1 missing {field}")
  for label, pattern in SECRET:
    if re.search(pattern, text):
      err.append(f"possible {label}; remove it")
  hit = re.search(VAGUE, text)
  if hit:
    warn.append(f"vague instruction `{hit.group(0)}`; give a command")
  return err, warn


def main(argv):
  usage = __doc__.strip()
  flags = [a for a in argv if a.startswith("-")]
  paths = [a for a in argv if not a.startswith("-")]
  unknown = [f for f in flags if f not in ("--template", "--self-test", "--help", "-h")]
  if unknown:
    print(f"error: unknown flag {unknown[0]}\n\n{usage}", file=sys.stderr)
    return 2
  if "--help" in flags or "-h" in flags:
    print(usage)
    return 0
  if "--self-test" in flags:
    return self_test()
  if not paths:
    print(usage, file=sys.stderr)
    return 2
  bad = False
  for path in paths:
    try:
      with open(path, encoding="utf-8") as handle:
        text = handle.read()
    except OSError as exc:
      print(f"error: {exc}", file=sys.stderr)
      return 2
    err, warn = lint(text, template="--template" in flags)
    print(f"== {path}")
    for kind, items in (("ERROR", err), ("WARNING", warn)):
      for item in items:
        print(f"  {kind:7} {item}")
    if err:
      bad = True
      print(f"  FAIL: {len(err)} error(s)")
    elif not warn:
      print("  PASS")
  return 1 if bad else 0


GOOD = """---
workstream-id: ws-demo
handoff-id: HANDOFF-001
state: HANDED OFF
from: agent-a
to: agent-b
---

## 1. Handoff metadata
ws-demo, HANDOFF-001, HANDED OFF, agent-a to agent-b.

## 2. Objective
Ship signed webhooks with at-least-once delivery.

## 3. Current state
- Working: signature checks (`pytest tests/test_auth.py -q` -> 14 passed)
- Not working: retry queue drops the second attempt after a 503
- Branch / commit: `feat/hooks @ 9f2c1ab`

## 4. Context
- Constraints: keys stay in Vault

## 5. Resources
| Repository | `git@host.example:acme/api` | implementation |

## 6. Completed work
- Signature verification — evidence: 14 passed

## 7. Decisions
- D1. 2026-09-04 — HMAC-SHA256, 300s skew — Rationale: matches SDK — Status: ACTIVE

## 8. Attempts
- A1. 2026-09-05
  - Action: inline retry with sleep
  - Expected: second attempt delivered
  - Observed: consumer blocked 8s, message lost
  - Conclusion: inline retry cannot survive a restart
  - Evidence: logs/503.log
  - Follow-up: N1

## 9. Do not repeat
- DR1. Approach: inline retry — Reason ruled out: blocks the consumer —
  Evidence: A1 — Revisit if: delivery moves to a worker pool

## 10. Unknowns, blockers, risks, decision triggers
- Blockers: none
- If tenants deduplicate on event-id -> keep at-least-once delivery.

## 11. Next actions
1. N1 — agent-b
   - Command: pytest tests/test_retry.py -q
   - Expected: 1 failed with ConnectionResetError
   - Validation: matches logs/503.log
   - Stop / rollback if: the test passes

## 12. Definition of Done
- Retry test passes with a 503 injected

## 13. Validation
| Functional | signature accepted | pytest tests/test_auth.py -q | pass |

## 14. Rollback / recovery
- Trigger: duplicate delivery above 1 per event
- Steps: revert <sha>

## 15. Handoff history
| HANDOFF-001 | 2026-09-05 | agent-a -> agent-b | HANDED OFF | signing done |
"""

CASES = [
  ("good", "", 0, 0),
  ("bad state", ("state: HANDED OFF", "state: PAUSED"), 1, 0),
  ("reused handoff id", ("handoff-id: HANDOFF-001", "handoff-id: HANDOFF-007"), 1, 0),
  ("dropped section", ("## 8. Attempts", "## 8. Stuff"), 1, 0),
  ("attempt without evidence", ("  - Evidence: logs/503.log\n", ""), 1, 0),
  ("unfilled placeholder", ("ws-demo, HANDOFF-001", "ws-demo, <id>"), 1, 0),
  ("no attempts recorded", ("## 8. Attempts\n- A1.", "## 8. Attempts\n- none."), 1, 0),
  ("embedded secret", ("from: agent-a", "from: agent-a\nkey: AKIAABCDEFGHIJKLMNOP"), 1, 0),
  ("vague instruction", ("pytest tests/test_retry.py -q", "investigate further"), 0, 1),
]


def self_test():
  failed = 0
  for label, mutation, want_err, want_warn in CASES:
    text = GOOD.replace(*mutation, 1) if mutation else GOOD
    err, warn = lint(text)
    ok = (len(err) > 0) == bool(want_err) and (len(warn) > 0) == bool(want_warn)
    failed += not ok
    print(f"  {'PASS' if ok else 'FAIL'}  {label}"
          f"{' — ' + err[0] if err and not ok else ''}")
  print(f"\n{'ALL SELF-TESTS PASSED' if not failed else 'SELF-TESTS FAILED'} "
        f"({len(CASES) - failed}/{len(CASES)})")
  return 1 if failed else 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
