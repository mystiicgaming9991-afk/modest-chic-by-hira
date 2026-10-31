# Data Model: Commerce Foundation and Policies

All timestamps are UTC `TIMESTAMPTZ`; IDs are UUIDs. Foreign keys and uniqueness are enforced by PostgreSQL. Secret setting values are AES-256-GCM encrypted at rest; the encrypted blob is stored as a JSONB wrapper (`{ "v": 1, "ciphertext": "<b64>", "nonce": "<b64>" }`). Policy versions are immutable—inserted once and never updated.

## StoreSetting

Represents a named, versioned business configuration with an optional secrecy flag.

| Field | Type | Constraints |
|---|---|---|
| id | UUID | Primary key |
| key | VARCHAR(100) | Required, UNIQUE; stable lookup key (e.g., `fulfillment.availability`, `operational.quote_timeout_seconds`) |
| value | JSONB | Required; plain JSON for non-secret settings; ciphertext wrapper for secrets |
| is_secret | BOOLEAN | Required, DEFAULT FALSE; when TRUE, value is encrypted and never returned in reads |
| version | INT | Required, DEFAULT 1; incremented atomically on every write for optimistic concurrency |
| updated_by | UUID | FK → `staff_users.id`; the staff member who made the last change |
| updated_at | TIMESTAMPTZ | Required; set on every write |

**Rules**:
- Writes require the current `version` to match the stored version (optimistic concurrency). A mismatch returns a conflict error.
- Secret settings can only be written through a dedicated endpoint that accepts the plaintext secret and encrypts it.
- Reads return `"***"` as the value for secret settings.
- Invalid keys (not in the approved key registry) are rejected.
- The full setting history is preserved via audit log records; the table only stores the latest version.

## PolicyVersion

Represents an immutable approved policy text with an effective date. Once inserted, it cannot be modified.

| Field | Type | Constraints |
|---|---|---|
| id | UUID | Primary key |
| type | VARCHAR(100) | Required; one of `checkout_bundle`, `returns`, `shipping`, `privacy`, `terms`, `cod_confirmation` |
| version | INT | Required; auto-incremented within each type |
| effective_from | TIMESTAMPTZ | Required; when this version becomes governing |
| content | JSONB | Required; the immutable approved policy text (structure depends on type) |
| approved_by | UUID | FK → `staff_users.id`; the staff member who approved this version |
| created_at | TIMESTAMPTZ | Required |

UNIQUE(`type`, `version`)

**Rules**:
- New versions are inserted, never updated.
- The effective version for a given type at time T is the one with the largest `effective_from` ≤ T.
- Future-dated policies are not used until their `effective_from` time arrives.
- Orders and consent decisions reference the specific `policy_versions.id` that governed them at acceptance time.
- Each accepted order retains one immutable acceptance link for every policy shown at checkout (`checkout_bundle`, `shipping`, and `returns`), including the policy type and acceptance timestamp. Publishing a newer version does not change those links.
- Only staff with `settings.manage` may insert policy versions.

## Cross-Feature Reportable Record Conventions (FR-009)

These are design-time constraints enforced when later features plan their data models:

1. **Stable business links**: Every commerce record (order, payment, shipment, return, refund) must reference its owning entity by a stable UUID FK, not a mutable status or sequence number.
2. **Immutable snapshots**: Orders capture customer-facing price, item, policy version, and address at acceptance time. These are never mutated after acceptance.
3. **Deduplicated transitions**: Lifecycle events (order status changes, payment attempts, shipment milestones) use unique event IDs and a separate event table; the current status column is a denormalized projection.
4. **Trusted timestamps**: Every event records `occurred_at` (when it happened in the real world), `recorded_at` (when the system received it), and `effective_at` (when it takes effect, if different).
5. **Typed dimensions**: Non-sensitive dimensions (e.g., payment method, fulfillment type, city) use ENUM or constrained VARCHAR, never free text for aggregation. Free-text notes are separate.
6. **Privacy-safe**: No PII in dimension columns used for aggregation. Personal data is in separate columns or tables with access controls.
7. **Measured indexes**: Partial indexes on active states for working queues; time-range indexes on event tables for financial reporting.

## Invariants

- Setting writes are atomic: the value update, version increment, audit log, and optional outbox event commit in one transaction.
- Policy version inserts are atomic: the row insert, audit log, and optional outbox event commit in one transaction.
- No secret setting value appears in any GET response; the API returns `"***"` and the authenticated owner must use a separate secret-specific endpoint to retrieve the actual value.
- The `settings.manage` permission gates all setting and policy mutations.
- Existing staff, session, audit, and outbox records are preserved unchanged.
- The shared `Error` schema (`code`, `message`, `request_id`) is the only error response shape for all new endpoints.
