"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Select,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@clarity/ui";
import type {
  ForesightCalibration,
  ForesightRun,
  ForesightSpike,
  ScenarioView,
} from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

/**
 * The Foresight rehearsal workspace, on the real API.
 *
 * This page read `GET /v1/demo/foresight`, a route that built a scenario, ran
 * it and threw the result away on every request. Nothing it showed could be
 * cited later, because nothing it showed was stored. It also hard-coded the
 * "NOT CALIBRATED" badge, which happened to be true and was not something the
 * page had checked.
 *
 * Workstream C gave foresight persistence, an API, permissions and a
 * calibration gate, so the page now reads scenarios, asks for runs and renders
 * stored reports. Every claim on screen comes from the API, including whether
 * the model is calibrated.
 *
 * **Reading and rehearsing are different permissions.** `foresight:read` shows
 * the workspace; `foresight:run` asks for a rehearsal. Neither carries
 * `foresight:outcome:record`, deliberately: the person who wants the
 * calibration gate open must not be the person recording the evidence that
 * opens it, so this page cannot record an outcome at all.
 */

/** Band to tone. Unknown bands render neutral rather than guessing. */
const BAND_TONE: Record<string, "danger" | "warning" | "neutral"> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

export default function ForesightPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const canRead = hasPermission("foresight:read");
  const canRun = hasPermission("foresight:run");

  const [scenarios, setScenarios] = useState<ScenarioView[] | null>(null);
  const [runs, setRuns] = useState<ForesightRun[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [opened, setOpened] = useState<ForesightRun | null>(null);
  const [calibration, setCalibration] = useState<ForesightCalibration | null>(null);
  const [spikes, setSpikes] = useState<ForesightSpike[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!canRead) return;
    void (async () => {
      try {
        const [s, r, k] = await Promise.all([
          client.foresightScenarios(),
          client.foresightRuns(),
          client.foresightSpikes(),
        ]);
        setScenarios(s.scenarios);
        setRuns(r.runs);
        setSpikes(k.spikes);
        setSelected((current) => current || (s.scenarios[0]?.version_id ?? ""));
        setError(null);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Foresight failed");
      }
      // A 404 here means no backtest has run, which is the normal state and
      // not an error worth a red banner.
      try {
        setCalibration(await client.foresightCalibration());
      } catch {
        setCalibration(null);
      }
    })();
  }, [canRead, client]);

  useEffect(load, [load, generation]);

  async function rehearse() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      // The route requires an Idempotency-Key (I8). A fresh one per click is
      // what makes this a new rehearsal; replaying an old key would return the
      // original run, which is the point of the header.
      const key = `foresight-${selected}-${Date.now()}`;
      const run = await client.requestForesightRun(selected, key);
      const full = await client.foresightRun(run.run_id);
      setOpened(full);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not request a rehearsal");
    } finally {
      setBusy(false);
    }
  }

  async function open(runId: string) {
    setError(null);
    try {
      setOpened(await client.foresightRun(runId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not read that run");
    }
  }

  if (!session || !canRead) return <AccessDenied need="foresight:read" />;

  const report = opened?.report ?? null;

  return (
    <div className="space-y-5">
      <header className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <Badge tone="warning">SYNTHETIC SCENARIO</Badge>
          {/* Read from the API, not asserted by the page. A badge that says
              "calibrated" because somebody typed it is worse than none. */}
          {calibration ? (
            <Badge tone={calibration.calibrated ? "success" : "warning"}>
              {calibration.status.replace(/_/g, " ").toUpperCase()}
            </Badge>
          ) : (
            <Badge tone="warning">NOT CALIBRATED</Badge>
          )}
        </div>
        <h1 className="text-2xl font-semibold">Foresight rehearsal</h1>
        <p className="font-medium text-amber-900">SCENARIO, NOT CERTAINTY</p>
        <p className="text-sm text-slate-600">
          A rehearsal predicts which themes and segments a change is likely to stir up. It
          is a scenario, never a forecast of what will happen, and no launch decision rests
          on it until the model has been backtested against real launches.
        </p>
      </header>

      {error ? <Alert tone="danger">{error}</Alert> : null}

      <Card className="space-y-3">
        <h2 className="font-semibold">Rehearse a scenario</h2>
        {scenarios === null ? (
          <Spinner />
        ) : scenarios.length === 0 ? (
          <EmptyState
            title="No scenarios yet"
            description="A scenario is drafted with foresight:scenario:draft before it can be rehearsed."
          />
        ) : (
          <>
            <Select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              aria-label="Scenario version to rehearse"
            >
              {scenarios.map((s) => (
                <option key={s.version_id} value={s.version_id}>
                  {s.name} · v{s.version} · {s.change_type} · effective{" "}
                  {s.effective_date}
                </option>
              ))}
            </Select>
            {canRun ? (
              <Button disabled={busy || !selected} onClick={() => void rehearse()}>
                {busy ? "Rehearsing..." : "Rehearse"}
              </Button>
            ) : (
              <p className="text-xs text-slate-500">
                Asking for a rehearsal needs <code>foresight:run</code>.
              </p>
            )}
          </>
        )}
      </Card>

      {report ? (
        <Card className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-semibold">{report.scenario}</h2>
            <Badge tone={report.decision_ready ? "success" : "warning"}>
              {report.decision_ready ? "DECISION READY" : "NOT DECISION READY"}
            </Badge>
            {opened?.replayed ? <Badge tone="info">REPLAYED</Badge> : null}
          </div>
          {/* The basis and the caveats are the honest part of the report, so
              they sit with the numbers rather than under a disclosure. */}
          <p className="text-xs text-slate-500">{report.basis}</p>
          {report.caveats.length ? (
            <ul className="list-disc space-y-1 pl-5 text-xs text-amber-900">
              {report.caveats.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          ) : null}

          {report.predictions.length === 0 ? (
            <EmptyState
              title="No predictions"
              description="The catalogue produced nothing for this change type, which is a configuration gap rather than a finding of no risk."
            />
          ) : (
            <Table
              caption="Predicted themes and segments for this rehearsal, by band"
              showCaption={false}
            >
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Band</TableHeaderCell>
                  <TableHeaderCell>Segment</TableHeaderCell>
                  <TableHeaderCell>Theme</TableHeaderCell>
                  <TableHeaderCell>Score</TableHeaderCell>
                  <TableHeaderCell>Suggested preparation</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {report.predictions.map((p, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Badge tone={BAND_TONE[p.band] ?? "neutral"}>
                        {p.band.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell>{p.segment}</TableCell>
                    <TableCell>{p.theme}</TableCell>
                    <TableCell>{p.relative_score}</TableCell>
                    <TableCell>{p.mitigation}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      ) : null}

      <Card className="space-y-2">
        <h2 className="font-semibold">Runs</h2>
        {runs.length === 0 ? (
          <p className="text-sm text-slate-600">
            No rehearsals yet. A run is stored, so a report can be cited later.
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {runs.map((run) => (
              <li key={run.run_id} className="flex flex-wrap items-center gap-2">
                <Badge tone={run.status === "succeeded" ? "success" : "warning"}>
                  {run.status.toUpperCase()}
                </Badge>
                <button
                  type="button"
                  onClick={() => void open(run.run_id)}
                  className="font-mono text-xs underline"
                >
                  {run.run_id}
                </button>
                <span className="text-xs text-slate-500">
                  by {run.requested_by} · {new Date(run.requested_at).toLocaleString()}
                </span>
                {run.failure ? (
                  <span className="text-xs text-rose-800">{run.failure}</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="space-y-2">
        <h2 className="font-semibold">Calibration</h2>
        {calibration === null ? (
          <p className="text-sm text-slate-600">
            No backtest has been run, so the model is not calibrated and no launch decision
            should rest on a rehearsal.
          </p>
        ) : (
          <>
            <p className="text-sm">{calibration.summary}</p>
            <p className="text-xs text-slate-500">
              {calibration.real_launches} real of {calibration.launches} launches ·{" "}
              {calibration.compared} compared · band error{" "}
              {calibration.mean_absolute_band_error ?? "not computable"} · theme recall{" "}
              {calibration.theme_recall ?? "not computable"} · rank correlation{" "}
              {calibration.segment_rank_correlation ?? "not computable"}
            </p>
            <p className="text-xs text-slate-500">{calibration.basis}</p>
          </>
        )}
      </Card>

      <Card className="space-y-2">
        <h2 className="font-semibold">Early-warning spikes</h2>
        {spikes.length === 0 ? (
          <p className="text-sm text-slate-600">
            Nothing above the baseline. The radar counts complaints per channel and never
            reads what anybody wrote.
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {spikes.map((spike) => (
              <li key={spike.spike_id}>
                <strong>{spike.scope_ref}</strong> · {spike.observed} observed against a{" "}
                {spike.baseline} baseline
                {spike.ratio ? ` · ${spike.ratio}x` : ""} ·{" "}
                {new Date(spike.detected_at).toLocaleString()}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
