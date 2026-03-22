"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { apiFetch } from "@/lib/api-client";
import { uploadFile, getMediaDownloadUrl } from "@/lib/upload";
import type { UploadProgress } from "@/lib/upload";

interface Category {
  id: string;
  name: string;
}

interface PaginatedCategories {
  items: Category[];
}

interface Product {
  id: string;
  category_id: string | null;
  name: string;
  description: string | null;
  name_ar: string | null;
  description_ar: string | null;
  price_amount: string;
  currency: string | null;
  is_active: boolean;
  sort_order: number;
  track_inventory: boolean;
  stock_qty: number | null;
  low_stock_threshold: number | null;
}

/** Tracks a single image upload (in-progress or completed). */
interface ImageEntry {
  id: string; // media_id from backend (or temp UUID while uploading)
  previewUrl: string; // object URL for thumbnail
  fileName: string;
  uploading: boolean;
  progress: UploadProgress | null;
  error: string | null;
}

interface MediaAsset {
  id: string;
  file_name: string | null;
  content_type: string | null;
  s3_key: string;
}

interface StockMovement {
  id: string;
  product_id: string;
  delta_qty: number;
  reason: string;
  note: string | null;
  order_id: string | null;
  actor_user_id: string | null;
  created_at: string;
}

interface PaginatedMovements {
  items: StockMovement[];
  next_cursor: string | null;
  has_more: boolean;
}

const REASON_KEYS: Record<string, string> = {
  manual_restock: "reasonManualRestock",
  manual_adjustment: "reasonManualAdjustment",
  order_cancel_restore: "reasonOrderCancelRestore",
};

const ACCEPTED_IMAGE_TYPES = "image/jpeg,image/png,image/webp";
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

