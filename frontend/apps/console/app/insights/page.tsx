"use client";

import { useEffect, useState } from "react";
import { Badge, Card } from "@clarity/ui";
import type { AutopsyWorkspace, ForesightPrediction } from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

export default function InsightsPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const allowed = hasPermission("desk:queue:read");
  // Foresight is a separate permission from the desk's. This page is gated on
  // the desk's, so a reader without `foresight:read` sees everything else
  // rather than a 403 that takes the whole page down with it.
  const canReadForesight = hasPermission("foresight:read");
  const [ops, setOps] = useState<Record<string, unknown> | null>(null);
  const [autopsy, setAutopsy] = useState<AutopsyWorkspace | null>(null);
  const [predictions, setPredictions] = useState<ForesightPrediction[] | null>(null);
  const [foresightNote, setForesightNote] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!allowed) return;
    setError(null);
    void (async () => {
      try {
        const [o, a] = await Promise.all([
          client.insightsDashboards(),
          // The reviewer workspace, not `demo/autopsy`: that route was
          // retired in D4 and this one is the same clusters, typed.
          client.autopsyClusters(),
        ]);
        setOps(o);
        setAutopsy(a);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Insights failed");
      }

      if (!canReadForesight) {
        setPredictions([]);
        setForesightNote("Reading rehearsals needs foresight:read.");
        return;
      }
      // The latest stored report, not a scenario built for this request. The
      // demo route used to rehearse on every call and discard the result, so
      // nothing this panel showed could be cited afterwards.
      try {
        const { runs } = await client.foresightRuns();
        const latest = runs.find((run) => run.status === "succeeded");
        if (!latest) {
          setPredictions([]);
          setForesightNote("No rehearsal has been run yet.");
          return;
        }
        const full = await client.foresightRun(latest.run_id);
        setPredictions(full.report?.predictions ?? []);
        setForesightNote(full.report?.basis ?? "");
      } catch (err) {
        setPredictions([]);
        setForesightNote(err instanceof Error ? err.message : "Foresight failed");
      }
    })();
  }, [allowed, canReadForesight, client, generation]);

  if (!session || !allowed) {
    return <AccessDenied need="desk:queue:read" />;
  }

  const byOutcome = (ops?.by_outcome || {}) as Record<string, number>;
  const clusters = autopsy?.clusters ?? [];


  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">
          Anticipate
        </p>
        <h1 className="font-display text-4xl font-semibold tracking-tight">Insights</h1>
        <p className="text-sm text-mute">
          Counts from synthetic cases in this process. Autopsy and foresight
          stay labelled as hypotheses.
        </p>
      </div>

      {error ? (
        <Card className="border-rose-200 bg-rose-50 text-sm text-rose-900">{error}</Card>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="space-y-2">
          <p className="text-xs uppercase text-slate-500">Cases</p>
          <p className="text-lg font-medium">{String(ops?.cases ?? " - ")}</p>
          <Badge tone="neutral">Decided {String(ops?.decided ?? 0)}</Badge>
        </Card>
        <Card className="space-y-2">
          <p className="text-xs uppercase text-slate-500">Money at stake</p>
          <p className="text-lg font-medium">
            LKR {String(ops?.money_at_stake_lkr ?? "0.00")}
          </p>
          <Badge tone="warning">Synthetic records</Badge>
        </Card>
        <Card className="space-y-2">
          <p className="text-xs uppercase text-slate-500">Top autopsy cluster</p>
          <p className="text-lg font-medium">
            {clusters[0]?.label || " - pending seed"}
          </p>
          <Badge tone="warning">Hypothesis</Badge>
        </Card>
      </div>

      <Card>
        <h2 className="mb-2 font-medium">Outcomes</h2>
        <ul className="space-y-1 text-sm text-slate-700">
          {Object.keys(byOutcome).length
            ? Object.entries(byOutcome).map(([k, v]) => (
                <li key={k}>
                  {k} · {v}
                </li>
              ))
            : (
              <li className="text-slate-500">None yet. Cases show up here after they are opened.</li>
            )}
        </ul>
      </Card>

      <Card>
        <h2 className="mb-2 font-medium">Complaint Autopsy</h2>
        <p className="mb-2 text-xs text-slate-500">{autopsy?.note ?? ""}</p>
        <ul className="space-y-1 text-sm">
          {clusters.map((c) => (
            <li key={c.cluster_id}>
              {c.label} · {c.size} · {c.status}
              {c.suggested_rule_id ? ` · ${c.suggested_rule_id}` : ""}
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <h2 className="mb-2 font-medium">Foresight</h2>
        <p className="mb-2 text-xs text-slate-500">{foresightNote}</p>
        {predictions === null ? (
          <p className="text-sm text-slate-600">Loading the latest rehearsal...</p>
        ) : predictions.length === 0 ? (
          <p className="text-sm text-slate-600">
            Nothing to show. A rehearsal is a scenario, never a forecast, and none has been
            stored for this panel to read.
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            {predictions.map((p, i) => (
              <li key={i}>
                <strong>{p.band}</strong> · {p.segment} · {p.theme} - {p.mitigation}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
