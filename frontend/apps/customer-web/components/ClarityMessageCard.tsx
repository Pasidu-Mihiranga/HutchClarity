"use client";

import type {
  Article,
  ClarityState,
  Decision,
  FollowUp,
  Timeline,
  Pack,
  ResultKind,
} from "@/lib/clarityChat";
import { PROGRESS_STEPS, INTENT_EMPTY } from "@/lib/clarityChat";
import type { Lang } from "@/lib/clarityChat";

// ─── inline translations (mirrors customer.js I18N, English-only for card text) ─
type TranslationKey = keyof typeof EN;
const EN = {
  foundReason: "I found the reason",
  whatIChecked: "What I checked",
  viewEvidence: "View evidence",
  talkSupport: "Talk to Support",
  getReceipt: "Get a receipt of this check",
  refundDisable: "Refund & Disable",
  confirm: "Confirm",
  apply: "Apply the correction",
  evidenceOk: "Record found",
  evidenceWarn: "Valid consent not found",
  evidenceMissing: "Evidence incomplete",
  confidenceLabel: "{n}% confidence",
  caseNo: "Case {id}",
  humanFinding: "A person will pick this up with the full trail - you will not need to repeat anything.",
  couldNotConfirm: "Could not confirm",
  intentHint: 'Something else may need a look - try "Why did my balance change?"',
  tryAgain: "Try again",
  intentNone: "We checked your account for that, and it is not what we found.",
  intentSub: "We did not find an active subscription charge without your confirmation.",
  intentTwice: "We did not find a reload that was taken twice on this number.",
  intentSlow: "Your data is not slowed by a fair-use cap right now.",
  intentMissing: "We did not find a reload that failed to credit your balance.",
  dataRemaining: "Data remaining",
  fupActive: "Fair use cap is active",
  fupOk: "Within fair use",
  viewUsageDetails: "View usage details",
  fuBuy: "Buy another package",
  qRecommend: "Which package is best for me?",
  fuDetails: "Show full details",
  fuActivate: "Activate package",
  checkNetwork: "Check network status",
  reportIssue: "Report an issue",
  accountOk: "Account status looks normal",
  packOk: "Pack is active",
  checkLocalSignal: "Local signal may be weak",
  networkLikely: "This looks like a coverage issue rather than a billing problem.",
  qNetwork: "Is there a network problem?",
  sentToSpecialist: "Sent to a specialist",
  viewCase: "View case",
  needMoreHelp: "Need more help?",
  resolvedTitle: "Resolved",
  viewReceipt: "View Trust Receipt",
  done: "Done. Your receipt is below.",
  refundedAmount: "Refunded LKR {amount} to your balance",
  subscriptionDisabled: "Subscription disabled",
  newBalance: "New balance: LKR {amount}",
  trustReceipt: "Trust Receipt",
  verified: "Verified",
  notVerified: "not verified",
  unknown: "We could not confirm a single cause from the records we hold.",
  checking: "Checking your account...",
  progUnderstand: "Understanding your question",
  progCharges: "Checking recent charges",
  progSubs: "Checking subscriptions",
  progConsent: "Checking consent records",
  confirmDisableTitle: "Disable {product}?",
  confirmBulletStop: "Stops the subscription from renewing",
  confirmBulletNoCharge: "No further daily charges",
  confirmBulletRefund: "Refunds the disputed amount to your balance",
  thisSubscription: "this subscription",
  cancel: "Cancel",
  // Follow-up chip labels. These lived only in the chat page's catalogue, so
  // `FollowUps` fell through to rendering the raw key and customers saw
  // buttons labelled "fuSubs", "fuPrevent" and "fuSupport".
  fuSubs: "Show other subscriptions",
  fuPrevent: "Prevent this happening again",
  fuSupport: "Talk to support",
  fuFup: "Check my FUP",
  fuUsage: "Show remaining data",
  fuNetwork: "Check network status",
  fuCompare: "Compare packages",
  fuDisable: "Disable this service",
  sourcesTitle: "Sources",
  // Suggestion chips reach `FollowUps` too, so their keys belong here or the
  // fallback humanises "qBalance" into "Q Balance".
  qBalance: "Why did my balance change?",
  qSub: "Why am I subscribed?",
  qTwice: "Why was my reload taken twice?",
  qSlow: "Why is my data slow?",
  qMissing: "Why didn't my reload arrive?",
  qEsim: "How do I convert to eSIM?",
  qActivate: "How do I activate a pack?",
  qFup: "Why has my speed reduced?",
  qPackIssue: "Why isn't my package working?",
  qPackMissing: "I paid but didn't receive my data",
  qExpiry: "What happens when my package expires?",
};

