# [M-RCPT] Receipts: signer service port with OpenBao/KMS driver, isolated rendering

| Field | Value |
|---|---|
| Wave | W1 Core modules on the baseline |
| Area | `receipts` |
| Priority | P1 |
| Depends on | [B06](B06-first-event-driven-flow-receipts-issued-on-actio.md) |
| Plan | 09 §15, 21 §5 |
| Labels | `wave:w1`, `area:receipts`, `priority:p1`, `type:feature` |

## Context
The signing key is generated in memory at startup.

## Scope
- `Signer` port: dev key driver (`lite`), OpenBao/KMS driver (`full`/`prod`); `kid` rotation; public keys at `/.well-known`
- Rendering isolated (no network egress); packaged as a serverless-ready job
- Publish `receipt.issued@v1`

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a receipt signed with key 1 then key rotated | verified | still valid; new receipts use key 2 | `backend/tests/unit/test_receipts.py` |
| 2 | both signer drivers | the parity suite runs | same results | `backend/tests/contract/test_port_parity.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
