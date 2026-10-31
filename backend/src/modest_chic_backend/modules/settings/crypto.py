"""AES-256-GCM encryption and decryption for secret store settings."""

import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_CURRENT_VERSION = 1


def encrypt_setting_value(key: bytes, value: Any) -> dict[str, Any]:
    """Encrypt a setting value with AES-256-GCM and return a versioned wrapper.

    The returned wrapper is a JSON-serializable dict:
        {"v": 1, "ciphertext": "<base64>", "nonce": "<base64>"}

    Args:
        key: 32-byte AES-256 key.
        value: Any JSON-serializable Python value.

    Returns:
        A dict with version marker, base64 ciphertext, and base64 nonce.
    """
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(key)
    plaintext = json.dumps(value).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return {
        "v": _CURRENT_VERSION,
        "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
    }


def decrypt_setting_value(key: bytes, wrapper: dict[str, Any]) -> Any:
    """Decrypt a versioned ciphertext wrapper and return the original value.

    Args:
        key: 32-byte AES-256 key.
        wrapper: A dict with "v", "ciphertext", and "nonce" keys.

    Returns:
        The original Python value.

    Raises:
        ValueError: If the wrapper is malformed, the version is unsupported,
                    or decryption fails.
    """
    if not isinstance(wrapper, dict):
        raise ValueError("expected a dict wrapper for decryption")
    version = wrapper.get("v")
    if version != _CURRENT_VERSION:
        raise ValueError(f"unsupported ciphertext version: {version}")
    ciphertext_b64 = wrapper.get("ciphertext")
    nonce_b64 = wrapper.get("nonce")
    if not ciphertext_b64:
        raise ValueError("missing ciphertext in encrypted wrapper")
    if not nonce_b64:
        raise ValueError("missing nonce in encrypted wrapper")

    try:
        ciphertext = base64.urlsafe_b64decode(ciphertext_b64)
        nonce = base64.urlsafe_b64decode(nonce_b64)
    except Exception as exc:
        raise ValueError("invalid base64 in encrypted wrapper") from exc

    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ValueError("decryption failed") from exc

    return json.loads(plaintext.decode("utf-8"))
