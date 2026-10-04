"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supportedLangs, t, type Lang } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";
import { expireSession, readToken } from "@/lib/session";
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
    chatHi: "Hi {name}", howHelpToday: "How can I help you today?",
    chatSubtitle: "Ask me anything about your Hutch account.",
    askClarityAnything: "Ask Clarity anything...", speak: "Speak",
    stageMasked: "Protecting your details...", stageUnderstood: "Understanding your question...",
    stageChecked: "Checking your account...", stageComposed: "Writing the answer...",
    stageVerified: "Checking the answer...",
    newChat: "New chat", chatHistory: "History", empty: "Nothing here yet.",
    seeMoreTopics: "See more topics", seeFewerTopics: "Show fewer",
    browseTopics: "Browse topics",
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
    chatHi: "ආයුබෝවන් {name}", howHelpToday: "අද මම උදව් කරන්නේ කෙසේද?",
    chatSubtitle: "ඔබේ Hutch ගිණුම ගැන ඕනෑම දෙයක් අසන්න.",
    askClarityAnything: "Clarity ගෙන් ඕනෑම දෙයක් අසන්න...", speak: "කතා කරන්න",
    stageMasked: "ඔබේ විස්තර ආරක්ෂා කරමින්...", stageUnderstood: "ඔබේ ප්‍රශ්නය තේරුම් ගනිමින්...",
    stageChecked: "ඔබේ ගිණුම පරීක්ෂා කරමින්...", stageComposed: "පිළිතුර ලියමින්...",
    stageVerified: "පිළිතුර පරීක්ෂා කරමින්...",
    newChat: "නව කතාබස්", chatHistory: "ඉතිහාසය", empty: "මෙතැන තවම කිසිවක් නැත.",
    seeMoreTopics: "තවත් මාතෘකා", seeFewerTopics: "අඩුවෙන් පෙන්වන්න",
    browseTopics: "මාතෘකා බලන්න",
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
    chatHi: "வணக்கம் {name}", howHelpToday: "இன்று நான் எப்படி உதவட்டும்?",
    chatSubtitle: "உங்கள் Hutch கணக்கு பற்றி எதையும் கேளுங்கள்.",
    askClarityAnything: "Clarity இடம் எதையும் கேளுங்கள்...", speak: "பேசு",
    stageMasked: "உங்கள் விவரங்களைப் பாதுகாக்கிறேன்...", stageUnderstood: "உங்கள் கேள்வியைப் புரிந்துகொள்கிறேன்...",
    stageChecked: "உங்கள் கணக்கைச் சரிபார்க்கிறேன்...", stageComposed: "பதிலை எழுதுகிறேன்...",
    stageVerified: "பதிலைச் சரிபார்க்கிறேன்...",
    newChat: "புதிய அரட்டை", chatHistory: "வரலாறு", empty: "இங்கே இன்னும் ஒன்றுமில்லை.",
    seeMoreTopics: "மேலும் தலைப்புகள்", seeFewerTopics: "குறைவாகக் காட்டு",
    browseTopics: "தலைப்புகளைப் பார்",
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

