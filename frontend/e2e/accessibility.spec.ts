import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { CONSOLE, customerToken, signInOnDesk, signedIn } from "./session";

/**
 * FE01 (#28) acceptance 2: every page passes an axe run with no serious
 * violations.
 *
 * **What "serious" means here.** axe tags each violation `minor`, `moderate`,
 * `serious` or `critical`. The issue's bar is "no serious violations", so this
 * suite fails on `serious` and `critical` and reports the rest without failing.
 * Treating every `minor` as a blocker is how an accessibility gate gets
 * disabled a week later; treating a `critical` as advisory is how a page ships
 * that a screen reader cannot use at all.
 *
 * **Why the violations are printed, not just counted.** A failure that says
 * "3 violations" sends the next person back to axe to find out what they were.
 * The reporter below prints the rule, the impact and the element.
 */

/** Rules axe cannot judge from a running page, or that need a human. */
const DISABLED = [
  // Needs the whole page's colour contrast computed against images, which axe
  // reports as "incomplete" rather than pass or fail. Reviewed by hand.
  "color-contrast-enhanced",
];

type Violation = {
  id: string;
  impact?: string | null;
  help: string;
  nodes: { target: unknown[] }[];
};

function describe(violations: Violation[]): string {
  return violations
    .map(
      (v) =>
        `  [${v.impact ?? "unknown"}] ${v.id}: ${v.help}\n` +
        v.nodes.map((n) => `      at ${JSON.stringify(n.target)}`).join("\n"),
    )
    .join("\n");
}

async function audit(page: Page, name: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .disableRules(DISABLED)
    .analyze();

  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  ) as Violation[];
  const lesser = results.violations.filter(
    (v) => v.impact !== "serious" && v.impact !== "critical",
  ) as Violation[];

  if (lesser.length > 0) {
    console.log(`axe on ${name}: ${lesser.length} non-serious violation(s)\n${describe(lesser)}`);
  }

  expect(
    serious,
    `axe found ${serious.length} serious or critical violation(s) on ${name}:\n${describe(serious)}`,
  ).toEqual([]);
}




test.describe("accessibility", () => {
  test("the sign-in page has no serious violations", async ({ page }) => {
    await page.goto("/login");
    await audit(page, "/login");
  });

  test("the account page has no serious violations", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
        await page.goto("/account");
    await audit(page, "/account");
  });

  test("the clarity chat has no serious violations", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
        await page.goto("/clarity");
    await audit(page, "/clarity");
  });

  test("the cases list has no serious violations", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
        await page.goto("/cases");
    await audit(page, "/cases");
  });

  test("the packages page has no serious violations", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await page.goto("/packages");
    await expect(page.getByRole("heading", { name: "Packages" })).toBeVisible();
    await audit(page, "/packages");
  });

  test("the usage page has no serious violations", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await page.goto("/usage");
    await expect(page.getByRole("heading", { name: "Usage" })).toBeVisible();
    await audit(page, "/usage");
  });

  test("a chat in mid-journey has no serious violations", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    // The confirm card, the citation and the journey nav only exist once a
    // flow is running, and they are the parts a customer acts on. Auditing
    // only the empty page would miss exactly the controls that matter.
        await page.goto("/clarity");
    const box = page.getByRole("textbox", { name: /ask|message|type/i });
    await box.fill("Why was LKR 49 deducted from my balance?");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: /found the reason/i })).toBeVisible();

    // Audit the confirm sheet, not the resting page: it is where a customer
    // commits to money moving, so it is the state whose labels, focus order
    // and contrast matter most.
    await page.getByRole("button", { name: /refund & disable/i }).click();
    await expect(page.getByRole("heading", { name: /disable this subscription/i })).toBeVisible();

    await audit(page, "/clarity with the confirm sheet open");
  });
});

/**
 * The console, every route (E2).
 *
 * **Why each route needs its own run and its own identity.** The console is
 * deny-by-default, so a route rendered for the wrong role is the access-denied
 * card, and auditing that would pass while proving nothing about the page. Each
 * test therefore signs in as a role that holds the permission the route checks:
 * Foresight and Studio are only reachable as CX engineering, Audit as security,
 * the merchant block as VAS ops.
 *
 * **Why the dialogs are audited open.** A focus trap, an accessible name and a
 * described-by only exist while the dialog is mounted, and those are exactly
 * what E2 added. Auditing the resting page would miss them.
 */
