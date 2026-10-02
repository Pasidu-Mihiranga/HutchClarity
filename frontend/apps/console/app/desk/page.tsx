"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card } from "@clarity/ui";
import type {
  ApproveResult,
  CasePayload,
  DecisionPayload,
  QueueItem,
  ReceiptPayload,
  TimelinePayload,
} from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

const APPROVING_ROLES = ["supervisor", "finance", "agent"] as const;

function money(value?: string | null) {
  return value ? `LKR ${value}` : "—";
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
  const [receipt, setReceipt] = useState<{
    execution: ApproveResult;
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
      if (body.status === "AWAITING_SECOND_APPROVAL" || body.detail) {
        setNote(
          `${body.detail || "Awaiting second approval"} — sign in as a different user (e.g. finance) and approve again.`,
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

  async function seed() {
    setActing(true);
    setError(null);
    try {
      await client.demoSeed();
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Seed failed");
    } finally {
      setActing(false);
    }
  }

  async function reset() {
    setActing(true);
    setError(null);
    try {
      await client.demoReset();
      setCurrentId(null);
      setSummary(null);
      setDecision(null);
      setTimeline(null);
      setReceipt(null);
      setPlanId(null);
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setActing(false);
    }
  }

  async function suspendMerchant() {
    setActing(true);
    setError(null);
    try {
      const result = await client.suspendMerchant({
        merchant_id: "merchant-gamezone",
        reason: "Console VAS ops suspend (simulated)",
        subscriber_msisdn: "0771234567",
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
        <div>
          <h1 className="text-2xl font-semibold">Desk</h1>
          <p className="text-sm text-slate-600">
            Cases that need a person, biggest money at stake first.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => void loadQueue()} disabled={loading || acting || sessionBusy}>
            Refresh
          </Button>
          <Button variant="secondary" onClick={() => void seed()} disabled={acting}>
            Create demo cases
          </Button>
          <Button variant="ghost" onClick={() => void reset()} disabled={acting}>
            Reset demo data
          </Button>
        </div>
      </div>

      {error ? (
        <Card className="border-rose-200 bg-rose-50 text-sm text-rose-900">{error}</Card>
      ) : null}
      {note ? (
        <Card className="border-amber-200 bg-amber-50 text-sm text-amber-950">{note}</Card>
      ) : null}

      {canSuspend ? (
        <Card className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-medium">Merchant suspend</h2>
            <p className="text-sm text-slate-600">
              Block GameZone on Dilani (simulated). Needs step-up MFA.
            </p>
          </div>
          <Button variant="secondary" onClick={() => void suspendMerchant()} disabled={acting}>
            Suspend GameZone
          </Button>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1 max-h-[min(70vh,36rem)] space-y-2 overflow-y-auto">
          <h2 className="text-sm font-medium uppercase text-slate-500">Queue</h2>
          {loading && !queue.length ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : null}
          {!queue.length && !loading ? (
            <p className="text-sm text-slate-500">
              Nothing waiting. Use Create demo cases, or raise one from the
              customer app.
            </p>
          ) : null}
          <ul className="space-y-2">
            {queue.map((item) => (
              <li key={item.case_id}>
                <button
                  type="button"
                  onClick={() => void openCase(item.case_id)}
                  className={`w-full rounded border px-3 py-2 text-left text-sm transition ${
                    currentId === item.case_id
                      ? "border-sky-400 bg-sky-50"
                      : "border-slate-100 hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-mono text-xs text-slate-500">{item.case_no}</p>
                      <p>{(item.cause || "—").replace(/_/g, " ")}</p>
                      <p className="text-xs text-slate-500">{item.msisdn_masked}</p>
                    </div>
                    <div className="text-right">
                      <Badge tone={item.outcome === "STAFF_APPROVAL" ? "warning" : "neutral"}>
                        {item.outcome || item.state}
                      </Badge>
                      <p className="mt-1 text-xs font-medium">{money(item.money_at_stake_lkr)}</p>
                    </div>
                  </div>
                  {item.reason ? (
                    <p className="mt-1 text-xs text-slate-500 line-clamp-2">{item.reason}</p>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="lg:col-span-2 space-y-4">
          <h2 className="text-sm font-medium uppercase text-slate-500">Cockpit</h2>
          {!decision || !summary ? (
            <p className="text-sm text-slate-500">Open a case from the queue.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-lg font-medium">{String(summary.case_no || currentId)}</p>
                  <p className="text-sm text-slate-600">
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
                <h3 className="text-sm font-medium text-slate-500">Ranked cause</h3>
                <p className="text-lg">
                  {decision.cause
                    ? decision.cause.rule_id.replace(/_/g, " ")
                    : "No cause confirmed"}
                </p>
                <p className="text-sm text-slate-600">
                  {decision.cause
                    ? `version ${decision.cause.rule_version || "—"} · confidence ${Math.round((decision.cause.confidence || 0) * 100)}% · ${money(decision.amount_lkr)}`
                    : decision.handoff_reason || ""}
                </p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-slate-500">Policy said</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {(decision.rationale || []).map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </div>

              {timeline ? (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">Evidence</h3>
                  <ul className="mt-1 max-h-40 space-y-1 overflow-auto text-sm">
                    {timeline.events.slice(0, 12).map((ev, i) => (
                      <li key={`${ev.event_type}-${i}`} className="flex gap-2">
                        <span className="font-mono text-xs text-slate-400">
                          {ev.source.replace(/_/g, " ")}
                        </span>
                        <span>
                          {ev.event_type.replace(/_/g, " ")}
                          {ev.amount_lkr ? ` · LKR ${ev.amount_lkr}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {timeline.sources.map((s) => (
                      <Badge key={s.source} tone={s.completeness === "complete" ? "success" : "warning"}>
                        {s.source}: {s.completeness}
                      </Badge>
                    ))}
                  </div>
                </div>
              ) : null}

              {decision.outcome === "STAFF_APPROVAL" ? (
                <div className="space-y-2 border-t border-slate-100 pt-3">
                  <h3 className="font-medium">Approve</h3>
                  <p className="text-xs text-slate-500">
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
                    <p className="text-sm text-amber-800">
                      This session holds no role that may approve. Switch to
                      supervisor or finance (with step-up for high value).
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-slate-600">
                  This case does not need an approval: outcome is{" "}
                  <strong>{decision.outcome.replace(/_/g, " ")}</strong>.
                </p>
              )}
            </>
          )}
        </Card>
      </div>

      {receipt ? (
        <Card className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Trust Receipt issued</h2>
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
                  ? ` — balance ${a.before.balance_lkr} → ${a.after?.balance_lkr}`
                  : ""}
              </li>
            ))}
          </ul>
          <p className="text-sm text-slate-600">
            Authorised by {String(receipt.execution.confirmed_by || "").replace(/_/g, " ")} ·
            returned {money(receipt.verified.corrected_lkr as string | undefined)}
          </p>
        </Card>
      ) : null}
    </div>
  );
}
