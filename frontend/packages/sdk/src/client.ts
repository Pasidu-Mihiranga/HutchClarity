import type { components } from "./generated/schema";
import type {
  ApiPath,
  BodyOf,
  HttpMethod,
  MethodsOf,
  OnlyIfOpen,
  PathParamsOf,
  QueryOf,
  SuccessBody,
} from "./routes";
import type {
  AlertQueue,
  OfferCheckView,
  OfferRecordBody,
  OfferView,
  AlertView,
  ApproveResult,
  AuditGrantView,
  AuditHealth,
  AuditRecordVerdict,
  AuditRecovery,
  AuditTrailPage,
  AutopsyCluster,
  AutopsyWorkspace,
  CaseSummary,
  CustomerApp,
  CustomerHome,
  CustomerReceiptRow,
  DecisionView,
  DemoSubscriber,
  ExecutionView,
  ForesightCalibration,
  ForesightRun,
  ForesightSpike,
  LogoutResult,
  MyCaseRow,
  OpenCaseBody,
  OtpRequestResult,
  PlanView,
  PolicyChangeView,
  PreferencesBody,
  ProposeBody,
  QueueItem,
  SafeguardKind,
  ScenarioView,
  SessionRecord,
  SessionView,
  SignedReceipt,
  SignInMethods,
  StaffLoginRequest,
  StaffSessionRequest,
  StepUpResult,
  SwitchStateView,
  TimelineView,
  TranscriptPayload,
  VerificationView,
} from "./types";

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

function resolveBase(baseUrl?: string): string {
  const fromEnv =
    typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_API_BASE
      : undefined;
  return (baseUrl ?? fromEnv ?? "http://localhost:8000").replace(/\/$/, "");
}

/** The CSRF cookie the API sets beside a session cookie. Readable by design. */
const CSRF_COOKIE = "clarity_csrf";
const CSRF_HEADER = "X-CSRF-Token";

