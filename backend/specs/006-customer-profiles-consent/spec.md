# Feature Specification: Customer Profiles and Consent

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§6.3, 7.6, 8.1; `BACKEND_TRD.md` §4.3; `PRD.md` §§3, 12, 14; STORY-012.

## User Scenarios & Testing

### User Story 1 - Recognize Guest Buyers (Priority: P1)

Checkout and manual sales can connect an order to a customer profile without requiring a customer account. Staff can view an accurate order history. Optional passwordless email accounts and private shopper access are specified separately in feature 024.

**Independent Test**: Place a web and manual order with the same normalized phone, then verify one appropriate customer record and both orders in its history.

**Acceptance Scenarios**:

1. **Given** a verified normalized phone match, **When** a new order is placed, **Then** it links to the existing customer without rewriting prior order snapshots.
2. **Given** two buyers who share a phone but have conflicting identities, **When** staff inspect them, **Then** the system does not silently merge them.

### User Story 2 - Respect Contact Preferences (Priority: P1)

The business can record channel-specific consent and suppress optional messages or exports when consent is absent or withdrawn.

**Independent Test**: Record consent, withdraw it, and verify later marketing export excludes that customer while necessary order messages remain governed by their own purpose.

**Acceptance Scenarios**:

1. **Given** explicit marketing consent, **When** the customer withdraws it, **Then** future marketing use stops and the historic decision remains auditable.
2. **Given** staff without customer export permission, **When** they request an export, **Then** no private customer data is returned.

### Edge Cases

- Simultaneous orders with the same normalized phone do not create unintended duplicate canonical profiles.
- Shared family phones and corrected numbers do not cause automatic cross-person merges.
- Absent email does not block COD checkout when phone contact is valid.
- Prior order contact/address snapshots remain intact after profile correction.

## Requirements

### Functional Requirements

- **FR-001**: Guest order creation MUST resolve or create a customer using normalized contact data without requiring customer sign-in; optional account linking MUST follow feature 024's proof rules.
- **FR-002**: Customer identity resolution MUST prevent concurrent duplicate creation and MUST require an explicit, audited decision before merging conflicting profiles.
- **FR-003**: Staff customer search and history MUST show linked orders, COD outcomes, and return-to-origin history only to authorized staff.
- **FR-004**: Customer profile corrections MUST not alter the contact, address, and policy snapshots stored on existing orders.
- **FR-005**: Consent MUST record purpose, channel, policy version, decision, actor/source, and time; withdrawal MUST affect later optional use.
- **FR-006**: Customer exports and optional marketing sends MUST respect current permission and consent, with the business-approved retention rules applied.

### Key Entities

- **Guest customer**: Canonical contact and identity hints linked to orders.
- **Customer address**: Current reusable address separate from immutable order address snapshots.
- **Consent record**: Versioned purpose and channel choice with withdrawal history.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of guest orders link to a customer record without requiring a customer password.
- **SC-002**: Concurrent creation attempts for the same unambiguous normalized contact yield one canonical customer.
- **SC-003**: 100% of optional marketing exports and sends exclude customers without current required consent.

## Assumptions

- The approved retention and consent policy is a business gate; the feature must not invent a legal retention period.
- Customer account self-service belongs to feature 024; automated cross-person identity matching remains outside V1.