const SI: Partial<typeof EN> = {
  sourcesTitle: "මූලාශ්‍ර",
  fuPrevent: "නැවත සිදු නොවීමට",
  fuSupport: "සහාය සමඟ කතා කරන්න",
  foundReason: "හේතුව හමු වුණා",
  whatIChecked: "මම පරීක්ෂා කළේ",
  talkSupport: "සහාය සමඟ කතා කරන්න",
  getReceipt: "මෙම පරීක්ෂාවේ රිසිට්පතක් ගන්න",
  refundDisable: "ආපසු ගෙවීම සහ අක්‍රිය කරන්න",
  confirm: "තහවුරු කරන්න",
  viewReceipt: "Trust Receipt බලන්න",
  resolvedTitle: "විසඳුණා",
  sentToSpecialist: "විශේෂඥයෙකුට යැව්වා",
  cancel: "අවලංගු කරන්න",
};

const TA: Partial<typeof EN> = {
  sourcesTitle: "ஆவணங்கள்",
  fuPrevent: "மீண்டும் நடக்காமல் தடு",
  fuSupport: "ஆதரவிடம் பேசு",
  foundReason: "காரணம் கிடைத்தது",
  whatIChecked: "நான் சரிபார்த்தவை",
  talkSupport: "ஆதரவிடம் பேசு",
  getReceipt: "இந்த சரிபார்ப்பின் ரசீதைப் பெறு",
  refundDisable: "திரும்பப்பணம் & நிறுத்து",
  confirm: "உறுதிசெய்",
  viewReceipt: "Trust Receipt பார்",
  resolvedTitle: "தீர்க்கப்பட்டது",
  sentToSpecialist: "நிபுணரிடம் அனுப்பப்பட்டது",
  cancel: "ரத்துசெய்",
};

function tl(lang: string, key: TranslationKey): string {
  const catalogue =
    lang === "si" ? { ...EN, ...SI } : lang === "ta" ? { ...EN, ...TA } : EN;
  return catalogue[key] ?? EN[key] ?? key;
}

// ─── card sub-components ───────────────────────────────────────────────────────

/**
 * A label for a follow-up chip, never the raw key.
 *
 * This used to be `fu.i18n_key in EN ? tl(...) : fu.i18n_key`, and the
 * follow-up keys were defined in the chat page's catalogue rather than this
 * one, so three chips rendered as "fuSubs", "fuPrevent" and "fuSupport" in the
 * customer's chat. The keys are now here, and the fallback humanises anything
 * still missing instead of leaking an identifier (I15 in spirit: a customer
 * sees approved wording, not internals).
 */
function followUpLabel(lang: string, fu: FollowUp): string {
  if (fu.i18n_key in EN) return tl(lang, fu.i18n_key as TranslationKey);
  return fu.i18n_key
    .replace(/^fu/, "")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/^./, (c) => c.toUpperCase());
}

