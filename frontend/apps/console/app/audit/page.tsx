"use client";

/**
 * The Audit section (audit assurance plan 5.8, ADR-0037, ADR-0038, ADR-0039).
 *
 * Eight panels, and one rule running through all of them: show the evidence, not
 * a reassurance. Chain health shows the verdict and what it does and does not
 * cover; an alert shows the seq numbers that justify it; the trail explorer can
 * recompute a record's hashes in front of you.
 *
 * Two deliberate restraints.
 *
 * Health polls, the trail does not. The health endpoint is not recorded as
 * `audit.read`, because a dashboard polling it would make the console trip the
 * `mass_audit_read` rule within minutes: the monitor would raise alerts about
 * the act of monitoring. Reading the trail *is* recorded, so the explorer loads
 * on request rather than on a timer.
 *
 * Nothing here is a write path for money, and the permission checks are the
 * real ones: a role without `audit:read` sees the access-denied page, and the
 * lifecycle buttons are hidden without `alert:dispose` rather than failing on
 * click.
 *
 * ---
 *
 * E2 added the accessibility structure this page did not have.
 *
 * **Each panel is a landmark with a name.** Eight cards of dense evidence were
 * one undifferentiated region; they are now named sections, so a screen reader
 * user can jump to Recovery without reading Chain health first.
 *
 * **The trail is a grid, navigable by arrow key.** Fifty records with a button
 * each meant fifty tab stops. The table takes one, Up and Down move a row at a
 * time, and Enter verifies the row that has focus (see `useRovingRows`).
 *
 * **Disposing of an alert is a dialog.** The reason is required and the API
 * refuses without one, which the inline form expressed as a validation error
 * after the click. Asking for it in a dialog puts the requirement where the
 * decision is, and gives the keyboard path a focus trap and an Escape route.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  Field,
  Input,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@clarity/ui";
import { ClarityApiError } from "@clarity/sdk";
import type {
  AlertView,
  AuditGrantView,
  AuditHealth,
  AuditRecordVerdict,
  AuditRecordView,
  AuditRecovery,
  AuditTrailPage,
} from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { PageHeader } from "@/components/PageHeader";
import { useStaffSession } from "@/components/StaffSessionProvider";
import { useRovingRows } from "@/lib/useRovingRows";

const BAND_TONE: Record<string, "neutral" | "success" | "warning" | "danger"> = {
  low: "neutral",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

const DISPOSITIONS = [
  { value: "confirmed", label: "Confirmed" },
  { value: "false_positive", label: "False positive" },
  { value: "accepted_risk", label: "Accepted risk" },
];

function age(seconds: number | null): string {
  if (seconds === null) return "never";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

function when(value: string | null | undefined): string {
  if (!value) return "never";
  return value.replace("T", " ").slice(0, 19);
}

export default function AuditPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const canRead = hasPermission("audit:read");
  const canDispose = hasPermission("alert:dispose");
  const canExport = hasPermission("audit:export");

  const [health, setHealth] = useState<AuditHealth | null>(null);
  const [recovery, setRecovery] = useState<AuditRecovery | null>(null);
  const [alerts, setAlerts] = useState<AlertView[]>([]);
  const [detectionRan, setDetectionRan] = useState<string | null>(null);
  const [grants, setGrants] = useState<AuditGrantView[]>([]);
  const [trail, setTrail] = useState<AuditTrailPage | null>(null);
  const [verdicts, setVerdicts] = useState<Record<number, AuditRecordVerdict>>({});
  const [filters, setFilters] = useState({ actor_ref: "", event_type: "", case_id: "" });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [disposing, setDisposing] = useState<AlertView | null>(null);
  const [disposition, setDisposition] = useState("confirmed");
  const [reason, setReason] = useState("");

  const [refused, setRefused] = useState<Record<string, boolean>>({});

  /**
   * Each panel loads on its own, and a refusal on one does not blank the rest.
   *
   * Deny by default (I9) means different roles legitimately see different
   * panels: compliance holds `audit:read` and `alert:dispose` but not
   * `audit:assign`, so `GET /v1/audit/grants` answers 403 for them. A single
   * `Promise.all` turned that one expected refusal into an empty page with an
   * error banner, which the first browser run showed. A 403 is now the panel
   * saying "not for this role"; anything else is a real error.
   */
  const loadStatus = useCallback(async () => {
    if (!canRead) return;
    setError(null);
    const problems: string[] = [];
    const denied: Record<string, boolean> = {};

    async function panel<T>(name: string, load: () => Promise<T>, apply: (value: T) => void) {
      try {
        apply(await load());
      } catch (err) {
        // The status, not the message. Matching on wording would break the
        // moment a detail string changed, and the SDK already carries the code.
        if (err instanceof ClarityApiError && (err.status === 403 || err.status === 401)) {
          denied[name] = true;
          return;
        }
        problems.push(`${name}: ${err instanceof Error ? err.message : String(err)}`);
      }
    }

    await Promise.all([
      panel("health", () => client.auditHealth(), setHealth),
      panel("recovery", () => client.auditRecovery(), setRecovery),
      panel("alerts", () => client.listAlerts(), (queue) => {
        setAlerts(queue.alerts);
        setDetectionRan(queue.detection_last_ran_at);
      }),
      panel("grants", () => client.listAuditGrants(), (value) => setGrants(value.grants)),
    ]);

    setRefused(denied);
    setError(problems.length ? problems.join(" · ") : null);
  }, [canRead, client]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus, generation]);

  async function loadTrail() {
    setBusy(true);
    setError(null);
    try {
      setTrail(await client.auditTrail({ ...filters, limit: 50 }));
      setVerdicts({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read the trail");
    } finally {
      setBusy(false);
    }
  }

  const verifyRecord = useCallback(
    async (seq: number) => {
      try {
        const verdict = await client.verifyAuditRecord(seq);
        setVerdicts((current) => ({ ...current, [seq]: verdict }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not verify that record");
      }
    },
    [client],
  );

  const records = trail?.records ?? [];
  // Enter on the focused row verifies that row, which is the one action the
  // trail offers: the keyboard gets the same reach as the mouse.
  const { rowProps } = useRovingRows(records.length, (index) => {
    const record = records[index];
    if (record) void verifyRecord(record.seq);
  });

  async function move(alertId: string, action: "acknowledge" | "investigate") {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (action === "acknowledge") {
        await client.acknowledgeAlert(alertId);
      } else {
        await client.investigateAlert(alertId);
      }
      setMessage(`${alertId}: ${action}d`);
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not ${action} that alert`);
    } finally {
      setBusy(false);
    }
  }

  async function dispose() {
    const target = disposing;
    if (!target || !reason.trim()) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await client.disposeAlert(target.alert_id, {
        disposition,
        reason: reason.trim(),
      });
      setMessage(`${target.alert_id}: disposed`);
      setDisposing(null);
      setReason("");
      setDisposition("confirmed");
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not dispose of that alert");
    } finally {
      setBusy(false);
    }
  }

  if (!session || !canRead) {
    return <AccessDenied need="audit:read" />;
  }

  const activeGrants = grants.filter((grant) => grant.state === "active");
  const breakGlass = grants.filter((grant) => grant.break_glass);
  const monitors = activeGrants.filter((grant) =>
    ["audit:read", "alert:dispose", "audit:export"].includes(grant.permission),
  );
  const openAlerts = alerts.filter((alert) => alert.state !== "disposed");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit"
        description="Every panel shows the evidence, not a reassurance. Reading the trail is itself recorded, and so is this session."
      />

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      {/* 1. Chain health */}
      <section aria-labelledby="audit-health">
        <Card className="space-y-3" data-testid="chain-health">
          <div className="flex items-center justify-between">
            <h2 id="audit-health" className="font-medium">
              Chain health
            </h2>
            {health ? (
              <Badge tone={health.intact ? "success" : "danger"}>
                {health.intact ? "intact" : "BROKEN"}
              </Badge>
            ) : (
              <Badge>loading</Badge>
            )}
          </div>
          {health ? (
            <>
              <dl className="grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs uppercase text-fg-muted">Records</dt>
                  <dd className="font-mono" data-testid="chain-length">
                    {health.length}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-fg-muted">Checkpoints</dt>
                  <dd className="font-mono">{health.checkpoints}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-fg-muted">Last checkpoint</dt>
                  <dd className="font-mono">{age(health.last_checkpoint_age_seconds)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-fg-muted">Detection last ran</dt>
                  <dd className="font-mono">{when(health.detection_last_ran_at)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-fg-muted">Writer lag</dt>
                  <dd className="font-mono" data-testid="writer-lag">
                    {health.writer_lag_events} event(s) unpublished
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-fg-muted">Archived below</dt>
                  <dd className="font-mono">
                    {health.archived_below_seq ? `seq ${health.archived_below_seq}` : "nothing"}
                  </dd>
                </div>
              </dl>
              {!health.intact ? (
                <Alert tone="danger">
                  Broken at seq {health.broken_at}: {health.reason}
                  {health.lost_from
                    ? ` Records ${health.lost_from} to ${health.lost_to} are missing.`
                    : ""}
                </Alert>
              ) : null}
              <p className="text-xs text-fg-muted">
                This check recomputes from seq {health.verified_from} up, anchored on
                the last signed checkpoint. It catches truncation and any tampering
                since that checkpoint; it does not re-read the records below it,
                which the full verification at startup does. Keep a copy of{" "}
                <a className="underline" href={health.witness_url}>
                  the public checkpoint
                </a>{" "}
                somewhere this system cannot reach: without one, a restore cannot
                tell you what it lost.
              </p>
            </>
          ) : null}
        </Card>
      </section>

      <div className="grid items-start gap-4 lg:grid-cols-2">
        <div className="grid content-start gap-4">
        {/* 4. Alerts */}
        <section aria-labelledby="audit-alerts">
          <Card className="h-fit space-y-3" data-testid="alerts-panel">
            <div className="flex items-center justify-between">
              <h2 id="audit-alerts" className="font-medium">
                Alerts
              </h2>
              <Badge tone={openAlerts.length ? "warning" : "success"}>
                {openAlerts.length} open
              </Badge>
            </div>
            <p className="text-xs text-fg-muted">
              Counted from the trail, never scored by a model. Detection last ran{" "}
              {when(detectionRan)}.
            </p>
            {alerts.length === 0 ? (
              <p className="text-sm text-fg-muted" data-testid="no-alerts">
                Nothing has fired. A quiet queue and a stopped detector are not the
                same thing, which is why detection writes a heartbeat either way.
              </p>
            ) : null}
            <ul className="space-y-3">
              {alerts.slice(0, 8).map((alert) => (
                <li
                  key={alert.alert_id}
                  className="space-y-2 rounded border border-border p-3 text-sm"
                  data-testid="alert-row"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="font-mono text-xs">{alert.rule_id}</span>
                      <p className="text-fg">{alert.summary}</p>
                    </div>
                    <Badge tone={BAND_TONE[alert.band] || "neutral"}>{alert.band}</Badge>
                  </div>
                  <p className="text-xs text-fg-muted">
                    {alert.state}
                    {alert.occurrences > 1 ? ` · seen ${alert.occurrences} times` : ""}
                    {alert.acknowledged_by ? ` · acknowledged by ${alert.acknowledged_by}` : ""}
                    {alert.escalated_at ? " · escalated" : ""}
                  </p>
                  <p className="text-xs text-fg-muted">
                    Evidence:{" "}
                    {alert.evidence.length ? (
                      alert.evidence.map((seq: number) => (
                        <button
                          key={seq}
                          type="button"
                          className="mr-1 underline"
                          aria-label={`Verify record ${seq}, cited by ${alert.rule_id}`}
                          onClick={() => {
                            setFilters({ actor_ref: "", event_type: "", case_id: "" });
                            void verifyRecord(seq);
                          }}
                        >
                          #{seq}
                        </button>
                      ))
                    ) : (
                      <span>none cited</span>
                    )}
                  </p>
                  {canDispose && alert.state !== "disposed" ? (
                    <div className="flex flex-wrap items-center gap-2">
                      {alert.state === "open" ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={busy}
                          aria-label={`Acknowledge ${alert.rule_id}`}
                          onClick={() => void move(alert.alert_id, "acknowledge")}
                        >
                          Acknowledge
                        </Button>
                      ) : null}
                      {alert.state === "acknowledged" ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={busy}
                          aria-label={`Investigate ${alert.rule_id}`}
                          onClick={() => void move(alert.alert_id, "investigate")}
                        >
                          Investigate
                        </Button>
                      ) : null}
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={busy}
                        aria-label={`Dispose of ${alert.rule_id}`}
                        onClick={() => {
                          setDisposing(alert);
                          setReason("");
                          setDisposition("confirmed");
                        }}
                      >
                        Dispose
                      </Button>
                    </div>
                  ) : null}
                  {alert.state === "disposed" ? (
                    <p className="text-xs text-fg-muted">
                      {alert.disposition} by {alert.disposed_by}: {alert.disposition_reason}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
            {!canDispose ? (
              <p className="text-xs text-fg-muted">
                Read-only: closing an alert needs alert:dispose, which costs its
                holder every money permission.
              </p>
            ) : null}
          </Card>
        </section>

        {/* 6. Access */}
        <section aria-labelledby="audit-access">
          <Card className="h-fit space-y-3" data-testid="access-panel">
            <div className="flex items-center justify-between">
              <h2 id="audit-access" className="font-medium">
                Access
              </h2>
              <Badge tone={breakGlass.length ? "warning" : "neutral"}>
                {breakGlass.length} break-glass
              </Badge>
            </div>
            <p className="text-xs text-fg-muted">
              Audit duties are granted, approved by a second person, time-boxed and
              recertified. Holding one removes every money permission.
            </p>
            {refused.grants ? (
              <p className="text-sm text-fg-muted" data-testid="access-refused">
                Not for this role: granting, approving and revoking audit duties needs
                audit:assign, which is a role permission and never itself a grant.
              </p>
            ) : grants.length === 0 ? (
              <p className="text-sm text-fg-muted">No grants have been requested.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {grants.slice(0, 10).map((grant) => (
                  <li key={grant.grant_id} className="space-y-1">
                    <div className="flex justify-between gap-2">
                      <span className="font-mono text-xs">{grant.subject_ref}</span>
                      <Badge
                        tone={
                          grant.state === "active"
                            ? "success"
                            : grant.state === "pending"
                              ? "warning"
                              : "neutral"
                        }
                      >
                        {grant.state}
                      </Badge>
                    </div>
                    <p className="text-xs text-fg-muted">
                      {grant.permission} · expires {when(grant.expires_at)} · review due{" "}
                      {when(grant.review_due_at)}
                      {grant.break_glass ? " · BREAK-GLASS" : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </section>
        </div>

        <div className="grid content-start gap-4">
        {/* 5. Monitors */}
        <section aria-labelledby="audit-monitors">
          <Card className="h-fit space-y-3" data-testid="monitors-panel">
            <h2 id="audit-monitors" className="font-medium">
              Monitors
            </h2>
            <p className="text-xs text-fg-muted">
              Who is watching, and since when. A monitor is someone holding an audit
              duty, which is a time-boxed grant rather than a permanent role, so this
              list empties by itself when nobody recertifies.
            </p>
            {refused.grants ? (
              <p className="text-sm text-fg-muted" data-testid="monitors-refused">
                Not for this role: the grant list needs audit:assign. Everything else
                on this page is still live.
              </p>
            ) : monitors.length === 0 ? (
              <p className="text-sm text-fg-muted" data-testid="no-monitors">
                Nobody currently holds an audit duty by grant.
              </p>
            ) : (
              <ul className="space-y-2 text-sm">
                {monitors.map((grant) => (
                  <li key={grant.grant_id} className="flex justify-between gap-2">
                    <span>
                      <span className="font-mono text-xs">{grant.subject_ref}</span>{" "}
                      <span className="text-fg-muted">{grant.permission}</span>
                    </span>
                    <span className="text-xs text-fg-muted">
                      since {when(grant.requested_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <h3 className="pt-2 text-sm font-medium">Alerts someone owns</h3>
            <ul className="space-y-1 text-xs text-fg-muted">
              {openAlerts.filter((alert) => alert.acknowledged_by).length ? (
                openAlerts
                  .filter((alert) => alert.acknowledged_by)
                  .map((alert) => (
                    <li key={alert.alert_id}>
                      {alert.rule_id} · {alert.acknowledged_by} since{" "}
                      {when(alert.acknowledged_at)}
                    </li>
                  ))
              ) : (
                <li>No open alert has been picked up yet.</li>
              )}
            </ul>
          </Card>
        </section>

        {/* 7. Recovery */}
        <section aria-labelledby="audit-recovery">
          <Card className="h-fit space-y-3" data-testid="recovery-panel">
            <div className="flex items-center justify-between">
              <h2 id="audit-recovery" className="font-medium">
                Recovery
              </h2>
              {recovery ? (
                <Badge tone={recovery.backups_configured ? "success" : "danger"}>
                  {recovery.backups_configured ? "key set" : "no backup key"}
                </Badge>
              ) : null}
            </div>
            {recovery ? (
              <>
                <dl className="space-y-2 text-sm">
                  <div>
                    <dt className="text-xs uppercase text-fg-muted">Last backup</dt>
                    <dd className="font-mono text-xs" data-testid="last-backup">
                      {recovery.last_backup
                        ? `${when(String(recovery.last_backup.at))} · ${recovery.last_backup.records} records`
                        : "never taken"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-fg-muted">Last restore</dt>
                    <dd className="font-mono text-xs">
                      {recovery.last_restore
                        ? `${when(String(recovery.last_restore.at))} · lost ${recovery.last_restore.lost_count} record(s)`
                        : "never restored"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-fg-muted">Last segment sealed</dt>
                    <dd className="font-mono text-xs">
                      {recovery.last_segment_sealed
                        ? `${when(String(recovery.last_segment_sealed.at))} · seq ${recovery.last_segment_sealed.from_seq} to ${recovery.last_segment_sealed.to_seq}`
                        : "nothing archived"}
                    </dd>
                  </div>
                </dl>
                {!recovery.backups_configured ? (
                  <Alert tone="danger">
                    CLARITY_AUDIT_BACKUP_KEY is unset, so a backup is refused rather
                    than written in the clear. Nothing is being backed up.
                  </Alert>
                ) : null}
                <p className="text-xs text-fg-muted">
                  Backup and restore are operator actions with step-up, run from the
                  runbook (WT-14), not from this page.
                </p>
              </>
            ) : null}
          </Card>
        </section>
        </div>
      </div>

      {/* 2 and 3. Trail explorer and actor timeline */}
      <section aria-labelledby="audit-trail">
        <Card className="space-y-3" data-testid="trail-explorer">
          <div className="flex items-center justify-between">
            <h2 id="audit-trail" className="font-medium">
              Trail explorer
            </h2>
            <Badge tone="warning">reading this is recorded</Badge>
          </div>
          <p className="text-xs text-fg-muted">
            Hashes and masked detail only, never a payload and never raw personal
            data. Leave the actor blank for everything, or name one for their
            timeline: sign-ins, actions and refusals in one line.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Actor" className="w-40">
              {(control) => (
                <Input
                  {...control}
                  placeholder="sup:ruwan"
                  value={filters.actor_ref}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, actor_ref: event.target.value }))
                  }
                />
              )}
            </Field>
            <Field label="Event type" className="w-44">
              {(control) => (
                <Input
                  {...control}
                  placeholder="action.executed"
                  value={filters.event_type}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, event_type: event.target.value }))
                  }
                />
              )}
            </Field>
            <Field label="Case" className="w-40">
              {(control) => (
                <Input
                  {...control}
                  placeholder="CS-2026-0012"
                  value={filters.case_id}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, case_id: event.target.value }))
                  }
                />
              )}
            </Field>
            <Button loading={busy} onClick={() => void loadTrail()} data-testid="load-trail">
              Read the trail
            </Button>
            {canExport ? (
              <a
                className="inline-flex min-h-10 items-center rounded-md border border-border-strong px-3 text-sm text-fg hover:bg-surface-2"
                href={`/v1/audit/export${filters.case_id ? `?case_id=${filters.case_id}` : ""}`}
                data-testid="export-link"
              >
                Export a verifiable bundle
              </a>
            ) : null}
          </div>
          {canExport ? (
            <p className="text-xs text-fg-muted">
              The bundle is checked with backend/scripts/verify_audit_export.py,
              which imports nothing from Clarity. Scoping it to a case makes it a
              selection, and it says so, so nobody reads a selection as the whole
              trail.
            </p>
          ) : null}
          {trail ? (
            <>
              <p className="text-xs text-fg-muted">
                Up and Down move between records, Home and End jump to the ends, and
                Enter recomputes the hashes of the record that has focus.
              </p>
              <Table
                role="grid"
                caption="Audit trail records matching the current filters"
                scrollLabel="Audit trail"
                className="text-xs"
              >
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>#</TableHeaderCell>
                    <TableHeaderCell>When</TableHeaderCell>
                    <TableHeaderCell>Event</TableHeaderCell>
                    <TableHeaderCell>Actor</TableHeaderCell>
                    <TableHeaderCell>Object</TableHeaderCell>
                    <TableHeaderCell>Detail</TableHeaderCell>
                    <TableHeaderCell>
                      <span className="sr-only">Hash verdict</span>
                    </TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {records.map((record: AuditRecordView, index) => (
                    <TableRow
                      key={record.seq}
                      {...rowProps(index)}
                      className="align-top focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
                    >
                      <TableCell className="font-mono">{record.seq}</TableCell>
                      <TableCell className="font-mono">{when(record.recorded_at)}</TableCell>
                      <TableCell className="font-mono">{record.event_type}</TableCell>
                      <TableCell className="font-mono">{record.actor_ref}</TableCell>
                      <TableCell className="font-mono">{record.object_ref}</TableCell>
                      <TableCell className="max-w-xs truncate text-fg-muted">
                        {JSON.stringify(record.detail)}
                      </TableCell>
                      <TableCell>
                        {verdicts[record.seq] ? (
                          <Badge tone={verdicts[record.seq].intact ? "success" : "danger"}>
                            {verdicts[record.seq].intact ? "hash ok" : "FAILS"}
                          </Badge>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Verify record ${record.seq}`}
                            onClick={() => void verifyRecord(record.seq)}
                          >
                            Verify
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {records.length === 0 ? (
                <p className="py-2 text-sm text-fg-muted" data-testid="no-records">
                  No records match those filters.
                </p>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-fg-muted">
              Not loaded. The trail is read on request, not on a timer, because every
              read is recorded and a polling dashboard would bury the reads that
              matter in the ones that do not.
            </p>
          )}
        </Card>
      </section>

      <Dialog
        open={disposing !== null}
        onClose={() => setDisposing(null)}
        title="Close this alert"
        description={
          disposing
            ? `${disposing.rule_id}: ${disposing.summary}`
            : undefined
        }
        dismissOnBackdrop={false}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDisposing(null)}>
              Cancel
            </Button>
            <Button disabled={busy || !reason.trim()} onClick={() => void dispose()}>
              Close the alert
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-fg-muted">
            A disposition is part of the trail and cannot be edited afterwards. The
            reason is what the next reader has to go on, so it is required rather
            than encouraged.
          </p>
          <Field label="Disposition">
            {(control) => (
              <Select
                {...control}
                value={disposition}
                onChange={(event) => setDisposition(event.target.value)}
              >
                {DISPOSITIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field
            label="Reason (required)"
            hint="What you found, in words the next reader can act on. The API refuses a disposition without one."
          >
            {(control) => (
              <Input
                {...control}
                data-autofocus
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            )}
          </Field>
        </div>
      </Dialog>
    </div>
  );
}
