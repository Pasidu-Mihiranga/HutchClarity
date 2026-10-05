"use client";

/**
 * IAM role policies (ADR-0045).
 *
 * Platform admin views the closed role→permission matrix and attaches or
 * detaches permissions on top of the checked-in baseline. Money permissions
 * cannot land on admin roles; locked permissions stay baseline-only. The API
 * refuses both; this page hides the illegal options rather than offering a
 * click that fails.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  Field,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Textarea,
} from "@clarity/ui";
import type { IamRoleCatalogue, IamRoleRow } from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { PageHeader } from "@/components/PageHeader";
import { useStaffSession } from "@/components/StaffSessionProvider";

type PendingChange = {
  operation: "attach" | "detach";
  role: string;
  permission: string;
};

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `iam-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function IamPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const canManage = hasPermission("iam:role:manage");

  const [catalogue, setCatalogue] = useState<IamRoleCatalogue | null>(null);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingChange | null>(null);
  const [reason, setReason] = useState("");
  const [attachPermission, setAttachPermission] = useState("");

  const load = useCallback(async () => {
    if (!canManage) return;
    setError(null);
    try {
      const next = await client.listIamRoles();
      setCatalogue(next);
      setSelectedRole((current) => {
        if (current && next.roles.some((row) => row.role === current)) {
          return current;
        }
        return next.roles[0]?.role ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load IAM roles");
    }
  }, [canManage, client]);

  useEffect(() => {
    void load();
  }, [load, generation]);

  const row: IamRoleRow | null = useMemo(() => {
    if (!catalogue || !selectedRole) return null;
    return catalogue.roles.find((item) => item.role === selectedRole) ?? null;
  }, [catalogue, selectedRole]);

  const attachable = useMemo(() => {
    if (!catalogue || !row) return [];
    const locked = new Set(catalogue.locked_permissions);
    const money = new Set(catalogue.money_permissions);
    const effective = new Set(row.effective);
    return catalogue.permissions.filter((permission) => {
      if (effective.has(permission)) return false;
      if (locked.has(permission)) return false;
      if (row.is_admin && money.has(permission)) return false;
      return true;
    });
  }, [catalogue, row]);

  const detachable = useMemo(() => {
    if (!catalogue || !row) return [];
    const locked = new Set(catalogue.locked_permissions);
    return row.effective.filter((permission) => !locked.has(permission));
  }, [catalogue, row]);

  useEffect(() => {
    if (attachable.length === 0) {
      setAttachPermission("");
      return;
    }
    if (!attachable.includes(attachPermission)) {
      setAttachPermission(attachable[0] ?? "");
    }
  }, [attachable, attachPermission]);

  function openChange(operation: "attach" | "detach", permission: string) {
    if (!row) return;
    setPending({ operation, role: row.role, permission });
    setReason("");
    setMessage(null);
    setError(null);
  }

  async function confirmChange() {
    if (!pending || !reason.trim()) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const body = {
        role: pending.role,
        permission: pending.permission,
        reason: reason.trim(),
      };
      const key = newIdempotencyKey();
      const result =
        pending.operation === "attach"
          ? await client.attachIamPermission(body, key)
          : await client.detachIamPermission(body, key);
      setMessage(
        `${result.operation} ${result.permission} on ${result.role}` +
          (result.replayed ? " (replayed)" : ""),
      );
      setPending(null);
      setReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "IAM change failed");
    } finally {
      setBusy(false);
    }
  }

  if (!session || !canManage) {
    return <AccessDenied need="iam:role:manage" />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="IAM"
        description="Attach or detach closed permissions on staff roles. Overrides sit on the checked-in baseline; money stays off admin roles."
        meta={
          catalogue ? (
            <Badge tone="neutral">{catalogue.roles.length} roles</Badge>
          ) : null
        }
      />

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <Card className="space-y-2 p-4">
          <h2 className="text-sm font-semibold text-ink">Roles</h2>
          <ul className="space-y-1" aria-label="Staff roles">
            {(catalogue?.roles ?? []).map((item) => {
              const active = item.role === selectedRole;
              return (
                <li key={item.role}>
                  <button
                    type="button"
                    className={
                      "w-full rounded-md px-3 py-2 text-left text-sm " +
                      (active
                        ? "bg-primary-soft font-medium text-ink"
                        : "text-mute hover:bg-surface-2 hover:text-ink")
                    }
                    aria-current={active ? "true" : undefined}
                    onClick={() => setSelectedRole(item.role)}
                  >
                    <span className="block">{item.role}</span>
                    <span className="block text-xs text-mute">
                      {item.effective.length} effective
                      {item.is_admin ? " · admin" : ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Card>

        <Card className="space-y-5 p-5">
          {!row ? (
            <p className="text-sm text-mute">Select a role to inspect its permissions.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-display text-xl font-semibold text-ink">{row.role}</h2>
                {row.is_admin ? <Badge tone="warning">admin SoD</Badge> : null}
                {(row.attached.length > 0 || row.detached.length > 0) ? (
                  <Badge tone="neutral">has overrides</Badge>
                ) : (
                  <Badge tone="success">baseline only</Badge>
                )}
              </div>

              <section className="space-y-2" aria-labelledby="iam-effective">
                <h3 id="iam-effective" className="text-sm font-semibold text-ink">
                  Effective permissions
                </h3>
                <Table
                  caption={`Effective permissions for ${row.role}`}
                  scrollLabel="Effective permissions"
                >
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Permission</TableHeaderCell>
                      <TableHeaderCell>Source</TableHeaderCell>
                      <TableHeaderCell>Action</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {row.effective.map((permission) => {
                      const fromAttach = row.attached.includes(permission);
                      const locked = catalogue?.locked_permissions.includes(permission);
                      const canDetach = detachable.includes(permission);
                      return (
                        <TableRow key={permission}>
                          <TableCell>
                            <code className="text-xs">{permission}</code>
                          </TableCell>
                          <TableCell>
                            {fromAttach ? "attached" : locked ? "baseline (locked)" : "baseline"}
                          </TableCell>
                          <TableCell>
                            {canDetach ? (
                              <Button
                                size="sm"
                                variant="danger"
                                disabled={busy}
                                onClick={() => openChange("detach", permission)}
                              >
                                Detach
                              </Button>
                            ) : (
                              <span className="text-xs text-mute">locked</span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </section>

              {row.detached.length > 0 ? (
                <section className="space-y-2" aria-labelledby="iam-detached">
                  <h3 id="iam-detached" className="text-sm font-semibold text-ink">
                    Detached (override)
                  </h3>
                  <ul className="flex flex-wrap gap-2">
                    {row.detached.map((permission) => (
                      <li key={permission}>
                        <Badge tone="warning">{permission}</Badge>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <section className="space-y-3" aria-labelledby="iam-attach">
                <h3 id="iam-attach" className="text-sm font-semibold text-ink">
                  Attach permission
                </h3>
                {attachable.length === 0 ? (
                  <p className="text-sm text-mute">
                    Nothing else can be attached to this role under the SoD rules.
                  </p>
                ) : (
                  <div className="flex flex-wrap items-end gap-3">
                    <Field label="Permission" className="min-w-[16rem] flex-1">
                      {(control) => (
                        <Select
                          {...control}
                          value={attachPermission}
                          onChange={(event) => setAttachPermission(event.target.value)}
                        >
                          {attachable.map((permission) => (
                            <option key={permission} value={permission}>
                              {permission}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>
                    <Button
                      disabled={busy || !attachPermission}
                      onClick={() => openChange("attach", attachPermission)}
                    >
                      Attach...
                    </Button>
                  </div>
                )}
              </section>
            </>
          )}
        </Card>
      </div>

      <Dialog
        open={pending !== null}
        onClose={() => {
          if (!busy) setPending(null);
        }}
        title={
          pending
            ? `${pending.operation === "attach" ? "Attach" : "Detach"} ${pending.permission}`
            : "Confirm IAM change"
        }
        description={
          pending
            ? `Role ${pending.role}. A reason is required and is written to the audit trail.`
            : undefined
        }
        dismissOnBackdrop={false}
        footer={
          <>
            <Button variant="ghost" disabled={busy} onClick={() => setPending(null)}>
              Cancel
            </Button>
            <Button
              data-autofocus
              disabled={busy || !reason.trim()}
              loading={busy}
              onClick={() => void confirmChange()}
            >
              {pending?.operation === "attach" ? "Attach" : "Detach"}
            </Button>
          </>
        }
      >
        <Field label="Reason">
          {(control) => (
            <Textarea
              {...control}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={3}
              placeholder="Why this role needs this change"
            />
          )}
        </Field>
      </Dialog>
    </div>
  );
}
