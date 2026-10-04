import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const { CaseRow } = await import("@/components/CaseRow");

/**
 * One row in the customer's case list (E6, for E4).
 *
 * The row's old props (`cause`, `amount`) did not exist on the payload. They
 * were filled from two invented cases, so nothing noticed that the real data
 * carries a `headline` and an `outcome` and no amount at all. These tests pin
 * the row to the fields the API actually sends, and pin the one judgement the
 * row makes: what to say about a case that has not been decided yet.
 */

const BASE = {
  id: "case-1",
  caseNo: "CS-2026-0012",
  state: "OPEN",
  open: true,
  headline: "A subscription renewed without a confirmation",
  outcome: "ONE_TAP_FIX",
  openedAt: "2026-10-02T09:15:00Z",
};

describe("CaseRow", () => {
  test("it links to the case and shows what the decision said", () => {
    render(<CaseRow {...BASE} />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/case/case-1");
    expect(screen.getByText(BASE.headline)).toBeInTheDocument();
    expect(screen.getByText(/CS-2026-0012/)).toBeInTheDocument();
    expect(screen.getByText(/one tap fix/i)).toBeInTheDocument();
  });

  test("an undecided case says so instead of inventing a cause", () => {
    // `headline` is the first line of the decision's own rationale, so it is
    // null until there is a decision. The row must not reach for anything else.
    render(<CaseRow {...BASE} headline={null} outcome={null} />);
    expect(screen.getByText("Looking into this")).toBeInTheDocument();
    expect(screen.queryByText(/one tap fix/i)).toBeNull();
  });

  test("a multi-word state reads as words", () => {
    render(<CaseRow {...BASE} state="AWAITING_APPROVAL" />);
    expect(screen.getByText("AWAITING APPROVAL")).toBeInTheDocument();
  });

  test("an unparseable date is shown as it arrived, not as Invalid Date", () => {
    render(<CaseRow {...BASE} openedAt="not-a-date" />);
    expect(screen.getByText("not-a-date")).toBeInTheDocument();
  });
});
