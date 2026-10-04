export type ClarityClientOptions = {
  baseUrl?: string;
  token?: string;
  fetchImpl?: typeof fetch;
};

/**
 * An error the API answered with, carrying the status it answered.
 *
 * Without the status a caller cannot tell "this receipt does not exist" from
 * "the API is unreachable", and the verify page needs that distinction: one is
 * a real verdict about a receipt, the other is no verdict at all. It used to
 * guess, and guessed "valid" for both (FE01).
 */
export class ClarityApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ClarityApiError";
    this.status = status;
  }
}

export type OtpRequestResult = {
  /** Required by `verifyOtp`: the challenge this code belongs to. */
  challenge_id: string;
  sent_to?: string;
  simulated?: boolean;
  detail?: string;
  /** Older field names kept so a caller reading them still compiles. */
  ok?: boolean;
  msisdn_masked?: string;
  message?: string;
};

export type OtpVerifyResult = {
  token: string;
  expires_at: string;
  principal: Record<string, unknown>;
  rls?: Record<string, unknown>;
};

export type CasePayload = {
  case_id?: string;
  case_no?: string;
  id?: string;
  state?: string;
  msisdn_masked?: string;
  channel?: string;
  [key: string]: unknown;
};

export type ReceiptPayload = {
  receipt_id?: string;
  id?: string;
  valid?: boolean;
  chain_ok?: boolean;
  status?: string;
  reason?: string;
  corrected_lkr?: string;
  key_id?: string;
  [key: string]: unknown;
};

export type SessionView = {
  token: string;
  expires_at?: string | null;
  subject: string;
  roles: string[];
  assurance: string;
  permissions: string[];
};

export type QueueItem = {
  case_id: string;
  case_no: string;
  state: string;
  outcome?: string | null;
  cause?: string | null;
  money_at_stake_lkr?: string | null;
  msisdn_masked: string;
  channel: string;
  reason?: string | null;
  plan_id?: string | null;
};

export type RuledOutItem = {
  rule_id: string;
  [key: string]: unknown;
};

export type DecisionPayload = {
  outcome: string;
  cause?: { rule_id: string; rule_version?: string; confidence?: number } | null;
  amount_lkr?: string | null;
  rationale?: string[];
  allowed_actions?: string[];
  handoff_reason?: string | null;
  ruled_out?: RuledOutItem[];
  unknown?: RuledOutItem[];
  [key: string]: unknown;
};

export type TimelineEvent = {
  source: string;
  event_type: string;
  amount_lkr?: string | null;
  occurred_at?: string;
  [key: string]: unknown;
};

export type TimelineSource = {
  source: string;
  completeness: string;
};

export type TimelinePayload = {
  events: TimelineEvent[];
  sources: TimelineSource[];
  snapshot_hash?: string;
  [key: string]: unknown;
};

export type ProposalPayload = {
  plan_id: string;
  [key: string]: unknown;
};

export type ApproveResult = {
  status?: string;
  detail?: string;
  case_id?: string;
  plan_id?: string;
  receipt_id?: string;
  confirmed_by?: string;
  actions?: Array<{
    type: string;
    before?: { balance_lkr?: string };
    after?: { balance_lkr?: string };
  }>;
  [key: string]: unknown;
};

export type DemoSubscriber = {
  name: string;
  msisdn: string;
  masked: string;
  language?: string;
  balance_lkr?: string;
  scenario?: string;
};

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

export type StaffSessionRequest = {
  user_ref: string;
  roles: string[];
  step_up?: boolean;
};

export type StaffLoginRequest = {
  username: string;
  password: string;
  step_up_code?: string;
};

function resolveBase(baseUrl?: string): string {
  const fromEnv =
    typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_API_BASE
      : undefined;
  return (baseUrl ?? fromEnv ?? "http://localhost:8000").replace(/\/$/, "");
}

export class ClarityClient {
  private baseUrl: string;
  private token?: string;
  private fetchImpl: typeof fetch;

