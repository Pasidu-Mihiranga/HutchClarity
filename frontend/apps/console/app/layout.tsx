import type { Metadata } from "next";
// Self-hosted (OFL-1.1): no font download at build time or at runtime, which
// keeps the build offline-safe and the page inside `font-src 'self'`.
import "@fontsource-variable/inter";
import "@fontsource-variable/space-grotesk";
import { ConsoleNav } from "@/components/ConsoleNav";
import { RoleSwitcherBar } from "@/components/RoleSwitcherBar";
import { SessionGate } from "@/components/SessionGate";
import { StaffSessionProvider } from "@/components/StaffSessionProvider";
import "@clarity/ui/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Clarity Desk",
  description: "Staff desk for synthetic cases: evidence, approval, and Trust Receipts.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="light">
      <body>
        <StaffSessionProvider>
          <header className="sticky top-0 z-40 border-b border-line bg-surface/90 backdrop-blur-xl backdrop-saturate-150">
            <ConsoleNav />
            <RoleSwitcherBar />
          </header>
          <main className="mx-auto max-w-[1240px] px-4 py-8 sm:px-6 sm:py-12">
            <SessionGate>{children}</SessionGate>
          </main>
        </StaffSessionProvider>
      </body>
    </html>
  );
}
