"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Badge, Card, EmptyState, Spinner } from "@clarity/ui";
import type { AutopsyWorkspace, ForesightPrediction } from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { PageHeader } from "@/components/PageHeader";
import { useStaffSession } from "@/components/StaffSessionProvider";

/**
 * Insights, with the accessibility pass of E2.
 *
 * The three headline figures are a description list rather than three
 * paragraphs: "Cases, 14" is a term and its value, and a screen reader reads
 * the pair as one thing instead of two unrelated lines. Each panel below is a
 * named section, and the two that load after the first paint announce
 * themselves when they arrive rather than appearing in silence.
 */
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
      <PageHeader
        title="Insights"
        description="Counts from synthetic cases in this process. Autopsy and foresight stay labelled as hypotheses."
      />

      {error ? <Alert tone="danger">{error}</Alert> : null}

      <section aria-labelledby="insights-headline">
        <h2 id="insights-headline" className="sr-only">
          Headline figures
        </h2>
        <dl className="grid gap-3 sm:grid-cols-3">
          <Card className="space-y-2">
            <dt className="text-xs uppercase text-fg-muted">Cases</dt>
            <dd className="text-lg font-medium">{String(ops?.cases ?? " - ")}</dd>
            <dd>
              <Badge tone="neutral">Decided {String(ops?.decided ?? 0)}</Badge>
            </dd>
          </Card>
          <Card className="space-y-2">
            <dt className="text-xs uppercase text-fg-muted">Money at stake</dt>
            <dd className="text-lg font-medium">
              LKR {String(ops?.money_at_stake_lkr ?? "0.00")}
            </dd>
          </Card>
          <Card className="space-y-2">
            <dt className="text-xs uppercase text-fg-muted">Top autopsy cluster</dt>
            <dd className="text-lg font-medium">{clusters[0]?.label || " - pending seed"}</dd>
            <dd>
              <Badge tone="warning">Hypothesis</Badge>
            </dd>
          </Card>
        </dl>
      </section>

      <section aria-labelledby="insights-outcomes">
        <Card>
          <h2 id="insights-outcomes" className="mb-2 font-medium">
            Outcomes
          </h2>
          <ul className="space-y-1 text-sm text-fg">
            {Object.keys(byOutcome).length ? (
              Object.entries(byOutcome).map(([k, v]) => (
                <li key={k}>
                  {k} · {v}
                </li>
              ))
            ) : (
              <li className="text-fg-muted">
                None yet. Cases show up here after they are opened.
              </li>
            )}
          </ul>
        </Card>
      </section>

      <section aria-labelledby="insights-autopsy">
        <Card className="!p-0 overflow-hidden rounded-card border-line bg-surface shadow-card">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 id="insights-autopsy" className="font-medium">
                  Complaint Autopsy
                </h2>
                <Badge tone="warning">Hypothesis</Badge>
              </div>
              <p className="mt-1 max-w-3xl text-xs text-fg-muted">{autopsy?.note ?? ""}</p>
            </div>
            <Link href="/autopsy" className="text-sm font-medium text-primary hover:underline">
              Open the review workspace
            </Link>
          </div>
          <dl className="grid gap-px border-b border-line bg-line sm:grid-cols-3">
            <div className="bg-surface px-4 py-3">
              <dt className="text-xs uppercase text-fg-muted">Clusters</dt>
              <dd className="text-lg font-medium">{clusters.length}</dd>
            </div>
            <div className="bg-surface px-4 py-3">
              <dt className="text-xs uppercase text-fg-muted">Complaints</dt>
              <dd className="text-lg font-medium">{autopsy?.complaint_count ?? 0}</dd>
            </div>
            <div className="bg-surface px-4 py-3">
              <dt className="text-xs uppercase text-fg-muted">Not reviewed</dt>
              <dd className="text-lg font-medium">
                {clusters.filter((c) => c.hypothesis).length}
              </dd>
            </div>
          </dl>
          {clusters.length === 0 ? (
            <p className="px-4 py-6 text-sm text-mute">No clusters yet.</p>
          ) : (
            <div className="max-h-[28rem] overflow-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">
                  Autopsy clusters. Each row is one cluster: its label, how many complaints it holds, whether a person has reviewed it, and any suggested rule.
                </caption>
                <thead className="sticky top-0 bg-surface text-xs font-medium text-fg-subtle">
                  <tr className="border-b border-line">
                    <th scope="col" className="px-4 py-2 font-medium">
                      Cluster
                    </th>
                    <th scope="col" className="px-4 py-2 font-medium">
                      Complaints
                    </th>
                    <th scope="col" className="px-4 py-2 font-medium">
                      Status
                    </th>
                    <th scope="col" className="px-4 py-2 font-medium">
                      Suggested rule
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {clusters.map((c) => (
                    <tr key={c.cluster_id} className="border-b border-line last:border-b-0">
                      <th scope="row" className="px-4 py-3 text-left font-medium text-ink">
                        {c.label}
                      </th>
                      <td className="px-4 py-3 tabular-nums text-ink">{c.size}</td>
                      <td className="px-4 py-3">
                        <Badge tone={c.hypothesis ? "warning" : c.status === "rejected" ? "danger" : "success"}>
                          {c.status_label}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        {c.suggested_rule_id ? (
                          <span className="block font-mono text-xs text-ink">{c.suggested_rule_id}</span>
                        ) : null}
                        <span className="block text-xs text-fg-muted">{c.mapping_label}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      <section aria-labelledby="insights-foresight">
        <Card>
          <h2 id="insights-foresight" className="mb-2 font-medium">
            Foresight
          </h2>
          <p className="mb-2 text-xs text-fg-muted">{foresightNote}</p>
          <div aria-live="polite">
            {predictions === null ? (
              <p className="flex items-center gap-2 text-sm text-fg-muted">
                <Spinner size="sm" label="Loading the latest rehearsal" />
                Loading the latest rehearsal...
              </p>
            ) : predictions.length === 0 ? (
              <EmptyState
                title="Nothing to show"
                description="A rehearsal is a scenario, never a forecast, and none has been stored for this panel to read."
              />
            ) : (
              <ul className="space-y-2 text-sm">
                {predictions.map((p, i) => (
                  <li key={i}>
                    <strong>{p.band}</strong> · {p.segment} · {p.theme} - {p.mitigation}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </section>
    </div>
  );
}
