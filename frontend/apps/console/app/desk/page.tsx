"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Badge, Button, Card, Dialog, Input, Spinner } from "@clarity/ui";
import type {
  ExecutionView,
  CasePayload,
  DecisionPayload,
  QueueItem,
  ReceiptPayload,
  TimelinePayload,
} from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

/**
 * The Desk, with the accessibility pass of E2.
 *
 * Three things the page used to do silently.
 *
 * **The queue is a selection, and now says so.** Each case is a button that
 * swaps the panel beside it; `aria-current` marks which one is open, so a
 * screen reader user can tell where they are in a list of seven without
 * reading the right-hand panel to find out.
 *
 * **Opening a case announces itself.** The case panel is a polite live region,
 * because the click happens on the left and the result appears on the right:
 * without it, nothing tells a non-sighted user that the panel changed.
 *
 * **Blocking a merchant asks first.** It was a single click that suspended a
 * merchant for a subscriber, with the outcome reported afterwards. It is now a
 * dialog that names what will happen, which also gives the keyboard path a
 * focus trap and an Escape route.
 */

const APPROVING_ROLES = ["supervisor", "finance", "agent"] as const;

type QueueFilter = "all" | "needs_action" | "handoff";

function money(value?: string | null) {
  return value ? `LKR ${value}` : " - ";
}

function statusLabel(outcome?: string | null, state?: string) {
  if (outcome === "STAFF_APPROVAL") return "Needs action";
  if (outcome === "HANDOFF") return "Handoff";
  if (outcome) return outcome.replace(/_/g, " ");
  return (state || "Open").replace(/_/g, " ");
}

function statusTone(outcome?: string | null): "warning" | "danger" | "neutral" {
  if (outcome === "STAFF_APPROVAL") return "warning";
  if (outcome === "HANDOFF") return "danger";
  return "neutral";
}

