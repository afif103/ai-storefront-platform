"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api-client";

interface Category {
  id: string;
  name: string;
  description: string | null;
  sort_order: number;
}

interface PublicProduct {
  id: string;
  category_id: string | null;
  name: string;
  description: string | null;
  price_amount: string;
  effective_currency: string;
  sort_order: number;
}

interface PaginatedCategories {
  items: Category[];
  has_more: boolean;
}

interface PaginatedProducts {
  items: PublicProduct[];
  has_more: boolean;
}

export default function StorefrontPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<PublicProduct[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [filterLoading, setFilterLoading] = useState(false);

  // Initial load: fetch categories and all products in parallel
  useEffect(() => {
    async function fetchData() {
      const [catResult, prodResult] = await Promise.all([
        apiFetch<PaginatedCategories>(
          `/api/v1/storefront/${slug}/categories?limit=100`
        ),
        apiFetch<PaginatedProducts>(`/api/v1/storefront/${slug}/products`),
      ]);

      if (!catResult.ok && !prodResult.ok) {
        setError(catResult.detail || prodResult.detail);
      } else {
        if (catResult.ok) setCategories(catResult.data.items);
        if (prodResult.ok) setProducts(prodResult.data.items);
        if (!catResult.ok) setError(catResult.detail);
      }
      setLoading(false);
    }
    fetchData();
  }, [slug]);

  // Re-fetch products when category filter changes
  useEffect(() => {
    if (loading) return;
    async function fetchFiltered() {
      setFilterLoading(true);
      const url =
        selectedCategory !== null
          ? `/api/v1/storefront/${slug}/products?category_id=${encodeURIComponent(selectedCategory)}`
          : `/api/v1/storefront/${slug}/products`;
      const result = await apiFetch<PaginatedProducts>(url);
      if (result.ok) setProducts(result.data.items);
      setFilterLoading(false);
    }
    fetchFiltered();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCategory]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-400">Loading storefront...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="rounded-lg border border-red-300 bg-red-50 p-8 text-center">
          <p className="text-sm font-medium text-red-700">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white shadow-sm">
        <div className="mx-auto max-w-5xl px-6 py-6">
          <h1 className="text-2xl font-bold capitalize text-gray-900">
            {slug}
          </h1>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {/* Category filter tabs */}
        {categories.length > 0 && (
          <div className="mb-6 flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                selectedCategory === null
                  ? "bg-blue-600 text-white"
                  : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
              }`}
            >
              All
            </button>
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                  selectedCategory === cat.id
                    ? "bg-blue-600 text-white"
                    : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                }`}
              >
                {cat.name}
              </button>
            ))}
          </div>
        )}

        {/* Product grid */}
        {filterLoading ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : products.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">No products available.</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((product) => (
              <div
                key={product.id}
                className="rounded-lg border bg-white p-5 shadow-sm"
              >
                <h3 className="text-sm font-semibold text-gray-900">
                  {product.name}
                </h3>
                {product.description && (
                  <p className="mt-1 line-clamp-2 text-sm text-gray-500">
                    {product.description}
                  </p>
                )}
                <p className="mt-3 text-base font-bold text-gray-900">
                  {product.price_amount} {product.effective_currency}
                </p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
