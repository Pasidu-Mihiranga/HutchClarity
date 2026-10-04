/**
 * Types the client returns.
 *
 * Two kinds, kept apart on purpose:
 *
 * - **Schema types** are aliases of `components["schemas"]`, generated from
 *   the backend's OpenAPI document. They cannot drift, because regenerating
 *   changes them and `tsc` then fails wherever the app disagrees.
 * - **Declared types** describe routes whose response the backend does not
 *   publish a model for (it returns `dict[str, Any]`). They are written here by
 *   hand and are the only hand-written shapes in the SDK. The client refuses to
 *   declare a shape for a route the schema does type (`OnlyIfOpen`), so a
 *   declared type disappears from this file the day the backend publishes a
 *   model. Each says which handler it mirrors.
 */

import type { components } from "./generated/schema";

type Schemas = components["schemas"];

/* ------------------------------------------------------------ schema types */

/**
 * `roles` and `permissions` have server-side defaults, so the generated type
 * marks them optional; the API always sends them, and every caller wants them.
 */
export type SessionView = Omit<Schemas["SessionView"], "roles" | "permissions"> & {
  roles: string[];
  permissions: string[];
};
export type CaseSummary = Schemas["CaseSummary"];
export type DecisionView = Schemas["DecisionView"];
export type CauseView = Schemas["CauseView"];
export type RuledOutView = Schemas["RuledOutView"];
export type QueueItem = Schemas["QueueItem"];
export type TimelineView = Schemas["TimelineView"];
export type TimelineEventView = Schemas["TimelineEventView"];
export type SourceStatusView = Schemas["SourceStatusView"];
export type PlanView = Schemas["PlanView"];
export type ExecutionView = Schemas["ExecutionView"];
export type ActionView = Schemas["ActionView"];
export type VerificationView = Schemas["VerificationView"];
export type DemoSubscriber = Schemas["DemoSubscriber"];

/** Older names, kept so a caller importing them still compiles. */
export type CasePayload = CaseSummary;
export type DecisionPayload = DecisionView;
export type TimelinePayload = TimelineView;
export type TimelineEvent = TimelineEventView;
export type TimelineSource = SourceStatusView;
export type RuledOutItem = RuledOutView;
export type ProposalPayload = PlanView;
export type ReceiptPayload = VerificationView;
export type OtpVerifyResult = SessionView;

/* ---------------------------------------------------------- request bodies */

/** Fields the server defaults are optional for the caller, whatever the schema generator says. */
type WithDefaults<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

export type OpenCaseBody = WithDefaults<
  Schemas["OpenCaseRequest"],
  "channel" | "language" | "customer_requested_human" | "charge_ref"
>;
export type ProposeBody = WithDefaults<Schemas["ProposeRequest"], "created_by" | "action_types">;
export type StaffSessionRequest = WithDefaults<Schemas["StaffSignIn"], "step_up">;
export type StaffLoginRequest = WithDefaults<Schemas["StaffLogin"], "step_up_code">;
export type PreferencesBody = WithDefaults<Schemas["PreferencesRequest"], "large_text" | "notify">;
export type SafeguardKind = "data_on_expiry" | "spend_cap" | "vas_confirm" | "usage_alerts" | "merchant_block";

/* ---------------------------------------------------------- declared types */

/** `POST /v1/auth/otp/request`. */
export type OtpRequestResult = {
  /** Required by `verifyOtp`: the challenge this code belongs to. */
  challenge_id: string;
  sent_to?: string;
  simulated?: boolean;
  detail?: string;
};

/** `GET /v1/auth/sign-in-methods` (staff_sso.py). */
export type SignInMethods = {
  /** Keycloak, or whichever provider this deployment federates. */
  provider: boolean;
  /** The simulated staff directory: a username and password. */
  directory: boolean;
  /** The development role picker, which has no credential at all. */
  development_role_picker: boolean;
};

/** `POST /v1/auth/logout`. */
export type LogoutResult = { signed_out: boolean; provider_logout?: string | null };

/** `POST /v1/auth/staff/step-up`. */
export type StepUpResult = { redirect_to: string; level: string };

