"""Small time-to-live stores for staged blobs and background jobs."""

import threading
import time
import uuid
from pathlib import Path

DEFAULT_TTL_SECONDS = 3600


class Store:
  """Hold staged bytes on disk and job records in memory, and drop expired entries."""

  def __init__(self, directory, ttl=DEFAULT_TTL_SECONDS):
    self.directory = Path(directory)
    self.ttl = ttl
    self.blobs = {}
    self.jobs = {}
    self.lock = threading.Lock()

  def new_id(self):
    """Return a short random id for a blob or a job."""
    return uuid.uuid4().hex[:16]

  def put_blob(self, data):
    """Write bytes to the state directory and return their id and size."""
    blob_id = self.new_id()
    path = self.directory / f"{blob_id}.bin"
    path.write_bytes(data)
    with self.lock:
      self.blobs[blob_id] = {"path": path, "size": len(data), "at": time.time()}
      self._prune_locked()
    return blob_id, len(data)

  def get_blob(self, blob_id):
    """Return one live blob record, or None when it is unknown or expired."""
    with self.lock:
      self._prune_locked()
      return self.blobs.get(blob_id)

  def put_job(self, record):
    """Store a job record under a fresh id and return that id."""
    job_id = self.new_id()
    record["at"] = time.time()
    with self.lock:
      self.jobs[job_id] = record
      self._prune_locked()
    return job_id

  def get_job(self, job_id):
    """Return one live job record, or None when it is unknown or expired."""
    with self.lock:
      self._prune_locked()
      return self.jobs.get(job_id)

  def _prune_locked(self):
    cutoff = time.time() - self.ttl
    for blob_id in [key for key, value in self.blobs.items() if value["at"] < cutoff]:
      record = self.blobs.pop(blob_id)
      try:
        record["path"].unlink(missing_ok=True)
      except OSError:
        pass
    for job_id in [key for key, value in self.jobs.items() if value["at"] < cutoff]:
      self.jobs.pop(job_id)
