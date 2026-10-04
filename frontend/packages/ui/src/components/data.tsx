"use client";

import * as React from "react";
import { cx, focusRing, useControllable } from "./utils";

/* ------------------------------------------------------------------ Table */

export type TableProps = React.TableHTMLAttributes<HTMLTableElement> & {
  /** Required: a table without a caption has no accessible name. Visually hidden by default. */
  caption: React.ReactNode;
  showCaption?: boolean;
  /** Makes the scroll container focusable so keyboard users can scroll wide tables. */
  scrollLabel?: string;
};

export const Table = React.forwardRef<HTMLTableElement, TableProps>(function Table(
  { caption, showCaption = false, scrollLabel, className, children, ...rest },
  ref,
) {
  return (
    <div
      className={cx("overflow-x-auto rounded-md border border-border", focusRing)}
      role="region"
      aria-label={scrollLabel ?? (typeof caption === "string" ? caption : undefined)}
      tabIndex={0}
    >
      <table ref={ref} className={cx("w-full border-collapse text-left text-sm", className)} {...rest}>
        <caption className={showCaption ? "px-3 py-2 text-left text-sm font-semibold" : "sr-only"}>{caption}</caption>
        {children}
      </table>
    </div>
  );
});

export const TableHead = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  function TableHead({ className, ...rest }, ref) {
    return <thead ref={ref} className={cx("bg-surface-2 text-xs uppercase tracking-wide text-fg-muted", className)} {...rest} />;
  },
);

export const TableBody = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  function TableBody({ className, ...rest }, ref) {
    return <tbody ref={ref} className={cx("divide-y divide-border", className)} {...rest} />;
  },
);

export const TableRow = React.forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement> & { selected?: boolean }>(
  function TableRow({ className, selected, ...rest }, ref) {
    return (
      <tr
        ref={ref}
        aria-selected={selected}
        className={cx("bg-surface hover:bg-surface-2 aria-selected:bg-primary-soft", className)}
        {...rest}
      />
    );
  },
);

export type TableHeaderCellProps = React.ThHTMLAttributes<HTMLTableCellElement> & {
  /** Present when the column can be sorted; `none` means sortable but not sorted. */
  sort?: "ascending" | "descending" | "none";
  onSort?: () => void;
};

export const TableHeaderCell = React.forwardRef<HTMLTableCellElement, TableHeaderCellProps>(function TableHeaderCell(
  { sort, onSort, className, children, scope = "col", ...rest },
  ref,
) {
  const arrow = sort === "ascending" ? "▲" : sort === "descending" ? "▼" : "↕";
  return (
    <th
      ref={ref}
      scope={scope}
      aria-sort={sort}
      className={cx("px-3 py-2 font-semibold", className)}
      {...rest}
    >
      {onSort ? (
        <button
          type="button"
          onClick={onSort}
          className={cx("inline-flex items-center gap-1 rounded uppercase tracking-wide", focusRing)}
        >
          {children}
          <span aria-hidden="true">{arrow}</span>
        </button>
      ) : (
        children
      )}
    </th>
  );
});

export const TableCell = React.forwardRef<HTMLTableCellElement, React.TdHTMLAttributes<HTMLTableCellElement>>(
  function TableCell({ className, ...rest }, ref) {
    return <td ref={ref} className={cx("px-3 py-2 align-top text-fg", className)} {...rest} />;
  },
);

/* ------------------------------------------------------------------- Tabs */

type TabsContextValue = {
  value: string;
  select: (value: string) => void;
  baseId: string;
  orientation: "horizontal" | "vertical";
};

const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabs(): TabsContextValue {
  const ctx = React.useContext(TabsContext);
  if (!ctx) throw new Error("Tabs parts must be used inside <Tabs>");
  return ctx;
}

export type TabsProps = {
  value?: string;
  defaultValue: string;
  onValueChange?: (value: string) => void;
  orientation?: "horizontal" | "vertical";
  className?: string;
  children: React.ReactNode;
};

