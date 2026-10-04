import { expect, test } from "@playwright/test";
import { CONSOLE, PRIYA, evaluatedCase, proposedPlan, signInOnDesk, staffToken } from "./session";

/**
 * The staff console's Desk (FE01, #28).
 *
 * This is the parity evidence for retiring the static `desk.html`, which
 * served `/desk`, `/ops`, `/autopsy` and `/foresight`. What the static Desk
 * did and this has to keep doing: pick a staff identity, see the cases that
 * need a person with the biggest money at stake first, open one, and approve
 * it under four-eyes and step-up.
 *
 * The case is set up over `/v1` as an agent, so the approval in the browser is
 * made by a *different* person. Four-eyes is the reason: a plan's author may
 * not approve it, and a test that raised and approved as one identity would
 * pass while proving the opposite.
 */
test.describe("the staff console desk", () => {
  test("a stepped-up supervisor approves a case the agent raised", async ({ page, request }) => {
    const agent = await staffToken(request, "agent:nadeesha", ["agent"]);
    const { caseId, outcome } = await evaluatedCase(request, agent, PRIYA);
    expect(outcome, "Priya's disputed reload should need a person").toBe("STAFF_APPROVAL");
    await proposedPlan(request, agent, caseId, "agent:nadeesha");

    // Sign in through the desk form. The directory assigns supervisor; the
    // page cannot pick the role.
    await page.goto(`${CONSOLE}/desk`);
    await signInOnDesk(page, "Supervisor");

    // The queue is the Desk's whole proposition: what needs a person, ordered
    // by what it costs to leave it.
    const queue = page.getByRole("button", { name: /SIM_SWAP|sim swap|CASE-/i });
    await expect(queue.first()).toBeVisible({ timeout: 30_000 });
    await queue.first().click();

    // Approving is the staff equivalent of the customer's one tap: the button
    // asks the tool layer to execute an already-built plan, and the amount
    // comes from the decision, never from this page (I1).
    const approve = page.getByRole("button", { name: /approve as supervisor/i });
    await expect(approve).toBeVisible();
    await approve.click();

    // And it ends where every fix ends: a receipt the backend verifies.
    await expect(page.getByRole("heading", { name: /trust receipt issued/i })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText("VERIFIED").first()).toBeVisible();
  });

  test("a role without the permission is refused the desk, not shown an empty one", async ({
    page,
  }) => {
    // Deny by default (I9). An auditor may read receipts but holds no
    // `desk:queue:read`, and the page has to say so rather than render a desk
    // with nothing in it, which looks like "no work waiting".
    await page.goto(`${CONSOLE}/desk`);
    await signInOnDesk(page, "Auditor", false);

    await expect(page.getByText(/desk:queue:read/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: /approve as/i })).toHaveCount(0);
  });
});
