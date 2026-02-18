/**
 * Fetch wrapper with Authorization header and 401 retry via refresh.
 *
 * - Attaches Bearer token from in-memory store on every request.
 * - On 401: calls POST /api/v1/auth/refresh (with credentials: "include"
 *   so the httpOnly cookie is sent), then retries the original request once.
 * - If refresh fails: clears token and redirects to /login.
 *
 * credentials: "include" is ONLY used for the refresh call (cookie transport).
 * Normal API calls do NOT send cookies — auth is via the Authorization header.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ---- In-memory token store (module-level singleton) ----

let _accessToken: string | null = null;
let _onTokenChange: ((token: string | null) => void) | null = null;

export function getAccessToken(): string | null {
  return _accessToken;
}

export function setAccessToken(token: string | null): void {
  _accessToken = token;
  _onTokenChange?.(token);
}

export function subscribeTokenChange(
  cb: (token: string | null) => void
): () => void {
  _onTokenChange = cb;
  return () => {
    if (_onTokenChange === cb) _onTokenChange = null;
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

  let res = await doFetch(_accessToken);

  // On 401, attempt refresh then retry once
  if (res.status === 401 && _accessToken) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      setAccessToken(newToken);
      res = await doFetch(newToken);
    } else {
      // Refresh failed — clear and redirect
      setAccessToken(null);
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
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

  const data = (await res.json()) as T;
  return { ok: true, data };
}
