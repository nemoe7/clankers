"""OpenAI-compatible calls through the owner's endpoint, queued and polled.

The fetch tool waits on one request, so a model call would time out or die with
the connection. This module accepts a job, answers at once with its id, calls
the endpoint on a worker thread, and lets the agent poll for the result. Images
arrive as URLs and leave as data URIs, which gives a vision model the picture
while the Arena session stays text-only.
"""

import base64
import json
import queue
import threading
import urllib.error
import urllib.request

from . import transfers

PROMPT_CAP_CHARS = 8000
IMAGE_CAP_BYTES = 8_000_000
MAX_IMAGES = 4
TIMEOUT_SECONDS = 180
DEFAULT_SYSTEM = (
  "You are a review service for a coding agent that cannot see images or reach"
  " this service itself. Answer with direct, specific findings."
)


class LlmService:
  """Queue model jobs, run them on one worker thread, and keep their results."""

  def __init__(self, store, base_url, api_key, model, token="", api=""):
    self.store = store
    self.base_url = base_url.rstrip("/")
    self.api_key = api_key
    self.model = model
    self.token = token
    self.api = api
    self.queue = queue.Queue()
    self.started = False
    self.lock = threading.Lock()

  def enabled(self):
    """Report whether the owner configured an endpoint, a key and a model."""
    return bool(self.base_url and self.api_key and self.model)

  def submit(self, params):
    """Queue one job and return its id, or raise ValueError with the reason."""
    prompt = params.get("prompt", [""])[0]
    if not prompt:
      raise ValueError("prompt is required")
    if len(prompt) > PROMPT_CAP_CHARS:
      raise ValueError(f"prompt is over {PROMPT_CAP_CHARS} characters")
    images = params.get("image", [])
    if len(images) > MAX_IMAGES:
      raise ValueError(f"at most {MAX_IMAGES} images are allowed")
    job = {
      "status": "queued",
      "params": params,
      "prompt": prompt,
      "images": images,
      "model": params.get("model", [""])[0] or self.model,
      "text": "",
      "error": None,
    }
    job_id = self.store.put_job(job)
    self._ensure_worker()
    self.queue.put(job_id)
    return job_id

  def _ensure_worker(self):
    with self.lock:
      if self.started:
        return
      self.started = True
      threading.Thread(target=self._work, daemon=True).start()

  def _work(self):
    while True:
      job_id = self.queue.get()
      job = self.store.get_job(job_id)
      if job is None:
        continue
      job["status"] = "running"
      try:
        job["text"] = self._run(job)
        job["status"] = "done"
      except Exception as error:
        job["error"] = f"{type(error).__name__}: {error}"
        job["status"] = "error"

  def _run(self, job):
    system, context = self._context(job["params"])
    content = [{"type": "text", "text": job["prompt"] + context}]
    for url in job["images"]:
      data, content_type = transfers.fetch_url(url, IMAGE_CAP_BYTES)
      mime = content_type.split(";")[0] or "image/png"
      encoded = base64.b64encode(data).decode("ascii")
      content.append(
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}
      )
    messages = [
      {"role": "system", "content": system},
      {"role": "user", "content": content},
    ]
    max_tokens = job["params"].get("max_tokens", [""])[0]
    return self._chat(messages, job["model"], max_tokens)

  def _context(self, params):
    """Build the system line and any requested diff or file text."""
    from . import github_api

    system = params.get("system", [""])[0] or DEFAULT_SYSTEM
    repo = params.get("repo", [""])[0]
    pr = params.get("diff", [""])[0]
    path = params.get("file", [""])[0]
    if not (pr or path):
      return system, ""
    if not github_api.valid_repo(repo):
      raise ValueError("repo must look like owner/name when diff or file is set")
    text, error = github_api.pull_context(
      repo,
      pr=pr,
      path=path,
      ref=params.get("ref", [""])[0],
      token=self.token,
      api=self.api,
    )
    if error:
      raise ValueError(error)
    return f"{system}\n\nContext follows.\n\n{text}", ""

  def _chat(self, messages, model, max_tokens):
    body = {"model": model, "messages": messages}
    if max_tokens.isdigit():
      body["max_tokens"] = int(max_tokens)
    request = urllib.request.Request(
      f"{self.base_url}/chat/completions",
      data=json.dumps(body).encode(),
      headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {self.api_key}",
        "User-Agent": "arena-proxy/2",
      },
      method="POST",
    )
    try:
      with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
      raise ValueError(f"the endpoint answered HTTP {error.code}") from error
    except (TimeoutError, urllib.error.URLError) as error:
      raise ValueError(f"the endpoint is unreachable: {error}") from error
    try:
      return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
      raise ValueError("the endpoint answer held no choices") from error
