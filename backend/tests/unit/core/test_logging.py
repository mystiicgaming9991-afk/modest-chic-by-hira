from modest_chic_backend.core.logging import redact_sensitive_fields


def test_redacts_secrets_and_personal_identifiers_recursively() -> None:
    event = {
        "event": "staff_login",
        "email": "staff@example.com",
        "password": "cleartext",
        "nested": {"refresh_token": "opaque", "totp_secret": "seed"},
    }

    redacted = redact_sensitive_fields(None, "info", event)

    assert redacted["email"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["nested"]["refresh_token"] == "[REDACTED]"
    assert redacted["nested"]["totp_secret"] == "[REDACTED]"


def test_redacts_secrets_in_structured_strings() -> None:
    redacted = redact_sensitive_fields(None, "info", {"message": "password=cleartext"})

    assert "cleartext" not in redacted["message"]
