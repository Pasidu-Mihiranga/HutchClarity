import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

/**
 * The console's section navigation and its refusal card (E6, for E2).
 *
 * **Why these two.** They are the parts that decide what a staff member can
 * even see, and both state it in ways only assistive tech reads: the active
 * section through `aria-current`, an unreachable section through text rather
 * than a dimmed link. Neither is visible to a reviewer skimming the rendered
 * page, so both are easy to lose in a later edit.
 *
 * The permission check itself is the backend's and is tested there. What is
 * tested here is that the nav asks, and renders the answer honestly: a section
 * this identity cannot open must not be a link, because a link that lands on a
 * refusal wastes the click and tells a screen reader nothing.
 */

const pathname = vi.fn(() => "/desk");
const hasPermission = vi.fn(() => true);
const session = { subject: "sup:ruwan", roles: ["supervisor"], permissions: ["desk:queue:read"] };
const sessionState: { session: unknown; restoring: boolean; activeRole: string | null } = {
  session,
  restoring: false,
  activeRole: "supervisor",
};

vi.mock("next/navigation", () => ({ usePathname: () => pathname() }));

vi.mock("@/components/StaffSessionProvider", () => ({
  useStaffSession: () => ({
    ...sessionState,
    hasPermission,
  }),
}));

// Imported after the mocks, which is what `vi.mock` hoisting needs.
const { ConsoleNav } = await import("@/components/ConsoleNav");
const { AccessDenied } = await import("@/components/AccessDenied");

beforeEach(() => {
  pathname.mockReturnValue("/desk");
  hasPermission.mockReturnValue(true);
  sessionState.session = session;
  sessionState.restoring = false;
  sessionState.activeRole = "supervisor";
});

describe("ConsoleNav", () => {
  test("the sections are a list, so their number is announced", () => {
    render(<ConsoleNav />);
    const nav = screen.getByRole("navigation", { name: "Console sections" });
    expect(nav).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(7);
  });

  test("the section being viewed is marked, not just coloured", () => {
    pathname.mockReturnValue("/audit");
    render(<ConsoleNav />);
    expect(screen.getByRole("link", { name: "Audit" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Desk" })).not.toHaveAttribute("aria-current");
  });

  test("a section this identity cannot open is not a link", () => {
    hasPermission.mockReturnValue(false);
    render(<ConsoleNav />);

    // Not a dimmed link that goes to a refusal: no link at all.
    expect(screen.queryByRole("link", { name: "Audit" })).toBeNull();
    expect(screen.getByText("Audit")).toBeInTheDocument();
  });

  test("and it says why, in text a screen reader reads", () => {
    hasPermission.mockReturnValue(false);
    render(<ConsoleNav />);
    expect(screen.getAllByText("(not available for your role)").length).toBeGreaterThan(0);
  });

  test("a signed-out console offers every section", () => {
    // Before sign-in there is no identity to refuse, so the nav shows the map
    // of the product rather than an empty bar.
    sessionState.session = null;
    hasPermission.mockReturnValue(false);
    render(<ConsoleNav />);
    expect(screen.getAllByRole("link").length).toBeGreaterThan(7);
  });
});

describe("AccessDenied", () => {
  test("it carries the page's h1, because it replaces the page", () => {
    render(<AccessDenied need="audit:read" />);
    expect(
      screen.getByRole("heading", { level: 1, name: /cannot open this/i }),
    ).toBeInTheDocument();
  });

  test("the refusal is announced and names the permission", () => {
    render(<AccessDenied need="audit:read" />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("audit:read");
    expect(alert).toHaveTextContent("sup:ruwan");
  });

  test("restoring a session is a status, not an alert", () => {
    // A session being read back is not news. Announcing it assertively would
    // interrupt whatever the screen reader was saying.
    sessionState.restoring = true;
    render(<AccessDenied need="audit:read" />);
    expect(screen.getByRole("status")).toHaveTextContent(/restoring/i);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  test("with no session it tells you to sign in rather than naming a role", () => {
    sessionState.session = null;
    sessionState.activeRole = null;
    render(<AccessDenied need="audit:read" />);
    expect(screen.getByRole("alert")).toHaveTextContent(/sign in to start/i);
  });
});
