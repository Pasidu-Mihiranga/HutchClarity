import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

const signIn = vi.fn(async () => true);

vi.mock("@/components/StaffSessionProvider", () => ({
  useStaffSession: () => ({
    signIn,
    signInWithProvider: vi.fn(),
    methods: { provider: false, directory: true },
    busy: false,
    error: null,
  }),
}));

const { DeskLogin } = await import("@/components/DeskLogin");

beforeEach(() => signIn.mockClear());

describe("DeskLogin role autofill", () => {
  test("fills a selected role but waits for the explicit Sign in click", async () => {
    render(<DeskLogin />);

    fireEvent.click(screen.getByRole("button", { name: "Supervisor" }));

    expect(screen.getByLabelText("Staff ID or email")).toHaveValue("supervisor");
    expect(screen.getByLabelText("Password")).toHaveValue("supervisor-clarity");
    expect(screen.getByLabelText("Step-up code")).toHaveValue("step-up");
    expect(signIn).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(signIn).toHaveBeenCalledWith("supervisor", "supervisor-clarity", "step-up"),
    );
  });

  test("uses the configured platform-admin credential instead of deriving it", () => {
    render(<DeskLogin />);

    fireEvent.click(screen.getByRole("button", { name: "Platform admin" }));

    expect(screen.getByLabelText("Staff ID or email")).toHaveValue("admin");
    expect(screen.getByLabelText("Password")).toHaveValue("admin123456");
    expect(signIn).not.toHaveBeenCalled();
  });
});
