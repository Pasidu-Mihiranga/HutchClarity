"use client";

import type { ReactNode } from "react";
import { SignInPortal } from "./SignInPortal";
import { useStaffSession } from "./StaffSessionProvider";

/** Every desk page needs a session: without one, the page is the sign-in portal. */
export function SessionGate({ children }: { children: ReactNode }) {
  const { session, restoring } = useStaffSession();
  // A stored session is still being checked; showing the portal now would
  // flash it at someone who is already signed in.
  if (restoring) return null;
  return session ? <>{children}</> : <SignInPortal />;
}
