"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ClarityApiError, ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";

const client = new ClarityClient();

/**
 * The customer's view of a Trust Receipt, and the page an officer reaches
 * from its QR code.
 *
 * **It must never claim a receipt is valid unless the backend said so.** This
 * is the same rule `apps/verify/app/r/[id]/page.tsx` documents. The verdict
 * comes from `POST /v1/receipts/{id}/verify`, the only endpoint that computes
 * one. `GET /v1/receipts/{id}` returns the signed document (`payload`,
 * `payload_hash`, `signature`, `verify_url`) and carries no verdict, so it
 * only enriches the page: it needs `receipt:read`, a signed-out holder of the
 * link still gets a real verdict, and a document that fails to load never
 * changes it.
 *
 * | Backend                  | Shown           |
 * |--------------------------|-----------------|
 * | `valid: true`            | Valid           |
 * | `valid: false`           | Invalid         |
 * | 404, or no answer at all | Not checked     |
 *
 * The QR code is `GET /v1/receipts/{id}/qr.svg`. It encodes only the public
 * verify URL, so an officer's scan re-checks the signed record on the server
 * instead of trusting anything printed on the screen beside it.
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

type ReceiptAction = { type?: string; amount_lkr?: string | null; adapter_ref?: string | null };

type ReceiptDetail = {
  issuedAt?: string;
  summary?: string;
  actions: ReceiptAction[];
  caseId?: string;
  verifyUrl?: string;
};

function readDetail(doc: Record<string, unknown> | null | undefined): ReceiptDetail | null {
  const payload = doc?.payload as Record<string, unknown> | undefined;
  if (!payload) return null;
  const what = payload.what_happened as { summary?: unknown } | undefined;
  return {
    issuedAt: typeof payload.issued_at === "string" ? payload.issued_at : undefined,
    summary: typeof what?.summary === "string" && what.summary ? what.summary : undefined,
    actions: Array.isArray(payload.actions) ? (payload.actions as ReceiptAction[]) : [],
    caseId: typeof payload.case_id === "string" ? payload.case_id : undefined,
    verifyUrl: typeof doc?.verify_url === "string" ? doc.verify_url : undefined,
  };
}

function formatDate(iso: string | undefined, lang: string): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  const locale = lang === "si" ? "si-LK" : lang === "ta" ? "ta-LK" : "en-GB";
  return date.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
}

export default function ReceiptPage({ params }: { params: { id: string } }) {
  const { lang } = useLanguage();
  const router = useRouter();
  const [state, setState] = useState<Verdict>({ phase: "checking" });
  const [detail, setDetail] = useState<ReceiptDetail | null>(null);
  const [alerts, setAlerts] = useState<"on" | "off" | null>(null);
  const [alertsBusy, setAlertsBusy] = useState(false);
  const [shared, setShared] = useState(false);

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
        const doc = (await client.getReceipt(params.id)) as Record<string, unknown>;
        if (!cancelled) setDetail(readDetail(doc));
      } catch {
        /* signed out, or not this customer's receipt: the verdict stands alone */
      }
    })();

    // The spend-alert switch is the customer's own setting, so it appears only
    // for a signed-in customer. An officer scanning the code sees no switch.
    (async () => {
      try {
        const app = await client.myApp();
        if (cancelled) return;
        const value = (app.safeguards as Record<string, unknown> | undefined)?.usage_alerts;
        setAlerts(value === "on" ? "on" : "off");
      } catch {
        /* not signed in as a customer */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [params.id]);

  async function toggleAlerts() {
    if (alerts === null || alertsBusy) return;
    const next = alerts === "on" ? "off" : "on";
    setAlertsBusy(true);
    try {
      const app = await client.setSafeguard("usage_alerts", next);
      const value = (app.safeguards as Record<string, unknown> | undefined)?.usage_alerts;
      setAlerts(value === "on" ? "on" : "off");
    } catch {
      /* the switch stays where the server last said it was */
    } finally {
      setAlertsBusy(false);
    }
  }

  async function share() {
    const url = detail?.verifyUrl ?? (typeof window !== "undefined" ? window.location.href : "");
    if (!url) return;
    try {
      if (typeof navigator !== "undefined" && navigator.share) {
        await navigator.share({ title: `${t(lang, "receipt.title")} ${params.id}`, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setShared(true);
    } catch {
      /* the person closed the share sheet */
    }
  }

  const checked = state.phase === "checked";
  const valid = checked ? state.valid : null;
  const exists = !(state.phase === "unchecked" && state.missing);
  const refunded = detail?.actions.some((a) => a.type === "REFUND") ?? false;
  const amount =
    detail?.actions.find((a) => a.amount_lkr)?.amount_lkr ??
    (checked && state.correctedLkr ? state.correctedLkr : null);
  const actionLabel = detail
    ? detail.actions.length
      ? Array.from(new Set(detail.actions.map((a) => t(lang, `receipt.action.${a.type}`)))).join(", ")
      : t(lang, "receipt.action.none")
    : null;
  const reference = detail?.actions.find((a) => a.adapter_ref)?.adapter_ref ?? detail?.caseId ?? null;
  const issued = formatDate(detail?.issuedAt, lang);

  const rows: Array<[string, string | null, boolean?]> = [
    [t(lang, "receipt.field.id"), params.id, true],
    [t(lang, "receipt.field.date"), issued],
    [t(lang, "receipt.field.action"), actionLabel],
    [t(lang, "receipt.field.amount"), amount ? `LKR ${amount}` : null],
    [t(lang, "receipt.field.reason"), detail?.summary ?? (checked ? state.reason || null : null)],
    [t(lang, "receipt.field.reference"), reference, true],
  ];

  return (
    <main className="mx-auto grid max-w-[560px] gap-4 px-1 pb-8 pt-3">
      <header className="relative flex items-center justify-center py-1">
        <button
          type="button"
          onClick={() => router.back()}
          aria-label={t(lang, "receipt.back")}
          className="absolute left-0 grid h-10 w-10 place-items-center rounded-full text-fg transition hover:bg-surface-2"
        >
          <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2.2}>
            <path d="M19 12H5M11 5l-7 7 7 7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <h1 className="m-0 text-lg font-bold text-fg">{t(lang, "receipt.title")}</h1>
      </header>

      {state.phase === "checking" ? (
        <section role="status" className="rounded-3xl border border-border bg-surface px-6 py-10 text-center text-sm text-fg-muted">
          {t(lang, "receipt.checking")}
        </section>
      ) : (
        <>
          <section
            className={`rounded-3xl px-6 py-7 text-center ${
              valid === true ? "bg-success-soft" : valid === false ? "bg-danger-soft" : "bg-warning-soft"
            }`}
          >
            <span
              aria-hidden
              className={`mx-auto mb-3 grid h-16 w-16 place-items-center rounded-full text-white shadow-2 ${
                valid === true ? "bg-success" : valid === false ? "bg-danger" : "bg-warning"
              }`}
            >
              {valid === true ? (
                <svg viewBox="0 0 24 24" className="h-8 w-8" fill="none" stroke="currentColor" strokeWidth={3}>
                  <path d="M5 12.5l4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" className="h-8 w-8" fill="none" stroke="currentColor" strokeWidth={3}>
                  <path d="M12 7v6M12 17h.01" strokeLinecap="round" />
                </svg>
              )}
            </span>
            <h2 className="m-0 text-2xl font-extrabold tracking-tight text-fg">
              {valid === true
                ? t(lang, "receipt.resolved")
                : valid === false
                  ? t(lang, "receipt.invalidTitle")
                  : t(lang, "receipt.uncheckedTitle")}
            </h2>
            <p className="mx-auto mt-1.5 max-w-sm text-sm text-fg-muted">
              {valid === true
                ? refunded
                  ? t(lang, "receipt.resolvedRefund")
                  : t(lang, "receipt.resolvedCheck")
                : valid === false
                  ? t(lang, "receipt.invalidBody")
                  : state.phase === "unchecked" && state.missing
                    ? t(lang, "receipt.missingHint")
                    : t(lang, "receipt.unavailable")}
            </p>
          </section>

          <section
            className="rounded-3xl border border-border bg-surface p-6 shadow-2"
            data-testid="receipt-result"
            data-verified={state.phase === "unchecked" ? "unchecked" : String(valid)}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div className="leading-none">
                <p className="m-0 text-sm font-extrabold tracking-wide text-brand">HUTCH</p>
                <p className="m-0 text-4xl font-extrabold tracking-tight text-fg">Clarity</p>
              </div>
              <span
                className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider ${
                  !checked
                    ? "bg-warning-soft text-warning"
                    : valid
                      ? "bg-success-soft text-success"
                      : "bg-danger-soft text-danger"
                }`}
              >
                {!checked
                  ? t(lang, "receipt.badge.unchecked")
                  : valid
                    ? t(lang, "receipt.badge.valid")
                    : t(lang, "receipt.badge.invalid")}
              </span>
            </div>

            {state.phase === "unchecked" ? (
              <div className="border-t border-border pt-4">
                <p className="m-0 font-mono text-sm font-semibold text-fg [overflow-wrap:anywhere]">{params.id}</p>
                <p className="mt-2 text-sm text-fg">
                  {state.missing
                    ? t(lang, "receipt.missing", { id: params.id })
                    : t(lang, "receipt.unavailable")}
                </p>
                {!state.missing ? (
                  <p className="mt-1 text-xs text-fg-muted">
                    {t(lang, "receipt.unavailableHint", { detail: state.detail })}
                  </p>
                ) : null}
              </div>
            ) : (
              <dl className="m-0 divide-y divide-border border-t border-border">
                {rows
                  .filter(([, value]) => value)
                  .map(([label, value, mono]) => (
                    <div key={label} className="flex items-start justify-between gap-4 py-3">
                      <dt className="text-sm text-fg-muted">{label}</dt>
                      <dd
                        className={`m-0 max-w-[62%] text-right text-sm font-semibold text-fg [overflow-wrap:anywhere] ${
                          mono ? "font-mono" : ""
                        }`}
                      >
                        {value}
                      </dd>
                    </div>
                  ))}
                {checked ? (
                  <>
                    <div className="flex items-center justify-between gap-4 py-3">
                      <dt className="text-sm text-fg-muted">{t(lang, "receipt.field.signature")}</dt>
                      <dd className={`m-0 text-sm font-bold ${valid ? "text-success" : "text-danger"}`}>
                        {valid ? t(lang, "receipt.signatureOk") : t(lang, "receipt.signatureBad")}
                      </dd>
                    </div>
                    <div className="flex items-center justify-between gap-4 py-3">
                      <dt className="text-sm text-fg-muted">{t(lang, "receipt.field.chain")}</dt>
                      <dd className={`m-0 text-sm font-bold ${state.chainOk ? "text-success" : "text-danger"}`}>
                        {state.chainOk ? t(lang, "receipt.chainOk") : t(lang, "receipt.chainBad")}
                      </dd>
                    </div>
                    {state.keyId ? (
                      <div className="flex items-center justify-between gap-4 py-3">
                        <dt className="text-sm text-fg-muted">{t(lang, "receipt.field.key")}</dt>
                        <dd className="m-0 font-mono text-xs font-semibold text-fg">{state.keyId}</dd>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </dl>
            )}

            {exists ? (
              <div className="mt-5 grid items-center gap-4 rounded-2xl border border-border bg-surface-2 p-4 sm:grid-cols-[132px_1fr]">
                {/* eslint-disable-next-line @next/next/no-img-element -- an SVG from the API, not a static asset */}
                <img
                  src={client.receiptQrUrl(params.id)}
                  alt={t(lang, "receipt.scanTitle")}
                  width={132}
                  height={132}
                  className="mx-auto h-[132px] w-[132px] rounded-xl bg-white p-1.5"
                  data-testid="receipt-qr"
                />
                <div className="text-center sm:text-left">
                  <p className="m-0 text-sm font-bold text-fg">{t(lang, "receipt.scanTitle")}</p>
                  <p className="mt-1 text-xs leading-5 text-fg-muted">{t(lang, "receipt.scanBody")}</p>
                </div>
              </div>
            ) : null}

            {exists ? (
              <button
                type="button"
                onClick={() => void share()}
                className="mt-4 flex min-h-[52px] w-full items-center justify-center gap-2 rounded-2xl border border-border-strong bg-surface text-sm font-bold text-fg transition hover:border-brand hover:text-primary"
              >
                <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5 text-brand" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M12 3v12M7 8l5-5 5 5M5 13v6a2 2 0 002 2h10a2 2 0 002-2v-6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {shared ? t(lang, "receipt.shareCopied") : t(lang, "receipt.share")}
              </button>
            ) : null}
          </section>

          {alerts !== null ? (
            <section className="flex items-center gap-4 rounded-3xl bg-primary-soft p-5">
              <span aria-hidden className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-surface text-brand">
                <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <div className="min-w-0 flex-1">
                <p id="alerts-title" className="m-0 text-sm font-bold text-fg">{t(lang, "receipt.alertsTitle")}</p>
                <p className="mt-0.5 text-xs leading-5 text-fg-muted">{t(lang, "receipt.alertsBody")}</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={alerts === "on"}
                aria-labelledby="alerts-title"
                disabled={alertsBusy}
                onClick={() => void toggleAlerts()}
                className={`relative h-8 w-14 shrink-0 rounded-full transition disabled:opacity-60 ${
                  alerts === "on" ? "bg-primary" : "bg-border-strong"
                }`}
              >
                <span
                  aria-hidden
                  className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow-1 transition-all ${
                    alerts === "on" ? "left-7" : "left-1"
                  }`}
                />
              </button>
            </section>
          ) : null}
        </>
      )}
    </main>
  );
}
