# WT-15 - the console Audit section

| Field | Value |
|---|---|
| Audience | compliance / security admins / demo presenters / judges |
| Journey | Sign in to the console as a role with an audit duty; read chain health; read the trail and watch that read appear in the trail; recompute a record's hashes; take an alert through its lifecycle; see what a role without the duty is refused |
| Status | verified, browser steps |
| Last verified | 2026-10-04 (browser, `frontend/e2e/audit-console.spec.ts`, 9 of 9; whole suite 28 of 28) |

Related: audit assurance plan 5.8, ADR-0037 (assurance module), ADR-0038
(recovery), ADR-0039 (lifecycle), WT-13 (the rest of the console), WT-14 (the
backup and restore runbook).

## 1. What you will see

Eight panels, and one rule running through all of them: **show the evidence, not
a reassurance.** Chain health shows what it recomputed and says what that does
not cover. An alert shows the `seq` numbers that justify it, as links. The trail
explorer will recompute a record's hashes in front of you.

## 2. Start it

```
make dev          # the API on :8000, lite profile, no services
make web-console  # the console on :3001
```

Open `http://localhost:3001/audit`. The role picker is at the bottom: tick
**Step-up MFA** and choose **Security** (security admin) for the fullest view, or
**Compliance** to see a role that can close alerts but not grant duties.

## 3. Chain health

The badge is `intact` or `BROKEN`. The numbers next to it are the length, the
checkpoint count, the age of the last signed checkpoint, when detection last ran,
the writer lag (events committed but not yet published) and how much has been
archived.

Read the note underneath, because it is the point: this check recomputes **from
the last signed checkpoint up**, not from record 1. It catches truncation and
tampering since that checkpoint. It does **not** re-read the records below it,
which the full verification at startup does. A green badge that implied more than
that would be the kind of reassurance this whole section exists to avoid.

The note also links the public checkpoint,
`/.well-known/clarity-audit-checkpoint.json`. Keep a copy somewhere this system
cannot reach. Without one, a restore cannot tell you what it lost (WT-14 §0).

## 4. The trail explorer, and the read that records itself

It says **Not loaded**, deliberately. The trail is read on request, not on a
timer: every read is recorded, and a polling dashboard would bury the reads that
matter in the ones that do not. It would also trip the `mass_audit_read` rule
within minutes, so the monitor would raise alerts about the act of monitoring.

Press **Read the trail**. Then press it again and look for `audit.read` in the
list: your own read is in there, with who you are and the filters you used. That
is rule 5, and the browser test asserts it.

Filter by **Actor** for one person's timeline: sign-ins, actions and refusals in
one line. Filter by **Event type** (`action.executed`, `access.denied`,
`otp.failed`) or by **Case**.

## 5. Verify a record

Press **Verify** on any row. The badge that comes back is the server having
recomputed that record's own hash from its fields and checked its link to the
record before it.

What it cannot do, and says so in the route's own documentation: confirm the
*payload*. The ledger never stored one, only its hash. Confirming a payload is
`proves()`, and it needs the document the caller is holding, which a console does
not have. An auditor with a document uses the export instead.

## 6. Alerts

The queue, by severity, with the evidence `seq` numbers as links. Detection's last
run is printed above it, because a quiet queue and a stopped detector are not the
same thing.

With `alert:dispose` (Compliance has it by role) you can **Acknowledge**, then
**Investigate**, then **Dispose** with a disposition and a reason. The reason is
required by the server, not just by the form.

Two rules you can see working:

- **Nobody closes an alert they are the subject of.** The server refuses it.
- **A high or critical alert is closed by someone other than whoever
  acknowledged it.** Acknowledge as Compliance, then switch role and try to
  dispose as the same person: it is refused with `SECOND_PERSON`.

As **Security**, the lifecycle buttons are absent: security admin holds
`audit:read` and `audit:assign` but not `alert:dispose`. Absent rather than
present-and-failing, which is the difference between a UI that knows the rules and
one that discovers them.

## 7. Monitors, Access, Recovery

**Monitors** is who is watching and since when, read from the grants: a monitor is
someone holding a time-boxed audit duty, so the list empties by itself when nobody
recertifies. Underneath it, which open alerts somebody has picked up.

**Access** is the grants themselves with their expiry and recertification dates,
and the break-glass count. As **Compliance** this panel says *not for this role*,
because granting needs `audit:assign`: one panel being refused does not blank the
rest, which a browser test pins after the first run of this suite showed it doing
exactly that.

**Recovery** is the last backup, the last restore with its loss count, and the
last sealed segment, read out of the trail rather than from a status table: a
status table can disagree with what happened. In the `lite` profile with no
`CLARITY_AUDIT_BACKUP_KEY` it says **no backup key** in red and states that
nothing is being backed up, rather than showing an empty "last backup" and looking
fine. Backup and restore themselves are operator actions with step-up, run from
WT-14.

## 8. Export

With `audit:export`, **Export a verifiable bundle** downloads the records, the
covering checkpoints and the public keys. Check it with something that has never
imported Clarity:

```
python backend/scripts/verify_audit_export.py export.json
```

Scoping it to a case makes it a **selection**, and the bundle says so, and the
verifier prints it. A verifier that read a selection as the whole trail would
accept a redacted export as complete, which is the one way a verifier can be worse
than nothing.

## 9. What a role without the duty sees

Pick **Agent**. The page itself refuses with `audit:read`. The nav link is greyed
out too, but the greying is a convenience: the refusal is the real control, and it
is enforced server-side on every one of these routes.

## What is not here

- **No backup, restore, archive, hold or erase buttons.** Those are operator
  actions needing step-up and, for a restore, an authority that is not grantable.
  They are run from the runbook (WT-14) and the plan does not put them in a
  console that a desk supervisor can reach.
- **No shift handover.** Plan 5.8 lists it under Monitors. There is no shift model
  in the system to hand over, so the panel shows duty start times and alert
  ownership instead, which is what the trail actually knows.
