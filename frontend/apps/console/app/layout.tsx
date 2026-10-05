import type { Metadata } from "next";
// Self-hosted (OFL-1.1): no font download at build time or at runtime, which
// keeps the build offline-safe and the page inside `font-src 'self'`.
import "@fontsource-variable/google-sans/wght.css";
import "@fontsource-variable/google-sans-flex/wght.css";
import { ConsoleShell } from "@/components/ConsoleShell";
import { StaffSessionProvider } from "@/components/StaffSessionProvider";
import "@clarity/ui/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Clarity Desk",
  description: "Staff desk for synthetic cases: evidence, approval, and Trust Receipts.",
  appleWebApp: { capable: true, title: "Clarity Desk" },
  // Unique public path (+ version query) so browsers drop a stale /favicon.ico tab icon.
  icons: {
    icon: [
      {
        url: "/clarity-mark-favicon.png?v=orange-c-1",
        type: "image/png",
        sizes: "48x48",
      },
      { url: "/icon-192.png?v=orange-c-1", type: "image/png", sizes: "192x192" },
    ],
    apple: [
      {
        url: "/apple-touch-icon.png?v=orange-c-1",
        type: "image/png",
        sizes: "180x180",
      },
    ],
    shortcut: "/clarity-mark-favicon.png?v=orange-c-1",
  },
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
          <ConsoleShell>{children}</ConsoleShell>
        </StaffSessionProvider>
      </body>
    </html>
  );
}
