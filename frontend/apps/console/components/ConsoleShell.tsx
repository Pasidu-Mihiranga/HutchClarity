"use client";

import type { ReactNode } from "react";
import { ConsoleNav } from "./ConsoleNav";
import { DeskLogin } from "./DeskLogin";
import { RoleSwitcherBar } from "./RoleSwitcherBar";
import { SessionGate } from "./SessionGate";
import { useStaffSession } from "./StaffSessionProvider";

/**
 * The console shell (E2).
 *
 * Signed out, the shell is the desk sign-in and nothing else. The section
 * map used to render before there was an identity, which offered links the
 * next page then refused. Until a session exists there is no identity to
 * authorise, so the page does not offer the sections.
 *
 * Signed in, the shell is a sidebar and a workspace. The sidebar is the
 * section list and the person who is signed in. The page fills the rest.
 *
 * **The skip link is first in the DOM** once someone is signed in. The
 * sidebar carries the navigation, so a keyboard user landing on a page would
 * otherwise tab through every section link before reaching the thing they
 * came for. It is visually hidden until focused.
 *
 * **`<main>` is the skip target and takes focus.** `tabIndex={-1}` makes it
 * focusable programmatically but keeps it out of the tab order, so following
 * the skip link moves the actual focus ring rather than only scrolling.
 *
 * **One landmark each.** The sidebar is `complementary` and `main` is `main`.
 */
export function ConsoleShell({ children }: { children: ReactNode }) {
  const { session, restoring } = useStaffSession();

  if (restoring) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <p role="status" className="text-sm text-mute">
          Restoring staff session…
        </p>
      </main>
    );
  }

  if (!session) return <DeskLogin />;

  return (
    <div className="flex min-h-screen bg-bg">
      <a
        href="#console-main"
        className="sr-only rounded-md focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-fg focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-bg"
      >
        Skip to main content
      </a>
      <aside className="sticky top-0 flex h-screen w-[248px] shrink-0 flex-col border-r border-line bg-surface">
        <ConsoleNav />
        <RoleSwitcherBar />
      </aside>
      <main
        id="console-main"
        tabIndex={-1}
        className="min-w-0 flex-1 px-6 py-6 focus:outline-none"
      >
        <SessionGate>{children}</SessionGate>
      </main>
    </div>
  );
}
