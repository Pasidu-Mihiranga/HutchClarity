import { expect, test } from "@playwright/test";
import { CONSOLE, PRIYA, evaluatedCase, proposedPlan, signInOnDesk, staffToken } from "./session";

/**
 * The console's Audit section (audit assurance plan Phase 5).
 *
 * What these tests are for, and what they deliberately are not.
 *
 * They prove the panels are **wired to the real API and the real permission
 * checks**, which is what Phase 5 promises and what the admin page previously
 * admitted it was not ("Audit trail API: not wired"). The rules, the hash chain,
 * the alert lifecycle rules and the recovery paths are proven in the backend
 * suite, where they can be set up precisely; a browser test that tried to stage
 * a structuring pattern through the UI would be slow and would prove less.
 *
 * So: the data arrives, the verdict is shown rather than asserted, reading the
 * trail is itself recorded, a role without the duty is refused, and the trail is
 * loaded on request rather than on a timer.
 */

const API = process.env.E2E_API_BASE ?? "http://127.0.0.1:8100";

/** Sign in through the desk form, as a staff member would. */
async function signInAs(page: import("@playwright/test").Page, role: string) {
  await page.goto(`${CONSOLE}/audit`);
  await signInOnDesk(page, role);
}

test.describe("the console audit section", () => {
  test("chain health shows the verdict and what it covers", async ({ page }) => {
    await signInAs(page, "Security");

    const health = page.getByTestId("chain-health");
    await expect(health).toBeVisible({ timeout: 30_000 });
    await expect(health.getByText("intact", { exact: true })).toBeVisible();
    // A length, not a reassurance: the panel reports what it counted.
    await expect(page.getByTestId("chain-length")).not.toHaveText("0");
    await expect(page.getByTestId("writer-lag")).toContainText("unpublished");
    // And it says what the incremental check does not cover, rather than
    // letting a green badge imply more than it proves.
    await expect(health).toContainText("does not re-read the records below it");
    await expect(health).toContainText("public checkpoint");
  });

  test("the trail is read on request, not on a timer, and each read is recorded", async ({
    page,
    request,
  }) => {
    const auditor = await staffToken(request, "sec:dilani", ["security_admin"], true);
    const before = await request.get(`${API}/v1/audit?event_type=audit.read&limit=200`, {
      headers: { Authorization: `Bearer ${auditor}` },
    });
    const beforeCount = ((await before.json()) as { records: unknown[] }).records.length;

    await signInAs(page, "Security");
    const explorer = page.getByTestId("trail-explorer");
    await expect(explorer).toContainText("Not loaded");
    await expect(explorer).toContainText("read is recorded");

    await page.getByTestId("load-trail").click();
    await expect(explorer.locator("table")).toBeVisible({ timeout: 30_000 });

    // The console's own read is in the trail, which is rule 5: who watched the
    // watchers is part of what is watched.
    const after = await request.get(`${API}/v1/audit?event_type=audit.read&limit=200`, {
      headers: { Authorization: `Bearer ${auditor}` },
    });
    const afterCount = ((await after.json()) as { records: unknown[] }).records.length;
    expect(afterCount).toBeGreaterThan(beforeCount);
  });

  test("a record's hashes are recomputed in front of you", async ({ page }) => {
    await signInAs(page, "Security");
    await page.getByTestId("load-trail").click();
    await expect(page.getByTestId("trail-explorer").locator("table")).toBeVisible({
      timeout: 30_000,
    });

    const verify = page.getByRole("button", { name: "Verify" }).first();
    await verify.click();

    // "hash ok" is the server having recomputed the record's own hash and its
    // link, not a label the page decided to show.
    await expect(page.getByText("hash ok").first()).toBeVisible();
  });

  test("the alert queue distinguishes a quiet detector from a quiet day", async ({ page }) => {
    await signInAs(page, "Security");

    const alerts = page.getByTestId("alerts-panel");
    await expect(alerts).toBeVisible({ timeout: 30_000 });
    await expect(alerts).toContainText("Detection last ran");
    // Either there are alerts, or the panel says so in the words that matter:
    // a quiet queue and a stopped detector are not the same thing.
    const rows = alerts.getByTestId("alert-row");
    if ((await rows.count()) === 0) {
      await expect(alerts.getByTestId("no-alerts")).toContainText("heartbeat");
    } else {
      await expect(rows.first()).toContainText("Evidence:");
    }
  });

  test("recovery reports an unset backup key as a problem, not a blank", async ({ page }) => {
    await signInAs(page, "Security");

    const recovery = page.getByTestId("recovery-panel");
    await expect(recovery).toBeVisible({ timeout: 30_000 });
    await expect(recovery.getByTestId("last-backup")).toContainText(/never taken|records/);
    // The lite profile sets no backup key, so the panel must say that nothing is
    // being backed up rather than showing an empty "last backup" and looking fine.
    await expect(recovery).toContainText(/no backup key|key set/);
  });

  test("monitors and access read from the grant system", async ({ page }) => {
    await signInAs(page, "Security");

    await expect(page.getByTestId("monitors-panel")).toContainText("time-boxed grant");
    await expect(page.getByTestId("access-panel")).toContainText(
      "removes every money permission",
    );
    // Security admin holds audit:assign, so the grant list loads for them.
    await expect(page.getByTestId("access-refused")).toHaveCount(0);
  });

  test("one panel being refused does not blank the rest", async ({ page }) => {
    /**
     * Deny by default means different roles legitimately see different panels.
     * Compliance holds audit:read and alert:dispose but not audit:assign, so the
     * grant list answers 403 for them. The first run of this suite showed that a
     * single Promise.all turned that expected refusal into an empty page with an
     * error banner, which is the bug this pins.
     */
    await signInAs(page, "Compliance");

    await expect(page.getByTestId("chain-health")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("alerts-panel")).toBeVisible();
    await expect(page.getByTestId("recovery-panel")).toBeVisible();
    // And the one panel that is not theirs says so, instead of looking broken.
    await expect(page.getByTestId("access-refused")).toContainText("audit:assign");
  });

  test("an agent cannot reach the audit section", async ({ page }) => {
    await signInAs(page, "Agent");

    // The real permission check, not a hidden link: an agent holds no audit duty,
    // so the page itself refuses.
    await expect(page.getByText(/audit:read/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("chain-health")).toHaveCount(0);
  });

  test("a supervisor who approved money cannot dispose of an alert", async ({ page, request }) => {
    // Separation of duties, as the console shows it: a supervisor has the money
    // permissions and therefore not alert:dispose, so the lifecycle buttons are
    // absent rather than present and failing on click.
    const agent = await staffToken(request, "agent:nadeesha", ["agent"]);
    const { caseId } = await evaluatedCase(request, agent, PRIYA);
    await proposedPlan(request, agent, caseId, "agent:nadeesha");

    await signInAs(page, "Compliance");
    const alerts = page.getByTestId("alerts-panel");
    await expect(alerts).toBeVisible({ timeout: 30_000 });
    // Compliance holds alert:dispose by role, so the control is there for them.
    if ((await alerts.getByTestId("alert-row").count()) > 0) {
      await expect(alerts.getByRole("button", { name: /acknowledge|dispose/i }).first()).toBeVisible();
    }

    await signInAs(page, "Supervisor");
    const forSupervisor = page.getByTestId("alerts-panel");
    if (await forSupervisor.isVisible().catch(() => false)) {
      await expect(forSupervisor).toContainText("needs alert:dispose");
    } else {
      // A supervisor may hold no audit:read either, in which case the page
      // refuses outright, which is the same rule enforced one step earlier.
      await expect(page.getByText(/audit:read/)).toBeVisible();
    }
  });
});
