// Clarity chat state machine and API calls.
// All API calls target the hutch-sim backend at NEXT_PUBLIC_API_BASE (default :8000).

import { expireSession, readToken } from "@/lib/session";

export type Lang = "en" | "si" | "ta";

export type ResultKind =
  | "thinking"
  | "progress"
  | "investigation"
  | "knowledge"
  | "miss"
  | "usage"
  | "packages"
  | "network"
  | "handoff"
  | "success"
  | "receipt"
  // C05: the flow's own artefacts.
  | "confirm"
  | "grounded"
  | "refused";

export type ChatMessage =
  | { role: "user"; text: string }
  /**
   * `reply` is the server's composed answer for this turn.
   *
   * It was declared on `TurnResponse` and then dropped on the floor: the
   * message carried only `kind`, so the card was all the customer ever saw.
   * Everything the backend spends the orchestrator, K03 and both verifiers
   * establishing about *what is said* - approved templates (I15), grounded
   * quotes rendered verbatim, the verifier's substituted wording, the refusal
   * text - applied to a string the browser threw away. The WhatsApp gateway
   * returned it; the web app did not, so the same question answered in two
   * channels gave the customer different things.
   *
   * It is per message, not on the shared state, because a transcript has to
   * keep what was said two turns ago. Optional: a card pushed by a local
   * action (a receipt, a success) has no turn behind it and no reply.
   */
  | { role: "clarity"; kind: ResultKind; reply?: string };

export type Decision = {
  outcome: "AUTO_FIX" | "ONE_TAP_FIX" | "STAFF_APPROVAL" | "EXPLAIN_ONLY" | "HANDOFF";
  explanation?: string;
  amount_lkr?: string | number;
  product?: string;
  merchant?: string;
  confidence?: number;
  matched_rule?: string;
  rule_id?: string;
  allowed_actions?: string[];
  rationale?: string[];
};

export type TimelineEvent = {
  occurred_at?: string;
  type?: string;
  detail?: string;
  amount_lkr?: string | number;
};

export type TimelineSource = {
  source?: string;
  name?: string;
  completeness?: string;
  status?: string;
};

export type Timeline = {
  events?: TimelineEvent[];
  sources?: TimelineSource[];
};

export type Article = { title: string; body: string; citation?: string; owner?: string };

// ─── flow artefacts (C05, #24) ────────────────────────────────────────────────

// Where the server-side flow has the conversation. Plan 22 step 10 asks the UI
// to render this, and until C05 the client threw it away: `fetchTurn` never
// sent `case_id` at the top level of the body, so every turn took the stateless
// path and no flow ever ran. That is why the chat rendered single responses.
export type FlowSnapshot = {
  case_id?: string;
  flow?: string;
  state?: string;
  turn_no?: number;
  language?: string;
  last_proposal_id?: string | null;
  channels?: string[];
};

// A citation is `source@version` with an optional `#clause`, which is what the
// K03 verifier checked and what a reader can look up. Rendered whole: dropping
// the version would leave a reference to "the terms" with no way to tell which.
export type Citation = string;

export type Verifier = {
  ok?: boolean;
  failures?: string[];
  warnings?: string[];
};

export type Handoff = {
  handoff?: boolean;
  reason?: string | null;
  queue?: string | null;
};

export type FollowUp = { id: string; i18n_key: string; intent?: string };

export type Pack = {
  name?: string;
  data_gb?: string | number;
  used_gb?: string | number;
  used_pct?: number;
  days_left?: number | string;
  data_remaining?: string;
  remaining?: string;
  price_lkr?: string | number;
  price?: string | number;
  data?: string;
  validity?: string;
  offering_id?: string;
};

export type Subscription = {
  id?: string;
  name?: string;
  active?: boolean;
  consent?: boolean;
};

export type ActivityRow = {
  id: string;
  type?: string;
  bucket?: string;
  detail?: string;
  amount_lkr?: string | number;
  balance_before?: string | number;
  balance_after?: string | number;
  at?: string;
  status?: string;
};

export type AppState = {
  msisdn?: string;
  masked?: string;
  name?: string;
  balance_lkr?: string | number;
  pack?: Pack;
  subscriptions?: Subscription[];
  activity?: ActivityRow[];
  catalogue?: Pack[];
  cases?: { case_id: string; status?: string }[];
};

