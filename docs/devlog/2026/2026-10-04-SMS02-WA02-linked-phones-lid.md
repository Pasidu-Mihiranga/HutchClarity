# 2026-10-04 - SMS02/WA02 - Linked test phones, and WhatsApp @lid senders

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | SMS01 #75 and WA01 #59 follow-up |
| PR / commit | branch `fix/channels-linked-phones` |
| Units touched | `iam` (OTP delivery), `app` (settings, composition), `integration.drivers.mock` (world), `interfaces.http`, `services/whatsapp-baileys` |

## What changed
- `CLARITY_LINKED_PHONES` (server only): `real=synthetic` pairs. `SyntheticWorld.link_phone` makes `account_by_msisdn` resolve a linked real phone to its synthetic customer, so sign-in, the chat and the channel gateway all treat that phone as the customer.
- `iam.RoutedOtpDelivery` chooses per number: a linked phone gets a real SMS (httpSMS); any other synthetic number gets the inbox on the sign-in page; an unknown number gets nothing. The request answer is the same for unknown and synthetic numbers.
- A link that names no synthetic customer stops startup; a malformed value is a settings error.
- WhatsApp bridge: a one-to-one message addressed by a privacy `@lid` is read through `key.senderPn` (Baileys 6.7) or `key.remoteJidAlt` (Baileys 7) and answered in the same chat. Every ignored message logs a reason (`from_me`, `not_one_to_one`, `no_phone_number`, `bad_number`, `no_text`), never content or number.

## Why
Live testing on the VPS failed on both channels:
- SMS: with httpSMS configured, the OTP route texted whatever number was typed. A tester's own phone is not a synthetic customer, so it received a code that could never verify (the anti-enumeration decoy, #84); signing in as a synthetic customer texted that number's real owner; and anyone could make the server send SMS to any number at the operator's cost.
- WhatsApp: the bridge accepted only `@s.whatsapp.net` senders and dropped everything else without a log line; the channel gateway received no inbound request in 90 minutes while the transport was connected.

## Decisions made
- Linking is the operator's deliberate act per phone, recorded only in `.env.production`; real numbers never enter the repository. Linking a real phone puts personal data on the server, so the deploy README says to link only consenting owners and unlink after testing.
- Replies go back to the chat id the message came from, in whichever form it used.

## Docs updated
- [x] `.env.example`, `deploy/README.md` (linked test phones), `iam/MODULE.md`

## Tests
- `tests/unit/test_linked_phones.py` (7): only a linked phone is texted; it signs in as its customer; a synthetic number is never texted; an unknown number is not texted and looks like any other; bad links fail.
- `services/whatsapp-baileys`: 15 passed, including `@lid` with `senderPn` and `remoteJidAlt`, `@lid` without a number, and skip reasons.
- Live checks before the change: httpSMS heartbeats every 15 minutes (phone online), account answers; WhatsApp transport connected; gateway idle.

## Open issues / next step
- Link the tester's phone on the VPS, then test sign-in by SMS and a WhatsApp journey end to end.
