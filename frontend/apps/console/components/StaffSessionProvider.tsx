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
} from "@clarity/sdk";

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
    client.setToken(undefined);
    setSession(null);
    writeStored(null);
    setGeneration((g) => g + 1);
    setError(null);
  }, [client]);

  useEffect(() => {
    const token = readStored();
    if (!token) {
      setRestoring(false);
      return;
    }
    client.setToken(token);
    void client
      .whoami()
      .then((me) => {
        setSession({ ...me, token });
        setGeneration((g) => g + 1);
      })
      .catch(() => {
        writeStored(null);
        client.setToken(undefined);
      })
      .finally(() => {
        setRestoring(false);
      });
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