export type ClarityState = {
  messages: ChatMessage[];
  mode: string | null;
  decision: Decision | null;
  timeline: Timeline | null;
  caseId: string | null;
  planId: string | null;
  receiptDoc: Record<string, unknown> | null;
  receiptCheck: Record<string, unknown> | null;
  question: string;
  intent: string | null;
  chatIntent: string | null;
  articles: Article[] | null;
  followUps: FollowUp[];
  suggestions: SuggestionChip[];
  moreTopics: SuggestionChip[];
  threadId: string | null;
  contextProduct: string | null;
  contextAmount: string | number | null;
  progressStep: number;
  thinkingLabel: string;
  // C05: what the server-side flow said, rendered rather than discarded.
  flow: FlowSnapshot | null;
  citations: Citation[];
  verifier: Verifier | null;
  handoff: Handoff | null;
  refused: boolean;
};

export type SuggestionChip = {
  id: string;
  i18n_key: string;
  intent?: string;
  label?: string;
  reason?: string;
  personalized?: boolean;
};

export type Thread = {
  id: string;
  title: string;
  status: string;
  messages: ChatMessage[];
  snapshot: Partial<ClarityState>;
  at: number;
};

// ─── config ───────────────────────────────────────────────────────────────────

export const BASE =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000")
    : "http://localhost:8000";

const HISTORY_KEY = "clarity_chat_threads_v1";

export const SUGGESTED: Array<{ key: string; intent: string; chatIntent: string }> = [
  { key: "qBalance", intent: "balance", chatIntent: "BALANCE_DEDUCTION_QUERY" },
  { key: "qSub", intent: "sub", chatIntent: "UNEXPECTED_CHARGE" },
  { key: "qTwice", intent: "twice", chatIntent: "DOUBLE_CHARGE" },
  { key: "qSlow", intent: "slow", chatIntent: "DATA_SLOW" },
  { key: "qMissing", intent: "missing", chatIntent: "RELOAD_MISSING" },
  { key: "qEsim", intent: "knowledge", chatIntent: "ESIM_HELP" },
  { key: "qActivate", intent: "knowledge", chatIntent: "PACK_ACTIVATE" },
  { key: "qFup", intent: "slow", chatIntent: "FUP_QUERY" },
  { key: "qRecommend", intent: "knowledge", chatIntent: "PACK_RECOMMEND" },
  { key: "qPrevent", intent: "knowledge", chatIntent: "PREVENT_CHARGES" },
  { key: "qVasList", intent: "sub", chatIntent: "VAS_SUBSCRIPTIONS" },
  { key: "qNetwork", intent: "knowledge", chatIntent: "NETWORK_STATUS" },
  { key: "qExpiry", intent: "balance", chatIntent: "PACK_EXPIRY" },
  { key: "qPackIssue", intent: "slow", chatIntent: "PACK_NOT_WORKING" },
  { key: "qPackMissing", intent: "missing", chatIntent: "PACK_MISSING" },
  { key: "qRefund", intent: "balance", chatIntent: "REFUND_STATUS" },
  { key: "qCase", intent: "balance", chatIntent: "CASE_STATUS" },
];

export const TOPIC_CATEGORIES = [
  { id: "money", i18n: "catMoney", keys: ["qBalance", "qSub", "qTwice", "qRefund"] },
  { id: "packs", i18n: "catPacks", keys: ["qSlow", "qFup", "qPackIssue", "qPackMissing", "qRecommend", "qActivate", "qExpiry"] },
  { id: "reloads", i18n: "catReloads", keys: ["qMissing", "qTwice"] },
  { id: "subs", i18n: "catSubs", keys: ["qSub", "qVasList", "qPrevent"] },
  { id: "network", i18n: "catNetwork", keys: ["qSlow", "qNetwork"] },
  { id: "esim", i18n: "catEsim", keys: ["qEsim"] },
  { id: "protect", i18n: "catProtect", keys: ["qPrevent"] },
  { id: "support", i18n: "catSupport", keys: ["qCase"] },
];

export const PROGRESS_STEPS = [
  { id: "understand", key: "progUnderstand" },
  { id: "charges", key: "progCharges" },
  { id: "subs", key: "progSubs" },
  { id: "consent", key: "progConsent" },
];

export const INTENT_EMPTY: Record<string, string> = {
  balance: "intentNone",
  sub: "intentSub",
  twice: "intentTwice",
  slow: "intentSlow",
  missing: "intentMissing",
};

