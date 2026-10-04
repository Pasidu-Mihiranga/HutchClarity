"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { t } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";
import { SessionEnded, authFetch } from "@/lib/session";

type Summary = {
  case_id: string;
  case_no: string;
  state: string;
  msisdn_masked: string;
  money_at_stake_lkr: string | null;
  opened_at: string;
};
type AppCase = { case_id: string; outcome: string | null; headline: string | null; open: boolean };
type Receipt = { receipt_id: string; case_id: string; summary: string; corrected_lkr: string };

const OUTCOME_LABEL: Record<string, string> = {
  AUTO_FIX: "Fixed automatically",
  ONE_TAP_FIX: "Ready for your confirmation",
  STAFF_APPROVAL: "Waiting for a staff approval",
  EXPLAIN_ONLY: "Explained: nothing to refund",
  HANDOFF: "With a Hutch agent",
};

async function json<T>(path: string): Promise<T> {
  const res = await authFetch(path);
  if (!res.ok) throw new Error(res.status === 404 ? "This case was not found." : `Request failed (${res.status})`);
  return (await res.json()) as T;
}

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const { lang } = useLanguage();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [detail, setDetail] = useState<AppCase | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const id = encodeURIComponent(params.id);
      const [found, app, receipts] = await Promise.all([
        json<Summary>(`/v1/cases/${id}`),
        json<{ cases?: AppCase[] }>("/v1/me/app"),
        json<Receipt[]>("/v1/me/receipts"),
      ]);
      setSummary(found);
      setDetail(app.cases?.find((c) => c.case_id === params.id) ?? null);
      setReceipt(receipts.find((r) => r.case_id === params.id) ?? null);
    } catch (err) {
      // An error is shown as an error. This page used to fall back to an
      // invented "VAS silent renewal" case for LKR 99.00.
      if (!(err instanceof SessionEnded)) setError(err instanceof Error ? err.message : "Could not load this case");
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "40px 0" }}>
        <div role="alert" style={card}>
          <p style={{ margin: "0 0 8px", fontWeight: 700 }}>We could not load this case.</p>
          <p style={{ margin: "0 0 14px", fontSize: 13, color: "var(--muted)" }}>{error}</p>
          <button type="button" className="h-btn h-btn-primary" onClick={() => void load()}>
            Try again
          </button>
        </div>
      </main>
    );
  }

  if (!summary) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "40px 0" }} aria-busy="true">
        <p style={{ color: "var(--muted)" }}>Loading the case...</p>
      </main>
    );
  }

  const open = detail ? detail.open : summary.state !== "CLOSED";
  const outcome = detail?.outcome ? (OUTCOME_LABEL[detail.outcome] ?? detail.outcome) : "Being investigated";

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <p style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, color: "var(--muted)", margin: "0 0 10px" }}>
        Case {summary.case_no} · opened {new Date(summary.opened_at).toLocaleDateString()}
      </p>

      <div style={{ ...card, borderTop: `3px solid ${open ? "var(--orange)" : "var(--ok)"}` }}>
        <span className={`h-badge ${open ? "h-badge-open" : "h-badge-resolved"}`}>{open ? "Open" : "Resolved"}</span>
        <h1 style={{ fontSize: 20, fontWeight: 800, margin: "10px 0 4px" }}>{outcome}</h1>
        {summary.money_at_stake_lkr ? (
          <p style={{ margin: 0, fontSize: 15, color: "var(--muted)" }}>Amount in question: LKR {summary.money_at_stake_lkr}</p>
        ) : null}
      </div>

      <p style={{ fontSize: 13, fontWeight: 650, color: "var(--muted)", margin: "18px 0 8px" }}>{t(lang, "why.heading")}</p>
      <div style={card}>
        <p style={{ margin: 0, fontSize: 15 }}>{detail?.headline ?? "Clarity has not reached a finding on this case yet."}</p>
      </div>

      <div style={{ display: "grid", gap: 8, marginTop: 16 }}>
        <Link href="/clarity" className="h-btn h-btn-primary" style={{ width: "100%", fontSize: 16, textAlign: "center" }}>
          Continue in Clarity
        </Link>
        {receipt ? (
          <Link
            href={`/receipt/${encodeURIComponent(receipt.receipt_id)}`}
            style={{ display: "block", textAlign: "center", fontSize: 14, fontWeight: 650, color: "var(--orange-ink)", padding: "10px 0", textDecoration: "underline" }}
          >
            {t(lang, "receipt.verify")} →
          </Link>
        ) : null}
      </div>
    </main>
  );
}

const card: React.CSSProperties = {
  border: "1px solid var(--line)",
  borderRadius: "var(--radius)",
  padding: "16px 20px",
  background: "#fff",
  boxShadow: "var(--shadow)",
};
