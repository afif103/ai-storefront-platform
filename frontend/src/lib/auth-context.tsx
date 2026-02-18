"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AuthState, AuthUser } from "@/types/auth";
import {
  getAccessToken,
  setAccessToken,
  subscribeTokenChange,
} from "@/lib/api-client";

interface AuthContextValue extends AuthState {
  login: (accessToken: string) => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** Decode JWT payload (no verification — verification is backend's job). */
function decodeJwtPayload(token: string): AuthUser | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return {
      sub: payload.sub ?? "",
      email: payload.email ?? "",
    };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setTokenState] = useState<string | null>(
    () => getAccessToken()
  );
  const [user, setUser] = useState<AuthUser | null>(() => {
    const token = getAccessToken();
    return token ? decodeJwtPayload(token) : null;
  });
  const [isLoading] = useState(false);

  // Sync with the module-level store (e.g. after refresh)
  useEffect(() => {
    const unsub = subscribeTokenChange((newToken) => {
      setTokenState(newToken);
      setUser(newToken ? decodeJwtPayload(newToken) : null);
    });
    return unsub;
  }, []);

  const login = useCallback((token: string) => {
    setAccessToken(token);
    setTokenState(token);
    setUser(decodeJwtPayload(token));
  }, []);

  const logout = useCallback(() => {
    setAccessToken(null);
    setTokenState(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      accessToken,
      user,
      isLoading,
      login,
      logout,
    }),
    [accessToken, user, isLoading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
