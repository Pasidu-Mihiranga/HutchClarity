import { expect, test } from "@playwright/test";
import { customerToken, signedIn } from "./session";

/**
 * A session the API no longer accepts sends the customer to sign in.
 *
 * Every deploy used to rotate the token key, and the chat then answered every
 * turn with a 401 nobody saw: the console filled with errors and the page
 * simply stopped working. Now a refused or missing token clears the session
 * and goes to `/login`, which returns to the chat after sign-in.
 */

test.describe("session expiry", () => {
  test("the chat without a session goes to sign-in", async ({ page }) => {
    await page.goto("/clarity");
    await expect(page).toHaveURL(/\/login\?next=%2Fclarity$/);
  });

  test("a refused session sends the customer to sign in", async ({ page }) => {
    await page.context().addCookies([
      {
        name: "clarity_customer_session",
        value: "not-a-token-this-server-issued",
        domain: "127.0.0.1",
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
