"""HTTPX adapter for the Resend transactional email API."""

import httpx


class ResendEmailProvider:
    """Send idempotent transactional mail through Resend."""

    def __init__(self, api_key: str, sender: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._sender = sender
        self._client = client

    async def send(
        self,
        *,
        recipient: str,
        subject: str,
        html_body: str,
        idempotency_key: str,
    ) -> None:
        """Send a message with provider-side deduplication for worker retries."""
        response = await self._client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Idempotency-Key": idempotency_key,
            },
            json={
                "from": self._sender,
                "to": [recipient],
                "subject": subject,
                "html": html_body,
            },
        )
        response.raise_for_status()
