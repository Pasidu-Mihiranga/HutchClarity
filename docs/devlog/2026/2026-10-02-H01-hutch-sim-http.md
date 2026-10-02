# 2026-10-02 - H01 - hutch-sim HTTP service and drivers

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | H01 (#29), R4 |
| PR / commit | uncommitted |
| Units touched | integration, timeline, app settings, HTTP contract, hutch-sim |

## What changed

- Added a standalone, explicitly simulated `hutch-sim` ASGI service.
- Added HTTP implementations of every evidence read port and the command port.
- Ran the same read and command parity suites against in-process and HTTP drivers.
- Wired the `full` profile to HTTP while keeping `lite` in process.
- Removed the seven `/mock/*` operations from the Clarity API and regenerated its contracts.

## Why

H01 and plan 06 section 9 require a real network boundary in `full` without
inventing or depending on unconfirmed HUTCH production interfaces.

## Decisions made

- The service reuses the canonical models and mock-store behavior; transport
  changes do not create a second integration contract.
- Container images and Compose deployment stay in X03. H01 supplies a directly
  runnable ASGI entry point and profile wiring.

## Docs updated

- [x] timeline `MODULE.md`
- [x] `docs/modules.md`, `ARCHITECTURE.md`
- [x] `CHANGELOG.md`, OpenAPI snapshot and generated frontend SDK
- [x] Plan 21 status, plan change record and revision table
- [ ] Walkthrough: no customer-visible journey changed

## Tests

- `pytest tests/contract/test_port_parity.py tests/acceptance/test_route_contract.py`: passed.
- `pytest tests/acceptance/test_openapi_contract.py`: passed and snapshot regenerated.
- `mypy`: passed (187 source files).
- `make check`: 1,210 passed, 511 infrastructure-dependent skipped; lint,
  formatting, strict typing and all three import contracts passed.

## Open issues / next step

X03 owns the deployable image and Compose/Helm/OpenTofu wiring. Real HUTCH
sandbox and production drivers still require confirmed interfaces.
