# Modest Chic Backend — deployment checklist (Spec 021)

## Pre-deployment
- [ ] All migrations applied (`alembic upgrade head`)
- [ ] Seed roles/permissions exist
- [ ] At least one owner staff user exists
- [ ] Backup taken before migration (`pg_dump`)
- [ ] Staging environment smoke-tested

## Health checks
- `GET /health` — liveness only; it remains 200 while required dependencies are unavailable.
- `GET /health/ready` — returns 200 only when PostgreSQL and Redis respond; otherwise it returns 503 with non-sensitive dependency states. The API image health check uses readiness so an orchestrator can withhold traffic.
- The local Compose worker health check verifies its process is alive. It does not prove the email provider or outbox is making progress.

## Environment variables (production)
See `.env.example`:
- `APP_ENV=production`
- `DATABASE_URL`, `REDIS_URL`
- `JWT_SIGNING_KEY` (≥32 bytes)
- `CSRF_SIGNING_KEY` (≥32 bytes)
- `TOTP_ENCRYPTION_KEY` (=32 bytes)
- `OUTBOX_ENCRYPTION_KEY` (=32 bytes)
- `TRUSTED_ORIGINS` — HTTPS only in production
- `EMAIL_PROVIDER=resend` + `RESEND_API_KEY`

## Backup & recovery rehearsal

Set `DATABASE_URL` to the source database and `RESTORE_DATABASE_URL` to a newly
provisioned, isolated restore target. Keep the backup outside the application
container and use the business-approved storage and retention policy. Use
`pg_dump` and `pg_restore` from the same PostgreSQL major version as the source
server, and restore to a server of the same or a newer major version.

```bash
# Create a timestamped custom-format backup.
backup_file="modest-chic-$(date -u +%Y%m%dT%H%M%SZ).dump"
# The app uses SQLAlchemy's +asyncpg driver suffix; libpq tools use a standard
# PostgreSQL URI. This leaves already-compatible postgresql:// URLs unchanged.
pg_source_url="${DATABASE_URL/+asyncpg/}"
pg_restore_url="${RESTORE_DATABASE_URL/+asyncpg/}"
pg_dump --format=custom --file="$backup_file" "$pg_source_url"

# Restore to the isolated target, which must already exist.
pg_restore --exit-on-error --dbname="$pg_restore_url" "$backup_file"

# Record the restored schema revision. Rehearse the application-specific
# record-count/checksum checks and critical customer/staff journeys separately.
DATABASE_URL="$RESTORE_DATABASE_URL" uv run alembic current
```

## Release recovery

- Prefer a forward fix when an application release fails but its schema remains
  compatible with the previous application version.
- Do not use `alembic downgrade -1` as a generic production rollback. Review the
  exact migration downgrade first; dropping columns or constraints can discard
  accepted business data or newly collected evidence.
- Before restoring, rehearse the target, recovery point, data-loss window, and
  traffic switch in an isolated environment. Restore only through the approved
  incident procedure and retain the verification evidence.
- Configure backup coverage, private-object coverage, retention, recovery-time
  objectives, and recovery ownership with the business before launch.
