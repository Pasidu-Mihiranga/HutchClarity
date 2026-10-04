"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useStaffSession } from "./StaffSessionProvider";

const links = [
  {
    href: "/desk",
    label: "Desk",
    anyOf: ["desk:queue:read"],
  },
  {
    href: "/insights",
    label: "Insights",
    anyOf: ["desk:queue:read"],
  },
  { href: "/autopsy", label: "Complaint Autopsy", anyOf: ["desk:queue:read"] },
  { href: "/foresight", label: "Foresight", anyOf: ["foresight:read"] },
  {
    href: "/studio",
    label: "Studio",
    anyOf: ["rule:draft", "rule:publish", "config:draft", "config:approve"],
  },
  {
    href: "/audit",
    label: "Audit",
    anyOf: ["audit:read"],
  },
  {
    href: "/admin",
    label: "Admin",
    anyOf: ["admin:manage", "flags:kill_switch"],
  },
];

/**
 * The section navigation (E2).
 *
 * **A list, because it is one.** A screen reader announces "navigation, list,
 * 7 items" and lets its user step through them or skip the lot; a bare row of
 * anchors announces each link with no sense of how many are left.
 *
 * **`aria-current="page"` rather than colour alone.** The active section was
 * marked only by a dark pill, which is invisible to anybody not looking at it
 * and to anybody who cannot distinguish the two backgrounds.
 *
 * **A section this role cannot open is not a link.** It renders as text with a
 * visually hidden reason, so a screen reader hears "Audit, not available for
 * your role" instead of meeting a link that goes nowhere. `title` alone did
 * not do this: it is not announced reliably and never reaches a touch user.
 */
export function ConsoleNav() {
  const pathname = usePathname();
  const { hasPermission, session } = useStaffSession();

  return (
    <nav
      aria-label="Console sections"
      className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-1 px-4 py-3 sm:px-6"
    >
      <Link href="/" className="mr-3 flex items-center gap-2">
        <span
          aria-hidden="true"
          className="grid h-8 w-8 place-items-center rounded-full bg-accent text-xs font-semibold text-primary-on"
        >
          C
        </span>
        <span className="font-display text-sm font-semibold tracking-tight text-ink">
          Clarity Desk
        </span>
      </Link>
      <ul className="flex flex-wrap items-center gap-1">
        {links.map((link) => {
          const allowed = !session || hasPermission(...link.anyOf);
          const active = pathname?.startsWith(link.href);
          return (
            <li key={link.href}>
              {allowed ? (
                <Link
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={`block rounded-full px-3 py-1.5 text-sm ${
                    active ? "bg-ink text-bg" : "text-fg-muted hover:bg-paper"
                  }`}
                >
                  {link.label}
                </Link>
              ) : (
                <span className="block cursor-not-allowed rounded-full px-3 py-1.5 text-sm text-fg-subtle">
                  {link.label}
                  <span className="sr-only"> (not available for your role)</span>
                </span>
              )}
            </li>
          );
        })}
      </ul>
      <p className="ml-auto hidden text-[11px] font-medium uppercase tracking-[0.14em] text-fg-subtle sm:block">
        Synthetic records
      </p>
    </nav>
  );
}
