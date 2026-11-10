"""Exercise signed browser retry lifetimes without executing operations."""

import hashlib
import hmac

import pytest
from arena_steering.browser_retry import (
  TOKEN_LIFETIME_SECONDS,
  issue_token,
  verify_token,
)

SECRET = bytes(range(32))
GENERATION = "0123456789abcdef"


def test_signed_token_is_unique_and_has_the_approved_lifetime():
  token = issue_token(SECRET, GENERATION, 1000)
  assert token != issue_token(SECRET, GENERATION, 1000)
  result = verify_token(token, SECRET, GENERATION, 1000)
  assert result.generation == GENERATION
  assert result.issued_at == 1000
  assert result.expires_at == result.issued_at + TOKEN_LIFETIME_SECONDS
  assert verify_token(token, SECRET, GENERATION, result.expires_at - 1) == result
  with pytest.raises(ValueError):
    verify_token(token, SECRET, GENERATION, result.expires_at)


@pytest.mark.parametrize("candidate", ["", "unsigned", None, 123, "v1_" * 1000])
def test_unsigned_or_malformed_tokens_are_rejected(candidate):
  with pytest.raises(ValueError):
    verify_token(candidate, SECRET, GENERATION, 1000)


def test_signature_generation_and_future_issue_time_are_checked():
  token = issue_token(SECRET, GENERATION, 1000)
  for secret, generation, now in [
    (bytes(reversed(SECRET)), GENERATION, 1000),
    (SECRET, "fedcba9876543210", 1000),
    (SECRET, GENERATION, 999),
  ]:
    with pytest.raises(ValueError):
      verify_token(token, secret, generation, now)
  payload, signature = token.rsplit("_", 1)
  changed_signature = ("0" if signature[0] != "0" else "1") + signature[1:]
  with pytest.raises(ValueError):
    verify_token(f"{payload}_{changed_signature}", SECRET, GENERATION, 1000)


def test_signed_but_extended_lifetime_is_rejected():
  token = issue_token(SECRET, GENERATION, 1000)
  parts = token.split("_")
  parts[3] = f"{1000 + TOKEN_LIFETIME_SECONDS + 1:x}"
  payload = "_".join(parts[:-1])
  signature = hmac.digest(SECRET, payload.encode("ascii"), hashlib.sha256).hex()
  with pytest.raises(ValueError):
    verify_token(f"{payload}_{signature}", SECRET, GENERATION, 1000)


@pytest.mark.parametrize(
  "generation,now", [("invalid", 1000), (GENERATION, -1), (GENERATION, 2**48 - 1)]
)
def test_invalid_signing_state_cannot_issue_tokens(generation, now):
  with pytest.raises(ValueError):
    issue_token(SECRET, generation, now)
