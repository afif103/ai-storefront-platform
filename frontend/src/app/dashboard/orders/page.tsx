"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/require-auth";
import { apiFetch } from "@/lib/api-client";

interface Order {
  id: string;
  order_number: string;
  customer_name: string;
  customer_phone: string | null;
  total_amount: string;
  currency: string;
  status: string;
  created_at: string;
  updated_at: string | null;
}

const ORDER_TRANSITIONS: Record<string, string[]> = {
  pending: ["confirmed", "cancelled"],
  confirmed: ["fulfilled", "cancelled"],
  fulfilled: [],
  cancelled: [],
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-blue-100 text-blue-800",
  fulfilled: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
};

function OrdersContent() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      const result = await apiFetch<Order[]>("/api/v1/tenants/me/orders");
      if (cancelled) return;
      if (result.ok) {
        setOrders(result.data);
      } else {
        setError(result.detail);
      }
      setLoading(false);
    }
    load();
    return () => { cancelled = true; };
  }, []);

  async function handleTransition(orderId: string, newStatus: string) {
    setTransitioning(orderId);
    setError("");
    const result = await apiFetch<Order>(
      `/api/v1/tenants/me/orders/${orderId}/status`,
      {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      }
    );
    setTransitioning(null);
    if (result.ok) {
      setOrders((prev) =>
        prev.map((o) =>
          o.id === orderId
            ? { ...o, status: result.data.status, updated_at: result.data.updated_at }
            : o
        )
      );
    } else {
      setError(typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail));
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">
              Dashboard
            </Link>
            <span className="text-gray-300">/</span>
            <h1 className="text-lg font-semibold text-gray-900">Orders</h1>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {error && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : orders.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">No orders yet.</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Number</th>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Total</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {orders.map((order) => {
                  const allowed = ORDER_TRANSITIONS[order.status] ?? [];
                  return (
                    <tr key={order.id}>
                      <td className="px-4 py-3 font-mono text-gray-900">
                        {order.order_number}
                      </td>
                      <td className="px-4 py-3 text-gray-700">{order.customer_name}</td>
                      <td className="px-4 py-3 text-gray-700">
                        {order.total_amount} {order.currency}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[order.status] ?? "bg-gray-100 text-gray-600"}`}
                        >
                          {order.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500">
                        {new Date(order.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          {allowed.map((next) => (
                            <button
                              key={next}
                              onClick={() => handleTransition(order.id, next)}
                              disabled={transitioning === order.id}
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
    </div>
  );
}

export default function OrdersPage() {
  return (
    <RequireAuth>
      <OrdersContent />
    </RequireAuth>
  );
}
