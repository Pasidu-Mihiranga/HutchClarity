import { expect, test } from "@playwright/test";
import { KUMAR, customerTokenFor, signedIn } from "./session";

/**
 * Every customer screen shows the signed-in customer's own account.
 *
 * The home page used to render a hard-coded customer (with a number from the
 * old 077 range) for everyone, its Reload button did nothing, and the cases
 * page always showed two invented cases because it called an SDK method that
 * did not exist. These tests sign in as someone other than that hard-coded
 * customer, so any leftover fixture shows up as a wrong name.
 */

test.describe("real account data", () => {
  test("home shows the signed-in customer, and a reload changes the balance", async ({ page, request }) => {
    await signedIn(page, await customerTokenFor(request, KUMAR));
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1 })).not.toHaveText("Dilani Perera");
    const balance = page.getByText(/^LKR \d/).first();
    await expect(balance).toBeVisible();
    const before = Number((await balance.innerText()).replace(/[^\d.]/g, ""));

    await page.getByRole("button", { name: "Reload" }).click();
    await page.getByRole("group", { name: "Reload amount" }).getByRole("button", { name: "LKR 100", exact: true }).click();

    await expect(page.getByRole("status")).toHaveText("LKR 100 added to your balance.");
    await expect(balance).toHaveText(`LKR ${(before + 100).toFixed(2)}`);
  });

  test("the cases page lists only real cases", async ({ page, request }) => {
    await signedIn(page, await customerTokenFor(request, KUMAR));
    await page.goto("/cases");

    await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible();
    await expect(page.getByText(/VAS silent renewal|Duplicate data charge/)).toHaveCount(0);
    await expect(page.locator('a[href^="/case/demo-case"]')).toHaveCount(0);
  });

  test("account shows the customer's own masked number", async ({ page, request }) => {
    await signedIn(page, await customerTokenFor(request, KUMAR));
    await page.goto("/account");

    await expect(page.getByText("07X XXX 4444")).toBeVisible();
    await expect(page.getByText("Demo customer")).toHaveCount(0);
  });
});
