"use client";

import { useRef, useState, type FormEvent } from "react";
import { useStaffSession } from "./StaffSessionProvider";

/**
 * The synthetic accounts in `config/staff/synthetic-directory.json`. Shown only
 * when the API says the simulated directory is the way in
 * (`GET /v1/auth/sign-in-methods` -> `directory`), which a HUTCH deployment
 * with its own identity provider does not offer (I9). Picking one fills the
 * form and submits it; the server still checks the password and assigns the role.
 */
const SYNTHETIC_ROLES: ReadonlyArray<{
  username: string;
  role: string;
  summary: string;
}> = [
  { username: "agent", role: "Agent", summary: "Work the queue, explain a charge, approve within the cap" },
  { username: "supervisor", role: "Supervisor", summary: "High-value approvals, autopsy review, kill switch" },
  { username: "finance", role: "Finance", summary: "Second approver for money, reconciliation" },
  { username: "vasops", role: "VAS operations", summary: "Propose fixes, suspend a merchant" },
  { username: "cx", role: "CX engineer", summary: "Draft rules and config, Foresight outcomes" },
  { username: "product", role: "Product", summary: "Rehearse Foresight scenarios and draft product changes" },
  { username: "compliance", role: "Compliance", summary: "Publish rules, audit export, regulator pack" },
  { username: "auditor", role: "Auditor", summary: "Read-only cases, receipts and audit trail" },
  { username: "platform", role: "Platform admin", summary: "Flags, kill switches, audit restore" },
  { username: "security", role: "Security admin", summary: "Access administration, audit assignment" },
];

const SYNTHETIC_STEP_UP = "step-up";

export function SignInPortal() {
  const { signIn, signInWithProvider, methods, busy, error } = useStaffSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [stepUpCode, setStepUpCode] = useState("");
  const submitRef = useRef<HTMLButtonElement>(null);

  const syntheticDirectory = methods?.directory === true;
  const chosen = SYNTHETIC_ROLES.find((r) => r.username === username);

  async function choose(account: (typeof SYNTHETIC_ROLES)[number]) {
    const password = `${account.username}-clarity`;
    setUsername(account.username);
    setPassword(password);
    setStepUpCode(SYNTHETIC_STEP_UP);
    await signIn(account.username, password, SYNTHETIC_STEP_UP);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const ok = await signIn(username, password, stepUpCode);
    if (ok) {
      setPassword("");
      setStepUpCode("");
    }
  }

  const field =
    "min-h-[50px] w-full rounded-md border border-border-strong bg-surface-2 px-3.5 text-sm text-ink outline-none transition focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand/10";

  return (
    <section className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:items-start">
      <div className="space-y-5">
        <div className="space-y-3">
          <p className="flex items-center gap-2.5 text-[11px] font-extrabold uppercase tracking-[0.16em] text-mute">
            <span aria-hidden className="h-0.5 w-6 rounded bg-brand shadow-[0_0_14px_rgb(var(--c-brand)/0.3)]" />
            Clarity Desk
          </p>
          <h1 className="text-4xl font-extrabold tracking-tight text-ink sm:text-5xl">
            Choose your desk
          </h1>
          <p className="max-w-xl text-base leading-7 text-mute">
            Evidence, a rule decision and a signed Trust Receipt for every case.
            {syntheticDirectory
              ? " Pick a role to fill its synthetic account and sign in immediately."
              : " Sign in with the account you were issued; the server assigns the role."}
          </p>
        </div>

        {syntheticDirectory ? (
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Staff roles">
            {SYNTHETIC_ROLES.map((account) => {
              const active = account.username === username;
              return (
                <li key={account.username}>
                  <button
                    type="button"
                    onClick={() => void choose(account)}
                    disabled={busy}
                    aria-pressed={active}
                    className={`group flex h-full w-full flex-col gap-1.5 rounded-lg border bg-surface p-4 text-left shadow-1 transition hover:-translate-y-0.5 hover:shadow-2 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand/25 ${
                      active ? "border-brand bg-primary-soft/60 ring-4 ring-brand/15" : "border-line hover:border-border-strong"
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-bold text-ink">{account.role}</span>
                      <span
                        aria-hidden
                        className={`h-2.5 w-2.5 rounded-full transition ${active ? "bg-brand" : "bg-line group-hover:bg-brand/50"}`}
                      />
                    </span>
                    <span className="text-xs leading-5 text-mute">{account.summary}</span>
                    <span className="mt-auto pt-1 font-mono text-[11px] text-fg-subtle">{account.username}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>

      <div className="rounded-xl border border-line bg-surface p-6 shadow-3 sm:p-8 lg:sticky lg:top-24">
        <div className="mb-6 flex items-center justify-between gap-4 border-b border-line pb-5 font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
          <span>{chosen ? chosen.role : "Staff access"}</span>
          {syntheticDirectory ? <span className="rounded-full bg-warm px-2 py-1 text-accent">Synthetic accounts</span> : null}
        </div>

        {methods?.provider ? (
          <div className="mb-5 space-y-2">
            <button
              type="button"
              onClick={signInWithProvider}
              disabled={busy}
              className="min-h-[46px] w-full rounded-full bg-accent px-5 text-sm font-bold text-white transition hover:bg-accent-deep disabled:opacity-50"
            >
              Sign in with HUTCH SSO
            </button>
            {methods.directory ? (
              <p className="text-center text-xs text-mute">or use a synthetic account</p>
            ) : null}
          </div>
        ) : null}

        {methods && !methods.provider && !methods.directory ? (
          <p className="text-sm text-mute">No sign-in method is configured on this API.</p>
        ) : null}

        {methods?.provider && !methods.directory ? null : (
          <form className="grid gap-4" onSubmit={(e) => void onSubmit(e)}>
            <label className="grid gap-2 text-xs font-bold text-ink">
              Username
              <input
                id="staff-username"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={field}
                required
              />
            </label>
            <label className="grid gap-2 text-xs font-bold text-ink">
              Password
              <input
                id="staff-password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={field}
                required
              />
            </label>
            <label className="grid gap-2 text-xs font-bold text-ink">
              Step-up code
              <input
                id="staff-step-up"
                name="step_up_code"
                autoComplete="one-time-code"
                value={stepUpCode}
                onChange={(e) => setStepUpCode(e.target.value)}
                className={field}
              />
              <span className="text-[11px] font-normal leading-4 text-mute">
                Needed for approvals above the cap. Leave empty for a single-factor session.
              </span>
            </label>
            <button
              ref={submitRef}
              type="submit"
              disabled={busy}
              className="mt-1 min-h-[50px] rounded-full bg-accent px-5 text-sm font-bold text-white shadow-[0_12px_30px_rgb(var(--c-brand)/0.2)] transition hover:bg-accent-deep focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand/30 disabled:opacity-50"
            >
              Sign in
            </button>
          </form>
        )}

        {error ? (
          <p role="alert" className="mt-4 rounded-md bg-danger-soft px-3 py-2 text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
