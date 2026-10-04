"use client";

import Link from "next/link";
import { Badge, Card } from "@clarity/ui";
import { useStaffSession } from "@/components/StaffSessionProvider";

/**
 * The console landing page (E2).
 *
 * The section cards are a list, so a screen reader announces how many there
 * are and which of them this identity can actually open. A card for a section
 * the role cannot reach is not a link and says why in text, rather than being
 * a dimmed link that goes to a refusal.
 */
export default function ConsoleHomePage() {
  const { session, activeRole, hasPermission } = useStaffSession();

  const sections = [
    {
      href: "/desk",
      title: "Desk",
      body: "Queue and approval",
      ok: hasPermission("desk:queue:read"),
    },
    {
      href: "/insights",
      title: "Insights",
      body: "Ops, autopsy and foresight",
      ok: hasPermission("desk:queue:read"),
    },
    {
      href: "/studio",
      title: "Studio",
      body: "Teach once, what-if, publish",
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
    <div className="space-y-8">
      <div className="max-w-2xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">
          Resolve and support
        </p>
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          Clarity Desk
        </h1>
        <p className="text-base leading-7 text-mute">
          Evidence, a rule decision, and a signed Trust Receipt. The queue is
          synthetic subscriber data. Sign in with the account you were issued.
          The server assigns the role.
        </p>
      </div>

      <section aria-labelledby="console-identity">
        <h2 id="console-identity" className="sr-only">
          This session
        </h2>
        {!session ? (
          <Card className="space-y-3 rounded-card border-line bg-surface shadow-card">
            <p className="text-ink">
              Sign in from the header. The account decides the role. A wrong
              password is refused, and the desk cannot grant a role by itself.
            </p>
          </Card>
        ) : (
          <Card className="space-y-2 rounded-card border-line bg-surface shadow-card">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="success">{activeRole}</Badge>
              <span className="text-sm text-mute">{session.subject}</span>
              <Badge>{session.assurance}</Badge>
            </div>
            <details className="text-sm">
              <summary className="cursor-pointer text-ink">
                {session.permissions.length} permissions
              </summary>
              <ul className="mt-2 columns-2 gap-4 font-mono text-xs text-mute">
                {session.permissions.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </details>
          </Card>
        )}
      </section>

      <section aria-labelledby="console-sections">
        <h2 id="console-sections" className="sr-only">
          Sections
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2">
          {sections.map((item) => (
            <li key={item.href}>
              {item.ok || !session ? (
                <Link href={item.href} className="block rounded-card">
                  <Card className="rounded-card border-line bg-surface shadow-card transition hover:-translate-y-0.5 hover:border-primary">
                    <h3 className="font-display text-xl font-semibold">{item.title}</h3>
                    <p className="mt-1 text-sm text-mute">{item.body}</p>
                  </Card>
                </Link>
              ) : (
                <Card className="rounded-card border-line opacity-60">
                  <h3 className="font-display text-xl font-semibold">{item.title}</h3>
                  <p className="text-sm text-mute">Not allowed for this identity</p>
                </Card>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
