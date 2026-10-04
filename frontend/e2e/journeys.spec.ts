import { expect, test } from "@playwright/test";
import { KUMAR, NIMAL, customerTokenFor, signedIn } from "./session";

/**
 * The two remaining demo journeys, driven in the customer app (FE01, #28,
 * acceptance 1: "the four journeys driven in the Next.js apps").
 *
 * `dispute-charge.spec.ts` covers ONE_TAP_FIX and `staff-desk.spec.ts` covers
 * STAFF_APPROVAL. These are the other two, and between them they are the test
 * of restraint: one pays money back with nobody in the loop, the other refuses
 * to pay anything at all. Getting either wrong in the other's direction is the
 * failure that matters, so each asserts what must *not* be on the page as well
 * as what must.
 *
 * Both go through the chat, because that is where a case is *opened*. E4 wired
 * `/cases` to `/v1/me/app`, so the list is real now and shows what the chat
 * produced; it is still not a way to start a dispute, which is the chat's job.
 */
test.describe("the remaining demo journeys", () => {
  test("a duplicate reload is already refunded, with nobody in the loop", async ({
    page,
    request,
  }) => {
    await signedIn(page, await customerTokenFor(request, NIMAL));
    await page.goto("/clarity");

    await page
      .getByRole("textbox", { name: /ask|message|type/i })
      .fill("I was charged twice for my reload");
    await page.keyboard.press("Enter");

    await expect(page.getByRole("heading", { name: /found the reason/i })).toBeVisible();

    // The amount is the decision's, not the page's: LKR 3,500 is what the rule
    // pack resolved for this duplicate reload (I1, I3).
    await expect(page.getByText(/LKR\s*3[,.]?500/).first()).toBeVisible();

    // AUTO_FIX is the one path with no human in it, so there is nothing to
    // confirm. A confirm button here would mean the narrowest path had grown a
    // customer decision it is not supposed to have.
    await expect(page.getByRole("button", { name: /refund & disable/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^confirm$/i })).toHaveCount(0);
  });

  test("a disclosed fair-use cap is explained, and nothing is refunded", async ({
    page,
    request,
  }) => {
    await signedIn(page, await customerTokenFor(request, KUMAR));
    await page.goto("/clarity");

    await page
      .getByRole("textbox", { name: /ask|message|type/i })
      .fill("Why is my unlimited data so slow?");
    await page.keyboard.press("Enter");

    // A cap question is answered from the customer's own usage, not as a
    // charge dispute, so this is the usage card rather than an investigation.
    await expect(page.getByRole("heading", { name: /data remaining/i })).toBeVisible();

    // The cap is real and the page has to say so. Before FE01 wired this page
    // to `GET /v1/me/app` it said the opposite, in as many words: "Your data is
    // not slowed by a fair-use cap right now."
    await expect(page.getByText(/fair use cap is active/i)).toBeVisible();

    // Nothing was charged wrongly: the cap was disclosed at purchase, and the
    // decision is EXPLAIN_ONLY at LKR 0.00. Refunding here would be the
    // expensive mistake, so there is nothing to confirm and nothing to refund.
    await expect(page.getByRole("button", { name: /refund/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^confirm$/i })).toHaveCount(0);
  });
});
