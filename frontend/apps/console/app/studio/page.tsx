"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, Input } from "@clarity/ui";
import type { PolicyChangeView } from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

/**
 * Policy Studio, on the governance lifecycle (D3).
 *
 * This page used to write a draft to `sessionStorage` and download a JSON
 * blob, under the status line "Publish is not connected yet." The backend it
 * needed had existed since M-GOV: seven routes under `/v1/admin/policy/changes`
 * doing draft, review, approve, schedule, activate and reversal, with the
 * change class derived from the artefact's own tags and maker-checker enforced
 * server side. Nothing a policy author did here ever reached any of it.
 *
 * So this is wiring, and the page deliberately holds no lifecycle logic of its
 * own. It does not decide how many approvals a change needs, whether this
 * person may approve it, or which state follows which: it renders what the API
 * returns and offers the transitions the API will consider. Those are all
 * money-path rules, and a second copy of them in React is a second copy to get
 * wrong.
 *
 * **Two permissions, because they are two jobs.** `config:draft` opens a change
 * and attaches the replay; `config:approve` signs it off. The API gates each
 * route separately and refuses the maker's own approval, so this page shows
 * each person only the half they hold. `config:approve` is also a step-up
 * permission, which is why an approver on an ordinary session is asked to
 * re-authenticate before the buttons would do anything.
 */

type Busy = string | null;

/** The states `ChangeState` actually has. Anything else renders neutral. */
const STATE_TONE: Record<string, "neutral" | "warning" | "success" | "danger"> = {
  draft: "neutral",
  in_review: "warning",
  approved: "warning",
  scheduled: "warning",
  active: "success",
  superseded: "neutral",
  rejected: "danger",
};

