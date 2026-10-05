"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Dialog, useFocusTrap } from "@clarity/ui";
import { t, type Lang } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";
import { AppHeader } from "@/components/AppHeader";
import { expireSession, withSession } from "@/lib/session";
import { ClarityMessageCard } from "@/components/ClarityMessageCard";
import { VoiceSheet, useVoiceSupported } from "@/components/VoiceSheet";
import {
  Citations,
  ConfirmCard,
  FlowProgress,
  HandoffNotice,
  RefusedNotice,
  type FlowCopy,
} from "@/components/FlowCards";
import type { CardActions } from "@/components/ClarityMessageCard";
import {
  BASE,
  makeInitialState,
  fetchSuggestions,
  fetchTurn,
  streamTurn,
  type TurnStage,
  openCase,
  evaluateCase,
  fetchTimeline,
  routeQuestion,
  createProposal,
  applyFix,
  issueExplainReceipt,
  fetchReceipt,
  verifyReceipt,
  intentForQuestion,
  chargeForIntent,
  pickResultKind,
  saveThread,
  loadThreads,
  SUGGESTED,
  TOPIC_CATEGORIES,
  type ClarityState,
  type SuggestionChip,
  type FollowUp,
  type AppState,
} from "@/lib/clarityChat";
import type { ResultKind } from "@/lib/clarityChat";

// ─── inline translations (chat UI labels) ─────────────────────────────────────
const CHAT_I18N: Record<Lang, Record<string, string>> = {
  en: {
    clarityBrand: "Clarity", claritySubtitle: "Hutch AI Assistant",
    chatHi: "Hi {name}", chatHiAnon: "Hi there", howHelpToday: "How can I help you today?",
    chatSubtitle: "Ask me anything about your Hutch account.",
    askClarityAnything: "Ask Clarity anything...", speak: "Speak",
    stageMasked: "Protecting your details...", stageUnderstood: "Understanding your question...",
    stageChecked: "Checking your account...", stageComposed: "Writing the answer...",
    stageVerified: "Checking the answer...",
    newChat: "New chat", chatHistory: "History", empty: "Nothing here yet.",
    seeMoreTopics: "See more topics", seeFewerTopics: "Show fewer",
    browseTopics: "Browse topics",
    chatPrivate: "Don't share your OTP or password in this chat.",
    catMoney: "Money & Balance", catPacks: "Packages & Data", catReloads: "Reloads",
    catSubs: "Subscriptions", catNetwork: "Network", catEsim: "SIM & eSIM",
    catProtect: "Account Protection", catSupport: "Support",
    qBalance: "Why did my balance change?", qSub: "Why am I subscribed?",
    qTwice: "Why was my reload taken twice?", qSlow: "Why is my data slow?",
    qMissing: "Why didn't my reload arrive?", qEsim: "How do I convert to eSIM?",
    qActivate: "How do I activate a pack?", qFup: "Why has my speed reduced?",
    qPackIssue: "Why isn't my package working?", qPackMissing: "I paid but didn't receive my data",
    qRecommend: "Which package is best for me?", qExpiry: "What happens when my package expires?",
    qVasList: "What subscriptions are active?", qNetwork: "Is there a network problem?",
    qRefund: "What happened to my refund?", qCase: "What's happening with my case?",
    qPrevent: "How can I prevent unexpected charges?",
    confirmDisableTitle: "Disable {product}?",
    confirmBulletStop: "Stops the subscription from renewing",
    confirmBulletNoCharge: "No further daily charges",
    confirmBulletRefund: "Refunds the disputed amount to your balance",
    thisSubscription: "this subscription", cancel: "Cancel", confirm: "Confirm",
    fuSubs: "Show other subscriptions", fuPrevent: "Prevent this happening again",
    fuSupport: "Talk to support", fuFup: "Check my FUP", fuUsage: "Show remaining data",
    fuBuy: "Buy another package", fuNetwork: "Check network status",
    fuCompare: "Compare packages", fuDetails: "Show full details",
    fuActivate: "Activate package", fuDisable: "Disable this service",
  },
  si: {
    clarityBrand: "Clarity", claritySubtitle: "Hutch AI සහායක",
    chatHi: "ආයුබෝවන් {name}", chatHiAnon: "ආයුබෝවන්", howHelpToday: "අද මම උදව් කරන්නේ කෙසේද?",
    chatSubtitle: "ඔබේ Hutch ගිණුම ගැන ඕනෑම දෙයක් අසන්න.",
    askClarityAnything: "Clarity ගෙන් ඕනෑම දෙයක් අසන්න...", speak: "කතා කරන්න",
    stageMasked: "ඔබේ විස්තර ආරක්ෂා කරමින්...", stageUnderstood: "ඔබේ ප්‍රශ්නය තේරුම් ගනිමින්...",
    stageChecked: "ඔබේ ගිණුම පරීක්ෂා කරමින්...", stageComposed: "පිළිතුර ලියමින්...",
    stageVerified: "පිළිතුර පරීක්ෂා කරමින්...",
    newChat: "නව කතාබස්", chatHistory: "ඉතිහාසය", empty: "මෙතැන තවම කිසිවක් නැත.",
    seeMoreTopics: "තවත් මාතෘකා", seeFewerTopics: "අඩුවෙන් පෙන්වන්න",
    browseTopics: "මාතෘකා බලන්න",
    chatPrivate: "මෙම කතාබසේ OTP හෝ මුරපදය බෙදා නොගන්න.",
    catMoney: "මුදල් සහ ශේෂය", catPacks: "පැකේජ සහ දත්ත", catReloads: "රීලෝඩ්",
    catSubs: "දායකත්ව", catNetwork: "ජාලය", catEsim: "SIM සහ eSIM",
    catProtect: "ගිණුම් ආරක්ෂාව", catSupport: "සහාය",
    qBalance: "මගේ ශේෂය වෙනස් වුණේ ඇයි?", qSub: "මම දායක වුණේ ඇයි?",
    qSlow: "මගේ දත්ත මන්දගාමී ඇයි?", qFup: "මගේ වේගය අඩු වුණේ ඇයි?",
    qMissing: "මගේ රීලෝඩ් නොආවේ ඇයි?", qEsim: "eSIM එකට මාරු වෙන්නේ කොහොමද?",
    qPrevent: "අනපේක්ෂිත අයකිරීම් වළක්වන්නේ කොහොමද?",
    qVasList: "සක්‍රීය දායකත්ව මොනවාද?",
    cancel: "අවලංගු කරන්න", confirm: "තහවුරු කරන්න",
    thisSubscription: "මෙම දායකත්වය",
    confirmBulletStop: "දායකත්වය අලුත් වීම නවත්වයි",
    confirmBulletNoCharge: "තවත් දෛනික ගාස්තු නැත",
    confirmBulletRefund: "විවාදිත මුදල ශේෂයට ආපසු දෙයි",
    confirmDisableTitle: "{product} අක්‍රිය කරන්නද?",
    fuPrevent: "නැවත සිදු නොවීමට", fuSupport: "සහාය සමඟ කතා කරන්න",
  },
  ta: {
    clarityBrand: "Clarity", claritySubtitle: "Hutch AI உதவியாளர்",
    chatHi: "வணக்கம் {name}", chatHiAnon: "வணக்கம்", howHelpToday: "இன்று நான் எப்படி உதவட்டும்?",
    chatSubtitle: "உங்கள் Hutch கணக்கு பற்றி எதையும் கேளுங்கள்.",
    askClarityAnything: "Clarity இடம் எதையும் கேளுங்கள்...", speak: "பேசு",
    stageMasked: "உங்கள் விவரங்களைப் பாதுகாக்கிறேன்...", stageUnderstood: "உங்கள் கேள்வியைப் புரிந்துகொள்கிறேன்...",
    stageChecked: "உங்கள் கணக்கைச் சரிபார்க்கிறேன்...", stageComposed: "பதிலை எழுதுகிறேன்...",
    stageVerified: "பதிலைச் சரிபார்க்கிறேன்...",
    newChat: "புதிய அரட்டை", chatHistory: "வரலாறு", empty: "இங்கே இன்னும் ஒன்றுமில்லை.",
    seeMoreTopics: "மேலும் தலைப்புகள்", seeFewerTopics: "குறைவாகக் காட்டு",
    browseTopics: "தலைப்புகளைப் பார்",
    chatPrivate: "இந்த அரட்டையில் OTP அல்லது கடவுச்சொல்லைப் பகிர வேண்டாம்.",
    catMoney: "பணம் & இருப்பு", catPacks: "பேக்குகள் & தரவு", catReloads: "ரீலோட்கள்",
    catSubs: "சந்தாக்கள்", catNetwork: "நெட்வொர்க்", catEsim: "SIM & eSIM",
    catProtect: "கணக்குப் பாதுகாப்பு", catSupport: "ஆதரவு",
    qBalance: "என் இருப்பு ஏன் மாறியது?", qSub: "நான் ஏன் சந்தா செய்தேன்?",
    qSlow: "என் தரவு ஏன் மெதுவாக உள்ளது?", qFup: "என் வேகம் ஏன் குறைந்தது?",
    qMissing: "என் ரீலோட் ஏன் வரவில்லை?", qEsim: "eSIM-க்கு எப்படி மாறுவது?",
    qPrevent: "எதிர்பாராத கட்டணங்களை எப்படித் தடுப்பது?",
    qVasList: "எந்த சந்தாக்கள் செயலில் உள்ளன?",
    cancel: "ரத்துசெய்", confirm: "உறுதிசெய்",
    thisSubscription: "இந்த சந்தா",
    confirmBulletStop: "சந்தா புதுப்பிப்பை நிறுத்தும்",
    confirmBulletNoCharge: "மேலும் தினசரி கட்டணம் இல்லை",
    confirmBulletRefund: "விவாதத் தொகையை இருப்பிற்குத் திருப்பும்",
    confirmDisableTitle: "{product} நிறுத்தவா?",
    fuPrevent: "மீண்டும் நடக்காமல் தடு", fuSupport: "ஆதரவிடம் பேசு",
  },
};

