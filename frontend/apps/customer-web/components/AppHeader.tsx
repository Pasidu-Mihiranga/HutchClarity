"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLanguage } from "./LanguageProvider";
import { supportedLangs, type Lang } from "@clarity/i18n";
import { meClient, useMe } from "@/lib/useMe";

const LANG_LABELS: Record<Lang, string> = {
  en: "English",
  si: "සිංහල",
  ta: "தமிழ்",
};
const LANG_SHORT: Record<Lang, string> = { en: "EN", si: "සිං", ta: "தமிழ்" };

type Props = {
  backHref?: string;
  backLabel?: string;
  title?: string;
};

export function AppHeader({ backHref, backLabel = "Back", title }: Props) {
  const { lang, setLang } = useLanguage();
  const { app, act } = useMe();
  const router = useRouter();
  const [langOpen, setLangOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const langRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!langOpen && !profileOpen) return;
    function onPointer(event: MouseEvent) {
      const target = event.target as Node;
      if (!langRef.current?.contains(target)) setLangOpen(false);
      if (!profileRef.current?.contains(target)) setProfileOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setLangOpen(false);
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [langOpen, profileOpen]);

  async function signOut() {
    setSigningOut(true);
    try {
      await meClient.logout();
    } catch {
      // The next call is refused if the cookie is still there.
    } finally {
      setProfileOpen(false);
      router.push("/login");
    }
  }

  return (
    <header
      style={{
        position: "sticky",
        top: "env(safe-area-inset-top, 0px)",
        zIndex: 50,
        background: "rgb(var(--c-surface))",
        borderBottom: "1px solid var(--line)",
        padding: "10px 16px",
      }}
    >
      <div
        style={{
          maxWidth: 720,
          margin: "0 auto",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        {backHref ? (
          <Link
            href={backHref}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              color: "var(--orange-ink)",
              fontWeight: 600,
              fontSize: 15,
              textDecoration: "none",
            }}
          >
            <span aria-hidden="true">←</span>
            {backLabel}
          </Link>
        ) : (
          <Link href="/" aria-label="Hutch Clarity" style={{ display: "flex", minWidth: 0 }}>
            <img src="/hutch-clarity-logo.png" alt="" className="brand-logo" />
          </Link>
        )}

        {backHref ? (
          <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 16, flex: 1, minWidth: 0 }}>
            {title ?? "Hutch"}
          </div>
        ) : (
          <span style={{ flex: 1 }} />
        )}

        <div ref={langRef} style={{ position: "relative" }}>
          <button
            type="button"
            aria-haspopup="listbox"
            aria-expanded={langOpen}
            aria-label={`Language, ${LANG_LABELS[lang]}`}
            onClick={() => setLangOpen((open) => !open)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              border: "1px solid var(--line)",
              background: "rgb(var(--c-surface-2))",
              color: "rgb(var(--c-fg))",
              font: "inherit",
              fontSize: 13,
              fontWeight: 700,
              borderRadius: 999,
              padding: "8px 12px",
              cursor: "pointer",
            }}
          >
            {LANG_SHORT[lang]}
            <span aria-hidden="true" style={{ fontSize: 10, color: "var(--muted)" }}>▾</span>
          </button>
          {langOpen ? (
            <ul
              role="listbox"
              aria-label="Language"
              style={{
                position: "absolute",
                top: "calc(100% + 8px)",
                right: 0,
                zIndex: 60,
                margin: 0,
                padding: 6,
                listStyle: "none",
                minWidth: 148,
                borderRadius: 16,
                border: "1px solid var(--line)",
                background: "rgb(var(--c-surface))",
                boxShadow: "0 12px 32px rgb(0 0 0 / 0.18)",
              }}
            >
              {supportedLangs.map((code) => {
                const selected = code === lang;
                return (
                  <li key={code} role="option" aria-selected={selected}>
                    <button
                      type="button"
                      onClick={() => {
                        setLang(code);
                        setLangOpen(false);
                      }}
                      style={{
                        width: "100%",
                        textAlign: "left",
                        border: 0,
                        borderRadius: 12,
                        padding: "10px 12px",
                        cursor: "pointer",
                        font: "inherit",
                        fontSize: 14,
                        fontWeight: 700,
                        color: selected ? "var(--orange-ink)" : "rgb(var(--c-fg))",
                        background: selected ? "rgb(var(--c-primary-soft))" : "transparent",
                      }}
                    >
                      {LANG_LABELS[code]}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>

        <div ref={profileRef} style={{ position: "relative" }}>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={profileOpen}
            aria-label="Profile"
            onClick={() => setProfileOpen((open) => !open)}
            style={{
              width: 40,
              height: 40,
              borderRadius: 999,
              display: "grid",
              placeItems: "center",
              color: "rgb(var(--c-fg))",
              background: "rgb(var(--c-surface-2))",
              border: "1px solid var(--line)",
              flexShrink: 0,
              cursor: "pointer",
            }}
          >
            <ProfileIcon />
          </button>
          {profileOpen ? (
            <div
              role="menu"
              style={{
                position: "absolute",
                top: "calc(100% + 8px)",
                right: 0,
                zIndex: 60,
                width: 260,
                padding: 12,
                borderRadius: 16,
                border: "1px solid var(--line)",
                background: "rgb(var(--c-surface))",
                boxShadow: "0 12px 32px rgb(0 0 0 / 0.18)",
              }}
            >
              <p style={{ margin: 0, fontWeight: 800, fontSize: 16 }}>{app?.active_profile?.name ?? app?.name ?? "Signed in"}</p>
              <p style={{ margin: "2px 0 10px", fontSize: 14, fontWeight: 650, letterSpacing: ".02em" }}>
                {displayNumber(app?.active_profile?.msisdn ?? app?.msisdn, app?.masked)}
              </p>
              <div role="group" aria-label="Profiles" style={{ display: "grid", gap: 6, marginBottom: 10 }}>
                <ProfileChoice
                  label="You"
                  detail={displayNumber(app?.msisdn, app?.masked)}
                  selected={!app?.active_profile}
                  onClick={() => void act((api) => api.switchProfile(null))}
                />
                {(app?.family ?? []).map((member) => (
                  <ProfileChoice
                    key={member.msisdn}
                    label={member.name}
                    detail={`${member.role === "child" ? "Child" : "Elder"} · ${displayNumber(member.msisdn)}`}
                    selected={app?.active_profile?.msisdn === member.msisdn}
                    onClick={() => void act((api) => api.switchProfile(member.msisdn))}
                  />
                ))}
              </div>
              <p style={{ margin: "0 0 8px", display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 700 }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "#4A90C2" }}>
                  <MedalIcon />
                  Silver
                </span>
                <span style={{ fontSize: 11, fontWeight: 650, color: "var(--muted)" }}>Simulated</span>
              </p>
              <button
                type="button"
                role="menuitem"
                disabled={signingOut}
                onClick={() => void signOut()}
                style={{
                  width: "100%",
                  borderRadius: 999,
                  border: "1px solid var(--line)",
                  background: "transparent",
                  color: "var(--orange-ink)",
                  font: "inherit",
                  fontWeight: 700,
                  padding: "10px 12px",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                }}
              >
                <SignOutIcon />
                {signingOut ? "Signing out…" : "Sign out"}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function ProfileChoice({
  label,
  detail,
  selected,
  onClick,
}: {
  label: string;
  detail: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="menuitemradio"
      aria-checked={selected}
      onClick={onClick}
      style={{
        textAlign: "left",
        borderRadius: 12,
        border: selected ? "2px solid var(--orange)" : "1px solid var(--line)",
        background: selected ? "var(--orange-soft)" : "transparent",
        padding: "8px 10px",
        cursor: "pointer",
        font: "inherit",
      }}
    >
      <span style={{ display: "block", fontWeight: 800, fontSize: 14 }}>{label}</span>
      <span style={{ display: "block", fontSize: 12, color: "var(--muted)" }}>{detail}</span>
    </button>
  );
}

function displayNumber(msisdn?: string, masked?: string): string {
  if (!msisdn) return masked ?? "";
  const digits = msisdn.replace(/\D/g, "");
  const local = digits.startsWith("94") ? `0${digits.slice(2)}` : digits;
  if (local.length === 10) return `${local.slice(0, 3)} ${local.slice(3, 6)} ${local.slice(6)}`;
  return msisdn;
}

function MedalIcon() {
  return (
    <svg viewBox="0 0 24 24" width={18} height={18} aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <circle cx="12" cy="9" r="4.2" />
      <path d="m8.2 12.2-1.6 7.2 5.4-2.6 5.4 2.6-1.6-7.2" strokeLinejoin="round" />
    </svg>
  );
}

function SignOutIcon() {
  return (
    <svg viewBox="0 0 24 24" width={18} height={18} aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path d="M10 6H6.8A1.8 1.8 0 0 0 5 7.8v8.4A1.8 1.8 0 0 0 6.8 18H10" strokeLinecap="round" />
      <path d="M13 12H21M17.5 8.5 21 12l-3.5 3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ProfileIcon() {
  return (
    <svg viewBox="0 0 24 24" width={20} height={20} fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.5 19.2c1.2-3.2 3.4-4.7 6.5-4.7s5.3 1.5 6.5 4.7" strokeLinecap="round" />
    </svg>
  );
}
