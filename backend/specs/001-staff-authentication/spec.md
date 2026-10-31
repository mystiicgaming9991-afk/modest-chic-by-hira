# Feature Specification: Staff Email and Password Authentication

**Feature Branch**: `main`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Implement the reviewed backend design and add email and password login, using Spec Driven Development and Test Driven Development."

## User Scenarios & Testing

### User Story 1 - Invite and Sign In Staff (Priority: P1)

An owner can establish the first staff account through a one-time bootstrap invitation, then invite other staff members. A staff member accepts an invitation by choosing a password and signs into the admin system with their normalized email address and password.

**Why this priority**: Staff need access to administer the store. No protected backend feature can be operated without a secure staff identity.

**Independent Test**: Bootstrap an owner, accept the invitation, sign in with valid credentials, then verify that incorrect credentials and expired or reused invitations are rejected without exposing account existence.

**Acceptance Scenarios**:

1. **Given** an invited owner or staff member with a valid invitation, **When** they set a compliant password, **Then** the invitation is consumed and the staff account becomes active.
2. **Given** an active staff account, **When** the user supplies the correct email and password, **Then** the system grants a short-lived staff access session and establishes a protected refresh session.
3. **Given** an unknown, invited, suspended, or incorrectly authenticated account, **When** a login is attempted, **Then** the system returns a generic authentication failure and grants no access.
4. **Given** an invitation that is expired, already consumed, or superseded, **When** it is accepted, **Then** the account remains unchanged and the system rejects the invitation.
5. **Given** an owner who invites an email that already has an active account, **When** the invite is submitted, **Then** no duplicate account is created and the owner receives a non-sensitive conflict response.

### User Story 2 - Protect and End Staff Sessions (Priority: P1)

A staff member can continue an authenticated session without entering their password on every request, and can log out. The system can revoke a stolen or reused refresh credential and immediately apply account suspension and role changes.

**Why this priority**: A login flow is incomplete without safe session renewal and revocation, especially for accounts that can change orders, payments, and customer data.

**Independent Test**: Sign in, renew the session, replay an old refresh credential, and verify that the session family is revoked; separately verify logout, suspension, and role removal.

**Acceptance Scenarios**:

1. **Given** a valid unexpired refresh session, **When** the staff member renews it, **Then** the old refresh credential is invalidated and a new short-lived access session is issued.
2. **Given** a refresh credential that has already been rotated, **When** it is reused, **Then** the system revokes all sessions in that session family and requires a fresh login.
3. **Given** an authenticated staff member, **When** they log out, **Then** the current session family is revoked and the browser refresh credential is cleared.
4. **Given** a staff member whose account is suspended or whose role was removed, **When** they access a protected admin action, **Then** access is denied using current account and permission state.
5. **Given** a browser mutation or login request that lacks a valid CSRF value or trusted origin, **When** the request is submitted, **Then** the request is rejected without changing account or session state.

### User Story 3 - Recover or Change a Password (Priority: P1)

A staff member who forgets a password can request an email reset link and set a new password. An authenticated staff member can change a password by proving their current password.

**Why this priority**: Staff must recover access without exposing whether an email is registered, and compromised credentials must be replaceable promptly.

**Independent Test**: Request resets for both known and unknown email addresses, compare responses, consume a valid reset once, and verify that prior sessions stop working.

**Acceptance Scenarios**:

1. **Given** any syntactically valid email address, **When** a password reset is requested, **Then** the system returns the same accepted response regardless of whether an active account exists.
2. **Given** an active account and a valid unused reset link, **When** the staff member chooses a compliant new password within 30 minutes, **Then** the password changes and all existing refresh sessions are revoked.
3. **Given** an expired, used, or invalid reset link, **When** it is submitted, **Then** no password or session state changes.
4. **Given** an authenticated staff member, **When** they change their password with the correct current password, **Then** the new password takes effect and all existing refresh sessions are revoked.
5. **Given** an authenticated staff member, **When** they submit an incorrect current password, **Then** the change is rejected and the existing credential remains valid.
6. **Given** an active staff member requests another reset link, **When** the new request is accepted, **Then** every earlier unused reset link for that account is invalidated before the new link is queued.

