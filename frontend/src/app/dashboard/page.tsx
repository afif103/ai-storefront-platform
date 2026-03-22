"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { apiFetch } from "@/lib/api-client";

interface HealthStatus {
  status: string;
  db: string;
  redis: string;
  version: string;
}

// ---------------------------------------------------------------------------
// Nav card data
// ---------------------------------------------------------------------------

const NAV_CARDS: { titleKey: string; descKey: string; href: string }[] = [
  {
    titleKey: "cardAnalytics",
    descKey: "cardAnalyticsDesc",
    href: "/dashboard/analytics",
  },
  {
    titleKey: "cardAssistant",
    descKey: "cardAssistantDesc",
    href: "/dashboard/assistant",
  },
  {
    titleKey: "cardStorefront",
    descKey: "cardStorefrontDesc",
    href: "/dashboard/storefront",
  },
  {
    titleKey: "cardCategories",
    descKey: "cardCategoriesDesc",
    href: "/dashboard/categories",
  },
  {
    titleKey: "cardProducts",
    descKey: "cardProductsDesc",
    href: "/dashboard/products",
  },
  {
    titleKey: "cardOrders",
    descKey: "cardOrdersDesc",
    href: "/dashboard/orders",
  },
  {
    titleKey: "cardDonations",
    descKey: "cardDonationsDesc",
    href: "/dashboard/donations",
  },
  {
    titleKey: "cardPledges",
    descKey: "cardPledgesDesc",
    href: "/dashboard/pledges",
  },
];

// ---------------------------------------------------------------------------
// Status dot component
// ---------------------------------------------------------------------------

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`}
      aria-hidden="true"
    />
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function DashboardContent() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthError, setHealthError] = useState("");
  const t = useTranslations("dashboardHome");

  useEffect(() => {
    async function checkHealth() {
      const result = await apiFetch<HealthStatus>("/api/v1/health");
      if (result.ok) {
        setHealth(result.data);
      } else {
        setHealthError(result.detail);
      }
    }
    checkHealth();
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      {/* Navigation grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {NAV_CARDS.map((card) => (
          <div
            key={card.href}
            className="rounded-lg border bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
          >
            <h2 className="text-base font-semibold text-gray-900">
              {t(card.titleKey)}
            </h2>
            <p className="mt-1 text-sm text-gray-500">{t(card.descKey)}</p>
            <Link
              href={card.href}
              className="mt-4 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              {t("openLink", { title: t(card.titleKey) })}
            </Link>
          </div>
        ))}
      </div>

      {/* Platform Admin — always visible, backend 403 is the real guard */}
      <div className="mt-8 rounded-lg border-l-4 border-gray-800 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-gray-900">
          {t("platformAdmin")}
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          {t("platformAdminDesc")}
        </p>
        <Link
          href="/dashboard/admin/tenants"
          className="mt-4 inline-block rounded bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-900"
        >
          {t("platformAdminButton")}
        </Link>
      </div>

      {/* System Status */}
      <div className="mt-8 rounded-lg border bg-white px-5 py-4 shadow-sm">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
          {t("systemStatus")}
        </h2>
        {healthError ? (
          <p className="mt-2 text-sm text-red-600">
            {t("backendError", { error: healthError })}
          </p>
        ) : health ? (
          <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm text-gray-600">
            <span className="flex items-center gap-1.5">
              <StatusDot ok={health.status === "ok"} />
              {t("apiLabel")} {health.status}
            </span>
            <span className="flex items-center gap-1.5">
              <StatusDot ok={health.db === "ok"} />
              {t("databaseLabel")} {health.db}
            </span>
            <span className="flex items-center gap-1.5">
              <StatusDot ok={health.redis === "ok"} />
              {t("redisLabel")} {health.redis}
            </span>
            <span className="text-xs text-gray-400">v{health.version}</span>
          </div>
        ) : (
          <p className="mt-2 text-sm text-gray-400">{t("checking")}</p>
        )}
      </div>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <DashboardContent />
      </DashboardShell>
    </RequireAuth>
  );
}
