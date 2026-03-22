"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { apiFetch } from "@/lib/api-client";

interface Donation {
  id: string;
  donation_number: string;
  donor_name: string;
  donor_phone: string | null;
  amount: string;
  currency: string;
  campaign: string | null;
  status: string;
  created_at: string;
  updated_at: string | null;
}

const DONATION_TRANSITIONS: Record<string, string[]> = {
  pending: ["received", "cancelled"],
  received: ["receipted", "cancelled"],
  receipted: [],
  cancelled: [],
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  received: "bg-blue-100 text-blue-800",
  receipted: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
};

function DonationsContent() {
  const [donations, setDonations] = useState<Donation[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState<string | null>(null);
  const t = useTranslations("dashboardDonations");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      const result = await apiFetch<Donation[]>("/api/v1/tenants/me/donations");
      if (cancelled) return;
      if (result.ok) {
        setDonations(result.data);
      } else {
        setError(result.detail);
      }
      setLoading(false);
    }
    load();
    return () => { cancelled = true; };
  }, []);

  async function handleTransition(donationId: string, newStatus: string) {
    setTransitioning(donationId);
    setError("");
    const result = await apiFetch<Donation>(
      `/api/v1/tenants/me/donations/${donationId}/status`,
      {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      }
    );
    setTransitioning(null);
    if (result.ok) {
      setDonations((prev) =>
        prev.map((d) =>
          d.id === donationId
            ? { ...d, status: result.data.status, updated_at: result.data.updated_at }
            : d
        )
      );
    } else {
      setError(typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail));
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-gray-900">{t("title")}</h1>
        <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      {error && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-gray-400">{t("loading")}</p>
        ) : donations.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">{t("empty")}</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">{t("thNumber")}</th>
                  <th className="px-4 py-3">{t("thDonor")}</th>
                  <th className="px-4 py-3">{t("thAmount")}</th>
                  <th className="px-4 py-3">{t("thCampaign")}</th>
                  <th className="px-4 py-3">{t("thStatus")}</th>
                  <th className="px-4 py-3">{t("thCreated")}</th>
                  <th className="px-4 py-3">{t("thActions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {donations.map((don) => {
                  const allowed = DONATION_TRANSITIONS[don.status] ?? [];
                  return (
                    <tr key={don.id}>
                      <td className="px-4 py-3 font-mono text-gray-900">
                        {don.donation_number}
                      </td>
                      <td className="px-4 py-3 text-gray-700">{don.donor_name}</td>
                      <td className="px-4 py-3 text-gray-700">
                        {don.amount} {don.currency}
                      </td>
                      <td className="px-4 py-3 text-gray-500">{don.campaign ?? "—"}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[don.status] ?? "bg-gray-100 text-gray-600"}`}
                        >
                          {don.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500">
                        {new Date(don.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          {allowed.map((next) => (
                            <button
                              key={next}
                              onClick={() => handleTransition(don.id, next)}
                              disabled={transitioning === don.id}
                              className={`rounded px-2 py-1 text-xs font-medium disabled:opacity-50 ${
                                next === "cancelled"
                                  ? "bg-red-50 text-red-700 hover:bg-red-100"
                                  : "bg-blue-50 text-blue-700 hover:bg-blue-100"
                              }`}
                            >
                              {next}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
    </main>
  );
}

export default function DonationsPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <DonationsContent />
      </DashboardShell>
    </RequireAuth>
  );
}
