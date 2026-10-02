import * as React from "react";

type ClassProps = { className?: string; children?: React.ReactNode };

function cx(...parts: Array<string | undefined | false>): string {
  return parts.filter(Boolean).join(" ");
}

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
};

export function Button({
  variant = "primary",
  className,
  children,
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50";
  const variants: Record<NonNullable<ButtonProps["variant"]>, string> = {
    primary: "bg-sky-700 text-white hover:bg-sky-800 focus:ring-sky-500",
    secondary:
      "bg-slate-100 text-slate-900 hover:bg-slate-200 focus:ring-slate-400",
    ghost: "bg-transparent text-slate-700 hover:bg-slate-100 focus:ring-slate-300",
  };
  return (
    <button className={cx(base, variants[variant], className)} {...rest}>
      {children}
    </button>
  );
}

export type CardProps = ClassProps & React.HTMLAttributes<HTMLDivElement>;

export function Card({ className, children, ...rest }: CardProps) {
  return (
    <div
      className={cx(
        "rounded-lg border border-slate-200 bg-white p-4 shadow-sm",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export type BadgeProps = ClassProps & {
  tone?: "neutral" | "success" | "warning" | "danger";
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: BadgeProps) {
  const tones: Record<NonNullable<BadgeProps["tone"]>, string> = {
    neutral: "bg-slate-100 text-slate-700",
    success: "bg-emerald-100 text-emerald-800",
    warning: "bg-amber-100 text-amber-900",
    danger: "bg-rose-100 text-rose-800",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center rounded px-2 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...rest }: InputProps) {
  return (
    <input
      className={cx(
        "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200",
        className,
      )}
      {...rest}
    />
  );
}
