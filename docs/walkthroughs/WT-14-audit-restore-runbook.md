# WT-14 - audit trail backup and restore runbook

| Field | Value |
|---|---|
| Audience | operators / incident responders / auditors |
| Journey | Take a backup; lose the trail; measure what was lost against an external checkpoint; restore; reconcile the window |
| Status | verified in the `lite` profile; the PostgreSQL drill is written and runs in the `full` CI lane, **not yet executed** (no PostgreSQL in the container this was built in) |
| Last verified | 2026-10-04, `backend/tests/security/test_audit_recovery.py` (28 of 28) |

Related: ADR-0038 (recovery measured against an external checkpoint), ADR-0035
(signed checkpoints), ADR-0036 (audit grants), `docs/audit-assurance-plan.md`
Phase 6.

## 0. The one thing to do before you need this

**Keep a witness copy of a checkpoint somewhere this system cannot reach.**

```
curl -s http://localhost:8000/.well-known/clarity-audit-checkpoint.json \
  > witness-$(date +%F).json
```

The endpoint is unauthenticated on purpose (ADR-0035): a witness nobody can fetch
is not a witness. It serves the latest checkpoint plus the public key, which is
everything needed to verify it and nothing else.

Anything that is not this deployment will do: an operator's laptop, another
host's cron job, an auditor's inbox. Without one, a restore cannot tell you
whether it recovered everything; it will say `complete` is unknown, and it will be
telling the truth, which is not the same as reassuring you.

A witness file is public material. It carries a `seq`, a chain head, a time, a
signature and the public key. It reveals nothing about any customer, which is why
it can be sent to anyone.

## 1. Taking a backup

Needs `audit:export`. Holding it removes every money permission from the account
for as long as it is held (ADR-0036 rule 1), so it is normally a time-boxed grant
rather than a standing role.

```python
from pathlib import Path
clarity.audit_vault.back_up(principal, Path(".backups/trail-2026-10-04.backup"))
```

What happens:

1. Every record, every checkpoint and the head pointer are read in one unit of work.
2. The bundle is sealed with AES-256-GCM under `CLARITY_AUDIT_BACKUP_KEY`.
   **Unset means refused**, not written in the clear.
3. It is written to a temporary file and renamed, so a failure leaves the previous
   backup rather than a truncated one.
4. `backup.created` is appended, naming the checksum, the record count and the
   `seq` range. The **file name**, never the path: a path names a mount, a host,
   sometimes a person.

Note the checksum printed by the audit record. It is also in the bundle's header,
in the clear, so you can read it off the file without the key:

```
head -3 .backups/trail-2026-10-04.backup
```

## 2. When the trail is gone

Symptoms: the console's chain health panel is red, or startup refuses with
`AuditChainBroken`, or the assurance module raised `chain_break` and the
playbook has already turned off `AUTO_FIX_GLOBAL` and `CUSTOMER_ACTIONS`.

**Leave those switches off.** Money stops moving while the trail cannot be
trusted. Turning them back on is a deliberate act by someone with the authority,
with a reason, after the break is understood.

## 3. Measure before you restore

This is the step people skip and should not. `inspect` reads the bundle and
reports what a restore would and would not recover, **without touching the
database**, so you learn the size of the loss while it is still your choice.

```python
import json
from clarity.platform.audit.checkpoints import Checkpoint
witness = Checkpoint.model_validate(json.loads(Path("witness-2026-10-04.json").read_text()))
report = clarity.audit_vault.inspect(principal, path, witness)
print(report.summary)
```

A real answer looks like:

```
the trail was restored to seq 3990; a signed checkpoint proves it reached 4210,
so records 3991 to 4210 (220) were lost
```

If the report says the external checkpoint "does not verify, so it proves
nothing", the witness file is wrong or forged. Find another; do not proceed on it.

## 4. Restore

Needs `audit:restore`, which comes from the platform admin role, needs recent
MFA, and is **not** grantable: replacing history is not a duty handed out for an
afternoon.

```python
report = clarity.audit_vault.restore(principal, path, witness=witness, accept_loss=True)
```

`accept_loss=True` is required when anything was lost. Without it the restore
refuses and tells you why. Saying it is recorded: `restore.performed` carries
`accepted_loss`, the range and the count, and it is written **into the restored
trail**, so the restore is part of the history it created.

Then confirm:

```python
clarity.audit.verify().intact          # the chain
clarity.audit_checkpoints.verify(witness=witness).intact
```

## 5. Reconcile the window

Records in the lost window are gone, so the trail cannot say what they held. Two
things can: the restored domain state, and HUTCH itself.

```python
from clarity.integration.replay import ReadOnlyCommandPort
from clarity.platform.audit.recovery import ActionToCheck, reconcile

port = ReadOnlyCommandPort(clarity.adapters.command_port)
plan = reconcile(actions, port.status_of)
print(plan.summary)
```

Four buckets, and what each means:

| Bucket | Meaning | What to do |
|---|---|---|
| `agreed` | both sides hold the execution | nothing |
| `missing_locally` | HUTCH did it, the restored state lost it | re-ingest the outcome **once**; never execute it again |
| `not_done` | HUTCH has no record of the key | a person may put it through the normal path, which is the only path that moves money |
| `unknown` | the far side could not be asked | a person decides; nothing is guessed |

`reconcile` cannot execute anything, and not by convention: `ReadOnlyCommandPort`
raises on `execute`. The same applies to any replay that rebuilds state, which
runs under `SealedCommandPort` and refuses every call while counting the attempts,
so "zero adapter calls" is checkable rather than assumed.

Check everything the restored state knows about, not only the lost window. The
window names the audit records that went missing, not the actions: an action whose
record survived may still have been rolled back with the database.

## 6. Afterwards

- Record the incident with the loss report's exact numbers.
- Take a fresh backup, and a fresh witness copy.
- Turn the kill switches back on, with a reason, now that the trail verifies.
- The `break_glass_used`, `chain_break` and `restore.performed` records are all in
  the trail. Somebody other than whoever ran the restore closes those alerts: the
  second-person rule applies here as everywhere.

## What is not verified yet

The PostgreSQL drill (`tests/integration/test_audit_restore_drill.py`) is written
and wired into the `full` CI lane as its own named step, but it has not run: the
container this was built in has no PostgreSQL, so it skipped. Until a `full` lane
goes green, the memory-store tests are the evidence, and the behaviour of a real
`DELETE` and a real transaction is argued rather than observed. Re-verify this
walkthrough and this line on the first green `full` run.
