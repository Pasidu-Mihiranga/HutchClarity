import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { customerToken, signedIn } from "./session";

/**
 * Voice input in the chat.
 *
 * **Why the speech API is stubbed.** The real `SpeechRecognition` sends audio
 * to the browser vendor's service, which a test must not depend on (and a
 * headless browser has no microphone). The stub plays the part of that
 * service: it returns one fixed transcript. What is under test is everything
 * on our side of it: the opt-in notice, the transcript the customer can check,
 * and that the words reach the same turn pipeline as typed text.
 */

const SPOKEN = "Why was LKR 49 deducted from my balance?";

async function fakeSpeech(page: Page, transcript: string | null, failWith?: string): Promise<void> {
  await page.addInitScript(([said, fail]) => {
    const w = window as unknown as Record<string, unknown>;
    if (said === null) {
      delete w.SpeechRecognition;
      delete w.webkitSpeechRecognition;
      return;
    }
    class FakeRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        (window as unknown as { __speechLang?: string }).__speechLang = this.lang;
        if (fail) {
          setTimeout(() => { this.onerror?.({ error: fail }); this.onend?.(); }, 100);
          return;
        }
        setTimeout(() => {
          this.onresult?.({ resultIndex: 0, results: { length: 1, 0: { isFinal: true, length: 1, 0: { transcript: said } } } });
          this.onend?.();
        }, 300);
      }
      stop() { this.onend?.(); }
      abort() {}
    }
    w.SpeechRecognition = FakeRecognition;
    w.webkitSpeechRecognition = FakeRecognition;
  }, [transcript, failWith ?? null] as const);
}

test.describe("voice input", () => {
  test("Speak starts listening at once and says where the audio goes", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await fakeSpeech(page, SPOKEN);
    await page.goto("/clarity");

    await page.getByRole("button", { name: "Speak" }).click();
    const sheet = page.getByRole("dialog", { name: "Speak to Clarity" });
    await expect(sheet).toBeVisible();
    // The tap on Speak is the opt-in: no second tap, and the notice is there
    // while it listens.
    await expect(sheet.getByText(/goes to Google or Apple/)).toBeVisible();
    await expect(sheet.getByTestId("voice-transcript")).toHaveText(SPOKEN);

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .disableRules(["color-contrast-enhanced"])
      .analyze();
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => v.id)).toEqual([]);

    await page.keyboard.press("Escape");
    await expect(sheet).toHaveCount(0);
  });

  test("a spoken question is shown for checking, then asked like a typed one", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await fakeSpeech(page, SPOKEN);
    await page.goto("/clarity");

    await page.getByRole("button", { name: "Speak" }).click();
    const sheet = page.getByRole("dialog");

    await expect(sheet.getByTestId("voice-transcript")).toHaveText(SPOKEN);
    await expect(sheet.getByRole("status")).toHaveText("Is this what you said?");
    await sheet.getByRole("button", { name: "Ask" }).click();

    await expect(sheet).toHaveCount(0);
    await expect(page.getByText(SPOKEN)).toBeVisible();
    await expect(page.getByRole("heading", { name: /found the reason/i })).toBeVisible();
  });

  test("Edit puts the words in the message box instead of sending them", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await fakeSpeech(page, SPOKEN);
    await page.goto("/clarity");

    await page.getByRole("button", { name: "Speak" }).click();
    await page.getByRole("button", { name: "Edit" }).click();

    const box = page.getByRole("textbox", { name: /ask clarity/i });
    await expect(box).toHaveValue(SPOKEN);
    await expect(box).toBeFocused();
  });

  test("listening uses the chosen language", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await fakeSpeech(page, "මගේ ශේෂය අඩු වුණේ ඇයි?");
    await page.goto("/clarity");
    await page.getByRole("group", { name: "Language" }).getByRole("button").nth(1).click();

    await page.getByRole("button", { name: "කතා කරන්න" }).click();
    await expect(page.getByTestId("voice-transcript")).toBeVisible();
    expect(await page.evaluate(() => (window as unknown as { __speechLang?: string }).__speechLang)).toBe("si-LK");
  });

  test("a blocked microphone says so and offers Try again", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await fakeSpeech(page, SPOKEN, "not-allowed");
    await page.goto("/clarity");

    await page.getByRole("button", { name: "Speak" }).click();
    const sheet = page.getByRole("dialog");
    await expect(sheet.getByRole("status")).toContainText("Microphone access is blocked");
    await expect(sheet.getByRole("button", { name: "Try again" })).toBeFocused();
  });

  test("without speech recognition the Speak button is not offered", async ({ page, request }) => {
    await signedIn(page, await customerToken(request));
    await fakeSpeech(page, null);
    await page.goto("/clarity");

    await expect(page.getByRole("textbox", { name: /ask clarity/i })).toBeVisible();
    await expect(page.getByRole("button", { name: "Speak" })).toHaveCount(0);
  });
});