function EditProductContent() {
  const router = useRouter();
  const t = useTranslations("dashboardProducts");
  const params = useParams();
  const productId = params.id as string;

  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [name, setName] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [description, setDescription] = useState("");
  const [descriptionAr, setDescriptionAr] = useState("");
  const [priceAmount, setPriceAmount] = useState("");
  const [currency, setCurrency] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [sortOrder, setSortOrder] = useState(0);
  const [trackInventory, setTrackInventory] = useState(true);
  const [stockQty, setStockQty] = useState(0);
  const [lowStockThreshold, setLowStockThreshold] = useState("5");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Image uploads
  const [images, setImages] = useState<ImageEntry[]>([]);
  const [imageError, setImageError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Restock
  const [restockQty, setRestockQty] = useState("");
  const [restockNote, setRestockNote] = useState("");
  const [restocking, setRestocking] = useState(false);
  const [restockMsg, setRestockMsg] = useState("");
  const [restockIsError, setRestockIsError] = useState(false);
  const restockTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Stock movement history
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [movementsLoading, setMovementsLoading] = useState(false);

  useEffect(() => {
    async function fetchData() {
      const [productResult, categoriesResult] = await Promise.all([
        apiFetch<Product>(`/api/v1/tenants/me/products/${productId}`),
        apiFetch<PaginatedCategories>(
          "/api/v1/tenants/me/categories?is_active=true&limit=100"
        ),
      ]);

      if (productResult.ok) {
        const p = productResult.data;
        setName(p.name);
        setNameAr(p.name_ar ?? "");
        setDescription(p.description ?? "");
        setDescriptionAr(p.description_ar ?? "");
        setCategoryId(p.category_id ?? "");
        setPriceAmount(p.price_amount);
        setCurrency(p.currency ?? "");
        setIsActive(p.is_active);
        setSortOrder(p.sort_order);
        setTrackInventory(p.track_inventory);
        setStockQty(p.stock_qty ?? 0);
        setLowStockThreshold(p.low_stock_threshold != null ? String(p.low_stock_threshold) : "");
      } else {
        setError(productResult.detail);
      }

      if (categoriesResult.ok) {
        setCategories(categoriesResult.data.items);
      }

      // Load existing images for this product
      const mediaResult = await apiFetch<MediaAsset[]>(
        `/api/v1/tenants/me/media?product_id=${productId}&limit=100`,
        { cache: "no-store" },
      );
      if (mediaResult.ok && mediaResult.data.length > 0) {
        const entries: ImageEntry[] = [];
        for (const asset of mediaResult.data) {
          const dlResult = await getMediaDownloadUrl(asset.id);
          entries.push({
            id: asset.id,
            previewUrl: dlResult.ok ? dlResult.url : "",
            fileName: asset.file_name ?? "image",
            uploading: false,
            progress: null,
            error: dlResult.ok ? null : "Failed to load",
          });
        }
        setImages(entries);
      }

      setLoading(false);
    }
    fetchData();
  }, [productId]);

  async function fetchMovements() {
    setMovementsLoading(true);
    const result = await apiFetch<PaginatedMovements>(
      `/api/v1/tenants/me/products/${productId}/stock-movements?limit=20`,
    );
    if (result.ok) {
      setMovements(result.data.items);
    } else {
      setMovements([]);
    }
    setMovementsLoading(false);
  }

  // Load movements on mount; clean up restock toast timer on unmount
  useEffect(() => {
    fetchMovements();
    return () => {
      if (restockTimerRef.current) clearTimeout(restockTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  async function handleRestock(e: React.FormEvent) {
    e.preventDefault();
    setRestocking(true);
    setRestockMsg("");
    setRestockIsError(false);

    const result = await apiFetch<Product>(
      `/api/v1/tenants/me/products/${productId}/restock`,
      {
        method: "POST",
        body: JSON.stringify({
          qty: parseInt(restockQty),
          note: restockNote || null,
        }),
      },
    );

    if (result.ok) {
      setStockQty(result.data.stock_qty ?? 0);
      setRestockIsError(false);
      setRestockMsg(t("restockSuccess", { qty: restockQty }));
      setRestockQty("");
      setRestockNote("");
      if (restockTimerRef.current) clearTimeout(restockTimerRef.current);
      restockTimerRef.current = setTimeout(() => setRestockMsg(""), 3000);
      fetchMovements();
    } else {
      setRestockIsError(true);
      setRestockMsg(t("restockError", { error: result.detail }));
    }
    setRestocking(false);
  }

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setImageError("");

    // Validate all files first
    const validFiles: File[] = [];
    for (const file of Array.from(files)) {
      if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
        setImageError(
          t("imagesInvalidType", { name: file.name })
        );
        continue;
      }
      if (file.size > MAX_FILE_SIZE) {
        setImageError(t("imagesTooLarge", { name: file.name }));
        continue;
      }
      validFiles.push(file);
    }

    if (validFiles.length === 0) return;

    // Create placeholder entries for each file
    const newEntries: ImageEntry[] = validFiles.map((file) => ({
      id: `temp-${crypto.randomUUID()}`,
      previewUrl: URL.createObjectURL(file),
      fileName: file.name,
      uploading: true,
      progress: null,
      error: null,
    }));

    setImages((prev) => [...prev, ...newEntries]);

    // Upload each file in parallel
    await Promise.all(
      validFiles.map(async (file, idx) => {
        const tempId = newEntries[idx].id;

        const result = await uploadFile(file, {
          entity_type: "product",
          entity_id: productId,
          product_id: productId,
          onProgress: (progress) => {
            setImages((prev) =>
              prev.map((img) =>
                img.id === tempId ? { ...img, progress } : img
              )
            );
          },
        });

        if (result.ok) {
          setImages((prev) =>
            prev.map((img) =>
              img.id === tempId
                ? {
                    ...img,
                    id: result.result.media_id,
                    uploading: false,
                    progress: null,
                  }
                : img
            )
          );
        } else {
          setImages((prev) =>
            prev.map((img) =>
              img.id === tempId
                ? { ...img, uploading: false, error: result.detail }
                : img
            )
          );
        }
      })
    );

    // Reset file input so same files can be re-selected
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function handleRemoveImage(id: string) {
    // Skip API call for temp entries (still uploading / failed before save)
    if (!id.startsWith("temp-")) {
      const result = await apiFetch(`/api/v1/tenants/me/media/${id}`, {
        method: "DELETE",
      });
      if (!result.ok) {
        setImageError(result.detail);
        return;
      }
    }
    setImages((prev) => {
      const entry = prev.find((img) => img.id === id);
      if (entry) {
        URL.revokeObjectURL(entry.previewUrl);
      }
      return prev.filter((img) => img.id !== id);
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    const result = await apiFetch(`/api/v1/tenants/me/products/${productId}`, {
      method: "PATCH",
      body: JSON.stringify({
        name,
        description: description || null,
        name_ar: nameAr || null,
        description_ar: descriptionAr || null,
        category_id: categoryId || null,
        price_amount: priceAmount,
        currency: currency.toUpperCase() || null,
        is_active: isActive,
        sort_order: sortOrder,
        track_inventory: trackInventory,
        stock_qty: trackInventory ? stockQty : null,
        low_stock_threshold: trackInventory && lowStockThreshold
          ? parseInt(lowStockThreshold)
          : null,
      }),
    });

    if (result.ok) {
      router.push(`/dashboard/products?t=${Date.now()}`);
    } else {
      setError(result.detail);
    }
    setSubmitting(false);
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-gray-400">{t("loading")}</p>
      </div>
    );
  }

  const anyUploading = images.some((img) => img.uploading);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-6 py-4">
          <Link
            href="/dashboard/products"
            className="text-sm text-blue-600 hover:underline"
          >
            {t("title")}
          </Link>
          <span className="text-gray-300">/</span>
          <h1 className="text-lg font-semibold text-gray-900">{t("editProduct")}</h1>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-8">
        {error && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border bg-white p-6 shadow-sm"
        >
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("formName")}
            </label>
            <input
              type="text"
              required
              maxLength={255}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("formNameAr")}
            </label>
            <input
              type="text"
              maxLength={255}
              value={nameAr}
              onChange={(e) => setNameAr(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("formDescription")}
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("formDescriptionAr")}
            </label>
            <textarea
              rows={3}
              value={descriptionAr}
              onChange={(e) => setDescriptionAr(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("formCategoryOptional")}
            </label>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">{t("noCategory")}</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                {t("formPrice")}
              </label>
              <input
                type="number"
                required
                min="0"
                step="0.001"
                value={priceAmount}
                onChange={(e) => setPriceAmount(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                {t("formCurrencyHint")}
              </label>
              <input
                type="text"
                maxLength={3}
                placeholder={t("tenantDefault")}
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                {t("formSortOrder")}
              </label>
              <input
                type="number"
                value={sortOrder}
                onChange={(e) => setSortOrder(parseInt(e.target.value) || 0)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="rounded border-gray-300"
                />
                {t("active")}
              </label>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={trackInventory}
                  onChange={(e) => setTrackInventory(e.target.checked)}
                  className="rounded border-gray-300"
                />
                {t("trackInventory")}
              </label>
            </div>

            {trackInventory && (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  {t("formStockQty")}
                </label>
                <input
                  type="number"
                  min="0"
                  value={stockQty}
                  onChange={(e) => setStockQty(parseInt(e.target.value) || 0)}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            )}
          </div>

          {trackInventory && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  {t("formLowStockThreshold")}
                </label>
                <input
                  type="number"
                  min="0"
                  placeholder="5"
                  value={lowStockThreshold}
                  onChange={(e) => setLowStockThreshold(e.target.value)}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Link
              href="/dashboard/products"
              className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              {t("cancel")}
            </Link>
            <button
              type="submit"
              disabled={submitting || anyUploading}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? t("saving") : t("saveChanges")}
            </button>
          </div>
        </form>

        {/* Restock Section — only for tracked-inventory products */}
        {trackInventory && (
          <div className="mt-6 rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
              {t("restock")}
            </h2>
            <form onSubmit={handleRestock} className="flex items-end gap-3">
              <div className="w-24">
                <label className="mb-1 block text-xs font-medium text-gray-600">
                  {t("restockQtyLabel")}
                </label>
                <input
                  type="number"
                  min="1"
                  placeholder={t("restockQtyPlaceholder")}
                  value={restockQty}
                  onChange={(e) => setRestockQty(e.target.value)}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div className="flex-1">
                <label className="mb-1 block text-xs font-medium text-gray-600">
                  {t("restockNoteOptional")}
                </label>
                <input
                  type="text"
                  maxLength={500}
                  placeholder={t("restockNotePlaceholder")}
                  value={restockNote}
                  onChange={(e) => setRestockNote(e.target.value)}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <button
                type="submit"
                disabled={restocking || !restockQty || parseInt(restockQty) < 1}
                className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                {restocking ? t("restockAdding") : t("restock")}
              </button>
            </form>
            {restockMsg && (
              <p className={`mt-2 text-xs ${restockIsError ? "text-red-600" : "text-green-600"}`}>
                {restockMsg}
              </p>
            )}
          </div>
        )}

        {/* Stock Movement History */}
        {trackInventory && (
          <div className="mt-6 rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
              {t("movementHistory")}
            </h2>
            {movementsLoading ? (
              <p className="text-sm text-gray-400">{t("loading")}</p>
            ) : movements.length === 0 ? (
              <p className="text-sm text-gray-400">{t("noMovements")}</p>
            ) : (
              <div className="overflow-hidden rounded border">
                <table className="w-full text-left text-sm">
                  <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-3 py-2">{t("movementDate")}</th>
                      <th className="px-3 py-2">{t("movementReason")}</th>
                      <th className="px-3 py-2 text-right">{t("movementQty")}</th>
                      <th className="px-3 py-2">{t("movementNote")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {movements.map((m) => (
                      <tr key={m.id}>
                        <td className="whitespace-nowrap px-3 py-2 text-xs text-gray-500">
                          {new Date(m.created_at).toLocaleString()}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          {REASON_KEYS[m.reason] ? t(REASON_KEYS[m.reason]) : m.reason}
                        </td>
                        <td className={`px-3 py-2 text-right text-xs font-medium ${m.delta_qty > 0 ? "text-green-600" : "text-red-600"}`}>
                          {m.delta_qty > 0 ? `+${m.delta_qty}` : m.delta_qty}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500">
                          {m.note ?? t("emptyNote")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Product Images Section */}
        <div className="mt-6 rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            {t("images")}
          </h2>

          {/* Thumbnail Grid */}
          {images.length > 0 && (
            <div className="mb-4 grid grid-cols-4 gap-3">
              {images.map((img) => (
                <div key={img.id} className="group relative">
                  {/* eslint-disable-next-line @next/next/no-img-element -- object URL thumbnail */}
                  <img
                    src={img.previewUrl}
                    alt={img.fileName}
                    className={`h-24 w-full rounded border object-cover ${
                      img.error
                        ? "border-red-300 opacity-50"
                        : "border-gray-200"
                    }`}
                  />

                  {/* Upload progress overlay */}
                  {img.uploading && (
                    <div className="absolute inset-0 flex items-center justify-center rounded bg-black/30">
                      <span className="text-xs font-medium text-white">
                        {img.progress
                          ? `${img.progress.percent}%`
                          : t("imagesPreparing")}
                      </span>
                    </div>
                  )}

                  {/* Error indicator */}
                  {img.error && (
                    <div className="absolute inset-x-0 bottom-0 rounded-b bg-red-600/80 px-1 py-0.5">
                      <p className="truncate text-xs text-white">{img.error}</p>
                    </div>
                  )}

                  {/* Remove button */}
                  {!img.uploading && (
                    <button
                      type="button"
                      onClick={() => handleRemoveImage(img.id)}
                      className="absolute -right-1.5 -top-1.5 hidden h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs text-white shadow group-hover:flex"
                      title={t("imagesRemove")}
                    >
                      x
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Upload Control */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("imagesAddLabel")}{" "}
              <span className="ml-1 text-gray-400">
                {t("imagesFormats")}
              </span>
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_IMAGE_TYPES}
              multiple
              onChange={handleImageUpload}
              disabled={anyUploading}
              className="block w-full text-sm text-gray-500 file:mr-4 file:rounded file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100 disabled:opacity-50"
            />
          </div>

          {imageError && (
            <div className="mt-3 rounded border border-red-300 bg-red-50 p-2 text-xs text-red-700">
              {imageError}
            </div>
          )}

          <p className="mt-3 text-xs text-gray-400">
            {t("imagesSavedNote")}
          </p>
        </div>
      </main>
    </div>
  );
}

export default function EditProductPage() {
  return (
    <RequireAuth>
      <EditProductContent />
    </RequireAuth>
  );
}