function tl(lang: Lang, key: string): string {
  return CHAT_I18N[lang]?.[key] ?? CHAT_I18N.en[key] ?? key;
}

function markFor(id: string): string {
  if (/balance|money|refund/i.test(id)) return "wallet";
  if (/pack|activate|expiry/i.test(id)) return "box";
  if (/reload|missing|twice/i.test(id)) return "reload";
  if (/sub|vas/i.test(id)) return "repeat";
  if (/slow|fup|network/i.test(id)) return "signal";
  if (/esim|sim/i.test(id)) return "sim";
  if (/prevent|protect/i.test(id)) return "shield";
  if (/support|case/i.test(id)) return "headset";
  if (/recommend/i.test(id)) return "star";
  return "dot";
}

function MarkIcon({ name }: { name: string }) {
  const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <span className="dial-mark" aria-hidden="true">
      <svg width={16} height={16} viewBox="0 0 24 24" {...stroke}>
        {name === "wallet" ? <path d="M4 8.5h16v9H4zM4 8.5 6.5 5h9L18 8.5M16 13h2" /> : null}
        {name === "box" ? <path d="M4 8l8-4 8 4v9l-8 4-8-4zM4 8l8 4 8-4M12 12v9" /> : null}
        {name === "reload" ? <path d="M19 12a7 7 0 1 1-2-4.9M19 4.5V8h-3.5" /> : null}
        {name === "repeat" ? <path d="M7 7h9l-2-2M17 17H8l2 2M7 11v6M17 7v6" /> : null}
        {name === "signal" ? <path d="M5 18v-3M9 18v-6M13 18V9M17 18V6" /> : null}
        {name === "sim" ? <path d="M8 3.5h6l4 4V20H8zM10 13h6M10 17h4" /> : null}
        {name === "shield" ? <path d="M12 3.5 19 6.2v5.2c0 4-2.8 6.8-7 8.1-4.2-1.3-7-4.1-7-8.1V6.2z" /> : null}
        {name === "headset" ? <path d="M5 13a7 7 0 0 1 14 0M5 13v4.5A1.5 1.5 0 0 0 6.5 19H8v-6H6.5A1.5 1.5 0 0 0 5 14.5M19 13v4.5a1.5 1.5 0 0 1-1.5 1.5H16v-6h1.5A1.5 1.5 0 0 1 19 14.5" /> : null}
        {name === "star" ? <path d="m12 4 2.1 4.6 5 .6-3.7 3.4.9 5L12 15.4 7.7 17.6l.9-5L4.9 9.2l5-.6z" /> : null}
        {name === "dot" ? <circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none" /> : null}
      </svg>
    </span>
  );
}

