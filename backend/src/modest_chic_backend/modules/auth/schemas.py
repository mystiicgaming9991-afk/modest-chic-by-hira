"""Validated API request and response schemas for staff authentication."""

import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AcceptInvitationRequest(BaseModel):
    """Invitation acceptance fields needed to activate a staff account."""

    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=12, max_length=72)
    display_name: str = Field(min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        """Enforce the bcrypt byte limit for multi-byte Unicode passwords."""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password must not exceed 72 UTF-8 bytes")
        return value


class LoginRequest(BaseModel):
    """Staff email/password login values with optional TOTP proof."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=72)
    totp_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        """Reject malformed basic email forms before a database lookup."""
        normalized = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("email address is invalid")
        return normalized


class InviteStaffRequest(BaseModel):
    """Normalized staff email and roles selected by an authorized owner."""

    email: str = Field(min_length=3, max_length=255)
    roles: list[str] = Field(min_length=1, max_length=20)

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        """Reject malformed email addresses before role or account writes."""
        normalized = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("email address is invalid")
        return normalized


class ForgotPasswordRequest(BaseModel):
    """Email identity for a non-enumerating password recovery request."""

    email: str = Field(min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        """Reject malformed email addresses before account lookup."""
        normalized = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("email address is invalid")
        return normalized


class ResetPasswordRequest(BaseModel):
    """One-time reset token and compliant new password."""

    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=12, max_length=72)

    @field_validator("new_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        """Enforce the bcrypt byte limit for multi-byte Unicode passwords."""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password must not exceed 72 UTF-8 bytes")
        return value


class ChangePasswordRequest(BaseModel):
    """Current credential proof plus a new password value."""

    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=12, max_length=72)

    @field_validator("new_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        """Enforce the bcrypt byte limit for multi-byte Unicode passwords."""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password must not exceed 72 UTF-8 bytes")
        return value


class StaffSummary(BaseModel):
    """Non-secret identity details included in login responses."""

    id: uuid.UUID
    name: str
    roles: list[str]


class SessionResponse(BaseModel):
    """Access credential and explicit enrollment state; refresh stays cookie-only."""

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    auth_state: Literal["ACTIVE", "TOTP_ENROLLMENT_REQUIRED"]
    staff_user: StaffSummary


class StaffIdentityResponse(BaseModel):
    """Current persisted staff details and permission keys."""

    id: uuid.UUID
    email: str
    name: str
    permission_keys: list[str]
    totp_enabled: bool


class TotpSetupResponse(BaseModel):
    """One-time TOTP seed and provisioning URI with no-store transport semantics."""

    secret: str
    qr_code_url: str


class VerifyTotpRequest(BaseModel):
    """Six-digit enrollment proof from the staff authenticator."""

    totp_code: str = Field(pattern=r"^[0-9]{6}$")
