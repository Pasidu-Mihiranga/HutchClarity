import * as React from "react";
import { cx, focusRing } from "./utils";

/* ---------------------------------------------------------------- Spinner */

export type SpinnerProps = React.HTMLAttributes<HTMLSpanElement> & {
  /** Accessible name. Pass the translated word for "Loading". */
  label?: string;
  size?: "sm" | "md" | "lg";
};

const spinnerSize = { sm: "h-4 w-4 border-2", md: "h-6 w-6 border-2", lg: "h-10 w-10 border-[3px]" };

export const Spinner = React.forwardRef<HTMLSpanElement, SpinnerProps>(function Spinner(
  { label = "Loading", size = "md", className, ...rest },
  ref,
) {
  return (
    <span
      ref={ref}
      role="status"
      aria-label={label}
      className={cx(
        "ui-anim-spin inline-block rounded-full border-border-strong border-t-primary",
        spinnerSize[size],
        className,
      )}
      {...rest}
    />
  );
});

/* ----------------------------------------------------------------- Button */

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  /** Disables the button and shows a spinner. Sets `aria-busy`. */
  loading?: boolean;
  /** Fully rounded, for customer-facing surfaces. */
  pill?: boolean;
};

const buttonVariants: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary: "bg-primary text-primary-on hover:bg-primary-hover",
  secondary: "bg-surface-2 text-fg hover:bg-border",
  ghost: "bg-transparent text-fg hover:bg-surface-2",
  danger: "bg-danger text-primary-on hover:opacity-90",
};

const buttonSizes: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "min-h-8 px-3 text-xs",
  md: "min-h-10 px-4 text-sm",
  lg: "min-h-12 px-6 text-base",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, pill = false, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-2 font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        pill ? "rounded-full" : "rounded-md",
        buttonVariants[variant],
        buttonSizes[size],
        focusRing,
        className,
      )}
      {...rest}
    >
      {loading ? <Spinner size="sm" label="" aria-hidden="true" role="presentation" /> : null}
      {children}
    </button>
  );
});

/* ------------------------------------------------------------------- Card */

export type CardProps = React.HTMLAttributes<HTMLDivElement>;

export const Card = React.forwardRef<HTMLDivElement, CardProps>(function Card(
  { className, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cx("rounded-lg border border-border bg-surface p-4 text-fg shadow-1", className)}
      {...rest}
    />
  );
});

/* ------------------------------------------------------------------ Badge */

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warning" | "danger" | "info" | "brand";
};

const badgeTones: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "bg-surface-2 text-fg-muted",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  info: "bg-info-soft text-info",
  brand: "bg-primary-soft text-primary",
};

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(function Badge(
  { tone = "neutral", className, ...rest },
  ref,
) {
  return (
    <span
      ref={ref}
      className={cx("inline-flex items-center rounded px-2 py-0.5 text-xs font-medium", badgeTones[tone], className)}
      {...rest}
    />
  );
});

/* ------------------------------------------------------------------ Field */

const fieldBase =
  "w-full rounded-md border border-border-strong bg-surface px-3 py-2 text-sm text-fg placeholder:text-fg-subtle focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/30 disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-danger";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean };

export const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, ...rest },
  ref,
) {
  return <input ref={ref} aria-invalid={invalid || undefined} className={cx(fieldBase, className)} {...rest} />;
});

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean };

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid, rows = 3, ...rest },
  ref,
) {
  return (
    <textarea ref={ref} rows={rows} aria-invalid={invalid || undefined} className={cx(fieldBase, className)} {...rest} />
  );
});

/** A styled native `<select>`: keeps the platform picker, keyboard and screen-reader behaviour. */
export type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean };

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, invalid, children, ...rest },
  ref,
) {
  return (
    <select ref={ref} aria-invalid={invalid || undefined} className={cx(fieldBase, "pr-8", className)} {...rest}>
      {children}
    </select>
  );
});

/** Label, control, hint and error wired together with the right ids. */
export type FieldProps = {
  label: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  className?: string;
  children: (control: {
    id: string;
    "aria-describedby"?: string;
    invalid: boolean;
  }) => React.ReactNode;
};

export function Field({ label, hint, error, className, children }: FieldProps) {
  const id = React.useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cx("grid gap-1", className)}>
      <label htmlFor={id} className="text-sm font-medium text-fg">
        {label}
      </label>
      {children({ id, "aria-describedby": describedBy, invalid: Boolean(error) })}
      {hint ? (
        <p id={hintId} className="text-xs text-fg-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/* ---------------------------------------------------------------- Skeleton */

export type SkeletonProps = React.HTMLAttributes<HTMLDivElement>;

/** Placeholder block. Decorative: hidden from assistive tech, the page announces loading itself. */
export const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(function Skeleton(
  { className, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      aria-hidden="true"
      className={cx("ui-anim-pulse rounded-md bg-surface-2", className)}
      {...rest}
    />
  );
});
