import type { ReactNode } from "react";

/**
 * Workspace page title block shared by every console tab.
 *
 * One size and one typeface for the topic name, so Audit / Admin / Desk / …
 * read as the same product surface regardless of role.
 */
export function PageHeader({
  title,
  description,
  meta,
  actions,
}: {
  title: string;
  description?: ReactNode;
  /** Chip or count beside the title (e.g. "3 switches"). */
  meta?: ReactNode;
  /** Right-side controls aligned with the title row. */
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">
            {title}
          </h1>
          {meta}
        </div>
        {description ? (
          <p className="text-sm text-mute">{description}</p>
        ) : null}
      </div>
      {actions}
    </div>
  );
}
