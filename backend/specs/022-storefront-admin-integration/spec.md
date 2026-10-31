# Feature Specification: Storefront and Admin Integration

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: `BACKEND_PRD.md` §§2, 14; `PRD.md` §§5, 10, 13, 18; `TRD.md` §12; STORY-003–006, TASK-009–011.

## User Scenarios & Testing

### User Story 1 - Shop Through Real Commerce Data (Priority: P1)

A mobile shopper can browse approved products, build a guest cart, review an accurate quote, place an order, and return to private order progress through the live commerce service.

**Independent Test**: Complete discovery, cart, COD checkout, confirmation, and private tracking from a fresh browser session with no account.

**Acceptance Scenarios**:

1. **Given** published in-stock products, **When** a shopper browses, **Then** product, price, and availability match the authoritative public commerce data.
2. **Given** a valid cart, **When** a shopper checks out, **Then** the displayed accepted totals and order confirmation match the resulting order.
3. **Given** a guest order credential, **When** the shopper opens only that order, **Then** they see private progress without exposing the credential in a shareable URL.

### User Story 2 - Sign In and Work Safely (Priority: P1)

An invited staff member can accept an invitation, sign in with email and password, complete required second-factor enrollment, recover access, and work only the admin actions allowed by current permissions.

**Independent Test**: Accept invitation, log in, complete second factor, view an allowed queue, lose a role, and verify the same browser cannot perform its former action.

**Acceptance Scenarios**:

1. **Given** a valid invitation, **When** staff set a password and sign in, **Then** they reach an authorized admin landing view.
2. **Given** production second-factor enrollment is incomplete, **When** staff log in, **Then** they are guided through enrollment and cannot reach privileged actions first.
3. **Given** an expired session or suspended account, **When** staff navigate, **Then** private data is cleared from the view and they must authenticate again.

### User Story 3 - Reach and Understand Public Pages (Priority: P2)

Shoppers can use mobile and assistive technology to find products and understand policies, while search engines see only approved public content.

**Independent Test**: Audit representative home, category, product, cart, checkout, and order pages for keyboard use, mobile layout, metadata, and absence of private indexing.

**Acceptance Scenarios**:

1. **Given** a public published product, **When** its page is shared or indexed, **Then** its title, description, image, and canonical location are correct.
2. **Given** an order or admin page, **When** a crawler requests it, **Then** private content is not indexed.

### User Story 4 - Use an Optional Customer Account (Priority: P1)

A shopper can request an OTP by email, enter the code to create or access an account without a password, and view only their account-linked orders without losing the guest buying path.

**Independent Test**: Complete first and repeat sign-in by email proof, authenticated checkout, order history, and logout; then complete guest checkout without signing in.

**Acceptance Scenarios**:

1. **Given** a valid emailed OTP, **When** its owner enters the code, **Then** they see only authenticated or explicitly claimed orders.
2. **Given** a guest shopper, **When** they reach checkout, **Then** customer sign-in is optional and no email challenge is required to place an order.

### Edge Cases

- A stale quote, lost network response, or exact checkout retry does not produce a second order or hide the original confirmation.
- The browser sends guest, customer, and staff credentials only in their appropriate protected contexts; a public page does not display private account or staff data.
- Login, refresh, cart, and checkout mutations handle anti-forgery and origin failures with a clear retry path.
- Product, cart, and checkout states remain usable on narrow mobile screens and with keyboard navigation.
- Optional analytics does not transmit personal data or events without the approved consent rule.

## Requirements

### Functional Requirements

- **FR-001**: Storefront product, cart, quote, checkout, and order views MUST use the accepted commerce contracts and display loading, empty, validation, conflict, and retry states.
- **FR-002**: Guest checkout MUST preserve one request identity across retry and display the original accepted order after an interrupted response.
- **FR-003**: Staff invitation, email/password login, refresh, logout, password recovery, and required second-factor enrollment MUST be usable through the admin experience.
- **FR-004**: Staff screens and actions MUST reflect current permissions and account state and MUST clear private session information after revocation or logout.
- **FR-005**: Public pages MUST expose approved indexable content and metadata; order and admin pages MUST not expose private content to crawlers.
- **FR-006**: Representative shopping and admin journeys MUST meet the approved mobile, keyboard, screen-reader, and performance acceptance criteria.
- **FR-007**: Browser mutations MUST apply the shared anti-forgery and origin protections without making public read-only browsing dependent on a session.
- **FR-008**: Analytics and attribution MUST separate placed COD orders, paid orders, and delivered orders and obey the approved consent rule.
- **FR-009**: Customer OTP request, one-time code verification, logout, session recovery through a fresh OTP, and private order history MUST be usable through the storefront without reusing staff credentials or blocking guest checkout.

### Key Entities

- **Browser shopping session**: Guest cart identity, anti-forgery state, and pending checkout retry context.
- **Admin session view**: Current staff identity, enrollment state, and permitted actions.
- **Public content page**: Approved catalog/policy data and discoverability metadata.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A shopper completes the mobile discovery-to-COD-order journey in under three minutes, excluding product browsing time.
- **SC-002**: An invited staff member can reach an authorized admin action in under five minutes after receiving the invitation, excluding email delivery time.
- **SC-003**: Exact checkout retries produce one displayed order; private order and admin data appear on zero public indexed pages.
- **SC-004**: All representative journeys pass the approved keyboard and mobile acceptance checks.

## Assumptions

- This integration follows the accepted API contracts as each backend feature is implemented; it does not introduce alternate browser-only business rules.
- Brand assets, approved public copy, analytics consent, and mobile/accessibility thresholds need product-owner sign-off.
