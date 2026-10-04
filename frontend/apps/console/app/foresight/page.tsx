"use client";

import { useEffect, useState } from "react";
import { Badge, Card } from "@clarity/ui";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

type Prediction = { theme: string; segment: string; band: string; mitigation: string };
type Comparison = { theme: string; segment: string; baseline: string; swarm: string; agrees: boolean };

export default function ForesightPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const allowed = hasPermission("desk:queue:read");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (allowed) void client.foresight().then(setData).catch((e: unknown) => setError(e instanceof Error ? e.message : "Foresight failed")); }, [allowed, client, generation]);
  if (!session || !allowed) return <AccessDenied need="desk:queue:read" />;
  const predictions = (data?.predictions || []) as Prediction[];
  const comparison = (data?.baseline_vs_swarm || []) as Comparison[];
  const simulation = (data?.simulation || {}) as Record<string, unknown>;
  return <div className="space-y-5">
    <header className="space-y-2"><div className="flex gap-2"><Badge tone="warning">SYNTHETIC SCENARIO</Badge><Badge tone="warning">NOT CALIBRATED</Badge></div><h1 className="text-2xl font-semibold">Foresight rehearsal</h1><p className="font-medium text-amber-900">SCENARIO, NOT CERTAINTY</p><p className="text-sm text-slate-600">{String(data?.note || "")}</p></header>
    {error ? <Card className="text-rose-900">{error}</Card> : null}
    <Card><h2 className="font-semibold">{String(data?.scenario || "Loading scenario")}</h2><p className="text-xs text-slate-500">Seed {String(simulation.seed ?? "-")} · {String(simulation.version ?? "-")} · {String(data?.calibration_status ?? "not_calibrated")}</p></Card>
    <Card><h2 className="mb-2 font-semibold">Predicted themes and preparation</h2><ul className="space-y-2">{predictions.map((p, i) => <li key={i} className="text-sm"><strong>{p.band.toUpperCase()}</strong> · {p.segment} · {p.theme}<br/><span className="text-slate-600">{p.mitigation}</span></li>)}</ul></Card>
    <Card><h2 className="mb-2 font-semibold">Statistical baseline vs persona swarm</h2><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Theme</th><th>Segment</th><th>Baseline</th><th>Swarm</th><th>Result</th></tr></thead><tbody>{comparison.map((c, i) => <tr key={i} className="border-t"><td>{c.theme}</td><td>{c.segment}</td><td>{c.baseline}</td><td>{c.swarm}</td><td>{c.agrees ? "agree" : "differ"}</td></tr>)}</tbody></table></div></Card>
  </div>;
}
