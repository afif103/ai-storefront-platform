"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/require-auth";
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

const RANGE_LABELS: Record<RangePreset, string> = {
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
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

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function AnalyticsContent() {
  const [preset, setPreset] = useState<RangePreset>("7d");
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="text-sm text-blue-600 hover:underline"
            >
              Dashboard
            </Link>
            <span className="text-gray-400">/</span>
            <h1 className="text-lg font-semibold text-gray-900">Analytics</h1>
          </div>

          {/* Range selector */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">{RANGE_LABELS[preset]}</span>
          </div>
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
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {loading && (
          <p className="text-sm text-gray-400">Loading analytics...</p>
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
                  No data for the selected range.
                </p>
                <p className="mt-1 text-sm text-gray-400">
                  Analytics events will appear here once your storefront
                  receives traffic.
                </p>
              </div>
            ) : (
              <>
                {/* KPI cards */}
                <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
                  <KpiCard label="Visitors" value={data.visitors} />
                  <KpiCard label="Sessions" value={data.sessions} />
                  <KpiCard
                    label="Storefront Views"
                    value={ec.storefront_view ?? 0}
                  />
                  <KpiCard
                    label="Orders"
                    value={ec.submit_order ?? 0}
                  />
                  <KpiCard
                    label="Donations"
                    value={ec.submit_donation ?? 0}
                  />
                  <KpiCard
                    label="Pledges"
                    value={ec.submit_pledge ?? 0}
                  />
                </div>

                {/* Funnel */}
                <section className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
                    Conversion Funnel
                  </h2>
                  <table className="w-full text-left text-sm">
                    <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                      <tr>
                        <th className="px-3 py-2">Step</th>
                        <th className="px-3 py-2 text-right">Count</th>
                        <th className="px-3 py-2 text-right">Rate</th>
                        <th className="px-3 py-2">Bar</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {data.funnel.map((step) => (
                        <tr key={step.event_name}>
                          <td className="px-3 py-2 text-gray-900">
                            {FUNNEL_LABELS[step.event_name] ?? step.event_name}
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
                      Daily Activity
                    </h2>
                    <table className="w-full text-left text-sm">
                      <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                        <tr>
                          <th className="px-3 py-2">Date</th>
                          <th className="px-3 py-2 text-right">
                            Storefront Views
                          </th>
                          <th className="px-3 py-2 text-right">Submissions</th>
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
    </div>
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
      <AnalyticsContent />
    </RequireAuth>
  );
}
