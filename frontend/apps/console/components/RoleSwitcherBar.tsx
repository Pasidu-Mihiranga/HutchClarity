"use client";

import { useState, type FormEvent } from "react";
import { useStaffSession } from "./StaffSessionProvider";

export function RoleSwitcherBar() {
  const { signIn, signOut, session, busy, error } = useStaffSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [stepUpCode, setStepUpCode] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const ok = await signIn(username, password, stepUpCode);
    if (ok) {
      setPassword("");
      setStepUpCode("");
    }
  }

  return (
    <div className="border-t border-[#f0e7e1] bg-warm">
      <div className="mx-auto flex max-w-[1240px] flex-col gap-2 px-4 py-2.5 sm:px-6">
        {session ? (
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-mute">
            <span>
              <strong className="text-ink">{session.subject}</strong>
              {" · "}
              {session.roles.join(", ")}
              {" · "}
              {session.permissions.length} permissions
              {" · "}
              assurance {session.assurance}
            </span>
            <button
              type="button"
              className="font-medium text-accent-deep underline"
              onClick={signOut}
              disabled={busy}
            >
              Sign out
            </button>
          </div>
        ) : (
          <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => void onSubmit(e)}>
            <label className="flex flex-col gap-1 text-xs text-mute">
              Username
              <input
                id="staff-username"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="rounded-full border border-line bg-white px-3 py-1.5 text-sm text-ink"
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-mute">
              Password
              <input
                id="staff-password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-full border border-line bg-white px-3 py-1.5 text-sm text-ink"
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-mute">
              Step-up code
              <input
                id="staff-step-up"
                name="step_up_code"
                autoComplete="one-time-code"
                value={stepUpCode}
                onChange={(e) => setStepUpCode(e.target.value)}
                className="rounded-full border border-line bg-white px-3 py-1.5 text-sm text-ink"
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="rounded-full bg-accent px-4 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              Sign in
            </button>
          </form>
        )}
        {error ? (
          <p className="rounded-xl bg-rose-50 px-2 py-1 text-xs text-rose-800">{error}</p>
        ) : null}
      </div>
    </div>
  );
}
