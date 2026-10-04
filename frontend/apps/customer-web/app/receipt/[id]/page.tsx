"use client";

import { useEffect, useState } from "react";
import { ClarityApiError, ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";
import { ValidityHero } from "@/components/ValidityHero";

const client = new ClarityClient();

/**
 * The customer's view of a Trust Receipt.
 *
 * **It must never claim a receipt is valid unless the backend said so.** This
 * is the same rule `apps/verify/app/r/[id]/page.tsx` documents, and this page
 * was the copy that still broke it.
 *
 * The verdict comes from `POST /v1/receipts/{id}/verify`, which is the only
 * endpoint that computes one. `GET /v1/receipts/{id}` returns the signed
 * document (`payload`, `payload_hash`, `signature`, `verify_url`) and carries
 * no `valid` or `chain_ok` field at all, so the previous `receipt?.valid ??
 * receipt?.chain_ok ?? true` could only ever resolve to `true` - on the success
 * path as much as on the error path. Every receipt rendered "Valid", "Signature
 * Verified" and "Chain Intact" whether or not anything had been checked, and a
 * failed load additionally invented a "Credit LKR 99.00" summary. On the one
 * page whose job is to prove a correction happened, a fabricated pass is worse
 * than no page at all.
 *
 * Three outcomes, and "could not check" is a real one:
 *
 * | Backend                  | Shown           |
 * |--------------------------|-----------------|
 * | `valid: true`            | Valid           |
 * | `valid: false`           | Invalid         |
 * | 404, or no answer at all | Not checked     |
 *
 * The document is fetched separately and only enriches the page: it needs
 * `receipt:read`, so a signed-out holder of the link still gets a real verdict
 * and simply sees less detail. A document that fails to load never changes the
 * verdict.
 */

type Verdict =
  | { phase: "checking" }
  | {
      phase: "checked";
      valid: boolean;
      chainOk: boolean;
      status: string;
      reason: string;
      keyId?: string;
      correctedLkr?: string;
    }
  | { phase: "unchecked"; missing: boolean; detail: string };

export default function ReceiptPage({ params }: { params: { id: string } }) {
  const { lang } = useLanguage();
  const [state, setState] = useState<Verdict>({ phase: "checking" });
  const [summary, setSummary] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const data = await client.verifyReceipt(params.id);
        if (cancelled) return;
        setState({
          phase: "checked",
          // Explicitly `=== true`: a response missing the field is not a pass.
          valid: data.valid === true,
          chainOk: data.chain_ok === true,
          status: typeof data.status === "string" ? data.status : "UNKNOWN",
          reason: typeof data.reason === "string" ? data.reason : "",
          keyId: typeof data.key_id === "string" ? data.key_id : undefined,
          correctedLkr:
            typeof data.corrected_lkr === "string" ? data.corrected_lkr : undefined,
        });
      } catch (err) {
        if (cancelled) return;
        setState({
          phase: "unchecked",
          missing: err instanceof ClarityApiError && err.status === 404,
          detail: err instanceof Error ? err.message : "the service did not answer",
        });
      }
    })();

    // Detail only. It never contributes to the verdict, so its failure is silent.
    (async () => {
      try {
        const doc = await client.getReceipt(params.id);
        if (cancelled) return;
        const payload = doc?.payload as { what_happened?: { summary?: unknown } } | undefined;
        const text = payload?.what_happened?.summary;
        if (typeof text === "string" && text.length > 0) setSummary(text);
      } catch {
        /* signed out, or not this customer's receipt: the verdict stands alone */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [params.id]);

  const valid = state.phase === "checked" ? state.valid : null;
  const checked = state.phase === "checked";

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <p style={{ margin: 0, fontSize: 13, fontWeight: 650, color: "var(--muted)" }}>
          {t(lang, "receipt.verify")}
        </p>
      </div>

      {state.phase === "checking" ? (
        <div className="h-card" role="status" style={{ textAlign: "center", padding: "32px 16px" }}>
          <p style={{ margin: 0, fontSize: 14, color: "var(--muted)" }}>Checking chain...</p>
        </div>
      ) : (
        <>
          <ValidityHero valid={valid} />

          <div
            className="h-card"
            style={{ marginTop: 14 }}
            data-testid="receipt-result"
            data-verified={state.phase === "unchecked" ? "unchecked" : String(valid)}
          >
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
                  background: !checked ? "rgb(var(--c-warning-soft))" : valid ? "rgb(var(--c-success-soft))" : "rgb(var(--c-danger-soft))",
                  color: !checked ? "rgb(var(--c-warning))" : valid ? "rgb(var(--c-success))" : "rgb(var(--c-danger))",
                }}
              >
                {!checked ? "Not checked" : valid ? "Valid" : "Invalid"}
              </span>
            </div>

            {state.phase === "unchecked" ? (
              <>
                <p style={{ margin: "0 0 6px", fontSize: 14, color: "var(--ink)" }}>
                  {state.missing
                    ? `No receipt numbered ${params.id} has ever been issued.`
                    : "This receipt could not be checked right now."}
                </p>
                <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
                  {state.missing
                    ? "Check the number on your receipt, or scan the QR code again."
                    : `The verification service did not answer (${state.detail}). Nothing here says whether the receipt is genuine.`}
                </p>
              </>
            ) : (
              <>
                <p style={{ margin: "0 0 14px", fontSize: 14, color: "var(--ink)" }}>
                  {summary ?? state.reason ?? state.status}
                </p>

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
                  <dt style={{ color: "var(--muted)" }}>Status</dt>
                  <dd style={{ margin: 0, fontWeight: 600, color: "var(--ink)" }}>
                    {state.status}
                  </dd>

                  <dt style={{ color: "var(--muted)" }}>Chain</dt>
                  <dd
                    style={{
                      margin: 0,
                      fontWeight: 600,
                      color: state.chainOk ? "rgb(var(--c-success))" : "rgb(var(--c-danger))",
                    }}
                  >
                    {state.chainOk ? "Intact" : "Broken"}
                  </dd>

                  <dt style={{ color: "var(--muted)" }}>Signature</dt>
                  <dd
                    style={{ margin: 0, fontWeight: 600, color: valid ? "rgb(var(--c-success))" : "rgb(var(--c-danger))" }}
                  >
                    {valid ? "Verified" : "Failed"}
                  </dd>

                  {state.correctedLkr ? (
                    <>
                      <dt style={{ color: "var(--muted)" }}>Corrected</dt>
                      <dd style={{ margin: 0, fontWeight: 600, color: "var(--ink)" }}>
                        LKR {state.correctedLkr}
                      </dd>
                    </>
                  ) : null}

                  {state.keyId ? (
                    <>
                      <dt style={{ color: "var(--muted)" }}>Key id</dt>
                      <dd
                        style={{
                          margin: 0,
                          fontWeight: 600,
                          fontFamily: "ui-monospace, monospace",
                          color: "var(--ink)",
                        }}
                      >
                        {state.keyId}
                      </dd>
                    </>
                  ) : null}
                </dl>
              </>
            )}
          </div>
        </>
      )}
    </main>
  );
}
