import { expect, test } from "@playwright/test";
import { DILANI } from "./session";

/**
 * The one test that drives the login page itself (FE01, #28).
 *
 * Every other test injects a token instead, because the OTP service allows
 * five challenges per number per fifteen minutes and the suite is larger than
 * that. This one spends a challenge deliberately, to prove the page a customer
 * actually uses works.
 */
test.describe("sign in", () => {
  test("a wrong code is refused and the right one signs the customer in", async ({ page }) => {
    // Both assertions share one challenge on purpose. The OTP service allows
    // five challenges per number per fifteen minutes (TH1), and a test that
    // spends one to prove a refusal makes the next test fail for a reason that
    // has nothing to do with what it tests.
    await page.goto("/login");
    await expect(page.getByTestId("simulated-sms-inbox")).toHaveCount(0);
    await page.getByLabel("Hutch number").fill(DILANI);
    await page.getByRole("button", { name: "Continue" }).click();

    // The panel used to say "Any 6-digit code works in demo mode", which was
    // false: the backend generates a code per challenge and answers 401 to
    // anything else, so nobody following that instruction could sign in.
    const shown = page.getByTestId("demo-otp-code");
    await expect(page.getByTestId("simulated-sms-inbox")).toBeVisible();
    await expect(shown).toBeVisible();
    const code = (await shown.innerText()).trim();
    expect(code).toMatch(/^\d{6}$/);
    await expect(page.getByLabel("6-digit code")).toHaveValue(code);

    // A refused code must leave nothing behind. Regression: a failed verify
    // used to store `clarity_token = "demo-token"` and report "placeholder
    // login accepted locally", so a rejected code produced a half-signed-in
    // state instead of an error (I9).
    const wrong = code === "000000" ? "111111" : "000000";
    await page.getByLabel("6-digit code").fill(wrong);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/login/);
    expect(
      (await page.context().cookies()).find((c) => c.name === "clarity_customer_session"),
      "a refused sign-in set a session cookie anyway",
    ).toBeUndefined();

    // The real code, on the same challenge, signs in.
    await page.getByLabel("6-digit code").fill(code);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/(account|clarity|cases)?$/);
    // B4 moved the session to an `HttpOnly` cookie. This used to assert the
    // token was in `sessionStorage`, which is now exactly the thing that must
    // not be true: a token any script on the page can read is the credential
    // that opens a dispute and confirms a refund.
    const session = (await page.context().cookies()).find(
      (c) => c.name === "clarity_customer_session",
    );
    expect(session, "no session cookie was set").toBeTruthy();
    expect(session?.httpOnly, "the session cookie must not be readable by a script").toBe(true);
    expect(
      await page.evaluate(() => window.sessionStorage.getItem("clarity_token")),
      "the token must not also be left where a script can read it",
    ).toBeNull();
  });
});
