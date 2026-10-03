# clarity-channel-gateway

WhatsApp, SMS and USSD ingress (N02, #40; plan 09 section 9.7). A separate
deployable so the least trusted door into the system runs in a process holding
no signing keys and no staff session, and can be scaled and rate limited alone.

```bash
make channel-gateway          # runs on :8102
```

## What it refuses

| Case | Response |
|---|---|
| No `CLARITY_CHANNEL_WEBHOOK_SECRET` set | every webhook `401 no_signing_secret_configured` |
| Wrong or tampered signature | `401 bad_signature` |
| Timestamp older than 5 minutes | `401 stale_timestamp` |
| A delivery id already seen | `401 delivery_already_seen` |
| Unknown number | accepted, nothing opened, nothing revealed |
| Outside the 24-hour service window | an approved template, and the composed reply is dropped and reported |

## Signing

`sha256=<hex>` of `HMAC-SHA256(secret, "<timestamp>.<raw body>")`, in
`x-clarity-signature`, with the same timestamp in `x-clarity-timestamp` and a
unique `x-clarity-delivery-id`. The timestamp is inside the signed payload, so
neither it nor the body can be changed without breaking the digest.

**ASSUMPTION / REQUIRES HUTCH CONFIRMATION:** this is the common provider shape
(Stripe, Slack and the WhatsApp Cloud API differ only in header names and
separators). Confirm the real provider's scheme before this faces a real
webhook; only the header parsing changes, not the checks.

## Simulator

`POST /sim/{sms|ussd}` takes the same body without a signature, for the
basic-phone journey in a demo. It is a separate path rather than a bypass flag
on `/webhooks/*`, so the strict route stays strict.
