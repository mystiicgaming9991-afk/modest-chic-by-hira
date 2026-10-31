"""arq worker entrypoint that polls the PostgreSQL outbox for email delivery."""

import logging
import os
from typing import Any

import httpx
from arq import cron
from arq.connections import RedisSettings

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.outbox.service import OutboxWorker
from modest_chic_backend.providers.email.memory import MemoryEmailProvider
from modest_chic_backend.providers.email.protocol import EmailProvider
from modest_chic_backend.providers.email.resend import ResendEmailProvider

LOGGER = logging.getLogger(__name__)


async def startup(context: dict[str, Any]) -> None:
    """Create worker-owned database and email client resources."""
    settings = Settings()
    database = Database(str(settings.database_url))
    client = httpx.AsyncClient(timeout=10)
    provider: EmailProvider
    if settings.email_provider == "resend":
        api_key = settings.resend_api_key
        if api_key is None:
            raise RuntimeError("Resend API key is required for the configured email provider")
        provider = ResendEmailProvider(api_key.get_secret_value(), settings.email_from, client)
    else:
        provider = MemoryEmailProvider()
    context["database"] = database
    context["email_client"] = client
    context["outbox_worker"] = OutboxWorker(
        database,
        provider,
        settings.outbox_encryption_key.get_secret_value().encode("utf-8"),
    )


async def shutdown(context: dict[str, Any]) -> None:
    """Close worker-owned database and HTTP resources."""
    client: httpx.AsyncClient = context["email_client"]
    database: Database = context["database"]
    await client.aclose()
    await database.dispose()


async def dispatch_outbox(context: dict[str, Any]) -> int:
    """Deliver due events without logging recipient details or secret-bearing errors."""
    worker: OutboxWorker = context["outbox_worker"]
    processed = 0
    for _ in range(50):
        try:
            delivered = await worker.deliver_next()
        except Exception:
            LOGGER.warning("outbox_delivery_attempt_failed")
            continue
        if not delivered:
            break
        processed += 1
    return processed


class WorkerSettings:
    """arq worker configuration for durable outbox polling."""

    functions = [dispatch_outbox]
    cron_jobs = [
        cron(
            "modest_chic_backend.worker.dispatch_outbox",
            second={0, 10, 20, 30, 40, 50},
            run_at_startup=True,
        )
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:56379/0"))
    max_jobs = 10
    job_timeout = 60
