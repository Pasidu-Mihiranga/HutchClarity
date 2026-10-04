"use client";

import { Card, Spinner } from "@clarity/ui";
import { useStaffSession } from "./StaffSessionProvider";

/**
 * What a page renders instead of itself when the identity cannot open it (E2).
 *
 * This replaces the whole page, so it carries the `h1`: without one the
 * document has no top-level heading and a screen reader user navigating by
 * heading lands nowhere. It is also announced, because a refusal that renders
 * silently leaves somebody waiting for a page that has already decided.
 *
 * The restoring state is a `status` rather than an `alert`: a session being
 * read back is not news, and announcing it assertively would interrupt.
 */
export function AccessDenied({ need }: { need: string }) {
  const { session, activeRole, restoring } = useStaffSession();
  if (restoring) {
    return (
      <Card className="flex items-center gap-3" role="status">
        {/* The card is the live region and the paragraph is its text, so the
            spinner is decoration here. Left as its own `role="status"` it
            would announce a second time from inside the region that has
            already said what is happening. */}
        <Spinner size="sm" label="" role="presentation" aria-hidden="true" />
        <p className="text-sm text-mute">Restoring staff session…</p>
      </Card>
    );
  }
  return (
    <Card className="space-y-2 rounded-card border-primary/30 bg-warm shadow-card" role="alert">
      <h1 className="font-display text-lg font-semibold text-ink">
        This identity cannot open this
      </h1>
      <p className="text-sm text-fg">
        {session
          ? `Signed in as ${session.subject} (${activeRole}). Needs: ${need}.`
          : "Sign in from the header to start."}
      </p>
      <p className="text-xs text-fg-muted">
        Four-eyes approvals need a different person (supervisor, then finance),
        not two roles on the same user.
      </p>
    </Card>
  );
}
