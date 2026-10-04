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

/**
 * The console shell (E2).
 *
 * Three things here are accessibility structure rather than decoration.
 *
 * **The skip link is first in the DOM.** The header carries the whole
 * navigation and the sign-in bar, so a keyboard user landing on a page would
 * otherwise tab through every section link and three form fields before
 * reaching the thing they came for. It is visually hidden until focused, which
 * is the only way it stays useful without becoming clutter.
 *
 * **`<main>` is the skip target and takes focus.** `tabIndex={-1}` makes it
 * focusable programmatically but keeps it out of the tab order, so following
 * the skip link moves the actual focus ring rather than only scrolling: a
 * screen reader then reads from the heading, not from wherever focus was left.
 *
 * **One landmark each.** `header` as a direct child of `body` is the `banner`
 * landmark and `main` is `main`, so a screen reader's landmark list has the two
 * entries it should and no nesting that would hide one inside the other.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <StaffSessionProvider>
          <a
            href="#console-main"
            className="sr-only rounded-md focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-fg focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-bg"
          >
            Skip to main content
          </a>
          <header className="sticky top-0 z-40 border-b border-line bg-surface/90 backdrop-blur">
            <ConsoleNav />
            <RoleSwitcherBar />
          </header>
          <main
            id="console-main"
            tabIndex={-1}
            className="mx-auto max-w-[1240px] px-4 py-8 focus:outline-none sm:px-6"
          >
            <SessionGate>{children}</SessionGate>
          </main>
        </StaffSessionProvider>
      </body>
    </html>
  );
}
