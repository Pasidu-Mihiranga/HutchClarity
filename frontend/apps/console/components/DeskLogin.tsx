"use client";

import { useState, type FormEvent } from "react";
import { Button, Input } from "@clarity/ui";
import { useStaffSession } from "./StaffSessionProvider";

const SYNTHETIC_ROLES = [
  { username: "agent", password: "agent-clarity", label: "Agent" },
  { username: "supervisor", password: "supervisor-clarity", label: "Supervisor" },
  { username: "finance", password: "finance-clarity", label: "Finance" },
  { username: "vasops", password: "vasops-clarity", label: "VAS operations" },
  { username: "cx", password: "cx-clarity", label: "CX engineer" },
  { username: "product", password: "product-clarity", label: "Product" },
  { username: "compliance", password: "compliance-clarity", label: "Compliance" },
  { username: "auditor", password: "auditor-clarity", label: "Auditor" },
  { username: "admin", password: "admin123456", label: "Platform admin" },
  { username: "security", password: "security-clarity", label: "Security admin" },
] as const;

/**
 * The signed-out desk (the split screen from the desk mockup).
 *
 * Remember me and a password reset are on that picture and nowhere in the
 * API, so they are not on this page: a control that cannot do what it says
 * is a sign-in that lies.
 *
 * The step-up code stays. An approval above the cap still asks for it, and
 * the field's hint says so (`aria-describedby`, not nearby text).
 *
 * A refusal is a live region. An ordinary paragraph is silent to a screen
 * reader: the page looks unchanged and the person waits for something that
 * already happened.
 */
export function DeskLogin() {
  const { signIn, signInWithProvider, methods, busy, error } = useStaffSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [stepUpCode, setStepUpCode] = useState("");

  function fillRole(account: (typeof SYNTHETIC_ROLES)[number]) {
    setUsername(account.username);
    setPassword(account.password);
    setStepUpCode("step-up");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const ok = await signIn(username, password, stepUpCode);
    if (ok) {
      setPassword("");
      setStepUpCode("");
    }
  }

  const showDirectory = !(methods?.provider && !methods.directory);

  return (
    <main className="sign-in-light grid min-h-screen lg:grid-cols-2">
      <section className="relative hidden min-h-screen bg-white lg:block">
        <img
          src="/desk-hero.jpg"
          alt=""
          className="absolute inset-0 h-full w-full object-contain p-4"
        />
      </section>

      <section className="flex items-center bg-surface px-6 py-12 sm:px-10">
        <div className="mx-auto w-full max-w-md">
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink">
            Hutch Clarity Desk
          </h1>
          <p className="mt-1 text-sm text-mute">Support smarter. Serve better.</p>

          {methods?.provider ? (
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button pill onClick={signInWithProvider} disabled={busy}>
                Sign in with HUTCH SSO
              </Button>
              {methods.directory ? (
                <span className="text-xs text-mute">or use a simulated account</span>
              ) : null}
            </div>
          ) : null}

          {methods && !methods.provider && !methods.directory ? (
            <p className="mt-8 text-sm text-mute">No sign-in method is configured on this API.</p>
          ) : null}

          {showDirectory ? (
            <form
              aria-label="Sign in with a simulated account"
              className="mt-8 grid gap-4"
              onSubmit={(e) => void onSubmit(e)}
            >
              <div className="flex flex-col gap-1 text-sm text-mute">
                <label htmlFor="staff-username">Staff ID or email</label>
                <div className="relative">
                  <PersonIcon />
                  <Input
                    id="staff-username"
                    name="username"
                    autoComplete="username"
                    placeholder="Staff ID or email"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="rounded-xl py-3 pl-11"
                    required
                  />
                </div>
              </div>
              <div className="flex flex-col gap-1 text-sm text-mute">
                <label htmlFor="staff-password">Password</label>
                <div className="relative">
                  <LockIcon />
                  <Input
                    id="staff-password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="rounded-xl py-3 pl-11"
                    required
                  />
                </div>
              </div>
              <div className="flex flex-col gap-1 text-sm text-mute">
                <label htmlFor="staff-step-up">Step-up code</label>
                <Input
                  id="staff-step-up"
                  name="step_up_code"
                  autoComplete="one-time-code"
                  aria-describedby="staff-step-up-hint"
                  value={stepUpCode}
                  onChange={(e) => setStepUpCode(e.target.value)}
                  className="rounded-xl py-3"
                />
                <span id="staff-step-up-hint" className="text-[11px] text-fg-subtle">
                  Needed to approve above the cap
                </span>
              </div>
              <Button type="submit" pill size="lg" className="w-full" disabled={busy}>
                Sign in
              </Button>
              <fieldset className="grid gap-2">
                <legend className="mb-1 text-xs font-semibold text-ink">
                  Autofill a role
                </legend>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {SYNTHETIC_ROLES.map((account) => (
                    <button
                      key={account.username}
                      type="button"
                      aria-pressed={username === account.username}
                      onClick={() => fillRole(account)}
                      className={`rounded-xl border px-3 py-2 text-left text-xs transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                        username === account.username
                          ? "border-primary bg-primary-soft font-semibold text-primary"
                          : "border-border bg-surface text-fg hover:border-primary/50"
                      }`}
                    >
                      {account.label}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-fg-subtle">
                  Selecting a role only fills the credentials. Review them, then click Sign in.
                </p>
              </fieldset>
            </form>
          ) : null}

          {error ? (
            <p role="alert" className="mt-4 rounded-xl bg-danger-soft px-3 py-2 text-sm text-danger">
              {error}
            </p>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function PersonIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-fg-muted"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.5 19.2c1.2-3.2 3.4-4.7 6.5-4.7s5.3 1.5 6.5 4.7" strokeLinecap="round" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-fg-muted"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <rect x="5" y="10.5" width="14" height="9" rx="2" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" strokeLinecap="round" />
    </svg>
  );
}
