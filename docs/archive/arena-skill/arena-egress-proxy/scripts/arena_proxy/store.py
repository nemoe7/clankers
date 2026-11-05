"""Small time-to-live store for staged blobs."""

import threading
import time
import uuid
from pathlib import Path

DEFAULT_TTL_SECONDS = 3600


class Store:
  """Hold staged bytes on disk and drop expired entries."""

  def __init__(self, directory, ttl=DEFAULT_TTL_SECONDS):
    self.directory = Path(directory)
    self.ttl = ttl
    self.blobs = {}
    self.lock = threading.Lock()

  def new_id(self):
    """Return a short random id for a staged blob."""
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

  def _prune_locked(self):
    cutoff = time.time() - self.ttl
    for blob_id in [key for key, value in self.blobs.items() if value["at"] < cutoff]:
      record = self.blobs.pop(blob_id)
      try:
        record["path"].unlink(missing_ok=True)
      except OSError:
        pass
