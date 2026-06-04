"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { apiFetch } from "@/lib/api-client";

interface Variant {
  id: string;
  product_id: string;
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

interface VariantForm {
  name: string;
  size: string;
  color: string;
  sku: string;
  barcode: string;
  price_amount: string;
  stock_qty: string;
  is_active: boolean;
  sort_order: string;
}

const EMPTY_FORM: VariantForm = {
  name: "",
  size: "",
  color: "",
  sku: "",
  barcode: "",
  price_amount: "",
  stock_qty: "",
  is_active: true,
  sort_order: "0",
};

const INPUT_CLASS =
  "w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

/** Build the JSON payload: empty optional text/number fields become null. */
function buildPayload(form: VariantForm) {
  return {
    name: form.name,
    size: form.size.trim() || null,
    color: form.color.trim() || null,
    sku: form.sku.trim() || null,
    barcode: form.barcode.trim() || null,
    price_amount: form.price_amount.trim() || null,
    stock_qty: form.stock_qty.trim() === "" ? null : parseInt(form.stock_qty, 10),
    is_active: form.is_active,
    sort_order: parseInt(form.sort_order, 10) || 0,
  };
}

export function ProductVariants({ productId }: { productId: string }) {
  const t = useTranslations("dashboardProducts");

  const [variants, setVariants] = useState<Variant[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");

  const [form, setForm] = useState<VariantForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const base = `/api/v1/tenants/me/products/${productId}/variants`;

  async function fetchVariants() {
    setLoading(true);
    const result = await apiFetch<PaginatedVariants>(`${base}?limit=100`);
    if (result.ok) {
      setVariants(result.data.items);
      setListError("");
    } else {
      setListError(result.detail);
    }
    setLoading(false);
  }

  useEffect(() => {
    fetchVariants();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFormError("");
  }

  function startEdit(v: Variant) {
    setEditingId(v.id);
    setFormError("");
    setForm({
      name: v.name,
      size: v.size ?? "",
      color: v.color ?? "",
      sku: v.sku ?? "",
      barcode: v.barcode ?? "",
      price_amount: v.price_amount ?? "",
      stock_qty: v.stock_qty != null ? String(v.stock_qty) : "",
      is_active: v.is_active,
      sort_order: String(v.sort_order),
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setFormError("");

    const body = JSON.stringify(buildPayload(form));
    const result = editingId
      ? await apiFetch<Variant>(`${base}/${editingId}`, { method: "PATCH", body })
      : await apiFetch<Variant>(base, { method: "POST", body });

    if (result.ok) {
      resetForm();
      await fetchVariants();
    } else {
      setFormError(t("variantSaveError", { error: result.detail }));
    }
    setSubmitting(false);
  }

  async function handleDelete(v: Variant) {
    if (!window.confirm(t("variantDeleteConfirm"))) return;
    const result = await apiFetch(`${base}/${v.id}`, { method: "DELETE" });
    if (result.ok) {
      if (editingId === v.id) resetForm();
      await fetchVariants();
    } else {
      setListError(t("variantDeleteError", { error: result.detail }));
    }
  }

  return (
    <div className="mt-6 rounded-lg border bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
        {t("variants")}
      </h2>

      {listError && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-xs text-red-700">
          {listError}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-400">{t("loading")}</p>
      ) : variants.length === 0 ? (
        <p className="mb-4 text-sm text-gray-400">{t("noVariants")}</p>
      ) : (
        <div className="mb-4 overflow-x-auto rounded border">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-3 py-2">{t("variantName")}</th>
                <th className="px-3 py-2">{t("variantSize")}</th>
                <th className="px-3 py-2">{t("variantColor")}</th>
                <th className="px-3 py-2">{t("variantSku")}</th>
                <th className="px-3 py-2">{t("variantBarcode")}</th>
                <th className="px-3 py-2 text-right">{t("variantPrice")}</th>
                <th className="px-3 py-2 text-right">{t("variantStock")}</th>
                <th className="px-3 py-2">{t("active")}</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {variants.map((v) => (
                <tr key={v.id}>
                  <td className="px-3 py-2 text-gray-900">{v.name}</td>
                  <td className="px-3 py-2 text-gray-600">{v.size ?? "-"}</td>
                  <td className="px-3 py-2 text-gray-600">{v.color ?? "-"}</td>
                  <td className="px-3 py-2 text-gray-600">{v.sku ?? "-"}</td>
                  <td className="px-3 py-2 text-gray-600">{v.barcode ?? "-"}</td>
                  <td className="px-3 py-2 text-right text-gray-600">
                    {v.price_amount ?? "-"}
                  </td>
                  <td className="px-3 py-2 text-right text-gray-600">
                    {v.stock_qty ?? "-"}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {v.is_active ? t("active") : t("inactive")}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => startEdit(v)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      {t("edit")}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(v)}
                      className="ml-3 text-xs text-red-600 hover:underline"
                    >
                      {t("delete")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={handleSubmit} className="rounded border bg-gray-50 p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
          {editingId ? t("editVariant") : t("addVariant")}
        </p>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-gray-600">{t("variantName")}</label>
            <input
              type="text"
              required
              maxLength={255}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-600">{t("variantSize")}</label>
            <input
              type="text"
              maxLength={255}
              value={form.size}
              onChange={(e) => setForm({ ...form, size: e.target.value })}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-600">{t("variantColor")}</label>
            <input
              type="text"
              maxLength={255}
              value={form.color}
              onChange={(e) => setForm({ ...form, color: e.target.value })}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-600">{t("variantSku")}</label>
            <input
              type="text"
              maxLength={64}
              value={form.sku}
              onChange={(e) => setForm({ ...form, sku: e.target.value })}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-600">{t("variantBarcode")}</label>
            <input
              type="text"
              maxLength={64}
              value={form.barcode}
              onChange={(e) => setForm({ ...form, barcode: e.target.value })}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-600">{t("variantPrice")}</label>
            <input
              type="number"
              min="0"
              step="0.001"
              value={form.price_amount}
              onChange={(e) => setForm({ ...form, price_amount: e.target.value })}
              className={INPUT_CLASS}
            />
            <p className="mt-0.5 text-[10px] text-gray-400">{t("variantPriceInherit")}</p>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-600">{t("variantStock")}</label>
            <input
              type="number"
              min="0"
              value={form.stock_qty}
              onChange={(e) => setForm({ ...form, stock_qty: e.target.value })}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-600">{t("variantSortOrder")}</label>
            <input
              type="number"
              value={form.sort_order}
              onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
              className={INPUT_CLASS}
            />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="rounded border-gray-300"
              />
              {t("active")}
            </label>
          </div>
        </div>

        {formError && <p className="mt-2 text-xs text-red-600">{formError}</p>}

        <div className="mt-3 flex justify-end gap-2">
          {editingId && (
            <button
              type="button"
              onClick={resetForm}
              className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
            >
              {t("cancel")}
            </button>
          )}
          <button
            type="submit"
            disabled={submitting || !form.name.trim()}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? t("saving") : editingId ? t("saveVariant") : t("addVariant")}
          </button>
        </div>
      </form>
    </div>
  );
}
