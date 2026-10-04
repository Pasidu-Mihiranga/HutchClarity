import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { useRovingRows } from "@/lib/useRovingRows";

/**
 * The audit trail's keyboard navigation (E6, for E2).
 *
 * **Why this is tested and not just reviewed.** A roving `tabIndex` is easy to
 * write in a way that looks right and is not: setting the index without moving
 * focus leaves the ring behind, so the visible position and the real one
 * drift, and the bug is invisible to anyone using a mouse. These tests assert
 * on `document.activeElement`, which is the thing a keyboard user experiences.
 */

function Grid({ rows, onActivate }: { rows: string[]; onActivate?: (index: number) => void }) {
  const { rowProps } = useRovingRows(rows.length, onActivate);
  return (
    <table role="grid">
      <tbody>
        {rows.map((label, index) => (
          <tr key={label} {...rowProps(index)} data-testid={label}>
            <td>{label}</td>
            <td>
              <button type="button">Verify {label}</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const ROWS = ["one", "two", "three"];

describe("useRovingRows", () => {
  test("the table is one tab stop, not one per row", () => {
    render(<Grid rows={ROWS} />);
    expect(screen.getByTestId("one")).toHaveAttribute("tabindex", "0");
    expect(screen.getByTestId("two")).toHaveAttribute("tabindex", "-1");
    expect(screen.getByTestId("three")).toHaveAttribute("tabindex", "-1");
  });

  test("Down and Up move focus a row at a time and stop at the ends", async () => {
    const user = userEvent.setup();
    render(<Grid rows={ROWS} />);
    const [one, two, three] = ROWS.map((label) => screen.getByTestId(label));

    one.focus();
    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(two);

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(three);

    // Clamped rather than wrapped: wrapping a 50-row trail puts a reader back
    // at the top without anything telling them it happened.
    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(three);

    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(document.activeElement).toBe(one);
    await user.keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(one);
  });

  test("Home and End jump to the ends", async () => {
    const user = userEvent.setup();
    render(<Grid rows={ROWS} />);
    const [one, , three] = ROWS.map((label) => screen.getByTestId(label));

    one.focus();
    await user.keyboard("{End}");
    expect(document.activeElement).toBe(three);
    await user.keyboard("{Home}");
    expect(document.activeElement).toBe(one);
  });

  test("the focused row becomes the tab stop", async () => {
    const user = userEvent.setup();
    render(<Grid rows={ROWS} />);
    screen.getByTestId("one").focus();
    await user.keyboard("{ArrowDown}");

    expect(screen.getByTestId("two")).toHaveAttribute("tabindex", "0");
    expect(screen.getByTestId("one")).toHaveAttribute("tabindex", "-1");
  });

  test("Enter acts on the focused row", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(<Grid rows={ROWS} onActivate={onActivate} />);

    screen.getByTestId("one").focus();
    await user.keyboard("{ArrowDown}{Enter}");
    expect(onActivate).toHaveBeenCalledWith(1);
  });

  test("a key pressed inside a row's own control is left alone", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(<Grid rows={ROWS} onActivate={onActivate} />);

    // Enter on the Verify button is the button's, not the grid's. Swallowing
    // it here would make the button do the row's action instead of its own.
    await user.click(screen.getByRole("button", { name: "Verify two" }));
    onActivate.mockClear();
    await user.keyboard("{ArrowDown}");
    expect(onActivate).not.toHaveBeenCalled();
  });

  test("a shorter list does not leave the active row past the end", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Grid rows={ROWS} />);
    // Moved with the keyboard rather than a bare `focus()`: the hook's state
    // update has to be flushed for the assertion below to mean anything, and
    // `userEvent` is what wraps it.
    screen.getByTestId("one").focus();
    await user.keyboard("{End}");
    expect(screen.getByTestId("three")).toHaveAttribute("tabindex", "0");

    // Filtering the trail down is the real case: the next arrow press must not
    // try to focus a row that is no longer rendered.
    rerender(<Grid rows={["one"]} />);
    expect(screen.getByTestId("one")).toHaveAttribute("tabindex", "0");
  });

  test("an empty table does not throw on a key press", async () => {
    const user = userEvent.setup();
    render(<Grid rows={[]} />);
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("grid")).toBeInTheDocument();
  });
});
