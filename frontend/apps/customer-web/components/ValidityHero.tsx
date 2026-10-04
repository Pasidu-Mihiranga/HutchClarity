type ValidityHeroProps = {
  /** `null` means the check did not complete. It is not a failure and not a pass. */
  valid: boolean | null;
};

const TONES = {
  valid: { accent: "rgb(var(--c-success))", glyph: "✓", title: "Valid", note: "Signature and chain verified" },
  invalid: { accent: "rgb(var(--c-danger))", glyph: "✕", title: "Invalid", note: "Verification failed" },
  unknown: { accent: "rgb(var(--c-warning))", glyph: "?", title: "Not checked", note: "We could not verify this receipt" },
} as const;

export function ValidityHero({ valid }: ValidityHeroProps) {
  const tone = valid === null ? TONES.unknown : valid ? TONES.valid : TONES.invalid;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "32px 16px",
        background: "rgb(var(--c-surface))",
        border: "1px solid var(--line)",
        borderTop: `3px solid ${tone.accent}`,
        borderRadius: "var(--radius)",
        boxShadow: "var(--shadow)",
      }}
    >
      <span style={{ fontSize: 48, color: tone.accent }} aria-hidden="true">
        {tone.glyph}
      </span>
      <p
        style={{
          margin: 0,
          fontSize: 20,
          fontWeight: 800,
          color: tone.accent,
          letterSpacing: "-.01em",
        }}
      >
        {tone.title}
      </p>
      <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>{tone.note}</p>
    </div>
  );
}
