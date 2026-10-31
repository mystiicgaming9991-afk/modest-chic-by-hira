# Authentication Requirements Quality Checklist

This checklist reviews requirement quality, not implementation status.

## Completeness

- [x] CHK001 Are all staff account states and permitted transitions explicitly specified? [Completeness] [Spec §User Stories, §Key Entities]
- [x] CHK002 Are bootstrap, invitation, login, refresh, logout, recovery, password change, and TOTP flows all covered by acceptance scenarios? [Completeness] [Spec §User Stories]
- [x] CHK003 Are email delivery failure, retries, and duplicate delivery behavior defined without exposing account existence? [Completeness] [Spec §Edge Cases]

## Clarity and Consistency

- [x] CHK004 Is the exact password character/UTF-8 byte policy consistent across invitation, reset, and change flows? [Clarity] [Spec §FR-003]
- [x] CHK005 Are generic authentication errors specified consistently for unknown, invited, suspended, wrong-password, and wrong-TOTP identities? [Consistency] [Spec §FR-004]
- [x] CHK006 Are access JWT validity and refresh-session family expiry/revocation semantics distinct and unambiguous? [Clarity] [Spec §FR-006–FR-010]

## Security Scenario Coverage

- [x] CHK007 Are token hashing, one-time consumption, expiry, supersession, and concurrent-use outcomes defined for invitation and reset credentials? [Coverage] [Spec §FR-002, FR-012–FR-013]
- [x] CHK008 Is the behavior specified when CSRF, Origin, or rate-limit infrastructure is missing or unavailable? [Edge Cases] [Spec §FR-005, FR-011]
- [ ] CHK009 Are TOTP provisioning, unverified enrollment, replay prevention, recovery, and production enforcement fully specified? [Coverage] [Spec §FR-015]
- [x] CHK010 Does the audit requirement identify allowed event metadata and prohibit sensitive values consistently? [Clarity] [Spec §FR-016, SC-007]

## Acceptance Quality

- [x] CHK011 Can each security-related success criterion be verified deterministically using API or database behavior? [Measurability] [Spec §Success Criteria; SC-001–SC-005 and SC-007 map to contract/integration evidence. SC-006 is the separate human-timed usability target, not a security criterion.]
- [x] CHK012 Is the five-minute first-login target defined with all included/excluded steps and a reproducible measurement method? [Measurability] [Spec §SC-006]
