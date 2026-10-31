import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.outbox.models import OutboxEvent
from modest_chic_backend.modules.outbox.repository import OutboxRepository
from modest_chic_backend.modules.outbox.service import OutboxService, OutboxWorker
from modest_chic_backend.providers.email.memory import MemoryEmailProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required for PostgreSQL tests"
)


@pytest.mark.asyncio
async def test_outbox_claims_due_event_with_lease_and_marks_sent() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    event_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            await session.execute(delete(OutboxEvent))
        async with database.transaction() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    event_type="staff.invitation_email",
                    aggregate_type="staff_invitation",
                    aggregate_id=uuid.uuid4(),
                    payload={"ciphertext": "encrypted-payload"},
                    status="PENDING",
                    attempts=0,
                    next_attempt_at=datetime.now(UTC),
                )
            )
        async with database.transaction() as session:
            repository = OutboxRepository(session)
            event = await repository.claim_next(lease_seconds=30)
            assert event is not None
            assert event.id == event_id
            await repository.mark_sent(event)
        async with database.session() as session:
            event = await session.get(OutboxEvent, event_id)
            assert event is not None
            assert event.status == "SENT"
            assert event.processed_at is not None
    finally:
        async with database.transaction() as session:
            event = await session.get(OutboxEvent, event_id)
            if event is not None:
                await session.delete(event)
        await database.dispose()


@pytest.mark.asyncio
async def test_outbox_reclaims_processing_event_after_worker_lease_expires() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    event_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            await session.execute(delete(OutboxEvent))
        async with database.transaction() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    event_type="staff.password_reset_email",
                    aggregate_type="staff_password_reset",
                    aggregate_id=uuid.uuid4(),
                    payload={"encrypted": "ciphertext"},
                    status="PROCESSING",
                    attempts=1,
                    next_attempt_at=datetime.now(UTC) - timedelta(minutes=2),
                    lease_until=datetime.now(UTC) - timedelta(minutes=1),
                )
            )
        async with database.transaction() as session:
            event = await OutboxRepository(session).claim_next(lease_seconds=30)
            assert event is not None
            assert event.id == event_id
            assert event.attempts == 2
        async with database.transaction() as session:
            event = await session.get(OutboxEvent, event_id)
            assert event is not None
            await session.delete(event)
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_worker_decrypts_and_delivers_email_then_marks_event_sent() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    provider = MemoryEmailProvider()
    encryption_key = b"o" * 32
    aggregate_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            event_id = await OutboxService(session, encryption_key).enqueue_email(
                aggregate_type="staff_invitation",
                aggregate_id=aggregate_id,
                recipient="staff@example.com",
                subject="Your staff invitation",
                html_body="<a href='https://admin.example.test/invite?token=one-time'>Accept</a>",
            )

        worker = OutboxWorker(database, provider, encryption_key)
        assert await worker.deliver_next() is True
        assert await worker.deliver_next() is False
        assert len(provider.messages) == 1
        message = provider.messages[str(event_id)]
        assert message.recipient == "staff@example.com"
        assert "token=one-time" in message.html_body
        async with database.session() as session:
            event = await session.get(OutboxEvent, event_id)
            assert event is not None
            assert event.status == "SENT"
            assert event.payload == {"encrypted": event.payload["encrypted"]}
            assert "token=one-time" not in str(event.payload)
    finally:
        async with database.transaction() as session:
            event = await session.get(OutboxEvent, event_id)
            if event is not None:
                await session.delete(event)
        await database.dispose()
