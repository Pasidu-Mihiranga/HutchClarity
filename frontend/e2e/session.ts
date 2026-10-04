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

export const DILANI = "+94771234567";

const API = process.env.E2E_API_BASE ?? "http://127.0.0.1:8100";

let cached: string | null = null;

/** Mint a customer token through the API, once per worker. */
export async function customerToken(request: APIRequestContext): Promise<string> {
  if (cached) return cached;

  const started = await request.post(`${API}/v1/auth/otp/request`, {
    data: { msisdn: DILANI },
  });
  expect(started.ok(), `otp request failed: ${started.status()}`).toBeTruthy();
  const { challenge_id } = (await started.json()) as { challenge_id: string };

  // The code is generated per challenge. There is no "any six digits" path:
  // the backend answers 401 to anything else.
  const inbox = await request.get(
    `${API}/v1/demo/inbox?msisdn=${encodeURIComponent(DILANI)}`,
  );
  expect(inbox.ok(), `demo inbox failed: ${inbox.status()}`).toBeTruthy();
  const { code } = (await inbox.json()) as { code: string };

  const verified = await request.post(`${API}/v1/auth/otp/verify`, {
    data: { challenge_id, code },
  });
  expect(verified.ok(), `otp verify failed: ${verified.status()}`).toBeTruthy();
  const { token } = (await verified.json()) as { token: string };

  cached = token;
  return token;
}

/** Put the session in place before any page script runs. */
export async function signedIn(page: Page, token: string): Promise<void> {
  await page.addInitScript((value) => {
    try {
      window.sessionStorage.setItem("clarity_token", value);
    } catch {
      /* a private context without storage still renders the page */
    }
  }, token);
}

/**
 * The other two apps' origins. `baseURL` belongs to customer-web, because
 * most of the suite lives there; the console and the verify page are separate
 * Next.js apps on their own ports, so their specs navigate absolutely.
 */
export const CONSOLE = process.env.E2E_CONSOLE_BASE ?? "http://127.0.0.1:3101";
export const VERIFY = process.env.E2E_VERIFY_BASE ?? "http://127.0.0.1:3102";

/** The other synthetic subscribers, by the outcome their case reaches. */
export const NIMAL = "+94772223333"; // duplicate reload -> AUTO_FIX
export const PRIYA = "+94774445555"; // LKR 12,000 reload, SIM swap -> STAFF_APPROVAL

/**
 * A staff token, minted through the development role picker's own endpoint.
 *
 * Unlike the customer's OTP there is no challenge budget here, so specs may
 * call this freely. `step_up` simulates recent MFA, which an approval above
 * the cap requires.
 */
export async function staffToken(
  request: APIRequestContext,
  userRef: string,
  roles: string[],
  stepUp = false,
): Promise<string> {
  const session = await request.post(`${API}/v1/auth/staff/session`, {
    data: { user_ref: userRef, roles, step_up: stepUp },
  });
  expect(session.ok(), `staff session failed: ${session.status()}`).toBeTruthy();
  const { token } = (await session.json()) as { token: string };
  return token;
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
