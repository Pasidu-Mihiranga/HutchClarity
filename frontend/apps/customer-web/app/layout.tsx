import type { Metadata, Viewport } from "next";
import { LanguageProvider } from "@/components/LanguageProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hutch Clarity",
  description: "Why did my balance change?",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "Clarity",
  },
};

export const viewport: Viewport = {
  themeColor: "#0369a1",
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
          <div className="mx-auto min-h-screen max-w-lg px-4 py-6">
            {children}
          </div>
        </LanguageProvider>
      </body>
    </html>
  );
}
