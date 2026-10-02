# 2026-10-02 - M-CASE - Orchestration split into a resolution service

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | M-CASE (issue #34), Wave 1; plan 21 section 2.2 |
| Units touched | case, resolution (new), app (container, mcp_view), tests/architecture |

## What changed

- `clarity.modules.case` keeps the **aggregate**: `CaseAggregate` in `aggregate.py` holds one case, its evidence, its decision and the states it may move between. It calls no other module.
- `clarity.modules.resolution` (new) holds the **orchestration** that was `CaseService`: open, evidence, evaluate, propose, confirm or approve, execute, read the receipt.
- `open_case` now publishes `case.created@v1`, so insights and autopsy can follow a case from its start.
- The right to import `actions.capability`, the only code that can move money, moved from `case` to `resolution`. It follows the orchestrator, not the aggregate.
- The dependency map now reads `resolution -> {case, timeline, detection, decision, actions, receipts}`.

The methods moved verbatim. The resolution service reaches the aggregate through one-line delegations, so no orchestration code was rewritten and the refactor could be checked against the existing suite rather than against a rewrite.

## Why

Issue #34: `CaseService` was a 659-line class doing two unrelated jobs. The cost was not length, it was the dependency map: the module holding a customer's case also called six others, so it could not be reasoned about, tested or deployed without them.

## Decisions made

- **`resolution` is an L4 module, not part of `clarity.app`.** Plan 21 section 2.2 calls it an "application service", which would put it in the composition root. But the composition root is not covered by the dependency map, so putting orchestration there would have hidden six call edges from the test that exists to keep them honest. As a module they stay declared and enforced.
- **The public surface kept its method names**, so the HTTP and MCP interfaces were untouched. A test asserts the seventeen names the interfaces call still resolve.
- **`case` is declared as depending on four modules, and this is honest rather than ideal.** It calls nothing; those are the types its record *holds*: the evaluation detection produced, the thresholds decision used, the execution actions returned, the receipt that proves it. The dependency test reads imports and cannot tell naming a type from calling a function. Moving those four types down to `clarity.contracts`, where ADR-0029 section 4 says shared vocabulary belongs, would make `case` a leaf in the file as well as in behaviour. That is a follow-up, and the reason is written into the dependency map next to the declaration rather than left for someone to rediscover.

## Docs updated

- [x] `backend/src/clarity/modules/resolution/MODULE.md` (new)
- [x] `backend/src/clarity/modules/case/MODULE.md`: files, public surface, migration status
- [x] `tests/architecture/test_module_dependencies.py` and `test_module_boundaries.py`: the new edge set and the capability allowlist
- [ ] `docs/modules.md` and `ARCHITECTURE.md`: updated with the Wave 1 batch
- [ ] CHANGELOG.md: no `/v1` contract change; the OpenAPI snapshot is unchanged

## Tests

- **Acceptance 1**: the R0 acceptance suite passes unchanged, which is the point of a refactor whose public surface did not move.
- **Acceptance 2** (`tests/unit/test_case_service.py`, new): evaluating a case twice returns the same decision, before a plan exists, after one does, and after execution, where the receipt already cites it. Plus the state machine order, that the orchestrator holds no collections, that `case.created` is published and keyed by subscriber, and that it carries no raw number.
- `make check`: **692 passed, 45 skipped**. Full profile: **142 passed**.

## Open issues / next step

- Move `RuleEvaluation`, `PolicyThresholds`, `ExecutionResult` and `TrustReceipt` handling in `CaseRecord` down to `clarity.contracts` so `case` is a leaf in the import graph too.
- `action.failed` is published by the actions module (M-ACT) but nothing consumes it yet. M-CASE's scope named "`action.failed` handling": the honest status is that the event exists and the resolution service does not yet subscribe to it, because a failed plan currently raises synchronously to the caller that asked for it. A consumer matters once execution is asynchronous, which is X03's relay process.
