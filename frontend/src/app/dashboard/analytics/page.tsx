"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { apiFetch } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types matching AnalyticsSummaryResponse
// ---------------------------------------------------------------------------

interface FunnelStep {
  event_name: string;
  count: number;
  rate: number;
}

interface DailyPoint {
  date: string;
  storefront_views: number;
  submissions: number;
}

interface SummaryData {
  visitors: number;
  sessions: number;
  event_counts: Record<string, number>;
  funnel: FunnelStep[];
  daily_series: DailyPoint[] | null;
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

type RangePreset = "7d" | "30d" | "90d";

function dateRange(preset: RangePreset): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  const days = preset === "7d" ? 7 : preset === "30d" ? 30 : 90;
  from.setDate(from.getDate() - days);
  // +1 day on `to` so today is included (endpoint uses exclusive upper bound)
  to.setDate(to.getDate() + 1);
  return {
    from: from.toISOString().split("T")[0],
    to: to.toISOString().split("T")[0],
  };
}

const RANGE_LABEL_KEYS: Record<RangePreset, string> = {
  "7d": "range7d",
  "30d": "range30d",
  "90d": "range90d",
};

const FUNNEL_LABELS: Record<string, string> = {
  storefront_view: "Storefront Views",
  product_view: "Product Views",
  add_to_cart: "Add to Cart",
  begin_checkout: "Begin Checkout",
  submit_order: "Orders",
  submit_donation: "Donations",
  submit_pledge: "Pledges",
};

const FUNNEL_KEYS: Record<string, string> = {
  storefront_view: "funnelStorefrontViews",
  product_view: "funnelProductViews",
  add_to_cart: "funnelAddToCart",
  begin_checkout: "funnelBeginCheckout",
  submit_order: "funnelOrders",
  submit_donation: "funnelDonations",
  submit_pledge: "funnelPledges",
};

// ---------------------------------------------------------------------------
// CSV export
// ---------------------------------------------------------------------------

function buildCsv(data: SummaryData): string {
  const rows: string[] = [];

  // Section 1: KPI Summary
  rows.push("Section,Metric,Value");
  rows.push(`Summary,Visitors,${data.visitors}`);
  rows.push(`Summary,Sessions,${data.sessions}`);
  for (const step of data.funnel) {
    const label = FUNNEL_LABELS[step.event_name] ?? step.event_name;
    rows.push(`Summary,${label},${step.count}`);
  }

  // Blank line between sections
  rows.push("");

  // Section 2: Funnel with rates
  rows.push("Funnel Step,Count,Rate (%)");
  for (const step of data.funnel) {
    const label = FUNNEL_LABELS[step.event_name] ?? step.event_name;
    rows.push(`${label},${step.count},${(step.rate * 100).toFixed(1)}`);
  }

  // Section 3: Daily series (if present)
  if (data.daily_series && data.daily_series.length > 0) {
    rows.push("");
    rows.push("Date,Storefront Views,Submissions");
    for (const day of data.daily_series) {
      rows.push(`${day.date},${day.storefront_views},${day.submissions}`);
    }
  }

  return rows.join("\n");
}

