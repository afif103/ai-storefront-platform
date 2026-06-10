"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { apiFetch } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types matching SalesSummaryResponse
// ---------------------------------------------------------------------------

interface ChannelSales {
  source: string;
  order_count: number;
  gross_sales: string;
}

interface PaymentMethodSales {
  payment_method: string | null;
  order_count: number;
  gross_sales: string;
}

interface SalesSummary {
  currency: string;
  total_sales: string;
  total_orders: number;
  average_order_value: string;
  storefront_sales: string;
  storefront_orders: number;
  pos_sales: string;
  pos_orders: number;
  cancelled_orders: number;
  cancelled_amount: string;
  by_channel: ChannelSales[];
  by_payment_method: PaymentMethodSales[];
}

// ---------------------------------------------------------------------------
// Types matching RevenueAnalyticsResponse (M13.2)
// ---------------------------------------------------------------------------

interface DailyRevenuePoint {
  date: string;
  order_count: number;
  gross_sales: string;
  storefront_sales: string;
  pos_sales: string;
}

interface ProductRevenue {
  product_id: string;
  name: string;
  qty_sold: number;
  gross_sales: string;
}

interface RevenueAnalytics {
  currency: string;
  by_day: DailyRevenuePoint[];
  top_products: ProductRevenue[];
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

type RangePreset = "7d" | "30d" | "90d";

function dateRange(preset: RangePreset): { from: string; to: string } {
  const today = new Date();
  const days = preset === "7d" ? 7 : preset === "30d" ? 30 : 90;
  const from = new Date();
  from.setDate(from.getDate() - days);
  // The backend applies the exclusive upper bound (adds 1 day to `to`),
  // so send to=today (not today+1).
  return {
    from: from.toISOString().split("T")[0],
    to: today.toISOString().split("T")[0],
  };
}

const RANGE_LABEL_KEYS: Record<RangePreset, string> = {
  "7d": "range7d",
  "30d": "range30d",
  "90d": "range90d",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function SalesReportContent() {
  const t = useTranslations("dashboardReports");
  const [preset, setPreset] = useState<RangePreset>("30d");
  const [data, setData] = useState<SalesSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revenueData, setRevenueData] = useState<RevenueAnalytics | null>(null);
  const [revenueError, setRevenueError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      const { from, to } = dateRange(preset);
      const result = await apiFetch<SalesSummary>(
        `/api/v1/tenants/me/analytics/sales?from=${from}&to=${to}`,
      );
      if (cancelled) return;
      if (result.ok) {
        setData(result.data);
      } else {
        setError(
          typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail),
        );
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [preset]);

  // Independent revenue-analytics fetch (M13.2): shares only the `preset`, so a
  // failure here never blocks the M13.1 sales report rendered above. revenueData
  // is cleared at fetch start and on error so no stale rows show across ranges.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setRevenueError("");
      setRevenueData(null);
      const { from, to } = dateRange(preset);
      const result = await apiFetch<RevenueAnalytics>(
        `/api/v1/tenants/me/analytics/revenue?from=${from}&to=${to}`,
      );
      if (cancelled) return;
      if (result.ok) {
        setRevenueData(result.data);
      } else {
        setRevenueData(null);
        setRevenueError(
          typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail),
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [preset]);

  function channelLabel(source: string): string {
    if (source === "storefront") return t("channelStorefront");
    if (source === "pos") return t("channelPos");
    return source;
  }

  const isEmpty = data && data.total_orders === 0 && data.cancelled_orders === 0;

  const showRevenue =
    revenueData !== null &&
    !revenueError &&
    (revenueData.by_day.length > 0 || revenueData.top_products.length > 0);

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      {/* Header + range controls */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
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
        </div>
      </div>

      {loading && <p className="text-sm text-gray-400">{t("loading")}</p>}

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-6 text-sm text-red-700">
          {t("error")}: {error}
        </div>
      )}

