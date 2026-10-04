# 2026-10-04 - AUDIT Phase 7 - retention, legal hold, erasure and verifiable export

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Opus), for Thanoj Buddhima |
| Work package | Audit assurance plan, Phase 7 |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | platform.audit, app (container, collections, settings), interfaces.http, config/policy, scripts, contracts |

## What changed

- **`AuditLedger.verify` rewritten around one forward walk.** Three ways in (the
  whole chain, from a checkpoint, from an archival floor) all reduce to the same
  loop over a known starting point. The previous version had three partly
  overlapping branches and was about to get a fourth.
- **`platform/audit/lifecycle.py`**: archival into sealed segments with a floor,
  legal holds by subject or seq range, erasure by crypto-shredding the pseudonym
  link, and `verify_segment` for an archived bundle.
- **`platform/audit/export.py`** and **`backend/scripts/verify_audit_export.py`**:
  a self-describing export, and a verifier that imports nothing from Clarity.
- **`GET /v1/audit/export`**, needing `audit:export`. Snapshot and SDK regenerated.
- **Record hash version 3.** See below; this is the important one.
- Five new collections, one new policy key, ADR-0039.

## Why

`docs/audit-assurance-plan.md` Phase 7. The three requirements pull against the
trail's design: retention wants records gone and the chain needs them; erasure
wants a person's data gone and deleting a record breaks the chain for everyone
after them; a legal hold wants some records kept whatever the other two say.

## Decisions made

ADR-0039 has the substance. The shape of the answer: **records move, they do not
leave** (a sealed segment plus a floor, so the chain is continuous across the
boundary), **erasure shreds the link, not the record**, and **a hold outranks
both**.

## The defect this phase found

**The record hash was computed over a form the record is never published in.**

`record_hash` passed `occurred_at.isoformat()`, which gives `...+00:00`. The
canonical hasher normalises a `datetime` to `...Z`, but it never saw a datetime,
only a string it had no reason to touch. Meanwhile `model_dump(mode="json")`
publishes `...Z`. So anyone reading the published JSON and recomputing the hash
got a different answer, every time, for every record. `statement_hash` for
checkpoints had the same defect.

Nothing inside Clarity noticed, because Clarity hashed and verified through the
same function: the code agreed with itself. It surfaced the moment a second
implementation existed, in the first run of the test that compares the in-process
verifier with the offline script. That test was written expecting to catch future
drift and caught a present defect instead.

Fixed by passing the datetimes as datetimes and bumping `HASH_VERSION` to 3. No
version 2 record was ever persisted outside a test, so there is nothing to
migrate, as with the 1 to 2 bump.

The general lesson, recorded in ADR-0039: a verifier that imports the code it
checks proves only that the code agrees with itself. The duplicated canonical form
in the script is a cost worth paying, and the test that compares them is the thing
that makes the duplication safe rather than dangerous.

## Other things found

- **`ExportVerdict.problems` and a local variable shared a line of source.** A
  blanket replace turned a local `problems: list[str] = []` into a pydantic
  `Field(default_factory=list)`, which then went into a model as a `FieldInfo`.
  Caught by the tests immediately; noting it because the same careless replace
  could have been quieter somewhere else.
- **A subject hold protects its own `hold.placed` record**, because that record
  names the subject. Correct, harmless, and the test now asserts a superset rather
  than an exact set.

## Docs updated
- [x] ADR-0039, indexed
- [x] `CHANGELOG.md`: the hash version change, the new route, the new permission,
      the new collections and settings
- [x] `ARCHITECTURE.md` and `docs/modules.md` rule counts and phase status
- [x] `docs/audit-assurance-plan.md` Phase 7 checked off, revision 10
- [x] `contracts/openapi.json`, the golden snapshot and the frontend SDK
- [x] `config/policy/audit.yaml`: `audit.retention.period`
- [ ] Walkthrough (WT-14 covers backup and restore; archival and erasure are
      operator actions with no UI until Phase 5)

## Tests

`make check`: **1 failed, 2358 passed, 625 skipped**. The one failure is the
pre-existing `test_an_outbound_connection_is_refused` (403 from this container's
egress proxy; passes in CI). `make contracts-check`: passes.

New: `tests/security/test_audit_lifecycle.py`, 32 cases, including the offline
verifier run as a subprocess so it cannot borrow Clarity's code, and the test that
asserts the two verifier implementations agree.

## Open issues / next step

- **The erasure limitation is real and stated** in ADR-0039: `subscriber_ref` is an
  HMAC under one shared key, so shredding the registry entry stops Clarity linking
  a pseudonym to a person but not an outsider with the key confirming a guess.
  Closing it needs a per-subject salt in a kernel function that receipts and Kafka
  partitioning depend on. **REQUIRES HUTCH CONFIRMATION** on whether the bounded
  form is sufficient.
- RPO and RTO are still open (plan section 8 decision 1). The retention period is
  an **ASSUMPTION** at P365D.
- No UI for archival, holds or erasure. They are operator actions with step-up;
  Phase 5 decides which belong in the console.
- Next: Phase 5, the console Audit section and its browser tests.
