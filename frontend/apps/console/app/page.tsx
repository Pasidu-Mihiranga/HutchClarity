"use client";

import Link from "next/link";
import { Badge, Card } from "@clarity/ui";
import { STAFF_ROLES, useStaffSession } from "@/components/StaffSessionProvider";

export default function ConsoleHomePage() {
  const { session, activeRole, hasPermission } = useStaffSession();

  const sections = [
    {
      href: "/desk",
      title: "Desk",
      body: "Queue + cockpit",
      ok: hasPermission("desk:queue:read"),
    },
    {
      href: "/insights",
      title: "Insights",
      body: "Ops · autopsy · foresight",
      ok: hasPermission("desk:queue:read"),
    },
    {
      href: "/studio",
      title: "Studio",
      body: "Teach once · what-if · publish",
      ok: hasPermission("rule:draft", "rule:publish", "config:draft", "config:approve"),
    },
    {
      href: "/admin",
      title: "Admin",
      body: "Flags, kill switches",
      ok: hasPermission("admin:manage", "flags:kill_switch"),
    },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Staff console</h1>
      {!session ? (
        <Card className="space-y-2">
          <p className="text-slate-700">
            Pick a demo role in the bar below to start. Same idea as the
            customer quick-login: one tap switches identity; the API enforces
            what that role may do.
          </p>
          <ul className="grid gap-1 text-sm text-slate-600 sm:grid-cols-3">
            {STAFF_ROLES.map((r) => (
              <li key={r.id} className="font-mono text-xs">
                {r.id}
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <Card className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="success">{activeRole}</Badge>
            <span className="text-sm text-slate-600">{session.subject}</span>
            <Badge>{session.assurance}</Badge>
          </div>
          <details className="text-sm">
            <summary className="cursor-pointer text-slate-700">
              {session.permissions.length} permissions
            </summary>
            <ul className="mt-2 columns-2 gap-4 font-mono text-xs text-slate-600">
              {session.permissions.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </details>
        </Card>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {sections.map((item) =>
          item.ok || !session ? (
            <Link key={item.href} href={item.href}>
              <Card className="hover:border-sky-300">
                <h2 className="font-medium">{item.title}</h2>
                <p className="text-sm text-slate-600">{item.body}</p>
              </Card>
            </Link>
          ) : (
            <Card key={item.href} className="opacity-50">
              <h2 className="font-medium">{item.title}</h2>
              <p className="text-sm text-slate-500">Not allowed for this role</p>
            </Card>
          ),
        )}
      </div>
    </div>
  );
}
