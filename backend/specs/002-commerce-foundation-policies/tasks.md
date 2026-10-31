# Tasks: Commerce Foundation and Policies

**Input**: Design documents from `specs/002-commerce-foundation-policies/`

**Prerequisites**: plan.md (complete), spec.md (complete), data-model.md (complete), contracts/ (complete)

**Tests**: All tasks follow TDD — write a failing test first, then implement.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 = Set Store Rules, US2 = Preserve Policy Evidence)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create module directories and the Alembic migration

- [x] T001 Create module directory structure for `modules/settings/` and `modules/policies/` with `__init__.py` files
- [x] T002 Create Alembic migration `0002_commerce_foundation.py` that adds `store_settings` and `policy_versions` tables per data-model.md

---

## Phase 2: Foundational — Settings Encryption and Repository

**Purpose**: AES-256-GCM crypto utilities and database access layer

- [x] T003 [P] [US1] Write unit tests for settings crypto in `tests/unit/modules/settings/test_crypto.py` (encrypt round-trip, decrypt with wrong key, version marker)
- [x] T004 [P] [US1] Implement `modules/settings/crypto.py` with `encrypt_setting_value` / `decrypt_setting_value` using AES-256-GCM
- [x] T005 [P] [US1] Write integration tests for settings repository in `tests/integration/modules/settings/test_settings_repository.py` (create, read, update with version check, version conflict)
- [x] T006 [US1] Implement `modules/settings/repository.py` with `get_by_key`, `get_all`, `upsert_with_version_check`
- [x] T007 [P] [US2] Write integration tests for policies repository in `tests/integration/modules/policies/test_policies_repository.py` (insert, get by type, get effective, version auto-increment)
- [x] T008 [US2] Implement `modules/policies/repository.py` with `insert`, `get_by_type`, `get_effective`, `get_all`

---

## Phase 3: User Story 1 - Set Store Rules (P1) 🎯 MVP

**Goal**: Owner can view and update store settings; stale writes are rejected; secret settings are encrypted and hidden.

**Independent Test**: Update a non-secret setting, read it back, verify version increment and audit trail. Attempt a stale write and verify 409. Write a secret and verify it returns `"***"` in the list.

**⚠️ CRITICAL**: Each test task MUST be written and MUST FAIL before its corresponding implementation task begins.

### Tests for User Story 1

- [x] T009 [P] [US1] Write unit tests for settings service in `tests/unit/modules/settings/test_settings_service.py` (update non-secret, update secret via encrypt path, version conflict raises, unknown key raises, unauthorized role raises)
- [x] T010 [P] [US1] Write contract tests for settings endpoints in `tests/contract/modules/settings/test_settings_contract.py` (GET returns non-secrets only, PUT updates and increments version, PUT secret returns masked, PUT version conflict, GET secret returns plaintext for owner, forbidden for non-owner)
- [x] T011 [P] [US1] Write integration tests for settings module in `tests/integration/modules/settings/test_settings_module.py` (full update-read cycle with PostgreSQL, version increment atomicity, audit log is created, secret round-trip through encrypt/decrypt)

### Implementation for User Story 1

- [x] T012 [P] [US1] Create `StoreSetting` SQLAlchemy model in `modules/settings/models.py`
- [x] T013 [P] [US1] Create Pydantic schemas in `modules/settings/schemas.py` (StoreSettingRead, StoreSettingUpdate, StoreSettingSecretUpdate, RegisterSettingKey for key registry)
- [x] T014 [US1] Implement `modules/settings/service.py` with `get_all_visible`, `update_setting`, `update_secret`, `get_decrypted_secret` using the repository, crypto, and audit log
- [x] T015 [US1] Implement `api/v1/settings.py` routes: `GET /admin/settings`, `PUT /admin/settings`, `PUT /admin/settings/secrets`, `GET /admin/settings/secrets/{key}` with `require_permission("settings.manage")`
- [x] T016 [US1] Register settings router in `main.py`
- [x] T017 [US1] Implement key registry: define the set of allowed setting keys with their expected types and secrecy flags; validate on write

---

## Phase 4: User Story 2 - Preserve Policy Evidence (P2)

**Goal**: Owner can publish immutable policy versions; effective version is used at acceptance time; orders reference the exact version that governed them.

**Independent Test**: Publish a policy, verify it's immutable (no update), publish a future-dated one, verify effective query returns the correct one at the current time.

### Tests for User Story 2

