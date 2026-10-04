"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Card, Input } from "@clarity/ui";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

const DRAFT_KEY = "clarity_studio_draft_v1";

type Draft = {
  pattern: string;
  utterance: string;
  threshold: string;
  savedAt?: string;
};

export default function StudioPage() {
  const { session, hasPermission, stepUp } = useStaffSession();
  const canDraft = hasPermission("rule:draft", "config:draft");
  const canPublish = hasPermission("rule:publish", "config:approve");
  const canExport = hasPermission("regulator_pack:export");
  const allowed = canDraft || canPublish || canExport;

  const [draft, setDraft] = useState<Draft>({
    pattern: "",
    utterance: "",
    threshold: "+10%",
  });
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(DRAFT_KEY);
      if (raw) setDraft(JSON.parse(raw) as Draft);
    } catch {
      /* ignore */
    }
  }, []);

  function saveDraft() {
    const next = { ...draft, savedAt: new Date().toISOString() };
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(next));
    setDraft(next);
    setStatus("Draft saved in this browser. Publish is not connected yet.");
  }

  function exportPack() {
    const payload = {
      simulated: true,
      exported_at: new Date().toISOString(),
      subject: session?.subject,
      note: "Synthetic regulator pack. Not a signed production export.",
      draft,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "clarity-regulator-pack.json";
    a.click();
    URL.revokeObjectURL(url);
    setStatus("Downloaded simulated regulator pack JSON.");
  }

  if (!session || !allowed) {
    return (
      <AccessDenied need="rule:draft / rule:publish / config:draft" />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Policy studio</h1>
        <p className="text-sm text-slate-600">
          Teach once · what-if · publish. Drafts stay in this browser until a
          real governance API ships.
        </p>
      </div>

      {status ? (
        <Card className="border-sky-200 bg-sky-50 text-sm text-sky-950">{status}</Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Teach once</h2>
            <Badge>{canDraft ? "Draft" : "Read-only"}</Badge>
          </div>
          <label className="block space-y-1 text-sm">
            <span>Pattern name</span>
            <Input
              placeholder="e.g. social_pack_scope"
              value={draft.pattern}
              disabled={!canDraft}
              onChange={(e) => setDraft({ ...draft, pattern: e.target.value })}
            />
          </label>
          <label className="block space-y-1 text-sm">
            <span>Example utterance</span>
            <Input
              placeholder="Why did Facebook use my main data?"
              value={draft.utterance}
              disabled={!canDraft}
              onChange={(e) => setDraft({ ...draft, utterance: e.target.value })}
            />
          </label>
          {canDraft ? (
            <Button variant="secondary" onClick={saveDraft}>
              Save draft
            </Button>
          ) : (
            <p className="text-xs text-slate-500">Needs cx_engineer (rule:draft).</p>
          )}
          {draft.savedAt ? (
            <p className="text-xs text-slate-500">Saved {draft.savedAt}</p>
          ) : null}
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">What-if</h2>
          <p className="text-sm text-slate-600">
            Replay last N snapshots with a candidate threshold (UI stub).
          </p>
          <label className="block space-y-1 text-sm">
            <span>Threshold delta</span>
            <Input
              value={draft.threshold}
              disabled={!canDraft}
              onChange={(e) => setDraft({ ...draft, threshold: e.target.value })}
            />
          </label>
          <Button
            variant="secondary"
            disabled={!canDraft}
            onClick={() =>
              setStatus("Simulate: 0 auto-fixes flipped (placeholder - no replay API).")
            }
          >
            Simulate
          </Button>
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">Publish / export</h2>
          <p className="text-sm text-slate-600">
            Four-eyes approval required before activation. Publish API not
            wired; export is a labelled stub.
          </p>
          <Button
            variant="secondary"
            disabled={!canPublish || !stepUp}
            onClick={() =>
              setStatus(
                "Publish is not connected yet. Step-up is on.",
              )
            }
          >
            Request publish
          </Button>
          {!stepUp && canPublish ? (
            <p className="text-xs text-amber-800">Sign in again with your step-up code.</p>
          ) : null}
          {canExport ? (
            <Button variant="ghost" onClick={exportPack}>
              Export regulator pack (simulated)
            </Button>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
