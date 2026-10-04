"use client";

import { usePathname } from "next/navigation";
import { AppHeader } from "./AppHeader";
import { BottomNav } from "./BottomNav";

const BACK_ROUTES: Record<string, { href: string; label: string; title: string }> = {
  "/case":    { href: "/cases", label: "Cases", title: "Case" },
  "/receipt": { href: "/cases", label: "Cases", title: "Trust Receipt" },
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";
  const isImmersive = pathname === "/clarity";
  const backRoute = Object.entries(BACK_ROUTES).find(([prefix]) => pathname.startsWith(prefix))?.[1];

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
