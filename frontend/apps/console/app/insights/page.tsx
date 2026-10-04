"use client";

import { useEffect, useState } from "react";
import { Badge, Card } from "@clarity/ui";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

export default function InsightsPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const allowed = hasPermission("desk:queue:read");
  const [ops, setOps] = useState<Record<string, unknown> | null>(null);
  const [autopsy, setAutopsy] = useState<Record<string, unknown> | null>(null);
  const [foresight, setForesight] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!allowed) return;
    setError(null);
    void (async () => {
      try {
        const [o, a, f] = await Promise.all([
          client.opsSummary(),
          client.autopsy(),
          client.foresight(),
        ]);
        setOps(o);
        setAutopsy(a);
        setForesight(f);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Insights failed");
      }
    })();
  }, [allowed, client, generation]);

  if (!session || !allowed) {
    return <AccessDenied need="desk:queue:read" />;
  }

  const byOutcome = (ops?.by_outcome || {}) as Record<string, number>;
  const clusters = (autopsy?.clusters || []) as Array<{
    label: string;
    size: number;
    status: string;
    suggested_rule_id?: string;
  }>;
  const predictions = (foresight?.predictions || []) as Array<{
    band: string;
    segment: string;
    theme: string;
    mitigation: string;
  }>;

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
        <p className="mb-2 text-xs text-slate-500">{String(autopsy?.note || "")}</p>
        <ul className="space-y-1 text-sm">
          {clusters.map((c) => (
            <li key={c.label}>
              {c.label} · {c.size} · {c.status}
              {c.suggested_rule_id ? ` · ${c.suggested_rule_id}` : ""}
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <h2 className="mb-2 font-medium">Foresight</h2>
        <p className="mb-2 text-sm text-slate-600">
          {String(foresight?.scenario || "")}. {String(foresight?.note || "")}
        </p>
        <ul className="space-y-2 text-sm">
          {predictions.map((p, i) => (
            <li key={i}>
              <strong>{p.band}</strong> · {p.segment} · {p.theme} - {p.mitigation}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