function FollowUps({ items, lang, onFollow }: { items: FollowUp[]; lang: string; onFollow: (f: FollowUp) => void }) {
  if (!items.length) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
      {items.map((fu) => (
        <button
          key={fu.id}
          onClick={() => onFollow(fu)}
          style={{
            border: "1.5px solid #fdd5c0",
            background: "#fff",
            borderRadius: 999,
            padding: "8px 14px",
            fontSize: 13,
            fontWeight: 600,
            color: "var(--orange-ink)",
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {followUpLabel(lang, fu)}
        </button>
      ))}
    </div>
  );
}

function EvidenceList({ decision, timeline, lang }: { decision: Decision | null; timeline: Timeline | null; lang: string }) {
  const sources = timeline?.sources ?? [];
  const items: { warn: boolean; text: string }[] = [];

  for (const src of sources.slice(0, 6)) {
    const name = src.source ?? src.name ?? "source";
    const status = String(src.completeness ?? src.status ?? "").toLowerCase();
    if (status === "missing" || status === "partial") {
      items.push({ warn: true, text: `${name}: ${tl(lang, "evidenceMissing")}` });
    } else {
      items.push({ warn: false, text: `${name}: ${tl(lang, "evidenceOk")}` });
    }
  }
  const rule = decision?.matched_rule ?? decision?.rule_id ?? "";
  if (/VAS|CONSENT|NO_CONSENT/i.test(String(rule))) {
    items.push({ warn: true, text: tl(lang, "evidenceWarn") });
  }
  if (!items.length) items.push({ warn: false, text: tl(lang, "evidenceOk") });

  return (
    <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", display: "grid", gap: 4 }}>
      {items.map((it, i) => (
        <li key={i} style={{ display: "flex", gap: 8, fontSize: 13 }}>
          <span style={{ color: it.warn ? "#f59e0b" : "#22c55e", fontWeight: 700, flexShrink: 0 }}>
            {it.warn ? "⚠" : "✓"}
          </span>
          <span style={{ color: "var(--muted)" }}>{it.text}</span>
        </li>
      ))}
    </ul>
  );
}

// ─── individual card types ─────────────────────────────────────────────────────

function ThinkingCard({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 16px" }}>
      <span style={{ display: "flex", gap: 4 }} aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--orange)",
              display: "inline-block",
              animation: `ccBounce 1.2s ease-in-out ${i * 0.2}s infinite`,
            }}
          />
        ))}
      </span>
      <span style={{ fontSize: 14, color: "var(--muted)" }}>{label || "Checking your account..."}</span>
    </div>
  );
}

