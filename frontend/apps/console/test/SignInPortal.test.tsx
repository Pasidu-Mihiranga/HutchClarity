import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

const signIn = vi.fn(async () => true);
const signInWithProvider = vi.fn();
const sessionState = {
  methods: { provider: false, directory: true, development_role_picker: false },
  busy: false,
  error: null,
};

vi.mock("@/components/StaffSessionProvider", () => ({
  useStaffSession: () => ({
    ...sessionState,
    signIn,
    signInWithProvider,
  }),
}));

const { SignInPortal } = await import("@/components/SignInPortal");

beforeEach(() => {
  signIn.mockClear();
  signInWithProvider.mockClear();
});

describe("SignInPortal", () => {
  test("offers every synthetic staff role when the API enables the directory", () => {
    render(<SignInPortal />);

    expect(screen.getByRole("list", { name: "Staff roles" })).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(11);
    expect(screen.getByRole("button", { name: /Product/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Security admin/i })).toBeInTheDocument();
  });

  test("one role click fills its credentials and authenticates through the server", async () => {
    render(<SignInPortal />);

    fireEvent.click(screen.getByRole("button", { name: /Supervisor/i }));

    await waitFor(() =>
      expect(signIn).toHaveBeenCalledWith("supervisor", "supervisor-clarity", "step-up"),
    );
    expect(screen.getByLabelText("Username")).toHaveValue("supervisor");
    expect(screen.getByLabelText("Password")).toHaveValue("supervisor-clarity");
    expect(screen.getByLabelText(/^Step-up code/)).toHaveValue("step-up");
  });
});
