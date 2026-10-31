# Modest Chic Backend

Python 3.12 async commerce API for the Modest Chic storefront and staff operations.
The storefront connects through its server-side `/api/commerce/*` proxy.

## Local setup

```bash
uv sync
cp .env.example .env
docker compose up -d postgres redis
uv run alembic upgrade head
uv run uvicorn modest_chic_backend.main:create_app --factory --reload
```

The canonical `compose.yaml` also defines the API and email worker. To run those
in containers, apply migrations through the API image and then start both
services:

```bash
docker compose run --rm api uv run alembic upgrade head
docker compose up -d api worker
```

The API is then available at `http://localhost:8000`. Compose development
signing keys are only for local use; supply unique secrets outside development.

Start the durable email worker separately with
`uv run arq modest_chic_backend.worker.WorkerSettings`. Configure Resend and a
verified sender in `.env` to deliver email. The default `console` provider is a
non-delivering adapter and intentionally never logs invitation or reset links.
The first-owner command, `uv run modest-chic-backend bootstrap-owner --email
owner@example.com`, creates an invitation only; no default password is generated.

Use unique random 32-byte values for signing/encryption keys outside local
development. Production settings require HTTPS trusted origins, a Resend
credential, PostgreSQL, Redis, and explicit frontend/admin origins.

## Quality checks

```bash
uv run pytest tests/unit tests/contract
uv run pytest tests/integration
uv run ruff check src tests
uv run mypy src
```

PostgreSQL integration tests use `TEST_DATABASE_URL`; Redis tests use
`TEST_REDIS_URL`. Migration-upgrade/downgrade tests use the separate
`MIGRATION_DATABASE_URL` because that test intentionally drops and recreates
its target schema. Bootstrap tests likewise need a separate disposable
`BOOTSTRAP_DATABASE_URL`. See `specs/001-staff-authentication/quickstart.md` for
the end-to-end bootstrap and login flow, and the root `INTEGRATION_REVIEW.md`
for current feature coverage.
