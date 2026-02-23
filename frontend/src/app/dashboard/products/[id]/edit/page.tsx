"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { RequireAuth } from "@/components/require-auth";
import { apiFetch } from "@/lib/api-client";
import { uploadFile } from "@/lib/upload";
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
  price_amount: string;
  currency: string | null;
  is_active: boolean;
  sort_order: number;
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

const ACCEPTED_IMAGE_TYPES = "image/jpeg,image/png,image/webp";
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

function EditProductContent() {
  const router = useRouter();
  const params = useParams();
  const productId = params.id as string;

  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [priceAmount, setPriceAmount] = useState("");
  const [currency, setCurrency] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [sortOrder, setSortOrder] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Image uploads
  const [images, setImages] = useState<ImageEntry[]>([]);
  const [imageError, setImageError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

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
        setDescription(p.description ?? "");
        setCategoryId(p.category_id ?? "");
        setPriceAmount(p.price_amount);
        setCurrency(p.currency ?? "");
        setIsActive(p.is_active);
        setSortOrder(p.sort_order);
      } else {
        setError(productResult.detail);
      }

      if (categoriesResult.ok) {
        setCategories(categoriesResult.data.items);
      }

      setLoading(false);
    }
    fetchData();
  }, [productId]);

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setImageError("");

    // Validate all files first
    const validFiles: File[] = [];
    for (const file of Array.from(files)) {
      if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
        setImageError(
          `"${file.name}" skipped — only JPEG, PNG, and WebP are allowed.`
        );
        continue;
      }
      if (file.size > MAX_FILE_SIZE) {
        setImageError(`"${file.name}" skipped — file size must be under 10 MB.`);
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

  function handleRemoveImage(id: string) {
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
        category_id: categoryId || null,
        price_amount: priceAmount,
        currency: currency.toUpperCase() || null,
        is_active: isActive,
        sort_order: sortOrder,
      }),
    });

    if (result.ok) {
      router.push("/dashboard/products");
    } else {
      setError(result.detail);
    }
    setSubmitting(false);
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-gray-400">Loading...</p>
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
            Products
          </Link>
          <span className="text-gray-300">/</span>
          <h1 className="text-lg font-semibold text-gray-900">Edit Product</h1>
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
              Name
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
              Description
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
              Category <span className="text-gray-400">(optional)</span>
            </label>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">No category</option>
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
                Price
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
                Currency{" "}
                <span className="text-gray-400">(optional, e.g. KWD)</span>
              </label>
              <input
                type="text"
                maxLength={3}
                placeholder="Tenant default"
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Sort Order
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
                Active
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Link
              href="/dashboard/products"
              className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={submitting || anyUploading}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>

        {/* Product Images Section */}
        <div className="mt-6 rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Images
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
                          : "Preparing..."}
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
                      title="Remove"
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
              Add images
              <span className="ml-1 text-gray-400">
                (JPEG, PNG, WebP, max 10 MB each)
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
            Images are saved immediately when uploaded. Remove only hides from
            this view — a backend media list endpoint is needed to display
            previously uploaded images on page reload.
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