function DialList({
  label,
  tall,
  children,
}: {
  label: string;
  tall?: boolean;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const frame = useRef(0);
  const layout = useCallback(() => {
    const root = ref.current;
    if (!root) return;
    const box = root.getBoundingClientRect();
    const mid = box.top + box.height / 2;
    const reach = box.height / 2 || 1;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    for (const node of Array.from(root.children)) {
      const el = node as HTMLElement;
      const card = el.getBoundingClientRect();
      const signed = (card.top + card.height / 2 - mid) / reach;
      const dist = Math.min(Math.abs(signed), 1);
      if (reduce) {
        el.style.transform = "none";
        el.style.opacity = "1";
        continue;
      }
      // The previous wheel. A circular ease only softens the moment a row leaves the middle.
      const sign = signed < 0 ? -1 : signed > 0 ? 1 : 0;
      const circ = 1 - Math.sqrt(Math.max(0, 1 - dist * dist));
      const travel = dist * 0.85 + circ * 0.15;
      const tilt = (-sign * travel * 46).toFixed(2);
      const depth = (-travel * 150).toFixed(1);
      const scale = (1 - travel * 0.38).toFixed(3);
      el.style.transform = `rotateX(${tilt}deg) translateZ(${depth}px) scale(${scale})`;
      el.style.opacity = (1 - travel * 0.42).toFixed(3);
    }
  }, []);
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const onScroll = () => {
      cancelAnimationFrame(frame.current);
      frame.current = requestAnimationFrame(layout);
    };
    layout();
    root.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      root.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(frame.current);
    };
  }, [layout, children]);
  return (
    <div ref={ref} className={tall ? "dial-wheel dial-wheel-tall" : "dial-wheel dial-wheel-short"} role="list" aria-label={label}>
      {children}
    </div>
  );
}

const toolBtnStyle = {
  width: 36,
  height: 36,
  borderRadius: 999,
  border: "1px solid var(--line)",
  background: "rgb(var(--c-surface-2))",
  cursor: "pointer",
  color: "var(--ink)",
  display: "grid",
  placeItems: "center",
  flexShrink: 0,
  padding: 0,
} as const;

function HistoryIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v5l3 2" strokeLinecap="round" />
    </svg>
  );
}

function TagIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M20 13.5 12.5 21a2 2 0 0 1-2.8 0L3 14.3V4h10.3L20 10.7a2 2 0 0 1 0 2.8z" />
      <circle cx="7.5" cy="7.5" r="1.2" fill="currentColor" />
    </svg>
  );
}

/** Server stage code -> the i18n key the waiting card shows (A5). */
const STAGE_LABELS: Record<TurnStage, string> = {
  masked: "stageMasked",
  understood: "stageUnderstood",
  checked: "stageChecked",
  composed: "stageComposed",
  verified: "stageVerified",
};

// ─── component ─────────────────────────────────────────────────────────────────

