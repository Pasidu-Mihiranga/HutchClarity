"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, EmptyState, Field, Input } from "@clarity/ui";
import type { AutopsyCluster, AutopsyWorkspace } from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

/**
 * The Complaint Autopsy reviewer workspace (D1).
 *
 * This page used to be a read-only view of `/v1/demo/autopsy`: a reviewer
 * could look at a cluster and had no way to rule on it, because the backend
 * had no route to rule through. It now reads `/v1/autopsy/clusters` and
 * carries the three actions that make the review step mean anything.
 *
 * **Seeing and ruling are different permissions.** The desk reads with
 * `desk:queue:read`; the verdict buttons appear only for `autopsy:review`,
 * and proposing a policy change needs `rule:draft` on top of that. An agent
 * can see what the pattern engine thinks and cannot decide it is right.
 *
 * No business logic lives here (UI02). The page sends a verdict and renders
 * what comes back; it never computes a status, never decides whether a
 * cluster is a hypothesis, and never constructs a rule.
 *
 * E2 added the structure: the clusters are a list so their number is
 * announced, each one is a named section, the verdict buttons carry the
 * cluster in their accessible name (eight pairs of "Confirm" and "Reject" on
 * one page are otherwise indistinguishable), and the note is a real labelled
 * field rather than an `aria-label` standing in for one.
 */

type Busy = { clusterId: string; action: string } | null;

