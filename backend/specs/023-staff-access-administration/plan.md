# Implementation Plan: Staff Access Administration

**Branch**: `023-staff-access-administration` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

## Summary

Extend the staff authentication module with owner-facing administration: list all staff (identity, status, roles, TOTP enrollment — no secrets), change role assignments, suspend/activate accounts, and enforce the last-active-owner invariant. Suspension immediately revokes all active sessions. All changes are audited.

## Technical Context

**Language/Version**: Python 3.12+, FastAPI, SQLAlchemy 2 async

**Storage**: No new tables. Extends existing `staff_users`, `roles`, `staff_user_roles`, `staff_sessions`.

**Testing**: pytest, pytest-asyncio, HTTPX

**Permissions**: `staff.manage` gates all admin endpoints.

## Design

### Service: `modules/auth/admin_service.py`

- `list_staff(session)` — returns identity, status, roles, TOTP state for all staff
- `assign_roles(staff_user_id, role_keys, actor_id)` — replace roles atomically, audit, versioned
- `remove_roles(staff_user_id, role_keys, actor_id)` — remove specific roles
- `suspend(staff_user_id, actor_id)` — set status=SUSPENDED, revoke all sessions, enforce last-owner check
- `activate(staff_user_id, actor_id)` — set status=ACTIVE
- `_enforce_owner_quorum(staff_user_id)` — reject if this would leave zero active owners

### API: `api/v1/admin_staff.py`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/staff` | List all staff members |
| `PUT` | `/admin/staff/{id}/roles` | Set role assignments |
| `POST` | `/admin/staff/{id}/suspend` | Suspend a staff member |
| `POST` | `/admin/staff/{id}/activate` | Activate a suspended member |

### Key invariants
- Last active owner cannot be suspended or have the `owner` role removed
- Role changes take effect on next request (permissions are resolved from DB on every request, not cached in JWT)
- Suspension revokes all active session families immediately
- `staff.manage` permission required for all operations
