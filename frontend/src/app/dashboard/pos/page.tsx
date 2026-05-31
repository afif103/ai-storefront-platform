"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { apiFetch } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Product {
  id: string;
  name: string;
  price_amount: string;
  effective_currency: string;
  is_active: boolean;
  track_inventory: boolean;
  stock_qty: number | null;
  sku: string | null;
  barcode: string | null;
}

interface PaginatedProducts {
  items: Product[];
  next_cursor: string | null;
  has_more: boolean;
}

interface CartLine {
  productId: string;
  qty: number;
}

interface OrderItem {
  name: string;
  qty: number;
  unit_price: string;
  currency: string;
  subtotal: string;
}

interface OrderResponse {
  id: string;
  order_number: string;
  customer_name: string;
  items: OrderItem[];
  total_amount: string;
  currency: string;
  status: string;
  source: string;
  created_at: string;
}

interface HistoryOrder {
  id: string;
  order_number: string;
  customer_name: string;
  total_amount: string;
  currency: string;
  created_at: string;
  status: string;
}

interface PaginatedHistory {
  items: HistoryOrder[];
  next_cursor: string | null;
  has_more: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function canSell(p: Product): boolean {
  if (!p.is_active) return false;
  if (p.track_inventory && (p.stock_qty ?? 0) <= 0) return false;
  return true;
}

function maxQty(p: Product): number {
  if (!p.track_inventory) return Infinity;
  return p.stock_qty ?? 0;
}

// ---------------------------------------------------------------------------
// Inner content
// ---------------------------------------------------------------------------

function POSContent() {
  const t = useTranslations("pos");
  const { bootstrap } = useAuth();
  const storeName = bootstrap?.memberships?.[0]?.tenant_name;

  // Product catalog
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  // Cart
  const [cart, setCart] = useState<CartLine[]>([]);

  // Checkout
  const [customerName, setCustomerName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Success
  const [lastOrder, setLastOrder] = useState<OrderResponse | null>(null);

  // History
  const [showHistory, setShowHistory] = useState(false);
  const [historyOrders, setHistoryOrders] = useState<HistoryOrder[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");

  // Cancel
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState("");

  // ------ Fetch products ------

  const [refreshKey, setRefreshKey] = useState(0);

  function refreshProducts() {
    setLoading(true);
    setError("");
    setRefreshKey((k) => k + 1);
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await apiFetch<PaginatedProducts>(
        "/api/v1/tenants/me/products",
      );
      if (cancelled) return;
      if (result.ok) {
        setProducts(result.data.items.filter(canSell));
      } else {
        setError(result.detail);
      }
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [refreshKey]);

  // ------ Filtered products ------

  const filtered = (() => {
    const q = search.trim().toLowerCase();
    if (!q) return products;
    return products.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.sku ?? "").toLowerCase().includes(q) ||
        (p.barcode ?? "").toLowerCase().includes(q),
    );
  })();

  // ------ Cart helpers ------

  function cartQty(productId: string): number {
    return cart.find((l) => l.productId === productId)?.qty ?? 0;
  }

  function addToCart(productId: string) {
    const p = products.find((pr) => pr.id === productId);
    if (!p) return;
    const current = cartQty(productId);
    if (current >= maxQty(p)) return;

    setCart((prev) => {
      const idx = prev.findIndex((l) => l.productId === productId);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], qty: next[idx].qty + 1 };
        return next;
      }
      return [...prev, { productId, qty: 1 }];
    });
  }

  function updateQty(productId: string, qty: number) {
    if (qty < 1) return removeFromCart(productId);
    const p = products.find((pr) => pr.id === productId);
    const clamped = p ? Math.min(qty, maxQty(p)) : qty;
    setCart((prev) =>
      prev.map((l) =>
        l.productId === productId ? { ...l, qty: clamped } : l,
      ),
    );
  }

  function removeFromCart(productId: string) {
    setCart((prev) => prev.filter((l) => l.productId !== productId));
  }

  function cartTotal(): number {
    return cart.reduce((sum, line) => {
      const p = products.find((pr) => pr.id === line.productId);
      return sum + (p ? parseFloat(p.price_amount) * line.qty : 0);
    }, 0);
  }

  const currency = products[0]?.effective_currency ?? "KWD";

  // ------ Checkout ------

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (cart.length === 0) return;
    setSubmitting(true);
    setError("");

    const result = await apiFetch<OrderResponse>(
      "/api/v1/tenants/me/pos/orders",
      {
        method: "POST",
        body: JSON.stringify({
          items: cart.map((l) => ({
            catalog_item_id: l.productId,
            qty: l.qty,
          })),
          customer_name: customerName || undefined,
        }),
      },
    );

    if (result.ok) {
      setLastOrder(result.data);
      setCart([]);
      setCustomerName("");
    } else {
      if (result.status === 409) {
        setError(t("insufficientStock"));
      } else {
        setError(result.detail || t("saleFailed"));
      }
    }
    setSubmitting(false);
  }

  // ------ History ------

  async function openHistory() {
    setShowHistory(true);
    setHistoryLoading(true);
    setHistoryError("");
    const result = await apiFetch<PaginatedHistory>(
      "/api/v1/tenants/me/pos/orders",
    );
    if (result.ok) {
      setHistoryOrders(result.data.items);
    } else {
      setHistoryError(result.detail);
    }
    setHistoryLoading(false);
  }

  async function viewHistoryOrder(id: string) {
    const result = await apiFetch<OrderResponse>(
      `/api/v1/tenants/me/pos/orders/${id}`,
    );
    if (result.ok) {
      setLastOrder(result.data);
    }
  }

  async function cancelOrder(id: string) {
    if (!window.confirm(t("cancelConfirm"))) return;
    setCancelling(true);
    setCancelError("");
    const result = await apiFetch<OrderResponse>(
      `/api/v1/tenants/me/pos/orders/${id}/cancel`,
      { method: "PATCH" },
    );
    if (result.ok) {
      setLastOrder(result.data);
      setHistoryOrders((prev) =>
        prev.map((o) => (o.id === id ? { ...o, status: "cancelled" } : o)),
      );
    } else {
      setCancelError(result.detail || t("cancelFailed"));
    }
    setCancelling(false);
  }

  // ------ Success screen ------

  if (lastOrder) {
    return (
      <main className="mx-auto max-w-md px-6 py-16">
        <div className="rounded-lg border bg-white p-8 shadow-sm">
          {storeName && (
            <p className="text-center text-sm font-medium text-gray-900">
              {storeName}
            </p>
          )}
          <h2 className="mt-1 text-center text-xl font-semibold text-green-700">
            {t("saleComplete")}
          </h2>
          <p className="mt-3 text-center text-sm text-gray-700">
            {t("orderNumber", { number: lastOrder.order_number })}
          </p>
          <p className="mt-1 text-center text-sm text-gray-700">
            {t("receiptCustomer", {
              name: lastOrder.customer_name || t("customerNamePlaceholder"),
            })}
          </p>
          <p className="mt-1 text-center text-xs text-gray-500">
            {new Date(lastOrder.created_at).toLocaleString()}
          </p>

          {/* Line items */}
          <table className="mt-4 w-full text-sm">
            <thead className="border-b text-left text-xs font-medium uppercase text-gray-500">
              <tr>
                <th className="py-1">{t("name")}</th>
                <th className="py-1 text-center">{t("qty")}</th>
                <th className="py-1 text-right">{t("receiptUnitPrice")}</th>
                <th className="py-1 text-right">{t("subtotal")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {lastOrder.items.map((item, i) => (
                <tr key={i}>
                  <td className="py-1 text-gray-900">{item.name}</td>
                  <td className="py-1 text-center text-gray-700">
                    {item.qty}
                  </td>
                  <td className="py-1 text-right text-gray-700">
                    {item.unit_price}
                  </td>
                  <td className="py-1 text-right text-gray-700">
                    {item.subtotal}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Total */}
          <div className="mt-3 border-t pt-2 text-right text-sm font-semibold text-gray-900">
            {t("saleTotal", {
              total: lastOrder.total_amount,
              currency: lastOrder.currency,
            })}
          </div>

          {lastOrder.status === "cancelled" && (
            <p className="mt-2 text-center text-xs font-medium uppercase text-red-600 print:hidden">
              {t("cancelledBadge")}
            </p>
          )}

          {/* Actions (hidden on print) */}
          <div className="mt-6 flex gap-3 print:hidden">
            <button
              onClick={() => window.print()}
              className="flex-1 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              {t("printReceipt")}
            </button>
            {lastOrder.status !== "cancelled" && (
              <button
                onClick={() => cancelOrder(lastOrder.id)}
                disabled={cancelling}
                className="flex-1 rounded border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                {cancelling ? t("cancelling") : t("cancelOrder")}
              </button>
            )}
            <button
              onClick={() => {
                setLastOrder(null);
                setShowHistory(false);
                refreshProducts();
              }}
              className="flex-1 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              {t("newSale")}
            </button>
          </div>
          {cancelError && (
            <p className="mt-2 text-center text-xs text-red-600 print:hidden">
              {cancelError}
            </p>
          )}
        </div>
      </main>
    );
  }

  // ------ History view ------

  if (showHistory) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6 flex items-center gap-4 print:hidden">
          <button
            onClick={() => setShowHistory(false)}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
          >
            {t("historyBack")}
          </button>
          <h2 className="text-lg font-semibold text-gray-900">
            {t("historyTitle")}
          </h2>
        </div>

        {historyLoading ? (
          <p className="text-sm text-gray-400">{t("historyLoading")}</p>
        ) : historyError ? (
          <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {historyError}
          </div>
        ) : historyOrders.length === 0 ? (
          <p className="text-sm text-gray-500">{t("historyEmpty")}</p>
        ) : (
          <div className="overflow-hidden rounded-lg border bg-white">
            <table className="w-full text-sm">
              <thead className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-2">{t("historyOrderNum")}</th>
                  <th className="px-4 py-2">{t("historyCustomer")}</th>
                  <th className="px-4 py-2">{t("total")}</th>
                  <th className="px-4 py-2">{t("historyDate")}</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {historyOrders.map((o) => (
                  <tr key={o.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium text-gray-900">
                      {o.order_number}
                      {o.status === "cancelled" && (
                        <span className="ml-2 text-xs font-medium uppercase text-red-500">
                          {t("cancelledBadge")}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-gray-700">
                      {o.customer_name}
                    </td>
                    <td className="px-4 py-2 text-gray-700">
                      {o.total_amount} {o.currency}
                    </td>
                    <td className="px-4 py-2 text-gray-500">
                      {new Date(o.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => viewHistoryOrder(o.id)}
                        className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700"
                      >
                        {t("historyView")}
                      </button>
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

  // ------ Main layout ------

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">{t("title")}</h1>
        <button
          onClick={openHistory}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100 print:hidden"
        >
          {t("historyTitle")}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ---- Product catalog (2/3) ---- */}
        <div className="lg:col-span-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />

          {loading ? (
            <p className="text-sm text-gray-400">{t("loading")}</p>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-gray-500">{t("noProducts")}</p>
          ) : (
            <div className="overflow-hidden rounded-lg border bg-white">
              <table className="w-full text-sm">
                <thead className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                  <tr>
                    <th className="px-4 py-2">{t("name")}</th>
                    <th className="px-4 py-2">{t("price")}</th>
                    <th className="px-4 py-2">{t("stock")}</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filtered.map((p) => {
                    const atMax = cartQty(p.id) >= maxQty(p);
                    return (
                      <tr key={p.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-medium text-gray-900">
                          {p.name}
                        </td>
                        <td className="px-4 py-2 text-gray-700">
                          {p.price_amount} {p.effective_currency}
                        </td>
                        <td className="px-4 py-2 text-gray-700">
                          {p.track_inventory ? p.stock_qty : t("unlimited")}
                        </td>
                        <td className="px-4 py-2 text-right">
                          <button
                            onClick={() => addToCart(p.id)}
                            disabled={atMax}
                            className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                          >
                            {t("add")}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ---- Cart (1/3) ---- */}
        <div className="rounded-lg border bg-white p-5 shadow-sm lg:sticky lg:top-4 lg:self-start">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            {t("cart")}
          </h2>

          {cart.length === 0 ? (
            <p className="text-sm text-gray-400">{t("emptyCart")}</p>
          ) : (
            <>
              <div className="mb-4 max-h-72 space-y-3 overflow-y-auto">
                {cart.map((line) => {
                  const p = products.find((pr) => pr.id === line.productId);
                  if (!p) return null;
                  const sub = parseFloat(p.price_amount) * line.qty;
                  const max = maxQty(p);
                  return (
                    <div key={line.productId} className="border-b pb-2">
                      <div className="flex items-start justify-between">
                        <p className="text-sm font-medium text-gray-900">
                          {p.name}
                        </p>
                        <button
                          onClick={() => removeFromCart(line.productId)}
                          className="text-xs text-red-500 hover:text-red-700"
                        >
                          {t("remove")}
                        </button>
                      </div>
                      <div className="mt-1 flex items-center justify-between text-xs text-gray-600">
                        <div className="flex items-center gap-1">
                          <span>{t("qty")}:</span>
                          <input
                            type="number"
                            min={1}
                            max={max === Infinity ? undefined : max}
                            value={line.qty}
                            onChange={(e) =>
                              updateQty(
                                line.productId,
                                parseInt(e.target.value, 10) || 1,
                              )
                            }
                            className="w-14 rounded border border-gray-300 px-1.5 py-0.5 text-center text-xs"
                          />
                        </div>
                        <span>
                          {t("subtotal")}: {sub.toFixed(3)} {currency}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Total + checkout form */}
              <div className="border-t pt-3">
                <div className="mb-3 flex justify-between text-sm font-semibold text-gray-900">
                  <span>{t("total")}</span>
                  <span>
                    {cartTotal().toFixed(3)} {currency}
                  </span>
                </div>

                <form onSubmit={handleSubmit} className="space-y-3">
                  <div>
                    <label className="mb-1 block text-xs text-gray-600">
                      {t("customerName")}
                    </label>
                    <input
                      type="text"
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                      placeholder={t("customerNamePlaceholder")}
                      className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={submitting || cart.length === 0}
                    className="w-full rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    {submitting ? t("completing") : t("completeSale")}
                  </button>
                </form>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Page export
// ---------------------------------------------------------------------------

export default function POSPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <POSContent />
      </DashboardShell>
    </RequireAuth>
  );
}
