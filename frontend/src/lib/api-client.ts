/**
 * Fetch wrapper with Authorization header and 401 retry via refresh.
 *
 * - Attaches Bearer token from in-memory store on every request.
 * - On 401: calls POST /api/v1/auth/refresh (with credentials: "include"
 *   so the httpOnly cookie is sent), then retries the original request once.
 * - If refresh fails: returns 401 error (RequireAuth handles redirect).
 *
 * credentials: "include" is ONLY used for the refresh call (cookie transport).
 * Normal API calls do NOT send cookies — auth is via the Authorization header.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ---- Token store (in-memory + sessionStorage for tab persistence) ----

const TOKEN_KEY = "__sat";

function readPersistedToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

// Lazy-initialized: null until first client-side read.
// This avoids the SSR module-eval problem where window is undefined.
let _accessToken: string | null = null;
let _initialized = false;

const _listeners = new Set<(token: string | null) => void>();

export function getAccessToken(): string | null {
  if (!_initialized && typeof window !== "undefined") {
    _accessToken = readPersistedToken();
    _initialized = true;
  }
  return _accessToken;
}

export function setAccessToken(token: string | null): void {
  _accessToken = token;
  _initialized = true;
  if (typeof window !== "undefined") {
    try {
      if (token) {
        sessionStorage.setItem(TOKEN_KEY, token);
      } else {
        sessionStorage.removeItem(TOKEN_KEY);
      }
    } catch (e) {
      // sessionStorage unavailable (e.g. SSR, private browsing quota)
      console.error("sessionStorage write failed:", e);
    }
  }
  _listeners.forEach((cb) => cb(token));
}

export function subscribeTokenChange(
  cb: (token: string | null) => void
): () => void {
  _listeners.add(cb);
  return () => {
    _listeners.delete(cb);
  };
}

// ---- Refresh logic ----

let _refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  // Deduplicate concurrent refresh attempts
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include", // send httpOnly cookie
        body: JSON.stringify({}),
      });

      if (!res.ok) return null;

      const data = (await res.json()) as { access_token: string };
      return data.access_token;
    } catch {
      return null;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

// ---- Main fetch wrapper ----

export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit
): Promise<{ ok: true; data: T } | { ok: false; status: number; detail: string }> {
  const url = `${API_BASE_URL}${path}`;

  const doFetch = (token: string | null) =>
    fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init?.headers,
      },
    });

  const currentToken = getAccessToken();

  let res: Response;
  try {
    res = await doFetch(currentToken);
  } catch {
    return { ok: false, status: 0, detail: "Network error — is the backend running?" };
  }

  // On 401, attempt refresh then retry once
  if (res.status === 401 && currentToken) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      setAccessToken(newToken);
      try {
        res = await doFetch(newToken);
      } catch {
        return { ok: false, status: 0, detail: "Network error — is the backend running?" };
      }
    } else {
      // Refresh failed — don't clear token here.
      // Let RequireAuth handle the redirect naturally.
      // Dev-login has no refresh cookie so refresh always fails.
      return { ok: false, status: 401, detail: "Session expired" };
    }
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? body.title ?? detail;
    } catch {
      // body not JSON
    }
    return { ok: false, status: res.status, detail };
  }

  // Handle empty responses (204 No Content, missing body, non-JSON)
  const contentType = res.headers.get("content-type") ?? "";
  if (
    res.status === 204 ||
    res.headers.get("content-length") === "0" ||
    !contentType.includes("application/json")
  ) {
    return { ok: true, data: null as T };
  }

  const data = (await res.json()) as T;
  return { ok: true, data };
}