/** `GET /v1/auth/sessions`: never carries a token. */
export type SessionRecord = {
  session_ref: string;
  channel: string;
  assurance: string;
  started_at: string;
  expires_at: string;
  refresh_expires_at: string;
  current: boolean;
};

/** `GET /v1/cases/{id}/transcript`. */
export type TranscriptEntry = {
  turn_no: number;
  role: "customer" | "clarity";
  text: string;
  language: string;
  channel: string;
  at: string;
};

export type TranscriptPayload = {
  case_id: string;
  entries: TranscriptEntry[];
  masked: boolean;
  retention_days: number;
};

/**
 * `GET /v1/receipts/{id}`: the full signed document (contracts/receipt.py).
 * It carries no verdict; only `verifyReceipt` computes one. Only the parts a
 * screen reads are typed.
 */
export type SignedReceipt = {
  receipt_id: string;
  case_id: string;
  payload: {
    receipt_id: string;
    case_id: string;
    issued_at: string;
    what_happened: { cause_rule: string; rule_version: number; summary: string };
    decision: { decision_id: string; outcome: string; policy_version: string };
    actions: Array<{
      action_id: string;
      type: string;
      amount_lkr?: string | null;
      before: Record<string, string>;
      after: Record<string, string>;
      status: string;
    }>;
    safeguard?: { type: string; status: string } | null;
    audit_anchor?: { checkpoint_seq: number; kid: string } | null;
  };
  payload_hash?: string;
  signature?: string;
  verify_url?: string;
};

/** `POST /v1/cases/{id}/approve` answers 202 with this when a second approver is needed (schemas.py). */
export type PendingApproval = {
  case_id: string;
  plan_id: string;
  status: "AWAITING_SECOND_APPROVAL";
  detail: string;
};

/** The execution, or the news that it is waiting for a second, different approver. */
export type ApproveResult = ExecutionView | PendingApproval;

/** `GET /v1/admin/switches`. */
export type SwitchStateView = {
  switches: Array<{ key: string; enabled: boolean }>;
  disabled: string[];
  history: Array<{
    name: string;
    enabled: boolean;
    actor_ref: string;
    reason: string;
    at: string;
  }>;
};

export type AuditRecordView = {
  seq: number;
  hash_version: number;
  event_type: string;
  actor_ref: string;
  actor_kind: string;
  session_ref?: string | null;
  object_ref: string;
  case_id?: string | null;
  payload_hash: string;
  detail: Record<string, unknown>;
  detail_hash: string;
  occurred_at: string;
  recorded_at: string;
  prev_hash?: string | null;
  chain_hash: string;
};

export type AuditTrailPage = {
  records: AuditRecordView[];
  next_after_seq: number | null;
  verification: {
    intact: boolean;
    length: number;
    checkpoints: number;
    last_checkpoint_seq: number | null;
    broken_at: number | null;
    reason: string | null;
    lost_from: number | null;
    lost_to: number | null;
  };
};

export type AuditHealth = {
  intact: boolean;
  length: number;
  verified_from: number;
  broken_at: number | null;
  reason: string | null;
  lost_from: number | null;
  lost_to: number | null;
  checkpoints: number;
  last_checkpoint_seq: number | null;
  last_checkpoint_at: string | null;
  last_checkpoint_age_seconds: number | null;
  detection_last_ran_at: string | null;
  writer_lag_events: number;
  archived_below_seq: number;
  witness_url: string;
};

export type AuditRecovery = {
  last_backup: Record<string, unknown> | null;
  last_backup_read: Record<string, unknown> | null;
  last_restore: Record<string, unknown> | null;
  last_segment_sealed: Record<string, unknown> | null;
  last_erasure: Record<string, unknown> | null;
  backups_configured: boolean;
};

export type AuditRecordVerdict = {
  seq: number;
  detail_matches_its_hash: boolean;
  record_hash_matches_its_contents: boolean;
  follows_its_predecessor: boolean;
  predecessor_available: boolean;
  intact: boolean;
  hash_version: number;
  chain_hash: string;
};

export type AuditGrantView = {
  grant_id: string;
  subject_kind: string;
  subject_ref: string;
  permission: string;
  state: string;
  reason: string;
  requested_by: string;
  requested_at: string;
  approved_by?: string | null;
  expires_at?: string | null;
  review_due_at?: string | null;
  break_glass: boolean;
};

