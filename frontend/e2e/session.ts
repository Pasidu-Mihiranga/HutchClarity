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
