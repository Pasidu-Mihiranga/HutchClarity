"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ClarityApiError,
  ClarityClient,
  type CaseSummary,
  type DecisionView,
} from "@clarity/sdk";
import { Alert, ErrorState, Skeleton } from "@clarity/ui";
import { t } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";
import { WhyWidget } from "@/components/WhyWidget";
import { ChargeHero } from "@/components/ChargeHero";
import { expireSession } from "@/lib/session";

const client = new ClarityClient();

/**
 * One case, as the customer sees it (E4).
 *
 * Two things were wrong here, and they were the same thing twice.
 *
 * **It fabricated a case when the request failed.** The `catch` set
 * `{ cause: "VAS silent renewal", amount: "99.00" }` and the page rendered it
 * behind an "Offline placeholder" chip. A customer whose network dropped was
 * shown a charge that did not exist, in a product whose promise is that every
 * figure on the screen came from a record. A failure is now an error state.
 *
 * **"Fix this" did nothing.** The button had no `onClick`, and the receipt link
 * pointed at `/receipt/TR-<case id>`, an id invented by string concatenation.
 * The page now offers the action the decision actually allows, and links to a
 * receipt only when one exists for this case.
 *
 * **Why the explanation comes from `evaluate`.** `POST /v1/cases/{id}/evaluate`
 * runs the rules and the policy and changes nothing on the account (its own
 * docstring says so), and a customer holds `case:evaluate` bound to their own
 * subject. So the cause, the amount and the rationale on this page are the
 * decision's, not this page's reading of the case (I1).
 */

type Loaded = {
  summary: CaseSummary;
  decision: DecisionView;
  receiptId: string | null;
};

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const { lang } = useLanguage();
  const router = useRouter();
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setError(null);
      try {
        // The session is an HttpOnly cookie the SDK sends with credentials (B4).
        const [summary, decision, receipts] = await Promise.all([
          client.getCase(params.id),
          client.evaluateCase(params.id),
          client.myReceipts(),
        ]);
        if (cancelled) return;
        const mine = receipts.find((row) => row.case_id === params.id);
        setLoaded({ summary, decision, receiptId: mine?.receipt_id ?? null });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ClarityApiError && (err.status === 401 || err.status === 403)) {
          expireSession();
          return;
        }
        setLoaded(null);
        setError(
          err instanceof ClarityApiError && err.status === 404
            ? "We could not find this case."
            : err instanceof Error
              ? err.message
              : "We could not load this case.",
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.id, attempt]);

  if (error && !loaded) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <ErrorState
          title="We could not load this case"
          message={error}
          onRetry={() => setAttempt((n) => n + 1)}
        />
      </main>
    );
  }

  if (!loaded) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <p role="status" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
          Loading this case
        </p>
        <div style={{ display: "grid", gap: 12 }}>
          <Skeleton style={{ height: 24, width: 160 }} />
          <Skeleton style={{ height: 120, borderRadius: "var(--radius)" }} />
          <Skeleton style={{ height: 140, borderRadius: "var(--radius)" }} />
        </div>
      </main>
    );
  }

  const { summary, decision, receiptId } = loaded;
  const cause = decision.cause
    ? decision.cause.rule_id.replace(/_/g, " ")
    : decision.handoff_reason || "No cause confirmed yet";
  const amount = decision.amount_lkr ?? summary.money_at_stake_lkr;
  const outcome = decision.outcome;

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <p style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <span
          style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, color: "var(--muted)" }}
        >
          {summary.case_no}
        </span>
      </p>

      <ChargeHero
        amount={amount ?? "-"}
        cause={cause}
        state={summary.state.replace(/_/g, " ")}
      />

      <h2
        style={{
          fontSize: 13,
          fontWeight: 650,
          color: "var(--muted)",
          margin: "18px 0 8px",
        }}
      >
        {t(lang, "why.heading")}
      </h2>
      {/* The widget quotes the decision. With no amount there is nothing for it
          to quote, so the explanation is rendered plainly instead of the card
          being given a figure to show. */}
      {amount ? (
        <WhyWidget cause={cause} amount={amount} onFix={() => router.push("/clarity")} />
      ) : (
        <p className="h-card" style={{ fontSize: 14 }}>
          {decision.explanation || "This case has not been decided yet."}
        </p>
      )}

      {decision.rationale && decision.rationale.length > 0 ? (
        <section aria-labelledby="case-rationale" style={{ marginTop: 14 }}>
          <h2
            id="case-rationale"
            style={{ fontSize: 13, fontWeight: 650, color: "var(--muted)", margin: "0 0 8px" }}
          >
            What the policy said
          </h2>
          <ul className="h-card" style={{ fontSize: 14, margin: 0, paddingLeft: 32 }}>
            {decision.rationale.map((line) => (
              <li key={line} style={{ marginBottom: 4 }}>
                {line}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div style={{ display: "grid", gap: 8, marginTop: 16 }}>
        {/* The action the decision allows, not a button that is always there.
            A confirmation is minted in the chat, outside the AI path, which is
            why the fix path leads there rather than executing here. */}
        {decision.requires_confirmation ? (
          <button
            type="button"
            className="h-btn h-btn-primary"
            style={{ width: "100%", fontSize: 16 }}
            onClick={() => router.push("/clarity")}
          >
            {t(lang, "fix.cta")}
          </button>
        ) : null}

        {outcome === "STAFF_APPROVAL" ? (
          <Alert tone="info">
            A person is reviewing this. Approving a refund of this size needs two
            of them, and you will get a Trust Receipt when it is done.
          </Alert>
        ) : null}

        {outcome === "HANDOFF" ? (
          <Alert tone="warning">
            {decision.handoff_reason ||
              "We have passed this to a person, because the records did not say enough to decide it."}
          </Alert>
        ) : null}

        {outcome === "EXPLAIN_ONLY" ? (
          <Alert tone="info">
            There is nothing to refund here: the charge was correct. The reason is
            above, with the records it came from.
          </Alert>
        ) : null}

        {receiptId ? (
          <Link
            href={`/receipt/${receiptId}`}
            style={{
              display: "block",
              textAlign: "center",
              fontSize: 14,
              fontWeight: 650,
              color: "var(--orange-ink)",
              padding: "10px 0",
              textDecoration: "none",
            }}
          >
            {t(lang, "receipt.verify")} →
          </Link>
        ) : null}
      </div>
    </main>
  );
}
