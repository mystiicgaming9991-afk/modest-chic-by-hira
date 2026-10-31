from modest_chic_backend.modules.outbox.crypto import decrypt_payload, encrypt_payload


def test_outbox_sensitive_payload_is_encrypted_and_round_trips() -> None:
    payload = {"recipient": "staff@example.com", "reset_token": "do-not-store-plaintext"}
    encryption_key = b"e" * 32

    ciphertext = encrypt_payload(payload, encryption_key)

    assert "do-not-store-plaintext" not in ciphertext
    assert decrypt_payload(ciphertext, encryption_key) == payload


def test_outbox_payload_rejects_wrong_encryption_key() -> None:
    ciphertext = encrypt_payload({"token": "one-time-secret"}, b"e" * 32)

    try:
        decrypt_payload(ciphertext, b"x" * 32)
    except ValueError:
        return
    raise AssertionError("decryption with an unrelated key must fail")