const LANG_LABELS: Record<Lang, string> = { en: "EN", si: "සිං", ta: "த" };
const DEMO_NAME = "Dilani Perera";

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
  const { lang, setLang } = useLanguage();
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
        const token = readToken();
        if (!token) return expireSession();
        const res = await fetch(`${BASE}/v1/me/app`, {
          headers: { Authorization: `Bearer ${token}` },
        });
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
  const [showTopics, setShowTopics] = useState(false);
  const [topicCategory, setTopicCategory] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
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

      // No client-side eligibility gate (A2). `accountIntents` used to read
      // `used_pct >= 80`, duplicate payment amounts and consent flags here and
      // decide whether the rule engine was asked at all. That is I1 inverted:
      // rules decide, and a heuristic in React deciding there is nothing to
      // find is a decision. It also failed closed in the worst direction - a
      // customer whose evidence the browser had not loaded was told nothing was
      // wrong while the backend had a cause waiting (FE01, #28).
      //
      // The question now always reaches detection. When no rule matches,
      // `decision/policy.py` answers HANDOFF with `NO_CAUSE_FOUND`, which
      // `pickResultKind` renders as the handoff card: a person, not a guess
      // (I2). That is the same conclusion the gate was reaching for, reached by
      // the component the invariant puts in charge of it.

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
      const proposal = await createProposal(cs.caseId);
      const done = await applyFix(cs.caseId, proposal.plan_id, pendingConfirm.outcome);
      const [verified, full] = await Promise.all([
        verifyReceipt(done.receipt_id),
        fetchReceipt(done.receipt_id),
      ]);
      setCs((s) => ({
        ...s,
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
    } catch (e) { console.error(e); }
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
    setShowTopics(false);
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

  const chips = cs.suggestions.length
    ? cs.suggestions
    : SUGGESTED.slice(0, 6).map((s) => ({ id: s.key, i18n_key: s.key, intent: s.chatIntent, reason: "default" } as SuggestionChip));

  // ─── render ────────────────────────────────────────────────────────────────

  const isEmpty = cs.messages.length === 0;
  const threads = loadThreads();

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", minHeight: "100dvh", background: "#fafafa" }}>

        {/* ── Header ── */}
        <header style={{
          position: "sticky", top: "env(safe-area-inset-top,0px)", zIndex: 30,
          background: "#fff", borderBottom: "1px solid var(--line)",
          padding: "12px 14px", display: "flex", alignItems: "center", gap: 10,
        }}>
          {/* back button */}
          <button
            onClick={() => router.back()}
            aria-label="Back"
            style={{
              border: 0, background: "transparent", padding: "6px 4px",
              cursor: "pointer", fontSize: 20, color: "var(--ink)",
              display: "grid", placeItems: "center", flexShrink: 0,
            }}
          >←</button>

          <div style={{
            width: 40, height: 40, borderRadius: 14,
            background: "linear-gradient(145deg,#f26226,#c2410c)",
            color: "#fff", display: "grid", placeItems: "center",
            fontWeight: 800, fontSize: 18, flexShrink: 0,
          }} aria-hidden="true">C</div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 800, fontSize: 16, lineHeight: 1.2 }}>{tl(lang, "clarityBrand")}</div>
            <div style={{ fontSize: 12, color: "var(--muted)" }}>{tl(lang, "claritySubtitle")}</div>
          </div>

          {/* lang switcher */}
          <div style={{ display: "flex", gap: 2, background: "#f4f4f5", borderRadius: 10, padding: 2 }} role="group" aria-label="Language">
            {supportedLangs.map((l) => (
              <button key={l} type="button" onClick={() => setLang(l)} style={{
                border: 0,
                background: l === lang ? "#fff" : "transparent",
                color: l === lang ? "var(--orange-ink)" : "#52525b",
                boxShadow: l === lang ? "0 1px 2px rgba(0,0,0,.06)" : "none",
                fontSize: 11, fontWeight: 700, padding: "6px 8px", borderRadius: 8,
                cursor: "pointer", fontFamily: "inherit",
              }}>{LANG_LABELS[l]}</button>
            ))}
          </div>

          <button onClick={() => setShowHistory(true)} aria-label={tl(lang, "chatHistory")} style={{ border: 0, background: "transparent", padding: "6px 4px", cursor: "pointer", fontSize: 18, color: "var(--ink)" }}>☰</button>
          <button onClick={newChat} aria-label={tl(lang, "newChat")} style={{ border: 0, background: "transparent", padding: "6px 4px", cursor: "pointer", fontSize: 20, color: "var(--ink)", fontWeight: 300 }}>+</button>
        </header>

        {/* ── Scrollable body ── */}
        <div ref={bodyRef} style={{
          flex: 1, overflowY: "auto",
          padding: "0 16px calc(88px + 32px)",
          maxWidth: 640, margin: "0 auto", width: "100%",
        }}>

          {isEmpty ? (
            /* ── Welcome ── */
            <div>
              <div style={{ textAlign: "center", padding: "40px 8px 24px" }}>
                <div style={{
                  width: 72, height: 72, margin: "0 auto 18px", borderRadius: 22,
                  background: "linear-gradient(145deg,#fff1eb,#ffe4d6)",
                  border: "1px solid #fdd5c0", display: "grid", placeItems: "center",
                  color: "var(--orange)",
                }} aria-hidden="true">
                  <svg width="36" height="36" viewBox="0 0 36 36" fill="currentColor">
                    <rect x="10" y="10" width="16" height="16" rx="8" fill="currentColor" />
                  </svg>
                </div>
                <h1 style={{ fontSize: "clamp(24px,6vw,30px)", fontWeight: 800, letterSpacing: "-.03em", margin: "0 0 6px", color: "var(--ink)" }}>
                  {tl(lang, "chatHi").replace("{name}", app.name ?? DEMO_NAME)}
                </h1>
                <p style={{ fontSize: 19, fontWeight: 700, margin: "0 0 6px", color: "#3f3f46" }}>{tl(lang, "howHelpToday")}</p>
                <p style={{ fontSize: 14, color: "var(--muted)", margin: "0 0 24px", maxWidth: 280, marginLeft: "auto", marginRight: "auto" }}>
                  {tl(lang, "chatSubtitle")}
                </p>
              </div>

              {/* suggestion chips */}
              <div style={{ display: "grid", gap: 8 }}>
                {chips.map((chip) => {
                  const label = chip.label ?? tl(lang, chip.i18n_key) ?? chip.id;
                  const personalized = chip.personalized ?? false;
                  return (
                    <button key={chip.id} onClick={() => ask(chip.i18n_key, label, chip.intent ?? null)}
                      style={{
                        width: "100%", textAlign: "left", padding: "14px 18px",
                        borderRadius: 999, border: `1.5px solid ${personalized ? "var(--orange)" : "#fdd5c0"}`,
                        background: personalized ? "var(--orange-soft)" : "#fff",
                        cursor: "pointer", fontFamily: "inherit", fontWeight: 600,
                        fontSize: 15, color: "var(--ink)",
                        boxShadow: "0 1px 2px rgba(24,24,27,.04)",
                      }}
                    >{label}</button>
                  );
                })}
              </div>

              {/* see more topics toggle */}
              <button onClick={() => setShowTopics((v) => !v)} style={{
                border: 0, background: "transparent", color: "var(--orange-ink)",
                fontWeight: 700, fontSize: 13, cursor: "pointer", padding: "14px 4px",
                fontFamily: "inherit",
              }}>
                {tl(lang, showTopics ? "seeFewerTopics" : "seeMoreTopics")}
              </button>

              {showTopics && (
                <div style={{ marginBottom: 16 }}>
                  <p style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", margin: "0 0 10px" }}>
                    {tl(lang, "browseTopics")}
                  </p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                    {TOPIC_CATEGORIES.map((cat) => (
                      <button key={cat.id} onClick={() => setTopicCategory((v) => (v === cat.id ? null : cat.id))}
                        style={{
                          border: "1.5px solid",
                          borderColor: topicCategory === cat.id ? "var(--orange)" : "var(--line)",
                          background: topicCategory === cat.id ? "var(--orange-soft)" : "#fff",
                          color: topicCategory === cat.id ? "var(--orange-ink)" : "var(--ink)",
                          borderRadius: 999, padding: "8px 14px", fontSize: 13, fontWeight: 600,
                          cursor: "pointer", fontFamily: "inherit",
                        }}
                      >{tl(lang, cat.i18n)}</button>
                    ))}
                  </div>

                  {topicCategory && (() => {
                    const cat = TOPIC_CATEGORIES.find((c) => c.id === topicCategory);
                    if (!cat) return null;
                    return (
                      <div style={{ display: "grid", gap: 6 }}>
                        {cat.keys.map((key) => {
                          const label = tl(lang, key);
                          const sug = SUGGESTED.find((s) => s.key === key);
                          return (
                            <button key={key} onClick={() => ask(key, label, sug?.chatIntent ?? null)}
                              style={{
                                width: "100%", textAlign: "left", padding: "12px 16px",
                                borderRadius: 12, border: "1px solid var(--line)",
                                background: "#fff", cursor: "pointer", fontFamily: "inherit",
                                fontWeight: 500, fontSize: 14, color: "var(--ink)",
                              }}
                            >{label}</button>
                          );
                        })}
                      </div>
                    );
                  })()}
                </div>
              )}
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
                        background: "var(--orange-strong)", color: "#fff", borderRadius: "18px 18px 4px 18px",
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
                            background: "#fff",
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
          position: "fixed", left: 0, right: 0, bottom: "var(--safe-bottom,0px)", zIndex: 35,
          background: "linear-gradient(to top,#fff 70%,rgba(255,255,255,0))",
          padding: "10px 16px 8px",
        }}>
          <div style={{
            maxWidth: 640, margin: "0 auto", display: "flex", alignItems: "flex-end", gap: 8,
            background: "#fff", border: "1px solid var(--line)", borderRadius: 22,
            padding: "8px 10px", boxShadow: "0 8px 24px rgba(24,24,27,.08)",
          }}>
            {/* Shown only where the browser can turn speech into text, so
                the button never opens something that cannot work. */}
            {voiceSupported ? (
              <button type="button" aria-haspopup="dialog" onClick={() => setVoiceOpen(true)} disabled={busy} style={{
                border: 0, background: "var(--orange-soft)", color: "var(--orange-ink)",
                fontWeight: 700, fontSize: 14, cursor: busy ? "not-allowed" : "pointer", padding: "8px 12px",
                fontFamily: "inherit", flexShrink: 0, borderRadius: 999,
                display: "inline-flex", alignItems: "center", gap: 6,
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="9" y="3" width="6" height="11" rx="3" />
                  <path d="M5 11a7 7 0 0 0 14 0" />
                  <path d="M12 18v3" />
                </svg>
                {tl(lang, "speak")}
              </button>
            ) : null}

            <textarea
              ref={textareaRef}
              rows={1}
              // A placeholder is not an accessible name: it disappears on the
              // first keystroke and some screen readers never announce it, so
              // the one control on this screen had no name at all (C05 scope).
              aria-label={tl(lang, "askClarityAnything")}
              placeholder={tl(lang, "askClarityAnything")}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(null, input);
                }
              }}
              style={{
                flex: 1, border: 0, resize: "none", fontFamily: "inherit", fontSize: 15,
                minHeight: 24, maxHeight: 96, padding: "8px 4px", background: "transparent",
                outline: "none", color: "var(--ink)", lineHeight: 1.4,
              }}
            />

            <button
              type="button"
              onClick={() => ask(null, input)}
              disabled={!input.trim() || busy}
              style={{
                width: 40, height: 40, borderRadius: 999, border: 0,
                background: input.trim() && !busy ? "var(--orange-strong)" : "#e4e4e7",
                color: input.trim() && !busy ? "#fff" : "#a1a1aa",
                fontSize: 16, fontWeight: 700,
                cursor: input.trim() && !busy ? "pointer" : "not-allowed",
                display: "grid", placeItems: "center", flexShrink: 0, transition: "background .15s",
              }}
              aria-label="Send"
            >↑</button>
          </div>
        </div>
      </div>

      {/* ── History drawer ── */}
      {showHistory && (
        <div onClick={() => setShowHistory(false)} style={{
          position: "fixed", inset: 0, zIndex: 50, background: "rgba(0,0,0,.4)",
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            position: "absolute", top: 0, left: 0, bottom: 0, width: "min(320px,90vw)",
            background: "#fff", display: "flex", flexDirection: "column",
            boxShadow: "4px 0 24px rgba(0,0,0,.12)", overflowY: "auto",
          }}>
            <div style={{ padding: "20px 16px 12px", borderBottom: "1px solid var(--line)" }}>
              <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>{tl(lang, "chatHistory")}</h2>
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

      {/* ── Confirm modal ── */}
      {voiceOpen && (
        <VoiceSheet
          lang={lang}
          onClose={() => setVoiceOpen(false)}
          onAsk={(spoken) => { setVoiceOpen(false); ask(null, spoken); }}
          onEdit={(spoken) => { setVoiceOpen(false); setInput(spoken); textareaRef.current?.focus(); }}
        />
      )}

      {pendingConfirm && (
        <div onClick={() => setPendingConfirm(null)} style={{
          position: "fixed", inset: 0, zIndex: 60, background: "rgba(0,0,0,.5)",
          display: "grid", placeItems: "center", padding: 16,
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            background: "#fff", borderRadius: "var(--radius)", padding: "24px 20px",
            maxWidth: 360, width: "100%", boxShadow: "var(--shadow)",
          }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 700 }}>{pendingConfirm.title}</h3>
            <ul style={{ margin: "0 0 20px", paddingLeft: 18, display: "grid", gap: 6 }}>
              {pendingConfirm.bullets.map((b, i) => <li key={i} style={{ fontSize: 14 }}>{b}</li>)}
            </ul>
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={() => setPendingConfirm(null)} style={{
                flex: 1, border: "1px solid var(--line)", background: "#fff", borderRadius: 999,
                padding: "10px 0", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
              }}>{tl(lang, "cancel")}</button>
              <button onClick={doConfirm} style={{
                flex: 1, border: 0, background: "var(--orange-strong)", color: "#fff", borderRadius: 999,
                padding: "10px 0", fontSize: 14, fontWeight: 700, cursor: "pointer", fontFamily: "inherit",
              }}>{tl(lang, "confirm")}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
