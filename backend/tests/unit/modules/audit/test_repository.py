import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.audit.repository import AuditRepository


@pytest.mark.asyncio
async def test_record_persists_only_action_specific_metadata() -> None:
    session = Mock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = AuditRepository(session)

    await repository.record(
        action="staff.login.failed",
        entity_type="staff_user",
        actor_id=uuid.uuid4(),
        metadata={
            "outcome": "denied",
            "password": "plain-password",
            "reset_url": "https://example.test/reset?token=private",
            "extra": "unreviewed value",
            "nested": {"secret": "private"},
        },
    )

    audit_log = session.add.call_args.args[0]
    assert audit_log.event_metadata == {"outcome": "denied"}
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_drops_metadata_for_unknown_actions() -> None:
    session = Mock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = AuditRepository(session)

    await repository.record(
        action="staff.unreviewed_action",
        entity_type="staff_user",
        actor_id=uuid.uuid4(),
        metadata={"outcome": "accepted"},
    )

    audit_log = session.add.call_args.args[0]
    assert audit_log.event_metadata is None


@pytest.mark.asyncio
async def test_record_drops_nested_values_even_for_allowed_keys() -> None:
    session = Mock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = AuditRepository(session)

    await repository.record(
        action="staff.login.failed",
        entity_type="staff_user",
        actor_id=uuid.uuid4(),
        metadata={"outcome": {"token": "private"}},
    )

    audit_log = session.add.call_args.args[0]
    assert audit_log.event_metadata is None


@pytest.mark.asyncio
async def test_record_rejects_free_form_values_for_enum_fields() -> None:
    session = Mock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = AuditRepository(session)

    await repository.record(
        action="staff.login.failed",
        entity_type="staff_user",
        actor_id=uuid.uuid4(),
        metadata={"outcome": "password-reset-token-value"},
    )

    audit_log = session.add.call_args.args[0]
    assert audit_log.event_metadata is None
