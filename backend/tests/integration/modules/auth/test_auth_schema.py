from modest_chic_backend.db.base import Base
from modest_chic_backend.modules.audit import models as audit_models
from modest_chic_backend.modules.auth import models as auth_models
from modest_chic_backend.modules.outbox import models as outbox_models


def test_auth_metadata_contains_documented_tables() -> None:
    expected = {
        "staff_users",
        "roles",
        "permissions",
        "staff_user_roles",
        "role_permissions",
        "staff_sessions",
        "staff_invitations",
        "staff_password_resets",
        "audit_logs",
        "outbox_events",
    }

    assert expected <= set(Base.metadata.tables)
    assert auth_models.StaffUser.__tablename__ == "staff_users"
    assert audit_models.AuditLog.__tablename__ == "audit_logs"
    assert outbox_models.OutboxEvent.__tablename__ == "outbox_events"


def test_staff_password_and_invitation_constraints_match_lifecycle() -> None:
    staff = Base.metadata.tables["staff_users"]
    invitations = Base.metadata.tables["staff_invitations"]
    sessions = Base.metadata.tables["staff_sessions"]

    assert staff.c.hashed_password.nullable is True
    assert any(
        "chk_staff_password_state" in str(constraint.name) for constraint in staff.constraints
    )
    assert "uq_staff_invite_token" in {index.name for index in invitations.indexes}
    assert "uq_session_token" in {index.name for index in sessions.indexes}


def test_totp_replay_counter_and_outbox_delivery_state_are_persisted() -> None:
    staff = Base.metadata.tables["staff_users"]
    outbox = Base.metadata.tables["outbox_events"]

    assert "totp_last_counter" in staff.c
    assert {"attempts", "status", "next_attempt_at"} <= set(outbox.c.keys())
