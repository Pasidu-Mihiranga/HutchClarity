import { expect, test } from "@playwright/test";
import { VERIFY, issuedReceiptId } from "./session";

/**
 * The public verify page, which is what a Trust Receipt's QR code opens
 * (FE01, #28).
 *
 * This is the parity evidence for retiring the static `verify.html`. The
 * static page's behaviour was: ask the backend, show its verdict, and show an
 * error on a 404. Anything less than that in the Next.js app would be a
 * regression on the one page whose entire purpose is to let a stranger check
 * that a receipt is genuine, so all three outcomes are tested here, including
 * the one that is neither a pass nor a fail.
 *
 * The page takes no credentials, which is the point: verification has to work
 * for someone holding a printed receipt and nothing else.
 */
test.describe("the public verify page", () => {
  test("an issued receipt is shown as verified, with the backend's verdict", async ({
    page,
    request,
  }) => {
    const receiptId = await issuedReceiptId(request);

    // No token is injected anywhere in this test.
    await page.goto(`${VERIFY}/r/${receiptId}`);

    const result = page.getByTestId("verify-result");
    await expect(result).toBeVisible();
    // `true` comes from `POST /v1/receipts/{id}/verify`, which recomputes the
    // hash chain and checks the signature. The page is reporting the
    // backend's verdict, not its own.
    await expect(result).toHaveAttribute("data-verified", "true");
    await expect(result.getByText("Chain valid")).toBeVisible();
    await expect(result.getByText(receiptId)).toBeVisible();
    await expect(result.getByText("VERIFIED")).toBeVisible();
  });

  test("a receipt that was never issued is not reported as valid", async ({ page }) => {
    // The regression this test exists for. The page used to fall back to a
    // "placeholder" verdict whenever the call failed, and that verdict was
    // *valid* for any id not containing the string "bad". So this exact URL
    // rendered a green "Chain valid" badge for a receipt that does not exist.
    await page.goto(`${VERIFY}/r/TR-2027-999999`);

    const result = page.getByTestId("verify-result");
    await expect(result).toBeVisible();
    await expect(result).toHaveAttribute("data-verified", "unchecked");
    await expect(result.getByText(/has ever been issued/i)).toBeVisible();

    // And it must not say the two things that would mislead someone holding a
    // forged receipt.
    await expect(page.getByText("Chain valid")).toHaveCount(0);
    await expect(page.getByText("Chain invalid")).toHaveCount(0);
  });

  test("when the service cannot be reached it says so instead of guessing", async ({ page }) => {
    // Same rule, different cause: no answer is not a pass. Without this the
    // page's own offline fallback decided the verdict.
    await page.route("**/v1/receipts/**/verify", (route) => route.abort("failed"));
    await page.goto(`${VERIFY}/r/TR-2027-000001`);

    const result = page.getByTestId("verify-result");
    await expect(result).toBeVisible();
    await expect(result).toHaveAttribute("data-verified", "unchecked");
    await expect(result.getByText(/did not answer/i)).toBeVisible();
    await expect(page.getByText("Chain valid")).toHaveCount(0);
  });
});
