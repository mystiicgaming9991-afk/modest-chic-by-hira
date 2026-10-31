"""Unit tests for settings AES-256-GCM encryption utilities."""

import pytest

from modest_chic_backend.modules.settings.crypto import decrypt_setting_value, encrypt_setting_value


def _key() -> bytes:
    return b"a" * 32


def test_encrypt_decrypt_round_trip() -> None:
    """A plaintext value survives encryption and decryption."""
    key = _key()
    plaintext = {"api_key": "re_abc123xyz"}
    encrypted = encrypt_setting_value(key, plaintext)
    assert isinstance(encrypted, dict)
    assert encrypted["v"] == 1
    assert "ciphertext" in encrypted
    assert "nonce" in encrypted
    assert isinstance(encrypted["ciphertext"], str)
    assert isinstance(encrypted["nonce"], str)
    decrypted = decrypt_setting_value(key, encrypted)
    assert decrypted == plaintext


def test_encrypt_produces_unique_nonces() -> None:
    """Each encryption produces a unique nonce and ciphertext."""
    key = _key()
    plaintext = {"value": "same"}
    enc1 = encrypt_setting_value(key, plaintext)
    enc2 = encrypt_setting_value(key, plaintext)
    assert enc1["nonce"] != enc2["nonce"]
    assert enc1["ciphertext"] != enc2["ciphertext"]


def test_encrypt_handles_complex_json() -> None:
    """Nested objects, arrays, numbers, and booleans round-trip correctly."""
    key = _key()
    plaintext = {
        "string": "hello",
        "number": 42,
        "boolean": True,
        "null_value": None,
        "array": [1, 2, 3],
        "nested": {"a": {"b": "c"}},
    }
    encrypted = encrypt_setting_value(key, plaintext)
    decrypted = decrypt_setting_value(key, encrypted)
    assert decrypted == plaintext


def test_encrypt_handles_string_values() -> None:
    """Plain string values round-trip correctly."""
    key = _key()
    plaintext = "a plain string secret"
    encrypted = encrypt_setting_value(key, plaintext)
    decrypted = decrypt_setting_value(key, encrypted)
    assert decrypted == plaintext


def test_encrypt_handles_integer_values() -> None:
    """Plain integer values round-trip correctly."""
    key = _key()
    plaintext = 12345
    encrypted = encrypt_setting_value(key, plaintext)
    decrypted = decrypt_setting_value(key, encrypted)
    assert decrypted == 12345


def test_decrypt_rejects_wrong_key() -> None:
    """Decryption with a different key raises an error."""
    key1 = b"a" * 32
    key2 = b"b" * 32
    encrypted = encrypt_setting_value(key1, {"secret": "data"})
    with pytest.raises(ValueError, match="decryption failed"):
        decrypt_setting_value(key2, encrypted)


def test_decrypt_rejects_tampered_ciphertext() -> None:
    """A modified ciphertext raises a decryption error."""
    key = _key()
    encrypted = encrypt_setting_value(key, {"secret": "data"})
    tampered = dict(encrypted)
    tampered["ciphertext"] = encrypted["ciphertext"][:-1] + (
        "A" if encrypted["ciphertext"][-1] != "A" else "B"
    )
    with pytest.raises(ValueError):
        decrypt_setting_value(key, tampered)


def test_decrypt_rejects_missing_version_marker() -> None:
    """A payload without the version marker raises an error."""
    key = _key()
    with pytest.raises(ValueError, match="version"):
        decrypt_setting_value(key, {"ciphertext": "abc", "nonce": "xyz"})


def test_decrypt_rejects_unknown_version() -> None:
    """A payload with an unsupported version raises an error."""
    key = _key()
    with pytest.raises(ValueError, match="version"):
        decrypt_setting_value(key, {"v": 99, "ciphertext": "abc", "nonce": "xyz"})


def test_decrypt_requires_ciphertext_field() -> None:
    """Decryption requires the ciphertext field."""
    key = _key()
    with pytest.raises(ValueError, match="ciphertext"):
        decrypt_setting_value(key, {"v": 1, "nonce": "xyz"})


def test_decrypt_requires_nonce_field() -> None:
    """Decryption requires the nonce field."""
    key = _key()
    with pytest.raises(ValueError, match="nonce"):
        decrypt_setting_value(key, {"v": 1, "ciphertext": "abc"})
