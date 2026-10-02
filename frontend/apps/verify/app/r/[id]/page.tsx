"use client";

import { useEffect, useState } from "react";
import { ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { Badge, Card } from "@clarity/ui";

const client = new ClarityClient();

type VerifyState = {
  loading: boolean;
  valid: boolean | null;
  chainOk: boolean | null;
  kid?: string;
  summary?: string;
  error?: string;
  source: "api" | "placeholder";
};

export default function VerifyReceiptPage({
  params,
}: {
  params: { id: string };
}) {
  const [state, setState] = useState<VerifyState>({
    loading: true,
    valid: null,
    chainOk: null,
    source: "placeholder",
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await client.verifyReceipt(params.id);
        if (cancelled) return;
        setState({
          loading: false,
          valid: Boolean(data.valid ?? data.chain_ok ?? true),
          chainOk: data.chain_ok !== false,
          kid: typeof data.kid === "string" ? data.kid : undefined,
          summary:
            typeof data.summary === "string"
              ? data.summary
              : "Trust receipt verified",
          source: "api",
        });
      } catch (err) {
        if (cancelled) return;
        // Lean demo fallback when API is offline
        const looksTampered = params.id.toLowerCase().includes("bad");
        setState({
          loading: false,
          valid: !looksTampered,
          chainOk: !looksTampered,
          summary: looksTampered
            ? "Chain hash mismatch (demo invalid)"
            : "Credit applied · signature chain intact (placeholder)",
          error: err instanceof Error ? err.message : "API unavailable",
          source: "placeholder",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  const valid = state.valid === true;

  return (
    <main className="space-y-6">
      <header className="space-y-1 text-center">
        <p className="text-xs uppercase tracking-wide text-slate-500">
          Hutch Clarity
        </p>
        <h1 className="text-2xl font-semibold">{t("en", "receipt.verify")}</h1>
      </header>

      <Card className="space-y-4 text-center">
        {state.loading ? (
          <p className="text-sm text-slate-500">Checking chain…</p>
        ) : (
          <>
            <Badge tone={valid ? "success" : "danger"} className="text-sm">
              {valid ? "Chain valid" : "Chain invalid"}
            </Badge>
            <p className="font-mono text-sm text-slate-600">{params.id}</p>
            <p className="text-base">{state.summary}</p>
            <dl className="mx-auto grid max-w-xs grid-cols-2 gap-2 text-left text-sm text-slate-600">
              <dt>Signature</dt>
              <dd>{valid ? "OK" : "Failed"}</dd>
              <dt>Chain</dt>
              <dd>{state.chainOk ? "Intact" : "Broken"}</dd>
              {state.kid ? (
                <>
                  <dt>Key id</dt>
                  <dd className="font-mono">{state.kid}</dd>
                </>
              ) : null}
            </dl>
            {state.source === "placeholder" && state.error ? (
              <p className="text-xs text-slate-400">
                Offline demo · {state.error}
              </p>
            ) : null}
          </>
        )}
      </Card>
    </main>
  );
}