export type AlertView = {
  alert_id: string;
  rule_id: string;
  band: string;
  group_key: string;
  summary: string;
  evidence: number[];
  subject_ref?: string | null;
  case_id?: string | null;
  state: string;
  raised_at: string;
  last_seen_at: string;
  occurrences: number;
  acknowledged_by?: string | null;
  acknowledged_at?: string | null;
  escalated_at?: string | null;
  disposed_by?: string | null;
  disposed_at?: string | null;
  disposition?: string | null;
  disposition_reason?: string | null;
};

export type AlertQueue = {
  alerts: AlertView[];
  detection_last_ran_at: string | null;
};

/* ------------------------------------------------- the signed-in customer */

/** One pack the customer holds (`_home_for` in main.py). */
export type CustomerPack = {
  name: string;
  price_lkr: string;
  purchased_at: string;
  expires_at: string;
  days_left: number;
  data_gb: string | null;
  used_gb: string | null;
  used_pct: number | null;
  after_cap_speed: string | null;
  disclosed: boolean;
  apps: string;
  restrictions: string;
  renewal: string;
  after_expiry: string;
};

export type CustomerSubscription = {
  id: string;
  name: string;
  merchant: string;
  merchant_id: string;
  price_lkr: string;
  active: boolean;
  consent: boolean;
  renewal: string;
  charges: string[];
};

export type ActivityBucket = "packages" | "usage" | "reloads" | "refunds" | "charges";

export type ActivityRow = {
  id: string;
  at: string;
  type: string;
  bucket: ActivityBucket;
  amount_lkr: string | null;
  source: string;
  detail: string;
  balance_before: string | null;
  balance_after: string | null;
  status: string;
  subscription_id: string | null;
};

export type CustomerAlert = { kind: string; text: string };

/** `GET /v1/me/home`. */
export type CustomerHome = {
  name: string;
  msisdn: string;
  masked: string;
  language: "si" | "ta" | "en";
  notify: string;
  large_text: boolean;
  onboarded: boolean;
  balance_lkr: string;
  pack: CustomerPack | null;
  subscriptions: CustomerSubscription[];
  activity: ActivityRow[];
  alerts: CustomerAlert[];
  open_case_id: string | null;
  open_case_state: string | null;
};

export type CatalogueOffering = {
  offering_id: string;
  name: string;
  category: string;
  price_lkr: string;
  data_gb: string;
  validity_days: number;
  after_cap_speed: string;
  apps: string;
  recommended: boolean;
};

/** A case in the customer's own list (`/v1/me/app`). */
export type CustomerCaseRow = {
  case_id: string;
  case_no: string;
  state: string;
  opened_at: string;
  outcome: string | null;
  headline: string | null;
  open: boolean;
};

/** A Trust Receipt the customer already holds (`/v1/me/receipts`, `/v1/me/app`). */
export type CustomerReceiptRow = {
  receipt_id: string;
  issued_at: string;
  corrected_lkr: string;
  summary: string;
  case_id: string;
};

export type CustomerNotification = {
  kind: string;
  text: string;
  receipt_id?: string;
};

export type FamilyMember = {
  name: string;
  masked: string;
  msisdn: string;
  pack: string | null;
  safeguards: string[];
};

/** `GET /v1/me/app`, and what every `/v1/me/*` write returns. */
export type CustomerApp = CustomerHome & {
  catalogue: CatalogueOffering[];
  safeguards: Record<string, unknown>;
  blocked_merchants: string[];
  cases: CustomerCaseRow[];
  receipts: CustomerReceiptRow[];
  notifications: CustomerNotification[];
  network: { status: string; text: string; eta: string | null };
  family: FamilyMember[];
  usage: {
    data_used_gb: string | null;
    data_cap_gb: string | null;
    voice_minutes: number;
    sms: number;
  };
};

/** `GET /v1/me/cases`. */
export type MyCaseRow = {
  case_id: string;
  case_no: string;
  state: string;
  channel: string;
  opened_at: string;
  outcome: string | null;
};

