import type { Metadata, Viewport } from "next";
import { LanguageProvider } from "@/components/LanguageProvider";
import { AppShell } from "@/components/AppShell";
import "@clarity/ui/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hutch Clarity",
  description: "Why did my balance change?",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "Clarity",
  },
  icons: { apple: "/apple-touch-icon.png" },
  // The standard name for what `appleWebApp.capable` declares for iOS only;
  // Chrome warns when the Apple tag appears without it.
  other: { "mobile-web-app-capable": "yes" },
};

export const viewport: Viewport = {
  themeColor: "#f26226",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <LanguageProvider>
          <AppShell>{children}</AppShell>
        </LanguageProvider>
      </body>
    </html>
  );
}
