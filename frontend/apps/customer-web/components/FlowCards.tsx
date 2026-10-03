"use client";

/**
 * The flow's own artefacts, rendered (C05, #24; plan 22 section 4 step 10).
 *
 * Until C05 the chat showed one reply bubble per turn and discarded everything
 * the server-side flow produced: which journey the customer was on, the plan
 * waiting to be confirmed, the sources an answer was grounded in, and whether
 * a person had been asked for. All four were already in the turn payload.
 *
 * Three rules these components follow, and all three come from backend
 * invariants rather than from taste:
 *
 * 1. **No amount is ever composed here.** `ConfirmCard` prints the amount the
 *    plan carries and nothing else: no arithmetic, no currency guessing, no
 *    "about LKR 50". I1 keeps amounts to the decision record, and a UI that
 *    rounds one has invented a figure as surely as a model would.
 * 2. **A citation is shown whole.** `source@version#clause` is what the K03
 *    verifier checked and what a reader can look up; dropping the version
 *    would leave a reference to "the terms" with no way to tell which terms.
 * 3. **Confirming is a link to the server's own confirm step**, never a local
 *    "mark as done". The confirmation token is minted server side (ADR-0007)
 *    and nothing here can mint one.
 */

import { type Citation, type FlowSnapshot, type Handoff } from "@/lib/clarityChat";

export type FlowCopy = {
  flowLabel: (flow: string) => string;
  stateLabel: (state: string) => string;
  confirmTitle: string;
  confirmBody: string;
  confirmCta: string;
  confirmPending: string;
  sourcesTitle: string;
  sourcesNote: string;
  handoffTitle: string;
  handoffBody: (queue: string) => string;
  refusedTitle: string;
  refusedBody: string;
  receiptCta: string;
  stepOf: (position: number, total: number) => string;
};

/** The journeys a customer can be on, in the order their states run. */
const FLOW_STEPS: Record<string, string[]> = {
  DISPUTE_CHARGE: ["identify", "evaluate", "explain", "offer_remedy", "propose", "await_confirm", "receipt"],
  KNOWLEDGE_QA: ["retrieve", "answer", "answered"],
  ACCOUNT_AND_POLICY: ["account_facts", "policy_context", "answered"],
  SAFEGUARD_SETUP: ["choose", "propose", "await_confirm", "safeguard_on"],
  CASE_STATUS: ["find_case", "status", "done"],
  NETWORK_STATUS: ["lookup", "incident", "no_incident"],
  HANDOFF: ["ticket", "handed_off"],
};

/**
 * Where the customer is in their journey.
 *
 * An ordered list with the current step marked, not a percentage: a flow can
 * exit early and legitimately (a dispute that explains and proposes nothing),
 * so a progress bar would either lie about how far along someone is or imply
 * steps that will never run.
 */
export function FlowProgress({
  flow,
  copy,
}: {
  flow: FlowSnapshot;
  copy: FlowCopy;
}) {
  const steps = FLOW_STEPS[flow.flow ?? ""] ?? [];
  const position = steps.indexOf(flow.state ?? "");
  if (!flow.flow || flow.flow === "none" || steps.length === 0) return null;

  return (
    <nav
      aria-label={copy.flowLabel(flow.flow)}
      className="rounded-xl border border-slate-200 bg-white/70 px-3 py-2 text-xs"
    >
      <p className="font-medium text-slate-700">{copy.flowLabel(flow.flow)}</p>
      <ol className="mt-1 flex flex-wrap gap-1">
        {steps.map((step, index) => {
          const done = position > index;
          const current = position === index;
          return (
            <li
              key={step}
              // The current step is announced, the rest are decoration. A
              // screen reader hearing seven step names on every turn learns
              // nothing; hearing "step 5 of 7, awaiting your confirmation"
              // is the whole message.
              aria-current={current ? "step" : undefined}
              className={[
                "rounded-full px-2 py-0.5",
                current
                  ? "bg-slate-900 text-white"
                  : done
                    ? "bg-slate-200 text-slate-600"
                    : "bg-slate-50 text-slate-400",
              ].join(" ")}
            >
              {copy.stateLabel(step)}
            </li>
          );
        })}
      </ol>
      {position >= 0 ? (
        <p className="sr-only">{copy.stepOf(position + 1, steps.length)}</p>
      ) : null}
    </nav>
  );
}

