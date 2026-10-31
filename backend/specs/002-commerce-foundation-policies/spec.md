# Feature Specification: Commerce Foundation and Policies

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§5–6, 11–13; `BACKEND_TRD.md` §§4.2, 7–8, 11; `BACKEND_HLD.md` §§3, 5–6; TASK-001, TASK-004, TASK-007.

## User Scenarios & Testing

### User Story 1 - Set Store Rules (Priority: P1)

An owner can view and update approved store rules such as fulfillment availability, operational timeouts, and public policy references. Staff and customer flows use the effective version rather than a hard-coded value.

**Independent Test**: Change one non-secret setting, read it back with its new version, and verify a dependent quote uses the effective value.

**Acceptance Scenarios**:

1. **Given** an owner and a valid setting, **When** they update it, **Then** the new version and actor are recorded and subsequent reads use the new value.
2. **Given** a staff member without settings permission, **When** they attempt a change, **Then** no value or version changes.
3. **Given** an unapproved fulfillment or payment rule, **When** a customer flow requires it, **Then** that option is unavailable with a clear, safe explanation.

### User Story 2 - Preserve Policy Evidence (Priority: P1)

The business can publish effective policy versions and tie each accepted order or consent decision to the version that applied at the time.

**Independent Test**: Accept an order under one policy, publish a newer version, and verify the order still points to the original text and effective date.

**Acceptance Scenarios**:

1. **Given** an effective policy, **When** an order or consent is recorded, **Then** its policy version remains identifiable after later policy changes.
2. **Given** a future-dated policy, **When** a transaction occurs before its effective time, **Then** the current effective policy is used.

### Edge Cases

- A stale concurrent settings edit must not silently overwrite a newer edit.
- Secret settings must not appear in owner read responses, audit metadata, or public content.
- No approved policy for a policy-gated flow blocks that flow instead of choosing an old or draft text.
- Existing authentication and outbox data remain readable when commerce data is introduced.

## Requirements

### Functional Requirements

- **FR-001**: Only staff with `settings.manage` may change store settings; every change MUST record actor, time, prior version, and new version.
- **FR-002**: Settings writes MUST reject invalid values, unknown keys, and stale versions without partial change.
- **FR-003**: Secret settings MUST be writeable through a controlled owner action and MUST never be returned as values or included in logs.
- **FR-004**: Policy publications MUST have a unique type and version, effective time, immutable approved content, and an identifiable prior version.
- **FR-005**: An accepted order or consent MUST retain the policy version that governed it even after newer versions become effective.
- **FR-006**: A business flow whose payment, pickup, shipping, or return policy is unapproved MUST remain disabled until approval is recorded.
- **FR-007**: Introducing commerce foundation records MUST preserve existing staff, session, audit, and email delivery behavior and their stable identifiers.
- **FR-008**: Cross-feature money, time, error, pagination, and idempotency conventions MUST have one documented contract before dependent features are planned.
- **FR-009**: Cross-feature persistence conventions MUST define reportable grain, stable business links, transition deduplication, trusted event/effective and recorded times, approved attribution dimensions, privacy boundaries, and canonical-versus-projection ownership before dependent tables are planned.

### Key Entities

- **Store setting**: Named versioned business configuration, secrecy flag, effective value, and approving actor.
- **Policy version**: Immutable approved text and effective date for a specific policy type.
- **Policy acknowledgement**: A customer's consent or order acceptance bound to an exact policy version.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of policy-gated transactions identify the effective approved version used at acceptance.
- **SC-002**: 100% of unauthorized, invalid, or stale setting updates leave the previous version unchanged.
- **SC-003**: No secret setting value appears in owner read views, public responses, or security audit output.
- **SC-004**: Existing staff sign-in, recovery, and queued-email journeys pass after the foundation is introduced.
- **SC-005**: Every later commerce data-model plan can identify a canonical record, unique transition identity, time rule, and privacy rule for each reportable business outcome without relying on mutable status alone.

## Assumptions

- A business owner supplies approved policy text and commercial terms; this feature does not invent them.
- This feature establishes shared business rules and compatibility; individual product, order, and payment behavior belongs to later specs.
- The existing staff-authentication feature supplies owner identity and current permissions.
