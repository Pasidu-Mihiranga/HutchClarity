"use client";

import { Button } from "@clarity/ui";
import { useStaffSession } from "./StaffSessionProvider";

/**
 * The signed-in person, at the foot of the sidebar (E2).
 *
 * The sign-in form lives on `DeskLogin`. This is only the person who is
 * already in: who they are, a re-authentication when the provider can do it,
 * and sign out.
 */
function initials(subject: string) {
  const parts = subject.split(/[:\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
}

export function RoleSwitcherBar() {
  const { stepUpWithProvider, methods, signOut, session, stepUp, busy, error } = useStaffSession();

  if (!session) return null;

  const roles = session.roles.map((role) => role.replace(/_/g, " ")).join(", ");

  return (
    <section aria-label="Staff session" className="mt-auto border-t border-line px-4 py-4">
      <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.14em] text-fg-subtle">
        Synthetic records
      </p>
      <div className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-surface-2 text-[11px] font-semibold text-ink"
        >
          {initials(session.subject)}
        </span>
        <p className="min-w-0 flex-1 text-xs leading-4">
          <span className="block truncate font-medium text-ink">{session.subject}</span>
          <span className="block truncate text-fg-muted">{roles}</span>
        </p>
        <Button variant="ghost" size="sm" onClick={signOut} disabled={busy}>
          Sign out
        </Button>
      </div>
      <p className="mt-2 text-[11px] text-fg-subtle">
        {session.permissions.length} permissions · assurance {session.assurance}
      </p>
      {methods?.provider && !stepUp ? (
        <Button
          variant="ghost"
          size="sm"
          className="mt-2"
          onClick={() => void stepUpWithProvider()}
          disabled={busy}
        >
          Re-authenticate
        </Button>
      ) : null}
      {error ? (
        <p role="alert" className="mt-2 rounded-xl bg-danger-soft px-2 py-1 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </section>
  );
}