// ─── initial state ─────────────────────────────────────────────────────────────

export function makeInitialState(): ClarityState {
  return {
    messages: [],
    mode: null,
    decision: null,
    timeline: null,
    caseId: null,
    planId: null,
    receiptDoc: null,
    receiptCheck: null,
    question: "",
    intent: null,
    chatIntent: null,
    articles: null,
    followUps: [],
    suggestions: [],
    moreTopics: [],
    threadId: null,
    contextProduct: null,
    contextAmount: null,
    progressStep: -1,
    thinkingLabel: "",
    flow: null,
    citations: [],
    verifier: null,
    handoff: null,
    refused: false,
  };
}

// ─── API ───────────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const opts: RequestInit = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const token = typeof window !== "undefined" ? (readToken() ?? "") : "";
  if (token) (opts.headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, opts);
  if (res.status === 401 && typeof window !== "undefined") expireSession();
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function fetchSuggestions(lang: string, app: AppState): Promise<SuggestionChip[]> {
  try {
    const payload = await apiFetch<{ suggestions?: SuggestionChip[] }>(
      "/v1/conversation/suggestions",
      "POST",
      {
        language: lang,
        limit: 6,
        snapshot: {
          pack: app.pack || {},
          subscriptions: app.subscriptions || [],
          activity: app.activity || [],
          open_case: (app.cases || []).some((c) => c.status === "open"),
        },
      }
    );
    return payload.suggestions || [];
  } catch {
    return defaultSuggestions();
  }
}

function defaultSuggestions(): SuggestionChip[] {
  const keys = ["qBalance", "qSlow", "qSub", "qRecommend", "qPackIssue", "qEsim"];
  return keys.map((key) => ({
    id: key,
    i18n_key: key,
    intent: SUGGESTED.find((s) => s.key === key)?.chatIntent ?? "",
    reason: "default",
    personalized: false,
  }));
}

type TurnResponse = {
  turn?: {
    reply?: string;
    route?: string;
    client_intent?: string;
    case_id?: string | null;
    follow_ups?: FollowUp[];
    articles?: Article[];
    // Added by C01 to C03 and K03, and read by the client since C05.
    state?: FlowSnapshot;
    citations?: Citation[];
    proposal_id?: string | null;
    refused?: boolean;
    verifier?: Verifier;
    handoff?: Handoff;
    intake?: {
      intent?: string;
      client_intent?: string;
      route?: string;
      language?: string;
      confidence?: number;
      assisted?: boolean;
      slots?: { product?: string; amount_lkr?: string };
    };
  };
};

export async function fetchTurn(
  text: string,
  lang: string,
  intentOverride: string | null,
  facts: Record<string, unknown>,
  app: AppState,
  caseId?: string | null
): Promise<TurnResponse["turn"]> {
  try {
    const payload = await apiFetch<TurnResponse>("/v1/conversation/turn", "POST", {
      text,
      language: lang,
      intent: intentOverride,
      facts,
      // Top level, not inside `facts`: the route reads it from the body and
      // only then takes the stateful pipeline. Passing it in `facts` left
      // every turn stateless, which is the bug C05 fixes.
      //
      // Null on the first turn of a conversation, because the case does not
      // exist yet. The server answers statelessly and keeps nothing, which is
      // correct: there is nothing to attach state to.
      case_id: caseId ?? null,
      channel: "app",
      snapshot: {
        pack: app.pack || {},
        subscriptions: app.subscriptions || [],
        activity: app.activity || [],
      },
    });
    return payload.turn ?? {};
  } catch {
    return {};
  }
}

export async function openCase(msisdn: string, lang: string, chargeRef: string | null, wantsHuman: boolean) {
  return apiFetch<{ case_id: string }>("/v1/cases", "POST", {
    msisdn,
    channel: "app",
    language: lang,
    charge_ref: chargeRef ?? null,
    customer_requested_human: wantsHuman,
  });
}

export async function evaluateCase(caseId: string, wantsHuman: boolean) {
  return apiFetch<Decision>(`/v1/cases/${caseId}/evaluate?human=${wantsHuman}`, "POST");
}

export async function fetchTimeline(caseId: string) {
  return apiFetch<Timeline>(`/v1/cases/${caseId}/timeline`);
}