export default function AutopsyPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const canRead = hasPermission("desk:queue:read");
  const canReview = hasPermission("autopsy:review");
  const canDraft = hasPermission("rule:draft");

  const [data, setData] = useState<AutopsyWorkspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    if (!canRead) return;
    void client
      .autopsyClusters()
      .then((found) => {
        setData(found);
        setError(null);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Autopsy failed"));
  }, [canRead, client]);

  useEffect(load, [load, generation]);

  // Every action reloads rather than patching local state: the server owns
  // what a cluster's status is, and a page that computed it would be a second
  // place that rule lives.
  async function act(clusterId: string, action: string, run: () => Promise<unknown>) {
    setBusy({ clusterId, action });
    setError(null);
    try {
      await run();
      load();
      setNotes((current) => ({ ...current, [clusterId]: "" }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `${action} failed`);
    } finally {
      setBusy(null);
    }
  }

  if (!session || !canRead) return <AccessDenied need="desk:queue:read" />;

  const clusters = data?.clusters ?? [];

  return (
    <div className="space-y-5">
      <div>
        <Badge tone="warning">SYNTHETIC DATA</Badge>
        <h1 className="mt-2 text-2xl font-semibold">Complaint Autopsy</h1>
        <p className="text-sm text-fg-muted">
          Clusters are hypotheses until a person reviews them. A suggested mapping never
          activates a rule.
        </p>
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}

      <section aria-labelledby="autopsy-basis">
        <Card>
          <h2 id="autopsy-basis" className="sr-only">
            What this workspace is reading
          </h2>
          <p className="text-sm">
            <strong>{data?.complaint_count ?? 0}</strong> masked complaints ·{" "}
            {data?.clustering_method ?? "loading"}
          </p>
          <p className="text-xs text-fg-muted">{data?.clustering_disclosure ?? ""}</p>
          {!canReview ? (
            <p className="mt-2 text-xs text-warning">
              You can read this workspace. Ruling on a cluster needs{" "}
              <code>autopsy:review</code>.
            </p>
          ) : null}
        </Card>
      </section>

      {data && clusters.length === 0 ? (
        <Card>
          <EmptyState
            title="No clusters yet"
            description="They appear once complaints have been ingested and clustered."
          />
        </Card>
      ) : null}

      <section aria-labelledby="autopsy-clusters">
        <h2 id="autopsy-clusters" className="sr-only">
          Clusters awaiting a verdict
        </h2>
        <ul className="space-y-3">
          {clusters.map((cluster) => (
            <li key={cluster.cluster_id}>
              <ClusterCard
                cluster={cluster}
                canReview={canReview}
                canDraft={canDraft}
                busy={busy}
                note={notes[cluster.cluster_id] ?? ""}
                onNote={(value) =>
                  setNotes((current) => ({ ...current, [cluster.cluster_id]: value }))
                }
                onReview={(accept) =>
                  act(cluster.cluster_id, "review", () =>
                    client.reviewCluster(cluster.cluster_id, {
                      accept,
                      note: notes[cluster.cluster_id] ?? "",
                    }),
                  )
                }
                onSupersede={(accept) =>
                  act(cluster.cluster_id, "supersede", () =>
                    client.supersedeClusterReview(cluster.cluster_id, {
                      accept,
                      note: notes[cluster.cluster_id] ?? "",
                    }),
                  )
                }
              />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function ClusterCard({
  cluster,
  canReview,
  canDraft,
  busy,
  note,
  onNote,
  onReview,
  onSupersede,
}: {
  cluster: AutopsyCluster;
  canReview: boolean;
  canDraft: boolean;
  busy: Busy;
  note: string;
  onNote: (value: string) => void;
  onReview: (accept: boolean) => void;
  onSupersede: (accept: boolean) => void;
}) {
  const working = busy?.clusterId === cluster.cluster_id;
  const ruled = !cluster.hypothesis;
  // A reversal needs a reason, and the API refuses one without it. The button
  // is disabled rather than the refusal being a surprise after the click.
  const canSupersede = ruled && note.trim().length > 0;
  const headingId = `cluster-${cluster.cluster_id}`;

  return (
    <Card
      role="group"
      aria-labelledby={headingId}
      className="space-y-2"
      data-testid="autopsy-cluster"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 id={headingId} className="font-semibold">
          {cluster.label}
        </h3>
        <Badge tone={cluster.hypothesis ? "warning" : "success"}>
          {cluster.hypothesis ? "HYPOTHESIS" : cluster.status.toUpperCase()}
        </Badge>
        <span className="text-sm">{cluster.size} complaints</span>
      </div>
      <p className="text-sm">{cluster.status_label}</p>
      <p className="text-xs text-warning">{cluster.mapping_label}</p>
      <p className="text-xs">
        Languages:{" "}
        {Object.entries(cluster.languages)
          .map(([k, v]) => `${k} ${v}`)
          .join(" · ")}
      </p>

      <div>
        <h4 className="text-xs font-semibold uppercase text-fg-muted">
          Representative masked complaints
        </h4>
        {cluster.representative_masked_complaints.map((text, i) => (
          <blockquote key={i} className="mt-1 border-l-2 border-border pl-2 text-sm">
            {text}
          </blockquote>
        ))}
      </div>

      <p className="text-xs text-fg-muted">
        Synthetic trend:{" "}
        {Object.entries(cluster.synthetic_demo_trend)
          .map(([k, v]) => `${k}: ${v}`)
          .join(" · ")}
      </p>

      {cluster.reviews?.length ? (
        <div className="rounded-lg bg-surface-2 p-2">
          <h4 className="text-xs font-semibold uppercase text-fg-muted">Verdicts</h4>
          {/* Every verdict, including the ones that were superseded. A
              reversal that hid what it reversed would leave the trail saying
              the cluster was always judged this way. */}
          <ul className="mt-1 space-y-1 text-xs text-fg">
            {cluster.reviews.map((review, i) => (
              <li key={i}>
                <strong>{review.accepted ? "confirmed" : "rejected"}</strong> by{" "}
                {review.reviewer} · {new Date(review.at).toLocaleString()}
                {review.note ? ` · ${review.note}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {canReview ? (
        <div className="space-y-2 border-t border-border pt-2">
          <Field
            label={ruled ? "Reason for changing this verdict (required)" : "Note (optional)"}
          >
            {(control) => (
              <Input {...control} value={note} onChange={(e) => onNote(e.target.value)} />
            )}
          </Field>
          <div className="flex flex-wrap items-center gap-2">
            {ruled ? (
              <>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={working || !canSupersede}
                  aria-label={`Change ${cluster.label} to confirmed`}
                  onClick={() => onSupersede(true)}
                >
                  Change to confirmed
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={working || !canSupersede}
                  aria-label={`Change ${cluster.label} to rejected`}
                  onClick={() => onSupersede(false)}
                >
                  Change to rejected
                </Button>
                {!canSupersede ? (
                  <span className="self-center text-xs text-fg-muted">
                    Changing a verdict needs a reason.
                  </span>
                ) : null}
              </>
            ) : (
              <>
                <Button
                  size="sm"
                  disabled={working}
                  aria-label={`Confirm ${cluster.label}`}
                  onClick={() => onReview(true)}
                >
                  Confirm
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  disabled={working}
                  aria-label={`Reject ${cluster.label}`}
                  onClick={() => onReview(false)}
                >
                  Reject
                </Button>
              </>
            )}
          </div>
          {canDraft && ruled ? (
            <p className="text-xs text-fg-muted">
              A confirmed cluster can be proposed as a policy change from Policy Studio. It
              becomes a draft for somebody else to approve, never a live rule.
            </p>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
