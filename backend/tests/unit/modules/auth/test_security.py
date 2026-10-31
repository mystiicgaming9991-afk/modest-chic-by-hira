from datetime import UTC, datetime, timedelta

import pytest

from modest_chic_backend.modules.auth.security import (
    create_access_token,
    create_opaque_token,
    hash_password,
    hash_token,
    normalize_email,
    validate_password,
    verify_access_token,
    verify_password,
)


def test_normalize_email_trims_and_casefolds() -> None:
    assert normalize_email("  Staff@Example.COM ") == "staff@example.com"


@pytest.mark.parametrize("password", ["short", "x" * 73, "é" * 37])
def test_password_policy_rejects_short_or_over_72_utf8_bytes(password: str) -> None:
    with pytest.raises(ValueError):
        validate_password(password)


def test_password_hash_uses_bcrypt_cost_12() -> None:
    password = "secure-and-correct-horse"

    hashed = hash_password(password)

    assert hashed.startswith("$2b$12$")
    assert verify_password(password, hashed)
    assert not verify_password("incorrect-password", hashed)


def test_opaque_token_has_high_entropy_and_hash_is_one_way() -> None:
    token = create_opaque_token()

    assert len(token) >= 40
    assert hash_token(token) != token
    assert hash_token(token) == hash_token(token)


def test_access_token_pins_algorithm_and_required_claims() -> None:
    now = datetime.now(UTC)
    token = create_access_token(
        subject="staff-id",
        session_id="session-id",
        signing_key="s" * 32,
        now=now,
        expires_at=now + timedelta(minutes=15),
    )

    claims = verify_access_token(token, "s" * 32, now=now)

    assert claims["sub"] == "staff-id"
    assert claims["session_id"] == "session-id"
    assert claims["exp"] == int((now + timedelta(minutes=15)).timestamp())


def test_expired_access_token_is_rejected() -> None:
    now = datetime.now(UTC)
    token = create_access_token(
        subject="staff-id",
        session_id="session-id",
        signing_key="s" * 32,
        now=now - timedelta(minutes=20),
        expires_at=now - timedelta(minutes=5),
    )

    with pytest.raises(ValueError):
        verify_access_token(token, "s" * 32, now=now)
