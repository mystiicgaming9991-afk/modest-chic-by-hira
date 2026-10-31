from datetime import UTC, datetime

import pyotp

from modest_chic_backend.modules.auth.totp import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    verify_totp_code,
)


def test_totp_secret_is_encrypted_and_round_trips() -> None:
    secret = pyotp.random_base32()
    encrypted = encrypt_totp_secret(secret, b"t" * 32)

    assert secret not in encrypted
    assert decrypt_totp_secret(encrypted, b"t" * 32) == secret


def test_totp_accepts_current_code_once_and_rejects_replay() -> None:
    now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).at(now)

    counter = verify_totp_code(secret, code, now=now, last_counter=None)

    assert counter is not None
    assert verify_totp_code(secret, code, now=now, last_counter=counter) is None


def test_totp_rejects_invalid_code() -> None:
    now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)

    assert verify_totp_code("JBSWY3DPEHPK3PXP", "000000", now=now, last_counter=None) is None
