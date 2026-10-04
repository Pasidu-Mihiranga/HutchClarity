"use client";

import Link from "next/link";
import { EmptyState, ErrorState, Skeleton } from "@clarity/ui";
import { CaseRow } from "@/components/CaseRow";
import { useMe } from "@/lib/useMe";

/**
 * The customer's cases (E4).
 *
 * This page called `client.getCases()`, a method the SDK does not have. The
 * call threw on every render, the `catch` swallowed it, and the page rendered
 * two cases written into the source: "VAS silent renewal, LKR 99.00, OPEN" and
 * "Duplicate data charge, LKR 45.00, RESOLVED". A customer with no cases saw
 * two; a customer with three saw the same two. E5's typed client is what makes
 * that impossible to write again, and this is the page it was hiding in.
 *
 * It now reads the cases out of `/v1/me/app`. An empty list is an empty state,
 * and a failed load is an error state with a retry; neither is filled in.
 */
export default function CasesPage() {
  const { app, loading, error, refresh } = useMe();

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <h1
        style={{
          fontSize: 11,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: ".08em",
          color: "var(--muted)",
          marginBottom: 14,
        }}
      >
        Cases
      </h1>

      {loading ? (
        <div style={{ display: "grid", gap: 10 }}>
          <p role="status" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
            Loading your cases
          </p>
          {[1, 2].map((i) => (
            <Skeleton key={i} style={{ height: 80, borderRadius: "var(--radius-card-sm)" }} />
          ))}
        </div>
      ) : !app ? (
        <ErrorState
          title="We could not load your cases"
          message={error ?? "Please try again in a moment."}
          onRetry={refresh}
        />
      ) : app.cases.length === 0 ? (
        <div className="h-card" style={{ borderStyle: "dashed" }}>
          <EmptyState
            title="No cases yet"
            description="If a charge looks wrong, ask Clarity about it and it will open one for you."
            action={
              <Link href="/clarity" className="h-btn h-btn-primary" style={{ textDecoration: "none" }}>
                Ask Clarity
              </Link>
            }
          />
        </div>
      ) : (
        <ul style={{ display: "grid", gap: 10, listStyle: "none", margin: 0, padding: 0 }}>
          {app.cases.map((row) => (
            <li key={row.case_id}>
              <CaseRow
                id={row.case_id}
                caseNo={row.case_no}
                state={row.state}
                open={row.open}
                headline={row.headline}
                outcome={row.outcome}
                openedAt={row.opened_at}
              />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
