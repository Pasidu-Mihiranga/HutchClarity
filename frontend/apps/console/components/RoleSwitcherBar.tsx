"use client";

import { useState, type FormEvent } from "react";
import { Button, Input } from "@clarity/ui";
import { useStaffSession } from "./StaffSessionProvider";

/**
 * The staff sign-in and session bar (E2).
 *
 * **The labels are associated, not just adjacent.** Each field had its label
 * as wrapping text, which works until the markup moves; `htmlFor` with a
 * matching `id` survives that and is what `getByLabel` in the browser suite
 * relies on.
 *
 * **The error is a live region.** A sign-in refusal rendered as an ordinary
 * paragraph is silent to a screen reader: the page looks unchanged and the
 * person waits for something that already happened. `role="alert"` makes the
 * refusal announce itself.
 *
 * **The step-up code says what it is for.** "Step-up code" alone does not
 * explain why an optional field is there, so it carries a hint, wired with
 * `aria-describedby` rather than left as nearby text.
 */
export function RoleSwitcherBar() {
  const {
    signIn,
    signInWithProvider,
    stepUpWithProvider,
    methods,
    signOut,
    session,
    stepUp,
    busy,
    error,
  } = useStaffSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [stepUpCode, setStepUpCode] = useState("");

  // The full role picker and credential form own the signed-out state. Keep
  // the header compact and useful only after authentication.
  if (!session) return null;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const ok = await signIn(username, password, stepUpCode);
    if (ok) {
      setPassword("");
      setStepUpCode("");
    }
  }

  const fieldClass = "mt-1 rounded-full px-3 py-1.5 text-sm";

  return (
    <section aria-label="Staff session" className="border-t border-line bg-warm">
      <div className="mx-auto flex max-w-[1240px] flex-col gap-2 px-4 py-2.5 sm:px-6">
        {session ? (
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-mute">
            <p>
              <strong className="text-ink">{session.subject}</strong>
              {" · "}
              {session.roles.join(", ")}
              {" · "}
              {session.permissions.length} permissions
              {" · "}
              assurance {session.assurance}
            </p>
            <span className="flex items-center gap-3">
              {/* Offered only where it can do anything: the provider is what
                  re-authenticates, and a session already stepped up has
                  nothing to gain from doing it again (B2). */}
              {methods?.provider && !stepUp ? (
                <Button variant="ghost" size="sm" onClick={() => void stepUpWithProvider()} disabled={busy}>
                  Re-authenticate
                </Button>
              ) : null}
              <Button variant="ghost" size="sm" onClick={signOut} disabled={busy}>
                Sign out
              </Button>
            </span>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {/* The provider is the way in where one is configured. The form
                below it is the simulated directory, which production does not
                have: `GET /v1/auth/sign-in-methods` says which exist here, so
                the console shows what the API will actually accept rather
                than what it was built expecting. */}
            {methods?.provider ? (
              <div className="flex flex-wrap items-center gap-3">
                <Button pill size="sm" onClick={signInWithProvider} disabled={busy}>
                  Sign in with HUTCH SSO
                </Button>
                {methods.directory ? (
                  <span className="text-xs text-mute">or use a simulated account</span>
                ) : null}
              </div>
            ) : null}

            {methods && !methods.provider && !methods.directory ? (
              <p className="text-xs text-mute">
                No sign-in method is configured on this API.
              </p>
            ) : null}

            {methods?.provider && !methods.directory ? null : (
              <form
                aria-label="Sign in with a simulated account"
                className="flex flex-wrap items-end gap-2"
                onSubmit={(e) => void onSubmit(e)}
              >
                <div className="flex flex-col text-xs text-mute">
                  <label htmlFor="staff-username">Username</label>
                  <Input
                    id="staff-username"
                    name="username"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className={fieldClass}
                    required
                  />
                </div>
                <div className="flex flex-col text-xs text-mute">
                  <label htmlFor="staff-password">Password</label>
                  <Input
                    id="staff-password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={fieldClass}
                    required
                  />
                </div>
                <div className="flex flex-col text-xs text-mute">
                  <label htmlFor="staff-step-up">Step-up code</label>
                  <Input
                    id="staff-step-up"
                    name="step_up_code"
                    autoComplete="one-time-code"
                    aria-describedby="staff-step-up-hint"
                    value={stepUpCode}
                    onChange={(e) => setStepUpCode(e.target.value)}
                    className={fieldClass}
                  />
                  <span id="staff-step-up-hint" className="mt-1 text-[11px] text-fg-subtle">
                    Needed to approve above the cap
                  </span>
                </div>
                <Button type="submit" pill size="sm" disabled={busy}>
                  Sign in
                </Button>
              </form>
            )}
          </div>
        )}
        {error ? (
          <p role="alert" className="rounded-xl bg-danger-soft px-2 py-1 text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
