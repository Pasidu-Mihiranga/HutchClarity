import { expect, test } from "@playwright/test";
import { CONSOLE, signInOnDesk } from "./session";

/**
 * The Complaint Autopsy workspace (UI02 acceptance 1 and 2).
 *
 * Split out of `autopsy-foresight.spec.ts`, which UI02 names as two files and
 * which had gone stale twice over: it asserted a "Statistical baseline vs
 * persona swarm" heading that C4 removed, and signed in as a role that E2's
 * nav fix no longer offers Foresight to.
 *
 * What these cover, in UI02's words: clusters, trends, masked examples and
 * hypotheses are visible (1), and a review action uses the API and shows
 * immutable history (2).
 *
 * **Why the review half matters more than it looks.** D1 gave the reviewer
 * three actions and the page sends a verdict and re-reads; the thing that
 * could silently regress is the history. A reversal that replaced the verdict
 * it reversed would leave the trail saying the cluster was always judged that
 * way, which is the opposite of what a review trail is for. So the test
 * confirms, then reverses, then asserts **both** verdicts are on the page.
 */
test.describe("the Complaint Autopsy workspace", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${CONSOLE}/autopsy`);
    // Supervisor holds `desk:queue:read` and `autopsy:review`, which is what
    // this page reads and writes with.
    await signInOnDesk(page, "Supervisor");
    await expect(page.getByRole("heading", { name: "Complaint Autopsy" })).toBeVisible({
      timeout: 60_000,
    });
  });

  test("clusters, the method, masked examples and the hypothesis label are visible", async ({
    page,
  }) => {
    // The synthetic label is not decoration: DATA01 requires that nothing here
    // reads as measured HUTCH data (I16).
    await expect(page.getByText("SYNTHETIC DATA")).toBeVisible();

    // The clustering method is named rather than implied, so a reader knows
    // what produced the grouping.
    await expect(page.getByText(/TrigramSimilarity/)).toBeVisible();

    const clusters = page.getByTestId("autopsy-cluster");
    await expect(clusters.first()).toBeVisible();

    const first = clusters.first();
    await expect(first.getByText("HYPOTHESIS")).toBeVisible();
    await expect(first.getByText(/Representative masked complaints/i)).toBeVisible();
    await expect(first.getByText(/Synthetic trend:/)).toBeVisible();
    await expect(first.getByText(/Languages:/)).toBeVisible();
  });

  test("a verdict goes through the API and the history keeps what it replaced", async ({
    page,
  }) => {
    const cluster = page.getByTestId("autopsy-cluster").first();
    const label = (await cluster.getByRole("heading").first().textContent())?.trim() ?? "";
    expect(label.length, "the cluster should have a label to act on").toBeGreaterThan(0);

    // Confirm it. The page sends the verdict and re-reads: it never computes a
    // status itself, so the badge changing is the server's answer.
    await cluster.getByRole("button", { name: `Confirm ${label}` }).click();
    await expect(cluster.getByText("HYPOTHESIS")).toHaveCount(0);
    await expect(cluster.getByRole("heading", { name: "Verdicts" })).toBeVisible();
    await expect(cluster.getByText(/confirmed/).first()).toBeVisible();

    // A reversal needs a reason, and the control is disabled until there is
    // one rather than the refusal arriving after the click.
    const reverse = cluster.getByRole("button", { name: `Change ${label} to rejected` });
    await expect(reverse).toBeDisabled();
    await cluster
      .getByLabel(/Reason for changing this verdict/i)
      .fill("Reversed by the browser suite: the sample was mislabelled");
    await expect(reverse).toBeEnabled();
    await reverse.click();

    // Both verdicts, not just the current one. This is the assertion that
    // would catch a reversal that overwrote its own history.
    const verdicts = cluster.getByRole("listitem");
    await expect(verdicts.filter({ hasText: "confirmed" }).first()).toBeVisible();
    await expect(verdicts.filter({ hasText: "rejected" }).first()).toBeVisible();
  });

  test("an agent can read the workspace and cannot rule on it", async ({ page }) => {
    // Seeing and ruling are different permissions (D1): an agent holds
    // `desk:queue:read` and not `autopsy:review`, so the verdict buttons are
    // absent rather than present and failing on click.
    await signInOnDesk(page, "Agent", false);
    await expect(page.getByRole("heading", { name: "Complaint Autopsy" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/autopsy:review/)).toBeVisible();
    await expect(page.getByRole("button", { name: /^Confirm / })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^Reject / })).toHaveCount(0);
  });
});
