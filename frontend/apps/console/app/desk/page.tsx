"use client";

import { t } from "@clarity/i18n";
import { Badge, Card } from "@clarity/ui";

const queue = [
  { id: "CASE-01", cause: "Double charge", risk: "high", age: "4m" },
  { id: "CASE-02", cause: "FUP surprise", risk: "med", age: "12m" },
  { id: "CASE-03", cause: "Loan stacking", risk: "low", age: "31m" },
];

export default function DeskPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("en", "desk.queue")}</h1>
        <p className="text-sm text-slate-600">
          Queue + agent cockpit placeholder (D3).
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1 space-y-2">
          <h2 className="text-sm font-medium uppercase text-slate-500">
            Queue
          </h2>
          <ul className="space-y-2">
            {queue.map((item) => (
              <li
                key={item.id}
                className="flex items-center justify-between rounded border border-slate-100 px-3 py-2 text-sm"
              >
                <div>
                  <p className="font-mono text-xs text-slate-500">{item.id}</p>
                  <p>{item.cause}</p>
                </div>
                <div className="text-right">
                  <Badge
                    tone={
                      item.risk === "high"
                        ? "danger"
                        : item.risk === "med"
                          ? "warning"
                          : "neutral"
                    }
                  >
                    {item.risk}
                  </Badge>
                  <p className="mt-1 text-xs text-slate-500">{item.age}</p>
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="lg:col-span-2 space-y-3">
          <h2 className="text-sm font-medium uppercase text-slate-500">
            Cockpit
          </h2>
          <p className="text-lg font-medium">CASE-01 · Double charge</p>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-slate-500">Subscriber</dt>
            <dd className="font-mono">sub_demo_***</dd>
            <dt className="text-slate-500">Allowed actions</dt>
            <dd>Refund · Notify · Handoff</dd>
            <dt className="text-slate-500">Evidence</dt>
            <dd>3 events · snapshot ready</dd>
          </dl>
          <p className="text-sm text-slate-500">
            Wire to GET /v1/desk/queue and case evaluate when API is up.
          </p>
        </Card>
      </div>
    </div>
  );
}
