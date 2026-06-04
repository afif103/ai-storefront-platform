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

interface Variant {
  id: string;
  name: string;
  size: string | null;
  color: string | null;
  sku: string | null;
  barcode: string | null;
  price_amount: string | null;
  stock_qty: number | null;
  is_active: boolean;
  sort_order: number;
}

interface PaginatedVariants {
  items: Variant[];
  next_cursor: string | null;
  has_more: boolean;
}

interface CartLine {
  key: string;
  productId: string;
  variantId: string | null;
  name: string;
  variantName: string | null;
  unitPrice: string;
  currency: string;
  maxQty: number | null;
  qty: number;
}

interface OrderItem {
  name: string;
  variant_name?: string | null;
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
  payment_method: string | null;
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

/** Max sellable qty for a product line, or null when stock is not tracked (unlimited). */
function productMax(p: Product): number | null {
  if (!p.track_inventory) return null;
  return p.stock_qty ?? 0;
}

/** Max sellable qty for a variant line, gated on the parent product's track_inventory. */
function variantMax(p: Product, v: Variant): number | null {
  if (!p.track_inventory) return null;
  return v.stock_qty ?? 0;
}

// ---------------------------------------------------------------------------
// Inner content
// ---------------------------------------------------------------------------

function POSContent() {
  const t = useTranslations("pos");
  const tPayment = useTranslations("paymentMethods");
  const paymentMethodLabels: Record<string, string> = {
    cash: tPayment("cash"),
    knet: tPayment("knet"),
    bank_transfer: tPayment("bank_transfer"),
    cod: tPayment("cod"),
    manual: tPayment("manual"),
  };
  const { bootstrap } = useAuth();
  const storeName = bootstrap?.memberships?.[0]?.tenant_name;

  // Product catalog
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  // Cart
  const [cart, setCart] = useState<CartLine[]>([]);

  // Variants (lazy-fetched + cached per product)
  const [variantsByProduct, setVariantsByProduct] = useState<
    Record<string, Variant[]>
  >({});
  const [loadingVariantsFor, setLoadingVariantsFor] = useState<string | null>(
    null,
  );
  const [pickerProduct, setPickerProduct] = useState<Product | null>(null);

  // Checkout
  const [customerName, setCustomerName] = useState("");
  const [paymentMethods, setPaymentMethods] = useState<string[]>(["cash"]);
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState("cash");
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

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await apiFetch<{ payment_methods: string[] }>(
        "/api/v1/tenants/me/pos/payment-methods",
      );
      if (cancelled) return;
      if (result.ok && result.data.payment_methods.length > 0) {
        setPaymentMethods(result.data.payment_methods);
        setSelectedPaymentMethod(result.data.payment_methods[0]);
      }
    })();
    return () => { cancelled = true; };
  }, []);

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

  /** Qty of the no-variant line for a product (used for the catalog button state). */
  function baseCartQty(productId: string): number {
    return cart.find((l) => l.key === productId)?.qty ?? 0;
  }

  /** Add one unit of a snapshot line, respecting its maxQty; merges by key. */
  function addLine(line: Omit<CartLine, "qty">) {
    setCart((prev) => {
      const idx = prev.findIndex((l) => l.key === line.key);
      if (idx >= 0) {
        const existing = prev[idx];
        if (existing.maxQty != null && existing.qty >= existing.maxQty) {
          return prev;
        }
        const next = [...prev];
        next[idx] = { ...existing, qty: existing.qty + 1 };
        return next;
      }
      return [...prev, { ...line, qty: 1 }];
    });
  }

  function addBaseProduct(p: Product) {
    addLine({
      key: p.id,
      productId: p.id,
      variantId: null,
      name: p.name,
      variantName: null,
      unitPrice: p.price_amount,
      currency: p.effective_currency,
      maxQty: productMax(p),
    });
  }

  function addVariant(p: Product, v: Variant) {
    addLine({
      key: `${p.id}:${v.id}`,
      productId: p.id,
      variantId: v.id,
      name: p.name,
      variantName: v.name,
      unitPrice: v.price_amount ?? p.price_amount,
      currency: p.effective_currency,
      maxQty: variantMax(p, v),
    });
    setPickerProduct(null);
  }

  /** Add click: lazy-load + cache variants, then open the picker or add the base product. */
  async function handleAddClick(p: Product) {
    const cached = variantsByProduct[p.id];
    if (cached) {
      if (cached.some((v) => v.is_active)) setPickerProduct(p);
      else addBaseProduct(p);
      return;
    }

    setLoadingVariantsFor(p.id);
    const result = await apiFetch<PaginatedVariants>(
      `/api/v1/tenants/me/products/${p.id}/variants?limit=100`,
    );
    setLoadingVariantsFor(null);

    if (!result.ok) {
      setError(result.detail);
      return;
    }

    const items = result.data.items;
    setVariantsByProduct((prev) => ({ ...prev, [p.id]: items }));
    if (items.some((v) => v.is_active)) setPickerProduct(p);
    else addBaseProduct(p);
  }

  function updateQty(key: string, qty: number) {
    if (qty < 1) return removeFromCart(key);
    setCart((prev) =>
      prev.map((l) =>
        l.key === key
          ? { ...l, qty: l.maxQty != null ? Math.min(qty, l.maxQty) : qty }
          : l,
      ),
    );
  }

  function removeFromCart(key: string) {
    setCart((prev) => prev.filter((l) => l.key !== key));
  }

  function cartTotal(): number {
    return cart.reduce(
      (sum, line) => sum + parseFloat(line.unitPrice) * line.qty,
      0,
    );
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
            ...(l.variantId ? { variant_id: l.variantId } : {}),
            qty: l.qty,
          })),
          customer_name: customerName || undefined,
          payment_method: selectedPaymentMethod || undefined,
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
                  <td className="py-1 text-gray-900">
                    {item.name}
                    {item.variant_name && (
                      <span className="block text-xs text-gray-500">
                        {t("variant")}: {item.variant_name}
                      </span>
                    )}
                  </td>
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

          {lastOrder.payment_method && (
            <div className="mt-1 text-right text-sm text-gray-700">
              {tPayment("fieldLabel")}:{" "}
              {paymentMethodLabels[lastOrder.payment_method] ??
                lastOrder.payment_method}
            </div>
          )}

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
                setVariantsByProduct({});
                setPickerProduct(null);
                setLoadingVariantsFor(null);
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
                    const pMax = productMax(p);
                    const atMax = pMax != null && baseCartQty(p.id) >= pMax;
                    const isLoading = loadingVariantsFor === p.id;
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
                            onClick={() => handleAddClick(p)}
                            disabled={atMax || isLoading}
                            className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                          >
                            {isLoading ? t("loadingVariants") : t("add")}
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
                  const sub = parseFloat(line.unitPrice) * line.qty;
                  return (
                    <div key={line.key} className="border-b pb-2">
                      <div className="flex items-start justify-between">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-gray-900">
                            {line.name}
                          </p>
                          {line.variantName && (
                            <p className="text-xs text-gray-500">
                              {t("variant")}: {line.variantName}
                            </p>
                          )}
                        </div>
                        <button
                          onClick={() => removeFromCart(line.key)}
                          className="ml-2 shrink-0 text-xs text-red-500 hover:text-red-700"
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
                            max={line.maxQty ?? undefined}
                            value={line.qty}
                            onChange={(e) =>
                              updateQty(
                                line.key,
                                parseInt(e.target.value, 10) || 1,
                              )
                            }
                            className="w-14 rounded border border-gray-300 px-1.5 py-0.5 text-center text-xs"
                          />
                        </div>
                        <span>
                          {t("subtotal")}: {sub.toFixed(3)} {line.currency}
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
                  <div>
                    <label className="mb-1 block text-xs text-gray-600">
                      {tPayment("fieldLabel")}
                    </label>
                    <select
                      value={selectedPaymentMethod}
                      onChange={(e) => setSelectedPaymentMethod(e.target.value)}
                      className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    >
                      {paymentMethods.map((code) => (
                        <option key={code} value={code}>
                          {paymentMethodLabels[code] ?? code}
                        </option>
                      ))}
                    </select>
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

      {pickerProduct && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 print:hidden"
          onClick={() => setPickerProduct(null)}
        >
          <div
            className="w-full max-w-md rounded-lg border bg-white p-5 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between">
              <div className="min-w-0">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                  {t("selectVariant")}
                </h2>
                <p className="mt-1 text-sm font-medium text-gray-900">
                  {pickerProduct.name}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPickerProduct(null)}
                className="ml-3 shrink-0 text-xs text-gray-500 hover:text-gray-700"
              >
                {t("close")}
              </button>
            </div>
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {(variantsByProduct[pickerProduct.id] ?? [])
                .filter((v) => v.is_active)
                .map((v) => {
                  const price = v.price_amount ?? pickerProduct.price_amount;
                  const outOfStock =
                    pickerProduct.track_inventory && (v.stock_qty ?? 0) <= 0;
                  const meta = [v.size, v.color].filter(Boolean).join(" / ");
                  return (
                    <div
                      key={v.id}
                      className="flex items-center justify-between rounded border px-3 py-2"
                    >
                      <div className="min-w-0 pr-2">
                        <p className="text-sm font-medium text-gray-900">
                          {v.name}
                        </p>
                        {meta && <p className="text-xs text-gray-500">{meta}</p>}
                        <p className="mt-0.5 text-xs text-gray-600">
                          {price} {pickerProduct.effective_currency}
                          {pickerProduct.track_inventory && (
                            <span className="ml-2">
                              {t("stock")}: {v.stock_qty ?? 0}
                            </span>
                          )}
                        </p>
                      </div>
                      <button
                        type="button"
                        disabled={outOfStock}
                        onClick={() => addVariant(pickerProduct, v)}
                        className="shrink-0 rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {outOfStock ? t("outOfStock") : t("add")}
                      </button>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      )}
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
