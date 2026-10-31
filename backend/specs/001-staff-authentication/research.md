# Research: Staff Email and Password Authentication

## Decisions

### Service and persistence

- **Decision**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 async, asyncpg, Alembic, PostgreSQL 16, Redis 7, and arq.
- **Rationale**: This is the technology baseline in `BACKEND_TRD.md`; it aligns with the HLD worker/outbox topology and the current auth schema in the TRD.
- **Alternatives considered**: SQLite for local/test persistence was rejected because the feature depends on PostgreSQL row locks, partial indexes, and transaction isolation; an in-memory job queue was rejected because it is not durable.

### Password and access-token cryptography

- **Decision**: Use `bcrypt` at work factor 12 for passwords, reject inputs over 72 UTF-8 bytes, and use PyJWT with one configured signing algorithm and explicit verification parameters for access tokens.
- **Rationale**: Both bcrypt and the work factor are specified by the reviewed TRD/LLD. The bcrypt implementation rejects inputs beyond 72 bytes, so the public contract enforces this boundary rather than permitting silent truncation. JWT decoding must pin the accepted algorithm rather than trusting the untrusted token header.
- **Alternatives considered**: Argon2id is a viable modern password KDF, but changing from the reviewed bcrypt design is outside this feature. `python-jose` and `passlib` in the older baseline were not selected because the direct `bcrypt` API and maintained PyJWT API keep these narrowly scoped operations explicit.
- **Sources**: [pyca/bcrypt README](https://github.com/pyca/bcrypt); [PyJWT usage](https://pyjwt.readthedocs.io/en/stable/usage.html).

### Async database ownership and tests

- **Decision**: One SQLAlchemy `AsyncSession` per request/job and transaction; run API tests with HTTPX/pytest-asyncio, plus integration tests on PostgreSQL 16 for refresh replay, invitation consumption, and reset races.
- **Rationale**: SQLAlchemy documents that concurrent asyncio tasks need separate `AsyncSession` objects. FastAPI documents async HTTP tests through HTTPX; PostgreSQL integration coverage is required by the constitution for locks and transactions.
- **Alternatives considered**: A shared session across concurrent tasks is unsafe; SQLite-only tests cannot validate PostgreSQL concurrency semantics.
- **Sources**: [SQLAlchemy asyncio documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html); [FastAPI async tests](https://fastapi.tiangolo.com/advanced/async-tests/).

### Sessions, CSRF, and permission checks

- **Decision**: Return a 15-minute signed access token; set a random opaque refresh token in a secure HttpOnly SameSite=Strict cookie and persist only SHA-256 hashes. Rotate under a row lock, retain old hashes for replay detection, and revoke the family on reuse. Sign a readable CSRF cookie; require its matching header and exact trusted Origin on browser state changes. Load user/session/permission state from PostgreSQL for every protected request.
- **Rationale**: This matches reviewed HLD/LLD security requirements while ensuring session and permission revocation take effect without waiting for JWT expiry.
- **Alternatives considered**: Self-contained role claims without a current database check were rejected because they delay role/suspension revocation. JavaScript-readable refresh tokens were rejected because they expand XSS impact.

### Invitations, recovery, and email

- **Decision**: Store only hashes of random single-use invitation/reset secrets. Persist email jobs to the PostgreSQL outbox in the same transaction as the secret record, then deliver through the documented email provider adapter (Resend in production, local fake in development/tests) outside the transaction.
- **Rationale**: Durable outbox handling supports retry without coupling account-enumeration behavior or business transactions to provider uptime. The HLD identifies Resend as the production email adapter.
- **Alternatives considered**: Sending inline with the request can lose messages or hold database locks during network failure; storing raw links is unnecessary because the worker can receive encrypted/outbox payload material under the project's approved secret-handling design.

### TOTP

- **Decision**: Use pyotp for TOTP generation/verification, encrypt pending and active seeds with AES-GCM using a key supplied outside the database, and persist the last accepted time counter to reject replay.
- **Rationale**: TOTP and at-rest secret protection are required by the reviewed design. Replay tracking is necessary to meet the specification's explicit previously-used-code rejection case.
- **Alternatives considered**: Plaintext seed storage and stateless verification that accepts the same time-window code more than once are rejected.

## Repository Findings

- The Git repository initially contains a Next.js storefront and no backend package or backend-specific test harness.
- The reviewed design documents are in the workspace parent (`BACKEND_PRD.md`, `BACKEND_TRD.md`, `BACKEND_HLD.md`, `BACKEND_LLD.md`, and `BACKEND_DESIGN_REVIEW.md`); they define 53 commerce tables, but this feature intentionally implements only staff authentication foundations and the auth-facing audit/outbox records it depends on.
- The working tree has existing storefront changes. This plan confines implementation to the new `backend/` project.