export default function ClarityPage() {
  const { lang } = useLanguage();
  const router = useRouter();

  const [cs, setCs] = useState<ClarityState>(makeInitialState);
  // The signed-in customer's own account, from `GET /v1/me/app`.
  //
  // It feeds the turn's `snapshot` and the suggestion chips. It no longer
  // decides anything: the eligibility heuristic that used to read these fields
  // and gate the rule engine was removed in A2, so a stale or empty account can
  // no longer suppress a decision the backend would have made.
  const [app, setApp] = useState<AppState>({});
  // A question asked before the account has loaded used to be answered from
  // an empty account: a customer under a fair-use cap was told they were not
  // capped. `ask` waits on this promise and reads the account from the ref,
  // which a render-time closure would leave stale.
  const appRef = useRef<AppState>({});
  const appReady = useRef<Promise<void> | null>(null);

  useEffect(() => {
    let cancelled = false;
    appReady.current = (async () => {
      try {
        // The chat is for a signed-in customer: without a session every turn
        // is refused, so go and get one instead of failing turn by turn.
        //
        // The session is an HttpOnly cookie (B4), so there is nothing to check
        // before asking. The API's answer is the check: a 401 means no usable
        // session, whether the cookie is missing, expired or revoked, and this
        // page no longer has to guess which.
        const res = await fetch(`${BASE}/v1/me/app`, withSession());
        if (res.status === 401) return expireSession();
        if (!res.ok) return;
        const data = (await res.json()) as AppState;
        appRef.current = data;
        if (!cancelled) setApp(data);
      } catch {
        // No account state means the heuristic below stays conservative, which
        // is the safe direction: it asks rather than inventing an answer.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const [input, setInput] = useState("");
  const [topicOpen, setTopicOpen] = useState(false);
  const [topicTag, setTopicTag] = useState<string | null>(null);
  const [topicCategory, setTopicCategory] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  // The history drawer is modal, so it gets the same treatment as a dialog:
  // focus moves in, Tab stays inside, Escape closes it and focus returns to
  // the button that opened it (E6). It had none of that, and no close button
  // either, so the only way out was a mouse click on the scrim.
  const historyPanel = useRef<HTMLDivElement>(null);
  useFocusTrap(historyPanel, showHistory, () => setShowHistory(false));
  const [showEvidence, setShowEvidence] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState<{ title: string; bullets: string[]; outcome: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const voiceSupported = useVoiceSupported();

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  // load suggestions on mount
  useEffect(() => {
    fetchSuggestions(lang, app).then((suggestions) => {
      setCs((s) => ({ ...s, suggestions }));
    });
  }, [lang]); // eslint-disable-line react-hooks/exhaustive-deps

  // scroll to bottom when messages change
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [cs.messages.length]);

  // auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 96) + "px";
  }, [input]);

  const update = useCallback((patch: Partial<ClarityState>) => {
    setCs((s) => ({ ...s, ...patch }));
  }, []);

  // ─── ask flow ──────────────────────────────────────────────────────────────

  async function ask(questionKey: string | null, freeText: string, intentOverride: string | null = null) {
    const typed = freeText || tl(lang, questionKey ?? "") || questionKey || "";
    if (!typed.trim() || busy) return;
    setBusy(true);
    setInput("");

    const newMsg: ClarityState["messages"][number] = { role: "user", text: typed };
    setCs((s) => ({
      ...s,
      messages: [...s.messages, newMsg],
      question: typed,
      progressStep: -1,
      thinkingLabel: tl(lang, "askClarityAnything"),
    }));

    // The waiting card goes up at once, with no invented label on it: what it
    // says now comes from the server as each pipeline step completes (A5).
    // This used to be a `setTimeout` with a hardcoded English string, so it
    // reported nothing and a hung turn looked exactly like a slow one.
    setCs((s) => ({
      ...s,
      messages: [...s.messages, { role: "clarity", kind: "thinking" as ResultKind }],
      thinkingLabel: tl(lang, "stageUnderstood"),
    }));

    const onStage = (stage: TurnStage) => {
      const label = STAGE_LABELS[stage];
      if (label) setCs((s) => ({ ...s, thinkingLabel: tl(lang, label) }));
    };

    try {
      // turn classification
      const facts = {
        case_id: cs.caseId,
        chat_intent: cs.chatIntent,
        product: cs.contextProduct,
        amount_lkr: cs.contextAmount ?? cs.decision?.amount_lkr,
      };
      // `cs.caseId` at the top level is what puts this turn on the stateful
      // pipeline. Passing it only inside `facts`, as this did until C05, left
      // every turn stateless and no flow ever ran (C05 devlog).
      await appReady.current;
      const account = appRef.current;
      const turn = await streamTurn(
        typed,
        lang,
        intentOverride,
        facts,
        account,
        cs.caseId,
        onStage
      );

      // The composed answer. Approved template or grounded quote, already
      // through the verifier, and until now discarded (A1).
      const reply = turn?.reply?.trim() || undefined;

      let clientIntent = turn?.client_intent ?? turn?.intake?.client_intent ?? intentForQuestion(questionKey, typed);
      const route = turn?.route ?? turn?.intake?.route ?? "account";
      const followUps: FollowUp[] = turn?.follow_ups ?? [];
      const articles = turn?.articles ?? null;
      const chatIntent = turn?.intake?.intent ?? intentOverride ?? null;

      const update1: Partial<ClarityState> = { chatIntent, followUps };
      // The flow's own output, rendered rather than discarded (C05).
      if (turn?.state) update1.flow = turn.state;
      if (turn?.citations) update1.citations = turn.citations;
      if (turn?.verifier) update1.verifier = turn.verifier;
      if (turn?.handoff) update1.handoff = turn.handoff;
      if (turn?.proposal_id) update1.planId = turn.proposal_id;
      update1.refused = Boolean(turn?.refused);
      if (turn?.intake?.slots?.product) update1.contextProduct = turn.intake.slots.product;
      if (turn?.intake?.slots?.amount_lkr) update1.contextAmount = turn.intake.slots.amount_lkr;
      if (articles) update1.articles = articles;

      // knowledge route
      if (route === "knowledge" || clientIntent === "knowledge") {
        let arts = articles;
        if (!arts) {
          try {
            const r = await routeQuestion(typed, lang);
            arts = r.articles ?? [];
          } catch { arts = []; }
        }
        setCs((s) => {
          const msgs = s.messages.filter((m) => !(m.role === "clarity" && (m.kind === "thinking" || m.kind === "progress")));
          return {
            ...s, ...update1, articles: arts, mode: "knowledge", intent: "knowledge",
            messages: [...msgs, { role: "clarity", kind: "knowledge" as ResultKind, reply }],
          };
        });
        setBusy(false);
        return;
      }

      // handoff route
      if (route === "handoff" || clientIntent === "human") {
        await runEvaluate("human", null, true, update1, reply);
        setBusy(false);
        return;
      }

      // A stateful flow can evaluate the existing case and create its pending
      // plan during this turn. Opening another case below would separate the
      // displayed plan from cs.caseId, so Confirm would submit a valid plan to
      // the wrong case and be refused. Keep the existing case and render the
      // flow-owned confirmation artefact.
      if (turn?.proposal_id && cs.caseId) {
        setCs((s) => {
          const msgs = s.messages.filter(
            (m) => !(m.role === "clarity" && (m.kind === "thinking" || m.kind === "progress")),
          );
          return {
            ...s,
            ...update1,
            caseId: cs.caseId,
            mode: "result",
            messages: [...msgs, { role: "clarity", kind: "confirm" as ResultKind }],
          };
        });
        setBusy(false);
        return;
      }

      // No client-side eligibility gate (A2): rules decide (I1). When no rule
      // matches, `decision/policy.py` answers HANDOFF with `NO_CAUSE_FOUND`,
      // which `pickResultKind` renders as the handoff card (I2).

      // progress steps
      setCs((s) => {
        const msgs = s.messages.filter((m) => !(m.role === "clarity" && m.kind === "thinking"));
        return { ...s, ...update1, messages: [...msgs, { role: "clarity", kind: "progress" as ResultKind }], progressStep: 0 };
      });

      const chargeRef = chargeForIntent(clientIntent, account.activity ?? []);
      await runEvaluate(clientIntent, chargeRef, false, update1, reply);
    } catch (err) {
      console.error(err);
      setCs((s) => {
        const msgs = s.messages.filter((m) => !(m.role === "clarity" && (m.kind === "thinking" || m.kind === "progress")));
        return { ...s, messages: [...msgs, { role: "clarity", kind: "miss" as ResultKind }] };
      });
    }
    setBusy(false);
  }

  async function runEvaluate(
    clientIntent: string,
    chargeRef: string | null,
    wantsHuman: boolean,
    patch: Partial<ClarityState>,
    reply?: string
  ) {
    // step 1 - open case
    setCs((s) => ({ ...s, progressStep: 1 }));
    const opened = await openCase(appRef.current.msisdn ?? "0781234567", lang, chargeRef, wantsHuman);
    const caseId = opened.case_id;

    // step 2+3 - evaluate + timeline
    setCs((s) => ({ ...s, caseId, progressStep: 2 }));
    const [decision, timeline] = await Promise.all([
      evaluateCase(caseId, wantsHuman),
      fetchTimeline(caseId),
    ]);
    setCs((s) => ({ ...s, progressStep: 3 }));

    const mode = decision.outcome === "HANDOFF" || wantsHuman ? "human" : "result";
    if (decision.product) patch.contextProduct = decision.product;
    if (decision.amount_lkr) patch.contextAmount = decision.amount_lkr;

    const newState: Partial<ClarityState> = { ...patch, decision, timeline, caseId, mode };
    setCs((s) => {
      const kind = pickResultKind({ ...s, ...newState } as ClarityState);
      const msgs = s.messages.filter((m) => !(m.role === "clarity" && (m.kind === "thinking" || m.kind === "progress")));
      const answered: ClarityState["messages"] = [...msgs, { role: "clarity", kind, reply }];
      const saved = saveThread({ ...s, ...newState, messages: answered });
      void saved;
      return { ...s, ...newState, messages: answered };
    });
  }

  // ─── card actions ──────────────────────────────────────────────────────────

  async function handleGetReceipt() {
    if (!cs.caseId || busy) return;
    setBusy(true);
    try {
      const r = await issueExplainReceipt(cs.caseId);
      const full = await fetchReceipt(r.receipt_id);
      setCs((s) => ({
        ...s,
        receiptDoc: full,
        receiptCheck: { ok: true },
        messages: [...s.messages, { role: "clarity", kind: "receipt" as ResultKind }],
      }));
    } catch (e) { console.error(e); }
    setBusy(false);
  }

  function handleConfirmFix() {
    const d = cs.decision;
    const product = d?.product ?? cs.contextProduct ?? tl(lang, "thisSubscription");
    setPendingConfirm({
      title: tl(lang, "confirmDisableTitle").replace("{product}", product),
      bullets: [
        tl(lang, "confirmBulletStop"),
        tl(lang, "confirmBulletNoCharge"),
        tl(lang, "confirmBulletRefund"),
      ],
      outcome: d?.outcome ?? "ONE_TAP_FIX",
    });
  }

  async function doConfirm() {
    if (!cs.caseId || !pendingConfirm || busy) return;
    setBusy(true);
    setPendingConfirm(null);
    try {
      // A server-driven conversation flow already created the plan shown in
      // ConfirmCard. Creating another plan here can make the visible button
      // execute a different proposal, or fail while the original remains
      // pending. Only legacy result cards need a proposal created on tap.
      const planId = cs.planId ?? (await createProposal(cs.caseId)).plan_id;
      const done = await applyFix(cs.caseId, planId, pendingConfirm.outcome);
      const [verified, full] = await Promise.all([
        verifyReceipt(done.receipt_id),
        fetchReceipt(done.receipt_id),
      ]);
      setCs((s) => ({
        ...s,
        planId: null,
        receiptDoc: full,
        receiptCheck: verified,
        mode: "resolved",
        followUps: [
          { id: "prevent", i18n_key: "fuPrevent", intent: "PREVENT_CHARGES" },
          { id: "support", i18n_key: "fuSupport", intent: "HANDOFF" },
        ],
        messages: [
          ...s.messages,
          { role: "clarity", kind: "success" as ResultKind },
          { role: "clarity", kind: "receipt" as ResultKind },
        ],
      }));
    } catch (e) {
      console.error(e);
      setCs((s) => ({
        ...s,
        messages: [...s.messages, { role: "clarity", kind: "miss" as ResultKind }],
      }));
    }
    setBusy(false);
  }

  async function handleStaffApprove() {
    if (!cs.caseId || busy) return;
    setBusy(true);
    try {
      const proposal = await createProposal(cs.caseId);
      setCs((s) => ({
        ...s,
        planId: proposal.plan_id,
        mode: "human",
        followUps: [{ id: "support", i18n_key: "fuSupport", intent: "HANDOFF" }],
        messages: [...s.messages, { role: "clarity", kind: "handoff" as ResultKind }],
      }));
    } catch (e) { console.error(e); }
    setBusy(false);
  }

  function handleFollow(fu: FollowUp) {
    if (fu.intent === "HANDOFF") {
      ask(null, tl(lang, "fuSupport"), "human");
    } else {
      ask(fu.i18n_key, tl(lang, fu.i18n_key), fu.intent ?? null);
    }
  }

  function newChat() {
    saveThread(cs);
    setCs((s) => ({ ...makeInitialState(), suggestions: s.suggestions }));
    setTopicOpen(false);
    setTopicTag(null);
    fetchSuggestions(lang, app).then((suggestions) => setCs((s) => ({ ...s, suggestions })));
  }

  // Every string from the shared i18n package (C05 scope), so a translator
  // changes one file rather than hunting through components. `t` falls back to
  // English and then to the key, so a missing string is visible rather than
  // rendering as a blank control.
  const flowCopy: FlowCopy = {
    flowLabel: (flow) => t(lang, `flow.${flow}`),
    stateLabel: (state) => t(lang, `state.${state}`),
    confirmTitle: t(lang, "confirm.title"),
    confirmBody: t(lang, "confirm.body"),
    confirmCta: t(lang, "confirm.cta"),
    confirmPending: t(lang, "confirm.pending"),
    sourcesTitle: t(lang, "sources.title"),
    sourcesNote: t(lang, "sources.note"),
    handoffTitle: t(lang, "handoff.title"),
    handoffBody: (queue) => t(lang, "handoff.body", { queue }),
    refusedTitle: t(lang, "refused.title"),
    refusedBody: t(lang, "refused.body"),
    receiptCta: t(lang, "receipt.cta"),
    stepOf: (position, total) => t(lang, "flow.step", { position, total }),
  };

  const cardActions: CardActions = {
    onAction: (a) => {
      if (a === "getReceipt") handleGetReceipt();
      if (a === "confirmFix") handleConfirmFix();
      if (a === "staffApprove") handleStaffApprove();
      if (a === "handoff") ask(null, tl(lang, "fuSupport"), "human");
    },
    onFollow: handleFollow,
    onToggleEvidence: () => setShowEvidence((v) => !v),
    onViewCase: () => router.push("/cases"),
    onViewReceipt: () => {
      const id = cs.receiptDoc?.receipt_id ?? cs.receiptDoc?.id;
      if (id) router.push(`/receipt/${id}`);
    },
    onRetry: () => ask("qBalance", tl(lang, "qBalance")),
    onBuy: () => ask("qRecommend", tl(lang, "qRecommend"), "PACK_RECOMMEND"),
    onHandoff: () => ask(null, tl(lang, "fuSupport"), "human"),
    showEvidence,
    app,
    lang,
  };

  // ─── suggestion chips ──────────────────────────────────────────────────────

  const chips = (() => {
    const seen = new Set<string>();
    const rows: SuggestionChip[] = [];
    for (const chip of cs.suggestions) {
      const id = chip.i18n_key || chip.id;
      if (seen.has(id)) continue;
      seen.add(id);
      rows.push(chip);
    }
    for (const item of SUGGESTED) {
      if (seen.has(item.key)) continue;
      seen.add(item.key);
      rows.push({ id: item.key, i18n_key: item.key, intent: item.chatIntent, reason: "default" });
    }
    return rows;
  })();

  // ─── render ────────────────────────────────────────────────────────────────

  const isEmpty = cs.messages.length === 0;
  const threads = loadThreads();

  return (
    <>
      <div style={{ position: "fixed", inset: 0, display: "flex", flexDirection: "column", background: "rgb(var(--c-surface-2))", overflow: "hidden" }}>

        <AppHeader />

        <div style={{ flex: 1, minHeight: 0, position: "relative", display: "flex", flexDirection: "column" }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "8px 14px", borderBottom: "1px solid var(--line)",
          background: "rgb(var(--c-surface))", flexShrink: 0,
        }}>
          <button
            type="button"
            onClick={() => router.push("/")}
            aria-label="Back"
            style={{
              width: 36, height: 36, borderRadius: 999, border: "1px solid var(--line)",
              background: "rgb(var(--c-surface-2))", cursor: "pointer", color: "var(--ink)",
              display: "grid", placeItems: "center", flexShrink: 0,
            }}
          >
            <span aria-hidden="true">←</span>
          </button>
          <span style={{ flex: 1 }} />
          <button
            type="button"
            onClick={() => setShowHistory(true)}
            aria-label={tl(lang, "chatHistory")}
            style={toolBtnStyle}
          >
            <HistoryIcon />
          </button>
          <button type="button" onClick={newChat} aria-label={tl(lang, "newChat")} style={toolBtnStyle}>
            <span aria-hidden="true" style={{ fontSize: 22, lineHeight: 1 }}>+</span>
          </button>
        </div>

        {/* ── Scrollable body ── */}
        <div ref={bodyRef} style={{
          flex: 1, minHeight: 0, overflowY: isEmpty ? "hidden" : "auto",
          padding: "0 16px 12px",
          maxWidth: 640, margin: "0 auto", width: "100%",
          display: "flex", flexDirection: "column",
        }}>

          {isEmpty ? (
            /* ── Welcome ── */
            <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{ textAlign: "center", padding: "8px 8px 4px", flexShrink: 0 }}>
                <img src="/icon-192.png" alt="" className="chat-logo-bounce" width={72} height={72} />
                <h1 style={{ fontSize: "clamp(22px,5.5vw,28px)", fontWeight: 800, letterSpacing: "-.03em", margin: "10px 0 4px", color: "var(--ink)" }}>
                  {app.name
                    ? tl(lang, "chatHi").replace("{name}", app.name)
                    : tl(lang, "chatHiAnon")}
                </h1>
                <p style={{ fontSize: 19, fontWeight: 700, margin: "0 0 6px", color: "rgb(var(--c-fg-muted))" }}>{tl(lang, "howHelpToday")}</p>
                <p style={{ fontSize: 14, color: "var(--muted)", margin: "0 0 12px", maxWidth: 280, marginLeft: "auto", marginRight: "auto" }}>
                  {tl(lang, "chatSubtitle")}
                </p>
              </div>

              <DialList label="Suggested questions" tall>
                {chips.map((chip) => {
                  const label = chip.label ?? tl(lang, chip.i18n_key) ?? chip.id;
                  return (
                    <button
                      key={chip.id}
                      type="button"
                      role="listitem"
                      className="dial-card"
                      onClick={() => ask(chip.i18n_key, label, chip.intent ?? null)}
                    >
                      <MarkIcon name={markFor(chip.i18n_key || chip.id)} />
                      {label}
                    </button>
                  );
                })}
              </DialList>
            </div>
          ) : (
            /* ── Transcript ── */
            <div
              // Polite, not assertive: a reply should be read when the screen
              // reader finishes what it is saying, not interrupt the customer
              // mid-sentence. Without this, an answer that arrives while focus
              // is in the composer is never announced at all (C05 scope).
              role="log"
              aria-live="polite"
              aria-label={t(lang, "chat.transcript")}
              style={{ paddingTop: 16, display: "grid", gap: 12 }}
            >
              {cs.messages.map((msg, i) => {
                if (msg.role === "user") {
                  return (
                    <div key={i} style={{ display: "flex", justifyContent: "flex-end" }}>
                      <div style={{
                        background: "var(--orange-strong)", color: "rgb(var(--c-on-primary))", borderRadius: "18px 18px 4px 18px",
                        padding: "10px 16px", maxWidth: "80%", fontSize: 15, fontWeight: 500,
                      }}>
                        {msg.text}
                      </div>
                    </div>
                  );
                }
                const isLast = i === cs.messages.length - 1;
                return (
                  <div key={i} style={{ display: "flex", justifyContent: "flex-start" }}>
                    <div style={{ maxWidth: "90%", width: "100%", display: "grid", gap: 8 }}>
                      {/* The flow artefacts go on the newest card only. On
                          every card they would repeat the same journey state
                          down the whole transcript, and a screen reader would
                          read it once per turn. */}
                      {isLast && cs.flow ? <FlowProgress flow={cs.flow} copy={flowCopy} /> : null}
                      {/* What Clarity actually said. Kept on the message, so
                          scrolling back still shows the answer rather than
                          just the card it came with. */}
                      {msg.reply ? (
                        <div
                          data-testid="clarity-reply"
                          style={{
                            background: "rgb(var(--c-surface))",
                            border: "1px solid var(--line)",
                            borderRadius: "18px 18px 18px 4px",
                            padding: "10px 16px",
                            fontSize: 15,
                            lineHeight: 1.5,
                            color: "var(--ink)",
                            whiteSpace: "pre-wrap",
                          }}
                        >
                          {msg.reply}
                        </div>
                      ) : null}
                      <ClarityMessageCard kind={msg.kind} state={cs} actions={cardActions} />
                      {isLast && cs.citations.length > 0 ? (
                        <Citations citations={cs.citations} copy={flowCopy} />
                      ) : null}
                      {isLast && cs.refused ? <RefusedNotice copy={flowCopy} /> : null}
                      {isLast && cs.planId && !cs.receiptDoc ? (
                        <ConfirmCard
                          planId={cs.planId}
                          amount={cs.decision?.amount_lkr != null ? String(cs.decision.amount_lkr) : null}
                          summary={cs.decision?.explanation ?? null}
                          busy={busy}
                          // The server's own confirm step, through the same
                          // action the existing card uses. Nothing here marks
                          // a plan done locally: the confirmation token is
                          // minted server side (ADR-0007).
                          onConfirm={() => cardActions.onAction("confirmFix")}
                          copy={flowCopy}
                        />
                      ) : null}
                      {isLast && cs.handoff?.handoff ? (
                        <HandoffNotice handoff={cs.handoff} copy={flowCopy} />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Composer ── */}
        <div style={{
          flexShrink: 0, zIndex: 35,
          background: "rgb(var(--c-surface))",
          borderTop: "1px solid var(--line)",
          padding: "8px 16px calc(28px + env(safe-area-inset-bottom, 0px))",
        }}>
          {topicOpen ? (
            <div className="topic-list" role="listbox" aria-label={tl(lang, "browseTopics")}>
              {TOPIC_CATEGORIES.map((cat) => {
                const label = tl(lang, cat.i18n);
                const selected = topicTag === label;
                return (
                  <button
                    key={cat.id}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className="dial-card"
                    style={{ borderColor: selected ? "var(--orange)" : undefined }}
                    onClick={() => {
                      setTopicTag(label);
                      setTopicCategory(cat.id);
                      setTopicOpen(false);
                    }}
                  >
                    <MarkIcon name={markFor(cat.id)} />
                    {label}
                  </button>
                );
              })}
            </div>
          ) : null}
          <div style={{
            maxWidth: 640, margin: "0 auto", display: "flex", alignItems: "center", gap: 8,
            background: "rgb(var(--c-surface))", border: "1px solid var(--line)", borderRadius: 22,
            padding: "8px 10px", boxShadow: "0 8px 24px rgba(24,24,27,.08)",
          }}>
            <button
              type="button"
              aria-label={tl(lang, "browseTopics")}
              aria-expanded={topicOpen}
              onClick={() => setTopicOpen((open) => !open)}
              style={{
                width: 36, height: 36, borderRadius: 999, border: "1px solid var(--line)",
                background: topicOpen ? "var(--orange-soft)" : "rgb(var(--c-surface-2))",
                color: "var(--orange-ink)", cursor: "pointer", flexShrink: 0,
                display: "grid", placeItems: "center",
              }}
            >
              <TagIcon />
            </button>
            {voiceSupported ? (
              <button type="button" className="composer-mic" aria-label={tl(lang, "speak")} aria-haspopup="dialog" onClick={() => setVoiceOpen(true)} disabled={busy} style={{
                width: 36, height: 36, border: 0, background: "var(--orange-soft)", color: "var(--orange-ink)",
                cursor: busy ? "not-allowed" : "pointer", padding: 0,
                flexShrink: 0, borderRadius: 999,
                display: "grid", placeItems: "center",
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="9" y="3" width="6" height="11" rx="3" />
                  <path d="M5 11a7 7 0 0 0 14 0" />
                  <path d="M12 18v3" />
                </svg>
              </button>
            ) : null}

            <div style={{ flex: 1, minWidth: 0, display: "flex", flexWrap: "nowrap", alignItems: "center", gap: 6 }}>
              {topicTag ? (
                <span style={{
                  display: "inline-flex", alignItems: "center", gap: 4, flexShrink: 0, maxWidth: 128,
                  borderRadius: 999, padding: "4px 8px 4px 10px",
                  background: "var(--orange-soft)", color: "var(--orange-ink)",
                  fontSize: 12, fontWeight: 700,
                }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{topicTag}</span>
                  <button
                    type="button"
                    aria-label="Remove topic"
                    onClick={() => setTopicTag(null)}
                    style={{ border: 0, background: "transparent", color: "inherit", cursor: "pointer", font: "inherit", padding: 0 }}
                  >
                    ×
                  </button>
                </span>
              ) : null}
              <textarea
                className="composer-field"
                ref={textareaRef}
                rows={1}
                aria-label={tl(lang, "askClarityAnything")}
                placeholder={tl(lang, "askClarityAnything")}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    const text = topicTag ? `${topicTag}: ${input}`.trim() : input;
                    ask(null, text);
                  }
                }}
                style={{
                  flex: 1, minWidth: 0, border: 0, resize: "none", fontFamily: "inherit", fontSize: 15,
                  minHeight: 24, maxHeight: 96, padding: "8px 4px", background: "transparent",
                  outline: "none", color: "var(--ink)", lineHeight: 1.4,
                }}
              />
            </div>

            <button
              type="button"
              className="composer-send"
              onClick={() => {
                const text = topicTag ? `${topicTag}: ${input}`.trim() : input;
                ask(null, text);
              }}
              disabled={(!input.trim() && !topicTag) || busy}
              style={{
                width: 40, height: 40, borderRadius: 999, border: 0,
                background: (input.trim() || topicTag) && !busy ? "var(--orange-strong)" : "rgb(var(--c-border))",
                color: (input.trim() || topicTag) && !busy ? "rgb(var(--c-surface))" : "rgb(var(--c-fg-subtle))",
                fontSize: 16, fontWeight: 700,
                cursor: (input.trim() || topicTag) && !busy ? "pointer" : "not-allowed",
                display: "grid", placeItems: "center", flexShrink: 0, transition: "background .15s",
              }}
              aria-label="Send"
            >↑</button>
          </div>
          <p className="chat-private">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <rect x="6" y="10" width="12" height="9" rx="2" />
              <path d="M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10" strokeLinecap="round" />
            </svg>
            {tl(lang, "chatPrivate")}
          </p>
        </div>
        {showHistory && (
          <div
            className="history-scrim"
            role="presentation"
            onClick={(event) => {
              if (event.target === event.currentTarget) setShowHistory(false);
            }}
          >
            <div
              ref={historyPanel}
              className="history-panel"
              role="dialog"
              aria-modal="true"
              aria-labelledby="chat-history-title"
              tabIndex={-1}
            >
              <div style={{
                padding: "16px 16px 12px", borderBottom: "1px solid var(--line)",
                display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
              }}>
                <h2 id="chat-history-title" style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>
                  {tl(lang, "chatHistory")}
                </h2>
                <button
                  type="button"
                  data-autofocus
                  aria-label={tl(lang, "cancel")}
                  onClick={() => setShowHistory(false)}
                  style={{
                    border: 0, background: "transparent", cursor: "pointer", fontFamily: "inherit",
                    fontSize: 22, lineHeight: 1, color: "var(--muted)", padding: "0 4px",
                  }}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </div>
              {threads.length === 0 ? (
                <p style={{ padding: 16, fontSize: 14, color: "var(--muted)" }}>{tl(lang, "empty")}</p>
              ) : (
                threads.map((th) => (
                  <button key={th.id} onClick={() => {
                    setCs((s) => ({
                      ...s,
                      ...(th.snapshot as Partial<ClarityState>),
                      messages: th.messages,
                      threadId: th.id,
                    }));
                    setShowHistory(false);
                  }} style={{
                    display: "flex", flexDirection: "column", gap: 2, textAlign: "left",
                    border: 0, borderBottom: "1px solid var(--line)", background: "transparent",
                    padding: "14px 16px", cursor: "pointer", fontFamily: "inherit",
                  }}>
                    <span style={{ fontSize: 14, fontWeight: 600 }}>{th.title}</span>
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>{th.status}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        )}
        </div>
      </div>

      {/* ── Confirm modal ── */}
      {voiceOpen && (
        <VoiceSheet
          lang={lang}
          onClose={() => setVoiceOpen(false)}
          onAsk={(spoken) => { setVoiceOpen(false); ask(null, spoken); }}
          onEdit={(spoken) => { setVoiceOpen(false); setInput(spoken); textareaRef.current?.focus(); }}
        />
      )}

      {/* The money confirmation, on the shared Dialog (E6).
          This was a scrim div with a click handler and a panel inside it: no
          `role="dialog"`, no `aria-modal`, no focus trap, no Escape and no
          focus return. It is the single most consequential control a customer
          touches - the tap that moves money - and it was the one sheet in the
          app that a keyboard or screen-reader user could not work. `Dialog`
          brings all of that, and `dismissOnBackdrop={false}` because a stray
          tap on the scrim must not dismiss a decision about a refund. */}
      {pendingConfirm && (
        <Dialog
          open
          onClose={() => setPendingConfirm(null)}
          title={pendingConfirm.title}
          size="sm"
          dismissOnBackdrop={false}
          closeLabel={tl(lang, "cancel")}
          footer={
            <>
              <button onClick={() => setPendingConfirm(null)} style={{
                flex: 1, border: "1px solid var(--line)", background: "rgb(var(--c-surface))", borderRadius: 999,
                padding: "10px 0", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
              }}>{tl(lang, "cancel")}</button>
              <button data-autofocus onClick={doConfirm} style={{
                flex: 1, border: 0, background: "var(--orange-strong)", color: "rgb(var(--c-on-primary))", borderRadius: 999,
                padding: "10px 0", fontSize: 14, fontWeight: 700, cursor: "pointer", fontFamily: "inherit",
              }}>{tl(lang, "confirm")}</button>
            </>
          }
        >
          <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }}>
            {pendingConfirm.bullets.map((b, i) => <li key={i} style={{ fontSize: 14 }}>{b}</li>)}
          </ul>
        </Dialog>
      )}
    </>
  );
}
