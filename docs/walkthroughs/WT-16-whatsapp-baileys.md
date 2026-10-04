# WT-16 - WhatsApp direct message through Baileys

Last verified: 2026-10-04, branch `feat/wa01-baileys-whatsapp` (mocked
transport). Live pairing and the synthetic subscriber journey remain pending.

Live verification on 2026-10-04 found and corrected provider timestamp
freshness using the frozen domain clock. Repeat the linked-phone journey after
the correction deploys before marking this walkthrough complete.

## Preconditions

- Hosted `clarity-channel-gateway` is healthy and has a webhook HMAC secret.
- The approved operator owns the pairing phone and can open WhatsApp Linked
  Devices on it.
- The test customer is one of the synthetic `078` subscribers. No real HUTCH
  customer record is used.

## Operator pairing

1. Keep `WHATSAPP_ENABLED=false` while pairing.
2. Run the private Compose pairing command from `deploy/README.md`, supplying
   the authorized country-code digits through the process environment.
3. Enter the displayed one-time code in WhatsApp Linked Devices.
4. Set `COMPOSE_PROFILES=whatsapp` and `WHATSAPP_ENABLED=true`, then start the
   service. No pairing or auth-state endpoint is public.

## Journey and proof

1. Send a direct text message from a synthetic subscriber number.
2. Baileys ignores non-direct provider events and converts the sender to E.164.
3. The provider message ID becomes `x-clarity-delivery-id`; the timestamp and
   exact JSON bytes are HMAC signed.
4. The channel gateway finds or opens the subscriber case and calls the
   conversation orchestrator.
5. Baileys sends the exact returned reply without adding rules or wording.
6. Re-delivery of the same provider ID is refused by the gateway replay guard.
7. A voice note receives the approved fallback asking the customer to type.

Run `npm test` in `services/whatsapp-baileys` for the mocked proof. The live
proof is complete only after the service reports paired and connected and a
synthetic `078` journey receives a Clarity reply.
