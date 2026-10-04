import { expect, type Page, type APIRequestContext } from "@playwright/test";

/**
 * One sign-in for the whole suite.
 *
 * **Why this exists.** The OTP service allows five challenges per number per
 * fifteen minutes (`MAX_REQUESTS_PER_WINDOW`), which is the TH1 mitigation
 * against SMS pumping. The suite has more than five tests and every one of
 * them needs a signed-in customer, so a helper that signs in per test runs out
 * of challenges partway through and the rest fail on a 429 that has nothing to
 * do with what they are testing. The first full run of this suite did exactly
 * that.
 *
 * So the token is minted once against the API and injected into
 * `sessionStorage` before each page loads. `storageState` cannot carry it:
 * Playwright persists cookies and `localStorage`, and this app keeps the token
 * in `sessionStorage` so it dies with the tab.
 *
 * The login *page* is still exercised, once, by its own test in
 * `login.spec.ts`. That is the right split: one test proves a customer can
 * sign in, and the rest spend their budget on what they are actually for.
 */

export const DILANI = "+94781234567";

const API = process.env.E2E_API_BASE ?? "http://127.0.0.1:8100";

/** The app's own origin, which is where its cookies live. */
const BASE = process.env.E2E_BASE ?? "http://127.0.0.1:3100";

/** Echoed in the `X-CSRF-Token` header by anything the page sends. */
export const E2E_CSRF = "e2e-csrf-token";


const cached = new Map<string, string>();

/**
 * Mint a customer token through the API, once per subscriber per worker.
 *
 * Cached per number, not globally: the four journeys belong to four different
 * synthetic subscribers, and each one's challenge budget is its own.
 */
export async function customerTokenFor(
  request: APIRequestContext,
  msisdn: string,
): Promise<string> {
  const hit = cached.get(msisdn);
  if (hit) return hit;

  const started = await request.post(`${API}/v1/auth/otp/request`, {
    data: { msisdn },
  });
  expect(started.ok(), `otp request failed: ${started.status()}`).toBeTruthy();
  const { challenge_id } = (await started.json()) as { challenge_id: string };

  // The code is generated per challenge. There is no "any six digits" path:
  // the backend answers 401 to anything else.
  const inbox = await request.get(
    `${API}/v1/demo/inbox?msisdn=${encodeURIComponent(msisdn)}`,
  );
  expect(inbox.ok(), `demo inbox failed: ${inbox.status()}`).toBeTruthy();
  const { code } = (await inbox.json()) as { code: string };

  const verified = await request.post(`${API}/v1/auth/otp/verify`, {
    data: { challenge_id, code },
  });
  expect(verified.ok(), `otp verify failed: ${verified.status()}`).toBeTruthy();
  const { token } = (await verified.json()) as { token: string };

  cached.set(msisdn, token);
  return token;
}

/** Dilani, whose journey most of the suite drives. */
export async function customerToken(request: APIRequestContext): Promise<string> {
  return customerTokenFor(request, DILANI);
}

/**
 * Put the session in place before any page script runs.
 *
 * The session is an `HttpOnly` cookie now (B4), so this sets a cookie rather
 * than writing `sessionStorage`, and the long-standing note about
 * `storageState` not being able to carry it no longer applies: Playwright
 * persists cookies perfectly well. The CSRF token goes in beside it, because a
 * browser holding a session also holds the token it echoes, and a
 * state-changing call without it is refused.
 */
