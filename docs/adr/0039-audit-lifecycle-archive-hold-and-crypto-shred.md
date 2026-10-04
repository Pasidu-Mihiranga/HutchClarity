# ADR-0039: the audit trail is archived, held and crypto-shredded, never deleted

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Thanoj Buddhima |
| Supersedes | - |
| Related | ADR-0033 (record hash), ADR-0035 (signed checkpoints), ADR-0036 (audit grants), ADR-0038 (recovery) |

## Context

Three lifecycle requirements pull against the trail's design and against each
other.

**Retention** says old records leave the hot table. But a hash chain is a chain:
remove record 400 and record 401 follows nothing, and `verify()` reports a
truncated trail, which is the same signal an attack produces.

**Erasure** says a person can require their data gone. Deleting their records
breaks the chain for every record after them, so honouring erasure by deletion
destroys the evidential value of everyone else's records too.

**Legal hold** says some records must be preserved whatever the other two say,
including against a sincere erasure request.

## Decision

**Records move, they do not leave.** A contiguous run is sealed into a **segment**,
a bundle in the same format and under the same key as a backup (ADR-0038), and the
hot table keeps a **floor** naming the seq and hash of the last record removed.
`AuditLedger.verify` resumes at the floor; the archived part is verified by
verifying the segment. The boundary is a join, not a gap, and nothing is
unaccounted for at any point.

**Archival is contiguous or it does not happen.** A segment with a hole cannot be
verified as a chain, so a legal hold in the middle of the eligible range **pauses
archival behind it** rather than skipping past it. The whole trail can never be
archived: the hot table keeps at least the head, so the chain has somewhere to
continue from.

**Erasure is crypto-shredding of the link, not deletion of the record.** The trail
holds pseudonyms, never numbers (I13). What identifies a person is the registry
entry mapping `subscriber_ref` to a masked number and an account; erasure destroys
that entry and leaves a tombstone saying an entry existed and was erased, which a
regulator needs and which identifies nobody. The records stay, the chain still
verifies, and `sub_9f2a...` no longer leads anywhere.

The response to the person says so, including the part they will not like: *the
link is destroyed; N audit records remain, pseudonymous, because removing one
would break the chain that makes the rest evidence.*

**A legal hold outranks an erasure request**, and the refusal is recorded with the
hold that caused it, so a person asking why can be told.

**An export is verifiable by someone who does not trust us.** It carries the
records, the covering checkpoints, the public keys and the instructions, and
`backend/scripts/verify_audit_export.py` checks all of it with nothing from
Clarity imported. A scoped export is labelled `contiguous: false` and the verifier
prints that, because a verifier that read a selection as the whole trail would
accept a redacted export as complete, which is the one way a verifier can be worse
than nothing.

**Record hash version 3.** Writing the offline verifier exposed a defect in
version 2: `record_hash` passed `isoformat()` strings for the datetimes, which
bypassed the canonical hasher's normalisation and produced `...+00:00`, while the
published JSON carries `...Z`. The hash was computed over a form the record is
never published in, so **no external verifier could ever reproduce it**. Version 3
passes the datetimes as datetimes. The same fix applies to `statement_hash`.

## The limitation, stated rather than papered over

`subscriber_ref` is an HMAC of the number under **one key shared by every
subscriber** (`kernel.common`). Destroying the registry entry removes Clarity's own
ability to go from pseudonym to person. It does **not** make the pseudonym
unlinkable to someone who holds that key and already suspects which person it is:
they can recompute the HMAC for a candidate number and confirm a match, and the
Sri Lankan mobile space is small enough to enumerate.

Closing that needs a per-subject salt inside the pseudonym, which changes a kernel
function that Trust Receipts (`subscriber_ref_hash`) and Kafka partitioning both
depend on. That is a bigger change than this phase, and it is recorded here rather
than claimed as done, because an erasure claim that is not true is worse than one
that is bounded. **REQUIRES HUTCH CONFIRMATION**: whether the bounded form
satisfies the applicable regime, and whether the HMAC key is to be held in a KMS
with its own access audit.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Delete archived records and renumber | Breaks every hash after the gap. The chain is the product. |
| Tombstone a record in place, keeping its hash | Works for the chain and fails the requirement: the detail is what identifies, and a tombstone that keeps the hash but drops the detail cannot be verified against its own `detail_hash`. |
| Encrypt every record's detail under a per-subject key | Genuine crypto-shredding of the content, and a key per subscriber on the write path of every append. Reconsider if detail ever needs to carry more than pseudonyms. |
| Let a hold block erasure but not archival | Retention would quietly move the held evidence somewhere the hold does not reach. A hold is the coarser instrument on purpose. |
| Have the offline verifier import Clarity | Then it proves the code agrees with itself. The duplication is the cost of the property, and a test asserts the two implementations agree. |
| Encrypt the export | A backup is our copy and travels in our custody; an export is handed over on purpose, so encrypting it means handing over the key, which is theatre. |

## Consequences

- An archived trail verifies from its floor, so `verified_from` is above 1 and a
  reader must not treat that as a weaker result; it is the same result over a
  trail that is partly elsewhere.
- Four new collections beside the trail: the floor, the segment index, the holds
  and the pseudonym registry. Beside it deliberately: a floor in a different store
  from the records it bounds can be lost separately from them, which would read as
  a truncated trail.
- The retention period is a policy value resolved `as_of` the moment it applies
  (I10), so lengthening it does not re-judge what was already archived. Its value
  is an **ASSUMPTION** pending the HUTCH retention period.
- The canonical form is now implemented twice, in Clarity and in the verifier
  script. A test runs both over the same export and asserts they agree, because
  two implementations drift and this is the only thing that notices.

## Compliance

`tests/security/test_audit_lifecycle.py` covers archival across the floor, holds
over ranges and subjects, erasure with the chain still intact, and the offline
verifier run as a subprocess so it cannot borrow Clarity's code. A lifecycle
operation that deletes an audit record is a review finding against this ADR.
