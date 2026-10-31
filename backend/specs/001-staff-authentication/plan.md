# Implementation Plan: Staff Email and Password Authentication

**Branch**: `001-staff-authentication` (feature directory; repository branch remains `main`) | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-staff-authentication/spec.md`

## Summary

Deliver the first backend vertical slice: invite-only staff identity, email/password and TOTP authentication, rotating sessions, password recovery, CSRF/origin defenses, current-permission checks, and security audit. Follow the reviewed backend PRD/TRD/HLD/LLD; start with contract and failing tests, then add the smallest production implementation. The API runs independently in `backend/`; email is sent through the existing documented outbox/provider boundary.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI; Pydantic v2 / pydantic-settings; SQLAlchemy 2 async; Alembic; asyncpg; PyJWT; bcrypt; pyotp; cryptography (AES-GCM); Redis 7 + arq; HTTPX; structlog

**Storage**: PostgreSQL 16; Redis for distributed rate limits and job dispatch; PostgreSQL outbox is the durable source for email delivery

**Testing**: pytest, pytest-asyncio, HTTPX ASGI transport, unit tests plus PostgreSQL 16 integration/concurrency tests; Ruff and mypy

**Target Platform**: Linux container; local development on Python 3.12+

**Project Type**: Standalone async HTTP API service, isolated under `backend/`

**Performance Goals**: Login and ordinary auth endpoint p95 under 300 ms at the documented pilot load, excluding email-provider delivery; email enqueue and response do not wait for provider network calls

**Constraints**: Passwords require >=12 characters and <=72 UTF-8 bytes; bcrypt cost 12; access JWT 15 minutes; opaque refresh credential <=7 days; one request/job owns one `AsyncSession`; all external email calls occur outside DB transactions; fail closed for auth if rate-limit infrastructure is unavailable

**Scale/Scope**: Initial pilot <=100 orders/day, <=10 staff users, and the complete staff-authentication flow only. Catalog and commerce feature modules will be specified separately.

## Constitution Check

| Gate | Result | Evidence |
|---|---|---|
| Contract-first modular design | PASS | OpenAPI contract and data model precede route/service implementation; scope follows reviewed backend docs. |
| Test-first development | PASS | Every behavior task starts with a focused failing test; PostgreSQL tests cover locking and transaction semantics. |
| Atomic domain changes | PASS | Account/session/reset/outbox/audit transitions share one request transaction; email delivery runs after commit through durable outbox. |
| Secure defaults | PASS | bcrypt, hashed opaque secrets, CSRF + Origin, rate limits, generic failures, current role checks, TOTP, and log redaction are explicit. |
| Observable, simple operations | PASS | Structured redacted audit/logging; Redis and PostgreSQL dependencies are health-checked; no provider calls inside transactions. |
| Python/FastAPI/PostgreSQL constraints | PASS | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL 16. |

No constitution violations or unresolved technical choices remain for this feature.

## Design Phases

### Phase 0: Research

Record selected libraries and security/database patterns in `research.md`, including alternatives and tradeoffs. Resolve all decisions before defining implementation tasks.

### Phase 1: Design and Contracts

- `data-model.md`: staff identity, role assignments, invitations, session families, password resets, audit records, and outbox lifecycle.
- `contracts/openapi.yaml`: versioned HTTP requests, responses, errors, cookies, CSRF/origin requirements, and protected-route authorization semantics.
- `quickstart.md`: local service setup and black-box validation scenarios.

### Phase 2: Tests and Implementation

Tests precede source for each story. Keep transport schemas, domain rules, persistence, and provider adapters separate; map each task to an FR and a test. Build on PostgreSQL rather than substituting SQLite for concurrency-sensitive tests.

## Project Structure

### Documentation (this feature)

```text
specs/001-staff-authentication/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/openapi.yaml
├── checklists/requirements.md
├── checklists/auth-security.md
└── tasks.md
```

### Source Code

```text
backend/
├── pyproject.toml
├── alembic.ini
├── migrations/
├── src/modest_chic_backend/
│   ├── api/v1/auth.py
│   ├── core/                 # settings, security, errors, logging
│   ├── db/                   # async session and metadata
│   ├── modules/auth/         # domain, schemas, service, repository
│   ├── modules/audit/
│   ├── modules/outbox/
│   └── providers/email/      # protocol and Resend/local adapters
└── tests/
    ├── unit/
    ├── contract/
    └── integration/
```

**Structure Decision**: Treat `backend/` as an independent Python service within the existing storefront repository. Keep all implementation, migration, and test files inside it; do not alter the existing Next.js app for this API-only feature.

## Complexity Tracking

No constitution violations requiring justification.
