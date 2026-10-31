# Feature Specification: Staff Access Administration

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.6, 11.3; `BACKEND_TRD.md` §§4.1, 13; `BACKEND_HLD.md` §6.2; TASK-005-B, TASK-005-C.

## User Scenarios & Testing

### User Story 1 - Review and Change Staff Access (Priority: P1)

An owner can see current staff status and roles, then grant or remove approved roles without waiting for an existing access credential to expire.

**Independent Test**: Sign in a staff member, remove a role, and verify their still-open session immediately loses the related admin action.

**Acceptance Scenarios**:

1. **Given** an active owner, **When** they list staff, **Then** they see each member's status, roles, and second-factor enrollment state without password or secret values.
2. **Given** an authorized role change, **When** the owner saves it, **Then** protected actions use the new permissions on the next request and the change is audited.
3. **Given** staff without staff-management permission, **When** they attempt a role change, **Then** no assignment changes.

### User Story 2 - Suspend Compromised Access (Priority: P1)

An owner can suspend a staff member and immediately stop both session renewal and protected actions while retaining the person's history for review.

**Independent Test**: Suspend an active member with an open access and refresh session, then verify both credentials can no longer authorize work.

**Acceptance Scenarios**:

1. **Given** an active member, **When** an owner suspends them, **Then** their protected requests and refresh attempts are denied immediately.
2. **Given** a suspension attempt that would leave the store without an active owner, **When** it is submitted, **Then** the action is rejected and an audit event explains the refusal safely.

### Edge Cases

- Simultaneous owner removals cannot leave zero active owners.
- Role assignments are unique; an exact retry does not duplicate them or their audit history.
- Suspended staff remain linked to past orders, decisions, and audit records.
- Invited members cannot gain admin access before invitation acceptance and required second-factor enrollment.
- The owner view never reveals credential hashes, reset secrets, session tokens, or TOTP seeds.

## Requirements

### Functional Requirements

- **FR-001**: Only staff with current `staff.manage` permission MUST be able to list members, change roles, or suspend access.
- **FR-002**: Staff listing MUST show identity, status, roles, and enrollment state without any credential or recovery secret.
- **FR-003**: Role changes MUST validate approved role keys, reject conflicting stale edits, and take effect on the next protected request.
- **FR-004**: Suspension MUST block access and refresh immediately while preserving historical actor and order references.
- **FR-005**: A role or suspension change MUST record prior/new state, owner actor, time, reason where required, and a safe audit event.
- **FR-006**: No permitted operation may remove or suspend the last active owner; concurrent changes MUST preserve that invariant.
- **FR-007**: Owner invitations and staff sign-in remain governed by the staff-authentication specification rather than a second credential workflow.

### Key Entities

- **Staff account**: Current identity, status, enrollment, and role assignments.
- **Role assignment decision**: Versioned owner action with actor and time.
- **Access audit event**: Safe record of grant, removal, suspension, or rejected last-owner change.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of role removals deny the removed action on the next request, including requests with an unexpired access credential.
- **SC-002**: 100% of suspended staff requests and refresh attempts are denied immediately.
- **SC-003**: Concurrent role/suspension changes never leave the store without an active owner.

## Assumptions

- The initial role and permission catalog is established by staff authentication; owner changes use those approved roles.
- Permanent deletion of staff identity and history is outside V1.
