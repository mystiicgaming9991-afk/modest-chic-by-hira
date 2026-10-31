"""Transactional enqueue and out-of-transaction email delivery."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.outbox.crypto import decrypt_payload, encrypt_payload
from modest_chic_backend.modules.outbox.models import OutboxEvent
from modest_chic_backend.modules.outbox.repository import OutboxRepository
from modest_chic_backend.providers.email.protocol import EmailProvider


class OutboxService:
    """Queue encrypted email payloads in the caller's current transaction."""

    def __init__(self, session: AsyncSession, encryption_key: bytes) -> None:
        self._session = session
        self._encryption_key = encryption_key

    async def enqueue_email(
        self,
        *,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        recipient: str,
        subject: str,
        html_body: str,
    ) -> uuid.UUID:
        """Encrypt and persist an email event without committing the caller's transaction."""
        event_id = uuid.uuid4()
        encrypted_payload = encrypt_payload(
            {"recipient": recipient, "subject": subject, "html_body": html_body},
            self._encryption_key,
        )
        self._session.add(
            OutboxEvent(
                id=event_id,
                event_type="email.send",
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload={"encrypted": encrypted_payload},
            )
        )
        await self._session.flush()
        return event_id


class OutboxWorker:
    """Claim events transactionally, send outside the transaction, and record outcome."""

    def __init__(self, database: Database, provider: EmailProvider, encryption_key: bytes) -> None:
        self._database = database
        self._provider = provider
        self._encryption_key = encryption_key

    async def deliver_next(self) -> bool:
        """Deliver one due event and persist success or a bounded retry state."""
        event_id, ciphertext = await self._claim()
        if event_id is None or ciphertext is None:
            return False
        try:
            payload = decrypt_payload(ciphertext, self._encryption_key)
            await self._provider.send(
                recipient=str(payload["recipient"]),
                subject=str(payload["subject"]),
                html_body=str(payload["html_body"]),
                idempotency_key=str(event_id),
            )
        except Exception:
            await self._mark_failed(event_id)
            raise
        await self._mark_sent(event_id)
        return True

    async def _claim(self) -> tuple[uuid.UUID | None, str | None]:
        """Commit a row claim before performing provider I/O."""
        async with self._database.transaction() as session:
            event = await OutboxRepository(session).claim_next()
            if event is None:
                return None, None
            ciphertext = event.payload.get("encrypted")
            if not isinstance(ciphertext, str):
                raise ValueError("email outbox event is missing its encrypted payload")
            return event.id, ciphertext

    async def _mark_sent(self, event_id: uuid.UUID) -> None:
        """Record successful email delivery after the network request completes."""
        async with self._database.transaction() as session:
            event = await OutboxRepository(session).get(event_id)
            if event is not None:
                await OutboxRepository(session).mark_sent(event)

    async def _mark_failed(self, event_id: uuid.UUID) -> None:
        """Schedule another delivery attempt or terminally fail the event."""
        async with self._database.transaction() as session:
            event = await OutboxRepository(session).get(event_id)
            if event is not None:
                await OutboxRepository(session).mark_failed(event)
