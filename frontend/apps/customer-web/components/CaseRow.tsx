import Link from "next/link";

type CaseRowProps = {
  id: string;
  cause: string;
  amount: string;
  currency?: string;
  state: "OPEN" | "RESOLVED" | string;
  date?: string;
};

export function CaseRow({
  id,
  cause,
  amount,
  currency = "LKR",
  state,
  date,
}: CaseRowProps) {
  const isOpen = state === "OPEN";

  return (
    <Link
      href={`/case/${id}`}
      className="h-option"
      style={{ borderRadius: 16, textDecoration: "none", color: "inherit" }}
    >
      <div
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
        {isOpen ? "!" : "✓"}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
          <span
            style={{
              display: "inline-flex",
              padding: "3px 8px",
              borderRadius: 999,
              fontSize: 11,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: ".04em",
              background: isOpen ? "rgb(var(--c-primary-soft))" : "rgb(var(--c-success-soft))",
              color: isOpen ? "rgb(var(--c-primary))" : "rgb(var(--c-success))",
            }}
          >
            {state}
          </span>
          {date && <span style={{ fontSize: 12, color: "var(--muted)" }}>{date}</span>}
        </div>
        <p style={{ margin: 0, fontWeight: 650, fontSize: 15, color: "var(--ink)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {cause}
        </p>
        <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--muted)", fontVariantNumeric: "tabular-nums" }}>
          {currency} {amount}
        </p>
      </div>
      <span style={{ color: "rgb(var(--c-fg-subtle))", fontSize: 20, flexShrink: 0 }} aria-hidden="true">›</span>
    </Link>
  );
}
