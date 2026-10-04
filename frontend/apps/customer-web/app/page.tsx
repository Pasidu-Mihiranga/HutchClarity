"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, Dialog, ErrorState } from "@clarity/ui";
import { useMe } from "@/lib/useMe";

/**
 * Home, on the customer's real account (E4).
 *
 * This page was a `const DEMO` object: a name, a masked number, a balance, a
 * pack and one alert, all written into the source. The Reload button had an
 * empty `onClick` and three of the five quick actions pointed at `"#"`. It
 * showed a customer a balance no system had produced, which is the one thing
 * a product whose promise is "we explain with evidence" must never do.
 *
 * It now renders `GET /v1/me/app` and nothing else. There is no fallback
 * object: a failed load is an error state, because an invented balance is
 * worse than no balance.
 *
 * **The reload amounts.** The API accepts exactly 100, 200, 500, 1000 and
 * 2000 and answers 422 for anything else, so the sheet offers those five.
 * That list is duplicated here, which is a small but real smell: it belongs
 * in the payload so the server stays the only place it is written. The
 * refusal is surfaced verbatim, so if the server's list changes the customer
 * is told what is allowed rather than left guessing.
 */

const RELOAD_AMOUNTS = ["100", "200", "500", "1000", "2000"];

export default function HomePage() {
  const router = useRouter();
  const { app, loading, error, refresh, act, busy } = useMe();
  const [reloading, setReloading] = useState(false);
  const [amount, setAmount] = useState(RELOAD_AMOUNTS[1]);

  if (loading) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <p role="status" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
          Loading your account
        </p>
        <div style={{ display: "grid", gap: 12 }}>
          {[96, 120, 64].map((height, i) => (
            <div
              key={i}
              aria-hidden="true"
              style={{
                height,
                borderRadius: "var(--radius)",
                background: "rgb(var(--c-surface-2))",
              }}
            />
          ))}
        </div>
      </main>
    );
  }

  if (!app) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <ErrorState
          title="We could not load your account"
          message={error ?? "Please try again in a moment."}
          onRetry={refresh}
        />
      </main>
    );
  }

  const pack = app.pack;
  const usedPct = pack?.used_pct ?? null;
  const remaining =
    pack && pack.data_gb && pack.used_gb
      ? (Number(pack.data_gb) - Number(pack.used_gb)).toFixed(1)
      : null;

  const quickActions: Array<{ label: string; onClick: () => void }> = [
    { label: "Reload", onClick: () => setReloading(true) },
    { label: "Packages", onClick: () => router.push("/packages") },
    { label: "Usage", onClick: () => router.push("/usage") },
    { label: "Cases", onClick: () => router.push("/cases") },
    { label: "Support", onClick: () => router.push("/clarity") },
  ];

  async function submitReload() {
    const ok = await act((api) => api.reload(amount));
    if (ok) setReloading(false);
  }

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <p
        style={{
          fontSize: 12,
          color: "var(--muted)",
          margin: "0 0 2px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: ".06em",
        }}
      >
        Hello
      </p>
      <h1
        style={{
          fontSize: 26,
          fontWeight: 800,
          letterSpacing: "-.03em",
          margin: "0 0 2px",
          color: "var(--ink)",
        }}
      >
        {app.name}
      </h1>
      <p
        style={{
          fontSize: 13,
          color: "var(--muted)",
          margin: "0 0 20px",
          fontFamily: "monospace",
        }}
      >
        {app.masked}
      </p>

      {error ? (
        <div style={{ marginBottom: 14 }}>
          <Alert tone="danger">{error}</Alert>
        </div>
      ) : null}

      <section
        aria-labelledby="home-balance"
        className="h-card h-rule-card"
        style={{ marginBottom: 14 }}
      >
        <h2
          id="home-balance"
          style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 4px", fontWeight: 600 }}
        >
          Main balance
        </h2>
        <p
          style={{
            fontSize: 32,
            fontWeight: 800,
            letterSpacing: "-.03em",
            margin: 0,
            color: "var(--ink)",
          }}
        >
          LKR {app.balance_lkr}
        </p>
        <button
          type="button"
          className="h-btn h-btn-primary"
          style={{ marginTop: 14, borderRadius: 999, padding: "10px 24px" }}
          onClick={() => setReloading(true)}
        >
          Reload
        </button>
      </section>

      {pack ? (
        <section aria-labelledby="home-pack" className="h-card" style={{ marginBottom: 14 }}>
          <h2
            id="home-pack"
            style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 4px", fontWeight: 600 }}
          >
            Current pack
          </h2>
          <p style={{ fontSize: 17, fontWeight: 700, margin: "0 0 4px" }}>{pack.name}</p>
          <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 10px" }}>
            {remaining ? `Data remaining: ${remaining} GB` : "Data allowance not metered"}
            &nbsp;·&nbsp; Valid for {pack.days_left} days
          </p>
          {usedPct !== null ? (
            <>
              <div
                role="progressbar"
                aria-valuenow={Math.min(usedPct, 100)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Data used"
                style={{
                  height: 6,
                  borderRadius: 999,
                  background: "rgb(var(--c-surface-2))",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${Math.min(usedPct, 100)}%`,
                    background: usedPct >= 80 ? "rgb(var(--c-warning))" : "var(--orange)",
                    borderRadius: 999,
                  }}
                />
              </div>
              {/* The restriction wording comes from the pack record, not from a
                  threshold this page decided (I10). */}
              <p style={{ fontSize: 12, color: "var(--muted)", margin: "6px 0 0" }}>
                {pack.restrictions}
              </p>
            </>
          ) : null}
        </section>
      ) : null}

      <nav aria-label="Quick actions" style={{ marginBottom: 16 }}>
        <ul
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 8,
            listStyle: "none",
            margin: 0,
            padding: 0,
          }}
        >
          {quickActions.map(({ label, onClick }) => (
            <li key={label}>
              <button
                type="button"
                onClick={onClick}
                style={{
                  width: "100%",
                  border: "1px solid var(--line)",
                  background: "rgb(var(--c-surface))",
                  borderRadius: "var(--radius-card-sm)",
                  padding: "12px 6px",
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--ink)",
                  cursor: "pointer",
                  fontFamily: "inherit",
                  textAlign: "center",
                }}
              >
                {label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <button
        type="button"
        onClick={() => router.push("/clarity")}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          border: "1.5px solid rgb(var(--c-primary) / 0.3)",
          borderRadius: "var(--radius)",
          background: "var(--orange-soft)",
          padding: "16px 18px",
          cursor: "pointer",
          fontFamily: "inherit",
          textAlign: "left",
          marginBottom: 14,
        }}
      >
        <span>
          <span
            style={{
              display: "block",
              fontWeight: 700,
              fontSize: 15,
              color: "var(--orange-ink)",
            }}
          >
            Something doesn&apos;t look right?
          </span>
          <span style={{ display: "block", fontSize: 13, color: "var(--muted)", marginTop: 3 }}>
            Ask Clarity why your balance changed
          </span>
        </span>
        <span aria-hidden="true" style={{ fontSize: 20, color: "var(--orange)", marginLeft: 12 }}>
          →
        </span>
      </button>

      {app.alerts.length > 0 ? (
        <section aria-labelledby="home-alerts">
          <h2
            id="home-alerts"
            style={{
              fontSize: 12,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: ".08em",
              color: "var(--muted)",
              margin: "0 0 8px",
            }}
          >
            For you
          </h2>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {app.alerts.map((alert, i) => (
              <li key={`${alert.kind}-${i}`}>
                <button
                  type="button"
                  onClick={() => router.push("/clarity")}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    border: "1px solid var(--line)",
                    borderRadius: "var(--radius-card-sm)",
                    background: "rgb(var(--c-surface))",
                    padding: "14px 16px",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    textAlign: "left",
                    fontSize: 14,
                    color: "var(--ink)",
                    marginBottom: 8,
                  }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 10,
                      flexShrink: 0,
                      background: "var(--orange-soft)",
                      display: "grid",
                      placeItems: "center",
                      fontSize: 18,
                    }}
                  >
                    !
                  </span>
                  {alert.text}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <Dialog
        open={reloading}
        onClose={() => setReloading(false)}
        title="Reload your balance"
        description="These are the amounts this account can reload. The reload is simulated."
        footer={
          <>
            <button
              type="button"
              className="h-btn h-btn-ghost"
              onClick={() => setReloading(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="h-btn h-btn-primary"
              data-autofocus
              disabled={busy}
              onClick={() => void submitReload()}
            >
              {busy ? "Reloading…" : `Reload LKR ${amount}`}
            </button>
          </>
        }
      >
        <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
          <legend style={{ fontSize: 13, color: "var(--muted)", marginBottom: 8 }}>Amount</legend>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {RELOAD_AMOUNTS.map((value) => (
              <label
                key={value}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  borderRadius: 999,
                  padding: "8px 14px",
                  fontSize: 14,
                  fontWeight: 650,
                  cursor: "pointer",
                  border: value === amount ? "2px solid var(--orange)" : "1px solid var(--line)",
                  background: value === amount ? "var(--orange-soft)" : "rgb(var(--c-surface))",
                  color: value === amount ? "var(--orange-ink)" : "var(--ink)",
                }}
              >
                <input
                  type="radio"
                  name="reload-amount"
                  value={value}
                  checked={value === amount}
                  onChange={() => setAmount(value)}
                />
                LKR {value}
              </label>
            ))}
          </div>
        </fieldset>
        {error ? (
          <div style={{ marginTop: 12 }}>
            <Alert tone="danger">{error}</Alert>
          </div>
        ) : null}
      </Dialog>
    </main>
  );
}
