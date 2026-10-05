"use client";

import { Button } from "@clarity/ui";
import { useSidebarCollapse } from "./SidebarCollapseContext";
import { useStaffSession } from "./StaffSessionProvider";

/**
 * The signed-in person, at the foot of the orange sidebar rail (E2).
 * Half-collapsed shows the initials and a compact sign-out control.
 */
function initials(subject: string) {
  const parts = subject.split(/[:\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
}

export function RoleSwitcherBar() {
  const { stepUpWithProvider, methods, signOut, session, stepUp, busy, error } = useStaffSession();
  const { collapsed } = useSidebarCollapse();

  if (!session) return null;

  const roles = session.roles.map((role) => role.replace(/_/g, " ")).join(", ");

  if (collapsed) {
    return (
      <section aria-label="Staff session" className="mt-auto border-t border-white/25 px-2 py-4">
        <div className="flex flex-col items-center gap-2">
          <span
            aria-hidden="true"
            className="grid h-9 w-9 place-items-center rounded-full bg-white/20 text-[11px] font-semibold text-white"
            title={`${session.subject} · ${roles}`}
          >
            {initials(session.subject)}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={signOut}
            disabled={busy}
            title="Sign out"
            aria-label="Sign out"
            className="h-9 w-9 rounded-full border border-white/70 p-0 text-white hover:border-white hover:bg-white/15 hover:text-white"
          >
            <SignOutIcon />
          </Button>
        </div>
        {error ? (
          <p role="alert" className="mt-2 rounded-full bg-white/20 px-2 py-1 text-center text-[10px] text-white">
            {error}
          </p>
        ) : null}
      </section>
    );
  }

  return (
    <section aria-label="Staff session" className="mt-auto border-t border-white/25 px-5 py-5">
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden="true"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white/20 text-[11px] font-semibold text-white"
        >
          {initials(session.subject)}
        </span>
        <p className="min-w-0 flex-1 text-xs leading-4">
          <span className="block truncate font-semibold text-white">{session.subject}</span>
          <span className="block truncate text-white/80">{roles}</span>
        </p>
        <Button
          variant="ghost"
          size="sm"
          onClick={signOut}
          disabled={busy}
          className="rounded-full border border-white/70 px-3.5 text-white hover:border-white hover:bg-white/15 hover:text-white"
        >
          Sign out
        </Button>
      </div>
      {methods?.provider && !stepUp ? (
        <Button
          variant="ghost"
          size="sm"
          className="mt-2 rounded-full text-white hover:bg-white/20 hover:text-white"
          onClick={() => void stepUpWithProvider()}
          disabled={busy}
        >
          Re-authenticate
        </Button>
      ) : null}
      {error ? (
        <p role="alert" className="mt-2 rounded-full bg-white/20 px-3 py-1.5 text-xs text-white">
          {error}
        </p>
      ) : null}
    </section>
  );
}

function SignOutIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path d="M10 4H6.5A1.5 1.5 0 0 0 5 5.5v13A1.5 1.5 0 0 0 6.5 20H10" strokeLinecap="round" />
      <path d="M14 16l4-4-4-4M10 12h8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
