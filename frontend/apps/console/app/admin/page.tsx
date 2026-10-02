"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card } from "@clarity/ui";
import type { SwitchStateView } from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

const DEFAULT_KEYS = [
  "auto_fix_global",
  "customer_actions",
  "llm_explanations",
  "proactive_messages",
];

export default function AdminPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const canRead = hasPermission("admin:manage", "flags:kill_switch");
  const canFlip = hasPermission("flags:kill_switch");
  const isAdmin = hasPermission("admin:manage");

  const [state, setState] = useState<SwitchStateView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!canRead) return;
    setError(null);
    try {
      setState(await client.listSwitches());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    }
  }, [canRead, client]);

  useEffect(() => {
    void load();
  }, [load, generation]);

  async function flip(key: string, enabled: boolean) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await client.flipSwitch({
        key,
        enabled,
        reason: `Console admin toggle by ${session?.subject || "staff"}`,
      });
      setState(next);
      setMessage(`${key} → ${enabled ? "on" : "off"}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Flip failed");
    } finally {
      setBusy(false);
    }
  }

  if (!session || !canRead) {
    return <AccessDenied need="admin:manage or flags:kill_switch" />;
  }

  const switches =
    state?.switches?.length
      ? state.switches
      : DEFAULT_KEYS.map((key) => ({ key, enabled: true }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="text-sm text-slate-600">
          Kill switches degrade journeys; they never invent money.
        </p>
      </div>

      {error ? (
        <Card className="border-rose-200 bg-rose-50 text-sm text-rose-900">{error}</Card>
      ) : null}
      {message ? (
        <Card className="border-emerald-200 bg-emerald-50 text-sm text-emerald-900">
          {message}
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Kill switches</h2>
            {canFlip ? <Badge tone="success">can flip</Badge> : <Badge>read-only</Badge>}
          </div>
          {switches.map((sw) => (
            <div
              key={sw.key}
              className="flex items-center justify-between gap-2 text-sm"
            >
              <span className="font-mono text-xs">{sw.key}</span>
              <div className="flex items-center gap-2">
                <Badge tone={sw.enabled ? "success" : "danger"}>
                  {sw.enabled ? "on" : "off"}
                </Badge>
                {canFlip ? (
                  <Button
                    variant="ghost"
                    disabled={busy}
                    onClick={() => void flip(sw.key, !sw.enabled)}
                  >
                    {sw.enabled ? "Turn off" : "Turn on"}
                  </Button>
                ) : null}
              </div>
            </div>
          ))}
          {!canFlip ? (
            <p className="text-xs text-slate-500">
              Read-only for this role (needs flags:kill_switch to flip).
            </p>
          ) : null}
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">Admin posture</h2>
          <ul className="space-y-2 text-sm text-slate-700">
            <li className="flex justify-between">
              <span>admin:manage</span>
              <Badge tone={isAdmin ? "success" : "neutral"}>
                {isAdmin ? "yes" : "no"}
              </Badge>
            </li>
            <li className="flex justify-between">
              <span>Money approve</span>
              <Badge tone="success">stripped for admins</Badge>
            </li>
            <li className="flex justify-between">
              <span>Audit trail API</span>
              <Badge tone="warning">not wired</Badge>
            </li>
          </ul>
          <p className="text-xs text-slate-500">
            Platform and security admins never approve refunds. Use Desk with
            supervisor/finance for money.
          </p>
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">Recent flips</h2>
          <ul className="max-h-48 space-y-1 overflow-auto text-xs text-slate-600">
            {(state?.history || []).length ? (
              state!.history.map((h, i) => (
                <li key={`${h.name}-${i}`}>
                  {h.at}: {h.name} → {h.enabled ? "on" : "off"} by {h.actor_ref} (
                  {h.reason})
                </li>
              ))
            ) : (
              <li>No flips yet in this process.</li>
            )}
          </ul>
        </Card>

        <Card className="space-y-3">
          <h2 className="font-medium">MCP / templates</h2>
          <p className="text-sm text-slate-600">
            Placeholder inventory — not connected to live MCP clients.
          </p>
          <ul className="space-y-1 text-sm text-slate-700">
            <li>· desk-copilot (designed)</li>
            <li>· receipt_issued · si/ta/en</li>
            <li>· otp_request · si/ta/en</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
