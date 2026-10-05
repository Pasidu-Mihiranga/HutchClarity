/**
 * Console workspace sections and the permission any-of each page keeps.
 *
 * Shared by the sidebar (what to show) and AccessDenied (where to send a
 * signed-in identity that opened a URL their role cannot keep).
 */

export type ConsoleSection = {
  href: string;
  label: string;
  anyOf: readonly string[];
};

export const CONSOLE_SECTIONS: readonly ConsoleSection[] = [
  { href: "/desk", label: "Cases", anyOf: ["desk:queue:read"] },
  { href: "/insights", label: "Insights", anyOf: ["desk:queue:read"] },
  { href: "/autopsy", label: "Complaint Autopsy", anyOf: ["desk:queue:read"] },
  // `foresight:read`, which the page itself requires (C4).
  { href: "/foresight", label: "Foresight", anyOf: ["foresight:read"] },
  {
    // Same two the Policy Studio page checks (D3).
    href: "/studio",
    label: "Studio",
    anyOf: ["config:draft", "config:approve"],
  },
  { href: "/offers", label: "Offers", anyOf: ["offer:manage"] },
  { href: "/audit", label: "Audit", anyOf: ["audit:read"] },
  {
    href: "/iam",
    label: "IAM",
    anyOf: ["iam:role:manage"],
  },
  {
    href: "/admin",
    label: "Admin",
    anyOf: ["admin:manage", "flags:kill_switch"],
  },
] as const;

export function firstAllowedSection(
  hasPermission: (...needed: string[]) => boolean,
): ConsoleSection | null {
  return CONSOLE_SECTIONS.find((section) => hasPermission(...section.anyOf)) ?? null;
}
