"use client";

import { Card } from "@clarity/ui";
import { useStaffSession } from "./StaffSessionProvider";

export function AccessDenied({ need }: { need: string }) {
  const { session, activeRole, restoring } = useStaffSession();
  if (restoring) {
    return (
      <Card className="space-y-2">
        <p className="text-sm text-slate-600">Restoring staff session…</p>
      </Card>
    );
  }
  return (
    <Card className="space-y-2 rounded-card border-[#ffd4b6] bg-warm shadow-card">
      <h2 className="font-display text-lg font-semibold text-ink">This identity cannot open this</h2>
      <p className="text-sm text-[#82401e]">
        {session
          ? `Signed in as ${session.subject} (${activeRole}). Needs: ${need}.`
          : "Sign in from the header to start."}
      </p>
      <p className="text-xs text-[#8a4a28]">
        Four-eyes approvals need a different person (supervisor, then finance),
        not two roles on the same user.
      </p>
    </Card>
  );
}
