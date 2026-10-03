"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ClarityClient } from "@clarity/sdk";
import { t } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";

const client = new ClarityClient();

export default function LoginPage() {
  const { lang } = useLanguage();
  const router = useRouter();
  const [msisdn, setMsisdn] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"request" | "verify">("request");
  const [status, setStatus] = useState<{ text: string; tone: "ok" | "info" } | null>(null);
  const [busy, setBusy] = useState(false);

  async function onRequest(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setStatus(null);
    try {
      const result = await client.requestOtp(msisdn);
      setStatus({
        text: result.message ?? (result.demo_code ? `OTP sent (demo: ${result.demo_code})` : "OTP sent to your number."),
        tone: "ok",
      });
      setStep("verify");
    } catch (err) {
      setStatus({
        text: err instanceof Error
          ? `${err.message} - demo mode: enter any 6-digit code`
          : "Request failed",
        tone: "info",
      });
      setStep("verify");
    } finally { setBusy(false); }
  }

  async function onVerify(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setStatus(null);
    try {
      const result = await client.verifyOtp(msisdn, code);
      try { window.sessionStorage.setItem("clarity_token", result.token); } catch {}
      client.setToken(result.token);
      setStatus({ text: "Signed in - redirecting...", tone: "ok" });
      router.push("/");
    } catch (err) {
      setStatus({
        text: err instanceof Error
          ? `${err.message} - placeholder login accepted locally`
          : "Verify failed",
        tone: "info",
      });
      try { window.sessionStorage.setItem("clarity_token", "demo-token"); } catch {}
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
            <div>
              <label
                htmlFor="msisdn"
                style={{ display: "block", fontSize: 13, color: "var(--muted)", marginBottom: 6 }}
              >
                Hutch number
              </label>
              <input
                id="msisdn"
                name="msisdn"
                autoComplete="tel"
                inputMode="tel"
                placeholder="07XXXXXXXX"
                value={msisdn}
                onChange={(e) => setMsisdn(e.target.value)}
                required
                style={{
                  width: "100%",
                  font: "inherit",
                  fontSize: 15,
                  padding: "12px 16px",
                  border: "1px solid var(--line)",
                  borderRadius: "var(--radius-sm)",
                  background: "#fff",
                  color: "var(--ink)",
                  outline: "none",
                }}
              />
            </div>
            <button
              type="submit"
              disabled={busy || !msisdn}
              className="h-btn h-btn-primary"
              style={{ width: "100%" }}
            >
              Continue
            </button>
          </form>
        ) : (
          <form onSubmit={onVerify} style={{ display: "grid", gap: 14 }}>
            <div>
              <label
                htmlFor="otp"
                style={{ display: "block", fontSize: 13, color: "var(--muted)", marginBottom: 6 }}
              >
                6-digit code
              </label>
              <input
                id="otp"
                name="otp"
                autoComplete="one-time-code"
                inputMode="numeric"
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                maxLength={6}
                style={{
                  fontFamily: "ui-monospace, monospace",
                  fontSize: 24,
                  letterSpacing: ".32em",
                  padding: "10px 12px",
                  border: "1px solid var(--line)",
                  borderRadius: "var(--radius-sm)",
                  background: "#fff",
                  color: "var(--ink)",
                  width: "100%",
                  outline: "none",
                }}
              />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="submit"
                disabled={busy || !code}
                className="h-btn h-btn-primary"
                style={{ flex: 1 }}
              >
                Sign in
              </button>
              <button
                type="button"
                className="h-btn h-btn-ghost"
                onClick={() => { setStep("request"); setStatus(null); }}
              >
                Back
              </button>
            </div>
          </form>
        )}

        {status && (
          <div
            role="status"
            style={{
              marginTop: 14,
              padding: "10px 14px",
              borderRadius: 10,
              fontSize: 14,
              background: status.tone === "ok" ? "#f0fdf4" : "var(--orange-soft)",
              border: `1px solid ${status.tone === "ok" ? "#86efac" : "#fdd5c0"}`,
              color: status.tone === "ok" ? "#166534" : "var(--orange-ink)",
            }}
          >
            {status.text}
          </div>
        )}
      </div>

      {/* Simulated OTP inbox */}
      <div
        style={{
          marginTop: 16,
          border: "1px dashed var(--warn)",
          borderRadius: 10,
          background: "#fffbeb",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            background: "var(--warn)",
            color: "#fff",
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
          Any 6-digit code works in demo mode.
        </p>
      </div>
    </main>
  );
}
