import { expect, test } from "@playwright/test";
import { customerToken, signedIn } from "./session";

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




test.describe("DISPUTE_CHARGE in the browser", () => {
  test("a customer disputing a charge reaches a verified receipt", async ({ page, request }) => {
    let proposalPosts = 0;
    page.on("request", (sent) => {
      if (sent.method() === "POST" && /\/v1\/cases\/[^/]+\/proposals$/.test(sent.url())) {
        proposalPosts += 1;
      }
    });
    await signedIn(page, await customerToken(request));
        await page.goto("/clarity");

    const box = page.getByRole("textbox", { name: /ask|message|type/i });
    await box.fill("Why was LKR 49 deducted from my balance?");
    await page.keyboard.press("Enter");

    // 1. The cause, with its evidence. The rules decided this, not a model
    //    (I1), and the amount comes from the decision.
    await expect(page.getByRole("heading", { name: /found the reason/i })).toBeVisible();
    await expect(page.getByText("LKR 49.00").first()).toBeVisible();

    // A follow-up enters the stateful flow. It creates the one pending plan
    // that the confirm card displays; the browser must execute that plan, not
    // silently create a replacement when Confirm is tapped.
    await box.fill("Please refund it and stop the subscription");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: /^confirm$/i }).first()).toBeVisible();

    // 2. The flow-owned plan opens a confirmation rather than acting. This is
    //    the assertion that matters for ADR-0007: the visible plan belongs to
    //    this case, and a second, explicit confirm executes it.
    await page.getByRole("button", { name: /^confirm$/i }).first().click();

    const sheet = page.getByRole("heading", { name: /disable this subscription/i });
    await expect(sheet).toBeVisible();
    // What the fix will do, before it does it.
    await expect(page.getByText(/refunds the disputed amount/i)).toBeVisible();

    // 3. Confirming is what executes it.
    await page.getByRole("button", { name: /^confirm$/i }).last().click();
    expect(proposalPosts).toBe(0);

    // 4. The receipt, and the backend's own verdict on it. `verified` comes
    //    from `POST /v1/receipts/{id}/verify`, which recomputes the hash chain
    //    and checks the signature, so this is not the UI marking its own work.
    const receipt = page.getByTestId("receipt-verified");
    await expect(receipt).toBeVisible({ timeout: 30_000 });
    await expect(receipt).toHaveAttribute("data-verified", "true");
  });

  test("a knowledge question shows the source it was answered from", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
        await page.goto("/clarity");

    // A how-to, not a question about this customer's own account. "What is
    // the fair use policy?" routes to `account` and is answered from the
    // customer's own FUP status, which is a correct answer with nothing to
    // cite. The knowledge route is for questions a document answers.
    await page.getByRole("textbox", { name: /ask|message|type/i }).fill(
      "How do I activate a data package?",
    );
    await page.keyboard.press("Enter");

    // A grounded answer shows its citation, whole, including the version:
    // a reference a customer cannot look up is decoration (K03).
    const sources = page.getByRole("region", { name: /sources|මූලාශ්‍ර|ஆவணங்கள்/i });
    await expect(sources).toBeVisible();
    // Whole, including the version: a reference a customer cannot look up is
    // decoration. The server returns `SOURCE@version` and this card used to
    // drop it entirely.
    await expect(sources.getByText(/@\d+/).first()).toBeVisible();
  });

  test("a question with no source offers a person instead of guessing", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
        await page.goto("/clarity");

    await page.getByRole("textbox", { name: /ask|message|type/i }).fill(
      "What is the capital of France?",
    );
    await page.keyboard.press("Enter");

    // It must not answer. Nothing in the knowledge base covers this, and a
    // plausible-sounding answer is the failure mode the whole design exists to
    // avoid (I2: missing evidence means a person, never a guess).
    await expect(page.getByText(/could not confirm/i)).toBeVisible();
    await expect(page.getByText(/paris/i)).toHaveCount(0);

    // And it must offer a way to a person rather than leaving the customer
    // with a dead end.
    await expect(page.getByRole("button", { name: /talk to support/i })).toBeVisible();
  });
});
