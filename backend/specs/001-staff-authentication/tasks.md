# Tasks: Staff Email and Password Authentication

**Input**: Design documents from `specs/001-staff-authentication/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/openapi.yaml`

**Path convention**: Implementation and test paths are relative to the `backend/` project root.

**Testing**: TDD is mandatory. For each story, author the specified tests first, run them to confirm expected failures, and only then implement the smallest passing production change. PostgreSQL 16 is required for persistence and concurrency integration tests.

## Phase 1: Setup

**Purpose**: Establish the isolated Python API project and reproducible developer environment.

- [x] T001 Create the backend package and test directories from `specs/001-staff-authentication/plan.md` under `src/modest_chic_backend/` and `tests/`.
- [x] T002 Initialize `pyproject.toml` with Python 3.12+, runtime/development dependencies, uv settings, and test/lint/type-check commands.
- [x] T003 [P] Add `.env.example`, local `compose.yaml`, and backend-specific ignore rules for PostgreSQL 16, Redis 7, and secrets.
- [x] T004 [P] Configure Ruff, mypy, pytest, and pytest-asyncio in `pyproject.toml`.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create shared runtime, persistence, and test infrastructure before user-story tests.

- [x] T005 Write unit tests for strict auth settings, environment validation, and secret redaction in `tests/unit/core/test_settings.py` and `tests/unit/core/test_logging.py`.
- [x] T006 Implement settings, error types, request correlation, and structured redacted logging in `src/modest_chic_backend/core/`.
- [x] T007 Write integration tests for request-scoped `AsyncSession` rollback/commit and metadata migration in `tests/integration/db/test_database.py`.
- [x] T008 Implement SQLAlchemy async engine/session lifecycle and Alembic setup in `src/modest_chic_backend/db/` and `migrations/`.
- [x] T009 Write contract tests for API error envelope, health routes, trusted-origin rejection, and CSRF double-submit validation in `tests/contract/test_api_security.py`.
- [x] T010 Implement FastAPI app factory, versioned router, validation/error translation, CORS/origin, and CSRF middleware/dependencies in `src/modest_chic_backend/main.py`, `src/modest_chic_backend/api/`, and `src/modest_chic_backend/core/`.
- [x] T011 Write unit tests for email normalization, compliant password length/UTF-8 bytes, token generation/digests, JWT algorithm pinning, and bcrypt work factor in `tests/unit/modules/auth/test_security.py`.
- [x] T012 Implement auth primitives and typed password/token/JWT helpers in `src/modest_chic_backend/modules/auth/security.py`.
- [x] T013 Write unit and integration tests for encrypted outbox payloads, claiming/recovery, email delivery, and provider idempotency in `tests/unit/modules/outbox/` and `tests/integration/modules/outbox/test_outbox_repository.py`.
- [x] T014 Implement outbox records, repositories, worker dispatch, email protocol, local fake adapter, and Resend adapter in `src/modest_chic_backend/modules/outbox/` and `src/modest_chic_backend/providers/email/`.
- [x] T015 Write tests for staff/role/session/invitation/reset/audit ORM constraints and TOTP counter columns in `tests/integration/modules/auth/test_auth_schema.py`.
- [x] T016 Implement auth and audit SQLAlchemy models plus initial migration in `src/modest_chic_backend/modules/auth/models.py`, `src/modest_chic_backend/modules/audit/models.py`, and `migrations/versions/`.
- [x] T017 Write tests for Redis rate-limit keys, identity/network buckets, limits, and unavailable-Redis fail-closed behavior in `tests/integration/core/test_rate_limiter.py`.
- [x] T018 Implement shared Redis rate limiter and dependency wiring in `src/modest_chic_backend/core/rate_limit.py`.

## Phase 3: User Story 1 - Invite and Sign In Staff (Priority: P1)

**Goal**: Establish an invited owner/staff account without default passwords and support secure email/password login.

**Independent Test**: Bootstrap owner, accept valid invitation once, log in with valid credentials, reject invalid/unknown/invited/suspended users uniformly, and confirm rate limits and audit events.

### Tests for User Story 1 (write/run before implementation)

- [x] T019 [P] [US1] Write OpenAPI contract tests for invite, accept-invitation, and login schemas/statuses/cookies (FR-002–FR-004, FR-011) in `tests/contract/modules/auth/test_invitation_login_contract.py`.
- [x] T020 [P] [US1] Write PostgreSQL integration tests for bootstrap, normalized-email uniqueness, concurrent single-use invite acceptance, generic login failures, valid login, TOTP-enabled login, restricted enrollment-only session, throttling, and audit redaction (FR-001–FR-005, FR-015–FR-016) in `tests/integration/modules/auth/test_invitation_login.py`.

### Implementation for User Story 1

