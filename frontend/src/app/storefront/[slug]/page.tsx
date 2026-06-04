"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { apiFetch } from "@/lib/api-client";
import { initAnalytics, track, flush } from "@/lib/analytics";
import { useVisit } from "@/hooks/use-visit";
import { cartLineKey, useCart } from "@/hooks/use-cart";
import { StorefrontChat } from "@/components/storefront-chat";
import { LocaleSwitcher } from "@/components/locale-switcher";

interface Category {
  id: string;
  name: string;
  description: string | null;
  name_ar: string | null;
  description_ar: string | null;
  sort_order: number;
}

interface PublicVariant {
  id: string;
  name: string;
  size: string | null;
  color: string | null;
  price_amount: string | null;
  in_stock: boolean;
}

interface PublicProduct {
  id: string;
  category_id: string | null;
  name: string;
  description: string | null;
  name_ar: string | null;
  description_ar: string | null;
  price_amount: string;
  effective_currency: string;
  sort_order: number;
  image_url: string | null;
  in_stock: boolean;
  stock_display: string | null;
  variants: PublicVariant[];
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

function variantLabel(v: PublicVariant): string {
  const extra = [v.size, v.color].filter(Boolean).join(" / ");
  return extra ? `${v.name} (${extra})` : v.name;
}

export default function StorefrontPage() {
  const params = useParams();
  const slug = params.slug as string;
  const t = useTranslations("storefront");
  const locale = useLocale();

  useVisit(slug);
  const cart = useCart(slug);

  // Analytics: init tracker + fire storefront_view once on mount
  useEffect(() => {
    initAnalytics(slug);
    track("storefront_view", { path: window.location.pathname });
    return () => flush();
  }, [slug]);

  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<PublicProduct[]>([]);
  const [config, setConfig] = useState<StorefrontConfig | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [filterLoading, setFilterLoading] = useState(false);
  const [addedId, setAddedId] = useState<string | null>(null);
  const [selectedVariants, setSelectedVariants] = useState<
    Record<string, string>
  >({});

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

  function resolveVariant(product: PublicProduct): PublicVariant | null {
    if (product.variants.length === 0) return null;
    const chosen = product.variants.find(
      (v) => v.id === selectedVariants[product.id]
    );
    if (chosen) return chosen;
    return product.variants.find((v) => v.in_stock) ?? product.variants[0];
  }

  function isAvailable(product: PublicProduct): boolean {
    if (product.variants.length === 0) return product.in_stock;
    return resolveVariant(product)?.in_stock ?? false;
  }

  function currentLineKey(product: PublicProduct): string {
    return cartLineKey({
      catalogItemId: product.id,
      variantId: resolveVariant(product)?.id ?? null,
    });
  }

  function handleAddToCart(product: PublicProduct) {
    const variant = resolveVariant(product);
    cart.addItem(
      {
        catalogItemId: product.id,
        variantId: variant?.id ?? null,
        name: (locale === "ar" && product.name_ar) ? product.name_ar : product.name,
        variantName: variant ? variantLabel(variant) : null,
        priceAmount: variant?.price_amount ?? product.price_amount,
        currency: product.effective_currency,
      },
      1
    );
    track("product_view", { product_id: product.id });
    track("add_to_cart", {
      product_id: product.id,
      ...(variant ? { variant_id: variant.id } : {}),
      qty: 1,
    });
    setAddedId(currentLineKey(product));
    setTimeout(() => setAddedId(null), 1200);
  }

  const primaryColor = config?.primary_color ?? undefined;
  const secondaryColor = config?.secondary_color ?? undefined;
  const headerTextColor = primaryColor ? "#ffffff" : "#111827";

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-400">{t("loadingStorefront")}</p>
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
              {t("donate")}
            </Link>
            <Link
              href={`/storefront/${slug}/pledge`}
              className="rounded-full border px-4 py-1.5 text-sm font-medium transition-colors hover:opacity-80"
              style={{
                borderColor: headerTextColor,
                color: headerTextColor,
              }}
            >
              {t("pledge")}
            </Link>

            <LocaleSwitcher
              className="rounded-full border px-3 py-1.5 text-sm font-medium transition-colors hover:opacity-80"
              style={{ borderColor: headerTextColor, color: headerTextColor }}
            />

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
                  className="absolute -right-1 rtl:-right-auto rtl:-left-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold text-white"
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
              {t("allCategories")}
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
                {(locale === "ar" && cat.name_ar) ? cat.name_ar : cat.name}
              </button>
            ))}
          </div>
        )}

        {/* Product grid */}
        {filterLoading ? (
          <p className="text-sm text-gray-400">{t("loading")}</p>
        ) : products.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">{t("noProducts")}</p>
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
                    alt={(locale === "ar" && product.name_ar) ? product.name_ar : product.name}
                    className="h-40 w-full object-contain bg-gray-100"
                  />
                )}
                <div className="p-5">
                  <h3 className="text-sm font-semibold text-gray-900">
                    {(locale === "ar" && product.name_ar) ? product.name_ar : product.name}
                  </h3>
                  {(() => {
                    const desc = (locale === "ar" && product.description_ar) ? product.description_ar : product.description;
                    return desc ? (
                      <p className="mt-1 line-clamp-2 text-sm text-gray-500">
                        {desc}
                      </p>
                    ) : null;
                  })()}
                  {product.variants.length > 0 && (
                    <select
                      aria-label={t("variant")}
                      value={resolveVariant(product)?.id ?? ""}
                      onChange={(e) =>
                        setSelectedVariants((prev) => ({
                          ...prev,
                          [product.id]: e.target.value,
                        }))
                      }
                      className="mt-3 w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
                    >
                      {product.variants.map((pv) => (
                        <option key={pv.id} value={pv.id} disabled={!pv.in_stock}>
                          {variantLabel(pv)}
                        </option>
                      ))}
                    </select>
                  )}
                  <p
                    className="mt-3 text-base font-bold"
                    style={{ color: secondaryColor ?? "#111827" }}
                  >
                    {resolveVariant(product)?.price_amount ?? product.price_amount}{" "}
                    {product.effective_currency}
                  </p>
                  {product.variants.length === 0 && product.stock_display && (
                    <p
                      className={`mt-1 text-xs font-medium ${
                        product.in_stock ? "text-gray-500" : "text-red-600"
                      }`}
                    >
                      {product.stock_display}
                    </p>
                  )}
                  <button
                    onClick={() => handleAddToCart(product)}
                    disabled={!isAvailable(product)}
                    className="mt-3 w-full rounded-lg py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    style={{ backgroundColor: primaryColor ?? "#2563eb" }}
                  >
                    {!isAvailable(product)
                      ? t("outOfStock")
                      : addedId === currentLineKey(product)
                        ? t("added")
                        : t("addToCart")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <StorefrontChat slug={slug} primaryColor={primaryColor} />
    </div>
  );
}
