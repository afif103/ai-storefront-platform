"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/require-auth";
import { apiFetch } from "@/lib/api-client";

interface AdminTenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  member_count: number;
  order_count: number;
  donation_count: number;
  pledge_count: number;
  last_activity_at: string | null;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString();
}

function formatRelative(iso: string | null): string {
  if (!iso) return "\u2014";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(iso);
}

function AdminTenantsContent() {
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  async function loadTenants() {
    setLoading(true);
    setError("");
    const result = await apiFetch<AdminTenant[]>("/api/v1/admin/tenants");
    if (result.ok) {
      setTenants(result.data);
    } else {
      setError(result.detail);
    }
    setLoading(false);
  }

  useEffect(() => {
    let cancelled = false;
    async function fetchInitial() {
      const result = await apiFetch<AdminTenant[]>("/api/v1/admin/tenants");
      if (cancelled) return;
      if (result.ok) {
        setTenants(result.data);
      } else {
        setError(result.detail);
      }
      setLoading(false);
    }
    fetchInitial();
    return () => { cancelled = true; };
  }, []);

  async function handleSuspend(id: string, name: string) {
    if (!window.confirm(`Suspend tenant "${name}"? All tenant-scoped API access will be blocked.`)) {
      return;
    }
    setActionId(id);
    setActionResult(null);
    const result = await apiFetch(`/api/v1/admin/tenants/${id}/suspend`, {
      method: "POST",
    });
    setActionId(null);
    if (result.ok) {
      setActionResult({ type: "success", message: `"${name}" suspended.` });
      setTenants((prev) =>
        prev.map((t) => (t.id === id ? { ...t, is_active: false } : t))
      );
    } else {
      setActionResult({ type: "error", message: result.detail });
    }
  }

  async function handleReactivate(id: string, name: string) {
    setActionId(id);
    setActionResult(null);
    const result = await apiFetch(`/api/v1/admin/tenants/${id}/reactivate`, {
      method: "POST",
    });
    setActionId(null);
    if (result.ok) {
      setActionResult({ type: "success", message: `"${name}" reactivated.` });
      setTenants((prev) =>
        prev.map((t) => (t.id === id ? { ...t, is_active: true } : t))
      );
    } else {
      setActionResult({ type: "error", message: result.detail });
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">
              Dashboard
            </Link>
            <span className="text-gray-300">/</span>
            <h1 className="text-lg font-semibold text-gray-900">Admin: Tenants</h1>
          </div>
          <button
            onClick={loadTenants}
            disabled={loading}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50"
          >
            Refresh
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {error && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {actionResult && (
          <div
            className={`mb-4 rounded border p-3 text-sm ${
              actionResult.type === "success"
                ? "border-green-300 bg-green-50 text-green-700"
                : "border-red-300 bg-red-50 text-red-700"
            }`}
          >
            {actionResult.message}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : tenants.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">No tenants found.</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Tenant</th>
                  <th className="px-4 py-3">Slug</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Members</th>
                  <th className="px-4 py-3 text-right">Orders</th>
                  <th className="px-4 py-3 text-right">Donations</th>
                  <th className="px-4 py-3 text-right">Pledges</th>
                  <th className="px-4 py-3">Last Activity</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {tenants.map((t) => (
                  <tr key={t.id} className={!t.is_active ? "bg-red-50/50" : ""}>
                    <td className="px-4 py-3 font-medium text-gray-900">{t.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-600">{t.slug}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                          t.is_active
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {t.is_active ? "Active" : "Suspended"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">{t.member_count}</td>
                    <td className="px-4 py-3 text-right text-gray-700">{t.order_count}</td>
                    <td className="px-4 py-3 text-right text-gray-700">{t.donation_count}</td>
                    <td className="px-4 py-3 text-right text-gray-700">{t.pledge_count}</td>
                    <td className="px-4 py-3 text-gray-500">{formatRelative(t.last_activity_at)}</td>
                    <td className="px-4 py-3 text-gray-500">{formatDate(t.created_at)}</td>
                    <td className="px-4 py-3">
                      {t.is_active ? (
                        <button
                          onClick={() => handleSuspend(t.id, t.name)}
                          disabled={actionId === t.id}
                          className="rounded bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                        >
                          {actionId === t.id ? "..." : "Suspend"}
                        </button>
                      ) : (
                        <button
                          onClick={() => handleReactivate(t.id, t.name)}
                          disabled={actionId === t.id}
                          className="rounded bg-green-50 px-2 py-1 text-xs font-medium text-green-700 hover:bg-green-100 disabled:opacity-50"
                        >
                          {actionId === t.id ? "..." : "Reactivate"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

export default function AdminTenantsPage() {
  return (
    <RequireAuth>
      <AdminTenantsContent />
    </RequireAuth>
  );
}
