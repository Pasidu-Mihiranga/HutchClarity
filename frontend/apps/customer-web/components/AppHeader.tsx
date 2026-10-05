"use client";

import Link from "next/link";
import { useLanguage } from "./LanguageProvider";
import { supportedLangs, type Lang } from "@clarity/i18n";

const LANG_LABELS: Record<Lang, string> = { en: "EN", si: "සිං", ta: "தமிழ்" };

type Props = {
  backHref?: string;
  backLabel?: string;
  title?: string;
};

export function AppHeader({ backHref, backLabel = "Back", title }: Props) {
  const { lang, setLang } = useLanguage();

  return (
    <header
      style={{
        position: "sticky",
        top: "env(safe-area-inset-top, 0px)",
        zIndex: 30,
        background: "rgb(var(--c-surface))",
        borderBottom: "1px solid var(--line)",
        padding: "12px 16px",
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
              marginRight: 4,
            }}
          >
            <span aria-hidden="true">←</span>
            {backLabel}
          </Link>
        ) : null}

        {/* Agent identity */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
          {!backHref && (
            <span
              aria-hidden="true"
              style={{
                width: 36,
                height: 36,
                borderRadius: 12,
                background: "var(--orange)",
                color: "rgb(var(--c-on-primary))",
                fontWeight: 800,
                fontSize: 15,
                display: "grid",
                placeItems: "center",
                flexShrink: 0,
                boxShadow: "0 4px 12px rgba(242,98,38,.35)",
              }}
            >
              H
            </span>
          )}
          <div style={{ minWidth: 0 }}>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 16, letterSpacing: "-.02em" }}>
              {backHref ? title ?? "Hutch" : "Hutch"}
            </div>
            {!backHref && (
              <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.2 }}>
                Clarity
              </div>
            )}
          </div>
        </div>

        {/* Language switcher */}
        <div
          style={{
            display: "flex",
            gap: 2,
            background: "rgb(var(--c-surface-2))",
            borderRadius: 10,
            padding: 2,
            marginLeft: "auto",
          }}
          role="group"
          aria-label="Language"
        >
          {supportedLangs.map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setLang(l)}
              style={{
                border: 0,
                background: l === lang ? "rgb(var(--c-surface))" : "transparent",
                color: l === lang ? "var(--orange-ink)" : "rgb(var(--c-fg-muted))",
                boxShadow: l === lang ? "0 1px 2px rgba(0,0,0,.06)" : "none",
                fontSize: 11,
                fontWeight: 700,
                padding: "6px 8px",
                borderRadius: 8,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
