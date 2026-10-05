"use client";

import type { ReactNode } from "react";
import { ConsoleNav } from "./ConsoleNav";
import { DeskLogin } from "./DeskLogin";
import { RoleSwitcherBar } from "./RoleSwitcherBar";
import { SessionGate } from "./SessionGate";
import {
  SidebarCollapseProvider,
  useSidebarCollapse,
} from "./SidebarCollapseContext";
import { useStaffSession } from "./StaffSessionProvider";

/**
 * The console shell (E2).
 *
 * Signed out, the shell is the desk sign-in and nothing else. Until a session
 * exists there is no identity to authorise, so the page does not offer the
 * sections.
 *
 * Signed in, the shell is an orange sidebar rail and a light workspace. The
 * rail can sit expanded (labels) or half-collapsed (icons only). The active
 * tab is open on the right so it joins the workspace.
 *
 * **The skip link is first in the DOM** once someone is signed in.
 * **`<main>` is the skip target.** **One landmark each:** aside / main.
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
    <SidebarCollapseProvider>
      <SignedInShell>{children}</SignedInShell>
    </SidebarCollapseProvider>
  );
}

function SignedInShell({ children }: { children: ReactNode }) {
  const { collapsed } = useSidebarCollapse();

  return (
    <div className="flex min-h-screen bg-bg">
      <a
        href="#console-main"
        className="sr-only rounded-md focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-fg focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-bg"
      >
        Skip to main content
      </a>
      <aside
        className={`sticky top-0 flex h-screen shrink-0 flex-col text-white transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
          collapsed ? "w-[80px]" : "w-[260px]"
        }`}
        style={{ backgroundColor: "var(--console-rail)" }}
        data-collapsed={collapsed ? "true" : "false"}
      >
        <ConsoleNav />
        <RoleSwitcherBar />
      </aside>
      <main
        id="console-main"
        tabIndex={-1}
        className="min-w-0 flex-1 bg-bg px-6 py-6 focus:outline-none"
      >
        <SessionGate>{children}</SessionGate>
      </main>
    </div>
  );
}
