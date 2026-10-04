import * as React from "react";
import { Button } from "./primitives";
import { cx } from "./utils";

/* ------------------------------------------------------------------ Alert */

export type AlertProps = Omit<React.HTMLAttributes<HTMLDivElement>, "title"> & {
  tone?: "info" | "success" | "warning" | "danger";
  title?: React.ReactNode;
  onDismiss?: () => void;
  dismissLabel?: string;
};

const alertTones: Record<NonNullable<AlertProps["tone"]>, string> = {
  info: "border-info/40 bg-info-soft text-fg",
  success: "border-success/40 bg-success-soft text-fg",
  warning: "border-warning/40 bg-warning-soft text-fg",
  danger: "border-danger/40 bg-danger-soft text-fg",
};

const alertIcons: Record<NonNullable<AlertProps["tone"]>, string> = {
  info: "i",
  success: "✓",
  warning: "!",
  danger: "×",
};

/**
 * Inline status message. `danger` and `warning` use `role="alert"` (announced
 * at once); `info` and `success` use `role="status"` (announced politely).
 */
export const Alert = React.forwardRef<HTMLDivElement, AlertProps>(function Alert(
  { tone = "info", title, onDismiss, dismissLabel = "Dismiss", className, children, ...rest },
  ref,
) {
  const urgent = tone === "danger" || tone === "warning";
  return (
    <div
      ref={ref}
      role={urgent ? "alert" : "status"}
      className={cx("flex items-start gap-3 rounded-md border p-3 text-sm", alertTones[tone], className)}
      {...rest}
    >
      <span
        aria-hidden="true"
        className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface text-xs font-bold"
      >
        {alertIcons[tone]}
      </span>
      <div className="min-w-0 flex-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className={title ? "mt-0.5 text-fg-muted" : undefined}>{children}</div> : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label={dismissLabel}
          className="rounded px-1 text-lg leading-none text-fg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <span aria-hidden="true">{"×"}</span>
        </button>
      ) : null}
    </div>
  );
});

/* ------------------------------------------------------------- EmptyState */

export type EmptyStateProps = Omit<React.HTMLAttributes<HTMLDivElement>, "title"> & {
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  icon?: React.ReactNode;
};

/** Nothing to show yet. Says why and, where there is one, what to do next. */
export const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(function EmptyState(
  { title, description, action, icon, className, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cx("flex flex-col items-center gap-2 px-4 py-10 text-center", className)}
      {...rest}
    >
      {icon ? (
        <div aria-hidden="true" className="text-3xl text-fg-subtle">
          {icon}
        </div>
      ) : null}
      <p className="text-base font-semibold text-fg">{title}</p>
      {description ? <p className="max-w-md text-sm text-fg-muted">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
});

/* ------------------------------------------------------------- ErrorState */

export type ErrorStateProps = Omit<React.HTMLAttributes<HTMLDivElement>, "title"> & {
  title?: React.ReactNode;
  /** What went wrong, in words a person can act on. Never a raw stack or status line. */
  message?: React.ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
};

/** A failed load. Always announced, and offers a retry when the caller can. */
export const ErrorState = React.forwardRef<HTMLDivElement, ErrorStateProps>(function ErrorState(
  { title = "Something went wrong", message, onRetry, retryLabel = "Try again", className, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      role="alert"
      className={cx("flex flex-col items-center gap-2 px-4 py-10 text-center", className)}
      {...rest}
    >
      <p className="text-base font-semibold text-danger">{title}</p>
      {message ? <p className="max-w-md text-sm text-fg-muted">{message}</p> : null}
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry} className="mt-2">
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
});
