"""Signed double-submit CSRF token generation and verification."""

import hashlib
import hmac
import secrets


def create_csrf_token(signing_key: str) -> str:
    """Create a signed unpredictable token to share between cookie and request header."""
    nonce = secrets.token_urlsafe(24)
    signature = hmac.new(
        signing_key.encode("utf-8"), nonce.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{nonce}.{signature}"


def verify_csrf_token(token: str, signing_key: str) -> bool:
    """Verify the signature on a CSRF token without timing-sensitive string comparison."""
    try:
        nonce, supplied_signature = token.rsplit(".", maxsplit=1)
    except ValueError:
        return False
    expected_signature = hmac.new(
        signing_key.encode("utf-8"), nonce.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return bool(nonce) and hmac.compare_digest(supplied_signature, expected_signature)
