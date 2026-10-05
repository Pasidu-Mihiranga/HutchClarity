"use client";

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
  ["/check-message", { href: "/", label: "Home", title: "Check a message" }],
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";
  const isImmersive = pathname === "/clarity";
  const backRoute = BACK_ROUTES.find(([prefix]) => pathname.startsWith(prefix))?.[1];

  // Clarity is fully immersive - it renders its own header + composer
  if (isImmersive) return <>{children}</>;

  return (
    <>
      {!isLogin && (
        <AppHeader
          backHref={backRoute?.href}
          backLabel={backRoute?.label}
          title={backRoute?.title}
        />
      )}
      <div
        style={{
          maxWidth: 720,
          margin: "0 auto",
          padding: isLogin
            ? "0 16px"
            : "0 16px calc(var(--nav-h) + var(--safe-bottom) + 28px)",
        }}
      >
        {children}
      </div>
      {!isLogin && <BottomNav />}
    </>
  );
}
