# Implementation Plan: deployment and recovery

**Status**: Local readiness and migration checks exist; production recovery is not verified (reviewed 2026-10-25).

## Implemented

- Liveness and readiness endpoints distinguish application process health from required database/Redis availability.
- The canonical Compose file starts PostgreSQL, Redis, API, and worker services with valid local settings; the API container health check uses readiness, while the worker has a process liveness check.
- Readiness returns 503 with non-sensitive dependency status when PostgreSQL or Redis is unavailable, without changing the liveness response.
- Database migration upgrade/downgrade has a clean-PostgreSQL integration test. Local backend and frontend build/test checks are documented in the integration review.
- A local PostgreSQL 16 custom-format backup restored into a new isolated database; Alembic reported head and the five built-in role rows matched the source. This schema/seed smoke does not verify production data coverage, private objects, retention, checksums, or recovery time.
- Outbox jobs use leases and bounded retries so worker process restarts do not discard queued authentication email.

## Remaining

- Select and configure production hosting, secret ownership/rotation, traffic gating, deployment rollback, and background-worker operations.
- Configure commerce database and required private-object backups, business-approved retention, access ownership, and recovery objectives.
- Rehearse restore into an isolated environment and retain record-count/checksum and recovery-time evidence.
- Add operational dashboards/alerts for API, worker, provider failures, and business exceptions, plus named incident/recovery procedures.
- Run risk-based release assurance and end-to-end customer/staff journeys in the actual deployment environment.