/* ------------------------------------------------------------------------ *
 * Policy governance (D3), Complaint Autopsy (D1) and Foresight (C4).
 *
 * The backend returns `dict[str, Any]` from these routes and publishes no
 * response model, so the schema types them open and the SDK declares the shape
 * here. When the backend publishes models, these come out and the generated
 * types take over.
 * ------------------------------------------------------------------------ */

export type PolicyApproval = {
  approver_ref: string;
  role: string;
  at: string;
  mfa_step_up: boolean;
};

export type PolicyImpact = {
  cases_evaluated: number;
  changed: number;
  /** A string, not a number: money is Decimal on the wire (I3). */
  money_delta_lkr: string;
  candidate_summary: string;
};

export type PolicyChangeView = {
  change_id: string;
  key: string;
  candidate: Record<string, unknown>;
  change_class: string;
  maker_ref: string;
  /** draft | in_review | approved | scheduled | active | superseded | rejected */
  state: string;
  reason: string;
  approvals_needed: number;
  approvals: PolicyApproval[];
  impact: PolicyImpact | null;
  scheduled_for: string | null;
  activated_at: string | null;
  /** The change this one replaces, and the only thing a reversal can restore. */
  supersedes: string | null;
  [key: string]: unknown;
};

export type ScenarioView = {
  scenario_id: string;
  version_id: string;
  version: number;
  supersedes: string | null;
  created_at: string;
  created_by: string;
  name: string;
  change_type: string;
  effective_date: string;
  /** Exact decimals on the wire, as strings. Never parse these to float. */
  affected_share: string;
  severity: string;
  affected_products: string[];
  business_context: string;
};

export type ForesightPrediction = {
  theme: string;
  segment: string;
  band: string;
  relative_score: string;
  mitigation: string;
};

export type ForesightReport = {
  report_id: string;
  scenario: string;
  scenario_id: string;
  effective_date: string | null;
  generated_at: string | null;
  /** What the numbers rest on. Render it: an unbasised figure is a guess. */
  basis: string;
  caveats: string[];
  backtested: boolean;
  decision_ready: boolean;
  predictions: ForesightPrediction[];
};

export type ForesightRun = {
  run_id: string;
  scenario_version_id: string;
  status: string;
  requested_at: string;
  requested_by: string;
  started_at: string | null;
  finished_at: string | null;
  report_id: string | null;
  failure: string | null;
  poll_url: string;
  /** Present only when an Idempotency-Key matched an earlier request (I8). */
  replayed?: boolean;
  report?: ForesightReport | null;
};

export type ForesightCalibration = {
  calibration_id: string;
  computed_at: string;
  computed_by: string;
  launch_ids: string[];
  status: string;
  calibrated: boolean;
  launches: number;
  real_launches: number;
  compared: number;
  /** `null`, not 0, when nothing was comparable: a 0.000 reads as flawless. */
  mean_absolute_band_error: string | null;
  signed_band_error: string | null;
  exact_band_rate: string | null;
  top_theme_hit_rate: string | null;
  theme_recall: string | null;
  segment_rank_correlation: string | null;
  unpredicted: { theme: string; segment: string; band: string }[];
  unobserved: { theme: string; segment: string }[];
  basis: string;
  caveats: string[];
  summary: string;
};

export type ForesightSpike = {
  spike_id: string;
  scope: string;
  /** A code, never a name. The event this becomes forbids a `name` field. */
  scope_ref: string;
  window_start: string;
  window_end: string;
  observed: number;
  baseline: string;
  ratio: string | null;
  detected_at: string;
  basis: string;
  caveats: string[];
};

export type AutopsyCluster = {
  cluster_id: string;
  label: string;
  size: number;
  status: string;
  status_label: string;
  mapping_label: string;
  hypothesis: boolean;
  suggested_rule_id: string | null;
  languages: Record<string, number>;
  representative_masked_complaints: string[];
  synthetic_demo_trend: Record<string, number>;
  reviews?: { reviewer: string; accepted: boolean; at: string; note: string }[];
};

export type AutopsyWorkspace = {
  clusters: AutopsyCluster[];
  complaint_count: number;
  languages: Record<string, number>;
  clustering_method: string;
  clustering_disclosure: string;
  hypothesis: boolean;
  synthetic: boolean;
  note: string;
};
