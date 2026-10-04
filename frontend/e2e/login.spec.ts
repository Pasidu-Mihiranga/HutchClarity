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
    await page.getByLabel("Hutch number").fill(DILANI);
    await page.getByRole("button", { name: "Continue" }).click();

    // The panel used to say "Any 6-digit code works in demo mode", which was
    // false: the backend generates a code per challenge and answers 401 to
    // anything else, so nobody following that instruction could sign in.
    const shown = page.getByTestId("otp-code");
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
      await page.evaluate(() => window.sessionStorage.getItem("clarity_token")),
      "a refused sign-in stored a session anyway",
    ).toBeFalsy();

    // The real code, on the same challenge, signs in.
    await page.getByLabel("6-digit code").fill(code);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/(account|clarity|cases)?$/);
    const token = await page.evaluate(() => window.sessionStorage.getItem("clarity_token"));
    expect(token, "no session was stored").toBeTruthy();
    expect(token).not.toBe("demo-token");
  });
});