      {data && !loading && !error && (
        <>
          {isEmpty ? (
            <div className="rounded-lg border bg-white p-12 text-center">
              <p className="text-gray-500">{t("empty")}</p>
            </div>
          ) : (
            <>
              {/* KPI cards */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <KpiCard
                  label={t("kpiTotalSales")}
                  value={`${data.total_sales} ${data.currency}`}
                />
                <KpiCard label={t("kpiTotalOrders")} value={data.total_orders} />
                <KpiCard
                  label={t("kpiAvgOrderValue")}
                  value={`${data.average_order_value} ${data.currency}`}
                />
                <KpiCard
                  label={t("kpiStorefrontSales")}
                  value={`${data.storefront_sales} ${data.currency}`}
                />
                <KpiCard
                  label={t("kpiPosSales")}
                  value={`${data.pos_sales} ${data.currency}`}
                />
                <KpiCard
                  label={t("kpiCancelled")}
                  value={data.cancelled_orders}
                  hint={`${data.cancelled_amount} ${data.currency}`}
                />
              </div>

              {/* By Channel */}
              <section className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
                  {t("byChannel")}
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                      <tr>
                        <th className="px-3 py-2">{t("thChannel")}</th>
                        <th className="px-3 py-2 text-right">{t("thOrders")}</th>
                        <th className="px-3 py-2 text-right">{t("thGrossSales")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {data.by_channel.map((c) => (
                        <tr key={c.source}>
                          <td className="px-3 py-2 text-gray-900">{channelLabel(c.source)}</td>
                          <td className="px-3 py-2 text-right font-mono text-gray-900">
                            {c.order_count}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-700">
                            {c.gross_sales} {data.currency}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* By Payment Method */}
              <section className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
                  {t("byPaymentMethod")}
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                      <tr>
                        <th className="px-3 py-2">{t("thMethod")}</th>
                        <th className="px-3 py-2 text-right">{t("thOrders")}</th>
                        <th className="px-3 py-2 text-right">{t("thGrossSales")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {data.by_payment_method.map((m) => (
                        <tr key={m.payment_method ?? "__unspecified__"}>
                          <td className="px-3 py-2 text-gray-900">
                            {m.payment_method ?? t("methodUnspecified")}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-gray-900">
                            {m.order_count}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-700">
                            {m.gross_sales} {data.currency}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </>
      )}

      {revenueError && (
        <div className="mt-8 rounded-lg border border-red-300 bg-red-50 p-6 text-sm text-red-700">
          {t("revenueError")}: {revenueError}
        </div>
      )}

      {showRevenue && revenueData && (
        <>
          {/* Revenue Over Time */}
          <section className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
              {t("revenueOverTime")}
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-3 py-2">{t("thDate")}</th>
                    <th className="px-3 py-2 text-right">{t("thOrders")}</th>
                    <th className="px-3 py-2 text-right">{t("thStorefront")}</th>
                    <th className="px-3 py-2 text-right">{t("thPos")}</th>
                    <th className="px-3 py-2 text-right">{t("thTotal")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {revenueData.by_day.map((d) => (
                    <tr key={d.date}>
                      <td className="px-3 py-2 text-gray-900">{d.date}</td>
                      <td className="px-3 py-2 text-right font-mono text-gray-900">
                        {d.order_count}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-700">
                        {d.storefront_sales} {revenueData.currency}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-700">
                        {d.pos_sales} {revenueData.currency}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-900">
                        {d.gross_sales} {revenueData.currency}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Top Products */}
          <section className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
              {t("topProducts")}
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-3 py-2">{t("thProduct")}</th>
                    <th className="px-3 py-2 text-right">{t("thQtySold")}</th>
                    <th className="px-3 py-2 text-right">{t("thRevenue")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {revenueData.top_products.map((p) => (
                    <tr key={p.product_id}>
                      <td className="px-3 py-2 text-gray-900">{p.name}</td>
                      <td className="px-3 py-2 text-right font-mono text-gray-900">
                        {p.qty_sold}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-700">
                        {p.gross_sales} {revenueData.currency}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

function KpiCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-gray-400">{hint}</p>}
    </div>
  );
}

export default function ReportsPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <SalesReportContent />
      </DashboardShell>
    </RequireAuth>
  );
}
