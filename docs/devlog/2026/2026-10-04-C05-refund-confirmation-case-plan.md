# 2026-10-04 - C05 - keep confirmation plan on its case

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | C05 follow-up |
| PR / commit | pending |
| Units touched | customer-web |

## What changed

- Stopped a stateful follow-up from opening a second case after its flow had already created a plan.
- Confirmed the flow-owned plan instead of creating a replacement proposal.
- Made a refused confirmation visible instead of logging it only to the browser console.
- Extended the browser journey through two turns, confirmation and verified receipt.

## Why

The UI paired the first case's pending plan with a newly opened second case.
The API correctly refused that mismatch, but the UI swallowed the error, so
the customer saw a Confirm button that appeared to do nothing.

## Decisions made

- The server flow remains the owner of its pending plan.
- Legacy single-response cards still create a proposal when no flow plan exists.

## Docs updated

- [x] WT-02 VAS journey
- [x] Submission demo script
- [ ] No API or module contract changed

## Tests

- `frontend/e2e/dispute-charge.spec.ts`: 3 passed.
- Full repository gate pending.

## Open issues / next step

Run the complete gate, merge, deploy, and repeat the journey against the VPS.
