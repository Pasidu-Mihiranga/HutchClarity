"use client";

import { useStaffSession } from "./StaffSessionProvider";

/**
 * Who is signed in, under the nav. Signing in happens in `SignInPortal`,
 * which takes the page while there is no session.
 */
export function RoleSwitcherBar() {
  const { stepUpWithProvider, methods, signOut, session, stepUp, busy, error } =
    useStaffSession();

  if (!session) return null;

  return (
    <div className="border-t border-line bg-surface-2/80">
      <div className="mx-auto flex max-w-[1240px] flex-col gap-2 px-4 py-2.5 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-mute">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span aria-hidden className="h-2 w-2 rounded-full bg-success" />
            <strong className="text-ink">{session.subject}</strong>
            <span className="rounded-full bg-warm px-2 py-0.5 font-semibold text-accent">
              {session.roles.join(", ")}
            </span>
            <span>{session.permissions.length} permissions</span>
            <span>· assurance {session.assurance}</span>
          </span>
          <span className="flex items-center gap-3">
            {/* Offered only where it can do anything: the provider is what
                re-authenticates, and a session already stepped up has
                nothing to gain from doing it again (B2). */}
            {methods?.provider && !stepUp ? (
              <button
                type="button"
                className="font-semibold text-accent underline-offset-2 hover:underline"
                onClick={() => void stepUpWithProvider()}
                disabled={busy}
              >
                Re-authenticate
              </button>
            ) : null}
            <button
              type="button"
              className="rounded-full border border-border-strong bg-surface px-3 py-1 font-semibold text-ink transition hover:border-brand hover:text-accent"
              onClick={signOut}
              disabled={busy}
            >
              Sign out
            </button>
          </span>
        </div>
        {error ? (
          <p role="alert" className="rounded-md bg-danger-soft px-2 py-1 text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
