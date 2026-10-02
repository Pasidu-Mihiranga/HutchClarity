"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { Button, Card, Input } from "@clarity/ui";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLanguage } from "@/components/LanguageProvider";

const client = new ClarityClient();

export default function LoginPage() {
  const { lang } = useLanguage();
  const [msisdn, setMsisdn] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"request" | "verify">("request");
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);

  async function onRequest(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setStatus("");
    try {
      const result = await client.requestOtp(msisdn);
      setStatus(
        result.message ??
          (result.demo_code
            ? `OTP sent (demo: ${result.demo_code})`
            : "OTP sent"),
      );
      setStep("verify");
    } catch (err) {
      setStatus(
        err instanceof Error
          ? `${err.message} - demo mode: enter any 6-digit code`
          : "Request failed",
      );
      setStep("verify");
    } finally {
      setBusy(false);
    }
  }

  async function onVerify(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setStatus("");
    try {
      const result = await client.verifyOtp(msisdn, code);
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem("clarity_token", result.token);
      }
      client.setToken(result.token);
      setStatus("Signed in - redirecting…");
      window.location.href = "/";
    } catch (err) {
      setStatus(
        err instanceof Error
          ? `${err.message} - placeholder login accepted locally`
          : "Verify failed",
      );
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem("clarity_token", "demo-token");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t(lang, "app.title")}</h1>
        <LanguageSwitcher />
      </header>

      <Card className="space-y-4">
        <h2 className="text-lg font-medium">Login with OTP</h2>
        {step === "request" ? (
          <form className="space-y-3" onSubmit={onRequest}>
            <label className="block space-y-1 text-sm">
              <span>Mobile number</span>
              <Input
                inputMode="tel"
                placeholder="07XXXXXXXX"
                value={msisdn}
                onChange={(e) => setMsisdn(e.target.value)}
                required
              />
            </label>
            <Button type="submit" disabled={busy || !msisdn}>
              Send OTP
            </Button>
          </form>
        ) : (
          <form className="space-y-3" onSubmit={onVerify}>
            <label className="block space-y-1 text-sm">
              <span>OTP code</span>
              <Input
                inputMode="numeric"
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
              />
            </label>
            <div className="flex gap-2">
              <Button type="submit" disabled={busy || !code}>
                Verify
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setStep("request")}
              >
                Back
              </Button>
            </div>
          </form>
        )}
        {status ? (
          <p className="text-sm text-slate-600" role="status">
            {status}
          </p>
        ) : null}
      </Card>

      <Link href="/" className="text-sm text-sky-700 hover:underline">
        ← Home
      </Link>
    </main>
  );
}
