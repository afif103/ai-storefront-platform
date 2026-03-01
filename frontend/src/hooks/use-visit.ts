"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";

interface VisitResponse {
  visit_id: string;
}

function storageKey(slug: string): string {
  return `visit:${slug}`;
}

function readStoredVisit(slug: string): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(storageKey(slug));
}

/**
 * Create/reuse a storefront visit for UTM attribution.
 *
 * On first load for a given slug, captures UTM params from the URL and
 * POSTs to /storefront/{slug}/visit. The returned visit_id is persisted
 * in localStorage so subsequent loads skip the API call.
 */
export function useVisit(slug: string): { visitId: string | null } {
  const [visitId, setVisitId] = useState<string | null>(() =>
    readStoredVisit(slug)
  );

  useEffect(() => {
    // Already have a visit for this slug — nothing to do
    if (readStoredVisit(slug)) return;

    // Generate a stable session_id for this browser
    let sessionId = localStorage.getItem("session_id");
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      localStorage.setItem("session_id", sessionId);
    }

    // Capture UTM params from current URL (first visit only)
    const params = new URLSearchParams(window.location.search);

    apiFetch<VisitResponse>(`/api/v1/storefront/${slug}/visit`, {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        utm_source: params.get("utm_source") || undefined,
        utm_medium: params.get("utm_medium") || undefined,
        utm_campaign: params.get("utm_campaign") || undefined,
        utm_content: params.get("utm_content") || undefined,
        utm_term: params.get("utm_term") || undefined,
      }),
    }).then((result) => {
      if (result.ok) {
        const key = storageKey(slug);
        localStorage.setItem(key, result.data.visit_id);
        setVisitId(result.data.visit_id);
      }
    });
  }, [slug]);

  return { visitId };
}
