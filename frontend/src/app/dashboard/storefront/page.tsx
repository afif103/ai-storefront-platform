"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { apiFetch } from "@/lib/api-client";
import { uploadFile } from "@/lib/upload";
import type { UploadProgress } from "@/lib/upload";

const PAYMENT_METHOD_CATALOG = [
  "cash",
  "knet",
  "bank_transfer",
  "cod",
  "manual",
] as const;

interface ShippingMethodRow {
  id: string;
  name: string;
  fee: string;
  active: boolean;
}

interface StorefrontConfig {
  id: string;
  logo_s3_key: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  hero_text: string | null;
  custom_css: Record<string, unknown> | null;
  payment_methods: { pos: string[]; online: string[] } | null;
  shipping: { methods: ShippingMethodRow[] } | null;
  created_at: string;
  updated_at: string | null;
}

interface TenantInfo {
  slug: string;
}

interface PublicConfig {
  logo_url: string | null;
}

const ACCEPTED_IMAGE_TYPES = "image/jpeg,image/png,image/webp";
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

function StorefrontSettingsContent() {
  const t = useTranslations("dashboardStorefront");
  const tPayment = useTranslations("paymentMethods");
  const paymentMethodLabels: Record<string, string> = {
    cash: tPayment("cash"),
    knet: tPayment("knet"),
    bank_transfer: tPayment("bank_transfer"),
    cod: tPayment("cod"),
    manual: tPayment("manual"),
  };
  const [config, setConfig] = useState<StorefrontConfig | null>(null);
  const [heroText, setHeroText] = useState("");
  const [primaryColor, setPrimaryColor] = useState("");
  const [secondaryColor, setSecondaryColor] = useState("");
  const [logoPreview, setLogoPreview] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Payment methods
  const [posMethods, setPosMethods] = useState<string[]>([]);
  const [onlineMethods, setOnlineMethods] = useState<string[]>([]);

  // Shipping/delivery methods
  const [shippingMethods, setShippingMethods] = useState<ShippingMethodRow[]>([]);

  // Logo upload state
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(
    null
  );
  const [uploadError, setUploadError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function fetchData() {
      // Fetch storefront config + tenant slug in parallel
      const [configResult, tenantResult] = await Promise.all([
        apiFetch<StorefrontConfig | null>("/api/v1/tenants/me/storefront"),
        apiFetch<TenantInfo>("/api/v1/tenants/me"),
      ]);

      if (configResult.ok && configResult.data) {
        const c = configResult.data;
        setConfig(c);
        setHeroText(c.hero_text ?? "");
        setPrimaryColor(c.primary_color ?? "");
        setSecondaryColor(c.secondary_color ?? "");
        setPosMethods(c.payment_methods?.pos ?? []);
        setOnlineMethods(c.payment_methods?.online ?? []);
        setShippingMethods(c.shipping?.methods ?? []);

        // Load existing logo via public config endpoint (returns presigned URL)
        if (c.logo_s3_key && tenantResult.ok) {
          const publicResult = await apiFetch<PublicConfig>(
            `/api/v1/storefront/${tenantResult.data.slug}/config`
          );
          if (publicResult.ok && publicResult.data.logo_url) {
            setLogoPreview(publicResult.data.logo_url);
          }
        }
      } else if (!configResult.ok) {
        setError(configResult.detail);
      }

      setLoading(false);
    }
    fetchData();
  }, []);

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError("");
    setSuccess("");

    if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
      setUploadError(t("uploadInvalidType"));
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setUploadError(t("uploadTooLarge"));
      return;
    }

    setUploading(true);
    setUploadProgress(null);

    // Show local preview immediately
    const objectUrl = URL.createObjectURL(file);
    const previousPreview = logoPreview;
    setLogoPreview(objectUrl);

    // 1. Request presigned URL + 2. PUT to S3
    const uploadResult = await uploadFile(file, {
      onProgress: setUploadProgress,
    });

    if (!uploadResult.ok) {
      setUploadError(uploadResult.detail);
      setLogoPreview(previousPreview);
      URL.revokeObjectURL(objectUrl);
      setUploading(false);
      setUploadProgress(null);
      return;
    }

    // 3. Update storefront config with the new logo S3 key
    const updateResult = await apiFetch<StorefrontConfig>(
      "/api/v1/tenants/me/storefront",
      {
        method: "PUT",
        body: JSON.stringify({ logo_s3_key: uploadResult.result.s3_key }),
      }
    );

    if (!updateResult.ok) {
      setUploadError(t("uploadSaveError", { error: updateResult.detail }));
      setUploading(false);
      setUploadProgress(null);
      return;
    }

    setConfig(updateResult.data);
    setSuccess(t("logoUpdated"));
    setUploading(false);
    setUploadProgress(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

    // Client guard: every delivery method must have a non-blank name.
    if (shippingMethods.some((m) => !m.name.trim())) {
      setError(t("shippingNameRequired"));
      setSubmitting(false);
      return;
    }

    const body: Record<string, unknown> = {};
    body.hero_text = heroText || null;
    body.primary_color = primaryColor || null;
    body.secondary_color = secondaryColor || null;
    body.payment_methods = { pos: posMethods, online: onlineMethods };
    body.shipping = {
      methods: shippingMethods.map((m) => ({
        id: m.id,
        name: m.name.trim(),
        fee: m.fee || "0",
        active: m.active,
      })),
    };

    const result = await apiFetch<StorefrontConfig>(
      "/api/v1/tenants/me/storefront",
      { method: "PUT", body: JSON.stringify(body) }
    );

    if (result.ok) {
      setConfig(result.data);
      setShippingMethods(result.data.shipping?.methods ?? []);
      setSuccess(t("settingsSaved"));
    } else {
      setError(
        typeof result.detail === "string"
          ? result.detail
          : JSON.stringify(result.detail)
      );
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

  return (
    <main className="mx-auto max-w-2xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-gray-900">{t("title")}</h1>
        <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
      </div>
        {error && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-700">
            {success}
          </div>
        )}

        {/* Logo Upload Section */}
        <div className="mb-6 rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            {t("sectionLogo")}
          </h2>

          <div className="mb-4">
            {logoPreview ? (
              /* eslint-disable-next-line @next/next/no-img-element -- presigned/object URL */
              <img
                src={logoPreview}
                alt={t("logoAlt")}
                className="h-20 w-20 rounded border border-gray-200 object-contain"
              />
            ) : (
              <div className="flex h-20 w-20 items-center justify-center rounded border border-dashed border-gray-300 bg-gray-50">
                <span className="text-xs text-gray-400">{t("noLogo")}</span>
              </div>
            )}
            {config?.logo_s3_key ? (
              <p className="mt-1 text-xs text-gray-500">{t("logoIsSet")}</p>
            ) : (
              <p className="mt-1 text-xs text-gray-500">{t("noLogoYet")}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("uploadLogoLabel")}{" "}
              <span className="ml-1 text-gray-400">
                {t("uploadLogoFormats")}
              </span>
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_IMAGE_TYPES}
              onChange={handleLogoUpload}
              disabled={uploading}
              className="block w-full text-sm text-gray-500 file:mr-4 file:rounded file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100 disabled:opacity-50"
            />
          </div>

          {uploading && uploadProgress && (
            <div className="mt-3">
              <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                <div
                  className="h-2 rounded-full bg-blue-600 transition-all"
                  style={{ width: `${uploadProgress.percent}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-gray-500">
                {t("uploadingProgress", { percent: uploadProgress.percent })}
              </p>
            </div>
          )}
          {uploading && !uploadProgress && (
            <p className="mt-2 text-xs text-gray-500">{t("preparingUpload")}</p>
          )}

          {uploadError && (
            <div className="mt-3 rounded border border-red-300 bg-red-50 p-2 text-xs text-red-700">
              {uploadError}
            </div>
          )}
        </div>

        {/* Branding Form */}
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border bg-white p-6 shadow-sm"
        >
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
            {t("sectionBranding")}
          </h2>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("heroText")}
            </label>
            <input
              type="text"
              value={heroText}
              onChange={(e) => setHeroText(e.target.value)}
              placeholder={t("heroTextPlaceholder")}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                {t("primaryColor")}
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  maxLength={7}
                  placeholder="#3B82F6"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                {primaryColor && /^#[0-9a-fA-F]{6}$/.test(primaryColor) && (
                  <div
                    className="h-8 w-8 shrink-0 rounded border border-gray-300"
                    style={{ backgroundColor: primaryColor }}
                  />
                )}
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                {t("secondaryColor")}
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  maxLength={7}
                  placeholder="#10B981"
                  value={secondaryColor}
                  onChange={(e) => setSecondaryColor(e.target.value)}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                {secondaryColor &&
                  /^#[0-9a-fA-F]{6}$/.test(secondaryColor) && (
                    <div
                      className="h-8 w-8 shrink-0 rounded border border-gray-300"
                      style={{ backgroundColor: secondaryColor }}
                    />
                  )}
              </div>
            </div>
          </div>

          {/* Payment Methods */}
          <div className="border-t pt-4">
            <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
              {t("sectionPayments")}
            </p>

            <div className="mb-4">
              <p className="mb-2 text-sm font-medium text-gray-700">
                {t("posMethods")}
              </p>
              <div className="flex flex-wrap gap-4">
                {PAYMENT_METHOD_CATALOG.map((code) => (
                  <label
                    key={code}
                    className="flex items-center gap-1.5 text-sm text-gray-700"
                  >
                    <input
                      type="checkbox"
                      checked={posMethods.includes(code)}
                      onChange={(e) =>
                        setPosMethods((prev) =>
                          e.target.checked
                            ? [...prev, code]
                            : prev.filter((m) => m !== code)
                        )
                      }
                      className="rounded border-gray-300"
                    />
                    {paymentMethodLabels[code] ?? code}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 text-sm font-medium text-gray-700">
                {t("onlineMethods")}
              </p>
              <div className="flex flex-wrap gap-4">
                {PAYMENT_METHOD_CATALOG.map((code) => (
                  <label
                    key={code}
                    className="flex items-center gap-1.5 text-sm text-gray-700"
                  >
                    <input
                      type="checkbox"
                      checked={onlineMethods.includes(code)}
                      onChange={(e) =>
                        setOnlineMethods((prev) =>
                          e.target.checked
                            ? [...prev, code]
                            : prev.filter((m) => m !== code)
                        )
                      }
                      className="rounded border-gray-300"
                    />
                    {paymentMethodLabels[code] ?? code}
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Delivery Methods */}
          <div className="border-t pt-4">
            <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
              {t("sectionShipping")}
            </p>

            {shippingMethods.length === 0 ? (
              <p className="mb-3 text-sm text-gray-400">
                {t("noShippingMethods")}
              </p>
            ) : (
              <div className="mb-3 space-y-2">
                {shippingMethods.map((method) => (
                  <div
                    key={method.id}
                    className="flex flex-wrap items-center gap-2"
                  >
                    <input
                      type="text"
                      value={method.name}
                      onChange={(e) =>
                        setShippingMethods((prev) =>
                          prev.map((m) =>
                            m.id === method.id
                              ? { ...m, name: e.target.value }
                              : m
                          )
                        )
                      }
                      placeholder={t("shippingMethodName")}
                      className="min-w-0 flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                    />
                    <input
                      type="number"
                      min="0"
                      step="0.001"
                      value={method.fee}
                      onChange={(e) =>
                        setShippingMethods((prev) =>
                          prev.map((m) =>
                            m.id === method.id
                              ? { ...m, fee: e.target.value }
                              : m
                          )
                        )
                      }
                      placeholder={t("shippingMethodFee")}
                      className="w-28 rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                    />
                    <label className="flex items-center gap-1.5 text-sm text-gray-700">
                      <input
                        type="checkbox"
                        checked={method.active}
                        onChange={(e) =>
                          setShippingMethods((prev) =>
                            prev.map((m) =>
                              m.id === method.id
                                ? { ...m, active: e.target.checked }
                                : m
                            )
                          )
                        }
                        className="rounded border-gray-300"
                      />
                      {t("shippingMethodActive")}
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        setShippingMethods((prev) =>
                          prev.filter((m) => m.id !== method.id)
                        )
                      }
                      className="rounded px-2 py-1 text-sm text-red-600 hover:bg-red-50"
                    >
                      {t("removeShippingMethod")}
                    </button>
                  </div>
                ))}
              </div>
            )}

            <button
              type="button"
              onClick={() =>
                setShippingMethods((prev) => [
                  ...prev,
                  { id: crypto.randomUUID(), name: "", fee: "", active: true },
                ])
              }
              className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              {t("addShippingMethod")}
            </button>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? t("saving") : t("saveBranding")}
            </button>
          </div>
        </form>
    </main>
  );
}

export default function StorefrontSettingsPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <StorefrontSettingsContent />
      </DashboardShell>
    </RequireAuth>
  );
}
