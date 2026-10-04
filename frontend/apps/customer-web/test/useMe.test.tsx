import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

/**
 * The customer payload hook (E6, for E4).
 *
 * **What these tests are really protecting.** Every screen in customer-web
 * used to fill itself in when a request failed: a balance, two cases, a
 * "VAS silent renewal" charge of LKR 99.00. The product's whole claim is that
 * a figure on the screen came from a record (I2, I16), and a fallback object
 * breaks that claim in the one case where a customer is least able to tell.
 *
 * So the first test is the important one: a failed load leaves `app` null and
 * renders nothing of the account. It is also the test most likely to start
 * failing for the "helpful" reason, when somebody adds a placeholder so the
 * screen looks less empty.
 *
 * The second is the session boundary: a refused session must send the customer
 * to sign in, not show them a page that cannot work.
 */

const myApp = vi.fn();
const reload = vi.fn();
const expireSession = vi.fn();

class FakeApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

vi.mock("@clarity/sdk", () => ({
  ClarityApiError: FakeApiError,
  ClarityClient: class {
    myApp = myApp;
    reload = reload;
  },
}));

vi.mock("@/lib/session", () => ({ expireSession: () => expireSession() }));

const { useMe } = await import("@/lib/useMe");

const PAYLOAD = { name: "Nimal", masked: "078 *** 3333", balance_lkr: "120.00" };

function Probe() {
  const { app, loading, error, act, busy } = useMe();
  return (
    <div>
      <p data-testid="state">
        {loading ? "loading" : app ? `account:${app.name}` : "no-account"}
      </p>
      <p data-testid="balance">{app ? app.balance_lkr : ""}</p>
      <p data-testid="error">{error ?? ""}</p>
      <button type="button" disabled={busy} onClick={() => void act((api) => api.reload("500"))}>
        Reload
      </button>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  myApp.mockResolvedValue(PAYLOAD);
  reload.mockResolvedValue({ ...PAYLOAD, balance_lkr: "620.00" });
});

describe("useMe", () => {
  test("it renders the account the API sent", async () => {
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("account:Nimal"));
    expect(screen.getByTestId("balance")).toHaveTextContent("120.00");
  });

  test("a failed load fills nothing in", async () => {
    myApp.mockRejectedValue(new Error("gateway timeout"));
    render(<Probe />);

    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("no-account"));
    // No balance, no name, no invented pack. The screen says it could not
    // load, and the page renders an error state from that.
    expect(screen.getByTestId("balance")).toHaveTextContent("");
    expect(screen.getByTestId("error")).toHaveTextContent("gateway timeout");
  });

  test("a refused session goes to sign in, not to an error", async () => {
    myApp.mockRejectedValue(new FakeApiError("token expired", 401));
    render(<Probe />);

    await waitFor(() => expect(expireSession).toHaveBeenCalled());
    // Deliberately not an error message: the customer is being sent to sign
    // in with a return address, so telling them something broke would be wrong.
    expect(screen.getByTestId("error")).toHaveTextContent("");
  });

  test("a write adopts the payload it returns, without a reload", async () => {
    const user = userEvent.setup();
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("balance")).toHaveTextContent("120.00"));

    await user.click(screen.getByRole("button", { name: "Reload" }));

    await waitFor(() => expect(screen.getByTestId("balance")).toHaveTextContent("620.00"));
    // One read, at mount. The write's own response is the new truth, so a
    // second GET would only be a chance for the two to disagree.
    expect(myApp).toHaveBeenCalledTimes(1);
  });

  test("a refused write shows the API's own words", async () => {
    const user = userEvent.setup();
    reload.mockRejectedValue(new FakeApiError("choose a listed reload amount", 422));
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("balance")).toHaveTextContent("120.00"));

    await user.click(screen.getByRole("button", { name: "Reload" }));

    // Not "something went wrong": the API's refusal tells the customer what to
    // do instead, and rewriting it hides the rule that refused.
    await waitFor(() =>
      expect(screen.getByTestId("error")).toHaveTextContent("choose a listed reload amount"),
    );
    // And the account it already had is untouched.
    expect(screen.getByTestId("balance")).toHaveTextContent("120.00");
  });
});
