import { expect, test, type Page } from "@playwright/test";

/**
 * C05 (#24) acceptance 1: the DISPUTE_CHARGE flow, driven in a browser, ends
 * with the customer holding a verified receipt.
 *
 * **Why this exists when the backend journey is already tested.** C02's
 * acceptance test drives the same flow over `/v1` and reaches a verified
 * receipt, so the server side is covered. What it cannot catch is the UI
 * failing to carry the journey: before C05 the chat sent `case_id` only inside
 * `facts`, so every turn took the stateless path, no flow ever ran, and the
 * backend tests stayed green the whole time. That is the class of bug this
 * file exists for, and it is only visible from the browser.
 *
 * The assertions are on what a customer can see and do: the journey state, the
 * confirm card, the citation, and a receipt that the backend says verifies.
 * Nothing here asserts on an API response the user never sees.
 */

const DILANI = "+94771234567";

async function signIn(page: Page): Promise<void> {
  await page.goto("/login");
  // Any six digits are accepted in the synthetic profiles, and the identity
  // routes that allow it 404 in prod (I9), which is what makes automating
  // this journey safe rather than a bypass.
  await page.getByLabel("Hutch number").fill(DILANI);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("6-digit code").fill("123456");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/(account|clarity|cases)/);
}

test.describe("DISPUTE_CHARGE in the browser", () => {
  test("a customer disputing a charge reaches a verified receipt", async ({ page }) => {
    await signIn(page);
    await page.goto("/clarity");

    await page.getByRole("textbox", { name: /ask|message|type/i }).fill(
      "Why was LKR 49 deducted from my balance?",
    );
    await page.keyboard.press("Enter");

    // 1. The journey is visible. This is the assertion that would have failed
    //    before C05: with the flow never running there was no state to show.
    const journey = page.getByRole("navigation", { name: /charge|ගාස්තු|கட்டண/i });
    await expect(journey).toBeVisible();

    // 2. A plan is proposed and nothing has happened yet. The wording matters:
    //    a customer must know the fix has not run (I1, ADR-0007).
    const confirm = page.getByRole("button", { name: /^confirm$/i });
    await expect(confirm).toBeVisible();
    await expect(page.getByText(/nothing has changed yet/i)).toBeVisible();

    // 3. Confirming is what executes it.
    await confirm.click();

    // 4. The receipt, and the backend's own verdict on it. `verified` comes
    //    from `POST /v1/receipts/{id}/verify`, which recomputes the hash chain
    //    and checks the signature, so this is not the UI marking its own work.
    const receipt = page.getByTestId("receipt-verified");
    await expect(receipt).toBeVisible({ timeout: 30_000 });
    await expect(receipt).toHaveAttribute("data-verified", "true");
  });

  test("a knowledge question shows the source it was answered from", async ({ page }) => {
    await signIn(page);
    await page.goto("/clarity");

    await page.getByRole("textbox", { name: /ask|message|type/i }).fill(
      "What is the fair use policy?",
    );
    await page.keyboard.press("Enter");

    // A grounded answer shows its citation, whole, including the version:
    // a reference a customer cannot look up is decoration (K03).
    const sources = page.getByRole("region", { name: /sources|මූලාශ්ර|ஆவணங்கள்/i });
    await expect(sources).toBeVisible();
    await expect(sources.getByText(/@\d+/)).toBeVisible();
  });

  test("a question with no source offers a person instead of guessing", async ({ page }) => {
    await signIn(page);
    await page.goto("/clarity");

    await page.getByRole("textbox", { name: /ask|message|type/i }).fill(
      "What is the capital of France?",
    );
    await page.keyboard.press("Enter");

    await expect(page.getByText(/do not have a published source/i)).toBeVisible();
    await expect(page.getByRole("status")).toContainText(/person/i);
  });
});