### User Story 4 - Complete Multi-Factor Enrollment (Priority: P1)

A staff member can enroll a time-based one-time code after accepting an invitation. In production, protected admin access is withheld until enrollment is verified; subsequent sign-ins require the code.

**Why this priority**: Staff accounts can access sensitive commerce and customer information, so production access requires a second factor.

**Independent Test**: Enroll a second factor, verify it, then test login and protected access with valid, invalid, missing, and replayed codes.

**Acceptance Scenarios**:

1. **Given** an active staff member not yet enrolled, **When** they begin enrollment and verify a valid code, **Then** the second factor is enabled for the account.
2. **Given** production mode and an account without verified second-factor enrollment, **When** the account attempts a protected admin action, **Then** access is denied and the user is guided to enrollment.
3. **Given** an account with second-factor verification enabled, **When** a correct password is submitted without a valid current code, **Then** no authenticated session is granted.
4. **Given** an invalid or previously accepted code, **When** it is submitted, **Then** authentication or enrollment verification is rejected.
5. **Given** a production staff account without verified TOTP, **When** valid email/password credentials are submitted, **Then** the system permits only the TOTP enrollment flow and denies every admin permission until enrollment is verified.

### Edge Cases

- Email matching trims surrounding whitespace and ignores case; the system prevents duplicate normalized staff email addresses.
- Concurrent acceptance of one invitation activates at most one account and consumes the invitation once.
- Concurrent refresh requests cannot create two valid descendants from the same refresh credential.
- Rate limits apply to login, refresh, invitation acceptance, and password recovery using both account/email and network source where appropriate.
- Password reset email delivery failure does not reveal account existence; delivery is retried with the same outbox idempotency key for at most ten attempts, then enters a visible terminal failure state. A retry may deliver the same email more than once, but it must carry the same one-time token; a newer accepted reset request invalidates every earlier unused token.
- If Redis is unavailable, a rate-limited authentication operation fails closed with HTTP 503 and never bypasses its configured limit.
- Invalid CSRF or origin checks do not block read-only public catalog requests.
- Access tokens expire after 15 minutes; refresh sessions expire after seven days unless revoked sooner.
- TOTP setup material is not logged and is protected at rest; an unverified setup secret does not grant production access.
- Authentication logs record security outcomes and actor identifiers without passwords, raw tokens, or reset links.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide a restricted setup path to establish the first invited owner without a seeded password or default credential.
- **FR-002**: An active owner MUST be able to invite staff with assigned roles; invitation acceptance MUST be single-use and valid for 24 hours.
- **FR-003**: The system MUST normalize staff email addresses for lookup and uniqueness and require passwords of at least 12 characters and no more than 72 UTF-8 bytes.
- **FR-004**: The system MUST allow an active staff member to authenticate with email and password and MUST use the same generic authentication failure response for unknown, invited, suspended, wrong-password, missing-code, invalid-code, and replayed-code login attempts.
- **FR-005**: Login MUST be limited to five attempts per minute per normalized email and source network; invitation acceptance MUST be limited to five attempts per hour per token digest and source network; password recovery/reset MUST be limited to five attempts per hour, and refresh MUST be limited to ten attempts per minute. If Redis is unavailable for an operation that requires a limit, the operation MUST fail closed with HTTP 503 and MUST NOT proceed without rate limiting.
- **FR-006**: A successful login MUST establish a 15-minute access session and an opaque refresh session valid for at most seven days.
- **FR-007**: The browser refresh credential MUST be inaccessible to JavaScript, transmitted only over secure connections, and protected by same-site cookie rules.
- **FR-008**: Refresh MUST rotate credentials atomically; reuse of a rotated credential MUST revoke the whole related session family.
- **FR-009**: Logout MUST revoke the current session family and clear the browser refresh credential.
- **FR-010**: Every protected admin action MUST verify current account status and current role permissions; suspension and role removal MUST take effect immediately.
- **FR-011**: The system MUST establish anti-forgery protection before browser login and cookie-authenticated changes and MUST validate that these requests come from an allowed site origin.
- **FR-012**: Password recovery MUST return an indistinguishable accepted response for known and unknown addresses and MUST send a one-time 30-minute reset link only for an active account. A newly accepted request MUST invalidate all earlier unused reset links for that account in the same transaction that queues the new link.
- **FR-013**: Successful password reset MUST consume the reset link and revoke all active refresh sessions for that staff member.
- **FR-014**: Authenticated staff MUST be able to change a password only after providing the current password; a successful change MUST revoke all active refresh sessions.
- **FR-015**: The system MUST support second-factor enrollment and verification; a production staff account without verified enrollment MAY authenticate only into a restricted enrollment flow, MUST be denied all admin permissions until verification, and MUST provide a valid code during later logins.
- **FR-016**: The system MUST audit security-relevant authentication, invitation, session, password, and role events. Audit metadata MUST use an action-specific allow-list of bounded JSON scalars or scalar lists; unknown actions, metadata keys, nested objects, and oversized values MUST be omitted. Audit records MUST NOT store or log email addresses, passwords, raw session/invitation/reset tokens or links, TOTP codes, or TOTP secrets.
- **FR-017**: No customer account registration or customer password login is included in this feature.

