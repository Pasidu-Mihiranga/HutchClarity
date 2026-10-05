"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
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
type RuleCandidate = { key: string; value: string; rationale: string };

type StatusFilter = "all" | "hypothesis" | "confirmed" | "rejected";

const STATUS_FILTERS: { id: StatusFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "hypothesis", label: "Hypothesis" },
  { id: "confirmed", label: "Confirmed" },
  { id: "rejected", label: "Rejected" },
];

export default function AutopsyPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const canRead = hasPermission("desk:queue:read");
  const canReview = hasPermission("autopsy:review");
  const canDraft = hasPermission("rule:draft");

  const [data, setData] = useState<AutopsyWorkspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [status, setStatus] = useState<string | null>(null);

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

  const clusters = data?.clusters ?? [];
  const visibleClusters = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return clusters.filter((cluster) => {
      if (statusFilter === "hypothesis" && !cluster.hypothesis) return false;
      if (statusFilter === "confirmed" && cluster.status !== "confirmed") return false;
      if (statusFilter === "rejected" && cluster.status !== "rejected") return false;
      if (!needle) return true;
      const rule = cluster.suggested_rule_id ?? "";
      return (
        cluster.label.toLowerCase().includes(needle) ||
        rule.toLowerCase().includes(needle) ||
        cluster.status_label.toLowerCase().includes(needle)
      );
    });
  }, [clusters, query, statusFilter]);

  // Every action reloads rather than patching local state: the server owns
  // what a cluster's status is, and a page that computed it would be a second
  // place that rule lives.
  async function act(clusterId: string, action: string, run: () => Promise<unknown>) {
    setBusy({ clusterId, action });
    setError(null);
    setStatus(null);
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

  async function propose(clusterId: string, candidate: RuleCandidate) {
    setBusy({ clusterId, action: "propose" });
    setError(null);
    setStatus(null);
    try {
      const created = await client.proposeRuleCandidate(clusterId, candidate);
      setStatus(
        `Draft ${created.change_id} created. Continue its review, approval and activation in Policy Studio.`,
      );
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Rule proposal failed");
    } finally {
      setBusy(null);
    }
  }

  if (!session || !canRead) return <AccessDenied need="desk:queue:read" />;

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
      {status ? <Alert tone="success">{status}</Alert> : null}

      <section aria-labelledby="autopsy-basis">
        <Card>
          <h2 id="autopsy-basis" className="sr-only">
            What this workspace is reading
          </h2>
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase text-fg-muted">Complaints</dt>
              <dd className="text-lg font-medium">{data?.complaint_count ?? 0}</dd>
              <dd className="text-xs text-fg-muted">masked complaints</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-fg-muted">Method</dt>
              <dd className="text-lg font-medium">{data?.clustering_method ?? "loading"}</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-fg-muted">{data?.clustering_disclosure ?? ""}</p>
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

      {clusters.length > 0 ? (
        <section aria-labelledby="autopsy-filter">
          <Card className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="autopsy-filter" className="font-medium">
                Find a cluster
              </h2>
              <span className="text-sm text-fg-muted">
                {visibleClusters.length} of {clusters.length}
              </span>
            </div>
            <label htmlFor="autopsy-search" className="block">
              <span className="sr-only">Search clusters</span>
              <Input
                id="autopsy-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by cluster name or suggested rule"
                className="w-full"
              />
            </label>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
              {STATUS_FILTERS.map((item) => {
                const selected = statusFilter === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setStatusFilter(item.id)}
                    className={`rounded-full px-3 py-1.5 text-sm ${
                      selected
                        ? "bg-surface-2 font-medium text-fg"
                        : "text-fg-muted hover:bg-surface-2"
                    }`}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          </Card>
        </section>
      ) : null}

      <section aria-labelledby="autopsy-clusters">
        <h2 id="autopsy-clusters" className="sr-only">
          Clusters awaiting a verdict
        </h2>
        {clusters.length > 0 && visibleClusters.length === 0 ? (
          <p className="text-sm text-fg-muted">No cluster matches this filter.</p>
        ) : null}
        <ul className="space-y-3">
          {visibleClusters.map((cluster) => (
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
                onCandidate={(candidate) => void propose(cluster.cluster_id, candidate)}
              />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Disclosure({
  title,
  hint,
  children,
}: {
  title: string;
  hint: string;
  children: ReactNode;
}) {
  return (
    <details className="group rounded-lg border border-border">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5 [&::-webkit-details-marker]:hidden">
        <span className="text-xs font-semibold uppercase tracking-wide text-fg-muted">{title}</span>
        <span className="ml-auto flex items-center gap-2">
          <span className="text-xs text-fg-muted">{hint}</span>
          <svg
            viewBox="0 0 20 20"
            className="h-4 w-4 shrink-0 text-fg-muted transition-transform group-open:rotate-180"
            aria-hidden="true"
          >
            <path
              d="M5 8l5 5 5-5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </summary>
      <div className="border-t border-border px-3 py-3">{children}</div>
    </details>
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
  onCandidate,
}: {
  cluster: AutopsyCluster;
  canReview: boolean;
  canDraft: boolean;
  busy: Busy;
  note: string;
  onNote: (value: string) => void;
  onReview: (accept: boolean) => void;
  onSupersede: (accept: boolean) => void;
  onCandidate: (candidate: RuleCandidate) => void;
}) {
  const working = busy?.clusterId === cluster.cluster_id;
  const ruled = !cluster.hypothesis;
  // A reversal needs a reason, and the API refuses one without it. The button
  // is disabled rather than the refusal being a surprise after the click.
  const canSupersede = ruled && note.trim().length > 0;
  const headingId = `cluster-${cluster.cluster_id}`;
  const confirmed = cluster.status === "confirmed";
  const [candidate, setCandidate] = useState<RuleCandidate>({
    key: "",
    value: "",
    rationale: "",
  });

  const complaints = cluster.representative_masked_complaints;
  const languages = Object.entries(cluster.languages);
  const trend = Object.entries(cluster.synthetic_demo_trend);

  return (
    <Card
      role="group"
      aria-labelledby={headingId}
      className="space-y-3"
      data-testid="autopsy-cluster"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 id={headingId} className="font-semibold">
            {cluster.label}
          </h3>
          <span className="mt-0.5 block text-sm text-fg-muted">{cluster.size} complaints</span>
        </div>
        <Badge tone={cluster.hypothesis ? "warning" : "success"}>
          {cluster.hypothesis ? "HYPOTHESIS" : cluster.status.toUpperCase()}
        </Badge>
      </div>
      <dl className="grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase text-fg-muted">Status</dt>
          <dd className="text-sm">{cluster.status_label}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-fg-muted">Suggested mapping</dt>
          <dd className="text-sm text-warning">{cluster.mapping_label}</dd>
        </div>
      </dl>

      <div className="space-y-2">
        <Disclosure title="Representative masked complaints" hint={String(complaints.length)}>
          <ul className="flex flex-col gap-2">
            {complaints.map((text, i) => (
              <li key={i}>
                <blockquote className="border-l-2 border-border pl-2 text-sm">{text}</blockquote>
              </li>
            ))}
          </ul>
        </Disclosure>
        <Disclosure title="Languages:" hint={String(languages.length)}>
          <ul className="flex flex-wrap gap-1.5">
            {languages.map(([language, count]) => (
              <li
                key={language}
                className="rounded-full bg-surface-2 px-2.5 py-1 text-xs text-ink"
              >
                {language} {count}
              </li>
            ))}
          </ul>
        </Disclosure>
        <Disclosure title="Synthetic trend:" hint={String(trend.length)}>
          <ul className="flex flex-wrap gap-1.5">
            {trend.map(([day, count]) => (
              <li key={day} className="rounded-lg bg-surface-2 px-2.5 py-1.5 text-xs">
                <span className="block text-fg-subtle">{day}</span>
                <span className="font-medium text-ink">{count}</span>
              </li>
            ))}
          </ul>
        </Disclosure>
      </div>

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
          {canDraft && confirmed ? (
            <fieldset className="grid gap-2 rounded-lg border border-border bg-surface-2 p-3">
              <legend className="px-1 text-xs font-semibold uppercase text-fg-muted">
                Create governed rule draft
              </legend>
              <p className="text-xs text-fg-muted">
                Use an existing policy key. This creates a draft only; another authorized,
                stepped-up officer must approve and activate it in Policy Studio.
              </p>
              <div className="grid gap-2 sm:grid-cols-3">
                <Field label="Policy key">
                  {(control) => (
                    <Input
                      {...control}
                      value={candidate.key}
                      placeholder="refund.auto_cap_lkr"
                      onChange={(e) => setCandidate({ ...candidate, key: e.target.value })}
                    />
                  )}
                </Field>
                <Field label="Candidate value">
                  {(control) => (
                    <Input
                      {...control}
                      value={candidate.value}
                      onChange={(e) => setCandidate({ ...candidate, value: e.target.value })}
                    />
                  )}
                </Field>
                <Field label="Rationale">
                  {(control) => (
                    <Input
                      {...control}
                      value={candidate.rationale}
                      onChange={(e) =>
                        setCandidate({ ...candidate, rationale: e.target.value })
                      }
                    />
                  )}
                </Field>
              </div>
              <Button
                size="sm"
                disabled={
                  working ||
                  !candidate.key.trim() ||
                  !candidate.value.trim() ||
                  !candidate.rationale.trim()
                }
                onClick={() =>
                  onCandidate({
                    key: candidate.key.trim(),
                    value: candidate.value.trim(),
                    rationale: candidate.rationale.trim(),
                  })
                }
              >
                Send draft to Policy Studio
              </Button>
            </fieldset>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
