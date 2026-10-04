"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Badge, Button, Card, Dialog, Spinner } from "@clarity/ui";
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

function money(value?: string | null) {
  return value ? `LKR ${value}` : " - ";
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

  const approvalRoles = useMemo(() => {
    if (!session) return [];
    return APPROVING_ROLES.filter((r) => session.roles.includes(r));
  }, [session]);

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
      const [sum, dec, tl] = await Promise.all([
        client.getCase(caseId),
        client.evaluateCase(caseId),
        client.caseTimeline(caseId),
      ]);
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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-xl space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">
            Resolve and support
          </p>
          <h1 className="font-display text-4xl font-semibold tracking-tight">Desk</h1>
          <p className="text-sm leading-6 text-mute">
            Cases that need a person, largest amount first. The subscribers are
            synthetic.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
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

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {note ? <Alert tone="warning">{note}</Alert> : null}

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

      <div className="grid gap-4 lg:grid-cols-3">
        <section aria-labelledby="desk-queue" className="lg:col-span-1">
          <Card className="max-h-[min(70vh,36rem)] space-y-2 overflow-y-auto rounded-card border-line bg-surface shadow-card">
            <h2
              id="desk-queue"
              className="text-xs font-semibold uppercase tracking-[0.14em] text-mute"
            >
              Queue · {queue.length}
            </h2>
            {loading && !queue.length ? (
              <p className="flex items-center gap-2 text-sm text-mute">
                <Spinner size="sm" label="Loading the queue" />
                Loading…
              </p>
            ) : null}
            {!queue.length && !loading ? (
              <p className="text-sm text-mute">
                Nothing is waiting. Load the synthetic queue, or open a case from
                the customer app.
              </p>
            ) : null}
            <ul className="space-y-2">
              {queue.map((item) => (
                <li key={item.case_id}>
                  <button
                    type="button"
                    onClick={() => void openCase(item.case_id)}
                    aria-current={currentId === item.case_id ? "true" : undefined}
                    className={`w-full rounded-2xl border px-3 py-3 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 ${
                      currentId === item.case_id
                        ? "border-accent bg-warm"
                        : "border-line hover:border-primary"
                    }`}
                  >
                    <span className="flex items-start justify-between gap-2">
                      <span>
                        <span className="block font-mono text-xs text-mute">{item.case_no}</span>
                        <span className="block">{(item.cause || " - ").replace(/_/g, " ")}</span>
                        <span className="block text-xs text-mute">{item.msisdn_masked}</span>
                      </span>
                      <span className="text-right">
                        <Badge tone={item.outcome === "STAFF_APPROVAL" ? "warning" : "neutral"}>
                          {item.outcome || item.state}
                        </Badge>
                        <span className="mt-1 block text-xs font-medium">
                          {money(item.money_at_stake_lkr)}
                        </span>
                      </span>
                    </span>
                    {item.reason ? (
                      <span className="mt-1 block text-xs text-mute line-clamp-2">
                        {item.reason}
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </section>

        <section aria-labelledby="desk-case" className="lg:col-span-2">
          <Card className="space-y-4 rounded-card border-line bg-surface shadow-card">
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
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-display text-2xl font-semibold">
                        {String(summary.case_no || currentId)}
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
                            <span className="font-mono text-xs text-fg-muted">
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
  );
}
