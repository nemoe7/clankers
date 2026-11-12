"""Refs/live parity gates."""

from __future__ import annotations

from ..repo import Repo
from .prompts import check_system_prompt_parity
from .root_copies import check_root_copies
from .rules import check_rule_parity
from .skill_refs import check_skill_refs_parity

PARITY_CHECKS = (
  check_rule_parity,
  check_system_prompt_parity,
  check_skill_refs_parity,
  check_root_copies,
)


def check_parity(repo: Repo, errors: list[str]) -> None:
  for check in PARITY_CHECKS:
    check(repo, errors)
