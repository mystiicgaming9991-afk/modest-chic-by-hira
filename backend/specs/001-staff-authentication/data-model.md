# Data Model: Staff Email and Password Authentication

All timestamps are UTC `TIMESTAMPTZ`; IDs are UUIDs. Foreign keys, uniqueness, status checks, and partial indexes are enforced by PostgreSQL migrations. Secret values are never persisted in plaintext except transiently in the outbox payload protected by the deployment's configured encryption boundary; credential tables contain only digests/ciphertext.

## StaffUser

Represents an invite-only staff identity.

| Field | Type | Constraints |
|---|---|---|
| id | UUID | Primary key |
| email | VARCHAR(255) | Required; lookup and uniqueness use `lower(trim(email))` |
| display_name | VARCHAR(255) | Required |
| hashed_password | VARCHAR(255) nullable | Null only while invited; bcrypt work factor 12; active/suspended users require a value |
| status | enum | `INVITED`, `ACTIVE`, `SUSPENDED` |
| totp_secret | VARCHAR(255) nullable | AES-256-GCM encrypted value; never returned after enrollment |
| totp_enabled | BOOLEAN | Defaults false |
| totp_last_counter | BIGINT nullable | Last accepted TOTP counter; updated atomically to prevent replay |
| last_login_at | TIMESTAMPTZ nullable | Updated on successful login |
| created_at / updated_at | TIMESTAMPTZ | Required |

`INVITED -> ACTIVE` occurs only after valid invitation acceptance sets the password. `ACTIVE -> SUSPENDED` blocks access immediately. Email identity is case-insensitive through normalized storage and a unique index.

## Role, Permission, and Assignments

- `roles`: UUID, unique `key`, label, created timestamp.
- `permissions`: UUID, unique permission `key`, description.
- `staff_user_roles`: `(staff_user_id, role_id)` primary key, `assigned_by`, `assigned_at`.
- `role_permissions`: `(role_id, permission_id)` primary key.
- Permission/role changes are read from PostgreSQL on each protected request; they are not trusted from the access JWT.

## StaffInvitation

| Field | Type | Constraints |
|---|---|---|
| id | UUID | Primary key |
| email | VARCHAR(255) | Required; matches invitee by normalized email |
| token_hash | VARCHAR(255) | Required, unique digest of random secret |
| invited_by | UUID | Required FK to staff user; bootstrap invitation references its invited owner |
| expires_at | TIMESTAMPTZ | Required; 24 hours after creation |
| accepted_at | TIMESTAMPTZ nullable | Set once under row lock |
| revoked_at | TIMESTAMPTZ nullable | Used when superseded/revoked |
| created_at | TIMESTAMPTZ | Required |

## StaffSession

| Field | Type | Constraints |
|---|---|---|
| id | UUID | Primary key; access JWT `session_id` |
| staff_user_id | UUID | FK to staff user |
| family_id | UUID | Required; indexed; common to rotated descendants |
| token_hash | CHAR(64) | Required, unique SHA-256 hex digest |
| expires_at | TIMESTAMPTZ | Required; at most seven days from issue |
| rotated_at | TIMESTAMPTZ nullable | Old hash retained for replay detection |
| revoked_at | TIMESTAMPTZ nullable | Family/user revocation timestamp |
| created_at | TIMESTAMPTZ | Required |

Refresh locks the presented row, verifies not expired/revoked/rotated, marks it rotated, and inserts its successor in one transaction. A rotated-token replay revokes all sessions in that family.

## StaffPasswordReset

| Field | Type | Constraints |
|---|---|---|
| id | UUID | Primary key |
| staff_user_id | UUID | FK to staff user |
| token_hash | BYTEA | Required, unique SHA-256 digest |
| expires_at | TIMESTAMPTZ | 30 minutes after creation |
| consumed_at | TIMESTAMPTZ nullable | Set once under row lock |
| created_at | TIMESTAMPTZ | Required |

Successful consumption updates the bcrypt password and revokes every active session in one transaction.

At most one unexpired reset request may remain unused for an active staff member. A new request marks all prior unused reset requests consumed in the same transaction that stores the new request and encrypted email. Request and consumption operations lock the staff row before reset rows, so concurrent requests and link use serialize without reversing lock order.

## AuditLog

Record `actor_id`, `action`, `entity_type`, `entity_id`, `correlation_id`, action-allow-listed JSON metadata, and timestamp. Metadata contains bounded JSON scalars or scalar lists only; unknown actions and keys, nested objects, and oversized values are omitted. Passwords, email addresses, raw tokens or token-bearing links, TOTP codes, and TOTP material are prohibited.

## OutboxEvent

Record event type, aggregate ID, minimal delivery payload, status, attempt count, next attempt, lease, created/processed timestamps. Invitation and reset mail are queued transactionally with their corresponding invitation/reset records. Worker delivery is at-least-once and idempotent; provider I/O is outside the business transaction.

## Invariants

- Every `ACTIVE` or `SUSPENDED` user has a password digest; invited users cannot authenticate. Email lookup and uniqueness follow the database expression `lower(trim(email))`.
- No raw refresh, invitation, or reset secret is stored in a credential table.
- At most one successful consumer accepts a given invitation or password-reset token.
- At most one unused, unexpired password-reset request exists per staff member; issuing a new one invalidates its predecessors.
- Session-family replay revocation, password change/reset revocation, account state changes, audit, and outbox insertion commit atomically with their business transition.
- TOTP verification stores a strictly increasing accepted counter under account-row lock.