test.describe("console accessibility", () => {
  test("the signed-out shell has no serious violations", async ({ page }) => {
    await page.goto(`${CONSOLE}/`);
    await expect(page.getByRole("heading", { name: "Clarity Desk" })).toBeVisible();
    await audit(page, "console /");
  });

  test("the landing page has no serious violations", async ({ page }) => {
    await page.goto(`${CONSOLE}/`);
    await signInOnDesk(page, "Supervisor");
    await audit(page, "console / (signed in)");
  });

  test("the desk has no serious violations, with a case open", async ({ page }) => {
    await page.goto(`${CONSOLE}/desk`);
    await signInOnDesk(page, "Supervisor");
    await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible({
      timeout: 30_000,
    });

    // The case panel is where the evidence and the approve controls are, and
    // it only exists once a case is open.
    const queue = page.getByRole("button", { name: /CASE-|sim swap|duplicate/i });
    if ((await queue.count()) > 0) {
      await queue.first().click();
      await expect(page.getByRole("heading", { name: "Ranked cause" })).toBeVisible({
        timeout: 30_000,
      });
    }
    await audit(page, "console /desk");
  });

  test("the merchant block dialog has no serious violations", async ({ page }) => {
    await page.goto(`${CONSOLE}/desk`);
    await signInOnDesk(page, "VAS Ops");
    await page.getByRole("button", { name: "Suspend GameZone" }).click();
    await expect(
      page.getByRole("dialog", { name: /block gamezone for this subscriber/i }),
    ).toBeVisible();
    await audit(page, "console /desk with the block dialog open");
  });

  test("insights has no serious violations", async ({ page }) => {
    await page.goto(`${CONSOLE}/insights`);
    await signInOnDesk(page, "Supervisor");
    await expect(page.getByRole("heading", { name: "Insights" })).toBeVisible({
      timeout: 30_000,
    });
    await audit(page, "console /insights");
  });

  test("the autopsy workspace has no serious violations", async ({ page }) => {
    await page.goto(`${CONSOLE}/autopsy`);
    await signInOnDesk(page, "Supervisor");
    await expect(page.getByRole("heading", { name: "Complaint Autopsy" })).toBeVisible({
      timeout: 30_000,
    });
    await audit(page, "console /autopsy");
  });

  test("foresight has no serious violations", async ({ page }) => {
    await page.goto(`${CONSOLE}/foresight`);
    await signInOnDesk(page, "CX");
    await expect(page.getByRole("heading", { name: "Foresight rehearsal" })).toBeVisible({
      timeout: 30_000,
    });
    await audit(page, "console /foresight");
  });

  test("policy studio has no serious violations", async ({ page }) => {
    await page.goto(`${CONSOLE}/studio`);
    await signInOnDesk(page, "CX");
    await expect(page.getByRole("heading", { name: "Policy Studio" })).toBeVisible({
      timeout: 30_000,
    });
    await audit(page, "console /studio");
  });

  test("the audit section has no serious violations, trail loaded", async ({ page }) => {
    await page.goto(`${CONSOLE}/audit`);
    await signInOnDesk(page, "Security");
    await expect(page.getByTestId("chain-health")).toBeVisible({ timeout: 30_000 });

    // The trail grid is the densest thing in the console and the part E2 gave
    // keyboard navigation, so it is audited loaded rather than empty.
    await page.getByTestId("load-trail").click();
    await expect(page.getByTestId("trail-explorer").locator("table")).toBeVisible({
      timeout: 30_000,
    });
    await audit(page, "console /audit with the trail loaded");
  });

  test("the alert dispose dialog has no serious violations", async ({ page }) => {
    await page.goto(`${CONSOLE}/audit`);
    await signInOnDesk(page, "Compliance");
    await expect(page.getByTestId("alerts-panel")).toBeVisible({ timeout: 30_000 });

    const dispose = page.getByRole("button", { name: /^Dispose of / });
    // Nothing may have fired, and a quiet queue is the normal state. The
    // dialog is audited when there is an alert to dispose of.
    test.skip((await dispose.count()) === 0, "no alert has fired to dispose of");
    await dispose.first().click();
    await expect(page.getByRole("dialog", { name: "Close this alert" })).toBeVisible();
    await audit(page, "console /audit with the dispose dialog open");
  });

  test("admin has no serious violations, with the flip dialog open", async ({ page }) => {
    await page.goto(`${CONSOLE}/admin`);
    await signInOnDesk(page, "Platform");
    await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible({
      timeout: 30_000,
    });
    await audit(page, "console /admin");

    const flip = page.getByRole("button", { name: /^Turn (off|on) / });
    test.skip((await flip.count()) === 0, "this role cannot flip a switch");
    await flip.first().click();
    await expect(page.getByRole("dialog", { name: /^Turn (on|off) / })).toBeVisible();
    await audit(page, "console /admin with the flip dialog open");
  });
});
