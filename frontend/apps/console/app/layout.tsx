import type { Metadata } from "next";
import { ConsoleNav } from "@/components/ConsoleNav";
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
        <ConsoleNav />
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
