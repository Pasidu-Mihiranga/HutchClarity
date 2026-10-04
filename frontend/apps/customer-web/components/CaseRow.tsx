import Link from "next/link";

/**
 * One case in the customer's list (E4).
 *
 * The props changed with the data. This used to take `cause` and `amount`,
 * which `/v1/me/app` does not carry for a case: it sends `headline` (the first
 * line of the decision's own rationale) and `outcome`. The old props were
 * filled from two invented rows, so nothing noticed the mismatch. A row now
 * renders what the case actually has, and says "Looking into this" when the
 * case has not been decided yet rather than inventing a cause for it.
 */
type CaseRowProps = {
  id: string;
  caseNo: string;
  state: string;
  open: boolean;
  /** The decision's first rationale line. Null until the case is decided. */
  headline: string | null;
  outcome: string | null;
  openedAt: string;
};

export function CaseRow({
  id,
  caseNo,
  state,
  open,
  headline,
  outcome,
  openedAt,
}: CaseRowProps) {
  const when = new Date(openedAt);
  const date = Number.isNaN(when.getTime())
    ? openedAt
    : when.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

  return (
    <Link
      href={`/case/${id}`}
      className="h-option"
      style={{ borderRadius: 16, textDecoration: "none", color: "inherit" }}
    >
      <span
        style={{
          width: 40,
          height: 40,
          borderRadius: 12,
          background: "var(--orange-soft)",
          color: "var(--orange-ink)",
          display: "grid",
          placeItems: "center",
          flexShrink: 0,
          fontSize: 18,
          fontWeight: 700,
        }}
        aria-hidden="true"
      >
        {open ? "!" : "✓"}
      </span>
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
          <span
            style={{
              display: "inline-flex",
              padding: "3px 8px",
              borderRadius: 999,
              fontSize: 11,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: ".04em",
              background: open
                ? "rgb(var(--c-primary-soft))"
                : "rgb(var(--c-success-soft))",
              color: open ? "rgb(var(--c-primary))" : "rgb(var(--c-success))",
            }}
          >
            {state.replace(/_/g, " ")}
          </span>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>{date}</span>
        </span>
        <span
          style={{
            display: "block",
            fontWeight: 650,
            fontSize: 15,
            color: "var(--ink)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {headline ?? "Looking into this"}
        </span>
        <span
          style={{
            display: "block",
            margin: "2px 0 0",
            fontSize: 13,
            color: "var(--muted)",
          }}
        >
          {caseNo}
          {outcome ? ` · ${outcome.replace(/_/g, " ").toLowerCase()}` : ""}
        </span>
      </span>
      <span
        style={{ color: "rgb(var(--c-fg-subtle))", fontSize: 20, flexShrink: 0 }}
        aria-hidden="true"
      >
        ›
      </span>
    </Link>
  );
}
