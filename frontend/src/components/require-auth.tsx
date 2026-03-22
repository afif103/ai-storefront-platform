"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useAuth } from "@/hooks/use-auth";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { accessToken, isLoading } = useAuth();
  const router = useRouter();
  const t = useTranslations("dashboard");

  useEffect(() => {
    if (!isLoading && !accessToken) {
      router.replace("/login");
    }
  }, [accessToken, isLoading, router]);

  if (isLoading || !accessToken) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">{t("loading")}</p>
      </div>
    );
  }

  return <>{children}</>;
}
