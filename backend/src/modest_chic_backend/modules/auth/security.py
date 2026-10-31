"""Password, token, and access-token primitives for staff authentication."""

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

import bcrypt
import jwt

BCRYPT_WORK_FACTOR = 12
JWT_ALGORITHM = "HS256"
MIN_PASSWORD_CHARACTERS = 12
MAX_PASSWORD_UTF8_BYTES = 72


def normalize_email(email: str) -> str:
    """Return the canonical lookup form used for staff email identity."""
    return email.strip().lower()


def validate_password(password: str) -> None:
    """Reject passwords outside the minimum-length and bcrypt byte-size policy."""
    if len(password) < MIN_PASSWORD_CHARACTERS:
        raise ValueError("password must contain at least 12 characters")
    if len(password.encode("utf-8")) > MAX_PASSWORD_UTF8_BYTES:
        raise ValueError("password must not exceed 72 UTF-8 bytes")


def hash_password(password: str) -> str:
    """Return a bcrypt digest after validating the password policy."""
    validate_password(password)
    digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_WORK_FACTOR))
    return digest.decode("ascii")


def verify_password(password: str, hashed_password: str) -> bool:
    """Compare a candidate password with a bcrypt digest without leaking mismatch details."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("ascii"))
    except (ValueError, TypeError):
        return False


def create_opaque_token() -> str:
    """Generate a high-entropy URL-safe bearer secret for one-time or refresh use."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return a SHA-256 hex digest suitable for unique credential-table storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    subject: str,
    session_id: str,
    signing_key: str,
    now: datetime,
    expires_at: datetime,
) -> str:
    """Sign a short-lived access JWT with stable identity and session claims."""
    issued_at = _to_utc(now)
    expiration = _to_utc(expires_at)
    if expiration <= issued_at:
        raise ValueError("access token expiry must be after issue time")
    return jwt.encode(
        {
            "sub": subject,
            "session_id": session_id,
            "iat": int(issued_at.timestamp()),
            "exp": int(expiration.timestamp()),
            "jti": secrets.token_urlsafe(16),
        },
        signing_key,
        algorithm=JWT_ALGORITHM,
    )


def verify_access_token(
    token: str, signing_key: str, *, now: datetime | None = None
) -> dict[str, Any]:
    """Verify a JWT using only the configured algorithm and required claims."""
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "session_id", "iat", "exp", "jti"]},
            leeway=0,
        )
    except jwt.PyJWTError as error:
        raise ValueError("invalid access token") from error
    if now is not None and claims.get("iat", 0) > int(_to_utc(now).timestamp()):
        raise ValueError("access token was issued in the future")
    return claims


def _to_utc(value: datetime) -> datetime:
    """Normalize aware datetimes to UTC and reject ambiguous naive values."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)