- [x] T018 [P] [US2] Write unit tests for policies service in `tests/unit/modules/policies/test_policies_service.py` (publish new version, version auto-increment, future-dated effective, invalid type rejected)
- [x] T019 [P] [US2] Write contract tests for policies endpoints in `tests/contract/modules/policies/test_policies_contract.py` (POST publishes with auto-version, GET lists by type, GET effective returns latest effective version, 401/403 for unauthenticated/unauthorized)
- [x] T020 [P] [US2] Write integration tests for policies module in `tests/integration/modules/policies/test_policies_module.py` (multiple versions per type, effective query at different times, immutability verified, audit log created, unique constraint on type+version)

### Implementation for User Story 2

- [x] T021 [P] [US2] Create `PolicyVersion` SQLAlchemy model in `modules/policies/models.py`
- [x] T022 [P] [US2] Create Pydantic schemas in `modules/policies/schemas.py` (PolicyVersionRead, PolicyVersionPublish)
- [x] T023 [US2] Implement `modules/policies/service.py` with `publish_version`, `get_effective`, `list_versions` using the repository and audit log
- [x] T024 [US2] Implement `api/v1/policies.py` routes: `GET /admin/policies`, `POST /admin/policies`, `GET /admin/policies/{type}/effective` with `require_permission("settings.manage")`
- [x] T025 [US2] Register policies router in `main.py`

---

## Phase 5: Cross-Cutting — Shared Conventions

**Purpose**: Document and enforce shared error, money, pagination, and idempotency conventions

- [x] T026 [P] [US1] Write unit tests for shared error response helper in `tests/unit/core/test_errors.py` (ApplicationError produces correct status/code/message, error middleware formats consistent response)
- [x] T027 [P] Write unit tests for pagination helper in `tests/unit/core/test_pagination.py` (cursor encode/decode, after+limit, empty result)
- [x] T028 [US1] Implement `core/pagination.py` with `CursorPaginator` that encodes/decodes UUID cursors
- [x] T029 [US1] Verify error response shape matches existing `Error` schema; add `ApplicationError` subtypes for settings/policies if needed

---

## Phase 6: Polish & Validation

**Purpose**: Ensure existing tests still pass, run linters, and validate the full flow

- [x] T030 Run the full test suite and verify all 62 existing auth tests still pass alongside the new commerce foundation tests
- [x] T031 Run Ruff and mypy src; fix any new violations
- [x] T032 Run `alembic upgrade head` from a clean database and verify both 0001 and 0002 migrations apply cleanly
- [x] T033 Verify that `GET /admin/settings` returns an empty list (no settings seeded yet — settings are created by the owner at runtime)
- [x] T034 Verify that creating a setting as a non-owner staff member with `settings.manage` succeeds (FR-001 requires `settings.manage`, not necessarily owner role — the spec says only staff with `settings.manage` may change)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — models and migration needed for repositories
- **Phase 3 (US1)**: Depends on Phase 2 — repository and crypto needed for service
- **Phase 4 (US2)**: Depends on Phase 2 — repository needed for service; can run parallel with US1 after Phase 2
- **Phase 5 (Cross-Cutting)**: Depends on US1 core implementation
- **Phase 6 (Polish)**: Depends on all prior phases

### Parallel Opportunities

- T003, T005, T007 can run in parallel (different test files)
- T009, T010, T011 can run in parallel in Phase 3 tests
- T012, T013 can run in parallel (model and schema)
- T018, T019, T020 can run in parallel in Phase 4 tests
- T021, T022 can run in parallel (model and schema)
- T026, T027 can run in parallel (different test domains)

### Within Each User Story

1. Tests written FIRST, verified to FAIL
2. Models + Schemas (parallel)
3. Service (depends on models + repository)
4. API routes (depends on service)
5. Router registration

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T008)
3. Complete Phase 3: User Story 1 (T009–T017)
4. **STOP and VALIDATE**: Test store settings end-to-end
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 Set Store Rules → Test independently → MVP
3. Add US2 Preserve Policy Evidence → Test independently
4. Add Cross-Cutting conventions → Test
5. Polish and validate

---

## Notes

- The `settings.manage` permission already exists in the seed data from migration 0001.
- No setting seed data is created in the migration — settings are created by the owner at runtime through the API.
- Secret settings use the `outbox_encryption_key` from `Settings` for AES-256-GCM (same key length requirement, 32 bytes).
- The `owner` role grants all permissions including `settings.manage`; any staff with `settings.manage` can write settings regardless of role.
- Policy versions reference `staff_users.id` via FK; the `approved_by` field is set from the authenticated staff identity.