  constructor(options: ClarityClientOptions = {}) {
    this.baseUrl = resolveBase(options.baseUrl);
    this.token = options.token;
    this.fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);
  }

  getToken(): string | undefined {
    return this.token;
  }

  setToken(token: string | undefined): void {
    this.token = token;
  }

  private async request<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(init.headers);
    if (!headers.has("Content-Type") && init.body) {
      headers.set("Content-Type", "application/json");
    }
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }

    const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      let detail = text || res.statusText;
      try {
        const parsed = JSON.parse(text) as {
          detail?: unknown;
          title?: string;
        };
        // FastAPI reports a validation error as a *list* of field errors.
        // Assigning that straight to a message rendered as
        // "[object Object],[object Object]" in the UI, which told nobody
        // anything. Flatten it to the field and the reason instead.
        if (Array.isArray(parsed.detail)) {
          detail = parsed.detail
            .map((item) => {
              const entry = item as { loc?: unknown[]; msg?: string };
              const where = Array.isArray(entry.loc) ? entry.loc.join(".") : "";
              return where ? `${where}: ${entry.msg ?? "invalid"}` : (entry.msg ?? "invalid");
            })
            .join("; ");
        } else if (typeof parsed.detail === "string") {
          detail = parsed.detail;
        } else {
          detail = parsed.title || detail;
        }
      } catch {
        /* keep raw text */
      }
      throw new ClarityApiError(detail, res.status);
    }

    if (res.status === 204) {
      return undefined as T;
    }

    return (await res.json()) as T;
  }

  health(): Promise<{ status: string }> {
    return this.request("/health");
  }

  requestOtp(msisdn: string): Promise<OtpRequestResult> {
    return this.request("/v1/auth/otp/request", {
      method: "POST",
      body: JSON.stringify({ msisdn }),
    });
  }

  /**
   * The simulated SMS inbox. Synthetic profiles only: the route is gated by
   * `demo_only` and returns 404 in `prod` (I9).
   *
   * The sign-in code is generated per challenge and is **not** "any six
   * digits", which the login page used to claim. Reading it back is the only
   * way to complete a sign-in in the prototype.
   */
  demoInbox(msisdn: string): Promise<{ code: string; msisdn?: string; text?: string }> {
    return this.request(`/v1/demo/inbox?msisdn=${encodeURIComponent(msisdn)}`);
  }

  /**
   * Verify a code against the challenge that issued it.
   *
   * Takes the `challenge_id` from `requestOtp`, not the number. This used to
   * send `{ msisdn, code }`, which `OtpVerify` rejects with a 422, so
   * customer-web sign-in never worked: the login page caught the error and
   * wrote a placeholder token, which hid it.
   */
  verifyOtp(challengeId: string, code: string): Promise<OtpVerifyResult> {
    return this.request("/v1/auth/otp/verify", {
      method: "POST",
      body: JSON.stringify({ challenge_id: challengeId, code }),
    });
  }

  staffSession(body: StaffSessionRequest): Promise<SessionView> {
    return this.request("/v1/auth/staff/session", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  /** Directory sign-in. The server assigns the role. Synthetic profiles only. */
  staffLogin(body: StaffLoginRequest): Promise<SessionView> {
    return this.request("/v1/auth/staff/login", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  whoami(): Promise<SessionView> {
    return this.request("/v1/auth/me");
  }

  deskQueue(): Promise<QueueItem[]> {
    return this.request("/v1/desk/queue");
  }

  createCase(body: Record<string, unknown>): Promise<CasePayload> {
    return this.request("/v1/cases", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  getCase(caseId: string): Promise<CasePayload> {
    return this.request(`/v1/cases/${encodeURIComponent(caseId)}`);
  }

  evaluateCase(caseId: string): Promise<DecisionPayload> {
    return this.request(`/v1/cases/${encodeURIComponent(caseId)}/evaluate`, {
      method: "POST",
    });
  }

  caseTimeline(caseId: string): Promise<TimelinePayload> {
    return this.request(`/v1/cases/${encodeURIComponent(caseId)}/timeline`);
  }

  proposeCase(
    caseId: string,
    body: Record<string, unknown> = { created_by: "desk:console" },
  ): Promise<ProposalPayload> {
    return this.request(`/v1/cases/${encodeURIComponent(caseId)}/proposals`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  approveCase(
    caseId: string,
    body: { plan_id: string; role: string },
  ): Promise<ApproveResult> {
    return this.request(`/v1/cases/${encodeURIComponent(caseId)}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  getReceipt(receiptId: string): Promise<ReceiptPayload> {
    return this.request(`/v1/receipts/${encodeURIComponent(receiptId)}`);
  }

  verifyReceipt(receiptId: string): Promise<ReceiptPayload> {
    return this.request(`/v1/receipts/${encodeURIComponent(receiptId)}/verify`, {
      method: "POST",
    });
  }

  demoSubscribers(): Promise<DemoSubscriber[]> {
    return this.request("/v1/demo/subscribers");
  }

  demoReset(): Promise<Record<string, unknown>> {
    return this.request("/v1/demo/reset", { method: "POST" });
  }

  demoOps(): Promise<Record<string, unknown>> {
    return this.request("/v1/demo/ops");
  }

  demoAutopsy(): Promise<Record<string, unknown>> {
    return this.request("/v1/demo/autopsy");
  }

  demoForesight(): Promise<Record<string, unknown>> {
    return this.request("/v1/demo/foresight");
  }

  /** Seed one evaluated case per demo subscriber (Desk "Create demo cases"). */
  async demoSeed(): Promise<number> {
    const people = await this.demoSubscribers();
    for (const person of people) {
      const opened = await this.createCase({
        msisdn: person.msisdn,
        channel: "whatsapp",
      });
      const caseId = opened.case_id || opened.id;
      if (caseId) await this.evaluateCase(String(caseId));
    }
    return people.length;
  }

  listSwitches(): Promise<SwitchStateView> {
    return this.request("/v1/admin/switches");
  }

  flipSwitch(body: {
    key: string;
    enabled: boolean;
    reason: string;
  }): Promise<SwitchStateView> {
    return this.request("/v1/admin/switches", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  // -- audit assurance (plan 5.8) ------------------------------------------ //

  /**
   * Chain health. Deliberately *not* recorded as `audit.read` by the server: a
   * dashboard polls this, and recording every poll would make the console trip
   * the `mass_audit_read` rule. Reading the trail itself is recorded.
   */
  auditHealth(): Promise<AuditHealth> {
    return this.request("/v1/audit/health");
  }

  /** The trail. This one *is* recorded: who looked, with which filters. */
  auditTrail(params?: {
    actor_ref?: string;
    event_type?: string;
    case_id?: string;
    after_seq?: number;
    limit?: number;
  }): Promise<AuditTrailPage> {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params || {})) {
      if (value !== undefined && value !== "") query.set(key, String(value));
    }
    const suffix = query.toString();
    return this.request(`/v1/audit${suffix ? `?${suffix}` : ""}`);
  }

  auditRecovery(): Promise<AuditRecovery> {
    return this.request("/v1/audit/recovery");
  }

  /** Recompute one record's hashes. Changes nothing. */
  verifyAuditRecord(seq: number): Promise<AuditRecordVerdict> {
    return this.request(`/v1/audit/records/${seq}/verify`, { method: "POST" });
  }

  listAuditGrants(): Promise<{ grants: AuditGrantView[] }> {
    return this.request("/v1/audit/grants");
  }

  listAlerts(openOnly = false): Promise<AlertQueue> {
    return this.request(`/v1/assurance/alerts?open_only=${openOnly}`);
  }

  acknowledgeAlert(alertId: string): Promise<AlertView> {
    return this.request(`/v1/assurance/alerts/${alertId}/acknowledge`, {
      method: "POST",
    });
  }

  investigateAlert(alertId: string): Promise<AlertView> {
    return this.request(`/v1/assurance/alerts/${alertId}/investigate`, {
      method: "POST",
    });
  }

  disposeAlert(
    alertId: string,
    body: { disposition: string; reason: string },
  ): Promise<AlertView> {
    return this.request(`/v1/assurance/alerts/${alertId}/dispose`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  suspendMerchant(body: {
    merchant_id: string;
    reason: string;
    subscriber_msisdn?: string;
  }): Promise<Record<string, unknown>> {
    return this.request("/v1/admin/merchants/suspend", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }
}

export function createClarityClient(
  options?: ClarityClientOptions,
): ClarityClient {
  return new ClarityClient(options);
}
