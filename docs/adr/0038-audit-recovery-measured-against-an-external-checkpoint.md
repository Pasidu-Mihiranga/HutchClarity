# ADR-0038: audit recovery is measured against an external checkpoint

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Thanoj Buddhima |
| Supersedes | - |
| Related | ADR-0034 (one persisted trail), ADR-0035 (signed checkpoints), ADR-0036 (audit grants) |

## Context

The hash chain (ADR-0033) and the signed checkpoints (ADR-0035) make tampering
visible. Neither does anything about **loss**. A dropped table, a failed disk or a
bad migration takes the trail with it, and an append-only record of who did what
is exactly the kind of data that cannot be reconstructed from anywhere else: the
whole point of it is that it is the only copy of a fact.

Worse, loss is invisible from the inside. A trail that has lost its last three
hundred records verifies perfectly: the chain is intact up to where it stops, the
head pointer agrees, and every checkpoint inside it is genuine. A backup is the
same, only more so, because a backup is complete *as of when it was made* and
nothing inside it knows what came after. "It verified" is therefore not an answer
to "did we get everything back".

The assurance plan sets the constraint for all of this: enterprise-grade
recoverability with **no heavy infrastructure**.

## Decision

**Completeness is measured against a checkpoint held outside the backup.** A
signature over `seq` 4210 proves the trail once reached 4210, so a restore that
stops at 3990 lost exactly 3991 to 4210. The loss report says that, in those
numbers. The copy comes from the public witness endpoint, which exists already,
so this needs no new store and no new service: a witness is anyone who kept a
copy, including an auditor, a regulator or a cron job on another machine.

**A backup is a file, encrypted and checksummed.** AES-256-GCM under
`CLARITY_AUDIT_BACKUP_KEY`, because a backup travels and a copy of the trail is as
sensitive as the live table and more portable. GCM rather than CBC so the
ciphertext is authenticated. The checksum travels in the header in the clear, so
an operator can say which bundle they mean before they can open one, and compare
two systems without the key.

**Reading a backup is audited, not only writing one.** Restoring is the only
operation in the system that can put a different past in place of the real one,
so `backup.read` and `restore.performed` are both events, and the restore record
is written *into the restored trail*, making the restore part of the history it
created.

**Restoring is its own authority and is not grantable.** `audit:restore` comes
from the platform admin role, needs step-up, and is in `AUDIT_DUTIES`, so holding
it costs every money permission (ADR-0036 rule 1). Reading the trail out
(`audit:export`) is a time-boxed grant; replacing it is not something handed out
for an afternoon.

**A restore refuses to lose records silently.** When the bundle is measurably
short of the external checkpoint, the call fails unless the operator passes
`accept_loss=True`, and the accepted loss is recorded. The default is to stop.

**Replay cannot reach a HUTCH system, structurally.** `SealedCommandPort` raises
on every call and counts the attempts, so "zero adapter calls" is a property of
the type rather than a hope about the code path. Reconciliation uses
`ReadOnlyCommandPort`, which passes `status_of` through and still refuses
`execute`.

**Reconciliation never executes anything.** It asks the far side, by idempotency
key, whether each action was already done, and sorts the answers into four
buckets for a person: agreed, missing locally, not done, unknown. A refund HUTCH
already made is re-ingested as a fact, exactly once, and never executed again
(I8). An unreachable system becomes `unknown` rather than an exception, because a
reconciliation that halts at the first failure leaves the rest of the window
unexamined and the point is to hand over a complete picture.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Trust the backup's own completeness | A bundle is internally consistent by construction. This is the failure mode, not the fix. |
| Store checkpoints in a second database | New infrastructure, and a second thing an insider with access can reach. A witness's saved copy costs nothing and is outside the blast radius. |
| Write-ahead shipping to an append-only object store | Stronger, and real infrastructure. Reconsider when a deployment has it; the loss report works the same way over it. |
| Re-execute the lost window from the records | The one thing that must never happen. A refund executed twice is the harm the whole design is arranged to prevent. |
| Let `supports()` raise during replay too | Then code that checks before acting raises where it would have taken its unavailable branch. It answers locally, `False`, and is not counted. |

## Consequences

- A restore produces a number, not a reassurance: "records 3991 to 4210 (220) were
  lost" is something an incident report can carry and a regulator can check.
- Without a witness checkpoint, completeness is *unknown* and the report says so
  rather than claiming success. Keeping a witness copy is therefore an operational
  requirement, not an optimisation, and belongs in the runbook.
- A bundle ends one record before its own `backup.created`, because that record
  quotes the checksum and the checksum covers the records. The loss report counts
  it as lost, correctly.
- `platform.audit_checkpoints` had never been added to `ALL_COLLECTIONS`, so the
  `full` profile had no table for a checkpoint. A memory store makes a collection
  on first use, which is why nothing caught it until the drill asked PostgreSQL.
  Fixed here, with a test.
- The drill runs in the `full` CI lane on every merge. It is the only thing that
  proves a backup can be restored, and a backup nobody has restored is a hope.

## Compliance

`tests/security/test_audit_recovery.py` covers the three acceptance tests from the
plan and the authority rules. `tests/integration/test_audit_restore_drill.py`
runs the drill against PostgreSQL in the `full` lane. A new recovery path that
reports completeness without an external checkpoint is a review finding against
this ADR.
