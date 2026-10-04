"use client";

import { useEffect, useState } from "react";
import { ClarityApiError, ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { Badge, Card } from "@clarity/ui";

const client = new ClarityClient();

/**
 * The page a Trust Receipt's QR code opens (FE01, replacing the static
 * `verify.html`).
 *
 * **It must never claim a receipt is valid unless the backend said so.** The
 * first version of this page fell back to a "placeholder" verdict whenever the
 * call failed, and that verdict was *valid* for any id not containing the
 * string "bad". So an unknown receipt, a tampered id and an unreachable API
 * all rendered "Chain valid" with a green badge. On the one page whose whole
 * job is to prove a receipt is genuine, a fabricated pass is worse than no
 * page at all, and the static page it replaces got this right: it showed an
 * error on a 404.
 *
 * There are three outcomes here, and "could not check" is a real one:
 *
 * | Backend                      | Shown              |
 * |------------------------------|--------------------|
 * | `valid: true`                | Chain valid        |
 * | `valid: false`               | Chain invalid      |
 * | 404, or no answer at all     | Could not check    |
 */

type Verdict =
  | { phase: "checking" }
  | {
      phase: "checked";
      valid: boolean;
      chainOk: boolean;
      status: string;
      reason: string;
      keyId?: string;
    }
  | { phase: "unchecked"; missing: boolean; detail: string };

export default function VerifyReceiptPage({
  params,
}: {
  params: { id: string };
}) {
  const [state, setState] = useState<Verdict>({ phase: "checking" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await client.verifyReceipt(params.id);
        if (cancelled) return;
        setState({
          phase: "checked",
          // Explicitly `=== true`. The old code read `valid ?? chain_ok ?? true`,
          // so a response missing both fields also counted as valid.
          valid: data.valid === true,
          chainOk: data.chain_ok === true,
          status: typeof data.status === "string" ? data.status : "UNKNOWN",
          reason: typeof data.reason === "string" ? data.reason : "",
          // `key_id`, not `kid`: the API has always sent the former, so the
          // key id never rendered.
          keyId: typeof data.key_id === "string" ? data.key_id : undefined,
        });
      } catch (err) {
        if (cancelled) return;
        setState({
          phase: "unchecked",
          missing: err instanceof ClarityApiError && err.status === 404,
          detail: err instanceof Error ? err.message : "the service did not answer",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  const valid = state.phase === "checked" && state.valid;

  return (
    <main className="space-y-6">
      <header className="space-y-1 text-center">
        <p className="text-xs uppercase tracking-wide text-slate-500">
          Hutch Clarity
        </p>
        <h1 className="text-2xl font-semibold">{t("en", "receipt.verify")}</h1>
      </header>

      <Card className="space-y-4 text-center">
        {state.phase === "checking" ? (
          <p className="text-sm text-slate-500">Checking chain...</p>
        ) : state.phase === "unchecked" ? (
          <div
            className="space-y-2"
            data-testid="verify-result"
            data-verified="unchecked"
          >
            <Badge tone="warning" className="text-sm">
              Could not check
            </Badge>
            <p className="font-mono text-sm text-slate-600">{params.id}</p>
            <p className="text-base">
              {state.missing
                ? `No receipt numbered ${params.id} has ever been issued.`
                : "This receipt could not be checked right now."}
            </p>
            <p className="text-xs text-slate-500">
              {state.missing
                ? "Check the number on your receipt, or scan the QR code again."
                : `The verification service did not answer (${state.detail}). Nothing here says whether the receipt is genuine.`}
            </p>
          </div>
        ) : (
          <div
            className="space-y-4"
            data-testid="verify-result"
            data-verified={String(valid)}
          >
            <Badge tone={valid ? "success" : "danger"} className="text-sm">
              {valid ? "Chain valid" : "Chain invalid"}
            </Badge>
            <p className="font-mono text-sm text-slate-600">{params.id}</p>
            <p className="text-base">{state.reason || state.status}</p>
            <dl className="mx-auto grid max-w-xs grid-cols-2 gap-2 text-left text-sm text-slate-600">
              <dt>Status</dt>
              <dd>{state.status}</dd>
              <dt>Signature</dt>
              <dd>{valid ? "OK" : "Failed"}</dd>
              <dt>Chain</dt>
              <dd>{state.chainOk ? "Intact" : "Broken"}</dd>
              {state.keyId ? (
                <>
                  <dt>Key id</dt>
                  <dd className="font-mono">{state.keyId}</dd>
                </>
              ) : null}
            </dl>
          </div>
        )}
      </Card>
    </main>
  );
}
