# 2026-10-05 - RCPT01 - Keep the receipt on the case under PostgreSQL

Written by an AI coding agent (Claude Code) for its own change.

## What changed

- `ResolutionService._execute` carries the issued receipt and the RECEIPTED
  state onto the record it writes back, not only `receipts_by_plan`.
- `GET /v1/ai/usage` describes the configured provider instead of always
  saying no language model is configured.
- Regression test: a case repository that returns a copy on every read.

## Why

On the live `full` profile a confirmed refund returned `receipt_id: null`, the
chat then requested `/v1/receipts/null` (404) and showed no Trust Receipt. The
receipt was issued: the `action.completed` consumer loads its own copy of the
case, sets the receipt and RECEIPTED, and saves it. The PostgreSQL driver
unpickles a new object per read, so the executing request still held the
ACTIONED copy with no receipt and wrote it back over the consumer's save. Each
save is its own unit of work, so the version check did not catch it. The
in-memory driver shares one object, which is why `lite` tests never saw it.

The usage note told anyone reading it that no model was configured while the
deployment was calling `gemini-2.5-flash@vertex`.

## Validation

- New test failed before the fix (`receipt` was `None`), passes after.
- `test_receipts_consumer.py`, `test_case_service.py`, TH05 replay,
  migration defects and the acceptance suite: passed.
- ruff and mypy on the changed files: clean.

## Next step

Cases confirmed before this deploy keep `receipt = None` on the record; their
receipts exist in `receipts.by_plan`. A replay of the same plan returns the
original receipt.
