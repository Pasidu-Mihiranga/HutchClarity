# 0033 - The audit record hash covers the whole record

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Thanoj Buddhima |
| Plan references | `docs/audit-assurance-plan.md` (G1, W0), enterprise-plan/11 (T4), plan §20.3 |

## Context

The audit ledger chained records with
`chain_hash = sha256(prev + "\n" + payload_hash)`. Only the payload hash and
the previous hash were inside it. `seq`, `event_type`, `actor_ref`,
`object_ref`, `case_id`, `at` and the human-readable `detail` were not.

That was tested on 2026-10-04: rewriting a stored record's approver from
`sup:ruwan` to `agent:nadeesha`, changing its type, moving it to another case,
backdating it to 2020 and changing its shown amount from 12000.00 to 50.00 left
`verify()` returning `intact=True`. The fields an investigation depends on,
who did it, when and to which case, could be changed without trace.

## Decision

**Version 2 hashes the canonical form of every field except the hash itself.**
The `detail` an admin reads is bound through `detail_hash`, and verification
also checks that `detail` still matches it. Each record carries
`hash_version`, so the rule can change again without ambiguity.

Fields added at the same time, because accountability needs them inside the
hash from the start:

| Field | Why |
|---|---|
| `actor_kind` | customer, staff, system or agent: the first filter in an investigation |
| `session_ref` | ties an action to the session that performed it |
| `occurred_at` / `recorded_at` | when it happened, as stated, and when it was recorded, by the ledger's clock; `recorded_at` is non-decreasing along the chain, so a backdated record shows |

Floats in a payload or detail (confidence scores, never money: I3) are
rendered with `repr` before hashing, and the detail is stored in that form, so
the canonical hasher's refusal of floats stays in force everywhere else.

No migration: no version 1 record was ever persisted (ADR-0034 is the first
time the trail is stored), so version 2 starts at genesis.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Add fields to the payload instead | The ledger does not keep payloads, only their hashes, so it could not check a stored field against the payload anyway. |
| Sign every record | A signature per record costs a key operation per write and still needs a chain. Signed checkpoints over a whole-record chain give the same assurance at a fraction of the cost (audit assurance plan, Phase 2). |
| Hash `detail` directly into the record hash | Works, but a fixed-shape hash input with `detail_hash` keeps the verification logic independent of what a detail contains. |

## Consequences

- Any single-field edit to any stored record is detected, and the test suite
  checks each field individually.
- Tests that tampered by assigning the ledger's private list now tamper
  through the store, which is where an insider would do it.
- A hash chain still cannot catch an insider who rewrites **every** record and
  the head consistently. That needs a key held outside the database: signed
  checkpoints, Phase 2 of the plan.

## Compliance

`tests/unit/test_events_and_audit.py::test_rewriting_any_field_of_a_record_is_detected`
covers every field version 1 left exposed. A new field added to `AuditRecord`
without adding it to `record_hash` is a review finding against this ADR.

## Amendment, 2026-10-04: no keyed payload hash

The assurance plan proposed making `payload_hash` a keyed hash (HMAC under a key
held beside the checkpoint key), on the ground that a plain SHA-256 of a phone
number is reversible by enumerating a mobile prefix. **That is not being done**,
and the risk is addressed differently.

Two reasons it was the wrong fix.

- **It breaks verifiable export.** `AuditLedger.proves` exists so an auditor
  holding a document can confirm the ledger recorded *that* document, and the
  plan promises an export a regulator checks without trusting Clarity. A keyed
  hash makes both impossible without a key only Clarity holds, which leaves the
  trail verifiable by Clarity alone: the one property this design exists to
  avoid.
- **It protects the wrong field.** `detail` is stored in the clear so a person
  can read the trail. A phone number there is readable by anyone with audit
  access, and no hash, keyed or not, changes that.

Instead the identifier does not reach the ledger. `platform.audit.entropy`
screens every append, payload and detail alike, and **refuses** a raw MSISDN,
NIC, card number or email address. Masking is never optional (I13), so a caller
passing one has a defect, and a defect on the audit path fails loudly rather
than writing personal data into a store that by design cannot be edited.

The screen is deliberately high precision, not high recall: a false positive
fails a real customer operation (ADR-0034), so each pattern needs a structural
signal (the `+94`/`07` prefix, the `V` suffix, a Luhn-valid run) and must sit on
non-alphanumeric boundaries. Opaque cryptographic fields are listed and skipped,
because a hash has no author who could put a number in it and screening one only
invites a false positive. Recall stays the masker's job on the text path; this is
the backstop on the audit path.

Covered by `tests/security/test_audit_entropy.py`, which asserts both halves:
the identifiers that must be refused, and the forms the codebase actually uses,
which must keep working.
