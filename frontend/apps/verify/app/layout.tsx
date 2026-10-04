import type { Metadata } from "next";
import "@clarity/ui/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Verify receipt · Hutch Clarity",
  description: "Public trust receipt verification",
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