function readCsrfCookie(): string | null {
  if (typeof document === "undefined") return null;
  const found = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${CSRF_COOKIE}=`));
  return found ? decodeURIComponent(found.slice(CSRF_COOKIE.length + 1)) : null;
}

/** Fill `{placeholders}` in a path template, encoding each value. */
export function expandPath(template: string, params?: Record<string, unknown>): string {
  return template.replace(/\{([^}]+)\}/g, (_, name: string) => {
    const value = params?.[name];
    if (value === undefined || value === null) {
      throw new Error(`missing path parameter "${name}" for ${template}`);
    }
    return encodeURIComponent(String(value));
  });
}

function queryString(query?: Record<string, unknown>): string {
  if (!query) return "";
  const out = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") out.set(key, String(value));
  }
  const text = out.toString();
  return text ? `?${text}` : "";
}

/**
 * Let a request body omit a field the backend gives a default.
 *
 * `openapi-typescript` marks any property carrying a `default` as
 * non-optional. That is right for a response, where the server always sends
 * the value, and wrong for a request body, where omitting it is exactly how
 * the caller asks for the default. The OpenAPI document agrees with the
 * backend here: `version`, `candidate_summary`, `note` and `seed` are all
 * outside their schema's `required` array, so the call succeeds and only the
 * generated type objects.
 *
 * Deliberately narrow. It never invents a value, it only lets an omitted one
 * through. Writing the server's default into the client instead would pin it
 * here and diverge silently the day the backend changed it.
 */
function omittingServerDefaults<T>(body: object): T {
  return body as T;
}

/** What a caller may pass for one route. Every part is typed from the schema. */
type CallOptions<P extends ApiPath, M extends HttpMethod> = {
  path?: PathParamsOf<P, M>;
  query?: QueryOf<P, M>;
  body?: BodyOf<P, M>;
  /**
   * Request headers this route needs beyond the ones every call sends.
   *
   * Deliberately a plain record rather than typed from the schema's `header`
   * parameters: a required header is the route's business and the generated
   * types model it inconsistently, so typing it here would reject calls the
   * backend accepts. `POST /v1/foresight/runs` is the case that needs it, and
   * it requires `Idempotency-Key` (I8).
   */
  headers?: Record<string, string>;
};

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

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    if (!headers.has("Content-Type") && init.body) {
      headers.set("Content-Type", "application/json");
    }
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }
    // The session may instead be an HttpOnly cookie (B4), which the browser
    // only sends cross-origin when credentials are asked for. The API pins
    // CORS to the apps' own origins, which is what makes that safe, and
    // echoes the CSRF token back from the cookie the page can read.
    const csrf = readCsrfCookie();
    if (csrf && !headers.has(CSRF_HEADER)) {
      headers.set(CSRF_HEADER, csrf);
    }

    const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers,
      credentials: "include",
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

  /**
   * The one way a route is called. `path` must be a path the schema defines,
   * `method` one that path defines, and the params, query and body are the
   * schema's. The result is the schema's success body, so nothing here can
   * disagree with the backend without `tsc` failing after `sdk:generate`.
   */
  private call<P extends ApiPath, M extends MethodsOf<P>>(
    method: M,
    path: P,
    options: CallOptions<P, M> = {},
  ): Promise<SuccessBody<P, M>> {
    return this.request<SuccessBody<P, M>>(
      `${expandPath(path, options.path as Record<string, unknown> | undefined)}${queryString(
        options.query as Record<string, unknown> | undefined,
      )}`,
      {
        method: method.toUpperCase(),
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        headers: options.headers,
      },
    );
  }

  /**
   * Like `call`, for a route whose response the backend publishes no model for
   * (it returns an open dictionary). The caller states the shape; the route
   * itself is still checked against the schema, and the trailing guard stops
   * this being used on a route the schema does type.
   */
  private declared<R, P extends ApiPath, M extends MethodsOf<P>>(
    method: M,
    path: P,
    options: CallOptions<P, M> = {},
    ..._open: OnlyIfOpen<P, M>
  ): Promise<R> {
    return this.call(method, path, options) as unknown as Promise<R>;
  }

  /**
   * The generated `SessionView` marks `roles` and `permissions` optional
   * because the server defaults them; the API always sends both, so callers
   * get arrays and never have to guard.
   */
  private session(pending: Promise<components["schemas"]["SessionView"]>): Promise<SessionView> {
    return pending.then((view) => ({
      ...view,
      roles: view.roles ?? [],
      permissions: view.permissions ?? [],
    }));
  }

  /* ------------------------------------------------------------ platform */

  health(): Promise<{ status: string }> {
    return this.declared("get", "/health");
  }

  /* ---------------------------------------------------------------- auth */

  requestOtp(msisdn: string): Promise<OtpRequestResult> {
    return this.declared("post", "/v1/auth/otp/request", { body: { msisdn } });
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
    return this.declared("get", "/v1/demo/inbox", { query: { msisdn } });
  }

  /**
   * Verify a code against the challenge that issued it.
   *
   * Takes the `challenge_id` from `requestOtp`, not the number. This used to
   * send `{ msisdn, code }`, which `OtpVerify` rejects with a 422, so
   * customer-web sign-in never worked: the login page caught the error and
   * wrote a placeholder token, which hid it.
   */
  verifyOtp(challengeId: string, code: string): Promise<SessionView> {
    return this.session(
      this.call("post", "/v1/auth/otp/verify", {
        body: { challenge_id: challengeId, code, channel: "web" },
      }),
    );
  }

  refreshSession(refreshToken: string): Promise<SessionView> {
    return this.session(
      this.call("post", "/v1/auth/refresh", { body: { refresh_token: refreshToken } }),
    );
  }

  staffSession(body: StaffSessionRequest): Promise<SessionView> {
    return this.session(
      this.call("post", "/v1/auth/staff/session", { body: { step_up: false, ...body } }),
    );
  }

  /** Directory sign-in. The server assigns the role. Synthetic profiles only. */
  staffLogin(body: StaffLoginRequest): Promise<SessionView> {
    return this.session(
      this.call("post", "/v1/auth/staff/login", { body: { step_up_code: "", ...body } }),
    );
  }

  whoami(): Promise<SessionView> {
    return this.session(this.call("get", "/v1/auth/me"));
  }

  /** Which staff sign-in paths this deployment offers. Public. */
  signInMethods(): Promise<SignInMethods> {
    return this.declared("get", "/v1/auth/sign-in-methods");
  }

  /** Revokes the session on the server and clears the cookie. */
  logout(): Promise<LogoutResult> {
    return this.declared("post", "/v1/auth/logout");
  }

  /**
   * Ask the provider to re-authenticate before an approval (B2). Returns where
   * to send the browser; nothing is granted by this call itself.
   */
  stepUp(returnTo: string): Promise<StepUpResult> {
    return this.declared("post", "/v1/auth/staff/step-up", { query: { return_to: returnTo } });
  }

  /** Where the browser goes to sign in through the provider. A redirect, not a fetch. */
  oidcStartUrl(returnTo: string): string {
    return `${this.baseUrl}/v1/auth/staff/oidc/start${queryString({ return_to: returnTo })}`;
  }

  /** The signed-in person's own live sessions. Never carries a token. */
  listSessions(): Promise<{ sessions: SessionRecord[] }> {
    return this.declared("get", "/v1/auth/sessions");
  }

  /** Sign out everywhere. `keepCurrent` leaves this device signed in. */
  endOtherSessions(keepCurrent = true): Promise<{ ended: number; kept_current: boolean }> {
    return this.declared("delete", "/v1/auth/sessions", { query: { keep_current: keepCurrent } });
  }

  /* --------------------------------------------------------------- cases */

  deskQueue(): Promise<QueueItem[]> {
    return this.call("get", "/v1/desk/queue");
  }

  createCase(body: OpenCaseBody): Promise<CaseSummary> {
    return this.call("post", "/v1/cases", {
      body: { channel: "web", language: "en", customer_requested_human: false, ...body },
    });
  }

  getCase(caseId: string): Promise<CaseSummary> {
    return this.call("get", "/v1/cases/{case_id}", { path: { case_id: caseId } });
  }

  evaluateCase(caseId: string): Promise<DecisionView> {
    return this.call("post", "/v1/cases/{case_id}/evaluate", { path: { case_id: caseId } });
  }

  caseTimeline(caseId: string): Promise<TimelineView> {
    return this.call("get", "/v1/cases/{case_id}/timeline", { path: { case_id: caseId } });
  }

  /**
   * What was said on a case, oldest first and masked (ADR-0040).
   *
   * Subject bound: a customer sees their own, staff with `case:read:any` see
   * it so a handoff carries what was already explained.
   */
  caseTranscript(caseId: string): Promise<TranscriptPayload> {
    return this.declared("get", "/v1/cases/{case_id}/transcript", { path: { case_id: caseId } });
  }

  proposeCase(caseId: string, body: ProposeBody = { created_by: "desk:console" }): Promise<PlanView> {
    return this.call("post", "/v1/cases/{case_id}/proposals", {
      path: { case_id: caseId },
      body: { created_by: "desk:console", ...body },
    });
  }

  /** Staff approval of a plan. */
  approveCase(caseId: string, body: { plan_id: string; role: string }): Promise<ApproveResult> {
    return this.declared("post", "/v1/cases/{case_id}/approve", {
      path: { case_id: caseId },
      body,
    });
  }

  /** The customer confirms a one-tap plan. */
  confirmCase(caseId: string, planId: string): Promise<ExecutionView> {
    return this.call("post", "/v1/cases/{case_id}/confirm", {
      path: { case_id: caseId },
      body: { plan_id: planId },
    });
  }

  /* ------------------------------------------------------------ receipts */

  getReceipt(receiptId: string): Promise<SignedReceipt> {
    return this.declared("get", "/v1/receipts/{receipt_id}", { path: { receipt_id: receiptId } });
  }

  verifyReceipt(receiptId: string): Promise<VerificationView> {
    return this.call("post", "/v1/receipts/{receipt_id}/verify", {
      path: { receipt_id: receiptId },
    });
  }

  /**
   * The QR image for a receipt (`GET /v1/receipts/{id}/qr.svg`, public). It
   * encodes only the public verify URL, so scanning it re-checks the signed
   * receipt on the server rather than trusting anything printed beside it.
   */
  receiptQrUrl(receiptId: string): string {
    return `${this.baseUrl}/v1/receipts/${encodeURIComponent(receiptId)}/qr.svg`;
  }

  /* ------------------------------------------------------ the customer ("me") */

  /** The one customer read: every screen renders this payload. */
  myApp(): Promise<CustomerApp> {
    return this.declared("get", "/v1/me/app");
  }

  myHome(): Promise<CustomerHome> {
    return this.declared("get", "/v1/me/home");
  }

  myCases(): Promise<MyCaseRow[]> {
    return this.declared("get", "/v1/me/cases");
  }

  myReceipts(): Promise<CustomerReceiptRow[]> {
    return this.declared("get", "/v1/me/receipts");
  }

  /** Each write below returns the refreshed `CustomerApp`. */
  reload(amountLkr: string): Promise<CustomerApp> {
    return this.declared("post", "/v1/me/reload", { body: { amount_lkr: amountLkr } });
  }

  purchasePackage(offeringId: string): Promise<CustomerApp> {
    return this.declared("post", "/v1/me/packages/{offering_id}/purchase", {
      path: { offering_id: offeringId },
    });
  }

  cancelSubscription(subscriptionId: string): Promise<CustomerApp> {
    return this.declared("post", "/v1/me/subscriptions/{subscription_id}/cancel", {
      path: { subscription_id: subscriptionId },
    });
  }

  setSafeguard(kind: SafeguardKind, value: string): Promise<CustomerApp> {
    return this.declared("post", "/v1/me/safeguards", { body: { kind, value } });
  }

  addFamilyMember(msisdn: string): Promise<CustomerApp> {
    return this.declared("post", "/v1/me/family", { body: { msisdn } });
  }

  savePreferences(body: PreferencesBody): Promise<CustomerApp> {
    return this.declared("post", "/v1/me/preferences", {
      body: { large_text: false, notify: "important", ...body },
    });
  }

  /* ------------------------------------------- offer verification (OFFER01) */

  /**
   * Check a message against the offers on record for the signed-in number.
   *
   * The verdict is `ON_RECORD`, `NOT_ON_RECORD` or `NEEDS_A_PERSON` and is
   * never a scam flag: the records say what HUTCH sent, and the inference
   * past that belongs to the person holding the phone.
   */
  verifyOfferMessage(message: string): Promise<OfferCheckView> {
    // `signals` and `simulated` carry server defaults, which the generator
    // marks optional on the response as well as the request. The API always
    // sends both, so they are filled here and callers get an array rather
    // than guarding one. Same reason as `session()` above.
    return this.call("post", "/v1/offers/verify", { body: { message } }).then((view) => ({
      ...view,
      signals: view.signals ?? [],
      simulated: view.simulated ?? true,
    }));
  }

  /** Every recorded offer. Security admin only (`offer:manage`). */
  listOffers(): Promise<OfferView[]> {
    return this.call("get", "/v1/admin/offers");
  }

  /** Record what HUTCH sent to a number. Security admin only. */
  recordOffer(body: OfferRecordBody): Promise<OfferView> {
    return this.call("post", "/v1/admin/offers", {
      body: omittingServerDefaults({ offer_code: "", ...body }),
    });
  }

  /* ---------------------------------------------------------------- demo */

  demoSubscribers(): Promise<DemoSubscriber[]> {
    return this.call("get", "/v1/demo/subscribers");
  }

  demoReset(): Promise<Record<string, unknown>> {
    return this.declared("post", "/v1/demo/reset");
  }

  /* ------------------------------------------------------------ insights */

  /** Operations dashboards, folded from the event log (D2). */
  insightsDashboards(): Promise<Record<string, unknown>> {
    return this.declared("get", "/v1/insights/dashboards");
  }

  /* ------------------------------------------------------- policy studio */
  //
  // These routes existed since M-GOV with no caller: the Studio page wrote
  // drafts to `sessionStorage`, so nothing a policy author did there reached
  // the governance lifecycle (D3).

  /** Every change and where it is in its lifecycle. */
  policyChanges(): Promise<PolicyChangeView[]> {
    return this.declared("get", "/v1/admin/policy/changes");
  }

  /** Open a change. The class comes from the artefact's tags, not from here. */
  draftPolicyChange(body: {
    key: string;
    value: unknown;
    reason: string;
    scope?: Record<string, string>;
    version?: number;
    effective_from?: string | null;
  }): Promise<PolicyChangeView> {
    return this.declared("post", "/v1/admin/policy/changes", {
      body: omittingServerDefaults(body),
    });
  }

  /** Attach the replay that says what this change would have done. */
  reviewPolicyChange(
    changeId: string,
    body: { cases_evaluated: number; candidate_summary?: string },
  ): Promise<PolicyChangeView> {
    return this.declared("post", "/v1/admin/policy/changes/{change_id}/review", {
      path: { change_id: changeId },
      body: omittingServerDefaults(body),
    });
  }

  /** Approve. The maker cannot be an approver, and the API enforces it. */
  approvePolicyChange(changeId: string): Promise<PolicyChangeView> {
    return this.declared("post", "/v1/admin/policy/changes/{change_id}/approve", {
      path: { change_id: changeId },
      body: {},
    });
  }

  schedulePolicyChange(
    changeId: string,
    body: { effective_from: string },
  ): Promise<PolicyChangeView> {
    return this.declared("post", "/v1/admin/policy/changes/{change_id}/schedule", {
      path: { change_id: changeId },
      body,
    });
  }

  activatePolicyChange(changeId: string): Promise<PolicyChangeView> {
    return this.declared("post", "/v1/admin/policy/changes/{change_id}/activate", {
      path: { change_id: changeId },
      body: {},
    });
  }

  /**
   * Draft a governed reversal.
   *
   * This does not undo anything by itself: it opens a *new* change that
   * restores the version the named one replaced, and that change goes through
   * the same review and approval path as any other. A change that supersedes
   * nothing has nothing to restore, and the API refuses it.
   */
  rollbackPolicyChange(
    changeId: string,
    body: { reason: string },
  ): Promise<PolicyChangeView> {
    return this.declared("post", "/v1/admin/policy/changes/{change_id}/rollback", {
      path: { change_id: changeId },
      body,
    });
  }

  /* ------------------------------------------------------ complaint autopsy */

  /** The reviewer workspace. `desk:queue:read`: seeing is not ruling. */
  autopsyClusters(): Promise<AutopsyWorkspace> {
    return this.declared("get", "/v1/autopsy/clusters");
  }

  /** Record a first verdict. The reviewer is the caller, never a field. */
  reviewCluster(
    clusterId: string,
    body: { accept: boolean; note?: string },
  ): Promise<AutopsyCluster> {
    return this.declared("post", "/v1/autopsy/clusters/{cluster_id}/review", {
      path: { cluster_id: clusterId },
      body: omittingServerDefaults(body),
    });
  }

  /** Change a verdict, keeping the one it replaces. The note is required. */
  supersedeClusterReview(
    clusterId: string,
    body: { accept: boolean; note: string },
  ): Promise<AutopsyCluster> {
    return this.declared("post", "/v1/autopsy/clusters/{cluster_id}/supersede", {
      path: { cluster_id: clusterId },
      body,
    });
  }

  /**
   * Propose a policy change from a confirmed cluster (AU02).
   *
   * This publishes nothing. It creates a change in the draft state; approval,
   * scheduling and activation happen through governance, by somebody else.
   */
  proposeRuleCandidate(
    clusterId: string,
    body: { key: string; value: string; rationale: string },
  ): Promise<{ change_id: string; state: string; cluster_id: string; note: string }> {
    return this.declared("post", "/v1/autopsy/clusters/{cluster_id}/rule-candidate", {
      path: { cluster_id: clusterId },
      body,
    });
  }

  /* ----------------------------------------------------------- foresight */
  //
  // `GET /v1/demo/foresight` was the only address foresight had, and the
  // console read it because Workstream C had not landed. C landed, so the
  // demo route is gone and these replace it (C4, D4).

  /** The latest version of every scenario family, newest first. */
  foresightScenarios(): Promise<{ scenarios: ScenarioView[] }> {
    return this.declared("get", "/v1/foresight/scenarios");
  }

  /** Every version of one family, oldest first. */
  foresightScenario(scenarioId: string): Promise<{
    scenario_id: string;
    versions: ScenarioView[];
  }> {
    return this.declared("get", "/v1/foresight/scenarios/{scenario_id}", {
      path: { scenario_id: scenarioId },
    });
  }

  /** Every run, newest first. The report is only on the single-run read. */
  foresightRuns(): Promise<{ runs: ForesightRun[] }> {
    return this.declared("get", "/v1/foresight/runs");
  }

  /** One run and its report. This is the `poll_url` a request hands back. */
  foresightRun(runId: string): Promise<ForesightRun> {
    return this.declared("get", "/v1/foresight/runs/{run_id}", {
      path: { run_id: runId },
    });
  }

  /**
   * Ask for a rehearsal. Answers 202 with a `poll_url`.
   *
   * `Idempotency-Key` is required by the route, not optional (I8). Foresight
   * moves no money, so the risk is not a double charge but a double finding:
   * two runs of one scenario, reported twice, is how a rehearsal gets counted
   * as two pieces of evidence. A repeat returns the original run with
   * `replayed: true` rather than starting a second one.
   */
  requestForesightRun(
    scenarioVersionId: string,
    idempotencyKey: string,
  ): Promise<ForesightRun> {
    return this.declared("post", "/v1/foresight/runs", {
      // No `seed`: the service picks one and records it on the run, so a
      // rehearsal stays reproducible without the caller inventing entropy.
      body: omittingServerDefaults({ scenario_version_id: scenarioVersionId }),
      headers: { "Idempotency-Key": idempotencyKey },
    });
  }

  /** The latest calibration, or 404 when no backtest has run. */
  foresightCalibration(): Promise<ForesightCalibration> {
    return this.declared("get", "/v1/foresight/calibration");
  }

  /** Early-warning spikes from the radar (C5). */
  foresightSpikes(): Promise<{ spikes: ForesightSpike[] }> {
    return this.declared("get", "/v1/foresight/spikes");
  }

  /** Seed one evaluated case per demo subscriber (Desk "Create demo cases"). */
  async demoSeed(): Promise<number> {
    const people = await this.demoSubscribers();
    for (const person of people) {
      const opened = await this.createCase({ msisdn: person.msisdn, channel: "whatsapp" });
      await this.evaluateCase(opened.case_id);
    }
    return people.length;
  }

  /* --------------------------------------------------------------- admin */

  listSwitches(): Promise<SwitchStateView> {
    return this.declared("get", "/v1/admin/switches");
  }

  flipSwitch(body: { key: string; enabled: boolean; reason: string }): Promise<SwitchStateView> {
    return this.declared("post", "/v1/admin/switches", { body });
  }

  suspendMerchant(body: {
    merchant_id: string;
    reason: string;
    subscriber_msisdn?: string;
  }): Promise<Record<string, unknown>> {
    return this.declared("post", "/v1/admin/merchants/suspend", { body });
  }

  /* ------------------------------------------- audit assurance (plan 5.8) */

  /**
   * Chain health. Deliberately *not* recorded as `audit.read` by the server: a
   * dashboard polls this, and recording every poll would make the console trip
   * the `mass_audit_read` rule. Reading the trail itself is recorded.
   */
  auditHealth(): Promise<AuditHealth> {
    return this.declared("get", "/v1/audit/health");
  }

  /** The trail. This one *is* recorded: who looked, with which filters. */
  auditTrail(params?: {
    actor_ref?: string;
    event_type?: string;
    case_id?: string;
    after_seq?: number;
    limit?: number;
  }): Promise<AuditTrailPage> {
    return this.declared("get", "/v1/audit", { query: params });
  }

  auditRecovery(): Promise<AuditRecovery> {
    return this.declared("get", "/v1/audit/recovery");
  }

  /** Recompute one record's hashes. Changes nothing. */
  verifyAuditRecord(seq: number): Promise<AuditRecordVerdict> {
    return this.declared("post", "/v1/audit/records/{seq}/verify", { path: { seq } });
  }

  listAuditGrants(): Promise<{ grants: AuditGrantView[] }> {
    return this.declared("get", "/v1/audit/grants");
  }

  listAlerts(openOnly = false): Promise<AlertQueue> {
    return this.declared("get", "/v1/assurance/alerts", { query: { open_only: openOnly } });
  }

  acknowledgeAlert(alertId: string): Promise<AlertView> {
    return this.declared("post", "/v1/assurance/alerts/{alert_id}/acknowledge", {
      path: { alert_id: alertId },
    });
  }

  investigateAlert(alertId: string): Promise<AlertView> {
    return this.declared("post", "/v1/assurance/alerts/{alert_id}/investigate", {
      path: { alert_id: alertId },
    });
  }

  disposeAlert(
    alertId: string,
    body: { disposition: string; reason: string },
  ): Promise<AlertView> {
    return this.declared("post", "/v1/assurance/alerts/{alert_id}/dispose", {
      path: { alert_id: alertId },
      body,
    });
  }
}

export function createClarityClient(
  options?: ClarityClientOptions,
): ClarityClient {
  return new ClarityClient(options);
}
