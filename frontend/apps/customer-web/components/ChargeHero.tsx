type ChargeHeroProps = {
  amount: string;
  currency?: string;
  cause: string;
  state: string;
  isPlaceholder?: boolean;
};

export function ChargeHero({
  amount,
  currency = "LKR",
  cause,
  state,
  isPlaceholder,
}: ChargeHeroProps) {
  const isOpen = state === "OPEN";

  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid var(--line)",
        borderTop: `3px solid var(--orange)`,
        borderRadius: "var(--radius)",
        padding: 18,
        boxShadow: "var(--shadow)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "4px 10px",
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: ".04em",
            textTransform: "uppercase",
            background: isOpen ? "#fff1eb" : "#dcfce7",
            color: isOpen ? "#c2410c" : "#14532d",
          }}
        >
          {state}
        </span>
        {isPlaceholder && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              padding: "4px 10px",
              borderRadius: 999,
              fontSize: 12,
              fontWeight: 700,
              background: "#f4f4f5",
              color: "#52525b",
            }}
          >
            Placeholder
          </span>
        )}
      </div>
      <p
        style={{
          margin: 0,
          fontSize: 30,
          fontWeight: 800,
          letterSpacing: "-.03em",
          color: "var(--ink)",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {currency} {amount}
      </p>
      <p style={{ margin: "4px 0 0", fontSize: 14, color: "var(--muted)" }}>{cause}</p>
    </div>
  );
}
