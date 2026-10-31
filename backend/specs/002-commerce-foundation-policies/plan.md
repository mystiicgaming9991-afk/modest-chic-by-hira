# Implementation Plan: Commerce Foundation and Policies

**Current integration status (2026-10-25)**: Versioned settings and immutable policy publication are connected to an owner-only staff screen. Secret values remain masked; setting types and disabled provider/pickup paths are enforced server-side. In live mode, the public shipping and returns pages fetch the current effective approved policy through the commerce BFF. Checkout renders the exact current approved checkout, shipping, and returns policy versions, requires one explicit acceptance, and stores all three immutable version links with the order. Preview mode uses clearly marked preview copy. Cross-policy navigation and checkout policy snapshots have frontend/API/PostgreSQL regression coverage. Approved business content and release sign-off remain required before policy-gated commerce paths are enabled.

**Branch**: `002-commerce-foundation-policies` (feature directory) | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-commerce-foundation-policies/spec.md`

## Summary

Deliver the commerce foundation layer: versioned store settings with role-gated writes and secret handling, immutable policy versions for checkout/returns/shipping/privacy/terms/cod_confirmation, shared cross-feature API conventions (error shape, pagination, money, idempotency key), and reportable-record conventions. Build on the existing staff authentication, audit, and outbox infrastructure. All writes are atomic—audit log, outbox events, and the setting/policy change commit together.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI; Pydantic v2 / pydantic-settings; SQLAlchemy 2 async; Alembic; asyncpg; cryptography (AES-GCM for secret settings)

**Storage**: PostgreSQL 16 (new tables: `store_settings`, `policy_versions`; existing auth/audit/outbox tables preserved)

**Testing**: pytest, pytest-asyncio, HTTPX ASGI transport, PostgreSQL 16 integration tests; Ruff and mypy

**Target Platform**: Linux container; local development on Python 3.12+

**Project Type**: Shared foundation layer within the existing `modest-chic-backend` service

**Performance Goals**: Setting reads under 50ms; policy version insertion under 200ms

**Constraints**: All writes must be within a single transaction with audit; secret settings encrypted at rest with AES-256-GCM; setting updates must be version-checked (optimistic concurrency); policy versions are immutable

**Scale/Scope**: ~20–40 store settings, ~5–20 policy versions initially

## Constitution Check

| Gate | Result | Evidence |
|---|---|---|
| Contract-first modular design | PASS | New `modules/settings/` and `modules/policies/` follow existing module boundaries; OpenAPI contract precedes route implementation. |
| Test-first development | PASS | Every behavior task starts with a focused failing test. |
| Atomic domain changes | PASS | Setting write, policy publish, and the audit log commit in one transaction; no external calls inside transactions. |
| Secure defaults | PASS | `settings.manage` permission required; secret values encrypted at rest, never returned in reads or logged; version-checked writes prevent lost updates. |
| Observable, simple operations | PASS | Structured audit of every setting/policy change; no new infrastructure beyond what auth already provides. |
| Python/FastAPI/PostgreSQL constraints | PASS | Python 3.12+, existing FastAPI/Pydantic/SQLAlchemy stack. |

No constitution violations or unresolved technical choices remain for this feature.

## Existing Slice Compatibility

Per `specs/README.md` §Existing slice compatibility:

- **Outbox**: The existing `outbox_events` table, `modules/outbox/`, and worker delivery remain the single durable event mechanism. This feature does not create a second outbox. Policy publication events use the existing outbox columns (`event_type`, `aggregate_type`, `aggregate_id`, `payload`, `status`, etc.).
- **Error contract**: The existing `Error` schema (`code`, `message`, optional `request_id`) defined in `specs/001-staff-authentication/contracts/openapi.yaml` remains the shared error shape. This feature's new routes use the same `ApplicationError` class from `core/errors.py`.
- **Auth**: Staff identity, session, and permission checks reuse `require_staff_identity` and `require_permission` from `api/v1/dependencies.py`. The `settings.manage` permission already exists in the seed data.
- **Audit**: The existing `audit_logs` table continues to record security-relevant actions. Setting and policy changes produce audit records with `actor_id`, `action`, `entity_type`, `entity_id`.

## Data Model Design

### `store_settings` table
Follows `BACKEND_TRD.md` §4.2.1 with additions for secret encryption and concurrency:

- `id`: UUID PK
- `key`: VARCHAR(100) UNIQUE — stable lookup key
- `value`: JSONB — the effective value (plain for non-secret; AES-256-GCM ciphertext for secrets, stored as a structured JSON blob with `ciphertext` and `nonce`)
- `is_secret`: BOOLEAN — TRUE means value is encrypted at rest and never returned in GET
- `version`: INT — incremented on each write; used for optimistic concurrency
- `updated_by`: UUID FK → `staff_users.id`
- `updated_at`: TIMESTAMPTZ

### `policy_versions` table
Follows `BACKEND_TRD.md` §4.2.2:

- `id`: UUID PK
- `type`: VARCHAR(100) — one of `checkout_bundle`, `returns`, `shipping`, `privacy`, `terms`, `cod_confirmation`
- `version`: INT — within each type
- `effective_from`: TIMESTAMPTZ — when this version becomes the governing one
- `content`: JSONB — immutable approved text
- `approved_by`: UUID FK → `staff_users.id`
- `created_at`: TIMESTAMPTZ
- UNIQUE(`type`, `version`)

### Cross-feature conventions (FR-008, FR-009)

- **Error shape**: All routes return `{ "code": "...", "message": "...", "request_id": "..." }` on errors, matching the existing `Error` schema in `contracts/openapi.yaml`.
- **Money**: Stored as integer minor units (PKR paisa). Pydantic schemas receive/return decimal strings. Documented in `contracts/shared-conventions.yaml`.
- **Pagination**: Cursor-based using `after` (UUID) and `limit` (≤100). Response includes `items`, `next_cursor`. Documented in `contracts/shared-conventions.yaml`.
- **Idempotency**: Idempotency key (UUID) on mutation endpoints; stored results keyed by key for 24 hours. Documented in `contracts/shared-conventions.yaml`.
- **Reportable records**: Every commerce table must include stable entity IDs, immutable snapshots, deduplicated transition evidence, trusted timestamps, typed dimensions, and measured indexes. This is a design-time rule enforced during later spec planning, not runtime code.

## Project Structure

### Documentation (this feature)

```text
specs/002-commerce-foundation-policies/
├── plan.md              # This file
├── research.md          # Phase 0 research decisions
├── data-model.md        # Detailed entity relationships
├── quickstart.md        # Local setup and validation
├── contracts/
│   ├── openapi.yaml     # Settings and policies HTTP API
│   └── shared-conventions.yaml  # Error, money, pagination, idempotency contracts
├── checklists/
│   └── requirements.md  # Already complete (all checked)
└── tasks.md             # Phase 2 test + implementation tasks
```

### Source Code

```text
backend/
├── src/modest_chic_backend/
│   ├── modules/settings/        # NEW: Store settings domain
│   │   ├── __init__.py
│   │   ├── models.py            # StoreSetting SQLAlchemy model
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── repository.py        # Setting CRUD with version check
│   │   ├── service.py           # Business logic + encryption
│   │   └── crypto.py            # AES-256-GCM encrypt/decrypt for secrets
│   ├── modules/policies/        # NEW: Policy versions domain
│   │   ├── __init__.py
│   │   ├── models.py            # PolicyVersion SQLAlchemy model
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── repository.py        # Policy read and insert
│   │   └── service.py           # Policy publication with audit
│   └── api/v1/
│       ├── settings.py          # NEW: /admin/settings routes
│       └── policies.py          # NEW: /admin/policies routes
└── tests/
    ├── unit/modules/settings/   # NEW
    ├── unit/modules/policies/   # NEW
    ├── contract/modules/        # NEW contract tests
    └── integration/modules/     # NEW integration tests
```

**Structure Decision**: Follow the existing `modules/<domain>/` pattern used by `modules/auth/`, `modules/audit/`, and `modules/outbox/`. Keep settings and policies as separate modules since they have different lifecycle rules (settings are mutable with versioning; policies are immutable append-only).

## Complexity Tracking

No constitution violations requiring justification.
