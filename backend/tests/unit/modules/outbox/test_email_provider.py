import httpx
import pytest

from modest_chic_backend.providers.email.resend import ResendEmailProvider


@pytest.mark.asyncio
async def test_resend_adapter_sends_idempotent_transactional_email() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "email-id"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    provider = ResendEmailProvider("resend-secret", "admin@example.com", client)

    await provider.send(
        recipient="staff@example.com",
        subject="Accept invitation",
        html_body="<a href='https://example.test/invite?token=secret'>Accept</a>",
        idempotency_key="event-id",
    )
    await client.aclose()

    assert requests[0].url == "https://api.resend.com/emails"
    assert requests[0].headers["authorization"] == "Bearer resend-secret"
    assert requests[0].headers["idempotency-key"] == "event-id"
    assert b"staff@example.com" in requests[0].content


@pytest.mark.asyncio
async def test_resend_adapter_raises_on_provider_failure() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503, text="unavailable"))
    )
    provider = ResendEmailProvider("resend-secret", "admin@example.com", client)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.send(
            recipient="staff@example.com",
            subject="Reset password",
            html_body="Link",
            idempotency_key="event-id",
        )

    await client.aclose()
