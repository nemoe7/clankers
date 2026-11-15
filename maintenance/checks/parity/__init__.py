"""Refs/live parity gates."""

from __future__ import annotations

from ..repo import Repo
from .prompts import check_system_prompt_parity
from .root_copies import check_root_copies
from .rules import check_rule_parity
from .skills import check_skills_parity


def check_parity(repo: Repo, errors: list[str]) -> None:
  check_rule_parity(repo, errors)
  check_system_prompt_parity(repo, errors)
  check_skills_parity(repo, errors)
  check_root_copies(repo, errors)
