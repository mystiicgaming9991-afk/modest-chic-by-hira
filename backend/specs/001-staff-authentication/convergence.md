# Spec 001 convergence evidence

**Environment:** PostgreSQL 16 and Redis 7 in the local Compose stack, with distinct application, migration, and bootstrap test databases. The latest complete backend run passed 274 tests plus Ruff and mypy on 25 October 2026. A fresh isolated rerun of `test_bootstrap_email_to_owner_login_refresh_and_logout` passed on 25 October 2026 (one test, one upstream Starlette/httpx deprecation warning). The authentication requirements-quality checklist was reviewed separately from implementation evidence: eleven criteria pass; the TOTP recovery policy remains unspecified. The human-timed first-login usability target is SC-006 and remains pending separately from security-criterion measurability.

| Requirement | Evidence | Status |
|---|---|---|
| FR-001 | `test_bootstrap.py` verifies invited owner, no default password, and local delivery to first login | Pass locally |
| FR-002 | `test_invitation_login.py` verifies acceptance, expiry, reuse, and concurrent single use | Pass |
| FR-003 | `test_security.py` and PostgreSQL normalized-email uniqueness test | Pass |
| FR-004 | Generic unknown, invited, suspended, wrong-password, and valid-login tests | Pass |
| FR-005 | `test_rate_limiter.py` and login throttling integration test | Pass |
| FR-006 | Session contract and expiry tests verify access and refresh lifetimes | Pass |
| FR-007 | Login contract and production cookie assertions | Pass |
| FR-008 | Concurrent refresh and replay-family revocation integration tests | Pass |
| FR-009 | Logout cookie clearing and access revocation integration test | Pass |
| FR-010 | Existing-token role removal and suspension integration test | Pass |
| FR-011 | `test_api_security.py` checks CSRF, trusted Origin, and rejection behavior | Pass |
| FR-012 | Known/unknown response parity, encrypted outbox, superseded-link rejection, and concurrent one-time consumption in `test_password_recovery.py` | Pass locally; live Resend smoke pending |
| FR-013 | Reset expiry, reuse, concurrent consumption, and session revocation tests | Pass |
| FR-014 | Current-password change and session revocation test | Pass |
| FR-015 | TOTP confidentiality, enrollment, login, production gate, and concurrent replay tests | Pass |
| FR-016 | Action-specific metadata allow-list, bounded JSON value handling, and audit redaction checks in `test_repository.py` and auth integration tests | Pass |
| FR-017 | No customer account route is part of the staff-authentication slice | Pass |
| SC-001 | Invitation expiry, reuse, and concurrent acceptance tests | Pass |
| SC-002 | Invalid login, suspended account, and TOTP failure tests | Pass |
| SC-003 | Refresh replay, logout, password reset, and password change tests | Pass |
| SC-004 | Known/unknown forgot responses compare equal in status and body | Pass |
| SC-005 | Role removal and suspension deny an existing access token | Pass |
| SC-006 | Five-minute human first-login journey, excluding email delivery | Pending timed UX validation |
| SC-007 | Logging, audit, encrypted outbox, and TOTP secret-confidentiality tests | Pass locally |

The local bootstrap-to-login smoke uses the in-memory email adapter; it does not prove delivery through a verified production sender. Before release, run the quickstart with a configured Resend account and measure the first-login journey with a staff participant. Do not close T049 until both are recorded. On 25 October 2026, the quickstart's Uvicorn target was corrected to use the existing `create_app` factory; migrations, owner bootstrap, liveness, and PostgreSQL/Redis readiness were then verified against a newly created disposable database and isolated Redis DB 14. The database was dropped and Redis DB 14 cleared after the run.
