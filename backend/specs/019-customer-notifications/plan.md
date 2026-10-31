# Implementation Plan: customer notifications

**Status**: A permissioned status monitor for the existing authentication/system email outbox is integrated. Transactional order notifications remain disabled pending approved templates and provider policy (reviewed 2026-10-25).

## Implemented

- Encrypted email outbox events support staff invitation/password recovery and customer OTP delivery, with bounded retries.
- Staff with `notification.read` can filter and page through outbox delivery status from the staff workspace. The API selects only event type, flow type, status, attempt count, and timestamps; encrypted payloads, recipient addresses, and message bodies are neither queried into the response DTO nor displayed.
- A notification persistence model exists, but it is not connected to commerce transitions or a staff exception queue.
- Staff COD contact attempts are separately recorded and idempotent; this is manual operational history, not proof of automated delivery.
- Optional marketing email sending remains disabled pending approved consent language and suppression enforcement.

## Remaining

- Approve versioned transactional templates, sender configuration, recipient rules, event-to-template mapping, and retry/failure policy.
- Approve templates, sender configuration, recipient rules, event-to-template mapping, and retry/failure policy for commerce milestones.
- Create deduplicated notification intents in the transaction that commits each supported business transition, then deliver after commit.
- Add delivery attempt/error history and an actionable staff failure/manual-contact queue that never displays raw order tokens.
- Add stale-event suppression and provider retry/deduplication tests. Keep WhatsApp automation disabled.
