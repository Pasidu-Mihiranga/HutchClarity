"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CaseRow } from "@/components/CaseRow";
import { SessionEnded, authFetch } from "@/lib/session";

/** One row of the signed-in customer's `GET /v1/me/app` `cases`. */
type CaseItem = {
  case_id: string;
  case_no: string;
  state: string;
  opened_at: string;
  outcome: string | null;
  headline: string | null;
  open: boolean;
};

function opened(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export default function CasesPage() {
  const [cases, setCases] = useState<CaseItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await authFetch("/v1/me/app");
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const body = (await res.json()) as { cases?: CaseItem[] };
      setCases(body.cases ?? []);
    } catch (err) {
      // Show the failure. This page used to fall back to two invented cases,
      // so an outage looked like a customer with history they never had.
      if (!(err instanceof SessionEnded)) setError(err instanceof Error ? err.message : "Could not load your cases");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <h1 style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", margin: "0 0 14px" }}>
        Cases
      </h1>

      {error ? (
        <div role="alert" style={panel}>
          <p style={{ margin: 0, fontWeight: 650 }}>We could not load your cases.</p>
          <p style={{ margin: "6px 0 12px", fontSize: 14, color: "var(--muted)" }}>{error}</p>
          <button type="button" onClick={() => void load()} style={retry}>
            Try again
          </button>
        </div>
      ) : cases === null ? (
        <div style={{ display: "grid", gap: 10 }} aria-busy="true">
          {[1, 2].map((i) => (
            <div key={i} style={{ height: 80, borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", background: "#f4f4f5" }} />
          ))}
        </div>
      ) : cases.length === 0 ? (
        <div style={{ ...panel, border: "1px dashed var(--line)", textAlign: "center" }}>
          <p style={{ margin: 0, fontWeight: 650, color: "var(--ink)" }}>No cases yet</p>
          <p style={{ margin: "6px 0 0", fontSize: 14, color: "var(--muted)" }}>
            If a charge looks wrong, <Link href="/clarity" style={{ textDecoration: "underline", fontWeight: 600 }}>ask Clarity</Link> and it opens one for you.
          </p>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {cases.map((c) => (
            <CaseRow
              key={c.case_id}
              id={c.case_id}
              cause={c.headline ?? `Case ${c.case_no}`}
              state={c.open ? "OPEN" : "RESOLVED"}
              date={opened(c.opened_at)}
            />
          ))}
        </div>
      )}
    </main>
  );
}

const panel: React.CSSProperties = {
  border: "1px solid var(--line)",
  borderRadius: "var(--radius)",
  background: "#fff",
  padding: "24px 20px",
};

const retry: React.CSSProperties = {
  border: 0,
  borderRadius: 999,
  padding: "8px 18px",
  background: "var(--orange-strong)",
  color: "#fff",
  fontWeight: 700,
  cursor: "pointer",
  fontFamily: "inherit",
};
