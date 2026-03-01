"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api-client";
import { useVisit } from "@/hooks/use-visit";
import { useCart } from "@/hooks/use-cart";

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
  image_url: string | null;
}

interface StorefrontConfig {
  hero_text: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  logo_url: string | null;
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

  useVisit(slug);
  const cart = useCart(slug);

  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<PublicProduct[]>([]);
  const [config, setConfig] = useState<StorefrontConfig | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [filterLoading, setFilterLoading] = useState(false);
  const [addedId, setAddedId] = useState<string | null>(null);

  // Initial load: fetch config, categories, and all products in parallel
  useEffect(() => {
    async function fetchData() {
      const [configResult, catResult, prodResult] = await Promise.all([
        apiFetch<StorefrontConfig>(
          `/api/v1/storefront/${slug}/config`
        ),
        apiFetch<PaginatedCategories>(
          `/api/v1/storefront/${slug}/categories?limit=100`
        ),
        apiFetch<PaginatedProducts>(`/api/v1/storefront/${slug}/products`),
      ]);

      if (configResult.ok) setConfig(configResult.data);
      if (catResult.ok) setCategories(catResult.data.items);
      if (prodResult.ok) setProducts(prodResult.data.items);

      if (!catResult.ok && !prodResult.ok) {
        setError(catResult.detail || prodResult.detail);
      } else if (!catResult.ok) {
        setError(catResult.detail);
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

  function handleAddToCart(product: PublicProduct) {
    cart.addItem(
      {
        catalogItemId: product.id,
        name: product.name,
        priceAmount: product.price_amount,
        currency: product.effective_currency,
      },
      1
    );
    setAddedId(product.id);
    setTimeout(() => setAddedId(null), 1200);
  }

  const primaryColor = config?.primary_color ?? undefined;
  const secondaryColor = config?.secondary_color ?? undefined;
  const headerTextColor = primaryColor ? "#ffffff" : "#111827";

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
    <div
      className="min-h-screen bg-gray-50"
      style={
        {
          "--primary": primaryColor,
          "--secondary": secondaryColor,
        } as React.CSSProperties
      }
    >
      <header
        className="border-b shadow-sm"
        style={{ backgroundColor: primaryColor ?? "#ffffff" }}
      >
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-6 py-6">
          {config?.logo_url && (
            /* eslint-disable-next-line @next/next/no-img-element -- presigned URL expires; next/image caching would break */
            <img
              src={config.logo_url}
              alt={`${slug} logo`}
              className="h-10 w-10 rounded object-contain"
            />
          )}
          <h1
            className="flex-1 text-2xl font-bold capitalize"
            style={{ color: headerTextColor }}
          >
            {config?.hero_text ?? slug}
          </h1>

          {/* Nav links */}
          <div className="flex items-center gap-3">
            <Link
              href={`/storefront/${slug}/donate`}
              className="rounded-full border px-4 py-1.5 text-sm font-medium transition-colors hover:opacity-80"
              style={{
                borderColor: headerTextColor,
                color: headerTextColor,
              }}
            >
              Donate
            </Link>
            <Link
              href={`/storefront/${slug}/pledge`}
              className="rounded-full border px-4 py-1.5 text-sm font-medium transition-colors hover:opacity-80"
              style={{
                borderColor: headerTextColor,
                color: headerTextColor,
              }}
            >
              Pledge
            </Link>

            {/* Cart badge */}
            <Link
              href={`/storefront/${slug}/checkout`}
              className="relative rounded-full border p-2 transition-colors hover:opacity-80"
              style={{ borderColor: headerTextColor, color: headerTextColor }}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="h-5 w-5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15.75 10.5V6a3.75 3.75 0 10-7.5 0v4.5m11.356-1.993l1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 01-1.12-1.243l1.264-12A1.125 1.125 0 015.513 7.5h12.974c.576 0 1.059.435 1.119 1.007zM8.625 10.5a.375.375 0 11-.75 0 .375.375 0 01.75 0zm7.5 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"
                />
              </svg>
              {cart.totalItems > 0 && (
                <span
                  className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold text-white"
                  style={{ backgroundColor: secondaryColor ?? "#dc2626" }}
                >
                  {cart.totalItems}
                </span>
              )}
            </Link>
          </div>
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
                  ? "text-white"
                  : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
              }`}
              style={
                selectedCategory === null
                  ? { backgroundColor: primaryColor ?? "#2563eb" }
                  : undefined
              }
            >
              All
            </button>
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                  selectedCategory === cat.id
                    ? "text-white"
                    : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                }`}
                style={
                  selectedCategory === cat.id
                    ? { backgroundColor: primaryColor ?? "#2563eb" }
                    : undefined
                }
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
                className="overflow-hidden rounded-lg border bg-white shadow-sm"
              >
                {product.image_url && (
                  /* eslint-disable-next-line @next/next/no-img-element -- presigned URL expires; next/image caching would break */
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="h-40 w-full object-cover"
                  />
                )}
                <div className="p-5">
                  <h3 className="text-sm font-semibold text-gray-900">
                    {product.name}
                  </h3>
                  {product.description && (
                    <p className="mt-1 line-clamp-2 text-sm text-gray-500">
                      {product.description}
                    </p>
                  )}
                  <p
                    className="mt-3 text-base font-bold"
                    style={{ color: secondaryColor ?? "#111827" }}
                  >
                    {product.price_amount} {product.effective_currency}
                  </p>
                  <button
                    onClick={() => handleAddToCart(product)}
                    className="mt-3 w-full rounded-lg py-2 text-sm font-medium text-white transition-colors hover:opacity-90"
                    style={{ backgroundColor: primaryColor ?? "#2563eb" }}
                  >
                    {addedId === product.id ? "Added!" : "Add to Cart"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
