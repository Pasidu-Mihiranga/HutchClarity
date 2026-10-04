"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";
import { WhyWidget } from "@/components/WhyWidget";
import { ChargeHero } from "@/components/ChargeHero";

const client = new ClarityClient();

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const { lang } = useLanguage();
  const [caseData, setCaseData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // No token to set: the session is an HttpOnly cookie the SDK
        // sends with credentials (B4).
        const data = await client.getCase(params.id);
        if (!cancelled) setCaseData(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load case");
          setCaseData({ case_id: params.id, state: "OPEN", cause: "VAS silent renewal", amount: "99.00" });
        }
      }
    })();
    return () => { cancelled = true; };
  }, [params.id]);

  const cause = (caseData?.cause as string) ?? (caseData?.primary_cause as string) ?? "Investigating...";
  const amount = String(caseData?.amount ?? "99.00");
  const state  = String(caseData?.state ?? "OPEN");

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>

      {/* Reference row */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, color: "var(--muted)" }}>
          {params.id}
        </span>
        {error && (
          <span
            style={{
              padding: "3px 8px", borderRadius: 999, fontSize: 11,
              fontWeight: 700, background: "#f4f4f5", color: "#52525b",
            }}
          >
            Offline placeholder
          </span>
        )}
      </div>

      <ChargeHero amount={amount} cause={cause} state={state} />

      {/* Why section */}
      <p style={{ fontSize: 13, fontWeight: 650, color: "var(--muted)", margin: "18px 0 8px" }}>
        {t(lang, "why.heading")}
      </p>
      <WhyWidget cause={cause} amount={amount} />

      {/* Actions */}
      <div style={{ display: "grid", gap: 8, marginTop: 16 }}>
        <button className="h-btn h-btn-primary" style={{ width: "100%", fontSize: 16 }}>
          {t(lang, "fix.cta")}
        </button>
        <Link
          href={`/receipt/TR-${params.id}`}
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
      </div>
    </main>
  );
}
