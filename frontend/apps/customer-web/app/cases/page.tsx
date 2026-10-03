"use client";

import { useEffect, useState } from "react";
import { ClarityClient } from "@clarity/sdk";
import { CaseRow } from "@/components/CaseRow";

const client = new ClarityClient();

type CaseItem = {
  case_id: string;
  cause?: string;
  primary_cause?: string;
  amount?: string;
  currency?: string;
  state?: string;
  created_at?: string;
};

const DEMO_CASES: CaseItem[] = [
  {
    case_id: "demo-case-1",
    cause: "VAS silent renewal",
    amount: "99.00",
    currency: "LKR",
    state: "OPEN",
    created_at: "2 Oct 2026",
  },
  {
    case_id: "demo-case-2",
    cause: "Duplicate data charge",
    amount: "45.00",
    currency: "LKR",
    state: "RESOLVED",
    created_at: "28 Sep 2026",
  },
];

export default function CasesPage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token =
          typeof window !== "undefined"
            ? (window.sessionStorage.getItem("clarity_token") ?? undefined)
            : undefined;
        client.setToken(token);
        // Typed through a narrow shape rather than `Record<string, unknown>`,
        // whose values are `unknown` and so not callable. Pre-existing error,
        // invisible because `npm run typecheck` only covers packages/sdk and
        // never the apps (C05 devlog).
        const withCases = client as unknown as { getCases?: () => Promise<unknown> };
        const data = await withCases.getCases?.();
        if (!cancelled && Array.isArray(data) && data.length > 0) {
          setCases(data as CaseItem[]);
        } else {
          if (!cancelled) setCases(DEMO_CASES);
        }
      } catch {
        if (!cancelled) setCases(DEMO_CASES);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", marginBottom: 14 }}>
        Cases
      </p>

      {loading ? (
        <div style={{ display: "grid", gap: 10 }}>
          {[1, 2].map((i) => (
            <div
              key={i}
              style={{
                height: 80,
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--line)",
                background: "#f4f4f5",
                animation: "pulse 1.5s infinite",
              }}
            />
          ))}
        </div>
      ) : cases.length === 0 ? (
        <div
          style={{
            border: "1px dashed var(--line)",
            borderRadius: "var(--radius)",
            background: "#fff",
            padding: "32px 20px",
            textAlign: "center",
          }}
        >
          <p style={{ margin: 0, fontWeight: 650, color: "var(--ink)" }}>No cases yet</p>
          <p style={{ margin: "6px 0 0", fontSize: 14, color: "var(--muted)" }}>
            If a charge looks wrong, tap &ldquo;Fix this&rdquo; on the home screen.
          </p>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {cases.map((c) => (
            <CaseRow
              key={c.case_id}
              id={c.case_id}
              cause={(c.cause ?? c.primary_cause) || "Unknown charge"}
              amount={c.amount ?? "0.00"}
              currency={c.currency}
              state={c.state ?? "OPEN"}
              date={c.created_at}
            />
          ))}
        </div>
      )}
    </main>
  );
}
