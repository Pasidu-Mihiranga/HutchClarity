"use client";

import { STAFF_ROLES, useStaffSession } from "./StaffSessionProvider";

export function RoleSwitcherBar() {
  const { activeRole, stepUp, setStepUp, signInAs, signOut, session, busy, error } =
    useStaffSession();

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 shadow-[0_-4px_24px_rgba(15,23,42,0.08)] backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-3 py-2 sm:px-4">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
          <div className="min-w-0">
            {session ? (
              <span>
                <strong className="text-slate-900">{session.subject}</strong>
                {" · "}
                {session.roles.join(", ")}
                {" · "}
                {session.permissions.length} perms
                {" · "}
                assurance {session.assurance}
              </span>
            ) : (
              <span>Pick a demo role to start (roles are asserted, not proven)</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <label className="flex cursor-pointer items-center gap-1.5">
              <input
                type="checkbox"
                checked={stepUp}
                onChange={(e) => setStepUp(e.target.checked)}
                disabled={busy}
              />
              <span>Step-up MFA</span>
            </label>
            {session ? (
              <button
                type="button"
                className="text-sky-800 underline"
                onClick={signOut}
                disabled={busy}
              >
                Sign out
              </button>
            ) : null}
          </div>
        </div>
        {error ? (
          <p className="rounded bg-rose-50 px-2 py-1 text-xs text-rose-800">{error}</p>
        ) : null}
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {STAFF_ROLES.map((role) => {
            const on = activeRole === role.id;
            return (
              <button
                key={role.id}
                type="button"
                disabled={busy}
                onClick={() => void signInAs(role.id)}
                className={`whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  on
                    ? "bg-sky-700 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                } disabled:opacity-50`}
              >
                {role.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
