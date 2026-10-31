# Quickstart: Staff Authentication

## Prerequisites

- Python 3.12+, `uv`, Docker, and Docker Compose.
- PostgreSQL 16 and Redis 7 (the included Compose file binds to ports 55532 and 56379).
- A Resend API key and verified sender for real invitation and password-reset email delivery.

## Run the service

From `backend/`:

```bash
uv sync
cp .env.example .env
docker compose up -d postgres redis
uv run alembic upgrade head
uv run modest-chic-backend bootstrap-owner --email owner@example.com
uv run uvicorn modest_chic_backend.main:create_app --factory --reload
```

Set unique 32-byte values for `JWT_SIGNING_KEY` and `CSRF_SIGNING_KEY` in `.env`.
The provided TOTP and outbox encryption keys are development-only; replace them
with randomly generated 32-byte values. Set `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`,
and a verified `EMAIL_FROM` to deliver the bootstrap invitation. The `console`
provider does not send or log email; it is safe for local startup but cannot be
used to receive an invitation or password-reset link. Run the durable email worker
in a second terminal:

```bash
uv run arq modest_chic_backend.worker.WorkerSettings
```

Configure the frontend origin in `TRUSTED_ORIGINS` and `ADMIN_BASE_URL` before
using browser-based auth routes. The first-owner command creates only an invited
account and one-time invitation; it never seeds a password.

## Validate

```bash
uv run pytest tests/unit tests/contract
uv run pytest tests/integration
uv run ruff check src tests
uv run mypy src
```

For a complete integration run, set `TEST_DATABASE_URL`, `MIGRATION_DATABASE_URL`,
and `BOOTSTRAP_DATABASE_URL` to three distinct PostgreSQL test databases, and
`TEST_REDIS_URL` to an isolated Redis database. Tests guarded by an unset URL are
skipped. `test_bootstrap_email_to_owner_login_refresh_and_logout` exercises the
owner flow using the in-memory email adapter, without sending real mail.
Production email delivery still needs a separate smoke run with a verified Resend
sender and API credential before release.

Expected end-to-end results:

1. Bootstrap produces an invited owner and one-time invitation; accepting it with a
   compliant password activates the account exactly once.
2. Login with valid email/password returns a 15-minute access token and sets a
   secure, HttpOnly refresh cookie. Invalid/unknown/invited/suspended identities
   receive the same generic failure.
3. Refresh rotates the opaque token; replay of the prior token revokes the session
   family. Logout clears the cookie and revokes that family.
4. Forgot-password returns the same `202` body for known and unknown accounts.
   The delivered one-time link changes the password and revokes all sessions.
5. Production-mode admin access requires completed TOTP; a code cannot be accepted
   twice. Invalid CSRF or Origin rejects browser mutations.

See [contracts/openapi.yaml](contracts/openapi.yaml) for the endpoint contract and
[data-model.md](data-model.md) for persistence invariants.
