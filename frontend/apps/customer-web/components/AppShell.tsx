"use client";

import { useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { AppHeader } from "./AppHeader";
import { BottomNav } from "./BottomNav";

/**
 * Which screens get a back link, and where back goes.
 *
 * The prefixes are ordered and `/case/` carries its trailing slash on purpose:
 * `startsWith("/case")` also matched `/cases`, so the cases list rendered a
 * "back to Cases" link to itself, titled "Case". The list is a destination,
 * not a detail screen, so it gets a back link to Home like the other two
 * screens E4 added.
 */
const BACK_ROUTES: Array<[string, { href: string; label: string; title: string }]> = [
  ["/case/", { href: "/cases", label: "Cases", title: "Case" }],
  ["/cases", { href: "/", label: "Home", title: "Cases" }],
  ["/receipt", { href: "/cases", label: "Cases", title: "Trust Receipt" }],
  ["/packages", { href: "/", label: "Home", title: "Packages" }],
  ["/usage", { href: "/", label: "Home", title: "Usage" }],
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const scroller = useRef<HTMLDivElement>(null);
  const [compact, setCompact] = useState(false);
  const isLogin = pathname === "/login";
  const isImmersive = pathname === "/clarity";
  const backRoute = BACK_ROUTES.find(([prefix]) => pathname.startsWith(prefix))?.[1];

  // Clarity is fully immersive - it renders its own header + composer.
  // Sign-in is the same kind of screen: the mockup is the whole page, so the
  // app header, the bottom nav and the 720px column would crop it.
  if (isImmersive || isLogin) return <>{children}</>;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        left: 0,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        background: "rgb(var(--c-surface))",
      }}
    >
      <AppHeader
        backHref={backRoute?.href}
        backLabel={backRoute?.label}
        title={backRoute?.title}
      />
      <div
        ref={scroller}
        onScroll={(event) => setCompact(event.currentTarget.scrollTop > 24)}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          WebkitOverflowScrolling: "touch",
        }}
      >
        <div style={{ maxWidth: 720, margin: "0 auto", padding: "0 16px 16px" }}>
          {children}
        </div>
      </div>
      <BottomNav compact={compact} />
    </div>
  );
}
