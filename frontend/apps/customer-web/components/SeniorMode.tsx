"use client";

import { useMe } from "@/lib/useMe";

/**
 * Loads the account so a saved senior choice is on the document before the
 * customer has opened Settings. The attribute is written inside useMe.
 */
export function SeniorMode() {
  useMe();
  return null;
}
