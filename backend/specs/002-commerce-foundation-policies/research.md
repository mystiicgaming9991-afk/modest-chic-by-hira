# Research: Commerce Foundation and Policies

**Feature**: 002-commerce-foundation-policies

## Decision 1: AES-256-GCM Secret Encryption

**Choice**: Use `cryptography` library's AES-256-GCM with the existing `outbox_encryption_key` from `Settings`.

**Alternatives considered**:
- Fernet (simpler but uses AES-128-CBC, no built-in nonce handling suitable for DB storage)
- Separate encryption key (unnecessary complexity; 32-byte key already strict-validated)

**Decision**: Reuse `outbox_encryption_key` for secret settings encryption. Store ciphertext as `{ "v": 1, "ciphertext": "<b64>", "nonce": "<b64>" }` JSONB. Version marker allows key rotation in the future.

**Resolved**: Yes.

## Decision 2: Version-Based Optimistic Concurrency

**Choice**: Require the client to send the current `version` with each write. Server increments atomically and rejects on mismatch.

**Alternatives considered**:
- `updated_at` timestamp comparison (clock skew risk across replicas)
- ETags (adds HTTP header complexity without material benefit for an admin API)

**Decision**: Simple integer version column, incremented atomically under row lock.

**Resolved**: Yes.

## Decision 3: Policy Immutability

**Choice**: Policy versions are inserted once and never updated or deleted. The `UNIQUE(type, version)` constraint prevents duplicate version numbers.

**Alternatives considered**:
- Soft-delete with `deleted_at` (policy versions are legal evidence; deleting them destroys the paper trail)

**Decision**: Pure append-only table. The effective version is determined by `effective_from` ≤ NOW() with the highest version number.

**Resolved**: Yes.

## Decision 4: Key Registry for Setting Validation

**Choice**: Hard-code the set of valid setting keys in the application, each with its expected JSON schema type (string, integer, boolean, object, array) and secrecy flag.

**Alternatives considered**:
- Schema validation via JSON Schema stored in DB (more flexible but overkill for ~40 settings)
- Allow any key with any value (bypasses validation, breaks cross-feature contracts)

**Decision**: Maintain a Python dict for the registry. Add to it as new features introduce new settings. The registry is the authoritative list of known keys.

**Resolved**: Yes.

## Decision 5: Error Response Shape

**Choice**: Use the existing `Error` schema (`{ "code": "...", "message": "..." }`) already defined in Spec 001's OpenAPI contract. No changes to the existing `ApplicationError` base class.

**Alternatives considered**:
- RFC 7807 Problem Details (adds `type`, `title`, `detail`, `instance` fields that don't map to the existing contract)
- Separate error shape per module (inconsistent, breaks the shared contract)

**Decision**: Stick with the established `code` + `message` pattern. Add `request_id` as an optional field for correlation.

**Resolved**: Yes.
