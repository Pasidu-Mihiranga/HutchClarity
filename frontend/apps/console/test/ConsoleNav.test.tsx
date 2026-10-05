import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

/**
 * The console's section navigation and its refusal card (E6, for E2).
 *
 * **Why these two.** They decide what a staff member can even see. The active
 * section uses `aria-current`; after sign-in, sections this identity cannot
 * open are omitted from the sidebar.
 *
 * A signed-in identity that opens a URL they cannot keep is redirected to the
 * first allowed section, rather than left on a dead AccessDenied card.
 */

const pathname = vi.fn(() => "/desk");
const replace = vi.fn();
const hasPermission = vi.fn(() => true);
const session = { subject: "sup:ruwan", roles: ["supervisor"], permissions: ["desk:queue:read"] };
const sessionState: { session: unknown; restoring: boolean; activeRole: string | null } = {
  session,
  restoring: false,
  activeRole: "supervisor",
};

vi.mock("next/navigation", () => ({
  usePathname: () => pathname(),
  useRouter: () => ({ replace }),
}));

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
  replace.mockReset();
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
    expect(screen.getAllByRole("listitem")).toHaveLength(9);
  });

  test("the section being viewed is marked, not just coloured", () => {
    pathname.mockReturnValue("/audit");
    render(<ConsoleNav />);
    expect(screen.getByRole("link", { name: "Audit" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Cases" })).not.toHaveAttribute("aria-current");
  });

  test("a section this identity cannot open is omitted", () => {
    hasPermission.mockReturnValue(false);
    render(<ConsoleNav />);

    expect(screen.queryByRole("link", { name: "Audit" })).toBeNull();
    expect(screen.queryByText("Audit")).toBeNull();
    expect(screen.queryByRole("listitem")).toBeNull();
  });

  test("only sections this identity can open stay in the sidebar", () => {
    hasPermission.mockImplementation((...needed: string[]) =>
      needed.includes("desk:queue:read"),
    );
    render(<ConsoleNav />);

    expect(screen.getByRole("link", { name: "Cases" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Insights" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Complaint Autopsy" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Foresight" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Studio" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Offers" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Audit" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });
});

describe("AccessDenied", () => {
  test("signed in with another section: redirect instead of a dead card", () => {
    hasPermission.mockImplementation((...needed: string[]) =>
      needed.includes("admin:manage"),
    );
    render(<AccessDenied need="desk:queue:read" />);
    expect(replace).toHaveBeenCalledWith("/admin");
    expect(screen.getByRole("status")).toHaveTextContent(/Opening Admin/i);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  test("security with offers goes to Offers, not a desk refusal", () => {
    hasPermission.mockImplementation((...needed: string[]) =>
      needed.includes("offer:manage") || needed.includes("admin:manage"),
    );
    render(<AccessDenied need="desk:queue:read" />);
    expect(replace).toHaveBeenCalledWith("/offers");
  });

  test("it carries the page's h1 when there is nowhere to send them", () => {
    hasPermission.mockReturnValue(false);
    render(<AccessDenied need="audit:read" />);
    expect(
      screen.getByRole("heading", { level: 1, name: /cannot open this/i }),
    ).toBeInTheDocument();
  });

  test("the refusal is announced and names the permission when stuck", () => {
    hasPermission.mockReturnValue(false);
    render(<AccessDenied need="audit:read" />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("audit:read");
    expect(alert).toHaveTextContent("sup:ruwan");
  });

  test("restoring a session is a status, not an alert", () => {
    sessionState.restoring = true;
    render(<AccessDenied need="audit:read" />);
    expect(screen.getByRole("status")).toHaveTextContent(/restoring/i);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(replace).not.toHaveBeenCalled();
  });

  test("with no session it tells you to sign in rather than naming a role", () => {
    sessionState.session = null;
    sessionState.activeRole = null;
    render(<AccessDenied need="audit:read" />);
    expect(screen.getByRole("alert")).toHaveTextContent(/sign in to start/i);
    expect(replace).not.toHaveBeenCalled();
  });
});