- [x] T021 [US1] Implement staff, role, invitation, and audit repositories with normalized-email and row-lock operations (FR-002–FR-004, FR-016) in `src/modest_chic_backend/modules/auth/repository.py` and `src/modest_chic_backend/modules/audit/repository.py`.
- [x] T022 [US1] Implement restricted `bootstrap-owner` CLI to create an invited owner and self-referencing one-time invitation, never a password (FR-001), in `src/modest_chic_backend/modules/auth/bootstrap.py` and `src/modest_chic_backend/cli.py`.
- [x] T023 [US1] Implement owner-only staff invitation service, token hashing, role assignment, audit, and transactional outbox enqueue (FR-002, FR-016) in `src/modest_chic_backend/modules/auth/invitations.py`.
- [x] T024 [US1] Implement invitation acceptance transaction with password policy, bcrypt, one-time expiry/supersession, account activation, and audit (FR-002–FR-003, FR-016) in `src/modest_chic_backend/modules/auth/invitations.py`.
- [x] T025 [US1] Implement generic email/password/TOTP login, dummy verification for unknown/invited accounts, atomic session creation, rate limiting, and audit (FR-004–FR-006, FR-015–FR-016) in `src/modest_chic_backend/modules/auth/service.py`.
- [x] T026 [US1] Implement invitation/login routes, request schemas, generic error responses, access JWT, and protected refresh cookie attributes (FR-002–FR-007, FR-011) in `src/modest_chic_backend/api/v1/auth.py` and `src/modest_chic_backend/modules/auth/schemas.py`.
- [x] T027 [US1] Run US1 contract and PostgreSQL tests, confirm all acceptance scenarios, and record test-first failure/pass evidence in `specs/001-staff-authentication/tasks.md`.

## Phase 4: User Story 2 - Protect and End Staff Sessions (Priority: P1)

**Goal**: Rotate/revoke sessions and apply account status and current permission changes immediately.

**Independent Test**: Login, rotate refresh, replay old credential to revoke family, logout, then verify suspended/permission-removed staff cannot use a still-unexpired access JWT.

### Tests for User Story 2 (write/run before implementation)

- [x] T028 [P] [US2] Write contract tests for refresh, logout, current staff identity, and protected-route authorization (FR-006–FR-011) in `tests/contract/modules/auth/test_auth_workflows_contract.py`.
- [x] T029 [P] [US2] Write PostgreSQL concurrency tests for two simultaneous refreshes, replay family revocation, expiry, logout, suspension, and role revocation (FR-008–FR-010, FR-016) in `tests/integration/modules/auth/test_sessions.py`.

### Implementation for User Story 2

- [x] T030 [US2] Implement session repository queries and lock ordering with retained rotated hashes (FR-008–FR-010) in `src/modest_chic_backend/modules/auth/repository.py`.
- [x] T031 [US2] Implement atomic refresh rotation/replay detection, family/user revoke, and logout (FR-008–FR-009) in `src/modest_chic_backend/modules/auth/sessions.py`.
- [x] T032 [US2] Implement bearer authentication that verifies JWT/session family/user state, loads current permissions, and limits non-enrolled production users to enrollment-only capability (FR-006, FR-010, FR-015) in `src/modest_chic_backend/modules/auth/service.py` and `src/modest_chic_backend/api/v1/dependencies.py`.
- [x] T033 [US2] Implement refresh, logout, and `/auth/me` routes, cookie clearing, and authenticated current identity response (FR-006–FR-011) in `src/modest_chic_backend/api/v1/auth.py`.
- [x] T034 [US2] Run US2 contract and PostgreSQL tests, confirming replay and immediate permission/state effects, in `specs/001-staff-authentication/tasks.md`.

## Phase 5: User Story 3 - Recover or Change a Password (Priority: P1)

**Goal**: Support indistinguishable forgot-password requests, single-use email reset links, and current-password-protected password changes.

**Independent Test**: Compare known/unknown forgot responses, consume a reset only once, verify all sessions are revoked, and reject wrong current password without changing the credential.

### Tests for User Story 3 (write/run before implementation)

- [x] T035 [P] [US3] Write contract tests for forgot, reset, and password-change route status behavior (FR-012–FR-014) in `tests/contract/modules/auth/test_auth_workflows_contract.py`.
- [x] T036 [P] [US3] Write PostgreSQL integration tests for generic known/unknown reset response, 30-minute expiry, one-time concurrent consumption, email outbox payload handling, password change, and session revocation (FR-012–FR-016) in `tests/integration/modules/auth/test_password_recovery.py`.

### Implementation for User Story 3

- [x] T037 [US3] Implement reset-token issue/consume under row lock, password replacement, all-session revocation, and audit (FR-012–FR-013, FR-016) in `src/modest_chic_backend/modules/auth/passwords.py`.
- [x] T038 [US3] Implement generic forgot-password behavior, per-email/IP throttling, and encrypted transactional outbox delivery (FR-005, FR-012, FR-016) in `src/modest_chic_backend/modules/auth/passwords.py` and `src/modest_chic_backend/modules/outbox/`.
- [x] T039 [US3] Implement forgot, reset, and current-password change API routes with no account enumeration (FR-012–FR-014) in `src/modest_chic_backend/api/v1/auth.py`.
- [x] T040 [US3] Run US3 API and PostgreSQL tests, including identical known/unknown responses and credential/session invariants, in `specs/001-staff-authentication/tasks.md`.

