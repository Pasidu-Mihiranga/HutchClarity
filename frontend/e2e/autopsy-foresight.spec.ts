import { expect, test } from "@playwright/test";
import { CONSOLE, signInOnDesk } from "./session";

test.describe("synthetic intelligence workspaces", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${CONSOLE}/autopsy`);
    await signInOnDesk(page, "Supervisor");
  });

  test("Autopsy discloses hypotheses, masked examples and its active method", async ({
    page,
  }) => {
    await expect(page.getByRole("heading", { name: "Complaint Autopsy" })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByText("SYNTHETIC DATA")).toBeVisible();
    await expect(page.getByText(/TrigramSimilarity/)).toBeVisible();
    await expect(page.getByText("HYPOTHESIS").first()).toBeVisible();
    await expect(page.getByText(/Representative masked complaints/i).first()).toBeVisible();
  });

  /**
   * Updated for C4 and D4, which changed both who may read this page and what
   * it shows.
   *
   * It used to sign in as **Supervisor** and assert a "Statistical baseline vs
   * persona swarm" table. Neither holds any more, and neither change was
   * accidental:
   *
   * - C4 gave foresight its own permissions and scoped `foresight:read` to
   *   `PRODUCT` and `CX_ENGINEER`. A supervisor approves money; rehearsing a
   *   change is a different job. `ConsoleNav` gates the link on the same
   *   permission, so as Supervisor the link is not there to click.
   * - D4 retired `GET /v1/demo/foresight`, which rehearsed a scenario per
   *   request and discarded it. The page reads stored scenarios, runs and
   *   reports now, so the baseline-vs-swarm comparison that route composed is
   *   not a thing this page renders.
   *
   * What the test is for is unchanged: the page must not claim certainty, and
   * must say it is not calibrated when it is not.
   */
  test("Foresight rehearses without claiming certainty", async ({ page }) => {
    await signInOnDesk(page, "CX");
    await page.getByRole("link", { name: "Foresight", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Foresight rehearsal" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText("SCENARIO, NOT CERTAINTY", { exact: true })).toBeVisible();
    // From `GET /v1/foresight/calibration`, not hard-coded in the page. No
    // backtest has run in a fresh synthetic world, so this is the true answer
    // rather than a label that happens to match.
    await expect(page.getByText("NOT CALIBRATED", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Calibration" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Rehearse a scenario" })).toBeVisible();
  });

  test("a supervisor is not offered Foresight", async ({ page }) => {
    // The companion to the above, and it caught a real defect: `ConsoleNav`
    // gated this link on `desk:queue:read` while the page requires
    // `foresight:read`, so every agent and supervisor was offered a link that
    // lands on "access denied". The nav must promise what the page keeps.
    //
    // The label is still rendered, greyed and unclickable, so this asserts
    // there is no *link*.
    await expect(page.getByRole("link", { name: "Foresight", exact: true })).toHaveCount(0);
    await expect(page.getByTitle("Your current role cannot access this").first()).toBeVisible();
  });

  test("a role without desk permission cannot use either workspace", async ({ page }) => {
    await signInOnDesk(page, "Auditor", false);
    await expect(page.getByText(/desk:queue:read/i)).toBeVisible();
  });
});
