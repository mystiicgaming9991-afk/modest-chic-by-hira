# Feature Specification: Product Reviews

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§7.2, 7.5–7.6, 8.8; `BACKEND_TRD.md` §4.14; `PRD.md` §9; STORY-017.

## User Scenarios & Testing

### User Story 1 - Submit a Purchase Review (Priority: P1)

A guest with order-specific review permission can review a product bought in that order; the review awaits moderation before appearing publicly.

**Independent Test**: Submit a review for a completed purchased item, then attempt one for an unrelated product; verify only the first pending review exists.

**Acceptance Scenarios**:

1. **Given** an eligible completed order item and valid order access, **When** its buyer submits a rating and text, **Then** a pending review linked to that item is recorded.
2. **Given** a product not purchased in that order, **When** review is attempted, **Then** it is rejected.

### User Story 2 - Moderate Public Feedback (Priority: P1)

Authorized staff can approve or reject a review with a reason; only approved reviews contribute to the public list and rating summary.

**Independent Test**: Approve one review and reject another; verify the public page and aggregate include only the approved review.

**Acceptance Scenarios**:

1. **Given** a pending review, **When** authorized staff approve it, **Then** it appears publicly with verified-purchase status when eligibility is proven.
2. **Given** a rejected or pending review, **When** a shopper browses, **Then** it is absent from public results and ratings.

### Edge Cases

- A token for another order cannot create or manage the review.
- Repeated submissions for the same eligible order item cannot inflate ratings.
- Removing or archiving a product does not erase moderation evidence or historic order linkage.
- Staff must not expose buyer phone, email, address, or internal notes in public review text or metadata.

## Requirements

### Functional Requirements

- **FR-001**: Review creation MUST require exact-order review scope and a purchased item for the reviewed product under the approved eligibility rule.
- **FR-002**: Submitted reviews MUST begin pending and MUST not affect public rating or count before approval.
- **FR-003**: Moderation MUST require current permission and record decision, actor, time, and reason.
- **FR-004**: Verified-purchase labeling MUST be derived from a valid order-item link, never from shopper self-report.
- **FR-005**: Public review lists and aggregates MUST contain only approved, privacy-safe content with stable pagination.
- **FR-006**: Duplicate or edited submissions MUST not count twice for the same permitted purchase.

### Key Entities

- **Review**: Product, eligible order item, rating, text, status, and moderation history.
- **Public rating summary**: Aggregate of approved reviews only.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of public ratings and counts derive only from approved reviews.
- **SC-002**: Zero reviews for unpurchased products receive verified-purchase status.
- **SC-003**: Replaying one submission does not create a second counted review.

## Assumptions

- The business approves review eligibility and moderation rules; public product presentation comes from the discovery feature.
- Guest review access is scoped to one order; no customer account is required.
