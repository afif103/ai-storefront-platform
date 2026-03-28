"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useAuth } from "@/hooks/use-auth";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { accessToken, isLoading, bootstrap } = useAuth();
  const router = useRouter();
  const t = useTranslations("dashboard");

  useEffect(() => {
    if (isLoading) return;
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    if (bootstrap && bootstrap.memberships.length === 0) {
      router.replace("/onboarding");
    }
  }, [accessToken, isLoading, bootstrap, router]);

  if (isLoading || !accessToken || !bootstrap) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">{t("loading")}</p>
      </div>
    );
  }

  if (bootstrap.memberships.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">{t("loading")}</p>
      </div>
    );
  }

  return <>{children}</>;
}
