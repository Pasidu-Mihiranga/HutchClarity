"use client";

import { useEffect, useState } from "react";
import { Badge, Card } from "@clarity/ui";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

type Cluster = { cluster_id: string; label: string; size: number; status_label: string; mapping_label: string; languages: Record<string, number>; representative_masked_complaints: string[]; synthetic_demo_trend: Record<string, number> };

export default function AutopsyPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const allowed = hasPermission("desk:queue:read");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (allowed) void client.autopsy().then(setData).catch((e: unknown) => setError(e instanceof Error ? e.message : "Autopsy failed")); }, [allowed, client, generation]);
  if (!session || !allowed) return <AccessDenied need="desk:queue:read" />;
  const clusters = (data?.clusters || []) as Cluster[];
  return <div className="space-y-5">
    <header><Badge tone="warning">SYNTHETIC DATA</Badge><h1 className="mt-2 text-2xl font-semibold">Complaint Autopsy</h1><p className="text-sm text-slate-600">Clusters are hypotheses until reviewed. Suggested mappings do not activate rules.</p></header>
    {error ? <Card className="text-rose-900">{error}</Card> : null}
    <Card><p className="text-sm"><strong>{String(data?.complaint_count ?? 0)}</strong> masked complaints · {String(data?.clustering_method ?? "loading")}</p><p className="text-xs text-slate-500">{String(data?.clustering_disclosure ?? "")}</p></Card>
    <div className="space-y-3">{clusters.map((cluster) => <Card key={cluster.cluster_id} className="space-y-2">
      <div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold">{cluster.label}</h2><Badge tone="warning">HYPOTHESIS</Badge><span className="text-sm">{cluster.size} complaints</span></div>
      <p className="text-sm">{cluster.status_label}</p><p className="text-xs text-amber-800">{cluster.mapping_label}</p>
      <p className="text-xs">Languages: {Object.entries(cluster.languages).map(([k,v]) => `${k} ${v}`).join(" · ")}</p>
      <div><h3 className="text-xs font-semibold uppercase text-slate-500">Representative masked complaints</h3>{cluster.representative_masked_complaints.map((text, i) => <blockquote key={i} className="mt-1 border-l-2 pl-2 text-sm">{text}</blockquote>)}</div>
      <p className="text-xs text-slate-500">Synthetic trend: {Object.entries(cluster.synthetic_demo_trend).map(([k,v]) => `${k}: ${v}`).join(" · ")}</p>
    </Card>)}</div>
  </div>;
}
