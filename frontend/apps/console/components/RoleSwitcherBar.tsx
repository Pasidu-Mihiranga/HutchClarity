"use client";

import { Button } from "@clarity/ui";
import { useStaffSession } from "./StaffSessionProvider";

/**
 * The signed-in session bar (E2).
 *
 * The sign-in form lives on `DeskLogin`. This bar is only the person who is
 * already in: who they are, a re-authentication when the provider can do it,
 * and sign out.
 */
export function RoleSwitcherBar() {
  const { stepUpWithProvider, methods, signOut, session, stepUp, busy, error } = useStaffSession();

  if (!session) return null;

  return (
    <section aria-label="Staff session" className="border-t border-line bg-warm">
      <div className="mx-auto flex max-w-[1240px] flex-col gap-2 px-4 py-2.5 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-mute">
          <p>
            <strong className="text-ink">{session.subject}</strong>
            {" · "}
            {session.roles.join(", ")}
            {" · "}
            {session.permissions.length} permissions
            {" · "}
            assurance {session.assurance}
          </p>
          <span className="flex items-center gap-3">
            {/* Offered only where it can do anything: the provider is what
                re-authenticates, and a session already stepped up has
                nothing to gain from doing it again (B2). */}
            {methods?.provider && !stepUp ? (
              <Button variant="ghost" size="sm" onClick={() => void stepUpWithProvider()} disabled={busy}>
                Re-authenticate
              </Button>
            ) : null}
            <Button variant="ghost" size="sm" onClick={signOut} disabled={busy}>
              Sign out
            </Button>
          </span>
        </div>
        {error ? (
          <p role="alert" className="rounded-xl bg-danger-soft px-2 py-1 text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
