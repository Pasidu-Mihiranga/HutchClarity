"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { cx, mergeRefs, useFocusTrap, useScrollLock } from "./utils";

/* ----------------------------------------------------------------- Dialog */

export type DialogProps = {
  open: boolean;
  onClose: () => void;
  /** Required: names the dialog for assistive tech. */
  title: React.ReactNode;
  description?: React.ReactNode;
  footer?: React.ReactNode;
  children?: React.ReactNode;
  size?: "sm" | "md" | "lg";
  /** Click on the backdrop closes the dialog. Off for destructive confirmations. */
  dismissOnBackdrop?: boolean;
  closeLabel?: string;
  className?: string;
};

const dialogSize = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-2xl" };

/**
 * Modal dialog. Focus moves in on open, is trapped while open and returns to
 * the opener on close; Escape closes; the page behind does not scroll and is
 * hidden from assistive tech through `aria-modal`.
 */
export const Dialog = React.forwardRef<HTMLDivElement, DialogProps>(function Dialog(
  { open, onClose, title, description, footer, children, size = "md", dismissOnBackdrop = true, closeLabel = "Close", className },
  ref,
) {
  const panel = React.useRef<HTMLDivElement>(null);
  const titleId = React.useId();
  const descId = React.useId();
  useFocusTrap(panel, open, onClose);
  useScrollLock(open);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="ui-anim-fade fixed inset-0 z-50 flex items-end justify-center bg-overlay/50 p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        if (dismissOnBackdrop && event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={mergeRefs(panel, ref)}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={cx(
          "ui-anim-rise flex max-h-[90vh] w-full flex-col rounded-t-xl border border-border bg-surface text-fg shadow-3 focus:outline-none sm:rounded-xl",
          dialogSize[size],
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            {description ? (
              <p id={descId} className="mt-1 text-sm text-fg-muted">
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={closeLabel}
            className="-mr-1 rounded px-2 text-2xl leading-none text-fg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <span aria-hidden="true">{"×"}</span>
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4 text-sm">{children}</div>
        {footer ? <div className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-3">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
});

/* ---------------------------------------------------------------- Tooltip */

export type TooltipProps = {
  content: React.ReactNode;
  /** One focusable element. The tooltip describes it; it is never its only label. */
  children: React.ReactElement;
  side?: "top" | "bottom";
};

/** Shows on hover and keyboard focus, hides on blur, mouse-out and Escape. */
export function Tooltip({ content, children, side = "top" }: TooltipProps) {
  const id = React.useId();
  const [open, setOpen] = React.useState(false);
  const child = React.Children.only(children) as React.ReactElement<Record<string, unknown>>;

  React.useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const chain =
    (name: string, handler: () => void) =>
    (event: unknown) => {
      (child.props[name] as ((e: unknown) => void) | undefined)?.(event);
      handler();
    };

  return (
    <span className="relative inline-flex">
      {React.cloneElement(child, {
        "aria-describedby": open ? id : (child.props["aria-describedby"] as string | undefined),
        onMouseEnter: chain("onMouseEnter", () => setOpen(true)),
        onMouseLeave: chain("onMouseLeave", () => setOpen(false)),
        onFocus: chain("onFocus", () => setOpen(true)),
        onBlur: chain("onBlur", () => setOpen(false)),
      })}
      {open ? (
        <span
          id={id}
          role="tooltip"
          className={cx(
            "pointer-events-none absolute left-1/2 z-50 w-max max-w-xs -translate-x-1/2 rounded-md bg-fg px-2 py-1 text-xs text-bg shadow-2",
            side === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5",
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}

/* ------------------------------------------------------------------ Toast */

export type ToastTone = "info" | "success" | "warning" | "danger";

export type ToastInput = {
  title: React.ReactNode;
  description?: React.ReactNode;
  tone?: ToastTone;
  /** Milliseconds; 0 keeps it until dismissed. Errors default to staying. */
  duration?: number;
};

type ToastItem = ToastInput & { id: number };

type ToastApi = { toast: (input: ToastInput) => number; dismiss: (id: number) => void };

const ToastContext = React.createContext<ToastApi | null>(null);

const toastTones: Record<ToastTone, string> = {
  info: "border-info/50",
  success: "border-success/50",
  warning: "border-warning/50",
  danger: "border-danger/50",
};

export function ToastProvider({
  children,
  dismissLabel = "Dismiss",
  regionLabel = "Notifications",
}: {
  children: React.ReactNode;
  dismissLabel?: string;
  regionLabel?: string;
}) {
  const [items, setItems] = React.useState<ToastItem[]>([]);
  const counter = React.useRef(0);
  const timers = React.useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = React.useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) clearTimeout(timer);
    timers.current.delete(id);
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = React.useCallback(
    (input: ToastInput) => {
      const id = ++counter.current;
      setItems((current) => [...current, { ...input, id }]);
      const duration = input.duration ?? (input.tone === "danger" ? 0 : 5000);
      if (duration > 0) timers.current.set(id, setTimeout(() => dismiss(id), duration));
      return id;
    },
    [dismiss],
  );

  React.useEffect(() => {
    const live = timers.current;
    return () => live.forEach((timer) => clearTimeout(timer));
  }, []);

  const api = React.useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="region"
        aria-label={regionLabel}
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:items-end"
      >
        {items.map((item) => (
          <div
            key={item.id}
            role={item.tone === "danger" ? "alert" : "status"}
            className={cx(
              "ui-anim-rise pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-md border bg-surface p-3 text-sm text-fg shadow-3",
              toastTones[item.tone ?? "info"],
            )}
          >
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{item.title}</p>
              {item.description ? <p className="mt-0.5 text-fg-muted">{item.description}</p> : null}
            </div>
            <button
              type="button"
              onClick={() => dismiss(item.id)}
              aria-label={dismissLabel}
              className="rounded px-1 text-lg leading-none text-fg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              <span aria-hidden="true">{"×"}</span>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const api = React.useContext(ToastContext);
  if (!api) throw new Error("useToast must be used inside <ToastProvider>");
  return api;
}
