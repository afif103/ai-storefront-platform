/**
 * Storefront analytics tracker.
 *
 * - Manages visitor ID (localStorage, persistent) and session ID (rolling 30-min expiry).
 * - Captures UTM attribution once (first-touch sticks).
 * - Queues events and flushes in batches (max 20) to the public ingest endpoint.
 * - Flush triggers: 5 events queued, 2-second debounce, or page hide.
 * - Never blocks UX — all network errors are swallowed.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const SESSION_EXPIRY_MS = 30 * 60 * 1000; // 30 minutes
const FLUSH_THRESHOLD = 5;
const FLUSH_DEBOUNCE_MS = 2000;
const BATCH_MAX = 20;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface QueuedEvent {
  name: string;
  ts?: string;
  props?: Record<string, unknown>;
}

interface StoredSession {
  id: string;
  expiresAt: number;
}

interface Attribution {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  referrer?: string;
}

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

let _slug: string | null = null;
const _queue: QueuedEvent[] = [];
let _flushTimer: ReturnType<typeof setTimeout> | null = null;
let _listenersBound = false;

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

// ---------------------------------------------------------------------------
// Visitor ID
// ---------------------------------------------------------------------------

export function getOrCreateVisitorId(): string {
  if (!isBrowser()) return "";
  let id = localStorage.getItem("analytics_visitor_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("analytics_visitor_id", id);
  }
  return id;
}

// ---------------------------------------------------------------------------
// Session ID (rolling expiry)
// ---------------------------------------------------------------------------

export function getOrCreateSessionId(): string {
  if (!isBrowser()) return "";
  const raw = localStorage.getItem("analytics_session_id");
  if (raw) {
    try {
      const stored: StoredSession = JSON.parse(raw);
      if (stored.expiresAt > Date.now()) {
        stored.expiresAt = Date.now() + SESSION_EXPIRY_MS;
        localStorage.setItem("analytics_session_id", JSON.stringify(stored));
        return stored.id;
      }
    } catch {
      /* corrupted — fall through to regenerate */
    }
  }
  const session: StoredSession = {
    id: crypto.randomUUID(),
    expiresAt: Date.now() + SESSION_EXPIRY_MS,
  };
  localStorage.setItem("analytics_session_id", JSON.stringify(session));
  return session.id;
}

// ---------------------------------------------------------------------------
// Attribution (first-touch sticks)
// ---------------------------------------------------------------------------

export function captureAttributionOnce(): void {
  if (!isBrowser()) return;
  if (localStorage.getItem("analytics_attribution")) return;

  const params = new URLSearchParams(window.location.search);
  const attr: Attribution = {};

  const src = params.get("utm_source");
  const med = params.get("utm_medium");
  const camp = params.get("utm_campaign");
  const cont = params.get("utm_content");
  const term = params.get("utm_term");
  const ref = document.referrer;

  if (src) attr.utm_source = src;
  if (med) attr.utm_medium = med;
  if (camp) attr.utm_campaign = camp;
  if (cont) attr.utm_content = cont;
  if (term) attr.utm_term = term;
  if (ref) attr.referrer = ref;

  localStorage.setItem("analytics_attribution", JSON.stringify(attr));
}

function getAttribution(): Attribution {
  if (!isBrowser()) return {};
  try {
    const raw = localStorage.getItem("analytics_attribution");
    return raw ? (JSON.parse(raw) as Attribution) : {};
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// Init + lifecycle
// ---------------------------------------------------------------------------

export function initAnalytics(slug: string): void {
  _slug = slug;
  if (!isBrowser()) return;
  captureAttributionOnce();
  bindLifecycleListeners();
}

function bindLifecycleListeners(): void {
  if (_listenersBound || !isBrowser()) return;
  _listenersBound = true;

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
  window.addEventListener("pagehide", () => flush());
}

// ---------------------------------------------------------------------------
// track + flush
// ---------------------------------------------------------------------------

export function track(
  name: string,
  props?: Record<string, unknown>,
): void {
  if (!isBrowser() || !_slug) return;

  // Refresh session expiry
  getOrCreateSessionId();

  const event: QueuedEvent = { name };
  if (props) event.props = props;
  _queue.push(event);

  if (_queue.length >= FLUSH_THRESHOLD) {
    flush();
  } else {
    scheduleFlush();
  }
}

function scheduleFlush(): void {
  if (_flushTimer) clearTimeout(_flushTimer);
  _flushTimer = setTimeout(() => flush(), FLUSH_DEBOUNCE_MS);
}

export function flush(): void {
  if (_flushTimer) {
    clearTimeout(_flushTimer);
    _flushTimer = null;
  }
  if (!_slug || _queue.length === 0 || !isBrowser()) return;

  const visitorId = getOrCreateVisitorId();
  const sessionId = getOrCreateSessionId();
  const attribution = getAttribution();

  const batch = _queue.splice(0, BATCH_MAX);

  const body = JSON.stringify({
    visitor_id: visitorId,
    session_id: sessionId,
    ...attribution,
    events: batch.map((e) => ({
      name: e.name,
      ...(e.ts ? { ts: e.ts } : {}),
      ...(e.props ? { props: e.props } : {}),
    })),
  });

  const url = `${API_BASE_URL}/api/v1/storefront/${_slug}/analytics/events`;

  // Fire-and-forget with keepalive so it survives page unload
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {
    /* swallow — never block UX */
  });

  // Drain remaining events if any
  if (_queue.length > 0) scheduleFlush();
}
