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

export const STAFF_ROLES = [
  { id: "agent", label: "Agent", userRef: "agent-1" },
  { id: "supervisor", label: "Supervisor", userRef: "sup-1" },
  { id: "finance", label: "Finance", userRef: "fin-1" },
  { id: "vas_ops", label: "VAS ops", userRef: "vas-1" },
  { id: "cx_engineer", label: "CX eng", userRef: "cxe-1" },
  { id: "compliance", label: "Compliance", userRef: "comp-1" },
  { id: "auditor", label: "Auditor", userRef: "aud-1" },
  { id: "platform_admin", label: "Platform", userRef: "plat-1" },
  { id: "security_admin", label: "Security", userRef: "sec-1" },
] as const;

export type StaffRoleId = (typeof STAFF_ROLES)[number]["id"];

const STORAGE_KEY = "clarity_console_staff_v1";

type StoredSession = {
  token: string;
  role: StaffRoleId;
  stepUp: boolean;
};

type StaffSessionContextValue = {
  client: ClarityClient;
  session: SessionView | null;
  activeRole: StaffRoleId | null;
  stepUp: boolean;
  busy: boolean;
  restoring: boolean;
  error: string | null;
  setStepUp: (value: boolean) => void;
  signInAs: (role: StaffRoleId) => Promise<void>;
  signOut: () => void;
  hasPermission: (...perms: string[]) => boolean;
  refresh: () => Promise<void>;
  generation: number;
};

const StaffSessionContext = createContext<StaffSessionContextValue | null>(
  null,
);

function readStored(): StoredSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

function writeStored(value: StoredSession | null) {
  if (typeof window === "undefined") return;
  if (!value) sessionStorage.removeItem(STORAGE_KEY);
  else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

export function StaffSessionProvider({ children }: { children: ReactNode }) {
  const [client] = useState(() => createClarityClient());
  const [session, setSession] = useState<SessionView | null>(null);
  const [activeRole, setActiveRole] = useState<StaffRoleId | null>(null);
  const [stepUp, setStepUpState] = useState(false);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);

  const applySession = useCallback(
    (token: string, me: SessionView, role: StaffRoleId, stepped: boolean) => {
      client.setToken(token);
      setSession(me);
      setActiveRole(role);
      setStepUpState(stepped);
      writeStored({ token, role, stepUp: stepped });
      setGeneration((g) => g + 1);
    },
    [client],
  );

  useEffect(() => {
    const stored = readStored();
    if (!stored?.token) {
      setRestoring(false);
      return;
    }
    client.setToken(stored.token);
    void client
      .whoami()
      .then((me) => {
        setSession(me);
        setActiveRole(stored.role);
        setStepUpState(stored.stepUp);
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

  const signInAs = useCallback(
    async (role: StaffRoleId) => {
      const entry = STAFF_ROLES.find((r) => r.id === role);
      if (!entry) return;
      setBusy(true);
      setError(null);
      try {
        const started = await client.staffSession({
          user_ref: entry.userRef,
          roles: [role],
          step_up: stepUp,
        });
        client.setToken(started.token);
        const me = await client.whoami();
        applySession(started.token, me, role, stepUp);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Sign-in failed");
      } finally {
        setBusy(false);
      }
    },
    [applySession, client, stepUp],
  );

  const signOut = useCallback(() => {
    client.setToken(undefined);
    setSession(null);
    setActiveRole(null);
    writeStored(null);
    setGeneration((g) => g + 1);
    setError(null);
  }, [client]);

  const setStepUp = useCallback(
    (value: boolean) => {
      setStepUpState(value);
      if (!activeRole) return;
      void (async () => {
        setBusy(true);
        setError(null);
        try {
          const entry = STAFF_ROLES.find((r) => r.id === activeRole)!;
          const started = await client.staffSession({
            user_ref: entry.userRef,
            roles: [activeRole],
            step_up: value,
          });
          client.setToken(started.token);
          const me = await client.whoami();
          applySession(started.token, me, activeRole, value);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Step-up failed");
        } finally {
          setBusy(false);
        }
      })();
    },
    [activeRole, applySession, client],
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

  const value = useMemo(
    () => ({
      client,
      session,
      activeRole,
      stepUp,
      busy,
      restoring,
      error,
      setStepUp,
      signInAs,
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
      setStepUp,
      signInAs,
      signOut,
      hasPermission,
      refresh,
      generation,
    ],
  );

  return (
    <StaffSessionContext.Provider value={value}>
      {children}
    </StaffSessionContext.Provider>
  );
}

export function useStaffSession(): StaffSessionContextValue {
  const ctx = useContext(StaffSessionContext);
  if (!ctx) {
    throw new Error("useStaffSession must be used within StaffSessionProvider");
  }
  return ctx;
}
