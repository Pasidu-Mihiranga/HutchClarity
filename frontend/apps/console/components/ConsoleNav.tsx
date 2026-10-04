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
  { href: "/foresight", label: "Foresight", anyOf: ["desk:queue:read"] },
  {
    href: "/studio",
    label: "Studio",
    anyOf: ["rule:draft", "rule:publish", "config:draft", "config:approve"],
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
    <nav className="flex flex-wrap items-center gap-1 border-b border-slate-200 bg-white px-4 py-3">
      <Link
        href="/"
        className="mr-4 text-sm font-semibold text-sky-800 hover:text-sky-950"
      >
        Clarity Console
      </Link>
      {links.map((link) => {
        const allowed = !session || hasPermission(...link.anyOf);
        const active = pathname?.startsWith(link.href);
        if (!allowed) {
          return (
            <span
              key={link.href}
              title="Your current role cannot access this"
              className="cursor-not-allowed rounded px-3 py-1.5 text-sm text-slate-300"
            >
              {link.label}
            </span>
          );
        }
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`rounded px-3 py-1.5 text-sm ${
              active
                ? "bg-sky-700 text-white"
                : "text-slate-700 hover:bg-slate-100"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
      <span className="ml-auto text-xs text-amber-800">
        Simulated IDP · permissions are real
      </span>
    </nav>
  );
}
