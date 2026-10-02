import { Badge, Button, Card } from "@clarity/ui";

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="text-sm text-slate-600">
          Flags, kill switches, MCP clients, notification templates.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="font-medium">Feature flags</h2>
          {[
            { name: "customer_why_v2", on: true },
            { name: "auto_fix_vas", on: false },
            { name: "foresight_ui", on: false },
          ].map((flag) => (
            <div
              key={flag.name}
              className="flex items-center justify-between text-sm"
            >
              <span className="font-mono">{flag.name}</span>
              <Badge tone={flag.on ? "success" : "neutral"}>
                {flag.on ? "on" : "off"}
              </Badge>
            </div>
          ))}
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">Kill switches</h2>
          <p className="text-sm text-slate-600">
            Immediate halt for money-path automations.
          </p>
          <Button variant="secondary">Arm all auto-fix</Button>
          <Button variant="ghost">Trip actions.execute</Button>
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">MCP clients</h2>
          <ul className="space-y-2 text-sm">
            <li className="flex justify-between">
              <span>desk-copilot</span>
              <Badge tone="success">active</Badge>
            </li>
            <li className="flex justify-between">
              <span>partner-sandbox</span>
              <Badge tone="warning">limited</Badge>
            </li>
          </ul>
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">Notification templates</h2>
          <ul className="space-y-1 text-sm text-slate-700">
            <li>· receipt_issued · si/ta/en</li>
            <li>· otp_request · si/ta/en</li>
            <li>· vas_renewal_warn · draft</li>
          </ul>
          <Button variant="secondary">Open template editor</Button>
        </Card>
      </div>
    </div>
  );
}
