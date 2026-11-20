"""Refs/live parity gates."""

from __future__ import annotations

from ..repo import Repo
from ..report import Notes
from .prompts import check_system_prompt_parity
from .root_copies import check_root_copies
from .rules import check_rule_parity
from .skills import check_skills_parity


def check_parity(repo: Repo, errors: list[str], notes: Notes | None = None) -> None:
  owned = notes is None
  notes = notes or Notes()
  check_rule_parity(repo, errors, notes)
  check_system_prompt_parity(repo, errors, notes)
  check_skills_parity(repo, errors, notes)
  check_root_copies(repo, errors)
  if owned:
    notes.flush()
