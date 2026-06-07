"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { apiFetch } from "@/lib/api-client";

interface Customer {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  created_at: string;
}

interface CustomerListResponse {
  items: Customer[];
  next_cursor: string | null;
  has_more: boolean;
}

interface CustomerOrder {
  id: string;
  order_number: string;
  source: string;
  status: string;
  total_amount: string;
  currency: string;
  fulfillment_status: string | null;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-blue-100 text-blue-800",
  fulfilled: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
};

const FULFILLMENT_COLORS: Record<string, string> = {
  unfulfilled: "bg-gray-100 text-gray-600",
  packed: "bg-amber-100 text-amber-800",
  shipped: "bg-blue-100 text-blue-800",
  delivered: "bg-green-100 text-green-800",
};

function CustomersContent() {
  const t = useTranslations("dashboardCustomers");
  const tOrders = useTranslations("dashboardOrders");
  const fulfillmentLabels: Record<string, string> = {
    unfulfilled: tOrders("fulfillmentUnfulfilled"),
    packed: tOrders("fulfillmentPacked"),
    shipped: tOrders("fulfillmentShipped"),
    delivered: tOrders("fulfillmentDelivered"),
  };

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [customerOrders, setCustomerOrders] = useState<CustomerOrder[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await apiFetch<CustomerListResponse>(
        "/api/v1/tenants/me/customers"
      );
      if (cancelled) return;
      if (result.ok) {
        setCustomers(result.data.items);
        setNextCursor(result.data.next_cursor);
        setHasMore(result.data.has_more);
      } else {
        setError(
          typeof result.detail === "string"
            ? result.detail
            : JSON.stringify(result.detail)
        );
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleLoadMore() {
    if (!nextCursor) return;
    setLoadingMore(true);
    setError("");
    const result = await apiFetch<CustomerListResponse>(
      `/api/v1/tenants/me/customers?cursor=${encodeURIComponent(nextCursor)}`
    );
    if (result.ok) {
      setCustomers((prev) => [...prev, ...result.data.items]);
      setNextCursor(result.data.next_cursor);
      setHasMore(result.data.has_more);
    } else {
      setError(
        typeof result.detail === "string"
          ? result.detail
          : JSON.stringify(result.detail)
      );
    }
    setLoadingMore(false);
  }

  async function handleViewOrders(customer: Customer) {
    setSelectedCustomer(customer);
    setOrdersError("");
    setOrdersLoading(true);
    const result = await apiFetch<CustomerOrder[]>(
      `/api/v1/tenants/me/customers/${customer.id}/orders`
    );
    if (result.ok) {
      setCustomerOrders(result.data);
    } else {
      setOrdersError(
        typeof result.detail === "string"
          ? result.detail
          : JSON.stringify(result.detail)
      );
    }
    setOrdersLoading(false);
  }

  if (selectedCustomer) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-8">
        <div className="mb-4">
          <button
            type="button"
            onClick={() => {
              setSelectedCustomer(null);
              setOrdersError("");
            }}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
          >
            {t("back")}
          </button>
        </div>

        <div className="mb-6">
          <h1 className="text-lg font-semibold text-gray-900">
            {selectedCustomer.name}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {selectedCustomer.email ?? selectedCustomer.phone ?? "—"}
          </p>
          <h2 className="mt-3 text-sm font-semibold text-gray-700">
            {t("ordersTitle")}
          </h2>
        </div>

        {ordersError && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {t("error")}: {ordersError}
          </div>
        )}

        {ordersLoading ? (
          <p className="text-sm text-gray-400">{t("ordersLoading")}</p>
        ) : customerOrders.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">{t("ordersEmpty")}</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">{t("thNumber")}</th>
                  <th className="px-4 py-3">{t("thDate")}</th>
                  <th className="px-4 py-3">{t("thSource")}</th>
                  <th className="px-4 py-3">{t("thStatus")}</th>
                  <th className="px-4 py-3">{t("thFulfillment")}</th>
                  <th className="px-4 py-3 text-right">{t("thTotal")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {customerOrders.map((order) => (
                  <tr key={order.id}>
                    <td className="px-4 py-3 font-mono text-gray-900">
                      {order.order_number}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(order.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{order.source}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[order.status] ?? "bg-gray-100 text-gray-600"}`}
                      >
                        {order.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${FULFILLMENT_COLORS[order.fulfillment_status ?? "unfulfilled"]}`}
                      >
                        {fulfillmentLabels[order.fulfillment_status ?? "unfulfilled"]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {order.total_amount} {order.currency}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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
          {t("error")}: {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-400">{t("loading")}</p>
      ) : customers.length === 0 ? (
        <div className="rounded-lg border bg-white p-8 text-center">
          <p className="text-gray-500">{t("empty")}</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">{t("thName")}</th>
                  <th className="px-4 py-3">{t("thContact")}</th>
                  <th className="px-4 py-3">{t("thCreated")}</th>
                  <th className="px-4 py-3">{t("thActions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td className="px-4 py-3 text-gray-900">{customer.name}</td>
                    <td className="px-4 py-3 text-gray-700">
                      {customer.email ?? customer.phone ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(customer.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => handleViewOrders(customer)}
                        className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
                      >
                        {t("viewOrders")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <div className="mt-4 text-center">
              <button
                type="button"
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
              >
                {t("loadMore")}
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}

export default function CustomersPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <CustomersContent />
      </DashboardShell>
    </RequireAuth>
  );
}
