"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { apiFetch } from "@/lib/api-client";

interface Product {
  id: string;
  category_id: string | null;
  name: string;
  description: string | null;
  price_amount: string;
  currency: string | null;
  effective_currency: string;
  is_active: boolean;
  sort_order: number;
  track_inventory: boolean;
  stock_qty: number | null;
  low_stock_threshold: number | null;
  is_low_stock: boolean;
}

interface PaginatedProducts {
  items: Product[];
  next_cursor: string | null;
  has_more: boolean;
}

function ProductsContent() {
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [stockFilter, setStockFilter] = useState<"all" | "low">("all");
  const [toast, setToast] = useState("");
  const searchParams = useSearchParams();
  const t = useTranslations("dashboardProducts");

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    const result = await apiFetch<PaginatedProducts>(
      "/api/v1/tenants/me/products",
    );
    if (result.ok) {
      setProducts(result.data.items);
    } else {
      setError(result.detail);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await fetchProducts();
      if (cancelled) return;
    })();
    return () => { cancelled = true; };
  }, [searchParams, fetchProducts]);

  async function handleDelete(id: string, name: string) {
    if (!confirm(t("confirmDelete", { name }))) return;
    setDeletingIds((prev) => new Set(prev).add(id));
    setError("");

    const result = await apiFetch(`/api/v1/tenants/me/products/${id}`, {
      method: "DELETE",
    });

    setDeletingIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });

    if (result.ok) {
      setProducts((prev) => prev.filter((p) => p.id !== id));
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      showToast(t("deletedToast", { name }));
    } else {
      setError(t("deleteError", { name, error: result.detail }));
    }
  }

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

  async function handleBulkDelete() {
    if (selected.size === 0) return;
    const count = selected.size;
    if (!confirm(t("confirmBulkDelete", { count }))) return;

    const ids = [...selected];
    setDeletingIds(new Set(ids));
    setError("");

    const result = await apiFetch<{ deleted: number }>(
      "/api/v1/tenants/me/products/bulk-delete",
      {
        method: "POST",
        body: JSON.stringify({ ids }),
      },
    );

    setDeletingIds(new Set());

    if (result.ok) {
      const deletedSet = new Set(ids);
      setProducts((prev) => prev.filter((p) => !deletedSet.has(p.id)));
      setSelected(new Set());
      showToast(t("bulkDeletedToast", { count: result.data.deleted }));
    } else {
      setError(t("bulkDeleteError", { error: result.detail }));
    }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === products.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(products.map((p) => p.id)));
    }
  }

  return (
    <>
    <main className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <button
              onClick={handleBulkDelete}
              disabled={deletingIds.size > 0}
              className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {t("deleteSelected", { count: selected.size })}
            </button>
          )}
          <Link
            href="/dashboard/products/new"
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t("addProduct")}
          </Link>
        </div>
      </div>

      {error && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && products.length > 0 && (
          <div className="mb-4 flex items-center gap-2">
            <button
              onClick={() => setStockFilter("all")}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                stockFilter === "all"
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {t("filterAll")}
            </button>
            <button
              onClick={() => setStockFilter("low")}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                stockFilter === "low"
                  ? "bg-amber-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {t("filterLowStock")}
              {products.filter((p) => p.is_low_stock).length > 0 && (
                <span className="ml-1.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-200 text-[10px] font-bold text-amber-800">
                  {products.filter((p) => p.is_low_stock).length}
                </span>
              )}
            </button>
          </div>
        )}

        {loading ? (
          <p className="text-sm text-gray-400">{t("loading")}</p>
        ) : products.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">{t("empty")}</p>
            <Link
              href="/dashboard/products/new"
              className="mt-2 inline-block text-sm text-blue-600 hover:underline"
            >
              {t("createFirst")}
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3 w-8">
                    <input
                      type="checkbox"
                      checked={selected.size === products.length && products.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded"
                    />
                  </th>
                  <th className="px-4 py-3">{t("thName")}</th>
                  <th className="px-4 py-3">{t("thPrice")}</th>
                  <th className="px-4 py-3">{t("active")}</th>
                  <th className="px-4 py-3">{t("thStock")}</th>
                  <th className="px-4 py-3">{t("thSort")}</th>
                  <th className="px-4 py-3">{t("thActions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(stockFilter === "low"
                  ? products.filter((p) => p.is_low_stock)
                  : products
                ).map((prod) => {
                  const isDeleting = deletingIds.has(prod.id);
                  return (
                    <tr key={prod.id} className={isDeleting ? "opacity-50" : ""}>
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selected.has(prod.id)}
                          onChange={() => toggleSelect(prod.id)}
                          disabled={isDeleting}
                          className="rounded"
                        />
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {prod.name}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {prod.price_amount} {prod.effective_currency}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                            prod.is_active
                              ? "bg-green-100 text-green-700"
                              : "bg-gray-100 text-gray-500"
                          }`}
                        >
                          {prod.is_active ? t("active") : t("inactive")}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {!prod.track_inventory ? (
                          <span className="text-xs text-gray-400">{t("unlimited")}</span>
                        ) : (prod.stock_qty ?? 0) === 0 ? (
                          <span className="text-xs font-medium text-red-600">{t("outOfStock")}</span>
                        ) : prod.is_low_stock ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                            {t("stockLeft", { qty: prod.stock_qty ?? 0 })}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-700">{t("stockLeft", { qty: prod.stock_qty ?? 0 })}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{prod.sort_order}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <Link
                            href={`/dashboard/products/${prod.id}/edit`}
                            className="text-blue-600 hover:underline"
                          >
                            {t("edit")}
                          </Link>
                          <button
                            onClick={() => handleDelete(prod.id, prod.name)}
                            disabled={isDeleting}
                            className="text-red-600 hover:underline disabled:opacity-50"
                          >
                            {isDeleting ? t("deleting") : t("delete")}
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

    {toast && (
      <div className="fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-gray-900 px-4 py-2 text-sm text-white shadow-lg">
        {toast}
      </div>
    )}
    </>
  );
}

export default function ProductsPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <ProductsContent />
      </DashboardShell>
    </RequireAuth>
  );
}
