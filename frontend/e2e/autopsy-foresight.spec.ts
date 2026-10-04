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

  test("Foresight compares baseline and swarm without claiming certainty", async ({ page }) => {
    await page.getByRole("link", { name: "Foresight", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Foresight rehearsal" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText("SCENARIO, NOT CERTAINTY", { exact: true })).toBeVisible();
    await expect(page.getByText("NOT CALIBRATED", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Statistical baseline vs persona swarm" }),
    ).toBeVisible();
  });

  test("a role without desk permission cannot use either workspace", async ({ page }) => {
    await signInOnDesk(page, "Auditor", false);
    await expect(page.getByText(/desk:queue:read/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "Foresight", exact: true })).toHaveCount(0);
  });
});