export default function DeskPage() {
  const { client, session, generation, hasPermission, busy: sessionBusy } =
    useStaffSession();
  const canQueue = hasPermission("desk:queue:read");
  const canSuspend = hasPermission("merchant:suspend");

  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [summary, setSummary] = useState<CasePayload | null>(null);
  const [decision, setDecision] = useState<DecisionPayload | null>(null);
  const [timeline, setTimeline] = useState<TimelinePayload | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [confirmSuspend, setConfirmSuspend] = useState(false);
  const [receipt, setReceipt] = useState<{
    execution: ExecutionView;
    verified: ReceiptPayload;
  } | null>(null);
  const [acting, setActing] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<QueueFilter>("all");

  const approvalRoles = useMemo(() => {
    if (!session) return [];
    return APPROVING_ROLES.filter((r) => session.roles.includes(r));
  }, [session]);

  const visibleQueue = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return queue.filter((item) => {
      if (filter === "needs_action" && item.outcome !== "STAFF_APPROVAL") return false;
      if (filter === "handoff" && item.outcome !== "HANDOFF") return false;
      if (!needle) return true;
      const haystack = [
        item.case_no,
        item.case_id,
        item.msisdn_masked,
        item.cause,
        item.reason,
        item.state,
        item.channel,
        item.outcome,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [filter, query, queue]);

  const needsAction = queue.filter((item) => item.outcome === "STAFF_APPROVAL").length;
  const handoffs = queue.filter((item) => item.outcome === "HANDOFF").length;

  const loadQueue = useCallback(async () => {
    if (!canQueue) return;
    setLoading(true);
    setError(null);
    try {
      setQueue(await client.deskQueue());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Queue failed");
    } finally {
      setLoading(false);
    }
  }, [canQueue, client]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue, generation]);

  async function openCase(caseId: string) {
    setError(null);
    setNote(null);
    setReceipt(null);
    setPlanId(null);
    setCurrentId(caseId);
    setActing(true);
    try {
      // Evaluate before reading the timeline: both save the evidence on a
      // case that has none, and in parallel they raced into a 409.
      const dec = await client.evaluateCase(caseId);
      const [sum, tl] = await Promise.all([client.getCase(caseId), client.caseTimeline(caseId)]);
      setSummary(sum);
      setDecision(dec);
      setTimeline(tl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Open failed");
      setSummary(null);
      setDecision(null);
      setTimeline(null);
    } finally {
      setActing(false);
    }
  }

  async function approve(role: string) {
    if (!currentId) return;
    setActing(true);
    setError(null);
    setNote(null);
    try {
      let pid = planId;
      if (!pid) {
        const plan = await client.proposeCase(currentId, {
          created_by: "desk:console",
        });
        pid = plan.plan_id;
        setPlanId(pid);
      }
      const body = await client.approveCase(currentId, {
        plan_id: pid,
        role,
      });
      if ("detail" in body) {
        setNote(
          `${body.detail || "Awaiting second approval"} - sign in as a different user (e.g. finance) and approve again.`,
        );
        return;
      }
      setPlanId(null);
      const receiptId = String(body.receipt_id || "");
      const verified = receiptId
        ? await client.verifyReceipt(receiptId)
        : ({ valid: false } as ReceiptPayload);
      setReceipt({ execution: body, verified });
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setActing(false);
    }
  }

  async function suspendMerchant() {
    setConfirmSuspend(false);
    setActing(true);
    setError(null);
    try {
      const result = await client.suspendMerchant({
        merchant_id: "merchant-gamezone",
        reason: "Console VAS ops suspend (simulated)",
        subscriber_msisdn: "0781234567",
      });
      setNote(
        `Merchant ${result.merchant_id} blocked on Dilani (simulated). Newly blocked: ${String(result.newly_blocked)}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Suspend failed");
    } finally {
      setActing(false);
    }
  }

  if (!session) {
    return <AccessDenied need="desk:queue:read" />;
  }
  if (!canQueue) {
    return <AccessDenied need="desk:queue:read" />;
  }

  const filters: { id: QueueFilter; label: string; count: number }[] = [
    { id: "all", label: "All", count: queue.length },
    { id: "needs_action", label: "Needs action", count: needsAction },
    { id: "handoff", label: "Handoff", count: handoffs },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div className="flex justify-end">
        <label htmlFor="desk-search" className="w-full max-w-md">
          <span className="sr-only">Search cases</span>
          <Input
            id="desk-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by number, case ID, or keyword..."
            className="w-full rounded-full bg-surface"
          />
        </label>
      </div>
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-display text-3xl font-semibold tracking-tight">Cases</h1>
        <span className="rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-medium text-primary">
          {queue.length} waiting
        </span>
        <p className="text-sm text-mute">The subscribers are synthetic.</p>
        <div className="ml-auto">
          <Button
            variant="secondary"
            onClick={() => void loadQueue()}
            loading={loading}
            disabled={acting || sessionBusy}
          >
            Refresh
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter the queue">
        {filters.map((item) => {
          const selected = filter === item.id;
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={selected}
              onClick={() => setFilter(item.id)}
              className={`rounded-full px-3 py-1.5 text-sm ${
                selected ? "bg-surface font-medium text-ink shadow-1" : "text-fg-muted hover:bg-surface"
              }`}
            >
              {item.label}
              {item.id === "needs_action" && item.count > 0 ? (
                <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-warning align-middle" />
              ) : null}
              <span className="sr-only">, {item.count}</span>
            </button>
          );
        })}
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {note ? <Alert tone="warning">{note}</Alert> : null}

      <Dialog
        open={confirmSuspend}
        onClose={() => setConfirmSuspend(false)}
        title="Block GameZone for this subscriber?"
        description="The merchant system is simulated, and the block is recorded against your identity."
        dismissOnBackdrop={false}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmSuspend(false)}>
              Cancel
            </Button>
            <Button variant="danger" data-autofocus onClick={() => void suspendMerchant()}>
              Block the merchant
            </Button>
          </>
        }
      >
        <p>
          GameZone stops being able to charge synthetic subscriber 0781234567.
          Nothing is refunded by this: a block prevents the next charge and
          leaves the ones already made to the case that disputes them.
        </p>
      </Dialog>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-4">
        <section aria-labelledby="desk-queue">
          <Card className="!p-0 overflow-hidden rounded-card border-line bg-surface shadow-card">
            <h2 id="desk-queue" className="sr-only">
              Queue · {visibleQueue.length}
            </h2>
            <div className="hidden border-b border-line px-4 py-3 text-xs font-medium text-fg-subtle sm:grid sm:grid-cols-[minmax(7rem,1fr)_minmax(6rem,0.9fr)_minmax(8rem,1.3fr)_minmax(7rem,0.9fr)_minmax(5rem,0.7fr)] sm:gap-3">
              <span>Case</span>
              <span>Customer</span>
              <span>Issue</span>
              <span>Status</span>
              <span>Amount</span>
            </div>
            {loading && !queue.length ? (
              <p className="flex items-center gap-2 px-4 py-6 text-sm text-mute">
                <Spinner size="sm" label="Loading the queue" />
                Loading…
              </p>
            ) : null}
            {!queue.length && !loading ? (
              <p className="px-4 py-6 text-sm text-mute">
                Nothing is waiting. Load the synthetic queue, or open a case from
                the customer app.
              </p>
            ) : null}
            {queue.length && !visibleQueue.length ? (
              <p className="px-4 py-6 text-sm text-mute">No case matches this search.</p>
            ) : null}
            <ul>
              {visibleQueue.map((item) => {
                const selected = currentId === item.case_id;
                const cause = (item.cause || " - ").replace(/_/g, " ");
                return (
                  <li key={item.case_id} className="border-b border-line last:border-b-0">
                    <button
                      type="button"
                      onClick={() => void openCase(item.case_id)}
                      aria-current={selected ? "true" : undefined}
                      className={`grid w-full gap-1 px-4 py-3 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:grid-cols-[minmax(7rem,1fr)_minmax(6rem,0.9fr)_minmax(8rem,1.3fr)_minmax(7rem,0.9fr)_minmax(5rem,0.7fr)] sm:items-center sm:gap-3 ${
                        selected ? "bg-primary-soft" : "hover:bg-surface-2"
                      }`}
                    >
                      <span className="font-mono text-xs font-medium text-ink">{item.case_no}</span>
                      <span className="text-fg-muted">{item.msisdn_masked}</span>
                      <span className="min-w-0">
                        <span className="block truncate text-ink">{cause}</span>
                        {item.reason ? (
                          <span className="block truncate text-xs text-fg-subtle">{item.reason}</span>
                        ) : null}
                      </span>
                      <span>
                        <Badge tone={statusTone(item.outcome)}>{statusLabel(item.outcome, item.state)}</Badge>
                      </span>
                      <span className="text-xs font-medium text-ink">{money(item.money_at_stake_lkr)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Card>
        </section>

        {canSuspend ? (
          <section aria-labelledby="desk-merchant">
            <Card className="flex flex-wrap items-center justify-between gap-3 rounded-card border-line bg-surface shadow-card">
              <div>
                <h2 id="desk-merchant" className="font-display text-lg font-semibold">
                  Merchant block
                </h2>
                <p className="text-sm text-mute">
                  Block GameZone for synthetic subscriber 0781234567. Step-up is
                  required. The merchant system is simulated.
                </p>
              </div>
              <Button
                variant="secondary"
                onClick={() => setConfirmSuspend(true)}
                disabled={acting}
              >
                Suspend GameZone
              </Button>
            </Card>
          </section>
        ) : null}
        </div>

        <section aria-labelledby="desk-case">
          <Card className="space-y-4 rounded-card border-line bg-surface shadow-card xl:sticky xl:top-5">
            <h2
              id="desk-case"
              className="text-xs font-semibold uppercase tracking-[0.14em] text-mute"
            >
              Case
            </h2>
            {/* The click is on the left and the answer appears here, so this
                announces itself rather than changing in silence. */}
            <div aria-live="polite" aria-busy={acting} className="space-y-4">
              {!decision || !summary ? (
                <p className="text-sm text-mute">Open a case from the queue.</p>
              ) : (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2 border-b border-line pb-4">
                    <div>
                      <p className="font-mono text-xs text-fg-subtle">
                        {String(summary.case_no || currentId)}
                      </p>
                      <p className="font-display text-2xl font-semibold tracking-tight">
                        {decision.cause
                          ? decision.cause.rule_id.replace(/_/g, " ")
                          : "No cause confirmed"}
                      </p>
                      <p className="text-sm text-fg-muted">
                        {String(summary.msisdn_masked || "")} · {String(summary.channel || "")} ·{" "}
                        {String(summary.state || "")}
                      </p>
                    </div>
                    <Badge
                      tone={
                        decision.outcome === "STAFF_APPROVAL"
                          ? "warning"
                          : decision.outcome === "HANDOFF"
                            ? "danger"
                            : "success"
                      }
                    >
                      {decision.outcome.replace(/_/g, " ")}
                    </Badge>
                  </div>

                  <div>
                    <h3 className="text-sm font-medium text-fg-muted">Ranked cause</h3>
                    <p className="text-lg">
                      {decision.cause
                        ? decision.cause.rule_id.replace(/_/g, " ")
                        : "No cause confirmed"}
                    </p>
                    <p className="text-sm text-fg-muted">
                      {decision.cause
                        ? `version ${decision.cause.rule_version || " - "} · confidence ${Math.round((decision.cause.confidence || 0) * 100)}% · ${money(decision.amount_lkr)}`
                        : decision.handoff_reason || ""}
                    </p>
                  </div>

                  <div>
                    <h3 className="text-sm font-medium text-fg-muted">Policy said</h3>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-fg">
                      {(decision.rationale || []).map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </div>

                  {timeline ? (
                    <div>
                      <h3 className="text-sm font-medium text-fg-muted">Evidence</h3>
                      <ul className="mt-1 max-h-40 space-y-1 overflow-auto text-sm">
                        {timeline.events.slice(0, 12).map((ev, i) => (
                          <li key={`${ev.event_type}-${i}`} className="flex gap-2">
                            <span className="font-mono text-xs text-fg-subtle">
                              {ev.source.replace(/_/g, " ")}
                            </span>
                            <span>
                              {ev.event_type.replace(/_/g, " ")}
                              {ev.amount_lkr ? ` · LKR ${ev.amount_lkr}` : ""}
                            </span>
                          </li>
                        ))}
                      </ul>
                      <ul className="mt-2 flex flex-wrap gap-1">
                        {timeline.sources.map((s) => (
                          <li key={s.source}>
                            <Badge tone={s.completeness === "complete" ? "success" : "warning"}>
                              {s.source}: {s.completeness}
                            </Badge>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {decision.outcome === "STAFF_APPROVAL" ? (
                    <div className="space-y-3 rounded-card border border-primary/30 bg-warm p-4">
                      <h3 className="font-display text-lg font-semibold">Approve</h3>
                      <p className="text-xs text-fg-muted">
                        Approval is recorded against the signed-in user. You cannot
                        approve a plan you raised. Four-eyes needs a different person.
                      </p>
                      <ul className="list-disc pl-5 text-sm">
                        {(decision.allowed_actions || []).map((a) => (
                          <li key={a}>{a.replace(/_/g, " ").toLowerCase()}</li>
                        ))}
                      </ul>
                      <div className="flex flex-wrap gap-2">
                        {approvalRoles.map((role, i) => (
                          <Button
                            key={role}
                            variant={i === 0 ? "primary" : "secondary"}
                            disabled={acting}
                            onClick={() => void approve(role)}
                          >
                            Approve as {role}
                          </Button>
                        ))}
                      </div>
                      {!approvalRoles.length ? (
                        <p className="text-sm text-warning">
                          This session holds no role that may approve. Switch to
                          supervisor or finance (with step-up for high value).
                        </p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-sm text-fg-muted">
                      This case does not need an approval: outcome is{" "}
                      <strong>{decision.outcome.replace(/_/g, " ")}</strong>.
                    </p>
                  )}
                </>
              )}
            </div>
          </Card>
        </section>
      </div>

      {receipt ? (
        <section aria-labelledby="desk-receipt">
          <Card className="space-y-2" role="status">
            <div className="flex items-center justify-between">
              <h2 id="desk-receipt" className="font-medium">
                Trust Receipt issued
              </h2>
              <Badge tone={receipt.verified.valid ? "success" : "danger"}>
                {String(receipt.verified.status || (receipt.verified.valid ? "ok" : "bad"))}
              </Badge>
            </div>
            <p className="font-mono text-xs">{String(receipt.verified.receipt_id || "")}</p>
            <ul className="list-disc pl-5 text-sm">
              {(receipt.execution.actions || []).map((a, i) => (
                <li key={i}>
                  {a.type.replace(/_/g, " ").toLowerCase()}
                  {a.before?.balance_lkr
                    ? ` - balance ${a.before.balance_lkr} → ${a.after?.balance_lkr}`
                    : ""}
                </li>
              ))}
            </ul>
            <p className="text-sm text-fg-muted">
              Authorised by {String(receipt.execution.confirmed_by || "").replace(/_/g, " ")} ·
              returned {money(receipt.verified.corrected_lkr as string | undefined)}
            </p>
          </Card>
        </section>
      ) : null}
    </div>
    </div>
  );
}
