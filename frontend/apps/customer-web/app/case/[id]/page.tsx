"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { Badge, Button, Card } from "@clarity/ui";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLanguage } from "@/components/LanguageProvider";
import { WhyWidget } from "@/components/WhyWidget";

const client = new ClarityClient();

export default function CaseDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const { lang } = useLanguage();
  const [caseData, setCaseData] = useState<Record<string, unknown> | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token =
          typeof window !== "undefined"
            ? window.sessionStorage.getItem("clarity_token") ?? undefined
            : undefined;
        client.setToken(token);
        const data = await client.getCase(params.id);
        if (!cancelled) setCaseData(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Could not load case",
          );
          setCaseData({
            case_id: params.id,
            state: "OPEN",
            cause: "VAS silent renewal",
            amount: "99.00",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  const cause =
    (caseData?.cause as string) ??
    (caseData?.primary_cause as string) ??
    "Investigating…";
  const amount = String(caseData?.amount ?? "99.00");
  const state = String(caseData?.state ?? "OPEN");

  return (
    <main className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs text-slate-500">Case</p>
          <h1 className="font-mono text-lg">{params.id}</h1>
        </div>
        <LanguageSwitcher />
      </header>

      <Card className="space-y-3">
        <div className="flex items-center gap-2">
          <Badge tone={state === "OPEN" ? "warning" : "success"}>
            {state}
          </Badge>
          {error ? <Badge tone="neutral">Offline placeholder</Badge> : null}
        </div>
        <h2 className="text-lg font-medium">{t(lang, "why.heading")}</h2>
        <WhyWidget cause={cause} amount={amount} />
        <Button>{t(lang, "fix.cta")}</Button>
      </Card>

      <div className="flex gap-3 text-sm">
        <Link href="/" className="text-sky-700 hover:underline">
          ← Home
        </Link>
        <Link
          href="/receipt/TR-demo"
          className="text-sky-700 hover:underline"
        >
          {t(lang, "receipt.verify")}
        </Link>
      </div>
    </main>
  );
}
