# Feature Specification: Customer Email OTP Login

**Feature Branch**: Not created (specification stage)  
**Created**: 2026-10-24  
**Status**: Draft  
**Input**: User clarification: "login via OTP on email"; STORY-020. Staff email-and-password authentication remains a separate feature.

## User Scenarios & Testing

### User Story 1 - Sign In With Email Proof (Priority: P1)

A shopper can enter an email address, receive a one-time password (OTP) by email, and enter that code to access a private account. The first successful code verification creates the account; later verifications sign in to it. No customer password, sign-in link, or separate registration is required. Browsing and guest checkout remain available without an account.

**Independent Test**: Request an OTP for a new address, verify it, sign out, request another OTP for the same address, and verify invalid, expired, and replayed codes grant no access while guest checkout still succeeds.

**Acceptance Scenarios**:

1. **Given** a valid email address, **When** a shopper requests sign-in, **Then** the public response is the same whether the account is new or existing, and the email contains a short-lived OTP code, not a sign-in link.
2. **Given** a new address and a valid unused OTP, **When** its owner enters the code, **Then** one customer account is established and a private session begins.
3. **Given** an existing active account and valid unused OTP, **When** its owner enters the code, **Then** a private session begins without creating a second account.
4. **Given** an invalid, expired, replayed, or superseded OTP, **When** it is submitted, **Then** no account access is granted.
5. **Given** a shopper who does not want an account, **When** they buy as a guest, **Then** no email sign-in or registration is required.

### User Story 2 - End and Regain Access Safely (Priority: P1)

A customer can sign out, end other active sessions, and regain access by requesting another one-time email proof. There is no password to remember or reset.

**Independent Test**: Sign in twice, end other sessions, verify the ended session loses private access, then request and redeem a fresh email proof to regain access.

**Acceptance Scenarios**:

1. **Given** an active customer session, **When** its owner signs out, **Then** that session can no longer read private account data.
2. **Given** an active customer session, **When** its owner ends other sessions, **Then** those sessions lose private access and the current session remains usable.
3. **Given** an existing account with no usable session, **When** its owner requests and redeems fresh email proof, **Then** they regain access without a password-recovery flow.

### User Story 3 - See Only My Linked Orders (Priority: P1)

A signed-in customer can see their own account-linked orders without needing a separate token for each one. A guest order is never added to an account merely because its checkout email matches; the shopper must prove control of that order before linking it.

**Independent Test**: Create two guest orders with the same email, claim only one using its private order credential, and verify the account lists only the claimed order and later authenticated purchases.

**Acceptance Scenarios**:

1. **Given** an authenticated checkout, **When** the order is accepted, **Then** it appears in that customer's account history without changing the immutable order snapshot.
2. **Given** a guest order and valid order-specific proof, **When** the signed-in customer claims it, **Then** that order appears in their history once.
3. **Given** only a matching name, phone, or email, **When** a customer requests another guest order, **Then** no order details or ownership are granted.

### Edge Cases

- Email normalization prevents duplicate accounts differing only in case or surrounding whitespace.
- Sign-in requests and proof attempts are rate limited by normalized address and network source without revealing account existence through public responses.
- Only the latest issued OTP for an address can be accepted; a resend supersedes the previous code.
- OTP codes expire, are single-use, and never appear in logs or analytics.
- Repeated incorrect guesses exhaust the challenge without granting access; a new code requires another rate-limited request.
- A suspended account and every ended session lose private access immediately.
- Staff and customer credentials, sessions, and sign-in paths are separate.
- A guest cart is not silently discarded or exposed to another account during sign-in or sign-out.
- A guest order may already be claimed; conflicting claims require a safe rejection and support review.

## Requirements

### Functional Requirements

- **FR-001**: Customers MUST be able to request an email OTP for a normalized address; the public response MUST be indistinguishable for new and existing accounts.
- **FR-002**: The sign-in email MUST provide a short-lived one-time code and no sign-in link; successful code verification MUST consume the challenge exactly once and create or access the one account for the verified address.
- **FR-003**: Customer sessions MUST be revocable and checked against current account status on every private action; staff sessions MUST not authorize customer accounts and vice versa.
- **FR-004**: OTP requests and verification attempts MUST be rate limited; codes MUST expire, be superseded by resends, resist guessing and replay, and remain absent from logs and analytics.
- **FR-005**: Customers MUST be able to sign out and end other sessions; a new valid email proof MUST restore access without customer passwords or password-reset flows.
- **FR-006**: Authenticated checkout MUST associate a new order with the signed-in customer without changing order acceptance, stock, payment, or snapshot rules.
- **FR-007**: An existing guest order MUST be linked to an account only after proof through that order's valid private access credential or an equally strong approved recovery process; matching contact details alone MUST NOT grant access.
- **FR-008**: Account order history MUST include only authenticated purchases and explicitly claimed guest orders, with customer-safe details and no staff-only fields.
- **FR-009**: Guest browsing, cart, checkout, and order-token access MUST continue to work without registration or a customer email address where the original flow permits it.

### Key Entities

- **Customer account**: Verified email identity, status, and associated customer profile; no customer password credential.
- **Customer session**: Revocable private account access, separate from staff and guest credentials.
- **Email OTP challenge**: Single-use, expiring code with request and failed-attempt state.
- **Order claim**: Auditable proof that links one guest order to one customer account.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A verified customer can sign in and sign out in under one minute, excluding email delivery time.
- **SC-002**: 100% of invalid, expired, replayed, or superseded proofs and suspended accounts reveal no private account or order data.
- **SC-003**: 100% of guest orders linked to an account have recorded order-specific proof; contact matching alone links zero orders.
- **SC-004**: Each OTP challenge creates at most one session; replay or exhausted guesses create none, and ended sessions cannot access account data.
- **SC-005**: Guest checkout remains completable without email sign-in or account creation.

## Assumptions

- Shopper sign-in uses only a one-time emailed OTP code; no magic-link login is offered. Staff continue to use their separately specified email-and-password flow.
- Guest checkout remains an option, so an email address is not mandatory for the existing guest COD path.
- Saved payment methods, wishlists, loyalty, and automatic historical order matching remain outside V1.
- Exact challenge and session lifetimes and email-delivery contract are set in this feature's later plan and reviewed against the staff-authentication security baseline.
