"use client";

import { useState } from "react";
import { EmptyState, ErrorState, Skeleton, Tab, TabList, TabPanel, Tabs } from "@clarity/ui";
import type { ActivityBucket } from "@clarity/sdk";
import { useMe } from "@/lib/useMe";

/**
 * Usage and activity (E4).
 *
 * Home's "Usage" quick action pointed at `"#"`. `/v1/me/app` already carried
 * both halves of this screen and nothing read them: `usage` (data, voice, SMS
 * against the pack's cap) and `activity`, the account's own ledger with a
 * balance before and after every line.
 *
 * **Why the balance column matters.** "Why did my balance change?" is the
 * question this whole product exists to answer, and the ledger answers the
 * easy half of it directly: the customer can see the charge and what the
 * balance was on either side of it. Clarity's job starts where that is not
 * enough, which is why each charge links into the chat rather than this page
 * trying to explain it.
 *
 * Every figure is the row's own. Nothing here is summed or derived by the
 * page: a total this page computed could disagree with the one the decision
 * engine used, and then two screens would be telling a customer different
 * things about the same money (I3, I16).
 */

const BUCKETS: Array<{ id: ActivityBucket | "all"; label: string }> = [
  { id: "all", label: "Everything" },
  { id: "charges", label: "Charges" },
  { id: "reloads", label: "Reloads" },
  { id: "packages", label: "Packs" },
  { id: "refunds", label: "Refunds" },
  { id: "usage", label: "Usage" },
];

function when(value: string): string {
  const at = new Date(value);
  if (Number.isNaN(at.getTime())) return value;
  return at.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function UsagePage() {
  const { app, loading, error, refresh } = useMe();
  const [bucket, setBucket] = useState<string>("all");

  if (loading) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <p role="status" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
          Loading your usage
        </p>
        <div style={{ display: "grid", gap: 12 }}>
          <Skeleton style={{ height: 96, borderRadius: "var(--radius)" }} />
          <Skeleton style={{ height: 220, borderRadius: "var(--radius)" }} />
        </div>
      </main>
    );
  }

  if (!app) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <ErrorState
          title="We could not load your usage"
          message={error ?? "Please try again in a moment."}
          onRetry={refresh}
        />
      </main>
    );
  }

  const rows =
    bucket === "all" ? app.activity : app.activity.filter((row) => row.bucket === bucket);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em", margin: "0 0 18px" }}>
        Usage
      </h1>

      <section aria-labelledby="usage-totals" className="h-card" style={{ marginBottom: 18 }}>
        <h2 id="usage-totals" className="sr-only">
          This period
        </h2>
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 12,
            margin: 0,
          }}
        >
          <div>
            <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Data</dt>
            <dd style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 700 }}>
              {app.usage.data_used_gb ?? "-"}
              {app.usage.data_cap_gb ? (
                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--muted)" }}>
                  {" "}
                  / {app.usage.data_cap_gb} GB
                </span>
              ) : null}
            </dd>
          </div>
          <div>
            <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Voice</dt>
            <dd style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 700 }}>
              {app.usage.voice_minutes}
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--muted)" }}> min</span>
            </dd>
          </div>
          <div>
            <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>SMS</dt>
            <dd style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 700 }}>{app.usage.sms}</dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="usage-activity">
        <h2
          id="usage-activity"
          style={{
            fontSize: 11,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: ".08em",
            color: "var(--muted)",
            margin: "0 0 10px",
          }}
        >
          Activity
        </h2>
        <Tabs defaultValue="all" value={bucket} onValueChange={setBucket}>
          <TabList label="Filter activity">
            {BUCKETS.map((entry) => (
              <Tab key={entry.id} value={entry.id}>
                {entry.label}
              </Tab>
            ))}
          </TabList>
          {BUCKETS.map((entry) => (
            <TabPanel key={entry.id} value={entry.id}>
              {rows.length === 0 ? (
                <EmptyState
                  title="Nothing here yet"
                  description="Lines appear as the account is used."
                />
              ) : (
                <ul style={{ display: "grid", gap: 8, listStyle: "none", margin: 0, padding: 0 }}>
                  {rows.map((row) => (
                    <li
                      key={row.id}
                      style={{
                        border: "1px solid var(--line)",
                        borderRadius: "var(--radius-card-sm)",
                        background: "rgb(var(--c-surface))",
                        padding: "12px 14px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 12,
                          alignItems: "baseline",
                        }}
                      >
                        <p style={{ margin: 0, fontWeight: 650, fontSize: 15 }}>{row.detail}</p>
                        {row.amount_lkr ? (
                          <p
                            style={{
                              margin: 0,
                              fontWeight: 700,
                              whiteSpace: "nowrap",
                              fontVariantNumeric: "tabular-nums",
                            }}
                          >
                            LKR {row.amount_lkr}
                          </p>
                        ) : null}
                      </div>
                      <p style={{ margin: "3px 0 0", fontSize: 12, color: "var(--muted)" }}>
                        {when(row.at)} · {row.source} · {row.status}
                      </p>
                      {row.balance_before && row.balance_after ? (
                        <p style={{ margin: "3px 0 0", fontSize: 12, color: "var(--muted)" }}>
                          Balance {row.balance_before} → {row.balance_after}
                        </p>
                      ) : null}
                      {row.bucket === "charges" ? (
                        <a
                          href="/clarity"
                          style={{
                            display: "inline-block",
                            marginTop: 6,
                            fontSize: 13,
                            fontWeight: 650,
                            color: "var(--orange-ink)",
                          }}
                        >
                          Ask why this was charged →
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </TabPanel>
          ))}
        </Tabs>
      </section>
    </main>
  );
}
