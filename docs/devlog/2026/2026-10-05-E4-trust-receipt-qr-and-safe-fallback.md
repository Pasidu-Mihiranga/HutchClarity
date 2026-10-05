# 2026-10-05 - E4 - Trust Receipt with a scan-to-verify QR; opt-in fallback login

Written by an AI coding agent (Claude Code) for its own change.

## What changed

- Customer receipt page (`/receipt/{id}`) redesigned after the HUTCH mobile
  mock: a result banner, a HUTCH Clarity card (receipt id, date, action,
  amount, reason, reference, signature, chain), a QR panel, Share, and a
  spend-alert switch. Every verdict still comes only from
  `POST /v1/receipts/{id}/verify`; the document only adds detail.
- The QR is the existing public `GET /v1/receipts/{id}/qr.svg`. It encodes
  only the verify URL (`VERIFY_BASE/r/{id}`), so an officer's scan re-checks
  the signed record on the verify app instead of trusting the screen.
  SDK: `ClarityClient.receiptQrUrl(id)`.
- The spend-alert switch writes the real `usage_alerts` safeguard through
  `POST /v1/me/safeguards`; it is shown only to a signed-in customer.
- 42 receipt strings in en/si/ta (`receipt.*`). The Sinhala and Tamil were
  drafted by the agent: **REQUIRES native-speaker review**.
- The synthetic fallback login (#129) is opt-in:
  `CLARITY_SYNTHETIC_FALLBACK_OTP=true`, never in prod. A code printed on a
  public login page is a login for anyone, so a deployment turns it on
  deliberately. `GET /v1/auth/sign-in-methods` reports `customer_fallback`,
  and the login page shows the fallback box only when it is true.
- The customer chat and the desk evaluate a case before reading its
  timeline. Both save evidence on a case that has none, and in parallel they
  raced into `409` under PostgreSQL.

## Validation

- Frontend unit tests: customer-web 13 (+4 copy), console 22, sdk 12, ui 48,
  i18n catalogues 4. tsc and lint clean.
- Backend IAM tests: fallback off by default and on with the setting.

## Next step

Native review of the si/ta receipt strings.
