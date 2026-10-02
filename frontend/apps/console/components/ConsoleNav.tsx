"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/desk", label: "Desk" },
  { href: "/insights", label: "Insights" },
  { href: "/studio", label: "Studio" },
  { href: "/admin", label: "Admin" },
];

export function ConsoleNav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap gap-1 border-b border-slate-200 bg-white px-4 py-3">
      <Link
        href="/"
        className="mr-4 text-sm font-semibold text-sky-800 hover:text-sky-950"
      >
        Clarity Console
      </Link>
      {links.map((link) => {
        const active = pathname?.startsWith(link.href);
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
    </nav>
  );
}
