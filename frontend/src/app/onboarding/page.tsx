"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod/v4";
import { useTranslations } from "next-intl";
import { useAuth } from "@/hooks/use-auth";
import { apiFetch } from "@/lib/api-client";
import { LocaleSwitcher } from "@/components/locale-switcher";

const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/;
const CURRENCIES = ["PHP", "KWD", "USD", "EUR", "SAR", "AED", "BHD", "QAR", "OMR", "GBP"];

function nameToSlug(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

const BACKEND_FIELD_MAP: Record<string, string> = {
  name: "storeName",
  slug: "slug",
  default_currency: "currency",
};

function mapBackendErrors(detail: unknown): Record<string, string> {
  if (!Array.isArray(detail)) return {};
  const mapped: Record<string, string> = {};
  for (const err of detail) {
    if (typeof err !== "object" || !err) continue;
    const loc = (err as { loc?: string[] }).loc;
    const msg = (err as { msg?: string }).msg;
    if (!Array.isArray(loc) || typeof msg !== "string") continue;
    const field = loc[loc.length - 1];
    const key = BACKEND_FIELD_MAP[field] ?? field;
    if (!mapped[key]) mapped[key] = msg;
  }
  return mapped;
}

export default function OnboardingPage() {
  const { accessToken, isLoading, bootstrap, logout, refreshBootstrap } =
    useAuth();
  const router = useRouter();
  const t = useTranslations("onboarding");

  const [acceptError, setAcceptError] = useState("");
  const [isAccepting, setIsAccepting] = useState(false);

  const [storeName, setStoreName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [currency, setCurrency] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [createError, setCreateError] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    if (isLoading) return;
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    if (bootstrap && bootstrap.memberships.length > 0) {
      router.replace("/dashboard");
    }
  }, [accessToken, isLoading, bootstrap, router]);

  if (isLoading || !accessToken || !bootstrap) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500">{t("loading")}</p>
      </div>
    );
  }

  if (bootstrap.memberships.length > 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500">{t("loading")}</p>
      </div>
    );
  }

  const pendingCount = bootstrap.pending_invitations;

  async function handleAcceptInvitations() {
    setAcceptError("");
    setIsAccepting(true);

    try {
      const res = await apiFetch("/api/v1/auth/accept-invite", {
        method: "POST",
      });
      if (!res.ok) {
        setAcceptError(res.detail || t("acceptFailed"));
        return;
      }
      await refreshBootstrap();
      router.push("/dashboard");
    } catch (err) {
      setAcceptError(err instanceof Error ? err.message : t("acceptFailed"));
    } finally {
      setIsAccepting(false);
    }
  }

  const createStoreSchema = z.object({
    storeName: z.string().min(1, t("storeNameRequired")).max(255),
    slug: z.string().regex(SLUG_PATTERN, t("slugInvalid")),
    currency: z.enum(CURRENCIES as [string, ...string[]], {
      message: t("currencyRequired"),
    }),
  });

  function handleNameChange(value: string) {
    setStoreName(value);
    if (!slugTouched) {
      setSlug(nameToSlug(value));
    }
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.storeName;
      return next;
    });
  }

  function handleSlugChange(value: string) {
    const lower = value.toLowerCase();
    setSlug(lower);
    setSlugTouched(lower.length > 0);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.slug;
      return next;
    });
  }

  function handleCurrencyChange(value: string) {
    setCurrency(value);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.currency;
      return next;
    });
  }

  async function handleCreateStore(e: React.FormEvent) {
    e.preventDefault();
    setFieldErrors({});
    setCreateError("");

    const result = createStoreSchema.safeParse({
      storeName: storeName.trim(),
      slug,
      currency,
    });
    if (!result.success) {
      const errs: Record<string, string> = {};
      for (const issue of result.error.issues) {
        const key = issue.path.join(".");
        if (!errs[key]) errs[key] = issue.message;
      }
      setFieldErrors(errs);
      return;
    }

    setIsCreating(true);
    try {
      const res = await apiFetch("/api/v1/tenants", {
        method: "POST",
        body: JSON.stringify({
          name: storeName.trim(),
          slug,
          default_currency: currency,
        }),
      });

      if (!res.ok) {
        if (res.status === 409) {
          setFieldErrors({ slug: t("slugTaken") });
        } else if (res.status === 422) {
          const mapped = mapBackendErrors(res.detail);
          if (Object.keys(mapped).length > 0) {
            setFieldErrors(mapped);
          } else {
            setCreateError(
              typeof res.detail === "string" ? res.detail : t("createFailed"),
            );
          }
        } else {
          setCreateError(
            typeof res.detail === "string" ? res.detail : t("createFailed"),
          );
        }
        return;
      }

      await refreshBootstrap();
      router.push("/dashboard");
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : t("createFailed"));
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-lg space-y-8 rounded-lg bg-white p-8 shadow">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>
          <div className="flex items-center gap-3">
            <LocaleSwitcher className="text-sm text-gray-500 hover:text-gray-700" />
            <button
              type="button"
              onClick={logout}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              {t("signOut")}
            </button>
          </div>
        </div>

        {pendingCount > 0 && (
          <section className="space-y-3 rounded border border-blue-200 bg-blue-50 p-4">
            <h2 className="text-lg font-semibold text-gray-900">
              {t("pendingInvitationsHeading")}
            </h2>
            <p className="text-sm text-gray-600">
              {t("pendingInvitationsDescription", { count: pendingCount })}
            </p>

            {acceptError && (
              <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {acceptError}
              </div>
            )}

            <button
              type="button"
              onClick={handleAcceptInvitations}
              disabled={isAccepting}
              className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
            >
              {isAccepting
                ? t("accepting")
                : t("acceptAll", { count: pendingCount })}
            </button>
          </section>
        )}

        <section className="space-y-3">
          {pendingCount > 0 ? (
            <h2 className="text-lg font-semibold text-gray-900">
              {t("orCreateYourOwn")}
            </h2>
          ) : (
            <>
              <h2 className="text-lg font-semibold text-gray-900">
                {t("createStoreHeading")}
              </h2>
              <p className="text-sm text-gray-600">
                {t("createStoreDescription")}
              </p>
            </>
          )}

          {createError && (
            <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {createError}
            </div>
          )}

          <form onSubmit={handleCreateStore} className="space-y-4">
            <div>
              <label
                htmlFor="storeName"
                className="block text-sm font-medium text-gray-700"
              >
                {t("storeName")}
              </label>
              <input
                id="storeName"
                type="text"
                value={storeName}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder={t("storeNamePlaceholder")}
                className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              {fieldErrors.storeName && (
                <p className="mt-1 text-sm text-red-600">
                  {fieldErrors.storeName}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="slug"
                className="block text-sm font-medium text-gray-700"
              >
                {t("slug")}
              </label>
              <input
                id="slug"
                type="text"
                value={slug}
                onChange={(e) => handleSlugChange(e.target.value)}
                className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 font-mono text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-500">{t("slugHint")}</p>
              {fieldErrors.slug && (
                <p className="mt-1 text-sm text-red-600">
                  {fieldErrors.slug}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="currency"
                className="block text-sm font-medium text-gray-700"
              >
                {t("currency")}
              </label>
              <select
                id="currency"
                value={currency}
                onChange={(e) => handleCurrencyChange(e.target.value)}
                className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="">{t("currencyPlaceholder")}</option>
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              {fieldErrors.currency && (
                <p className="mt-1 text-sm text-red-600">
                  {fieldErrors.currency}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isCreating}
              className="w-full rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
            >
              {isCreating ? t("creating") : t("createStore")}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
