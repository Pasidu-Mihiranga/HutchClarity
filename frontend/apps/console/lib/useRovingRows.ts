"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";

/**
 * Row-level keyboard navigation for a long table (E2).
 *
 * **Why the audit trail needs this.** The trail explorer renders fifty records,
 * each with a Verify button. Tabbing through it means fifty tab stops to reach
 * the last row, and nothing tells a keyboard user which row they are on: focus
 * lands on a button whose only context is the cells beside it, which a screen
 * reader does not read on focus.
 *
 * **The pattern.** One tab stop for the whole table (a roving `tabIndex`), then
 * Up and Down to move a row at a time, Home and End to jump to the ends, and
 * Enter or Space to act on the focused row. This is the ARIA grid pattern for
 * row navigation, so the table is given `role="grid"` by the caller and each
 * row is focusable; without the grid role, focusable `<tr>` elements are a
 * structure a screen reader has no way to interpret.
 *
 * **Why focus is moved rather than only tracked.** Setting `tabIndex` alone
 * changes where the next Tab goes and leaves the focus ring behind, so the
 * visible position and the real one drift apart. `focus()` on the row keeps
 * them together, which is also what makes the row's cells announce.
 *
 * The hook owns no data. It takes a count and hands back the props a row
 * needs, so a table that re-sorts or re-filters only has to pass the new count.
 */
export function useRovingRows(count: number, onActivate?: (index: number) => void) {
  const [active, setActive] = useState(0);
  const rows = useRef<Array<HTMLTableRowElement | null>>([]);
  const activate = useRef(onActivate);
  activate.current = onActivate;

  // A filter that returns fewer records must not leave the active row past the
  // end: the next arrow press would otherwise move focus to nothing.
  useEffect(() => {
    setActive((current) => (count === 0 ? 0 : Math.min(current, count - 1)));
  }, [count]);

  const focusRow = useCallback((index: number) => {
    setActive(index);
    rows.current[index]?.focus();
  }, []);

  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTableRowElement>, index: number) => {
      // Let a control inside the row keep its own keys: Enter on the Verify
      // button is the button's, not the grid's.
      if (event.target !== event.currentTarget) return;
      if (count === 0) return;

      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          focusRow(Math.min(index + 1, count - 1));
          break;
        case "ArrowUp":
          event.preventDefault();
          focusRow(Math.max(index - 1, 0));
          break;
        case "Home":
          event.preventDefault();
          focusRow(0);
          break;
        case "End":
          event.preventDefault();
          focusRow(count - 1);
          break;
        case "Enter":
        case " ":
          event.preventDefault();
          activate.current?.(index);
          break;
        default:
          break;
      }
    },
    [count, focusRow],
  );

  const rowProps = useCallback(
    (index: number) => ({
      ref: (node: HTMLTableRowElement | null) => {
        rows.current[index] = node;
      },
      tabIndex: index === active ? 0 : -1,
      onKeyDown: (event: KeyboardEvent<HTMLTableRowElement>) => onKeyDown(event, index),
      onFocus: () => setActive(index),
    }),
    [active, onKeyDown],
  );

  return { active, rowProps, focusRow };
}
