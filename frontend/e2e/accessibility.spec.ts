import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { customerToken, signedIn } from "./session";

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

  test("a chat in mid-journey has no serious violations", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    // The confirm card, the citation and the journey nav only exist once a
    // flow is running, and they are the parts a customer acts on. Auditing
    // only the empty page would miss exactly the controls that matter.
        await page.goto("/clarity");
    const box = page.getByRole("textbox", { name: /ask|message|type/i });
    await box.fill("Why was LKR 49 deducted from my balance?");
    await page.keyboard.press("Enter");
    // The first turn opens the case; the flow runs from the second.
    await expect(page.getByRole("heading", { name: /found the reason/i })).toBeVisible();
    await box.fill("Yes, please fix it");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("navigation", { name: /charge|ගාස්තු|கட்டண/i })).toBeVisible();

    await audit(page, "/clarity mid-journey");
  });
});
