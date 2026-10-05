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
 *
 * **MCP card opens the Inspector.** It does not list tools in-console; it
 * deep-links the MCP Inspector to `clarity-mcp` (Streamable HTTP) so staff
 * connect and explore tools in the real MCP UI (WT-10).
 */

const DEFAULT_KEYS = [
  "auto_fix_global",
  "customer_actions",
  "llm_explanations",
  "proactive_messages",
];

/** Streamable HTTP endpoint for `make mcp` (override with NEXT_PUBLIC_MCP_URL). */
const MCP_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_MCP_URL) ||
  "http://127.0.0.1:8099/mcp";

/** MCP Inspector web UI (override with NEXT_PUBLIC_MCP_INSPECTOR_URL). */
const MCP_INSPECTOR_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_MCP_INSPECTOR_URL) ||
  "http://127.0.0.1:6274";

function mcpInspectorHref(serverUrl: string, inspectorBase: string): string {
  const url = new URL(inspectorBase);
  url.searchParams.set("transport", "streamable-http");
  url.searchParams.set("serverUrl", serverUrl);
  return url.toString();
}

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
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [switchFilter, setSwitchFilter] = useState<"all" | "on" | "off">("all");
  const [switchQuery, setSwitchQuery] = useState("");
  const [mcpCopied, setMcpCopied] = useState(false);

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

  const inspectorHref = mcpInspectorHref(MCP_URL, MCP_INSPECTOR_URL);

  async function copyMcpUrl() {
    try {
      await navigator.clipboard.writeText(MCP_URL);
      setMcpCopied(true);
      window.setTimeout(() => setMcpCopied(false), 2000);
    } catch {
      setMcpCopied(false);
    }
  }

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

  const needle = switchQuery.trim().toLowerCase();
  const visibleSwitches = switches.filter((sw) => {
    if (switchFilter === "on" && !sw.enabled) return false;
    if (switchFilter === "off" && sw.enabled) return false;
    if (needle && !sw.key.toLowerCase().includes(needle)) return false;
    return true;
  });
  const selected = visibleSwitches.find((sw) => sw.key === selectedKey) ?? visibleSwitches[0] ?? null;
  const onCount = switches.filter((sw) => sw.enabled).length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-display text-3xl font-semibold tracking-tight">Admin</h1>
            <span className="rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-medium text-primary">
              {switches.length} switches
            </span>
          </div>
          <p className="mt-1 text-sm text-fg-muted">
            Kill switches degrade journeys; they never invent money.
          </p>
        </div>
        <label className="w-full max-w-sm">
          <span className="sr-only">Search switches</span>
          <input
            value={switchQuery}
            onChange={(event) => setSwitchQuery(event.target.value)}
            placeholder="Search switches"
            className="w-full rounded-full border border-line bg-surface px-4 py-2 text-sm text-ink outline-none ring-focus focus:ring-2"
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter switches">
        {(
          [
            { id: "all", label: "All" },
            { id: "on", label: "On" },
            { id: "off", label: "Off" },
          ] as const
        ).map((item) => {
          const selectedFilter = switchFilter === item.id;
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={selectedFilter}
              onClick={() => setSwitchFilter(item.id)}
              className={`rounded-full px-3 py-1.5 text-sm ${
                selectedFilter ? "bg-surface font-medium text-ink shadow-1" : "text-fg-muted hover:bg-surface"
              }`}
            >
              {item.label}
              {item.id === "on" ? (
                <span className="ml-1.5 text-xs text-fg-subtle">{onCount}</span>
              ) : null}
            </button>
          );
        })}
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

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-labelledby="admin-switches">
          <Card className="!p-0 overflow-hidden rounded-card border-line bg-surface shadow-card">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <h2 id="admin-switches" className="text-sm font-medium">
                Kill switches
              </h2>
              {canFlip ? <Badge tone="success">can flip</Badge> : <Badge>read-only</Badge>}
            </div>
            <div className="hidden border-b border-line px-4 py-2 text-xs font-medium text-fg-subtle sm:grid sm:grid-cols-[minmax(0,1fr)_5rem_6rem] sm:gap-3">
              <span>Switch</span>
              <span>Status</span>
              <span>Action</span>
            </div>
            {!visibleSwitches.length ? (
              <p className="px-4 py-6 text-sm text-mute">No switch matches this search.</p>
            ) : (
              <ul>
                {visibleSwitches.map((sw) => {
                  const open = selected?.key === sw.key;
                  return (
                    <li key={sw.key} className="border-b border-line last:border-b-0">
                      <div
                        className={`grid gap-2 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_5rem_6rem] sm:items-center sm:gap-3 ${
                          open ? "bg-primary-soft" : ""
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => setSelectedKey(sw.key)}
                          aria-current={open ? "true" : undefined}
                          className="text-left font-mono text-xs text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                        >
                          {sw.key}
                        </button>
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
                        ) : (
                          <span className="text-xs text-fg-subtle">Read only</span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
            {!canFlip ? (
              <p className="border-t border-line px-4 py-3 text-xs text-fg-muted">
                Read-only for this role (needs flags:kill_switch to flip).
              </p>
            ) : null}
          </Card>
        </section>

        <section aria-labelledby="admin-switch-detail">
          <Card className="space-y-4 rounded-card border-line bg-surface shadow-card xl:sticky xl:top-6">
            <h2 id="admin-switch-detail" className="text-xs font-semibold uppercase tracking-[0.14em] text-mute">
              Switch
            </h2>
            {selected ? (
              <>
                <div className="flex items-start justify-between gap-3 border-b border-line pb-4">
                  <p className="font-mono text-sm font-medium text-ink">{selected.key}</p>
                  <Badge tone={selected.enabled ? "success" : "danger"}>
                    {selected.enabled ? "on" : "off"}
                  </Badge>
                </div>
                <p className="text-sm text-fg-muted">
                  {selected.enabled
                    ? "This journey is running. Turning it off degrades it for every customer at once."
                    : "This journey is degraded. Turning it on lets it run again. Cases already handled stay as they are."}
                </p>
                {canFlip ? (
                  <Button
                    variant={selected.enabled ? "danger" : "primary"}
                    disabled={busy}
                    aria-label={`${selected.enabled ? "Turn off" : "Turn on"} ${selected.key}`}
                    onClick={() => setPending({ key: selected.key, enabled: !selected.enabled })}
                  >
                    {selected.enabled ? "Turn off" : "Turn on"}
                  </Button>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-mute">No switch is loaded.</p>
            )}
            <div>
              <h3 className="text-sm font-medium text-fg-muted">Recent flips</h3>
              <ul className="mt-2 max-h-48 space-y-2 overflow-auto text-xs text-fg-muted">
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
            </div>
          </Card>
        </section>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
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

        <section aria-labelledby="admin-mcp">
          <Card className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id="admin-mcp" className="font-medium">
                MCP Inspector
              </h2>
              <Badge tone="neutral">Streamable HTTP</Badge>
            </div>
            <p className="text-sm text-fg-muted">
              Connect the MCP Inspector to{" "}
              <code className="text-xs">clarity-mcp</code>. Tools stay in the
              Inspector UI; no tool here executes money or service changes.
            </p>
            <div className="rounded-xl border border-line bg-bg px-3 py-2">
              <p className="text-xs font-medium text-fg-subtle">Server URL</p>
              <p className="mt-1 break-all font-mono text-xs text-ink">{MCP_URL}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                onClick={() => window.open(inspectorHref, "_blank", "noopener,noreferrer")}
              >
                Open MCP Inspector
              </Button>
              <Button variant="ghost" onClick={() => void copyMcpUrl()}>
                {mcpCopied ? "Copied" : "Copy server URL"}
              </Button>
            </div>
            <ol className="list-decimal space-y-1 pl-4 text-xs text-fg-muted">
              <li>
                Run <code className="text-xs">make mcp</code> (serves{" "}
                <code className="text-xs">{MCP_URL}</code>).
              </li>
              <li>
                Run{" "}
                <code className="text-xs">npx @modelcontextprotocol/inspector</code>{" "}
                (UI on <code className="text-xs">{MCP_INSPECTOR_URL}</code>).
              </li>
              <li>
                Open the button above, or paste the server URL with transport{" "}
                <code className="text-xs">streamable-http</code>.
              </li>
              <li>Authenticate with a staff-assist token (WT-10). Deny by default without one.</li>
            </ol>
            <p className="text-xs text-fg-muted">
              Walkthrough:{" "}
              <code className="text-xs">docs/walkthroughs/WT-10-external-mcp-client.md</code>
              .
            </p>
          </Card>
        </section>
      </div>
    </div>
  );
}
