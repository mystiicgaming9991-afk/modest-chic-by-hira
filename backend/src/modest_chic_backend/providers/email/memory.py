"""In-memory email adapter for isolated tests and local development."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveredEmail:
    """A captured transactional email that is never written to application logs."""

    recipient: str
    subject: str
    html_body: str
    idempotency_key: str


class MemoryEmailProvider:
    """Capture one-time email messages for tests without sending or logging them."""

    def __init__(self) -> None:
        self.messages: dict[str, DeliveredEmail] = {}

    async def send(
        self,
        *,
        recipient: str,
        subject: str,
        html_body: str,
        idempotency_key: str,
    ) -> None:
        """Store a message by idempotency key, ignoring duplicate worker delivery."""
        self.messages.setdefault(
            idempotency_key,
            DeliveredEmail(recipient, subject, html_body, idempotency_key),
        )
