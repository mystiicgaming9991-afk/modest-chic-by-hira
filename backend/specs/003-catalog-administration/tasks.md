# Tasks: Catalog Administration

**Input**: Design documents from `specs/003-catalog-administration/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/openapi.yaml

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Create module directory `modules/catalog/` with `__init__.py`
- [x] T002 Create Alembic migration `0004_catalog.py` — product_status enum + all 9 tables per TRD §4.4

---

## Phase 2: Models

- [x] T003 [P] Create `modules/catalog/enums.py` — ProductStatus enum
- [x] T004 [P] Create `modules/catalog/models.py` — all 9 entities inheriting BaseModel
- [x] T005 Verify models import and are registered on Base.metadata

---

## Phase 3: US1 — Products and Variants (P1)

### Tests (write first, ensure they fail)

- [x] T006 [P] [US1] Unit tests for catalog service in `tests/unit/modules/catalog/test_catalog_service.py`
- [x] T007 [P] [US1] Contract tests in `tests/contract/modules/catalog/test_catalog_contract.py`
- [x] T008 [P] [US1] Integration tests in `tests/integration/modules/catalog/test_catalog_module.py`

### Implementation

- [x] T009 [P] [US1] Create `modules/catalog/schemas.py` — Pydantic request/response
- [x] T010 [P] [US1] Create `modules/catalog/repository.py` — CRUD with slug/SKU uniqueness checks
- [x] T011 [US1] Create `modules/catalog/service.py` — product + variant lifecycle with audit
- [x] T012 [US1] Create `api/v1/catalog.py` routes — POST/GET/PATCH products, POST variants, PATCH variant
- [x] T013 [US1] Register catalog router in `main.py`

---

## Phase 4: US2 — Categories, Collections, Tags, Media (P2)

### Tests

- [x] T014 [P] [US2] Unit tests for category/collection/tag/media service operations
- [x] T015 [P] [US2] Contract tests for category/collection/tag/media endpoints
- [x] T016 [P] [US2] Integration tests for full catalog read paths

### Implementation

- [x] T017 [P] [US2] Extend repository with category, collection, tag, media CRUD
- [x] T018 [US2] Extend service with category hierarchy, collection ordering, media attach
- [x] T019 [US2] Add routes: categories CRUD, collections CRUD + products, tags CRUD, media POST

---

## Phase 5: Polish

- [x] T020 Run full test suite — all 88 existing + new catalog tests pass
- [x] T021 Ruff check + mypy src
- [x] T022 Verify migration applies cleanly from a fresh database (0001 → 0002 → 0003 → 0004)
- [x] T023 Verify duplicate slug and SKU rejection at API level
- [x] T024 Quickstart smoke test passes
