"""Staff identity, authorization, invitation, and session persistence models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Table,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modest_chic_backend.db.base import Base, BaseModel


class StaffStatus(enum.StrEnum):
    """Lifecycle states that control staff authentication."""

    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


staff_user_roles = Table(
    "staff_user_roles",
    Base.metadata,
    Column(
        "staff_user_id",
        Uuid(as_uuid=True),
        ForeignKey("staff_users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("assigned_by", Uuid(as_uuid=True), ForeignKey("staff_users.id")),
    Column("assigned_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        Uuid(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class StaffUser(BaseModel):
    """An internal staff identity with password, TOTP, and account state.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.
    """

    __tablename__ = "staff_users"
    __table_args__ = (
        CheckConstraint("length(trim(email)) > 0", name="chk_staff_email_not_blank"),
        CheckConstraint(
            "status = 'INVITED' OR hashed_password IS NOT NULL", name="chk_staff_password_state"
        ),
        Index("uq_staff_users_email_ci", func.lower(func.trim(text("email"))), unique=True),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    totp_secret: Mapped[str | None] = mapped_column(String(255))
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    totp_last_counter: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[StaffStatus] = mapped_column(
        Enum(StaffStatus, name="staff_status", native_enum=True),
        nullable=False,
        default=StaffStatus.INVITED,
        server_default=StaffStatus.INVITED.value,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roles: Mapped[list["Role"]] = relationship(
        secondary="staff_user_roles",
        back_populates="staff_users",
        lazy="selectin",
        primaryjoin="StaffUser.id == staff_user_roles.c.staff_user_id",
        secondaryjoin="Role.id == staff_user_roles.c.role_id",
    )


class Role(BaseModel):
    """A named staff role that grants a set of permissions.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.
    """

    __tablename__ = "roles"
    __table_args__ = (Index("uq_role_key", "key", unique=True),)

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    display_label: Mapped[str] = mapped_column(String(255), nullable=False)

    staff_users: Mapped[list["StaffUser"]] = relationship(
        secondary="staff_user_roles",
        back_populates="roles",
        primaryjoin="Role.id == staff_user_roles.c.role_id",
        secondaryjoin="StaffUser.id == staff_user_roles.c.staff_user_id",
    )


class Permission(BaseModel):
    """A named staff capability referenced by role grants.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.
    """

    __tablename__ = "permissions"
    __table_args__ = (Index("uq_permission_key", "key", unique=True),)

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)


class StaffSession(BaseModel):
    """A refresh credential row participating in one revocable session family.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.

    Session rows are created by the authentication service and are
    never modified in place — rotation inserts a *new* row — so
    ``updated_by`` and ``deleted_at`` will never be set.
    """

    __tablename__ = "staff_sessions"
    __table_args__ = (
        Index("uq_session_token", "token_hash", unique=True),
        Index("idx_sessions_user", "staff_user_id"),
        Index("idx_sessions_expiry", "expires_at", postgresql_where=text("revoked_at IS NULL")),
        Index("idx_sessions_family", "family_id"),
    )

    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff_users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StaffInvitation(BaseModel):
    """A one-time invitation secret bound to a normalized staff email.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.
    """

    __tablename__ = "staff_invitations"
    __table_args__ = (Index("uq_staff_invite_token", "token_hash", unique=True),)

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    invited_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff_users.id"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StaffPasswordReset(BaseModel):
    """A one-time token that permits a staff password replacement.

    Inherits ``id``, ``created_at``, ``created_by``, ``updated_at``,
    ``updated_by``, and ``deleted_at`` from :class:`BaseModel`.
    """

    __tablename__ = "staff_password_resets"
    __table_args__ = (
        Index("uq_staff_password_reset_token", "token_hash", unique=True),
        Index("idx_password_resets_user", "staff_user_id"),
    )

    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff_users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = [
    "Permission",
    "Role",
    "StaffInvitation",
    "StaffPasswordReset",
    "StaffSession",
    "StaffStatus",
    "StaffUser",
    "role_permissions",
    "staff_user_roles",
]
