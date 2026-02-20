"use client";

import {
  createContext,
  useCallback,
  useMemo,
  useSyncExternalStore,
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

/** Subscribe adapter for useSyncExternalStore. */
function subscribe(cb: () => void): () => void {
  return subscribeTokenChange(() => cb());
}

/** Server snapshot: always null (no token on server). */
function getServerSnapshot(): string | null {
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const accessToken = useSyncExternalStore(
    subscribe,
    getAccessToken,
    getServerSnapshot
  );

  const user = useMemo(
    () => (accessToken ? decodeJwtPayload(accessToken) : null),
    [accessToken]
  );

  const login = useCallback((token: string) => {
    setAccessToken(token);
  }, []);

  const logout = useCallback(() => {
    setAccessToken(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      accessToken,
      user,
      isLoading: false,
      login,
      logout,
    }),
    [accessToken, user, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
