"use client";

import { useEffect, useState } from "react";
import { Alert, Badge, Card, EmptyState, Spinner } from "@clarity/ui";
import type { AutopsyWorkspace, ForesightPrediction } from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
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
            <dd>
              <Badge tone="warning">Synthetic records</Badge>
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
        <Card>
          <h2 id="insights-autopsy" className="mb-2 font-medium">
            Complaint Autopsy
          </h2>
          <p className="mb-2 text-xs text-fg-muted">{autopsy?.note ?? ""}</p>
          <ul className="space-y-1 text-sm">
            {clusters.map((c) => (
              <li key={c.cluster_id}>
                {c.label} · {c.size} · {c.status}
                {c.suggested_rule_id ? ` · ${c.suggested_rule_id}` : ""}
              </li>
            ))}
          </ul>
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
