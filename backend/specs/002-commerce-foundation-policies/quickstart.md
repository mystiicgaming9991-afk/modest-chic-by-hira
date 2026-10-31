# Quickstart: Commerce Foundation and Policies

## Prerequisites

1. A running PostgreSQL 16 instance configured per the backend TRD
2. A running Redis 7 instance
3. `.env` file in `backend/` with all required `Settings` values (see Spec 001 quickstart)
4. The staff authentication migration (0001) already applied
5. At least one staff member with the `owner` role (or `settings.manage` permission)

## Setup

```bash
cd backend

# Apply the new migration
uv run alembic upgrade head

# Verify the current migration head (as of 2026-10-25)
uv run alembic current
# Expected output: 0021_order_policy_acceptances (head)
```

## Smoke Test: Store Settings

### 1. Authenticate as Owner

```bash
# Get CSRF token
curl -c cookies.txt http://localhost:8000/api/v1/auth/csrf
CSRF=$(awk '$6 == "mc_csrf" { print $7 }' cookies.txt)

# Login (replace with actual credentials; Origin must be in TRUSTED_ORIGINS)
LOGIN=$(curl -sS -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Origin: http://localhost:3000" \
  -d '{"email":"owner@modestchic.pk","password":"..."}' \
  http://localhost:8000/api/v1/auth/login)

TOKEN=$(printf '%s' "$LOGIN" | jq -r '.access_token')

# Admin mutations require trusted Origin plus the signed CSRF cookie and header,
# including when using a bearer access token directly.
admin_write() {
  curl -sS -b cookies.txt -c cookies.txt \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -H "Origin: http://localhost:3000" \
    -H "X-CSRF-Token: $CSRF" "$@"
}
```

### 2. List Settings (Initially Empty)

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/settings
# A fresh database returns { "items": [] }; otherwise this lists the current settings.
```

### 3. Create/Update a Non-Secret Setting

```bash
admin_write -X PUT \
  -d '{"key":"operational.quote_timeout_seconds","value":300,"version":1}' \
  http://localhost:8000/api/v1/admin/settings
# Expected: { "key": "operational.quote_timeout_seconds", "value": 300, "version": 2, ... }
```

### 4. Verify Stale Write Rejection

```bash
admin_write -X PUT \
  -d '{"key":"operational.quote_timeout_seconds","value":600,"version":1}' \
  http://localhost:8000/api/v1/admin/settings
# Expected: 409 with code "SETTING_VERSION_CONFLICT"
```

### 5. Write a Secret Setting

```bash
admin_write -X PUT \
  -d '{"key":"provider.resend_api_key","value":"re_abc123","version":1}' \
  http://localhost:8000/api/v1/admin/settings/secrets
# Expected: the response contains value "***", never the submitted secret.
```

### 6. Read Back Secret (Owner)

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/settings/secrets/provider.resend_api_key \
  | jq -e '.key == "provider.resend_api_key" and (.value | type == "string")'
# The endpoint decrypts for authorized server-side use. Filter its response so
# the plaintext secret is not printed into terminal history or logs.
```

## Smoke Test: Policy Versions

### 1. Publish a Policy

```bash
admin_write -X POST \
  -d '{
    "type": "returns",
    "effective_from": "2026-10-24T00:00:00Z",
    "content": {
      "title": "Returns Policy v1",
      "return_window_days": 7,
      "conditions": "Unworn, tags attached, original packaging"
    }
  }' \
  http://localhost:8000/api/v1/admin/policies
# Expected: 201 with { "id": "...", "type": "returns", "version": 1, ... }
```

### 2. List Policies by Type

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/policies?type=returns
# Expected: { "items": [{ ... policy version 1 ... }] }
```

### 3. Get Effective Policy

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/policies/returns/effective
# Expected: The policy version with effective_from <= now, highest version
```

## Validation Checklist

- [ ] Non-secret settings visible in GET `/admin/settings`
- [ ] Secret settings return `"***"` in GET, not plaintext
- [ ] Version mismatch returns 409
- [ ] Unknown setting keys return 400
- [ ] Unauthenticated requests return 401
- [ ] Staff without `settings.manage` return 403
- [ ] Policy versions are immutable (PUT returns 405 or similar)
- [ ] Policy version auto-increments within type
- [ ] Existing auth endpoints still work (login, me, refresh)
- [ ] `ruff check src tests` passes
- [ ] `mypy src` passes
