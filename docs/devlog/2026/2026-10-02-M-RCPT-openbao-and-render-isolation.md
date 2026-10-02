# 2026-10-02 - M-RCPT - OpenBao signer and render isolation

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | M-RCPT (#37), R4 |
| PR / commit | uncommitted |
| Units touched | receipts, settings, compose, events |

## What changed

- Added dev-key rotation and an OpenBao Transit Ed25519 signing driver with retained public keys.
- Blocked renderer network access and exposed a JSON-safe stateless render job.
- Committed receipt state and `receipt.issued@v1` in one unit of work.

## Why

Trust Receipt keys require isolated custody and historic verification; rendering may scale separately without network egress.

## Decisions made

- The full driver uses OpenBao Transit version numbers as stable `kid` values.

## Docs updated

- [x] receipts `MODULE.md`
- [x] `.env.example`, compose and `ARCHITECTURE.md`

## Tests

Both signing drivers passed one parity suite; rotation, receipts, consumer and outbox tests passed.

## Open issues / next step

Production token delivery and KMS/HSM mapping remain deployment concerns.
