"""AES-GCM-protected TOTP enrollment and replay-aware code verification."""

import base64
import hmac
import os
from datetime import UTC, datetime

import pyotp
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TOTP_INTERVAL_SECONDS = 30


def encrypt_totp_secret(secret: str, encryption_key: bytes) -> str:
    """Encrypt a base32 seed with AES-256-GCM and a fresh nonce."""
    _validate_key(encryption_key)
    nonce = os.urandom(12)
    ciphertext = AESGCM(encryption_key).encrypt(nonce, secret.encode("ascii"), None)
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"v1:{encoded}"


def decrypt_totp_secret(encrypted_secret: str, encryption_key: bytes) -> str:
    """Authenticate and decrypt one stored TOTP secret."""
    _validate_key(encryption_key)
    if not encrypted_secret.startswith("v1:"):
        raise ValueError("unsupported encrypted TOTP secret version")
    try:
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_secret[3:].encode("ascii"))
        plaintext = AESGCM(encryption_key).decrypt(encrypted_bytes[:12], encrypted_bytes[12:], None)
        return plaintext.decode("ascii")
    except (InvalidTag, ValueError, UnicodeDecodeError) as error:
        raise ValueError("TOTP secret could not be authenticated") from error


def verify_totp_code(
    secret: str,
    code: str,
    *,
    now: datetime,
    last_counter: int | None,
) -> int | None:
    """Return a matched time counter only when valid and not previously consumed."""
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    if now.tzinfo is None:
        raise ValueError("TOTP verification time must be timezone-aware")
    current_counter = int(now.astimezone(UTC).timestamp()) // TOTP_INTERVAL_SECONDS
    totp = pyotp.TOTP(secret, interval=TOTP_INTERVAL_SECONDS)
    matched_counter: int | None = None
    for counter in range(max(0, current_counter - 1), current_counter + 2):
        expected = totp.at(counter * TOTP_INTERVAL_SECONDS)
        if hmac.compare_digest(expected, code):
            matched_counter = counter
    if matched_counter is None or (last_counter is not None and matched_counter <= last_counter):
        return None
    return matched_counter


def _validate_key(encryption_key: bytes) -> None:
    """Require exactly 256 bits of AES key material."""
    if len(encryption_key) != 32:
        raise ValueError("TOTP encryption key must contain exactly 32 bytes")
