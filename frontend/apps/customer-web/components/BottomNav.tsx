"use client";

import { usePathname } from "next/navigation";

type Tab = {
  id: string;
  href: string;
  label: string;
  icon: React.ReactNode;
};

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" width={22} height={22} stroke="currentColor" fill="none" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5z" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" width={22} height={22} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 17.5 3.5 20V6.5A2.5 2.5 0 0 1 6 4h12a2.5 2.5 0 0 1 2.5 2.5v8A2.5 2.5 0 0 1 18 17H6z" />
    </svg>
  );
}

function ReceiptsIcon() {
  return (
    <svg viewBox="0 0 24 24" width={22} height={22} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M7 3.5h10a1 1 0 0 1 1 1V21l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2L6 21V4.5a1 1 0 0 1 1-1z" />
      <path d="M9 8h6M9 12h6" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" width={22} height={22} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2H4.5L6 16z" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg viewBox="0 0 24 24" width={22} height={22} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9c.3.6.9 1 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </svg>
  );
}

const TABS: Tab[] = [
  { id: "home", href: "/", label: "Home", icon: <HomeIcon /> },
  { id: "alerts", href: "/#home-alerts", label: "Alerts", icon: <BellIcon /> },
  { id: "support", href: "/clarity", label: "Support", icon: <ChatIcon /> },
  { id: "receipts", href: "/cases", label: "Receipts", icon: <ReceiptsIcon /> },
  { id: "settings", href: "/account", label: "Settings", icon: <SettingsIcon /> },
];

export function BottomNav({ compact }: { compact: boolean }) {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div
      style={{
        flexShrink: 0,
        position: "sticky",
        bottom: 0,
        zIndex: 80,
        padding: "8px 12px calc(10px + env(safe-area-inset-bottom, 0px))",
        background: "rgb(var(--c-surface))",
      }}
    >
      <nav
        aria-label="Hutch"
        style={{
          display: "flex",
          alignItems: "stretch",
          gap: compact ? 0 : 2,
          width: compact ? "fit-content" : "min(440px, 100%)",
          margin: "0 auto",
          padding: compact ? 4 : 6,
          borderRadius: 999,
          background: "rgb(var(--c-surface-2))",
          border: "1px solid var(--line)",
          boxShadow: "0 8px 24px rgb(0 0 0 / 0.18)",
        }}
      >
        {TABS.map(({ id, href, label, icon }) => {
          const active = isActive(href);
          return (
            <a
              key={id}
              href={href}
              aria-current={active ? "page" : undefined}
              style={{
                display: "flex",
                flex: compact ? "none" : 1,
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
                minWidth: compact ? 40 : 52,
                minHeight: compact ? 44 : 52,
                padding: compact ? 8 : "6px 8px",
                borderRadius: 999,
                textDecoration: "none",
                color: active ? "var(--orange-ink)" : "var(--muted)",
                background: active ? "rgb(var(--c-primary-soft))" : "transparent",
                fontSize: 11,
                fontWeight: 700,
              }}
            >
              {icon}
              <span
                style={
                  compact
                    ? {
                        position: "absolute",
                        width: 1,
                        height: 1,
                        overflow: "hidden",
                        clip: "rect(0 0 0 0)",
                      }
                    : { lineHeight: 1.1 }
                }
              >
                {label}
              </span>
            </a>
          );
        })}
      </nav>
    </div>
  );
}
