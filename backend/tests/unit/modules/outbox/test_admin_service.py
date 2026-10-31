"""Allow-listed staff monitoring of encrypted outbox delivery state."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from modest_chic_backend.modules.outbox.admin_service import OutboxAdminService
from modest_chic_backend.modules.outbox.models import OutboxEvent


class _Session:
    def __init__(self, events: list[OutboxEvent]) -> None:
        self.events = events
        self.statements: list[object] = []

    async def scalar(self, statement: object) -> int:
        self.statements.append(statement)
        return len(self.events)

    async def scalars(self, statement: object) -> SimpleNamespace:
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: self.events)


@pytest.mark.asyncio
async def test_outbox_admin_list_returns_only_allow_listed_delivery_metadata() -> None:
    now = datetime.now(UTC)
    event = OutboxEvent(
        id=uuid.uuid4(),
        event_type="email.send",
        aggregate_type="customer_email_otp",
        aggregate_id=uuid.uuid4(),
        payload={"encrypted": "secret recipient token body"},
        status="FAILED",
        attempts=10,
        created_at=now,
        updated_at=now,
        next_attempt_at=now,
        processed_at=None,
    )
    session = _Session([event])

    page = await OutboxAdminService(session).list_events(status="FAILED", limit=20, offset=0)

    assert page["total_count"] == 1
    assert page["limit"] == 20
    assert page["offset"] == 0
    assert page["items"] == [
        {
            "id": str(event.id),
            "event_type": "email.send",
            "aggregate_type": "customer_email_otp",
            "status": "FAILED",
            "attempts": 10,
            "created_at": now,
            "processed_at": None,
            "next_attempt_at": now,
        }
    ]
    assert len(session.statements) == 2
    assert "payload" not in str(session.statements[1]).lower()