export default function StudioPage() {
  const { client, session, hasPermission, stepUp, stepUpWithProvider } = useStaffSession();
  // Exactly the permissions the routes check. Gating on `rule:publish` too
  // would let compliance in, and every call they made would come back 403.
  const canDraft = hasPermission("config:draft");
  const canApprove = hasPermission("config:approve");
  const allowed = canDraft || canApprove;

  const [changes, setChanges] = useState<PolicyChangeView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState<Busy>(null);
  const [form, setForm] = useState({ key: "", value: "", reason: "" });

  const load = useCallback(() => {
    if (!allowed) return;
    void client
      .policyChanges()
      .then((found) => {
        setChanges(found);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not read policy changes"),
      );
  }, [allowed, client]);

  useEffect(load, [load]);

  const act = useCallback(
    async (label: string, run: () => Promise<unknown>) => {
      setBusy(label);
      setError(null);
      setStatus("");
      try {
        await run();
        load();
        setStatus(`${label} done.`);
      } catch (e: unknown) {
        // The API's refusal is the message. Rewriting it would hide the rule
        // that refused, and "this approver has already signed off" or "this
        // change needs MFA step-up" is the thing the person needs to read.
        setError(e instanceof Error ? e.message : `${label} failed`);
      } finally {
        setBusy(null);
      }
    },
    [load],
  );

  if (!session || !allowed) {
    return <AccessDenied need="config:draft or config:approve" />;
  }

  return (
    <div className="space-y-5">
      <header>
        <Badge tone="warning">SYNTHETIC POLICY</Badge>
        <h1 className="mt-2 text-2xl font-semibold">Policy Studio</h1>
        <p className="text-sm text-slate-600">
          A change is drafted, replayed, approved, scheduled and only then active. The
          change class comes from the artefact&apos;s own tags, and the number of approvals
          it needs follows from that.
        </p>
      </header>

      {error ? (
        <Card className="border-rose-300 text-sm text-rose-900" role="alert">
          {error}
        </Card>
      ) : null}
      {status ? (
        <Card className="border-emerald-300 text-sm text-emerald-900">{status}</Card>
      ) : null}

      {canApprove && !stepUp ? (
        <Card className="space-y-2 border-amber-300">
          <p className="text-sm text-amber-900">
            Approving, scheduling and activating need a recent re-authentication. Your
            session is valid but not stepped up, so the API will refuse those calls.
          </p>
          <Button variant="secondary" onClick={() => void stepUpWithProvider()}>
            Re-authenticate
          </Button>
        </Card>
      ) : null}

      {canDraft ? (
        <Card className="space-y-3">
          <h2 className="font-semibold">Open a change</h2>
          <p className="text-xs text-slate-500">
            The key must already exist as a policy artefact. Its tags decide the change
            class, so a key invented here would route around the thing that sets how many
            approvals are needed.
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              Policy key
              <Input
                value={form.key}
                onChange={(e) => setForm({ ...form, key: e.target.value })}
                placeholder="refund.auto_cap_lkr"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              Candidate value
              <Input
                value={form.value}
                onChange={(e) => setForm({ ...form, value: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              Reason (required)
              <Input
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
              />
            </label>
          </div>
          <Button
            disabled={busy !== null || !form.key.trim() || !form.reason.trim()}
            onClick={() =>
              void act("Draft", async () => {
                await client.draftPolicyChange({
                  key: form.key.trim(),
                  value: form.value,
                  reason: form.reason.trim(),
                });
                setForm({ key: "", value: "", reason: "" });
              })
            }
          >
            Open change
          </Button>
        </Card>
      ) : null}

      {changes === null ? (
        <Card className="text-sm text-slate-600">Loading changes...</Card>
      ) : changes.length === 0 ? (
        <Card className="text-sm text-slate-600">
          No policy changes yet. Opening one puts it in draft; nothing takes effect until
          it has been approved, scheduled and activated.
        </Card>
      ) : (
        <div className="space-y-3">
          {changes.map((change) => (
            <ChangeCard
              key={change.change_id}
              change={change}
              canDraft={canDraft}
              canApprove={canApprove}
              busy={busy}
              onAct={act}
              client={client}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ChangeCard({
  change,
  canDraft,
  canApprove,
  busy,
  onAct,
  client,
}: {
  change: PolicyChangeView;
  canDraft: boolean;
  canApprove: boolean;
  busy: Busy;
  onAct: (label: string, run: () => Promise<unknown>) => Promise<void>;
  client: ReturnType<typeof useStaffSession>["client"];
}) {
  const id = change.change_id;
  const working = busy !== null;
  const [effectiveFrom, setEffectiveFrom] = useState("");

  return (
    <Card className="space-y-2" data-testid="policy-change">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-mono text-sm font-semibold">{change.key}</h2>
        <Badge tone={STATE_TONE[change.state] ?? "neutral"}>
          {change.state.replace("_", " ").toUpperCase()}
        </Badge>
        <span className="text-xs text-slate-500">class {change.change_class}</span>
        <span className="text-xs text-slate-500">
          {change.approvals.length} of {change.approvals_needed} approvals
        </span>
      </div>

      <p className="text-sm">{change.reason}</p>
      <p className="font-mono text-xs text-slate-500">
        candidate: {JSON.stringify(change.candidate.value)}
      </p>
      <p className="text-xs text-slate-500">
        Opened by {change.maker_ref} · {id}
      </p>
      {change.scheduled_for ? (
        <p className="text-xs text-slate-500">
          Scheduled for {new Date(change.scheduled_for).toLocaleString()}
        </p>
      ) : null}
      {change.activated_at ? (
        <p className="text-xs text-emerald-800">
          Active since {new Date(change.activated_at).toLocaleString()}
        </p>
      ) : null}

      {change.impact ? (
        <p className="rounded-lg bg-slate-50 p-2 text-xs text-slate-700">
          Replay: {change.impact.cases_evaluated} cases evaluated, {change.impact.changed}{" "}
          would change, LKR {change.impact.money_delta_lkr} difference.{" "}
          {change.impact.candidate_summary}
        </p>
      ) : null}

      {change.approvals.length ? (
        <ul className="rounded-lg bg-slate-50 p-2 text-xs text-slate-700">
          {change.approvals.map((approval, i) => (
            <li key={i}>
              approved by {approval.approver_ref} ({approval.role})
              {approval.mfa_step_up ? " · stepped up" : ""} ·{" "}
              {new Date(approval.at).toLocaleString()}
            </li>
          ))}
        </ul>
      ) : null}

      {/* Every transition the caller's permission allows is offered, and the
          API decides whether this change is in a state to take it. Hiding one
          it would accept, or showing one it would always refuse, means this
          page has grown its own idea of the lifecycle. */}
      <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-2">
        {canDraft ? (
          <Button
            variant="secondary"
            disabled={working}
            onClick={() =>
              void onAct("Replay", () =>
                client.reviewPolicyChange(id, {
                  cases_evaluated: 0,
                  candidate_summary: "Replay requested from Policy Studio",
                }),
              )
            }
          >
            Attach replay
          </Button>
        ) : null}

        {canApprove ? (
          <>
            <Button
              disabled={working}
              onClick={() => void onAct("Approve", () => client.approvePolicyChange(id))}
            >
              Approve
            </Button>
            <label className="flex items-center gap-1 text-xs text-slate-500">
              from
              <input
                type="datetime-local"
                value={effectiveFrom}
                onChange={(e) => setEffectiveFrom(e.target.value)}
                aria-label={`Effective from for ${change.key}`}
                className="rounded-md border border-slate-300 px-2 py-1 text-xs"
              />
            </label>
            <Button
              variant="secondary"
              disabled={working || !effectiveFrom}
              onClick={() =>
                void onAct("Schedule", () =>
                  client.schedulePolicyChange(id, {
                    effective_from: new Date(effectiveFrom).toISOString(),
                  }),
                )
              }
            >
              Schedule
            </Button>
            <Button
              disabled={working}
              onClick={() => void onAct("Activate", () => client.activatePolicyChange(id))}
            >
              Activate
            </Button>
            {/* A reversal restores the version this change replaced, so a
                change that replaced nothing has nothing to restore. */}
            {change.supersedes ? (
              <Button
                variant="secondary"
                disabled={working}
                onClick={() =>
                  void onAct("Reversal", () =>
                    client.rollbackPolicyChange(id, {
                      reason: `Reversal of ${id}, requested from Policy Studio`,
                    }),
                  )
                }
              >
                Propose reversal
              </Button>
            ) : null}
          </>
        ) : (
          <span className="text-xs text-slate-500">
            You can open and replay changes. Signing one off needs{" "}
            <code>config:approve</code>, and the person who opened a change may never
            approve it.
          </span>
        )}
      </div>
    </Card>
  );
}
