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
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5z"/>
    </svg>
  );
}

function ClarityIcon() {
  return (
    <svg viewBox="0 0 24 24" width={22} height={22} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3a7 7 0 0 0-7 7c0 2.5 1.2 4.2 2.4 5.4.6.6 1.1 1.3 1.3 2.1h6.6c.2-.8.7-1.5 1.3-2.1C17.8 14.2 19 12.5 19 10a7 7 0 0 0-7-7z"/>
      <path d="M9 21h6"/>
    </svg>
  );
}

function AccountIcon() {
  return (
    <svg viewBox="0 0 24 24" width={22} height={22} stroke="currentColor" fill="none" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="8" r="4"/>
      <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
    </svg>
  );
}

const TABS: Tab[] = [
  { id: "home",    href: "/",         label: "Home",    icon: <HomeIcon /> },
  { id: "clarity", href: "/clarity",  label: "Clarity", icon: <ClarityIcon /> },
  { id: "account", href: "/account",  label: "More",    icon: <AccountIcon /> },
];

export function BottomNav() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <nav
      style={{
        position: "fixed",
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 40,
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        background: "#fff",
        borderTop: "1px solid var(--line)",
        padding: "6px 8px env(safe-area-inset-bottom, 0px)",
        minHeight: "var(--nav-h)",
        boxShadow: "0 -4px 20px rgba(0,0,0,.04)",
      }}
      aria-label="Hutch"
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
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 3,
              minHeight: 48,
              padding: "6px 4px",
              textDecoration: "none",
              color: active ? "var(--orange-ink)" : "var(--muted)",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: ".01em",
              borderRadius: 10,
              position: "relative",
            }}
          >
            {active && (
              <span
                aria-hidden="true"
                style={{
                  position: "absolute",
                  top: 0,
                  left: "22%",
                  right: "22%",
                  height: 3,
                  borderRadius: "0 0 3px 3px",
                  background: "var(--orange)",
                }}
              />
            )}
            {icon}
            {label}
          </a>
        );
      })}
    </nav>
  );
}
