import { expect, test } from "@playwright/test";
import { customerToken, issuedReceiptId, signedIn } from "./session";

/**
 * The customer's own receipt page, `customer-web/app/receipt/[id]`.
 *
 * `verify-receipt.spec.ts` pins the same rule for the public verify app. This
 * spec exists because the customer copy of that page still broke it, and
 * nothing tested it.
 *
 * The page read `receipt?.valid ?? receipt?.chain_ok ?? true` from
 * `GET /v1/receipts/{id}`, which returns the signed document
 * (`payload`, `payload_hash`, `signature`, `verify_url`) and carries neither
 * field. So the expression could only ever resolve to `true`: every receipt
 * rendered "Valid", "Signature Verified" and "Chain Intact" whether or not
 * anything had been checked, and a failed load additionally fabricated a
 * "Credit LKR 99.00 for silent VAS renewal" summary for an id that had never
 * been issued.
 *
 * The verdict now comes from `POST /v1/receipts/{id}/verify`, the only
 * endpoint that computes one, and "could not check" is a real third outcome.
 */
test.describe("the customer's receipt page", () => {
  test("an issued receipt is shown as valid, with the backend's verdict", async ({
    page,
    request,
  }) => {
    const receiptId = await issuedReceiptId(request);
    await signedIn(page, await customerToken(request));

    await page.goto(`/receipt/${receiptId}`);

    const result = page.getByTestId("receipt-result");
    await expect(result).toBeVisible();
    // `true` is the backend recomputing the hash chain and checking the
    // signature, not the page assuming a pass.
    await expect(result).toHaveAttribute("data-verified", "true");
    await expect(result.getByText(receiptId)).toBeVisible();
    await expect(result.getByText("Verified")).toBeVisible();
    await expect(result.getByText("Intact")).toBeVisible();
  });

  test("a receipt that was never issued is not reported as valid", async ({ page, request }) => {
    // The regression. This exact URL used to render a green "Valid" hero and a
    // fabricated LKR 99.00 credit summary.
    await signedIn(page, await customerToken(request));

    await page.goto("/receipt/TR-2027-999999");

    const result = page.getByTestId("receipt-result");
    await expect(result).toBeVisible();
    await expect(result).toHaveAttribute("data-verified", "unchecked");
    await expect(result.getByText(/has ever been issued/i)).toBeVisible();

    // The three things that would mislead someone holding a forged receipt.
    await expect(page.getByText("Signature and chain verified")).toHaveCount(0);
    await expect(page.getByText("Credit LKR 99.00", { exact: false })).toHaveCount(0);
    await expect(result.getByText("Verified")).toHaveCount(0);
  });

  test("when the service cannot be reached it says so instead of guessing", async ({
    page,
    request,
  }) => {
    await signedIn(page, await customerToken(request));
    await page.route("**/v1/receipts/**/verify", (route) => route.abort("failed"));

    await page.goto("/receipt/TR-2027-000001");

    const result = page.getByTestId("receipt-result");
    await expect(result).toBeVisible();
    await expect(result).toHaveAttribute("data-verified", "unchecked");
    await expect(result.getByText(/did not answer/i)).toBeVisible();
    await expect(page.getByText("Signature and chain verified")).toHaveCount(0);
  });
});
