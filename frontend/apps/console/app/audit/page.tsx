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
 */

import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, Input } from "@clarity/ui";
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
import { useStaffSession } from "@/components/StaffSessionProvider";

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
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  async function verifyRecord(seq: number) {
    try {
      const verdict = await client.verifyAuditRecord(seq);
      setVerdicts((current) => ({ ...current, [seq]: verdict }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not verify that record");
    }
  }

  async function move(alertId: string, action: "acknowledge" | "investigate" | "dispose") {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (action === "dispose") {
        const reason = reasons[alertId]?.trim();
        if (!reason) {
          setError("A disposition always needs a reason.");
          return;
        }
        await client.disposeAlert(alertId, {
          disposition: reasons[`${alertId}:disposition`] || "confirmed",
          reason,
        });
      } else if (action === "acknowledge") {
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
      <div>
        <h1 className="text-2xl font-semibold">Audit</h1>
        <p className="text-sm text-slate-600">
          Every panel shows the evidence, not a reassurance. Reading the trail is
          itself recorded, and so is this session.
        </p>
      </div>

      {error ? (
        <Card className="border-rose-200 bg-rose-50 text-sm text-rose-900">{error}</Card>
      ) : null}
      {message ? (
        <Card className="border-emerald-200 bg-emerald-50 text-sm text-emerald-900">
          {message}
        </Card>
      ) : null}

      {/* 1. Chain health */}
      <Card className="space-y-3" data-testid="chain-health">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Chain health</h2>
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
                <dt className="text-xs uppercase text-slate-500">Records</dt>
                <dd className="font-mono" data-testid="chain-length">
                  {health.length}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-slate-500">Checkpoints</dt>
                <dd className="font-mono">{health.checkpoints}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-slate-500">Last checkpoint</dt>
                <dd className="font-mono">{age(health.last_checkpoint_age_seconds)}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-slate-500">Detection last ran</dt>
                <dd className="font-mono">{when(health.detection_last_ran_at)}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-slate-500">Writer lag</dt>
                <dd className="font-mono" data-testid="writer-lag">
                  {health.writer_lag_events} event(s) unpublished
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-slate-500">Archived below</dt>
                <dd className="font-mono">
                  {health.archived_below_seq ? `seq ${health.archived_below_seq}` : "nothing"}
                </dd>
              </div>
            </dl>
            {!health.intact ? (
              <p className="rounded bg-rose-50 p-2 text-sm text-rose-900">
                Broken at seq {health.broken_at}: {health.reason}
                {health.lost_from
                  ? ` Records ${health.lost_from} to ${health.lost_to} are missing.`
                  : ""}
              </p>
            ) : null}
            <p className="text-xs text-slate-500">
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

      <div className="grid gap-4 lg:grid-cols-2">
        {/* 4. Alerts */}
        <Card className="space-y-3" data-testid="alerts-panel">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Alerts</h2>
            <Badge tone={openAlerts.length ? "warning" : "success"}>
              {openAlerts.length} open
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Counted from the trail, never scored by a model. Detection last ran{" "}
            {when(detectionRan)}.
          </p>
          {alerts.length === 0 ? (
            <p className="text-sm text-slate-600" data-testid="no-alerts">
              Nothing has fired. A quiet queue and a stopped detector are not the
              same thing, which is why detection writes a heartbeat either way.
            </p>
          ) : null}
          <ul className="space-y-3">
            {alerts.slice(0, 8).map((alert) => (
              <li
                key={alert.alert_id}
                className="space-y-2 rounded border border-slate-200 p-3 text-sm"
                data-testid="alert-row"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="font-mono text-xs">{alert.rule_id}</span>
                    <p className="text-slate-800">{alert.summary}</p>
                  </div>
                  <Badge tone={BAND_TONE[alert.band] || "neutral"}>{alert.band}</Badge>
                </div>
                <p className="text-xs text-slate-500">
                  {alert.state}
                  {alert.occurrences > 1 ? ` · seen ${alert.occurrences} times` : ""}
                  {alert.acknowledged_by ? ` · acknowledged by ${alert.acknowledged_by}` : ""}
                  {alert.escalated_at ? " · escalated" : ""}
                </p>
                <p className="text-xs text-slate-500">
                  Evidence:{" "}
                  {alert.evidence.length ? (
                    alert.evidence.map((seq: number) => (
                      <button
                        key={seq}
                        type="button"
                        className="mr-1 underline"
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
                        disabled={busy}
                        onClick={() => void move(alert.alert_id, "acknowledge")}
                      >
                        Acknowledge
                      </Button>
                    ) : null}
                    {alert.state === "acknowledged" ? (
                      <Button
                        variant="ghost"
                        disabled={busy}
                        onClick={() => void move(alert.alert_id, "investigate")}
                      >
                        Investigate
                      </Button>
                    ) : null}
                    <select
                      className="rounded border border-slate-300 px-2 py-1 text-xs"
                      value={reasons[`${alert.alert_id}:disposition`] || "confirmed"}
                      onChange={(event) =>
                        setReasons((current) => ({
                          ...current,
                          [`${alert.alert_id}:disposition`]: event.target.value,
                        }))
                      }
                    >
                      {DISPOSITIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <Input
                      className="w-40 text-xs"
                      placeholder="Reason (required)"
                      value={reasons[alert.alert_id] || ""}
                      onChange={(event) =>
                        setReasons((current) => ({
                          ...current,
                          [alert.alert_id]: event.target.value,
                        }))
                      }
                    />
                    <Button
                      variant="ghost"
                      disabled={busy}
                      onClick={() => void move(alert.alert_id, "dispose")}
                    >
                      Dispose
                    </Button>
                  </div>
                ) : null}
                {alert.state === "disposed" ? (
                  <p className="text-xs text-slate-600">
                    {alert.disposition} by {alert.disposed_by}: {alert.disposition_reason}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
          {!canDispose ? (
            <p className="text-xs text-slate-500">
              Read-only: closing an alert needs alert:dispose, which costs its
              holder every money permission.
            </p>
          ) : null}
        </Card>

        {/* 5. Monitors */}
        <Card className="space-y-3" data-testid="monitors-panel">
          <h2 className="font-medium">Monitors</h2>
          <p className="text-xs text-slate-500">
            Who is watching, and since when. A monitor is someone holding an audit
            duty, which is a time-boxed grant rather than a permanent role, so this
            list empties by itself when nobody recertifies.
          </p>
          {refused.grants ? (
            <p className="text-sm text-slate-600" data-testid="monitors-refused">
              Not for this role: the grant list needs audit:assign. Everything else
              on this page is still live.
            </p>
          ) : monitors.length === 0 ? (
            <p className="text-sm text-slate-600" data-testid="no-monitors">
              Nobody currently holds an audit duty by grant.
            </p>
          ) : (
            <ul className="space-y-2 text-sm">
              {monitors.map((grant) => (
                <li key={grant.grant_id} className="flex justify-between gap-2">
                  <span>
                    <span className="font-mono text-xs">{grant.subject_ref}</span>{" "}
                    <span className="text-slate-500">{grant.permission}</span>
                  </span>
                  <span className="text-xs text-slate-500">
                    since {when(grant.requested_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <h3 className="pt-2 text-sm font-medium">Alerts someone owns</h3>
          <ul className="space-y-1 text-xs text-slate-600">
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

        {/* 6. Access */}
        <Card className="space-y-3" data-testid="access-panel">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Access</h2>
            <Badge tone={breakGlass.length ? "warning" : "neutral"}>
              {breakGlass.length} break-glass
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Audit duties are granted, approved by a second person, time-boxed and
            recertified. Holding one removes every money permission.
          </p>
          {refused.grants ? (
            <p className="text-sm text-slate-600" data-testid="access-refused">
              Not for this role: granting, approving and revoking audit duties needs
              audit:assign, which is a role permission and never itself a grant.
            </p>
          ) : grants.length === 0 ? (
            <p className="text-sm text-slate-600">No grants have been requested.</p>
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
                  <p className="text-xs text-slate-500">
                    {grant.permission} · expires {when(grant.expires_at)} · review due{" "}
                    {when(grant.review_due_at)}
                    {grant.break_glass ? " · BREAK-GLASS" : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* 7. Recovery */}
        <Card className="space-y-3" data-testid="recovery-panel">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Recovery</h2>
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
                  <dt className="text-xs uppercase text-slate-500">Last backup</dt>
                  <dd className="font-mono text-xs" data-testid="last-backup">
                    {recovery.last_backup
                      ? `${when(String(recovery.last_backup.at))} · ${recovery.last_backup.records} records`
                      : "never taken"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Last restore</dt>
                  <dd className="font-mono text-xs">
                    {recovery.last_restore
                      ? `${when(String(recovery.last_restore.at))} · lost ${recovery.last_restore.lost_count} record(s)`
                      : "never restored"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Last segment sealed</dt>
                  <dd className="font-mono text-xs">
                    {recovery.last_segment_sealed
                      ? `${when(String(recovery.last_segment_sealed.at))} · seq ${recovery.last_segment_sealed.from_seq} to ${recovery.last_segment_sealed.to_seq}`
                      : "nothing archived"}
                  </dd>
                </div>
              </dl>
              {!recovery.backups_configured ? (
                <p className="rounded bg-rose-50 p-2 text-xs text-rose-900">
                  CLARITY_AUDIT_BACKUP_KEY is unset, so a backup is refused rather
                  than written in the clear. Nothing is being backed up.
                </p>
              ) : null}
              <p className="text-xs text-slate-500">
                Backup and restore are operator actions with step-up, run from the
                runbook (WT-14), not from this page.
              </p>
            </>
          ) : null}
        </Card>
      </div>

      {/* 2 and 3. Trail explorer and actor timeline */}
      <Card className="space-y-3" data-testid="trail-explorer">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Trail explorer</h2>
          <Badge tone="warning">reading this is recorded</Badge>
        </div>
        <p className="text-xs text-slate-500">
          Hashes and masked detail only, never a payload and never raw personal
          data. Leave the actor blank for everything, or name one for their
          timeline: sign-ins, actions and refusals in one line.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs text-slate-600">
            Actor
            <Input
              className="mt-1 w-40"
              placeholder="sup:ruwan"
              value={filters.actor_ref}
              onChange={(event) =>
                setFilters((current) => ({ ...current, actor_ref: event.target.value }))
              }
            />
          </label>
          <label className="text-xs text-slate-600">
            Event type
            <Input
              className="mt-1 w-44"
              placeholder="action.executed"
              value={filters.event_type}
              onChange={(event) =>
                setFilters((current) => ({ ...current, event_type: event.target.value }))
              }
            />
          </label>
          <label className="text-xs text-slate-600">
            Case
            <Input
              className="mt-1 w-40"
              placeholder="CS-2026-0012"
              value={filters.case_id}
              onChange={(event) =>
                setFilters((current) => ({ ...current, case_id: event.target.value }))
              }
            />
          </label>
          <Button disabled={busy} onClick={() => void loadTrail()} data-testid="load-trail">
            Read the trail
          </Button>
          {canExport ? (
            <a
              className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
              href={`/v1/audit/export${filters.case_id ? `?case_id=${filters.case_id}` : ""}`}
              data-testid="export-link"
            >
              Export a verifiable bundle
            </a>
          ) : null}
        </div>
        {canExport ? (
          <p className="text-xs text-slate-500">
            The bundle is checked with backend/scripts/verify_audit_export.py,
            which imports nothing from Clarity. Scoping it to a case makes it a
            selection, and it says so, so nobody reads a selection as the whole
            trail.
          </p>
        ) : null}
        {trail ? (
          <div className="overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500">
                <tr>
                  <th className="py-1">#</th>
                  <th className="py-1">When</th>
                  <th className="py-1">Event</th>
                  <th className="py-1">Actor</th>
                  <th className="py-1">Object</th>
                  <th className="py-1">Detail</th>
                  <th className="py-1" />
                </tr>
              </thead>
              <tbody>
                {trail.records.map((record: AuditRecordView) => (
                  <tr key={record.seq} className="border-t border-slate-100 align-top">
                    <td className="py-1 font-mono">{record.seq}</td>
                    <td className="py-1 font-mono">{when(record.recorded_at)}</td>
                    <td className="py-1 font-mono">{record.event_type}</td>
                    <td className="py-1 font-mono">{record.actor_ref}</td>
                    <td className="py-1 font-mono">{record.object_ref}</td>
                    <td className="max-w-xs truncate py-1 text-slate-600">
                      {JSON.stringify(record.detail)}
                    </td>
                    <td className="py-1">
                      {verdicts[record.seq] ? (
                        <Badge tone={verdicts[record.seq].intact ? "success" : "danger"}>
                          {verdicts[record.seq].intact ? "hash ok" : "FAILS"}
                        </Badge>
                      ) : (
                        <Button
                          variant="ghost"
                          onClick={() => void verifyRecord(record.seq)}
                        >
                          Verify
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {trail.records.length === 0 ? (
              <p className="py-2 text-sm text-slate-600" data-testid="no-records">
                No records match those filters.
              </p>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-slate-600">
            Not loaded. The trail is read on request, not on a timer, because every
            read is recorded and a polling dashboard would bury the reads that
            matter in the ones that do not.
          </p>
        )}
      </Card>
    </div>
  );
}