export async function routeQuestion(question: string, lang: string) {
  return apiFetch<{ articles?: Article[] }>("/v1/clarity/route", "POST", { question, language: lang });
}

export async function createProposal(caseId: string) {
  return apiFetch<{ plan_id: string }>(`/v1/cases/${caseId}/proposals`, "POST", {
    created_by: "channel:web",
  });
}

export async function applyFix(caseId: string, planId: string, outcome: string) {
  const path = outcome === "AUTO_FIX" ? "auto-fix" : "confirm";
  return apiFetch<{ receipt_id: string }>(`/v1/cases/${caseId}/${path}`, "POST", { plan_id: planId });
}

export async function issueExplainReceipt(caseId: string) {
  return apiFetch<{ receipt_id: string }>(`/v1/cases/${caseId}/receipt`, "POST");
}

export async function fetchReceipt(receiptId: string) {
  return apiFetch<Record<string, unknown>>(`/v1/receipts/${receiptId}`);
}

export async function verifyReceipt(receiptId: string) {
  return apiFetch<Record<string, unknown>>(`/v1/receipts/${receiptId}/verify`, "POST");
}

// ─── intent helpers ────────────────────────────────────────────────────────────

export function intentForQuestion(questionKey: string | null, freeText: string): string {
  if (questionKey) {
    const s = SUGGESTED.find((x) => x.key === questionKey);
    if (s) return s.intent;
  }
  const text = freeText.toLowerCase();
  if (/esim|e-sim|convert|activate a pack|how do i|how to/.test(text)) return "knowledge";
  if (/subscri/.test(text)) return "sub";
  if (/twice|duplicate/.test(text)) return "twice";
  if (/slow|fup/.test(text)) return "slow";
  if (/arriv|missing|credit/.test(text)) return "missing";
  return "balance";
}

export function chargeForIntent(intent: string, activity: ActivityRow[]): string | null {
  const pick = (test: (r: ActivityRow) => boolean) => activity.find(test)?.id ?? null;
  if (intent === "sub") return pick((r) => r.type === "vas_charge" || r.bucket === "charges");
  if (intent === "twice" || intent === "missing") return pick((r) => r.type === "payment_captured");
  if (intent === "slow") return pick((r) => r.type === "fup_cap_reached" || r.type === "throttle_applied" || r.bucket === "usage");
  return pick((r) => ["charges", "reloads", "refunds"].includes(r.bucket ?? ""));
}

export function pickResultKind(state: ClarityState): ResultKind {
  const intent = state.chatIntent ?? "";
  const outcome = state.decision?.outcome;
  if (state.mode === "human" || outcome === "HANDOFF") return "handoff";
  if (state.mode === "knowledge") return "knowledge";
  if (state.mode === "miss") return "miss";
  if (intent === "DATA_SLOW" || intent === "FUP_QUERY") return "usage";
  if (intent === "PACK_RECOMMEND") return "packages";
  if (intent === "NETWORK_STATUS") return "network";
  return "investigation";
}

// ─── thread history ────────────────────────────────────────────────────────────

export function loadThreads(): Thread[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]") as Thread[];
  } catch {
    return [];
  }
}

export function saveThread(state: ClarityState): void {
  if (!state.messages.length) return;
  const title =
    state.question ||
    (state.messages.find((m) => m.role === "user") as { role: "user"; text: string } | undefined)?.text ||
    "Clarity";
  let status = "In progress";
  if (state.mode === "resolved") status = "Resolved";
  else if (state.mode === "result" || state.mode === "knowledge" || state.mode === "miss") status = "Explained";

  const threads = loadThreads().filter((t) => t.id !== state.threadId);
  const id = state.threadId ?? `th_${Date.now()}`;
  threads.unshift({
    id,
    title: String(title).slice(0, 80),
    status,
    messages: state.messages,
    snapshot: {
      mode: state.mode,
      decision: state.decision,
      timeline: state.timeline,
      caseId: state.caseId,
      followUps: state.followUps,
      articles: state.articles,
      receiptDoc: state.receiptDoc,
      receiptCheck: state.receiptCheck,
      question: state.question,
      chatIntent: state.chatIntent,
      contextProduct: state.contextProduct,
      contextAmount: state.contextAmount,
    },
    at: Date.now(),
  });
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(threads.slice(0, 20)));
  } catch {
    // storage full
  }
}
