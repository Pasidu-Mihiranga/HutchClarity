"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ClarityClient } from "@clarity/sdk";
import { Alert, Button, Field, Input } from "@clarity/ui";
import { safeNext } from "@/lib/session";

const client = new ClarityClient();

/**
 * Wrong guesses the sign-in page will accept for one code.
 *
 * The same number the server uses (`MAX_ATTEMPTS` in `modules/iam/otp.py`).
 * A wrong code increments the challenge, and the guess after the third is
 * refused even when the digits are right, because the check is
 * `attempts > MAX_ATTEMPTS`. The HTTP body does not say which refusal it was
 * (every one is "that code is not valid"), so the page counts for itself and
 * stops offering the field once three have failed.
 */
const MAX_OTP_ATTEMPTS = 3;
const SYNTHETIC_FALLBACK_NUMBER = "0781234567";
const SYNTHETIC_FALLBACK_CODE = "246810";

type Status = { text: string; tone: "ok" | "bad" };

export default function LoginPage() {
  const router = useRouter();
  const codeRef = useRef<HTMLInputElement>(null);
  const [msisdn, setMsisdn] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"request" | "verify">("request");
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  // The code from the simulated inbox. There is no "any six digits" path: the
  // backend generates a code per challenge and refuses anything else, so the
  // panel below has to show the real one or nobody can sign in.
  const [demoCode, setDemoCode] = useState<string | null>(null);
  const [simulatedDelivery, setSimulatedDelivery] = useState(false);
  // `verifyOtp` needs the challenge this code belongs to, not the number.
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [failures, setFailures] = useState(0);
  const locked = failures >= MAX_OTP_ATTEMPTS;
  // Shown only when the API will accept it (CLARITY_SYNTHETIC_FALLBACK_OTP):
  // advertising a code the server refuses would be one more dead end.
  const [fallbackOffered, setFallbackOffered] = useState(false);
  useEffect(() => {
    let live = true;
    client
      .signInMethods()
      .then((methods) => {
        if (live) setFallbackOffered(methods.customer_fallback === true);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  // After a refusal the field is a new node (the shake restarts by remounting
  // it) and it is empty. Put the cursor back in it, or the next attempt starts
  // with focus on the button that just failed.
  useEffect(() => {
    if (step === "verify" && failures > 0 && !locked) {
      codeRef.current?.focus();
    }
  }, [failures, locked, step]);

  function resetChallenge() {
    setStep("request");
    setStatus(null);
    setCode("");
    setFailures(0);
    setChallengeId(null);
    setDemoCode(null);
    setSimulatedDelivery(false);
  }

  async function requestCode() {
    setBusy(true);
    setStatus(null);
    setFailures(0);
    setCode("");
    setDemoCode(null);
    try {
      const result = await client.requestOtp(msisdn);
      setChallengeId(result.challenge_id);
      setSimulatedDelivery(result.simulated === true);
      setStatus({
        text: result.detail ?? "A sign-in code was requested.",
        tone: "ok",
      });
      setStep("verify");

      // The inbox route exists only for synthetic delivery. Calling it after
      // a real SMS request creates a guaranteed production 404.
      if (result.simulated === true) {
        try {
          const message = await client.demoInbox(msisdn);
          if (message.code) {
            setDemoCode(message.code);
            setCode(message.code);
          }
        } catch {
          setDemoCode(null);
        }
      }
    } catch (err) {
      setSimulatedDelivery(false);
      setDemoCode(null);
      setStatus({
        text: err instanceof Error ? err.message : "Request failed",
        tone: "bad",
      });
    } finally {
      setBusy(false);
    }
  }

  async function onRequest(e: FormEvent) {
    e.preventDefault();
    await requestCode();
  }

  async function onVerify(e: FormEvent) {
    e.preventDefault();
    if (locked) return;
    setBusy(true);
    setStatus(null);
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
      client.setToken(undefined);
      const next = failures + 1;
      setFailures(next);
      setCode("");
      if (next >= MAX_OTP_ATTEMPTS) {
        setStatus({
          text: "You cannot sign in with this code. Request a new code to try again.",
          tone: "bad",
        });
      } else {
        const left = MAX_OTP_ATTEMPTS - next;
        const reason = err instanceof Error ? err.message : "Verify failed";
        setStatus({
          text: `${reason}. ${left} ${left === 1 ? "attempt" : "attempts"} left.`,
          tone: "bad",
        });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="sign-in-light box-border min-h-dvh w-full bg-white px-[max(1rem,env(safe-area-inset-left))] pt-[max(0.75rem,env(safe-area-inset-top))]">
      <div className="relative mx-auto flex w-full max-w-[440px] flex-col pb-[max(1.5rem,env(safe-area-inset-bottom))]">
        <img src="/login-hero.png" alt="" className="login-hero mx-auto mb-1" />

        <h1 className="mb-1 text-center text-[clamp(1.35rem,5.2vw,1.7rem)] font-extrabold tracking-tight text-fg">
          Welcome to Hutch Clarity
        </h1>
        <p className="mb-4 text-center text-sm leading-6 text-fg-muted sm:mb-6">
          Manage your bills, packages and services anytime, anywhere.
        </p>

        <p className="mb-3 text-center text-xs text-fg-muted">
          {step === "request" ? "Step 1 of 2 - Enter your number" : "Step 2 of 2 - Enter your OTP"}
        </p>

        {step === "request" ? (
          <form onSubmit={onRequest} className="grid gap-3.5">
            {fallbackOffered ? (
            <div className="rounded-2xl border border-primary/20 bg-primary-soft px-4 py-3 text-sm text-fg">
              <p className="font-semibold">Synthetic fallback access</p>
              <p className="mt-1 text-xs text-fg-muted">
                Number <strong>{SYNTHETIC_FALLBACK_NUMBER}</strong> · code{" "}
                <strong>{SYNTHETIC_FALLBACK_CODE}</strong>
              </p>
              <button
                type="button"
                className="mt-2 text-xs font-semibold text-primary underline"
                onClick={() => setMsisdn(SYNTHETIC_FALLBACK_NUMBER)}
              >
                Use fallback number
              </button>
            </div>
            ) : null}
            <Field label="Hutch number">
              {(control) => (
                <div className="relative">
                  <PhoneIcon />
                  <Input
                    {...control}
                    name="msisdn"
                    autoComplete="tel"
                    inputMode="tel"
                    placeholder="07XXXXXXXX"
                    value={msisdn}
                    onChange={(e) => setMsisdn(e.target.value)}
                    required
                    className="min-h-12 rounded-2xl py-3 pl-11 pr-4 text-base"
                  />
                </div>
              )}
            </Field>
            <Button type="submit" pill size="lg" loading={busy} disabled={!msisdn} className="w-full">
              Continue
              <span aria-hidden="true">→</span>
            </Button>
          </form>
        ) : (
          <form onSubmit={onVerify} className="grid gap-3.5">
            <Field label="6-digit code">
              {(control) => (
                <div
                  key={failures}
                  data-testid="otp-field"
                  data-shaken={String(failures)}
                  className={failures > 0 ? "otp-shake" : undefined}
                >
                  <Input
                    {...control}
                    ref={codeRef}
                    name="otp"
                    autoComplete="one-time-code"
                    inputMode="numeric"
                    placeholder="123456"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    required
                    maxLength={6}
                    disabled={locked}
                    aria-invalid={failures > 0 || undefined}
                    className="min-h-12 w-full rounded-2xl px-3 py-3 text-center font-mono text-[clamp(1.25rem,6vw,1.5rem)] tracking-[0.22em] min-[380px]:tracking-[0.32em]"
                  />
                </div>
              )}
            </Field>
            <div className="flex flex-col gap-2 min-[380px]:flex-row">
              <Button
                type="submit"
                pill
                size="lg"
                loading={busy}
                disabled={locked || !code}
                className="flex-1"
              >
                Sign in
                <span aria-hidden="true">→</span>
              </Button>
              {locked ? null : (
                <Button type="button" variant="secondary" pill size="lg" className="w-full min-[380px]:w-auto" onClick={resetChallenge}>
                  Back
                </Button>
              )}
            </div>
            {locked ? (
              <Button
                type="button"
                variant="secondary"
                pill
                size="lg"
                className="w-full"
                onClick={resetChallenge}
              >
                Request a new code
              </Button>
            ) : (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={busy}
                disabled={busy}
                onClick={() => void requestCode()}
                className="w-full"
              >
                Resend code
              </Button>
            )}
          </form>
        )}

        {status && (
          <Alert tone={status.tone === "ok" ? "success" : "danger"} className="mt-3.5">
            {status.text}
          </Alert>
        )}

        <button
          type="button"
          className="mt-5 text-sm font-semibold text-primary"
          aria-expanded={helpOpen}
          aria-controls="login-help"
          onClick={() => setHelpOpen((open) => !open)}
        >
          Need help?
        </button>
        {helpOpen ? (
          <p id="login-help" className="mt-2 text-center text-sm leading-6 text-fg-muted">
            Enter your Hutch number and the 6-digit code we send. If it does not arrive,
            check your mobile signal and use Resend code.
          </p>
        ) : null}

        <div className="mt-4 flex items-start gap-3 rounded-2xl border border-primary/15 bg-surface px-4 py-3">
          <ShieldIcon />
          <p className="text-sm leading-5 text-fg-muted">
            Secure support for bills, packages and service help.
          </p>
        </div>
        <CityLine />

        {/* Synthetic-profile inbox, shown only when this request used it. */}
        {simulatedDelivery && (
          <div
            data-testid="simulated-sms-inbox"
            className="mt-4 overflow-hidden rounded-[10px] border border-dashed border-warning bg-warning-soft"
          >
            <div className="bg-warning px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-primary-on">
              Simulated SMS inbox
            </div>
            <p className="m-0 p-3 text-sm text-fg">
              {demoCode ? (
                <>
                  Your code is{" "}
                  <strong data-testid="demo-otp-code" className="tracking-[.1em]">
                    {demoCode}
                  </strong>
                  . It has been filled in for you.
                </>
              ) : (
                "Enter your Hutch number to receive a simulated code here."
              )}
            </p>
          </div>
        )}
      </div>
    </main>
  );
}

/** City line under the form, in the page flow so a short phone can scroll to it. */
function CityLine() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 480 90"
      className="mt-4 h-16 w-full shrink-0 text-brand opacity-35 sm:h-20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.2"
    >
      <path d="M0 78h480" />
      <path d="M16 78V52h18v26M42 78V40h26v38M78 78V58h16v20M110 78V36l12-20 12 20v42M150 78V48h30v30M196 78V60h20v18M230 78V42h10V28h10v14h10v36M286 78V54h28v24M330 78V62h20v16M364 78V46l8-14 8 14v32M400 78V58h22v20M436 78V64h24v14" />
      <path d="M8 78c40-10 70-4 110 2s70 10 100-2 60-12 100 0 70 8 120-4" />
    </svg>
  );
}

function PhoneIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-fg-muted"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <rect x="7" y="2.5" width="10" height="19" rx="2" />
      <path d="M11 18.5h2" strokeLinecap="round" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="mt-0.5 h-6 w-6 shrink-0 text-primary" fill="none">
      <path
        d="M12 3.2 19 6v5.4c0 4.2-2.9 7.3-7 8.6-4.1-1.3-7-4.4-7-8.6V6l7-2.8Z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path d="m8.8 12.1 2.1 2.1 4.3-4.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