function ProgressCard({ step }: { step: number }) {
  return (
    <div style={{ padding: "12px 16px" }}>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
        {PROGRESS_STEPS.map((s, i) => {
          const done = i < step;
          const active = i === step;
          return (
            <li
              key={s.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 13,
                color: done ? "#22c55e" : active ? "var(--ink)" : "var(--muted)",
                fontWeight: active ? 600 : 400,
              }}
            >
              <span style={{ width: 18, textAlign: "center", fontWeight: 700 }}>
                {done ? "✓" : active ? "…" : "○"}
              </span>
              {EN[s.key as TranslationKey] ?? s.key}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function InvestigationCard({
  state,
  lang,
  onAction,
  onFollow,
  onToggleEvidence,
  showEvidence,
}: {
  state: ClarityState;
  lang: string;
  onAction: (action: "getReceipt" | "confirmFix" | "staffApprove" | "handoff") => void;
  onFollow: (f: FollowUp) => void;
  onToggleEvidence: () => void;
  showEvidence: boolean;
}) {
  const d = state.decision ?? ({} as Decision);
  const outcome = d.outcome ?? "EXPLAIN_ONLY";
  const finding = d.explanation ?? tl(lang, "unknown");
  const amount = d.amount_lkr ? `LKR ${d.amount_lkr}` : "";
  const product = d.product ?? d.merchant ?? state.contextProduct ?? "";
  const conf =
    d.confidence != null
      ? tl(lang, "confidenceLabel").replace("{n}", String(Math.round(Number(d.confidence) * (Number(d.confidence) <= 1 ? 100 : 1))))
      : "";

  let primaryBtn = null;
  if (state.mode !== "human" && outcome !== "HANDOFF") {
    if (outcome === "EXPLAIN_ONLY") {
      primaryBtn = (
        <button onClick={() => onAction("getReceipt")} style={btnPrimary}>
          {tl(lang, "getReceipt")}
        </button>
      );
    } else if (outcome === "STAFF_APPROVAL") {
      primaryBtn = (
        <button onClick={() => onAction("staffApprove")} style={btnPrimary}>
          {tl(lang, "confirm")}
        </button>
      );
    } else {
      primaryBtn = (
        <button onClick={() => onAction("confirmFix")} style={btnPrimary}>
          {outcome === "AUTO_FIX" ? tl(lang, "apply") : tl(lang, "refundDisable")}
        </button>
      );
    }
  }

  return (
    <div style={card}>
      <span style={{ ...verdict, background: outcome === "HANDOFF" ? "#fef3c7" : "#f0fdf4", color: outcome === "HANDOFF" ? "#92400e" : "#15803d" }}>
        {String(outcome).replace(/_/g, " ")}
      </span>
      <h3 style={cardH3}>{tl(lang, "foundReason")}</h3>
      {amount && <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.02em", margin: "4px 0 8px" }}>{amount}</div>}
      {product && <p style={metaText}>{product}</p>}
      <p style={{ fontSize: 15, margin: "6px 0 0" }}>{state.mode === "human" ? tl(lang, "humanFinding") : finding}</p>
      {conf && <p style={metaText}>{conf}</p>}
      <h4 style={{ fontSize: 13, fontWeight: 600, margin: "14px 0 0", color: "var(--muted)" }}>{tl(lang, "whatIChecked")}</h4>
      <EvidenceList decision={d} timeline={state.timeline} lang={lang} />
      <button onClick={onToggleEvidence} style={btnGhost}>
        {tl(lang, "viewEvidence")}
      </button>
      {showEvidence && state.timeline?.events?.slice(0, 8).map((ev, i) => (
        <p key={i} style={{ fontSize: 12, color: "var(--muted)", margin: "2px 0" }}>
          {ev.detail ?? ev.type} {ev.occurred_at ? `· ${ev.occurred_at}` : ""}
        </p>
      ))}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
        {primaryBtn}
        <button onClick={() => onAction("handoff")} style={btnSecondary}>
          {tl(lang, "talkSupport")}
        </button>
      </div>
      <FollowUps items={state.followUps} lang={lang} onFollow={onFollow} />
    </div>
  );
}

/**
 * Where a grounded answer came from (K03).
 *
 * The server returns `citation` on every article, in `SOURCE@version` form, and
 * this card used to drop it: a customer read an answer taken from a policy
 * document with no way to tell which document, or which version of it. A
 * reference a customer cannot look up is decoration, so the version is shown
 * whole rather than trimmed to something tidier.
 *
 * Rendered as a labelled region so it is announced as one, and so a test can
 * ask for it by name rather than by styling.
 */
function Sources({ articles, lang }: { articles: Article[] | null; lang: string }) {
  const cited = (articles ?? []).filter((a) => a.citation);
  if (!cited.length) return null;
  return (
    <section
      aria-label={tl(lang, "sourcesTitle")}
      style={{ marginTop: 12, borderTop: "1px solid #e2e8f0", paddingTop: 10 }}
    >
      <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: "#64748b" }}>
        {tl(lang, "sourcesTitle")}
      </p>
      <ul style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 12, color: "#475569" }}>
        {cited.map((a) => (
          <li key={a.citation}>
            {a.title}
            {" "}
            <code style={{ fontSize: 11 }}>{a.citation}</code>
            {a.owner ? ` (${a.owner})` : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}

function KnowledgeCard({ state, lang, onFollow, onHandoff }: { state: ClarityState; lang: string; onFollow: (f: FollowUp) => void; onHandoff: () => void }) {
  const top = state.articles?.[0];
  return (
    <div style={card}>
      <span style={{ ...verdict, background: "#eff6ff", color: "#1d4ed8" }}>HOW TO</span>
      <h3 style={cardH3}>{top?.title ?? tl(lang, "unknown")}</h3>
      <p style={{ fontSize: 15, margin: "6px 0 0" }}>{top?.body ?? tl(lang, "intentHint")}</p>
      <Sources articles={state.articles ?? null} lang={lang} />
      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <button onClick={onHandoff} style={btnSecondary}>{tl(lang, "needMoreHelp")}</button>
      </div>
      <FollowUps items={state.followUps} lang={lang} onFollow={onFollow} />
    </div>
  );
}

function MissCard({ state, lang, onRetry, onHandoff, onFollow }: { state: ClarityState; lang: string; onRetry: () => void; onHandoff: () => void; onFollow: (f: FollowUp) => void }) {
  const finding = tl(lang, (INTENT_EMPTY[state.intent ?? ""] ?? "intentNone") as TranslationKey);
  return (
    <div style={card}>
      <span style={{ ...verdict, background: "#fef3c7", color: "#92400e" }}>{tl(lang, "couldNotConfirm")}</span>
      <h3 style={cardH3}>{finding}</h3>
      <p style={{ fontSize: 14, color: "var(--muted)", margin: "6px 0 0" }}>{tl(lang, "intentHint")}</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
        <button onClick={onRetry} style={btnPrimary}>{tl(lang, "tryAgain")}</button>
        <button onClick={onHandoff} style={btnSecondary}>{tl(lang, "talkSupport")}</button>
      </div>
      <FollowUps items={state.followUps} lang={lang} onFollow={onFollow} />
    </div>
  );
}

function UsageCard({ state, lang, app, onFollow, onBuy }: { state: ClarityState; lang: string; app: { pack?: Pack; balance_lkr?: string | number }; onFollow: (f: FollowUp) => void; onBuy: () => void }) {
  const pack = app.pack ?? {};
  const used = Number(pack.used_pct ?? 0);
  const left = pack.data_remaining ?? pack.remaining ?? "-";
  const total = "data_gb" in pack ? `${pack.data_gb} GB` : "";
  return (
    <div style={card}>
      <h3 style={cardH3}>{tl(lang, "dataRemaining")}</h3>
      <p style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.02em", margin: "4px 0 8px" }}>
        {left}{total ? ` / ${total}` : ""}
      </p>
      <div style={{ height: 6, borderRadius: 999, background: "#f4f4f5", overflow: "hidden", margin: "4px 0 6px" }}>
        <div style={{ height: "100%", width: `${Math.min(100, used)}%`, background: used >= 80 ? "#f59e0b" : "var(--orange)", borderRadius: 999 }} />
      </div>
      <p style={metaText}>{used >= 80 ? tl(lang, "fupActive") : tl(lang, "fupOk")}</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
        <button onClick={onBuy} style={btnPrimary}>{tl(lang, "fuBuy")}</button>
      </div>
      <FollowUps items={state.followUps} lang={lang} onFollow={onFollow} />
    </div>
  );
}

function PackagesCard({ state, lang, app, onFollow }: { state: ClarityState; lang: string; app: { catalogue?: Pack[] }; onFollow: (f: FollowUp) => void }) {
  const catalogue = (app.catalogue ?? []).slice(0, 3);
  if (!catalogue.length) {
    return <KnowledgeCard state={state} lang={lang} onFollow={onFollow} onHandoff={() => {}} />;
  }
  return (
    <div style={card}>
      <h3 style={cardH3}>{tl(lang, "qRecommend")}</h3>
      <div style={{ display: "grid", gap: 10, marginTop: 8 }}>
        {catalogue.map((p) => (
          <div key={p.offering_id ?? p.name} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "12px 14px" }}>
            <strong style={{ fontSize: 15 }}>{p.name}</strong>
            <p style={metaText}>LKR {p.price_lkr ?? p.price ?? "-"} · {p.data ?? "-"} · {p.validity ?? "-"}</p>
            <button style={{ ...btnPrimary, marginTop: 8 }}>{tl(lang, "fuActivate")}</button>
          </div>
        ))}
      </div>
      <FollowUps items={state.followUps} lang={lang} onFollow={onFollow} />
    </div>
  );
}

function NetworkCard({ state, lang, onFollow, onHandoff }: { state: ClarityState; lang: string; onFollow: (f: FollowUp) => void; onHandoff: () => void }) {
  return (
    <div style={card}>
      <h3 style={cardH3}>{tl(lang, "qNetwork")}</h3>
      <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", display: "grid", gap: 4 }}>
        {[["ok", tl(lang, "accountOk")], ["ok", tl(lang, "packOk")], ["warn", tl(lang, "checkLocalSignal")]].map(([cls, text], i) => (
          <li key={i} style={{ display: "flex", gap: 8, fontSize: 13 }}>
            <span style={{ color: cls === "warn" ? "#f59e0b" : "#22c55e", fontWeight: 700 }}>{cls === "warn" ? "⚠" : "✓"}</span>
            <span style={{ color: "var(--muted)" }}>{text}</span>
          </li>
        ))}
      </ul>
      <p style={{ fontSize: 14, margin: "10px 0 0" }}>{tl(lang, "networkLikely")}</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
        <button onClick={onHandoff} style={btnSecondary}>{tl(lang, "reportIssue")}</button>
      </div>
      <FollowUps items={state.followUps} lang={lang} onFollow={onFollow} />
    </div>
  );
}

function HandoffCard({ state, lang, onViewCase }: { state: ClarityState; lang: string; onViewCase: () => void }) {
  const id = state.caseId ?? "-";
  return (
    <div style={card}>
      <span style={{ ...verdict, background: "#fef3c7", color: "#92400e" }}>HANDOFF</span>
      <h3 style={cardH3}>{tl(lang, "sentToSpecialist")}</h3>
      <p style={metaText}>{tl(lang, "caseNo").replace("{id}", id)}</p>
      <p style={{ fontSize: 14, margin: "6px 0 0" }}>{tl(lang, "humanFinding")}</p>
      <div style={{ marginTop: 14 }}>
        <button onClick={onViewCase} style={btnPrimary}>{tl(lang, "viewCase")}</button>
      </div>
    </div>
  );
}

function SuccessCard({ state, lang, app, onViewReceipt, onFollow }: {
  state: ClarityState;
  lang: string;
  app: { balance_lkr?: string | number };
  onViewReceipt: () => void;
  onFollow: (f: FollowUp) => void;
}) {
  const amount = state.decision?.amount_lkr ?? state.contextAmount ?? "";
  const bal = app.balance_lkr;
  return (
    <div style={{ ...card, borderTop: "3px solid #22c55e" }}>
      <h3 style={{ ...cardH3, color: "#15803d" }}>✓ {tl(lang, "resolvedTitle")}</h3>
      <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", display: "grid", gap: 4 }}>
        {amount && <li style={{ fontSize: 14 }}>{tl(lang, "refundedAmount").replace("{amount}", String(amount))}</li>}
        <li style={{ fontSize: 14 }}>{tl(lang, "subscriptionDisabled")}</li>
        {bal != null && <li style={{ fontSize: 14 }}>{tl(lang, "newBalance").replace("{amount}", String(bal))}</li>}
      </ul>
      <div style={{ marginTop: 14 }}>
        {state.receiptDoc && <button onClick={onViewReceipt} style={btnPrimary}>{tl(lang, "viewReceipt")}</button>}
      </div>
      <FollowUps items={state.followUps} lang={lang} onFollow={onFollow} />
    </div>
  );
}

function ReceiptCard({ state, lang, onViewReceipt }: { state: ClarityState; lang: string; onViewReceipt: () => void }) {
  const full = state.receiptDoc ?? {};
  const id = (full.receipt_id ?? full.id ?? "-") as string;
  const verified = state.receiptCheck && ((state.receiptCheck as Record<string, unknown>).valid || (state.receiptCheck as Record<string, unknown>).ok);
  return (
    <div style={card}>
      <span
        // A stable hook for the e2e, and the verdict as data rather than as
        // wording, so the assertion does not depend on the display language.
        // `verified` is the backend's answer from POST /v1/receipts/{id}/verify,
        // which recomputes the hash chain: the UI never decides this (C05).
        data-testid="receipt-verified"
        data-verified={verified ? "true" : "false"}
        style={{
          ...verdict,
          background: verified ? "#f0fdf4" : "#fef2f2",
          color: verified ? "#15803d" : "#b91c1c",
        }}
      >
        {verified ? tl(lang, "verified") : tl(lang, "notVerified")}
      </span>
      <h3 style={cardH3}>{tl(lang, "trustReceipt")}</h3>
      <p style={metaText}>{id}</p>
      <div style={{ marginTop: 14 }}>
        <button onClick={onViewReceipt} style={btnPrimary}>{tl(lang, "viewReceipt")}</button>
      </div>
    </div>
  );
}

// ─── shared styles ─────────────────────────────────────────────────────────────

const card: React.CSSProperties = {
  border: "1px solid var(--line)",
  borderRadius: "var(--radius)",
  padding: "16px 18px",
  background: "#fff",
  boxShadow: "var(--shadow)",
};

const cardH3: React.CSSProperties = {
  margin: "8px 0 0",
  fontSize: 16,
  fontWeight: 700,
};

const metaText: React.CSSProperties = {
  fontSize: 12,
  color: "var(--muted)",
  margin: "4px 0 0",
};

const verdict: React.CSSProperties = {
  display: "inline-block",
  padding: "3px 10px",
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: ".05em",
  textTransform: "uppercase",
};

const btnPrimary: React.CSSProperties = {
  background: "var(--orange-strong)",
  color: "#fff",
  border: 0,
  borderRadius: 999,
  padding: "10px 20px",
  fontSize: 14,
  fontWeight: 700,
  cursor: "pointer",
  fontFamily: "inherit",
};

const btnSecondary: React.CSSProperties = {
  background: "#f4f4f5",
  color: "var(--ink)",
  border: 0,
  borderRadius: 999,
  padding: "10px 20px",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
  fontFamily: "inherit",
};

const btnGhost: React.CSSProperties = {
  background: "transparent",
  color: "var(--orange-ink)",
  border: 0,
  padding: "8px 0",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
  fontFamily: "inherit",
  display: "block",
  marginTop: 8,
};

// ─── public dispatcher ────────────────────────────────────────────────────────

export type CardActions = {
  onAction: (action: "getReceipt" | "confirmFix" | "staffApprove" | "handoff") => void;
  onFollow: (f: FollowUp) => void;
  onToggleEvidence: () => void;
  onViewCase: () => void;
  onViewReceipt: () => void;
  onRetry: () => void;
  onBuy: () => void;
  onHandoff: () => void;
  showEvidence: boolean;
  app: { pack?: Pack; balance_lkr?: string | number; catalogue?: Pack[] };
  lang: Lang;
};

export function ClarityMessageCard({
  kind,
  state,
  actions,
}: {
  kind: ResultKind;
  state: ClarityState;
  actions: CardActions;
}) {
  const { lang, app } = actions;

  if (kind === "thinking") return <ThinkingCard label={state.thinkingLabel || "Checking your account..."} />;
  if (kind === "progress") return <ProgressCard step={state.progressStep} />;
  if (kind === "investigation") return (
    <InvestigationCard
      state={state}
      lang={lang}
      onAction={actions.onAction}
      onFollow={actions.onFollow}
      onToggleEvidence={actions.onToggleEvidence}
      showEvidence={actions.showEvidence}
    />
  );
  if (kind === "knowledge") return <KnowledgeCard state={state} lang={lang} onFollow={actions.onFollow} onHandoff={actions.onHandoff} />;
  if (kind === "miss") return <MissCard state={state} lang={lang} onRetry={actions.onRetry} onHandoff={actions.onHandoff} onFollow={actions.onFollow} />;
  if (kind === "usage") return <UsageCard state={state} lang={lang} app={app} onFollow={actions.onFollow} onBuy={actions.onBuy} />;
  if (kind === "packages") return <PackagesCard state={state} lang={lang} app={app} onFollow={actions.onFollow} />;
  if (kind === "network") return <NetworkCard state={state} lang={lang} onFollow={actions.onFollow} onHandoff={actions.onHandoff} />;
  if (kind === "handoff") return <HandoffCard state={state} lang={lang} onViewCase={actions.onViewCase} />;
  if (kind === "success") return <SuccessCard state={state} lang={lang} app={app} onViewReceipt={actions.onViewReceipt} onFollow={actions.onFollow} />;
  if (kind === "receipt") return <ReceiptCard state={state} lang={lang} onViewReceipt={actions.onViewReceipt} />;
  return null;
}
