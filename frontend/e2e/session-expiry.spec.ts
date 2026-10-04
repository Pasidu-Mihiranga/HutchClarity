import { expect, test } from "@playwright/test";
import { customerToken, signedIn } from "./session";

/**
 * A session the API no longer accepts sends the customer to sign in.
 *
 * Every deploy used to rotate the token key, and the chat then answered every
 * turn with a 401 nobody saw: the console filled with errors and the page
 * simply stopped working. Now a refused or missing session goes to `/login`,
 * which returns to the chat after sign-in.
 *
 * The session is an `HttpOnly` cookie since B4, so the app never removes it
 * itself. Only the API can, and it does so on sign-out.
 */

test.describe("session expiry", () => {
  test("the chat without a session goes to sign-in", async ({ page }) => {
    await page.goto("/clarity");
    await expect(page).toHaveURL(/\/login\?next=%2Fclarity$/);
  });

  /**
   * Rewritten for B4, which moved the session into an `HttpOnly` cookie.
   *
   * This used to plant a bogus token in `sessionStorage` and assert the app
   * cleared it. Both halves stopped meaning anything:
   *
   * - `clarity_token` is a key nothing reads or writes any more, so planting
   *   one exercised no code path and the page's redirect was really only
   *   testing "no session at all", which the test above already covers.
   * - Clearing is not the app's job and deliberately so. `lib/session.ts`
   *   says it: the cookie is `HttpOnly`, only the API can remove it, and a
   *   page writing a cookie it cannot read is how you end up with two.
   *
   * So this now plants a bogus **cookie**, which is what the server actually
   * refuses, and asserts the behaviour B4 does guarantee: a 401 sends the
   * customer to sign in carrying the address they came from, instead of a
   * chat that silently stops answering.
   */
  test("a refused session sends the customer to sign in, keeping their place", async ({
    page,
    baseURL,
  }) => {
    // From the fixture, not `page.url()`: nothing has been visited yet, so the
    // page is still `about:blank` and has no origin to take a hostname from.
    const origin = new URL(baseURL ?? "http://127.0.0.1:3100");
    await page.context().addCookies([
      {
        name: "clarity_customer_session",
        value: "not-a-token-this-server-issued",
        domain: origin.hostname,
        path: "/",
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);

    await page.goto("/clarity");

    await expect(page).toHaveURL(/\/login\?next=%2Fclarity$/);
  });

  test("a valid session stays on the chat", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await page.goto("/clarity");
    await expect(page.getByRole("textbox", { name: /ask clarity/i })).toBeVisible();
    await expect(page).toHaveURL(/\/clarity$/);
  });
});
