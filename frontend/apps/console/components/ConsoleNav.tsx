"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useStaffSession } from "./StaffSessionProvider";

const links: { href: string; label: string; anyOf: string[]; icon: ReactNode }[] = [
  { href: "/desk", label: "Cases", anyOf: ["desk:queue:read"], icon: <IconRows /> },
  { href: "/insights", label: "Insights", anyOf: ["desk:queue:read"], icon: <IconBars /> },
  { href: "/autopsy", label: "Complaint Autopsy", anyOf: ["desk:queue:read"], icon: <IconBook /> },
  // `foresight:read`, which the page itself requires (C4). Gating the link on
  // the desk's permission instead offered every agent and supervisor a link
  // that lands on "access denied": the nav must promise what the page keeps.
  { href: "/foresight", label: "Foresight", anyOf: ["foresight:read"], icon: <IconBars /> },
  {
    // The same two the Policy Studio page and the governance routes check
    // (D3). `rule:publish` was in here and is held by compliance, who holds
    // neither config permission, so they were shown a link to a refusal.
    href: "/studio",
    label: "Studio",
    anyOf: ["config:draft", "config:approve"],
    icon: <IconGear />,
  },
  { href: "/audit", label: "Audit", anyOf: ["audit:read"], icon: <IconBook /> },
  { href: "/admin", label: "Admin", anyOf: ["admin:manage", "flags:kill_switch"], icon: <IconGear /> },
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
    <div className="flex min-h-0 flex-1 flex-col">
      <Link href="/" className="flex items-center gap-2.5 px-5 py-5">
        <span
          aria-hidden="true"
          className="grid h-9 w-9 place-items-center rounded-full bg-primary text-primary-on"
        >
          <IconMark />
        </span>
        <span className="leading-tight">
          <span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">
            Hutch
          </span>
          <span className="block font-display text-[15px] font-semibold tracking-tight text-ink">
            Clarity Desk
          </span>
        </span>
      </Link>
      <nav aria-label="Console sections" className="px-3">
        <ul className="flex flex-col gap-1">
          {links.map((link) => {
            const allowed = !session || hasPermission(...link.anyOf);
            const active = pathname === link.href || pathname?.startsWith(`${link.href}/`);
            const itemClass = `flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm ${
              active ? "bg-primary-soft font-medium text-primary" : "text-fg-muted hover:bg-surface-2"
            }`;
            return (
              <li key={link.href}>
                {allowed ? (
                  <Link href={link.href} aria-current={active ? "page" : undefined} className={itemClass}>
                    <span aria-hidden="true">{link.icon}</span>
                    {link.label}
                  </Link>
                ) : (
                  <span className="flex cursor-not-allowed items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-fg-subtle">
                    <span aria-hidden="true">{link.icon}</span>
                    {link.label}
                    <span className="sr-only"> (not available for your role)</span>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}

function IconMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M5 6.5A3.5 3.5 0 0 1 8.5 3h7A3.5 3.5 0 0 1 19 6.5v6A3.5 3.5 0 0 1 15.5 16H12l-4 4v-4H8.5A3.5 3.5 0 0 1 5 12.5v-6Z" />
    </svg>
  );
}

function IconRows() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <rect x="4" y="4" width="16" height="16" rx="3" />
      <path d="M8 9h8M8 12h8M8 15h5" />
    </svg>
  );
}

function IconBars() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M5 19V10M12 19V5M19 19v-7" strokeLinecap="round" />
    </svg>
  );
}

function IconBook() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H19v16H7.5A2.5 2.5 0 0 0 5 21.5V5.5Z" />
    </svg>
  );
}

function IconGear() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3.5v2.2M12 18.3V20.5M4.8 6.8l1.6 1.6M17.6 15.6l1.6 1.6M3.5 12h2.2M18.3 12h2.2" strokeLinecap="round" />
    </svg>
  );
}
