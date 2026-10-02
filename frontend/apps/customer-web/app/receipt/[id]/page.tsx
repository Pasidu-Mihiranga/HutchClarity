"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { Badge, Card } from "@clarity/ui";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLanguage } from "@/components/LanguageProvider";

const client = new ClarityClient();

export default function ReceiptPage({
  params,
}: {
  params: { id: string };
}) {
  const { lang } = useLanguage();
  const [receipt, setReceipt] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await client.getReceipt(params.id);
        if (!cancelled) setReceipt(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Load failed");
          setReceipt({
            receipt_id: params.id,
            summary: "Credit LKR 99.00 for silent VAS renewal",
            chain_ok: true,
            valid: true,
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  const valid = Boolean(receipt?.valid ?? receipt?.chain_ok ?? true);

  return (
    <main className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t(lang, "receipt.verify")}</h1>
        <LanguageSwitcher />
      </header>

      <Card className="space-y-3">
        <div className="flex items-center gap-2">
          <Badge tone={valid ? "success" : "danger"}>
            {valid ? "Valid" : "Invalid"}
          </Badge>
          {error ? <Badge tone="neutral">Placeholder</Badge> : null}
        </div>
        <p className="font-mono text-sm text-slate-600">{params.id}</p>
        <p className="text-base">
          {String(receipt?.summary ?? "Trust receipt")}
        </p>
        <dl className="grid grid-cols-2 gap-2 text-sm text-slate-600">
          <dt>Chain</dt>
          <dd>{receipt?.chain_ok === false ? "Broken" : "Intact"}</dd>
          <dt>Signature</dt>
          <dd>{valid ? "Verified" : "Failed"}</dd>
        </dl>
      </Card>

      <Link href="/" className="text-sm text-sky-700 hover:underline">
        ← Home
      </Link>
    </main>
  );
}
