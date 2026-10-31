"""Typed contract for transactional email delivery."""

from typing import Protocol


class EmailProvider(Protocol):
    """Send one transactional message with a stable idempotency key."""

    async def send(
        self,
        *,
        recipient: str,
        subject: str,
        html_body: str,
        idempotency_key: str,
    ) -> None:
        """Deliver a message or raise a provider error for durable retry."""
