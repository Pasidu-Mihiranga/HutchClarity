"use client";

import Link from "next/link";
import { t } from "@clarity/i18n";
import { Badge, Button, Card } from "@clarity/ui";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLanguage } from "@/components/LanguageProvider";
import { WhyWidget } from "@/components/WhyWidget";

export default function HomePage() {
  const { lang } = useLanguage();

  return (
    <main className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Hutch
          </p>
          <h1 className="text-2xl font-semibold text-slate-900">
            {t(lang, "app.title")}
          </h1>
        </div>
        <LanguageSwitcher />
      </header>

      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">{t(lang, "why.heading")}</h2>
          <Badge tone="warning">Placeholder</Badge>
        </div>
        <WhyWidget
          cause="VAS auto-renewed without notice"
          amount="99.00"
          onFix={() => {
            window.location.href = "/case/demo-case-1";
          }}
        />
      </Card>

      <div className="flex flex-wrap gap-2">
        <Link href="/login">
          <Button variant="secondary">Login (OTP)</Button>
        </Link>
        <Link href="/case/demo-case-1">
          <Button variant="ghost">Case detail</Button>
        </Link>
        <Link href="/receipt/TR-demo">
          <Button variant="ghost">{t(lang, "receipt.verify")}</Button>
        </Link>
      </div>
    </main>
  );
}
