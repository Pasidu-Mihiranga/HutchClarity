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
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
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