## Phase 6: User Story 4 - Complete Multi-Factor Enrollment (Priority: P1)

**Goal**: Enroll staff TOTP safely, reject replayed codes, and require verified setup for production admin access.

**Independent Test**: Begin enrollment, verify once, reject replay/invalid code, require TOTP at enabled-account login, and block privileged production access until verified enrollment.

### Tests for User Story 4 (write/run before implementation)

- [x] T041 [P] [US4] Write API contract tests for enrollment provisioning and verification responses (FR-015) in `tests/contract/modules/auth/test_auth_workflows_contract.py`.
- [x] T042 [P] [US4] Write PostgreSQL tests for AES-GCM seed confidentiality, valid/invalid/missing/replayed TOTP codes, concurrent counter update, production gate, and login challenge (FR-015–FR-016) in `tests/integration/modules/auth/test_totp.py`.

### Implementation for User Story 4

- [x] T043 [US4] Implement TOTP seed encryption, pending enrollment state, code verification, counter locking/replay prevention, and audit (FR-015–FR-016) in `src/modest_chic_backend/modules/auth/totp.py` and `src/modest_chic_backend/modules/auth/totp_service.py`.
- [x] T044 [US4] Implement TOTP enrollment/verification endpoints and ensure production authorization denies incomplete enrollment (FR-015) in `src/modest_chic_backend/api/v1/auth.py` and `src/modest_chic_backend/api/v1/dependencies.py`.
- [x] T045 [US4] Run US4 API and PostgreSQL tests and confirm no secrets appear in responses/logs beyond the one-time enrollment secret in `specs/001-staff-authentication/tasks.md`.

## Phase 7: Polish and Cross-Cutting Validation

**Purpose**: Prove the complete flow, migrations, and code quality against the contract.

- [x] T046 [P] Update `README.md` and `specs/001-staff-authentication/quickstart.md` with actual commands, bootstrap procedure, and safe local email adapter behavior.
- [x] T047 Run clean PostgreSQL migration-upgrade and downgrade/recovery tests in `tests/integration/db/test_migrations.py`.
- [x] T048 Run complete unit, contract, and PostgreSQL integration suites plus Ruff and mypy; resolve only feature-local failures.
- [ ] T049 Run `specs/001-staff-authentication/quickstart.md` end-to-end and reconcile every FR/SC against implementation and test evidence.

## Current Delivery Note

The staff email/password authentication slice, session protection, password recovery,
TOTP enrollment, durable encrypted email outbox, PostgreSQL migration, and operator
runbook are implemented. PostgreSQL acceptance tests now cover concurrent invite,
refresh, reset, and TOTP transitions; session expiry, suspension, role removal,
throttling, and audit redaction. A red regression test showed that a wrong password
consumed a valid TOTP code; the authentication service now verifies the password
before consuming the second factor, and the test passes. Existing-implementation
acceptance tests were backfilled rather than falsely claimed as red-first work.
Full backend validation with separate test, migration, and bootstrap databases
passed 274 tests, Ruff, and mypy on 25 October 2026. The reviewed auth quality
checklist now has eleven satisfied criteria; TOTP recovery remains unspecified.
SC-006 is a human-timed usability measure, separate from deterministic verification
of the security criteria. A new integration
regression proves a newer reset request invalidates an earlier unused reset link,
and the full recovery test module passes. A fresh isolated rerun of
the local in-memory email smoke passed bootstrap invitation through login,
refresh, and logout. The FR/SC audit is recorded in `convergence.md`. T049
now also has a verified local quickstart run: its Uvicorn command was corrected
to use `create_app --factory`, then migrations, bootstrap-owner, liveness, and
database/Redis readiness succeeded on a disposable database. T049 remains open
for a real Resend delivery quickstart and timed human first-login check; these
require a verified sender, API credential, and a staff participant. No
production email credentials are assumed in automated tests.

## Dependencies and Execution Order

- Setup T001-T004 precedes all feature work.
- Foundational T005-T018 precedes every user story.
- US1 T019-T027 establishes staff/session creation; US2 T028-T034 depends on US1 login/session data.
- US3 T035-T040 depends on shared staff/password/session tables but is independently testable after foundation; implement after US1 so test fixtures are stable.
- US4 T041-T045 depends on auth identity and login, so follows US1; US2/US3 can be developed before or after it.
- Polish T046-T049 depends on all stories intended for release.

## Parallel Opportunities

- T003 and T004 can run concurrently with project setup review.
- In the foundation, settings/logging tests, DB tests, and rate-limit tests target separate files; production implementation still follows each failing test.
- For each story, contract and integration test files can be authored independently before its implementation starts.
- Story implementations have shared service/router/repository files and should be delivered sequentially to avoid file conflicts.

## MVP and Delivery Strategy

The requested MVP is US1 email/password access via invitation; however, a production release must not expose login without US2 session revocation/current authorization. Treat US1+US2 as the minimum deployable increment, then add recovery and production TOTP before enabling production admin access. Do not claim full-feature completion until all P1 flows and convergence checks pass.
