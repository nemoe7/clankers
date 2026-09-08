#!/usr/bin/env python3
"""Lint an AGENT_HANDOFF.md against the agent-handoff model.

  handoff_lint.py DOC.md ...     lint; exit 0 = automated checks passed; manual review still required
  handoff_lint.py --template T   structure only, placeholders allowed
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
REQ = ["workstream-id", "handoff-id", "state", "from", "to", "created"]
TRANSITIONS = {
  "ACTIVE": {"PREPARING", "BLOCKED", "DONE"},
  "PREPARING": {"HANDED OFF", "ACTIVE", "BLOCKED", "DONE"},
  "HANDED OFF": {"ACCEPTED", "BLOCKED"},
  "ACCEPTED": {"ACTIVE", "BLOCKED"},
  "BLOCKED": {"ACCEPTED", "ACTIVE", "PREPARING", "DONE"},
  "DONE": set(),
}
STATES = set(TRANSITIONS)
WS_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
ID_RE = re.compile(r"^HANDOFF-(\d{3,})$")
PH = re.compile(r"<[A-Za-z][^<>\n]{0,78}>")
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
ATTEMPT_FIELDS = ["Action", "Expected", "Observed", "Conclusion", "Evidence", "Follow-up"]


def frontmatter(text):
  match = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", text, re.S)
  if not match:
    return {}, text
  meta = {}
  for line in match.group(1).splitlines():
    if ":" in line and not line.startswith(" "):
      key, _, val = line.partition(":")
      meta[key.strip()] = val.strip().strip("\"'").strip()
  return meta, text[match.end():]


def slice_ids(sec, prefix):
  """Return each entry's id and its own, unflattened field block."""
  matches = list(re.finditer(rf"(?m)^[ \t]*-[ \t]*({prefix}\d+)\.", sec))
  return [
    (match.group(1), sec[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(sec)])
    for i, match in enumerate(matches)
  ]


def missing_fields(block, fields):
  missing = []
  for field in fields:
    label = r"Stop(?: / rollback if)?" if field == "Stop" else re.escape(field)
    if not re.search(rf"(?m)^[ \t]*-[ \t]+{label}:[ \t]*\S[^\n]*$", block):
      missing.append(field)
  return missing


def lint_history(section, meta, err):
  rows = []
  for line in section.splitlines():
    if not line.startswith("|"):
      continue
    cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
    if cells[0] == "Handoff" or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
      continue
    if len(cells) != 5 or not all(cells) or not ID_RE.fullmatch(cells[0]):
      err.append("history needs five nonempty cells beginning with HANDOFF-NNN")
      continue
    rows.append(cells)
  if not rows:
    err.append("handoff history has no HANDOFF-NNN entry")
    return
  previous = None
  sent, accepted = set(), set()
  for identity, date, route, state, summary in rows:
    number = int(identity.split("-")[1])
    if number < 1:
      err.append("handoff ids start at HANDOFF-001")
    if state not in STATES:
      err.append(f"invalid history state: `{state}`")
    if previous:
      old_number, old_state = previous
      if number < old_number:
        err.append("new transfer ids must be increasing; older transfers cannot reappear")
      elif number > old_number and state != "PREPARING":
        err.append("a new transfer must start with a PREPARING event")
      elif number == old_number and state == "PREPARING" and identity in sent:
        err.append("preparing another transfer requires an increasing handoff id")
      if state != old_state and state not in TRANSITIONS.get(old_state, set()):
        err.append(f"invalid lifecycle transition: {old_state} -> {state}")
      if old_state == "DONE":
        err.append("invalid lifecycle transition: DONE is terminal")
    if state == "ACTIVE" and identity in sent and identity not in accepted:
      err.append("starting received work requires an acceptance event")
    if state == "HANDED OFF":
      sent.add(identity)
    if state == "ACCEPTED":
      accepted.add(identity)
    previous = number, state
    parties = re.split(r"[ \t]*(?:->|→)[ \t]*", route)
    if len(parties) != 2 or not all(parties):
      err.append("history From → To needs a sender and receiver")
  latest = rows[-1]
  for key, value in (("handoff-id", latest[0]), ("state", latest[3])):
    if value != meta.get(key):
      err.append(f"newest history {key} `{value}` != frontmatter `{meta.get(key, '')}`")
  parties = re.split(r"[ \t]*(?:->|→)[ \t]*", latest[2])
  if parties != [meta.get("from"), meta.get("to")]:
    err.append("newest history sender/receiver != frontmatter from/to")


