import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import { ConsoleNav } from "@/components/ConsoleNav";
import { RoleSwitcherBar } from "@/components/RoleSwitcherBar";
import { StaffSessionProvider } from "@/components/StaffSessionProvider";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const display = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
});

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
    <html lang="en" className={`${inter.variable} ${display.variable}`}>
      <body className={inter.className}>
        <StaffSessionProvider>
          <header className="sticky top-0 z-40 border-b border-line bg-white/90 backdrop-blur">
            <ConsoleNav />
            <RoleSwitcherBar />
          </header>
          <main className="mx-auto max-w-[1240px] px-4 py-8 sm:px-6">{children}</main>
        </StaffSessionProvider>
      </body>
    </html>
  );
}
