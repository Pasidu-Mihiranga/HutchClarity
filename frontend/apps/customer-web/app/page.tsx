"use client";

import { useRouter } from "next/navigation";

const DEMO = {
  name: "Dilani Perera",
  masked: "077 *** 4567",
  balance_lkr: "285.50",
  pack: {
    name: "Anytime 10GB",
    data_gb: 10,
    used_gb: 7.2,
    used_pct: 72,
    days_left: 3,
  },
  alerts: [
    { text: "LKR 49.00 was charged by a VAS subscription yesterday" },
  ],
};

const QUICK_ACTIONS = [
  { label: "Reload",   href: "#"        },
  { label: "Packages", href: "#"        },
  { label: "Usage",    href: "#"        },
  { label: "Cases",    href: "/cases"   },
  { label: "Support",  href: "/clarity" },
];

export default function HomePage() {
  const router = useRouter();
  const a = DEMO;
  const pack = a.pack;
  const usedPct = Math.min(pack.used_pct, 100);
  const remaining = (pack.data_gb - pack.used_gb).toFixed(1);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>

      {/* greeting */}
      <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 2px", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em" }}>
        Hello
      </p>
      <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-.03em", margin: "0 0 2px", color: "var(--ink)" }}>
        {a.name}
      </h1>
      <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 20px", fontFamily: "monospace" }}>
        {a.masked}
      </p>

      {/* balance card */}
      <div style={{
        border: "1px solid var(--line)",
        borderTop: "3px solid var(--orange)",
        borderRadius: "var(--radius)",
        padding: "18px 20px",
        background: "#fff",
        boxShadow: "var(--shadow)",
        marginBottom: 14,
      }}>
        <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 4px", fontWeight: 600 }}>Main balance</p>
        <p style={{ fontSize: 32, fontWeight: 800, letterSpacing: "-.03em", margin: 0, color: "var(--ink)" }}>
          LKR {a.balance_lkr}
        </p>
        <button
          onClick={() => {}}
          style={{
            marginTop: 14,
            background: "var(--orange)",
            color: "#fff",
            border: 0,
            borderRadius: 999,
            padding: "10px 24px",
            fontSize: 14,
            fontWeight: 700,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          Reload
        </button>
      </div>

      {/* pack card */}
      <div style={{
        border: "1px solid var(--line)",
        borderRadius: "var(--radius)",
        padding: "16px 20px",
        background: "#fff",
        boxShadow: "var(--shadow)",
        marginBottom: 14,
      }}>
        <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 4px", fontWeight: 600 }}>Current pack</p>
        <p style={{ fontSize: 17, fontWeight: 700, margin: "0 0 4px" }}>{pack.name}</p>
        <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 10px" }}>
          Data remaining: {remaining} GB &nbsp;·&nbsp; Valid for {pack.days_left} days
        </p>
        <div style={{ height: 6, borderRadius: 999, background: "#f4f4f5", overflow: "hidden" }}>
          <div style={{
            height: "100%",
            width: `${usedPct}%`,
            background: usedPct >= 80 ? "#f59e0b" : "var(--orange)",
            borderRadius: 999,
          }} />
        </div>
        {usedPct >= 80 && (
          <p style={{ fontSize: 12, color: "#f59e0b", margin: "6px 0 0", fontWeight: 600 }}>
            Fair use cap active — speed reduced
          </p>
        )}
      </div>

      {/* quick actions */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(5, 1fr)",
        gap: 8,
        marginBottom: 16,
      }}>
        {QUICK_ACTIONS.map(({ label, href }) => (
          <button
            key={label}
            onClick={() => router.push(href)}
            style={{
              border: "1px solid var(--line)",
              background: "#fff",
              borderRadius: "var(--radius-sm)",
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
        ))}
      </div>

      {/* Clarity prompt */}
      <button
        onClick={() => router.push("/clarity")}
        style={{
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
        }}
      >
        <div>
          <p style={{ margin: 0, fontWeight: 700, fontSize: 15, color: "var(--orange-ink)" }}>
            Something doesn&apos;t look right?
          </p>
          <p style={{ margin: "3px 0 0", fontSize: 13, color: "var(--muted)" }}>
            Ask Clarity why your balance changed
          </p>
        </div>
        <span style={{ fontSize: 20, color: "var(--orange)", marginLeft: 12 }}>→</span>
      </button>

      {/* alerts */}
      {a.alerts.length > 0 && (
        <>
          <p style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", margin: "0 0 8px" }}>
            For you
          </p>
          {a.alerts.map((al, i) => (
            <button
              key={i}
              onClick={() => router.push("/clarity")}
              style={{
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
              }}
            >
              <span style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                background: "var(--orange-soft)", display: "grid", placeItems: "center",
                fontSize: 18,
              }}>!</span>
              {al.text}
            </button>
          ))}
        </>
      )}
    </main>
  );
}