export function Tabs({ value, defaultValue, onValueChange, orientation = "horizontal", className, children }: TabsProps) {
  const [current, select] = useControllable(value, defaultValue, onValueChange);
  const baseId = React.useId();
  const ctx = React.useMemo(() => ({ value: current, select, baseId, orientation }), [current, select, baseId, orientation]);
  return (
    <TabsContext.Provider value={ctx}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

/** Arrow keys, Home and End move between tabs; the active tab is the only tab stop. */
export const TabList = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { label: string }>(
  function TabList({ label, className, children, ...rest }, ref) {
    const { orientation } = useTabs();
    const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
      const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]:not([disabled])'));
      const index = tabs.indexOf(document.activeElement as HTMLElement);
      if (index < 0) return;
      const next = orientation === "horizontal" ? "ArrowRight" : "ArrowDown";
      const prev = orientation === "horizontal" ? "ArrowLeft" : "ArrowUp";
      let target: HTMLElement | undefined;
      if (event.key === next) target = tabs[(index + 1) % tabs.length];
      else if (event.key === prev) target = tabs[(index - 1 + tabs.length) % tabs.length];
      else if (event.key === "Home") target = tabs[0];
      else if (event.key === "End") target = tabs[tabs.length - 1];
      if (target) {
        event.preventDefault();
        target.focus();
        target.click();
      }
    };
    return (
      <div
        ref={ref}
        // jsx-a11y wants a focusable element for an interactive role with a key
        // handler. Here the handler is delegation: the ARIA tabs pattern puts a
        // roving `tabIndex` on the tabs and never makes the list itself a tab
        // stop, so making this focusable would add a stop that does nothing.
        // eslint-disable-next-line jsx-a11y/interactive-supports-focus
        role="tablist"
        aria-label={label}
        aria-orientation={orientation}
        onKeyDown={onKeyDown}
        className={cx(
          orientation === "horizontal" ? "flex gap-1 border-b border-border" : "flex flex-col gap-1",
          className,
        )}
        {...rest}
      >
        {children}
      </div>
    );
  },
);

export const Tab = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string }>(
  function Tab({ value, className, children, ...rest }, ref) {
    const { value: current, select, baseId } = useTabs();
    const active = current === value;
    return (
      <button
        ref={ref}
        type="button"
        role="tab"
        id={`${baseId}-tab-${value}`}
        aria-selected={active}
        aria-controls={`${baseId}-panel-${value}`}
        tabIndex={active ? 0 : -1}
        onClick={() => select(value)}
        className={cx(
          "-mb-px rounded-t-md border-b-2 px-3 py-2 text-sm font-medium",
          active ? "border-primary text-primary" : "border-transparent text-fg-muted hover:text-fg",
          focusRing,
          className,
        )}
        {...rest}
      >
        {children}
      </button>
    );
  },
);

export const TabPanel = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { value: string }>(
  function TabPanel({ value, className, children, ...rest }, ref) {
    const { value: current, baseId } = useTabs();
    const active = current === value;
    return (
      <div
        ref={ref}
        role="tabpanel"
        id={`${baseId}-panel-${value}`}
        aria-labelledby={`${baseId}-tab-${value}`}
        hidden={!active}
        tabIndex={0}
        className={cx("pt-4", focusRing, className)}
        {...rest}
      >
        {active ? children : null}
      </div>
    );
  },
);

/* ------------------------------------------------------------- Pagination */

export type PaginationProps = {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
  /** Accessible name of the navigation landmark. */
  label?: string;
  previousLabel?: string;
  nextLabel?: string;
  /** Builds the per-page button name, e.g. (n) => `Page ${n}`. */
  pageLabel?: (page: number) => string;
  className?: string;
};

/** Page numbers to show: first, last, and a window around the current page, with gaps as `null`. */
export function pageWindow(page: number, pageCount: number, radius = 1): Array<number | null> {
  const wanted = new Set<number>([1, pageCount]);
  for (let n = page - radius; n <= page + radius; n += 1) if (n >= 1 && n <= pageCount) wanted.add(n);
  const sorted = Array.from(wanted).sort((a, b) => a - b);
  const out: Array<number | null> = [];
  sorted.forEach((n, i) => {
    if (i > 0 && n - sorted[i - 1] > 1) out.push(null);
    out.push(n);
  });
  return out;
}

export function Pagination({
  page,
  pageCount,
  onPageChange,
  label = "Pagination",
  previousLabel = "Previous",
  nextLabel = "Next",
  pageLabel = (n) => `Page ${n}`,
  className,
}: PaginationProps) {
  if (pageCount <= 1) return null;
  const step = "inline-flex min-h-9 min-w-9 items-center justify-center rounded-md border border-border px-3 text-sm";
  return (
    <nav aria-label={label} className={cx("flex flex-wrap items-center gap-1", className)}>
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className={cx(step, "bg-surface hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50", focusRing)}
      >
        {previousLabel}
      </button>
      {pageWindow(page, pageCount).map((n, i) =>
        n === null ? (
          <span key={`gap-${i}`} aria-hidden="true" className="px-1 text-fg-muted">
            {"…"}
          </span>
        ) : (
          <button
            key={n}
            type="button"
            onClick={() => onPageChange(n)}
            aria-label={pageLabel(n)}
            aria-current={n === page ? "page" : undefined}
            className={cx(
              step,
              n === page ? "border-primary bg-primary text-primary-on" : "bg-surface hover:bg-surface-2",
              focusRing,
            )}
          >
            {n}
          </button>
        ),
      )}
      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= pageCount}
        className={cx(step, "bg-surface hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50", focusRing)}
      >
        {nextLabel}
      </button>
    </nav>
  );
}
