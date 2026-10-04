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
  // `foresight:read`, which the page itself requires (C4). Gating the link on
  // the desk's permission instead offered every agent and supervisor a link
  // that lands on "access denied": the nav must promise what the page keeps.
  { href: "/foresight", label: "Foresight", anyOf: ["foresight:read"] },
  {
    // The same two the Policy Studio page and the governance routes check
    // (D3). `rule:publish` was in here and is held by compliance, who holds
    // neither config permission, so they were shown a link to a refusal.
    href: "/studio",
    label: "Studio",
    anyOf: ["config:draft", "config:approve"],
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

export function ConsoleNav() {
  const pathname = usePathname();
  const { hasPermission, session } = useStaffSession();

  return (
    <nav className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-1 px-4 py-3 sm:px-6">
      <Link href="/" className="mr-3 flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-accent text-xs font-semibold text-white">
          C
        </span>
        <span className="font-display text-sm font-semibold tracking-tight text-ink">
          Clarity Desk
        </span>
      </Link>
      {links.map((link) => {
        const allowed = !session || hasPermission(...link.anyOf);
        const active = pathname?.startsWith(link.href);
        if (!allowed) {
          return (
            <span
              key={link.href}
              title="Your current role cannot access this"
              className="cursor-not-allowed rounded-full px-3 py-1.5 text-sm text-[#c7ced5]"
            >
              {link.label}
            </span>
          );
        }
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`rounded-full px-3 py-1.5 text-sm ${
              active
                ? "bg-ink text-white"
                : "text-[#555d68] hover:bg-paper"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
      <span className="ml-auto hidden text-[11px] font-medium uppercase tracking-[0.14em] text-[#818995] sm:inline">
        Synthetic records
      </span>
    </nav>
  );
}
