"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Dialog } from "@clarity/ui";
import type { SwitchStateView } from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { useStaffSession } from "@/components/StaffSessionProvider";

/**
 * Admin, with the accessibility pass of E2.
 *
 * **Every toggle names what it toggles.** The button said "Turn off" and the
 * switch key sat in a sibling element, so a screen reader reading the controls
 * heard "Turn off, Turn off, Turn off, Turn off" with nothing to tell them
 * apart. Each one now carries the key in its accessible name.
 *
 * **Flipping a switch asks first.** A kill switch degrades a journey for every
 * customer at once and the page flipped it on a single click. It now confirms
 * in a dialog that names the switch and the direction, which is also what
 * gives the keyboard path a focus trap.
 *
 * The confirmation is a courtesy, not a control: the API still decides whether
 * this identity may flip anything, and the button is absent without
 * `flags:kill_switch` rather than present and failing.
 */

const DEFAULT_KEYS = [
  "auto_fix_global",
  "customer_actions",
  "llm_explanations",
  "proactive_messages",
];

type Pending = { key: string; enabled: boolean };

export default function AdminPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const canRead = hasPermission("admin:manage", "flags:kill_switch");
  const canFlip = hasPermission("flags:kill_switch");
  const isAdmin = hasPermission("admin:manage");

  const [state, setState] = useState<SwitchStateView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);

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
    setPending(null);
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
      setMessage(`${key} is now ${enabled ? "on" : "off"}`);
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
        <p className="text-sm text-fg-muted">
          Kill switches degrade journeys; they never invent money.
        </p>
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      <Dialog
        open={pending !== null}
        onClose={() => setPending(null)}
        title={
          pending
            ? `Turn ${pending.enabled ? "on" : "off"} ${pending.key}?`
            : "Confirm"
        }
        description="A kill switch takes effect for every customer at once, and the flip is recorded against your identity with its reason."
        dismissOnBackdrop={false}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPending(null)}>
              Cancel
            </Button>
            <Button
              variant={pending?.enabled ? "primary" : "danger"}
              data-autofocus
              onClick={() => pending && void flip(pending.key, pending.enabled)}
            >
              {pending?.enabled ? "Turn it on" : "Turn it off"}
            </Button>
          </>
        }
      >
        <p>
          {pending?.enabled
            ? "The journey this switch guards starts working again. Nothing is replayed: cases that fell back while it was off stay as they were handled."
            : "The journey this switch guards degrades for everyone. Customers are not left without an answer, they are routed to the explain-only path or to a person."}
        </p>
      </Dialog>

      <div className="grid gap-4 md:grid-cols-2">
        <section aria-labelledby="admin-switches">
          <Card className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 id="admin-switches" className="font-medium">
                Kill switches
              </h2>
              {canFlip ? <Badge tone="success">can flip</Badge> : <Badge>read-only</Badge>}
            </div>
            <ul className="space-y-3">
              {switches.map((sw) => (
                <li key={sw.key} className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-mono text-xs">{sw.key}</span>
                  <span className="flex items-center gap-2">
                    <Badge tone={sw.enabled ? "success" : "danger"}>
                      {sw.enabled ? "on" : "off"}
                    </Badge>
                    {canFlip ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={busy}
                        aria-label={`${sw.enabled ? "Turn off" : "Turn on"} ${sw.key}`}
                        onClick={() => setPending({ key: sw.key, enabled: !sw.enabled })}
                      >
                        {sw.enabled ? "Turn off" : "Turn on"}
                      </Button>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
            {!canFlip ? (
              <p className="text-xs text-fg-muted">
                Read-only for this role (needs flags:kill_switch to flip).
              </p>
            ) : null}
          </Card>
        </section>

        <section aria-labelledby="admin-posture">
          <Card className="space-y-3">
            <h2 id="admin-posture" className="font-medium">
              Admin posture
            </h2>
            <ul className="space-y-2 text-sm text-fg">
              <li className="flex justify-between">
                <span>admin:manage</span>
                <Badge tone={isAdmin ? "success" : "neutral"}>{isAdmin ? "yes" : "no"}</Badge>
              </li>
              <li className="flex justify-between">
                <span>Money approve</span>
                <Badge tone="success">stripped for admins</Badge>
              </li>
              <li className="flex justify-between">
                <span>Audit trail API</span>
                <Badge tone="success">wired - see Audit</Badge>
              </li>
            </ul>
            <p className="text-xs text-fg-muted">
              Platform and security admins never approve refunds. Use Desk with
              supervisor/finance for money.
            </p>
          </Card>
        </section>

        <section aria-labelledby="admin-flips">
          <Card className="space-y-3">
            <h2 id="admin-flips" className="font-medium">
              Recent flips
            </h2>
            <ul className="max-h-48 space-y-1 overflow-auto text-xs text-fg-muted">
              {(state?.history || []).length ? (
                state!.history.map((h, i) => (
                  <li key={`${h.name}-${i}`}>
                    {h.at}: {h.name} is now {h.enabled ? "on" : "off"}, by {h.actor_ref} (
                    {h.reason})
                  </li>
                ))
              ) : (
                <li>No flips yet in this process.</li>
              )}
            </ul>
          </Card>
        </section>

        <section aria-labelledby="admin-mcp">
          <Card className="space-y-3">
            <h2 id="admin-mcp" className="font-medium">
              MCP and templates
            </h2>
            <p className="text-sm text-fg-muted">
              Placeholder inventory - not connected to live MCP clients.
            </p>
            <ul className="space-y-1 text-sm text-fg">
              <li>desk-copilot (designed)</li>
              <li>receipt_issued · si/ta/en</li>
              <li>otp_request · si/ta/en</li>
            </ul>
          </Card>
        </section>
      </div>
    </div>
  );
}
