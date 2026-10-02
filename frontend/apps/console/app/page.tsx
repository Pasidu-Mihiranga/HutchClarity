import Link from "next/link";
import { Card } from "@clarity/ui";

export default function ConsoleHomePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Staff console</h1>
      <p className="text-slate-600">
        Phase D3 placeholder — desk queue, insights, policy studio, and admin.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {[
          { href: "/desk", title: "Desk", body: "Queue + cockpit" },
          { href: "/insights", title: "Insights", body: "Trends & autopsy" },
          {
            href: "/studio",
            title: "Studio",
            body: "Teach once · what-if · publish",
          },
          {
            href: "/admin",
            title: "Admin",
            body: "Flags, kill switches, MCP, templates",
          },
        ].map((item) => (
          <Link key={item.href} href={item.href}>
            <Card className="hover:border-sky-300">
              <h2 className="font-medium">{item.title}</h2>
              <p className="text-sm text-slate-600">{item.body}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
