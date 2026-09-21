import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

const STORAGE_KEY = "verify.session.v1";

export type Session = {
  token: string;
  email: string;
  role?: "supervisor" | "reviewer" | "auditor";
};

type AuthContextValue = {
  session: Session | null;
  loading: boolean;
  setSession: (session: Session | null) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Session;
    if (parsed && parsed.token && parsed.email) return parsed;
  } catch {
    /* ignore */
  }
  return null;
}

function writeSession(session: Session | null): void {
  if (typeof window === "undefined") return;
  if (session) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

export function getStoredToken(): string | null {
  return readSession()?.token ?? null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(() => readSession());
  const [loading] = useState(false);

  const setSession = useCallback((next: Session | null) => {
    writeSession(next);
    setSessionState(next);
  }, []);

  const logout = useCallback(() => {
    setSession(null);
  }, [setSession]);

  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key === STORAGE_KEY) {
        setSessionState(readSession());
      }
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const value = useMemo(() => ({ session, loading, setSession, logout }), [
    session,
    loading,
    setSession,
    logout,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
