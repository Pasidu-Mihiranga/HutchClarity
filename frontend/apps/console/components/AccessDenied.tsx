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
    <Card className="space-y-2 border-amber-200 bg-amber-50">
      <h2 className="font-medium text-amber-950">Your current role cannot access this</h2>
      <p className="text-sm text-amber-900">
        {session
          ? `Signed in as ${session.subject} (${activeRole}). Needs: ${need}.`
          : "Pick a role in the bar below to start."}
      </p>
      <p className="text-xs text-amber-800">
        Switch roles with the bottom bar. Four-eyes approvals need a different
        user ref (e.g. supervisor then finance), not only a different role on
        the same person.
      </p>
    </Card>
  );
}