def lint(text, template=False):
  """Return (errors, warnings). Checks are not a safety or truth guarantee."""
  text = text.lstrip("\ufeff").replace("\r\n", "\n")
  err, warn = [], []
  meta, body = frontmatter(text)
  if not meta:
    err.append("missing YAML frontmatter")
  for key in REQ:
    if not meta.get(key):
      err.append(f"missing or empty frontmatter field `{key}`")
  headings = list(re.finditer(r"(?m)^## ([^\n]+)$", body))
  sections, order = {}, []
  for index, match in enumerate(headings):
    title = re.sub(r"\s+\(.*\)$", "", match.group(1)).strip()
    if title not in SECTIONS:
      continue
    if title in sections:
      err.append(f"duplicate section `## {title}`")
    end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
    sections[title] = body[match.end():end]
    order.append(title)
  for title in SECTIONS:
    if title not in sections:
      err.append(f"missing section `## {title}`")
  if order != [title for title in SECTIONS if title in sections]:
    err.append("sections out of order")
  if template:
    return err, warn
  for key, ok in (("state", lambda v: v in STATES),
                  ("workstream-id", lambda v: bool(WS_RE.fullmatch(v))),
                  ("handoff-id", lambda v: bool(ID_RE.fullmatch(v)) and int(v.split("-")[1]) > 0)):
    val = meta.get(key, "")
    if val and not ok(val):
      err.append(f"invalid {key}: `{val}`")
  left = sorted(set(PH.findall(text)))
  if left:
    err.append(f"unfilled placeholders: {', '.join(left[:4])}")
  lint_history(sections.get("15. Handoff history", ""), meta, err)
  attempts = slice_ids(sections.get("8. Attempts", ""), "A")
  if not attempts:
    err.append("no attempts recorded (A1, A2, ...)")
  for aid, block in attempts:
    missing = missing_fields(block, ATTEMPT_FIELDS)
    if missing:
      err.append(f"{aid} missing or empty {', '.join(missing)}")
  for drid, block in slice_ids(sections.get("9. Do not repeat", ""), "DR"):
    for field in ("Reason ruled out", "Evidence"):
      if not re.search(rf"{field}:[ \t]*\S", block):
        err.append(f"{drid} needs {field}")
  actions = sections.get("11. Next actions", "")
  entries = list(re.finditer(r"(?m)^(\d+)\.[ \t]+([^\n]+)", actions))
  done = meta.get("state") == "DONE"
  if done and actions.strip() != "NONE":
    err.append("DONE requires Next actions to contain only NONE")
  if not entries and not done:
    err.append("next actions need an ordered `1. N1` entry (or NONE when DONE)")
  for index, entry in enumerate(entries, 1):
    if entry.group(1) != str(index) or not re.match(rf"N{index}\b", entry.group(2)):
      err.append("next actions must be ordered `1. N1`, `2. N2`, ...")
    end = entries[index].start() if index < len(entries) else len(actions)
    block = actions[entry.end():end]
    missing = missing_fields(block, ("Command", "Expected", "Validation", "Stop"))
    if missing:
      err.append(f"N{index} missing or empty {', '.join(missing)}")
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
  unknown = [f for f in flags if f not in ("--template", "--help", "-h")]
  if unknown:
    print(f"error: unknown flag {unknown[0]}\n\n{usage}", file=sys.stderr)
    return 2
  if "--help" in flags or "-h" in flags:
    print(usage)
    return 0
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


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
