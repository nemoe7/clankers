"""The repository tree every check reads. Tests pass a temporary root instead of patching globals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Vendored agent-facing skills live only under `.agents/skills/`. The checks never read them:
# they are not owner skills, so they are neither checked nor listed in `skills/README.md`.


@dataclass(frozen=True)
class Repo:
  root: Path

  @property
  def readme(self) -> Path:
    return self.root / "README.md"

  @property
  def docs(self) -> Path:
    return self.root / "docs"

  @property
  def skills(self) -> Path:
    return self.root / "skills"

  @property
  def rules(self) -> Path:
    return self.root / "rules"

  @property
  def rule_refs(self) -> Path:
    return self.rules / "refs"

  @property
  def system_prompts(self) -> Path:
    return self.root / "system-prompts"

  def relative(self, path: Path) -> str:
    """Return a POSIX label, or the plain path when it lies outside the root."""
    if path.is_relative_to(self.root):
      return path.relative_to(self.root).as_posix()
    return str(path)


DEFAULT_ROOT = Path(__file__).resolve().parents[2]
