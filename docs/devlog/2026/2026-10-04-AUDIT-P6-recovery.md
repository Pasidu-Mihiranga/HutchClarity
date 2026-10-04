# 2026-10-04 - AUDIT Phase 6 - recovery, loss reporting and side-effect-free replay

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Opus), for Thanoj Buddhima |
| Work package | Audit assurance plan, Phase 6 |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | platform.audit, integration, platform.security, app (container, settings, collections), config/opa, CI |

## What changed

- **`platform/audit/backup.py`**: `AuditBundle`, sealed with AES-256-GCM under
  `CLARITY_AUDIT_BACKUP_KEY` and checksummed, the checksum in the header in the
  clear and bound as GCM associated data. Written through a temporary file and
  renamed.
- **`platform/audit/recovery.py`**: `LossReport`, which names the exact `seq`
  range lost, and `reconcile`, which sorts a window into agreed, missing locally,
  not done and unknown. It never executes anything.
- **`platform/audit/vault.py`**: `AuditVault.back_up`, `inspect` and `restore`,
  with their audit records. `inspect` runs before the database is touched;
  `restore` refuses a measurable loss unless `accept_loss=True`.
- **`integration/replay.py`**: `SealedCommandPort` (refuses everything, counts
  attempts) and `ReadOnlyCommandPort` (`status_of` passes, `execute` never does).
- **`Permission.AUDIT_RESTORE`**, in `AUDIT_DUTIES` and `STEP_UP_PERMISSIONS`,
  **not** grantable, held by `PLATFORM_ADMIN` only. Mirrored into
  `config/opa/data.json` so the parity suite agrees.
- Four new event types: `backup.created`, `backup.read`, `restore.performed`,
  `reconciled`.
- `tests/integration/test_audit_restore_drill.py` plus its own named step in the
  `full` CI lane.
- `docs/walkthroughs/WT-14-audit-restore-runbook.md`, ADR-0038.
- `.backups/` git-ignored; two settings and their `.env.example` entries.

## Why

`docs/audit-assurance-plan.md` Phase 6. The chain and the checkpoints make
tampering visible and do nothing about loss, which is invisible from the inside: a
trail missing its last three hundred records verifies perfectly.

## Decisions made

See ADR-0038 for the substance. Three worth repeating here:

- **Completeness can only be measured from outside the backup.** This is the whole
  design. A bundle is internally consistent by construction, so "it verified" is
  not an answer to "did we get everything back". The witness copy of a checkpoint,
  from the endpoint that already exists, is what makes the loss a number.
- **Restoring is its own authority and is not grantable.** Reading the trail out
  is a time-boxed grant; replacing history is a role permission with step-up.
- **Zero adapter calls is enforced by the type, not by discipline.** A test that
  hopes no adapter was called is not a test.

## Things found while doing it

- **`platform.audit_checkpoints` was never in `ALL_COLLECTIONS`.** The `full`
  profile had no table for a checkpoint. A memory store creates a collection on
  first use, so nothing caught it until something asked PostgreSQL for the table.
  Fixed, with a test asserting the registration. I first believed three more
  collections were missing too; they were already registered under their imported
  names and only this one was genuinely absent.
- **A corrupted bundle raised one of two different exceptions** depending on which
  bit moved: a flipped bit lands outside the base64 alphabet often enough that a
  corruption test passed four times in five. Decode failure is now
  `BundleTampered` like any other corruption, which is both the correct taxonomy
  and what makes the test deterministic. Confirmed over eight consecutive runs.
- **A bundle ends one record before its own `backup.created`**, because that record
  quotes the checksum and the checksum covers the records. Documented rather than
  worked around; the loss report counts it as lost, correctly.

## Docs updated
- [ ] MODULE.md (nothing in a module changed; this is platform and integration)
- [x] ADR-0038, indexed in `docs/adr/README.md`
- [x] Walkthrough WT-14, indexed in `docs/WALKTHROUGHS.md`
- [x] `.env.example` and `.gitignore` for the two new variables
- [x] `docs/audit-assurance-plan.md` Phase 6 checked off
- [ ] CHANGELOG.md (no `/v1` contract change; the vault has no route yet)
- [ ] Plan via CHANGES.md (no enterprise-plan chapter changed)

## Tests

`make check`: **1 failed, 2314 passed, 624 skipped**, the one failure being the
pre-existing `test_an_outbound_connection_is_refused`, which gets `403 Forbidden`
from this container's egress proxy and passes in CI.

`backend/tests/security/test_audit_recovery.py`: 28 of 28, run eight times
consecutively after the taxonomy fix to confirm the flake is gone.

**Not run:** `tests/integration/test_audit_restore_drill.py`. No PostgreSQL in
this container, so it skipped. The CI `full` lane is where it executes, and until
a green run there the real-`DELETE`, real-transaction behaviour is argued rather
than observed. WT-14 says so in its status line, and so does the plan.

## Open issues / next step

- The drill needs a green `full` lane before WT-14's status can say verified.
- RPO, RTO and the retention period are still **REQUIRES HUTCH CONFIRMATION** (plan
  section 8, decisions 1 and 2). The drill has no pass criterion for elapsed time
  until there is an RTO.
- There is no HTTP route for backup or restore yet. Deliberate: it is an operator
  action with step-up, and a route is a bigger surface than a method. Phase 5's
  console work is where that decision belongs.
- Next: Phase 7 (retention, legal hold, erasure, verifiable export), then Phase 5.
