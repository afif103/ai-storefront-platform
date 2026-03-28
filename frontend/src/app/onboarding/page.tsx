"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useAuth } from "@/hooks/use-auth";
import { apiFetch } from "@/lib/api-client";
import { LocaleSwitcher } from "@/components/locale-switcher";

export default function OnboardingPage() {
  const { accessToken, isLoading, bootstrap, logout, refreshBootstrap } =
    useAuth();
  const router = useRouter();
  const t = useTranslations("onboarding");

  const [acceptError, setAcceptError] = useState("");
  const [isAccepting, setIsAccepting] = useState(false);

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

          <div className="rounded border border-dashed border-gray-300 p-6 text-center text-sm text-gray-400">
            {t("createStoreComingSoon")}
          </div>
        </section>
      </div>
    </div>
  );
}
