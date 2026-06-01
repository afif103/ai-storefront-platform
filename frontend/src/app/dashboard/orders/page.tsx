"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
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

interface OrderItem {
  name: string;
  qty: number;
  unit_price: string;
  currency: string;
  subtotal: string;
}

interface OrderDetail {
  id: string;
  order_number: string;
  customer_name: string;
  customer_phone: string | null;
  customer_email: string | null;
  items: OrderItem[];
  total_amount: string;
  currency: string;
  status: string;
  source: string;
  payment_method: string | null;
  payment_notes: string | null;
  notes: string | null;
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
  const t = useTranslations("dashboardOrders");
  const tPayment = useTranslations("paymentMethods");
  const paymentMethodLabels: Record<string, string> = {
    cash: tPayment("cash"),
    knet: tPayment("knet"),
    bank_transfer: tPayment("bank_transfer"),
    cod: tPayment("cod"),
    manual: tPayment("manual"),
  };

  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

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

  async function viewOrder(orderId: string) {
    setDetailLoading(true);
    setDetailError("");
    const result = await apiFetch<OrderDetail>(
      `/api/v1/tenants/me/orders/${orderId}`
    );
    if (result.ok) {
      setSelectedOrder(result.data);
    } else {
      setDetailError(
        typeof result.detail === "string"
          ? result.detail
          : JSON.stringify(result.detail)
      );
    }
    setDetailLoading(false);
  }

  if (selectedOrder) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-8">
        <div className="mb-4 flex items-center gap-3 print:hidden">
          <button
            type="button"
            onClick={() => setSelectedOrder(null)}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
          >
            {t("back")}
          </button>
          <h2 className="text-lg font-semibold text-gray-900">{t("receipt")}</h2>
        </div>

        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <p className="text-center text-sm font-medium text-gray-900">
            {t("thNumber")}:{" "}
            <span className="font-mono">{selectedOrder.order_number}</span>
          </p>
          <p className="mt-1 text-center text-xs text-gray-500">
            {new Date(selectedOrder.created_at).toLocaleString()}
          </p>
          <p className="mt-1 text-center text-sm text-gray-700">
            {t("receiptCustomer")} {selectedOrder.customer_name}
          </p>
          {selectedOrder.customer_phone && (
            <p className="mt-0.5 text-center text-xs text-gray-500">
              {t("phone")}: {selectedOrder.customer_phone}
            </p>
          )}
          {selectedOrder.customer_email && (
            <p className="mt-0.5 text-center text-xs text-gray-500">
              {t("email")}: {selectedOrder.customer_email}
            </p>
          )}
          <div className="mt-2 flex justify-center gap-4 text-xs text-gray-500">
            <span>
              {t("statusLabel")}: {selectedOrder.status}
            </span>
            <span>
              {t("source")}: {selectedOrder.source}
            </span>
          </div>

          {selectedOrder.items.length > 0 && (
            <table className="mt-4 w-full text-sm">
              <thead className="border-b text-left text-xs font-medium uppercase text-gray-500">
                <tr>
                  <th className="py-1">{t("item")}</th>
                  <th className="py-1 text-center">{t("qty")}</th>
                  <th className="py-1 text-right">{t("unitPrice")}</th>
                  <th className="py-1 text-right">{t("subtotal")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {selectedOrder.items.map((lineItem, i) => (
                  <tr key={i}>
                    <td className="py-1 text-gray-900">{lineItem.name}</td>
                    <td className="py-1 text-center text-gray-700">
                      {lineItem.qty}
                    </td>
                    <td className="py-1 text-right text-gray-700">
                      {lineItem.unit_price}
                    </td>
                    <td className="py-1 text-right text-gray-700">
                      {lineItem.subtotal}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="mt-3 border-t pt-2 text-right text-sm font-semibold text-gray-900">
            {t("total")}: {selectedOrder.total_amount} {selectedOrder.currency}
          </div>

          {selectedOrder.payment_method && (
            <div className="mt-1 text-right text-sm text-gray-700">
              {t("paymentMethod")}:{" "}
              {paymentMethodLabels[selectedOrder.payment_method] ??
                selectedOrder.payment_method}
            </div>
          )}
          {selectedOrder.payment_notes && (
            <div className="mt-1 text-sm text-gray-700">
              {t("paymentNotes")}: {selectedOrder.payment_notes}
            </div>
          )}
          {selectedOrder.notes && (
            <div className="mt-1 text-sm text-gray-700">
              {t("notes")}: {selectedOrder.notes}
            </div>
          )}
        </div>

        <div className="mt-4 flex gap-3 print:hidden">
          <button
            type="button"
            onClick={() => window.print()}
            className="flex-1 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            {t("printReceipt")}
          </button>
          <button
            type="button"
            onClick={() => setSelectedOrder(null)}
            className="flex-1 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            {t("back")}
          </button>
        </div>
      </main>
    );
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
        {detailError && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {detailError}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-gray-400">{t("loading")}</p>
        ) : orders.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">{t("empty")}</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">{t("thNumber")}</th>
                  <th className="px-4 py-3">{t("thCustomer")}</th>
                  <th className="px-4 py-3">{t("thTotal")}</th>
                  <th className="px-4 py-3">{t("thStatus")}</th>
                  <th className="px-4 py-3">{t("thCreated")}</th>
                  <th className="px-4 py-3">{t("thActions")}</th>
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
                          <button
                            onClick={() => viewOrder(order.id)}
                            disabled={detailLoading}
                            className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200 disabled:opacity-50"
                          >
                            {t("view")}
                          </button>
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

export default function OrdersPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <OrdersContent />
      </DashboardShell>
    </RequireAuth>
  );
}