export async function signedIn(page: Page, token: string): Promise<void> {
  const origin = new URL(BASE);
  await page.context().addCookies([
    {
      name: "clarity_customer_session",
      value: token,
      domain: origin.hostname,
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
    {
      name: "clarity_csrf",
      value: E2E_CSRF,
      domain: origin.hostname,
      path: "/",
      sameSite: "Lax",
    },
  ]);
}

/**
 * The other two apps' origins. `baseURL` belongs to customer-web, because
 * most of the suite lives there; the console and the verify page are separate
 * Next.js apps on their own ports, so their specs navigate absolutely.
 */
export const CONSOLE = process.env.E2E_CONSOLE_BASE ?? "http://127.0.0.1:3101";
export const VERIFY = process.env.E2E_VERIFY_BASE ?? "http://127.0.0.1:3102";

/** The other synthetic subscribers, by the outcome their case reaches. */
export const NIMAL = "+94782223333"; // duplicate reload -> AUTO_FIX
export const KUMAR = "+94783334444"; // disclosed fair-use cap -> EXPLAIN_ONLY
export const PRIYA = "+94784445555"; // LKR 12,000 reload, SIM swap -> STAFF_APPROVAL

/**
 * A staff token, minted through the development role picker's own endpoint.
 *
 * Unlike the customer's OTP there is no challenge budget here, so specs may
 * call this freely. `step_up` simulates recent MFA, which an approval above
 * the cap requires.
 */
/** Synthetic directory accounts. The e2e API must load config/staff/synthetic-directory.json. */
const LOGIN_BY_REF: Record<string, { username: string; password: string }> = {
  "agent:nadeesha": { username: "nadeesha", password: "nadeesha-clarity" },
  "sec:dilani": { username: "dilani", password: "dilani-clarity" },
  "ops:stream": { username: "stream", password: "stream-clarity" },
};

const LOGIN_BY_LABEL: Record<string, { username: string; password: string }> = {
  Agent: { username: "agent", password: "agent-clarity" },
  Supervisor: { username: "supervisor", password: "supervisor-clarity" },
  Finance: { username: "finance", password: "finance-clarity" },
  Compliance: { username: "compliance", password: "compliance-clarity" },
  Auditor: { username: "auditor", password: "auditor-clarity" },
  Security: { username: "security", password: "security-clarity" },
  Platform: { username: "platform", password: "platform-clarity" },
  // CX engineering holds `foresight:read` and `config:draft`, which no other
  // synthetic account does, so Foresight and Policy Studio can only be
  // reached as this person (WT-13 steps 7 and 8).
  CX: { username: "cx", password: "cx-clarity" },
  "VAS Ops": { username: "vasops", password: "vasops-clarity" },
};

export async function staffToken(
  request: APIRequestContext,
  userRef: string,
  roles: string[],
  stepUp = false,
): Promise<string> {
  const account = LOGIN_BY_REF[userRef];
  if (!account) {
    throw new Error(`no synthetic login for ${userRef}`);
  }
  const session = await request.post(`${API}/v1/auth/staff/login`, {
    data: {
      username: account.username,
      password: account.password,
      step_up_code: stepUp ? "step-up" : "",
    },
  });
  expect(session.ok(), `staff login failed: ${session.status()}`).toBeTruthy();
  const body = (await session.json()) as { token: string; roles: string[] };
  expect(body.roles).toEqual(expect.arrayContaining(roles));
  return body.token;
}

/** Sign in through the desk form. The label is the role the directory assigns. */
export async function signInOnDesk(
  page: import("@playwright/test").Page,
  roleLabel: string,
  stepUp = true,
): Promise<void> {
  const account = LOGIN_BY_LABEL[roleLabel];
  if (!account) {
    throw new Error(`no synthetic login for ${roleLabel}`);
  }
  const signOut = page.getByRole("button", { name: "Sign out" });
  if (await signOut.isVisible().catch(() => false)) {
    await signOut.click();
  }
  await page.getByLabel("Username").fill(account.username);
  await page.getByLabel("Password").fill(account.password);
  if (stepUp) {
    await page.getByLabel("Step-up code").fill("step-up");
  } else {
    await page.getByLabel("Step-up code").fill("");
  }
  await page.getByRole("button", { name: "Sign in" }).click();
  // Wait until the desk shows the signed-in staff member. Without this the
  // next call could look for "Sign out" before the sign-in had landed, skip
  // signing out, and then wait for a login form that is no longer there.
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

type OpenedCase = { caseId: string; outcome: string };

/** Open a case for a subscriber and evaluate it, over `/v1`, as `token`. */
export async function evaluatedCase(
  request: APIRequestContext,
  token: string,
  msisdn: string,
): Promise<OpenedCase> {
  const headers = { Authorization: `Bearer ${token}` };
  const opened = await request.post(`${API}/v1/cases`, {
    headers,
    data: { msisdn },
  });
  expect(opened.ok(), `open case failed: ${opened.status()}`).toBeTruthy();
  const caseId = ((await opened.json()) as { case_id: string }).case_id;

  const decided = await request.post(`${API}/v1/cases/${caseId}/evaluate`, { headers });
  expect(decided.ok(), `evaluate failed: ${decided.status()}`).toBeTruthy();
  const outcome = ((await decided.json()) as { outcome: string }).outcome;
  return { caseId, outcome };
}

/** Build the pending plan for a case. */
export async function proposedPlan(
  request: APIRequestContext,
  token: string,
  caseId: string,
  createdBy: string,
): Promise<string> {
  const plan = await request.post(`${API}/v1/cases/${caseId}/proposals`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { created_by: createdBy },
  });
  expect(plan.ok(), `propose failed: ${plan.status()}`).toBeTruthy();
  return ((await plan.json()) as { plan_id: string }).plan_id;
}

/**
 * A real, issued receipt id, for the specs that need one to look at.
 *
 * Nimal's duplicate reload is the AUTO_FIX journey, so it reaches a receipt
 * without a customer tap and without spending an OTP challenge. It also
 * leaves Dilani's charge alone, which the chat journeys dispute.
 */
export async function issuedReceiptId(request: APIRequestContext): Promise<string> {
  const staff = await staffToken(request, "ops:stream", ["supervisor"], true);
  const { caseId, outcome } = await evaluatedCase(request, staff, NIMAL);
  expect(outcome, "the duplicate reload journey should auto-fix").toBe("AUTO_FIX");
  const planId = await proposedPlan(request, staff, caseId, "clarity-stream-detector");

  const fixed = await request.post(`${API}/v1/cases/${caseId}/auto-fix`, {
    headers: { Authorization: `Bearer ${staff}` },
    data: { plan_id: planId },
  });
  expect(fixed.ok(), `auto-fix failed: ${fixed.status()}`).toBeTruthy();
  return ((await fixed.json()) as { receipt_id: string }).receipt_id;
}
