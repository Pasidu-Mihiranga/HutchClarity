"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  ClarityClient,
  createClarityClient,
  type SessionView,
  type SignInMethods,
} from "@clarity/sdk";

export type { SignInMethods };

const STORAGE_KEY = "clarity_console_staff_v2";

type StaffSessionContextValue = {
  client: ClarityClient;
  session: SessionView | null;
  activeRole: string | null;
  stepUp: boolean;
  busy: boolean;
  restoring: boolean;
  error: string | null;
  signIn: (username: string, password: string, stepUpCode: string) => Promise<boolean>;
  /** Send the browser to the provider to sign in (B1). */
  signInWithProvider: () => void;
  /** Ask the provider to re-authenticate before an approval (B2). */
  stepUpWithProvider: () => Promise<void>;
  /** Which sign-in paths this deployment offers. Null until it has answered. */
  methods: SignInMethods | null;
  signOut: () => void;
  hasPermission: (...perms: string[]) => boolean;
  refresh: () => Promise<void>;
  generation: number;
};

const StaffSessionContext = createContext<StaffSessionContextValue | null>(null);

function readStored(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStored(token: string | null) {
  if (typeof window === "undefined") return;
  if (!token) sessionStorage.removeItem(STORAGE_KEY);
  else sessionStorage.setItem(STORAGE_KEY, token);
}

export function StaffSessionProvider({ children }: { children: ReactNode }) {
  const [client] = useState(() => createClarityClient());
  const [session, setSession] = useState<SessionView | null>(null);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);
  const [methods, setMethods] = useState<SignInMethods | null>(null);

  const applySession = useCallback(
    (token: string, me: SessionView) => {
      client.setToken(token);
      setSession({ ...me, token });
      writeStored(token);
      setGeneration((g) => g + 1);
    },
    [client],
  );

  const signOut = useCallback(() => {
    const clearLocally = () => {
      client.setToken(undefined);
      setSession(null);
      writeStored(null);
      setGeneration((g) => g + 1);
      setError(null);
    };

    // Tell the API, so the session is revoked and the cookie cleared, and
    // follow the provider's logout when there is one. Clearing only what this
    // page can see would leave the session alive on the server and the
    // provider's own cookie untouched, so the next visit would return
    // instantly with nothing asked for.
    void client
      .logout()
      .then((body) => {
        clearLocally();
        if (body.provider_logout) window.location.assign(body.provider_logout);
      })
      .catch(clearLocally);
  }, [client]);

  const signInWithProvider = useCallback(() => {
    const here = window.location.pathname + window.location.search;
    window.location.assign(client.oidcStartUrl(here));
  }, [client]);

  const stepUpWithProvider = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const here = window.location.pathname + window.location.search;
      const { redirect_to } = await client.stepUp(here).catch(() => {
        throw new Error("step-up is not available");
      });
      // The provider re-authenticates and sends the browser back here with a
      // stronger session. Nothing is granted by this call itself.
      window.location.assign(redirect_to);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Step-up failed");
      setBusy(false);
    }
  }, [client]);

  // Which sign-in paths exist here. Asked rather than assumed: a console that
  // decided from its own build-time setting would show a provider button on a
  // deployment with no provider configured, and a password form on one where
  // the password routes are gone.
  useEffect(() => {
    let cancelled = false;
    void client
      .signInMethods()
      .then((found) => {
        if (!cancelled) setMethods(found);
      })
      .catch(() => {
        /* the sign-in screen falls back to showing the form */
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  // Restoring a session.
  //
  // Two carriers now. A sign-in through the provider leaves an `HttpOnly`
  // cookie the browser sends on its own and this code cannot read, so the only
  // way to know whether one exists is to ask. A token in `sessionStorage` is
  // the older path, still used by the development sign-in, and it is tried
  // first because it is the one this code can see.
  useEffect(() => {
    let cancelled = false;
    const token = readStored();
    if (token) client.setToken(token);

    void client
      .whoami()
      .then((me) => {
        if (cancelled) return;
        setSession(token ? { ...me, token } : me);
        setGeneration((g) => g + 1);
      })
      .catch(() => {
        if (cancelled) return;
        // Neither carrier produced a session. Clear the one we can.
        writeStored(null);
        client.setToken(undefined);
      })
      .finally(() => {
        if (!cancelled) setRestoring(false);
      });

    return () => {
      cancelled = true;
    };
  }, [client]);

  const signIn = useCallback(
    async (username: string, password: string, stepUpCode: string) => {
      setBusy(true);
      setError(null);
      try {
        const started = await client.staffLogin({
          username,
          password,
          step_up_code: stepUpCode,
        });
        client.setToken(started.token);
        const me = await client.whoami();
        applySession(started.token, me);
        return true;
      } catch (err) {
        client.setToken(undefined);
        setError(err instanceof Error ? err.message : "Sign-in failed");
        return false;
      } finally {
        setBusy(false);
      }
    },
    [applySession, client],
  );

  const refresh = useCallback(async () => {
    if (!client.getToken()) return;
    try {
      const me = await client.whoami();
      setSession(me);
      setGeneration((g) => g + 1);
    } catch {
      signOut();
    }
  }, [client, signOut]);

  const hasPermission = useCallback(
    (...perms: string[]) => {
      if (!session) return false;
      return perms.some((p) => session.permissions.includes(p));
    },
    [session],
  );

  const activeRole = session?.roles[0] ?? null;
  const stepUp = session?.assurance === "mfa-recent";

  const value = useMemo(
    () => ({
      client,
      session,
      activeRole,
      stepUp,
      busy,
      restoring,
      error,
      signIn,
      signInWithProvider,
      stepUpWithProvider,
      methods,
      signOut,
      hasPermission,
      refresh,
      generation,
    }),
    [
      client,
      session,
      activeRole,
      stepUp,
      busy,
      restoring,
      error,
      signIn,
      signInWithProvider,
      stepUpWithProvider,
      methods,
      signOut,
      hasPermission,
      refresh,
      generation,
    ],
  );

  return (
    <StaffSessionContext.Provider value={value}>{children}</StaffSessionContext.Provider>
  );
}

export function useStaffSession(): StaffSessionContextValue {
  const ctx = useContext(StaffSessionContext);
  if (!ctx) {
    throw new Error("useStaffSession must be used within StaffSessionProvider");
  }
  return ctx;
}
