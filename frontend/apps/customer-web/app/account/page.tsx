"use client";

import { useRouter } from "next/navigation";
import { useLanguage } from "@/components/LanguageProvider";
import { supportedLangs, type Lang } from "@clarity/i18n";

const LANG_LABELS: Record<Lang, string> = {
  en: "English",
  si: "සිංහල",
  ta: "தமிழ்",
};

const MENU_ROWS = [
  { label: "Notifications", sub: "All alerts" },
  { label: "Network status", sub: "No outages in your area" },
  { label: "Terms",          sub: null },
  { label: "Privacy",        sub: null },
];

export default function AccountPage() {
  const { lang, setLang } = useLanguage();
  const router = useRouter();

  function signOut() {
    try { window.sessionStorage.removeItem("clarity_token"); } catch {}
    router.push("/login");
  }

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>

      {/* Profile */}
      <div className="h-card" style={{ marginBottom: 14 }}>
        <p style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", margin: "0 0 4px" }}>
          Account
        </p>
        <p style={{ margin: 0, fontWeight: 700, fontSize: 18, letterSpacing: "-.02em" }}>07X XXXX XX89</p>
        <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--muted)" }}>Demo customer</p>
      </div>

      {/* Language */}
      <div className="h-card" style={{ marginBottom: 14 }}>
        <p style={{ fontSize: 13, fontWeight: 650, color: "var(--muted)", margin: "0 0 10px" }}>Language</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {supportedLangs.map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              style={{
                borderRadius: 999,
                padding: "8px 16px",
                fontSize: 14,
                fontWeight: 650,
                fontFamily: "inherit",
                cursor: "pointer",
                border: l === lang ? "2px solid var(--orange)" : "1px solid var(--line)",
                background: l === lang ? "var(--orange-soft)" : "#fff",
                color: l === lang ? "var(--orange-ink)" : "var(--ink)",
              }}
            >
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
      </div>

      {/* Menu rows */}
      <div style={{ display: "grid", gap: 8, marginBottom: 14 }}>
        {MENU_ROWS.map(({ label, sub }) => (
          <button
            key={label}
            style={{
              width: "100%",
              textAlign: "left",
              padding: "14px 16px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--line)",
              background: "#fff",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontFamily: "inherit",
              cursor: "pointer",
              boxShadow: "0 1px 2px rgba(0,0,0,.03)",
            }}
          >
            <span>
              <span style={{ display: "block", fontWeight: 650, fontSize: 15 }}>{label}</span>
              {sub && <span style={{ display: "block", fontSize: 13, color: "var(--muted)", marginTop: 1 }}>{sub}</span>}
            </span>
            <span style={{ color: "#a1a1aa", fontSize: 18 }} aria-hidden="true">›</span>
          </button>
        ))}
      </div>

      {/* Sign out */}
      <button
        onClick={signOut}
        className="h-btn h-btn-ghost"
        style={{ width: "100%", marginBottom: 14 }}
      >
        Sign out
      </button>

      {/* Simulated notice - I16 */}
      <div
        style={{
          border: "1px solid #fdd5c0",
          borderRadius: "var(--radius-sm)",
          background: "var(--orange-soft)",
          padding: "10px 14px",
          fontSize: 13,
          color: "var(--orange-ink)",
        }}
      >
        <strong>SIMULATED</strong> - This is a demo session. No real HUTCH account is connected.
      </div>
    </main>
  );
}