function downloadCsv(data: SummaryData, preset: RangePreset): void {
  const csv = buildCsv(data);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const today = new Date().toISOString().split("T")[0];
  const a = document.createElement("a");
  a.href = url;
  a.download = `analytics-${preset}-${today}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function AnalyticsContent() {
  const [preset, setPreset] = useState<RangePreset>("7d");
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const t = useTranslations("dashboardAnalytics");

  useEffect(() => {
    async function fetchSummary() {
      setLoading(true);
      setError("");
      const { from, to } = dateRange(preset);
      const result = await apiFetch<SummaryData>(
        `/api/v1/tenants/me/analytics/summary?from=${from}&to=${to}`,
      );
      if (result.ok) {
        setData(result.data);
      } else {
        setError(
          typeof result.detail === "string"
            ? result.detail
            : JSON.stringify(result.detail),
        );
      }
      setLoading(false);
    }
    fetchSummary();
  }, [preset]);

  const ec = data?.event_counts ?? {};

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      {/* Page intro + controls */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-gray-500">
            {t("subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{t(RANGE_LABEL_KEYS[preset])}</span>
          <div className="flex gap-1">
            {(["7d", "30d", "90d"] as RangePreset[]).map((p) => (
              <button
                key={p}
                onClick={() => setPreset(p)}
                className={`rounded px-3 py-1.5 text-sm font-medium ${
                  preset === p
                    ? "bg-blue-600 text-white"
                    : "border border-gray-300 text-gray-700 hover:bg-gray-100"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          <button
            onClick={() => data && downloadCsv(data, preset)}
            disabled={loading || !data || data.visitors === 0}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t("exportCsv")}
          </button>
        </div>
      </div>
        {loading && (
          <p className="text-sm text-gray-400">{t("loading")}</p>
        )}

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-6 text-center text-sm text-red-700">
            {error}
          </div>
        )}

        {data && !loading && (
          <>
            {/* Empty state */}
            {data.visitors === 0 ? (
              <div className="rounded-lg border bg-white p-12 text-center">
                <p className="text-gray-500">
                  {t("emptyTitle")}
                </p>
                <p className="mt-1 text-sm text-gray-400">
                  {t("emptyHint")}
                </p>
              </div>
            ) : (
              <>
                {/* KPI cards */}
                <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
                  <KpiCard label={t("kpiVisitors")} value={data.visitors} />
                  <KpiCard label={t("kpiSessions")} value={data.sessions} />
                  <KpiCard
                    label={t("funnelStorefrontViews")}
                    value={ec.storefront_view ?? 0}
                  />
                  <KpiCard
                    label={t("funnelOrders")}
                    value={ec.submit_order ?? 0}
                  />
                  <KpiCard
                    label={t("funnelDonations")}
                    value={ec.submit_donation ?? 0}
                  />
                  <KpiCard
                    label={t("funnelPledges")}
                    value={ec.submit_pledge ?? 0}
                  />
                </div>

                {/* Funnel */}
                <section className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
                    {t("conversionFunnel")}
                  </h2>
                  <table className="w-full text-left text-sm">
                    <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                      <tr>
                        <th className="px-3 py-2">{t("thStep")}</th>
                        <th className="px-3 py-2 text-right">{t("thCount")}</th>
                        <th className="px-3 py-2 text-right">{t("thRate")}</th>
                        <th className="px-3 py-2">{t("thBar")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {data.funnel.map((step) => (
                        <tr key={step.event_name}>
                          <td className="px-3 py-2 text-gray-900">
                            {FUNNEL_KEYS[step.event_name] ? t(FUNNEL_KEYS[step.event_name]) : step.event_name}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-gray-900">
                            {step.count}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-600">
                            {(step.rate * 100).toFixed(1)}%
                          </td>
                          <td className="px-3 py-2">
                            <div className="h-2 w-full rounded-full bg-gray-100">
                              <div
                                className="h-2 rounded-full bg-blue-500"
                                style={{
                                  width: `${Math.min(step.rate * 100, 100)}%`,
                                }}
                              />
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>

                {/* Daily series */}
                {data.daily_series && data.daily_series.length > 0 && (
                  <section className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
                    <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
                      {t("dailyActivity")}
                    </h2>
                    <table className="w-full text-left text-sm">
                      <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                        <tr>
                          <th className="px-3 py-2">{t("thDate")}</th>
                          <th className="px-3 py-2 text-right">
                            {t("funnelStorefrontViews")}
                          </th>
                          <th className="px-3 py-2 text-right">{t("thSubmissions")}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {data.daily_series.map((day) => (
                          <tr key={day.date}>
                            <td className="px-3 py-2 text-gray-900">
                              {day.date}
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-gray-900">
                              {day.storefront_views}
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-gray-900">
                              {day.submissions}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </section>
                )}
              </>
            )}
          </>
        )}
    </main>
  );
}

function KpiCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </p>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <AnalyticsContent />
      </DashboardShell>
    </RequireAuth>
  );
}
