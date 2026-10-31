<!--
Sync Impact Report
- Version: none -> 1.0.0 (initial constitution)
- Principles added: Contract-First Modular Design; Test-First Development; Atomic Domain Changes; Secure Defaults; Observable, Simple Operations
- Sections added: Backend Constraints; Development and Verification
- Sections removed: none
- Follow-up TODOs: none
-->

# Modest Chic Backend Constitution

## Core Principles

### I. Contract-First Modular Design
Implement backend behavior against the approved PRD, TRD, HLD, LLD, and feature specification. Keep FastAPI routers, domain services, repositories, and provider adapters within their documented module boundaries. Public API, lifecycle, and persistence changes require an updated contract and compatibility review before implementation.

### II. Test-First Development (NON-NEGOTIABLE)
For every behavior change, write focused tests before production code. Run them and record the expected failure, implement the smallest change that makes them pass, then refactor while keeping tests green. Do not mark a task complete without the relevant test evidence. Defects discovered during implementation become regression tests before fixes.

### III. Atomic Domain Changes
Persist each business transition and its durable events in one PostgreSQL transaction. Keep one transaction boundary per application service operation; collaborators share the same session and never commit independently. Apply the documented lock ordering and idempotency rules to checkout, inventory, payments, refunds, returns, and settlement operations. Perform external network calls outside database transactions through durable outbox work.

### IV. Secure Defaults
Validate all external input at the API boundary. Store passwords only with the approved password hash, store only hashes of opaque refresh and reset tokens, and never log secrets or personal data. Enforce authentication, authorization, CSRF, origin, rate-limit, and account-state checks on every applicable route. Public access tokens remain scoped to their exact order and permitted actions.

### V. Observable, Simple Operations
Use structured logs with request correlation and secret/PII redaction. Model retries, idempotency, failure states, and operator recovery explicitly. Prefer the smallest maintainable design that meets the documented correctness and security requirements; do not introduce infrastructure or abstractions without a demonstrated need.

## Backend Constraints

- Use Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 async sessions, Alembic, and PostgreSQL 16 as defined in the backend technical requirements.
- Store money as integer minor units and timestamps as UTC. Preserve the documented PostgreSQL constraints, enums, indexes, and state transitions in migrations.
- Keep integrations behind typed provider interfaces. Provider calls, email, and courier actions must be retry-safe and outside business transactions.
- Treat the four backend design documents as the source of product and system requirements. Resolve conflicts in feature specifications before code changes.

## Development and Verification

- Use Spec Kit stages for every bounded feature: specify, clarify when needed, plan, checklist, tasks, analyze, implement, and converge. Review and reconcile each artifact before advancing.
- Keep features small enough to test independently. Trace each task to a functional requirement, acceptance scenario, or constitution principle.
- Run unit tests for domain logic and integration tests for persistence, HTTP contracts, security boundaries, and concurrent transitions. Use PostgreSQL-backed tests for database behavior that SQLite cannot faithfully model.
- Validate migrations from a clean database and verify rollback or recovery behavior for schema changes.
- Do not claim a feature is complete until Spec Kit convergence reports no remaining work and required tests pass.

## Governance

This constitution governs backend specifications, plans, tasks, implementation, and review. Amend it only when an established project rule changes; record the reason, affected principles, and semantic version change in the sync impact report. Feature specifications may add stricter rules but may not weaken these principles without an explicit constitution amendment. Review each implementation and convergence report against all applicable MUST statements.

**Version**: 1.0.0 | **Ratified**: 2026-10-24 | **Last Amended**: 2026-10-24
