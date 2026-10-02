import { Badge, Button, Card, Input } from "@clarity/ui";

export default function StudioPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Policy studio</h1>
        <p className="text-sm text-slate-600">
          Teach once · what-if · publish (D4).
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Teach once</h2>
            <Badge>Draft</Badge>
          </div>
          <label className="block space-y-1 text-sm">
            <span>Pattern name</span>
            <Input placeholder="e.g. social_pack_scope" />
          </label>
          <label className="block space-y-1 text-sm">
            <span>Example utterance</span>
            <Input placeholder="Why did Facebook use my main data?" />
          </label>
          <Button variant="secondary">Save draft</Button>
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">What-if</h2>
          <p className="text-sm text-slate-600">
            Replay last N snapshots with a candidate zen table / threshold.
          </p>
          <label className="block space-y-1 text-sm">
            <span>Threshold delta</span>
            <Input defaultValue="+10%" />
          </label>
          <Button variant="secondary">Simulate</Button>
          <p className="text-xs text-slate-500">
            Result: 0 auto-fixes flipped (placeholder).
          </p>
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">Publish</h2>
          <p className="text-sm text-slate-600">
            Four-eyes approval required before activation.
          </p>
          <ul className="space-y-1 text-sm text-slate-700">
            <li>· Version: draft-0.1</li>
            <li>· Approver: pending</li>
            <li>· Kill switch: armed</li>
          </ul>
          <Button disabled>Publish (needs approval)</Button>
        </Card>
      </div>
    </div>
  );
}
