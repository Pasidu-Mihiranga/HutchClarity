import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

const requestOtp = vi.fn();
const demoInbox = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/components/LanguageProvider", () => ({ useLanguage: () => ({ lang: "en" }) }));
vi.mock("@clarity/sdk", () => ({
  ClarityClient: class {
    requestOtp = requestOtp;
    demoInbox = demoInbox;
  },
}));

const { default: LoginPage } = await import("@/app/login/page");

beforeEach(() => {
  requestOtp.mockReset();
  demoInbox.mockReset();
});

describe("customer OTP request", () => {
  test("real SMS delivery does not call the production-disabled inbox", async () => {
    requestOtp.mockResolvedValue({
      challenge_id: "challenge-1",
      simulated: false,
      detail: "A sign-in code was requested by SMS.",
    });
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Hutch number"), { target: { value: "0787720767" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await screen.findByLabelText("6-digit code");
    expect(demoInbox).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Resend code" })).toBeEnabled();
  });

  test("resend issues a fresh challenge through the same protected endpoint", async () => {
    requestOtp.mockResolvedValue({ challenge_id: "challenge-1", simulated: false });
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Hutch number"), { target: { value: "0787720767" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByLabelText("6-digit code");
    expect(requestOtp).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Resend code" }));
    await waitFor(() => expect(requestOtp).toHaveBeenCalledTimes(2));
  });
});
