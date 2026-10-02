import { Badge, Card } from "@clarity/ui";

export default function InsightsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Insights</h1>
        <p className="text-sm text-slate-600">
          Aggregate autopsy / foresight placeholders (E7).
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "Top cause (7d)", value: "VAS silent renewal", tone: "warning" as const },
          { label: "Repeat contacts", value: "Relative band: elevated", tone: "danger" as const },
          { label: "Auto-fix rate", value: "— pending backtest", tone: "neutral" as const },
        ].map((kpi) => (
          <Card key={kpi.label} className="space-y-2">
            <p className="text-xs uppercase text-slate-500">{kpi.label}</p>
            <p className="text-lg font-medium">{kpi.value}</p>
            <Badge tone={kpi.tone}>Hypothesis</Badge>
          </Card>
        ))}
      </div>

      <Card>
        <h2 className="mb-2 font-medium">Cluster sketch</h2>
        <p className="text-sm text-slate-600">
          Mask-first complaint clusters appear here once autopsy feeds insights.
          Counts are relative bands only until governance review.
        </p>
      </Card>
    </div>
  );
}
