"""Authenticated encryption for outbox payloads containing one-time secrets."""

import base64
import json
import os
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_payload(payload: dict[str, Any], encryption_key: bytes) -> str:
    """Encrypt a JSON payload using AES-GCM and a fresh 96-bit nonce."""
    _validate_key(encryption_key)
    nonce = os.urandom(12)
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ciphertext = AESGCM(encryption_key).encrypt(nonce, plaintext, None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_payload(ciphertext: str, encryption_key: bytes) -> dict[str, Any]:
    """Decrypt and parse an outbox payload, rejecting tampering or key mismatch."""
    _validate_key(encryption_key)
    try:
        encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
        plaintext = AESGCM(encryption_key).decrypt(encrypted_bytes[:12], encrypted_bytes[12:], None)
        payload = json.loads(plaintext)
    except (InvalidTag, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("outbox payload could not be authenticated") from error
    if not isinstance(payload, dict):
        raise ValueError("outbox payload must be a JSON object")
    return payload


def _validate_key(encryption_key: bytes) -> None:
    """Require the AES-256 key size used by the outbox encryption contract."""
    if len(encryption_key) != 32:
        raise ValueError("outbox encryption key must contain exactly 32 bytes")
