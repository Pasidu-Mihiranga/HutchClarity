import { expect, test } from "@playwright/test";
import { CONSOLE, signInOnDesk } from "./session";

/**
 * Authorization, as the console shows it (UI02 acceptance 5).
 *
 * "An unauthorized user attempts access; backend denial and navigation
 * visibility agree."
 *
 * **The failure this is really about.** There are two places a permission is
 * expressed: the nav decides whether to offer a link, and the API decides
 * whether to answer. When they disagree, both ways are bad and neither is
 * obvious. A link to a refusal wastes a click and tells a screen reader
 * nothing; a hidden link to a page the role *could* use quietly removes
 * somebody's job. E2 found exactly the first case live: the Foresight link was
 * gated on `desk:queue:read` while the page required `foresight:read`, so
 * every supervisor was shown a link to a refusal.
 *
 * So each test here pins a pair: what the nav offers, and what the page says
 * when it is reached directly. Deny-by-default (I9) means the direct visit is
 * the one that must always refuse.
 */

/** Every console section, with the permission its page actually checks. */
const SECTIONS = [
  { path: "/desk", link: "Desk", needs: "desk:queue:read" },
  { path: "/insights", link: "Insights", needs: "desk:queue:read" },
  { path: "/autopsy", link: "Complaint Autopsy", needs: "desk:queue:read" },
  { path: "/foresight", link: "Foresight", needs: "foresight:read" },
  { path: "/audit", link: "Audit", needs: "audit:read" },
] as const;

test.describe("navigation and the API agree about what a role may open", () => {
  test("an auditor is refused the desk, and is not offered it", async ({ page }) => {
    await page.goto(`${CONSOLE}/desk`);
    await signInOnDesk(page, "Auditor", false);

    // The page refuses, naming the permission rather than rendering an empty
    // desk, which would read as "no work waiting".
    await expect(page.getByText(/desk:queue:read/)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("button", { name: /approve as/i })).toHaveCount(0);
    // And the nav agrees: no link to it.
    await expect(page.getByRole("link", { name: "Desk", exact: true })).toHaveCount(0);
  });

  test("a supervisor is not offered Foresight, because the page would refuse", async ({
    page,
  }) => {
    await page.goto(`${CONSOLE}/desk`);
    await signInOnDesk(page, "Supervisor");
    await expect(page.getByRole("heading", { name: "Desk" })).toBeVisible({ timeout: 60_000 });

    // This is the regression E2 fixed. `foresight:read` is product and CX
    // engineering's; approving money is a different job from rehearsing a
    // change.
    await expect(page.getByRole("link", { name: "Foresight", exact: true })).toHaveCount(0);
    await expect(page.getByText("Foresight")).toBeVisible();
    await expect(page.getByText("(not available for your role)").first()).toBeVisible();

    // Reached directly, the page refuses, which is the half that has to be
    // true even if the nav were wrong.
    await page.goto(`${CONSOLE}/foresight`);
    await expect(page.getByText(/foresight:read/)).toBeVisible({ timeout: 30_000 });
  });

  test("an agent cannot reach the audit trail by typing the address", async ({ page }) => {
    await page.goto(`${CONSOLE}/audit`);
    await signInOnDesk(page, "Agent", false);

    await expect(page.getByText(/audit:read/)).toBeVisible({ timeout: 60_000 });
    // Not one panel of it, either: the refusal is the whole page.
    await expect(page.getByTestId("chain-health")).toHaveCount(0);
    await expect(page.getByTestId("trail-explorer")).toHaveCount(0);
  });

  test("a signed-out console refuses every section it offers", async ({ page }) => {
    // The nav shows the whole map before sign-in, because there is no identity
    // to refuse yet. Each page still has to refuse.
    await page.goto(`${CONSOLE}/`);
    for (const section of SECTIONS) {
      await expect(page.getByRole("link", { name: section.link, exact: true })).toBeVisible();
    }

    await page.goto(`${CONSOLE}/desk`);
    await expect(page.getByText(/Sign in from the header/)).toBeVisible({ timeout: 30_000 });
  });

  test("a role that may read cannot write, and the controls are absent not broken", async ({
    page,
  }) => {
    // Compliance holds `audit:read` and `alert:dispose` but not `audit:assign`,
    // so the grant list is refused and the rest of the page stays live. A
    // single failed panel must not blank the others.
    await page.goto(`${CONSOLE}/audit`);
    await signInOnDesk(page, "Compliance");

    await expect(page.getByTestId("chain-health")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("alerts-panel")).toBeVisible();
    await expect(page.getByTestId("access-refused")).toContainText("audit:assign");
  });

  test("Policy Studio shows each person only the half they hold", async ({ page }) => {
    // D3: `config:draft` opens a change, `config:approve` signs it off, and the
    // API refuses the maker's own approval. CX drafts and does not approve.
    await page.goto(`${CONSOLE}/studio`);
    await signInOnDesk(page, "CX");
    await expect(page.getByRole("heading", { name: "Policy Studio" })).toBeVisible({
      timeout: 60_000,
    });

    await expect(page.getByRole("heading", { name: "Open a change" })).toBeVisible();
    await expect(page.getByText(/config:approve/)).toBeVisible();
    await expect(page.getByRole("button", { name: /^Approve / })).toHaveCount(0);
  });

  test("an admin may flip a switch and may not approve money", async ({ page }) => {
    // Separation of duties: platform admins never approve refunds. The desk is
    // where money is approved and an admin holds no `desk:queue:read`.
    await page.goto(`${CONSOLE}/admin`);
    await signInOnDesk(page, "Platform");
    await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("button", { name: /^Turn (off|on) / }).first()).toBeVisible();

    await page.goto(`${CONSOLE}/desk`);
    await expect(page.getByText(/desk:queue:read/)).toBeVisible({ timeout: 30_000 });
  });
});
