import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { customerToken, signedIn } from "./session";

/**
 * The chat's waiting state: the thinking orb.
 *
 * **Why the turn is held.** Against the lite API a turn answers in a few
 * milliseconds, so the waiting state is gone before any other spec could see
 * it, and a broken orb would pass the whole suite. Holding the turn request
 * keeps the waiting state on screen long enough to assert on and to audit.
 * The request is released unchanged afterwards, so the journey still ends on
 * the real backend's answer.
 *
 * Both turn routes are held: the chat asks over `/v1/conversation/turn/stream`
 * and falls back to the JSON route, and holding only one let the stream's
 * stage events replace the first label before the assertion ran.
 */

async function holdTurns(page: Page): Promise<() => void> {
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/v1/conversation/turn{,/stream}", async (route) => {
    await gate;
    await route.continue();
  });
  return release;
}

test.describe("thinking orb", () => {
  test("a pending question shows the orb with a live status, then the answer replaces it", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    const release = await holdTurns(page);
    await page.goto("/clarity");

    await page.getByRole("textbox", { name: /ask|message|type/i }).fill("Why was LKR 49 deducted from my balance?");
    await page.keyboard.press("Enter");

    const orb = page.locator(".mo-wait");
    await expect(orb).toBeVisible();
    await expect(orb.locator("canvas")).toBeVisible();
    // The status is announced politely, and starts at the first label.
    await expect(orb.getByRole("status")).toHaveText("Thinking");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .disableRules(["color-contrast-enhanced"])
      .analyze();
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => v.id)).toEqual([]);

    release();
    await expect(page.getByRole("heading", { name: /found the reason/i })).toBeVisible();
    await expect(orb).toHaveCount(0);
  });

  test("the waiting labels follow the chosen language", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    const release = await holdTurns(page);
    await page.goto("/clarity");
    // The language is not persisted, so pick it the way a customer would.
    // `supportedLangs` orders the buttons en, si, ta.
    await page.getByRole("group", { name: "Language" }).getByRole("button").nth(1).click();

    await page.getByRole("textbox").first().fill("Why was LKR 49 deducted from my balance?");
    await page.keyboard.press("Enter");

    await expect(page.locator(".mo-wait").getByRole("status")).toHaveText("සිතමින්");
    release();
  });
});
