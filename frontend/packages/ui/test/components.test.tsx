import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import {
  Alert,
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Pagination,
  Select,
  Tab,
  TabList,
  TabPanel,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Tabs,
  ToastProvider,
  Tooltip,
  pageWindow,
  useToast,
} from "../src";

describe("forwardRef", () => {
  it("passes refs through the form primitives", () => {
    const button = React.createRef<HTMLButtonElement>();
    const input = React.createRef<HTMLInputElement>();
    const select = React.createRef<HTMLSelectElement>();
    render(
      <>
        <Button ref={button}>Go</Button>
        <Input ref={input} aria-label="name" />
        <Select ref={select} aria-label="kind">
          <option>a</option>
        </Select>
      </>,
    );
    expect(button.current).toBeInstanceOf(HTMLButtonElement);
    expect(input.current).toBeInstanceOf(HTMLInputElement);
    expect(select.current).toBeInstanceOf(HTMLSelectElement);
  });
});

describe("Button", () => {
  it("is disabled and busy while loading", () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("never submits a form unless asked", () => {
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <Button>Plain</Button>
      </form>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Plain" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("Field", () => {
  it("ties label, hint and error to the control", () => {
    render(
      <Field label="Phone" hint="Digits only" error="Too short">
        {(c) => <Input {...c} />}
      </Field>,
    );
    const input = screen.getByLabelText("Phone");
    expect(input).toHaveAttribute("aria-invalid", "true");
    const described = input.getAttribute("aria-describedby") ?? "";
    expect(described.split(" ")).toHaveLength(2);
    expect(document.getElementById(described.split(" ")[1])).toHaveTextContent("Too short");
  });
});

describe("Dialog", () => {
  function Harness({ onClose = () => {} }: { onClose?: () => void }) {
    const [open, setOpen] = React.useState(false);
    return (
      <>
        <button onClick={() => setOpen(true)}>Open</button>
        <Dialog
          open={open}
          onClose={() => {
            setOpen(false);
            onClose();
          }}
          title="Confirm"
          description="Are you sure?"
          footer={<Button>Yes</Button>}
        >
          <input aria-label="reason" />
        </Dialog>
      </>
    );
  }

  it("is a named modal dialog and moves focus inside", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByText("Open"));
    const dialog = screen.getByRole("dialog", { name: "Confirm" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleDescription("Are you sure?");
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("traps Tab in both directions", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByText("Open"));
    const dialog = screen.getByRole("dialog");
    const stops = within(dialog).getAllByRole("button").concat(within(dialog).getByLabelText("reason"));
    for (let i = 0; i < stops.length * 2 + 1; i += 1) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
    for (let i = 0; i < stops.length * 2 + 1; i += 1) {
      await user.tab({ shift: true });
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  it("closes on Escape and returns focus to the opener", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const opener = screen.getByText("Open");
    await user.click(opener);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(opener).toHaveFocus();
  });

  it("closes on a backdrop click only when allowed", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { rerender } = render(
      <Dialog open onClose={onClose} title="T" dismissOnBackdrop={false}>
        body
      </Dialog>,
    );
    const backdrop = screen.getByRole("dialog").parentElement as HTMLElement;
    await user.pointer({ target: backdrop, keys: "[MouseLeft]" });
    expect(onClose).not.toHaveBeenCalled();
    rerender(
      <Dialog open onClose={onClose} title="T">
        body
      </Dialog>,
    );
    await user.pointer({ target: screen.getByRole("dialog").parentElement as HTMLElement, keys: "[MouseLeft]" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("Tabs", () => {
  it("moves with the arrow keys and keeps one tab stop", async () => {
    const user = userEvent.setup();
    render(
      <Tabs defaultValue="a">
        <TabList label="Sections">
          <Tab value="a">A</Tab>
          <Tab value="b">B</Tab>
          <Tab value="c">C</Tab>
        </TabList>
        <TabPanel value="a">panel a</TabPanel>
        <TabPanel value="b">panel b</TabPanel>
        <TabPanel value="c">panel c</TabPanel>
      </Tabs>,
    );
    expect(screen.getByRole("tab", { name: "A" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "B" })).toHaveAttribute("tabindex", "-1");
    screen.getByRole("tab", { name: "A" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "B" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("panel b");
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "C" })).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "A" })).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName("A");
  });
});

describe("Table", () => {
  it("has an accessible name and exposes sort state", async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();
    render(
      <Table caption="Audit events">
        <TableHead>
          <TableRow>
            <TableHeaderCell sort="ascending" onSort={onSort}>
              Time
            </TableHeaderCell>
            <TableHeaderCell>Actor</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <TableRow>
            <TableCell>10:00</TableCell>
            <TableCell>agent</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );
    expect(screen.getByRole("table", { name: "Audit events" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Time/ })).toHaveAttribute("aria-sort", "ascending");
    await user.click(screen.getByRole("button", { name: /Time/ }));
    expect(onSort).toHaveBeenCalled();
  });
});

describe("Pagination", () => {
  it("windows the pages and marks the current one", () => {
    expect(pageWindow(5, 10)).toEqual([1, null, 4, 5, 6, null, 10]);
    expect(pageWindow(1, 3)).toEqual([1, 2, 3]);
    const onPageChange = vi.fn();
    render(<Pagination page={2} pageCount={3} onPageChange={onPageChange} />);
    expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 2" })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("renders nothing for a single page and disables the ends", () => {
    const { container } = render(<Pagination page={1} pageCount={1} onPageChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
    render(<Pagination page={1} pageCount={4} onPageChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });
});

describe("Tooltip", () => {
  it("describes the trigger on focus and hides on Escape", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Copies the receipt id">
        <button>Copy</button>
      </Tooltip>,
    );
    await user.tab();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Copies the receipt id");
    expect(screen.getByRole("button", { name: "Copy" })).toHaveAccessibleDescription("Copies the receipt id");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});

describe("Toast", () => {
  function Trigger({ tone }: { tone: "info" | "danger" }) {
    const { toast } = useToast();
    return <button onClick={() => toast({ title: "Saved", tone, duration: 1000 })}>Fire</button>;
  }

  it("announces politely, dismisses itself and can be dismissed", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger tone="info" />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText("Fire"));
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    act(() => {
      vi.advanceTimersByTime(1100);
    });
    expect(screen.queryByRole("status")).toBeNull();
    vi.useRealTimers();
  });

  it("announces errors assertively", () => {
    render(
      <ToastProvider>
        <Trigger tone="danger" />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText("Fire"));
    expect(screen.getByRole("alert")).toHaveTextContent("Saved");
  });

  it("refuses to be used outside its provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Trigger tone="info" />)).toThrow(/ToastProvider/);
    spy.mockRestore();
  });
});

describe("feedback", () => {
  it("Alert picks its live-region role from urgency", () => {
    const { rerender } = render(<Alert tone="danger">Boom</Alert>);
    expect(screen.getByRole("alert")).toHaveTextContent("Boom");
    rerender(<Alert tone="success">Done</Alert>);
    expect(screen.getByRole("status")).toHaveTextContent("Done");
  });

  it("ErrorState announces and offers a retry", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Could not load" onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("EmptyState says why and what next", () => {
    render(<EmptyState title="No cases" description="Nothing yet" action={<button>New</button>} />);
    expect(screen.getByText("No cases")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New" })).toBeInTheDocument();
  });
});
