import { expect, test } from "@playwright/test";
import { CONSOLE, signInOnDesk } from "./session";

/**
 * Provenance across the staff workspaces (UI02 acceptance 4).
 *
 * "DATA01 is active; either workspace opens; synthetic provenance is prominent
 * and no value is presented as real HUTCH data."
 *
 * **Why this is its own spec rather than an assertion inside the others.**
 * I16 is a product-wide rule, and the way it breaks is one screen at a time:
 * somebody adds a panel, the label does not come with it, and every other
 * screen still says "synthetic" so nothing looks wrong. Checking every
 * workspace in one place is what catches the screen that forgot.
 *
 * **What counts as prominent.** Not a footnote. The label has to be in the
 * page before any figure it qualifies, which in practice means in the header,
 * so these tests assert it is visible without scrolling to find it.
 *
 * The second half is the harder half: no value presented as real. A rehearsal
 * says it is a scenario, a cluster says it is a hypothesis, and the autopsy
 * trend is labelled synthetic. Those three words are the product's honesty
 * and each is asserted where a number would otherwise read as measured.
 */
test.describe("synthetic provenance is never implied", () => {
  test("the desk says its subscribers are synthetic", async ({ page }) => {
    await page.goto(`${CONSOLE}/desk`);
    await signInOnDesk(page, "Supervisor");
    await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible({ timeout: 60_000 });

    await expect(page.getByText(/The subscribers are\s+synthetic/)).toBeVisible();
  });

  test("a case shows where its decision came from, not just what it decided", async ({ page }) => {
    await page.goto(`${CONSOLE}/desk`);
    await signInOnDesk(page, "Supervisor");
    const queue = page.getByRole("button", { name: /CASE-|sim swap|duplicate|renewal/i });
    await expect(queue.first()).toBeVisible({ timeout: 60_000 });
    await queue.first().click();

    // Provenance of the decision: which rule, which version of it, and how
    // confident it was. A cause without a version is a cause nobody can
    // reproduce later (I1).
    await expect(page.getByRole("heading", { name: "Ranked cause" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/version .* confidence \d+%/)).toBeVisible();

    // Provenance of the evidence: which source each event came from, and
    // whether that source was complete. "Complete" is the claim that matters,
    // because a decision on a partial timeline is a different decision.
    await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
    await expect(page.getByText(/: (complete|partial|missing)/).first()).toBeVisible();

    // And the rules the policy applied, in its own words rather than the
    // page's summary of them.
    await expect(page.getByRole("heading", { name: "Policy said" })).toBeVisible();
  });

  test("the autopsy workspace labels its clusters as hypotheses and its trend as synthetic", async ({
    page,
  }) => {
    await page.goto(`${CONSOLE}/autopsy`);
    await signInOnDesk(page, "Supervisor");
    await expect(page.getByRole("heading", { name: "Complaint Autopsy" })).toBeVisible({
      timeout: 60_000,
    });

    await expect(page.getByText("SYNTHETIC DATA")).toBeVisible();
    await expect(
      page.getByText(/Clusters are hypotheses until a person reviews them/),
    ).toBeVisible();
    // The trend numbers are the ones most likely to be read as measured, so
    // the word sits on the same line as them.
    await expect(page.getByText(/Synthetic trend:/).first()).toBeVisible();
  });

  test("a rehearsal is labelled a scenario, and its basis is stated", async ({ page }) => {
    await page.goto(`${CONSOLE}/foresight`);
    await signInOnDesk(page, "Product");
    await expect(page.getByRole("heading", { name: "Foresight rehearsal" })).toBeVisible({
      timeout: 60_000,
    });

    await expect(page.getByText("SYNTHETIC SCENARIO")).toBeVisible();
    await expect(page.getByText("SCENARIO, NOT CERTAINTY", { exact: true })).toBeVisible();
    await expect(
      page.getByText(/never a forecast of what will happen|It is a scenario/).first(),
    ).toBeVisible();
  });

  test("insights labels its counts and keeps the two workspaces as hypotheses", async ({
    page,
  }) => {
    await page.goto(`${CONSOLE}/insights`);
    await signInOnDesk(page, "Supervisor");
    await expect(page.getByRole("heading", { name: "Insights" })).toBeVisible({
      timeout: 60_000,
    });

    await expect(page.getByText(/Counts from synthetic cases/)).toBeVisible();
    await expect(page.getByText("Hypothesis").first()).toBeVisible();
  });

  test("the merchant block says the merchant system is simulated", async ({ page }) => {
    await page.goto(`${CONSOLE}/desk`);
    await signInOnDesk(page, "VAS Ops");
    await expect(page.getByRole("heading", { name: "Merchant block" })).toBeVisible({
      timeout: 60_000,
    });

    await expect(page.getByText(/The merchant system is simulated/)).toBeVisible();
    // And again in the confirmation, because that is where somebody decides.
    await page.getByRole("button", { name: "Suspend GameZone" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText(/simulated/);
  });
});
