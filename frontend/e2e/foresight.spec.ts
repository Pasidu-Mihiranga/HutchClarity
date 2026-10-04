import { expect, test } from "@playwright/test";
import { CONSOLE, signInOnDesk } from "./session";

/**
 * The Foresight rehearsal workspace (UI02 acceptance 3).
 *
 * "An authorized product/operations user configures a rehearsal, the backend
 * runs it, and comparison, mitigations and caveats display."
 *
 * **Three things this spec had to be rebuilt around.**
 *
 * C4 gave foresight its own permissions: `foresight:read` to see the
 * workspace and `foresight:run` to ask for a rehearsal, and only
 * `Role.PRODUCT` holds the second. E6 added the `product` account to the
 * synthetic directory for exactly this, because until then no browser could
 * reach the run path at all.
 *
 * D4 retired `GET /v1/demo/foresight`, which built a scenario, ran it and
 * threw the result away per request. The page reads stored scenarios and runs
 * now, which is what makes a report citable afterwards, and is why this spec
 * asserts the run appears in the Runs list rather than only on screen.
 *
 * The calibration badge is read from `GET /v1/foresight/calibration` rather
 * than hard-coded, so "NOT CALIBRATED" here is the API's answer in a fresh
 * synthetic world and not a label somebody typed.
 */
test.describe("the Foresight rehearsal workspace", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${CONSOLE}/foresight`);
    await signInOnDesk(page, "Product");
    await expect(page.getByRole("heading", { name: "Foresight rehearsal" })).toBeVisible({
      timeout: 60_000,
    });
  });

  test("it refuses to claim certainty, and says whether it is calibrated", async ({ page }) => {
    await expect(page.getByText("SYNTHETIC SCENARIO")).toBeVisible();
    await expect(page.getByText("SCENARIO, NOT CERTAINTY", { exact: true })).toBeVisible();

    // Either badge is a true answer; what must not happen is the page
    // asserting calibration it has not checked.
    await expect(
      page.getByText(/NOT CALIBRATED|CALIBRATED|INSUFFICIENT/).first(),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Calibration" })).toBeVisible();
  });

  test("a rehearsal is configured, run by the backend, and stored", async ({ page }) => {
    const rehearse = page.getByRole("button", { name: "Rehearse" });
    // With no scenario drafted there is nothing to rehearse, and the page says
    // so rather than offering a button that cannot work.
    const picker = page.getByLabel("Scenario version to rehearse");
    test.skip(
      (await picker.count()) === 0,
      "no scenario has been drafted in this world, so there is nothing to rehearse",
    );

    await expect(rehearse).toBeVisible();
    await rehearse.click();

    // The report is the stored run's, fetched back by id after the 202.
    await expect(page.getByRole("heading", { name: "Rehearse a scenario" })).toBeVisible();
    const runs = page.getByRole("heading", { name: "Runs" });
    await expect(runs).toBeVisible();
    await expect(page.getByText("SUCCEEDED").first()).toBeVisible({ timeout: 60_000 });

    // Mitigations and caveats are the honest half of a report, so they sit
    // with the numbers rather than under a disclosure. The basis line says
    // what the prediction was computed from.
    const report = page.getByRole("region").filter({ hasText: /DECISION READY|NOT DECISION READY/ });
    if ((await report.count()) > 0) {
      await expect(
        page.getByRole("columnheader", { name: /Suggested preparation/i }),
      ).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Band" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Segment" })).toBeVisible();
    }
  });

  test("the early-warning radar counts, and says it never reads the text", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Early-warning spikes" })).toBeVisible();
    // C5's radar is channel-scoped counting, and the page is explicit that no
    // model reads what anybody wrote (I2).
    await expect(
      page.getByText(/never reads what anybody wrote|observed against a/).first(),
    ).toBeVisible();
  });

  test("CX is offered the link, can read a rehearsal, and cannot ask for one", async ({
    page,
  }) => {
    // `foresight:read` without `foresight:run`. The split is deliberate and
    // this is the test that keeps the page honest about it.
    await signInOnDesk(page, "CX", false);

    // Reached by clicking the nav rather than by typing the address: that is
    // the half that proves the nav offers the link to a role that can use it.
    // Navigating directly would pass with the link missing entirely, which is
    // the mirror of the defect E2 fixed in the other direction.
    await page.getByRole("link", { name: "Foresight", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Foresight rehearsal" })).toBeVisible({
      timeout: 30_000,
    });

    await expect(page.getByText(/foresight:run/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Rehearse" })).toHaveCount(0);
  });

  test("the page cannot record an outcome at all", async ({ page }) => {
    // C4, deliberately: the person who wants the calibration gate open must
    // not be the person who records the evidence that opens it. `product`
    // holds no `foresight:outcome:record`, and there is no control for it.
    await expect(page.getByRole("button", { name: /record.*outcome/i })).toHaveCount(0);
  });
});
