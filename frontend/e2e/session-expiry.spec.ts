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

  test("a refused token is cleared and the customer is sent to sign in", async ({ page }) => {
    // Set once, not with `signedIn`: its init script would put the token back
    // on every navigation, including the one to /login.
    await page.goto("/login");
    await page.evaluate(() => window.sessionStorage.setItem("clarity_token", "not-a-token-this-server-issued"));
    await page.goto("/clarity");

    await expect(page).toHaveURL(/\/login\?next=%2Fclarity$/);
    expect(await page.evaluate(() => window.sessionStorage.getItem("clarity_token"))).toBeNull();
  });

  test("a valid session stays on the chat", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await page.goto("/clarity");
    await expect(page.getByRole("textbox", { name: /ask clarity/i })).toBeVisible();
    await expect(page).toHaveURL(/\/clarity$/);
  });
});
