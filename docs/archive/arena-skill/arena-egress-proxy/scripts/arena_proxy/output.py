"""Bound serialized replies, and select fields without changing upstream reads."""

import json
import urllib.parse


class OutputError(ValueError):
  pass


MAX_CHARS = 16_000
MAX_ITEMS = 20
EXCERPT_CHARS = 240


def serialize(value):
  return json.dumps(value, indent=2) + "\n"


def link(route, **params):
  return route + "?" + urllib.parse.urlencode(params, doseq=True)


def text_page(text, offset, metadata, following):
  if offset < 0 or offset > len(text):
    raise OutputError("offset is out of range")

  def payload(end):
    complete = end == len(text)
    return dict(
      metadata,
      text=text[offset:end],
      complete=complete,
      next=None if complete else following(end),
    )

  low, high = offset, len(text)
  while low < high:
    end = (low + high + 1) // 2
    if len(serialize(payload(end))) <= MAX_CHARS:
      low = end
    else:
      high = end - 1
  result = payload(low)
  if len(serialize(result)) > MAX_CHARS or (low == offset and low < len(text)):
    raise OutputError("response metadata exceeds the output limit")
  return result


def item_page(items, offset, metadata, following, *, key="items", upstream=None):
  if offset < 0 or offset > len(items):
    raise OutputError("offset is out of range")

  def payload(end):
    remaining = end < len(items)
    next_url = following(end) if remaining else upstream
    return dict(
      metadata, **{key: items[offset:end]}, complete=not next_url, next=next_url
    )

  end = offset
  while end < min(len(items), offset + MAX_ITEMS):
    if len(serialize(payload(end + 1))) > MAX_CHARS:
      break
    end += 1
  result = payload(end)
  if len(serialize(result)) > MAX_CHARS or (end == offset and end < len(items)):
    raise OutputError("selected record exceeds the output limit; select fewer fields")
  return result


def pointer(value, path):
  if path == "":
    return value
  if not path.startswith("/"):
    raise OutputError("field must be a JSON pointer")
  for part in path[1:].split("/"):
    if any(suffix[:1] not in ("0", "1") for suffix in part.split("~")[1:]):
      raise OutputError("invalid JSON pointer escape")
    part = part.replace("~1", "/").replace("~0", "~")
    if isinstance(value, list):
      if (
        not part.isascii()
        or not part.isdecimal()
        or (len(part) > 1 and part.startswith("0"))
      ):
        raise KeyError(path)
      if len(part) > len(str(len(value))):
        raise IndexError(path)
      value = value[int(part)]
    elif isinstance(value, dict):
      value = value[part]
    else:
      raise KeyError(path)
  return value


def fields(value):
  if isinstance(value, dict):
    return ["/" + key.replace("~", "~0").replace("/", "~1") for key in sorted(value)]
  if isinstance(value, list):
    return ["/" + str(index) for index in range(len(value))]
  return [""]


def project(value, selected):
  result, partial = {}, False
  for path in selected:
    try:
      item = pointer(value, path)
    except (KeyError, IndexError):
      continue
    if isinstance(item, str) and len(item) > EXCERPT_CHARS:
      item = item[:EXCERPT_CHARS] + "…"
      partial = True
    elif isinstance(item, (list, dict)):
      item = {
        "type": "array" if isinstance(item, list) else "object",
        "count": len(item),
      }
      partial = True
    current = result
    parts = path[1:].split("/") if path else ["value"]
    for part in parts[:-1]:
      part = part.replace("~1", "/").replace("~0", "~")
      if not isinstance(current.get(part), dict):
        current[part] = {}
      current = current[part]
    current[parts[-1].replace("~1", "/").replace("~0", "~")] = item
  return result, partial


PROFILES = {
  "code-scanning-alert-items": (
    "/number",
    "/state",
    "/rule/id",
    "/rule/description",
    "/rule/severity",
    "/rule/security_severity_level",
    "/tool/name",
    "/most_recent_instance/ref",
    "/most_recent_instance/commit_sha",
    "/most_recent_instance/message/text",
    "/most_recent_instance/location/path",
    "/most_recent_instance/location/start_line",
    "/most_recent_instance/location/end_line",
    "/html_url",
  ),
  "code-scanning-alert-instance": (
    "/ref",
    "/state",
    "/commit_sha",
    "/message/text",
    "/location/path",
    "/location/start_line",
    "/location/end_line",
  ),
  "secret-scanning-alert": (
    "/number",
    "/state",
    "/secret_type",
    "/secret_type_display_name",
    "/validity",
    "/resolution",
    "/locations_url",
  ),
  "secret-scanning-location": (
    "/type",
    "/details/path",
    "/details/start_line",
    "/details/end_line",
    "/details/commit_sha",
    "/details/blob_url",
    "/details/commit_url",
    "/details/html_url",
    "/details/discussion_body_url",
    "/details/discussion_comment_url",
    "/details/discussion_title_url",
    "/details/issue_body_url",
    "/details/issue_comment_url",
    "/details/issue_title_url",
    "/details/pull_request_body_url",
    "/details/pull_request_comment_url",
    "/details/pull_request_review_url",
    "/details/pull_request_review_comment_url",
    "/details/pull_request_title_url",
    "/details/page_url",
  ),
  "artifact": (
    "/id",
    "/name",
    "/size_in_bytes",
    "/expired",
    "/expires_at",
    "/workflow_run/id",
    "/workflow_run/head_sha",
    "/archive_download_url",
  ),
  "job": (
    "/id",
    "/run_id",
    "/name",
    "/workflow_name",
    "/head_sha",
    "/head_branch",
    "/run_attempt",
    "/status",
    "/conclusion",
    "/created_at",
    "/started_at",
    "/completed_at",
    "/html_url",
  ),
  "workflow-run": (
    "/id",
    "/name",
    "/display_title",
    "/event",
    "/head_branch",
    "/head_sha",
    "/run_number",
    "/run_attempt",
    "/status",
    "/conclusion",
    "/created_at",
    "/updated_at",
    "/run_started_at",
    "/html_url",
  ),
}


def profile(path):
  if "/code-scanning/alerts" in path:
    return (
      "code-scanning-alert-instance"
      if path.endswith("/instances")
      else "code-scanning-alert-items"
    )
  if "/secret-scanning/alerts" in path:
    return (
      "secret-scanning-location"
      if path.endswith("/locations")
      else "secret-scanning-alert"
    )
  if "/actions/" in path:
    if "/artifacts" in path:
      return "artifact"
    if "/jobs" in path:
      return "job"
    if "/runs" in path:
      return "workflow-run"
  return None


def defaults(name, row):
  selected = PROFILES[name]
  if name != "secret-scanning-location":
    return selected
  urls = [path for path in selected if path.endswith("_url")]
  selected = [path for path in selected if path not in urls]
  for path in urls:
    try:
      if pointer(row, path):
        return selected + [path]
    except (KeyError, IndexError):
      pass
  return selected


def records(value):
  if isinstance(value, list):
    return value
  if isinstance(value, dict):
    for name in ("workflow_runs", "jobs", "artifacts", "items"):
      if isinstance(value.get(name), list):
        return value[name]
  return [value]


def number(params, name):
  try:
    value = int(params.get(name, ["0"])[0])
  except ValueError as error:
    raise OutputError(f"{name} must be a whole number") from error
  if value < 0:
    raise OutputError(f"{name} must not be negative")
  return value
