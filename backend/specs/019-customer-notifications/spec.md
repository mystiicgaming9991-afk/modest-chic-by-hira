# Feature Specification: Customer Notifications

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§9.3, 10, 8.7; `BACKEND_TRD.md` §4.13; `PRD.md` §11; STORY-018, TASK-006.

## User Scenarios & Testing

### User Story 1 - Receive Order Updates (Priority: P1)

A shopper with an email address receives useful transactional messages for order placement, payment, dispatch, pickup readiness, return, and refund events; staff can see delivery status.

**Independent Test**: Trigger one eligible event, retry delivery after a provider error, and verify one customer message with an accurate status record.

**Acceptance Scenarios**:

1. **Given** an accepted order event and usable email, **When** notification delivery runs, **Then** the approved template reaches the recipient once or remains visibly retryable.
2. **Given** no email address, **When** an event occurs, **Then** checkout succeeds and staff have a manual contact path where policy requires follow-up.

### User Story 2 - Handle Contact Failures (Priority: P1)

Staff can identify messages that need retry or manual contact without seeing private secrets or misleading customers about order state.

**Independent Test**: Force repeated provider failure and verify the notification moves to an actionable failed state with an accurate order link and no leaked token.

**Acceptance Scenarios**:

1. **Given** a temporary provider failure, **When** delivery retries, **Then** no duplicate business event or message intent is created.
2. **Given** terminal failure, **When** staff open the exception queue, **Then** they see safe follow-up information and can record manual contact.

### Edge Cases

- A notification is never sent for a rolled-back order, refund, or shipment change.
- A stale event cannot send a contradictory state message after a later transition.
- Secret order links are not written to logs, analytics, or unrestricted staff views.
- Optional marketing messages respect current consent; transactional messages have their distinct business purpose.
- Automated WhatsApp delivery is outside V1; manual sharing is an explicit staff action.

## Requirements

### Functional Requirements

- **FR-001**: Approved templates MUST exist for the defined order, payment, fulfillment, pickup, return, and refund milestones before their automated messages are enabled.
- **FR-002**: Message intent MUST be recorded with the related successful business transition and delivered after that transition commits.
- **FR-003**: Each message intent MUST have a stable deduplication identity, recipient/channel, template version, state, and safe attempt history.
- **FR-004**: Temporary failures MUST retry within bounded policy; terminal failures MUST enter an actionable queue without losing the source event.
- **FR-005**: Optional marketing use MUST require the current applicable customer consent; transactional messages MUST use the correct purpose and approved contact data.
- **FR-006**: Staff MUST be able to record a manual contact or share action without implying that an automated message was delivered.
- **FR-007**: Raw order-access and recovery secrets MUST be protected in stored delivery data and excluded from logs and analytics.

### Key Entities

- **Notification intent**: One event-linked, channel-specific customer communication with delivery state.
- **Template version**: Approved content and event trigger.
- **Contact exception**: Failed delivery or manual follow-up record.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Replaying an event 100 times produces at most one notification intent per recipient, channel, and template version.
- **SC-002**: Every failed customer message is retryable or visible for manual follow-up; none silently disappears.
- **SC-003**: No rolled-back business event produces a sent notification.

## Assumptions

- Email is optional for checkout; a verified sender and approved templates are supplied before real delivery.
- Manual messaging links do not authorize background automated WhatsApp sends.