### Key Entities

- **Staff account**: A normalized email identity, display name, password credential state, second-factor enrollment, and assigned roles. Status is `INVITED`, `ACTIVE`, or `SUSPENDED`: invitation acceptance permits `INVITED -> ACTIVE`; staff with current `staff.manage` permission may perform `ACTIVE -> SUSPENDED` or `SUSPENDED -> ACTIVE` as specified in Feature 023. Suspension revokes every active session; reactivation does not restore revoked sessions. No other status transitions are permitted.
- **Invitation**: A single-use, time-limited authorization to establish or join a staff account, issued by an owner.
- **Staff session**: A short-lived access identity and its revocable, rotating refresh credential family.
- **Password reset request**: A single-use, time-limited authorization to replace a staff password.
- **Role and permission**: The current actions a staff member may perform in the admin system.
- **Security audit event**: A record of a relevant authentication or authorization outcome without secret values.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of valid invitations can be accepted once, and 100% of expired or reused invitations fail without activating an account.
- **SC-002**: 100% of login attempts with invalid credentials, invalid second-factor proof, or a suspended account are denied.
- **SC-003**: 100% of reused refresh credentials, password resets, password changes, and logout operations revoke the required session scope.
- **SC-004**: Password recovery responses for known and unknown addresses are identical in status and response body.
- **SC-005**: 100% of admin requests from suspended accounts or lacking current permission are denied, including requests made with an unexpired access credential.
- **SC-006**: A staff member can complete invitation acceptance and first login in under five minutes, excluding email delivery time. Measure from the valid invitation page's first interactive render to the first authorized admin page; include password setup and any required TOTP enrollment/login, and record elapsed wall-clock time with a stopwatch. Exclude time waiting for the invitation email to arrive or be opened.
- **SC-007**: No password, raw refresh token, invitation secret, reset secret, or second-factor secret appears in application logs.

## Assumptions

- Staff accounts are invite-only; public staff registration is not provided.
- The first owner is established through restricted deployment setup and completes the same invitation acceptance flow as later staff.
- Passwords follow the documented strength and secure non-reversible storage policy; password reset and invitation messages use the configured transactional email service.
- The password byte limit preserves the documented bcrypt policy without silently truncating credentials.
- TOTP is required for production admin permissions; local development may use a clearly isolated non-production setting.
- Staff administration UI is outside this API feature; the API returns explicit states needed by a future admin login UI.
- Customer registration, shopper password login, social sign-in, and remembered-device bypass are out of scope.
