# clarity-whatsapp-baileys

Baileys transport for WA01. It accepts one-to-one WhatsApp messages, filters
provider noise, signs the existing Clarity channel webhook, and sends only the
exact reply returned by the channel gateway. It contains no rules, amounts,
confirmation tokens, action execution or model calls.

Baileys is an unofficial WhatsApp Web client and is not affiliated with Meta or
HUTCH. Use requires operator approval and compliance with WhatsApp terms.

## Safety and operation

- Disabled unless `WHATSAPP_ENABLED=true`.
- Groups, own messages, statuses, broadcasts, newsletters and system messages
  are ignored before Clarity is called.
- Provider message IDs become signed delivery IDs for replay protection.
- Auth state lives at `WHATSAPP_AUTH_DIR`, which must be a persistent secret
  volume and must never enter an image, backup log or repository.
- Pairing has no HTTP route. An operator runs `npm run pair` inside the private
  deployment and supplies `WHATSAPP_PAIRING_PHONE` as country-code digits.
- Phone pairing waits for Baileys' pairing-ready event before requesting the
  code. After WhatsApp registers the device, the command reconnects through the
  required session restart and reports success only when the session opens.
- If phone-number linking is refused, the operator sets
  `WHATSAPP_PAIRING_MODE=qr` and scans the private terminal QR from WhatsApp
  Linked Devices.
- Voice notes receive the approved fallback asking the customer to type.

## Local proof

```bash
npm ci
npm test
```
