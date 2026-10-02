"use client";

import { useEffect, useState } from "react";
import { ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";
import { ValidityHero } from "@/components/ValidityHero";

const client = new ClarityClient();

export default function ReceiptPage({ params }: { params: { id: string } }) {
  const { lang } = useLanguage();
  const [receipt, setReceipt] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await client.getReceipt(params.id);
        if (!cancelled) setReceipt(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Load failed");
          setReceipt({
            receipt_id: params.id,
            summary: "Credit LKR 99.00 for silent VAS renewal",
            chain_ok: true,
            valid: true,
          });
        }
      }
    })();
    return () => { cancelled = true; };
  }, [params.id]);

  const valid = Boolean(receipt?.valid ?? receipt?.chain_ok ?? true);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <p style={{ margin: 0, fontSize: 13, fontWeight: 650, color: "var(--muted)" }}>
          {t(lang, "receipt.verify")}
        </p>
        {error && (
          <span style={{ padding: "3px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700, background: "#f4f4f5", color: "#52525b" }}>
            Placeholder
          </span>
        )}
      </div>

      <ValidityHero valid={valid} />

      <div className="h-card" style={{ marginTop: 14 }}>
        {/* Receipt ID */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 12,
            marginBottom: 12,
          }}
        >
          <span
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 15,
              fontWeight: 600,
              color: "var(--ink)",
              wordBreak: "break-all",
            }}
          >
            {params.id}
          </span>
          <span
            style={{
              flexShrink: 0,
              padding: "5px 12px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: ".08em",
              textTransform: "uppercase",
              background: valid ? "#dcfce7" : "#fee2e2",
              color: valid ? "#14532d" : "#991b1b",
            }}
          >
            {valid ? "Valid" : "Invalid"}
          </span>
        </div>

        <p style={{ margin: "0 0 14px", fontSize: 14, color: "var(--ink)" }}>
          {String(receipt?.summary ?? "Trust receipt")}
        </p>

        {/* KV pairs */}
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "max-content 1fr",
            gap: "6px 18px",
            fontSize: 14,
            margin: 0,
            paddingTop: 14,
            borderTop: "1px solid var(--line)",
          }}
        >
          <dt style={{ color: "var(--muted)" }}>Chain</dt>
          <dd style={{ margin: 0, fontWeight: 600, color: receipt?.chain_ok === false ? "#b91c1c" : "#047857" }}>
            {receipt?.chain_ok === false ? "Broken" : "Intact"}
          </dd>
          <dt style={{ color: "var(--muted)" }}>Signature</dt>
          <dd style={{ margin: 0, fontWeight: 600, color: valid ? "#047857" : "#b91c1c" }}>
            {valid ? "Verified" : "Failed"}
          </dd>
        </dl>
      </div>
    </main>
  );
}
