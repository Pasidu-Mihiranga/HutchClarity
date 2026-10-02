type ValidityHeroProps = {
  valid: boolean;
};

export function ValidityHero({ valid }: ValidityHeroProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "32px 16px",
        background: "#fff",
        border: "1px solid var(--line)",
        borderTop: `3px solid ${valid ? "#047857" : "#b91c1c"}`,
        borderRadius: "var(--radius)",
        boxShadow: "var(--shadow)",
      }}
    >
      <span style={{ fontSize: 48, color: valid ? "#047857" : "#b91c1c" }} aria-hidden="true">
        {valid ? "✓" : "✕"}
      </span>
      <p
        style={{
          margin: 0,
          fontSize: 20,
          fontWeight: 800,
          color: valid ? "#047857" : "#b91c1c",
          letterSpacing: "-.01em",
        }}
      >
        {valid ? "Valid" : "Invalid"}
      </p>
      <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
        {valid ? "Signature and chain verified" : "Verification failed"}
      </p>
    </div>
  );
}
