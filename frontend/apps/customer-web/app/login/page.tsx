"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { Alert, Button, Field, Input } from "@clarity/ui";
import { useLanguage } from "@/components/LanguageProvider";
import { safeNext } from "@/lib/session";

const client = new ClarityClient();

export default function LoginPage() {
  const { lang } = useLanguage();
  const router = useRouter();
  const [msisdn, setMsisdn] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"request" | "verify">("request");
  const [status, setStatus] = useState<{ text: string; tone: "ok" | "info" } | null>(null);
  const [busy, setBusy] = useState(false);
  // The code from the simulated inbox. There is no "any six digits" path: the
  // backend generates a code per challenge and refuses anything else, so the
  // panel below has to show the real one or nobody can sign in.
  const [demoCode, setDemoCode] = useState<string | null>(null);
  const [simulatedDelivery, setSimulatedDelivery] = useState(false);
  // `verifyOtp` needs the challenge this code belongs to, not the number.
  const [challengeId, setChallengeId] = useState<string | null>(null);

  async function onRequest(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setStatus(null);
    try {
      const result = await client.requestOtp(msisdn);
      setChallengeId(result.challenge_id);
      setSimulatedDelivery(result.simulated === true);
      setStatus({
        text: result.detail ?? result.message ?? "OTP sent to your number.",
        tone: "ok",
      });
      setStep("verify");
      // Read the simulated SMS back and prefill it. Synthetic profiles only;
      // the route 404s in prod, so a failure here is not an error worth
      // showing, it just means there is no inbox to read.
      try {
        const message = await client.demoInbox(msisdn);
        if (message.code) {
          setDemoCode(message.code);
          setCode(message.code);
        }
      } catch {
        setDemoCode(null);
      }
    } catch (err) {
      setSimulatedDelivery(false);
      setDemoCode(null);
      setStatus({
        text: err instanceof Error ? err.message : "Request failed",
        tone: "info",
      });
    } finally { setBusy(false); }
  }

  async function onVerify(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setStatus(null);
    try {
      if (!challengeId) throw new Error("Request a code first.");
      const result = await client.verifyOtp(challengeId, code);
      // The API set an HttpOnly session cookie on this response (B4); there is
      // nothing for the page to store, and nothing a script can read.
      client.setToken(result.token);
      setStatus({ text: "Signed in - redirecting...", tone: "ok" });
      // Back to where an expired session sent us from (lib/session.ts).
      router.push(safeNext(new URLSearchParams(window.location.search).get("next")));
    } catch (err) {
      // A failed sign-in used to write `clarity_token = "demo-token"` and say
      // "placeholder login accepted locally". That turned a rejected code into
      // a half-signed-in state: every later call carried a token the backend
      // refuses, so the customer saw errors everywhere except at the point
      // where something actually went wrong. Deny by default (I9) applies to
      // the UI too, so a refusal clears the session rather than inventing one.
      // Nothing to clear: the session cookie is the API's to remove.
      client.setToken(undefined);
      setStatus({
        text: err instanceof Error ? err.message : "Verify failed",
        tone: "info",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      style={{
        maxWidth: 420,
        margin: "0 auto",
        padding: "40px 0",
        display: "flex",
        flexDirection: "column",
        minHeight: "80vh",
        justifyContent: "center",
      }}
    >
      {/* Title */}
      <div style={{ marginBottom: 28 }}>
        <p style={{ margin: "0 0 4px", fontSize: 12, textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)" }}>Hutch</p>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, letterSpacing: "-.03em" }}>
          {t(lang, "app.title")}
        </h1>
      </div>

      <div className="h-card">
        {/* Step indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 4 }}>
            <span style={{ height: 4, width: 24, borderRadius: 999, background: "var(--orange)" }} />
            <span style={{ height: 4, width: 24, borderRadius: 999, background: step === "verify" ? "var(--orange)" : "var(--line)" }} />
          </div>
          <p style={{ margin: 0, fontSize: 12, color: "var(--muted)" }}>
            {step === "request" ? "Step 1 of 2 - Enter your number" : "Step 2 of 2 - Enter your OTP"}
          </p>
        </div>

        {step === "request" ? (
          <form onSubmit={onRequest} style={{ display: "grid", gap: 14 }}>
            <Field label="Hutch number">
              {(control) => (
                <Input
                  {...control}
                  name="msisdn"
                  autoComplete="tel"
                  inputMode="tel"
                  placeholder="07XXXXXXXX"
                  value={msisdn}
                  onChange={(e) => setMsisdn(e.target.value)}
                  required
                  className="rounded-[14px] px-4 py-3 text-[15px]"
                />
              )}
            </Field>
            <Button type="submit" pill size="lg" loading={busy} disabled={!msisdn} className="w-full">
              Continue
            </Button>
          </form>
        ) : (
          <form onSubmit={onVerify} style={{ display: "grid", gap: 14 }}>
            <Field label="6-digit code">
              {(control) => (
                <Input
                  {...control}
                  name="otp"
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  placeholder="123456"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                  maxLength={6}
                  className="rounded-[14px] px-3 py-2.5 font-mono text-2xl tracking-[.32em]"
                />
              )}
            </Field>
            <div style={{ display: "flex", gap: 8 }}>
              <Button type="submit" pill size="lg" loading={busy} disabled={!code} className="flex-1">
                Sign in
              </Button>
              <Button
                type="button"
                variant="secondary"
                pill
                size="lg"
                onClick={() => { setStep("request"); setStatus(null); }}
              >
                Back
              </Button>
            </div>
          </form>
        )}

        {status && (
          <Alert tone={status.tone === "ok" ? "success" : "info"} className="mt-3.5">
            {status.text}
          </Alert>
        )}
      </div>

      {/* Synthetic-profile inbox, shown only when this request used it. */}
      {simulatedDelivery && <div
        data-testid="simulated-sms-inbox"
        style={{
          marginTop: 16,
          border: "1px dashed var(--warn)",
          borderRadius: 10,
          background: "rgb(var(--c-warning-soft))",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            background: "var(--warn)",
            color: "rgb(var(--c-on-primary))",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: ".03em",
            textTransform: "uppercase",
            padding: "5px 10px",
          }}
        >
          Simulated SMS inbox
        </div>
        <p style={{ margin: 0, padding: 12, fontSize: 14, color: "var(--ink)" }}>
          {demoCode ? (
            <>
              Your code is{" "}
              <strong data-testid="demo-otp-code" style={{ letterSpacing: ".1em" }}>
                {demoCode}
              </strong>
              . It has been filled in for you.
            </>
          ) : (
            "Enter your Hutch number to receive a simulated code here."
          )}
        </p>
      </div>}
    </main>
  );
}
