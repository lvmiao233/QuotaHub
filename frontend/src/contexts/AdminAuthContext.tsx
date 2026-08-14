import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";
import { api } from "@/lib/api";

type AdminAuthValue = {
  authenticated: boolean;
  checking: boolean;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AdminAuthContext = createContext<AdminAuthValue | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(() => window.location.pathname.startsWith("/admin"));

  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      const session = await api.adminSession();
      setAuthenticated(session.authenticated);
    } catch {
      setAuthenticated(false);
    } finally {
      setChecking(false);
    }
  }, []);

  const login = useCallback(async (token: string) => {
    const result = await api.adminLogin(token);
    setAuthenticated(result.authenticated);
    setChecking(false);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.adminLogout();
    } finally {
      setAuthenticated(false);
    }
  }, []);

  useEffect(() => {
    if (location.pathname.startsWith("/admin")) {
      void refresh();
    } else {
      setChecking(false);
    }
  }, [location.pathname, refresh]);

  const value = useMemo(
    () => ({ authenticated, checking, login, logout, refresh }),
    [authenticated, checking, login, logout, refresh]
  );
  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>;
}

export function useAdminAuth() {
  const value = useContext(AdminAuthContext);
  if (!value) throw new Error("useAdminAuth must be used within AdminAuthProvider");
  return value;
}
