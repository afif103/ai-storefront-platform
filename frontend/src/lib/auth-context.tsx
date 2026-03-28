"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import type {
  AuthState,
  AuthUser,
  BootstrapPayload,
  LoginResponse,
} from "@/types/auth";
import {
  apiFetch,
  getAccessToken,
  setAccessToken,
  subscribeTokenChange,
} from "@/lib/api-client";
import { cognitoSignIn } from "@/lib/cognito";

const COGNITO_MOCK = process.env.NEXT_PUBLIC_COGNITO_MOCK === "true";

interface AuthContextValue extends AuthState {
  loginWithCredentials: (email: string, password: string) => Promise<void>;
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

/** No-op subscribe — hydration state never changes after mount. */
const subscribeNoop = (): (() => void) => () => {};

export function AuthProvider({ children }: { children: ReactNode }) {
  // Server: true (loading) — prevents RequireAuth redirect during SSR.
  // Client: false — getAccessToken() has already read sessionStorage.
  const hydrating = useSyncExternalStore(subscribeNoop, () => false, () => true);

  const accessToken = useSyncExternalStore(
    subscribe,
    getAccessToken,
    getServerSnapshot
  );

  const user = useMemo(
    () => (accessToken ? decodeJwtPayload(accessToken) : null),
    [accessToken]
  );

  const [bootstrap, setBootstrap] = useState<BootstrapPayload | null>(null);

  // Restore bootstrap state when token exists but bootstrap is missing (page refresh, dev login).
  useEffect(() => {
    if (!accessToken || bootstrap) return;

    let cancelled = false;
    (async () => {
      const res = await apiFetch<BootstrapPayload>("/api/v1/auth/bootstrap", {
        method: "POST",
      });
      if (cancelled) return;
      if (res.ok) {
        setBootstrap(res.data);
      } else if (res.status === 401) {
        setAccessToken(null);
        setBootstrap(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, bootstrap]);

  const loginWithCredentials = useCallback(
    async (email: string, password: string) => {
      let body: Record<string, string>;

      if (COGNITO_MOCK) {
        body = { email: email.trim().toLowerCase(), password };
      } else {
        const tokens = await cognitoSignIn(email, password);
        body = {
          access_token: tokens.access_token,
          id_token: tokens.id_token,
          refresh_token: tokens.refresh_token,
        };
      }

      const res = await apiFetch<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
        credentials: "include", // receive refresh cookie
      });

      if (!res.ok) {
        throw new Error(res.detail);
      }

      setAccessToken(res.data.access_token);
      setBootstrap({
        user: res.data.user,
        memberships: res.data.memberships,
        pending_invitations: res.data.pending_invitations,
        needs_onboarding: res.data.needs_onboarding,
      });
    },
    [],
  );

  const login = useCallback((token: string) => {
    setBootstrap(null);
    setAccessToken(token);
    // Bootstrap restored by the useEffect above on next render.
  }, []);

  const logout = useCallback(() => {
    setAccessToken(null);
    setBootstrap(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      accessToken,
      user,
      bootstrap,
      isLoading: hydrating,
      login,
      loginWithCredentials,
      logout,
    }),
    [accessToken, user, bootstrap, hydrating, login, loginWithCredentials, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
