import type { Metadata } from "next";
import "@fontsource-variable/google-sans/wght.css";
import "@fontsource-variable/google-sans-flex/wght.css";
import "@clarity/ui/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Verify receipt · Hutch Clarity",
  description: "Public trust receipt verification",
  appleWebApp: { capable: true, title: "Clarity" },
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
        <div className="mx-auto min-h-screen max-w-md px-4 py-10">
          {children}
        </div>
      </body>
    </html>
  );
}
