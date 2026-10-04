"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SessionEnded, authFetch } from "@/lib/session";

/** The signed-in customer's own `GET /v1/me/home`. */
type Home = {
  name: string;
  masked: string;
  balance_lkr: string;
  pack: {
    name: string;
    days_left: number;
    data_gb: string | null;
    used_gb: string | null;
    used_pct: number | null;
  } | null;
  alerts: { kind?: string; text: string }[];
};

/** The amounts `POST /v1/me/reload` accepts. */
const RELOAD_AMOUNTS = ["100", "200", "500", "1000", "2000"];

const QUICK_ACTIONS = [
  { label: "Ask Clarity", href: "/clarity" },
  { label: "My cases", href: "/cases" },
  { label: "Account", href: "/account" },
];

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, init);
  if (!res.ok) {
    const detail = await res
      .json()
      .then((body: { detail?: unknown }) => (typeof body.detail === "string" ? body.detail : undefined))
      .catch(() => undefined);
    throw new Error(detail ?? `Request failed (${res.status})`);
  }
  return (await res.json()) as T;
}

export default function HomePage() {
  const router = useRouter();
  const [home, setHome] = useState<Home | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadOpen, setReloadOpen] = useState(false);
  const [reloading, setReloading] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ text: string; ok: boolean } | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setHome(await call<Home>("/v1/me/home"));
    } catch (err) {
      if (!(err instanceof SessionEnded) && err instanceof Error) setError(err.message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function reload(amount: string) {
    // One request at a time: every amount is disabled while this runs, so a
    // double tap cannot credit twice from this page.
    if (reloading) return;
    setReloading(amount);
    setNotice(null);
    try {
      await call("/v1/me/reload", { method: "POST", body: JSON.stringify({ amount_lkr: amount }) });
      setReloadOpen(false);
      setNotice({ text: `LKR ${amount} added to your balance.`, ok: true });
      await load();
    } catch (err) {
      if (!(err instanceof SessionEnded) && err instanceof Error) setNotice({ text: err.message, ok: false });
    } finally {
      setReloading(null);
    }
  }

  if (error) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "40px 0" }}>
        <div style={card} role="alert">
          <p style={{ margin: "0 0 8px", fontWeight: 700 }}>We could not load your account.</p>
          <p style={{ margin: "0 0 14px", fontSize: 13, color: "var(--muted)" }}>{error}</p>
          <button type="button" onClick={() => void load()} style={primaryButton}>
            Try again
          </button>
        </div>
      </main>
    );
  }

  if (!home) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "40px 0" }} aria-busy="true">
        <p style={{ color: "var(--muted)" }}>Loading your account...</p>
      </main>
    );
  }

  const pack = home.pack;
  const usedPct = pack?.used_pct != null ? Math.min(pack.used_pct, 100) : null;
  const remaining =
    pack?.data_gb != null && pack.used_gb != null
      ? Math.max(0, Number(pack.data_gb) - Number(pack.used_gb)).toFixed(1)
      : null;

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      {/* greeting */}
      <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 2px", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em" }}>
        Hello
      </p>
      <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-.03em", margin: "0 0 2px", color: "var(--ink)" }}>
        {home.name}
      </h1>
      <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 20px", fontFamily: "monospace" }}>
        {home.masked}
      </p>

      {/* balance card */}
      <div style={{ ...card, borderTop: "3px solid var(--orange)", padding: "18px 20px" }}>
        <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 4px", fontWeight: 600 }}>Main balance</p>
        <p style={{ fontSize: 32, fontWeight: 800, letterSpacing: "-.03em", margin: 0, color: "var(--ink)" }}>
          LKR {home.balance_lkr}
        </p>
        <button
          type="button"
          aria-expanded={reloadOpen}
          onClick={() => setReloadOpen((open) => !open)}
          style={{ ...primaryButton, marginTop: 14 }}
        >
          Reload
        </button>
        {reloadOpen ? (
          <div role="group" aria-label="Reload amount" style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
            {RELOAD_AMOUNTS.map((amount) => (
              <button
                key={amount}
                type="button"
                disabled={reloading !== null}
                onClick={() => void reload(amount)}
                style={amountButton}
              >
                {reloading === amount ? "Adding..." : `LKR ${amount}`}
              </button>
            ))}
          </div>
        ) : null}
        {notice ? (
          <p role="status" style={{ margin: "10px 0 0", fontSize: 13, fontWeight: 600, color: notice.ok ? "var(--ok)" : "var(--stop)" }}>
            {notice.text}
          </p>
        ) : null}
      </div>

      {/* pack card */}
      <div style={card}>
        <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 4px", fontWeight: 600 }}>Current pack</p>
        {pack ? (
          <>
            <p style={{ fontSize: 17, fontWeight: 700, margin: "0 0 4px" }}>{pack.name}</p>
            <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 10px" }}>
              {remaining != null ? <>Data remaining: {remaining} GB &nbsp;·&nbsp; </> : null}
              Valid for {pack.days_left} {pack.days_left === 1 ? "day" : "days"}
            </p>
            {usedPct != null ? (
              <div
                role="progressbar"
                aria-label="Fair-use data used"
                aria-valuenow={usedPct}
                aria-valuemin={0}
                aria-valuemax={100}
                style={{ height: 6, borderRadius: 999, background: "#f4f4f5", overflow: "hidden" }}
              >
                <div style={{ height: "100%", width: `${usedPct}%`, background: usedPct >= 80 ? "var(--warn)" : "var(--orange)", borderRadius: 999 }} />
              </div>
            ) : null}
          </>
        ) : (
          <p style={{ fontSize: 15, margin: 0 }}>No active pack. Ask Clarity which pack suits you.</p>
        )}
      </div>

      {/* quick actions */}
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${QUICK_ACTIONS.length}, 1fr)`, gap: 8, marginBottom: 16 }}>
        {QUICK_ACTIONS.map(({ label, href }) => (
          <button key={label} type="button" onClick={() => router.push(href)} style={quickButton}>
            {label}
          </button>
        ))}
      </div>

      {/* Clarity prompt */}
      <button type="button" onClick={() => router.push("/clarity")} style={promptButton}>
        <div>
          <p style={{ margin: 0, fontWeight: 700, fontSize: 15, color: "var(--orange-ink)" }}>
            Something doesn&apos;t look right?
          </p>
          <p style={{ margin: "3px 0 0", fontSize: 13, color: "var(--muted)" }}>
            Ask Clarity why your balance changed
          </p>
        </div>
        <span aria-hidden="true" style={{ fontSize: 20, color: "var(--orange)", marginLeft: 12 }}>→</span>
      </button>

      {/* alerts, from the account itself */}
      {home.alerts.length > 0 ? (
        <>
          <p style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", margin: "0 0 8px" }}>
            For you
          </p>
          {home.alerts.map((alert, i) => (
            <button key={i} type="button" onClick={() => router.push("/clarity")} style={alertButton}>
              <span aria-hidden="true" style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, background: "var(--orange-soft)", display: "grid", placeItems: "center", fontSize: 18 }}>
                !
              </span>
              {alert.text}
            </button>
          ))}
        </>
      ) : null}
    </main>
  );
}

const card: React.CSSProperties = {
  border: "1px solid var(--line)",
  borderRadius: "var(--radius)",
  padding: "16px 20px",
  background: "#fff",
  boxShadow: "var(--shadow)",
  marginBottom: 14,
};

const primaryButton: React.CSSProperties = {
  background: "var(--orange-strong)",
  color: "#fff",
  border: 0,
  borderRadius: 999,
  padding: "10px 24px",
  fontSize: 14,
  fontWeight: 700,
  cursor: "pointer",
  fontFamily: "inherit",
};

const amountButton: React.CSSProperties = {
  border: "1px solid var(--line)",
  background: "var(--orange-soft)",
  color: "var(--orange-ink)",
  borderRadius: 999,
  padding: "8px 14px",
  fontSize: 13,
  fontWeight: 700,
  cursor: "pointer",
  fontFamily: "inherit",
};

const quickButton: React.CSSProperties = {
  border: "1px solid var(--line)",
  background: "#fff",
  borderRadius: "var(--radius-sm)",
  padding: "12px 6px",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--ink)",
  cursor: "pointer",
  fontFamily: "inherit",
  textAlign: "center",
};

const promptButton: React.CSSProperties = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  border: "1.5px solid #fdd5c0",
  borderRadius: "var(--radius)",
  background: "var(--orange-soft)",
  padding: "16px 18px",
  cursor: "pointer",
  fontFamily: "inherit",
  textAlign: "left",
  marginBottom: 14,
};

const alertButton: React.CSSProperties = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  gap: 12,
  border: "1px solid var(--line)",
  borderRadius: "var(--radius-sm)",
  background: "#fff",
  padding: "14px 16px",
  cursor: "pointer",
  fontFamily: "inherit",
  textAlign: "left",
  fontSize: 14,
  color: "var(--ink)",
  marginBottom: 8,
};