/**
 * The plan the flow proposed, and the one button that executes it.
 *
 * `amount` is printed exactly as the server sent it. The flow may only propose
 * (I1), so this card is the whole of what a customer is asked to agree to, and
 * what it says has to be what the plan says.
 */
export function ConfirmCard({
  planId,
  amount,
  summary,
  busy,
  onConfirm,
  copy,
}: {
  planId: string;
  amount?: string | null;
  summary?: string | null;
  busy?: boolean;
  onConfirm: () => void;
  copy: FlowCopy;
}) {
  return (
    <section
      aria-labelledby={`confirm-${planId}`}
      className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4"
    >
      <h3 id={`confirm-${planId}`} className="text-sm font-semibold text-emerald-900">
        {copy.confirmTitle}
      </h3>
      <p className="mt-1 text-sm text-emerald-900/80">{summary || copy.confirmBody}</p>
      {amount ? (
        <p className="mt-2 text-lg font-semibold tabular-nums text-emerald-950">
          {/* Printed, never computed. The currency and the figure both come
              from the plan: formatting one here would be composing an amount. */}
          LKR {amount}
        </p>
      ) : null}
      <button
        type="button"
        onClick={onConfirm}
        disabled={busy}
        aria-busy={busy || undefined}
        className="mt-3 w-full rounded-xl bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {busy ? copy.confirmPending : copy.confirmCta}
      </button>
    </section>
  );
}

/**
 * The sources an answer was grounded in.
 *
 * Shown for any answer that has them, because an answer a customer cannot
 * check is the thing this whole product exists not to give them. K03 already
 * verified that each one was retrieved, is effective and is allowed; this
 * renders what survived that.
 */
export function Citations({
  citations,
  copy,
}: {
  citations: Citation[];
  copy: FlowCopy;
}) {
  if (citations.length === 0) return null;
  return (
    <section aria-labelledby="sources-heading" className="mt-2 text-xs">
      <h3 id="sources-heading" className="font-medium text-slate-600">
        {copy.sourcesTitle}
      </h3>
      <ul className="mt-1 space-y-0.5">
        {citations.map((citation) => (
          <li key={citation} className="font-mono text-[11px] text-slate-500">
            {/* Whole, including the version and the clause. A citation a
                reader cannot look up is decoration. */}
            {citation}
          </li>
        ))}
      </ul>
      <p className="mt-1 text-[11px] text-slate-400">{copy.sourcesNote}</p>
    </section>
  );
}

/** A person has the case now. */
export function HandoffNotice({ handoff, copy }: { handoff: Handoff; copy: FlowCopy }) {
  if (!handoff.handoff) return null;
  return (
    <section
      // Assertive, because the customer has just been told a person is
      // taking over and that changes what they should do next.
      role="status"
      aria-live="polite"
      className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-sm"
    >
      <h3 className="font-semibold text-amber-900">{copy.handoffTitle}</h3>
      <p className="mt-1 text-amber-900/80">{copy.handoffBody(handoff.queue ?? "cx-general")}</p>
    </section>
  );
}

/**
 * The turn was refused, or its reply failed verification.
 *
 * Shown rather than swallowed. A refusal the customer cannot see leaves them
 * waiting for an answer that is never coming, and the backend refuses for
 * reasons they can act on (an OTP in a message, a reply that quoted a figure
 * nothing decided).
 */
export function RefusedNotice({ copy }: { copy: FlowCopy }) {
  return (
    <section role="status" className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm">
      <h3 className="font-semibold text-slate-800">{copy.refusedTitle}</h3>
      <p className="mt-1 text-slate-600">{copy.refusedBody}</p>
    </section>
  );
}
