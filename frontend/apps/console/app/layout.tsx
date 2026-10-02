import type { Metadata } from "next";
import { ConsoleNav } from "@/components/ConsoleNav";
import { RoleSwitcherBar } from "@/components/RoleSwitcherBar";
import { StaffSessionProvider } from "@/components/StaffSessionProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Clarity Console",
  description: "Desk, insights, studio, and admin",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <StaffSessionProvider>
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-950">
            Staff console · synthetic cases. Roles are <strong>picked, not
            proven</strong> - production federates HUTCH SSO + MFA; permission
            checks below are the real ones.
          </div>
          <ConsoleNav />
          <main className="mx-auto max-w-6xl px-4 py-6 pb-44">{children}</main>
          <RoleSwitcherBar />
        </StaffSessionProvider>
      </body>
    </html>
  );
}
